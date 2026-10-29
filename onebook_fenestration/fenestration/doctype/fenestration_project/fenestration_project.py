import frappe
from frappe.model.document import Document


class FenestrationProject(Document):
	def before_insert(self):
		self.company = self.company or default_company()


def default_company() -> str | None:
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
