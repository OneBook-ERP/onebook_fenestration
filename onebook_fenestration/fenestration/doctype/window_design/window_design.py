import dataclasses
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from onebook_fenestration.engine import DesignError, EngineResult, PriceBreakdown, RuleError
from onebook_fenestration.fenestration.svg import sanitize_svg
from onebook_fenestration.pricing.rates import price_design


def pricing_to_dict(breakdown: PriceBreakdown) -> dict:
	"""JSON-safe dict of a PriceBreakdown: cost-head lines, totals and pricing issues."""
	return {
		"lines": [dataclasses.asdict(line) for line in breakdown.lines],
		"unit_price": breakdown.unit_price,
		"rate_per_sqft": breakdown.rate_per_sqft,
		"issues": [dataclasses.asdict(issue) for issue in breakdown.issues],
	}


def result_to_dict(result: EngineResult) -> dict:
	"""JSON-safe dict of an EngineResult (tuples become lists)."""
	return json.loads(json.dumps(dataclasses.asdict(result)))


class WindowDesign(Document):
	def validate(self):
		if cint(self.qty) < 1:
			frappe.throw(_("Qty must be at least 1"))
		if not self.is_new() and (self.has_value_changed("project") or self.has_value_changed("design_ref")):
			frappe.throw(_("Design ref and project cannot be changed after creation"))
		self.set_pricing_defaults()
		if self.needs_pricing():
			self.compute_results()
		elif self.has_value_changed("qty"):
			self.line_total = round(flt(self.unit_price) * cint(self.qty), 2)
		if self.design_svg and (self.is_new() or self.has_value_changed("design_svg")):
			self.design_svg = sanitize_svg(self.design_svg)

	def set_pricing_defaults(self):
		settings = frappe.get_cached_doc("Fenestration Settings")
		self.finish = self.finish or settings.default_finish
		self.price_structure = self.price_structure or settings.default_price_structure

	def needs_pricing(self) -> bool:
		"""Price changes (Item Prices) never re-price a saved design; only its own inputs do."""
		fields = ("design_json", "series_version", "finish", "price_structure")
		return self.is_new() or any(self.has_value_changed(f) for f in fields)

	def compute_results(self):
		"""Run the engine and pricing on the design; only called when its inputs change, so stored results stay frozen."""
		if frappe.db.get_value("Series Version", self.series_version, "docstatus") != 1:
			frappe.throw(_("Series Version must be published"))
		try:
			design = json.loads(self.design_json) if isinstance(self.design_json, str) else self.design_json
			result, breakdown = price_design(design, self.series_version, self.finish, self.price_structure)
		except json.JSONDecodeError:
			frappe.throw(_("Design JSON is not valid"), title=_("Design is invalid"))
		except (DesignError, RuleError) as exc:
			frappe.throw(str(exc), title=_("Design is invalid"))
		self.area_m2 = result.area_m2
		self.area_sqft = result.area_sqft
		self.window_kg = result.window_kg
		self.error_count = sum(1 for i in result.issues if i.severity == "error")
		issues = result.issues + breakdown.issues
		self.warning_count = sum(1 for i in issues if i.severity == "warn")
		self.unit_price = breakdown.unit_price
		self.rate_per_sqft = breakdown.rate_per_sqft
		self.line_total = round(breakdown.unit_price * cint(self.qty), 2)
		self.pricing_json = json.dumps(pricing_to_dict(breakdown))
		self.result_json = json.dumps(result_to_dict(result))
