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
class TestExceptions(BaseTestCase):
    def setUp(self):
        frappe.conf.courier_secret = "test-secret"

    def out_for_delivery_parcel(self):
        parcel = make_parcel()
        do_scan(parcel, "pickup")
        do_scan(parcel, "hub_in", "Delhi Hub")
        do_scan(parcel, "hub_out", "Delhi Hub")
        do_scan(parcel, "hub_in", "Pune Hub")
        do_scan(parcel, "hub_out", "Pune Hub")
        return parcel

    def test_failed_delivery_blocks_scan_until_resumed(self):
        parcel = self.out_for_delivery_parcel()
        scan.ops_action(parcel.name, "fail_delivery", "Nobody home")
        self.assertEqual(current_status(parcel.name), "Delivery Failed")
        self.assertRaises(frappe.ValidationError, do_scan, parcel, "deliver")

        scan.ops_action(parcel.name, "resume")
        self.assertEqual(current_status(parcel.name), "Out for Delivery")
        do_scan(parcel, "deliver")
        self.assertEqual(current_status(parcel.name), "Delivered")

    def test_can_fail_twice(self):
        parcel = self.out_for_delivery_parcel()
        for _ in range(2):
            scan.ops_action(parcel.name, "fail_delivery", "Not available")
            scan.ops_action(parcel.name, "resume")
        self.assertEqual(current_status(parcel.name), "Out for Delivery")

    def test_hold_and_resume_at_hub(self):
        parcel = make_parcel()
        do_scan(parcel, "pickup")
        do_scan(parcel, "hub_in", "Delhi Hub")
        scan.ops_action(parcel.name, "hold", "Damaged packaging")
        self.assertRaises(frappe.ValidationError, do_scan, parcel, "hub_out", "Delhi Hub")
        scan.ops_action(parcel.name, "resume")
        do_scan(parcel, "hub_out", "Delhi Hub")
        self.assertEqual(current_status(parcel.name), "In Transit")

    def test_cannot_fail_a_parcel_that_is_not_out_for_delivery(self):
        parcel = make_parcel()
        self.assertRaises(frappe.ValidationError, scan.ops_action, parcel.name, "fail_delivery", "x")


class TestProof(BaseTestCase):
    def setUp(self):
        frappe.conf.courier_secret = "test-secret"

    def test_proof_is_kept_only_on_the_delivered_scan(self):
        parcel = make_parcel()
        token = make_token(parcel.name, "test-secret")
        process_scan(token, "pickup", None, "/private/files/ignored.jpg")
        process_scan(token, "hub_in", "Delhi Hub")
        process_scan(token, "hub_out", "Delhi Hub")
        process_scan(token, "hub_in", "Pune Hub")
        process_scan(token, "hub_out", "Pune Hub")
        process_scan(token, "deliver", None, "/private/files/proof.jpg")

        events = frappe.get_all("Scan Event", {"parcel": parcel.name}, ["status", "proof"])
        proofs = {e.status: e.proof for e in events}
        self.assertFalse(proofs["Picked Up"])
        self.assertEqual(proofs["Delivered"], "/private/files/proof.jpg")


def make_user(email, role):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": email.split("@")[0],
                "send_welcome_email": 0,
                "roles": [{"role": role}],
            }
        ).insert(ignore_permissions=True)
    return email


class TestApiAccess(BaseTestCase):
    def setUp(self):
        frappe.conf.courier_secret = "test-secret"
        self.owner = make_user("owner.test@example.com", "Courier Customer")
        self.other = make_user("other.test@example.com", "Courier Customer")

    def tearDown(self):
        frappe.set_user("Administrator")

    def parcel_owned_by_owner(self, paid=True):
        parcel = make_parcel(paid=paid)
        frappe.db.set_value("Parcel", parcel.name, "owner", self.owner)
        return parcel

    def test_owner_can_track_own_parcel(self):
        from courier import api

        parcel = self.parcel_owned_by_owner()
        frappe.set_user(self.owner)
        result = api.track_parcel(parcel.name)
        self.assertEqual(result["status"], "Booked & Paid")

    def test_other_customer_cannot_track_it(self):
        from courier import api

        parcel = self.parcel_owned_by_owner()
        frappe.set_user(self.other)
        self.assertRaises(frappe.PermissionError, api.track_parcel, parcel.name)

    def test_other_customer_cannot_get_the_label(self):
        from courier import api

        parcel = self.parcel_owned_by_owner()
        frappe.set_user(self.other)
        self.assertRaises(frappe.PermissionError, api.get_label, parcel.name)

    def test_other_customer_cannot_start_a_return(self):
        from courier import api

        parcel = self.parcel_owned_by_owner()
        frappe.set_user(self.other)
        self.assertRaises(frappe.PermissionError, api.raise_return, parcel.name)

    def test_customer_list_shows_only_own_parcels(self):
        from courier import api

        parcel = self.parcel_owned_by_owner()
        frappe.set_user(self.other)
        names = [p.name for p in api.my_parcels()]
        self.assertNotIn(parcel.name, names)

    def test_label_is_refused_before_payment(self):
        from courier import api

        parcel = self.parcel_owned_by_owner(paid=False)
        frappe.set_user(self.owner)
        self.assertRaises(frappe.ValidationError, api.get_label, parcel.name)

    def test_guest_cannot_use_customer_endpoints(self):
        from courier import api

        frappe.set_user("Guest")
        self.assertRaises(frappe.PermissionError, api.my_parcels)
        self.assertRaises(frappe.PermissionError, api.get_quote, "Delhi", "Pune", "Standard", 2)

    def test_customer_cannot_scan(self):
        from courier import api

        frappe.set_user(self.owner)
        self.assertRaises(frappe.PermissionError, api.scan_parcel, "anything", "pickup")

    def test_customer_cannot_use_ops_actions(self):
        from courier import api

        parcel = self.parcel_owned_by_owner()
        frappe.set_user(self.owner)
        self.assertRaises(frappe.PermissionError, api.ops_action, parcel.name, "hold", "x")

    def test_forged_webhook_is_rejected(self):
        from courier import api

        frappe.set_user("Guest")
        frappe.local.request = type("R", (), {"get_data": lambda self: b"{}", "headers": {}})()
        self.assertRaises(Exception, api.razorpay_webhook)
