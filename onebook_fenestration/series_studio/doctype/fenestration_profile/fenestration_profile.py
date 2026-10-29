import frappe
from frappe import _
from frappe.model.document import Document

from onebook_fenestration.engine import SectionError, analyze_dxf

SECTION_FIELDS = (
	"area_mm2",
	"width_mm",
	"depth_mm",
	"perimeter_mm",
	"total_perimeter_mm",
	"ix_mm4",
	"iy_mm4",
	"computed_kg_per_m",
	"section_svg",
	"section_warnings",
)


class FenestrationProfile(Document):
	def validate(self):
		self.validate_bar_lengths()
		if not self.dxf_file:
			self.clear_section()
		elif self.has_value_changed("dxf_file") or not self.area_mm2:
			self.fill_section_from_dxf()

	def validate_bar_lengths(self):
		"""Bar lengths are comma-separated positive numbers, e.g. "4880, 5800"."""
		for part in (self.bar_lengths or "").split(","):
			if not part.strip():
				continue
			try:
				valid = float(part) > 0
			except ValueError:
				valid = False
			if not valid:
				frappe.throw(
					_("Bar Lengths must be comma-separated positive numbers, e.g. 4880, 5800 (got {0})").format(
						frappe.bold(part.strip())
					),
					title=_("Invalid Bar Lengths"),
				)

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
		self.total_perimeter_mm = self.perimeter_mm
		self.ix_mm4 = round(section.ix_mm4)
		self.iy_mm4 = round(section.iy_mm4)
		self.computed_kg_per_m = round(section.kg_per_m, 3)
		self.section_svg = section.svg_path
		self.section_warnings = ", ".join(section.warnings)
