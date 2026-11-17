import frappe

try:
    from frappe.tests import IntegrationTestCase as BaseTestCase  # newer frappe
except ImportError:
    from frappe.tests.utils import FrappeTestCase as BaseTestCase  # v15

from courier import payment, scan
from courier.scan import current_status, process_scan, start_return
from courier.signing import make_token


def make_hub(name, city):
    if not frappe.db.exists("Hub", name):
        frappe.get_doc({"doctype": "Hub", "hub_name": name, "city": city}).insert()
    return name


def make_parcel(paid=True):
    parcel = frappe.get_doc(
        {
            "doctype": "Parcel",
            "sender_name": "Meena",
            "origin_city": "Delhi",
            "recipient_name": "Ravi",
            "destination_city": "Pune",
            "weight_kg": 2,
            "amount": 300,
            "origin_hub": make_hub("Delhi Hub", "Delhi"),
            "destination_hub": make_hub("Pune Hub", "Pune"),
            "razorpay_order_id": frappe.generate_hash(length=10),
        }
    ).insert()
    if paid:
        payment.mark_paid(parcel.razorpay_order_id, "pay_test")
        parcel.reload()
    return parcel


def do_scan(parcel, scan_type, hub=None):
    return process_scan(make_token(parcel.name, "test-secret"), scan_type, hub)


def walk_forward(parcel):
    do_scan(parcel, "pickup")
    do_scan(parcel, "hub_in", "Delhi Hub")
    do_scan(parcel, "hub_out", "Delhi Hub")
    do_scan(parcel, "hub_in", "Pune Hub")
    do_scan(parcel, "hub_out", "Pune Hub")
    do_scan(parcel, "deliver")


class TestScans(BaseTestCase):
    def setUp(self):
        frappe.conf.courier_secret = "test-secret"

    def test_full_forward_flow(self):
        parcel = make_parcel()
        walk_forward(parcel)
        self.assertEqual(current_status(parcel.name), "Delivered")
        events = frappe.get_all("Scan Event", {"parcel": parcel.name})
        self.assertEqual(len(events), 7)  # payment + 6 scans

    def test_wrong_hub_rejected(self):
        parcel = make_parcel()
        do_scan(parcel, "pickup")
        self.assertRaises(frappe.ValidationError, do_scan, parcel, "hub_in", "Pune Hub")

    def test_double_scan_makes_one_event(self):
        parcel = make_parcel()
        do_scan(parcel, "pickup")
        again = do_scan(parcel, "pickup")
        self.assertTrue(again["duplicate"])
        count = frappe.db.count("Scan Event", {"parcel": parcel.name, "status": "Picked Up"})
        self.assertEqual(count, 1)

    def test_no_pickup_before_payment(self):
        parcel = make_parcel(paid=False)
        parcel.db_set("token", make_token(parcel.name, "test-secret"))
        self.assertRaises(frappe.ValidationError, do_scan, parcel, "pickup")

        payment.mark_paid(parcel.razorpay_order_id, "pay_1")
        do_scan(parcel, "pickup")
        self.assertEqual(current_status(parcel.name), "Picked Up")

    def test_webhook_retry_does_not_pay_twice(self):
        parcel = make_parcel(paid=False)
        payment.mark_paid(parcel.razorpay_order_id, "pay_1")
        payment.mark_paid(parcel.razorpay_order_id, "pay_1")
        count = frappe.db.count("Scan Event", {"parcel": parcel.name, "status": "Booked & Paid"})
        self.assertEqual(count, 1)

    def test_status_cannot_be_edited(self):
        parcel = make_parcel()
        parcel.status = "Delivered"
        self.assertRaises(frappe.ValidationError, parcel.save)

    def test_scan_events_cannot_be_deleted(self):
        parcel = make_parcel()
        event = frappe.get_all("Scan Event", {"parcel": parcel.name}, pluck="name")[0]
        self.assertRaises(frappe.ValidationError, frappe.delete_doc, "Scan Event", event, force=True)

    def test_return_flow_mirrors_forward(self):
        parcel = make_parcel()
        walk_forward(parcel)
        start_return(parcel.name, parcel.owner)

        do_scan(parcel, "pickup")
        # return goes to the destination hub first
        self.assertRaises(frappe.ValidationError, do_scan, parcel, "hub_in", "Delhi Hub")
        do_scan(parcel, "hub_in", "Pune Hub")
        do_scan(parcel, "hub_out", "Pune Hub")
        do_scan(parcel, "hub_in", "Delhi Hub")
        do_scan(parcel, "hub_out", "Delhi Hub")
        do_scan(parcel, "deliver")
        self.assertEqual(current_status(parcel.name), "Returned")

    def test_cannot_return_before_delivery(self):
        parcel = make_parcel()
        self.assertRaises(frappe.ValidationError, start_return, parcel.name, parcel.owner)
