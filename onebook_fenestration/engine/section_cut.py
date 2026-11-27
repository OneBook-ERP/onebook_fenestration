"""Cross-section through a design: the profiles and glass one straight cut line crosses, placed along the cut.

Coordinates follow `layout()`: x runs right from the frame's left outer edge, y runs up from its bottom outer edge.
Axis "h" (B-B) cuts horizontally at height `at`; pieces run left -> right and `start` / `end` are x.
Axis "v" (A-A) cuts vertically at x = `at`; pieces run bottom -> top and `start` / `end` are y.
`at` snaps between adjacent perpendicular cell boundaries (outside the frame: the nearest band), so the cut never runs along a bar.

Pieces are placed with the deductions the cut list uses; glass sizes come from `compute()`. Each profile piece is
`widths[code]` wide (the profile's face width: its outline's extent along the cut, after the profile's section
rotation); `mirrored` marks pieces on the high side (R / T) of their opening, whose outline the drawing flips. Glass
pieces carry their glass spec's overall thickness. Pieces are listed in construction order: frame, then per crossed
cell its low-side sash and glass members, the glass, its high-side members, then the bar to the next cell, and the
far frame.
"""

from dataclasses import dataclass, field
from math import sqrt

from onebook_fenestration.engine.engine import compute
from onebook_fenestration.engine.layout import Bar, Cell, is_real, layout
from onebook_fenestration.engine.members import FRAME_PANEL
from onebook_fenestration.engine.section_config import (
	detect_design_context,
	resolve_pane_glazing_gaskets,
	resolve_piece_config_placement,
	resolve_template_glass_domain,
	resolve_template_placement,
)
from onebook_fenestration.engine.types import CutMember, DesignError, EngineResult, GlassPane, Issue, SeriesSnapshot

# axis -> (along coordinate, along size, low side, high side, bar kind crossed, perpendicular coordinate, size)
AXES = {"h": ("x", "w", "L", "R", "mullion", "y", "h"), "v": ("y", "h", "B", "T", "transom", "x", "w")}
GLASS_ROLES = ("glass_adaptor", "bead")


@dataclass(frozen=True)
class SectionPiece:
	kind: str
	code: str
	role: str
	panel: str
	start: float
	end: float
	mirrored: bool = False
	# glass only: overall unit thickness (mm) of the pane's glass spec; 0 for profiles
	thickness: float = 0.0
	# Physical owner; fixed panes share panel F1.
	path: str = ""
	blades: int = 0
	blade_width: float = 60.0
	opening_height: float = 0.0
	cutout: dict | None = None
	material: str = "glass"
	config_placement: dict | None = None


@dataclass(frozen=True)
class Dim:
	start: float
	end: float
	label: str
	chain: str = ""


@dataclass
class CrossSection:
	axis: str
	at: float
	length: float
	pieces: list[SectionPiece]
	dims: list[Dim]
	issues: list[Issue] = field(default_factory=list)


def cross_section(
	design: dict,
	snapshot: SeriesSnapshot,
	axis: str,
	at: float | None = None,
	widths: dict[str, float] | None = None,
	result: EngineResult | None = None,
) -> CrossSection:
	if axis not in AXES:
		raise DesignError(f"cut axis must be 'h' or 'v', got {axis!r}")
	if at is not None and not is_real(at):
		raise DesignError(f"cut position must be a number, got {at!r}")
	result = result or compute(design, snapshot)
	cells, bars = layout(design)
	return _Cut(design, snapshot, axis, result, bars, widths or {}).run(cells, at)


class _Cut:
	def __init__(self, design, snapshot, axis, result: EngineResult, bars: list[Bar], widths: dict[str, float]):
		self.design = design
		self.snapshot, self.axis, self.bars, self.widths = snapshot, axis, bars, widths
		self.along, self.size, self.low, self.high, self.bar_kind, self.perp, self.perp_size = AXES[axis]
		self.length = design["width"] if axis == "h" else design["height"]
		self.panes = {pane.path: pane for pane in result.glass}
		self.members: dict[tuple[str, str, str], list[CutMember]] = {}
		self.has_sash = False
		self.role_profiles: dict[str, str] = {}
		self.cell_sash_profiles: dict[str, str] = {}
		for m in result.members:
			self.members.setdefault((m.role, m.path, m.position), []).append(m)
			if m.role == "sash":
				self.has_sash = True
				if m.path and m.profile:
					self.cell_sash_profiles.setdefault(m.path, m.profile)
			if m.profile and m.role in ("frame", "sash", "mullion", "transom"):
				self.role_profiles.setdefault(m.role, m.profile)
		self.has_door_sash = self._design_has_door_sash(design.get("root") if isinstance(design, dict) else None)
		self.pieces: list[SectionPiece] = []
		self.dims: list[Dim] = []
		self.missing: dict[str, float] = {}

	def _design_has_door_sash(self, node: dict | None) -> bool:
		if not isinstance(node, dict):
			return False
		if str(node.get("sashConfig") or "").strip().lower() == "door":
			return True
		for child in node.get("children") or ():
			if self._design_has_door_sash(child):
				return True
		return False

	def _active_profiles(self, cell: Cell | None, role: str = "", code: str = "") -> dict[str, str]:
		profiles = dict(self.role_profiles)
		if cell is not None:
			sash_code = self.cell_sash_profiles.get(cell.path)
			if sash_code:
				profiles["sash"] = sash_code
			elif cell.node.get("type") != "sash":
				profiles.pop("sash", None)
		if role in ("frame", "sash", "mullion", "transom") and code:
			profiles[role] = code
		return profiles

	def run(self, cells: list[Cell], at: float | None) -> CrossSection:
		at = self._snap(cells, at)
		self.at = at
		crossed = sorted((c for c in cells if self._contains(c, at)), key=lambda c: getattr(c, self.along))
		self.dims.append(Dim(0, self.length, _label(self.length), "overall"))
		self._place_profiles("frame", FRAME_PANEL, self.low, 0)
		for i, cell in enumerate(crossed):
			lo, hi = self._span(cell)
			if i and not (self.design.get("isSliding") and self.bar_kind == "mullion"):
				self._place_bar(lo, at)
			self.dims.append(Dim(lo, hi, _label(hi - lo), "cells"))
			self._place_cell(cell, lo, hi)
		self._place_profiles("frame", FRAME_PANEL, self.high, self.length)
		return CrossSection(self.axis, at, self.length, self.pieces, self.dims, self._issues())

	def _snap(self, cells: list[Cell], at: float | None) -> float:
		"""Snap between perpendicular cell boundaries so nested panes remain reachable."""
		if at is None:
			lo, hi = self._perp_span(cells[0])
			at = (lo + hi) / 2
		edges = sorted({edge for cell in cells for edge in self._perp_span(cell)})
		bands = list(zip(edges, edges[1:]))
		lo, hi = min(bands, key=lambda band: -1 if band[0] <= at < band[1] else min(abs(at - band[0]), abs(at - band[1])))
		return (lo + hi) / 2

	def _place_cell(self, cell: Cell, lo: float, hi: float):
		kind = cell.node["type"]
		if kind == "sash":
			sash_lo = lo + self._deduction("sash_side", cell, self.low)
			sash_hi = hi - self._deduction("sash_side", cell, self.high)
			self._place_profiles("sash", cell.path, self.low, sash_lo, cell=cell)
			inset = self.snapshot.deductions["sash_glass"]
			self._place_glass(cell, sash_lo + inset, sash_hi - inset)
			self._place_profiles("sash", cell.path, self.high, sash_hi, cell=cell)
		elif kind == "fixed":
			self._place_glass(
				cell, lo + self._deduction("fixed_glass_side", cell, self.low), hi - self._deduction("fixed_glass_side", cell, self.high)
			)

		elif kind == "louver":
			start = lo + self._deduction("bar_end", cell, self.low)
			end = hi - self._deduction("bar_end", cell, self.high)
			height = cell.h - self._deduction("bar_end", cell, "B") - self._deduction("bar_end", cell, "T")
			width = cell.node.get("bladeWidth", 60.0)
			if not is_real(width) or width <= 0:
				width = 60.0
			material = cell.node.get("bladeMaterial", "metal")
			spec = self.snapshot.glasses.get(cell.node.get("glass")) if material == "glass" else None
			thickness = spec.thickness_mm if spec else 4.0
			if end > start and height > 0:
				self.pieces.append(SectionPiece(
					"louver", "Louver", "louver", cell.path, _mm(start), _mm(end),
					path=cell.path, blades=cell.node.get("blades", 7), opening_height=_mm(height), blade_width=width, thickness=thickness,
				))

	def _place_glass(self, cell: Cell, lo: float, hi: float):
		"""The pane centred in its opening, with its beads / adaptors from the rebate edge (glass edge + clearance)."""
		pane: GlassPane | None = self.panes.get(cell.path)
		if pane is None:
			return
		size = pane.width if self.axis == "h" else pane.height
		start = (lo + hi - size) / 2
		clearance = self.snapshot.constants.get("glass_clearance")
		if clearance is None or clearance == 0:
			clearance_low = max(
				0.0,
				self._deduction("fixed_glass_side", cell, self.low) - self._deduction("bar_end", cell, self.low)
				if cell.node.get("type") == "fixed"
				else 0.0,
			)
			clearance_high = max(
				0.0,
				self._deduction("fixed_glass_side", cell, self.high) - self._deduction("bar_end", cell, self.high)
				if cell.node.get("type") == "fixed"
				else 0.0,
			)
		else:
			clearance_low = clearance
			clearance_high = clearance
		for role in GLASS_ROLES:
			self._place_profiles(role, cell.path, self.low, start - clearance_low, cell=cell)
		spec = self.snapshot.glasses.get(pane.glass)
		thickness = pane.thickness or (spec.thickness_mm if spec else 0.0)
		in_sash = pane.panel != FRAME_PANEL
		glass_cfg = self._config_placement("glass", cell=cell, glass_t=thickness, in_sash=in_sash)
		opening_type, application = detect_design_context(self.design, cell.node if cell else None, is_sash_pane=in_sash)
		gaskets_meta = resolve_pane_glazing_gaskets(
			self.snapshot,
			thickness,
			"sash" if in_sash else "frame",
			opening_type,
			application,
			pane.glass,
		)
		if gaskets_meta:
			glass_cfg = {**(glass_cfg or {"source": "glazing_gaskets_only"}), "glazing_gaskets": gaskets_meta}
		self.pieces.append(
			SectionPiece(
				"glass",
				"Steel" if pane.material == "steel" else pane.glass,
				"glass",
				pane.panel,
				_mm(start),
				_mm(start + size),
				thickness=thickness,
				path=cell.path,
				cutout=self._glass_cutout(cell, pane, start),
				material=pane.material,
				config_placement=glass_cfg,
			)
		)
		self.dims.append(Dim(_mm(start), _mm(start + size), _label(size), "glass"))
		for role in GLASS_ROLES:
			self._place_profiles(role, cell.path, self.high, start + size + clearance_high, cell=cell)

	def _glass_cutout(self, cell, pane, start):
		cut = pane.cutout
		if not cut:
			return None
		# Same pane origin as the complete 3D assembly, including asymmetric deductions.
		if cell.node["type"] == "sash":
			x = cell.x + self._deduction("sash_side", cell, "L") + self.snapshot.deductions["sash_glass"]
			y = cell.y + self._deduction("sash_side", cell, "B") + self.snapshot.deductions["sash_glass"]
		else:
			x = cell.x + self._deduction("fixed_glass_side", cell, "L")
			y = cell.y + self._deduction("fixed_glass_side", cell, "B")
		perp = y + pane.height - cut["centerY"] if self.axis == "h" else x + cut["centerX"]
		distance = abs(self.at - perp)
		radius = cut["diameter"] / 2
		if distance >= radius:
			return None
		half_chord = sqrt(radius * radius - distance * distance)
		center = start + (cut["centerX"] if self.axis == "h" else pane.height - cut["centerY"])
		return {"start": _mm(center - half_chord), "end": _mm(center + half_chord), "diameter": cut["diameter"]}

	def _place_bar(self, edge: float, at: float):
		bar = next(
			(
				b
				for b in self.bars
				if b.kind == self.bar_kind and abs(b.at - edge) < 1e-6 and b.start <= at < b.start + b.length_span
			),
			None,
		)
		if bar is None:  # adjacent crossed cells always share a bar; guard against a malformed layout
			return
		for member in self.members.get((bar.kind, bar.id, "H" if bar.kind == "mullion" else "W"), []):
			width = self._width(member)
			self._add_profile(member, bar.id, edge - width / 2, edge + width / 2, False)

	def _place_profiles(self, role: str, path: str, side: str, edge: float, cell: Cell | None = None):
		"""Members of `role` on `side`, their outer face at `edge`: low side grows up the cut, high side down."""
		members = self.members.get((role, path, side), [])
		if not members and role == "bead" and cell and cell.node.get("type") == "fixed" and cell.node.get("bead", True) is not False:
			profiles = self.design.get("profiles") if isinstance(self.design, dict) and isinstance(self.design.get("profiles"), dict) else {}
			bead_code = (
				cell.node.get("beadProfileId")
				or profiles.get(f"{cell.path}:bead")
				or profiles.get("bead")
				or (self.design.get("beadProfileId") if isinstance(self.design, dict) else None)
				or (getattr(self.snapshot, "role_defaults", {}).get("bead"))
			)
			if bead_code:
				members = [CutMember(cell.path, "bead", side, bead_code, 0.0, (90.0, 90.0), cell.path)]
		for member in members:
			width = self._width(member)
			if side == self.low:
				self._add_profile(member, member.panel, edge, edge + width, False, cell=cell)
			else:
				self._add_profile(member, member.panel, edge - width, edge, True, cell=cell)

	def _config_placement(
		self,
		role: str,
		cell: Cell | None = None,
		glass_t: float = 0.0,
		in_sash: bool = False,
		mirrored: bool = False,
		code: str = "",
		adjacent: str = "",
	) -> dict | None:
		if not self.snapshot.section_config:
			return None
		node = cell.node if cell is not None else None
		opening_type, application = detect_design_context(self.design, node, is_sash_pane=in_sash)
		if cell is None and self.has_door_sash and application == "window":
			application = "door"
		active_profiles = self._active_profiles(cell, role=role, code=code)
		if role == "glass":
			low_side = str(cell.sides.get(self.low) or "") if cell is not None else ""
			high_side = str(cell.sides.get(self.high) or "") if cell is not None else ""
			glass_domain = resolve_template_glass_domain(
				self.snapshot.section_config,
				opening_type,
				application,
				self.axis,
				has_mullion=bool(self.bars),
				low_side=low_side,
				high_side=high_side,
				active_profiles=active_profiles,
			)
			if glass_domain is not None:
				return glass_domain
		tpl_cfg = resolve_template_placement(
			self.snapshot.section_config,
			opening_type,
			application,
			self.axis,
			role,
			code=code,
			mirrored=mirrored,
			has_mullion=bool(self.bars),
			adjacent=adjacent,
			design_has_sash=self.has_sash,
			active_profiles=active_profiles,
		)
		if tpl_cfg is not None:
			return tpl_cfg
		return resolve_piece_config_placement(
			self.snapshot.section_config,
			opening_type,
			application,
			role,
			glass_t=glass_t,
			in_sash=in_sash,
			mirrored=mirrored,
		)

	def _add_profile(self, member: CutMember, panel: str, start: float, end: float, mirrored: bool, cell: Cell | None = None):
		start, end = _mm(start), _mm(end)
		pane = self.panes.get(cell.path) if cell is not None else None
		glass_t = 0.0
		if pane is not None:
			spec = self.snapshot.glasses.get(pane.glass)
			glass_t = pane.thickness or (spec.thickness_mm if spec else 0.0)
		in_sash = bool(panel != FRAME_PANEL) or (cell is not None and cell.node.get("type") == "sash")
		adjacent = ""
		if cell is not None and member.position in cell.sides:
			adjacent = str(cell.sides.get(member.position) or "")
		cfg = self._config_placement(
			member.role,
			cell=cell,
			glass_t=glass_t,
			in_sash=in_sash,
			mirrored=mirrored,
			code=member.profile,
			adjacent=adjacent,
		)
		self.pieces.append(SectionPiece("profile", member.profile, member.role, panel, start, end, mirrored, path=member.path, config_placement=cfg))
		self.dims.append(Dim(start, end, _label(end - start), "profiles"))

	def _width(self, member: CutMember) -> float:
		width = self.widths.get(member.profile)
		if width and width > 0:
			return width
		width = self._fallback_width(member.role)
		self.missing.setdefault(member.profile, width)
		return width

	def _fallback_width(self, role: str) -> float:
		d, c = self.snapshot.deductions, self.snapshot.constants
		if role == "frame":
			return d["bar_end_frame"]
		if role in ("mullion", "transom"):
			return 2 * d[f"bar_end_{role}"]
		if role == "sash":
			return d["sash_glass"]
		return c.get("bead_depth") or c.get("glass_clearance", 0)

	def _issues(self) -> list[Issue]:
		return [
			Issue("warn", "no_section_width", f"Profile {code} has no section width; drawn {_label(width)} mm wide from the series deductions")
			for code, width in sorted(self.missing.items())
		]

	def _deduction(self, prefix: str, cell: Cell, side: str) -> float:
		return self.snapshot.deductions[f"{prefix}_{cell.sides[side]}"]

	def _contains(self, cell: Cell, at: float) -> bool:
		lo, hi = self._perp_span(cell)
		return lo <= at < hi

	def _span(self, cell: Cell) -> tuple[float, float]:
		lo = getattr(cell, self.along)
		return lo, lo + getattr(cell, self.size)

	def _perp_span(self, cell: Cell) -> tuple[float, float]:
		lo = getattr(cell, self.perp)
		return lo, lo + getattr(cell, self.perp_size)


def _mm(value: float) -> float:
	return round(value, 2)


def _label(value: float) -> str:
	return f"{round(value, 1):.1f}".removesuffix(".0")
