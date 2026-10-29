import dataclasses
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from onebook_fenestration.engine import DesignError, EngineResult, RuleError, compute
from onebook_fenestration.fenestration.svg import sanitize_svg
from onebook_fenestration.series_studio.snapshot import get_snapshot


def result_to_dict(result: EngineResult) -> dict:
	"""JSON-safe dict of an EngineResult (tuples become lists)."""
	return json.loads(json.dumps(dataclasses.asdict(result)))


class WindowDesign(Document):
	def validate(self):
		if cint(self.qty) < 1:
			frappe.throw(_("Qty must be at least 1"))
		if not self.is_new() and (self.has_value_changed("project") or self.has_value_changed("design_ref")):
			frappe.throw(_("Design ref and project cannot be changed after creation"))
		if self.is_new() or self.has_value_changed("design_json") or self.has_value_changed("series_version"):
			self.compute_results()
		if self.design_svg and (self.is_new() or self.has_value_changed("design_svg")):
			self.design_svg = sanitize_svg(self.design_svg)

	def compute_results(self):
		"""Run the engine on the design; only called when its inputs change, so stored results stay frozen."""
		if frappe.db.get_value("Series Version", self.series_version, "docstatus") != 1:
			frappe.throw(_("Series Version must be published"))
		try:
			design = json.loads(self.design_json) if isinstance(self.design_json, str) else self.design_json
			result = compute(design, get_snapshot(self.series_version))
		except json.JSONDecodeError:
			frappe.throw(_("Design JSON is not valid"), title=_("Design is invalid"))
		except (DesignError, RuleError) as exc:
			frappe.throw(str(exc), title=_("Design is invalid"))
		self.area_m2 = result.area_m2
		self.area_sqft = result.area_sqft
		self.window_kg = result.window_kg
		self.error_count = sum(1 for i in result.issues if i.severity == "error")
		self.warning_count = sum(1 for i in result.issues if i.severity == "warn")
		self.result_json = json.dumps(result_to_dict(result))
