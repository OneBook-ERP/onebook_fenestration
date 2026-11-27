"""Idempotent procurement, warehouse, payment-term, supplier, and UOM seeding."""

import json

import frappe
from frappe.utils import flt
from frappe.utils.nestedset import rebuild_tree

from onebook_fenestration.fenestration.doctype.fenestration_project.fenestration_project import (
	default_company,
)
from onebook_fenestration.fenestration.quote_party import company_address

SUPPLIER_GROUPS = ("Extrusions", "Glass")
MAIN_GROUP_WAREHOUSE = "Main Warehouse"
MAIN_CHILD_WAREHOUSES = ("Finished Goods", "Goods In Transit", "Stores", "Work In Progress")
LEAF_WAREHOUSES = ("Hilux Warehouse",)
DEFAULT_SUPPLIERS = (
	("Hilux Aluminium Extrusions", "Extrusions", "50% Advance + Balance Net 7"),
	("Hilux Toughened Glass", "Glass", "Net 30"),
	("Hilux Hardware & Gaskets", "All Supplier Groups", "Net 7"),
)
DEFAULT_PROFILE_BUYING_RATE = 320.0
DEFAULT_PROFILE_SELLING_RATE = 360.0
DEFAULT_HARDWARE_RATES = {
	"H422A": (260.0, 360.0),
	"H422B": (290.0, 400.0),
}
PAYMENT_TERMS = (
	("Net 7", 100.0, "Day(s) after invoice date", 7),
	("Net 30", 100.0, "Day(s) after invoice date", 30),
	("50% Advance", 50.0, "Day(s) after invoice date", 0),
	("50% Balance Net 7", 50.0, "Day(s) after invoice date", 7),
)
PAYMENT_TEMPLATES = (
	("Net 7", ("Net 7",)),
	("Net 30", ("Net 30",)),
	("50% Advance + Balance Net 7", ("50% Advance", "50% Balance Net 7")),
)


def setup_procurement(company: str | None = None) -> None:
	"""Configure warehouses, buying/stock allowances, payment terms, suppliers, item kinds, prices, and UOMs."""
	ensure_supplier_groups()
	ensure_payment_terms()
	ensure_warehouses(company)
	ensure_procurement_settings()
	ensure_item_classifications()
	ensure_profile_uoms_and_lead_times()
	ensure_hardware_uom_alignment()
	ensure_default_suppliers(company)
	ensure_company_address(company)
	ensure_glass_and_profile_prices()


def ensure_supplier_groups() -> None:
	parent = "All Supplier Groups"
	if not frappe.db.exists("Supplier Group", parent):
		return
	for name in SUPPLIER_GROUPS:
		if not frappe.db.exists("Supplier Group", name):
			frappe.get_doc(
				{
					"doctype": "Supplier Group",
					"supplier_group_name": name,
					"parent_supplier_group": parent,
				}
			).insert(ignore_permissions=True)


def ensure_payment_terms() -> None:
	for term_name, portion, based_on, credit_days in PAYMENT_TERMS:
		if not frappe.db.exists("Payment Term", term_name):
			frappe.get_doc(
				{
					"doctype": "Payment Term",
					"payment_term_name": term_name,
					"invoice_portion": portion,
					"due_date_based_on": based_on,
					"credit_days": credit_days,
				}
			).insert(ignore_permissions=True)

	for template_name, term_names in PAYMENT_TEMPLATES:
		if frappe.db.exists("Payment Terms Template", template_name):
			continue
		rows = []
		for term_name in term_names:
			term = frappe.get_doc("Payment Term", term_name)
			rows.append(
				{
					"payment_term": term.name,
					"invoice_portion": term.invoice_portion,
					"due_date_based_on": term.due_date_based_on,
					"credit_days": term.credit_days,
					"credit_months": term.credit_months,
				}
			)
		frappe.get_doc(
			{
				"doctype": "Payment Terms Template",
				"template_name": template_name,
				"terms": rows,
			}
		).insert(ignore_permissions=True)


def ensure_warehouses(company: str | None = None) -> list[str]:
	"""Arrange warehouse hierarchy: All Warehouses -> Main Warehouse (group: Finished Goods, Goods In Transit, Stores, WIP) + Hilux Warehouse."""
	company = _resolve_company(company)
	if not company:
		return []

	all_wh = _ensure_all_warehouses(company)
	main_group = _ensure_group_warehouse(MAIN_GROUP_WAREHOUSE, all_wh, company)
	created_or_existing = [main_group]

	for wh_name in MAIN_CHILD_WAREHOUSES:
		created_or_existing.append(_ensure_leaf_warehouse(wh_name, main_group, company))

	for wh_name in LEAF_WAREHOUSES:
		created_or_existing.append(_ensure_leaf_warehouse(wh_name, all_wh, company))

	rebuild_tree("Warehouse")
	_set_default_warehouses(company)
	return created_or_existing


def _ensure_group_warehouse(wh_name: str, parent_warehouse: str, company: str) -> str:
	existing = frappe.db.get_value(
		"Warehouse", {"warehouse_name": wh_name, "company": company}, "name"
	)
	if existing:
		doc = frappe.get_doc("Warehouse", existing)
		changed = False
		if not doc.is_group:
			has_stock = frappe.db.exists("Stock Ledger Entry", {"warehouse": existing}) or frappe.db.exists(
				"Bin", {"warehouse": existing}
			)
			if not has_stock:
				doc.is_group = 1
				changed = True
		if doc.parent_warehouse != parent_warehouse:
			doc.parent_warehouse = parent_warehouse
			changed = True
		if changed:
			doc.save(ignore_permissions=True)
		return doc.name

	return frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": wh_name,
			"parent_warehouse": parent_warehouse,
			"company": company,
			"is_group": 1,
		}
	).insert(ignore_permissions=True).name


def _ensure_leaf_warehouse(wh_name: str, parent_warehouse: str, company: str) -> str:
	existing = frappe.db.get_value(
		"Warehouse", {"warehouse_name": wh_name, "company": company}, "name"
	)
	if existing:
		doc = frappe.get_doc("Warehouse", existing)
		if doc.parent_warehouse != parent_warehouse:
			doc.parent_warehouse = parent_warehouse
			doc.save(ignore_permissions=True)
		return doc.name

	return frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": wh_name,
			"parent_warehouse": parent_warehouse,
			"company": company,
			"is_group": 0,
		}
	).insert(ignore_permissions=True).name


def ensure_procurement_settings() -> None:
	if not flt(frappe.db.get_single_value("Stock Settings", "over_delivery_receipt_allowance")):
		frappe.db.set_single_value("Stock Settings", "over_delivery_receipt_allowance", 10.0)
	if not flt(frappe.db.get_single_value("Accounts Settings", "over_billing_allowance")):
		frappe.db.set_single_value("Accounts Settings", "over_billing_allowance", 10.0)
	if not frappe.db.get_single_value("Buying Settings", "po_required"):
		frappe.db.set_single_value("Buying Settings", "po_required", "No")
	if not frappe.db.get_single_value("Buying Settings", "pr_required"):
		frappe.db.set_single_value("Buying Settings", "pr_required", "No")


def ensure_item_classifications() -> None:
	"""Tag linked profile and glass ERP Items with fen_item_kind and Fenestration Item Group."""
	fen_group = "Fenestration" if frappe.db.exists("Item Group", "Fenestration") else None
	has_kind = frappe.get_meta("Item").has_field("fen_item_kind")

	pairs = [
		(code, "Profile")
		for code in frappe.get_all("Fenestration Profile", filters={"item": ("is", "set")}, pluck="item")
	] + [
		(code, "Glass")
		for code in frappe.get_all("Fenestration Glass", filters={"item": ("is", "set")}, pluck="item")
	]
	seen: set[str] = set()
	for item_code, kind in pairs:
		if not item_code or item_code in seen or not frappe.db.exists("Item", item_code):
			continue
		seen.add(item_code)
		updates = {}
		if has_kind and frappe.db.get_value("Item", item_code, "fen_item_kind") != kind:
			updates["fen_item_kind"] = kind
		if fen_group and frappe.db.get_value("Item", item_code, "item_group") in (None, "", "All Item Groups"):
			updates["item_group"] = fen_group
		if updates:
			frappe.db.set_value("Item", item_code, updates, update_modified=False)


def ensure_profile_uoms_and_lead_times() -> None:
	"""Add Meter -> Kg conversion and default 14-day extrusion lead time on Fenestration Profile Items."""
	if not frappe.db.exists("UOM", "Meter"):
		return
	profiles = frappe.get_all(
		"Fenestration Profile",
		filters={"item": ("is", "set")},
		fields=["item", "kg_per_m"],
	)
	seen_items: set[str] = set()
	for profile in profiles:
		item_code = profile.item
		if not item_code or item_code in seen_items or flt(profile.kg_per_m) <= 0:
			continue
		seen_items.add(item_code)
		if not frappe.db.exists("Item", item_code):
			continue
		item = frappe.get_doc("Item", item_code)
		changed = False
		if item.stock_uom == "Kg" and not any(row.uom == "Meter" for row in item.uoms):
			item.append("uoms", {"uom": "Meter", "conversion_factor": round(flt(profile.kg_per_m), 6)})
			changed = True
		if not flt(item.lead_time_days):
			item.lead_time_days = 14
			changed = True
		if changed:
			item.save(ignore_permissions=True)


def ensure_hardware_uom_alignment() -> None:
	"""Ensure snapshot UOM aliases (Pairs, m) and CS400 H914 sealant UOM match ERP Item stock UOMs."""
	for uom_name, whole in (("Pairs", 1), ("m", 0), ("Can", 0)):
		if not frappe.db.exists("UOM", uom_name):
			frappe.get_doc(
				{"doctype": "UOM", "uom_name": uom_name, "must_be_whole_number": whole}
			).insert(ignore_permissions=True)

	for item_code, alias_uom in (("H416", "Pairs"), ("H915", "m")):
		if not frappe.db.exists("Item", item_code):
			continue
		item = frappe.get_doc("Item", item_code)
		if item.stock_uom != alias_uom and not any(r.uom == alias_uom for r in item.uoms):
			item.append("uoms", {"uom": alias_uom, "conversion_factor": 1.0})
			item.save(ignore_permissions=True)

	if frappe.db.exists("Item", "H914"):
		h914_uom = frappe.db.get_value("Item", "H914", "stock_uom")
		if h914_uom and h914_uom != "Nos":
			rules = frappe.get_all(
				"Series Hardware Rule",
				filters={"item": "H914", "uom": "Nos"},
				fields=["name", "parent"],
			)
			parents = set()
			for r in rules:
				frappe.db.set_value("Series Hardware Rule", r.name, "uom", h914_uom, update_modified=False)
				if r.parent:
					parents.add(r.parent)
			for version_name in parents:
				raw = frappe.db.get_value("Series Version", version_name, "snapshot_json")
				if not raw:
					continue
				data = json.loads(raw) if isinstance(raw, str) else raw
				updated = False
				for hr in data.get("hardware_rules", []):
					if hr.get("item") == "H914" and hr.get("uom") == "Nos":
						hr["uom"] = h914_uom
						updated = True
				if updated:
					frappe.db.set_value(
						"Series Version", version_name, "snapshot_json", json.dumps(data), update_modified=False
					)
					frappe.cache.hdel("fen_snapshot", version_name)


def ensure_default_suppliers(company: str | None = None) -> None:
	"""Create default Aluminium, Glass, and Hardware suppliers and set Item Default.default_supplier when unset."""
	company = _resolve_company(company)
	for sup_name, group, payment_terms in DEFAULT_SUPPLIERS:
		if not frappe.db.exists("Supplier", sup_name):
			target_group = group if frappe.db.exists("Supplier Group", group) else "All Supplier Groups"
			doc_dict = {
				"doctype": "Supplier",
				"supplier_name": sup_name,
				"supplier_group": target_group,
			}
			if frappe.db.exists("Payment Terms Template", payment_terms):
				doc_dict["payment_terms"] = payment_terms
			frappe.get_doc(doc_dict).insert(ignore_permissions=True)

	if not company:
		return

	kind_to_supplier = {
		"Profile": "Hilux Aluminium Extrusions",
		"Glass": "Hilux Toughened Glass",
		"Hardware": "Hilux Hardware & Gaskets",
		"Gasket": "Hilux Hardware & Gaskets",
		"Consumable": "Hilux Hardware & Gaskets",
	}
	items = frappe.get_all(
		"Item",
		filters={"fen_item_kind": ("in", list(kind_to_supplier.keys()))},
		fields=["name", "fen_item_kind"],
	)
	for row in items:
		sup = kind_to_supplier.get(row.fen_item_kind)
		if not sup or not frappe.db.exists("Supplier", sup):
			continue
		default_row = frappe.db.get_value(
			"Item Default",
			{"parent": row.name, "parenttype": "Item", "company": company},
			["name", "default_supplier"],
			as_dict=True,
		)
		if default_row:
			if not default_row.default_supplier:
				frappe.db.set_value("Item Default", default_row.name, "default_supplier", sup, update_modified=False)
		else:
			item_doc = frappe.get_doc("Item", row.name)
			item_doc.append("item_defaults", {"company": company, "default_supplier": sup})
			item_doc.save(ignore_permissions=True)


def ensure_company_address(company: str | None = None) -> None:
	"""Ensure the active company has a primary company address so Quotation creation works out of the box."""
	company = _resolve_company(company)
	if not company or company_address(company):
		return
	addr = {
		"doctype": "Address",
		"address_title": f"{company} - Head Office",
		"address_type": "Billing",
		"address_line1": "Industrial Estate",
		"city": "Chennai",
		"state": "Tamil Nadu",
		"pincode": "600001",
		"country": "India",
		"is_primary_address": 1,
		"is_your_company_address": 1,
		"links": [{"link_doctype": "Company", "link_name": company}],
	}
	if frappe.get_meta("Address").has_field("gst_state"):
		addr["gst_state"] = "Tamil Nadu"
	if frappe.get_meta("Address").has_field("gstin"):
		addr["gstin"] = "33AAHCH3108G1Z0"
	frappe.get_doc(addr).insert(ignore_permissions=True)


def ensure_glass_and_profile_prices() -> None:
	"""Ensure Fenestration Glass, Profile, and Hardware/Gasket items have Standard Buying/Selling prices."""
	cost_list = (
		frappe.db.get_single_value("Fenestration Settings", "cost_price_list")
		if frappe.db.exists("DocType", "Fenestration Settings")
		else None
	) or "Standard Buying"

	price_lists = list(dict.fromkeys(((cost_list, 1), ("Standard Buying", 1), ("Standard Selling", 0))))
	profile_items = list(
		dict.fromkeys(frappe.get_all("Fenestration Profile", filters={"item": ("is", "set")}, pluck="item"))
	)
	hw_items = frappe.get_all(
		"Item",
		filters={"fen_item_kind": ("in", ("Hardware", "Gasket")), "disabled": 0},
		pluck="name",
	)

	for plist, is_buying in price_lists:
		if not frappe.db.exists("Price List", plist):
			continue
		default_glass_rate = 850.0 if is_buying else 1050.0
		for glass in frappe.get_all("Fenestration Glass", filters={"item": ("is", "set")}, fields=["item", "thickness_mm"]):
			rate = default_glass_rate if flt(glass.thickness_mm) <= 6 else round(default_glass_rate * 1.4, 2)
			_ensure_item_price(glass.item, plist, rate)

		profile_rate = DEFAULT_PROFILE_BUYING_RATE if is_buying else DEFAULT_PROFILE_SELLING_RATE
		for item_code in profile_items:
			_ensure_item_price(item_code, plist, profile_rate)

		for item_code in hw_items:
			buy_rate, sell_rate = DEFAULT_HARDWARE_RATES.get(item_code, (100.0, 140.0))
			_ensure_item_price(item_code, plist, buy_rate if is_buying else sell_rate)

	# Re-price any existing Window Design that previously had missing-price warnings.
	for d_name in frappe.get_all("Window Design", filters={"pricing_warning_count": (">", 0)}, pluck="name"):
		try:
			frappe.get_doc("Window Design", d_name).reprice()
		except Exception:
			pass


def _ensure_item_price(item_code: str, price_list: str, rate: float) -> None:
	if not item_code or not frappe.db.exists("Item", item_code):
		return
	if frappe.db.exists("Item Price", {"item_code": item_code, "price_list": price_list}):
		return
	uom = frappe.db.get_value("Item", item_code, "stock_uom")
	frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item_code,
			"price_list": price_list,
			"uom": uom,
			"price_list_rate": rate,
		}
	).insert(ignore_permissions=True)


def _resolve_company(company: str | None) -> str | None:
	if company and frappe.db.exists("Company", company):
		return company
	found = default_company()
	if found and frappe.db.exists("Company", found):
		return found
	return frappe.db.get_value("Company", {}, "name")


def _ensure_all_warehouses(company: str) -> str:
	existing = frappe.db.get_value(
		"Warehouse",
		{"warehouse_name": "All Warehouses", "company": company, "is_group": 1},
		"name",
	)
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": "All Warehouses",
			"company": company,
			"is_group": 1,
		}
	).insert(ignore_permissions=True)
	return doc.name


def _set_default_warehouses(company: str) -> None:
	stores_wh = frappe.db.get_value(
		"Warehouse", {"warehouse_name": "Stores", "company": company, "is_group": 0}, "name"
	)
	wip_wh = frappe.db.get_value(
		"Warehouse", {"warehouse_name": "Work In Progress", "company": company, "is_group": 0}, "name"
	)
	fg_wh = frappe.db.get_value(
		"Warehouse", {"warehouse_name": "Finished Goods", "company": company, "is_group": 0}, "name"
	)
	comp = frappe.get_doc("Company", company)
	changed = False
	for fieldname, value in (
		("default_warehouse", stores_wh),
		("default_wip_warehouse", wip_wh),
		("default_fg_warehouse", fg_wh),
	):
		if value and not comp.get(fieldname):
			comp.set(fieldname, value)
			changed = True
	if changed:
		comp.save(ignore_permissions=True)
