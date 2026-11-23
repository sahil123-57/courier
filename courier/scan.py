import frappe

from courier import state_machine
from courier.signing import make_token, read_token
from courier.state_machine import ScanError

FAILABLE = ("Out for Delivery", "Return Out for Delivery")
HOLDABLE = ("In at Origin Hub", "In at Destination Hub",
            "Return In at Pickup Hub", "Return In at Drop Hub")


def get_secret():
    secret = frappe.conf.get("courier_secret")
    if not secret:
        frappe.throw("courier_secret is not set in site_config.json")
    return secret


def current_status(parcel_name):
    # the log is the truth, Parcel.status is only a copy of it
    last = frappe.get_all(
        "Scan Event",
        filters={"parcel": parcel_name},
        fields=["status"],
        order_by="seq desc",
        limit=1,
    )
    return last[0].status if last else "Unpaid"


def add_event(parcel, scan_type, status, hub=None, proof=None, note=None, unique=False):
    seq = frappe.db.count("Scan Event", {"parcel": parcel.name}) + 1
    key = f"{parcel.name}:{status}"
    if unique:
        # exceptions can repeat (fail, retry, fail again), so the key needs the seq
        key = f"{key}:{seq}"

    frappe.get_doc(
        {
            "doctype": "Scan Event",
            "parcel": parcel.name,
            "seq": seq,
            "scan_type": scan_type,
            "status": status,
            "hub": hub,
            "scanned_by": frappe.session.user,
            "proof": proof,
            "note": note,
            "scan_key": key,
        }
    ).insert(ignore_permissions=True)
    parcel.db_set("status", status)


def process_scan(token, scan_type, hub=None, proof=None):
    name = read_token(token, get_secret())
    if not name or not frappe.db.exists("Parcel", name):
        frappe.throw("Invalid barcode")

    # lock the row so two scans of the same parcel run one after another
    parcel = frappe.get_doc("Parcel", name, for_update=True)

    # a return needs no payment, the order was already paid for
    if scan_type == "pickup" and not parcel.is_return and parcel.payment_status != "Paid":
        frappe.throw("Payment is not confirmed for this parcel")

    direction = "Return" if parcel.is_return else "Forward"
    status = current_status(parcel.name)
    try:
        action, new_status = state_machine.decide(
            direction,
            status,
            scan_type,
            hub,
            parcel.origin_hub,
            parcel.destination_hub,
        )
    except ScanError as e:
        frappe.throw(str(e))

    if action == "duplicate":
        return {"parcel": parcel.name, "status": status, "duplicate": True}

    add_event(parcel, scan_type, new_status, hub=hub, proof=proof if scan_type == "deliver" else None)
    return {"parcel": parcel.name, "status": new_status, "duplicate": False}


def start_return(parcel_name, user):
    """A return is a second parcel on the same order. The first one stays Delivered."""
    original = frappe.get_doc("Parcel", parcel_name, for_update=True)
    if original.owner != user:
        frappe.throw("Not your parcel", frappe.PermissionError)
    if original.is_return:
        frappe.throw("A return cannot be returned")
    if current_status(original.name) != "Delivered":
        frappe.throw("Only a delivered parcel can be returned")
    if frappe.db.exists("Parcel", {"return_against": original.name}):
        frappe.throw("A return was already raised for this parcel")

    # sender and recipient swap, and so do the two hubs
    ret = frappe.get_doc(
        {
            "doctype": "Parcel",
            "is_return": 1,
            "return_against": original.name,
            "booking_key": f"return:{original.name}",
            "sender_name": original.recipient_name,
            "sender_phone": original.recipient_phone,
            "sender_address": original.recipient_address,
            "origin_city": original.destination_city,
            "recipient_name": original.sender_name,
            "recipient_phone": original.sender_phone,
            "recipient_address": original.sender_address,
            "destination_city": original.origin_city,
            "weight_kg": original.weight_kg,
            "service_level": original.service_level,
            "amount": 0,
            "payment_status": "Not Needed",
            "origin_hub": original.destination_hub,
            "destination_hub": original.origin_hub,
        }
    ).insert(ignore_permissions=True)

    # the return belongs to the same customer and gets its own barcode
    frappe.db.set_value("Parcel", ret.name, "owner", original.owner)
    ret.db_set("token", make_token(ret.name, get_secret()))
    add_event(ret, "return_request", "Return Requested")
    return ret.name


def status_before_last(parcel_name):
    last_two = frappe.get_all(
        "Scan Event",
        filters={"parcel": parcel_name},
        fields=["status"],
        order_by="seq desc",
        limit=2,
    )
    return last_two[1].status


def ops_action(parcel_name, action, reason=""):
    # used by ops from Desk, still goes through the log
    parcel = frappe.get_doc("Parcel", parcel_name, for_update=True)
    status = current_status(parcel.name)

    if action == "fail_delivery" and status in FAILABLE:
        new_status = "Delivery Failed"
    elif action == "hold" and status in HOLDABLE:
        new_status = "On Hold"
    elif action == "resume" and status in ("Delivery Failed", "On Hold"):
        new_status = status_before_last(parcel.name)
    else:
        frappe.throw(f"Cannot do '{action}' while the parcel is '{status}'")

    add_event(parcel, action, new_status, note=reason, unique=True)
