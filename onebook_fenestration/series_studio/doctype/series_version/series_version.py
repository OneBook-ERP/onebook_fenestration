import frappe

from frappe.model.document import Document


class SeriesVersion(Document):
	def on_submit(self):
		frappe.db.set_value("Profile Series", self.series, "published_version", self.name)

	def on_cancel(self):
		if frappe.db.get_value("Profile Series", self.series, "published_version") == self.name:
			frappe.db.set_value("Profile Series", self.series, "published_version", None)
