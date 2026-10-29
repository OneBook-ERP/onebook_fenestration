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


def nested(levels: int) -> dict:
	"""A design whose tree is `levels` splits deep before the last leaf."""
	node: dict = {"type": "fixed", "glass": "6CTG"}
	for _ in range(levels):
		node = {"type": "split", "dir": "v", "at": [1], "children": [{"type": "fixed", "glass": "6CTG"}, node]}
	return {"width": 10000, "height": 1220, "root": node}


def two_cells(**split) -> dict:
	root = {"type": "split", "dir": "v", "at": [457.5], "children": [{"type": "fixed"}, {"type": "fixed"}], **split}
	return {"width": 915, "height": 1220, "root": root}


class TestDesignErrors(unittest.TestCase):
	def assertDesignError(self, design, path):
		with self.assertRaises(DesignError) as cm:
			layout(design)
		self.assertIn(path, str(cm.exception))

	def test_design_must_be_object(self):
		self.assertDesignError([], "F1")

	def test_missing_root(self):
		self.assertDesignError({"width": 915, "height": 1220}, "F1")

	def test_root_must_be_object(self):
		for root in (None, [], "sash"):
			with self.subTest(root=root):
				self.assertDesignError({"width": 915, "height": 1220, "root": root}, "F1")

	def test_child_must_be_object(self):
		self.assertDesignError(two_cells(children=["sash", {"type": "fixed"}]), "F1.0")

	def test_children_must_be_list(self):
		self.assertDesignError(two_cells(children="ab"), "F1")

	def test_at_must_be_list_of_finite_numbers(self):
		for at in (["457.5"], 457.5, [True], [float("nan")], [float("inf")]):
			with self.subTest(at=at):
				self.assertDesignError(two_cells(at=at), "F1")

	def test_width_height_must_be_finite_numbers(self):
		for width, height in ((float("nan"), 1220), (915, float("inf")), (True, 1220), (915, True)):
			with self.subTest(width=width, height=height):
				self.assertDesignError({"width": width, "height": height, "root": {"type": "fixed"}}, "F1")

	def test_glass_must_be_string(self):
		self.assertDesignError(two_cells(children=[{"type": "fixed", "glass": ["6CTG"]}, {"type": "fixed"}]), "F1.0")

	def test_depth_is_capped_at_32(self):
		self.assertEqual(len(layout(nested(31))[0]), 32)
		self.assertDesignError(nested(32), "depth")
		self.assertDesignError(nested(1500), "depth")
