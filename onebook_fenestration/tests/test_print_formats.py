import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.pdf import get_pdf

from onebook_fenestration.fenestration.quotation import make_quotation
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.tests import test_quotation
from onebook_fenestration.tests.test_snapshot import load
from onebook_fenestration.fenestration import print_context
from onebook_fenestration.utils.jinja import fen_svg_data_uri

QUOTATION_FORMAT = "Fenestration Quotation"
PROJECT_FORMATS = ("Fenestration Elevation", "Fenestration Estimate Confirmation")
DATA_URI = "data:image/svg+xml;base64,"
PLACEHOLDER = "Drawing not available"
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'


class TestPrintFormats(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		test_quotation.TestQuotation.set_up_prices()
		test_quotation.TestQuotation.set_up_parties()
		cls.project = frappe.get_doc(
			{
				"doctype": "Fenestration Project",
				"project_title": "Print Test",
				"customer": test_quotation.IN_STATE_CUSTOMER,
				"company": test_quotation.COMPANY,
				"transport_charges": 1000,
			}
		).insert()
		cls.designs = [cls.make_design("W01", SVG), cls.make_design("W02", "", "<b>x</b>")]
		cls.quotation = frappe.get_doc("Quotation", make_quotation(cls.project.name))

	@classmethod
	def make_design(cls, ref, svg, location="Hall"):
		design = frappe.get_doc(
			{
				"doctype": "Window Design",
				"project": cls.project.name,
				"design_ref": ref,
				"qty": 2,
				"location": location,
				"series_version": cls.version,
				"design_json": json.dumps(load("w01.json")),
			}
		).insert()
		design.db_set({"design_svg": svg, "pricing_warning_count": 0})
		return design

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def printed(self, doctype, name, print_format):
		return frappe.get_print(doctype, name, print_format=print_format)

	def test_quotation_format(self):
		html = self.printed("Quotation", self.quotation.name, QUOTATION_FORMAT)
		for ref in ("W01", "W02"):
			self.assertIn(ref, html)
		self.assertIn("Grand Total", html)
		self.assertIn(frappe.format(self.quotation.grand_total, {"fieldtype": "Currency"}), html)
		self.assertIn(DATA_URI, html)
		self.assertIn("Hilux Standard Terms", html)

	def test_project_formats(self):
		for print_format in PROJECT_FORMATS:
			html = self.printed("Fenestration Project", self.project.name, print_format)
			for ref in ("W01", "W02"):
				self.assertIn(ref, html)
			self.assertIn(DATA_URI, html)
			self.assertIn("CS400", html)

	def test_elevation_totals_and_estimate_sections(self):
		html = self.printed("Fenestration Project", self.project.name, "Fenestration Elevation")
		self.assertIn(self.project.name, html)
		html = self.printed("Fenestration Project", self.project.name, "Fenestration Estimate Confirmation")
		for text in ("Scaffolding", "Unloading", "Lifting", "Power and water", "Storage", "Revise"):
			self.assertIn(text, html)

	def test_no_inline_svg_and_placeholder(self):
		pages = [self.printed("Quotation", self.quotation.name, QUOTATION_FORMAT)] + [
			self.printed("Fenestration Project", self.project.name, name) for name in PROJECT_FORMATS
		]
		for html in pages:
			self.assertNotIn("<svg", html)
			self.assertIn(PLACEHOLDER, html)  # W02 has no drawing

	def test_pdfs(self):
		pages = [self.printed("Quotation", self.quotation.name, QUOTATION_FORMAT)] + [
			self.printed("Fenestration Project", self.project.name, name) for name in PROJECT_FORMATS
		]
		for html in pages:
			self.assertTrue(get_pdf(html).startswith(b"%PDF"))

	def test_svg_data_uri(self):
		self.assertEqual(fen_svg_data_uri(None), "")
		self.assertEqual(fen_svg_data_uri(""), "")
		self.assertTrue(fen_svg_data_uri(SVG).startswith(DATA_URI))

	def test_quotation_money_uses_quotation_currency(self):
		frappe.db.set_value("Quotation", self.quotation.name, "currency", "USD")
		self.addCleanup(frappe.db.set_value, "Quotation", self.quotation.name, "currency", "INR")
		html = self.printed("Quotation", self.quotation.name, QUOTATION_FORMAT)
		self.assertIn("$", html)
		self.assertNotIn("\u20b9", html)

	def test_quotation_prints_quotation_lines_not_current_design_price(self):
		windows = [row for row in self.quotation.items if row.item_code == "FEN-WINDOW"]
		basic = sum(row.amount for row in windows)
		design = self.designs[0]
		design.db_set({"unit_price": 12345.67, "line_total": 24691.34})
		html = self.printed("Quotation", self.quotation.name, QUOTATION_FORMAT)
		self.assertIn(frappe.format(basic, {"fieldtype": "Currency"}), html)
		self.assertIn(frappe.format(windows[0].rate, {"fieldtype": "Currency"}), html)
		self.assertNotIn("12,345.67", html)
		self.assertNotIn("24,691.34", html)

	def test_user_text_is_escaped(self):
		pages = [self.printed("Quotation", self.quotation.name, QUOTATION_FORMAT)] + [
			self.printed("Fenestration Project", self.project.name, name) for name in PROJECT_FORMATS
		]
		for html in pages:
			self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
			self.assertNotIn("<b>x</b>", html)

	def test_design_name_falls_back_to_typology(self):
		html = self.printed("Fenestration Project", self.project.name, "Fenestration Elevation")
		self.assertIn("2 sash", html)

	def test_project_formats_print_company_header(self):
		for print_format in PROJECT_FORMATS:
			html = self.printed("Fenestration Project", self.project.name, print_format)
			self.assertIn(test_quotation.COMPANY, html)
			self.assertIn("Karur", html)

	def test_grand_total_prints_rounded_total_and_adjustment(self):
		frappe.db.set_value(
			"Quotation", self.quotation.name, {"rounded_total": 99999, "rounding_adjustment": 0.5}
		)
		html = self.printed("Quotation", self.quotation.name, QUOTATION_FORMAT)
		self.assertIn("Rounding Adjustment", html)
		self.assertIn(frappe.format(99999, {"fieldtype": "Currency"}), html)

	def test_no_rounding_row_when_adjustment_is_zero(self):
		frappe.db.set_value("Quotation", self.quotation.name, {"rounded_total": 0, "rounding_adjustment": 0})
		html = self.printed("Quotation", self.quotation.name, QUOTATION_FORMAT)
		self.assertNotIn("Rounding Adjustment", html)
		self.assertIn(frappe.format(self.quotation.grand_total, {"fieldtype": "Currency"}), html)

	def test_quotation_skips_lines_of_deleted_designs(self):
		line = next(row for row in self.quotation.items if row.fen_window_design)
		frappe.db.set_value("Quotation Item", line.name, "fen_window_design", "NO-SUCH-DESIGN")
		self.addCleanup(frappe.db.set_value, "Quotation Item", line.name, "fen_window_design", line.fen_window_design)
		html = self.printed("Quotation", self.quotation.name, QUOTATION_FORMAT)
		self.assertIn("Grand Total", html)


ASSEMBLY_FORMATS = ("Fenestration Assembly Summary", "Fenestration Assembly Detail")
POSITION_ORDER = "BTLRHW"


class TestAssemblyPrints(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		test_quotation.TestQuotation.set_up_prices()
		test_quotation.TestQuotation.set_up_parties()
		cls.project = frappe.get_doc(
			{
				"doctype": "Fenestration Project",
				"project_title": "Assembly Test",
				"customer": test_quotation.IN_STATE_CUSTOMER,
				"company": test_quotation.COMPANY,
			}
		).insert()
		cls.make_design("W01", 1200, 930, 2, "<b>x</b>")
		cls.make_design("W02", 1200, 930, 3)
		cls.make_design("W03", 600, 600, 1)

	@classmethod
	def make_design(cls, ref, width, height, qty, name=""):
		spec = {**load("w01.json"), "width": width, "height": height}
		design = frappe.get_doc(
			{
				"doctype": "Window Design",
				"project": cls.project.name,
				"design_ref": ref,
				"design_name": name,
				"qty": qty,
				"series_version": cls.version,
				"design_json": json.dumps(spec),
			}
		).insert()
		design.db_set("pricing_warning_count", 0)

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def test_assembly_summary_groups_same_size(self):
		groups = print_context.assembly_summary(self.project)
		self.assertEqual(len(groups), 2)
		first, second = groups
		self.assertEqual((first["width"], first["height"]), (1200, 930))
		self.assertEqual(first["refs"], "W01, W02")
		self.assertEqual(first["qty"], 5)
		rows = {r["ref"]: r for r in print_context.design_rows(self.project)}
		self.assertAlmostEqual(first["area_sqft"], rows["W01"]["area_sqft"] * 2 + rows["W02"]["area_sqft"] * 3, 2)
		self.assertEqual((second["width"], second["height"], second["refs"]), (600, 600, "W03"))
		self.assertTrue(first["typology"])

	def test_assembly_detail_positions_and_panels(self):
		blocks = print_context.assembly_detail(self.project)
		block = next(b for b in blocks if b["ref"] == "W01")
		self.assertEqual((block["qty"], block["width"], block["height"]), (2, 1200, 930))
		pieces = block["pieces"]
		self.assertTrue(pieces[0]["panel"].startswith("F1"))
		self.assertLessEqual({p["position"] for p in pieces}, set(POSITION_ORDER))
		frame = [p["position"] for p in pieces if p["panel"] == "F1"]
		self.assertLess(frame.index("B"), frame.index("T"))
		keys = [(p["panel"], POSITION_ORDER.index(p["position"])) for p in pieces]
		self.assertEqual(keys, sorted(keys))
		self.assertTrue(all("/" in p["angles"] and p["profile_name"] and p["qty_per_window"] >= 1 for p in pieces))

	def test_assembly_prints_skip_superseded(self):
		w02 = frappe.db.get_value("Window Design", {"project": self.project.name, "design_ref": "W02"})
		w03 = frappe.db.get_value("Window Design", {"project": self.project.name, "design_ref": "W03"})
		frappe.db.savepoint("fen_superseded")
		self.addCleanup(frappe.db.rollback, save_point="fen_superseded")
		frappe.db.set_value("Window Design", w02, "superseded_by", w03)
		groups = print_context.assembly_summary(self.project)
		self.assertEqual(groups[0]["refs"], "W01")
		self.assertEqual(groups[0]["qty"], 2)
		self.assertEqual([b["ref"] for b in print_context.assembly_detail(self.project)], ["W01", "W03"])

	def test_assembly_prints_render(self):
		for print_format in ASSEMBLY_FORMATS:
			html = frappe.get_print("Fenestration Project", self.project.name, print_format=print_format)
			self.assertIn("W01", html)
			self.assertNotIn("<b>x</b>", html)
			self.assertIn(test_quotation.COMPANY, html)
			if print_format.endswith("Detail"):
				self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
			self.assertTrue(get_pdf(html).startswith(b"%PDF"))

