import unittest

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.tests.helpers import load, snapshot, snapshot_with
from onebook_fenestration.engine.types import RuleError


class TestSnapshotCheck(unittest.TestCase):
	def assertRuleError(self, mutate, *needles):
		snap = snapshot_with(mutate)
		with self.assertRaises(RuleError) as cm:
			snap.check()
		for needle in needles:
			self.assertIn(needle, str(cm.exception))
		with self.assertRaises(RuleError):
			compute(load("w01.json"), snap)

	def test_fixture_snapshot_passes(self):
		snapshot().check()

	def test_missing_deduction_keys_are_listed(self):
		def drop(data):
			del data["deductions"]["sash_glass"]
			del data["deductions"]["bar_end_transom"]

		self.assertRuleError(drop, "sash_glass", "bar_end_transom")

	def test_unknown_member_profile(self):
		self.assertRuleError(lambda d: d["member_rules"][0].update(profile="NOPE"), "mr_frame", "NOPE")

	def test_missing_glass_density(self):
		self.assertRuleError(lambda d: d["constants"].pop("glass_density"), "glass_density")

	def test_unknown_hardware_per(self):
		self.assertRuleError(lambda d: d["hardware_rules"][0].update(per="corner"), "hw_corner_cleat_frame", "corner")


class TestSnapshotFromDict(unittest.TestCase):
	def test_ignores_unknown_keys_in_rows(self):
		def add_db_columns(data):
			extra = {"idx": 1, "parent": "CS400", "doctype": "Series Row"}
			for table in ("member_rules", "hardware_rules", "validation_rules"):
				for row in data[table]:
					row.update(extra)
			for table in ("member_rules", "validation_rules"):
				for row in data[table]:
					row["name"] = f"{table}-{row['id']}"
			for entries in (data["profiles"], data["glasses"]):
				for row in entries.values():
					row.update(extra)

		snap = snapshot_with(add_db_columns)
		self.assertEqual(snap, snapshot())

	def test_missing_row_key_raises_rule_error(self):
		with self.assertRaises(RuleError) as cm:
			snapshot_with(lambda d: d["member_rules"][0].pop("length"))
		self.assertIn("mr_frame", str(cm.exception))
		self.assertIn("length", str(cm.exception))


class TestFormulaResultTypes(unittest.TestCase):
	def test_member_length_must_be_number(self):
		for expr in ("'abc'", "None", "span > 0"):
			snap = snapshot_with(lambda d: d["member_rules"][0].update(length=expr))
			with self.subTest(expr=expr), self.assertRaisesRegex(RuleError, "mr_frame"):
				compute(load("w01.json"), snap)

	def test_hardware_qty_must_be_number(self):
		snap = snapshot_with(lambda d: d["hardware_rules"][0].update(qty="'2'"))
		with self.assertRaisesRegex(RuleError, "hw_corner_cleat_frame"):
			compute(load("w01.json"), snap)

	def test_hardware_length_must_be_number(self):
		snap = snapshot_with(lambda d: d["hardware_rules"][-2].update(length="'8.54'"))
		with self.assertRaisesRegex(RuleError, "hw_masking_tape"):
			compute(load("w01.json"), snap)


class TestCompute(unittest.TestCase):
	def test_w01_has_no_issues(self):
		self.assertEqual(compute(load("w01.json"), snapshot()).issues, [])

	def test_design_error_propagates(self):
		from onebook_fenestration.engine.types import DesignError

		with self.assertRaisesRegex(DesignError, "F1"):
			compute({"width": 915, "height": 1220}, snapshot())

	def test_cut_lengths_are_floats(self):
		self.assertTrue(all(isinstance(m.length, float) for m in compute(load("w01.json"), snapshot()).members))


class TestResultPaths(unittest.TestCase):
	def test_w01_member_and_pane_paths(self):
		r = compute(load("w01.json"), snapshot())
		self.assertEqual(
			sorted({(m.panel, m.role, m.path) for m in r.members}),
			[("F1", "frame", "F1"), ("F1", "mullion", "M1"), ("F1-S1", "sash", "F1.0"), ("F1-S2", "sash", "F1.1")],
		)
		self.assertEqual([(p.panel, p.path) for p in r.glass], [("F1-S1", "F1.0"), ("F1-S2", "F1.1")])

	def test_fixed_pane_and_bar_issue_paths(self):
		design = {
			"width": 915,
			"height": 40,
			"root": {"type": "split", "dir": "v", "at": [457.5], "children": [{"type": "fixed", "glass": "6CTG"}, {"type": "louver"}]},
		}
		r = compute(design, snapshot())
		self.assertEqual(
			[(i.code, i.path) for i in r.issues],
			[("non_positive_size", "M1"), ("non_positive_size", "F1.0"), ("louver_placeholder", "F1.1")],
		)

	def test_sash_and_validation_issue_paths(self):
		r = compute({"width": 30, "height": 1220, "root": {"type": "sash", "glass": "6CTG"}}, snapshot())
		self.assertEqual([(i.code, i.path) for i in r.issues], [("non_positive_size", "F1")])
		heavy = compute(load("wall_12x6.json"), snapshot())
		self.assertIn(("v_shutter_kg", "F1-S1", "F1.0"), [(i.code, i.panel, i.path) for i in heavy.issues])
