"""Override crm.api.doc.get_data to translate semantic CRM priority sorting."""

import frappe

PRIORITY_SORTED_DOCTYPES = ("CRM Lead", "CRM Deal", "CRM Task")


def normalize_order_by(doctype: str, order_by: str | None) -> str:
	"""Translate semantic priority sorting using indexed priority_rank (High=1, Medium=2, Low=3)."""
	has_rank_column = doctype in PRIORITY_SORTED_DOCTYPES and frappe.db.has_column(doctype, "priority_rank")

	if not order_by or not str(order_by).strip():
		order_by = "priority asc, modified desc" if has_rank_column else "modified desc"

	clauses = [c.strip() for c in str(order_by).split(",") if c.strip()]
	rewritten = []
	has_modified = False
	has_priority = False

	for clause in clauses:
		parts = clause.split()
		field = parts[0].strip("`")
		direction = parts[1].lower() if len(parts) > 1 and parts[1].lower() in ("asc", "desc") else "asc"
		if field == "modified":
			has_modified = True
		if field == "priority" and has_rank_column:
			has_priority = True
			rewritten.append(f"priority_rank {direction}")
		else:
			rewritten.append(clause)

	if has_priority and not has_modified:
		rewritten.append("modified desc")

	return ", ".join(rewritten)


@frappe.whitelist()
def get_data(
	doctype: str,
	filters: dict,
	order_by: str = "",
	page_length: int = 20,
	page_length_count: int = 20,
	column_field: str | None = None,
	title_field: str | None = None,
	columns: str | list | None = None,
	rows: str | list | None = None,
	kanban_columns: str | list | None = None,
	kanban_fields: str | list | None = None,
	view: str | dict | None = None,
	default_filters: dict | None = None,
):
	from crm.api.doc import get_data as crm_get_data

	effective_order_by = normalize_order_by(doctype, order_by)
	return crm_get_data(
		doctype=doctype,
		filters=filters,
		order_by=effective_order_by,
		page_length=page_length,
		page_length_count=page_length_count,
		column_field=column_field,
		title_field=title_field,
		columns=columns,
		rows=rows,
		kanban_columns=kanban_columns,
		kanban_fields=kanban_fields,
		view=view,
		default_filters=default_filters,
	)
