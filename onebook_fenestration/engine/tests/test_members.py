import unittest

from onebook_fenestration.engine import compute
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
		members, issues, sash_sizes = run(d)
		self.assertTrue(any(i.code == "non_positive_size" for i in issues))
		self.assertEqual(len([m for m in members if m.panel == "F1"]), 4)
		self.assertEqual([m for m in members if m.panel == "F1-S1"], [])
		self.assertEqual(sash_sizes, {})
		self.assertEqual([(i.severity, i.code, i.panel) for i in issues], [("error", "non_positive_size", "F1-S1")])

	def test_partly_invalid_sash_gets_no_weight_or_hardware(self):
		from onebook_fenestration.engine import compute
		from onebook_fenestration.engine.tests.helpers import snapshot

		r = compute({"width": 30, "height": 1220, "root": {"type": "sash", "glass": "6CTG"}}, snapshot())
		self.assertEqual(r.shutter_kg, {})
		self.assertEqual([b for b in r.bom if b.panel == "F1-S1"], [])
		self.assertEqual([i.code for i in r.issues], ["non_positive_size"])


FIXED_6 = {"width": 1000, "height": 800, "root": {"type": "fixed", "glass": "6CTG"}}


def with_bead_rule(when: str):
	"""CS400 fixture plus one bead rule (reusing the sash profile) and the glass member constants."""
	from onebook_fenestration.engine.tests.helpers import snapshot_with

	def mutate(data):
		data["member_rules"].append(
			{
				"id": "t_bead",
				"role": "bead",
				"profile": "E104160",
				"angles": [90, 90],
				"when": when,
				"length": "opening_w if position in 'TB' else opening_h - 2*bead_depth",
			}
		)
		data["constants"].update({"glass_clearance": 4, "bead_depth": 20})

	return snapshot_with(mutate)


class TestMemberRuleWhen(unittest.TestCase):
	def test_member_rule_when_false_yields_nothing(self):
		result = compute(FIXED_6, with_bead_rule("glass_t > 100"))
		self.assertEqual([m for m in result.members if m.role == "bead"], [])

	def test_member_rule_when_true_yields_one_member_per_pane_side(self):
		result = compute(FIXED_6, with_bead_rule("glass_t == 6 and glass == '6CTG'"))
		pane = result.glass[0]
		beads = sorted(
			(m.panel, m.position, m.length, m.angles, m.path) for m in result.members if m.role == "bead"
		)
		w, h = pane.width + 8, pane.height + 8 - 40
		self.assertEqual(
			beads,
			sorted(
				[("F1", p, w, (90, 90), "F1") for p in "BT"] + [("F1", p, h, (90, 90), "F1") for p in "LR"]
			),
		)

	def test_empty_when_means_always(self):
		result = compute(FIXED_6, with_bead_rule(""))
		self.assertEqual(len([m for m in result.members if m.role == "bead"]), 4)

	def test_beads_only_on_fixed_panes(self):
		design = {"width": 1000, "height": 800, "root": {"type": "sash", "glass": "6CTG"}}
		result = compute(design, with_bead_rule("True"))
		self.assertEqual([m for m in result.members if m.role == "bead"], [])

	def test_fixed_pane_without_bead_warns(self):
		result = compute(FIXED_6, with_bead_rule("glass_t > 100"))
		self.assertIn(
			("warn", "no_glazing_bead", "F1"), [(i.severity, i.code, i.panel) for i in result.issues]
		)

	def test_bead_rules_need_glass_clearance(self):
		from onebook_fenestration.engine.tests.helpers import snapshot_with
		from onebook_fenestration.engine.types import RuleError

		snap = snapshot_with(
			lambda d: d["member_rules"].append(
				{
					"id": "t_bead",
					"role": "bead",
					"profile": "E104160",
					"angles": [90, 90],
					"length": "opening_w",
				}
			)
		)
		with self.assertRaisesRegex(RuleError, "glass_clearance"):
			snap.check()

	def test_when_on_structural_rule_picks_first_match(self):
		from onebook_fenestration.engine.tests.helpers import snapshot_with

		def mutate(data):
			frame = data["member_rules"][0]
			data["member_rules"].insert(
				0, {**frame, "id": "mr_frame_big", "profile": "E104159", "when": "span > 5000"}
			)

		members, _, _ = cut_members(FIXED_6, snapshot_with(mutate), *layout(FIXED_6))
		self.assertEqual({m.profile for m in members if m.role == "frame"}, {"E104156"})

	def test_adaptor_counts_in_its_shutter_weight(self):
		from onebook_fenestration.engine.tests.helpers import snapshot_with

		design = {"width": 1000, "height": 800, "root": {"type": "sash", "glass": "6CTG"}}

		def mutate(data):
			data["member_rules"].append(
				{
					"id": "t_adaptor",
					"role": "glass_adaptor",
					"profile": "E104159",
					"angles": [45, 135],
					"length": "opening_w if position in 'TB' else opening_h",
				}
			)
			data["constants"]["glass_clearance"] = 4

		base, with_adaptor = compute(design, snapshot()), compute(design, snapshot_with(mutate))
		adaptors = [m for m in with_adaptor.members if m.role == "glass_adaptor"]
		self.assertEqual({m.panel for m in adaptors}, {"F1-S1"})
		extra = sum(m.length for m in adaptors) / 1000 * 0.809
		self.assertAlmostEqual(with_adaptor.shutter_kg["F1-S1"], base.shutter_kg["F1-S1"] + extra, places=2)
		self.assertAlmostEqual(with_adaptor.window_kg, base.window_kg + extra, places=2)

	def test_cs400_has_no_bead_members(self):
		from onebook_fenestration.engine.tests.test_series_data import series_snapshot

		for snap in (snapshot(), series_snapshot("CS400")):
			for design in ("w01.json", "w02.json"):
				with self.subTest(series=snap.version, design=design):
					roles = {m.role for m in compute(load(design), snap).members}
					self.assertLessEqual(roles, {"frame", "sash", "mullion", "transom"})
