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


def _ensure_engineer_role():
	if frappe.db.exists("Role", ENGINEER_ROLE):
		return
	frappe.get_doc({"doctype": "Role", "role_name": ENGINEER_ROLE, "desk_access": 1}).insert(
		ignore_permissions=True
	)
