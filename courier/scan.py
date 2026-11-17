import frappe

from courier import state_machine
from courier.signing import read_token
from courier.state_machine import ScanError


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


def add_event(parcel, scan_type, status, hub=None, proof=None):
    seq = frappe.db.count("Scan Event", {"parcel": parcel.name}) + 1
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
            "scan_key": f"{parcel.name}:{status}",
        }
    ).insert(ignore_permissions=True)
    parcel.db_set("status", status)


def process_scan(token, scan_type, hub=None, proof=None):
    name = read_token(token, get_secret())
    if not name or not frappe.db.exists("Parcel", name):
        frappe.throw("Invalid barcode")

    # lock the row so two scans of the same parcel run one after another
    parcel = frappe.get_doc("Parcel", name, for_update=True)

    if scan_type == "pickup" and parcel.direction == "Forward" and parcel.payment_status != "Paid":
        frappe.throw("Payment is not confirmed for this parcel")

    status = current_status(parcel.name)
    try:
        action, new_status = state_machine.decide(
            parcel.direction,
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
    parcel = frappe.get_doc("Parcel", parcel_name, for_update=True)
    if parcel.owner != user:
        frappe.throw("Not your parcel", frappe.PermissionError)
    if current_status(parcel.name) != "Delivered":
        frappe.throw("Only a delivered parcel can be returned")
    parcel.db_set("direction", "Return")
    add_event(parcel, "return_request", "Return Requested")
    return parcel.name
