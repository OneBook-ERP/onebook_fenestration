"""DXF profile cross-section analyzer: area, inertia, weight and SVG outline."""

from dataclasses import dataclass
import math

import ezdxf
from ezdxf.acis import sab as acis_sab
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
		raise SectionError(f"cannot read DXF: {exc}") from exc
	insunits = doc.header.get("$INSUNITS", 0)
	scale, warnings = _unit_scale(insunits)
	raw_loops = _read_raw_loops(doc.modelspace(), layer)
	if not raw_loops:
		raise SectionError("no closed polylines")
	if insunits == 1 and _raw_span(raw_loops) >= 8.0:
		scale = 1.0
		warnings = (*warnings, "units_assumed_mm")
	loops = [[(x * scale, y * scale) for x, y in pts] for pts in raw_loops]
	signs = _loop_signs(loops)
	return _build(loops, signs, warnings)


def _unit_scale(insunits) -> tuple[float, tuple[str, ...]]:
	if insunits in UNIT_SCALE:
		return UNIT_SCALE[insunits], ()
	if insunits == 0:
		return 1.0, ("units_assumed_mm",)
	raise SectionError(f"unsupported $INSUNITS {insunits}")


def _raw_span(loops: list[list[tuple[float, float]]]) -> float:
	xs = [x for pts in loops for x, _ in pts]
	ys = [y for pts in loops for _, y in pts]
	return max(max(xs) - min(xs), max(ys) - min(ys))


def _read_raw_loops(modelspace, layer) -> list[list[tuple[float, float]]]:
	loops = []
	raw_edges = []
	open_polylines = []
	for entity in modelspace:
		if layer is not None and entity.dxf.layer != layer:
			continue
		dtype = entity.dxftype()
		if dtype in ("LWPOLYLINE", "POLYLINE"):
			pts = _flatten_entity(entity)
			if entity.is_closed:
				if len(pts) >= 3:
					loops.append(pts)
			elif len(pts) >= 3:
				open_polylines.append(pts)
		elif dtype == "SPLINE":
			pts = _flatten_entity(entity)
			if (entity.closed or _dist(pts[0], pts[-1]) < 0.1) and len(pts) >= 3:
				loops.append(pts)
			elif len(pts) >= 2:
				raw_edges.append(pts)
		elif dtype in ("LINE", "ARC", "ELLIPSE"):
			pts = _flatten_entity(entity)
			if len(pts) >= 2:
				raw_edges.append(pts)
		elif dtype == "REGION":
			loops.extend(_extract_region_loops(entity))

	if raw_edges:
		loops.extend(_chain_edges(raw_edges))
	if open_polylines and loops:
		loops.extend(open_polylines)
	if len(loops) > 1:
		areas = [abs(_moments(pts)[0]) for pts in loops]
		max_area = max(areas, default=0.0)
		if max_area > 5.0:
			loops = [pts for pts, a in zip(loops, areas, strict=True) if a >= 0.05]
	return loops


def _flatten_entity(entity) -> list[tuple[float, float]]:
	points = [(v.x, v.y) for v in make_path(entity).flattening(FLATTEN_DISTANCE)]
	if len(points) > 1 and points[0] == points[-1]:
		points.pop()
	return points


def _chain_edges(raw_edges: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
	edges = _prune_spurs(_deduplicate_edges(raw_edges))
	chains1 = _merge_chains(edges, tol=0.005)
	closed, open_chains = [], []
	for c in chains1:
		if _dist(c[0], c[-1]) <= 0.01 and len(c) >= 3:
			closed.append(_strip_closing_point(c))
		else:
			open_chains.append(c)
	for c in _merge_chains(open_chains, tol=0.15):
		if _dist(c[0], c[-1]) <= 0.5 and len(c) >= 3:
			closed.append(_strip_closing_point(c))
	return closed


def _deduplicate_edges(raw_edges: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
	unique = []
	seen = set()
	for pts in raw_edges:
		p0, p1 = pts[0], pts[-1]
		if _dist(p0, p1) < 1e-5 and len(pts) < 4:
			continue
		pm = pts[len(pts) // 2] if len(pts) > 2 else ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
		ends = tuple(sorted([(round(p0[0], 3), round(p0[1], 3)), (round(p1[0], 3), round(p1[1], 3))]))
		key = ends + (round(pm[0], 2), round(pm[1], 2))
		if key not in seen:
			seen.add(key)
			unique.append(pts)
	return unique


def _prune_spurs(edges: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
	active = set(range(len(edges)))

	def neighbors(pt, exclude_i, tol):
		return [
			j
			for j in active
			if j != exclude_i and (_dist(pt, edges[j][0]) <= tol or _dist(pt, edges[j][-1]) <= tol)
		]

	changed = True
	while changed:
		changed = False
		for i in list(active):
			p0, p1 = edges[i][0], edges[i][-1]
			n0_wide = neighbors(p0, i, 0.005)
			n1_tight = [j for j in neighbors(p1, i, 0.002) if j not in n0_wide]
			n1_wide = neighbors(p1, i, 0.005)
			n0_tight = [j for j in neighbors(p0, i, 0.002) if j not in n1_wide]
			if (not n0_wide and len(n1_tight) >= 2) or (not n1_wide and len(n0_tight) >= 2):
				active.remove(i)
				changed = True
	return [edges[i] for i in sorted(active)]


def _merge_chains(chains: list[list[tuple[float, float]]], tol: float) -> list[list[tuple[float, float]]]:
	used = [False] * len(chains)
	out = []
	for i in range(len(chains)):
		if used[i]:
			continue
		used[i] = True
		chain = list(chains[i])
		while True:
			if _dist(chain[0], chain[-1]) <= tol and len(chain) >= 3:
				break
			p_start, p_end = chain[0], chain[-1]
			best = (tol, -1, True, False)
			for j in range(len(chains)):
				if used[j]:
					continue
				q0, q1 = chains[j][0], chains[j][-1]
				candidates = (
					(_dist(p_end, q0), j, True, False),
					(_dist(p_end, q1), j, True, True),
					(_dist(p_start, q1), j, False, False),
					(_dist(p_start, q0), j, False, True),
				)
				for cand in candidates:
					if cand[0] < best[0]:
						best = cand
			_, best_j, at_end, rev = best
			if best_j == -1:
				break
			used[best_j] = True
			seg = list(reversed(chains[best_j])) if rev else chains[best_j]
			chain = chain + seg[1:] if at_end else seg[:-1] + chain
		out.append(chain)
	return out


def _strip_closing_point(pts: list[tuple[float, float]], tol: float = 0.25) -> list[tuple[float, float]]:
	if len(pts) > 3 and _dist(pts[0], pts[-1]) <= tol:
		return pts[:-1]
	return pts


def _extract_region_loops(entity) -> list[list[tuple[float, float]]]:
	try:
		builder = acis_sab.parse_sab(bytes(entity.acis_data))
	except Exception:
		return []
	r0, r1, tx, ty = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 0.0, 0.0
	for ent in builder.entities:
		if ent.name == "transform":
			vecs = [t.value for t in ent.data if hasattr(t, "tag") and acis_sab.Tags(t.tag).name == "DIRECTION_VEC"]
			if len(vecs) >= 4:
				r0, r1, tx, ty = vecs[0], vecs[1], vecs[3][0], vecs[3][1]
			break

	def to_2d(pt3):
		return (r0[0] * pt3[0] + r1[0] * pt3[1] + tx, r0[1] * pt3[0] + r1[1] * pt3[1] + ty)

	loops = []
	for ent in builder.entities:
		if ent.name != "loop":
			continue
		coedges = [t.value for t in ent.data if hasattr(t.value, "name") and t.value.name == "coedge"]
		if not coedges:
			continue
		pts = _trace_sab_coedges(coedges[0], to_2d)
		if len(pts) >= 3:
			loops.append(_strip_closing_point(pts))
	return loops


def _trace_sab_coedges(first_coedge, to_2d) -> list[tuple[float, float]]:
	curr = first_coedge
	visited = set()
	segs = []
	while curr is not None and id(curr) not in visited:
		visited.add(id(curr))
		ptrs = [t.value for t in curr.data if hasattr(t.value, "name")]
		edge_ent = next((p for p in ptrs if p.name == "edge"), None)
		next_coedge = next((p for p in ptrs if p.name == "coedge"), None)
		if edge_ent is not None:
			seg_pts = _sab_edge_points(edge_ent, to_2d)
			if seg_pts:
				segs.append(seg_pts)
		curr = next_coedge
		if curr is first_coedge:
			break
	if not segs:
		return []
	if len(segs) == 1:
		return segs[0]
	d_end = min(_dist(segs[0][-1], segs[1][0]), _dist(segs[0][-1], segs[1][-1]))
	d_start = min(_dist(segs[0][0], segs[1][0]), _dist(segs[0][0], segs[1][-1]))
	loop_pts = list(reversed(segs[0])) if d_start < d_end else list(segs[0])
	for seg in segs[1:]:
		if _dist(loop_pts[-1], seg[0]) <= _dist(loop_pts[-1], seg[-1]):
			loop_pts.extend(seg[1:])
		else:
			loop_pts.extend(list(reversed(seg))[1:])
	return loop_pts


def _sab_edge_points(edge_ent, to_2d) -> list[tuple[float, float]]:
	v_ents = [t.value for t in edge_ent.data if hasattr(t.value, "name") and t.value.name == "vertex"]
	c_ents = [t.value for t in edge_ent.data if hasattr(t.value, "name") and "curve" in t.value.name]
	e_dbls = [t.value for t in edge_ent.data if hasattr(t, "tag") and acis_sab.Tags(t.tag).name == "DOUBLE"]
	if len(v_ents) < 2:
		return []
	p0, p1 = _sab_vertex_point(v_ents[0]), _sab_vertex_point(v_ents[1])
	if not (p0 and p1):
		return []
	seg_pts = [to_2d(p0), to_2d(p1)]
	if c_ents and c_ents[0].name == "ellipse-curve" and len(e_dbls) >= 2:
		locs = [t.value for t in c_ents[0].data if hasattr(t, "tag") and acis_sab.Tags(t.tag).name == "LOCATION_VEC"]
		dirs = [t.value for t in c_ents[0].data if hasattr(t, "tag") and acis_sab.Tags(t.tag).name == "DIRECTION_VEC"]
		c_dbls = [t.value for t in c_ents[0].data if hasattr(t, "tag") and acis_sab.Tags(t.tag).name == "DOUBLE"]
		if locs and len(dirs) >= 2:
			center, norm, maj = locs[0], dirs[0], dirs[1]
			ratio = c_dbls[0] if c_dbls else 1.0
			min_v = (
				(norm[1] * maj[2] - norm[2] * maj[1]) * ratio,
				(norm[2] * maj[0] - norm[0] * maj[2]) * ratio,
				(norm[0] * maj[1] - norm[1] * maj[0]) * ratio,
			)
			t0, t1 = e_dbls[0], e_dbls[1]
			radius = math.hypot(maj[0], maj[1], maj[2])
			steps = max(4, int(abs(t1 - t0) * max(radius, 0.5) / 0.04) + 1)
			seg_pts = [
				to_2d(
					(
						center[0] + math.cos(t0 + (t1 - t0) * k / steps) * maj[0] + math.sin(t0 + (t1 - t0) * k / steps) * min_v[0],
						center[1] + math.cos(t0 + (t1 - t0) * k / steps) * maj[1] + math.sin(t0 + (t1 - t0) * k / steps) * min_v[1],
						center[2] + math.cos(t0 + (t1 - t0) * k / steps) * maj[2] + math.sin(t0 + (t1 - t0) * k / steps) * min_v[2],
					)
				)
				for k in range(steps + 1)
			]
	return seg_pts


def _sab_vertex_point(vertex_ent):
	for t in vertex_ent.data:
		val = getattr(t, "value", None)
		if hasattr(val, "name") and val.name == "point":
			for pt_t in val.data:
				if hasattr(pt_t, "tag") and acis_sab.Tags(pt_t.tag).name == "LOCATION_VEC":
					return pt_t.value
	return None


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
	return math.hypot(a[0] - b[0], a[1] - b[1])


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
		coords = [f"{x - min_x:.2f} {max_y - y:.2f}" for x, y in pts]
		parts.append("M " + " L ".join(coords) + " Z")
	return " ".join(parts)
