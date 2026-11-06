"""Profile outlines from a Hilux "Section Details" DXF (the EvA profile cutting format sheet).

The sheet has a table whose rows carry a profile code in the "Profile Code" column and a drawing of the profile's
cross-section in the "Section  Drawing" column. Each drawing becomes an SVG path (mm, bbox at 0,0, y down) stored on
the Fenestration Profile, for display only: weights and perimeters are never touched. The drawing is stored as
drawn; the profile's `section_rotation` turns it so the face runs along the cut (see `guess_rotation`).

Run from bench (System Manager only):
	bench --site <site> execute onebook_fenestration.series_studio.section_import.import_profile_sections \
		--kwargs '{"dxf_path": "/path/to/sheet.dxf"}'
"""

import re
from dataclasses import dataclass
from itertools import pairwise

import ezdxf
import frappe
from ezdxf import bbox
from ezdxf.path import make_path

from onebook_fenestration.series_studio.outline import rotate_path

SECTION_HEADER = "section drawing"
DESCRIPTION_HEADER = "profile description"
CODE_HEADER = "profile code"
GEOMETRY_TYPES = {"LINE", "ARC", "CIRCLE", "ELLIPSE", "LWPOLYLINE", "POLYLINE", "SPLINE"}
FLATTEN_DISTANCE = 0.05  # mm chord error when arcs and ellipses become line segments
# A LINE spanning this share of its cell's width or height is a table grid line, not part of the drawing.
GRID_LINE_SHARE = 0.9
# A label further below the previous one than this many median row spacings is past the end of the table.
TABLE_END_GAP = 2.5
# A code label is one word (descriptions have spaces); position in the Profile Code column does the rest.
CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
# Hilux profile names give the size as "<DEPTH>MM X <FACE>MM", e.g. "CMT T MULLION 40MM X 60MM".
SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:MM)?\s*X\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
# How close (mm) a drawn extent must be to a size in the name to count as that size.
SIZE_TOLERANCE = 1.5


class SectionSheetError(Exception):
	pass


@dataclass(frozen=True)
class Outline:
	svg: str
	width_mm: float
	depth_mm: float


@dataclass(frozen=True)
class Box:
	min_x: float
	min_y: float
	max_x: float
	max_y: float

	@property
	def centre(self) -> tuple[float, float]:
		return (self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2

	def holds(self, x: float, y: float) -> bool:
		return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y


def import_profile_sections(dxf_path: str, profile_codes: list[str] | None = None) -> dict:
	"""Store the outline of each profile row (default: every row in the sheet) on its Fenestration Profile.

	The outline is stored as drawn; `section_rotation` (guessed from the profile name, see `guess_rotation`) turns
	it for display, and width_mm / depth_mm are the turned extents. A rotation already set (non-zero) is kept.
	Profiles with their own `dxf_file` keep the outline computed from it. Returns updated codes, skipped ones with a
	reason, codes whose rotation could not be guessed (`rotation_unknown`) and codes whose set rotation was kept
	(`rotation_kept`).
	"""
	frappe.only_for("System Manager")
	try:
		outlines = read_sections(dxf_path)
	except (OSError, ezdxf.DXFError, SectionSheetError) as exc:
		frappe.throw(f"Could not read section sheet {dxf_path}: {exc}")
	result = {"updated": [], "skipped": [], "rotation_unknown": [], "rotation_kept": []}
	for code in profile_codes or sorted(outlines):
		outline = outlines.get(code)
		profile = _profile(code)
		reason = _skip_reason(outline, profile)
		if reason:
			result["skipped"].append({"code": code, "reason": reason})
			continue
		rotation = int(profile.section_rotation or 0)
		if rotation:
			result["rotation_kept"].append(code)
		else:
			guess = guess_rotation(profile.profile_name, outline.width_mm, outline.depth_mm)
			if guess is None:
				result["rotation_unknown"].append(code)
			rotation = guess or 0
		_svg, width, depth = rotate_path(outline.svg, rotation)
		frappe.db.set_value(
			"Fenestration Profile",
			code,
			{"section_svg": outline.svg, "section_rotation": str(rotation), "width_mm": width, "depth_mm": depth},
		)
		result["updated"].append(code)
	return result


def guess_rotation(name: str | None, width: float, depth: float) -> int | None:
	"""Quarter turn that puts the profile face along x, from a "<DEPTH>MM X <FACE>MM" name and the drawn extents.

	90 when the drawing has the depth along x, 0 when it already has the face along x; None when the name has no
	sizes, the drawing matches neither, or both (depth and face too close to tell).
	"""
	match = SIZE_PATTERN.search(name or "")
	if not match:
		return None
	depth_mm, face_mm = float(match[1]), float(match[2])
	turned = _near(width, depth_mm) and _near(depth, face_mm)
	upright = _near(width, face_mm) and _near(depth, depth_mm)
	if turned == upright:
		return None
	return 90 if turned else 0


def _near(a: float, b: float) -> bool:
	return abs(a - b) <= SIZE_TOLERANCE


def _profile(code: str):
	return frappe.db.get_value(
		"Fenestration Profile", code, ["name", "profile_name", "dxf_file", "section_rotation"], as_dict=True
	)


def _skip_reason(outline: Outline | None, profile) -> str | None:
	if outline is None:
		return "not in the Section Details table"
	if not outline.svg:
		return "no drawing in its table row"
	if not profile:
		return "no Fenestration Profile with this code"
	if profile.dxf_file:
		return "profile has its own DXF; its outline comes from that file"
	return None


def read_sections(dxf_path: str) -> dict[str, Outline]:
	"""Outline per profile code found in the sheet's Section Details table(s). Pure: no database access."""
	msp = ezdxf.readfile(dxf_path).modelspace()
	texts = [(_normalised(e), e) for e in msp.query("TEXT MTEXT")]
	headers = [e for text, e in texts if text.casefold() == SECTION_HEADER]
	if not headers:
		raise SectionSheetError('no "Section Drawing" header')
	shapes = [shape for shape in map(_shape, _geometry(msp)) if shape]
	outlines = {}
	for header in headers:
		for code, cell in _rows(header, texts):
			if code not in outlines:
				outlines[code] = _outline([pts for pts, box, line in shapes if _in_cell(box, line, cell)])
	return outlines


def _normalised(entity) -> str:
	"""Plain text with formatting codes removed and runs of whitespace collapsed."""
	return " ".join(entity.plain_text().split())


def _box(entity) -> Box:
	ext = bbox.extents([entity])
	return Box(ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y)


def _rows(section_header, texts) -> list[tuple[str, Box]]:
	"""(code, drawing cell) for every row of the table under `section_header`.

	Drawing column: from the "Section Drawing" header mirrored about its centre up to the left edge of the
	"Profile Description" header. Code column: midway between the description and code headers, mirrored about the
	code header's centre. Rows: labels in the code column below the headers; each row's band runs to the midpoints
	between neighbouring labels (the first row up to the header, the last row mirrors the spacing above it).
	"""
	section = _box(section_header)
	description = _nearest_right(section, texts, DESCRIPTION_HEADER)
	code_header = _nearest_right(description, texts, CODE_HEADER)
	right = description.min_x
	left = 2 * section.centre[0] - right
	code_left = (description.centre[0] + code_header.centre[0]) / 2
	code_right = 2 * code_header.centre[0] - code_left
	top = min(section.min_y, description.min_y, code_header.min_y)
	labels = []
	for text, entity in texts:
		if not CODE_PATTERN.match(text):
			continue
		x, y = _box(entity).centre
		if code_left <= x <= code_right and y < top:
			labels.append((y, text))
	labels = _contiguous(sorted(labels, reverse=True))
	rows = []
	for i, (y, code) in enumerate(labels):
		upper = top if i == 0 else (labels[i - 1][0] + y) / 2
		lower = (y + labels[i + 1][0]) / 2 if i + 1 < len(labels) else 2 * y - upper
		rows.append((code, Box(left, lower, right, upper)))
	return rows


def _contiguous(labels: list[tuple[float, str]]) -> list[tuple[float, str]]:
	"""The labels down to the table's end: the first gap much wider than the row spacing so far ends the table
	(the same column further down the sheet holds unrelated notes and dimension texts)."""
	kept = labels[:2]
	for y, code in labels[2:]:
		gaps = sorted(a[0] - b[0] for a, b in pairwise(kept))
		if kept[-1][0] - y > TABLE_END_GAP * gaps[len(gaps) // 2]:
			break
		kept.append((y, code))
	return kept


def _nearest_right(anchor: Box, texts, wanted: str) -> Box:
	"""Box of the closest `wanted` header right of `anchor` on the same header row."""
	height = anchor.max_y - anchor.min_y
	candidates = []
	for text, entity in texts:
		if text.casefold() != wanted:
			continue
		box = _box(entity)
		if box.min_x > anchor.centre[0] and abs(box.centre[1] - anchor.centre[1]) <= 2 * height:
			candidates.append((box.min_x, box))
	if not candidates:
		raise SectionSheetError(f'no "{wanted}" header beside the "Section Drawing" header')
	return min(candidates, key=lambda c: c[0])[1]


def _geometry(space):
	"""Drawing entities of `space`, with block references exploded (recursively) into their parts."""
	for entity in space:
		kind = entity.dxftype()
		if kind == "INSERT":
			yield from _geometry(entity.virtual_entities())
		elif kind in GEOMETRY_TYPES:
			yield entity


def _shape(entity) -> tuple[list[tuple[float, float]], Box, bool] | None:
	"""(flattened points, bbox, is a LINE) for one entity, or None when it has no extent."""
	try:
		points = [(v.x, v.y) for v in make_path(entity).flattening(FLATTEN_DISTANCE)]
	except TypeError, ValueError, ezdxf.DXFError:
		return None
	if len(points) < 2:
		return None
	xs, ys = zip(*points, strict=True)
	return points, Box(min(xs), min(ys), max(xs), max(ys)), entity.dxftype() == "LINE"


def _in_cell(box: Box, is_line: bool, cell: Box) -> bool:
	"""Geometry belongs to a row when its bbox centre is in the cell; LINEs spanning most of the cell are grid."""
	if not cell.holds(*box.centre):
		return False
	if not is_line:
		return True
	return (box.max_x - box.min_x) < GRID_LINE_SHARE * (cell.max_x - cell.min_x) and (
		box.max_y - box.min_y
	) < GRID_LINE_SHARE * (cell.max_y - cell.min_y)


def _outline(polylines: list[list[tuple[float, float]]]) -> Outline:
	"""One SVG path for all polylines: absolute mm coordinates, bbox min at 0,0, y flipped to point down."""
	if not polylines:
		return Outline("", 0.0, 0.0)
	xs = [x for pts in polylines for x, _y in pts]
	ys = [y for pts in polylines for _x, y in pts]
	min_x, max_y = min(xs), max(ys)
	parts, last = [], None
	for pts in polylines:
		coords = [f"{_num(x - min_x)} {_num(max_y - y)}" for x, y in pts]
		if coords[0] == last:
			parts.append(" ".join(coords[1:]))
		else:
			parts.append("M" + " ".join(coords))
		last = coords[-1]
	return Outline(" ".join(parts), round(max(xs) - min_x, 2), round(max_y - min(ys), 2))


def _num(value: float) -> str:
	text = f"{value:.2f}".rstrip("0").rstrip(".")
	return "0" if text in ("-0", "") else text
