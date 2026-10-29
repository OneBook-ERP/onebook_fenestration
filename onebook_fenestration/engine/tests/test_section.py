import tempfile
import unittest
from pathlib import Path

import ezdxf

from onebook_fenestration.engine.section import analyze_dxf
from onebook_fenestration.engine.tests.helpers import fixture
from onebook_fenestration.engine.types import SectionError


class TestSection(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)

	def _save(self, doc, name):
		path = str(Path(self._tmp.name) / name)
		doc.saveas(path)
		return path

	def make_rect_dxf(self, w, h, insunits):
		doc = ezdxf.new()
		doc.header["$INSUNITS"] = insunits
		doc.modelspace().add_lwpolyline([(0, 0), (w, 0), (w, h), (0, h)], close=True)
		return self._save(doc, "rect.dxf")

	def make_line_only_dxf(self):
		doc = ezdxf.new()
		doc.modelspace().add_line((0, 0), (10, 0))
		return self._save(doc, "lines.dxf")

	def test_flush_cap_properties(self):
		p = analyze_dxf(fixture("flush_cap.dxf"))
		self.assertAlmostEqual(p.area_mm2, 1412.0, delta=1.0)
		self.assertAlmostEqual(p.width_mm, 154.3, delta=0.2)
		self.assertAlmostEqual(p.depth_mm, 48.0, delta=0.2)
		self.assertAlmostEqual(p.kg_per_m, 3.812, delta=0.005)
		self.assertEqual(p.loops, 2)
		self.assertTrue(p.svg_path.startswith("M"))

	def test_rectangle_inertia(self):
		p = analyze_dxf(self.make_rect_dxf(40, 20, insunits=4))
		self.assertAlmostEqual(p.ix_mm4, 40 * 20**3 / 12, delta=1)
		self.assertAlmostEqual(p.iy_mm4, 20 * 40**3 / 12, delta=1)

	def test_units_missing_warns(self):
		self.assertIn("units_assumed_mm", analyze_dxf(self.make_rect_dxf(40, 20, insunits=0)).warnings)

	def test_no_closed_loops(self):
		with self.assertRaises(SectionError):
			analyze_dxf(self.make_line_only_dxf())

	def test_unsupported_units_raise(self):
		with self.assertRaises(SectionError):
			analyze_dxf(self.make_rect_dxf(40, 20, insunits=2))

	def test_zero_area_raises(self):
		doc = ezdxf.new()
		doc.header["$INSUNITS"] = 4
		doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (20, 0)], close=True)
		with self.assertRaisesRegex(SectionError, "section area is zero"):
			analyze_dxf(self._save(doc, "zero.dxf"))

	def test_unreadable_file_raises(self):
		with self.assertRaisesRegex(SectionError, "cannot read DXF"):
			analyze_dxf(str(Path(self._tmp.name) / "missing.dxf"))

	def test_rectangle_with_hole_inertia(self):
		doc = ezdxf.new()
		doc.header["$INSUNITS"] = 4
		msp = doc.modelspace()
		msp.add_lwpolyline([(0, 0), (40, 0), (40, 20), (0, 20)], close=True)
		msp.add_lwpolyline([(10, 5), (10, 15), (30, 15), (30, 5)], close=True)
		p = analyze_dxf(self._save(doc, "hole.dxf"))
		self.assertAlmostEqual(p.area_mm2, 600, delta=0.01)
		self.assertAlmostEqual(p.ix_mm4, (40 * 20**3 - 20 * 10**3) / 12, delta=1)
		self.assertAlmostEqual(p.iy_mm4, (20 * 40**3 - 10 * 20**3) / 12, delta=1)
		self.assertEqual(p.loops, 2)

	def test_inch_scaling(self):
		p = analyze_dxf(self.make_rect_dxf(1, 0.5, insunits=1))
		self.assertAlmostEqual(p.area_mm2, 25.4 * 12.7, delta=0.01)
		self.assertAlmostEqual(p.ix_mm4, 25.4 * 12.7**3 / 12, delta=0.5)
