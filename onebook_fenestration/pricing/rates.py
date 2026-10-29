"""Resolve ERPNext Item Prices into the pure pricing engine's input."""

import frappe

from onebook_fenestration.engine import EngineResult, PriceBreakdown, PricingInput, SeriesSnapshot, compute, price
from onebook_fenestration.pricing.doctype.price_structure.price_structure import to_cost_heads
from onebook_fenestration.series_studio.snapshot import get_snapshot

NO_PRICE_LIST = "cost price list not configured"


def build_pricing_input(
	snapshot: SeriesSnapshot,
	result: EngineResult,
	finish: str,
	price_structure: str,
	price_list: str | None = None,
) -> PricingInput:
	price_list = price_list or frappe.db.get_single_value("Fenestration Settings", "cost_price_list")
	profile_items, glass_items, missing = _linked_items(result)
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
		finish_type=frappe.db.get_value("Profile Finish", finish, "finish_type") or "Mill",
		missing=tuple(missing),
	)


def price_design(
	design: dict, series_version: str, finish: str | None = None, price_structure: str | None = None
) -> tuple[EngineResult, PriceBreakdown]:
	settings = frappe.get_cached_doc("Fenestration Settings")
	snapshot = get_snapshot(series_version)
	result = compute(design, snapshot)
	pricing = build_pricing_input(
		snapshot,
		result,
		finish or settings.default_finish,
		price_structure or settings.default_price_structure,
		settings.cost_price_list,
	)
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


def _item_map(doctype: str, code_field: str, codes: set) -> dict[str, str]:
	if not codes:
		return {}
	rows = frappe.get_all(doctype, filters={code_field: ["in", list(codes)]}, fields=[code_field, "item"])
	return {row[code_field]: row.item for row in rows if row.item}


def _item_prices(price_list: str, codes: set) -> dict[str, float]:
	if not codes:
		return {}
	rows = frappe.get_all(
		"Item Price",
		filters={"price_list": price_list, "item_code": ["in", list(codes)]},
		fields=["item_code", "price_list_rate"],
		order_by="modified desc",
	)
	prices = {}
	for row in rows:
		prices.setdefault(row.item_code, row.price_list_rate)
	return prices
