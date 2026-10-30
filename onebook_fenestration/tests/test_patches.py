import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.engine.glazing import GASKETS
from onebook_fenestration.patches.v0_1 import create_gasket_items, price_existing_window_designs
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


class TestCreateGasketItems(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def test_importer_creates_gasket_items(self):
		for code in GASKETS:
			frappe.delete_doc("Item", code, force=True)
		import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		for code, name in GASKETS.items():
			item = frappe.db.get_value("Item", code, ("item_name", "fen_item_kind", "stock_uom"), as_dict=True)
			self.assertEqual(item, {"item_name": name, "fen_item_kind": "Gasket", "stock_uom": "Meter"})
		if frappe.get_meta("Item").has_field("gst_hsn_code"):
			self.assertEqual(frappe.db.get_value("Item", "G21", "gst_hsn_code"), "400829")

	def test_patch_creates_missing_and_is_idempotent(self):
		frappe.delete_doc("Item", "G23", force=True)
		frappe.db.set_value("Item", "G21", "item_name", "CUSTOM NAME")
		create_gasket_items.execute()
		create_gasket_items.execute()
		self.assertEqual(frappe.db.get_value("Item", "G23", "fen_item_kind"), "Gasket")
		self.assertEqual(frappe.db.get_value("Item", "G21", "item_name"), "CUSTOM NAME")

	def test_patch_skips_without_item_group(self):
		frappe.delete_doc("Item", "G23", force=True)
		with patch.object(create_gasket_items.frappe.db, "exists", return_value=False):
			create_gasket_items.execute()
		self.assertFalse(frappe.db.exists("Item", "G23"))
