import unittest

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.tests.helpers import load, snapshot, snapshot_with
from onebook_fenestration.engine.types import GlassPane
from onebook_fenestration.engine.weights import weights

SNAP = snapshot()


class TestWeightsValidate(unittest.TestCase):
	def test_w01_weights_match_eva(self):
		r = compute(load("w01.json"), SNAP)
		self.assertAlmostEqual(r.shutter_kg["F1-S1"], 8.489, delta=0.02)
		self.assertAlmostEqual(r.window_kg, 20.698, delta=0.02)
		self.assertEqual((r.area_m2, r.area_sqft), (1.116, 12.013))

	def _pane_kg(self, snap, glass):
		_, kg = weights([], [GlassPane("F1", 1, glass, 1000, 1000)], snap)
		return kg

	def test_dgu_weight_ignores_air_gap(self):
		def add(d):
			d["glasses"]["12TG"] = {"name": "12 mm", "thickness_mm": 12}
			d["glasses"]["24DGU"] = {"name": "DGU 6+12+6", "thickness_mm": 24, "glass_mm": 12}

		snap = snapshot_with(add)
		self.assertEqual(self._pane_kg(snap, "24DGU"), self._pane_kg(snap, "12TG"))

	def test_glass_mm_defaults_to_thickness(self):
		snap = snapshot()
		self.assertIsNone(snap.glasses["6CTG"].glass_mm)
		self.assertAlmostEqual(self._pane_kg(snap, "6CTG"), 1000 * 1000 / 1e6 * 6 * snap.constants["glass_density"])

	def test_wall_12x6_shutter_fails_stay(self):
		r = compute(load("wall_12x6.json"), SNAP)
		self.assertTrue(any(i.code == "v_shutter_kg" and i.panel == "F1-S1" for i in r.issues))
		self.assertAlmostEqual(r.shutter_kg["F1-S1"], 32.9, delta=0.2)

	def test_message_placeholder_missing_raises_rule_error(self):
		from onebook_fenestration.engine.tests.helpers import snapshot_with
		from onebook_fenestration.engine.types import RuleError

		snap = snapshot_with(lambda d: d["validation_rules"][0].update(message="{nope} too heavy"))
		with self.assertRaises(RuleError) as cm:
			compute(load("wall_12x6.json"), snap)
		self.assertIn("v_shutter_kg", str(cm.exception))
		self.assertIn("placeholder", str(cm.exception))
