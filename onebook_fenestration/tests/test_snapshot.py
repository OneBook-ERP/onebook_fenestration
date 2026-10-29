import json
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

import onebook_fenestration.engine.tests as engine_tests
from onebook_fenestration.engine import SeriesSnapshot, compute
from onebook_fenestration.series_studio.importer import import_snapshot_json
from onebook_fenestration.series_studio.snapshot import build_snapshot_dict, get_snapshot

FIXTURES = Path(engine_tests.__file__).parent / "fixtures"


def load(name: str) -> dict:
	return json.loads((FIXTURES / name).read_text())


class TestSnapshot(IntegrationTestCase):
	def setUp(self):
		self.data = load("cs400_snapshot.json")
		self.version = import_snapshot_json("CS400", self.data, "CS400 Economical Casement")

	def test_import_and_compute_w01(self):
		r = compute(load("w01.json"), get_snapshot(self.version))
		self.assertEqual(r.issues, [])
		self.assertEqual(r.area_sqft, 12.013)
		self.assertLessEqual(abs(r.window_kg - 20.698), 0.02)
		self.assertEqual(sum(line.qty for line in r.bom if line.item == "H912"), 10)

	def test_snapshot_dict_roundtrip_equals_fixture(self):
		built = SeriesSnapshot.from_dict(build_snapshot_dict(self.version))
		expected = SeriesSnapshot.from_dict(self.data)
		for section in ("deductions", "member_rules", "hardware_rules", "constants"):
			self.assertEqual(getattr(built, section), getattr(expected, section), section)

	def test_submit_incomplete_version_fails(self):
		version = frappe.get_doc({"doctype": "Series Version", "series": "CS400"}).insert()
		with self.assertRaises(frappe.ValidationError) as ctx:
			version.submit()
		self.assertIn("sash_glass", str(ctx.exception))

	def test_cache_cleared_on_cancel(self):
		get_snapshot(self.version)
		self.assertIsNotNone(frappe.cache.hget("fen_snapshot", self.version))
		frappe.get_doc("Series Version", self.version).cancel()
		self.assertIsNone(frappe.cache.hget("fen_snapshot", self.version))
