from frappe.model.document import Document

from onebook_fenestration.production.cutting_plan import build_plan, set_defaults


class CuttingPlan(Document):
	def validate(self):
		if self.docstatus == 0:
			set_defaults(self)
			build_plan(self)
