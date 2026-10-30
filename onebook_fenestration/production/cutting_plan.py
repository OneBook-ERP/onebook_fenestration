"""Cutting Plan glue: Sales Order design lines -> cut pieces per profile + finish -> optimizer -> stored plan and summary."""

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import escape_html, flt

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.cutting import Piece, optimize, wastage
from onebook_fenestration.series_studio.snapshot import get_snapshot

SUMMARY_FIELDS = (
	"bar_count",
	"pieces",
	"cut_mm",
	"rest_mm",
	"waste_mm",
	"kg_bars",
	"kg_used",
	"waste_pct_incl_rest",
	"waste_pct_excl_rest",
	"kg_per_m",
)


def set_defaults(doc) -> None:
	"""Fill kerf and minimum rest from Fenestration Settings when the plan leaves them empty."""
	if not doc.is_new():
		return
	if doc.kerf_mm is None:
		doc.kerf_mm = _setting("cut_kerf_mm")
	if doc.min_rest_mm is None:
		doc.min_rest_mm = _setting("min_rest_mm")


def stored_value(fieldname: str) -> str | None:
	"""The raw saved Fenestration Settings value, None when never saved (a saved 0 stays "0")."""
	rows = frappe.db.sql(
		"select value from tabSingles where doctype = 'Fenestration Settings' and field = %s", fieldname
	)
	return rows[0][0] if rows else None


def _setting(fieldname: str) -> float:
	"""A Fenestration Settings number; the field's own default only when Settings never stored one."""
	value = stored_value(fieldname)
	if value in (None, ""):
		value = frappe.get_meta("Fenestration Settings").get_field(fieldname).default
	return flt(value)


def collect_pieces(order_names: list[str]) -> dict[tuple[str, str], list[Piece]]:
	"""Cut pieces of every design line on the given submitted Sales Orders, keyed by (profile, finish).

	Each member is cut once per unit of the Sales Order line quantity (not the design's own quantity).
	"""
	lines = frappe.get_all(
		"Sales Order Item",
		filters={"parenttype": "Sales Order", "parent": ("in", order_names), "fen_window_design": ("is", "set")},
		fields=["fen_window_design", "qty"],
		order_by="parent, idx",
	)
	default_finish = frappe.get_cached_doc("Fenestration Settings").default_finish
	groups: dict[tuple[str, str], list[Piece]] = defaultdict(list)
	cut_lists: dict[str, tuple] = {}
	for line in lines:
		design_name = line.fen_window_design
		if design_name not in cut_lists:
			cut_lists[design_name] = _design_members(design_name, default_finish)
		ref, finish, members = cut_lists[design_name]
		if flt(line.qty) != int(flt(line.qty)):
			frappe.throw(_("Qty must be whole for cutting (Sales Order line for {0}).").format(ref))
		for copy in range(1, int(line.qty) + 1):
			suffix = f" #{copy}" if copy > 1 else ""
			for member in members:
				groups[(member.profile, finish)].append(
					Piece(member.length, f"{ref} {member.panel} {member.position}{suffix}")
				)
	return dict(groups)


def build_plan(doc) -> None:
	"""Validate the orders, run the optimizer per (profile, finish) and store plan_json and the summary rows."""
	order_names = [row.sales_order for row in doc.orders]
	_check_orders(order_names, doc.company)
	groups = []
	doc.set("summary", [])
	for (profile, finish), pieces in sorted(collect_pieces(order_names).items()):
		info = profile_info(profile)
		if not info:
			frappe.throw(_("Fenestration Profile {0} no longer exists.").format(profile))
		result = optimize(pieces, parse_bar_lengths(info.bar_lengths, profile), doc.kerf_mm, doc.min_rest_mm)
		stats = wastage(result, flt(info.kg_per_m))
		groups.append(
			{
				"profile": profile,
				"finish": finish,
				"bars": [
					{
						"bar_length": bar.bar_length,
						"pieces": [_piece_dict(p) for p in bar.pieces],
						"remainder_mm": bar.remainder_mm,
						"is_rest": bar.is_rest,
					}
					for bar in result.bars
				],
				"unplaced": [_piece_dict(p) for p in result.unplaced],
			}
		)
		doc.append("summary", _summary_row(profile, finish, stats))
	doc.plan_json = json.dumps({"groups": groups})
	doc.unplaced_count = sum(len(group["unplaced"]) for group in groups)


def profile_info(profile: str):
	return frappe.db.get_value("Fenestration Profile", profile, ("bar_lengths", "kg_per_m"), as_dict=True)


def parse_bar_lengths(text: str | None, profile: str = "") -> list[float]:
	lengths = []
	for part in (text or "").replace(";", ",").split(","):
		if not part.strip():
			continue
		try:
			lengths.append(float(part))
		except ValueError:
			frappe.throw(_("Fenestration Profile {0} has an invalid bar length: {1}").format(profile, part.strip()))
	return lengths


def _design_members(design_name: str, default_finish: str | None) -> tuple:
	design = frappe.db.get_value(
		"Window Design", design_name, ("design_ref", "series_version", "design_json", "finish"), as_dict=True
	)
	spec = design.design_json
	result = compute(json.loads(spec) if isinstance(spec, str) else spec, get_snapshot(design.series_version))
	return design.design_ref, design.finish or default_finish or "", result.members


def _check_orders(order_names: list[str], company: str) -> None:
	seen = set()
	for name in order_names:
		if name in seen:
			frappe.throw(_("Sales Order {0} is listed twice.").format(name))
		seen.add(name)
		docstatus, order_company = frappe.db.get_value("Sales Order", name, ("docstatus", "company"))
		if docstatus != 1:
			frappe.throw(_("Sales Order {0} is not submitted.").format(name))
		if order_company != company:
			frappe.throw(_("Sales Order {0} belongs to {1}, not {2}.").format(name, order_company, company))


def _piece_dict(piece: Piece) -> dict:
	return {"length": piece.length, "label": piece.label}


def _summary_row(profile: str, finish: str, stats: dict) -> dict:
	bars = ", ".join(f"{length:g} × {count}" for length, count in sorted(stats["bars"].items()))
	return {"profile": profile, "finish": finish, "bars": bars, **{k: stats[k] for k in SUMMARY_FIELDS}}


def schedule_context(doc) -> dict:
	"""Escaped, display-ready groups and wastage rows for the Profile Cutting Schedule print format."""
	plan = json.loads(doc.plan_json or "{}").get("groups", [])
	groups = []
	for group in plan:
		names = frappe.db.get_value("Fenestration Profile", group["profile"], "profile_name")
		finish = frappe.db.get_value("Profile Finish", group["finish"], "finish_name") or group["finish"]
		groups.append(
			{
				"profile": escape_html(group["profile"]),
				"profile_name": escape_html(names or ""),
				"finish": escape_html(finish),
				"bars": [_bar_row(bar) for bar in group["bars"]],
				"unplaced": [_cut_text(piece) for piece in group["unplaced"]],
			}
		)
	summary = [
		{
			"profile": escape_html(row.profile),
			"finish": escape_html(row.finish or ""),
			"bars": escape_html(row.bars or ""),
			**{key: row.get(key) for key in SUMMARY_FIELDS},
		}
		for row in doc.summary
	]
	return {"groups": groups, "summary": summary}


def _bar_row(bar: dict) -> dict:
	return {
		"bar_length": f"{bar['bar_length']:g}",
		"cuts": "; ".join(_cut_text(piece) for piece in bar["pieces"]),
		"remainder": f"{bar['remainder_mm']:g}",
		"kind": "Rest" if bar["is_rest"] else "Waste",
	}


def _cut_text(piece: dict) -> str:
	return f"{escape_html(piece['label'])} {piece['length']:g}"
