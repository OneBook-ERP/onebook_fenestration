import json
from unittest.mock import patch
from collections import defaultdict

import frappe
from erpnext.selling.doctype.quotation.quotation import make_sales_order
from erpnext.selling.doctype.sales_order.sales_order import make_work_orders
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, nowdate

from onebook_fenestration.engine import compute
from onebook_fenestration.fenestration.quotation import make_quotation
from onebook_fenestration.pricing.rates import price_design
from onebook_fenestration.production.bom import bom_rows
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.series_studio.snapshot import get_snapshot
from onebook_fenestration.setup.install import setup_production_items
from onebook_fenestration.tests import test_quotation
from onebook_fenestration.tests.test_snapshot import load

HELPERS = ("set_up_prices", "set_up_parties", "make_quote_project", "make_design")
STATIC_HELPERS = ("make_customer", "make_address")
COMPANY = test_quotation.COMPANY


class TestProductionBom(IntegrationTestCase):
	"""Reuses the quotation fixtures without inheriting (and re-running) its tests."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for name in HELPERS:
			setattr(cls, name, classmethod(getattr(test_quotation.TestQuotation, name).__func__))
		for name in STATIC_HELPERS:
			setattr(cls, name, staticmethod(getattr(test_quotation.TestQuotation, name)))
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		cls.project = frappe.get_doc({"doctype": "Fenestration Project", "project_title": "BOM Test"}).insert()
		cls.set_up_prices()
		cls.set_up_parties()
		setup_production_items()

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def isolate(self):
		"""Undo this test's record edits so later tests see the fixtures untouched."""
		point = f"fen_{self._testMethodName}"[:60]
		frappe.db.savepoint(point)
		self.addCleanup(frappe.db.rollback, save_point=point)

	def draft_order(self, refs=("W01",), transport=0):
		project, designs = self.make_quote_project(refs=refs, transport=transport)
		quotation = frappe.get_doc("Quotation", make_quotation(project.name))
		quotation.submit()
		order = frappe.get_doc(make_sales_order(quotation.name))
		order.delivery_date = add_days(nowdate(), 30)
		order.insert()
		return order, designs

	def test_bom_rows_w01(self):
		design = self.make_design("W01")
		rows = bom_rows(design)
		self.assertEqual([r["item_code"] for r in rows], sorted(r["item_code"] for r in rows))
		by_item = {r["item_code"]: r for r in rows}

		result = compute(load("w01.json"), get_snapshot(self.version))
		mm = sum(m.length for m in result.members if m.profile == "E104156")
		expected_kg = round(mm / 1000 * get_snapshot(self.version).profiles["E104156"].kg_per_m, 3)
		self.assertEqual(by_item["E104156"]["uom"], "Kg")
		self.assertAlmostEqual(by_item["E104156"]["qty"], expected_kg, places=3)

		gasket_m = defaultdict(float)
		for line in result.bom:
			if line.group == "Gasket":
				gasket_m[line.item] += line.length / 1000
		self.assertTrue(gasket_m)
		for item, meters in gasket_m.items():
			self.assertEqual(by_item[item]["uom"], "Meter")
			self.assertAlmostEqual(by_item[item]["qty"], meters, places=3)

		glass_item = frappe.db.get_value("Fenestration Glass", result.glass[0].glass, "item")
		area = sum(p.width * p.height / 1e6 for p in result.glass)
		self.assertEqual(by_item[glass_item]["uom"], "Square Meter")
		self.assertAlmostEqual(by_item[glass_item]["qty"], area, places=3)

	def test_order_submit_creates_bom_per_design(self):
		order, designs = self.draft_order(refs=("W01", "W02"))
		order.submit()
		self.assertEqual(len(order.items), 2)
		for line, design in zip(order.items, designs, strict=True):
			self.assertTrue(line.bom_no)
			bom = frappe.db.get_value(
				"BOM", line.bom_no, ("item", "is_default", "docstatus", "fen_window_design"), as_dict=True
			)
			self.assertEqual(bom, {"item": "FEN-WINDOW", "is_default": 0, "docstatus": 1, "fen_window_design": design.name})
		self.assertNotEqual(order.items[0].bom_no, order.items[1].bom_no)

	def test_transport_line_gets_no_bom(self):
		order, _designs = self.draft_order(transport=500)
		order.submit()
		transport = [i for i in order.items if i.item_code == "FEN-TRANSPORT"]
		self.assertEqual(len(transport), 1)
		self.assertFalse(transport[0].bom_no)

	def test_amended_order_reuses_bom(self):
		order, designs = self.draft_order()
		order.submit()
		bom = order.items[0].bom_no
		order.cancel()
		amended = frappe.copy_doc(order)
		amended.amended_from = order.name
		amended.docstatus = 0
		for line in amended.items:
			line.bom_no = None
		amended.insert()
		amended.submit()
		self.assertEqual(amended.items[0].bom_no, bom)
		self.assertEqual(frappe.db.count("BOM", {"fen_window_design": designs[0].name}), 1)

	def test_changed_design_refuses_submit(self):
		order, _designs = self.draft_order()
		order.items[0].fen_design_hash = "stale"
		with self.assertRaises(frappe.ValidationError) as ctx:
			order.submit()
		self.assertIn("Requote before ordering", str(ctx.exception))

	def test_missing_glass_item_refuses_submit(self):
		order, designs = self.draft_order(refs=("W01", "W02"))
		glass = compute(load("w01.json"), get_snapshot(self.version)).glass[0].glass
		self.isolate()
		frappe.db.set_value("Fenestration Glass", glass, "item", None)
		with patch("onebook_fenestration.production.bom.ensure_bom") as ensure:
			with self.assertRaises(frappe.ValidationError) as ctx:
				order.submit()
		ensure.assert_not_called()
		message = str(ctx.exception)
		self.assertIn(glass, message)
		self.assertEqual(message.count(f"glass {glass}"), 2)  # one combined message, one entry per design
		for design in designs:
			self.assertEqual(frappe.db.count("BOM", {"fen_window_design": design.name}), 0)

	def test_glass_item_in_wrong_unit_refuses_submit(self):
		order, designs = self.draft_order()
		glass = compute(load("w01.json"), get_snapshot(self.version)).glass[0].glass
		item = frappe.db.get_value("Fenestration Glass", glass, "item")
		self.isolate()
		frappe.db.set_value("Item", item, "stock_uom", "Nos")
		frappe.db.delete("UOM Conversion Detail", {"parent": item, "uom": "Square Meter"})
		with self.assertRaises(frappe.ValidationError) as ctx:
			order.submit()
		self.assertIn(f"Item {item} is stocked in Nos; BOM needs Square Meter", str(ctx.exception))
		self.assertEqual(frappe.db.count("BOM", {"fen_window_design": designs[0].name}), 0)

	def test_work_order_from_order_uses_design_bom_and_batch(self):
		wip = self.warehouse("Fen Test WIP")
		fg = self.warehouse("Fen Test FG")
		frappe.db.set_single_value("Manufacturing Settings", "make_serial_no_batch_from_work_order", 0)
		setup_production_items()
		order, _designs = self.draft_order()
		order.submit()
		line = order.items[0]
		names = make_work_orders(
			json.dumps(
				{
					"items": [
						{
							"item_code": line.item_code,
							"bom": line.bom_no,
							"pending_qty": line.qty,
							"sales_order_item": line.name,
							"warehouse": fg,
							"description": line.description,
						}
					]
				}
			),
			order.name,
			COMPANY,
		)
		work_order = frappe.get_doc("Work Order", names[0])
		self.assertEqual(work_order.bom_no, line.bom_no)
		work_order.wip_warehouse = wip
		work_order.fg_warehouse = fg
		work_order.skip_transfer = 1
		work_order.save()
		work_order.submit()
		batches = frappe.get_all(
			"Batch",
			{"reference_doctype": "Work Order", "reference_name": work_order.name},
			["name", "use_batchwise_valuation"],
		)
		self.assertEqual(len(batches), 1)
		self.assertEqual(batches[0].use_batchwise_valuation, 1)

	@staticmethod
	def warehouse(name):
		full = f"{name} - Hilux"
		if not frappe.db.exists("Warehouse", full):
			frappe.get_doc({"doctype": "Warehouse", "warehouse_name": name, "company": COMPANY}).insert()
		return full

	def test_setup_is_idempotent_and_respects_stock(self):
		setup_production_items()
		setup_production_items()
		flags = frappe.db.get_value(
			"Item",
			"FEN-WINDOW",
			("is_stock_item", "has_batch_no", "create_new_batch", "include_item_in_manufacturing"),
		)
		self.assertEqual(tuple(flags), (1, 1, 1, 0))
		for code, expected in (("FEN-T-FRESH", "Kg"), ("FEN-T-USED", "Nos")):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_group": "Fenestration",
					"stock_uom": "Nos",
					"is_stock_item": 1,
					"fen_item_kind": "Profile",
					"gst_hsn_code": "761010",
				}
			).insert()
		frappe.db.sql(
			"""insert into `tabStock Ledger Entry` (name, item_code, creation, modified, docstatus)
			values ('fen-test-sle', 'FEN-T-USED', now(), now(), 1)"""
		)
		setup_production_items()
		self.assertEqual(frappe.db.get_value("Item", "FEN-T-FRESH", "stock_uom"), "Kg")
		self.assertEqual(frappe.db.get_value("Item", "FEN-T-USED", "stock_uom"), "Nos")

	def test_restock_drops_nos_row_and_moves_item_price(self):
		design = self.make_design("W09")
		before = design.unit_price
		self.isolate()
		glass = frappe.db.get_value("Fenestration Glass", "6CTG", "item")
		items = ("E104156", "G23", glass)
		frappe.db.delete("BOM Item", {"item_code": ("in", items)})  # BOMs from earlier tests would make them "used"
		for code in items:  # put them back in the legacy state: Nos stock unit, Nos row, Nos prices
			frappe.db.set_value("Item", code, "stock_uom", "Nos")
			frappe.db.sql("delete from `tabUOM Conversion Detail` where parent=%s", code)
			frappe.get_doc(
				{"doctype": "UOM Conversion Detail", "parent": code, "parenttype": "Item", "parentfield": "uoms",
				 "uom": "Nos", "conversion_factor": 1}
			).insert(ignore_permissions=True)
			frappe.db.set_value("Item Price", {"item_code": code}, "uom", "Nos")
		setup_production_items()
		for code, uom in zip(items, ("Kg", "Meter", "Square Meter"), strict=True):
			self.assertEqual(frappe.db.get_value("Item", code, "stock_uom"), uom)
			self.assertEqual(
				frappe.db.get_all("UOM Conversion Detail", {"parent": code, "uom": "Nos"}), []
			)
			for price_uom in frappe.get_all("Item Price", {"item_code": code}, pluck="uom"):
				self.assertEqual(price_uom, uom)
		self.assertEqual(price_design(load("w01.json"), self.version, design.finish, design.price_structure)[1].unit_price, before)
