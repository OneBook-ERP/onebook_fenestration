"""Evaluate series rule formulas in Frappe's restricted sandbox."""

import math

from frappe.utils.safe_exec import safe_eval

from onebook_fenestration.engine.types import RuleError

ALLOWED_FUNCTIONS = {
	"ceil": math.ceil,
	"floor": math.floor,
	"round": round,
	"min": min,
	"max": max,
	"abs": abs,
}


def evaluate(expr: str, variables: dict, rule_id: str) -> float | bool:
	try:
		return safe_eval(expr, dict(ALLOWED_FUNCTIONS), dict(variables))
	except Exception as exc:
		raise RuleError(f"{rule_id}: {expr!r}: {exc}") from exc
