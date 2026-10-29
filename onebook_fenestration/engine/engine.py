"""The single entry point: design tree + series snapshot -> EngineResult."""

from onebook_fenestration.engine.glazing import glaze
from onebook_fenestration.engine.hardware import hardware_bom
from onebook_fenestration.engine.layout import layout
from onebook_fenestration.engine.members import cut_members
from onebook_fenestration.engine.types import EngineResult, SeriesSnapshot
from onebook_fenestration.engine.validate import validate
from onebook_fenestration.engine.weights import weights


def compute(design: dict, snapshot: SeriesSnapshot) -> EngineResult:
	snapshot.check()
	cells, bars = layout(design)
	members, member_issues, sash_sizes = cut_members(design, snapshot, cells, bars)
	panes, gasket_bom, glass_issues = glaze(design, cells, sash_sizes, snapshot)
	shutter_kg, window_kg = weights(members, panes, snapshot)

	width, height = design["width"], design["height"]
	window_vars = {
		"W": width,
		"H": height,
		"perimeter_m": 2 * (width + height) / 1000,
		"window_kg": window_kg,
	}
	hardware = hardware_bom(members, panes, sash_sizes, shutter_kg, window_vars, snapshot)
	sash_paths = {m.panel: m.path for m in members if m.role == "sash"}
	issues = member_issues + glass_issues + validate(snapshot, sash_sizes, shutter_kg, window_vars, sash_paths)

	area_m2 = round(width * height / 1e6, 3)
	return EngineResult(
		members=members,
		glass=panes,
		bom=gasket_bom + hardware,
		shutter_kg=shutter_kg,
		window_kg=window_kg,
		area_m2=area_m2,
		area_sqft=round(area_m2 * 10.764, 3),
		issues=issues,
	)
