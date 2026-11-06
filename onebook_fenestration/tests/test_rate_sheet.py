import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today
from frappe.utils.xlsxutils import make_xlsx

from onebook_fenestration.pricing import rate_sheet
from onebook_fenestration.pricing.rate_sheet import import_rate_sheet, rate_sheet_rows, series_items
from onebook_fenestration.tests.test_snapshot import import_cs400

HEADER = ["item_code", "new_rate", "valid_from"]


class TestRateSheet(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_cs400()

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.price_list = f"TST {self._testMethodName}"
		frappe.get_doc(
			{"doctype": "Price List", "price_list_name": self.price_list, "currency": "INR", "buying": 1, "enabled": 1}
		).insert()
		frappe.db.set_single_value("Fenestration Settings", "cost_price_list", self.price_list)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def upload(self, rows):
		content = make_xlsx([HEADER, *rows], "Rates").getvalue()
		return frappe.get_doc(
			{"doctype": "File", "file_name": f"{self._testMethodName}.xlsx", "content": content, "is_private": 1}
		).insert().file_url

	def prices(self, item_code):
		return frappe.get_all(
			"Item Price",
			filters={"price_list": self.price_list, "item_code": item_code},
			fields=["price_list_rate", "valid_from", "uom"],
		)

	def test_rows_cover_profiles_glass_and_rule_items(self):
		by_code = {r["item_code"]: r for r in rate_sheet_rows([self.version])}
		profile = by_code["E104156"]
		self.assertEqual((profile["kind"], profile["rate_basis"], profile["series"]), ("Profile", "per kg", "CS400"))
		self.assertEqual(profile["uom"], "Kg")
		glass_item = frappe.db.get_value("Fenestration Glass", "6CTG", "item")
		self.assertEqual((by_code[glass_item]["kind"], by_code[glass_item]["rate_basis"]), ("Glass", "per m2"))
		self.assertEqual(by_code["H401"]["kind"], "Hardware")
		self.assertEqual(by_code["H401"]["rate_basis"], f"per {by_code['H401']['uom']}")
		gaskets = {r["item_code"] for r in by_code.values() if r["kind"] == "Gasket"}
		self.assertTrue(gaskets)
		self.assertEqual(len(by_code), len(rate_sheet_rows([self.version])))

	def test_current_rate_comes_from_cost_price_list(self):
		self.assertIn(rate_sheet_rows([self.version])[0]["current_rate"], (None, ""))
		import_rate_sheet(self.upload([["E104156", 310.5, None]]))
		row = next(r for r in rate_sheet_rows([self.version]) if r["item_code"] == "E104156")
		self.assertEqual(row["current_rate"], 310.5)

	def test_series_items_defaults_to_submitted_versions(self):
		codes = {r["item_code"] for r in series_items()}
		self.assertTrue({r["item_code"] for r in series_items([self.version])} <= codes)

	def test_import_creates_and_updates(self):
		result = import_rate_sheet(self.upload([["E104156", 300, None], ["H401", 5, None]]))
		self.assertEqual((result["created"], result["updated"], result["skipped"]), (2, 0, []))
		self.assertEqual(self.prices("E104156")[0].price_list_rate, 300)
		self.assertEqual(str(self.prices("E104156")[0].valid_from), today())
		self.assertEqual(self.prices("E104156")[0].uom, "Kg")
		result = import_rate_sheet(self.upload([["E104156", 320, None]]))
		self.assertEqual((result["created"], result["updated"]), (0, 1))
		self.assertEqual(len(self.prices("E104156")), 1)
		self.assertEqual(self.prices("E104156")[0].price_list_rate, 320)
		result = import_rate_sheet(self.upload([["E104156", 340, "2030-01-01"]]))
		self.assertEqual(result["created"], 1)
		self.assertEqual(len(self.prices("E104156")), 2)

	def test_reimport_is_idempotent(self):
		rows = [["E104156", 300, None], ["H401", 5, "2030-01-01"]]
		import_rate_sheet(self.upload(rows))
		count = frappe.db.count("Item Price", {"price_list": self.price_list})
		result = import_rate_sheet(self.upload(rows))
		self.assertEqual((result["created"], result["updated"], result["unchanged"]), (0, 0, 2))
		self.assertEqual(frappe.db.count("Item Price", {"price_list": self.price_list}), count)

	def test_blank_rate_rows_are_ignored(self):
		result = import_rate_sheet(self.upload([["E104156", None, None]]))
		self.assertEqual((result["created"], result["updated"], result["unchanged"], result["skipped"]), (0, 0, 0, []))

	def test_import_reports_bad_rows(self):
		rows = [["NOPE-ITEM", 10, None], ["E104156", "abc", None], ["H401", 0, None], ["H401", -3, None], ["E104159", 7, None]]
		result = import_rate_sheet(self.upload(rows))
		self.assertEqual(result["created"], 1)
		self.assertEqual([s["row"] for s in result["skipped"]], [2, 3, 4, 5])
		self.assertEqual(result["skipped"][0]["item_code"], "NOPE-ITEM")
		self.assertTrue(all(s["reason"] for s in result["skipped"]))

	def test_import_requires_price_list(self):
		frappe.db.set_single_value("Fenestration Settings", "cost_price_list", None)
		with self.assertRaises(frappe.ValidationError):
			import_rate_sheet(self.upload([["E104156", 300, None]]))

	def test_download_builds_xlsx(self):
		rate_sheet.download_rate_sheet()
		self.assertEqual(frappe.response["type"], "binary")
		self.assertTrue(frappe.response["filename"].endswith(".xlsx"))
		self.assertTrue(frappe.response["filecontent"])

	def test_rate_sheet_needs_role(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			rate_sheet_rows()
		with self.assertRaises(frappe.PermissionError):
			import_rate_sheet("/private/files/x.xlsx")
		with self.assertRaises(frappe.PermissionError):
			rate_sheet.download_rate_sheet()

	def test_import_rejects_bad_files(self):
		with self.assertRaises(frappe.ValidationError):
			import_rate_sheet("/private/files/does-not-exist.xlsx")
		for name, content in (("notes.txt", b"hello"), ("fake.xlsx", b"not a zip")):
			url = frappe.get_doc({"doctype": "File", "file_name": name, "content": content, "is_private": 1}).insert().file_url
			with self.assertRaises(frappe.ValidationError):
				import_rate_sheet(url)

	def test_import_rejects_unreadable_attached_file(self):
		user = "tst-rate-sheet@example.com"
		frappe.get_doc(
			{"doctype": "User", "email": user, "first_name": "Tst", "send_welcome_email": 0, "roles": [{"role": "Fenestration Engineer"}]}
		).insert()
		content = make_xlsx([HEADER, ["E104156", 300, None]], "Rates").getvalue()
		url = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "attached.xlsx",
				"content": content,
				"is_private": 1,
				"attached_to_doctype": "User",
				"attached_to_name": "Administrator",
			}
		).insert().file_url
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			import_rate_sheet(url)

	def test_other_uom_price_is_left_alone(self):
		item = frappe.get_doc("Item", "H401")
		if not any(row.uom == "Box" for row in item.uoms):
			item.append("uoms", {"uom": "Box", "conversion_factor": 10})
			item.save()
		frappe.get_doc(
			{"doctype": "Item Price", "price_list": self.price_list, "item_code": "H401", "uom": "Box", "price_list_rate": 9, "valid_from": today()}
		).insert()
		result = import_rate_sheet(self.upload([["H401", 5, None]]))
		self.assertEqual(result["created"], 1)
		self.assertEqual(sorted(p.price_list_rate for p in self.prices("H401")), [5, 9])

	def test_explicit_versions_must_be_submitted(self):
		draft = frappe.get_doc(frappe.get_doc("Series Version", self.version).as_dict() | {"name": None, "docstatus": 0, "amended_from": None})
		draft.insert()
		self.assertEqual(series_items([draft.name]), [])

	def make_engineer(self):
		user = "tst-engineer-only@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{"doctype": "User", "email": user, "first_name": "Tst", "send_welcome_email": 0, "roles": [{"role": "Fenestration Engineer"}]}
			).insert()
		return user

	def test_engineer_without_item_price_rights_can_import(self):
		user = self.make_engineer()
		frappe.set_user(user)
		self.assertEqual(import_rate_sheet(self.upload([["E104156", 300, None]]))["created"], 1)
		self.assertEqual(import_rate_sheet(self.upload([["E104156", 310, None]]))["updated"], 1)
		self.assertEqual(self.prices("E104156")[0].price_list_rate, 310)

	def test_unattached_file_of_another_user_is_refused(self):
		url = self.upload([["E104156", 300, None]])
		frappe.set_user(self.make_engineer())
		with self.assertRaises(frappe.PermissionError):
			import_rate_sheet(url)

	def test_rate_parsing(self):
		result = import_rate_sheet(
			self.upload([["E104156", "1,234.50", None], ["H401", True, None], ["E104159", "inf", None], ["E104160", "nan", None]])
		)
		self.assertEqual(result["created"], 1)
		self.assertEqual(self.prices("E104156")[0].price_list_rate, 1234.5)
		self.assertEqual([s["row"] for s in result["skipped"]], [3, 4, 5])

	def test_plain_desk_user_needs_role(self):
		user = "tst-plain-desk@example.com"
		frappe.get_doc({"doctype": "User", "email": user, "first_name": "Plain", "send_welcome_email": 0}).insert()
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			rate_sheet_rows()
