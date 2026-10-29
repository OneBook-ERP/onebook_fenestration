from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.tests.test_series import make_masters

FIXTURE = Path(__file__).parent.parent / "engine" / "tests" / "fixtures" / "flush_cap.dxf"


def make_file(content):
	return frappe.get_doc(
		{"doctype": "File", "file_name": "flush_cap.dxf", "content": content, "is_private": 1}
	).insert()


def profile_doc(code, file_url):
	return frappe.get_doc(
		{
			"doctype": "Fenestration Profile",
			"profile_code": code,
			"profile_name": "DXF Test",
			"series": "TST1",
			"role": "frame",
			"kg_per_m": 1,
			"bar_lengths": "5800",
			"dxf_file": file_url,
		}
	)


class TestProfileDxf(IntegrationTestCase):
	def setUp(self):
		make_masters()

	def test_flush_cap_fills_section(self):
		file_doc = make_file(FIXTURE.read_bytes())
		profile = profile_doc("TPDXF1", file_doc.file_url).insert()
		self.assertAlmostEqual(profile.area_mm2, 1412.0, delta=1)
		self.assertAlmostEqual(profile.computed_kg_per_m, 3.812, delta=0.005)
		self.assertTrue(profile.section_svg.startswith("M"))

	def test_bad_dxf_message(self):
		file_doc = make_file(b"not a dxf")
		with self.assertRaises(frappe.ValidationError) as ctx:
			profile_doc("TPDXF2", file_doc.file_url).insert()
		self.assertIn("Could not read section from DXF", str(ctx.exception))
