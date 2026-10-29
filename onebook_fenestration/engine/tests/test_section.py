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
