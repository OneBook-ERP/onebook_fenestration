import json

import frappe
from frappe import _

from onebook_fenestration.engine import DesignError, RuleError, compute
from onebook_fenestration.fenestration.doctype.window_design.window_design import result_to_dict
from onebook_fenestration.series_studio.snapshot import get_snapshot


@frappe.whitelist()
def compute_design(design: dict | str, series_version: str) -> dict:
	"""Compute cut list, weights and issues; bad designs return errors instead of raising."""
	docstatus = frappe.db.get_value("Series Version", series_version, "docstatus")
	if docstatus is None:
		return {"ok": False, "error_type": "series", "message": _("Series Version not found")}
	frappe.has_permission("Series Version", "read", series_version, throw=True)
	if docstatus != 1:
		return {"ok": False, "error_type": "series", "message": _("Series Version must be published")}
	if isinstance(design, str):
		try:
			design = json.loads(design)
		except json.JSONDecodeError:
			return {"ok": False, "error_type": "design", "message": "design is not valid JSON"}
	try:
		result = compute(design, get_snapshot(series_version))
	except DesignError as exc:
		return {"ok": False, "error_type": "design", "message": str(exc)}
	except RuleError as exc:
		return {"ok": False, "error_type": "series", "message": str(exc)}
	return {"ok": True, "result": result_to_dict(result)}


@frappe.whitelist()
def save_design(
	project: str,
	design_ref: str,
	series_version: str,
	design: dict | str,
	svg: str = "",
	qty: int = 1,
	design_name: str = "",
	location: str = "",
	name: str | None = None,
) -> dict:
	"""Insert a Window Design, or update `name`; results are recomputed by the doc's validate."""
	frappe.has_permission("Window Design", "write" if name else "create", doc=name, throw=True)
	if isinstance(design, str):
		try:
			design = json.loads(design)
		except json.JSONDecodeError:
			return {"ok": False, "message": _("Design JSON is not valid")}
	doc = frappe.get_doc("Window Design", name) if name else frappe.new_doc("Window Design")
	doc.update(
		{
			"project": project,
			"design_ref": design_ref,
			"series_version": series_version,
			"design_json": json.dumps(design),
			"qty": qty,
			"design_name": design_name,
			"location": location,
		}
	)
	if svg:
		doc.design_svg = svg
	try:
		doc.save()
	except frappe.DuplicateEntryError:
		return {"ok": False, "message": _("A design with this ref already exists in this project")}
	except frappe.ValidationError as exc:
		return {"ok": False, "message": str(exc)}
	return {
		"ok": True,
		"name": doc.name,
		"results": {
			"area_sqft": doc.area_sqft,
			"window_kg": doc.window_kg,
			"error_count": doc.error_count,
			"warning_count": doc.warning_count,
		},
	}


@frappe.whitelist()
def get_design(name: str) -> dict:
	"""Return a saved Window Design with its JSON fields parsed."""
	frappe.has_permission("Window Design", "read", name, throw=True)
	doc = frappe.get_doc("Window Design", name)
	out = {
		f: doc.get(f)
		for f in ("name", "project", "design_ref", "design_name", "qty", "location", "series_version", "design_svg")
	}
	for field in ("design_json", "result_json"):
		value = doc.get(field)
		out[field] = json.loads(value) if isinstance(value, str) else value
	return out
