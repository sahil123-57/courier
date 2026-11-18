import json

import frappe

from courier import payment, pricing, scan
from courier.signing import verify_webhook


def login_required():
    if frappe.session.user == "Guest":
        frappe.throw("Please login", frappe.PermissionError)


def my_parcel(name):
    parcel = frappe.get_doc("Parcel", name)
    if parcel.owner != frappe.session.user:
        frappe.throw("Not your parcel", frappe.PermissionError)
    return parcel


@frappe.whitelist()
def get_quote(origin_city, destination_city, service_level, weight_kg):
    login_required()
    return pricing.get_amount(origin_city, destination_city, service_level, float(weight_kg))


@frappe.whitelist()
def book_parcel(data):
    login_required()
    data = frappe.parse_json(data)

    # same key from the same user = same parcel (double click, retry)
    key = f"{frappe.session.user}:{data.get('booking_key')}"
    name = frappe.db.get_value("Parcel", {"booking_key": key})

    if name:
        parcel = frappe.get_doc("Parcel", name)
    else:
        weight = float(data.get("weight_kg"))
        parcel = frappe.get_doc(
            {
                "doctype": "Parcel",
                "booking_key": key,
                "sender_name": data.get("sender_name"),
                "sender_phone": data.get("sender_phone"),
                "sender_address": data.get("sender_address"),
                "origin_city": data.get("origin_city"),
                "recipient_name": data.get("recipient_name"),
                "recipient_phone": data.get("recipient_phone"),
                "recipient_address": data.get("recipient_address"),
                "destination_city": data.get("destination_city"),
                "weight_kg": weight,
                "service_level": data.get("service_level"),
                "amount": pricing.get_amount(
                    data.get("origin_city"), data.get("destination_city"), data.get("service_level"), weight
                ),
                "origin_hub": pricing.hub_for_city(data.get("origin_city")),
                "destination_hub": pricing.hub_for_city(data.get("destination_city")),
            }
        ).insert(ignore_permissions=True)

    order_id = payment.create_order(parcel)
    return {
        "parcel": parcel.name,
        "amount": parcel.amount,
        "order_id": order_id,
        "key_id": frappe.conf.get("razorpay_key_id"),
    }


@frappe.whitelist()
def my_parcels():
    login_required()
    return frappe.get_all(
        "Parcel",
        filters={"owner": frappe.session.user},
        fields=["name", "recipient_name", "destination_city", "status", "payment_status", "creation"],
        order_by="creation desc",
    )


@frappe.whitelist()
def track_parcel(name):
    parcel = my_parcel(name)
    events = frappe.get_all(
        "Scan Event",
        filters={"parcel": name},
        fields=["status", "hub", "creation"],
        order_by="seq asc",
    )
    return {"parcel": parcel.name, "status": scan.current_status(name), "events": events}


@frappe.whitelist()
def get_label(name):
    parcel = my_parcel(name)
    if parcel.payment_status != "Paid":
        frappe.throw("Label is available after payment")
    return {
        "parcel": parcel.name,
        "token": parcel.token,
        "sender": [parcel.sender_name, parcel.sender_phone, parcel.sender_address, parcel.origin_city],
        "recipient": [parcel.recipient_name, parcel.recipient_phone, parcel.recipient_address, parcel.destination_city],
        "weight_kg": parcel.weight_kg,
        "service_level": parcel.service_level,
    }


@frappe.whitelist()
def raise_return(name):
    login_required()
    return scan.start_return(name, frappe.session.user)


@frappe.whitelist()
def scan_parcel(token, scan_type, proof=None):
    if "Delivery Agent" not in frappe.get_roles():
        frappe.throw("Only delivery agents can scan", frappe.PermissionError)

    # hub comes from the agent's own record, not from the phone
    agent = frappe.db.get_value(
        "Delivery Agent", {"user": frappe.session.user, "active": 1}, ["hub"], as_dict=True
    )
    if not agent:
        frappe.throw("You are not set up as an active delivery agent")
    agent_hub = agent.hub
    return scan.process_scan(token, scan_type, hub=agent_hub, proof=proof)


@frappe.whitelist(allow_guest=True)
def razorpay_webhook():
    body = frappe.request.get_data()
    signature = frappe.get_request_header("X-Razorpay-Signature")
    if not verify_webhook(body, signature, frappe.conf.get("razorpay_webhook_secret")):
        frappe.throw("Bad signature", frappe.AuthenticationError)

    data = json.loads(body)
    if data.get("event") in ("payment.captured", "order.paid"):
        pay = data["payload"]["payment"]["entity"]
        payment.mark_paid(pay["order_id"], pay["id"])
    return "ok"
@frappe.whitelist()
def ops_action(name, action, reason=""):
    roles = frappe.get_roles()
    if "Courier Manager" not in roles and "System Manager" not in roles:
        frappe.throw("Only ops can do this", frappe.PermissionError)
    scan.ops_action(name, action, reason)
    return scan.current_status(name)


@frappe.whitelist()
def dev_simulate_payment(name):
    # development only, stands in for the razorpay webhook
    if not frappe.conf.get("developer_mode"):
        frappe.throw("Only available in developer mode")
    parcel = my_parcel(name)
    payment.mark_paid(parcel.razorpay_order_id, "pay_simulated")
    return "ok"
