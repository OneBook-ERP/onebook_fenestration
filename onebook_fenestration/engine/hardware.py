"""Hardware, gasket and consumable BOM lines from the series hardware rules.

Rule variables: series constants and deductions (context variables win on a name clash), then the context's own.
"""

from onebook_fenestration.engine.formula import evaluate, evaluate_number
from onebook_fenestration.engine.members import FRAME_PANEL
from onebook_fenestration.engine.types import BomLine, CutMember, GlassPane, Issue, SeriesSnapshot

GASKET_GROUP = "Gasket"
MEMBER_ROLES = {"frame_member": "frame", "sash_member": "sash", "mullion": "mullion", "transom_member": "transom"}


def hardware_bom(
	members: list[CutMember],
	panes: list[GlassPane],
	sash_sizes: dict[str, tuple[float, float]],
	shutter_kg: dict[str, float],
	window_vars: dict,
	snapshot: SeriesSnapshot,
) -> tuple[list[BomLine], list[Issue]]:
	"""BOM lines in rule order, plus a warning for each glass pane no gasket rule applied to."""
	bom: list[BomLine] = []
	gasketed: set[int] = set()
	base = {**snapshot.deductions, **snapshot.constants}

	for rule in snapshot.hardware_rules:
		for panel, position, variables in _contexts(rule.per, members, panes, sash_sizes, shutter_kg, window_vars, snapshot):
			variables = {**base, **variables}
			if not evaluate(rule.when, variables, rule.id):
				continue
			qty = evaluate_number(rule.qty, variables, rule.id)
			if not qty:
				continue
			length = evaluate_number(rule.length, variables, rule.id) if rule.length else None
			bom.append(BomLine(rule.item, rule.name, qty, rule.uom, panel, position, length, rule.group))
			if rule.per == "pane_side" and rule.group == GASKET_GROUP:
				gasketed.add(variables["pane_no"])
	return bom, _ungasketed_issues(panes, gasketed)


def _ungasketed_issues(panes: list[GlassPane], gasketed: set[int]) -> list[Issue]:
	return [
		Issue("warn", "no_glazing_gasket", f"{p.panel}: no glazing gasket rule for glass {p.glass}", p.panel, path=p.path)
		for p in panes
		if p.number not in gasketed
	]


def _contexts(per, members, panes, sash_sizes, shutter_kg, window_vars, snapshot):
	"""Yield (panel, position, variables) for every place a rule of this kind iterates."""
	if per in MEMBER_ROLES:
		for m in members:
			if m.role == MEMBER_ROLES[per]:
				yield m.panel, m.position, {"len": m.length, "position": m.position, "role": m.role}
	elif per == "frame_side":
		sizes = {FRAME_PANEL: (window_vars["W"], window_vars["H"]), **sash_sizes}
		for panel, (width, height) in sizes.items():
			for position, side_len in (("B", width), ("T", width), ("L", height), ("R", height)):
				yield panel, position, {"side_len": side_len, "position": position, "panel": panel}
	elif per == "pane_side":
		for p in panes:
			thickness = snapshot.glasses[p.glass].thickness_mm
			for position, side_len in (("W", p.width), ("W", p.width), ("H", p.height), ("H", p.height)):
				variables = {"side_len": side_len, "position": position, "panel": p.panel, "glass": p.glass}
				yield p.panel, position, {**variables, "glass_t": thickness, "pane_no": p.number}
	elif per == "sash":
		for panel, (sash_w, sash_h) in sash_sizes.items():
			yield panel, "", {"sash_w": sash_w, "sash_h": sash_h, "shutter_kg": shutter_kg.get(panel, 0.0), "panel": panel}
	elif per == "glass":
		for p in panes:
			thickness = snapshot.glasses[p.glass].thickness_mm
			yield p.panel, "", {"glass_w": p.width, "glass_h": p.height, "glass_t": thickness}
	elif per == "window":
		yield FRAME_PANEL, "", dict(window_vars)
