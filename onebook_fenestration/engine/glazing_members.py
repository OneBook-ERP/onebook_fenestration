"""Members cut per side of a glass pane: glazing beads around fixed panes, glass adaptors around sash panes.

Rule variables: series constants and deductions, then `opening_w` / `opening_h` (glass size + 2 x `glass_clearance`),
`position` (B/T/L/R), `glass_t` (overall thickness) and `glass` (code). Every rule whose `when` holds cuts a member.
"""

from onebook_fenestration.engine.formula import evaluate_number
from onebook_fenestration.engine.members import FRAME_PANEL, matching_rules
from onebook_fenestration.engine.types import CutMember, GlassPane, Issue, SeriesSnapshot

BEAD, ADAPTOR = "bead", "glass_adaptor"


def glass_members(panes: list[GlassPane], snapshot: SeriesSnapshot) -> tuple[list[CutMember], list[Issue]]:
	"""Bead / adaptor members for every pane, plus a warning for each fixed pane no bead rule applied to.

	A series without bead or adaptor rules gets nothing (and no warning).
	"""
	roles = {rule.role for rule in snapshot.member_rules}
	if BEAD not in roles and ADAPTOR not in roles:
		return [], []
	members: list[CutMember] = []
	issues: list[Issue] = []
	base = {**snapshot.deductions, **snapshot.constants}
	for pane in panes:
		role = BEAD if pane.panel == FRAME_PANEL else ADAPTOR
		cut = _pane_members(pane, role, base, snapshot)
		members += [m for m in cut if m.length > 0]
		issues += [_non_positive(pane, m) for m in cut if m.length <= 0]
		if role == BEAD and BEAD in roles and not cut:
			message = f"{pane.panel}: no glazing bead rule for glass {pane.glass}"
			issues.append(Issue("warn", "no_glazing_bead", message, pane.panel, path=pane.path))
	return members, issues


def _pane_members(pane: GlassPane, role: str, base: dict, snapshot: SeriesSnapshot) -> list[CutMember]:
	clearance = 2 * snapshot.constants["glass_clearance"]
	pane_vars = {
		"opening_w": pane.width + clearance,
		"opening_h": pane.height + clearance,
		"glass_t": snapshot.glasses[pane.glass].thickness_mm,
		"glass": pane.glass,
	}
	members = []
	for position in "BTLR":
		variables = {**base, **pane_vars, "position": position}
		for rule in matching_rules(snapshot, role, variables):
			length = float(round(evaluate_number(rule.length, variables, rule.id), 1))
			members.append(
				CutMember(pane.panel, role, position, rule.profile, length, rule.angles, pane.path)
			)
	return members


def _non_positive(pane: GlassPane, member: CutMember) -> Issue:
	message = f"{pane.panel}: {member.role} {member.position} length is {member.length} mm"
	return Issue("error", "non_positive_size", message, pane.panel, path=pane.path)
