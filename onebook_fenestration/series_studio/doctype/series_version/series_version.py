import json

import frappe
from frappe import _
from frappe.model.document import Document

from onebook_fenestration.engine import RuleError, SeriesSnapshot
from onebook_fenestration.series_studio.snapshot import build_snapshot_dict, clear_snapshot


class SeriesVersion(Document):
	def before_submit(self):
		"""Check completeness, then freeze the snapshot so later master edits never change this version."""
		snapshot = build_snapshot_dict(self)
		try:
			SeriesSnapshot.from_dict(snapshot).check()
		except RuleError as exc:
			frappe.throw(str(exc), title=_("Series is incomplete"))
		self.snapshot_json = json.dumps(snapshot)

	def on_submit(self):
		frappe.db.set_value("Profile Series", self.series, "published_version", self.name)
		clear_snapshot(self.name)

	def on_cancel(self):
		if frappe.db.get_value("Profile Series", self.series, "published_version") == self.name:
			frappe.db.set_value("Profile Series", self.series, "published_version", None)
		clear_snapshot(self.name)
