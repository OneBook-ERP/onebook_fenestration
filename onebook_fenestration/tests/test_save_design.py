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
		again = self.save(design_ref="W-INS", name=res["name"], qty=3)
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

	def test_update_cannot_change_ref_or_project(self):
		first = self.save(design_ref="W-A")
		other = self.save(design_ref="W-B")
		res = self.save(name=first["name"], design_ref="W-B")
		self.assertFalse(res["ok"])
		self.assertEqual(res["message"], "Design ref and project cannot be changed after creation")
		self.assertEqual(frappe.db.get_value("Window Design", first["name"], "design_ref"), "W-A")
		self.assertTrue(frappe.db.exists("Window Design", other["name"]))

	def test_svg_sanitizer_rejects_deep_nesting(self):
		deep = f'<svg xmlns="{SVG_NS}">' + "<g>" * 100 + "</g>" * 100 + "</svg>"
		with self.assertRaises(frappe.ValidationError):
			sanitize_svg(deep)
		ok = f'<svg xmlns="{SVG_NS}">' + "<g>" * 10 + "</g>" * 10 + "</svg>"
		sanitize_svg(ok)

	def test_svg_sanitizer_drops_namespaced_attributes(self):
		src = f'<svg xmlns="{SVG_NS}" xmlns:p="urn:evil" p:xmlns="urn:evil" p:x="1"><rect p:width="3" width="4"/></svg>'
		clean = sanitize_svg(src)
		self.assertNotIn("urn:evil", clean)
		self.assertEqual(sanitize_svg(clean), clean)

	def test_svg_sanitizer_drops_dangerous_values(self):
		src = (
			f'<svg xmlns="{SVG_NS}"><rect fill="url(http://169.254.169.254/x#a)" width="1"/>'
			'<rect transform="JAVA script:x()" height="2"/><rect stroke="expression (1)" x="3"/></svg>'
		)
		clean = sanitize_svg(src)
		for bad in ("169.254", "url(", "script", "expression"):
			self.assertNotIn(bad, clean)
		self.assertIn('width="1"', clean)

	def test_save_error_clears_message_log(self):
		self.save(design_ref="W-MSG")
		frappe.local.message_log = []
		res = self.save(design_ref="W-MSG")
		self.assertFalse(res["ok"])
		self.assertEqual(frappe.local.message_log, [])
