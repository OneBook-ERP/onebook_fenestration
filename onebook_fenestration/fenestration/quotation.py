import frappe


def reprice_project(project: str) -> dict:
	"""Re-price every design of the project from current Item Prices; one bad design does not stop the rest."""
	frappe.has_permission("Fenestration Project", "write", project, throw=True)
	names = frappe.get_all("Window Design", {"project": project}, pluck="name", order_by="design_ref")
	repriced, failed = 0, []
	for name in names:
		try:
			frappe.get_doc("Window Design", name).reprice()
			repriced += 1
		except frappe.ValidationError as exc:
			failed.append({"design": name, "message": str(exc)})
	return {"repriced": repriced, "failed": failed}
