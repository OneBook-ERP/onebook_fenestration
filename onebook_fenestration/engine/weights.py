"""Shutter and window weights from cut members and glass panes."""

from math import pi

from onebook_fenestration.engine.types import CutMember, GlassPane, SeriesSnapshot


def weights(
	members: list[CutMember], panes: list[GlassPane], snapshot: SeriesSnapshot
) -> tuple[dict[str, float], float]:
	density = snapshot.constants["glass_density"]

	def member_kg(member: CutMember) -> float:
		return member.length / 1000 * snapshot.profiles[member.profile].kg_per_m

	def glass_kg(pane: GlassPane) -> float:
		pane_density = density
		if pane.material == "steel":
			mm = pane.thickness
			pane_density = 7.85  # kg per square metre per mm (7850 kg/m³)
		else:
			spec = snapshot.glasses[pane.glass]
			mm = spec.thickness_mm if spec.glass_mm is None else spec.glass_mm
		area = pane.width * pane.height
		if pane.cutout:
			area -= pi * (pane.cutout["diameter"] / 2) ** 2
		return area / 1e6 * mm * pane_density

	# Every member cut for a sash panel (sash profile, door sash, glass adaptor) weighs on that shutter.
	shutter = {m.panel: 0.0 for m in members if m.role in ("sash", "door_sash")}
	for member in members:
		if member.panel in shutter:
			shutter[member.panel] += member_kg(member)
	for pane in panes:
		if pane.panel in shutter:
			shutter[pane.panel] += glass_kg(pane)

	window = sum(member_kg(m) for m in members) + sum(glass_kg(p) for p in panes)
	return {panel: round(kg, 3) for panel, kg in shutter.items()}, round(window, 3)
