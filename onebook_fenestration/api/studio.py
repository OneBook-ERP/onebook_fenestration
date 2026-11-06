import frappe
from frappe import _

from onebook_fenestration.engine import SectionError, analyze_dxf


@frappe.whitelist()
def preview_dxf(file_url: str) -> dict:
	"""Analyze an uploaded DXF file and return its computed cross-section properties and SVG path."""
	frappe.has_permission("Fenestration Profile", "read", throw=True)
	if not file_url:
		return {"ok": False, "message": _("No DXF file URL provided")}
	try:
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		section = analyze_dxf(file_doc.get_full_path())
	except (SectionError, frappe.DoesNotExistError, OSError) as exc:
		return {"ok": False, "message": _("Could not read section from DXF: {0}").format(exc)}

	return {
		"ok": True,
		"section": {
			"area_mm2": round(section.area_mm2, 1),
			"width_mm": round(section.width_mm, 1),
			"depth_mm": round(section.depth_mm, 1),
			"perimeter_mm": round(section.perimeter_mm, 1),
			"total_perimeter_mm": round(section.perimeter_mm, 1),
			"ix_mm4": round(section.ix_mm4),
			"iy_mm4": round(section.iy_mm4),
			"computed_kg_per_m": round(section.kg_per_m, 3),
			"section_svg": section.svg_path,
			"section_warnings": ", ".join(section.warnings),
		},
	}

