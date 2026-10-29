import json

import frappe
from frappe.utils import flt

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
		names = [row.fen_window_design for row in doc.items if row.fen_window_design]
		designs = [frappe.db.get_value("Window Design", name, DESIGN_FIELDS, as_dict=True) for name in names]
	else:
		designs = frappe.get_all(
			"Window Design", {"project": doc.name}, DESIGN_FIELDS, order_by="design_ref"
		)
	return [_row(design) for design in designs if design]


def quote_totals(doc, rows: list[dict]) -> dict:
	"""Summary figures for the quotation total table; money comes from the Quotation, never recomputed."""
	windows = sum(row["qty"] for row in rows)
	area = sum(row["area_sqft"] * row["qty"] for row in rows)
	basic = sum(row["value"] for row in rows)
	transport = sum(flt(item.amount) for item in doc.items if item.item_code == "FEN-TRANSPORT")
	return {
		"windows": windows,
		"area_sqft": round(area, 3),
		"basic_value": basic,
		"transport": transport,
		"project_cost": flt(doc.net_total),
		"gst": flt(doc.total_taxes_and_charges),
		"grand_total": flt(doc.grand_total),
		"avg_rate": round(flt(doc.net_total) / area, 2) if area else 0,
	}


def _row(design) -> dict:
	spec = json.loads(design.design_json or "{}")
	result = json.loads(design.result_json or "{}")
	snapshot = get_snapshot(design.series_version)
	glass_codes = dict.fromkeys(pane["glass"] for pane in result.get("glass", []))
	bom_names = [line["name"] for line in result.get("bom", [])]
	sash_codes = dict.fromkeys(m["profile"] for m in result.get("members", []) if m["role"] == "sash")
	frame_codes = dict.fromkeys(m["profile"] for m in result.get("members", []) if m["role"] == "frame")
	finish = frappe.db.get_value("Profile Finish", design.finish, ("finish_name", "color"), as_dict=True)
	return {
		"ref": design.design_ref,
		"name": design.design_name or "",
		"qty": design.qty,
		"width": spec.get("width"),
		"height": spec.get("height"),
		"series": _series_title(design.series_version),
		"finish": finish.finish_name if finish else "",
		"finish_color": finish.color if finish else "",
		"glass": [snapshot.glasses[c].name if c in snapshot.glasses else c for c in glass_codes],
		"location": design.location or "",
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
	return ", ".join(snapshot.profiles[c].name if c in snapshot.profiles else c for c in codes)


def _first_matching(names: list[str], word: str) -> str:
	return next((name for name in dict.fromkeys(names) if word in name.upper()), "")
