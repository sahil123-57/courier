import frappe
from frappe.model.document import Document


class Parcel(Document):
	def before_insert(self):
		if not self.booking_key:
			self.booking_key = frappe.generate_hash(length=12)

	def validate(self):
		if not self.is_new() and self.has_value_changed("status"):
			frappe.throw("Status cannot be edited, it comes from scans")
