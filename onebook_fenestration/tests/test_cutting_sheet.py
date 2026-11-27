import base64
import unittest

from onebook_fenestration.engine.cutting import Piece, optimize
from onebook_fenestration.production.cutting_sheet import (
	CutSpec,
	_bar_diagram_svg_uri,
	_group_bar_patterns,
	_parse_angles,
	_section_svg_uri,
)

L_SECTION = "M 0 0 L 40 0 L 40 60 L 0 60 Z"


def _decode_uri(uri: str) -> str:
	prefix = "data:image/svg+xml;base64,"
	assert uri.startswith(prefix)
	return base64.b64decode(uri[len(prefix) :]).decode("utf-8")


class TestCuttingSheet(unittest.TestCase):
	def test_section_svg_respects_default_rotation_and_flips(self):
		raw_svg = _decode_uri(_section_svg_uri(L_SECTION, 40, 60, rotation=0))
		rot90_svg = _decode_uri(_section_svg_uri(L_SECTION, 60, 40, rotation=90))
		rot90_flip_svg = _decode_uri(_section_svg_uri(L_SECTION, 60, 40, rotation="90", flip_x=1, flip_y=0))

		# Unrotated: width 40, depth 60 -> pad = 6 -> viewBox "-6.00 -6.00 52.00 72.00"
		self.assertIn('viewBox="-6.00 -6.00 52.00 72.00"', raw_svg)
		# Rotated 90: width 60, depth 40 -> pad = 6 -> viewBox "-6.00 -6.00 72.00 52.00"
		self.assertIn('viewBox="-6.00 -6.00 72.00 52.00"', rot90_svg)
		self.assertIn('d="M 60 0 L 60 40 L 0 40 L 0 0 Z"', rot90_svg)
		# Flipped horizontally before 90 deg rotation preserves rotated extents and changes path winding
		self.assertIn('viewBox="-6.00 -6.00 72.00 52.00"', rot90_flip_svg)
		self.assertNotEqual(rot90_svg, rot90_flip_svg)

	def test_section_svg_handles_arc_commands_in_bounds(self):
		arc_path = "M 0 0 L 40 0 L 40 60 M 10 20 A 5 3 0 0 1 20 20 Z"
		svg = _decode_uri(_section_svg_uri(arc_path, 40, 60, rotation=0))
		self.assertIn('viewBox="-6.00 -6.00 52.00 72.00"', svg)

	def test_bar_pattern_reconciles_cut_kerf_and_remainder(self):
		specs = [
			CutSpec(1220.0, f"{i:06d}", "W02", "F1", pos, "frame", 45, 45, "45° / 45°")
			for i, pos in enumerate(["B", "T", "L", "R"], start=1)
		]
		spec_by_key = {s.key: s for s in specs}
		result = optimize([Piece(s.length, s.key) for s in specs], [4880, 5800], kerf=10.0, min_rest=500.0)
		patterns = _group_bar_patterns(result.bars, spec_by_key, kerf_mm=10.0)

		self.assertEqual(len(patterns), 1)
		pat = patterns[0]
		self.assertEqual(pat["bar_length"], 5800.0)
		self.assertEqual(pat["cut_count"], 4)
		self.assertEqual(pat["net_cut_mm"], 4880.0)
		self.assertEqual(pat["kerf_loss_mm"], 40.0)
		self.assertEqual(pat["remainder_mm"], 880.0)
		self.assertEqual(pat["net_cut_mm"] + pat["kerf_loss_mm"] + pat["remainder_mm"], pat["bar_length"])
		self.assertTrue(pat["is_rest"])

	def test_bar_pattern_zero_kerf_has_zero_kerf_loss(self):
		specs = [
			CutSpec(1220.0, f"{i:06d}", "W02", "F1", pos, "frame", 45, 45, "45° / 45°")
			for i, pos in enumerate(["B", "T", "L", "R"], start=1)
		]
		spec_by_key = {s.key: s for s in specs}
		result = optimize([Piece(s.length, s.key) for s in specs], [4880, 5800], kerf=0.0, min_rest=500.0)
		patterns = _group_bar_patterns(result.bars, spec_by_key, kerf_mm=0.0)

		pat = patterns[0]
		self.assertEqual(pat["bar_length"], 4880.0)
		self.assertEqual(pat["net_cut_mm"], 4880.0)
		self.assertEqual(pat["kerf_loss_mm"], 0.0)
		self.assertEqual(pat["remainder_mm"], 0.0)

	def test_bar_diagram_contains_pieces_and_remainder(self):
		cuts = [CutSpec(1172.0, "000001", "W02", "F1", "H", "mullion", 90, 90, "90° / 90°")]
		svg = _decode_uri(_bar_diagram_svg_uri(4880.0, cuts, 3698.0, True, 10.0))
		self.assertIn("1172 · H/F1", svg)
		self.assertIn("3698", svg)
		self.assertIn("REST", svg)

		scrap_svg = _decode_uri(_bar_diagram_svg_uri(4880.0, cuts, 40.0, False, 10.0))
		self.assertNotIn("REST", scrap_svg)

	def test_parse_angles(self):
		self.assertEqual(_parse_angles([45, 45]), (45, 45))
		self.assertEqual(_parse_angles([45, 135]), (45, 45))
		self.assertEqual(_parse_angles("[90, 90]"), (90, 90))
		self.assertEqual(_parse_angles("45 / 45"), (45, 45))
		self.assertEqual(_parse_angles("45 / 135"), (45, 45))
		self.assertEqual(_parse_angles(None), (90, 90))
