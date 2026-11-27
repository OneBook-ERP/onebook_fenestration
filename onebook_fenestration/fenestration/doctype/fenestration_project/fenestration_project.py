import frappe
from frappe import _
from frappe.model.document import Document

from onebook_fenestration.fenestration.sharing import (
	VALID_PARTNER_TYPES,
	is_hilux_staff,
	is_partner_only,
	resolve_project_partner_type,
)

HILUX_MANAGED_FIELDS = (
	"fen_design_locked",
	"fen_manufacturing_status",
	"fen_shared_with_hilux",
	"fen_is_dealer_private",
	"fen_shared_on",
	"fen_shared_by",
	"quotation",
)


class FenestrationProject(Document):
	def before_insert(self):
		self.company = self.company or default_company()
		self._sync_partner_defaults()
		if not is_hilux_staff() and not self.flags.get("allow_sharing_field_update"):
			self.fen_design_locked = 0
			self.fen_shared_with_hilux = 0
			self.fen_shared_on = None
			self.fen_shared_by = None
			self.quotation = None
			self.fen_manufacturing_status = "Private Draft"
		if is_partner_only() and not self.fen_shared_with_hilux:
			self.fen_is_dealer_private = 1
			self.fen_manufacturing_status = "Private Draft"

	def validate(self):
		self._enforce_protected_fields()
		self._sync_partner_defaults()

	def _enforce_protected_fields(self):
		if self.is_new() or is_hilux_staff() or self.flags.get("allow_sharing_field_update"):
			return
		for fieldname in HILUX_MANAGED_FIELDS:
			if self.has_value_changed(fieldname):
				frappe.throw(
					_("Only Hilux staff can modify {0}.").format(self.meta.get_label(fieldname) or fieldname),
					frappe.PermissionError,
				)
		if self.has_value_changed("fen_partner_type"):
			frappe.throw(
				_("Only Hilux staff can change Partner Type after project creation."),
				frappe.PermissionError,
			)

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
