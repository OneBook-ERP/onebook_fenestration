"""Cut list for frame, bars and sashes from the series member rules."""

from onebook_fenestration.engine.formula import evaluate, evaluate_number
from onebook_fenestration.engine.layout import Bar, Cell
from onebook_fenestration.engine.types import CutMember, Issue, MemberRule, RuleError, SeriesSnapshot

FRAME_PANEL = "F1"


def cut_members(
	design: dict, snapshot: SeriesSnapshot, cells: list[Cell], bars: list[Bar]
) -> tuple[list[CutMember], list[Issue], dict[str, tuple[float, float]]]:
	members: list[CutMember] = []
	issues: list[Issue] = []
	sash_sizes: dict[str, tuple[float, float]] = {}

	base = {**snapshot.deductions, **snapshot.constants}
	raw_overrides = design.get("profiles")
	profile_overrides = raw_overrides if isinstance(raw_overrides, dict) else {}

	def resolve_profile(default_profile: str, *keys: str | None) -> str:
		for k in keys:
			if k and isinstance(k, str) and k in snapshot.profiles:
				return k
			if k and k in profile_overrides:
				cand = profile_overrides[k]
				if isinstance(cand, str) and cand in snapshot.profiles:
					return cand
		return default_profile

	def rule_and_length(
		role: str, span: float, d_start: float = 0, d_end: float = 0
	) -> tuple[MemberRule, float]:
		variables = {**base, "span": span, "d_start": d_start, "d_end": d_end}
		rule = _rule_for(snapshot, role, variables)
		return rule, float(round(evaluate_number(rule.length, variables, rule.id), 1))

	def emit(panel: str, rule: MemberRule, position: str, length: float, path: str, profile: str | None = None):
		members.append(CutMember(panel, rule.role, position, profile or rule.profile, length, rule.angles, path))

	def add(path: str, role: str, position: str, span: float, d_start: float = 0, d_end: float = 0, profile_override: str | None = None):
		rule, length = rule_and_length(role, span, d_start, d_end)
		if length <= 0:
			message = f"{path}: {role} {position} length is {length} mm"
			issues.append(Issue("error", "non_positive_size", message, FRAME_PANEL, path=path))
			return
		emit(FRAME_PANEL, rule, position, length, path, profile=profile_override or rule.profile)

	width, height = design["width"], design["height"]
	frame_code = design.get("frameProfileId")
	frame_profile = resolve_profile("", frame_code if isinstance(frame_code, str) else None, "frame", FRAME_PANEL) or None
	for position, span in (("B", width), ("T", width), ("L", height), ("R", height)):
		add(FRAME_PANEL, "frame", position, span, profile_override=frame_profile)

	deductions = snapshot.deductions
	for bar in bars:
		position = "H" if bar.kind == "mullion" else "W"
		d_start, d_end = (deductions[f"bar_end_{end}"] for end in bar.ends)
		bar_profile = resolve_profile("", bar.id, bar.kind) or None
		add(bar.id, bar.kind, position, bar.length_span, d_start, d_end, profile_override=bar_profile)

	number = 0
	for cell in cells:
		if cell.node["type"] != "sash":
			continue
		number += 1
		panel = f"{FRAME_PANEL}-S{number}"
		side = {s: deductions[f"sash_side_{cell.sides[s]}"] for s in "LRBT"}
		sash_w = cell.w - side["L"] - side["R"]
		sash_h = cell.h - side["B"] - side["T"]
		cuts = {pos: rule_and_length("sash", sash_w if pos in "BT" else sash_h) for pos in "BTLR"}
		if any(length <= 0 for _, length in cuts.values()):
			message = f"{panel}: sash size is {round(sash_w, 1)} x {round(sash_h, 1)} mm"
			issues.append(Issue("error", "non_positive_size", message, panel, path=cell.path))
			continue
		sash_profile = resolve_profile("", cell.node.get("profile"), cell.path, panel, "sash") or None
		for pos, (rule, length) in cuts.items():
			emit(panel, rule, pos, length, cell.path, profile=sash_profile or rule.profile)
		sash_sizes[panel] = (round(sash_w, 1), round(sash_h, 1))
	return members, issues, sash_sizes


def matching_rules(snapshot: SeriesSnapshot, role: str, variables: dict) -> list[MemberRule]:
	"""The member rules of `role` whose `when` holds for `variables` (an empty `when` always holds), in series order."""
	rules = [r for r in snapshot.member_rules if r.role == role]
	return [r for r in rules if not r.when or evaluate(r.when, variables, r.id)]


def _rule_for(snapshot: SeriesSnapshot, role: str, variables: dict) -> MemberRule:
	"""Frame, sash and bar members are cut once, so the first matching rule wins."""
	rules = matching_rules(snapshot, role, variables)
	if not rules:
		raise RuleError(f"No member rule for role {role!r} in series {snapshot.code}")
	return rules[0]


def sash_nodes(cells: list[Cell]) -> dict[str, dict]:
	"""Design node of every sash by panel id, numbered in cell order exactly as cut_members numbers them."""
	sashes = [c.node for c in cells if c.node["type"] == "sash"]
	return {f"{FRAME_PANEL}-S{i}": node for i, node in enumerate(sashes, 1)}
