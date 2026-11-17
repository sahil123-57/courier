import frappe


def on_scan_event(doc, method=None):
    frappe.enqueue(
        "courier.notify.send_email",
        event=doc.name,
        enqueue_after_commit=True,
    )


def send_email(event):
    ev = frappe.get_doc("Scan Event", event)
    owner = frappe.db.get_value("Parcel", ev.parcel, "owner")
    frappe.sendmail(
        recipients=[owner],
        subject=f"Parcel {ev.parcel}: {ev.status}",
        message=f"Your parcel {ev.parcel} is now: {ev.status}",
    )
