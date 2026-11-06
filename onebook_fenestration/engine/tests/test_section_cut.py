import json
import unittest
from dataclasses import asdict
from pathlib import Path

from onebook_fenestration.engine import compute, cross_section
from onebook_fenestration.engine.tests.helpers import load, snapshot
from onebook_fenestration.engine.types import DesignError, SeriesSnapshot

DATA = Path(__file__).resolve().parents[2] / "series_studio" / "data"
# Test face widths; real ones come from Fenestration Profile.width_mm.
CS400_WIDTHS = {"E104156": 50, "E104160": 60, "E104159": 70}
CS4800_WIDTHS = {"CS4801": 55, "CS4802": 70, "CS4803": 65, "CS4808": 20, "HSL3410": 10}


def cs4800() -> SeriesSnapshot:
	return SeriesSnapshot.from_dict(json.loads((DATA / "cs4800_v2.json").read_text()))


def sequence(section) -> list[tuple[str, str]]:
	return [(p.kind, p.code) for p in section.pieces]


class TestSectionCut(unittest.TestCase):
	def test_w01_horizontal_cut(self):
		design, snap = load("w01.json"), snapshot()
		section = cross_section(design, snap, "h", widths=CS400_WIDTHS)
		self.assertEqual(section.length, 915)
		self.assertEqual(section.at, 610)
		self.assertEqual(
			sequence(section),
			[
				("profile", "E104156"),
				("profile", "E104160"),
				("glass", "6CTG"),
				("profile", "E104160"),
				("profile", "E104159"),
				("profile", "E104160"),
				("glass", "6CTG"),
				("profile", "E104160"),
				("profile", "E104156"),
			],
		)
		p = section.pieces
		self.assertEqual((p[0].start, p[0].end, p[0].mirrored), (0, 50, False))
		self.assertEqual((p[8].start, p[8].end, p[8].mirrored), (865, 915, True))
		self.assertEqual((p[4].start, p[4].end), (422.5, 492.5))
		self.assertEqual((p[1].start, p[1].end, p[1].panel), (18, 78, "F1-S1"))
		self.assertEqual((p[3].start, p[3].end, p[3].mirrored), (392, 452, True))
		panes = compute(design, snap).glass
		self.assertEqual(p[2].end - p[2].start, panes[0].width)
		self.assertEqual((p[2].start, p[2].end), (68.5, 401.5))
		self.assertEqual((p[6].start, p[6].end, p[6].panel), (513.5, 846.5, "F1-S2"))
		self.assertEqual(section.issues, [])

	def test_123_vertical_cut_through_fixed_pane(self):
		section = cross_section(load("d123.json"), cs4800(), "v", widths=CS4800_WIDTHS)
		self.assertEqual(section.at, 375)
		self.assertEqual(
			sequence(section),
			[
				("profile", "CS4801"),
				("profile", "CS4808"),
				("glass", "12CTG"),
				("profile", "CS4808"),
				("profile", "CS4801"),
			],
		)
		frame_b, bead_b, glass, bead_t, frame_t = section.pieces
		self.assertEqual((glass.start, glass.end), (29.5, 1470.5))
		self.assertEqual(glass.end - glass.start, 1441)
		self.assertEqual((bead_b.start, bead_b.end, bead_b.role, bead_b.panel), (25.5, 45.5, "bead", "F1"))
		self.assertEqual((bead_t.start, bead_t.end, bead_t.mirrored), (1454.5, 1474.5, True))
		self.assertEqual((frame_t.start, frame_t.end), (1445, 1500))

	def test_123_horizontal_cut_crosses_sash_and_adaptor(self):
		section = cross_section(load("d123.json"), cs4800(), "h", widths=CS4800_WIDTHS)
		roles = [p.role for p in section.pieces]
		self.assertEqual(
			roles,
			["frame", "bead", "glass", "bead", "mullion", "sash", "glass_adaptor", "glass", "glass_adaptor", "sash", "frame"],
		)
		sash_glass = section.pieces[7]
		self.assertEqual(sash_glass.end - sash_glass.start, 613)
		mullion = section.pieces[4]
		self.assertEqual((mullion.start, mullion.end, mullion.panel), (715, 785, "M1"))

	def test_vertical_cut_crosses_transom(self):
		design = {
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
		section = cross_section(design, snapshot(), "v", at=1000, widths=CS400_WIDTHS)
		self.assertEqual(section.at, 1125)
		transom = [p for p in section.pieces if p.role == "transom"]
		self.assertEqual([(p.panel, p.start, p.end) for p in transom], [("T1", 965, 1035)])
		self.assertEqual([p.role for p in section.pieces][:4], ["frame", "sash", "glass", "sash"])
		cells = [(d.start, d.end) for d in section.dims if d.chain == "cells"]
		self.assertEqual(cells, [(0, 1000), (1000, 1500)])

	def test_cut_position_snaps_to_cell(self):
		design, snap = load("w01.json"), snapshot()
		cases = [("h", None, 610), ("h", 5000, 610), ("h", -10, 610), ("v", None, 228.75), ("v", 457.5, 686.25), ("v", 2000, 686.25)]
		for axis, at, expected in cases:
			with self.subTest(axis=axis, at=at):
				section = cross_section(design, snap, axis, at, CS400_WIDTHS)
				self.assertEqual(section.at, expected)
				self.assertTrue(any(p.kind == "glass" for p in section.pieces))

	def test_cut_reports_missing_widths(self):
		widths = {"E104156": 50}
		section = cross_section(load("w01.json"), snapshot(), "h", widths=widths)
		missing = [i for i in section.issues if i.code == "no_section_width"]
		self.assertEqual(sorted(i.message.split()[1] for i in missing), ["E104159", "E104160"])
		self.assertTrue(all(i.severity == "warn" for i in missing))
		sash, mullion = section.pieces[1], section.pieces[4]
		self.assertEqual(sash.end - sash.start, 50.5)  # sash_glass
		self.assertEqual(mullion.end - mullion.start, 48)  # 2 x bar_end_mullion

	def test_cut_is_deterministic(self):
		design, snap = load("d123.json"), cs4800()
		first = asdict(cross_section(design, snap, "h", None, CS4800_WIDTHS))
		second = asdict(cross_section(design, snap, "h", None, dict(reversed(CS4800_WIDTHS.items()))))
		self.assertEqual(first, second)

	def test_dims_cover_overall_cells_glass_and_profiles(self):
		section = cross_section(load("w01.json"), snapshot(), "h", widths=CS400_WIDTHS)
		chains = {}
		for d in section.dims:
			chains.setdefault(d.chain, []).append((d.start, d.end, d.label))
		self.assertEqual(chains["overall"], [(0, 915, "915")])
		self.assertEqual(chains["cells"], [(0, 457.5, "457.5"), (457.5, 915, "457.5")])
		self.assertEqual(chains["glass"], [(68.5, 401.5, "333"), (513.5, 846.5, "333")])
		self.assertEqual(len(chains["profiles"]), 7)

	def test_bad_axis(self):
		with self.assertRaises(DesignError):
			cross_section(load("w01.json"), snapshot(), "x")
		with self.assertRaises(DesignError):
			cross_section(load("w01.json"), snapshot(), "h", at="mid")

	def test_w02_louver_has_no_glass(self):
		section = cross_section(load("w02.json"), snapshot(), "v", widths=CS400_WIDTHS)
		self.assertEqual([p.role for p in section.pieces], ["frame", "frame"])
		section = cross_section(load("w02.json"), snapshot(), "h", widths=CS400_WIDTHS)
		self.assertEqual([p.role for p in section.pieces], ["frame", "mullion", "glass", "frame"])

	def test_glass_piece_has_thickness(self):
		section = cross_section(load("w01.json"), snapshot(), "h", widths=CS400_WIDTHS)
		glass = [p for p in section.pieces if p.kind == "glass"]
		self.assertTrue(glass)
		self.assertEqual({p.thickness for p in glass}, {6})
		self.assertEqual({p.thickness for p in section.pieces if p.kind == "profile"}, {0})
		self.assertEqual(asdict(glass[0])["thickness"], 6)
