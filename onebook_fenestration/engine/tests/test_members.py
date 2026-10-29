import unittest

from onebook_fenestration.engine.layout import layout
from onebook_fenestration.engine.members import cut_members
from onebook_fenestration.engine.tests.helpers import load, snapshot


def run(design):
	cells, bars = layout(design)
	return cut_members(design, snapshot(), cells, bars)


class TestMembers(unittest.TestCase):
	def test_w01_cut_list(self):
		members, issues, _ = run(load("w01.json"))
		got = sorted((m.panel, m.position, m.profile, m.length, m.angles) for m in members)
		expected = [
			("F1", "B", "E104156", 915.0, (45, 135)),
			("F1", "T", "E104156", 915.0, (45, 135)),
			("F1", "L", "E104156", 1220.0, (45, 135)),
			("F1", "R", "E104156", 1220.0, (45, 135)),
			("F1", "H", "E104159", 1172.0, (90, 90)),
			*[(p, s, "E104160", 434.0, (45, 135)) for p in ("F1-S1", "F1-S2") for s in ("B", "T")],
			*[(p, s, "E104160", 1184.0, (45, 135)) for p in ("F1-S1", "F1-S2") for s in ("L", "R")],
		]
		self.assertEqual(got, sorted(expected))
		self.assertEqual(issues, [])

	def test_w01_sash_sizes(self):
		_, _, sash_sizes = run(load("w01.json"))
		self.assertEqual(sash_sizes, {"F1-S1": (434.0, 1184.0), "F1-S2": (434.0, 1184.0)})

	def test_tiny_cell_gives_issue_not_crash(self):
		d = {"width": 30, "height": 1220, "root": {"type": "sash", "glass": "6CTG"}}
		members, issues, _ = run(d)
		self.assertTrue(any(i.code == "non_positive_size" for i in issues))
		self.assertEqual(len([m for m in members if m.panel == "F1"]), 4)
