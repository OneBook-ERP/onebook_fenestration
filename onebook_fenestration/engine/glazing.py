"""Glass pane sizes and gasket lengths."""

from onebook_fenestration.engine.layout import Cell
from onebook_fenestration.engine.members import FRAME_PANEL
from onebook_fenestration.engine.types import BomLine, GlassPane, Issue, SeriesSnapshot

GASKET_GROUP = "Gasket"


def glaze(
	design: dict,
	cells: list[Cell],
	sash_sizes: dict[str, tuple[float, float]],
	snapshot: SeriesSnapshot,
) -> tuple[list[GlassPane], list[BomLine], list[Issue]]:
	panes: list[GlassPane] = []
	bom: list[BomLine] = []
	issues: list[Issue] = []
	deductions = snapshot.deductions
	gasket = deductions["glazing_gasket"]

	def add_gasket(item: str, name: str, panel: str, position: str, length: float):
		bom.append(BomLine(item, name, 1, "Nos", panel, position, round(length, 1), GASKET_GROUP))

	def add_frame_gasket(panel: str, width: float, height: float):
		for position, length in (("B", width), ("T", width), ("L", height), ("R", height)):
			add_gasket("G21", "FRAME GASKET CASEMENT", panel, position, length)

	add_frame_gasket(FRAME_PANEL, design["width"], design["height"])

	sash_number = 0
	for cell in cells:
		kind = cell.node["type"]
		if kind == "sash":
			sash_number += 1
			panel = f"{FRAME_PANEL}-S{sash_number}"
			if panel not in sash_sizes:
				continue
			sash_w, sash_h = sash_sizes[panel]
			add_frame_gasket(panel, sash_w, sash_h)
			d = deductions["sash_glass"]
			width, height = sash_w - 2 * d, sash_h - 2 * d
		else:
			panel = FRAME_PANEL
			if kind == "louver":
				issues.append(Issue("warn", "louver_placeholder", "Louver glazing is not computed yet", panel))
				continue
			side = {s: deductions[f"fixed_glass_side_{cell.sides[s]}"] for s in "LRBT"}
			width = cell.w - side["L"] - side["R"]
			height = cell.h - side["B"] - side["T"]

		code = cell.node.get("glass")
		if code not in snapshot.glasses:
			issues.append(Issue("error", "unknown_glass", f"{panel}: unknown glass {code!r}", panel))
			continue
		width, height = round(width, 1), round(height, 1)
		if width <= 0 or height <= 0:
			issues.append(
				Issue("error", "non_positive_size", f"{panel}: glass size is {width} x {height} mm", panel)
			)
			continue
		panes.append(GlassPane(panel, len(panes) + 1, code, width, height))
		for position, length in (("W", width), ("W", width), ("H", height), ("H", height)):
			add_gasket("G23", "GASKET 3MM", panel, position, length - 2 * gasket)
	return panes, bom, issues
