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


def import_cs400() -> str:
	return import_snapshot_json("CS400", load("cs400_snapshot.json"), "CS400 Economical Casement")


class TestSnapshot(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.data = load("cs400_snapshot.json")
		cls.version = import_cs400()

	@classmethod
	def tearDownClass(cls):
		frappe.cache.hdel("fen_snapshot", cls.version)
		super().tearDownClass()

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
		version = import_cs400()
		get_snapshot(version)
		self.assertIsNotNone(frappe.cache.hget("fen_snapshot", version))
		frappe.get_doc("Series Version", version).cancel()
		self.assertIsNone(frappe.cache.hget("fen_snapshot", version))

	def test_draft_never_served_from_cache(self):
		draft = frappe.get_doc({"doctype": "Series Version", "series": "CS400"}).insert()
		bogus = {**self.data, "code": "BOGUS", "version": draft.name}
		frappe.cache.hset("fen_snapshot", draft.name, bogus)
		snap = get_snapshot(draft.name)
		self.assertEqual(snap.code, "CS400")
		self.assertEqual(snap.deductions, {})

	def test_published_version_frozen_against_master_edits(self):
		version = import_cs400()
		old_kg = get_snapshot(version).profiles["E104156"].kg_per_m
		frappe.cache.hdel("fen_snapshot", version)
		profile = frappe.get_doc("Fenestration Profile", "E104156")
		profile.kg_per_m = old_kg + 0.1
		profile.save()
		self.assertEqual(get_snapshot(version).profiles["E104156"].kg_per_m, old_kg)
		draft = frappe.get_doc({"doctype": "Series Version", "series": "CS400"}).insert()
		self.assertEqual(get_snapshot(draft.name).profiles["E104156"].kg_per_m, old_kg + 0.1)
		frappe.cache.hdel("fen_snapshot", version)

	def test_amend_flow(self):
		original = import_cs400()
		frappe.get_doc("Series Version", original).cancel()
		amended = frappe.copy_doc(frappe.get_doc("Series Version", original))
		amended.docstatus = 0
		amended.amended_from = original
		amended.insert()
		amended.submit()
		self.assertEqual(amended.name, f"{original}-1")
		self.assertEqual(frappe.db.get_value("Series Version", amended.name, "amended_from"), original)
		self.assertEqual(frappe.db.get_value("Profile Series", "CS400", "published_version"), amended.name)
		older = import_cs400()
		newer = import_cs400()
		frappe.get_doc("Series Version", older).cancel()
		self.assertEqual(frappe.db.get_value("Profile Series", "CS400", "published_version"), newer)
		for name in (original, amended.name, older, newer):
			frappe.cache.hdel("fen_snapshot", name)
