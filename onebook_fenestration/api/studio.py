import json

import frappe
from frappe import _

from onebook_fenestration.engine import SectionError, analyze_dxf
from onebook_fenestration.engine.section_config import (
	normalize_glass_glazing_rules,
	normalize_glazing_auto_config,
	normalize_global_glazing_rules,
	normalize_profile_anchors,
	normalize_section_config,
	normalize_supported_products,
)
from onebook_fenestration.series_studio.outline import compose_section_transform
from onebook_fenestration.series_studio.snapshot import clear_snapshot


@frappe.whitelist()
def preview_dxf(file_url: str) -> dict:
	"""Analyze an uploaded DXF file and return its computed cross-section properties and SVG path."""
	if not (
		frappe.has_permission("Fenestration Profile", "read")
		or frappe.has_permission("Fenestration Hardware", "read")
	):
		frappe.has_permission("Fenestration Profile", "read", throw=True)
	if not file_url or not isinstance(file_url, str):
		return {"ok": False, "message": _("No DXF file URL provided")}
	if not file_url.lower().endswith(".dxf"):
		return {"ok": False, "message": _("Only .dxf files can be previewed")}
	try:
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		file_doc.check_permission("read")
		section = analyze_dxf(file_doc.get_full_path())
	except frappe.PermissionError:
		raise
	except OSError:
		return {"ok": False, "message": _("Could not read the uploaded DXF file from storage")}
	except (SectionError, frappe.DoesNotExistError) as exc:
		return {"ok": False, "message": _("Could not read section from DXF: {0}").format(str(exc))}

	return {
		"ok": True,
		"section": {
			"area_mm2": round(section.area_mm2, 1),
			"width_mm": round(section.width_mm, 1),
			"depth_mm": round(section.depth_mm, 1),
			"perimeter_mm": round(section.perimeter_mm, 1),
			"total_perimeter_mm": round(section.perimeter_mm, 1),
			"ix_mm4": round(section.ix_mm4),
			"iy_mm4": round(section.iy_mm4),
			"computed_kg_per_m": round(section.kg_per_m, 3),
			"section_svg": section.svg_path,
			"section_warnings": ", ".join(section.warnings),
		},
	}


def _as_bool(value) -> bool:
	if isinstance(value, bool):
		return value
	if isinstance(value, (int, float)):
		return bool(int(value))
	return str(value or "").strip().lower() in ("1", "true", "yes")


@frappe.whitelist(methods=["POST"])
def set_profile_orientation(
	profile_name: str,
	rotation: int | str | None = None,
	delta: int | str | None = None,
	flip_x: int | bool | str | None = None,
	flip_y: int | bool | str | None = None,
	delta_flip_x: int | bool | str | None = None,
	delta_flip_y: int | bool | str | None = None,
) -> dict:
	"""Set the default section orientation (rotation 0/90/180/270 and flip_x / flip_y) on a Fenestration Profile.

	Accepts either absolute (`rotation`, `flip_x`, `flip_y`) or incremental (`delta`, `delta_flip_x`, `delta_flip_y`)
	relative to the profile's current default orientation.
	"""
	frappe.has_permission("Fenestration Profile", "write", throw=True)
	if not frappe.db.exists("Fenestration Profile", profile_name):
		actual_name = frappe.db.get_value("Fenestration Profile", {"profile_code": profile_name}, "name")
		if actual_name:
			profile_name = actual_name
	doc = frappe.get_doc("Fenestration Profile", profile_name)
	cur_rot = int(doc.section_rotation or 0)
	cur_fx = bool(int(getattr(doc, "section_flip_x", 0) or 0))
	cur_fy = bool(int(getattr(doc, "section_flip_y", 0) or 0))

	has_delta = any(v is not None and str(v).strip() != "" for v in (delta, delta_flip_x, delta_flip_y))
	has_abs = any(v is not None and str(v).strip() != "" for v in (rotation, flip_x, flip_y))
	if has_delta and not has_abs:
		d_rot = (((int(delta or 0)) % 360) + 360) % 360
		d_fx = _as_bool(delta_flip_x) if delta_flip_x is not None else False
		d_fy = _as_bool(delta_flip_y) if delta_flip_y is not None else False
		if d_rot not in (0, 90, 180, 270):
			frappe.throw(_("Rotation must be 0, 90, 180, or 270 degrees."))
		rot_int, fx_int, fy_int = compose_section_transform(cur_rot, cur_fx, cur_fy, d_rot, d_fx, d_fy)
	else:
		rot_int = (((int(rotation if rotation is not None and str(rotation).strip() else cur_rot)) % 360) + 360) % 360
		if rot_int not in (0, 90, 180, 270):
			frappe.throw(_("Rotation must be 0, 90, 180, or 270 degrees."))
		fx_int = int(_as_bool(flip_x) if flip_x is not None else cur_fx)
		fy_int = int(_as_bool(flip_y) if flip_y is not None else cur_fy)

	doc.section_rotation = str(rot_int)
	if hasattr(doc, "section_flip_x"):
		doc.section_flip_x = fx_int
	if hasattr(doc, "section_flip_y"):
		doc.section_flip_y = fy_int
	doc.save()
	return {
		"ok": True,
		"profile_name": doc.name,
		"section_rotation": doc.section_rotation,
		"section_flip_x": fx_int,
		"section_flip_y": fy_int,
		"width_mm": doc.width_mm,
		"depth_mm": doc.depth_mm,
	}


@frappe.whitelist()
def get_series_section_config(series: str) -> dict:
	"""Return the normalized auto section configuration for a Profile Series along with its profiles, glasses, and gaskets."""
	doc = frappe.get_doc("Profile Series", series)
	doc.check_permission("read")
	raw_cfg = getattr(doc, "section_config_json", None)
	config = normalize_section_config(raw_cfg)

	profiles = frappe.get_list(
		"Fenestration Profile",
		filters={"series": doc.name},
		fields=[
			"name",
			"profile_code",
			"profile_name",
			"series",
			"role",
			"profile_type",
			"width_mm",
			"depth_mm",
			"section_svg",
			"section_rotation",
			"section_flip_x",
			"section_flip_y",
			"section_anchors_json",
		],
		order_by="role asc, profile_code asc",
		limit_page_length=500,
	)
	for p in profiles:
		p["section_anchors"] = normalize_profile_anchors(p.get("section_anchors_json"))
	glasses = frappe.get_list(
		"Fenestration Glass",
		fields=["name", "glass_code", "glass_name", "thickness_mm", "glazing_rules_json"],
		order_by="thickness_mm asc, glass_code asc",
		limit_page_length=200,
	)
	for g in glasses:
		g["glazing_rules"] = normalize_glass_glazing_rules(g.get("glazing_rules_json"))
	gaskets = []
	if frappe.has_permission("Item", "read"):
		gaskets = frappe.get_list(
			"Item",
			filters={"fen_item_kind": "Gasket"},
			fields=["name", "item_name", "stock_uom"],
			order_by="name asc",
			limit_page_length=200,
		)
		if not gaskets:
			gaskets = frappe.get_list(
				"Item",
				filters={"item_name": ("like", "%gasket%")},
				fields=["name", "item_name", "stock_uom"],
				order_by="name asc",
				limit_page_length=200,
			)
	preview_series_version = doc.published_version
	if not preview_series_version and frappe.has_permission("Series Version", "read"):
		latest = frappe.get_list(
			"Series Version",
			filters={"series": doc.name},
			pluck="name",
			order_by="docstatus desc, modified desc",
			limit_page_length=1,
		)
		preview_series_version = latest[0] if latest else None

	global_rules = []
	global_auto = {}
	if frappe.db.exists("DocType", "Fenestration Glazing Settings"):
		global_rules = normalize_global_glazing_rules(
			frappe.db.get_single_value("Fenestration Glazing Settings", "rules_json")
		)
		raw_auto = frappe.db.get_single_value("Fenestration Glazing Settings", "auto_config_json")
		global_auto = normalize_glazing_auto_config(raw_auto)

	gasket_hardware = []
	if frappe.db.exists("DocType", "Fenestration Hardware") and frappe.has_permission(
		"Fenestration Hardware", "read"
	):
		gasket_hardware = frappe.get_list(
			"Fenestration Hardware",
			filters={"category": ("in", ["Gasket", "Seal / Weatherstrip"])},
			fields=["name", "hardware_code", "hardware_name", "category", "item", "thickness_mm"],
			order_by="thickness_mm asc, hardware_code asc",
			limit_page_length=200,
		)

	return {
		"ok": True,
		"series": {
			"name": doc.name,
			"series_code": doc.series_code,
			"series_title": doc.series_title,
			"system_type": doc.system_type,
			"published_version": doc.published_version,
			"supported_products": normalize_supported_products(getattr(doc, "supported_products", None)),
		},
		"preview_series_version": preview_series_version,
		"config": config,
		"global_glazing_rules": global_rules,
		"global_glazing_auto": global_auto,
		"gasket_hardware": gasket_hardware,
		"profiles": profiles,
		"glasses": glasses,
		"gaskets": gaskets,
	}


@frappe.whitelist(methods=["POST"])
def save_series_section_config(series: str, config: dict | str) -> dict:
	"""Validate, normalize, and persist `section_config_json` on a Profile Series."""
	frappe.has_permission("Profile Series", "write", throw=True)
	doc = frappe.get_doc("Profile Series", series)
	normalized = normalize_section_config(config)
	doc.section_config_json = json.dumps(normalized, indent=2)
	doc.save()
	for ver in frappe.get_all("Series Version", filters={"series": doc.name}, pluck="name"):
		clear_snapshot(ver)
	return {"ok": True, "series": doc.name, "config": normalized}


@frappe.whitelist(methods=["POST"])
def set_hardware_orientation(
	hardware_name: str,
	rotation: int | str | None = None,
	flip_x: int | bool | str | None = None,
	flip_y: int | bool | str | None = None,
) -> dict:
	"""Set default CAD section orientation on a Fenestration Hardware record."""
	frappe.has_permission("Fenestration Hardware", "write", throw=True)
	doc = frappe.get_doc("Fenestration Hardware", hardware_name)
	rot_int = (((int(rotation if rotation is not None and str(rotation).strip() else (doc.section_rotation or 0))) % 360) + 360) % 360
	if rot_int not in (0, 90, 180, 270):
		frappe.throw(_("Rotation must be 0, 90, 180, or 270 degrees."))
	fx_int = int(_as_bool(flip_x) if flip_x is not None else bool(int(doc.section_flip_x or 0)))
	fy_int = int(_as_bool(flip_y) if flip_y is not None else bool(int(doc.section_flip_y or 0)))
	doc.section_rotation = str(rot_int)
	doc.section_flip_x = fx_int
	doc.section_flip_y = fy_int
	doc.save()
	return {
		"ok": True,
		"hardware_name": doc.name,
		"section_rotation": doc.section_rotation,
		"section_flip_x": fx_int,
		"section_flip_y": fy_int,
		"width_mm": doc.width_mm,
		"depth_mm": doc.depth_mm,
	}


@frappe.whitelist()
def get_global_glazing_rules() -> dict:
	"""Return global & per-series Bead & Gasket rules, auto-width config, available beads, gaskets, glasses, and series."""
	frappe.has_permission("Fenestration Glass", "read", throw=True)
	has_settings = frappe.db.exists("DocType", "Fenestration Glazing Settings")
	raw_rules = frappe.db.get_single_value("Fenestration Glazing Settings", "rules_json") if has_settings else None
	raw_auto = frappe.db.get_single_value("Fenestration Glazing Settings", "auto_config_json") if has_settings else None
	rules = normalize_global_glazing_rules(raw_rules)
	auto_config = normalize_glazing_auto_config(raw_auto)

	series_fields = ["name", "series_code", "series_title", "system_type"]
	if frappe.db.has_column("Profile Series", "supported_products"):
		series_fields.append("supported_products")
	series_rows = (
		frappe.get_list(
			"Profile Series",
			fields=series_fields,
			order_by="series_code asc",
			limit_page_length=200,
		)
		if frappe.has_permission("Profile Series", "read")
		else []
	)
	for s in series_rows:
		s["supported_products"] = normalize_supported_products(s.get("supported_products"))

	# Collect bead profiles across all series
	bead_profiles = (
		frappe.get_list(
			"Fenestration Profile",
			filters={"role": "bead"},
			fields=["name", "profile_code", "profile_name", "series", "width_mm", "depth_mm", "section_svg"],
			order_by="series asc, profile_code asc",
			limit_page_length=300,
		)
		if frappe.has_permission("Fenestration Profile", "read")
		else []
	)
	hardware_rows = []
	if frappe.db.exists("DocType", "Fenestration Hardware") and frappe.has_permission(
		"Fenestration Hardware", "read"
	):
		hardware_rows = frappe.get_list(
			"Fenestration Hardware",
			fields=[
				"name",
				"hardware_code",
				"hardware_name",
				"category",
				"item",
				"uom",
				"thickness_mm",
				"width_mm",
				"depth_mm",
				"section_svg",
			],
			order_by="category asc, thickness_mm asc, hardware_code asc",
			limit_page_length=300,
		)
	gasket_items = []
	if frappe.has_permission("Item", "read"):
		gasket_items = frappe.get_list(
			"Item",
			filters={"fen_item_kind": "Gasket"},
			fields=["name", "item_name", "stock_uom"],
			order_by="name asc",
			limit_page_length=200,
		)
		if not gasket_items:
			gasket_items = frappe.get_list(
				"Item",
				filters={"item_name": ("like", "%gasket%")},
				fields=["name", "item_name", "stock_uom"],
				order_by="name asc",
				limit_page_length=200,
			)
	glasses = frappe.get_list(
		"Fenestration Glass",
		fields=["name", "glass_code", "glass_name", "thickness_mm"],
		order_by="thickness_mm asc, glass_code asc",
		limit_page_length=300,
	)
	return {
		"ok": True,
		"rules": rules,
		"auto_config": auto_config,
		"series_list": series_rows,
		"beads": bead_profiles,
		"hardware": hardware_rows,
		"gasket_items": gasket_items,
		"glasses": glasses,
	}


@frappe.whitelist(methods=["POST"])
def save_global_glazing_rules(rules: list | str, auto_config: dict | str | None = None) -> dict:
	"""Validate, normalize, and persist global Bead & Gasket rules and auto-width config."""
	frappe.has_permission("Fenestration Glazing Settings", "write", throw=True)
	normalized = normalize_global_glazing_rules(rules)
	doc = frappe.get_single("Fenestration Glazing Settings")
	doc.rules_json = json.dumps(normalized, indent=2)
	normalized_auto = None
	if auto_config is not None:
		normalized_auto = normalize_glazing_auto_config(auto_config)
		doc.auto_config_json = json.dumps(normalized_auto, indent=2)
	doc.save()
	for ver in frappe.get_all("Series Version", pluck="name"):
		clear_snapshot(ver)
	return {
		"ok": True,
		"rules": normalized,
		"auto_config": normalized_auto
		if normalized_auto is not None
		else normalize_glazing_auto_config(getattr(doc, "auto_config_json", None)),
	}



