"""
The rules for moving a parcel from one status to the next.

Every row below is one legal step:

    (status now, scan type, status after, where the scan must happen)

Example: ("Picked Up", "hub_in", "In at Origin Hub", "origin")
means: a parcel that is "Picked Up" can only move forward when someone does a
"hub_in" scan at the parcel's ORIGIN hub. It then becomes "In at Origin Hub".

Anything that is not in the table is not allowed.
"""


class ScanError(Exception):
    pass


# where the scan has to happen:
#   "origin"       the hub where this parcel's trip starts
#   "destination"  the hub where this parcel's trip ends
#   None           out in the field (pickup / delivery), no hub check
FORWARD = [
    ("Booked & Paid", "pickup", "Picked Up", None),
    ("Picked Up", "hub_in", "In at Origin Hub", "origin"),
    ("In at Origin Hub", "hub_out", "In Transit", "origin"),
    ("In Transit", "hub_in", "In at Destination Hub", "destination"),
    ("In at Destination Hub", "hub_out", "Out for Delivery", "destination"),
    ("Out for Delivery", "deliver", "Delivered", None),
]

# A return is its own parcel. It is created with the sender and recipient swapped
# and with the two hubs swapped, so its "origin" is the hub where the first parcel
# was delivered. That is why it walks the same steps with the same places. Only the
# status names differ, so the log reads clearly.
RETURN = [
    ("Return Requested", "pickup", "Return Picked Up", None),
    ("Return Picked Up", "hub_in", "Return In at Pickup Hub", "origin"),
    ("Return In at Pickup Hub", "hub_out", "Return In Transit", "origin"),
    ("Return In Transit", "hub_in", "Return In at Drop Hub", "destination"),
    ("Return In at Drop Hub", "hub_out", "Return Out for Delivery", "destination"),
    ("Return Out for Delivery", "deliver", "Returned", None),
]

TABLES = {"Forward": FORWARD, "Return": RETURN}


def expected_hub(place, origin_hub, destination_hub):
    # turn the word in the table into the real hub of this parcel
    if place == "origin":
        return origin_hub
    if place == "destination":
        return destination_hub
    return None


def is_repeat(steps, status, scan_type, hub, origin_hub, destination_hub):
    # Is this the same scan that already moved the parcel to its current status?
    for _, step_scan, status_after, place in steps:
        if status_after == status and step_scan == scan_type:
            wanted_hub = expected_hub(place, origin_hub, destination_hub)
            if wanted_hub is None or wanted_hub == hub:
                return True
    return False


def decide(direction, status, scan_type, hub, origin_hub, destination_hub):
    """
    Look at the parcel's current status and the scan that just came in.
    Gives back one of:
        ("apply", new_status)     the scan is legal, move the parcel
        ("duplicate", status)     the same scan again, do nothing
    or raises ScanError with the reason the scan is refused.
    """
    steps = TABLES[direction]

    if is_repeat(steps, status, scan_type, hub, origin_hub, destination_hub):
        return "duplicate", status

    for status_before, step_scan, status_after, place in steps:
        if status_before != status:
            continue

        # this is the one step the parcel is allowed to take now
        if step_scan != scan_type:
            raise ScanError(f"Expected a '{step_scan}' scan but got '{scan_type}'")

        wanted_hub = expected_hub(place, origin_hub, destination_hub)
        if wanted_hub and wanted_hub != hub:
            raise ScanError(f"This scan must be done at hub {wanted_hub}, not {hub}")

        return "apply", status_after

    raise ScanError(f"No scan is allowed while the parcel is '{status}'")
