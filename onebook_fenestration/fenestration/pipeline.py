"""Cross-project and project-scoped pipeline queries for Quotes, Orders, Production, Install, and Reports."""

import frappe
from frappe import _
from frappe.utils import add_days, flt, nowdate


def project_overview() -> dict:
	"""Return permitted projects with design counts, window quantities, and progression stage."""
	projects = _permitted_projects()
	if not projects:
		return {
			"stats": {
				"total_projects": 0,
				"total_designs": 0,
				"total_windows": 0,
				"quoted_or_ordered": 0,
				"in_production": 0,
			},
			"projects": [],
		}

	project_names = [p["name"] for p in projects]
	design_stats = _aggregate_design_stats(project_names)
	quote_stages = _resolve_quotation_stages([p["quotation"] for p in projects if p.get("quotation")])

	enriched = []
	total_designs = 0
	total_windows = 0
	quoted_or_ordered = 0
	in_production = 0

	for p in projects:
		ds = design_stats.get(p["name"], _empty_design_stat())
		q_name = p.get("quotation")
		stage = _derive_project_stage(ds["design_count"], quote_stages.get(q_name) if q_name else None)

		total_designs += ds["design_count"]
		total_windows += ds["window_qty"]
		if stage in ("Quotation", "Order", "Production"):
			quoted_or_ordered += 1
		if stage == "Production":
			in_production += 1

		enriched.append(
			{
				**p,
				"design_count": ds["design_count"],
				"window_qty": ds["window_qty"],
				"total_area_sqft": round(ds["total_area_sqft"], 1),
				"total_weight_kg": round(ds["total_weight_kg"], 1),
				"total_value": round(ds["total_value"], 2),
				"stage": stage,
			}
		)

	return {
		"stats": {
			"total_projects": len(enriched),
			"total_designs": total_designs,
			"total_windows": total_windows,
			"quoted_or_ordered": quoted_or_ordered,
			"in_production": in_production,
		},
		"projects": enriched,
	}


def workspace_pipeline(section: str, project: str | None = None) -> dict:
	"""Return overall or single-project pipeline data for quotes, orders, production, install, or reports."""
	if project:
		frappe.has_permission("Fenestration Project", "read", project, throw=True)
	projects = _permitted_projects(project)
	if not projects:
		return {"stats": {}, "items": [], "pending_orders": []}

	project_map = {p["name"]: p for p in projects}
	handlers = {
		"quotes": _quotes_pipeline,
		"orders": _orders_pipeline,
		"production": _production_pipeline,
		"install": _install_pipeline,
		"reports": _reports_pipeline,
	}
	handler = handlers.get(section)
	if not handler:
		frappe.throw(_("Unknown pipeline section: {0}").format(section))
	return handler(project_map)


def make_sales_order_from_project(project: str) -> dict:
	"""Create a Draft Sales Order from the project's submitted Quotation."""
	frappe.has_permission("Fenestration Project", "write", project, throw=True)
	frappe.has_permission("Sales Order", "create", throw=True)
	quotation_name = frappe.db.get_value("Fenestration Project", project, "quotation")
	if not quotation_name:
		return {"ok": False, "message": _("Create a Quotation for this project first.")}

	docstatus = frappe.db.get_value("Quotation", quotation_name, "docstatus")
	if docstatus == 0:
		return {
			"ok": False,
			"message": _("Quotation {0} is still a Draft. Submit it in Desk before creating a Sales Order.").format(
				quotation_name
			),
		}
	if docstatus == 2:
		return {"ok": False, "message": _("Quotation {0} is cancelled.").format(quotation_name)}

	from erpnext.selling.doctype.quotation.quotation import make_sales_order

	so = make_sales_order(quotation_name)
	so.fen_project = project
	if not so.delivery_date:
		so.delivery_date = add_days(nowdate(), 14)
	so.insert()
	return {"ok": True, "sales_order": so.name}


def _permitted_projects(project: str | None = None) -> list[dict]:
	filters = {"name": project} if project else {}
	fields = [
		"name",
		"project_title",
		"customer",
		"site_address",
		"default_series_version",
		"quotation",
		"modified",
	]
	for opt_field in (
		"fen_partner_type",
		"fen_shared_with_hilux",
		"fen_shared_on",
		"fen_shared_by",
		"fen_manufacturing_status",
		"fen_design_locked",
	):
		if frappe.db.has_column("Fenestration Project", opt_field):
			fields.append(opt_field)
	return frappe.get_list(
		"Fenestration Project",
		filters=filters,
		fields=fields,
		order_by="modified desc",
		limit_page_length=200,
	)


def _quotes_pipeline(project_map: dict[str, dict]) -> dict:
	names = list(project_map.keys())
	design_stats = _aggregate_design_stats(names)
	rows = frappe.get_list(
		"Quotation",
		filters={"fen_project": ["in", names]},
		fields=[
			"name",
			"fen_project",
			"customer_name",
			"party_name",
			"transaction_date",
			"valid_till",
			"docstatus",
			"status",
			"grand_total",
			"rounded_total",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=200,
	)
	items = []
	draft = 0
	submitted = 0
	ordered = 0
	total_value = 0.0
	for r in rows:
		if r["docstatus"] == 0:
			draft += 1
		elif r["docstatus"] == 1:
			submitted += 1
			if r["status"] == "Ordered":
				ordered += 1
		val = flt(r["rounded_total"] or r["grand_total"])
		if r["docstatus"] != 2:
			total_value += val
		proj = project_map.get(r["fen_project"], {})
		ds = design_stats.get(r["fen_project"], _empty_design_stat())
		items.append(
			{
				**r,
				"project_title": proj.get("project_title") or r["fen_project"],
				"customer": r["customer_name"] or r["party_name"] or proj.get("customer") or "",
				"amount": round(val, 2),
				"design_count": ds["design_count"],
				"window_qty": ds["window_qty"],
			}
		)
	return {
		"stats": {
			"total": len(items),
			"draft": draft,
			"submitted": submitted,
			"ordered": ordered,
			"total_value": round(total_value, 2),
		},
		"items": items,
	}


def _orders_pipeline(project_map: dict[str, dict]) -> dict:
	rows = _project_sales_orders(project_map)
	draft = 0
	to_deliver = 0
	completed = 0
	total_value = 0.0
	for r in rows:
		if r["docstatus"] == 0:
			draft += 1
		elif r["status"] == "Completed":
			completed += 1
		elif r["docstatus"] == 1 and flt(r["per_delivered"]) < 100:
			to_deliver += 1
		if r["docstatus"] != 2:
			total_value += flt(r["amount"])

	return {
		"stats": {
			"total": len(rows),
			"draft": draft,
			"to_deliver": to_deliver,
			"completed": completed,
			"total_value": round(total_value, 2),
		},
		"items": rows,
	}


def _production_pipeline(project_map: dict[str, dict]) -> dict:
	names = list(project_map.keys())
	sales_orders = _project_sales_orders(project_map)
	so_project = {so["name"]: so["fen_project"] for so in sales_orders}
	so_names = list(so_project.keys())

	items = []
	wo_count = 0
	in_progress = 0
	completed_units = 0
	mr_count = 0
	po_count = 0

	if so_names:
		wos = frappe.get_list(
			"Work Order",
			filters={"sales_order": ["in", so_names]},
			fields=["name", "production_item", "item_name", "sales_order", "qty", "produced_qty", "status", "docstatus", "planned_start_date", "modified"],
			order_by="modified desc",
			limit_page_length=200,
		)
		for w in wos:
			wo_count += 1
			if w["status"] in ("In Process", "Not Started") and w["docstatus"] == 1:
				in_progress += 1
			completed_units += int(flt(w["produced_qty"]))
			proj_name = so_project.get(w["sales_order"], "")
			qty = flt(w["qty"])
			pct = round((flt(w["produced_qty"]) / qty) * 100, 1) if qty else 0
			items.append(
				{
					"doctype": "Work Order",
					"name": w["name"],
					"fen_project": proj_name,
					"project_title": project_map.get(proj_name, {}).get("project_title") or proj_name,
					"subtitle": w["item_name"] or w["production_item"] or w["sales_order"],
					"status": w["status"],
					"docstatus": w["docstatus"],
					"qty": qty,
					"produced_qty": flt(w["produced_qty"]),
					"progress_pct": pct,
					"date": str(w["planned_start_date"] or w["modified"])[:10],
				}
			)

	mrs = frappe.get_list(
		"Material Request",
		filters={"fen_project": ["in", names]},
		fields=["name", "fen_project", "material_request_type", "set_warehouse", "status", "docstatus", "per_ordered", "transaction_date", "modified"],
		order_by="modified desc",
		limit_page_length=200,
	)
	for m in mrs:
		mr_count += 1
		proj_name = m["fen_project"]
		items.append(
			{
				"doctype": "Material Request",
				"name": m["name"],
				"fen_project": proj_name,
				"project_title": project_map.get(proj_name, {}).get("project_title") or proj_name,
				"subtitle": m["set_warehouse"] or m["material_request_type"],
				"status": m["status"],
				"docstatus": m["docstatus"],
				"qty": None,
				"produced_qty": None,
				"progress_pct": round(flt(m["per_ordered"]), 1),
				"date": str(m["transaction_date"] or m["modified"])[:10],
			}
		)

	pos = frappe.get_list(
		"Purchase Order",
		filters={"fen_project": ["in", names]},
		fields=["name", "fen_project", "supplier_name", "supplier", "status", "docstatus", "per_received", "grand_total", "transaction_date", "modified"],
		order_by="modified desc",
		limit_page_length=200,
	)
	for p in pos:
		po_count += 1
		proj_name = p["fen_project"]
		items.append(
			{
				"doctype": "Purchase Order",
				"name": p["name"],
				"fen_project": proj_name,
				"project_title": project_map.get(proj_name, {}).get("project_title") or proj_name,
				"subtitle": p["supplier_name"] or p["supplier"],
				"status": p["status"],
				"docstatus": p["docstatus"],
				"qty": None,
				"produced_qty": None,
				"progress_pct": round(flt(p["per_received"]), 1),
				"date": str(p["transaction_date"] or p["modified"])[:10],
			}
		)

	items.sort(key=lambda x: x.get("date") or "", reverse=True)
	return {
		"stats": {
			"work_orders": wo_count,
			"in_progress": in_progress,
			"material_requests": mr_count,
			"purchase_orders": po_count,
			"completed_units": completed_units,
		},
		"items": items,
	}


def _install_pipeline(project_map: dict[str, dict]) -> dict:
	sales_orders = _project_sales_orders(project_map)
	so_project = {so["name"]: so["fen_project"] for so in sales_orders}
	so_names = list(so_project.keys())

	deliveries = []
	dispatched_qty = 0
	installed_count = 0

	if so_names:
		dn_links = frappe.get_all(
			"Delivery Note Item",
			filters={"against_sales_order": ["in", so_names]},
			fields=["parent", "against_sales_order"],
		)
		dn_to_proj: dict[str, str] = {}
		for link in dn_links:
			if link["parent"] not in dn_to_proj and link["against_sales_order"] in so_project:
				dn_to_proj[link["parent"]] = so_project[link["against_sales_order"]]

		if dn_to_proj:
			dns = frappe.get_list(
				"Delivery Note",
				filters={"name": ["in", list(dn_to_proj.keys())]},
				fields=["name", "customer_name", "customer", "posting_date", "status", "docstatus", "total_qty", "per_installed", "modified"],
				order_by="modified desc",
				limit_page_length=200,
			)
			for dn in dns:
				proj_name = dn_to_proj.get(dn["name"], "")
				proj = project_map.get(proj_name, {})
				if dn["docstatus"] == 1:
					dispatched_qty += int(flt(dn["total_qty"]))
				if flt(dn["per_installed"]) >= 100 or dn["status"] == "Completed":
					installed_count += 1
				deliveries.append(
					{
						"name": dn["name"],
						"fen_project": proj_name,
						"project_title": proj.get("project_title") or proj_name,
						"customer": dn["customer_name"] or dn["customer"] or proj.get("customer") or "",
						"site_address": proj.get("site_address") or "",
						"posting_date": str(dn["posting_date"] or dn["modified"])[:10],
						"status": dn["status"],
						"docstatus": dn["docstatus"],
						"total_qty": int(flt(dn["total_qty"])),
						"per_installed": round(flt(dn["per_installed"]), 1),
					}
				)

	pending_orders = [
		so for so in sales_orders if so["docstatus"] == 1 and flt(so["per_delivered"]) < 100
	]
	return {
		"stats": {
			"total_deliveries": len(deliveries),
			"pending_dispatch": len(pending_orders),
			"dispatched_qty": dispatched_qty,
			"installed_count": installed_count,
		},
		"items": deliveries,
		"pending_orders": pending_orders,
	}


def _reports_pipeline(project_map: dict[str, dict]) -> dict:
	names = list(project_map.keys())
	design_stats = _aggregate_design_stats(names)
	quote_stages = _resolve_quotation_stages(
		[p["quotation"] for p in project_map.values() if p.get("quotation")]
	)
	items = []
	total_windows = 0
	total_area = 0.0
	total_weight = 0.0
	total_value = 0.0

	for p in project_map.values():
		ds = design_stats.get(p["name"], _empty_design_stat())
		stage = _derive_project_stage(ds["design_count"], quote_stages.get(p.get("quotation") or ""))
		total_windows += ds["window_qty"]
		total_area += ds["total_area_sqft"]
		total_weight += ds["total_weight_kg"]
		total_value += ds["total_value"]
		items.append(
			{
				"name": p["name"],
				"project_title": p["project_title"] or p["name"],
				"customer": p["customer"] or "",
				"quotation": p.get("quotation") or "",
				"stage": stage,
				"design_count": ds["design_count"],
				"window_qty": ds["window_qty"],
				"total_area_sqft": round(ds["total_area_sqft"], 2),
				"total_weight_kg": round(ds["total_weight_kg"], 1),
				"total_value": round(ds["total_value"], 2),
			}
		)

	return {
		"stats": {
			"total_projects": len(items),
			"total_windows": total_windows,
			"total_area_sqft": round(total_area, 1),
			"total_weight_kg": round(total_weight, 1),
			"total_value": round(total_value, 2),
		},
		"items": items,
	}


def _project_sales_orders(project_map: dict[str, dict]) -> list[dict]:
	names = list(project_map.keys())
	quote_to_proj = {p["quotation"]: p["name"] for p in project_map.values() if p.get("quotation")}
	so_names: set[str] = set()
	so_from_quote: dict[str, str] = {}

	if quote_to_proj:
		so_items = frappe.get_all(
			"Sales Order Item",
			filters={"prevdoc_docname": ["in", list(quote_to_proj.keys())]},
			fields=["parent", "prevdoc_docname"],
		)
		for row in so_items:
			so_names.add(row["parent"])
			if row["prevdoc_docname"] in quote_to_proj:
				so_from_quote[row["parent"]] = quote_to_proj[row["prevdoc_docname"]]

	direct_sos = frappe.get_list(
		"Sales Order",
		filters={"fen_project": ["in", names]},
		fields=["name"],
		limit_page_length=200,
	)
	for row in direct_sos:
		so_names.add(row["name"])

	if not so_names:
		return []

	rows = frappe.get_list(
		"Sales Order",
		filters={"name": ["in", list(so_names)]},
		fields=[
			"name",
			"fen_project",
			"customer_name",
			"customer",
			"transaction_date",
			"delivery_date",
			"docstatus",
			"status",
			"per_delivered",
			"per_billed",
			"grand_total",
			"rounded_total",
			"total_qty",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=200,
	)
	result = []
	for r in rows:
		proj_name = r.get("fen_project") or so_from_quote.get(r["name"], "")
		if proj_name not in project_map:
			continue
		proj = project_map[proj_name]
		val = flt(r["rounded_total"] or r["grand_total"])
		result.append(
			{
				**r,
				"fen_project": proj_name,
				"project_title": proj.get("project_title") or proj_name,
				"customer": r["customer_name"] or r["customer"] or proj.get("customer") or "",
				"amount": round(val, 2),
				"per_delivered": round(flt(r["per_delivered"]), 1),
				"per_billed": round(flt(r["per_billed"]), 1),
				"total_qty": int(flt(r["total_qty"])),
			}
		)
	return result


def _empty_design_stat() -> dict:
	return {"design_count": 0, "window_qty": 0, "total_area_sqft": 0.0, "total_weight_kg": 0.0, "total_value": 0.0}


def _aggregate_design_stats(project_names: list[str]) -> dict[str, dict]:
	if not project_names:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT
			project,
			COUNT(name) AS design_count,
			COALESCE(SUM(COALESCE(qty, 0)), 0) AS window_qty,
			COALESCE(SUM(COALESCE(area_sqft, 0) * COALESCE(qty, 0)), 0) AS total_area_sqft,
			COALESCE(SUM(COALESCE(window_kg, 0) * COALESCE(qty, 0)), 0) AS total_weight_kg,
			COALESCE(SUM(COALESCE(line_total, 0)), 0) AS total_value
		FROM `tabWindow Design`
		WHERE project IN %s
			AND COALESCE(superseded_by, '') = ''
		GROUP BY project
		""",
		(tuple(project_names),),
		as_dict=True,
	)
	return {
		r["project"]: {
			"design_count": int(r["design_count"] or 0),
			"window_qty": int(r["window_qty"] or 0),
			"total_area_sqft": float(r["total_area_sqft"] or 0.0),
			"total_weight_kg": float(r["total_weight_kg"] or 0.0),
			"total_value": float(r["total_value"] or 0.0),
		}
		for r in rows
	}


def _resolve_quotation_stages(quote_names: list[str]) -> dict[str, str]:
	if not quote_names:
		return {}

	quotes = frappe.get_all(
		"Quotation",
		filters={"name": ["in", quote_names]},
		fields=["name", "docstatus", "status"],
	)
	active_quotes = {q["name"]: q for q in quotes if q["docstatus"] != 2}
	if not active_quotes:
		return {}

	so_rows = frappe.get_all(
		"Sales Order Item",
		filters={"prevdoc_docname": ["in", list(active_quotes.keys())], "docstatus": 1},
		fields=["prevdoc_docname", "parent"],
	)
	quote_to_orders: dict[str, set[str]] = {}
	all_orders: set[str] = set()
	for r in so_rows:
		quote_to_orders.setdefault(r["prevdoc_docname"], set()).add(r["parent"])
		all_orders.add(r["parent"])

	orders_in_production: set[str] = set()
	if all_orders:
		wo_rows = frappe.get_all(
			"Work Order",
			filters={"sales_order": ["in", list(all_orders)], "docstatus": ["!=", 2]},
			fields=["sales_order"],
		)
		orders_in_production = {w["sales_order"] for w in wo_rows}

	stages: dict[str, str] = {}
	for q_name, q in active_quotes.items():
		orders = quote_to_orders.get(q_name, set())
		if orders & orders_in_production:
			stages[q_name] = "Production"
		elif orders or q["status"] == "Ordered":
			stages[q_name] = "Order"
		else:
			stages[q_name] = "Quotation"
	return stages


def _derive_project_stage(design_count: int, quote_stage: str | None) -> str:
	if quote_stage:
		return quote_stage
	return "Designing" if design_count > 0 else "Draft"


def quotation_details(quotation_name: str) -> dict:
	"""Return read-only Quotation header, line items, and tax breakdown for in-app viewing."""
	frappe.has_permission("Quotation", "read", quotation_name, throw=True)
	q = frappe.get_doc("Quotation", quotation_name)
	return {
		"name": q.name,
		"fen_project": q.get("fen_project") or "",
		"customer_name": q.customer_name or q.party_name or "",
		"address_display": q.address_display or "",
		"contact_display": q.contact_display or "",
		"contact_mobile": q.contact_mobile or "",
		"contact_email": q.contact_email or "",
		"transaction_date": str(q.transaction_date or ""),
		"valid_till": str(q.valid_till or ""),
		"docstatus": q.docstatus,
		"status": q.status or "",
		"currency": q.currency or "INR",
		"net_total": round(flt(q.net_total), 2),
		"total_taxes_and_charges": round(flt(q.total_taxes_and_charges), 2),
		"grand_total": round(flt(q.grand_total), 2),
		"rounded_total": round(flt(q.rounded_total or q.grand_total), 2),
		"in_words": q.in_words or "",
		"tc_name": q.tc_name or "",
		"terms": q.terms or "",
		"items": [
			{
				"idx": row.idx,
				"item_code": row.item_code,
				"item_name": row.item_name or row.item_code,
				"description": row.description or "",
				"fen_window_design": row.get("fen_window_design") or "",
				"qty": flt(row.qty),
				"uom": row.uom or "",
				"rate": round(flt(row.rate), 2),
				"amount": round(flt(row.amount), 2),
			}
			for row in (q.items or [])
		],
		"taxes": [
			{
				"idx": row.idx,
				"charge_type": row.charge_type or "",
				"account_head": row.account_head or "",
				"description": row.description or row.account_head or "",
				"rate": flt(row.rate),
				"tax_amount": round(flt(row.tax_amount), 2),
				"total": round(flt(row.total), 2),
			}
			for row in (q.taxes or [])
		],
	}

