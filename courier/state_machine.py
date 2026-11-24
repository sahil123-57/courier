class ScanError(Exception):
    pass


# each row is: status now, scan type, status after, hub the scan must happen at
# "origin" and "destination" are the parcel's own hubs, None means no hub check
FORWARD = [
    ("Booked & Paid", "pickup", "Picked Up", None),
    ("Picked Up", "hub_in", "In at Origin Hub", "origin"),
    ("In at Origin Hub", "hub_out", "In Transit", "origin"),
    ("In Transit", "hub_in", "In at Destination Hub", "destination"),
    ("In at Destination Hub", "hub_out", "Out for Delivery", "destination"),
    ("Out for Delivery", "deliver", "Delivered", None),
]

# a return is a separate parcel with the hubs swapped, so it walks the same steps
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
    if place == "origin":
        return origin_hub
    if place == "destination":
        return destination_hub
    return None


def is_repeat(steps, status, scan_type, hub, origin_hub, destination_hub):
    for _, step_scan, status_after, place in steps:
        if status_after == status and step_scan == scan_type:
            wanted_hub = expected_hub(place, origin_hub, destination_hub)
            if wanted_hub is None or wanted_hub == hub:
                return True
    return False


def decide(direction, status, scan_type, hub, origin_hub, destination_hub):
    steps = TABLES[direction]

    if is_repeat(steps, status, scan_type, hub, origin_hub, destination_hub):
        return "duplicate", status

    for status_before, step_scan, status_after, place in steps:
        if status_before != status:
            continue

        if step_scan != scan_type:
            raise ScanError(f"Expected a '{step_scan}' scan but got '{scan_type}'")

        wanted_hub = expected_hub(place, origin_hub, destination_hub)
        if wanted_hub and wanted_hub != hub:
            raise ScanError(f"This scan must be done at hub {wanted_hub}, not {hub}")

        return "apply", status_after

    raise ScanError(f"No scan is allowed while the parcel is '{status}'")
