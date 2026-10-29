"""Price Window Designs saved before pricing existed (no finish or price structure yet)."""

import frappe


def execute():
	names = frappe.get_all(
		"Window Design",
		or_filters=[["finish", "is", "not set"], ["price_structure", "is", "not set"]],
		pluck="name",
	)
	for name in names:
		try:
			doc = frappe.get_doc("Window Design", name)
			doc.set_pricing_defaults()
			doc.compute_results()
			doc.db_update()
		except Exception:
			frappe.log_error(
				title=f"Could not price Window Design {name}",
				reference_doctype="Window Design",
				reference_name=name,
			)
