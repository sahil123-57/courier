import frappe


def calc_amount(base_price, per_kg, weight):
    return round(base_price + per_kg * weight, 2)


def get_amount(origin_city, destination_city, service_level, weight):
    rate = frappe.db.get_value(
        "Shipping Rate",
        {
            "origin_city": origin_city,
            "destination_city": destination_city,
            "service_level": service_level,
        },
        ["base_price", "price_per_kg"],
        as_dict=True,
    )
    if not rate:
        frappe.throw(f"No rate for {origin_city} to {destination_city} ({service_level})")
    return calc_amount(rate.base_price, rate.price_per_kg, weight)


def hub_for_city(city):
    hub = frappe.db.get_value("Hub", {"city": city, "active": 1})
    if not hub:
        frappe.throw(f"We have no active hub in {city}")
    return hub
