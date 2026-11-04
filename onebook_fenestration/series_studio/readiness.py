"""Readiness report: what still stops a series version from pricing and drawing cleanly.

Each check is "ok", "warn" (works, but output is incomplete) or "block" (pricing fails). The report is ok when
nothing blocks.
"""

import frappe
from frappe import _

from onebook_fenestration.engine import SeriesSnapshot
from onebook_fenestration.engine.hardware import glazing_gasket_gaps
from onebook_fenestration.pricing.rate_sheet import _version_items
from onebook_fenestration.pricing.rates import _item_prices
from onebook_fenestration.series_studio.snapshot import get_snapshot

SETTINGS_FIELDS = ("cost_price_list", "default_price_structure", "default_finish")


@frappe.whitelist()
def readiness(series_version: str) -> dict:
	frappe.has_permission("Series Version", "read", doc=series_version, throw=True)
	snapshot = get_snapshot(series_version)
	profiles = sorted(
		{
			r.profile
			for r in frappe.get_all(
				"Series Member Rule", filters={"parent": series_version}, fields=["profile"]
			)
		}
	)
	checks = [
		_check("settings", "block", _missing_settings()),
		_check("item_links", "block", _unlinked(profiles, sorted(snapshot.glasses))),
		_check("prices", "block", _unpriced(series_version)),
		_check("gasket_rules", "warn", _ungasketed_glasses(snapshot)),
		_check("perimeters", "warn", _without_perimeters(profiles)),
		_check("outlines", "warn", _without_outline(profiles)),
	]
	return {"ok": all(c["status"] != "block" for c in checks), "checks": checks}


def _check(name: str, severity: str, items: list[str]) -> dict:
	return {"check": name, "status": severity if items else "ok", "items": items}


def _missing_settings() -> list[str]:
	settings = frappe.get_cached_doc("Fenestration Settings")
	meta = frappe.get_meta("Fenestration Settings")
	return [_(meta.get_label(field)) for field in SETTINGS_FIELDS if not settings.get(field)]


def _unlinked(profiles: list[str], glasses: list[str]) -> list[str]:
	"""Profiles and glasses that have no ERPNext Item, so they can neither be priced nor bought."""
	return _without_item("Fenestration Profile", "profile_code", profiles) + _without_item(
		"Fenestration Glass", "glass_code", glasses
	)


def _without_item(doctype: str, code_field: str, codes: list[str]) -> list[str]:
	if not codes:
		return []
	linked = set(
		frappe.get_all(doctype, filters={code_field: ["in", codes], "item": ["is", "set"]}, pluck=code_field)
	)
	return [code for code in codes if code not in linked]


def _unpriced(series_version: str) -> list[str]:
	price_list = frappe.db.get_single_value("Fenestration Settings", "cost_price_list")
	codes = {item for item, _kind in _version_items(series_version)}
	if not price_list:
		return sorted(codes)
	return sorted(codes - _item_prices(price_list, codes).keys())


def _ungasketed_glasses(snapshot: SeriesSnapshot) -> list[str]:
	"""Glass and glazing pairs ("6CTG (sash)") that would get the engine's no_glazing_gasket warning."""
	return [f"{glass} ({'sash' if in_sash else 'fixed'})" for glass, in_sash in glazing_gasket_gaps(snapshot)]


def _without_perimeters(codes: list[str]) -> list[str]:
	return _profiles_matching(codes, {"visible_perimeter_mm": 0, "total_perimeter_mm": 0})


def _without_outline(codes: list[str]) -> list[str]:
	return _profiles_matching(codes, {"section_svg": ["is", "not set"]})


def _profiles_matching(codes: list[str], filters: dict) -> list[str]:
	if not codes:
		return []
	return sorted(
		frappe.get_all(
			"Fenestration Profile", filters={"profile_code": ["in", codes], **filters}, pluck="profile_code"
		)
	)
