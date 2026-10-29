import unittest

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.tests.helpers import load, snapshot

SNAP = snapshot()


def totals(bom):
	t: dict[str, float] = {}
	for line in bom:
		t[line.item] = t.get(line.item, 0) + line.qty
	return t


class TestHardware(unittest.TestCase):
	def test_w01_hardware_totals(self):
		t = totals(compute(load("w01.json"), SNAP).bom)
		items = ["H401", "H266", "H912", "H913", "H904", "H903", "H902", "H901", "H911", "H412", "H411", "H416", "H429", "H425", "H422C", "H423", "H905"]
		self.assertEqual(
			{k: t[k] for k in items},
			{"H401": 12, "H266": 12, "H912": 10, "H913": 2, "H904": 10, "H903": 10, "H902": 6, "H901": 6, "H911": 10, "H412": 4, "H411": 2, "H416": 2, "H429": 12, "H425": 2, "H422C": 2, "H423": 4, "H905": 16},
		)

	def test_w01_consumables(self):
		bom = compute(load("w01.json"), SNAP).bom
		self.assertEqual(next(b.length for b in bom if b.item == "H915"), 8.54)
		self.assertEqual(next(b.qty for b in bom if b.item == "H914"), 1.423)

	def test_w02_frame_hardware(self):
		t = totals(compute(load("w02.json"), SNAP).bom)
		self.assertEqual((t["H912"], t["H902"], t["H911"]), (8, 4, 8))
