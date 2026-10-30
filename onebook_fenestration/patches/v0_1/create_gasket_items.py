"""Create the gasket Items the glazing rules emit on sites that imported a series before the importer did."""

import frappe

from onebook_fenestration.series_studio.importer import ITEM_GROUP, ensure_gasket_items


def execute():
	if frappe.db.exists("Item Group", ITEM_GROUP):
		ensure_gasket_items()
