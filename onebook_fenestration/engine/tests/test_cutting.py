import random
import unittest

from onebook_fenestration.engine.cutting import Piece, optimize, wastage


def _pieces(*specs):
	return [Piece(length, label) for length, label in specs]


class TestCutting(unittest.TestCase):
	def _two_bars(self):
		return optimize(_pieces((3000, "a"), (3000, "b"), (1500, "c")), [6000])

	def test_ffd_two_bars(self):
		r = self._two_bars()
		self.assertEqual(len(r.bars), 2)
		b0, b1 = r.bars
		self.assertEqual([p.label for p in b0.pieces], ["a", "c"])
		self.assertEqual((b0.used_mm, b0.remainder_mm, b0.is_rest), (4520, 1480, True))
		self.assertEqual([p.label for p in b1.pieces], ["b"])
		self.assertEqual((b1.used_mm, b1.remainder_mm), (3010, 2990))
		self.assertEqual(r.unplaced, [])

	def test_shrinks_to_shortest_bar(self):
		r = optimize(_pieces((4000, "a")), [4880, 5800])
		self.assertEqual([b.bar_length for b in r.bars], [4880])
		self.assertEqual(r.bars[0].remainder_mm, 870)
		r = optimize(_pieces((5000, "a")), [4880, 5800])
		self.assertEqual([b.bar_length for b in r.bars], [5800])

	def test_mixed_lengths_one_profile(self):
		r = optimize(_pieces((5000, "a"), (4000, "b")), [4880, 5800])
		self.assertEqual({b.bar_length for b in r.bars}, {5800, 4880})

	def test_short_remainder_is_waste(self):
		r = optimize(_pieces((5590, "a")), [6000])
		self.assertEqual(r.bars[0].remainder_mm, 400)
		self.assertFalse(r.bars[0].is_rest)

	def test_unplaced_piece(self):
		r = optimize(_pieces((6000, "big"), (1000, "small")), [5800])
		self.assertEqual([p.label for p in r.unplaced], ["big"])
		self.assertEqual(len(r.bars), 1)
		self.assertEqual(r.bars[0].pieces[0].label, "small")
		r = optimize(_pieces((1000, "small")), [])
		self.assertEqual(len(r.unplaced), 1)
		self.assertEqual(r.bars, [])

	def test_deterministic(self):
		pieces = _pieces((3000, "a"), (3000, "b"), (1500, "c"), (1200, "d"), (1200, "e"), (800, "f"))
		expected = optimize(pieces, [4880, 5800])
		for seed in range(5):
			shuffled = list(pieces)
			random.Random(seed).shuffle(shuffled)
			self.assertEqual(optimize(shuffled, [5800, 4880]), expected)

	def test_wastage_summary(self):
		w = wastage(self._two_bars(), 1.0)
		self.assertEqual(w["bar_count"], 2)
		self.assertEqual(w["bars"], {6000: 2})
		self.assertEqual(w["pieces"], 3)
		self.assertEqual(
			(w["bar_mm"], w["cut_mm"], w["kerf_mm"], w["rest_mm"], w["waste_mm"]),
			(12000, 7500, 30, 4470, 30),
		)
		self.assertEqual((w["kg_bars"], w["kg_used"]), (12.0, 7.5))
		self.assertEqual((w["waste_pct_incl_rest"], w["waste_pct_excl_rest"]), (37.5, 0.25))
		self.assertEqual(w["kg_per_m"], 1.0)
