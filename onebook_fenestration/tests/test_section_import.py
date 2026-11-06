import os
import re
import tempfile

import ezdxf
import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.series_studio.section_import import import_profile_sections
from onebook_fenestration.tests.test_series import make_masters

TEXT_HEIGHT = 7


def rectangle(space, x, y, width, height):
	corners = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
	for start, end in zip(corners, corners[1:] + corners[:1], strict=True):
		space.add_line(start, end)


def build_dxf(path):
	"""Synthetic "Section Details" table: rows TSTA, TSTB (and TSTZ, which has no profile) plus decoys."""
	doc = ezdxf.new("R2018")
	msp = doc.modelspace()
	msp.add_mtext("\\LSection  Drawing\\l", dxfattribs={"insert": (80, 1010), "char_height": TEXT_HEIGHT})
	for text, x in (("Profile Description", 250), ("Profile Code", 320), ("Standard Bar", 380)):
		msp.add_mtext(
			text, dxfattribs={"insert": (x, 1005), "char_height": TEXT_HEIGHT, "attachment_point": 5}
		)
	for code, y in (("TSTA", 950), ("TSTB", 870), ("TSTZ", 790)):
		msp.add_mtext(code, dxfattribs={"insert": (305, y), "char_height": TEXT_HEIGHT})
		msp.add_text("5800mm", height=TEXT_HEIGHT).set_placement((345, y))
	# table grid: horizontal row lines across the whole table, vertical column lines down it
	for y in (990, 910, 830, 750):
		msp.add_line((50, y), (450, y))
	for x in (50, 200, 290, 340):
		msp.add_line((x, 750), (x, 1020))
	# TSTA: 40 x 25 rectangle of loose lines with an arc inside it, and hatching that must not count
	rectangle(msp, 90, 925, 40, 25)
	msp.add_arc((110, 937), radius=8, start_angle=0, end_angle=180)
	msp.add_text("40", height=TEXT_HEIGHT).set_placement((60, 960))
	# TSTB: 30 x 50 closed polyline inside a block INSERT, plus an ellipse inside it
	block = doc.blocks.new("TSTB_SECTION")
	block.add_lwpolyline([(0, 0), (30, 0), (30, 50), (0, 50)], close=True)
	block.add_ellipse((15, 25), major_axis=(10, 0), ratio=0.5)
	msp.add_blockref("TSTB_SECTION", (100, 845))
	# TSTZ: a small square
	rectangle(msp, 100, 780, 10, 10)
	# decoy: the same code elsewhere in the drawing with big geometry next to it
	msp.add_mtext("TSTA", dxfattribs={"insert": (2000, 500), "char_height": TEXT_HEIGHT})
	rectangle(msp, 1900, 450, 300, 200)
	doc.saveas(path)


def svg_points(svg):
	numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", svg)]
	return list(zip(numbers[0::2], numbers[1::2], strict=True))


def svg_bbox(svg):
	xs, ys = zip(*svg_points(svg), strict=True)
	return min(xs), min(ys), max(xs), max(ys)


def make_profile(code):
	if not frappe.db.exists("Fenestration Profile", code):
		frappe.get_doc(
			{
				"doctype": "Fenestration Profile",
				"profile_code": code,
				"profile_name": f"Section import {code}",
				"series": "TST1",
				"role": "frame",
				"kg_per_m": 1.234,
				"bar_lengths": "5800",
				"visible_perimeter_mm": 11,
				"total_perimeter_mm": 22,
			}
		).insert()


class TestSectionImport(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.tmp = tempfile.mkdtemp()
		cls.path = os.path.join(cls.tmp, "section-details.dxf")
		build_dxf(cls.path)

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		make_masters()
		for code in ("TSTA", "TSTB"):
			make_profile(code)
			# rollback is per class, so undo what an earlier test of this class did
			frappe.db.set_value("Fenestration Profile", code, {"dxf_file": None, "section_svg": None})

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_rows_become_normalised_svg(self):
		result = import_profile_sections(self.path, ["TSTA", "TSTB"])
		self.assertEqual(sorted(result["updated"]), ["TSTA", "TSTB"])
		self.assertEqual(result["skipped"], [])
		for code, (width, depth) in (("TSTA", (40, 25)), ("TSTB", (30, 50))):
			profile = frappe.get_doc("Fenestration Profile", code)
			self.assertAlmostEqual(profile.width_mm, width, delta=0.01)
			self.assertAlmostEqual(profile.depth_mm, depth, delta=0.01)
			self.assertTrue(profile.section_svg.startswith("M"))
			min_x, min_y, max_x, max_y = svg_bbox(profile.section_svg)
			self.assertAlmostEqual(min_x, 0, delta=0.01)
			self.assertAlmostEqual(min_y, 0, delta=0.01)
			self.assertAlmostEqual(max_x, width, delta=0.01)
			self.assertAlmostEqual(max_y, depth, delta=0.01)
			# commercial data untouched
			self.assertEqual(
				(profile.kg_per_m, profile.visible_perimeter_mm, profile.total_perimeter_mm), (1.234, 11, 22)
			)

	def test_y_axis_is_flipped(self):
		import_profile_sections(self.path, ["TSTA"])
		points = svg_points(frappe.db.get_value("Fenestration Profile", "TSTA", "section_svg"))
		# the arc's top (110, 945) in the DXF is 5 mm below the rectangle's top edge (y = 950) in SVG, y down
		self.assertTrue(any(abs(x - 20) < 0.01 and abs(y - 5) < 0.01 for x, y in points))
		self.assertFalse(any(abs(x - 20) < 0.01 and abs(y - 20) < 0.01 for x, y in points))

	def test_profile_with_own_dxf_is_skipped(self):
		frappe.db.set_value(
			"Fenestration Profile", "TSTB", {"dxf_file": "/private/files/own.dxf", "section_svg": "M0 0 L1 1"}
		)
		result = import_profile_sections(self.path, ["TSTA", "TSTB"])
		self.assertEqual(result["updated"], ["TSTA"])
		self.assertEqual([s["code"] for s in result["skipped"]], ["TSTB"])
		self.assertTrue(result["skipped"][0]["reason"])
		self.assertEqual(frappe.db.get_value("Fenestration Profile", "TSTB", "section_svg"), "M0 0 L1 1")

	def test_unknown_code_is_skipped(self):
		result = import_profile_sections(self.path, ["TSTA", "TSTNOPE"])
		self.assertEqual(result["updated"], ["TSTA"])
		self.assertEqual([s["code"] for s in result["skipped"]], ["TSTNOPE"])
		result = import_profile_sections(self.path)
		self.assertIn("TSTZ", [s["code"] for s in result["skipped"]])
		self.assertEqual(sorted(result["updated"]), ["TSTA", "TSTB"])

	def test_needs_system_manager(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			import_profile_sections(self.path)
