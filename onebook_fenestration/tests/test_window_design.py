import json

import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.tests.test_snapshot import import_cs400, load


class TestWindowDesign(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		cls.project = frappe.get_doc({"doctype": "Fenestration Project", "project_title": "Test Project"}).insert()

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def make(self, design, version=None, design_ref="W01"):
		return frappe.get_doc(
			{
				"doctype": "Window Design",
				"project": self.project.name,
				"design_ref": design_ref,
				"qty": 1,
				"series_version": version or self.version,
				"design_json": json.dumps(design),
			}
		)

	def test_w01_design_computes_on_save(self):
		doc = self.make(load("w01.json")).insert()
		self.assertEqual(doc.area_sqft, 12.013)
		self.assertLessEqual(abs(doc.window_kg - 20.698), 0.02)
		self.assertEqual(doc.error_count, 0)
		self.assertEqual(len(json.loads(doc.result_json)["members"]), 13)

	def test_wall_12x6_saves_with_errors(self):
		doc = self.make(load("wall_12x6.json"), design_ref="WALL").insert()
		self.assertEqual(doc.error_count, 2)

	def test_bad_design_raises_with_path(self):
		design = load("w01.json")
		design["root"]["at"] = [0]
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.make(design, design_ref="BAD").insert()
		self.assertIn("F1", str(ctx.exception))

	def test_draft_version_rejected(self):
		draft = frappe.get_doc({"doctype": "Series Version", "series": "CS400"}).insert()
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.make(load("w01.json"), version=draft.name, design_ref="DRAFT").insert()
		self.assertIn("Series Version must be published", str(ctx.exception))

	def test_edit_location_after_version_cancelled_saves(self):
		version = import_cs400()
		doc = self.make(load("w01.json"), version=version, design_ref="LOC").insert()
		frappe.get_doc("Series Version", version).cancel()
		doc.location = "Bedroom 2"
		doc.save()
		self.assertEqual(frappe.db.get_value("Window Design", doc.name, "location"), "Bedroom 2")
		self.assertEqual(doc.area_sqft, 12.013)

	def test_invalid_design_json_message(self):
		doc = self.make({}, design_ref="BADJSON")
		doc.design_json = "{"
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert()
		self.assertIn("Design JSON is not valid", str(ctx.exception))

	def test_qty_must_be_at_least_one(self):
		doc = self.make(load("w01.json"), design_ref="QTY0")
		doc.qty = 0
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert()
		self.assertIn("Qty must be at least 1", str(ctx.exception))
