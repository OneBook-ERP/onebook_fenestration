import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.pricing.rate_sheet import _version_items
from onebook_fenestration.series_studio.readiness import readiness
from onebook_fenestration.series_studio.snapshot import get_snapshot
from onebook_fenestration.tests.test_snapshot import import_cs400

PRICE_LIST = "TST Readiness Cost"
STRUCTURE = "TPS Readiness"
GLASS_ITEM = "H401"
THICK_GLASS = "TSTG30"


class TestReadiness(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_cs400()

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()
		# the rollback restores the settings row but not the cached doc readiness() loaded
		frappe.clear_document_cache("Fenestration Settings", "Fenestration Settings")

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.make_settings()

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def make_settings(self):
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
		if not frappe.db.exists("Price Structure", STRUCTURE):
			frappe.get_doc(
				{
					"doctype": "Price Structure",
					"structure_name": STRUCTURE,
					"heads": [{"key": "flat", "label": "Flat", "calc": "Fixed", "rate": 1}],
				}
			).insert()
		finish = frappe.get_all("Profile Finish", pluck="name", limit=1)[0]
		settings = frappe.get_single("Fenestration Settings")
		settings.update(
			{"cost_price_list": PRICE_LIST, "default_price_structure": STRUCTURE, "default_finish": finish}
		)
		settings.save()

	def make_ready(self, version):
		"""Link, price, outline and perimeter everything the version uses.

		Idempotent: the rollback happens once per class, so earlier tests' changes are still there.
		"""
		# any existing Item will do for glasses the dev site has left unlinked
		for glass in frappe.get_all("Fenestration Glass", filters={"item": ["is", "not set"]}, pluck="name"):
			frappe.db.set_value("Fenestration Glass", glass, "item", GLASS_ITEM)
		profiles = {r.profile for r in frappe.get_doc("Series Version", version).member_rules}
		for code in profiles:
			frappe.db.set_value(
				"Fenestration Profile",
				code,
				{
					"item": code,
					"section_svg": "M0 0 L1 0",
					"visible_perimeter_mm": 10,
					"total_perimeter_mm": 20,
				},
			)
		for item_code in {item for item, _kind in _version_items(version)}:
			self.set_price(item_code, 100)

	def set_price(self, item_code, rate):
		if frappe.db.exists("Item Price", {"price_list": PRICE_LIST, "item_code": item_code}):
			return
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"price_list": PRICE_LIST,
				"item_code": item_code,
				"uom": frappe.db.get_value("Item", item_code, "stock_uom"),
				"price_list_rate": rate,
			}
		).insert()

	def draft_with_gasket_rule(self, *whens):
		"""A draft copy of CS400 whose only pane_side gasket rules apply when each of `whens` holds."""
		draft = frappe.copy_doc(frappe.get_doc("Series Version", self.version))
		draft.hardware_rules = [
			r for r in draft.hardware_rules if not (r.bom_group == "Gasket" and r.per == "pane_side")
		]
		for number, when in enumerate(whens):
			draft.append(
				"hardware_rules",
				{
					"rule_id": f"tst_glazing_gasket_{number}",
					"item": "H401",
					"item_name": "Test gasket",
					"per": "pane_side",
					"qty_expr": "1",
					"length_expr": "side_len",
					"when_expr": when,
					"bom_group": "Gasket",
				},
			)
		return draft.insert().name

	def checks(self, version):
		return {c["check"]: c for c in readiness(version)["checks"]}

	def test_ready_version_is_ok(self):
		# the dev site's glass catalogue is wider than CS400's 5-6 mm glazing gasket, so glaze every glass
		version = self.draft_with_gasket_rule("True")
		self.make_ready(version)
		report = readiness(version)
		self.assertTrue(report["ok"])
		statuses = {c["check"]: c["status"] for c in report["checks"]}
		self.assertEqual(
			statuses,
			{
				name: "ok"
				for name in ("settings", "item_links", "prices", "gasket_rules", "perimeters", "outlines")
			},
		)

	def test_missing_settings_block(self):
		frappe.db.set_single_value("Fenestration Settings", "default_finish", None)
		check = self.checks(self.version)["settings"]
		self.assertEqual(check["status"], "block")
		self.assertTrue(check["items"])
		self.assertFalse(readiness(self.version)["ok"])

	def test_missing_price_blocks(self):
		self.make_ready(self.version)
		frappe.db.delete("Item Price", {"price_list": PRICE_LIST, "item_code": "E104156"})
		report = readiness(self.version)
		check = {c["check"]: c for c in report["checks"]}["prices"]
		self.assertEqual(check["status"], "block")
		self.assertEqual(check["items"], ["E104156"])
		self.assertFalse(report["ok"])

	def test_unlinked_profile_blocks(self):
		self.make_ready(self.version)
		frappe.db.set_value("Fenestration Profile", "E104159", "item", None)
		check = self.checks(self.version)["item_links"]
		self.assertEqual((check["status"], check["items"]), ("block", ["E104159"]))

	def make_thick_glass(self):
		if not frappe.db.exists("Fenestration Glass", THICK_GLASS):
			frappe.get_doc(
				{
					"doctype": "Fenestration Glass",
					"glass_code": THICK_GLASS,
					"glass_name": "Test 30mm",
					"thickness_mm": 30,
				}
			).insert()

	def test_glass_without_gasket_warns(self):
		self.make_thick_glass()
		draft = self.draft_with_gasket_rule("glass_t <= 8")
		check = self.checks(draft)["gasket_rules"]
		self.assertEqual(check["status"], "warn")
		self.assertIn(f"{THICK_GLASS} (fixed)", check["items"])
		self.assertIn(f"{THICK_GLASS} (sash)", check["items"])
		thin = [code for code, glass in get_snapshot(draft).glasses.items() if glass.thickness_mm <= 8]
		self.assertTrue(thin)
		flagged = {item.rsplit(" (", 1)[0] for item in check["items"]}
		self.assertFalse(set(thin) & flagged)

	def test_fixed_only_gasket_still_warns_for_sash(self):
		# CS4800 style: one rule for any fixed glass, one for thin glass anywhere
		self.make_thick_glass()
		draft = self.draft_with_gasket_rule("not in_sash", "glass_t <= 8")
		items = self.checks(draft)["gasket_rules"]["items"]
		self.assertIn(f"{THICK_GLASS} (sash)", items)
		self.assertNotIn(f"{THICK_GLASS} (fixed)", items)

	def test_missing_outline_warns(self):
		self.make_ready(self.version)
		frappe.db.set_value("Fenestration Profile", "E104160", "section_svg", None)
		frappe.db.set_value(
			"Fenestration Profile", "E104159", {"visible_perimeter_mm": 0, "total_perimeter_mm": 0}
		)
		report = readiness(self.version)
		checks = {c["check"]: c for c in report["checks"]}
		self.assertEqual((checks["outlines"]["status"], checks["outlines"]["items"]), ("warn", ["E104160"]))
		self.assertEqual(
			(checks["perimeters"]["status"], checks["perimeters"]["items"]), ("warn", ["E104159"])
		)
		self.assertTrue(report["ok"])

	def test_needs_read_permission(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			readiness(self.version)

	def test_incomplete_draft_is_a_blocking_check(self):
		draft = frappe.copy_doc(frappe.get_doc("Series Version", self.version))
		draft.docstatus = 0
		draft.insert()
		frappe.db.set_value("Series Member Rule", draft.member_rules[0].name, "profile", "NO-SUCH-PROFILE")
		report = readiness(draft.name)
		self.assertFalse(report["ok"])
		self.assertEqual((report["checks"][0]["check"], report["checks"][0]["status"]), ("rules", "block"))
