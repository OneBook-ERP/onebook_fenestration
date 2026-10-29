"""Shutter and window weights from cut members and glass panes."""

from onebook_fenestration.engine.types import CutMember, GlassPane, SeriesSnapshot


def weights(
	members: list[CutMember], panes: list[GlassPane], snapshot: SeriesSnapshot
) -> tuple[dict[str, float], float]:
	density = snapshot.constants["glass_density"]

	def member_kg(member: CutMember) -> float:
		return member.length / 1000 * snapshot.profiles[member.profile].kg_per_m

	def glass_kg(pane: GlassPane) -> float:
		return pane.width * pane.height / 1e6 * snapshot.glasses[pane.glass].thickness_mm * density

	shutter = {m.panel: 0.0 for m in members if m.role == "sash"}
	for member in members:
		if member.role == "sash":
			shutter[member.panel] += member_kg(member)
	for pane in panes:
		if pane.panel in shutter:
			shutter[pane.panel] += glass_kg(pane)

	window = sum(member_kg(m) for m in members) + sum(glass_kg(p) for p in panes)
	return {panel: round(kg, 3) for panel, kg in shutter.items()}, round(window, 3)
