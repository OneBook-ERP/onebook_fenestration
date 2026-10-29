import unittest

from onebook_fenestration.engine.formula import evaluate, evaluate_number
from onebook_fenestration.engine.types import RuleError, SeriesSnapshot


class TestFormula(unittest.TestCase):
	def test_arithmetic(self):
		self.assertEqual(evaluate("span - d_start - d_end", {"span": 457.5, "d_start": 18, "d_end": 5.5}, "r1"), 434.0)

	def test_math_funcs(self):
		self.assertEqual(evaluate("ceil(len/500)", {"len": 1220}, "r2"), 3)

	def test_bool(self):
		self.assertIs(evaluate("position == 'B'", {"position": "B"}, "r3"), True)

	def test_unknown_variable_names_rule(self):
		with self.assertRaises(RuleError) as cm:
			evaluate("foo + 1", {}, "hw_hole_cap")
		self.assertIn("hw_hole_cap", str(cm.exception))
		self.assertIn("foo + 1", str(cm.exception))

	def test_syntax_error_names_rule(self):
		with self.assertRaises(RuleError):
			evaluate("len /", {"len": 1}, "r4")

	def test_snapshot_from_dict_roundtrip_minimal(self):
		s = SeriesSnapshot.from_dict(
			{
				"code": "X",
				"version": "1",
				"deductions": {},
				"profiles": {},
				"member_rules": [],
				"hardware_rules": [],
				"validation_rules": [],
				"glasses": {},
				"constants": {},
			}
		)
		self.assertEqual(s.code, "X")


class TestEvaluateNumber(unittest.TestCase):
	def test_int_result_is_float(self):
		value = evaluate_number("span", {"span": 915}, "mr_frame")
		self.assertIsInstance(value, float)
		self.assertEqual(value, 915.0)

	def test_non_numbers_raise_rule_error(self):
		for expr in ("'abc'", "None", "span > 0", "'2'"):
			with self.subTest(expr=expr), self.assertRaises(RuleError) as cm:
				evaluate_number(expr, {"span": 915}, "mr_frame")
			self.assertIn("mr_frame", str(cm.exception))
