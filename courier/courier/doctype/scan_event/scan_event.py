import frappe
from frappe.model.document import Document


class ScanEvent(Document):
	def before_save(self):
		if not self.is_new():
			frappe.throw("Scan events cannot be changed")

	def on_trash(self):
		frappe.throw("Scan events cannot be deleted")
