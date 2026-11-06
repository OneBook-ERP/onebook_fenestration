import frappe
from frappe import _
from frappe.model.document import Document

from onebook_fenestration.engine import SectionError, analyze_dxf
from onebook_fenestration.series_studio.outline import rotate_path

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
		self.validate_bar_lengths()
		if not self.dxf_file:
			# Only drop DXF-derived geometry when the DXF itself was removed; imported outlines and the
			# commercial perimeters (visible/total) must survive plain saves.
			# is_new guard: has_value_changed is True on a new doc, so every insert would clear imported geometry
			if not self.is_new() and self.has_value_changed("dxf_file"):
				self.clear_section()
		elif self.has_value_changed("dxf_file") or not self.area_mm2:
			self.fill_section_from_dxf()
			if int(self.section_rotation or 0):
				self.apply_section_rotation()
			return
		if self.rotation_changed():
			self.apply_section_rotation()

	def rotation_changed(self) -> bool:
		# a new doc reports every field as changed; there only a non-zero rotation means anything
		if self.is_new():
			return bool(int(self.section_rotation or 0))
		return self.has_value_changed("section_rotation")

	def apply_section_rotation(self):
		"""width_mm / depth_mm become the outline's extents after `section_rotation` (face along the cut)."""
		if not self.section_svg:
			return
		try:
			_svg, self.width_mm, self.depth_mm = rotate_path(self.section_svg, self.section_rotation)
		except ValueError as exc:
			frappe.throw(
				_("Could not rotate the section outline: {0}").format(str(exc)), title=_("Section outline")
			)

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
					_(
						"Bar Lengths must be comma-separated positive numbers, e.g. 4880, 5800 (got {0})"
					).format(frappe.bold(part.strip())),
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
			frappe.throw(_("Could not read section from DXF: {0}").format(str(exc)), title=_("DXF error"))

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
