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
	)
)


@dataclass(frozen=True)
class CostHead:
	key: str
	label: str
	calc: str
	rate: float = 0
	formula: str = ""
	base: str = ""
	condition: str = ""


@dataclass(frozen=True)
class PricingInput:
	heads: tuple[CostHead, ...]
	profile_rates: dict[str, float]
	item_rates: dict[str, float]
	glass_rates: dict[str, float]
	finish_type: str
	missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class PriceLine:
	key: str
	label: str
	amount: float


@dataclass
class PriceBreakdown:
	lines: list[PriceLine]
	unit_price: float
	rate_per_sqft: float
	variables: dict
	issues: list[Issue] = field(default_factory=list)


def price(result: EngineResult, snapshot: SeriesSnapshot, pricing: PricingInput) -> PriceBreakdown:
	variables = _variables(result, snapshot, pricing)
	lines = []
	seen = set()
	for head in pricing.heads:
		if head.key in _RESERVED or head.key in seen:
			raise RuleError(f"{head.key}: duplicate or reserved cost head key")
		seen.add(head.key)
		amount = round(_amount(head, variables), 2)
		variables[head.key] = amount
		lines.append(PriceLine(head.key, head.label, amount))
	unit_price = round(sum(line.amount for line in lines), 2)
	rate_per_sqft = round(unit_price / result.area_sqft, 2) if result.area_sqft else 0.0
	issues = [Issue("warn", "no_rate", f"{name}: no rate", path="") for name in pricing.missing]
	return PriceBreakdown(lines, unit_price, rate_per_sqft, variables, issues)


def _variables(result: EngineResult, snapshot: SeriesSnapshot, pricing: PricingInput) -> dict:
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
		"visible_perimeter_sqft": _perimeter_sqft(result, snapshot, "visible_perimeter_mm"),
		"total_perimeter_sqft": _perimeter_sqft(result, snapshot, "total_perimeter_mm"),
		"finish_type": pricing.finish_type,
	}


def _perimeter_sqft(result: EngineResult, snapshot: SeriesSnapshot, attr: str) -> float:
	m2 = sum(m.length / 1000 * getattr(snapshot.profiles[m.profile], attr) / 1000 for m in result.members)
	return m2 * SQFT_PER_M2


def _amount(head: CostHead, variables: dict) -> float:
	base = _base(head, variables) if head.calc == "Percentage" else 0.0
	if head.condition and not evaluate(head.condition, variables, head.key):
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

