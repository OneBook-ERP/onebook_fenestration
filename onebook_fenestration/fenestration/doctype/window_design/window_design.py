import dataclasses
import json

import frappe
from frappe.model.document import Document

from onebook_fenestration.engine import DesignError, EngineResult, RuleError, compute
from onebook_fenestration.series_studio.snapshot import get_snapshot


def result_to_dict(result: EngineResult) -> dict:
	"""JSON-safe dict of an EngineResult (tuples become lists)."""
	return json.loads(json.dumps(dataclasses.asdict(result)))


class WindowDesign(Document):
	def validate(self):
		if frappe.db.get_value("Series Version", self.series_version, "docstatus") != 1:
			frappe.throw("Series Version must be published")
		design = json.loads(self.design_json) if isinstance(self.design_json, str) else self.design_json
		try:
			result = compute(design, get_snapshot(self.series_version))
		except (DesignError, RuleError) as exc:
			frappe.throw(str(exc), title="Design is invalid")
		self.area_m2 = result.area_m2
		self.area_sqft = result.area_sqft
		self.window_kg = result.window_kg
		self.error_count = sum(1 for i in result.issues if i.severity == "error")
		self.warning_count = sum(1 for i in result.issues if i.severity == "warn")
		self.result_json = json.dumps(result_to_dict(result))
