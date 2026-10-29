import frappe
from frappe import _
from frappe.model.document import Document

from onebook_fenestration.engine import RuleError
from onebook_fenestration.engine.formula import evaluate, evaluate_number
from onebook_fenestration.engine.pricing import _RESERVED, CostHead


class PriceStructure(Document):
	def validate(self):
		earlier = set()
		for row in self.heads:
			self.validate_head(row, earlier)
			earlier.add(row.key)
		if self.is_default:
			self.clear_other_defaults()

	def validate_head(self, row, earlier: set):
		key = row.key or ""
		if key in earlier or key in _RESERVED:
			self.fail(key, _("key must be unique and not a reserved name"))
		if not key.isidentifier():
			self.fail(key, _("key must be a valid identifier"))
		if row.calc == "Formula" and not row.formula:
			self.fail(key, _("a Formula head needs a formula"))
		if row.calc == "Percentage":
			bases = [part.strip() for part in (row.base or "").split(",") if part.strip()]
			if not bases or not set(bases) <= earlier:
				self.fail(key, _("base must list earlier heads"))
		variables = {name: 1 for name in _RESERVED} | {"finish_type": "Mill"} | dict.fromkeys(earlier, 1)
		try:
			if row.formula:
				evaluate_number(row.formula, variables, key)
			if row.condition:
				evaluate(row.condition, variables, key)
		except (RuleError, ValueError) as exc:
			self.fail(key, str(exc))

	def fail(self, key: str, reason: str):
		frappe.throw(_("Cost head {0}: {1}").format(key, reason))

	def clear_other_defaults(self):
		frappe.db.set_value(
			"Price Structure", {"is_default": 1, "name": ("!=", self.name)}, "is_default", 0
		)


def to_cost_heads(name: str) -> tuple[CostHead, ...]:
	doc = frappe.get_cached_doc("Price Structure", name)
	return tuple(
		CostHead(
			key=row.key,
			label=row.label,
			calc=row.calc,
			rate=float(row.rate or 0),
			formula=row.formula or "",
			base=row.base or "",
			condition=row.condition or "",
			include_in_total=bool(row.include_in_total),
		)
		for row in doc.heads
	)
