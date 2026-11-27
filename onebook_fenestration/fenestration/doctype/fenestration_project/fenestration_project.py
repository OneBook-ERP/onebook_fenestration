import frappe
from frappe.model.document import Document

from onebook_fenestration.fenestration.sharing import (
	VALID_PARTNER_TYPES,
	is_partner_only,
	resolve_project_partner_type,
)


class FenestrationProject(Document):
	def before_insert(self):
		self.company = self.company or default_company()
		self._sync_partner_defaults()
		if is_partner_only() and not self.fen_shared_with_hilux:
			self.fen_is_dealer_private = 1
			self.fen_manufacturing_status = self.fen_manufacturing_status or "Private Draft"

	def validate(self):
		self._sync_partner_defaults()

	def _sync_partner_defaults(self):
		if self.customer and frappe.db.has_column("Customer", "fen_partner_type"):
			cust_type = frappe.db.get_value("Customer", self.customer, "fen_partner_type")
			if cust_type in VALID_PARTNER_TYPES:
				self.fen_partner_type = cust_type
		if not self.fen_partner_type:
			self.fen_partner_type = resolve_project_partner_type(self)
		if not self.fen_manufacturing_status:
			self.fen_manufacturing_status = "Shared with Hilux" if self.fen_shared_with_hilux else "Private Draft"


def default_company() -> str | None:
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
