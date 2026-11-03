"""Glass pane sizes. Gaskets are series hardware rules (per frame_side / pane_side)."""

from onebook_fenestration.engine.layout import Cell
from onebook_fenestration.engine.members import FRAME_PANEL
from onebook_fenestration.engine.types import GlassPane, Issue, SeriesSnapshot


def glaze(
	design: dict,
	cells: list[Cell],
	sash_sizes: dict[str, tuple[float, float]],
	snapshot: SeriesSnapshot,
) -> tuple[list[GlassPane], list[Issue]]:
	panes: list[GlassPane] = []
	issues: list[Issue] = []
	deductions = snapshot.deductions

	sash_number = 0
	for cell in cells:
		kind = cell.node["type"]
		if kind == "sash":
			sash_number += 1
			panel = f"{FRAME_PANEL}-S{sash_number}"
			if panel not in sash_sizes:
				continue
			sash_w, sash_h = sash_sizes[panel]
			d = deductions["sash_glass"]
			width, height = sash_w - 2 * d, sash_h - 2 * d
		else:
			panel = FRAME_PANEL
			if kind == "louver":
				issues.append(Issue("warn", "louver_placeholder", "Louver glazing is not computed yet", panel, path=cell.path))
				continue
			side = {s: deductions[f"fixed_glass_side_{cell.sides[s]}"] for s in "LRBT"}
			width = cell.w - side["L"] - side["R"]
			height = cell.h - side["B"] - side["T"]

		code = cell.node.get("glass")
		if code not in snapshot.glasses:
			issues.append(Issue("error", "unknown_glass", f"{panel}: unknown glass {code!r}", panel, path=cell.path))
			continue
		width, height = round(width, 1), round(height, 1)
		if width <= 0 or height <= 0:
			message = f"{panel}: glass size is {width} x {height} mm"
			issues.append(Issue("error", "non_positive_size", message, panel, path=cell.path))
			continue
		panes.append(GlassPane(panel, len(panes) + 1, code, width, height, cell.path))
	return panes, issues
