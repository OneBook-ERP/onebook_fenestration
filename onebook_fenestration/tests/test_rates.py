import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from onebook_fenestration.engine import compute, price
from onebook_fenestration.pricing.rates import _item_prices, build_pricing_input, price_design
from onebook_fenestration.series_studio.snapshot import get_snapshot
from onebook_fenestration.tests.test_snapshot import import_cs400, load

PRICE_LIST = "Fen Test Cost"
GLASS_ITEM = "FEN-GLASS-6CTG"


class TestRates(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.version = import_cs400()
		cls.snapshot = get_snapshot(cls.version)
		cls.result = compute(load("w01.json"), cls.snapshot)
		cls.make_price_list()
		cls.make_glass_item()
		for code in ("E104156", "E104159", "E104160"):
			cls.set_price(code, 300)
		cls.set_price("H401", 5)
		cls.set_price(GLASS_ITEM, 1000)

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	@classmethod
	def make_price_list(cls):
		if not frappe.db.exists("Price List", PRICE_LIST):
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": PRICE_LIST,
					"currency": frappe.db.get_default("currency") or "INR",
					"buying": 1,
					"enabled": 1,
				}
			).insert()

	@classmethod
	def make_glass_item(cls):
		if not frappe.db.exists("Item", GLASS_ITEM):
			item = {
				"doctype": "Item",
				"item_code": GLASS_ITEM,
				"item_name": GLASS_ITEM,
				"item_group": "Fenestration",
				"stock_uom": "Nos",
			}
			if frappe.get_meta("Item").has_field("gst_hsn_code"):
				if not frappe.db.exists("GST HSN Code", "700711"):
					frappe.get_doc(
						{"doctype": "GST HSN Code", "hsn_code": "700711", "description": "Toughened glass"}
					).insert()
				item["gst_hsn_code"] = "700711"
			frappe.get_doc(item).insert()
		frappe.db.set_value("Fenestration Glass", "6CTG", "item", GLASS_ITEM)

	@classmethod
	def set_price(cls, item_code, rate):
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"price_list": PRICE_LIST,
				"item_code": item_code,
				"price_list_rate": rate,
			}
		).insert()

	def add_price(self, price_list, rate, **extra):
		frappe.get_doc(
			{"doctype": "Item Price", "price_list": price_list, "item_code": "H401", "uom": "Nos", "price_list_rate": rate, **extra}
		).insert(ignore_links=True)

	def validity_list(self):
		name = f"Fen Test {self._testMethodName}"
		if not frappe.db.exists("Price List", name):
			frappe.get_doc(
				{"doctype": "Price List", "price_list_name": name, "currency": "INR", "buying": 1, "selling": 1, "enabled": 1}
			).insert()
		return name

	def test_expired_price_is_ignored(self):
		pl = self.validity_list()
		self.add_price(pl, 10, valid_from=add_days(today(), -30))
		self.add_price(pl, 99, valid_from=add_days(today(), -20), valid_upto=add_days(today(), -1))
		self.add_price(pl, 77, valid_from=add_days(today(), 5))
		self.assertEqual(_item_prices(pl, {"H401"}), {"H401": 10})

	def test_customer_specific_price_is_ignored(self):
		pl = self.validity_list()
		self.add_price(pl, 10)
		self.add_price(pl, 99, customer="Fen Test Customer")
		self.assertEqual(_item_prices(pl, {"H401"}), {"H401": 10})

	def test_latest_valid_from_wins(self):
		pl = self.validity_list()
		self.add_price(pl, 10, valid_from=add_days(today(), -30))
		self.add_price(pl, 20, valid_from=add_days(today(), -10))
		self.assertEqual(_item_prices(pl, {"H401"}), {"H401": 20})

	def build(self, price_list=PRICE_LIST):
		return build_pricing_input(self.snapshot, self.result, "GREY", "Standard", price_list)

	def test_rates_are_picked_up(self):
		pricing = self.build()
		self.assertEqual(pricing.profile_rates["E104156"], 300)
		self.assertEqual(pricing.item_rates["H401"], 5)
		self.assertEqual(pricing.glass_rates["6CTG"], 1000)
		self.assertEqual(pricing.finish_type, "Powder Coat")
		self.assertTrue(pricing.heads)

	def test_missing_price_is_reported(self):
		pricing = self.build()
		self.assertEqual(pricing.item_rates["H912"], 0)
		self.assertIn(f"H912 ({PRICE_LIST})", pricing.missing)

	def test_unknown_finish_is_mill(self):
		pricing = build_pricing_input(self.snapshot, self.result, "NOPE", "Standard", PRICE_LIST)
		self.assertEqual(pricing.finish_type, "Mill")

	def test_no_price_list(self):
		frappe.db.set_single_value("Fenestration Settings", "cost_price_list", None)
		pricing = build_pricing_input(self.snapshot, self.result, "GREY", "Standard")
		self.assertEqual(pricing.missing, ("cost price list not configured",))
		self.assertEqual(set(pricing.profile_rates.values()), {0})
		self.assertEqual(set(pricing.item_rates.values()) | set(pricing.glass_rates.values()), {0})

	def test_price_design_w01(self):
		frappe.db.set_single_value("Fenestration Settings", "cost_price_list", PRICE_LIST)
		result, breakdown = price_design(load("w01.json"), self.version)
		self.assertGreater(breakdown.unit_price, 0)
		self.assertEqual(result.area_sqft, 12.013)
		self.assertTrue(any(i.code == "no_rate" and "H912" in i.message for i in breakdown.issues))

	def test_live_perimeters_override_zero_snapshot(self):
		self.assertEqual(self.snapshot.profiles["E104156"].visible_perimeter_mm, 0)
		frappe.db.set_value("Fenestration Profile", "E104156", {"visible_perimeter_mm": 150, "total_perimeter_mm": 300})
		pricing = self.build()
		self.assertEqual(pricing.profile_perimeters["E104156"], (150, 300))
		breakdown = price(self.result, self.snapshot, pricing)
		self.assertGreater(breakdown.variables["visible_perimeter_sqft"], 0)
		self.assertFalse(any(i.code == "no_perimeter" and "E104156" in i.message for i in breakdown.issues))

	def test_finish_surcharge_pct_is_passed(self):
		frappe.db.set_value("Profile Finish", "WOOD", "surcharge_pct", 12)
		pricing = build_pricing_input(self.snapshot, self.result, "WOOD", "Standard", PRICE_LIST)
		self.assertEqual(pricing.finish_surcharge_pct, 12)
		self.assertEqual(self.build().finish_surcharge_pct, 0)
