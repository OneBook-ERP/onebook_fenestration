import frappe

from onebook_fenestration.fenestration import quotation


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
