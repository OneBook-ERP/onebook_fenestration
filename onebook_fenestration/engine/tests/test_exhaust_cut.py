import unittest
from onebook_fenestration.engine import compute, cross_section
from onebook_fenestration.engine.exhaust_cut import exhaust_cut
from onebook_fenestration.engine.tests.helpers import snapshot


class TestExhaustCut(unittest.TestCase):
	def design(self, kind="fixed"):
		return {"width": 600, "height": 500, "root": {"type": kind, "glass": "6CTG", "fan": True}}

	def test_legacy_defaults_and_invalid_sizes(self):
		self.assertEqual(exhaust_cut({"fan": True}, 600, 500), {"diameter": 180, "centerX": 300, "centerY": 250})
		for config in ({"diameter": 0}, {"diameter": 700}, {"centerX": 10}, {"centerY": float("nan")}):
			with self.assertRaises(ValueError):
				exhaust_cut({"fan": True, "fanCut": config}, 600, 500)

	def test_fixed_and_sash_panes_report_openings_and_vertical_cuts(self):
		for kind in ("fixed", "sash"):
			with self.subTest(kind=kind):
				design = self.design(kind)
				result = compute(design, snapshot())
				self.assertEqual(result.glass[0].cutout["diameter"], 180)
				section = cross_section(design, snapshot(), "v")
				pane = next(p for p in section.pieces if p.kind == "glass")
				self.assertAlmostEqual(pane.cutout["end"] - pane.cutout["start"], 180, places=1)
				self.assertGreater(pane.cutout["start"], pane.start)
				self.assertLess(pane.cutout["end"], pane.end)

	def test_horizontal_cut_misses_high_opening_and_intersects_centered_opening(self):
		design = self.design()
		design["height"] = 800
		design["root"]["fanCut"] = {"centerY": 140}
		section = cross_section(design, snapshot(), "h")
		self.assertIsNone(next(p for p in section.pieces if p.kind == "glass").cutout)
		height = compute(design, snapshot()).glass[0].height
		design["root"]["fanCut"] = {"centerY": height / 2}
		section = cross_section(design, snapshot(), "h")
		cut = next(p for p in section.pieces if p.kind == "glass").cutout
		self.assertAlmostEqual(cut["end"] - cut["start"], 180, places=1)

	def test_invalid_opening_is_reported_and_removing_flag_restores_solid_glass(self):
		design = self.design()
		design["root"]["fanCut"] = {"diameter": 1000}
		result = compute(design, snapshot())
		self.assertIsNone(result.glass[0].cutout)
		self.assertTrue(any(i.code == "invalid_exhaust_cut" and i.path == "F1" for i in result.issues))
		design["root"]["fan"] = False
		self.assertFalse(any(i.code == "invalid_exhaust_cut" for i in compute(design, snapshot()).issues))

	def test_steel_weight_uses_sheet_thickness_and_deducts_hole(self):
		from math import pi
		from onebook_fenestration.engine.weights import weights
		design = self.design()
		design["root"]["steelThickness"] = 2
		snap = snapshot()
		result = compute(design, snap)
		pane = result.glass[0]
		self.assertEqual(pane.material, "steel")
		_, weight = weights([], [pane], snap)
		expected = (pane.width * pane.height - pi * 90 ** 2) / 1e6 * 2 * 7.85
		self.assertAlmostEqual(weight, expected, delta=0.001)

	def test_only_exhaust_panel_is_steel_and_removal_restores_glass(self):
		design = {"width": 1200, "height": 1200, "root": {"type": "split", "dir": "v", "at": [600], "children": [
			{"type": "fixed", "glass": "6CTG"},
			{"type": "fixed", "glass": "6CTG", "fan": True},
		]}}
		snap = snapshot()
		result = compute(design, snap)
		self.assertEqual([p.material for p in result.glass], ["glass", "steel"])
		self.assertEqual([p.thickness for p in result.glass], [6, 1.2])
		pieces = [p for p in cross_section(design, snap, "h").pieces if p.kind == "glass"]
		self.assertEqual([p.material for p in pieces], ["glass", "steel"])
		self.assertIsNone(pieces[0].cutout)
		self.assertIsNotNone(pieces[1].cutout)
		from onebook_fenestration.engine.pricing import price
		from onebook_fenestration.engine.tests.test_pricing import _inputs
		cost = price(result, snap, _inputs(result))
		self.assertAlmostEqual(cost.variables["glass_cost"], result.glass[0].width * result.glass[0].height / 1e6 * 1000, places=2)
		self.assertTrue(any(i.code == "steel_rate_missing" and i.path == "F1.1" for i in cost.issues))
		design["root"]["children"][1]["fan"] = False
		result = compute(design, snap)
		self.assertEqual([p.material for p in result.glass], ["glass", "glass"])
		self.assertFalse(any(i.code == "steel_rate_missing" for i in price(result, snap, _inputs(result)).issues))

	def test_invalid_steel_thickness_is_reported(self):
		for thickness in (0, -1, True, float("nan")):
			design = self.design()
			design["root"]["steelThickness"] = thickness
			self.assertTrue(any(i.code == "invalid_steel_thickness" for i in compute(design, snapshot()).issues))

	def test_default_centre_does_not_move_when_diameter_changes(self):
		for diameter in (100, 180, 300):
			cut = exhaust_cut({"fan": True, "fanCut": {"diameter": diameter}}, 600, 500)
			self.assertEqual((cut["centerX"], cut["centerY"]), (300, 250))
		cut = exhaust_cut({"fan": True, "fanCut": {"diameter": 100, "centerX": 200, "centerY": 150}}, 600, 500)
		self.assertEqual((cut["centerX"], cut["centerY"]), (200, 150))
