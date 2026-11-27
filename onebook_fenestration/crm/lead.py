"""CRM Lead, Deal, and Task priority validation, default list columns, and kanban settings."""

import json

import frappe
from frappe import _

VALID_PRIORITIES = ("High", "Medium", "Low")
PRIORITY_RANKS = {"High": 1, "Medium": 2, "Low": 3}

PRIORITY_COLUMN_DEF = {
	"label": "Priority",
	"type": "Select",
	"options": "\nHigh\nMedium\nLow",
	"key": "priority",
	"width": "7.5rem",
}


def validate_lead_priority(doc, method=None) -> None:
	"""Validate mandatory priority on CRM Lead and compute indexed priority_rank."""
	if not frappe.db.has_column("CRM Lead", "priority"):
		return
	priority = (doc.get("priority") or "").strip()
	if not priority and not doc.flags.get("ignore_mandatory"):
		frappe.throw(_("Priority is mandatory"), frappe.MandatoryError)
	if priority and priority not in VALID_PRIORITIES:
		frappe.throw(_("Priority must be High, Medium, or Low"), frappe.ValidationError)
	doc.priority = priority
	if frappe.db.has_column("CRM Lead", "priority_rank"):
		doc.priority_rank = PRIORITY_RANKS.get(priority, 4)


def validate_deal_priority(doc, method=None) -> None:
	"""Ensure valid priority on CRM Deal (defaulting to Medium) and compute priority_rank."""
	if not frappe.db.has_column("CRM Deal", "priority"):
		return
	priority = (doc.get("priority") or "").strip() or "Medium"
	if priority not in VALID_PRIORITIES:
		frappe.throw(_("Priority must be High, Medium, or Low"), frappe.ValidationError)
	doc.priority = priority
	if frappe.db.has_column("CRM Deal", "priority_rank"):
		doc.priority_rank = PRIORITY_RANKS.get(priority, 4)


def sync_task_priority_rank(doc, method=None) -> None:
	"""Keep indexed priority_rank synchronized with CRM Task priority."""
	if not frappe.db.has_column("CRM Task", "priority_rank"):
		return
	priority = (doc.get("priority") or "").strip()
	doc.priority_rank = PRIORITY_RANKS.get(priority, 4)


def _inject_priority_list_data(base_data: dict) -> dict:
	columns = list(base_data.get("columns") or [])
	rows = list(base_data.get("rows") or [])

	if not any(isinstance(c, dict) and c.get("key") == "priority" for c in columns):
		priority_col = dict(PRIORITY_COLUMN_DEF)
		status_idx = next(
			(i for i, c in enumerate(columns) if isinstance(c, dict) and c.get("key") == "status"),
			None,
		)
		if status_idx is not None:
			columns.insert(status_idx + 1, priority_col)
		else:
			columns.append(priority_col)

	if "priority" not in rows:
		status_row_idx = rows.index("status") + 1 if "status" in rows else len(rows)
		rows.insert(status_row_idx, "priority")

	return {"columns": columns, "rows": rows}


def _inject_priority_kanban_settings(base_settings: dict | None) -> dict:
	settings = dict(base_settings or {})
	try:
		fields = json.loads(settings.get("kanban_fields") or "[]")
	except (TypeError, ValueError):
		fields = []
	if isinstance(fields, list) and "priority" not in fields:
		fields.insert(0, "priority")
		settings["kanban_fields"] = json.dumps(fields)
	return settings


class CRMLeadMixin:
	"""Mixin registered via extend_doctype_class to expose Priority in default Lead list & kanban views."""

	@staticmethod
	def default_list_data():
		from crm.fcrm.doctype.crm_lead.crm_lead import CRMLead

		return _inject_priority_list_data(CRMLead.default_list_data())

	@staticmethod
	def default_kanban_settings():
		from crm.fcrm.doctype.crm_lead.crm_lead import CRMLead

		return _inject_priority_kanban_settings(CRMLead.default_kanban_settings())


class CRMDealMixin:
	"""Mixin registered via extend_doctype_class to expose Priority in default Deal list & kanban views."""

	@staticmethod
	def default_list_data():
		from crm.fcrm.doctype.crm_deal.crm_deal import CRMDeal

		return _inject_priority_list_data(CRMDeal.default_list_data())

	@staticmethod
	def default_kanban_settings():
		from crm.fcrm.doctype.crm_deal.crm_deal import CRMDeal

		return _inject_priority_kanban_settings(CRMDeal.default_kanban_settings())
