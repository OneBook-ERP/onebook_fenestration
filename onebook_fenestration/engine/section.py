"""DXF profile cross-section analyzer: area, inertia, weight and SVG outline."""

from dataclasses import dataclass

import ezdxf
from ezdxf.path import make_path

from onebook_fenestration.engine.types import SectionError

ALUMINIUM_KG_PER_MM2_M = 2.7e-3  # 2700 kg/m3 expressed per mm2 of section, per metre
UNIT_SCALE = {1: 25.4, 4: 1.0, 5: 10.0, 6: 1000.0}
FLATTEN_DISTANCE = 0.01


@dataclass(frozen=True)
class SectionProperties:
	area_mm2: float
	width_mm: float
	depth_mm: float
	perimeter_mm: float
	centroid: tuple[float, float]
	ix_mm4: float
	iy_mm4: float
	kg_per_m: float
	loops: int
	svg_path: str
	warnings: tuple[str, ...]


def analyze_dxf(path: str, layer: str | None = None) -> SectionProperties:
	try:
		doc = ezdxf.readfile(path)
	except (OSError, ezdxf.DXFError) as exc:
		raise SectionError(f"cannot read DXF: {exc}")
	scale, warnings = _unit_scale(doc.header.get("$INSUNITS", 0))
	loops = _read_loops(doc.modelspace(), layer, scale)
	if not loops:
		raise SectionError("no closed polylines")
	signs = _loop_signs(loops)
	return _build(loops, signs, warnings)


def _unit_scale(insunits) -> tuple[float, tuple[str, ...]]:
	if insunits in UNIT_SCALE:
		return UNIT_SCALE[insunits], ()
	if insunits == 0:
		return 1.0, ("units_assumed_mm",)
	raise SectionError(f"unsupported $INSUNITS {insunits}")


def _read_loops(modelspace, layer, scale) -> list[list[tuple[float, float]]]:
	loops = []
	for entity in modelspace:
		if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
			continue
		if not entity.is_closed or (layer is not None and entity.dxf.layer != layer):
			continue
		points = [(v.x * scale, v.y * scale) for v in make_path(entity).flattening(FLATTEN_DISTANCE)]
		if len(points) > 1 and points[0] == points[-1]:
			points.pop()
		if len(points) >= 3:
			loops.append(points)
	return loops


def _loop_signs(loops) -> list[int]:
	"""+1 for solids, -1 for holes (loops inside the largest loop)."""
	outer = max(loops, key=lambda pts: abs(_moments(pts)[0]))
	signs = []
	for pts in loops:
		inside = pts is not outer and _contains(outer, pts[0])
		signs.append(-1 if inside else 1)
	return signs


def _contains(polygon, point) -> bool:
	px, py = point
	inside = False
	for (x1, y1), (x2, y2) in _edges(polygon):
		if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
			inside = not inside
	return inside


def _edges(pts):
	return zip(pts, pts[1:] + pts[:1], strict=True)


def _moments(pts) -> tuple[float, float, float, float, float]:
	"""Positive-oriented area, first moments and second moments about the origin."""
	area = sx = sy = ixx = iyy = 0.0
	for (x1, y1), (x2, y2) in _edges(pts):
		cross = x1 * y2 - x2 * y1
		area += cross
		sx += (x1 + x2) * cross
		sy += (y1 + y2) * cross
		ixx += (y1 * y1 + y1 * y2 + y2 * y2) * cross
		iyy += (x1 * x1 + x1 * x2 + x2 * x2) * cross
	orient = 1.0 if area >= 0 else -1.0
	return (orient * area / 2, orient * sx / 6, orient * sy / 6, orient * ixx / 12, orient * iyy / 12)


def _build(loops, signs, warnings) -> SectionProperties:
	total = [0.0] * 5
	for pts, sign in zip(loops, signs, strict=True):
		for i, value in enumerate(_moments(pts)):
			total[i] += sign * value
	area, sx, sy, ixx, iyy = total
	if abs(area) < 1e-9:
		raise SectionError("section area is zero")
	cx, cy = sx / area, sy / area
	xs = [x for pts in loops for x, _ in pts]
	ys = [y for pts in loops for _, y in pts]
	return SectionProperties(
		area_mm2=area,
		width_mm=max(xs) - min(xs),
		depth_mm=max(ys) - min(ys),
		perimeter_mm=sum(_length(pts) for pts in loops),
		centroid=(cx, cy),
		ix_mm4=ixx - area * cy * cy,
		iy_mm4=iyy - area * cx * cx,
		kg_per_m=area * ALUMINIUM_KG_PER_MM2_M,
		loops=len(loops),
		svg_path=_svg(loops, min(xs), max(ys)),
		warnings=warnings,
	)


def _length(pts) -> float:
	return sum(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 for (x1, y1), (x2, y2) in _edges(pts))


def _svg(loops, min_x, max_y) -> str:
	parts = []
	for pts in loops:
		coords = [f"{x - min_x:.1f} {max_y - y:.1f}" for x, y in pts]
		parts.append("M " + " L ".join(coords) + " Z")
	return " ".join(parts)
