import dataclasses
import json

import frappe
from frappe import _

from onebook_fenestration.engine import DesignError, RuleError
from onebook_fenestration.engine import cross_section as cut_design
from onebook_fenestration.fenestration.doctype.window_design.window_design import (
	locking_document,
	pricing_to_dict,
	result_to_dict,
)
from onebook_fenestration.pricing.rates import (
	missing_defaults_message,
	price_design,
	resolve_pricing_defaults,
)
from onebook_fenestration.series_studio.outline import rotate_path
from onebook_fenestration.series_studio.snapshot import get_snapshot


@frappe.whitelist()
def compute_design(
	design: dict | str, series_version: str, finish: str | None = None, price_structure: str | None = None
) -> dict:
	"""Compute cut list, weights, price and issues; bad designs return errors instead of raising."""
	design, error = _checked_input(design, series_version)
	if error:
		return error
	finish, price_structure = resolve_pricing_defaults(finish, price_structure)
	if not (finish and price_structure):
		return {"ok": False, "error_type": "series", "message": missing_defaults_message()}
	try:
		result, breakdown = price_design(design, series_version, finish, price_structure)
	except DesignError as exc:
		return {"ok": False, "error_type": "design", "message": str(exc)}
	except (RuleError, frappe.DoesNotExistError) as exc:
		return {"ok": False, "error_type": "series", "message": str(exc)}
	out = result_to_dict(result)
	pricing = pricing_to_dict(breakdown)
	out["issues"] += pricing.pop("issues")
	out["pricing"] = pricing
	return {"ok": True, "result": out, "series": series_info(series_version)}


@frappe.whitelist()
def cross_section(design: dict | str, series_version: str, axis: str, at: float | str | None = None) -> dict:
	"""Profiles and glass one cut line crosses (engine `cross_section`), plus the outline of every profile drawn."""
	design, error = _checked_input(design, series_version)
	if error:
		return error
	try:
		at = None if at in (None, "") else float(at)
	except (TypeError, ValueError):
		return {"ok": False, "error_type": "design", "message": f"cut position must be a number, got {at!r}"}
	try:
		snapshot = get_snapshot(series_version)
		profiles = _profile_sections(sorted(snapshot.profiles))
		widths = {code: p.width_mm for code, p in profiles.items() if p.width_mm}
		section = cut_design(design, snapshot, axis, at, widths)
	except DesignError as exc:
		return {"ok": False, "error_type": "design", "message": str(exc)}
	except RuleError as exc:
		return {"ok": False, "error_type": "series", "message": str(exc)}
	codes = {piece.code for piece in section.pieces if piece.kind == "profile"}
	outlines = {code: _outline(p) for code, p in sorted(profiles.items()) if code in codes and p.section_svg}
	return {"ok": True, "result": json.loads(json.dumps(dataclasses.asdict(section))), "outlines": outlines}


def _outline(profile) -> dict:
	"""The stored outline turned by the profile's `section_rotation`: face along x, bbox at 0,0."""
	if not int(profile.section_rotation or 0):
		return {"svg": profile.section_svg, "width": profile.width_mm, "depth": profile.depth_mm}
	svg, width, depth = rotate_path(profile.section_svg, profile.section_rotation)
	return {"svg": svg, "width": width, "depth": depth}


def _profile_sections(codes: list[str]) -> dict:
	"""Outline and face size of each profile; read without per-user permission, like the series snapshot itself."""
	rows = frappe.get_all(
		"Fenestration Profile",
		filters={"name": ("in", codes or [""])},
		fields=["name", "section_svg", "section_rotation", "width_mm", "depth_mm"],
	)
	return {row.name: row for row in rows}


def _checked_input(design: dict | str, series_version: str) -> tuple[dict | None, dict | None]:
	"""(design dict, None) when the version is published and readable and the design parses; else (None, error)."""
	docstatus = frappe.db.get_value("Series Version", series_version, "docstatus")
	if docstatus is None:
		return None, {"ok": False, "error_type": "series", "message": _("Series Version not found")}
	frappe.has_permission("Series Version", "read", series_version, throw=True)
	if docstatus != 1:
		return None, {"ok": False, "error_type": "series", "message": _("Series Version must be published")}
	if isinstance(design, str):
		try:
			design = json.loads(design)
		except json.JSONDecodeError:
			return None, {"ok": False, "error_type": "design", "message": "design is not valid JSON"}
	return design, None


def series_info(series_version: str) -> dict:
	"""What the designer needs to know of a version: its glass codes and its sash option defaults."""
	snapshot = get_snapshot(series_version)
	return {
		"glasses": sorted(snapshot.glasses),
		"defaults": {
			"limiter": snapshot.constants.get("default_limiter", 0) == 1,
			"mesh": snapshot.constants.get("default_mesh", 0) == 1,
		},
	}


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
	finish: str | None = None,
	price_structure: str | None = None,
) -> dict:
	"""Insert a Window Design, or update `name`; results are recomputed by the doc's validate."""
	frappe.has_permission("Window Design", "write" if name else "create", doc=name, throw=True)
	frappe.has_permission("Fenestration Project", "write", project, throw=True)
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
	if finish:
		doc.finish = finish
	if price_structure:
		doc.price_structure = price_structure
	frappe.db.savepoint("save_design")
	try:
		doc.save()
	except frappe.DuplicateEntryError:
		return _save_failed(_("A design with this ref already exists in this project"))
	except frappe.ValidationError as exc:
		return _save_failed(str(exc))
	frappe.db.release_savepoint("save_design")
	return {
		"ok": True,
		"name": doc.name,
		"results": {
			"area_sqft": doc.area_sqft,
			"window_kg": doc.window_kg,
			"error_count": doc.error_count,
			"warning_count": doc.warning_count,
			"unit_price": doc.unit_price,
			"line_total": doc.line_total,
		},
	}


def _save_failed(message: str) -> dict:
	"""Undo the failed save and drop queued toasts so the caller reports the error once."""
	frappe.db.rollback(save_point="save_design")
	frappe.clear_messages()
	return {"ok": False, "message": message}


@frappe.whitelist()
def get_design(name: str) -> dict:
	"""Return a saved Window Design with its JSON fields parsed."""
	frappe.has_permission("Window Design", "read", name, throw=True)
	doc = frappe.get_doc("Window Design", name)
	fields = (
		"name",
		"project",
		"design_ref",
		"design_name",
		"qty",
		"location",
		"series_version",
		"design_svg",
		"finish",
		"price_structure",
		"unit_price",
		"rate_per_sqft",
		"line_total",
	)
	out = {f: doc.get(f) for f in fields}
	lock = locking_document(name)
	out["locked_by"] = {"doctype": lock[0], "name": lock[1]} if lock else None
	out["finish"], out["price_structure"] = resolve_pricing_defaults(doc.finish, doc.price_structure)
	for field in ("design_json", "result_json", "pricing_json"):
		value = doc.get(field)
		out[field] = json.loads(value) if isinstance(value, str) else value
	return out


COPY_FIELDS = (
	"design_json",
	"series_version",
	"finish",
	"price_structure",
	"qty",
	"location",
	"design_name",
	"design_svg",
)


@frappe.whitelist()
def copy_design(name: str) -> str:
	"""Copy a design's inputs into a new, unlocked design in the same project and mark the original superseded by it;
	returns the copy's name."""
	frappe.has_permission("Window Design", "read", name, throw=True)
	source = frappe.get_doc("Window Design", name)
	frappe.has_permission("Fenestration Project", "write", source.project, throw=True)
	frappe.has_permission("Window Design", "create", throw=True)
	taken = set(frappe.get_all("Window Design", {"project": source.project}, pluck="design_ref"))
	number = 1
	while f"{source.design_ref}-R{number}" in taken:
		number += 1
	doc = frappe.new_doc("Window Design")
	doc.update({f: source.get(f) for f in COPY_FIELDS})
	doc.update({"project": source.project, "design_ref": f"{source.design_ref}-R{number}"})
	doc.insert()
	# Not a locked input, so allowed on a quoted design: new quotations and assembly prints use the copy instead.
	source.db_set("superseded_by", doc.name, update_modified=False)
	return doc.name


@frappe.whitelist()
def get_fenestration_defaults() -> dict:
	"""Default finish and price structure for new designs; readable by any logged-in user."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	return {
		"default_finish": frappe.db.get_single_value("Fenestration Settings", "default_finish"),
		"default_price_structure": frappe.db.get_single_value(
			"Fenestration Settings", "default_price_structure"
		),
	}
