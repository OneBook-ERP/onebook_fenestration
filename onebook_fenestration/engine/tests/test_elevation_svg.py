import unittest

from onebook_fenestration.engine.elevation_svg import generate_elevation_svg


class TestElevationSvg(unittest.TestCase):
	def test_fixed_window_svg(self):
		design = {"width": 1200, "height": 1200, "root": {"type": "fixed", "glass": "6CTG"}}
		svg = generate_elevation_svg(design)
		self.assertTrue(svg.startswith("<svg"))
		self.assertTrue(svg.endswith("</svg>"))
		self.assertIn('viewBox="0 0 640 760"', svg)
		self.assertIn(">1200<", svg)
		self.assertIn("#DCEBF7", svg)

	def test_split_sash_window_svg(self):
		design = {
			"width": 915,
			"height": 1220,
			"root": {
				"type": "split",
				"dir": "v",
				"at": [457.5],
				"children": [
					{"type": "sash", "glass": "6CTG", "hinge": "right"},
					{"type": "sash", "glass": "6CTG", "hinge": "left"},
				],
			},
		}
		svg = generate_elevation_svg(design, "#4A5568")
		self.assertTrue(svg.startswith("<svg"))
		self.assertIn("stroke-dasharray", svg)  # swing line
		self.assertIn("#4A5568", svg)
		self.assertIn(">915<", svg)
		self.assertIn(">1220<", svg)

	def test_invalid_design_returns_empty(self):
		self.assertEqual(generate_elevation_svg({}), "")
		self.assertEqual(generate_elevation_svg({"width": 0, "height": 100}), "")

