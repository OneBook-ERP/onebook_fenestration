import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from onebook_fenestration.engine import SectionError, analyze_dxf
from onebook_fenestration.series_studio.outline import transform_path

_SAFE_SVG_PATH_RE = re.compile(r"^[0-9eE.+\-,\sMLAZmlazHVCSQThvcsqt]*$")

SECTION_FIELDS = (
	"area_mm2",
	"width_mm",
	"depth_mm",
	"perimeter_mm",
	"section_svg",
	"section_warnings",
)


class FenestrationHardware(Document):
	def validate(self):
		if not self.dxf_file:
			if not self.is_new() and self.has_value_changed("dxf_file"):
				self.clear_section()
		elif self.has_value_changed("dxf_file") or not self.section_svg:
			self.fill_section_from_dxf()
			if (
				int(self.section_rotation or 0)
				or int(getattr(self, "section_flip_x", 0) or 0)
				or int(getattr(self, "section_flip_y", 0) or 0)
			):
				self.apply_section_rotation()
			return
		if self.rotation_changed():
			self.apply_section_rotation()
		if self.section_svg and not _SAFE_SVG_PATH_RE.match(self.section_svg):
			frappe.throw(_("Section SVG contains unsupported characters."), title=_("Section outline"))

	def rotation_changed(self) -> bool:
		if self.is_new():
			return bool(
				int(self.section_rotation or 0)
				or int(getattr(self, "section_flip_x", 0) or 0)
				or int(getattr(self, "section_flip_y", 0) or 0)
			)
		return (
			self.has_value_changed("section_rotation")
			or self.has_value_changed("section_flip_x")
			or self.has_value_changed("section_flip_y")
		)

	def apply_section_rotation(self):
		if not self.section_svg:
			return
		try:
			_svg, self.width_mm, self.depth_mm = transform_path(
				self.section_svg,
				self.section_rotation,
				cint(getattr(self, "section_flip_x", 0)),
				cint(getattr(self, "section_flip_y", 0)),
			)
		except ValueError as exc:
			frappe.throw(
				_("Could not rotate the hardware section outline: {0}").format(str(exc)),
				title=_("Section outline"),
			)

	def clear_section(self):
		for fieldname in SECTION_FIELDS:
			self.set(fieldname, None)

	def fill_section_from_dxf(self):
		try:
			file_doc = frappe.get_doc("File", {"file_url": self.dxf_file})
			file_doc.check_permission("read")
			section = analyze_dxf(file_doc.get_full_path())
		except frappe.PermissionError:
			raise
		except OSError:
			frappe.throw(_("Could not read the attached DXF file from storage."), title=_("DXF error"))
		except (SectionError, frappe.DoesNotExistError) as exc:
			frappe.throw(_("Could not read section from DXF: {0}").format(str(exc)), title=_("DXF error"))

		self.area_mm2 = round(section.area_mm2, 1)
		self.width_mm = round(section.width_mm, 1)
		self.depth_mm = round(section.depth_mm, 1)
		self.perimeter_mm = round(section.perimeter_mm, 1)
		self.section_svg = section.svg_path
		self.section_warnings = ", ".join(section.warnings)

