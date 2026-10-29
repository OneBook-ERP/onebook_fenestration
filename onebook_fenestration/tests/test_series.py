import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.engine.types import REQUIRED_DEDUCTIONS


def make_masters():
	if not frappe.db.exists("Fenestration Glass", "TSTG6"):
		frappe.get_doc(
			{"doctype": "Fenestration Glass", "glass_code": "TSTG6", "glass_name": "Test 6mm", "thickness_mm": 6}
		).insert()
	if not frappe.db.exists("Profile Series", "TST1"):
		frappe.get_doc(
			{"doctype": "Profile Series", "series_code": "TST1", "series_title": "Test Series", "system_type": "Casement"}
		).insert()
	if not frappe.db.exists("Fenestration Profile", "TP1"):
		frappe.get_doc(
			{
				"doctype": "Fenestration Profile",
				"profile_code": "TP1",
				"profile_name": "Test Frame",
				"series": "TST1",
				"role": "frame",
				"kg_per_m": 0.649,
				"bar_lengths": "4880, 5800",
			}
		).insert()


def make_version(series="TST1"):
	"""A draft version carrying the full deduction set and glass_density."""
	return frappe.get_doc(
		{
			"doctype": "Series Version",
			"series": series,
			"deductions": [{"deduction_key": key, "value": 1} for key in REQUIRED_DEDUCTIONS],
			"constants": [{"constant_key": "glass_density", "value": 2.5}],
		}
	).insert()


class TestSeries(IntegrationTestCase):
	def setUp(self):
		make_masters()

	def test_create_glass_profile_series_version(self):
		version = make_version()
		self.assertTrue(version.name.startswith("TST1-V"))

	def test_submit_sets_published_version(self):
		version = make_version()
		version.submit()
		self.assertEqual(frappe.db.get_value("Profile Series", "TST1", "published_version"), version.name)

	def test_submitted_version_is_immutable(self):
		version = make_version()
		version.submit()
		version.deductions[0].value = 99
		with self.assertRaises(frappe.ValidationError):
			version.save()
