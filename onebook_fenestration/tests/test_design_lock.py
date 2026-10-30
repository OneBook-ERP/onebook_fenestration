import json

import frappe
from erpnext.selling.doctype.quotation.quotation import make_sales_order
from frappe.tests import IntegrationTestCase

from onebook_fenestration.api.design import copy_design, get_design
from onebook_fenestration.fenestration.doctype.window_design.window_design import locking_document
from onebook_fenestration.fenestration.quotation import make_quotation, reprice_project
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.tests import test_quotation
from onebook_fenestration.tests.test_snapshot import load

HELPERS = ("set_up_prices", "set_up_parties", "make_quote_project", "make_design")
STATIC_HELPERS = ("make_customer", "make_address")


class TestDesignLock(IntegrationTestCase):
	"""Reuses the quotation fixtures without inheriting (and re-running) its tests."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for name in HELPERS:
			setattr(cls, name, classmethod(getattr(test_quotation.TestQuotation, name).__func__))
		for name in STATIC_HELPERS:
			setattr(cls, name, staticmethod(getattr(test_quotation.TestQuotation, name)))
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		cls.project = frappe.get_doc({"doctype": "Fenestration Project", "project_title": "Lock Test"}).insert()
		cls.set_up_prices()
		cls.set_up_parties()

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def submitted_quotation(self):
		project, designs = self.make_quote_project(refs=("W01",))
		quotation = frappe.get_doc("Quotation", make_quotation(project.name))
		quotation.submit()
		return project, designs[0], quotation

	def change_json(self, design_name):
		doc = frappe.get_doc("Window Design", design_name)
		data = json.loads(doc.design_json)
		data["width"] = data["width"] + 100
		doc.design_json = json.dumps(data)
		doc.save()

	def test_quotation_maps_design_fields_to_sales_order(self):
		project, design, quotation = self.submitted_quotation()
		order = frappe.get_doc(make_sales_order(quotation.name))
		self.assertEqual(order.fen_project, project.name)
		line = order.items[0]
		self.assertEqual(line.fen_window_design, design.name)
		self.assertEqual(line.fen_design_hash, quotation.items[0].fen_design_hash)
		self.assertTrue(line.fen_design_hash)

	def test_submitted_quotation_locks_design_inputs(self):
		_project, design, quotation = self.submitted_quotation()
		self.assertEqual(locking_document(design.name), ("Quotation", quotation.name))
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.change_json(design.name)
		self.assertIn("Copy the design", str(ctx.exception))
		self.assertIn(f"Quotation {quotation.name}", str(ctx.exception))
		doc = frappe.get_doc("Window Design", design.name)
		doc.location = "Porch"
		doc.design_name = "Porch window"
		doc.save()
		self.assertEqual(frappe.db.get_value("Window Design", design.name, "location"), "Porch")
		self.assertEqual(get_design(design.name)["locked_by"], {"doctype": "Quotation", "name": quotation.name})

	def test_lost_quotation_does_not_lock(self):
		_project, design, quotation = self.submitted_quotation()
		quotation.declare_enquiry_lost([], [], "")
		self.assertIsNone(locking_document(design.name))
		self.change_json(design.name)
		self.assertIsNone(get_design(design.name)["locked_by"])

	def test_draft_quotation_does_not_lock(self):
		project, designs = self.make_quote_project(refs=("W01",))
		make_quotation(project.name)
		self.assertIsNone(locking_document(designs[0].name))

	def test_reprice_project_skips_or_reports_locked(self):
		project, design, quotation = self.submitted_quotation()
		out = reprice_project(project.name)
		self.assertEqual(out["repriced"], 0)
		self.assertEqual(out["failed"][0]["design"], design.name)
		self.assertIn("Copy the design to change it", out["failed"][0]["message"])
		self.assertIn(quotation.name, out["failed"][0]["message"])

	def test_copy_design_gets_next_ref(self):
		project, design, _quotation = self.submitted_quotation()
		first = frappe.get_doc("Window Design", copy_design(design.name))
		second = frappe.get_doc("Window Design", copy_design(design.name))
		self.assertEqual((first.design_ref, second.design_ref), ("W01-R1", "W01-R2"))
		self.assertEqual(first.project, project.name)
		self.assertEqual(first.design_json, design.design_json)
		self.assertEqual(first.series_version, design.series_version)
		self.assertIsNone(locking_document(first.name))
		self.assertFalse(frappe.get_all("Quotation Item", {"fen_window_design": first.name}))
		self.change_json(first.name)

	def test_copy_design_requires_project_write(self):
		_project, design, _quotation = self.submitted_quotation()
		frappe.set_user("Guest")
		try:
			self.assertRaises(frappe.PermissionError, copy_design, design.name)
		finally:
			frappe.set_user("Administrator")
