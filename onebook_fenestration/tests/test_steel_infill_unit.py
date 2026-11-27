"""Steel infill must never be procured or charged as its previous glass selection."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.tests.helpers import snapshot
from onebook_fenestration.pricing import rates
from onebook_fenestration.production import bom


class TestSteelInfill(unittest.TestCase):
	def design(self):
		return {"width": 600, "height": 600, "root": {"type": "fixed", "glass": "6CTG", "fan": True}}

	def test_steel_does_not_request_glass_rates(self):
		result = compute(self.design(), snapshot())
		with patch.object(rates, "_item_map", return_value={}) as items:
			rates._linked_items(result)
		glass_codes = next(c.args[2] for c in items.call_args_list if c.args[0] == "Fenestration Glass")
		self.assertEqual(glass_codes, set())

	def test_bom_reports_missing_steel_item_instead_of_ordering_glass(self):
		doc = SimpleNamespace(name="TEST", series_version="SV1", design_json=self.design())
		db = MagicMock()
		db.get_value.return_value = "ITEM"
		with patch.object(bom, "get_snapshot", return_value=snapshot()), patch.object(bom.frappe, "db", db, create=True), patch.object(bom, "_unit_problem", return_value=None), patch.object(bom, "_", side_effect=lambda s: s):
			rows, problems = bom.collect_rows(doc)
		self.assertTrue(any("steel sheet 1.2 mm (F1)" in p for p in problems))
		self.assertFalse(any(c.args[0] == "Fenestration Glass" for c in db.get_value.call_args_list))
		self.assertFalse(any(r["uom"] == "Square Meter" for r in rows))
