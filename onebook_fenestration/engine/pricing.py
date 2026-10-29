"""Price a computed window as an ordered chain of cost heads."""

from dataclasses import dataclass, field

from onebook_fenestration.engine.formula import evaluate, evaluate_number
from onebook_fenestration.engine.types import EngineResult, Issue, RuleError, SeriesSnapshot

SQFT_PER_M2 = 10.764
_RESERVED = frozenset(
	(
		"profile_cost",
		"hardware_cost",
		"gasket_cost",
		"glass_cost",
		"area_sqft",
		"area_m2",
		"window_kg",
		"visible_perimeter_sqft",
		"total_perimeter_sqft",
		"finish_type",
		"finish_surcharge_pct",
	)
)
PERIMETER_KINDS = {"Per Visible Perimeter Sqft": "visible", "Per Total Perimeter Sqft": "total"}


@dataclass(frozen=True)
class CostHead:
	key: str
	label: str
	calc: str
	rate: float = 0
	formula: str = ""
	base: str = ""
	condition: str = ""
	include_in_total: bool = True


@dataclass(frozen=True)
class PricingInput:
	heads: tuple[CostHead, ...]
	profile_rates: dict[str, float]
	item_rates: dict[str, float]
	glass_rates: dict[str, float]
	finish_type: str
	missing: tuple[str, ...] = ()
	profile_perimeters: dict[str, tuple[float, float]] = field(default_factory=dict)
	"""Live (visible_mm, total_mm) per profile code; overrides the snapshot's values."""
	finish_surcharge_pct: float = 0


@dataclass(frozen=True)
class PriceLine:
	key: str
	label: str
	amount: float
	include_in_total: bool = True


@dataclass
class PriceBreakdown:
	lines: list[PriceLine]
	unit_price: float
	rate_per_sqft: float
	variables: dict
	issues: list[Issue] = field(default_factory=list)


def price(result: EngineResult, snapshot: SeriesSnapshot, pricing: PricingInput) -> PriceBreakdown:
	perimeters = _perimeters(result, snapshot, pricing)
	variables = _variables(result, snapshot, pricing, perimeters)
	lines = []
	seen = set()
	issues = [Issue("warn", "no_rate", f"{name}: no rate", path="") for name in pricing.missing]
	warned = set()
	for head in pricing.heads:
		if head.key in _RESERVED or head.key in seen:
			raise RuleError(f"{head.key}: duplicate or reserved cost head key")
		seen.add(head.key)
		active = not head.condition or bool(evaluate(head.condition, variables, head.key))
		amount = round(_amount(head, variables, active), 2)
		variables[head.key] = amount
		lines.append(PriceLine(head.key, head.label, amount, head.include_in_total))
		if active and head.rate > 0 and head.calc in PERIMETER_KINDS:
			issues += _perimeter_warnings(head, perimeters, warned)
	unit_price = round(sum(line.amount for line in lines if line.include_in_total), 2)
	rate_per_sqft = round(unit_price / result.area_sqft, 2) if result.area_sqft else 0.0
	return PriceBreakdown(lines, unit_price, rate_per_sqft, variables, issues)


def _perimeters(result: EngineResult, snapshot: SeriesSnapshot, pricing: PricingInput) -> dict[str, dict]:
	"""Perimeter (mm) by kind for each profile the design uses; live values win over the snapshot."""
	out = {}
	for code in sorted({m.profile for m in result.members}):
		spec = snapshot.profiles[code]
		visible, total = pricing.profile_perimeters.get(code, (spec.visible_perimeter_mm, spec.total_perimeter_mm))
		out[code] = {"visible": visible or 0, "total": total or 0}
	return out


def _perimeter_warnings(head: CostHead, perimeters: dict, warned: set) -> list[Issue]:
	kind = PERIMETER_KINDS[head.calc]
	issues = []
	for code, values in perimeters.items():
		if values[kind] or (code, kind) in warned:
			continue
		warned.add((code, kind))
		issues.append(Issue("warn", "no_perimeter", f"{code}: no {kind} perimeter — {head.label} under-priced"))
	return issues


def _variables(result: EngineResult, snapshot: SeriesSnapshot, pricing: PricingInput, perimeters: dict) -> dict:
	profile_cost = sum(
		m.length / 1000 * snapshot.profiles[m.profile].kg_per_m * pricing.profile_rates.get(m.profile, 0) for m in result.members
	)
	hardware_cost = sum(b.qty * pricing.item_rates.get(b.item, 0) for b in result.bom if b.group != "Gasket")
	gasket_cost = sum((b.length or 0) / 1000 * pricing.item_rates.get(b.item, 0) for b in result.bom if b.group == "Gasket")
	glass_cost = sum(g.width * g.height / 1e6 * pricing.glass_rates.get(g.glass, 0) for g in result.glass)
	return {
		"profile_cost": profile_cost,
		"hardware_cost": hardware_cost,
		"gasket_cost": gasket_cost,
		"glass_cost": glass_cost,
		"area_sqft": result.area_sqft,
		"area_m2": result.area_m2,
		"window_kg": result.window_kg,
		"visible_perimeter_sqft": _perimeter_sqft(result, perimeters, "visible"),
		"total_perimeter_sqft": _perimeter_sqft(result, perimeters, "total"),
		"finish_type": pricing.finish_type,
		"finish_surcharge_pct": pricing.finish_surcharge_pct,
	}


def _perimeter_sqft(result: EngineResult, perimeters: dict, kind: str) -> float:
	m2 = sum(m.length / 1000 * perimeters[m.profile][kind] / 1000 for m in result.members)
	return m2 * SQFT_PER_M2


def _amount(head: CostHead, variables: dict, active: bool) -> float:
	base = _base(head, variables) if head.calc == "Percentage" else 0.0
	if not active:
		return 0.0
	if head.calc == "Formula":
		return evaluate_number(head.formula, variables, head.key)
	if head.calc == "Percentage":
		return head.rate / 100 * base
	if head.calc == "Per Area Sqft":
		return head.rate * variables["area_sqft"]
	if head.calc == "Per Visible Perimeter Sqft":
		return head.rate * variables["visible_perimeter_sqft"]
	if head.calc == "Per Total Perimeter Sqft":
		return head.rate * variables["total_perimeter_sqft"]
	if head.calc == "Fixed":
		return float(head.rate)
	raise RuleError(f"{head.key}: unknown calculation {head.calc!r}")


def _base(head: CostHead, variables: dict) -> float:
	total = 0.0
	for key in (k.strip() for k in head.base.split(",") if k.strip()):
		if key not in variables or key in _RESERVED:
			raise RuleError(f"{head.key}: base '{key}' is not an earlier cost head")
		total += variables[key]
	return total

