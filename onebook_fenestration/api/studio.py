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


@frappe.whitelist(methods=["POST"])
def set_profile_orientation(profile_name: str, rotation: int | str | None = None, delta: int | str | None = None) -> dict:
	"""Set the default section orientation (0, 90, 180, 270) on a Fenestration Profile.

	Accepts either an absolute `rotation` or an incremental `delta` relative to the profile's current rotation.
	"""
	frappe.has_permission("Fenestration Profile", "write", throw=True)
	if not frappe.db.exists("Fenestration Profile", profile_name):
		actual_name = frappe.db.get_value("Fenestration Profile", {"profile_code": profile_name}, "name")
		if actual_name:
			profile_name = actual_name
	doc = frappe.get_doc("Fenestration Profile", profile_name)
	if delta is not None and str(delta).strip():
		cur_rot = int(doc.section_rotation or 0)
		rot_int = (cur_rot + int(delta)) % 360
	else:
		rot_int = int(rotation or 0) % 360
	if rot_int not in (0, 90, 180, 270):
		frappe.throw(_("Rotation must be 0, 90, 180, or 270 degrees."))
	doc.section_rotation = str(rot_int)
	doc.save()
	return {
		"ok": True,
		"profile_name": doc.name,
		"section_rotation": doc.section_rotation,
		"width_mm": doc.width_mm,
		"depth_mm": doc.depth_mm,
	}


