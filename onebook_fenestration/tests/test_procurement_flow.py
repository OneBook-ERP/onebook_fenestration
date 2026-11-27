import json

import frappe
from erpnext.manufacturing.doctype.production_plan.production_plan import (
	get_items_for_material_requests,
)
from erpnext.selling.doctype.quotation.quotation import make_sales_order
from erpnext.stock.doctype.material_request.material_request import make_purchase_order
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, nowdate

from onebook_fenestration.api.project import (
	make_project_material_request,
	make_project_purchase_order,
	material_tree,
)
from onebook_fenestration.fenestration.quotation import design_hash, make_quotation
from onebook_fenestration.production.bom import WINDOW_ITEM
from onebook_fenestration.production.takeoff import project_material_tree
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.setup.install import setup_production_items
from onebook_fenestration.setup.procurement import setup_procurement
from onebook_fenestration.tests import test_quotation
from onebook_fenestration.tests.test_snapshot import load

COMPANY = "OneBook Fenestration"
TEST_CUSTOMER = "Fen Procurement Test Customer"


class TestProcurementFlow(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Warehouse Type", "Transit"):
			frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"}).insert()
		if not frappe.db.exists("Company", COMPANY):
			abbr = "OBF" if not frappe.db.exists("Company", {"abbr": "OBF"}) else "OBF1"
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": COMPANY,
					"abbr": abbr,
					"default_currency": "INR",
					"country": "India",
				}
			).insert()
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		test_quotation.TestQuotation.set_up_prices()
		setup_production_items()
		setup_procurement(company=COMPANY)
		if not frappe.db.exists(
			"Dynamic Link", {"link_doctype": "Company", "link_name": COMPANY, "parenttype": "Address"}
		):
			frappe.get_doc(
				{
					"doctype": "Address",
					"address_title": f"{COMPANY} Billing",
					"address_type": "Billing",
					"address_line1": "1 Test Industrial Estate",
					"city": "Chennai",
					"state": "Tamil Nadu",
					"pincode": "600001",
					"country": "India",
					"is_primary_address": 1,
					"is_your_company_address": 1,
					"links": [{"link_doctype": "Company", "link_name": COMPANY}],
				}
			).insert()

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def isolate(self):
		point = f"fen_{self._testMethodName}"[:60]
		frappe.db.savepoint(point)
		self.addCleanup(frappe.db.rollback, save_point=point)

	def _make_supplier(self, name="Test Aluminium Supplier", group="Extrusions"):
		if frappe.db.exists("Supplier", name):
			return name
		doc = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": name,
				"supplier_group": group,
			}
		).insert()
		return doc.name

	def _make_customer(self, name=TEST_CUSTOMER):
		if frappe.db.exists("Customer", name):
			return name
		return (
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": name,
					"customer_type": "Company",
				}
			)
			.insert()
			.name
		)

	def _make_project_with_design(self, refs=("W01",)):
		customer = self._make_customer()
		project = frappe.get_doc(
			{
				"doctype": "Fenestration Project",
				"project_title": "Procurement Flow Test",
				"customer": customer,
				"company": COMPANY,
			}
		).insert()
		designs = []
		for ref in refs:
			design = frappe.get_doc(
				{
					"doctype": "Window Design",
					"project": project.name,
					"design_ref": ref,
					"qty": 1,
					"series_version": self.version,
					"design_json": json.dumps(load("w01.json")),
				}
			).insert()
			designs.append(design)
		return project, designs

	def test_procurement_setup_creates_warehouses_terms_and_uoms(self):
		self.isolate()
		abbr = frappe.db.get_value("Company", COMPANY, "abbr")
		main_group = f"Main Warehouse - {abbr}"
		self.assertEqual(frappe.db.get_value("Warehouse", main_group, "is_group"), 1)
		self.assertEqual(frappe.db.get_value("Warehouse", f"Stores - {abbr}", "parent_warehouse"), main_group)
		self.assertEqual(
			frappe.db.get_value("Warehouse", f"Work In Progress - {abbr}", "parent_warehouse"), main_group
		)
		self.assertEqual(
			frappe.db.get_value("Warehouse", f"Finished Goods - {abbr}", "parent_warehouse"), main_group
		)
		self.assertEqual(
			frappe.db.get_value("Warehouse", f"Goods In Transit - {abbr}", "parent_warehouse"), main_group
		)
		self.assertTrue(frappe.db.exists("Warehouse", f"Hilux Warehouse - {abbr}"))
		self.assertTrue(frappe.db.exists("Supplier Group", "Extrusions"))
		self.assertTrue(frappe.db.exists("Supplier Group", "Glass"))
		self.assertTrue(frappe.db.exists("Supplier", "Hilux Aluminium Extrusions"))
		self.assertTrue(frappe.db.exists("Supplier", "Hilux Toughened Glass"))
		self.assertTrue(frappe.db.exists("Supplier", "Hilux Hardware & Gaskets"))
		self.assertTrue(frappe.db.exists("Payment Terms Template", "Net 30"))
		self.assertTrue(frappe.db.exists("Payment Terms Template", "50% Advance + Balance Net 7"))
		self.assertGreater(
			flt(frappe.db.get_single_value("Stock Settings", "over_delivery_receipt_allowance")), 0
		)
		self.assertGreater(flt(frappe.db.get_single_value("Accounts Settings", "over_billing_allowance")), 0)

		e104 = frappe.get_doc("Item", "E104156")
		self.assertTrue(any(row.uom == "Meter" and flt(row.conversion_factor) > 0 for row in e104.uoms))
		self.assertGreater(flt(e104.lead_time_days), 0)

	def test_project_material_tree_groups_by_window_and_category_with_cut_lengths(self):
		self.isolate()
		project, designs = self._make_project_with_design(refs=("W01", "W02"))
		designs[1].db_set("superseded_by", designs[0].name)
		tree = project_material_tree(project.name)
		self.assertEqual(tree["project"]["name"], project.name)
		self.assertEqual(len(tree["windows"]), 1)
		win = tree["windows"][0]
		self.assertEqual(win["design_ref"], "W01")
		self.assertTrue(win["profiles"])
		self.assertTrue(win["glass"])
		self.assertTrue(win["hardware"])
		self.assertTrue(any(cut["length_mm"] > 0 and cut["pieces"] > 0 for cut in win["profiles"][0]["cuts"]))
		self.assertTrue(tree["summary"]["profiles"])
		self.assertTrue(all(row["cut_length_mm"] > 0 for row in tree["summary"]["profiles"]))

		api_tree = material_tree(project.name)
		self.assertEqual(api_tree["windows"][0]["design_ref"], "W01")

	def test_create_material_request_and_purchase_order_preserve_cut_lengths_and_proforma(self):
		self.isolate()
		project, _designs = self._make_project_with_design(refs=("W01",))
		abbr = frappe.db.get_value("Company", COMPANY, "abbr")
		main_wh = f"Stores - {abbr}"
		supplier = self._make_supplier()

		mr_all = make_project_material_request(project.name, category="all", warehouse=main_wh)
		self.assertTrue(mr_all["ok"])

		mr_res = make_project_material_request(project.name, category="Profile", warehouse=main_wh)
		self.assertTrue(mr_res["ok"])
		mr = frappe.get_doc("Material Request", mr_res["material_request"])
		self.assertEqual(mr.fen_project, project.name)
		self.assertEqual(mr.material_request_type, "Purchase")
		self.assertTrue(all(row.fen_cut_length_mm > 0 and row.fen_piece_count > 0 for row in mr.items))
		mr.submit()

		po_from_mr = frappe.get_doc(make_purchase_order(mr.name))
		po_from_mr.supplier = supplier
		po_from_mr.insert()
		self.assertTrue(all(row.fen_cut_length_mm > 0 for row in po_from_mr.items))

		po_res = make_project_purchase_order(
			project.name, supplier=supplier, category="Profile", warehouse=main_wh
		)
		po = frappe.get_doc("Purchase Order", po_res["purchase_order"])
		self.assertEqual(po.fen_project, project.name)
		self.assertTrue(all(row.fen_cut_length_mm > 0 and row.fen_piece_count > 0 for row in po.items))
		po.submit()

		# Supplier sends Proforma Invoice after PO submission.
		po.fen_proforma_no = "PI-ALU-101"
		po.fen_proforma_date = nowdate()
		po.fen_proforma_confirmed = 1
		po.save()
		po.reload()
		self.assertEqual(po.fen_proforma_no, "PI-ALU-101")
		self.assertEqual(po.fen_proforma_confirmed, 1)

		html = frappe.get_print("Purchase Order", po.name, print_format="Fenestration Purchase Order")
		self.assertIn("PI-ALU-101", html)
		self.assertIn("E104156", html)

	def test_direct_flow_sales_order_bom_and_production_plan(self):
		self.isolate()
		project, designs = self._make_project_with_design(refs=("W01",))
		for d in designs:
			d.db_set("pricing_warning_count", 0)
		quote = frappe.get_doc("Quotation", make_quotation(project.name))
		quote.submit()

		abbr = frappe.db.get_value("Company", COMPANY, "abbr")
		main_wh = f"Stores - {abbr}"
		so = frappe.get_doc(make_sales_order(quote.name))
		so.delivery_date = add_days(nowdate(), 30)
		so.set_warehouse = main_wh
		for item in so.items:
			item.warehouse = main_wh
			item.delivery_date = so.delivery_date
		so.insert()
		so.submit()
		self.assertTrue(all(row.bom_no for row in so.items if row.fen_window_design))

		plan = frappe.get_doc(
			{
				"doctype": "Production Plan",
				"company": COMPANY,
				"get_items_from": "Sales Order",
				"for_warehouse": main_wh,
				"sales_orders": [{"sales_order": so.name}],
			}
		)
		plan.get_so_items()
		self.assertTrue(plan.po_items)
		self.assertTrue(plan.po_items[0].bom_no)
		plan.insert()
		mr_items = get_items_for_material_requests(plan.as_dict())
		self.assertTrue(mr_items)
