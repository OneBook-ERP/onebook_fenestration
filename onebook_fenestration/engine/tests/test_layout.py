import unittest

from onebook_fenestration.engine.layout import Bar, layout
from onebook_fenestration.engine.tests.helpers import load
from onebook_fenestration.engine.types import DesignError


class TestLayout(unittest.TestCase):
	def test_w01_two_cells(self):
		cells, bars = layout(load("w01.json"))
		self.assertEqual([(c.x, c.w, c.h) for c in cells], [(0, 457.5, 1220), (457.5, 457.5, 1220)])
		self.assertEqual(cells[0].sides, {"L": "frame", "R": "mullion", "B": "frame", "T": "frame"})
		self.assertEqual(cells[1].sides, {"L": "mullion", "R": "frame", "B": "frame", "T": "frame"})
		self.assertEqual(bars, [Bar("mullion", "M1", 1220, ("frame", "frame"))])

	def test_nested_transom_ends_on_mullion(self):
		d = {
			"width": 1500,
			"height": 1500,
			"root": {
				"type": "split",
				"dir": "v",
				"at": [750],
				"children": [
					{"type": "fixed", "glass": "6CTG"},
					{
						"type": "split",
						"dir": "h",
						"at": [1000],
						"children": [{"type": "sash", "glass": "6CTG"}, {"type": "fixed", "glass": "6CTG"}],
					},
				],
			},
		}
		cells, bars = layout(d)
		self.assertEqual(len(cells), 3)
		self.assertEqual(bars[1], Bar("transom", "T1", 750, ("mullion", "frame")))
		self.assertEqual(cells[1].sides, {"L": "mullion", "R": "frame", "B": "frame", "T": "transom"})

	def test_bad_split_positions(self):
		for at in ([0], [915], [500, 400], []):
			d = {
				"width": 915,
				"height": 1220,
				"root": {"type": "split", "dir": "v", "at": at, "children": [{"type": "fixed"}, {"type": "fixed"}]},
			}
			with self.subTest(at=at), self.assertRaises(DesignError):
				layout(d)
