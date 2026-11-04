"""Hardware, gasket and consumable BOM lines from the series hardware rules.

Rule variables: series constants and deductions (context variables win on a name clash), then the context's own.
"""

from onebook_fenestration.engine.formula import evaluate, evaluate_number
from onebook_fenestration.engine.members import FRAME_PANEL
from onebook_fenestration.engine.types import BomLine, CutMember, GlassPane, Issue, RuleError, SeriesSnapshot

GASKET_GROUP = "Gasket"
# Sash option defaults come from 0/1 series constants; anything else is an invalid_series_constant error.
DEFAULT_CONSTANTS = ("default_butt_hinge", "default_single_point_handle", "default_limiter", "default_mesh")
# Any panel other than the frame is a sash for pane_side rules (in_sash).
PROBE_SASH = "S1"
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
	defaults, issues = _sash_defaults(snapshot)
	gasketed: set[int] = set()
	base = {**snapshot.deductions, **snapshot.constants}

	for rule in snapshot.hardware_rules:
		for panel, position, variables in _contexts(
			rule.per, members, panes, sash_sizes, shutter_kg, window_vars, snapshot, sash_nodes or {}, defaults
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
	return bom, issues + _ungasketed_issues(panes, gasketed)


def glazing_gasket_gaps(snapshot: SeriesSnapshot) -> list[tuple[str, bool]]:
	"""(glass, in_sash) for each catalogue glass and glazing (fixed in the frame / in a sash) that no Gasket-group
	pane_side rule applies to, i.e. where a design would get the no_glazing_gasket warning.

	Probes one pane per glass and glazing through the same pane_side context `hardware_bom` uses. A rule whose
	`when` cannot be evaluated for the probe counts as not applying.
	"""
	rules = [r for r in snapshot.hardware_rules if r.group == GASKET_GROUP and r.per == "pane_side"]
	base = {**snapshot.deductions, **snapshot.constants}
	gaps = []
	for glass in sorted(snapshot.glasses):
		for panel in (FRAME_PANEL, PROBE_SASH):
			probe = GlassPane(panel, 1, glass, 1000.0, 1000.0)
			if not _any_rule_applies(rules, probe, base, snapshot):
				gaps.append((glass, _in_sash(probe)))
	return gaps


def _any_rule_applies(rules, pane: GlassPane, base: dict, snapshot: SeriesSnapshot) -> bool:
	for rule in rules:
		for _panel, _position, variables in _contexts("pane_side", [], [pane], {}, {}, {}, snapshot, {}, {}):
			try:
				if evaluate(rule.when, {**base, **variables}, rule.id):
					return True
			except RuleError:
				continue
	return False


def _ungasketed_issues(panes: list[GlassPane], gasketed: set[int]) -> list[Issue]:
	return [
		Issue("warn", "no_glazing_gasket", f"{p.panel}: no glazing gasket rule for glass {p.glass}", p.panel, path=p.path)
		for p in panes
		if p.number not in gasketed
	]


def _contexts(per, members, panes, sash_sizes, shutter_kg, window_vars, snapshot, sash_nodes, defaults):
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
				variables = {"side_len": side_len, "position": position, "panel": p.panel, "glass": p.glass, "in_sash": _in_sash(p)}
				yield p.panel, position, {**variables, "glass_t": thickness, "pane_no": p.number}
	elif per == "sash":
		for panel, (sash_w, sash_h) in sash_sizes.items():
			options = _sash_options(sash_nodes.get(panel, {}), defaults)
			yield panel, "", {"sash_w": sash_w, "sash_h": sash_h, "shutter_kg": shutter_kg.get(panel, 0.0), "panel": panel, **options}
	elif per == "glass":
		for p in panes:
			thickness = snapshot.glasses[p.glass].thickness_mm
			yield p.panel, "", {"glass_w": p.width, "glass_h": p.height, "glass_t": thickness, "in_sash": _in_sash(p)}
	elif per == "window":
		yield FRAME_PANEL, "", dict(window_vars)


def _in_sash(pane: GlassPane) -> bool:
	"""True for a pane glazed in a sash, False for a pane glazed straight into the frame (fixed glass)."""
	return pane.panel != FRAME_PANEL


def _sash_defaults(snapshot: SeriesSnapshot) -> tuple[dict[str, bool], list[Issue]]:
	"""The four 0/1 default constants as bools (missing = False), plus an error for each value that is not 0 or 1."""
	defaults, issues = {}, []
	for name in DEFAULT_CONSTANTS:
		value = snapshot.constants.get(name, 0)
		if value not in (0, 1):
			issues.append(Issue("error", "invalid_series_constant", f"series constant {name} must be 0 or 1, got {value!r}"))
		defaults[name] = value == 1
	return defaults, issues


def _sash_options(node: dict, defaults: dict[str, bool]) -> dict:
	"""hinge_type, handle, limiter, mesh for one sash: the design node's value, else the series default."""
	limiter = node.get("limiter")
	mesh = node.get("mesh")
	return {
		"hinge_type": node.get("hinge_type") or ("butt" if defaults["default_butt_hinge"] else "friction"),
		"handle": node.get("handle") or ("single" if defaults["default_single_point_handle"] else "multipoint"),
		"limiter": defaults["default_limiter"] if limiter is None else bool(limiter),
		"mesh": defaults["default_mesh"] if mesh is None else bool(mesh),
	}
