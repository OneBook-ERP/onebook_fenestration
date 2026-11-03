"""Hardware, gasket and consumable BOM lines from the series hardware rules.

Rule variables: series constants and deductions (context variables win on a name clash), then the context's own.
"""

from onebook_fenestration.engine.formula import evaluate, evaluate_number
from onebook_fenestration.engine.members import FRAME_PANEL
from onebook_fenestration.engine.types import BomLine, CutMember, GlassPane, Issue, SeriesSnapshot

GASKET_GROUP = "Gasket"
# Sash option -> (series default constant, choices). Series constants are Float rows, so a number picks a choice
# by index (0 = first); a string is taken as the choice itself. No constant means the first choice / False.
SASH_CHOICES = {"hinge_type": ("friction", "butt"), "handle": ("multipoint", "single")}
SASH_FLAGS = ("limiter", "mesh")
MEMBER_ROLES = {"frame_member": "frame", "sash_member": "sash", "mullion": "mullion", "transom_member": "transom"}


def hardware_bom(
	members: list[CutMember],
	panes: list[GlassPane],
	sash_sizes: dict[str, tuple[float, float]],
	shutter_kg: dict[str, float],
	window_vars: dict,
	snapshot: SeriesSnapshot,
	sash_nodes: dict[str, dict] | None = None,
) -> tuple[list[BomLine], list[Issue]]:
	"""BOM lines in rule order, plus a warning for each glass pane no gasket rule applied to."""
	bom: list[BomLine] = []
	gasketed: set[int] = set()
	base = {**snapshot.deductions, **snapshot.constants}

	for rule in snapshot.hardware_rules:
		for panel, position, variables in _contexts(
			rule.per, members, panes, sash_sizes, shutter_kg, window_vars, snapshot, sash_nodes or {}
		):
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


def _contexts(per, members, panes, sash_sizes, shutter_kg, window_vars, snapshot, sash_nodes):
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
			options = _sash_options(sash_nodes.get(panel, {}), snapshot)
			yield panel, "", {"sash_w": sash_w, "sash_h": sash_h, "shutter_kg": shutter_kg.get(panel, 0.0), "panel": panel, **options}
	elif per == "glass":
		for p in panes:
			thickness = snapshot.glasses[p.glass].thickness_mm
			yield p.panel, "", {"glass_w": p.width, "glass_h": p.height, "glass_t": thickness}
	elif per == "window":
		yield FRAME_PANEL, "", dict(window_vars)


def _sash_options(node: dict, snapshot: SeriesSnapshot) -> dict:
	"""hinge_type, handle, limiter, mesh for one sash: the design node's value, else the series default constant."""
	options = {}
	for name, choices in SASH_CHOICES.items():
		default = snapshot.constants.get(f"default_{name}", 0)
		if not isinstance(default, str):
			default = choices[min(int(default), len(choices) - 1)]
		options[name] = node.get(name) or default
	for name in SASH_FLAGS:
		value = node.get(name)
		options[name] = bool(snapshot.constants.get(f"default_{name}", False)) if value is None else bool(value)
	return options
