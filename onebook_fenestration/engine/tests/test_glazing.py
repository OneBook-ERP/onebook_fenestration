import unittest

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.glazing import glaze
from onebook_fenestration.engine.layout import layout
from onebook_fenestration.engine.members import cut_members
from onebook_fenestration.engine.tests.helpers import load, snapshot, snapshot_with


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
		g23 = sorted(b.length for b in compute(load("w01.json"), snapshot()).bom if b.item == "G23")
		self.assertEqual(g23, [305.0] * 4 + [1055.0] * 4)

	def test_w01_frame_gasket(self):
		g21 = sorted(b.length for b in compute(load("w01.json"), snapshot()).bom if b.item == "G21")
		self.assertEqual(g21, [434.0] * 4 + [915.0] * 2 + [1184.0] * 4 + [1220.0] * 2)

	def test_gaskets_come_from_rules(self):
		def lines(snap):
			return [
				(b.item, b.panel, b.position, b.length)
				for b in compute(load("w01.json"), snap).bom
				if b.group == "Gasket"
			]

		without = snapshot_with(
			lambda d: d.update(hardware_rules=[r for r in d["hardware_rules"] if r.get("group") != "Gasket"])
		)
		self.assertEqual(lines(without), [])
		with_rules = lines(snapshot())
		self.assertEqual(
			[x for x in with_rules if x[0] == "G21"],
			[
				("G21", "F1", "B", 915.0),
				("G21", "F1", "T", 915.0),
				("G21", "F1", "L", 1220.0),
				("G21", "F1", "R", 1220.0),
				("G21", "F1-S1", "B", 434.0),
				("G21", "F1-S1", "T", 434.0),
				("G21", "F1-S1", "L", 1184.0),
				("G21", "F1-S1", "R", 1184.0),
				("G21", "F1-S2", "B", 434.0),
				("G21", "F1-S2", "T", 434.0),
				("G21", "F1-S2", "L", 1184.0),
				("G21", "F1-S2", "R", 1184.0),
			],
		)
		self.assertEqual(
			[x for x in with_rules if x[0] == "G23"],
			[
				("G23", panel, pos, length)
				for panel in ("F1-S1", "F1-S2")
				for pos, length in (("W", 305.0), ("W", 305.0), ("H", 1055.0), ("H", 1055.0))
			],
		)

	def test_glass_without_gasket_rule_warns(self):
		# 8 mm glass: no fixture rule matches its thickness
		snap = snapshot_with(
			lambda d: d["glasses"].update({"8CTG": {"name": "8MM CLEAR", "thickness_mm": 8}})
		)
		design = load("w01.json")
		design["root"]["children"][0]["glass"] = "8CTG"
		base = compute(load("w01.json"), snapshot())
		result = compute(design, snap)
		warns = [i for i in result.issues if i.code == "no_glazing_gasket"]
		self.assertEqual(len(warns), 1)
		self.assertIn("8CTG", warns[0].message)
		self.assertEqual(warns[0].severity, "warn")
		self.assertEqual(
			[b for b in result.bom if b.item == "G23" and b.panel == "F1-S2"],
			[b for b in base.bom if b.item == "G23" and b.panel == "F1-S2"],
		)
		self.assertEqual(base.issues, [])

	def test_rule_note_is_optional(self):
		rule = {"id": "x", "item": "X", "name": "X", "per": "window", "qty": "1"}
		for extra in ({}, {"note": "ASSUMPTION: test"}):
			snap = snapshot_with(lambda d: d["hardware_rules"].append({**rule, **extra}))
			self.assertEqual(snap.hardware_rules[-1].note, extra.get("note", ""))

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
		panes, issues = run_glaze(design)
		self.assertEqual([(p.panel, p.width, p.height) for p in panes], [("F1", 690.0, 1440.0)])
		self.assertEqual(
			[(i.severity, i.code, i.panel) for i in issues], [("warn", "louver_placeholder", "F1")]
		)

	def test_unknown_glass_issue(self):
		design = {"width": 915, "height": 1220, "root": {"type": "fixed", "glass": "NOPE"}}
		panes, issues = run_glaze(design)
		self.assertEqual(panes, [])
		self.assertEqual([(i.severity, i.code, i.panel) for i in issues], [("error", "unknown_glass", "F1")])

	def test_missing_glass_is_unknown_glass(self):
		_, issues = run_glaze({"width": 915, "height": 1220, "root": {"type": "fixed"}})
		self.assertEqual([i.code for i in issues], ["unknown_glass"])

	def test_non_positive_glass_issue(self):
		design = {
			"width": 915,
			"height": 1220,
			"root": {
				"type": "split",
				"dir": "v",
				"at": [50],
				"children": [{"type": "fixed", "glass": "6CTG"}, {"type": "fixed", "glass": "6CTG"}],
			},
		}
		panes, issues = run_glaze(design)
		self.assertEqual([p.width for p in panes], [805.0])
		self.assertEqual(
			[(i.severity, i.code, i.panel) for i in issues], [("error", "non_positive_size", "F1")]
		)
