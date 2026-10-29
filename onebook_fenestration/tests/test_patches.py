import json

import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.patches.v0_1 import price_existing_window_designs
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.tests.test_snapshot import import_cs400, load

UNPRICED = {"finish": None, "price_structure": None, "unit_price": 0, "line_total": 0, "pricing_json": None}


class TestPriceExistingWindowDesigns(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		cls.project = frappe.get_doc({"doctype": "Fenestration Project", "project_title": "Patch Project"}).insert()

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def make_unpriced(self, design_ref, version=None):
		doc = frappe.get_doc(
			{
				"doctype": "Window Design",
				"project": self.project.name,
				"design_ref": design_ref,
				"qty": 2,
				"series_version": version or self.version,
				"design_json": json.dumps(load("w01.json")),
			}
		).insert()
		frappe.db.set_value("Window Design", doc.name, UNPRICED, update_modified=False)
		return doc.name

	def test_backfills_finish_structure_and_price(self):
		name = self.make_unpriced("PATCH1")
		price_existing_window_designs.execute()
		fields = ["finish", "price_structure", "unit_price", "line_total", "pricing_json"]
		row = frappe.db.get_value("Window Design", name, fields, as_dict=True)
		self.assertEqual(row.finish, "GREY")
		self.assertEqual(row.price_structure, "Standard")
		self.assertGreater(row.unit_price, 0)
		self.assertEqual(row.line_total, round(row.unit_price * 2, 2))
		self.assertTrue(json.loads(row.pricing_json)["lines"])

	def test_is_idempotent(self):
		name = self.make_unpriced("PATCH2")
		price_existing_window_designs.execute()
		modified = frappe.db.get_value("Window Design", name, "modified")
		frappe.db.set_value("Window Design", name, "unit_price", 1, update_modified=False)
		price_existing_window_designs.execute()
		self.assertEqual(frappe.db.get_value("Window Design", name, "unit_price"), 1)
		self.assertEqual(frappe.db.get_value("Window Design", name, "modified"), modified)

	def test_failure_is_logged_and_others_continue(self):
		version = import_cs400()
		bad = self.make_unpriced("PATCH-BAD", version=version)
		frappe.get_doc("Series Version", version).cancel()
		good = self.make_unpriced("PATCH-GOOD")
		price_existing_window_designs.execute()
		self.assertFalse(frappe.db.get_value("Window Design", bad, "price_structure"))
		self.assertTrue(frappe.db.exists("Error Log", {"reference_doctype": "Window Design", "reference_name": bad}))
		self.assertGreater(frappe.db.get_value("Window Design", good, "unit_price"), 0)
