"""Resolve ERPNext Item Prices into the pure pricing engine's input."""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from onebook_fenestration.engine import EngineResult, PriceBreakdown, PricingInput, SeriesSnapshot, compute, price
from onebook_fenestration.pricing.doctype.price_structure.price_structure import to_cost_heads
from onebook_fenestration.series_studio.snapshot import get_snapshot

NO_PRICE_LIST = "cost price list not configured"


def missing_defaults_message() -> str:
	return _("Set a default price structure and finish in Fenestration Settings")


def resolve_pricing_defaults(finish: str | None, price_structure: str | None) -> tuple:
	"""The design's own finish and price structure, else the Settings defaults (either may still be empty)."""
	settings = frappe.get_cached_doc("Fenestration Settings")
	return finish or settings.default_finish, price_structure or settings.default_price_structure


def build_pricing_input(
	snapshot: SeriesSnapshot,
	result: EngineResult,
	finish: str,
	price_structure: str,
	price_list: str | None = None,
) -> PricingInput:
	price_list = price_list or frappe.db.get_single_value("Fenestration Settings", "cost_price_list")
	profile_items, glass_items, missing = _linked_items(result)
	finish_row = (
		frappe.db.get_value("Profile Finish", finish, ["finish_type", "surcharge_pct"], as_dict=True) or {}
	)
	bom_codes = {line.item for line in result.bom}
	codes = set(profile_items.values()) | set(glass_items.values()) | bom_codes
	if price_list:
		prices = _item_prices(price_list, codes)
		missing += [f"{code} ({price_list})" for code in sorted(codes - prices.keys())]
	else:
		prices = {}
		missing = [NO_PRICE_LIST]
	return PricingInput(
		heads=to_cost_heads(price_structure),
		profile_rates={code: prices.get(item, 0) for code, item in profile_items.items()},
		item_rates={code: prices.get(code, 0) for code in bom_codes},
		glass_rates={code: prices.get(item, 0) for code, item in glass_items.items()},
		finish_type=finish_row.get("finish_type") or "Mill",
		missing=tuple(missing),
		profile_perimeters=_profile_perimeters({m.profile for m in result.members}),
		finish_surcharge_pct=flt(finish_row.get("surcharge_pct")),
	)


def price_design(
	design: dict, series_version: str, finish: str | None = None, price_structure: str | None = None
) -> tuple[EngineResult, PriceBreakdown]:
	finish, price_structure = resolve_pricing_defaults(finish, price_structure)
	if not (finish and price_structure):
		frappe.throw(missing_defaults_message())
	snapshot = get_snapshot(series_version)
	result = compute(design, snapshot)
	price_list = frappe.get_cached_doc("Fenestration Settings").cost_price_list
	pricing = build_pricing_input(snapshot, result, finish, price_structure, price_list)
	return result, price(result, snapshot, pricing)


def _linked_items(result: EngineResult) -> tuple[dict, dict, list]:
	"""Items behind the profiles and glasses the design uses; unlinked ones are reported missing."""
	profile_codes = {m.profile for m in result.members}
	glass_codes = {g.glass for g in result.glass}
	profile_items = _item_map("Fenestration Profile", "profile_code", profile_codes)
	glass_items = _item_map("Fenestration Glass", "glass_code", glass_codes)
	missing = [f"{code} (no item)" for code in sorted(profile_codes - profile_items.keys())]
	missing += [f"{code} (no item)" for code in sorted(glass_codes - glass_items.keys())]
	return profile_items, glass_items, missing


def _profile_perimeters(codes: set) -> dict[str, tuple[float, float]]:
	"""Live (visible, total) perimeter mm per profile: perimeters are commercial data, not frozen geometry."""
	if not codes:
		return {}
	rows = frappe.get_all(
		"Fenestration Profile",
		filters={"profile_code": ["in", list(codes)]},
		fields=["profile_code", "visible_perimeter_mm", "total_perimeter_mm"],
	)
	return {row.profile_code: (flt(row.visible_perimeter_mm), flt(row.total_perimeter_mm)) for row in rows}


def _item_map(doctype: str, code_field: str, codes: set) -> dict[str, str]:
	if not codes:
		return {}
	rows = frappe.get_all(doctype, filters={code_field: ["in", list(codes)]}, fields=[code_field, "item"])
	return {row[code_field]: row.item for row in rows if row.item}


def _item_prices(price_list: str, codes: set) -> dict[str, float]:
	"""Current, party-independent rate per item. Rates are read as per kg / m2 / m by ruling (uom not converted)."""
	if not codes:
		return {}
	rows = frappe.get_all(
		"Item Price",
		filters={"price_list": price_list, "item_code": ["in", list(codes)]},
		fields=["item_code", "price_list_rate", "valid_from", "valid_upto", "customer", "supplier"],
		order_by="valid_from desc, modified desc",
	)
	today = getdate()
	prices = {}
	for row in rows:
		if row.customer or row.supplier or not _is_valid(row, today):
			continue
		prices.setdefault(row.item_code, row.price_list_rate)
	return prices


def _is_valid(row, today) -> bool:
	return (not row.valid_from or getdate(row.valid_from) <= today) and (
		not row.valid_upto or getdate(row.valid_upto) >= today
	)
