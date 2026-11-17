import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw("Please login first", frappe.PermissionError)
    if "Delivery Agent" not in frappe.get_roles():
        frappe.throw("Agents only", frappe.PermissionError)
    context.csrf_token = frappe.sessions.get_csrf_token()
