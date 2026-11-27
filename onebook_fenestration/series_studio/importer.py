"""Load a series from snapshot JSON (the engine fixture shape) into the Series Studio masters."""

import frappe

from onebook_fenestration.engine import SeriesSnapshot
from onebook_fenestration.series_studio.legacy_gaskets import GASKETS

ITEM_GROUP = "Fenestration"
DEFAULT_HSN_CODES = {"Profile": "760429", "Hardware": "830241", "Gasket": "400829", "Glass": "70071900"}
GLASS_ITEM_PREFIX = "FEN-GLASS-"
# Fenestration Profile role for a member rule role that has no profile role of its own.
PROFILE_ROLES = {"glass_adaptor": "bead"}


def import_snapshot_json(
	series_code: str,
	data: dict,
	title: str,
	system_type: str = "Casement",
	hsn_codes: dict | None = None,
	source_hash: str | None = None,
) -> str:
	"""Create any missing masters for `data`, then create and submit a Series Version. Returns its name.

	`hsn_codes` maps fen_item_kind to the GST HSN code for new Items (used only when india_compliance is installed).
	"""
	hsn_codes = DEFAULT_HSN_CODES if hsn_codes is None else hsn_codes
	snap = SeriesSnapshot.from_dict(data)
	_ensure_item_group()
	for glass in snap.glasses.values():
		_ensure_glass(glass, hsn_codes)
	_ensure_series(series_code, title, system_type)
	roles = {}
	for rule in snap.member_rules:
		roles.setdefault(rule.profile, PROFILE_ROLES.get(rule.role, rule.role))
	for profile in snap.profiles.values():
		_ensure_item(profile.code, profile.name, "Kg", "Profile", hsn_codes)
		_ensure_profile(profile, series_code, roles.get(profile.code, "accessory"))
	for rule in snap.hardware_rules:
		if rule.group == "Gasket":
			_ensure_item(rule.item, rule.name, "Meter", "Gasket", hsn_codes)
		else:
			_ensure_item(rule.item, rule.name, rule.uom, "Hardware", hsn_codes)
	version = frappe.get_doc(
		{
			"doctype": "Series Version",
			"series": series_code,
			"version_note": data.get("version_note"),
			"source_hash": source_hash,
			"deductions": [{"deduction_key": k, "value": v} for k, v in snap.deductions.items()],
			"constants": [{"constant_key": k, "value": v} for k, v in snap.constants.items()],
			"member_rules": [_member_row(rule) for rule in snap.member_rules],
			"hardware_rules": [_hardware_row(rule) for rule in snap.hardware_rules],
			"validation_rules": [_validation_row(rule) for rule in snap.validation_rules],
		}
	).insert()
	version.submit()
	return version.name


def ensure_gasket_items(hsn_codes: dict | None = None) -> None:
	"""Create the legacy gasket Items (G21, G23) when missing, for versions published before gaskets were rules."""
	hsn_codes = DEFAULT_HSN_CODES if hsn_codes is None else hsn_codes
	_ensure_item_group()
	for code, name in GASKETS.items():
		_ensure_item(code, name, "Meter", "Gasket", hsn_codes)


def _member_row(rule) -> dict:
	return {
		"rule_id": rule.id,
		"role": rule.role,
		"profile": rule.profile,
		"angle_start": rule.angles[0],
		"angle_end": rule.angles[1],
		"length_expr": rule.length,
		"when_expr": rule.when or None,
	}


def _hardware_row(rule) -> dict:
	return {
		"rule_id": rule.id,
		"item": rule.item,
		"item_name": rule.name,
		"per": rule.per,
		"when_expr": rule.when,
		"qty_expr": rule.qty,
		"length_expr": rule.length,
		"uom": rule.uom,
		"bom_group": rule.group,
		"note": rule.note,
	}


def _validation_row(rule) -> dict:
	return {
		"rule_id": rule.id,
		"when_expr": rule.when,
		"severity": rule.severity,
		"message": rule.message,
		"hint": rule.hint,
	}


def _insert_if_missing(doctype: str, name: str, values: dict) -> None:
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **values}).insert()


def _ensure_item_group() -> None:
	# ERPNext rejects group nodes on Items, so this is a leaf under the root.
	_insert_if_missing(
		"Item Group",
		ITEM_GROUP,
		{"item_group_name": ITEM_GROUP, "parent_item_group": "All Item Groups", "is_group": 0},
	)


def _ensure_glass(glass, hsn_codes: dict) -> None:
	"""A new glass also gets its Item (FEN-GLASS-<code>, priced per m²); an existing glass is left as it is."""
	if frappe.db.exists("Fenestration Glass", glass.code):
		return
	item = GLASS_ITEM_PREFIX + glass.code
	_ensure_item(item, glass.name, "Square Meter", "Glass", hsn_codes)
	values = {
		"glass_code": glass.code,
		"glass_name": glass.name,
		"thickness_mm": glass.thickness_mm,
		"glass_mm": glass.glass_mm,
	}
	frappe.get_doc({"doctype": "Fenestration Glass", **values, "item": item}).insert()


def _ensure_series(series_code: str, title: str, system_type: str) -> None:
	_insert_if_missing(
		"Profile Series",
		series_code,
		{"series_code": series_code, "series_title": title, "system_type": system_type},
	)


def _ensure_item(item_code: str, item_name: str, uom: str, kind: str, hsn_codes: dict) -> None:
	_insert_if_missing("UOM", uom, {"uom_name": uom})
	values = {
		"item_code": item_code,
		"item_name": item_name,
		"item_group": ITEM_GROUP,
		"stock_uom": uom,
		"is_stock_item": 1,
		"fen_item_kind": kind,
	}
	if kind in hsn_codes and frappe.get_meta("Item").has_field("gst_hsn_code"):
		values["gst_hsn_code"] = hsn_codes[kind]
	_insert_if_missing("Item", item_code, values)


def _ensure_profile(profile, series_code: str, role: str) -> None:
	_insert_if_missing(
		"Fenestration Profile",
		profile.code,
		{
			"profile_code": profile.code,
			"profile_name": profile.name,
			"series": series_code,
			"item": profile.code,
			"role": role,
			"kg_per_m": profile.kg_per_m,
			"bar_lengths": ", ".join(f"{length:g}" for length in profile.bar_lengths),
		},
	)
