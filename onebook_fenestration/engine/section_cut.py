"""Cross-section through a design: the profiles and glass one straight cut line crosses, placed along the cut.

Coordinates follow `layout()`: x runs right from the frame's left outer edge, y runs up from its bottom outer edge.
Axis "h" (B-B) cuts horizontally at height `at`; pieces run left -> right and `start` / `end` are x.
Axis "v" (A-A) cuts vertically at x = `at`; pieces run bottom -> top and `start` / `end` are y.
`at` snaps to the centre of the cell it falls in (outside the frame: the nearest cell), so the cut never runs along a bar.

Pieces are placed with the deductions the cut list uses; glass sizes come from `compute()`. Each profile piece is
`widths[code]` wide (the profile's face width: its outline's extent along the cut, after the profile's section
rotation); `mirrored` marks pieces on the high side (R / T) of their opening, whose outline the drawing flips. Glass
pieces carry their glass spec's overall thickness. Pieces are listed in construction order: frame, then per crossed
cell its low-side sash and glass members, the glass, its high-side members, then the bar to the next cell, and the
far frame.
"""

from dataclasses import dataclass, field

from onebook_fenestration.engine.engine import compute
from onebook_fenestration.engine.layout import Bar, Cell, is_real, layout
from onebook_fenestration.engine.members import FRAME_PANEL
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
	design: dict, snapshot: SeriesSnapshot, axis: str, at: float | None = None, widths: dict[str, float] | None = None
) -> CrossSection:
	if axis not in AXES:
		raise DesignError(f"cut axis must be 'h' or 'v', got {axis!r}")
	if at is not None and not is_real(at):
		raise DesignError(f"cut position must be a number, got {at!r}")
	result = compute(design, snapshot)
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
		for m in result.members:
			self.members.setdefault((m.role, m.path, m.position), []).append(m)
		self.pieces: list[SectionPiece] = []
		self.dims: list[Dim] = []
		self.missing: dict[str, float] = {}

	def run(self, cells: list[Cell], at: float | None) -> CrossSection:
		at = self._snap(cells, at)
		crossed = sorted((c for c in cells if self._contains(c, at)), key=lambda c: getattr(c, self.along))
		self.dims.append(Dim(0, self.length, _label(self.length), "overall"))
		self._place_profiles("frame", FRAME_PANEL, self.low, 0)
		for i, cell in enumerate(crossed):
			lo, hi = self._span(cell)
			if i:
				self._place_bar(lo, at)
			self.dims.append(Dim(lo, hi, _label(hi - lo), "cells"))
			self._place_cell(cell, lo, hi)
		self._place_profiles("frame", FRAME_PANEL, self.high, self.length)
		return CrossSection(self.axis, at, self.length, self.pieces, self.dims, self._issues())

	def _snap(self, cells: list[Cell], at: float | None) -> float:
		"""Centre of the cell `at` falls in; containing cells beat touching ones, and ties go to the first cell."""

		def distance(cell):
			lo, hi = self._perp_span(cell)
			return -1 if lo <= at < hi else min(abs(at - lo), abs(at - hi))

		cell = cells[0] if at is None else min(cells, key=distance)
		lo, hi = self._perp_span(cell)
		return (lo + hi) / 2

	def _place_cell(self, cell: Cell, lo: float, hi: float):
		kind = cell.node["type"]
		if kind == "sash":
			sash_lo = lo + self._deduction("sash_side", cell, self.low)
			sash_hi = hi - self._deduction("sash_side", cell, self.high)
			self._place_profiles("sash", cell.path, self.low, sash_lo)
			inset = self.snapshot.deductions["sash_glass"]
			self._place_glass(cell, sash_lo + inset, sash_hi - inset)
			self._place_profiles("sash", cell.path, self.high, sash_hi)
		elif kind == "fixed":
			self._place_glass(
				cell, lo + self._deduction("fixed_glass_side", cell, self.low), hi - self._deduction("fixed_glass_side", cell, self.high)
			)

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
		thickness = spec.thickness_mm if spec else 0.0
		self.pieces.append(
			SectionPiece("glass", pane.glass, "glass", pane.panel, _mm(start), _mm(start + size), thickness=thickness)
		)
		self.dims.append(Dim(_mm(start), _mm(start + size), _label(size), "glass"))
		for role in GLASS_ROLES:
			self._place_profiles(role, cell.path, self.high, start + size + clearance_high, cell=cell)

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
			bead_code = (
				cell.node.get("beadProfileId")
				or (self.design.get("beadProfileId") if isinstance(self.design, dict) else None)
				or ((self.design.get("profiles") or {}).get("bead") if isinstance(self.design, dict) else None)
				or (getattr(self.snapshot, "role_defaults", {}).get("bead"))
			)
			if bead_code:
				members = [CutMember(cell.path, "bead", side, bead_code, 0.0, (90.0, 90.0), cell.path)]
		for member in members:
			width = self._width(member)
			if side == self.low:
				self._add_profile(member, member.panel, edge, edge + width, False)
			else:
				self._add_profile(member, member.panel, edge - width, edge, True)

	def _add_profile(self, member: CutMember, panel: str, start: float, end: float, mirrored: bool):
		start, end = _mm(start), _mm(end)
		self.pieces.append(SectionPiece("profile", member.profile, member.role, panel, start, end, mirrored))
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
