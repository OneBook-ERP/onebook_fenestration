"""1D cutting optimizer: first-fit-decreasing with best fit, kerf, rest and wastage. Pure Python."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Piece:
	length: float
	label: str


@dataclass(frozen=True)
class BarPlan:
	bar_length: float
	pieces: tuple[Piece, ...]
	used_mm: float
	remainder_mm: float
	is_rest: bool


@dataclass
class CuttingResult:
	bars: list[BarPlan]
	unplaced: list[Piece]


def optimize(pieces: list[Piece], bar_lengths: list[float], kerf: float = 10.0, min_rest: float = 500.0) -> CuttingResult:
	lengths = sorted(set(bar_lengths))
	longest = lengths[-1] if lengths else 0.0
	unplaced: list[Piece] = []
	open_bars: list[list[Piece]] = []
	for piece in sorted(pieces, key=lambda p: (-p.length, p.label)):
		if not lengths or piece.length + kerf > longest:
			unplaced.append(piece)
			continue
		target = _best_fit(open_bars, piece, longest, kerf)
		if target is None:
			open_bars.append([piece])
		else:
			target.append(piece)
	return CuttingResult([_plan(bar, lengths, kerf, min_rest) for bar in open_bars], unplaced)


def wastage(result: CuttingResult, kg_per_m: float) -> dict:
	bars: dict[float, int] = {}
	for bar in result.bars:
		bars[bar.bar_length] = bars.get(bar.bar_length, 0) + 1
	bar_mm = sum(b.bar_length for b in result.bars)
	kerf_mm = sum(b.used_mm - sum(p.length for p in b.pieces) for b in result.bars)
	cut_mm = sum(b.used_mm for b in result.bars) - kerf_mm
	rest_mm = sum(b.remainder_mm for b in result.bars if b.is_rest)
	scrap_mm = sum(b.remainder_mm for b in result.bars if not b.is_rest)
	waste_mm = scrap_mm + kerf_mm
	return {
		"bars": bars,
		"bar_count": len(result.bars),
		"pieces": sum(len(b.pieces) for b in result.bars),
		"bar_mm": round(bar_mm, 3),
		"cut_mm": round(cut_mm, 3),
		"kerf_mm": round(kerf_mm, 3),
		"rest_mm": round(rest_mm, 3),
		"waste_mm": round(waste_mm, 3),
		"kg_bars": round(bar_mm / 1000 * kg_per_m, 3),
		"kg_used": round(cut_mm / 1000 * kg_per_m, 3),
		"waste_pct_incl_rest": _pct(waste_mm + rest_mm, bar_mm),
		"waste_pct_excl_rest": _pct(waste_mm, bar_mm),
		"kg_per_m": kg_per_m,
	}


def _pct(part: float, whole: float) -> float:
	return round(part / whole * 100, 2) if whole else 0.0


def _best_fit(open_bars: list[list[Piece]], piece: Piece, bar_length: float, kerf: float) -> list[Piece] | None:
	best, best_remainder = None, None
	for bar in open_bars:
		remainder = bar_length - _used(bar, kerf) - piece.length - kerf
		if remainder >= 0 and (best_remainder is None or remainder < best_remainder):
			best, best_remainder = bar, remainder
	return best


def _used(bar: list[Piece], kerf: float) -> float:
	return sum(p.length for p in bar) + kerf * len(bar)


def _plan(bar: list[Piece], lengths: list[float], kerf: float, min_rest: float) -> BarPlan:
	used = round(_used(bar, kerf), 3)
	bar_length = next(length for length in lengths if length >= used)
	remainder = round(bar_length - used, 3)
	return BarPlan(bar_length, tuple(bar), used, remainder, remainder >= min_rest)
