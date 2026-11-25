import unittest

from courier.signing import make_token, read_token
from courier.state_machine import FORWARD, RETURN, ScanError, decide

ORIGIN = "Delhi Hub"
DEST = "Pune Hub"


def scan(direction, status, scan_type, hub=None):
    return decide(direction, status, scan_type, hub, ORIGIN, DEST)


class TestTransitions(unittest.TestCase):
    def test_forward_flow_in_order(self):
        status = "Booked & Paid"
        for before, stype, after, place in FORWARD:
            hub = {"origin": ORIGIN, "destination": DEST}.get(place)
            action, status = scan("Forward", status, stype, hub)
            self.assertEqual(action, "apply")
            self.assertEqual(status, after)
        self.assertEqual(status, "Delivered")

    def test_skipping_a_step_is_rejected(self):
        with self.assertRaises(ScanError):
            scan("Forward", "Picked Up", "hub_out", ORIGIN)

    def test_wrong_hub_is_rejected(self):
        with self.assertRaises(ScanError):
            scan("Forward", "Picked Up", "hub_in", DEST)

    def test_going_backwards_is_rejected(self):
        with self.assertRaises(ScanError):
            scan("Forward", "In Transit", "pickup")

    def test_nothing_after_delivered(self):
        with self.assertRaises(ScanError):
            scan("Forward", "Delivered", "pickup")

    def test_unpaid_parcel_has_no_legal_scan(self):
        with self.assertRaises(ScanError):
            scan("Forward", "Unpaid", "pickup")


class TestDuplicates(unittest.TestCase):
    def test_repeat_scan_is_a_noop(self):
        action, status = scan("Forward", "Picked Up", "pickup")
        self.assertEqual(action, "duplicate")
        self.assertEqual(status, "Picked Up")

    def test_repeat_hub_scan_is_a_noop(self):
        action, _ = scan("Forward", "In at Origin Hub", "hub_in", ORIGIN)
        self.assertEqual(action, "duplicate")

    def test_repeat_at_wrong_hub_is_not_a_noop(self):
        with self.assertRaises(ScanError):
            scan("Forward", "In at Origin Hub", "hub_in", DEST)


class TestReturnMirror(unittest.TestCase):
    def test_same_shape_as_forward(self):
        self.assertEqual(len(FORWARD), len(RETURN))
        self.assertEqual([s[1] for s in FORWARD], [s[1] for s in RETURN])

    def test_same_hub_places_as_forward(self):
        self.assertEqual([s[3] for s in FORWARD], [s[3] for s in RETURN])

    def test_return_flow_in_order(self):
        status = "Return Requested"
        for before, stype, after, place in RETURN:
            hub = {"origin": ORIGIN, "destination": DEST}.get(place)
            _, status = scan("Return", status, stype, hub)
        self.assertEqual(status, "Returned")

    def test_return_wrong_hub_is_rejected(self):
        with self.assertRaises(ScanError):
            scan("Return", "Return Picked Up", "hub_in", DEST)

    def test_return_repeat_scan_is_a_noop(self):
        action, _ = scan("Return", "Return Picked Up", "pickup")
        self.assertEqual(action, "duplicate")


class TestTokens(unittest.TestCase):
    def test_good_token(self):
        t = make_token("PCL-00001", "secret")
        self.assertEqual(read_token(t, "secret"), "PCL-00001")

    def test_forged_token(self):
        self.assertIsNone(read_token("PCL-00001.abcdef", "secret"))
        self.assertIsNone(read_token(make_token("PCL-00001", "secret"), "other"))
        self.assertIsNone(read_token("", "secret"))


if __name__ == "__main__":
    unittest.main()
