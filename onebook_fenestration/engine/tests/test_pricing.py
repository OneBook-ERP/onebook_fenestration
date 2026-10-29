import unittest
from dataclasses import replace

from onebook_fenestration.engine import RuleError, compute
from onebook_fenestration.engine.pricing import CostHead, PricingInput, price
from onebook_fenestration.engine.tests.helpers import load, snapshot

ITEMS = ("profile", "profile_waste", "powder", "anodize", "wood", "hardware", "glass", "glass_waste", "fabrication", "installation")
STANDARD = (
	CostHead("profile", "Profile Cost", "Formula", formula="profile_cost"),
	CostHead("profile_waste", "Profile Wastage", "Percentage", rate=5, base="profile"),
	CostHead("powder", "Powder Coating", "Per Visible Perimeter Sqft", rate=25, condition="finish_type == 'Powder Coat'"),
	CostHead("anodize", "Anodizing", "Per Total Perimeter Sqft", rate=40, condition="finish_type == 'Anodized'"),
	CostHead("wood", "Wood Finish", "Per Visible Perimeter Sqft", rate=70, condition="finish_type == 'Wood'"),
	CostHead("hardware", "Hardware Cost", "Formula", formula="hardware_cost + gasket_cost"),
	CostHead("glass", "Glass Cost", "Formula", formula="glass_cost"),
	CostHead("glass_waste", "Glass Wastage", "Percentage", rate=1, base="glass"),
	CostHead("fabrication", "Fabrication Labour", "Per Area Sqft", rate=100),
	CostHead("installation", "Installation Labour", "Per Area Sqft", rate=80),
	CostHead("profit", "Profit", "Percentage", rate=20, base=",".join(ITEMS)),
)


def _inputs(result, heads=STANDARD, finish="Powder Coat", **kw):
	profiles = {m.profile for m in result.members}
	items = {b.item for b in result.bom}
	return PricingInput(
		heads=heads,
		profile_rates=dict.fromkeys(profiles, 300),
		item_rates={i: (20 if i in ("G21", "G23") else 10) for i in items},
		glass_rates={"6CTG": 1000},
		finish_type=finish,
		**kw,
	)


def _setup(with_perimeter=False, total=False):
	snap = snapshot()
	if with_perimeter:
		snap.profiles["E104156"] = replace(snap.profiles["E104156"], visible_perimeter_mm=100)
	if total:
		snap.profiles["E104156"] = replace(snap.profiles["E104156"], total_perimeter_mm=200)
	return compute(load("w01.json"), snap), snap


class TestPricing(unittest.TestCase):
	def test_profile_hardware_glass_costs(self):
		result, snap = _setup()
		out = price(result, snap, _inputs(result))
		kg = sum(m.length / 1000 * snap.profiles[m.profile].kg_per_m for m in result.members)
		self.assertAlmostEqual(out.variables["profile_cost"], round(kg * 300, 2), places=2)
		self.assertAlmostEqual(out.variables["glass_cost"], sum(g.width * g.height / 1e6 * 1000 for g in result.glass), places=2)
		hw = sum(b.qty * 10 for b in result.bom if b.group != "Gasket")
		gk = sum(b.length / 1000 * 20 for b in result.bom if b.group == "Gasket")
		self.assertGreater(gk, 0)
		self.assertAlmostEqual(out.variables["hardware_cost"], hw, places=2)
		self.assertAlmostEqual(out.variables["gasket_cost"], gk, places=2)

	def test_percentage_and_conditions(self):
		result, snap = _setup(with_perimeter=True)
		out = price(result, snap, _inputs(result))
		amt = {line.key: line.amount for line in out.lines}
		self.assertGreater(amt["powder"], 0)
		self.assertEqual(amt["anodize"], 0)
		self.assertEqual(amt["wood"], 0)
		self.assertEqual(len(out.lines), 11)
		self.assertAlmostEqual(amt["profit"], round(0.2 * sum(amt[k] for k in ITEMS), 2), places=2)

	def test_perimeter_sqft(self):
		result, snap = _setup(with_perimeter=True)
		out = price(result, snap, _inputs(result))
		metres = sum(m.length / 1000 * 0.1 for m in result.members if m.profile == "E104156")
		self.assertGreater(metres, 0)
		self.assertAlmostEqual(out.variables["visible_perimeter_sqft"], metres * 10.764, places=4)
		self.assertEqual(out.variables["total_perimeter_sqft"], 0)

	def test_percentage_base_must_be_earlier_head(self):
		result, snap = _setup()
		heads = (CostHead("a", "A", "Percentage", rate=5, base="b"), CostHead("b", "B", "Fixed", rate=1))
		with self.assertRaises(RuleError) as ctx:
			price(result, snap, _inputs(result, heads))
		self.assertIn("a:", str(ctx.exception))

	def test_zero_area_rate_per_sqft(self):
		result, snap = _setup()
		result.area_sqft = 0.0
		out = price(result, snap, _inputs(result, (CostHead("f", "F", "Fixed", rate=50),)))
		self.assertEqual(out.unit_price, 50)
		self.assertEqual(out.rate_per_sqft, 0.0)

	def test_missing_rates_warn(self):
		result, snap = _setup()
		out = price(result, snap, _inputs(result, missing=("E1", "G9")))
		warns = [i for i in out.issues if i.code == "no_rate"]
		self.assertEqual([i.message for i in warns], ["E1: no rate", "G9: no rate"])
		self.assertTrue(all(i.severity == "warn" for i in warns))

	def test_unit_price_and_rate_per_sqft_rounding(self):
		result, snap = _setup()
		out = price(result, snap, _inputs(result))
		self.assertEqual(out.unit_price, round(sum(line.amount for line in out.lines), 2))
		self.assertEqual(out.rate_per_sqft, round(out.unit_price / result.area_sqft, 2))

	def test_reserved_and_duplicate_keys_rejected(self):
		result, snap = _setup()
		for heads in (
			(CostHead("area_sqft", "A", "Fixed", rate=1),),
			(CostHead("a", "A", "Fixed", rate=1), CostHead("a", "A2", "Fixed", rate=1)),
		):
			with self.assertRaises(RuleError) as ctx:
				price(result, snap, _inputs(result, heads))
			self.assertIn("duplicate or reserved cost head key", str(ctx.exception))

	def test_fixed_and_area_amounts(self):
		result, snap = _setup()
		heads = (CostHead("f", "F", "Fixed", rate=12.5), CostHead("a", "A", "Per Area Sqft", rate=3))
		out = price(result, snap, _inputs(result, heads))
		self.assertEqual(out.variables["f"], 12.5)
		self.assertEqual(out.variables["a"], round(3 * result.area_sqft, 2))

	def test_total_perimeter_amount(self):
		result, snap = _setup(total=True)
		out = price(result, snap, _inputs(result, (CostHead("t", "T", "Per Total Perimeter Sqft", rate=40),)))
		self.assertGreater(out.variables["total_perimeter_sqft"], 0)
		self.assertEqual(out.variables["t"], round(40 * out.variables["total_perimeter_sqft"], 2))

	def test_percentage_of_skipped_head_is_zero(self):
		result, snap = _setup()
		heads = (
			CostHead("a", "A", "Fixed", rate=100, condition="finish_type == 'Wood'"),
			CostHead("b", "B", "Percentage", rate=10, base="a"),
		)
		out = price(result, snap, _inputs(result, heads))
		self.assertEqual([line.amount for line in out.lines], [0, 0])

	def test_bad_base_raises_even_when_condition_false(self):
		result, snap = _setup()
		heads = (CostHead("a", "A", "Percentage", rate=5, base="zzz", condition="False"),)
		with self.assertRaises(RuleError):
			price(result, snap, _inputs(result, heads))

	def test_unknown_calc_names_key(self):
		result, snap = _setup()
		with self.assertRaises(RuleError) as ctx:
			price(result, snap, _inputs(result, (CostHead("weird", "W", "Bogus"),)))
		self.assertIn("weird", str(ctx.exception))
