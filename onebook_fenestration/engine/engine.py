"""The single entry point: design tree + series snapshot -> EngineResult."""

from onebook_fenestration.engine.glazing import glaze
from onebook_fenestration.engine.glazing_members import frame_context, glass_members
from onebook_fenestration.engine.hardware import hardware_bom
from onebook_fenestration.engine.layout import layout
from onebook_fenestration.engine.members import cut_members, sash_nodes
from onebook_fenestration.engine.types import EngineResult, Issue, SeriesSnapshot
from onebook_fenestration.engine.validate import validate
from onebook_fenestration.engine.weights import weights


def compute(design: dict, snapshot: SeriesSnapshot) -> EngineResult:
	snapshot.check()
	cells, bars = layout(design)
	members, member_issues, sash_sizes = cut_members(design, snapshot, cells, bars)
	panes, glass_issues = glaze(design, cells, sash_sizes, snapshot)
	glazing, glazing_issues = glass_members(panes, snapshot, design, cells, members)
	members += glazing
	shutter_kg, window_kg = weights(members, panes, snapshot)

	width, height = design["width"], design["height"]
	window_vars = {
		"W": width,
		"H": height,
		"perimeter_m": 2 * (width + height) / 1000,
		"window_kg": window_kg,
		**frame_context(design, snapshot, members),
	}
	hardware, hardware_issues = hardware_bom(
		members, panes, sash_sizes, shutter_kg, window_vars, snapshot, sash_nodes(cells), design=design
	)
	sash_paths = {m.panel: m.path for m in members if m.role in ("sash", "door_sash")}
	issues = member_issues + glass_issues + glazing_issues + hardware_issues
	issues += _series_product_warnings(design, cells, snapshot)
	issues += [
		Issue(
			"warn",
			"grill_visual_only",
			"Grill: weight, fabrication quantities and cost are not included",
			path=c.path,
		)
		for c in cells
		if c.node.get("grill") is not None
	]
	issues += validate(snapshot, sash_sizes, shutter_kg, window_vars, sash_paths)

	area_m2 = round(width * height / 1e6, 3)
	return EngineResult(
		members=members,
		glass=panes,
		bom=hardware,
		shutter_kg=shutter_kg,
		window_kg=window_kg,
		area_m2=area_m2,
		area_sqft=round(area_m2 * 10.764, 3),
		issues=issues,
	)


def _series_product_warnings(design: dict, cells: list, snapshot: SeriesSnapshot) -> list[Issue]:
	"""Warn when a design uses an assembly type (Door / Window / Sliding) not supported by the active series."""
	supported = tuple(getattr(snapshot, "supported_products", ()) or ())
	if not supported:
		return []

	is_sliding = bool(design.get("isSliding")) or any(
		c.node.get("type") == "sash" and bool(c.node.get("isSliding")) for c in cells
	)
	frame_is_door = str(design.get("frameConfig") or "4-side").strip().lower() in (
		"3-side",
		"3-side-threshold",
	)
	has_door_sash = any(
		c.node.get("type") == "sash" and str(c.node.get("sashConfig") or "").strip().lower() == "door"
		for c in cells
	)
	has_window_sash = any(
		c.node.get("type") == "sash" and str(c.node.get("sashConfig") or "window").strip().lower() != "door"
		for c in cells
	)

	used: list[str] = []
	if is_sliding:
		used.append("Sliding Door" if (frame_is_door or has_door_sash) else "Sliding Window")
	else:
		if frame_is_door or has_door_sash:
			used.append("Door")
		if has_window_sash or (not frame_is_door and not has_door_sash):
			used.append("Window")

	supported_label = ", ".join(supported)
	out: list[Issue] = []
	for product in dict.fromkeys(used):
		if product not in supported:
			out.append(
				Issue(
					"warn",
					"unsupported_series_product",
					f"Series {snapshot.code} does not contain profiles for {product} assemblies",
					hint=f"Supported in {snapshot.code}: {supported_label}. Switch to a compatible series or change the configuration.",
				)
			)
	return out
