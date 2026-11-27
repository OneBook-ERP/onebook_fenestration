"""Idempotent Frappe CRM schema layouts, Quick Filters, standard views, and CRM Form Scripts."""

import json

import frappe

from onebook_fenestration.crm.lead import PRIORITY_COLUMN_DEF
from onebook_fenestration.crm.scripts import (
	DEAL_LIST_UI_SCRIPT_NAME,
	DEAL_QUOTATION_FORM_SCRIPT,
	DEAL_QUOTATION_SCRIPT_NAME,
	LEAD_FORM_UI_SCRIPT,
	LEAD_FORM_UI_SCRIPT_NAME,
	LEAD_LIST_UI_SCRIPT_NAME,
	LIST_UI_ENHANCER_SCRIPT,
	TASK_LIST_UI_SCRIPT_NAME,
)

PRIORITY_LAYOUT_NAMES = (
	"CRM Lead-Quick Entry",
	"CRM Lead-Side Panel",
	"CRM Lead-Data Fields",
	"CRM Deal-Quick Entry",
	"CRM Deal-Side Panel",
	"CRM Deal-Data Fields",
)

PRIORITY_QUICK_FILTER_DOCTYPES = ("CRM Lead", "CRM Deal")

PRIORITY_STANDARD_VIEWS = (
	("CRM Lead", "Leads"),
	("CRM Deal", "Deals"),
	("CRM Task", "Tasks"),
)


def sync_crm_customizations() -> None:
	"""Idempotently sync CRM Priority fields, layouts, Quick Filters, standard views, and scripts."""
	if not frappe.db.exists("DocType", "CRM Lead"):
		return
	_backfill_priority_fields()
	_ensure_priority_in_layouts()
	_ensure_partner_type_in_layouts()
	_ensure_priority_in_quick_filters()
	_ensure_priority_in_standard_views()
	ensure_crm_form_scripts()


def _backfill_priority_fields() -> None:
	if frappe.db.has_column("CRM Lead", "priority"):
		lead = frappe.qb.DocType("CRM Lead")
		frappe.qb.update(lead).set(lead.priority, "Medium").where(
			(lead.priority.isnull()) | (lead.priority == "")
		).run()
		_backfill_priority_rank("CRM Lead")

	if frappe.db.exists("DocType", "CRM Deal") and frappe.db.has_column("CRM Deal", "priority"):
		deal = frappe.qb.DocType("CRM Deal")
		# Inherit priority from linked CRM Lead for existing deals when unset
		if frappe.db.has_column("CRM Lead", "priority"):
			lead = frappe.qb.DocType("CRM Lead")
			deals_with_lead = (
				frappe.qb.from_(deal)
				.join(lead)
				.on(deal.lead == lead.name)
				.select(deal.name, lead.priority)
				.where(
					((deal.priority.isnull()) | (deal.priority == ""))
					& (lead.priority.isnotnull())
					& (lead.priority != "")
				)
				.run(as_dict=True)
			)
			for row in deals_with_lead:
				frappe.db.set_value("CRM Deal", row.name, "priority", row.priority, update_modified=False)
		frappe.qb.update(deal).set(deal.priority, "Medium").where(
			(deal.priority.isnull()) | (deal.priority == "")
		).run()
		_backfill_priority_rank("CRM Deal")

	if frappe.db.exists("DocType", "CRM Task") and frappe.db.has_column("CRM Task", "priority_rank"):
		_backfill_priority_rank("CRM Task")


def _backfill_priority_rank(doctype: str) -> None:
	if not frappe.db.has_column(doctype, "priority_rank"):
		return
	table = frappe.qb.DocType(doctype)
	for label, rank in (("High", 1), ("Medium", 2), ("Low", 3)):
		frappe.qb.update(table).set(table.priority_rank, rank).where(
			(table.priority == label) & ((table.priority_rank.isnull()) | (table.priority_rank != rank))
		).run()
	frappe.qb.update(table).set(table.priority_rank, 4).where(
		((table.priority.isnull()) | (table.priority == ""))
		& ((table.priority_rank.isnull()) | (table.priority_rank != 4))
	).run()


def _iter_columns(layout):
	for section in layout:
		yield from section.get("columns", [])
		for nested in section.get("sections", []):
			yield from nested.get("columns", [])


def _find_target_column(layout, prefer_field: str = "status"):
	for col in _iter_columns(layout):
		fields = [f.get("fieldname") if isinstance(f, dict) else f for f in (col.get("fields") or [])]
		if prefer_field in fields:
			return col
	for section in layout:
		if section.get("hidden"):
			continue
		if section.get("columns"):
			return section["columns"][0]
		for nested in section.get("sections", []):
			if not nested.get("hidden") and nested.get("columns"):
				return nested["columns"][0]
	return None


def _ensure_priority_in_layouts() -> None:
	if not frappe.db.exists("DocType", "CRM Fields Layout"):
		return
	for name in PRIORITY_LAYOUT_NAMES:
		if not frappe.db.exists("CRM Fields Layout", name):
			continue
		doc = frappe.get_doc("CRM Fields Layout", name)
		try:
			layout = json.loads(doc.layout or "[]")
		except (TypeError, ValueError):
			continue

		present = {
			f.get("fieldname") if isinstance(f, dict) else f
			for col in _iter_columns(layout)
			for f in (col.get("fields") or [])
		}
		if "priority" in present:
			continue

		target_col = _find_target_column(layout, prefer_field="status")
		if not target_col:
			continue
		fields = target_col.setdefault("fields", [])
		if "status" in fields:
			fields.insert(fields.index("status") + 1, "priority")
		else:
			fields.insert(0, "priority")
		doc.layout = json.dumps(layout)
		doc.save(ignore_permissions=True)


def _append_field_to_layout_section(nodes: list, section_name: str, fieldname: str) -> bool:
	for node in nodes:
		if not isinstance(node, dict):
			continue
		if node.get("name") == section_name and isinstance(node.get("columns"), list) and node["columns"]:
			fields = node["columns"][0].setdefault("fields", [])
			if fieldname not in fields:
				fields.append(fieldname)
				return True
		if isinstance(node.get("sections"), list):
			if _append_field_to_layout_section(node["sections"], section_name, fieldname):
				return True
	return False


def _ensure_partner_type_in_layouts() -> None:
	if not frappe.db.exists("DocType", "CRM Fields Layout"):
		return
	targets = (
		("CRM Deal-Quick Entry", "deal_section"),
		("CRM Lead-Data Fields", "details_section"),
	)
	for layout_name, section_name in targets:
		if not frappe.db.exists("CRM Fields Layout", layout_name):
			continue
		raw = frappe.db.get_value("CRM Fields Layout", layout_name, "layout")
		if not raw or "fen_partner_type" in raw:
			continue
		try:
			parsed = json.loads(raw)
		except (TypeError, ValueError):
			continue
		if _append_field_to_layout_section(parsed, section_name, "fen_partner_type"):
			frappe.db.set_value(
				"CRM Fields Layout", layout_name, "layout", json.dumps(parsed), update_modified=False
			)


def _ensure_priority_in_quick_filters() -> None:
	"""Ensure Priority appears in the top Quick Filters bar for CRM Lead and CRM Deal."""
	if not frappe.db.exists("DocType", "CRM Global Settings"):
		return
	for doctype in PRIORITY_QUICK_FILTER_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		name = frappe.db.exists("CRM Global Settings", {"dt": doctype, "type": "Quick Filters"})
		if not name:
			continue
		raw = frappe.db.get_value("CRM Global Settings", name, "json")
		try:
			filters = json.loads(raw or "[]")
		except (TypeError, ValueError):
			continue
		if not isinstance(filters, list) or "priority" in filters:
			continue
		if "status" in filters:
			filters.insert(filters.index("status") + 1, "priority")
		else:
			filters.append("priority")
		frappe.db.set_value("CRM Global Settings", name, "json", json.dumps(filters), update_modified=False)


def _ensure_priority_in_standard_views() -> None:
	"""Ensure standard List views exist and default to priority asc across Leads, Deals, and Tasks."""
	if not frappe.db.exists("DocType", "CRM View Settings"):
		return
	from frappe.model.base_document import get_controller

	for doctype, route_name in PRIORITY_STANDARD_VIEWS:
		if not frappe.db.exists("DocType", doctype):
			continue
		views = frappe.get_all(
			"CRM View Settings",
			filters={"dt": doctype, "is_standard": 1, "type": "list"},
			pluck="name",
		)
		if not views:
			controller = get_controller(doctype)
			default_data = controller.default_list_data() if hasattr(controller, "default_list_data") else {}
			columns = list(default_data.get("columns") or [])
			rows = list(default_data.get("rows") or [])
			_inject_priority_into_view_lists(columns, rows)
			frappe.get_doc(
				{
					"doctype": "CRM View Settings",
					"label": "List",
					"dt": doctype,
					"type": "list",
					"route_name": route_name,
					"user": "",
					"is_standard": 1,
					"load_default_columns": 1,
					"order_by": "priority asc",
					"columns": json.dumps(columns),
					"rows": json.dumps(rows),
				}
			).insert(ignore_permissions=True)
			continue

		for view_name in views:
			doc = frappe.get_doc("CRM View Settings", view_name)
			changed = False
			try:
				columns = json.loads(doc.columns or "[]")
				rows = json.loads(doc.rows or "[]")
			except (TypeError, ValueError):
				continue

			if _inject_priority_into_view_lists(columns, rows):
				doc.columns = json.dumps(columns)
				doc.rows = json.dumps(rows)
				changed = True

			if not doc.order_by or doc.order_by.strip() == "modified desc":
				doc.order_by = "priority asc"
				changed = True

			if changed:
				doc.save(ignore_permissions=True)


def _inject_priority_into_view_lists(columns: list, rows: list) -> bool:
	changed = False
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
		changed = True

	if "priority" not in rows:
		status_row_idx = rows.index("status") + 1 if "status" in rows else len(rows)
		rows.insert(status_row_idx, "priority")
		changed = True

	return changed


def _upsert_crm_form_script(name: str, dt: str, view: str, script: str) -> None:
	if frappe.db.exists("CRM Form Script", name):
		doc = frappe.get_doc("CRM Form Script", name)
		if doc.script != script or not doc.enabled or doc.dt != dt or doc.view != view:
			doc.dt = dt
			doc.view = view
			doc.script = script
			doc.enabled = 1
			doc.save(ignore_permissions=True)
		return

	frappe.get_doc(
		{
			"doctype": "CRM Form Script",
			"name": name,
			"dt": dt,
			"view": view,
			"enabled": 1,
			"script": script,
		}
	).insert(ignore_permissions=True)


def ensure_crm_form_scripts() -> None:
	"""Create or update OneBook Fenestration's CRM Form & List Scripts."""
	if not frappe.db.exists("DocType", "CRM Form Script"):
		return

	legacy_script = "Create Quotation from CRM Deal"
	if frappe.db.exists("CRM Form Script", legacy_script):
		if frappe.db.get_value("CRM Form Script", legacy_script, "enabled"):
			frappe.db.set_value("CRM Form Script", legacy_script, "enabled", 0, update_modified=False)

	_upsert_crm_form_script(DEAL_QUOTATION_SCRIPT_NAME, "CRM Deal", "Form", DEAL_QUOTATION_FORM_SCRIPT)
	_upsert_crm_form_script(LEAD_LIST_UI_SCRIPT_NAME, "CRM Lead", "List", LIST_UI_ENHANCER_SCRIPT)
	_upsert_crm_form_script(DEAL_LIST_UI_SCRIPT_NAME, "CRM Deal", "List", LIST_UI_ENHANCER_SCRIPT)
	_upsert_crm_form_script(TASK_LIST_UI_SCRIPT_NAME, "CRM Task", "List", LIST_UI_ENHANCER_SCRIPT)
	_upsert_crm_form_script(LEAD_FORM_UI_SCRIPT_NAME, "CRM Lead", "Form", LEAD_FORM_UI_SCRIPT)
