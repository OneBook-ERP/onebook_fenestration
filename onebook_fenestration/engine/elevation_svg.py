"""Synthesize a clean elevation SVG from a design dictionary.

Used when saving a design without frontend canvas markup, or rendering previews in backend reports.
"""

from __future__ import annotations

import re
from typing import Any

from onebook_fenestration.engine.exhaust_cut import exhaust_cut
from onebook_fenestration.engine.layout import layout

VIEW_W = 640
VIEW_H = 760
PAD = 60
FRAME_FACE = 42.0
BAR_FACE = 40.0
SASH_FACE = 50.0
DEFAULT_FINISH = "#8A8F98"
STROKE_COLOR = "#5B6470"
GLASS_FILL = "#DCEBF7"
DIM_COLOR = "#404040"


def _fmt(n: float) -> str:
	return f"{round(n, 2):.2f}".rstrip("0").rstrip(".")


def _lighten(hex_color: str, amount: float = 0.1) -> str:
	if not re.match(r"^#[0-9a-fA-F]{6}$", hex_color):
		hex_color = DEFAULT_FINISH
	num = int(hex_color[1:], 16)
	r = (num >> 16) & 255
	g = (num >> 8) & 255
	b = num & 255
	r_out = round(r + (255 - r) * amount)
	g_out = round(g + (255 - g) * amount)
	b_out = round(b + (255 - b) * amount)
	return f"#{r_out:02X}{g_out:02X}{b_out:02X}"


def generate_elevation_svg(design: dict[str, Any], finish_color: str | None = None) -> str:
	"""Generate a clean, self-contained SVG elevation for a fenestration design."""
	width = float(design.get("width", 0))
	height = float(design.get("height", 0))
	if width <= 0 or height <= 0 or "root" not in design:
		return ""

	finish = finish_color if (finish_color and re.match(r"^#[0-9a-fA-F]{6}$", finish_color)) else DEFAULT_FINISH
	sash_fill = _lighten(finish, 0.1)

	scale = min((VIEW_W - 2 * PAD) / width, (VIEW_H - 2 * PAD) / height)
	origin_x = (VIEW_W - width * scale) / 2
	origin_y = (VIEW_H - height * scale) / 2

	def px(mm: float) -> float:
		return origin_x + mm * scale

	def py(mm: float) -> float:
		return origin_y + (height - mm) * scale

	cells, bars = layout(design)

	svg_open = (
		f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Window {_fmt(width)} by {_fmt(height)} mm" '
		f'viewBox="0 0 {VIEW_W} {VIEW_H}" width="{VIEW_W}" height="{VIEW_H}" font-family="Inter, sans-serif">'
	)
	parts: list[str] = [
		svg_open,
		f'<rect x="0" y="0" width="{VIEW_W}" height="{VIEW_H}" fill="#FFFFFF"/>',
	]

	# Outer Frame
	frame_config = design.get("frameConfig") or "4-side"
	bottom_face = 0.0 if frame_config == "3-side" else (round(FRAME_FACE * 0.45) if frame_config == "3-side-threshold" else FRAME_FACE)
	fw = width * scale
	fh = height * scale
	fx = px(0)
	fy = py(height)
	ff = FRAME_FACE * scale
	bff = bottom_face * scale

	if frame_config == "4-side":
		parts.append(
			f'<rect x="{_fmt(fx)}" y="{_fmt(fy)}" width="{_fmt(fw)}" height="{_fmt(fh)}" '
			f'fill="{finish}" stroke="{STROKE_COLOR}" stroke-width="1"/>'
		)
		parts.append(f'<line x1="{_fmt(fx)}" y1="{_fmt(fy)}" x2="{_fmt(fx + ff)}" y2="{_fmt(fy + ff)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
		parts.append(f'<line x1="{_fmt(fx + fw)}" y1="{_fmt(fy)}" x2="{_fmt(fx + fw - ff)}" y2="{_fmt(fy + ff)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
		parts.append(f'<line x1="{_fmt(fx)}" y1="{_fmt(fy + fh)}" x2="{_fmt(fx + ff)}" y2="{_fmt(fy + fh - ff)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
		parts.append(f'<line x1="{_fmt(fx + fw)}" y1="{_fmt(fy + fh)}" x2="{_fmt(fx + fw - ff)}" y2="{_fmt(fy + fh - ff)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
	else:
		u_path = (
			f"M {_fmt(fx)} {_fmt(fy + fh)} L {_fmt(fx)} {_fmt(fy)} L {_fmt(fx + fw)} {_fmt(fy)} "
			f"L {_fmt(fx + fw)} {_fmt(fy + fh)} L {_fmt(fx + fw - ff)} {_fmt(fy + fh)} "
			f"L {_fmt(fx + fw - ff)} {_fmt(fy + ff)} L {_fmt(fx + ff)} {_fmt(fy + ff)} "
			f"L {_fmt(fx + ff)} {_fmt(fy + fh)} Z"
		)
		parts.append(f'<path d="{u_path}" fill="{finish}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
		parts.append(f'<line x1="{_fmt(fx)}" y1="{_fmt(fy)}" x2="{_fmt(fx + ff)}" y2="{_fmt(fy + ff)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
		parts.append(f'<line x1="{_fmt(fx + fw)}" y1="{_fmt(fy)}" x2="{_fmt(fx + fw - ff)}" y2="{_fmt(fy + ff)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
		if frame_config == "3-side-threshold":
			parts.append(
				f'<rect x="{_fmt(fx + ff)}" y="{_fmt(fy + fh - bff)}" width="{_fmt(fw - 2 * ff)}" height="{_fmt(bff)}" '
				f'fill="#64748B" stroke="{STROKE_COLOR}" stroke-width="1"/>'
			)
			parts.append(f'<line x1="{_fmt(fx)}" y1="{_fmt(fy + fh - bff)}" x2="{_fmt(fx + ff)}" y2="{_fmt(fy + fh - bff)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
			parts.append(f'<line x1="{_fmt(fx + fw - ff)}" y1="{_fmt(fy + fh - bff)}" x2="{_fmt(fx + fw)}" y2="{_fmt(fy + fh - bff)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')

	# Bars (Mullions & Transoms)
	for bar in bars:
		if bar.kind == "mullion":
			bw = BAR_FACE * scale
			bx = px(bar.at) - bw / 2
			b_bot = bottom_face if bar.start == 0 else BAR_FACE / 2
			b_top = FRAME_FACE if (bar.start + bar.length_span) >= height - 0.01 else BAR_FACE / 2
			by = py(bar.start + bar.length_span - b_top)
			bh = max(0.0, (bar.length_span - b_bot - b_top) * scale)
			parts.append(
				f'<rect x="{_fmt(bx)}" y="{_fmt(by)}" width="{_fmt(bw)}" height="{_fmt(bh)}" '
				f'fill="{finish}" stroke="{STROKE_COLOR}" stroke-width="1"/>'
			)
		else:
			bh = BAR_FACE * scale
			b_left = FRAME_FACE if bar.start == 0 else BAR_FACE / 2
			b_right = FRAME_FACE if (bar.start + bar.length_span) >= width - 0.01 else BAR_FACE / 2
			bx = px(bar.start + b_left)
			by = py(bar.at) - bh / 2
			bw = max(0.0, (bar.length_span - b_left - b_right) * scale)
			parts.append(
				f'<rect x="{_fmt(bx)}" y="{_fmt(by)}" width="{_fmt(bw)}" height="{_fmt(bh)}" '
				f'fill="{finish}" stroke="{STROKE_COLOR}" stroke-width="1"/>'
			)

	# Cells (Openings)
	for cell in cells:
		l = FRAME_FACE if cell.x == 0 else BAR_FACE / 2
		r = FRAME_FACE if (cell.x + cell.w) >= width - 0.01 else BAR_FACE / 2
		b = bottom_face if cell.y == 0 else BAR_FACE / 2
		t = FRAME_FACE if (cell.y + cell.h) >= height - 0.01 else BAR_FACE / 2

		cx = px(cell.x + l)
		cy = py(cell.y + cell.h - t)
		cw = max(0.0, (cell.w - l - r) * scale)
		ch = max(0.0, (cell.h - t - b) * scale)

		node_type = cell.node.get("type", "fixed")
		steel = bool(cell.node.get("fan")) and node_type != "louver"
		infill = "#A8ADB5" if steel else GLASS_FILL
		gx, gy, gw, gh = cx, cy, cw, ch
		if node_type == "sash":
			# Sash outer frame
			parts.append(
				f'<rect x="{_fmt(cx)}" y="{_fmt(cy)}" width="{_fmt(cw)}" height="{_fmt(ch)}" '
				f'fill="{sash_fill}" stroke="{STROKE_COLOR}" stroke-width="1"/>'
			)
			# Sash miter lines
			sf = SASH_FACE * scale
			parts.append(f'<line x1="{_fmt(cx)}" y1="{_fmt(cy)}" x2="{_fmt(cx + sf)}" y2="{_fmt(cy + sf)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
			parts.append(f'<line x1="{_fmt(cx + cw)}" y1="{_fmt(cy)}" x2="{_fmt(cx + cw - sf)}" y2="{_fmt(cy + sf)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
			parts.append(f'<line x1="{_fmt(cx)}" y1="{_fmt(cy + ch)}" x2="{_fmt(cx + sf)}" y2="{_fmt(cy + ch - sf)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')
			parts.append(f'<line x1="{_fmt(cx + cw)}" y1="{_fmt(cy + ch)}" x2="{_fmt(cx + cw - sf)}" y2="{_fmt(cy + ch - sf)}" stroke="{STROKE_COLOR}" stroke-width="1"/>')

			# Sash glass pane
			gx = cx + sf
			gy = cy + sf
			gw = max(0.0, cw - 2 * sf)
			gh = max(0.0, ch - 2 * sf)
			parts.append(
				f'<rect x="{_fmt(gx)}" y="{_fmt(gy)}" width="{_fmt(gw)}" height="{_fmt(gh)}" '
				f'fill="{infill}" stroke="{STROKE_COLOR}" stroke-width="1"/>'
			)

			# Sash swing dashed polyline
			hinge = cell.node.get("hinge")
			if hinge == "left":
				parts.append(
					f'<polyline points="{_fmt(gx)},{_fmt(gy)} {_fmt(gx + gw)},{_fmt(gy + gh / 2)} {_fmt(gx)},{_fmt(gy + gh)}" '
					f'fill="none" stroke="{DIM_COLOR}" stroke-dasharray="6 4"/>'
				)
			elif hinge == "right":
				parts.append(
					f'<polyline points="{_fmt(gx + gw)},{_fmt(gy)} {_fmt(gx)},{_fmt(gy + gh / 2)} {_fmt(gx + gw)},{_fmt(gy + gh)}" '
					f'fill="none" stroke="{DIM_COLOR}" stroke-dasharray="6 4"/>'
				)
			elif hinge == "top":
				parts.append(
					f'<polyline points="{_fmt(gx)},{_fmt(gy)} {_fmt(gx + gw / 2)},{_fmt(gy + gh)} {_fmt(gx + gw)},{_fmt(gy)}" '
					f'fill="none" stroke="{DIM_COLOR}" stroke-dasharray="6 4"/>'
				)
		else:
			# Fixed or louver glass pane
			parts.append(
				f'<rect x="{_fmt(cx)}" y="{_fmt(cy)}" width="{_fmt(cw)}" height="{_fmt(ch)}" '
				f'fill="{infill}" stroke="{STROKE_COLOR}" stroke-width="1"/>'
			)

		if steel and scale > 0:
			try:
				cut = exhaust_cut(cell.node, gw / scale, gh / scale)
			except ValueError:
				cut = None
			if cut:
				parts.append(
					f'<circle cx="{_fmt(gx + cut["centerX"] * scale)}" cy="{_fmt(gy + cut["centerY"] * scale)}" '
					f'r="{_fmt(cut["diameter"] / 2 * scale)}" fill="white" stroke="{STROKE_COLOR}"/>'
				)

	# Overall dimensions
	# Width dimension below
	dim_y = py(0) + 24
	parts.append(f'<line x1="{_fmt(fx)}" x2="{_fmt(fx + fw)}" y1="{_fmt(dim_y)}" y2="{_fmt(dim_y)}" stroke="{DIM_COLOR}"/>')
	parts.append(f'<line x1="{_fmt(fx)}" x2="{_fmt(fx)}" y1="{_fmt(dim_y - 5)}" y2="{_fmt(dim_y + 5)}" stroke="{DIM_COLOR}"/>')
	parts.append(f'<line x1="{_fmt(fx + fw)}" x2="{_fmt(fx + fw)}" y1="{_fmt(dim_y - 5)}" y2="{_fmt(dim_y + 5)}" stroke="{DIM_COLOR}"/>')
	parts.append(f'<text x="{_fmt(fx + fw / 2)}" y="{_fmt(dim_y - 4)}" text-anchor="middle" font-size="12" font-weight="600" fill="{DIM_COLOR}">{_fmt(width)}</text>')

	# Height dimension to the left
	dim_x = fx - 24
	parts.append(f'<line x1="{_fmt(dim_x)}" x2="{_fmt(dim_x)}" y1="{_fmt(fy)}" y2="{_fmt(fy + fh)}" stroke="{DIM_COLOR}"/>')
	parts.append(f'<line x1="{_fmt(dim_x - 5)}" x2="{_fmt(dim_x + 5)}" y1="{_fmt(fy)}" y2="{_fmt(fy)}" stroke="{DIM_COLOR}"/>')
	parts.append(f'<line x1="{_fmt(dim_x - 5)}" x2="{_fmt(dim_x + 5)}" y1="{_fmt(fy + fh)}" y2="{_fmt(fy + fh)}" stroke="{DIM_COLOR}"/>')
	parts.append(
		f'<text transform="translate({_fmt(dim_x - 4)} {_fmt(fy + fh / 2)}) rotate(-90)" '
		f'text-anchor="middle" font-size="12" font-weight="600" fill="{DIM_COLOR}">{_fmt(height)}</text>'
	)

	parts.append("</svg>")
	return "".join(parts)

