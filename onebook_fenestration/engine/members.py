"""Cut list for frame, bars and sashes from the series member rules."""

from onebook_fenestration.engine.formula import evaluate_number
from onebook_fenestration.engine.layout import Bar, Cell
from onebook_fenestration.engine.types import CutMember, Issue, MemberRule, RuleError, SeriesSnapshot

FRAME_PANEL = "F1"


def cut_members(
	design: dict, snapshot: SeriesSnapshot, cells: list[Cell], bars: list[Bar]
) -> tuple[list[CutMember], list[Issue], dict[str, tuple[float, float]]]:
	members: list[CutMember] = []
	issues: list[Issue] = []
	sash_sizes: dict[str, tuple[float, float]] = {}

	def length_of(role: str, span: float, d_start: float = 0, d_end: float = 0) -> float:
		rule = _rule_for(snapshot, role)
		variables = {"span": span, "d_start": d_start, "d_end": d_end}
		return float(round(evaluate_number(rule.length, variables, rule.id), 1))

	def emit(panel: str, role: str, position: str, length: float, path: str):
		rule = _rule_for(snapshot, role)
		members.append(CutMember(panel, role, position, rule.profile, length, rule.angles, path))

	def add(path: str, role: str, position: str, span: float, d_start: float = 0, d_end: float = 0):
		length = length_of(role, span, d_start, d_end)
		if length <= 0:
			message = f"{path}: {role} {position} length is {length} mm"
			issues.append(Issue("error", "non_positive_size", message, FRAME_PANEL, path=path))
			return
		emit(FRAME_PANEL, role, position, length, path)

	width, height = design["width"], design["height"]
	for position, span in (("B", width), ("T", width), ("L", height), ("R", height)):
		add(FRAME_PANEL, "frame", position, span)

	deductions = snapshot.deductions
	for bar in bars:
		position = "H" if bar.kind == "mullion" else "W"
		d_start, d_end = (deductions[f"bar_end_{end}"] for end in bar.ends)
		add(bar.id, bar.kind, position, bar.length_span, d_start, d_end)

	number = 0
	for cell in cells:
		if cell.node["type"] != "sash":
			continue
		number += 1
		panel = f"{FRAME_PANEL}-S{number}"
		side = {s: deductions[f"sash_side_{cell.sides[s]}"] for s in "LRBT"}
		sash_w = cell.w - side["L"] - side["R"]
		sash_h = cell.h - side["B"] - side["T"]
		lengths = {pos: length_of("sash", sash_w if pos in "BT" else sash_h) for pos in "BTLR"}
		if any(length <= 0 for length in lengths.values()):
			message = f"{panel}: sash size is {round(sash_w, 1)} x {round(sash_h, 1)} mm"
			issues.append(Issue("error", "non_positive_size", message, panel, path=cell.path))
			continue
		for pos, length in lengths.items():
			emit(panel, "sash", pos, length, cell.path)
		sash_sizes[panel] = (round(sash_w, 1), round(sash_h, 1))
	return members, issues, sash_sizes


def _rule_for(snapshot: SeriesSnapshot, role: str) -> MemberRule:
	for rule in snapshot.member_rules:
		if rule.role == role:
			return rule
	raise RuleError(f"No member rule for role {role!r} in series {snapshot.code}")
