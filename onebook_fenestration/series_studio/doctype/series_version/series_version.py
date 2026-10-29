import frappe

from frappe.model.document import Document

from onebook_fenestration.engine import RuleError, SeriesSnapshot
from onebook_fenestration.series_studio.snapshot import build_snapshot_dict, clear_snapshot


class SeriesVersion(Document):
	def before_submit(self):
		try:
			SeriesSnapshot.from_dict(build_snapshot_dict(self)).check()
		except RuleError as exc:
			frappe.throw(str(exc), title="Series is incomplete")

	def on_submit(self):
		frappe.db.set_value("Profile Series", self.series, "published_version", self.name)
		clear_snapshot(self.name)

	def on_cancel(self):
		if frappe.db.get_value("Profile Series", self.series, "published_version") == self.name:
			frappe.db.set_value("Profile Series", self.series, "published_version", None)
		clear_snapshot(self.name)
