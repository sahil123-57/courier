import frappe

from courier.scan import add_event, get_secret
from courier.signing import make_token
from razorpay_frappe.razorpay_integration.doctype.razorpay_order.razorpay_order import RazorpayOrder


def razorpay_key():
    return frappe.db.get_single_value("Razorpay Settings", "key_id")


def start_payment(parcel):
    if not razorpay_key() and frappe.conf.get("developer_mode"):
        return {"key_id": None, "order_id": None}

    order_id = frappe.db.get_value(
        "Razorpay Order",
        {"ref_dt": "Parcel", "ref_dn": parcel.name, "status": "Pending"},
        "order_id",
    )
    if order_id:
        return {"key_id": razorpay_key(), "order_id": order_id}

    return RazorpayOrder.initiate(
        parcel.amount, "INR", {"parcel": parcel.name}, ref_dt="Parcel", ref_dn=parcel.name
    )


def on_order_update(doc, method=None):
    if doc.ref_dt == "Parcel" and doc.status == "Paid":
        mark_paid(doc)


def mark_paid(order):
    parcel = frappe.get_doc("Parcel", order.ref_dn, for_update=True)
    if parcel.payment_status == "Paid":
        return

    parcel.db_set("payment_status", "Paid")
    parcel.db_set("razorpay_order_id", order.order_id)
    parcel.db_set("razorpay_payment_id", order.payment_id)
    parcel.db_set("token", make_token(parcel.name, get_secret()))
    add_event(parcel, "payment", "Booked & Paid")
