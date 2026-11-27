import json
import re

import frappe
from frappe.utils import escape_html, flt

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.layout import layout
from onebook_fenestration.fenestration.quotation import TRANSPORT_ITEM, _typology, current_designs
from onebook_fenestration.fenestration.quote_party import company_address
from onebook_fenestration.series_studio.snapshot import get_snapshot

DESIGN_FIELDS = (
	"name",
	"design_ref",
	"design_name",
	"qty",
	"floor",
	"location",
	"series_version",
	"finish",
	"design_json",
	"result_json",
	"unit_price",
	"rate_per_sqft",
	"line_total",
	"area_m2",
	"area_sqft",
	"window_kg",
	"design_svg",
)


def design_rows(doc) -> list[dict]:
	"""Plain dicts, one per window design of a Quotation or Fenestration Project, for the print formats."""
	if doc.doctype == "Quotation":
		rows = (_quoted_row(item) for item in doc.items if item.fen_window_design)
		return [row for row in rows if row]
	return [_row(design) for design in _project_designs(doc)]


def _project_designs(doc) -> list:
	return current_designs(doc.name, DESIGN_FIELDS)


POSITION_ORDER = "BTLRHW"


def assembly_summary(doc) -> list[dict]:
	"""Current designs of a project grouped by width x height, largest first, for the Assembly Summary format."""
	groups: dict[tuple, dict] = {}
	for row in [_row(d) for d in current_designs(doc.name, DESIGN_FIELDS)]:
		group = groups.setdefault(
			(row["width"], row["height"]),
			{
				"width": row["width"],
				"height": row["height"],
				"refs": [],
				"qty": 0,
				"area_sqft": 0,
				"weight_kg": 0,
				"series": row["series"],
				"typology": row["typology"],
				"finishes": [],
				"glasses": [],
				"svg": row["svg"],
			},
		)
		group["refs"].append(row["ref"])
		group["qty"] += row["qty"]
		group["area_sqft"] += row["area_sqft"] * row["qty"]
		group["weight_kg"] += row["weight"] * row["qty"]
		if row["finish"] and row["finish"] not in group["finishes"]:
			group["finishes"].append(row["finish"])
		for g in row["glass"]:
			if g and g not in group["glasses"]:
				group["glasses"].append(g)
		if not group["svg"] and row["svg"]:
			group["svg"] = row["svg"]
	result = sorted(groups.values(), key=lambda g: (g["width"] or 0, g["height"] or 0), reverse=True)
	for group in result:
		group["refs"] = ", ".join(group["refs"])
		group["area_sqft"] = round(group["area_sqft"], 3)
		group["weight_kg"] = round(group["weight_kg"], 2)
		group["finishes"] = ", ".join(group["finishes"])
		group["glasses"] = ", ".join(group["glasses"])
	return result


def assembly_detail(doc) -> list[dict]:
	"""One block per current design with its cut pieces and glazing schedule for the Assembly Detail format."""
	return [_detail_block(design) for design in current_designs(doc.name, DESIGN_FIELDS)]


def _detail_block(design) -> dict:
	row = _row(design)
	snapshot = get_snapshot(design.series_version)
	computed = compute(json.loads(design.design_json or "{}"), snapshot)
	design_qty = design.qty or 1
	counts: dict[tuple, int] = {}
	for m in computed.members:
		key = (m.panel, m.position, m.profile, m.length, f"{m.angles[0]}/{m.angles[1]}", m.role)
		counts[key] = counts.get(key, 0) + 1
	pieces = []
	for (panel, position, profile, length, angles, role), count in counts.items():
		prof_spec = snapshot.profiles.get(profile)
		kg_per_m = prof_spec.kg_per_m if prof_spec else 0.0
		total_qty = count * design_qty
		pieces.append(
			{
				"panel": escape_html(panel),
				"position": position,
				"role": escape_html(role),
				"profile": escape_html(profile),
				"profile_name": _profile_names(snapshot, [profile]),
				"length": length,
				"angles": angles,
				"qty_per_window": count,
				"total_qty": total_qty,
				"weight_kg": round((length / 1000.0) * kg_per_m * total_qty, 3),
			}
		)
	pieces.sort(key=lambda p: (p["panel"], _position_rank(p["position"])))
	glazing = _detail_glazing(computed.glass, snapshot, design_qty)
	return {
		**{key: row[key] for key in ("ref", "name", "qty", "width", "height", "svg", "series", "finish", "finish_color", "floor", "location", "area_m2", "area_sqft", "weight")},
		"total_weight": round(row["weight"] * design_qty, 2),
		"pieces": pieces,
		"glazing": glazing,
	}


def _detail_glazing(panes, snapshot, design_qty: int) -> list[dict]:
	grouped: dict[tuple, int] = {}
	for pane in panes:
		key = (round(pane.width, 1), round(pane.height, 1), pane.glass, pane.material)
		grouped[key] = grouped.get(key, 0) + 1
	result = []
	for (w, h, code, material), count in grouped.items():
		label = "Steel" if material == "steel" else (snapshot.glasses[code].name if code in snapshot.glasses else code)
		total_qty = count * design_qty
		result.append(
			{
				"glass": escape_html(code or ""),
				"glass_name": escape_html(label or ""),
				"width": w,
				"height": h,
				"qty_per_window": count,
				"total_qty": total_qty,
				"area_m2": round((w * h / 1_000_000.0) * total_qty, 3),
			}
		)
	return result


def _position_rank(position: str) -> int:
	return POSITION_ORDER.index(position) if position in POSITION_ORDER else len(POSITION_ORDER)


def _safe_logo_url(url: str | None) -> str:
	raw = str(url or "").strip()
	if not raw:
		return ""
	if raw.startswith(("/", "http://", "https://")):
		return escape_html(raw)
	return ""


def company_header(company: str | None) -> dict:
	"""Name, logo, contact and address lines of the company, for print formats."""
	company = company or frappe.defaults.get_global_default("company")
	address = company_address(company) if company else None
	comp = (
		frappe.db.get_value(
			"Company",
			company,
			("company_logo", "phone_no", "email", "website", "tax_id"),
			as_dict=True,
		)
		if company
		else None
	) or {}
	addr_meta = _address_details(address) if address else {}
	return {
		"name": escape_html(company or ""),
		"logo": _safe_logo_url(comp.get("company_logo")),
		"address": escape_html(addr_meta.get("line") or ""),
		"phone": escape_html(comp.get("phone_no") or addr_meta.get("phone") or ""),
		"email": escape_html(comp.get("email") or addr_meta.get("email_id") or ""),
		"website": escape_html(comp.get("website") or ""),
		"tax_id": escape_html(comp.get("tax_id") or addr_meta.get("gstin") or ""),
	}


def _address_details(address: str) -> dict:
	addr_fields = ["address_line1", "address_line2", "city", "state", "pincode", "phone", "email_id"]
	has_gstin = frappe.get_meta("Address").has_field("gstin")
	if has_gstin:
		addr_fields.append("gstin")
	values = frappe.db.get_value("Address", address, addr_fields, as_dict=True) or {}
	line = ", ".join(values[f] for f in ("address_line1", "address_line2", "city", "state", "pincode") if values.get(f))
	return {
		"line": line,
		"phone": values.get("phone") or "",
		"email_id": values.get("email_id") or "",
		"gstin": values.get("gstin") or "" if has_gstin else "",
	}


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
		"rounding_adjustment": flt(doc.rounding_adjustment),
		"grand_total": flt(doc.rounded_total or doc.grand_total),
		"avg_rate": round(flt(doc.net_total) / area, 2) if area else 0,
	}


def _quoted_row(item) -> dict | None:
	"""A design row priced as the Quotation line says, not as the design is priced now."""
	design = frappe.db.get_value("Window Design", item.fen_window_design, DESIGN_FIELDS, as_dict=True)
	if not design:
		return None
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
		"finish_color": _safe_color(finish.color if finish else None),
		"glass": [escape_html(snapshot.glasses[c].name if c in snapshot.glasses else c) for c in glass_codes],
		"floor": escape_html(design.floor or ""),
		"location": escape_html(design.location or ""),
		"area_m2": flt(design.area_m2),
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
		"typology": _typology(cells),
	}


def _series_title(series_version: str) -> str:
	series = frappe.db.get_value("Series Version", series_version, "series")
	return frappe.db.get_value("Profile Series", series, "series_title") or series


def _profile_names(snapshot, codes) -> str:
	return escape_html(", ".join(snapshot.profiles[c].name if c in snapshot.profiles else c for c in codes))


def _first_matching(names: list[str], word: str) -> str:
	return escape_html(next((name for name in dict.fromkeys(names) if word in name.upper()), ""))


def _safe_color(color: str | None) -> str:
	val = (color or "").strip()
	if re.fullmatch(r"#[0-9A-Fa-f]{3,8}|[A-Za-z]{3,20}", val):
		return val
	return ""
