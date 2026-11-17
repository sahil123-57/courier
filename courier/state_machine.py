class ScanError(Exception):
    pass


# (status now, scan type, status after, where the scan must happen)
# "origin" / "destination" mean the parcel's hubs, None means in the field
FORWARD = [
    ("Booked & Paid", "pickup", "Picked Up", None),
    ("Picked Up", "hub_in", "In at Origin Hub", "origin"),
    ("In at Origin Hub", "hub_out", "In Transit", "origin"),
    ("In Transit", "hub_in", "In at Destination Hub", "destination"),
    ("In at Destination Hub", "hub_out", "Out for Delivery", "destination"),
    ("Out for Delivery", "deliver", "Delivered", None),
]

# same steps, hubs swapped
RETURN = [
    ("Return Requested", "pickup", "Return Picked Up", None),
    ("Return Picked Up", "hub_in", "Return In at Pickup Hub", "destination"),
    ("Return In at Pickup Hub", "hub_out", "Return In Transit", "destination"),
    ("Return In Transit", "hub_in", "Return In at Drop Hub", "origin"),
    ("Return In at Drop Hub", "hub_out", "Return Out for Delivery", "origin"),
    ("Return Out for Delivery", "deliver", "Returned", None),
]

TABLES = {"Forward": FORWARD, "Return": RETURN}


def expected_hub(place, origin_hub, destination_hub):
    if place == "origin":
        return origin_hub
    if place == "destination":
        return destination_hub
    return None


def decide(direction, status, scan_type, hub, origin_hub, destination_hub):
    """Returns ("apply", new_status) or ("duplicate", status). Raises ScanError."""
    steps = TABLES[direction]

    # same scan again, parcel is already in the state it would produce
    for _, stype, after, place in steps:
        if after == status and stype == scan_type:
            want = expected_hub(place, origin_hub, destination_hub)
            if want is None or want == hub:
                return "duplicate", status

    for before, stype, after, place in steps:
        if before != status:
            continue
        if stype != scan_type:
            raise ScanError(f"Expected a '{stype}' scan but got '{scan_type}'")
        want = expected_hub(place, origin_hub, destination_hub)
        if want and want != hub:
            raise ScanError(f"This scan must be done at hub {want}, not {hub}")
        return "apply", after

    raise ScanError(f"No scan is allowed while the parcel is '{status}'")
