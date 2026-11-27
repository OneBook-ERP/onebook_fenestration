"""Clean, reconciled Cut Optimisation / Cutting Sheet builder and SVG diagram renderer."""

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import frappe
from frappe.utils import escape_html, flt, now_datetime

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.cutting import Piece, optimize, wastage
from onebook_fenestration.fenestration.print_context import (
	DESIGN_FIELDS,
	_safe_color,
	company_header,
)
from onebook_fenestration.fenestration.quotation import current_designs
from onebook_fenestration.production.cutting_plan import _setting, parse_bar_lengths
from onebook_fenestration.series_studio.outline import _coords, _parse, transform_path
from onebook_fenestration.series_studio.snapshot import get_snapshot

TEMPLATE_PATH = Path(__file__).with_name("cutting_sheet.html")


@dataclass(frozen=True)
class CutSpec:
	length: float
	key: str
	ref: str
	panel: str
	position: str
	role: str
	left_angle: int
	right_angle: int
	angles: str


def window_cutting_sheet(doc) -> dict:
	"""Build Cutting Sheet context for a single Window Design."""
	project = (
		frappe.db.get_value(
			"Fenestration Project",
			doc.project,
			("name", "project_title", "customer", "company", "owner"),
			as_dict=True,
		)
		or {}
	)
	return _build_cutting_sheet([doc], project)


def project_cutting_sheet(doc) -> dict:
	"""Build Cutting Sheet context across all active designs of a project."""
	designs = current_designs(doc.name, DESIGN_FIELDS)
	project = {
		"name": doc.name,
		"project_title": doc.project_title,
		"customer": doc.customer,
		"company": doc.company,
		"owner": doc.owner,
	}
	return _build_cutting_sheet(designs, project)


def render_cutting_sheet(doc, mode: str = "window", no_letterhead: bool = False, footer: str = "") -> str:
	"""Render the shared Cutting Sheet HTML for either Window Design or Fenestration Project."""
	cs = project_cutting_sheet(doc) if mode == "project" else window_cutting_sheet(doc)
	# Bundled static Jinja template from this package (never user-supplied).
	template = TEMPLATE_PATH.read_text(encoding="utf-8")
	return frappe.render_template(  # nosemgrep: frappe-ssti
		template,
		{
			"doc": doc,
			"cs": cs,
			"header": cs["header"],
			"mode": mode,
			"no_letterhead": bool(no_letterhead),
			"footer": footer or "",
		},
	)


def _build_cutting_sheet(design_docs: list, project: dict) -> dict:
	kerf_mm = _setting("cut_kerf_mm")
	min_rest_mm = _setting("min_rest_mm")
	default_finish = frappe.db.get_single_value("Fenestration Settings", "default_finish") or ""
	header = company_header(project.get("company"))
	grouped_specs = _collect_cut_specs(design_docs, default_finish)

	profile_codes = sorted({profile for profile, _finish in grouped_specs})
	profiles_meta = _fetch_profiles_meta(profile_codes)
	finishes_meta = _fetch_finishes_meta({finish for _profile, finish in grouped_specs if finish})

	groups = []
	residuals_map: dict[tuple, dict] = {}
	summary_rows = []

	for (profile_code, finish_code), specs in sorted(grouped_specs.items()):
		p_meta = profiles_meta.get(profile_code, {})
		f_meta = finishes_meta.get(finish_code, {})
		bar_lengths = _safe_bar_lengths(p_meta.get("bar_lengths"), profile_code)
		spec_by_key = {s.key: s for s in specs}
		pieces = [Piece(s.length, s.key) for s in specs]
		result = optimize(pieces, bar_lengths, kerf_mm, min_rest_mm)
		stats = wastage(result, flt(p_meta.get("kg_per_m")))

		finish_name = escape_html(f_meta.get("finish_name") or finish_code or "Mill Finish")
		finish_color = _safe_color(f_meta.get("color"))
		profile_name = escape_html(p_meta.get("profile_name") or profile_code)
		series = escape_html(p_meta.get("series") or "")

		patterns = _group_bar_patterns(result.bars, spec_by_key, kerf_mm)
		_accumulate_residuals(
			residuals_map, result.bars, profile_code, profile_name, finish_name, finish_color
		)

		bar_mm = round(stats["bar_mm"], 1)
		cut_mm = round(stats["cut_mm"], 1)
		kerf_total_mm = round(stats["kerf_mm"], 1)
		rest_mm = round(stats["rest_mm"], 1)
		waste_mm = round(stats["waste_mm"], 1)
		scrap_mm = round(max(0.0, waste_mm - kerf_total_mm), 1)
		unconsumed_mm = round(max(0.0, bar_mm - cut_mm), 1)
		utilization_pct = round((cut_mm / bar_mm) * 100.0, 1) if bar_mm else 0.0
		waste_pct_excl = round((waste_mm / bar_mm) * 100.0, 1) if bar_mm else 0.0
		wastage_pct = round((unconsumed_mm / bar_mm) * 100.0, 1) if bar_mm else 0.0
		stock_desc = _format_stock_summary(stats["bars"])

		groups.append(
			{
				"profile": escape_html(profile_code),
				"profile_name": profile_name,
				"series": series,
				"role": escape_html((p_meta.get("role") or "").capitalize()),
				"finish": finish_name,
				"finish_color": finish_color,
				"width_mm": flt(p_meta.get("width_mm")),
				"depth_mm": flt(p_meta.get("depth_mm")),
				"section_uri": _section_svg_uri(
					p_meta.get("section_svg"),
					flt(p_meta.get("width_mm")),
					flt(p_meta.get("depth_mm")),
					p_meta.get("section_rotation"),
					p_meta.get("section_flip_x"),
					p_meta.get("section_flip_y"),
				),
				"stock_summary": stock_desc,
				"bar_count": stats["bar_count"],
				"piece_count": stats["pieces"],
				"bar_mm": bar_mm,
				"cut_mm": cut_mm,
				"kerf_mm": kerf_total_mm,
				"rest_mm": rest_mm,
				"scrap_mm": scrap_mm,
				"waste_mm": waste_mm,
				"wastage_mm": unconsumed_mm,
				"utilization_pct": utilization_pct,
				"wastage_pct": wastage_pct,
				"net_waste_pct": waste_pct_excl,
				"kg_bars": stats["kg_bars"],
				"kg_used": stats["kg_used"],
				"patterns": patterns,
				"unplaced": [
					{
						"ref": escape_html(spec_by_key[p.label].ref),
						"panel": escape_html(spec_by_key[p.label].panel),
						"position": escape_html(spec_by_key[p.label].position),
						"length": p.length,
					}
					for p in result.unplaced
				],
			}
		)

		summary_rows.append(
			{
				"series": series,
				"profile": escape_html(profile_code),
				"profile_name": profile_name,
				"finish": finish_name,
				"finish_color": finish_color,
				"bar_count": stats["bar_count"],
				"piece_count": stats["pieces"],
				"bars_label": stock_desc,
				"bar_mm": bar_mm,
				"cut_mm": cut_mm,
				"kerf_mm": kerf_total_mm,
				"rest_mm": rest_mm,
				"scrap_mm": scrap_mm,
				"waste_mm": waste_mm,
				"wastage_mm": unconsumed_mm,
				"waste_pct_excl": waste_pct_excl,
				"wastage_pct": wastage_pct,
				"kg_bars": stats["kg_bars"],
				"kg_used": stats["kg_used"],
			}
		)

	residuals = sorted(
		residuals_map.values(),
		key=lambda r: (r["profile"], r["finish"], -r["length"]),
	)
	total_bar_mm = round(sum(r["bar_mm"] for r in summary_rows), 1)
	total_cut_mm = round(sum(r["cut_mm"] for r in summary_rows), 1)
	total_kerf_mm = round(sum(r["kerf_mm"] for r in summary_rows), 1)
	total_rest_mm = round(sum(r["rest_mm"] for r in summary_rows), 1)
	total_scrap_mm = round(sum(r["scrap_mm"] for r in summary_rows), 1)
	total_waste_mm = round(sum(r["waste_mm"] for r in summary_rows), 1)
	total_wastage_mm = round(sum(r["wastage_mm"] for r in summary_rows), 1)

	return {
		"header": header,
		"company": project.get("company") or "",
		"project_code": escape_html(project.get("name") or ""),
		"project_title": escape_html(project.get("project_title") or ""),
		"customer": escape_html(project.get("customer") or ""),
		"person_in_charge": escape_html(
			frappe.db.get_value("User", project.get("owner"), "full_name") or project.get("owner") or ""
		),
		"generated_on": now_datetime().strftime("%d-%m-%Y / %H:%M"),
		"kerf_mm": kerf_mm,
		"min_rest_mm": min_rest_mm,
		"residuals": residuals,
		"groups": groups,
		"summary": summary_rows,
		"totals": {
			"bar_count": sum(r["bar_count"] for r in summary_rows),
			"piece_count": sum(r["piece_count"] for r in summary_rows),
			"residual_count": sum(r["qty"] for r in residuals),
			"bar_mm": total_bar_mm,
			"cut_mm": total_cut_mm,
			"kerf_mm": total_kerf_mm,
			"rest_mm": total_rest_mm,
			"scrap_mm": total_scrap_mm,
			"waste_mm": total_waste_mm,
			"wastage_mm": total_wastage_mm,
			"utilization_pct": round((total_cut_mm / total_bar_mm) * 100.0, 1) if total_bar_mm else 0.0,
			"waste_pct_excl": round((total_waste_mm / total_bar_mm) * 100.0, 1) if total_bar_mm else 0.0,
			"wastage_pct": round((total_wastage_mm / total_bar_mm) * 100.0, 1) if total_bar_mm else 0.0,
			"kg_bars": round(sum(r["kg_bars"] for r in summary_rows), 2),
			"kg_used": round(sum(r["kg_used"] for r in summary_rows), 2),
		},
	}


def _collect_cut_specs(design_docs: list, default_finish: str) -> dict[tuple[str, str], list[CutSpec]]:
	from onebook_fenestration.engine import DesignError, RuleError

	groups: dict[tuple[str, str], list[CutSpec]] = {}
	seq = 0
	snapshots = {}
	for design in design_docs:
		sv = design.series_version
		if sv not in snapshots:
			try:
				snapshots[sv] = get_snapshot(sv)
			except RuleError, frappe.DoesNotExistError:
				continue
		spec = (
			json.loads(design.design_json or "{}")
			if isinstance(design.design_json, str)
			else (design.design_json or {})
		)
		try:
			computed = compute(spec, snapshots[sv])
		except DesignError, RuleError:
			continue
		finish = design.finish or default_finish or ""
		ref = design.design_ref or design.name or ""
		qty = max(1, int(flt(design.qty) or 1))
		for _copy_idx in range(qty):
			for member in computed.members:
				seq += 1
				a1, a2 = _parse_angles(member.angles)
				groups.setdefault((member.profile, finish), []).append(
					CutSpec(
						length=round(flt(member.length), 1),
						key=f"{seq:06d}",
						ref=ref,
						panel=member.panel or "",
						position=member.position or "",
						role=member.role or "",
						left_angle=a1,
						right_angle=a2,
						angles=f"{a1}° / {a2}°",
					)
				)
	return groups


def _parse_angles(angles) -> tuple[int, int]:
	if isinstance(angles, str):
		try:
			angles = json.loads(angles)
		except Exception:
			parts = [int(float(p)) for p in re.findall(r"\d+(?:\.\d+)?", angles)]
			if len(parts) >= 2:
				return (45 if parts[0] == 135 else parts[0]), (45 if parts[1] == 135 else parts[1])
			return (90, 90)
	if isinstance(angles, (list, tuple)) and len(angles) >= 2:
		a1 = round(flt(angles[0]))
		a2 = round(flt(angles[1]))
		return (45 if a1 == 135 else a1), (45 if a2 == 135 else a2)
	return (90, 90)


def _fetch_profiles_meta(profile_codes: list[str]) -> dict[str, dict]:
	if not profile_codes:
		return {}
	base_fields = [
		"name",
		"profile_name",
		"series",
		"role",
		"bar_lengths",
		"kg_per_m",
		"width_mm",
		"depth_mm",
		"section_svg",
	]
	rot_fields = ["section_rotation", "section_flip_x", "section_flip_y"]
	try:
		rows = frappe.get_all(
			"Fenestration Profile", filters={"name": ("in", profile_codes)}, fields=base_fields + rot_fields
		)
	except frappe.db.OperationalError:
		try:
			rows = frappe.get_all(
				"Fenestration Profile",
				filters={"name": ("in", profile_codes)},
				fields=[*base_fields, "section_rotation"],
			)
		except frappe.db.OperationalError:
			rows = frappe.get_all(
				"Fenestration Profile", filters={"name": ("in", profile_codes)}, fields=base_fields
			)
	return {r.name: r for r in rows}


def _fetch_finishes_meta(finish_codes: set[str]) -> dict[str, dict]:
	if not finish_codes:
		return {}
	rows = frappe.get_all(
		"Profile Finish",
		filters={"name": ("in", list(finish_codes))},
		fields=["name", "finish_name", "color"],
	)
	return {r.name: r for r in rows}


def _safe_bar_lengths(raw: str | None, profile_code: str) -> list[float]:
	if not raw:
		return []
	try:
		return parse_bar_lengths(raw, profile_code)
	except Exception:
		return []


def _format_stock_summary(bars_map: dict[float, int]) -> str:
	if not bars_map:
		return "0 Pcs."
	return ", ".join(f"{count} × {length:,.0f} mm" for length, count in sorted(bars_map.items()))  # noqa: RUF001


def _accumulate_residuals(residuals_map, bars, profile, profile_name, finish, finish_color):
	for bar in bars:
		if not bar.is_rest:
			continue
		rem = round(bar.remainder_mm)
		key = (profile, finish, rem)
		if key not in residuals_map:
			residuals_map[key] = {
				"profile": escape_html(profile),
				"profile_name": profile_name,
				"finish": finish,
				"finish_color": finish_color,
				"qty": 0,
				"length": rem,
			}
		residuals_map[key]["qty"] += 1


def _group_bar_patterns(bars, spec_by_key: dict[str, CutSpec], kerf_mm: float) -> list[dict]:
	pattern_buckets: dict[tuple, dict] = {}
	ordered_keys: list[tuple] = []

	for bar in bars:
		cuts = [spec_by_key[p.label] for p in bar.pieces]
		pat_key = (
			round(bar.bar_length, 1),
			tuple((c.ref, c.panel, c.position, round(c.length, 1), c.angles) for c in cuts),
		)
		if pat_key not in pattern_buckets:
			ordered_keys.append(pat_key)
			net_cut_mm = round(sum(c.length for c in cuts), 1)
			kerf_loss_mm = round(kerf_mm * len(cuts), 1)
			remainder_mm = round(bar.remainder_mm, 1)
			pattern_buckets[pat_key] = {
				"repeat_count": 0,
				"bar_length": bar.bar_length,
				"cut_count": len(cuts),
				"net_cut_mm": net_cut_mm,
				"kerf_loss_mm": kerf_loss_mm,
				"remainder_mm": remainder_mm,
				"utilization_pct": round((net_cut_mm / bar.bar_length) * 100.0, 1) if bar.bar_length else 0.0,
				"is_rest": bar.is_rest,
				"cuts": cuts,
				"diagram_uri": _bar_diagram_svg_uri(bar.bar_length, cuts, remainder_mm, bar.is_rest, kerf_mm),
			}
		pattern_buckets[pat_key]["repeat_count"] += 1

	patterns = []
	for key in ordered_keys:
		bucket = pattern_buckets[key]
		repeat = bucket["repeat_count"]
		cut_lines = _build_cut_lines(bucket["cuts"], repeat)
		patterns.append({**bucket, "cut_lines": cut_lines})
	return patterns


def _build_cut_lines(cuts: list[CutSpec], repeat: int) -> list[dict]:
	line_groups: dict[tuple, int] = {}
	line_order: list[tuple] = []
	for c in cuts:
		lkey = (c.position, c.panel, round(c.length, 1), c.angles, c.ref)
		if lkey not in line_groups:
			line_order.append(lkey)
			line_groups[lkey] = 0
		line_groups[lkey] += 1

	lines = []
	for pos, panel, length, angles, ref in line_order:
		per_bar_qty = line_groups[(pos, panel, length, angles, ref)]
		side_panel = " / ".join(part for part in (pos, panel) if part) or "—"
		lines.append(
			{
				"qty": per_bar_qty * repeat,
				"per_bar_qty": per_bar_qty,
				"side_panel": escape_html(side_panel),
				"length": length,
				"angles": escape_html(angles),
				"ref": escape_html(ref),
			}
		)
	return lines


def _section_svg_uri(
	path_d: str | None,
	width_mm: float,
	depth_mm: float,
	rotation: int | str | None = 0,
	flip_x: int | bool | None = 0,
	flip_y: int | bool | None = 0,
) -> str:
	if not path_d:
		return ""
	rot = int(rotation or 0)
	fx = bool(int(flip_x or 0))
	fy = bool(int(flip_y or 0))
	if rot or fx or fy:
		try:
			path_d, w, h = transform_path(path_d, rot, fx, fy)
			min_x, min_y = 0.0, 0.0
			max_x, max_y = w or width_mm or 40.0, h or depth_mm or 40.0
		except ValueError:
			min_x, min_y, max_x, max_y = _path_bounds(path_d, width_mm, depth_mm)
	else:
		min_x, min_y, max_x, max_y = _path_bounds(path_d, width_mm, depth_mm)

	w = max(1.0, max_x - min_x)
	h = max(1.0, max_y - min_y)
	pad = max(w, h) * 0.1
	stroke_w = max(w, h) * 0.03
	svg = (
		f'<svg xmlns="http://www.w3.org/2000/svg" '
		f'viewBox="{min_x - pad:.2f} {min_y - pad:.2f} {w + 2 * pad:.2f} {h + 2 * pad:.2f}">'
		f'<path d="{xml_escape(path_d, {chr(34): "&quot;"})}" fill="#E2E8F0" fill-rule="evenodd" '
		f'stroke="#0F172A" stroke-width="{stroke_w:.2f}" stroke-linejoin="round"/>'
		f"</svg>"
	)
	return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _path_bounds(path_d: str, width_mm: float, depth_mm: float) -> tuple[float, float, float, float]:
	try:
		xs, ys = _coords(_parse(path_d))
		if xs and ys:
			return min(xs), min(ys), max(xs), max(ys)
	except ValueError:
		pass
	return 0.0, 0.0, width_mm or 40.0, depth_mm or 40.0


def _bar_diagram_svg_uri(
	bar_length: float,
	cuts: list[CutSpec],
	remainder_mm: float,
	is_rest: bool,
	kerf_mm: float,
) -> str:
	if bar_length <= 0:
		return ""

	svg_w = 640.0
	pad_x = 4.0
	draw_w = svg_w - 2 * pad_x
	bar_y = 17.0
	bar_h = 25.0
	svg_h = 60.0
	scale = draw_w / bar_length

	bar_bg = (
		f'<rect x="{pad_x:.1f}" y="{bar_y:.1f}" width="{draw_w:.1f}" height="{bar_h:.1f}" rx="2" '
		f'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="0.9"/>'
	)
	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w:.0f} {svg_h:.0f}">',
		bar_bg,
	]

	cursor = pad_x
	kerf_px = max(0.0, kerf_mm * scale)

	for idx, c in enumerate(cuts):
		px_w = max(4.0, c.length * scale)
		x1 = cursor
		x2 = min(pad_x + draw_w, cursor + px_w)
		actual_w = x2 - x1

		bevel_l = min(4.5, actual_w * 0.2) if c.left_angle != 90 else 0.0
		bevel_r = min(4.5, actual_w * 0.2) if c.right_angle != 90 else 0.0

		top_x1 = x1 + bevel_l
		top_x2 = x2 - bevel_r
		pts = f"{top_x1:.1f},{bar_y:.1f} {top_x2:.1f},{bar_y:.1f} {x2:.1f},{bar_y + bar_h:.1f} {x1:.1f},{bar_y + bar_h:.1f}"
		parts.append(
			f'<polygon points="{pts}" fill="#EFF6FF" stroke="#1E3A8A" stroke-width="1.0" stroke-linejoin="round"/>'
		)

		cx = x1 + actual_w * 0.5
		if actual_w >= 26.0:
			ref_txt = xml_escape(c.ref)
			parts.append(
				f'<text x="{cx:.1f}" y="12.0" text-anchor="middle" '
				f'font-family="Inter, Helvetica, Arial, sans-serif" font-size="8.0" font-weight="700" fill="#334155">{ref_txt}</text>'
			)

		len_str = f"{c.length:g}"
		panel_tag = f"{c.position}/{c.panel}" if c.position and c.panel else (c.panel or c.position)
		if actual_w >= 66.0:
			label = xml_escape(f"{len_str} · {panel_tag}" if panel_tag else len_str)
			parts.append(
				f'<text x="{cx:.1f}" y="{bar_y + 16.0:.1f}" text-anchor="middle" '
				f'font-family="Inter, Helvetica, Arial, sans-serif" font-size="8.6" font-weight="700" fill="#0F172A">{label}</text>'
			)
		elif actual_w >= 26.0:
			parts.append(
				f'<text x="{cx:.1f}" y="{bar_y + 15.5:.1f}" text-anchor="middle" '
				f'font-family="Inter, Helvetica, Arial, sans-serif" font-size="7.8" font-weight="700" fill="#0F172A">{xml_escape(len_str)}</text>'
			)

		if actual_w >= 38.0:
			parts.append(
				f'<text x="{x1 + 2.5:.1f}" y="{bar_y + bar_h + 11.0:.1f}" text-anchor="start" '
				f'font-family="Inter, Helvetica, Arial, sans-serif" font-size="7.2" fill="#64748B">{c.left_angle}°</text>'
			)
			parts.append(
				f'<text x="{x2 - 2.5:.1f}" y="{bar_y + bar_h + 11.0:.1f}" text-anchor="end" '
				f'font-family="Inter, Helvetica, Arial, sans-serif" font-size="7.2" fill="#64748B">{c.right_angle}°</text>'
			)
		elif actual_w >= 20.0:
			parts.append(
				f'<text x="{cx:.1f}" y="{bar_y + bar_h + 11.0:.1f}" text-anchor="middle" '
				f'font-family="Inter, Helvetica, Arial, sans-serif" font-size="6.8" fill="#64748B">{c.left_angle}/{c.right_angle}</text>'
			)

		cursor = x2
		if kerf_mm > 0 and (idx < len(cuts) - 1 or remainder_mm > 0):
			gap = max(1.4, kerf_px)
			if cursor + gap <= pad_x + draw_w:
				parts.append(
					f'<rect x="{cursor:.1f}" y="{bar_y + 0.5:.1f}" width="{gap:.1f}" height="{bar_h - 1.0:.1f}" fill="#64748B"/>'
				)
				cursor += gap

	rem_w = (pad_x + draw_w) - cursor
	if remainder_mm > 0 and rem_w > 2.0:
		fill_c = "#ECFDF5" if is_rest else "#FFFBEB"
		stroke_c = "#10B981" if is_rest else "#D97706"
		txt_c = "#065F46" if is_rest else "#92400E"
		parts.append(
			f'<rect x="{cursor:.1f}" y="{bar_y:.1f}" width="{rem_w:.1f}" height="{bar_h:.1f}" rx="1.5" '
			f'fill="{fill_c}" stroke="{stroke_c}" stroke-width="0.9" stroke-dasharray="3,2"/>'
		)
		rem_label = f"{remainder_mm:g}"
		if rem_w >= 26.0:
			parts.append(
				f'<text x="{cursor + rem_w * 0.5:.1f}" y="{bar_y + 15.5:.1f}" text-anchor="middle" '
				f'font-family="Inter, Helvetica, Arial, sans-serif" font-size="8.2" font-weight="700" fill="{txt_c}">{rem_label}</text>'
			)
			if rem_w >= 46.0:
				tag = "REST" if is_rest else "SCRAP"
				parts.append(
					f'<text x="{cursor + rem_w * 0.5:.1f}" y="{bar_y + bar_h + 11.0:.1f}" text-anchor="middle" '
					f'font-family="Inter, Helvetica, Arial, sans-serif" font-size="6.8" font-weight="700" fill="{txt_c}">{tag}</text>'
				)

	parts.append("</svg>")
	svg = "".join(parts)
	return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
