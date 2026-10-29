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
