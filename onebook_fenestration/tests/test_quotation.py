import json

import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.api.project import make_quotation as api_make_quotation
from onebook_fenestration.fenestration.quotation import make_quotation, quote_status, reprice_project
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.tests.test_snapshot import load

PRICE_LIST = "Fen Test Cost"
COMPANY = "Hilux System Windows Pvt Ltd"
IN_STATE_CUSTOMER = "Fen Test Customer"
OUT_STATE_CUSTOMER = "Fen Test Customer KA"


class TestQuotation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		cls.set_up_prices()
		cls.project = frappe.get_doc(
			{"doctype": "Fenestration Project", "project_title": "Quote Test"}
		).insert()
		cls.designs = [cls.make_design(ref) for ref in ("W01", "W02")]
		cls.set_up_parties()

	@classmethod
	def set_up_prices(cls):
		if not frappe.db.exists("Price List", PRICE_LIST):
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": PRICE_LIST,
					"currency": "INR",
					"buying": 1,
					"enabled": 1,
				}
			).insert()
		for code in ("E104156", "E104159", "E104160", "H401"):
			if not frappe.db.exists("Item Price", {"price_list": PRICE_LIST, "item_code": code}):
				frappe.get_doc(
					{
						"doctype": "Item Price",
						"price_list": PRICE_LIST,
						"item_code": code,
						"price_list_rate": 300,
					}
				).insert()
		frappe.db.set_single_value("Fenestration Settings", "cost_price_list", PRICE_LIST)

	@classmethod
	def set_up_parties(cls):
		"""A company address (india_compliance needs one on every quotation) and two unregistered customers."""
		if not frappe.db.exists(
			"Dynamic Link", {"parenttype": "Address", "link_doctype": "Company", "link_name": COMPANY}
		):
			cls.make_address(
				"Fen Test Office", "Tamil Nadu", "639001", "Company", COMPANY, gstin="33AAHCH3108G1Z0"
			)
		for customer in (IN_STATE_CUSTOMER, OUT_STATE_CUSTOMER):
			if not frappe.db.exists("Customer", customer):
				frappe.get_doc(
					{
						"doctype": "Customer",
						"customer_name": customer,
						"customer_type": "Individual",
						"gst_category": "Unregistered",
					}
				).insert()
		cls.make_address("Fen Test KA", "Karnataka", "560001", "Customer", OUT_STATE_CUSTOMER)

	@staticmethod
	def make_address(title, state, pincode, link_doctype, link_name, gstin=None):
		return frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": title,
				"address_type": "Billing",
				"address_line1": "1 Test Street",
				"city": "Test City",
				"state": state,
				"gst_state": state,
				"pincode": pincode,
				"country": "India",
				"gstin": gstin,
				"is_primary_address": 1,
				"is_your_company_address": int(link_doctype == "Company"),
				"links": [{"link_doctype": link_doctype, "link_name": link_name}],
			}
		).insert()

	@classmethod
	def make_quote_project(cls, customer=IN_STATE_CUSTOMER, refs=("W01", "W02"), transport=0):
		project = frappe.get_doc(
			{
				"doctype": "Fenestration Project",
				"project_title": "Quote Build Test",
				"customer": customer,
				"company": COMPANY,
				"transport_charges": transport,
			}
		).insert()
		designs = [cls.make_design(ref, project.name) for ref in refs]
		# The fixture prices only a few items; mark the designs fully priced so the quotable gate passes.
		for design in designs:
			design.db_set("pricing_warning_count", 0)
		return project, designs

	@classmethod
	def make_design(cls, design_ref, project=None):
		return frappe.get_doc(
			{
				"doctype": "Window Design",
				"project": project or cls.project.name,
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

	def test_make_quotation_lines_and_totals(self):
		project, designs = self.make_quote_project(transport=1000)
		quotation = frappe.get_doc("Quotation", make_quotation(project.name))
		self.assertEqual(len(quotation.items), 3)
		self.assertEqual(quotation.fen_project, project.name)
		self.assertEqual(quotation.taxes_and_charges, "Output GST In-state - Hilux")
		lines = {row.fen_window_design: row for row in quotation.items if row.fen_window_design}
		for design in designs:
			design.reload()
			self.assertEqual(lines[design.name].item_code, "FEN-WINDOW")
			self.assertEqual(lines[design.name].rate, design.unit_price)
			self.assertEqual(lines[design.name].qty, design.qty)
		first = lines[designs[0].name]
		self.assertEqual(first.item_name, "W01 — 2 sash")
		self.assertEqual(
			first.description,
			"915 × 1220 mm · CS400 · Grey · 6 MM CLEAR TOUGHNED GLASS · 12.013 sq.ft",  # noqa: RUF001
		)
		self.assertEqual(quotation.tc_name, "Hilux Standard Terms")
		self.assertIn("90% advance", quotation.terms)
		transport = [row for row in quotation.items if row.item_code == "FEN-TRANSPORT"]
		self.assertEqual([(row.qty, row.rate) for row in transport], [(1, 1000)])
		heads = " ".join(row.account_head for row in quotation.taxes)
		self.assertIn("CGST", heads)
		self.assertIn("SGST", heads)
		self.assertNotIn("IGST", heads)
		self.assertAlmostEqual(
			quotation.grand_total, quotation.net_total + quotation.total_taxes_and_charges, places=2
		)
		self.assertEqual(
			frappe.db.get_value("Fenestration Project", project.name, "quotation"), quotation.name
		)
		status = quote_status(project.name)
		self.assertEqual(status["quotation"], quotation.name)
		self.assertEqual(status["docstatus"], 0)
		self.assertEqual(status["grand_total"], quotation.grand_total)

	def test_out_of_state_uses_igst(self):
		project, _designs = self.make_quote_project(customer=OUT_STATE_CUSTOMER, refs=("W01",))
		quotation = frappe.get_doc("Quotation", make_quotation(project.name))
		self.assertEqual(quotation.taxes_and_charges, "Output GST Out-state - Hilux")
		heads = " ".join(row.account_head for row in quotation.taxes)
		self.assertIn("IGST", heads)
		self.assertNotIn("CGST", heads)

	def test_make_quotation_refuses_unpriced_designs(self):
		project, designs = self.make_quote_project()
		frappe.db.set_value("Window Design", designs[1].name, "pricing_warning_count", 1)
		out = api_make_quotation(project.name)
		self.assertIs(out["ok"], False)
		self.assertIn("W02", out["message"])
		self.assertNotIn("W01", out["message"])
		self.assertFalse(frappe.db.get_value("Fenestration Project", project.name, "quotation"))

	def test_remake_updates_draft_in_place(self):
		project, designs = self.make_quote_project()
		first = make_quotation(project.name)
		frappe.delete_doc("Window Design", designs[1].name)
		second = make_quotation(project.name)
		self.assertEqual(first, second)
		quotation = frappe.get_doc("Quotation", second)
		self.assertEqual([row.fen_window_design for row in quotation.items], [designs[0].name])

	def test_submitted_quotation_not_modified(self):
		project, _designs = self.make_quote_project()
		first = frappe.get_doc("Quotation", make_quotation(project.name))
		first.submit()
		second = make_quotation(project.name)
		self.assertNotEqual(second, first.name)
		self.assertEqual(frappe.db.get_value("Fenestration Project", project.name, "quotation"), second)
		self.assertEqual(frappe.db.get_value("Quotation", first.name, "grand_total"), first.grand_total)
		self.assertEqual(frappe.db.get_value("Quotation", first.name, "docstatus"), 1)

	def test_no_customer_refused(self):
		project, _designs = self.make_quote_project(customer=None)
		out = api_make_quotation(project.name)
		self.assertEqual(out, {"ok": False, "message": "Set a customer on the project"})
