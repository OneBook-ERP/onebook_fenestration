"""Turn a Series Version into the engine's SeriesSnapshot.

Submitted versions serve the snapshot frozen at publish (cached in Redis); drafts rebuild from live masters.
"""

import frappe
from frappe.model.document import Document

from onebook_fenestration.engine import SeriesSnapshot
from onebook_fenestration.engine.section_config import (
	normalize_glass_glazing_rules,
	normalize_glazing_auto_config,
	normalize_global_glazing_rules,
	normalize_profile_anchors,
	normalize_section_config,
	normalize_supported_products,
)
from onebook_fenestration.series_studio.legacy_gaskets import with_legacy_gaskets

CACHE_KEY = "fen_snapshot"


def _series_section_config(series_code: str | None) -> dict:
	if not series_code:
		return {}
	raw = frappe.db.get_value("Profile Series", series_code, "section_config_json")
	if not raw:
		return {}
	return normalize_section_config(raw)


def _global_glazing_rules() -> list[dict]:
	if not frappe.db.exists("DocType", "Fenestration Glazing Settings"):
		return []
	raw = frappe.db.get_single_value("Fenestration Glazing Settings", "rules_json")
	return normalize_global_glazing_rules(raw)


def _global_glazing_auto() -> dict:
	if not frappe.db.exists("DocType", "Fenestration Glazing Settings"):
		return {}
	raw = frappe.db.get_single_value("Fenestration Glazing Settings", "auto_config_json")
	return normalize_glazing_auto_config(raw) if raw else {}


def _gasket_catalog() -> list[dict]:
	if not frappe.db.exists("DocType", "Fenestration Hardware"):
		return []
	rows = frappe.get_all(
		"Fenestration Hardware",
		filters={"category": ("in", ["Gasket", "Seal / Weatherstrip"])},
		fields=["name", "hardware_code", "hardware_name", "item", "thickness_mm"],
		order_by="thickness_mm asc, hardware_code asc",
		limit_page_length=200,
	)
	return [
		{
			"code": r.hardware_code or r.name,
			"item": r.item or r.hardware_code or r.name,
			"name": r.hardware_name or r.hardware_code or r.name,
			"thickness_mm": float(r.thickness_mm or 0.0),
		}
		for r in rows
		if float(r.thickness_mm or 0.0) > 0
	]


def _series_supported_products(series_code: str | None) -> list[str]:
	if not series_code or not frappe.db.has_column("Profile Series", "supported_products"):
		return []
	raw = frappe.db.get_value("Profile Series", series_code, "supported_products")
	return normalize_supported_products(raw)


def _with_section_config(data: dict) -> dict:
	cfg = _series_section_config(data.get("code"))
	live_glasses = _glasses()
	merged_glasses = dict(data.get("glasses") or {})
	for gcode, gspec in live_glasses.items():
		if gcode in merged_glasses:
			merged_glasses[gcode] = {**merged_glasses[gcode], "glazing_rules": gspec.get("glazing_rules", [])}
		else:
			merged_glasses[gcode] = gspec
	out = {
		**data,
		"glasses": merged_glasses,
		"global_glazing_rules": _global_glazing_rules(),
		"global_glazing_auto": _global_glazing_auto(),
		"gasket_catalog": _gasket_catalog(),
		"supported_products": _series_supported_products(data.get("code")),
	}
	if cfg:
		out["section_config"] = cfg
	return out


def get_snapshot(series_version: str) -> SeriesSnapshot:
	"""Snapshot for `series_version`; submitted versions use the frozen snapshot_json, drafts always rebuild."""
	if frappe.db.get_value("Series Version", series_version, "docstatus") != 1:
		return SeriesSnapshot.from_dict(_with_section_config(_with_all_profiles(build_snapshot_dict(series_version))))
	data = frappe.cache.hget(CACHE_KEY, series_version)
	if data is None:
		raw_json = frappe.db.get_value("Series Version", series_version, "snapshot_json")
		data = frappe.parse_json(raw_json) if raw_json else build_snapshot_dict(series_version)
		frappe.cache.hset(CACHE_KEY, series_version, data)
	return SeriesSnapshot.from_dict(_with_section_config(_with_all_profiles(with_legacy_gaskets(data))))


def _safe_bar_lengths(raw: str | None, fallback: list[float] | None = None) -> list[float]:
	out: list[float] = []
	for part in (raw or "").replace(";", ",").split(","):
		part = part.strip()
		if not part:
			continue
		try:
			val = float(part)
		except ValueError:
			continue
		if val > 0:
			out.append(val)
	return out if out else (list(fallback) if fallback is not None else [])


def _with_all_profiles(data: dict) -> dict:
	"""Ensure any Fenestration Profile in the database is available when overridden by a design."""
	out = {**data, "profiles": dict(data.get("profiles") or {})}
	for code, spec in _all_profiles().items():
		if code in out["profiles"]:
			out["profiles"][code] = {**out["profiles"][code], "section_anchors": spec.get("section_anchors") or {}}
		else:
			out["profiles"][code] = spec
	return out


def _all_profiles() -> dict:
	rows = frappe.get_all(
		"Fenestration Profile",
		fields=[
			"profile_code",
			"profile_name",
			"kg_per_m",
			"bar_lengths",
			"use_computed_weight",
			"computed_kg_per_m",
			"visible_perimeter_mm",
			"total_perimeter_mm",
			"width_mm",
			"depth_mm",
			"section_anchors_json",
		],
	)
	return {
		p.profile_code: {
			"name": p.profile_name,
			"kg_per_m": (p.computed_kg_per_m if p.use_computed_weight and p.computed_kg_per_m else p.kg_per_m) or 0.0,
			"bar_lengths": _safe_bar_lengths(p.bar_lengths, [6000.0]),
			"visible_perimeter_mm": p.visible_perimeter_mm or 0,
			"total_perimeter_mm": p.total_perimeter_mm or 0,
			"width_mm": p.width_mm or 0,
			"depth_mm": p.depth_mm or 0,
			"section_anchors": normalize_profile_anchors(getattr(p, "section_anchors_json", None)),
		}
		for p in rows
	}


def clear_snapshot(series_version: str) -> None:
	frappe.cache.hdel(CACHE_KEY, series_version)


def build_snapshot_dict(series_version: str | Document) -> dict:
	"""The plain dict `SeriesSnapshot.from_dict` expects, read from the version and its series masters."""
	doc = series_version if isinstance(series_version, Document) else frappe.get_doc("Series Version", series_version)
	return {
		"code": doc.series,
		"version": doc.name,
		"deductions": {row.deduction_key: row.value for row in doc.deductions},
		"constants": {row.constant_key: row.value for row in doc.constants},
		"profiles": _profiles(doc.series, {row.profile for row in doc.member_rules}),
		"member_rules": [_member_rule(row) for row in doc.member_rules],
		"hardware_rules": [_hardware_rule(row) for row in doc.hardware_rules],
		"validation_rules": [_validation_rule(row) for row in doc.validation_rules],
		"glasses": _glasses(),
		"section_config": _series_section_config(doc.series),
		"supported_products": _series_supported_products(doc.series),
	}


def _profiles(series: str, rule_profiles: set[str]) -> dict:
	"""The series' own profiles plus any profile its member rules use from another series (a profile has one series)."""
	rows = frappe.get_all(
		"Fenestration Profile",
		or_filters={"series": series, "name": ("in", sorted(rule_profiles) or [""])},
		fields=["profile_code", "profile_name", "kg_per_m", "bar_lengths", "use_computed_weight", "computed_kg_per_m", "visible_perimeter_mm", "total_perimeter_mm"],
	)
	return {
		p.profile_code: {
			"name": p.profile_name,
			"kg_per_m": p.computed_kg_per_m if p.use_computed_weight and p.computed_kg_per_m else p.kg_per_m,
			"bar_lengths": _safe_bar_lengths(p.bar_lengths),
			"visible_perimeter_mm": p.visible_perimeter_mm or 0,
			"total_perimeter_mm": p.total_perimeter_mm or 0,
		}
		for p in rows
	}


def _glasses() -> dict:
	rows = frappe.get_all(
		"Fenestration Glass",
		fields=["glass_code", "glass_name", "thickness_mm", "glass_mm", "glazing_rules_json"],
	)
	return {
		g.glass_code: {
			"name": g.glass_name,
			"thickness_mm": g.thickness_mm,
			"glass_mm": g.glass_mm or None,
			"glazing_rules": normalize_glass_glazing_rules(getattr(g, "glazing_rules_json", None)),
		}
		for g in rows
	}


def _member_rule(row) -> dict:
	return {
		"id": row.rule_id,
		"role": row.role,
		"profile": row.profile,
		"angles": [row.angle_start, row.angle_end],
		"length": row.length_expr,
		"when": row.when_expr or "",
	}


def _hardware_rule(row) -> dict:
	"""Empty optional columns are left out so the engine's HardwareRule defaults apply."""
	rule = {
		"id": row.rule_id,
		"item": row.item,
		"name": row.item_name,
		"per": row.per,
		"qty": row.qty_expr,
		"when": row.when_expr or "True",
		"length": row.length_expr or None,
	}
	if row.uom:
		rule["uom"] = row.uom
	if row.bom_group:
		rule["group"] = row.bom_group
	if row.note:
		rule["note"] = row.note
	return rule


def _validation_rule(row) -> dict:
	return {
		"id": row.rule_id,
		"when": row.when_expr,
		"severity": row.severity,
		"message": row.message,
		"hint": row.hint or "",
	}
