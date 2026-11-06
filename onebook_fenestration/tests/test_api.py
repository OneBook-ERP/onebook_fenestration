import json
import unittest.mock

import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.api.design import compute_design, cross_section, get_fenestration_defaults
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

	def test_api_returns_series_glasses_and_defaults(self):
		from onebook_fenestration.series_studio.snapshot import get_snapshot

		series = compute_design(load("w01.json"), self.version)["series"]
		self.assertEqual(series["glasses"], sorted(get_snapshot(self.version).glasses))
		self.assertEqual(series["defaults"], {"limiter": False, "mesh": False})

	def test_api_series_defaults_follow_constants(self):
		from onebook_fenestration.series_studio.snapshot import get_snapshot
		from onebook_fenestration.api.design import series_info

		snap = get_snapshot(self.version)
		snap.constants.update({"default_limiter": 1, "default_mesh": 0})
		with unittest.mock.patch("onebook_fenestration.api.design.get_snapshot", return_value=snap):
			self.assertEqual(series_info(self.version)["defaults"], {"limiter": True, "mesh": False})

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

	def test_api_missing_defaults(self):
		frappe.db.set_single_value("Fenestration Settings", "default_finish", None)
		try:
			out = compute_design(load("w01.json"), self.version)
		finally:
			frappe.db.set_single_value("Fenestration Settings", "default_finish", "GREY")
		self.assertEqual(
			out,
			{"ok": False, "error_type": "series", "message": "Set a default price structure and finish in Fenestration Settings"},
		)


CUT_SERIES = "TSTCUT"
# The CS400 fixture's profiles renamed so the test owns every Fenestration Profile it touches.
CUT_PROFILES = {"E104156": "TSTCUT-F", "E104160": "TSTCUT-S", "E104159": "TSTCUT-M", "CS4807": "TSTCUT-B"}


class TestCrossSectionApi(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		data = json.loads(json.dumps(load("cs400_snapshot.json")))
		for old, new in CUT_PROFILES.items():
			data["profiles"][new] = data["profiles"].pop(old)
		for rule in data["member_rules"]:
			rule["profile"] = CUT_PROFILES[rule["profile"]]
		data["code"] = CUT_SERIES
		cls.version = import_snapshot_json(CUT_SERIES, data, "Cross section test series")
		frappe.db.set_value(
			"Fenestration Profile", "TSTCUT-F", {"section_svg": "M 0 0 L 50 0 L 50 70 Z", "width_mm": 50, "depth_mm": 70}
		)

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_cross_section_api_returns_outlines(self):
		out = cross_section(json.dumps(load("w01.json")), self.version, "h")
		self.assertIs(out["ok"], True)
		result = out["result"]
		self.assertEqual((result["axis"], result["at"], result["length"]), ("h", 610, 915))
		frame = result["pieces"][0]
		self.assertEqual(
			frame,
			{"kind": "profile", "code": "TSTCUT-F", "role": "frame", "panel": "F1", "start": 0, "end": 50, "mirrored": False, "thickness": 0},
		)
		self.assertEqual(out["outlines"], {"TSTCUT-F": {"svg": "M 0 0 L 50 0 L 50 70 Z", "width": 50, "depth": 70}})
		missing = sorted(i["message"].split()[1] for i in result["issues"] if i["code"] == "no_section_width")
		self.assertEqual(missing, ["TSTCUT-M", "TSTCUT-S"])
		self.assertIn({"start": 0, "end": 915, "label": "915", "chain": "overall"}, result["dims"])

	def test_api_returns_rotated_outline(self):
		frappe.db.set_value("Fenestration Profile", "TSTCUT-F", {"section_rotation": "90", "width_mm": 70, "depth_mm": 50})
		try:
			out = cross_section(load("w01.json"), self.version, "h")
		finally:
			frappe.db.set_value(
				"Fenestration Profile", "TSTCUT-F", {"section_rotation": "0", "width_mm": 50, "depth_mm": 70}
			)
		self.assertEqual(out["outlines"], {"TSTCUT-F": {"svg": "M 70 0 L 70 50 L 0 50 Z", "width": 70, "depth": 50}})
		self.assertEqual(out["result"]["pieces"][0]["end"], 70)

	def test_cross_section_api_errors(self):
		self.assertEqual(cross_section(load("w01.json"), self.version, "x")["error_type"], "design")
		self.assertEqual(cross_section("{", self.version, "h")["error_type"], "design")
		self.assertEqual(cross_section(load("w01.json"), "NO-SUCH-VERSION", "h")["error_type"], "series")

	def test_cross_section_api_accepts_string_at(self):
		out = cross_section(load("w01.json"), self.version, "v", "457.5")
		self.assertEqual(out["result"]["at"], 686.25)

	def test_cross_section_api_requires_read_permission(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			cross_section(load("w01.json"), self.version, "h")
