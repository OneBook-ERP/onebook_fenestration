import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from onebook_fenestration.setup.custom_fields import CUSTOM_FIELDS

ENGINEER_ROLE = "Fenestration Engineer"


def after_install():
	_sync()


def after_migrate():
	_sync()


def before_uninstall():
	for custom_field in frappe.get_all(
		"Custom Field",
		filters={"dt": ("in", list(CUSTOM_FIELDS)), "fieldname": ("like", "fen\\_%")},
		pluck="name",
	):
		frappe.delete_doc("Custom Field", custom_field, force=True)


def _sync():
	create_custom_fields(CUSTOM_FIELDS, update=True)
	_ensure_engineer_role()
	seed_pricing()


def _ensure_engineer_role():
	if frappe.db.exists("Role", ENGINEER_ROLE):
		return
	frappe.get_doc({"doctype": "Role", "role_name": ENGINEER_ROLE, "desk_access": 1}).insert(
		ignore_permissions=True
	)


STANDARD_HEADS = (
	("profile", "Profile Cost", "Formula", 0, "profile_cost", "", ""),
	("profile_waste", "Profile Wastage", "Percentage", 5, "", "profile", ""),
	("powder", "Powder Coating", "Per Visible Perimeter Sqft", 25, "", "", "finish_type == 'Powder Coat'"),
	("anodize", "Anodizing", "Per Total Perimeter Sqft", 40, "", "", "finish_type == 'Anodized'"),
	("wood", "Wood Finish", "Per Visible Perimeter Sqft", 70, "", "", "finish_type == 'Wood'"),
	("hardware", "Hardware Cost", "Formula", 0, "hardware_cost + gasket_cost", "", ""),
	("glass", "Glass Cost", "Formula", 0, "glass_cost", "", ""),
	("glass_waste", "Glass Wastage", "Percentage", 1, "", "glass", ""),
	("fabrication", "Fabrication Labour", "Per Area Sqft", 100, "", "", ""),
	("installation", "Installation Labour", "Per Area Sqft", 80, "", "", ""),
	(
		"profit",
		"Profit",
		"Percentage",
		20,
		"",
		"profile,profile_waste,powder,anodize,wood,hardware,glass,glass_waste,fabrication,installation",
		"",
	),
)
STANDARD_FINISHES = (
	("GREY", "Grey", "Powder Coat", "#8A8F98", 0),
	("BROWN-5104", "5104 PC Brown", "Powder Coat", "#6B3E26", 0),
	("MILL", "Mill Finish", "Mill", "#B8BCC2", 0),
	("WOOD", "Wooden Finish", "Wood", "#8B5A2B", 12),
)


def seed_pricing():
	"""Create the Standard price structure, finishes and Settings defaults; never overwrites existing data."""
	for code, name, finish_type, color, surcharge_pct in STANDARD_FINISHES:
		if not frappe.db.exists("Profile Finish", code):
			frappe.get_doc(
				{
					"doctype": "Profile Finish",
					"finish_code": code,
					"finish_name": name,
					"finish_type": finish_type,
					"color": color,
					"surcharge_pct": surcharge_pct,
				}
			).insert(ignore_permissions=True)
	if not frappe.db.exists("Price Structure", "Standard"):
		frappe.get_doc(
			{
				"doctype": "Price Structure",
				"structure_name": "Standard",
				"is_default": 1,
				"heads": [
					dict(zip(("key", "label", "calc", "rate", "formula", "base", "condition"), head, strict=True))
					for head in STANDARD_HEADS
				],
			}
		).insert(ignore_permissions=True)
	_seed_settings()


def _seed_settings():
	settings = frappe.get_single("Fenestration Settings")
	defaults = {
		"default_price_structure": "Standard",
		"default_finish": "GREY",
		"billing_area_basis": "Frame size",
		"cost_price_list": "Standard Selling" if frappe.db.exists("Price List", "Standard Selling") else None,
	}
	changed = False
	for fieldname, value in defaults.items():
		if value and not settings.get(fieldname):
			settings.set(fieldname, value)
			changed = True
	if changed:
		settings.save(ignore_permissions=True)
