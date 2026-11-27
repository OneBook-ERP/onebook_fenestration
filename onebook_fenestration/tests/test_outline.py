import re
import unittest

from onebook_fenestration.series_studio.outline import (
	compose_section_transform,
	rotate_path,
	svg_extents,
	transform_path,
)

RECT = "M 0 0 L 40 0 L 40 60 L 0 60 Z"


def points(d):
	numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
	return list(zip(numbers[0::2], numbers[1::2], strict=True))


class TestRotatePath(unittest.TestCase):
	def test_rotate_path_90_and_270(self):
		d, width, depth = rotate_path(RECT, 90)
		self.assertEqual((width, depth), (60, 40))
		self.assertEqual(d, "M 60 0 L 60 40 L 0 40 L 0 0 Z")
		d, width, depth = rotate_path(RECT, 270)
		self.assertEqual((width, depth), (60, 40))
		self.assertEqual(d, "M 0 40 L 0 0 L 60 0 L 60 40 Z")
		for degrees in (90, 180, 270):
			xs, ys = zip(*points(rotate_path(RECT, degrees)[0]), strict=True)
			self.assertEqual((min(xs), min(ys)), (0, 0), degrees)

	def test_rotate_path_0_is_unchanged(self):
		self.assertEqual(rotate_path(RECT, 0), (RECT, 40, 60))
		self.assertEqual(rotate_path(RECT, "0"), (RECT, 40, 60))

	def test_rotate_path_180(self):
		self.assertEqual(rotate_path(RECT, 180), ("M 40 60 L 0 60 L 0 0 L 40 0 Z", 40, 60))

	def test_rotate_path_implicit_lineto(self):
		# The section importer writes "M x y x y ..." with implicit line-tos.
		d, width, depth = rotate_path("M0 0 40 0 40 60 M10 10 20 10", 90)
		self.assertEqual((width, depth), (60, 40))
		self.assertEqual(d, "M 60 0 60 40 0 40 M 50 10 50 20")

	def test_rotate_path_arc_keeps_sweep(self):
		d, width, depth = rotate_path("M 0 0 L 40 0 L 40 60 M 10 20 A 5 3 0 0 1 20 20", 90)
		arc = re.search(r"A ([^A-Za-z]+)", d).group(1).split()
		# rx ry kept, x-axis-rotation turns with the outline, large-arc and sweep flags preserved
		self.assertEqual(arc, ["5", "3", "90", "0", "1", "40", "20"])
		self.assertEqual((width, depth), (60, 40))

	def test_rotate_path_rejects_bad_input(self):
		with self.assertRaises(ValueError):
			rotate_path(RECT, 45)
		with self.assertRaises(ValueError):
			rotate_path("M 0 0 C 1 1 2 2 3 3", 90)

	def test_svg_extents(self):
		self.assertEqual(svg_extents("M 5 5 L 45 5 L 45 65 Z"), (40, 60))
		self.assertEqual(svg_extents(""), (0, 0))

	def test_transform_path_flip_and_arc_sweep(self):
		d, width, depth = transform_path(
			"M 0 0 L 40 0 L 40 60 M 10 20 A 5 3 15 0 1 20 20", degrees=0, flip_x=True
		)
		self.assertEqual((width, depth), (40, 60))
		self.assertTrue(d.startswith("M 40 0 L 0 0 L 0 60 M 30 20"))
		arc = re.search(r"A ([^A-Za-z]+)", d).group(1).split()
		# Odd reflection negates x-axis-rotation mod 360 and flips sweep flag
		self.assertEqual(arc, ["5", "3", "345", "0", "0", "20", "20"])

	def test_transform_path_flip_y_then_rotate_90(self):
		tri = "M 0 0 L 10 0 L 0 20 Z"
		d, width, depth = transform_path(tri, degrees=90, flip_y=True)
		self.assertEqual((width, depth), (20, 10))
		# flip_y: (0,0)->(0,0), (10,0)->(10,0), (0,20)->(0,-20); rot 90: (0,0), (0,10), (20,0)
		self.assertEqual(d, "M 0 0 L 0 10 L 20 0 Z")

	def test_compose_section_transform_d4_order(self):
		# Flip H (0, 1, 0) then rotate +90 = (90, 1, 0)
		self.assertEqual(compose_section_transform(0, 0, 0, 90, True, False), (90, 1, 0))
		# Now rotate that (90, 1, 0) again by +90 -> M(90) * M(90,1,0) = [[ -1, 0 ], [ 0, 1 ]] *? wait: M(90)*M(90,1,0) = (180,1,0) = M(0, 0, 1) (pure flip Y!)
		self.assertEqual(compose_section_transform(90, 1, 0, 90, False, False), (0, 0, 1))
		# Flip H twice returns identity
		self.assertEqual(compose_section_transform(0, 1, 0, 0, True, False), (0, 0, 0))
		# Flip X then Flip Y = 180° rotation with no flip
		self.assertEqual(compose_section_transform(0, 1, 0, 0, False, True), (180, 0, 0))
