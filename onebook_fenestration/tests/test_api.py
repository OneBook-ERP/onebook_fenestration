import json

import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.api.design import compute_design, get_fenestration_defaults
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.tests.test_snapshot import load

SALES_EMAIL = "fen.sales@example.com"


class TestComputeDesignApi(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_api_w01(self):
		out = compute_design(json.dumps(load("w01.json")), self.version)
		self.assertIs(out["ok"], True)
		self.assertEqual(out["result"]["area_sqft"], 12.013)

	def test_api_returns_pricing(self):
		out = compute_design(load("w01.json"), self.version)
		pricing = out["result"]["pricing"]
		self.assertTrue(pricing["lines"])
		self.assertGreater(pricing["unit_price"], 0)
		self.assertIn("rate_per_sqft", pricing)

	def test_api_pricing_issues_join_result_issues(self):
		frappe.db.set_single_value("Fenestration Settings", "cost_price_list", None)
		out = compute_design(load("w01.json"), self.version)
		self.assertTrue(any(i["code"] == "no_rate" for i in out["result"]["issues"]))

	def test_api_unknown_price_structure_is_series_error(self):
		out = compute_design(load("w01.json"), self.version, price_structure="Nope")
		self.assertIs(out["ok"], False)
		self.assertEqual(out["error_type"], "series")

	def test_api_bad_design_returns_error(self):
		design = load("w01.json")
		design["root"]["at"] = [0]
		out = compute_design(design, self.version)
		self.assertIs(out["ok"], False)
		self.assertEqual(out["error_type"], "design")
		self.assertIn("F1", out["message"])

	def test_fenestration_defaults(self):
		frappe.db.set_single_value("Fenestration Settings", "default_finish", "BROWN-5104")
		frappe.set_user(SALES_EMAIL)
		out = get_fenestration_defaults()
		self.assertEqual(out["default_finish"], "BROWN-5104")
		self.assertIn("default_price_structure", out)

	def test_api_invalid_json(self):
		out = compute_design("{", self.version)
		self.assertEqual(out["error_type"], "design")
		self.assertEqual(out["message"], "design is not valid JSON")

	def test_api_requires_read_permission(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			compute_design(load("w01.json"), self.version)

	def test_api_sales_user_can_compute(self):
		if not frappe.db.exists("User", SALES_EMAIL):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": SALES_EMAIL,
					"first_name": "Fen Sales",
					"send_welcome_email": 0,
					"roles": [{"role": "Sales User"}],
				}
			).insert()
		frappe.set_user(SALES_EMAIL)
		out = compute_design(load("w01.json"), self.version)
		self.assertIs(out["ok"], True)

	def test_api_rejects_draft_version(self):
		draft = frappe.get_doc({"doctype": "Series Version", "series": "CS400"}).insert()
		out = compute_design(load("w01.json"), draft.name)
		self.assertEqual(
			out, {"ok": False, "error_type": "series", "message": "Series Version must be published"}
		)

	def test_api_rejects_missing_version(self):
		out = compute_design(load("w01.json"), "NO-SUCH-VERSION")
		self.assertEqual(out, {"ok": False, "error_type": "series", "message": "Series Version not found"})
