"""Hardware and consumable BOM lines from the series hardware rules."""

from onebook_fenestration.engine.formula import evaluate
from onebook_fenestration.engine.members import FRAME_PANEL
from onebook_fenestration.engine.types import BomLine, CutMember, GlassPane, HardwareRule, SeriesSnapshot

MEMBER_ROLES = {"frame_member": "frame", "sash_member": "sash", "mullion": "mullion"}


def hardware_bom(
	members: list[CutMember],
	panes: list[GlassPane],
	sash_sizes: dict[str, tuple[float, float]],
	shutter_kg: dict[str, float],
	window_vars: dict,
	snapshot: SeriesSnapshot,
) -> list[BomLine]:
	bom: list[BomLine] = []
	constants = snapshot.constants

	for rule in snapshot.hardware_rules:
		for panel, position, variables in _contexts(rule.per, members, panes, sash_sizes, shutter_kg, window_vars, snapshot):
			variables = {**constants, **variables}
			if not evaluate(rule.when, variables, rule.id):
				continue
			qty = evaluate(rule.qty, variables, rule.id)
			if not qty:
				continue
			length = evaluate(rule.length, variables, rule.id) if rule.length else None
			bom.append(BomLine(rule.item, rule.name, qty, rule.uom, panel, position, length, rule.group))
	return bom


def _contexts(per, members, panes, sash_sizes, shutter_kg, window_vars, snapshot):
	"""Yield (panel, position, variables) for every place a rule of this kind iterates."""
	if per in MEMBER_ROLES:
		for m in members:
			if m.role == MEMBER_ROLES[per]:
				yield m.panel, m.position, {"len": m.length, "position": m.position, "role": m.role}
	elif per == "sash":
		for panel, (sash_w, sash_h) in sash_sizes.items():
			yield panel, "", {"sash_w": sash_w, "sash_h": sash_h, "shutter_kg": shutter_kg.get(panel, 0.0), "panel": panel}
	elif per == "glass":
		for p in panes:
			thickness = snapshot.glasses[p.glass].thickness_mm
			yield p.panel, "", {"glass_w": p.width, "glass_h": p.height, "glass_t": thickness}
	elif per == "window":
		yield FRAME_PANEL, "", dict(window_vars)
