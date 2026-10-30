import json
from unittest.mock import patch
from collections import defaultdict

import frappe
from erpnext.selling.doctype.quotation.quotation import make_sales_order
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.cutting import Piece, optimize, wastage
from onebook_fenestration.fenestration.quotation import make_quotation
from onebook_fenestration.production.cutting_plan import collect_pieces, parse_bar_lengths, stored_value
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.series_studio.snapshot import get_snapshot
from onebook_fenestration.setup.install import setup_production_items
from onebook_fenestration.tests import test_quotation
from onebook_fenestration.tests.test_snapshot import load

HELPERS = ("set_up_prices", "set_up_parties")
STATIC_HELPERS = ("make_customer", "make_address")
COMPANY = test_quotation.COMPANY
PRINT_FORMAT = "Profile Cutting Schedule"
SHORT_SERIES = "ZZCUT"
SHORT_SUFFIX = "-ZC"


class TestCuttingPlan(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for name in HELPERS:
			setattr(cls, name, classmethod(getattr(test_quotation.TestQuotation, name).__func__))
		for name in STATIC_HELPERS:
			setattr(cls, name, staticmethod(getattr(test_quotation.TestQuotation, name)))
		cls.version = import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")
		cls.set_up_prices()
		cls.set_up_parties()
		setup_production_items()
		cls.snapshot = get_snapshot(cls.version)

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

	def short_bar_version(self) -> str:
		"""A test-only series whose profiles come in 1000 mm bars; the CS400 dev profiles stay untouched."""
		data = load("cs400_snapshot.json")
		for code in list(data["profiles"]):
			data["profiles"][code]["bar_lengths"] = [1000]
		text = json.dumps(data)
		for code in data["profiles"]:
			text = text.replace(f'"{code}"', f'"{code}{SHORT_SUFFIX}"')
		return import_snapshot_json(SHORT_SERIES, json.loads(text), "Short Bar Test")

	def submitted_order(self, specs, version=None, transport=0):
		"""Submit a Sales Order with one design line per (ref, finish, design_qty, order_qty)."""
		project = frappe.get_doc(
			{
				"doctype": "Fenestration Project",
				"project_title": "Cutting Test",
				"customer": test_quotation.IN_STATE_CUSTOMER,
				"company": COMPANY,
				"transport_charges": transport,
			}
		).insert()
		designs = []
		for ref, finish, design_qty, _order_qty in specs:
			design = frappe.get_doc(
				{
					"doctype": "Window Design",
					"project": project.name,
					"design_ref": ref,
					"qty": design_qty,
					"series_version": version or self.version,
					"finish": finish,
					"design_json": json.dumps(load("w01.json")),
				}
			).insert()
			design.db_set("pricing_warning_count", 0)
			designs.append(design)
		quotation = frappe.get_doc("Quotation", make_quotation(project.name))
		quotation.submit()
		order = frappe.get_doc(make_sales_order(quotation.name))
		order.delivery_date = add_days(nowdate(), 30)
		by_design = {spec[0]: spec[3] for spec in specs}
		for line in order.items:
			if line.fen_window_design:
				line.qty = by_design[frappe.db.get_value("Window Design", line.fen_window_design, "design_ref")]
		order.insert()
		order.submit()
		return order, designs

	def members(self, version=None):
		return compute(load("w01.json"), get_snapshot(version or self.version)).members

	def new_plan(self, orders):
		return frappe.get_doc(
			{"doctype": "Cutting Plan", "company": COMPANY, "orders": [{"sales_order": o} for o in orders]}
		)

	def test_groups_by_profile_and_finish(self):
		order, _ = self.submitted_order([("W01", "GREY", 1, 1), ("W02", "BROWN-5104", 1, 1)])
		groups = collect_pieces([order.name])
		profiles = {m.profile for m in self.members()}
		self.assertEqual(set(groups), {(p, f) for p in profiles for f in ("GREY", "BROWN-5104")})
		plan = self.new_plan([order.name])
		plan.insert()
		self.assertEqual({(r.profile, r.finish) for r in plan.summary}, set(groups))
		self.assertEqual(
			[(g["profile"], g["finish"]) for g in json.loads(plan.plan_json)["groups"]], sorted(groups)
		)

	def test_order_qty_drives_piece_count(self):
		order, _ = self.submitted_order([("W01", "GREY", 4, 2)])
		groups = collect_pieces([order.name])
		per_profile = defaultdict(int)
		for member in self.members():
			per_profile[member.profile] += 1
		for (profile, _finish), pieces in groups.items():
			self.assertEqual(len(pieces), 2 * per_profile[profile])
		self.assertEqual(sum(len(v) for v in groups.values()), 2 * len(self.members()))
		labels = [p.label for p in next(iter(groups.values()))]
		self.assertEqual(sum(label.endswith(" #2") for label in labels), per_profile[next(iter(groups))[0]])
		self.assertTrue(any(label.startswith("W01 ") and label.endswith(" #2") for label in labels))
		self.assertFalse(any(label.endswith(" #3") for label in labels))
		self.assertTrue(any(label.startswith("W01 ") and not label.endswith(("#1", "#2")) for label in labels))

	def test_non_design_lines_skipped(self):
		order, _ = self.submitted_order([("W01", "GREY", 1, 1)], transport=500)
		self.assertIn("FEN-TRANSPORT", [i.item_code for i in order.items])
		groups = collect_pieces([order.name])
		per_profile = defaultdict(int)
		for member in self.members():
			per_profile[member.profile] += 1
		self.assertEqual({k: len(v) for k, v in groups.items()}, {(p, "GREY"): n for p, n in per_profile.items()})

	def test_summary_matches_engine_wastage(self):
		order, _ = self.submitted_order([("W01", "GREY", 2, 2)])
		plan = self.new_plan([order.name])
		plan.insert()
		profile, finish = self.members()[0].profile, "GREY"
		pieces = collect_pieces([order.name])[(profile, finish)]
		info = frappe.db.get_value("Fenestration Profile", profile, ("kg_per_m", "bar_lengths"), as_dict=True)
		expected = wastage(
			optimize(pieces, parse_bar_lengths(info.bar_lengths, profile), kerf=10, min_rest=500), info.kg_per_m
		)
		row = next(r for r in plan.summary if r.profile == profile and r.finish == finish)
		for key in ("bar_count", "pieces", "cut_mm", "rest_mm", "waste_mm", "kg_bars", "kg_used",
			"waste_pct_incl_rest", "waste_pct_excl_rest", "kg_per_m"):
			self.assertAlmostEqual(row.get(key), expected[key], places=3, msg=key)
		self.assertEqual(row.bars, ", ".join(f"{k:g} × {v}" for k, v in sorted(expected["bars"].items())))
		self.assertEqual(plan.unplaced_count, 0)

	def test_unplaced_piece_is_reported(self):
		version = self.short_bar_version()
		self.addCleanup(frappe.cache.hdel, "fen_snapshot", version)
		order, _ = self.submitted_order([("W01", "GREY", 1, 1)], version=version)
		plan = self.new_plan([order.name])
		plan.insert()
		self.assertGreater(plan.unplaced_count, 0)
		self.assertTrue(frappe.db.exists("Cutting Plan", plan.name))
		html = frappe.get_print("Cutting Plan", plan.name, PRINT_FORMAT)
		self.assertIn("Profile Cutting Schedule", html)
		self.assertIn("<b>Unplaced</b>", html)

	def test_draft_orders_rejected(self):
		order, _ = self.submitted_order([("W01", "GREY", 1, 1)])
		order.cancel()
		with self.assertRaises(frappe.ValidationError):
			self.new_plan([order.name]).insert()

	def test_submitted_plan_is_frozen(self):
		order, _ = self.submitted_order([("W01", "GREY", 1, 1)])
		plan = self.new_plan([order.name])
		plan.insert()
		plan.submit()
		before = plan.plan_json
		self.addCleanup(frappe.db.set_single_value, "Fenestration Settings", "cut_kerf_mm", 10)
		frappe.db.set_single_value("Fenestration Settings", "cut_kerf_mm", 25)
		reloaded = frappe.get_doc("Cutting Plan", plan.name)
		self.assertEqual(reloaded.plan_json, before)
		self.assertEqual(reloaded.kerf_mm, 10)

	def test_print_renders(self):
		order, _ = self.submitted_order([("W01", "GREY", 1, 1)])
		plan = self.new_plan([order.name])
		plan.insert()
		html = frappe.get_print("Cutting Plan", plan.name, PRINT_FORMAT)
		self.assertIn("E104156", html)
		self.assertIn("Rest", html)
		self.assertIn("Wastage Summary", html)
		self.assertIn("Waste % incl. Rest", html)
		self.assertIn("GREY", html)

	def set_setting(self, fieldname, value):
		old = frappe.db.get_single_value("Fenestration Settings", fieldname)
		self.addCleanup(frappe.db.set_single_value, "Fenestration Settings", fieldname, old)
		frappe.db.set_single_value("Fenestration Settings", fieldname, value)

	def test_settings_seeded(self):
		for fieldname, value in (("cut_kerf_mm", 10), ("min_rest_mm", 500)):
			row = stored_value(fieldname)
			self.assertEqual(float(row), value)

	def test_zero_kerf_setting_is_honoured(self):
		order, _ = self.submitted_order([("W01", "GREY", 1, 1)])
		self.set_setting("cut_kerf_mm", 0)
		plan = self.new_plan([order.name])
		plan.insert()
		self.assertEqual(plan.kerf_mm, 0)
		for group in json.loads(plan.plan_json)["groups"]:
			for bar in group["bars"]:
				self.assertEqual(bar["bar_length"] - bar["remainder_mm"], sum(p["length"] for p in bar["pieces"]))

	def test_zero_min_rest_survives_reload(self):
		order, _ = self.submitted_order([("W01", "GREY", 1, 1)])
		plan = self.new_plan([order.name])
		plan.min_rest_mm = 0
		plan.insert()
		reloaded = frappe.get_doc("Cutting Plan", plan.name)
		self.assertEqual(reloaded.min_rest_mm, 0)
		reloaded.save()
		self.assertEqual(frappe.get_doc("Cutting Plan", plan.name).min_rest_mm, 0)

	def test_duplicate_order_refused(self):
		order, _ = self.submitted_order([("W01", "GREY", 1, 1)])
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.new_plan([order.name, order.name]).insert()
		self.assertIn(f"Sales Order {order.name} is listed twice", str(ctx.exception))

	def test_other_company_order_refused(self):
		other = "Some Other Company"  # the company check runs in validate, before link validation
		order, _ = self.submitted_order([("W01", "GREY", 1, 1)])
		plan = self.new_plan([order.name])
		plan.company = other
		with self.assertRaises(frappe.ValidationError) as ctx:
			plan.insert()
		self.assertIn(order.name, str(ctx.exception))

	def test_parse_bar_lengths(self):
		self.assertEqual(parse_bar_lengths(" 4880 ,, 5800;", "P"), [4880, 5800])
		with self.assertRaises(frappe.ValidationError) as ctx:
			parse_bar_lengths("48x0", "P1")
		self.assertIn("P1", str(ctx.exception))
		self.assertIn("48x0", str(ctx.exception))

	def test_missing_profile_refused(self):
		order, _ = self.submitted_order([("W01", "GREY", 1, 1)])
		with patch("onebook_fenestration.production.cutting_plan.profile_info", return_value=None):
			with self.assertRaises(frappe.ValidationError) as ctx:
				self.new_plan([order.name]).insert()
		self.assertIn("Fenestration Profile", str(ctx.exception))

	def test_fractional_qty_refused(self):
		order, _ = self.submitted_order([("W01", "GREY", 2, 2)])
		line = next(i for i in order.items if i.fen_window_design)
		frappe.db.set_value("Sales Order Item", line.name, "qty", 1.5)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.new_plan([order.name]).insert()
		self.assertIn("Qty must be whole for cutting", str(ctx.exception))
