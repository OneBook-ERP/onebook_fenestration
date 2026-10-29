"""Turn a Series Version into the engine's SeriesSnapshot.

Submitted versions serve the snapshot frozen at publish (cached in Redis); drafts rebuild from live masters.
"""

import frappe
from frappe.model.document import Document

from onebook_fenestration.engine import SeriesSnapshot

CACHE_KEY = "fen_snapshot"


def get_snapshot(series_version: str) -> SeriesSnapshot:
	"""Snapshot for `series_version`; submitted versions use the frozen snapshot_json, drafts always rebuild."""
	if frappe.db.get_value("Series Version", series_version, "docstatus") != 1:
		return SeriesSnapshot.from_dict(build_snapshot_dict(series_version))
	data = frappe.cache.hget(CACHE_KEY, series_version)
	if data is None:
		data = frappe.parse_json(frappe.db.get_value("Series Version", series_version, "snapshot_json"))
		frappe.cache.hset(CACHE_KEY, series_version, data)
	return SeriesSnapshot.from_dict(data)


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
		"profiles": _profiles(doc.series),
		"member_rules": [_member_rule(row) for row in doc.member_rules],
		"hardware_rules": [_hardware_rule(row) for row in doc.hardware_rules],
		"validation_rules": [_validation_rule(row) for row in doc.validation_rules],
		"glasses": _glasses(),
	}


def _profiles(series: str) -> dict:
	rows = frappe.get_all(
		"Fenestration Profile",
		filters={"series": series},
		fields=["profile_code", "profile_name", "kg_per_m", "bar_lengths", "use_computed_weight", "computed_kg_per_m"],
	)
	return {
		p.profile_code: {
			"name": p.profile_name,
			"kg_per_m": p.computed_kg_per_m if p.use_computed_weight and p.computed_kg_per_m else p.kg_per_m,
			"bar_lengths": [float(part) for part in (p.bar_lengths or "").split(",") if part.strip()],
		}
		for p in rows
	}


def _glasses() -> dict:
	rows = frappe.get_all("Fenestration Glass", fields=["glass_code", "glass_name", "thickness_mm"])
	return {g.glass_code: {"name": g.glass_name, "thickness_mm": g.thickness_mm} for g in rows}


def _member_rule(row) -> dict:
	return {
		"id": row.rule_id,
		"role": row.role,
		"profile": row.profile,
		"angles": [row.angle_start, row.angle_end],
		"length": row.length_expr,
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
	return rule


def _validation_rule(row) -> dict:
	return {
		"id": row.rule_id,
		"when": row.when_expr,
		"severity": row.severity,
		"message": row.message,
		"hint": row.hint or "",
	}
