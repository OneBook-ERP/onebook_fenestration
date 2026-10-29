from frappe.model.document import Document

from onebook_fenestration.series_studio.snapshot import clear_all_snapshots


class FenestrationGlass(Document):
	def on_update(self):
		clear_all_snapshots()

	def on_trash(self):
		clear_all_snapshots()
