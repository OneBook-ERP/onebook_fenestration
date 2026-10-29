import frappe
from frappe import _
from frappe.model.document import Document

from onebook_fenestration.engine import SectionError, analyze_dxf

SECTION_FIELDS = (
	"area_mm2",
	"width_mm",
	"depth_mm",
	"perimeter_mm",
	"ix_mm4",
	"iy_mm4",
	"computed_kg_per_m",
	"section_svg",
	"section_warnings",
)


class FenestrationProfile(Document):
	def validate(self):
		if not self.dxf_file:
			self.clear_section()
		elif self.has_value_changed("dxf_file") or not self.area_mm2:
			self.fill_section_from_dxf()

	def clear_section(self):
		for fieldname in SECTION_FIELDS:
			self.set(fieldname, None)

	def fill_section_from_dxf(self):
		try:
			file_doc = frappe.get_doc("File", {"file_url": self.dxf_file})
			section = analyze_dxf(file_doc.get_full_path())
		except (SectionError, frappe.DoesNotExistError, OSError) as exc:
			frappe.throw(_("Could not read section from DXF: {0}").format(exc), title=_("DXF error"))

		self.area_mm2 = round(section.area_mm2, 1)
		self.width_mm = round(section.width_mm, 1)
		self.depth_mm = round(section.depth_mm, 1)
		self.perimeter_mm = round(section.perimeter_mm, 1)
		self.ix_mm4 = round(section.ix_mm4)
		self.iy_mm4 = round(section.iy_mm4)
		self.computed_kg_per_m = round(section.kg_per_m, 3)
		self.section_svg = section.svg_path
		self.section_warnings = ", ".join(section.warnings)
