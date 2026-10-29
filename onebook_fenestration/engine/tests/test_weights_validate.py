import unittest

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.tests.helpers import load, snapshot

SNAP = snapshot()


class TestWeightsValidate(unittest.TestCase):
	def test_w01_weights_match_eva(self):
		r = compute(load("w01.json"), SNAP)
		self.assertAlmostEqual(r.shutter_kg["F1-S1"], 8.489, delta=0.02)
		self.assertAlmostEqual(r.window_kg, 20.698, delta=0.02)
		self.assertEqual((r.area_m2, r.area_sqft), (1.116, 12.013))

	def test_wall_12x6_shutter_fails_stay(self):
		r = compute(load("wall_12x6.json"), SNAP)
		self.assertTrue(any(i.code == "v_shutter_kg" and i.panel == "F1-S1" for i in r.issues))
		self.assertAlmostEqual(r.shutter_kg["F1-S1"], 32.9, delta=0.2)
