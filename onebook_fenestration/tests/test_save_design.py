import json

import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.api.design import get_design, save_design
from onebook_fenestration.fenestration.svg import sanitize_svg
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.tests.test_snapshot import load

SVG_NS = "http://www.w3.org/2000/svg"


class TestSaveDesign(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		cls.project = frappe.get_doc({"doctype": "Fenestration Project", "project_title": "Save Project"}).insert()

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def save(self, **kwargs):
		args = {
			"project": self.project.name,
			"design_ref": "W01",
			"series_version": self.version,
			"design": load("w01.json"),
		}
		args.update(kwargs)
		return save_design(**args)

	def test_svg_sanitizer_strips_scripts_and_handlers(self):
		dirty = (
			f'<svg xmlns="{SVG_NS}" viewBox="0 0 10 10" onload="x()">'
			'<script>alert(1)</script>'
			'<foreignObject><div>hi</div></foreignObject>'
			'<a href="javascript:x()"><rect x="0" y="0"/></a>'
			'<rect data-path="F1.0" x="1" y="1" width="5" height="5" onclick="evil()" href="http://e"/>'
			"</svg>"
		)
		clean = sanitize_svg(dirty)
		for bad in ("script", "onclick", "onload", "foreignObject", "href", "alert"):
			self.assertNotIn(bad, clean)
		self.assertIn('<rect data-path="F1.0"', clean)

	def test_svg_sanitizer_rejects_entities(self):
		evil = '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x "boom">]><svg xmlns="http://www.w3.org/2000/svg">&x;</svg>'
		with self.assertRaises(frappe.ValidationError):
			sanitize_svg(evil)

	def test_save_design_insert_and_update(self):
		res = self.save(design_ref="W-INS", svg=f'<svg xmlns="{SVG_NS}"><script>x</script><rect/></svg>')
		self.assertTrue(res["ok"])
		self.assertEqual(res["results"]["area_sqft"], 12.013)
		self.assertNotIn("script", frappe.db.get_value("Window Design", res["name"], "design_svg"))
		again = self.save(name=res["name"], qty=3)
		self.assertEqual(again["name"], res["name"])
		self.assertEqual(frappe.db.get_value("Window Design", res["name"], "qty"), 3)
		self.assertIn("rect", frappe.db.get_value("Window Design", res["name"], "design_svg"))

	def test_save_design_duplicate_ref_message(self):
		self.assertTrue(self.save(design_ref="W-DUP")["ok"])
		res = self.save(design_ref="W-DUP")
		self.assertFalse(res["ok"])
		self.assertEqual(res["message"], "A design with this ref already exists in this project")

	def test_get_design_roundtrip(self):
		res = self.save(design_ref="W-GET")
		doc = get_design(res["name"])
		self.assertEqual(doc["design_json"], load("w01.json"))
		self.assertIsInstance(doc["result_json"], dict)
		self.assertEqual(doc["design_ref"], "W-GET")
