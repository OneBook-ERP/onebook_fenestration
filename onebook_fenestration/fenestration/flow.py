"""ERPNext document workflow actions and pipeline state for Fenestration Projects."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, flt, nowdate

from onebook_fenestration.fenestration.quotation import quote_status
from onebook_fenestration.fenestration.sharing import is_hilux_staff, resolve_project_partner_type
from onebook_fenestration.production import takeoff

ALLOWED_SUBMIT_DOCTYPES = frozenset(
	{
		"Quotation",
		"Sales Order",
		"Material Request",
		"Purchase Order",
		"Purchase Receipt",
		"Purchase Invoice",
		"Delivery Note",
		"Sales Invoice",
		"Payment Entry",
	}
)

ALLOWED_TRANSITIONS: dict[tuple[str, str], str] = {
	("Quotation", "Sales Order"): "erpnext.selling.doctype.quotation.quotation.make_sales_order",
	("Quotation", "Material Request"): "_takeoff_mr",
	("Quotation", "Purchase Order"): "_takeoff_po",
	("Sales Order", "Material Request"): "_takeoff_mr",
	("Sales Order", "Purchase Order"): "_takeoff_po",
	("Sales Order", "Delivery Note"): "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note",
	("Sales Order", "Sales Invoice"): "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
	(
		"Sales Order",
		"Payment Entry",
	): "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
	(
		"Material Request",
		"Purchase Order",
	): "erpnext.stock.doctype.material_request.material_request.make_purchase_order",
	(
		"Purchase Order",
		"Purchase Receipt",
	): "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt",
	(
		"Purchase Order",
		"Purchase Invoice",
	): "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice",
	(
		"Purchase Order",
		"Payment Entry",
	): "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
	(
		"Purchase Receipt",
		"Purchase Invoice",
	): "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice",
	(
		"Purchase Invoice",
		"Payment Entry",
	): "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
	(
		"Delivery Note",
		"Sales Invoice",
	): "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice",
	(
		"Sales Invoice",
		"Payment Entry",
	): "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
}


def project_flow_state(project: str) -> dict:
	"""Return the project's linked ERPNext document chain, contextual actions, and stage status."""
	frappe.has_permission("Fenestration Project", "read", project, throw=True)
	proj_fields = ["name", "project_title", "customer", "company", "quotation"]
	for opt_field in (
		"fen_partner_type",
		"fen_shared_with_hilux",
		"fen_shared_on",
		"fen_shared_by",
		"fen_share_notes",
		"fen_design_locked",
		"fen_manufacturing_status",
	):
		if frappe.db.has_column("Fenestration Project", opt_field):
			proj_fields.append(opt_field)
	proj = frappe.db.get_value(
		"Fenestration Project",
		project,
		proj_fields,
		as_dict=True,
	)
	if not proj:
		frappe.throw(_("Project {0} not found").format(project), frappe.DoesNotExistError)
	partner_type = resolve_project_partner_type(proj)
	design_count = frappe.db.count("Window Design", {"project": project, "superseded_by": ("is", "not set")})

	quotation = _get_quotation_doc(project)
	sales_orders = _get_sales_orders(project)
	so_names = [row["name"] for row in sales_orders]

	material_requests = _get_material_requests(project)
	mr_names = [row["name"] for row in material_requests]

	purchase_orders = _get_purchase_orders(project, mr_names)
	po_names = [row["name"] for row in purchase_orders]

	purchase_receipts = _get_purchase_receipts(project, po_names)
	pr_names = [row["name"] for row in purchase_receipts]

	purchase_invoices = _get_purchase_invoices(project, po_names, pr_names)
	pi_names = [row["name"] for row in purchase_invoices]

	delivery_notes = _get_delivery_notes(project, so_names)
	dn_names = [row["name"] for row in delivery_notes]

	sales_invoices = _get_sales_invoices(project, so_names, dn_names)
	si_names = [row["name"] for row in sales_invoices]

	payment_entries = _get_payment_entries(so_names, si_names, po_names, pi_names)

	_attach_actions(
		quotation=quotation,
		sales_orders=sales_orders,
		material_requests=material_requests,
		purchase_orders=purchase_orders,
		purchase_receipts=purchase_receipts,
		purchase_invoices=purchase_invoices,
		delivery_notes=delivery_notes,
		sales_invoices=sales_invoices,
		payment_entries=payment_entries,
	)

	primary_action, create_options = _build_header_actions(
		project=project,
		design_count=int(design_count or 0),
		quotation=quotation,
		sales_orders=sales_orders,
		material_requests=material_requests,
		purchase_orders=purchase_orders,
		purchase_receipts=purchase_receipts,
		purchase_invoices=purchase_invoices,
		delivery_notes=delivery_notes,
		sales_invoices=sales_invoices,
		payment_entries=payment_entries,
		partner_type=partner_type,
	)

	stages = _build_stages(
		quotation=quotation,
		sales_orders=sales_orders,
		material_requests=material_requests,
		purchase_orders=purchase_orders,
		purchase_receipts=purchase_receipts,
		purchase_invoices=purchase_invoices,
		delivery_notes=delivery_notes,
		sales_invoices=sales_invoices,
		payment_entries=payment_entries,
		partner_type=partner_type,
	)

	return {
		"project": project,
		"partner_type": partner_type,
		"shared_with_hilux": bool(proj.get("fen_shared_with_hilux")),
		"shared_on": str(proj.get("fen_shared_on")) if proj.get("fen_shared_on") else None,
		"shared_by": proj.get("fen_shared_by") or None,
		"share_notes": proj.get("fen_share_notes") or "",
		"design_locked": bool(proj.get("fen_design_locked")),
		"manufacturing_status": proj.get("fen_manufacturing_status") or "Private Draft",
		"is_hilux_staff": is_hilux_staff(),
		"quotation": quotation,
		"sales_orders": sales_orders,
		"material_requests": material_requests,
		"purchase_orders": purchase_orders,
		"purchase_receipts": purchase_receipts,
		"purchase_invoices": purchase_invoices,
		"delivery_notes": delivery_notes,
		"sales_invoices": sales_invoices,
		"payment_entries": payment_entries,
		"suppliers": _list_suppliers(),
		"primary_action": primary_action,
		"create_options": create_options,
		"stages": stages,
	}


def submit_document(doctype: str, name: str) -> dict:
	"""Submit an allowed Draft ERPNext document with permission and validation handling."""
	if doctype not in ALLOWED_SUBMIT_DOCTYPES:
		return {"ok": False, "message": _("Submitting {0} is not supported from here.").format(doctype)}

	if not name:
		return {"ok": False, "message": _("Document name is required.")}

	sp = "fen_flow_submit"
	frappe.db.savepoint(sp)
	try:
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("submit")
		if doc.docstatus == 1:
			return {
				"ok": True,
				"doctype": doctype,
				"name": doc.name,
				"status": doc.get("status") or "Submitted",
				"docstatus": 1,
				"already_submitted": True,
			}
		if doc.docstatus == 2:
			return {
				"ok": False,
				"message": _("{0} {1} is cancelled and cannot be submitted.").format(doctype, name),
			}
		doc.submit()
	except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError) as exc:
		frappe.db.rollback(save_point=sp)
		frappe.clear_messages()
		return {"ok": False, "message": _clean_exc_message(exc)}

	frappe.db.release_savepoint(sp)
	return {
		"ok": True,
		"doctype": doctype,
		"name": doc.name,
		"status": doc.get("status") or "Submitted",
		"docstatus": doc.docstatus,
		"project": _infer_project(doc),
	}


def create_next_document(
	source_doctype: str,
	source_name: str,
	target_doctype: str,
	supplier: str | None = None,
	po_no: str | None = None,
	submit: bool = False,
) -> dict:
	"""Create (and optionally submit) a downstream ERPNext document from an existing submitted doc."""
	key = (source_doctype, target_doctype)
	handler = ALLOWED_TRANSITIONS.get(key)
	if not handler:
		return {
			"ok": False,
			"message": _("Cannot create {0} from {1}.").format(target_doctype, source_doctype),
		}

	if not source_name:
		return {"ok": False, "message": _("Source {0} is required.").format(source_doctype)}

	sp = "fen_flow_create"
	frappe.db.savepoint(sp)
	try:
		src = frappe.get_doc(source_doctype, source_name)
		src.check_permission("read")
		frappe.has_permission(target_doctype, "create", throw=True)
		if submit:
			frappe.has_permission(target_doctype, "submit", throw=True)

		if src.docstatus != 1:
			frappe.throw(
				_("Submit {0} {1} before creating {2}.").format(source_doctype, source_name, target_doctype)
			)

		if handler in ("_takeoff_mr", "_takeoff_po"):
			return _create_takeoff_doc(src, target_doctype, supplier=supplier, submit=submit, savepoint=sp)

		doc = _map_downstream_doc(
			src, source_doctype, source_name, target_doctype, handler, supplier=supplier, po_no=po_no
		)
		doc.insert()
		if submit:
			doc.submit()
	except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError) as exc:
		frappe.db.rollback(save_point=sp)
		frappe.clear_messages()
		return {"ok": False, "message": _clean_exc_message(exc)}

	frappe.db.release_savepoint(sp)
	return {
		"ok": True,
		"doctype": target_doctype,
		"name": doc.name,
		"status": doc.get("status") or ("Submitted" if doc.docstatus == 1 else "Draft"),
		"docstatus": doc.docstatus,
		"project": _infer_project(doc) or _infer_project(src),
	}


def _create_takeoff_doc(src, target_doctype: str, supplier: str | None, submit: bool, savepoint: str) -> dict:
	project = _infer_project(src)
	if not project:
		frappe.throw(_("{0} {1} is not linked to a Fenestration Project.").format(src.doctype, src.name))
	frappe.has_permission("Fenestration Project", "read", project, throw=True)

	if target_doctype == "Material Request":
		res = takeoff.create_material_request_from_project(project)
		doc_name = res if isinstance(res, str) else (res or {}).get("material_request")
	else:
		res = takeoff.create_purchase_order_from_project(project, supplier=supplier or None)
		doc_name = res if isinstance(res, str) else (res or {}).get("purchase_order")

	if not doc_name:
		frappe.db.rollback(save_point=savepoint)
		frappe.clear_messages()
		return {
			"ok": False,
			"message": _("No {0} could be created for project {1}.").format(target_doctype, project),
		}

	doc = frappe.get_doc(target_doctype, doc_name)
	if submit:
		doc.submit()

	frappe.db.release_savepoint(savepoint)
	return {
		"ok": True,
		"doctype": target_doctype,
		"name": doc.name,
		"status": doc.get("status") or ("Submitted" if doc.docstatus == 1 else "Draft"),
		"docstatus": doc.docstatus,
		"project": project,
	}


def _map_downstream_doc(
	src,
	source_doctype: str,
	source_name: str,
	target_doctype: str,
	mapper_path: str,
	supplier: str | None,
	po_no: str | None,
):
	mapper = frappe.get_attr(mapper_path)
	if target_doctype == "Payment Entry":
		doc = mapper(source_doctype, source_name)
		if flt(doc.paid_amount) <= 0:
			frappe.throw(
				_("No outstanding amount left to pay on {0} {1}.").format(source_doctype, source_name)
			)
		_ensure_payment_reference(doc, source_name)
		return doc

	if source_doctype == "Material Request" and target_doctype == "Purchase Order" and supplier:
		doc = mapper(source_name, args={"supplier": supplier})
	else:
		doc = mapper(source_name)
	if target_doctype == "Sales Order":
		_prepare_sales_order(doc, src, po_no=po_no)
	elif target_doctype == "Purchase Order":
		if supplier and doc.get("supplier") != supplier:
			doc.supplier = supplier
			doc.run_method("set_missing_values")
			doc.run_method("calculate_taxes_and_totals")
		if not doc.get("supplier"):
			frappe.throw(_("Select a Supplier to create a Purchase Order."))

	if not doc.get("items"):
		frappe.throw(
			_("No pending items left on {0} {1} for {2}.").format(source_doctype, source_name, target_doctype)
		)

	_propagate_project(doc, src)
	return doc


def _prepare_sales_order(doc, src, po_no: str | None = None) -> None:
	delivery_date = doc.get("delivery_date") or add_days(nowdate(), 14)
	doc.delivery_date = delivery_date
	for row in doc.get("items") or []:
		if not row.get("delivery_date"):
			row.delivery_date = delivery_date
	if po_no and po_no.strip():
		doc.po_no = po_no.strip()
		if not doc.get("po_date"):
			doc.po_date = nowdate()
	_propagate_project(doc, src)


def _ensure_payment_reference(doc, source_name: str) -> None:
	account_types = {doc.get("paid_from_account_type"), doc.get("paid_to_account_type")}
	if "Bank" in account_types or not doc.get("reference_no"):
		if not doc.get("reference_no"):
			doc.reference_no = source_name
		if not doc.get("reference_date"):
			doc.reference_date = nowdate()


def _propagate_project(doc, src) -> None:
	project = _infer_project(src)
	if project and doc.meta.has_field("fen_project") and not doc.get("fen_project"):
		doc.fen_project = project
	if project and doc.meta.has_field("fen_partner_type") and not doc.get("fen_partner_type"):
		partner_type = frappe.db.get_value("Fenestration Project", project, "fen_partner_type")
		if partner_type:
			doc.fen_partner_type = partner_type


def _infer_project(doc) -> str | None:
	if doc.get("fen_project"):
		return doc.fen_project
	for row in doc.get("items") or []:
		for field, target_dt in (
			("sales_order", "Sales Order"),
			("against_sales_order", "Sales Order"),
			("purchase_order", "Purchase Order"),
			("purchase_receipt", "Purchase Receipt"),
			("delivery_note", "Delivery Note"),
			("material_request", "Material Request"),
		):
			ref = row.get(field)
			if ref and frappe.db.has_column(target_dt, "fen_project"):
				proj = frappe.db.get_value(target_dt, ref, "fen_project")
				if proj:
					return proj
	for ref_row in doc.get("references") or []:
		ref_dt = ref_row.get("reference_doctype")
		ref_name = ref_row.get("reference_name")
		if ref_dt and ref_name and frappe.db.has_column(ref_dt, "fen_project"):
			proj = frappe.db.get_value(ref_dt, ref_name, "fen_project")
			if proj:
				return proj
	return None


def _get_quotation_doc(project: str) -> dict | None:
	if not frappe.has_permission("Quotation", "read"):
		return None
	q_state = quote_status(project)
	q_name = q_state.get("quotation")
	if not q_name:
		rows = frappe.get_list(
			"Quotation",
			filters={"fen_project": project, "docstatus": ["!=", 2]},
			fields=["name"],
			order_by="modified desc",
			limit_page_length=1,
		)
		if not rows:
			return None
		q_name = rows[0]["name"]
	if not frappe.has_permission("Quotation", "read", q_name):
		return None
	row = frappe.db.get_value(
		"Quotation",
		q_name,
		[
			"name",
			"status",
			"docstatus",
			"grand_total",
			"rounded_total",
			"transaction_date",
			"valid_till",
			"modified",
		],
		as_dict=True,
	)
	if not row or row.docstatus == 2:
		return None
	row = dict(row)
	row["grand_total"] = row.get("rounded_total") or row.get("grand_total")
	row["stale"] = bool(q_state.get("is_stale")) if q_name == q_state.get("quotation") else False
	return row


def _get_sales_orders(project: str) -> list[dict]:
	if not frappe.has_permission("Sales Order", "read"):
		return []
	return frappe.get_list(
		"Sales Order",
		filters={"fen_project": project, "docstatus": ["!=", 2]},
		fields=[
			"name",
			"status",
			"docstatus",
			"customer",
			"po_no",
			"transaction_date",
			"delivery_date",
			"per_delivered",
			"per_billed",
			"grand_total",
			"advance_paid",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=50,
	)


def _get_material_requests(project: str) -> list[dict]:
	if not frappe.has_permission("Material Request", "read"):
		return []
	return frappe.get_list(
		"Material Request",
		filters={"fen_project": project, "docstatus": ["!=", 2]},
		fields=[
			"name",
			"status",
			"docstatus",
			"material_request_type",
			"schedule_date",
			"per_ordered",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=50,
	)


def _get_purchase_orders(project: str, mr_names: list[str]) -> list[dict]:
	if not frappe.has_permission("Purchase Order", "read"):
		return []
	names = set(_get_names_by_project("Purchase Order", project))
	if mr_names:
		linked = frappe.get_all(
			"Purchase Order Item",
			filters={"material_request": ["in", mr_names], "docstatus": ["!=", 2]},
			pluck="parent",
		)
		names.update(linked)
	if not names:
		return []
	return frappe.get_list(
		"Purchase Order",
		filters={"name": ["in", list(names)], "docstatus": ["!=", 2]},
		fields=[
			"name",
			"status",
			"docstatus",
			"supplier",
			"supplier_name",
			"transaction_date",
			"schedule_date",
			"per_received",
			"per_billed",
			"grand_total",
			"advance_paid",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=50,
	)


def _get_purchase_receipts(project: str, po_names: list[str]) -> list[dict]:
	if not frappe.has_permission("Purchase Receipt", "read"):
		return []
	names = set(_get_names_by_project("Purchase Receipt", project))
	if po_names:
		linked = frappe.get_all(
			"Purchase Receipt Item",
			filters={"purchase_order": ["in", po_names], "docstatus": ["!=", 2]},
			pluck="parent",
		)
		names.update(linked)
	if not names:
		return []
	return frappe.get_list(
		"Purchase Receipt",
		filters={"name": ["in", list(names)], "docstatus": ["!=", 2]},
		fields=[
			"name",
			"status",
			"docstatus",
			"supplier",
			"supplier_name",
			"posting_date",
			"per_billed",
			"grand_total",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=50,
	)


def _get_purchase_invoices(project: str, po_names: list[str], pr_names: list[str]) -> list[dict]:
	if not frappe.has_permission("Purchase Invoice", "read"):
		return []
	names = set(_get_names_by_project("Purchase Invoice", project))
	if po_names:
		names.update(
			frappe.get_all(
				"Purchase Invoice Item",
				filters={"purchase_order": ["in", po_names], "docstatus": ["!=", 2]},
				pluck="parent",
			)
		)
	if pr_names:
		names.update(
			frappe.get_all(
				"Purchase Invoice Item",
				filters={"purchase_receipt": ["in", pr_names], "docstatus": ["!=", 2]},
				pluck="parent",
			)
		)
	if not names:
		return []
	return frappe.get_list(
		"Purchase Invoice",
		filters={"name": ["in", list(names)], "docstatus": ["!=", 2]},
		fields=[
			"name",
			"status",
			"docstatus",
			"supplier",
			"supplier_name",
			"posting_date",
			"grand_total",
			"outstanding_amount",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=50,
	)


def _get_delivery_notes(project: str, so_names: list[str]) -> list[dict]:
	if not frappe.has_permission("Delivery Note", "read"):
		return []
	names = set(_get_names_by_project("Delivery Note", project))
	if so_names:
		names.update(
			frappe.get_all(
				"Delivery Note Item",
				filters={"against_sales_order": ["in", so_names], "docstatus": ["!=", 2]},
				pluck="parent",
			)
		)
	if not names:
		return []
	return frappe.get_list(
		"Delivery Note",
		filters={"name": ["in", list(names)], "docstatus": ["!=", 2]},
		fields=[
			"name",
			"status",
			"docstatus",
			"customer",
			"posting_date",
			"per_billed",
			"grand_total",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=50,
	)


def _get_sales_invoices(project: str, so_names: list[str], dn_names: list[str]) -> list[dict]:
	if not frappe.has_permission("Sales Invoice", "read"):
		return []
	names = set(_get_names_by_project("Sales Invoice", project))
	if so_names:
		names.update(
			frappe.get_all(
				"Sales Invoice Item",
				filters={"sales_order": ["in", so_names], "docstatus": ["!=", 2]},
				pluck="parent",
			)
		)
	if dn_names:
		names.update(
			frappe.get_all(
				"Sales Invoice Item",
				filters={"delivery_note": ["in", dn_names], "docstatus": ["!=", 2]},
				pluck="parent",
			)
		)
	if not names:
		return []
	return frappe.get_list(
		"Sales Invoice",
		filters={"name": ["in", list(names)], "docstatus": ["!=", 2]},
		fields=[
			"name",
			"status",
			"docstatus",
			"customer",
			"posting_date",
			"grand_total",
			"outstanding_amount",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=50,
	)


def _get_payment_entries(
	so_names: list[str], si_names: list[str], po_names: list[str], pi_names: list[str]
) -> list[dict]:
	if not frappe.has_permission("Payment Entry", "read"):
		return []
	ref_pairs = [
		("Sales Order", so_names),
		("Sales Invoice", si_names),
		("Purchase Order", po_names),
		("Purchase Invoice", pi_names),
	]
	pe_names: set[str] = set()
	pe_refs: dict[str, list[str]] = {}
	for ref_dt, ref_list in ref_pairs:
		if not ref_list:
			continue
		rows = frappe.get_all(
			"Payment Entry Reference",
			filters={"reference_doctype": ref_dt, "reference_name": ["in", ref_list], "docstatus": ["!=", 2]},
			fields=["parent", "reference_doctype", "reference_name"],
		)
		for r in rows:
			pe_names.add(r["parent"])
			pe_refs.setdefault(r["parent"], []).append(f"{r['reference_doctype']} {r['reference_name']}")
	if not pe_names:
		return []
	entries = frappe.get_list(
		"Payment Entry",
		filters={"name": ["in", list(pe_names)], "docstatus": ["!=", 2]},
		fields=[
			"name",
			"status",
			"docstatus",
			"payment_type",
			"party_type",
			"party",
			"party_name",
			"posting_date",
			"paid_amount",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=50,
	)
	for entry in entries:
		entry["references"] = sorted(set(pe_refs.get(entry["name"], [])))
	return entries


def _get_names_by_project(doctype: str, project: str) -> list[str]:
	if not frappe.db.has_column(doctype, "fen_project") or not frappe.has_permission(doctype, "read"):
		return []
	return frappe.get_list(
		doctype,
		filters={"fen_project": project, "docstatus": ["!=", 2]},
		pluck="name",
		limit_page_length=50,
	)


def _list_suppliers() -> list[dict]:
	if not frappe.has_permission("Supplier", "read"):
		return []
	return frappe.get_list(
		"Supplier",
		filters={"disabled": 0},
		fields=["name", "supplier_name"],
		order_by="supplier_name asc",
		limit_page_length=50,
	)


def _submit_action(doctype: str, name: str, label: str = "Submit") -> dict:
	return {
		"id": f"submit-{doctype.lower().replace(' ', '-')}-{name}",
		"kind": "submit",
		"label": label,
		"doctype": doctype,
		"name": name,
		"primary": True,
	}


def _create_action(
	source_doctype: str,
	source_name: str,
	target_doctype: str,
	label: str,
	primary: bool = False,
	requires_supplier: bool = False,
	supports_po_no: bool = False,
) -> dict:
	return {
		"id": f"create-{target_doctype.lower().replace(' ', '-')}-from-{source_name}",
		"kind": "create",
		"label": label,
		"source_doctype": source_doctype,
		"source_name": source_name,
		"target_doctype": target_doctype,
		"primary": primary,
		"requires_supplier": requires_supplier,
		"supports_po_no": supports_po_no,
	}


def _attach_actions(
	*,
	quotation: dict | None,
	sales_orders: list[dict],
	material_requests: list[dict],
	purchase_orders: list[dict],
	purchase_receipts: list[dict],
	purchase_invoices: list[dict],
	delivery_notes: list[dict],
	sales_invoices: list[dict],
	payment_entries: list[dict],
) -> None:
	if quotation:
		if quotation["docstatus"] == 0:
			quotation["actions"] = [_submit_action("Quotation", quotation["name"], "Submit Quotation")]
		elif quotation["docstatus"] == 1:
			quotation["actions"] = [
				_create_action(
					"Quotation",
					quotation["name"],
					"Sales Order",
					"Create Sales Order",
					primary=True,
					supports_po_no=True,
				),
				_create_action(
					"Quotation",
					quotation["name"],
					"Purchase Order",
					"Create Purchase Order",
					requires_supplier=True,
				),
				_create_action("Quotation", quotation["name"], "Material Request", "Create Material Request"),
			]
		else:
			quotation["actions"] = []

	for so in sales_orders:
		if so["docstatus"] == 0:
			so["actions"] = [_submit_action("Sales Order", so["name"], "Submit")]
		elif so["docstatus"] == 1:
			acts = []
			if flt(so.get("per_delivered")) < 100:
				acts.append(
					_create_action(
						"Sales Order", so["name"], "Delivery Note", "Create Delivery Note", primary=True
					)
				)
			if flt(so.get("per_billed")) < 100:
				acts.append(
					_create_action("Sales Order", so["name"], "Sales Invoice", "Create Sales Invoice")
				)
			acts.append(
				_create_action("Sales Order", so["name"], "Material Request", "Create Material Request")
			)
			acts.append(
				_create_action(
					"Sales Order",
					so["name"],
					"Purchase Order",
					"Create Purchase Order",
					requires_supplier=True,
				)
			)
			so["actions"] = acts

	for mr in material_requests:
		if mr["docstatus"] == 0:
			mr["actions"] = [_submit_action("Material Request", mr["name"], "Submit")]
		elif mr["docstatus"] == 1 and flt(mr.get("per_ordered")) < 100:
			mr["actions"] = [
				_create_action(
					"Material Request",
					mr["name"],
					"Purchase Order",
					"Create Purchase Order",
					primary=True,
					requires_supplier=True,
				)
			]
		else:
			mr["actions"] = []

	for po in purchase_orders:
		if po["docstatus"] == 0:
			po["actions"] = [_submit_action("Purchase Order", po["name"], "Submit")]
		elif po["docstatus"] == 1:
			acts = []
			if flt(po.get("per_received")) < 100:
				acts.append(
					_create_action(
						"Purchase Order",
						po["name"],
						"Purchase Receipt",
						"Create Purchase Receipt",
						primary=True,
					)
				)
			if flt(po.get("per_billed")) < 100:
				acts.append(
					_create_action(
						"Purchase Order", po["name"], "Purchase Invoice", "Create Purchase Invoice"
					)
				)
			if flt(po.get("advance_paid")) < flt(po.get("grand_total")):
				acts.append(_create_action("Purchase Order", po["name"], "Payment Entry", "Create Payment"))
			po["actions"] = acts

	for pr in purchase_receipts:
		if pr["docstatus"] == 0:
			pr["actions"] = [_submit_action("Purchase Receipt", pr["name"], "Submit")]
		elif pr["docstatus"] == 1 and flt(pr.get("per_billed")) < 100:
			pr["actions"] = [
				_create_action(
					"Purchase Receipt",
					pr["name"],
					"Purchase Invoice",
					"Create Purchase Invoice",
					primary=True,
				)
			]
		else:
			pr["actions"] = []

	for pi in purchase_invoices:
		if pi["docstatus"] == 0:
			pi["actions"] = [_submit_action("Purchase Invoice", pi["name"], "Submit")]
		elif pi["docstatus"] == 1 and flt(pi.get("outstanding_amount")) > 0:
			pi["actions"] = [
				_create_action(
					"Purchase Invoice", pi["name"], "Payment Entry", "Create Payment Entry", primary=True
				)
			]
		else:
			pi["actions"] = []

	for dn in delivery_notes:
		if dn["docstatus"] == 0:
			dn["actions"] = [_submit_action("Delivery Note", dn["name"], "Submit")]
		elif dn["docstatus"] == 1 and flt(dn.get("per_billed")) < 100:
			dn["actions"] = [
				_create_action(
					"Delivery Note", dn["name"], "Sales Invoice", "Create Sales Invoice", primary=True
				)
			]
		else:
			dn["actions"] = []

	for si in sales_invoices:
		if si["docstatus"] == 0:
			si["actions"] = [_submit_action("Sales Invoice", si["name"], "Submit")]
		elif si["docstatus"] == 1 and flt(si.get("outstanding_amount")) > 0:
			si["actions"] = [
				_create_action(
					"Sales Invoice", si["name"], "Payment Entry", "Create Payment Entry", primary=True
				)
			]
		else:
			si["actions"] = []

	for pe in payment_entries:
		if pe["docstatus"] == 0:
			pe["actions"] = [_submit_action("Payment Entry", pe["name"], "Submit Payment")]
		else:
			pe["actions"] = []


def _build_header_actions(
	*,
	project: str,
	design_count: int,
	quotation: dict | None,
	sales_orders: list[dict],
	material_requests: list[dict],
	purchase_orders: list[dict],
	purchase_receipts: list[dict],
	purchase_invoices: list[dict],
	delivery_notes: list[dict],
	sales_invoices: list[dict],
	payment_entries: list[dict],
	partner_type: str = "Dealer",
) -> tuple[dict | None, list[dict]]:
	create_options = _collect_create_options(
		quotation=quotation,
		sales_orders=sales_orders,
		material_requests=material_requests,
		purchase_orders=purchase_orders,
		purchase_receipts=purchase_receipts,
		purchase_invoices=purchase_invoices,
		delivery_notes=delivery_notes,
		sales_invoices=sales_invoices,
	)
	if partner_type == "Fabrication Partner":
		create_options = [
			opt
			for opt in create_options
			if opt.get("target_doctype") not in ("Material Request", "Purchase Order")
		]

	if design_count == 0:
		return None, create_options

	if not quotation:
		return {
			"id": "make-quotation",
			"kind": "quote",
			"label": "Create Quotation",
			"project": project,
		}, create_options

	if quotation["docstatus"] == 0:
		return _submit_action("Quotation", quotation["name"], f"Submit {quotation['name']}"), create_options

	if quotation.get("stale") and not any(so["docstatus"] == 1 for so in sales_orders):
		return {
			"id": "revise-quotation",
			"kind": "quote",
			"label": "New Quotation Revision",
			"project": project,
		}, create_options

	# Prioritize any draft awaiting submission across the flow.
	draft_queues = [
		("Sales Order", sales_orders),
		("Payment Entry", payment_entries),
		("Purchase Invoice", purchase_invoices),
		("Purchase Receipt", purchase_receipts),
		("Purchase Order", purchase_orders),
		("Material Request", material_requests),
		("Sales Invoice", sales_invoices),
		("Delivery Note", delivery_notes),
	]
	for doctype, rows in draft_queues:
		draft = next((r for r in rows if r["docstatus"] == 0), None)
		if draft:
			return _submit_action(doctype, draft["name"], f"Submit {doctype}"), create_options

	# Otherwise propose the natural next document creation step.
	if not sales_orders:
		return (
			_create_action(
				"Quotation",
				quotation["name"],
				"Sales Order",
				"Create Sales Order",
				primary=True,
				supports_po_no=True,
			),
			create_options,
		)

	collections = {
		"Material Request": material_requests,
		"Purchase Order": purchase_orders,
		"Purchase Receipt": purchase_receipts,
		"Purchase Invoice": purchase_invoices,
		"Sales Order": sales_orders,
		"Delivery Note": delivery_notes,
		"Sales Invoice": sales_invoices,
	}
	for _prio, src_dt, tgt_dt, label, pred, req_sup in _transition_priorities():
		if partner_type == "Fabrication Partner" and tgt_dt in (
			"Material Request",
			"Purchase Order",
			"Purchase Receipt",
			"Purchase Invoice",
		):
			continue
		row = next((r for r in collections[src_dt] if r["docstatus"] == 1 and pred(r)), None)
		if row:
			return (
				_create_action(src_dt, row["name"], tgt_dt, label, primary=True, requires_supplier=req_sup),
				create_options,
			)

	return None, create_options


def _transition_priorities():
	return (
		(
			0,
			"Purchase Receipt",
			"Purchase Invoice",
			"Create Purchase Invoice",
			lambda r: flt(r.get("per_billed")) < 100,
			False,
		),
		(
			1,
			"Purchase Invoice",
			"Payment Entry",
			"Create Payment Entry",
			lambda r: flt(r.get("outstanding_amount")) > 0,
			False,
		),
		(
			2,
			"Purchase Order",
			"Purchase Receipt",
			"Create Purchase Receipt",
			lambda r: flt(r.get("per_received")) < 100,
			False,
		),
		(
			3,
			"Material Request",
			"Purchase Order",
			"Create Purchase Order",
			lambda r: flt(r.get("per_ordered")) < 100,
			True,
		),
		(
			4,
			"Sales Invoice",
			"Payment Entry",
			"Create Payment Entry",
			lambda r: flt(r.get("outstanding_amount")) > 0,
			False,
		),
		(
			5,
			"Delivery Note",
			"Sales Invoice",
			"Create Sales Invoice",
			lambda r: flt(r.get("per_billed")) < 100,
			False,
		),
		(
			6,
			"Sales Order",
			"Delivery Note",
			"Create Delivery Note",
			lambda r: flt(r.get("per_delivered")) < 100,
			False,
		),
	)


def _collect_create_options(
	*,
	quotation: dict | None,
	sales_orders: list[dict],
	material_requests: list[dict],
	purchase_orders: list[dict],
	purchase_receipts: list[dict],
	purchase_invoices: list[dict],
	delivery_notes: list[dict],
	sales_invoices: list[dict],
) -> list[dict]:
	options: list[dict] = []
	for bucket in (
		[quotation] if quotation else [],
		sales_orders,
		material_requests,
		purchase_orders,
		purchase_receipts,
		purchase_invoices,
		delivery_notes,
		sales_invoices,
	):
		for row in bucket:
			if row and row["docstatus"] == 1:
				for act in row.get("actions") or []:
					if act["kind"] == "create":
						options.append(act)
	return options


def _build_stages(
	*,
	quotation: dict | None,
	sales_orders: list[dict],
	material_requests: list[dict],
	purchase_orders: list[dict],
	purchase_receipts: list[dict],
	purchase_invoices: list[dict],
	delivery_notes: list[dict],
	sales_invoices: list[dict],
	payment_entries: list[dict],
	partner_type: str = "Dealer",
) -> list[dict]:
	def _stage_state(rows: list[dict]) -> str:
		if any(r["docstatus"] == 1 for r in rows):
			return "submitted"
		if any(r["docstatus"] == 0 for r in rows):
			return "draft"
		return "pending"

	q_rows = [quotation] if quotation else []
	proc_rows = material_requests + purchase_orders
	rec_bill_rows = purchase_receipts + purchase_invoices
	deliv_rows = delivery_notes + sales_invoices
	if partner_type == "Fabrication Partner":
		return [
			{
				"id": "quote",
				"label": "Material Quote",
				"tab": "quote",
				"state": _stage_state(q_rows),
				"count": len(q_rows),
			},
			{
				"id": "order",
				"label": "Sales Order",
				"tab": "order",
				"state": _stage_state(sales_orders),
				"count": len(sales_orders),
			},
			{
				"id": "install",
				"label": "Material Dispatch & Invoice",
				"tab": "install",
				"state": _stage_state(deliv_rows),
				"count": len(deliv_rows),
			},
			{
				"id": "payment",
				"label": "Payment",
				"tab": "order",
				"state": _stage_state(payment_entries),
				"count": len(payment_entries),
			},
		]
	return [
		{
			"id": "quote",
			"label": "Quote",
			"tab": "quote",
			"state": _stage_state(q_rows),
			"count": len(q_rows),
		},
		{
			"id": "order",
			"label": "Sales Order",
			"tab": "order",
			"state": _stage_state(sales_orders),
			"count": len(sales_orders),
		},
		{
			"id": "po",
			"label": "MR / PO",
			"tab": "production",
			"state": _stage_state(proc_rows),
			"count": len(proc_rows),
		},
		{
			"id": "receipt",
			"label": "Receipt & Bill",
			"tab": "production",
			"state": _stage_state(rec_bill_rows),
			"count": len(rec_bill_rows),
		},
		{
			"id": "payment",
			"label": "Payment",
			"tab": "production",
			"state": _stage_state(payment_entries),
			"count": len(payment_entries),
		},
		{
			"id": "install",
			"label": "Delivery & Invoice",
			"tab": "install",
			"state": _stage_state(deliv_rows),
			"count": len(deliv_rows),
		},
	]


def _clean_exc_message(exc: Exception) -> str:
	msg = frappe.as_unicode(exc) or str(exc)
	return frappe.utils.strip_html(msg).strip() or _("ERPNext rejected this action.")
