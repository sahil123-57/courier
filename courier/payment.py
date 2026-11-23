import json

import frappe
import requests

from courier.scan import add_event, get_secret
from courier.signing import make_token


def create_order(parcel):
    if parcel.razorpay_order_id:
        return parcel.razorpay_order_id

    if not frappe.conf.get("razorpay_key_id") and frappe.conf.get("developer_mode"):
        order = {"id": "order_sim_" + frappe.generate_hash(length=10), "simulated": True}
    else:
        res = requests.post(
            "https://api.razorpay.com/v1/orders",
            auth=(frappe.conf.get("razorpay_key_id"), frappe.conf.get("razorpay_key_secret")),
            json={
                "amount": int(parcel.amount * 100),
                "currency": "INR",
                "receipt": parcel.name,
            },
            timeout=20,
        )
        res.raise_for_status()
        order = res.json()

    frappe.get_doc(
        {
            "doctype": "Integration Request",
            "integration_request_service": "Razorpay",
            "request_id": order["id"],
            "reference_doctype": "Parcel",
            "reference_docname": parcel.name,
            "is_remote_request": 1,
            "status": "Queued",
            "data": json.dumps(order),
        }
    ).insert(ignore_permissions=True)

    parcel.db_set("razorpay_order_id", order["id"])
    return order["id"]


def mark_paid(order_id, payment_id):
    name = frappe.db.get_value("Parcel", {"razorpay_order_id": order_id})
    if not name:
        return

    parcel = frappe.get_doc("Parcel", name, for_update=True)
    if parcel.payment_status == "Paid":
        return

    parcel.db_set("payment_status", "Paid")
    parcel.db_set("razorpay_payment_id", payment_id)
    parcel.db_set("token", make_token(parcel.name, get_secret()))
    add_event(parcel, "payment", "Booked & Paid")

    frappe.db.set_value("Integration Request", {"request_id": order_id}, "status", "Completed")
