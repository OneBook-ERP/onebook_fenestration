"""Members cut per side of a glass pane: glazing beads around fixed panes, glass adaptors around sash panes.

Rule variables: series constants and deductions, then `opening_w` / `opening_h` (glass size + 2 x `glass_clearance`),
`position` (B/T/L/R), `glass_t` (overall thickness) and `glass` (code). Every rule whose `when` holds cuts a member.
"""

import re

from onebook_fenestration.engine.formula import evaluate_number
from onebook_fenestration.engine.layout import Cell
from onebook_fenestration.engine.members import FRAME_PANEL, matching_rules, resolve_override
from onebook_fenestration.engine.section_config import (
	detect_design_context,
	match_bead_gasket_rule,
	match_glass_glazing_rule,
	match_global_glazing_rule,
	resolve_glazing_by_width,
)
from onebook_fenestration.engine.types import CutMember, GlassPane, Issue, SeriesSnapshot

BEAD, ADAPTOR = "bead", "glass_adaptor"
_MM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE)


def frame_context(
	design: dict | None, snapshot: SeriesSnapshot, members: list[CutMember] | None = None
) -> dict:
	"""Resolve selected frame profile code, face width, frame depth (thickness), and frame configuration."""
	design = design if isinstance(design, dict) else {}
	frame_code = design.get("frameProfileId")
	frame_profile = resolve_override(
		design, snapshot, frame_code if isinstance(frame_code, str) else None, "frame", FRAME_PANEL
	)
	if not frame_profile and members:
		frame_member = next((m for m in members if m.role == "frame"), None)
		if frame_member:
			frame_profile = frame_member.profile
	if not frame_profile:
		frame_rule = next((r for r in snapshot.member_rules if r.role == "frame"), None)
		if frame_rule:
			frame_profile = frame_rule.profile
	spec = snapshot.profiles.get(frame_profile) if frame_profile else None
	frame_depth = float(spec.depth_mm) if (spec and spec.depth_mm > 0) else 0.0
	frame_face = float(spec.width_mm) if (spec and spec.width_mm > 0) else 0.0
	if frame_depth <= 0 and spec and spec.name:
		matches = [float(m) for m in _MM_RE.findall(spec.name)]
		if matches:
			frame_depth = matches[0]
			if frame_face <= 0 and len(matches) > 1:
				frame_face = matches[1]
	if frame_depth <= 0:
		frame_depth = float(snapshot.constants.get("frame_depth", 0.0))
	if frame_face <= 0:
		frame_face = float(snapshot.constants.get("frame_face", 0.0))
	return {
		"frame_profile": frame_profile or "",
		"frame_depth": frame_depth,
		"frame_face": frame_face,
		"frame_config": design.get("frameConfig") or "4-side",
	}


def glass_members(
	panes: list[GlassPane],
	snapshot: SeriesSnapshot,
	design: dict | None = None,
	cells: list[Cell] | None = None,
	members: list[CutMember] | None = None,
) -> tuple[list[CutMember], list[Issue]]:
	"""Bead / adaptor members for every pane, plus a warning for each fixed pane no bead rule applied to.

	Explicit design/pane profile overrides are respected both when series rules exist and when a series
	has no bead / adaptor rule configured.
	"""
	design = design if isinstance(design, dict) else {}
	roles = {rule.role for rule in snapshot.member_rules}
	cell_by_path = {cell.path: cell for cell in (cells or ())}
	bead_joint = design.get("beadJoint") if isinstance(design.get("beadJoint"), str) else ""

	out_members: list[CutMember] = []
	issues: list[Issue] = []
	base = {**snapshot.deductions, **snapshot.constants, **frame_context(design, snapshot, members)}
	for pane in panes:
		role = BEAD if pane.panel == FRAME_PANEL else ADAPTOR
		if role == BEAD and not pane.bead:
			continue
		cell = cell_by_path.get(pane.path)
		in_sash = pane.panel != FRAME_PANEL
		opening_type, application = detect_design_context(
			design, cell.node if cell else None, is_sash_pane=in_sash
		)
		# Only door sashes use a glazing bead; window sashes do not get sash beading.
		is_window_sash = in_sash and application != "door"
		if is_window_sash and (
			not pane.bead or (cell is not None and cell.node.get("sashConfig") == "window")
		):
			continue
		override = _glazing_override(pane, cell, role, design, snapshot)
		if not override and not is_window_sash:
			host = "sash" if in_sash else "frame"
			glass_spec = snapshot.glasses.get(pane.glass)
			glass_t = pane.thickness or (glass_spec.thickness_mm if glass_spec else 0.0)
			auto_res = resolve_glazing_by_width(
				getattr(snapshot, "global_glazing_auto", None),
				getattr(snapshot, "gasket_catalog", ()),
				glass_t,
				snapshot.code,
				host,
				application,
			)
			bead_code = ""
			if auto_res is not None:
				if auto_res.get("ok"):
					if auto_res.get("no_bead") or not auto_res.get("bead_profile"):
						continue
					bead_code = auto_res.get("bead_profile") or ""
				else:
					issues.append(
						Issue(
							"warn",
							"glazing_width_mismatch",
							f"{pane.panel}: {auto_res.get('message') or 'Glass does not fit configured bead/pocket widths.'}",
							pane.panel,
							hint="Adjust glass thickness or update Bead / Pocket Width (BW) in Bead & Gasket Config.",
							path=pane.path,
						)
					)
			if not bead_code and not (auto_res and auto_res.get("ok")):
				global_rule = match_global_glazing_rule(
					getattr(snapshot, "global_glazing_rules", ()),
					glass_t,
					host,
					application,
				)
				if global_rule is not None and (
					global_rule.get("no_bead") or not global_rule.get("bead_profile")
				):
					# Rule explicitly configures No Beading for this (application, host, thickness)
					continue
				bead_code = (global_rule or {}).get("bead_profile") or ""
			if not bead_code:
				glass_rule = match_glass_glazing_rule(
					glass_spec.glazing_rules if glass_spec else None, snapshot.code, host
				)
				bead_code = (glass_rule or {}).get("bead_profile") or ""
			if not bead_code and snapshot.section_config:
				rule = match_bead_gasket_rule(
					snapshot.section_config, opening_type, application, glass_t, host
				)
				bead_code = (rule or {}).get("bead_profile") or ""
			resolved = _resolve_bead_code(bead_code, snapshot)
			if resolved:
				override = resolved
		if role not in roles:
			if not override:
				continue
			cut = _override_pane_members(pane, cell, role, override, snapshot, bead_joint)
			out_members += [m for m in cut if m.length > 0]
			issues += [_non_positive(pane, m) for m in cut if m.length <= 0]
			continue
		cut = _pane_members(pane, role, base, snapshot, profile_override=override)
		if not cut and override:
			cut = _override_pane_members(pane, cell, role, override, snapshot, bead_joint)
		out_members += [m for m in cut if m.length > 0]
		issues += [_non_positive(pane, m) for m in cut if m.length <= 0]
		if role == BEAD and BEAD in roles and not cut:
			message = f"{pane.panel}: no glazing bead rule for {'steel sheet' if pane.material == 'steel' else 'glass ' + str(pane.glass)}"
			issues.append(Issue("warn", "no_glazing_bead", message, pane.panel, path=pane.path))
	return out_members, issues


def _resolve_bead_code(bead_code: str, snapshot: SeriesSnapshot) -> str:
	"""Resolve a global bead code (e.g. `CS4807`) against the active series's profile catalogue."""
	if not bead_code:
		return ""
	if bead_code in snapshot.profiles:
		return bead_code
	suffixed = f"{bead_code}-{snapshot.code}"
	if suffixed in snapshot.profiles:
		return suffixed
	base = bead_code.split("-")[0]
	if base in snapshot.profiles:
		return base
	base_suffixed = f"{base}-{snapshot.code}"
	if base_suffixed in snapshot.profiles:
		return base_suffixed
	return ""


def _glazing_override(
	pane: GlassPane,
	cell: Cell | None,
	role: str,
	design: dict,
	snapshot: SeriesSnapshot,
) -> str | None:
	node = cell.node if cell is not None else {}
	if role == BEAD:
		return (
			resolve_override(
				design,
				snapshot,
				node.get("beadProfileId"),
				f"{pane.path}:bead",
				"bead",
				design.get("beadProfileId"),
			)
			or None
		)
	return (
		resolve_override(
			design,
			snapshot,
			node.get("glassAdaptorProfileId"),
			f"{pane.path}:glass_adaptor",
			"glass_adaptor",
			design.get("glassAdaptorProfileId"),
		)
		or None
	)


def _opening_size(pane: GlassPane, cell: Cell | None, snapshot: SeriesSnapshot) -> tuple[float, float]:
	clearance = snapshot.constants.get("glass_clearance")
	if clearance:
		return pane.width + 2 * clearance, pane.height + 2 * clearance
	if cell is not None and pane.panel == FRAME_PANEL:
		c_l = _side_clearance(snapshot, cell, "L")
		c_r = _side_clearance(snapshot, cell, "R")
		c_b = _side_clearance(snapshot, cell, "B")
		c_t = _side_clearance(snapshot, cell, "T")
		return pane.width + c_l + c_r, pane.height + c_b + c_t
	return pane.width, pane.height


def _side_clearance(snapshot: SeriesSnapshot, cell: Cell, side: str) -> float:
	edge = cell.sides[side]
	glass_d = snapshot.deductions.get(f"fixed_glass_side_{edge}", 0.0)
	bar_d = snapshot.deductions.get(f"bar_end_{edge}", 0.0)
	return max(0.0, glass_d - bar_d)


def _override_pane_members(
	pane: GlassPane,
	cell: Cell | None,
	role: str,
	profile: str,
	snapshot: SeriesSnapshot,
	bead_joint: str,
) -> list[CutMember]:
	opening_w, opening_h = _opening_size(pane, cell, snapshot)
	if role == BEAD and bead_joint == "b":
		angles = (90, 90)
		bead_depth = float(snapshot.constants.get("bead_depth", 0.0))
		bt_len, lr_len = opening_w, opening_h - 2 * bead_depth
	else:
		angles = (45, 45)
		bt_len, lr_len = opening_w, opening_h
	return [
		CutMember(
			pane.panel,
			role,
			position,
			profile,
			float(round(bt_len if position in "BT" else lr_len, 1)),
			angles,
			pane.path,
		)
		for position in "BTLR"
	]


def _pane_members(
	pane: GlassPane,
	role: str,
	base: dict,
	snapshot: SeriesSnapshot,
	profile_override: str | None = None,
) -> list[CutMember]:
	clearance = 2 * snapshot.constants["glass_clearance"]
	pane_vars = {
		"opening_w": pane.width + clearance,
		"opening_h": pane.height + clearance,
		"glass_t": pane.thickness or snapshot.glasses[pane.glass].thickness_mm,
		"glass": "STEEL" if pane.material == "steel" else pane.glass,
	}
	members = []
	for position in "BTLR":
		variables = {**base, **pane_vars, "position": position}
		for rule in matching_rules(snapshot, role, variables):
			length = float(round(evaluate_number(rule.length, variables, rule.id), 1))
			members.append(
				CutMember(
					pane.panel,
					role,
					position,
					profile_override or rule.profile,
					length,
					rule.angles,
					pane.path,
				)
			)
	return members


def _non_positive(pane: GlassPane, member: CutMember) -> Issue:
	message = f"{pane.panel}: {member.role} {member.position} length is {member.length} mm"
	return Issue("error", "non_positive_size", message, pane.panel, path=pane.path)
