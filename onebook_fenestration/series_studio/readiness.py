"""Readiness report: what still stops a series version from pricing and drawing cleanly.

Each check is "ok", "warn" (works, but output is incomplete) or "block" (pricing fails). The report is ok when
nothing blocks.
"""

import frappe
from frappe import _

from onebook_fenestration.engine import SeriesSnapshot
from onebook_fenestration.engine.formula import evaluate
from onebook_fenestration.engine.hardware import GASKET_GROUP, _contexts
from onebook_fenestration.engine.members import FRAME_PANEL
from onebook_fenestration.engine.types import GlassPane, RuleError
from onebook_fenestration.pricing.rate_sheet import _version_items
from onebook_fenestration.pricing.rates import _item_prices
from onebook_fenestration.series_studio.snapshot import get_snapshot

SETTINGS_FIELDS = ("cost_price_list", "default_price_structure", "default_finish")
# Any sash panel name works: the pane_side context only distinguishes the frame panel from a sash.
SASH_PANEL = "S1"


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
		_check("perimeters", "warn", _profiles_where(profiles, _no_perimeter)),
		_check("outlines", "warn", _profiles_where(profiles, lambda p: not p.section_svg)),
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
	"""Glasses no Gasket-group pane_side rule applies to, glazed in the frame or in a sash.

	Uses the engine's own pane_side contexts and formula evaluator on a one-pane probe per glass, so the answer is
	the same as the engine's no_glazing_gasket warning for a real design.
	"""
	rules = [r for r in snapshot.hardware_rules if r.group == GASKET_GROUP and r.per == "pane_side"]
	base = {**snapshot.deductions, **snapshot.constants}
	return [code for code in sorted(snapshot.glasses) if not _gasketed(code, rules, base, snapshot)]


def _gasketed(glass: str, rules: list, base: dict, snapshot: SeriesSnapshot) -> bool:
	probes = [GlassPane(panel, 1, glass, 1000.0, 1000.0) for panel in (FRAME_PANEL, SASH_PANEL)]
	for rule in rules:
		for _panel, _position, variables in _contexts("pane_side", [], probes, {}, {}, {}, snapshot, {}, {}):
			try:
				if evaluate(rule.when, {**base, **variables}, rule.id):
					return True
			except RuleError:
				continue
	return False


def _no_perimeter(profile) -> bool:
	return not profile.visible_perimeter_mm and not profile.total_perimeter_mm


def _profiles_where(codes: list[str], predicate) -> list[str]:
	if not codes:
		return []
	rows = frappe.get_all(
		"Fenestration Profile",
		filters={"profile_code": ["in", codes]},
		fields=["profile_code", "section_svg", "visible_perimeter_mm", "total_perimeter_mm"],
	)
	return sorted(row.profile_code for row in rows if predicate(row))
