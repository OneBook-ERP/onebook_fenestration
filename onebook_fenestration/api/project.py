import frappe

from onebook_fenestration.fenestration import quotation


@frappe.whitelist()
def reprice_project(project: str) -> dict:
	"""Re-price every design in the project from current Item Prices."""
	return quotation.reprice_project(project)
