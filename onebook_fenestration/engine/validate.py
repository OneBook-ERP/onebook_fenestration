"""Evaluate the series validation rules once per sash."""

from onebook_fenestration.engine.formula import evaluate
from onebook_fenestration.engine.types import Issue, RuleError, SeriesSnapshot


def validate(
	snapshot: SeriesSnapshot,
	sash_sizes: dict[str, tuple[float, float]],
	shutter_kg: dict[str, float],
	window_vars: dict,
	sash_paths: dict[str, str] | None = None,
) -> list[Issue]:
	sash_paths = sash_paths or {}
	issues: list[Issue] = []
	for panel, (sash_w, sash_h) in sash_sizes.items():
		variables = {
			**snapshot.constants,
			**window_vars,
			"panel": panel,
			"sash_w": sash_w,
			"sash_h": sash_h,
			"shutter_kg": shutter_kg.get(panel, 0.0),
		}
		for rule in snapshot.validation_rules:
			if evaluate(rule.when, variables, rule.id):
				issues.append(Issue(rule.severity, rule.id, _message(rule, variables), panel, rule.hint, sash_paths.get(panel, "")))
	return issues


def _message(rule, variables: dict) -> str:
	try:
		return rule.message.format(**variables)
	except (KeyError, IndexError, ValueError, AttributeError) as exc:
		raise RuleError(f"{rule.id}: message placeholder {exc} cannot be filled") from exc
