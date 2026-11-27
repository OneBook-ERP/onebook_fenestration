import frappe

from onebook_fenestration.fenestration import pipeline, quotation
from onebook_fenestration.production import takeoff


@frappe.whitelist()
def reprice_project(project: str) -> dict:
	"""Re-price every design in the project from current Item Prices."""
	return quotation.reprice_project(project)


@frappe.whitelist(methods=["POST"])
def make_quotation(project: str) -> dict:
	"""Build or update the project's draft Quotation; gate failures come back as {"ok": False, "message"}."""
	try:
		return {"ok": True, "quotation": quotation.make_quotation(project)}
	except quotation.QuoteNotReady as exc:
		return {"ok": False, "message": str(exc)}


@frappe.whitelist()
def quote_status(project: str) -> dict:
	return quotation.quote_status(project)


@frappe.whitelist()
def material_tree(project: str) -> dict:
	"""Return the Project -> Window -> Profile / Glass / Hardware BOM hierarchy and procurement summary."""
	frappe.has_permission("Fenestration Project", "read", project, throw=True)
	return takeoff.project_material_tree(project)


@frappe.whitelist(methods=["POST"])
def make_project_material_request(project: str, category: str = "all", warehouse: str | None = None) -> dict:
	"""Create a Draft Material Request from the project's BOM takeoff."""
	frappe.has_permission("Fenestration Project", "read", project, throw=True)
	frappe.has_permission("Material Request", "create", throw=True)
	name = takeoff.create_material_request_from_project(project, category=category, warehouse=warehouse)
	return {"ok": True, "material_request": name}


@frappe.whitelist(methods=["POST"])
def make_project_purchase_order(
	project: str, supplier: str, category: str = "all", warehouse: str | None = None
) -> dict:
	"""Create a Draft Purchase Order directly for a supplier from the project's BOM takeoff."""
	frappe.has_permission("Fenestration Project", "read", project, throw=True)
	frappe.has_permission("Purchase Order", "create", throw=True)
	name = takeoff.create_purchase_order_from_project(
		project, supplier=supplier, category=category, warehouse=warehouse
	)
	return {"ok": True, "purchase_order": name}


@frappe.whitelist()
def project_overview() -> dict:
	"""Return projects with design counts, window quantities, and progression stage."""
	return pipeline.project_overview()


@frappe.whitelist()
def workspace_pipeline(section: str, project: str | None = None) -> dict:
	"""Return overall or single-project pipeline data for quotes, orders, production, install, or reports."""
	return pipeline.workspace_pipeline(section, project=project)


@frappe.whitelist(methods=["POST"])
def make_sales_order(project: str) -> dict:
	"""Create a Draft Sales Order from the project's submitted Quotation."""
	return pipeline.make_sales_order_from_project(project)


@frappe.whitelist()
def quotation_details(quotation: str) -> dict:
	"""Return read-only Quotation header, line items, and taxes for viewing in the app."""
	return pipeline.quotation_details(quotation)


@frappe.whitelist()
def project_flow(project: str) -> dict:
	"""Return the project's full ERPNext document workflow chain and quick actions."""
	from onebook_fenestration.fenestration import flow

	return flow.project_flow_state(project)


@frappe.whitelist(methods=["POST"])
def submit_flow_doc(doctype: str, name: str) -> dict:
	"""Submit a Draft ERPNext document from the Fenestration workspace."""
	from onebook_fenestration.fenestration import flow

	return flow.submit_document(doctype, name)


@frappe.whitelist(methods=["POST"])
def create_flow_doc(
	source_doctype: str,
	source_name: str,
	target_doctype: str,
	supplier: str | None = None,
	po_no: str | None = None,
	submit: int | bool | str = False,
) -> dict:
	"""Create (and optionally submit) the next downstream ERPNext document."""
	from onebook_fenestration.fenestration import flow

	do_submit = submit if isinstance(submit, bool) else str(submit).strip().lower() in ("1", "true", "yes")
	return flow.create_next_document(
		source_doctype,
		source_name,
		target_doctype,
		supplier=supplier,
		po_no=po_no,
		submit=do_submit,
	)


@frappe.whitelist(methods=["POST"])
def share_project_with_hilux(
	project: str,
	notes: str | None = None,
	lock_designs: int | bool | str = True,
) -> dict:
	"""Share a Dealer's Fenestration Project, designs, and reports with Hilux for manufacturing."""
	from onebook_fenestration.fenestration import sharing

	do_lock = (
		lock_designs
		if isinstance(lock_designs, bool)
		else str(lock_designs).strip().lower() not in ("0", "false", "no")
	)
	return sharing.share_project_with_hilux(project, notes=notes, lock_designs=do_lock)


@frappe.whitelist(methods=["POST"])
def unlock_project_designs(project: str, reason: str | None = None) -> dict:
	"""Unlock a shared Dealer project's window designs for revision."""
	from onebook_fenestration.fenestration import sharing

	return sharing.unlock_project_designs(project, reason=reason)


@frappe.whitelist(methods=["POST"])
def update_manufacturing_status(project: str, status: str) -> dict:
	"""Update Hilux manufacturing progress status on a Dealer project."""
	from onebook_fenestration.fenestration import sharing

	return sharing.update_manufacturing_status(project, status)
