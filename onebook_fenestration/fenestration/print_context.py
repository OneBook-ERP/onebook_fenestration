import json

import frappe
from frappe.utils import escape_html, flt

from onebook_fenestration.engine.layout import layout
from onebook_fenestration.fenestration.quotation import TRANSPORT_ITEM, _typology
from onebook_fenestration.fenestration.quote_party import company_address
from onebook_fenestration.series_studio.snapshot import get_snapshot

DESIGN_FIELDS = (
	"name",
	"design_ref",
	"design_name",
	"qty",
	"location",
	"series_version",
	"finish",
	"design_json",
	"result_json",
	"unit_price",
	"rate_per_sqft",
	"line_total",
	"area_sqft",
	"window_kg",
	"design_svg",
)


def design_rows(doc) -> list[dict]:
	"""Plain dicts, one per window design of a Quotation or Fenestration Project, for the print formats."""
	if doc.doctype == "Quotation":
		return [_quoted_row(item) for item in doc.items if item.fen_window_design]
	designs = frappe.get_all("Window Design", {"project": doc.name}, DESIGN_FIELDS, order_by="design_ref")
	return [_row(design) for design in designs]


def company_header(company: str | None) -> dict:
	"""Name, logo and address lines of the company, for formats that print without a Letter Head."""
	company = company or frappe.defaults.get_global_default("company")
	address = company_address(company) if company else None
	return {
		"name": escape_html(company or ""),
		"logo": company and frappe.db.get_value("Company", company, "company_logo"),
		"address": escape_html(_address_line(address)) if address else "",
	}


def _address_line(address: str) -> str:
	fields = ("address_line1", "address_line2", "city", "state", "pincode")
	values = frappe.db.get_value("Address", address, fields, as_dict=True)
	return ", ".join(values[field] for field in fields if values[field])


def quote_totals(doc, rows: list[dict]) -> dict:
	"""Summary figures for the quotation total table, all taken from the Quotation itself."""
	lines = [item for item in doc.items if item.item_code != TRANSPORT_ITEM]
	area = sum(row["area_sqft"] * row["qty"] for row in rows)
	return {
		"windows": sum(item.qty for item in lines),
		"area_sqft": round(area, 3),
		"basic_value": sum(flt(item.amount) for item in lines),
		"transport": sum(flt(item.amount) for item in doc.items if item.item_code == TRANSPORT_ITEM),
		"project_cost": flt(doc.net_total),
		"gst": flt(doc.total_taxes_and_charges),
		"grand_total": flt(doc.grand_total),
		"avg_rate": round(flt(doc.net_total) / area, 2) if area else 0,
	}


def _quoted_row(item) -> dict:
	"""A design row priced as the Quotation line says, not as the design is priced now."""
	design = frappe.db.get_value("Window Design", item.fen_window_design, DESIGN_FIELDS, as_dict=True)
	row = _row(design)
	row.update(
		qty=item.qty,
		unit_price=flt(item.rate),
		value=flt(item.amount),
		rate_per_sqft=round(flt(item.rate) / row["area_sqft"], 2) if row["area_sqft"] else 0,
	)
	return row


def _row(design) -> dict:
	spec = json.loads(design.design_json or "{}")
	result = json.loads(design.result_json or "{}")
	snapshot = get_snapshot(design.series_version)
	glass_codes = dict.fromkeys(pane["glass"] for pane in result.get("glass", []))
	bom_names = [line["name"] for line in result.get("bom", [])]
	sash_codes = dict.fromkeys(m["profile"] for m in result.get("members", []) if m["role"] == "sash")
	frame_codes = dict.fromkeys(m["profile"] for m in result.get("members", []) if m["role"] == "frame")
	finish = frappe.db.get_value("Profile Finish", design.finish, ("finish_name", "color"), as_dict=True)
	cells, _bars = layout(spec) if spec else ([], [])
	return {
		"ref": escape_html(design.design_ref),
		"name": escape_html(design.design_name or _typology(cells)),
		"qty": design.qty,
		"width": spec.get("width"),
		"height": spec.get("height"),
		"series": escape_html(_series_title(design.series_version) or ""),
		"finish": escape_html(finish.finish_name) if finish else "",
		"finish_color": escape_html(finish.color or "") if finish else "",
		"glass": [escape_html(snapshot.glasses[c].name if c in snapshot.glasses else c) for c in glass_codes],
		"location": escape_html(design.location or ""),
		"area_sqft": flt(design.area_sqft),
		"rate_per_sqft": flt(design.rate_per_sqft),
		"unit_price": flt(design.unit_price),
		"value": flt(design.line_total),
		"weight": flt(design.window_kg),
		"sash_profile": _profile_names(snapshot, sash_codes),
		"frame_profile": _profile_names(snapshot, frame_codes),
		"handle": _first_matching(bom_names, "HANDLE"),
		"friction_stay": _first_matching(bom_names, "FRICTION"),
		"svg": design.design_svg or "",
	}


def _series_title(series_version: str) -> str:
	series = frappe.db.get_value("Series Version", series_version, "series")
	return frappe.db.get_value("Profile Series", series, "series_title") or series


def _profile_names(snapshot, codes) -> str:
	return escape_html(", ".join(snapshot.profiles[c].name if c in snapshot.profiles else c for c in codes))


def _first_matching(names: list[str], word: str) -> str:
	return escape_html(next((name for name in dict.fromkeys(names) if word in name.upper()), ""))
