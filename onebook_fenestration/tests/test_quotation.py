import json

import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.fenestration.quotation import reprice_project
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.tests.test_snapshot import load

PRICE_LIST = "Fen Test Cost"


class TestQuotation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		cls.set_up_prices()
		cls.project = frappe.get_doc({"doctype": "Fenestration Project", "project_title": "Quote Test"}).insert()
		cls.designs = [cls.make_design(ref) for ref in ("W01", "W02")]

	@classmethod
	def set_up_prices(cls):
		if not frappe.db.exists("Price List", PRICE_LIST):
			frappe.get_doc(
				{"doctype": "Price List", "price_list_name": PRICE_LIST, "currency": "INR", "buying": 1, "enabled": 1}
			).insert()
		for code in ("E104156", "E104159", "E104160", "H401"):
			if not frappe.db.exists("Item Price", {"price_list": PRICE_LIST, "item_code": code}):
				frappe.get_doc(
					{"doctype": "Item Price", "price_list": PRICE_LIST, "item_code": code, "price_list_rate": 300}
				).insert()
		frappe.db.set_single_value("Fenestration Settings", "cost_price_list", PRICE_LIST)

	@classmethod
	def make_design(cls, design_ref):
		return frappe.get_doc(
			{
				"doctype": "Window Design",
				"project": cls.project.name,
				"design_ref": design_ref,
				"qty": 1,
				"series_version": cls.version,
				"design_json": json.dumps(load("w01.json")),
			}
		).insert()

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def test_price_stamp_present(self):
		stamp = json.loads(self.designs[0].pricing_json)
		self.assertEqual(stamp["price_list"], PRICE_LIST)
		self.assertTrue(stamp["priced_on"])

	def test_reprice_project_picks_up_new_item_price(self):
		item_price = {"price_list": PRICE_LIST, "item_code": "E104156"}
		old = frappe.db.get_value("Window Design", self.designs[0].name, "unit_price")
		frappe.db.set_value("Item Price", item_price, "price_list_rate", 999)
		doc = frappe.get_doc("Window Design", self.designs[0].name)
		doc.location = "Kitchen"
		doc.save()
		self.assertEqual(doc.unit_price, old)
		result = reprice_project(self.project.name)
		self.assertEqual(result, {"repriced": 2, "failed": []})
		for design in self.designs:
			self.assertNotEqual(frappe.db.get_value("Window Design", design.name, "unit_price"), old)

	def test_reprice_requires_write(self):
		frappe.set_user("Guest")
		try:
			self.assertRaises(frappe.PermissionError, reprice_project, self.project.name)
		finally:
			frappe.set_user("Administrator")
