import unittest

from onebook_fenestration.engine.glazing import glaze
from onebook_fenestration.engine.layout import layout
from onebook_fenestration.engine.members import cut_members
from onebook_fenestration.engine.tests.helpers import load, snapshot


def run_glaze(name_or_design):
	design = load(name_or_design) if isinstance(name_or_design, str) else name_or_design
	cells, bars = layout(design)
	_, _, sash_sizes = cut_members(design, snapshot(), cells, bars)
	return glaze(design, cells, sash_sizes, snapshot())


class TestGlazing(unittest.TestCase):
	def test_w01_glass(self):
		panes = run_glaze("w01.json")[0]
		self.assertEqual(
			[(p.panel, p.number, p.width, p.height) for p in panes],
			[("F1-S1", 1, 333.0, 1083.0), ("F1-S2", 2, 333.0, 1083.0)],
		)

	def test_w01_glazing_gasket_lengths(self):
		bom = run_glaze("w01.json")[1]
		g23 = sorted(b.length for b in bom if b.item == "G23")
		self.assertEqual(g23, [305.0] * 4 + [1055.0] * 4)

	def test_w01_frame_gasket(self):
		bom = run_glaze("w01.json")[1]
		g21 = sorted(b.length for b in bom if b.item == "G21")
		self.assertEqual(g21, [434.0] * 4 + [915.0] * 2 + [1184.0] * 4 + [1220.0] * 2)

	def test_fixed_and_louver_cells(self):
		design = {
			"width": 1500,
			"height": 1500,
			"root": {
				"type": "split",
				"dir": "v",
				"at": [750],
				"children": [
					{"type": "fixed", "glass": "6CTG"},
					{"type": "louver", "glass": "5TGT", "blades": 9},
				],
			},
		}
		panes, _, issues = run_glaze(design)
		self.assertEqual([(p.panel, p.width, p.height) for p in panes], [("F1", 690.0, 1440.0)])
		self.assertEqual([(i.severity, i.code, i.panel) for i in issues], [("warn", "louver_placeholder", "F1")])
