"""CRM Deal quotation preview, direct ERPNext Quotation creation, and partner type sync."""

from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_url_to_form, nowdate

VALID_PARTNER_TYPES = ("Dealer", "Fabrication Partner", "Own Client")
PARTNER_TYPE_CUSTOMER_GROUPS = {
	"Dealer": "Dealers",
	"Fabrication Partner": "Fabrication Partners",
	"Own Client": "Own Clients",
}
QUOTATION_LIST_FIELDS = [
	"name",
	"status",
	"grand_total",
	"rounded_total",
	"currency",
	"transaction_date",
	"valid_till",
	"crm_deal",
	"party_name",
	"customer_name",
	"contact_display",
	"contact_email",
	"contact_mobile",
	"territory",
]


def _default_company(settings=None) -> str | None:
	return (
		(settings.erpnext_company if settings else None)
		or frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
	)


def _existing_default_quotation_item() -> str:
	"""Return an existing fallback ERPNext Item without mutating DB (safe for read-only previews)."""
	for candidate in ("FEN-WINDOW", "CRM-DEAL-QUOTATION"):
		if frappe.db.exists("Item", candidate):
			return candidate
	return ""


def _get_or_create_deal_quotation_item() -> str:
	"""Return a non-stock Item for deal-level quotations when Deal products aren't linked to ERPNext Items."""
	for candidate in ("CRM-DEAL-QUOTATION", "FEN-WINDOW"):
		if frappe.db.exists("Item", candidate):
			return candidate

	item_group = (
		"Services"
		if frappe.db.exists("Item Group", "Services")
		else frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
	)
	stock_uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_value("UOM", {}, "name") or "Nos"
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": "CRM-DEAL-QUOTATION",
			"item_name": "Fenestration Deal Quotation Item",
			"item_group": item_group,
			"stock_uom": stock_uom,
			"is_stock_item": 0,
			"is_sales_item": 1,
		}
	)
	item.insert(ignore_permissions=True)
	return item.name


def _deal_display_name(deal) -> str:
	return deal.get("organization") or deal.get("lead_name") or deal.name


def resolve_partner_type(deal, customer: str | None = None, override: str | None = None) -> str:
	if override in VALID_PARTNER_TYPES:
		return override
	if deal and deal.get("fen_partner_type") in VALID_PARTNER_TYPES:
		return deal.get("fen_partner_type")
	if customer and frappe.db.has_column("Customer", "fen_partner_type"):
		val = frappe.db.get_value("Customer", customer, "fen_partner_type")
		if val in VALID_PARTNER_TYPES:
			return val
	return "Dealer"


def sync_customer_partner_type(customer: str | None, partner_type: str) -> None:
	if not customer or not frappe.db.exists("Customer", customer):
		return
	updates = {}
	if frappe.db.has_column("Customer", "fen_partner_type"):
		updates["fen_partner_type"] = partner_type
	target_group = PARTNER_TYPE_CUSTOMER_GROUPS.get(partner_type, "Dealers")
	if frappe.db.exists("Customer Group", target_group):
		updates["customer_group"] = target_group
	if updates:
		frappe.db.set_value("Customer", customer, updates, update_modified=False)


def _is_confirmed_deal(deal) -> bool:
	if not deal.get("status") or not frappe.db.exists("DocType", "CRM Deal Status"):
		return False
	status_type = frappe.get_cached_value("CRM Deal Status", deal.status, "type")
	return status_type == "Won"


def sync_erpnext_crm_settings(doc, method=None) -> None:
	"""Hook on ERPNext CRM Settings on_update: enable CRM sync on same-site and keep form scripts synced."""
	if not doc.get("enabled"):
		return
	if not doc.get("is_erpnext_in_different_site") and frappe.db.exists("DocType", "CRM Settings"):
		if not frappe.db.get_single_value("CRM Settings", "enable_frappe_crm_data_synchronization"):
			frappe.db.set_single_value("CRM Settings", "enable_frappe_crm_data_synchronization", 1)

	from onebook_fenestration.setup.crm import ensure_crm_form_scripts

	ensure_crm_form_scripts()


def _desk_form_path(doctype: str, name: str) -> str:
	"""Return a relative Desk path (e.g. /desk/quotation/SAL-QTN-...) that works on any host/origin."""
	return urlparse(get_url_to_form(doctype, name)).path


def sync_customer_partner_type_on_insert(doc, method=None) -> None:
	"""Hook on Customer after_insert: propagate fen_partner_type and customer_group from linked CRM Deal."""
	crm_deal = doc.get("crm_deal")
	if (
		not crm_deal
		or not frappe.db.exists("DocType", "CRM Deal")
		or not frappe.db.exists("CRM Deal", crm_deal)
	):
		return
	deal = frappe.db.get_value("CRM Deal", crm_deal, ["name", "fen_partner_type"], as_dict=True)
	if not deal:
		return
	partner_type = resolve_partner_type(deal, doc.name)
	sync_customer_partner_type(doc.name, partner_type)


def sync_customer_partner_group(doc, method=None) -> None:
	"""Hook on Customer validate: keep customer_group aligned when fen_partner_type is set/changed."""
	partner_type = doc.get("fen_partner_type")
	if partner_type not in VALID_PARTNER_TYPES:
		return
	if not doc.is_new() and not doc.has_value_changed("fen_partner_type"):
		return
	target_group = PARTNER_TYPE_CUSTOMER_GROUPS.get(partner_type)
	if target_group and frappe.db.exists("Customer Group", target_group):
		doc.customer_group = target_group


@frappe.whitelist()
def get_deal_quotation_preview(crm_deal: str) -> dict:
	"""Return structured Deal, Party (Dealer/Fabrication Partner/Own Client), and default Item details."""
	from crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings import (
		can_create_quotations,
		get_local_customer,
		get_organization_address,
		get_primary_contact,
	)

	if not crm_deal or not frappe.db.exists("CRM Deal", crm_deal):
		frappe.throw(_("CRM Deal {0} not found").format(crm_deal))
	if not frappe.has_permission("CRM Deal", "read", crm_deal):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	deal = frappe.get_doc("CRM Deal", crm_deal)
	customer = get_local_customer(crm_deal)
	primary_contact_name = get_primary_contact(crm_deal)
	primary_contact = next((c for c in deal.contacts if c.is_primary), None) or (
		deal.contacts[0] if deal.contacts else None
	)
	address = get_organization_address(deal.organization)
	address_parts = [
		address.get(k)
		for k in ("address_line1", "address_line2", "city", "state", "pincode", "country")
		if address and address.get(k)
	]

	default_item_code = _existing_default_quotation_item()
	items = []
	for row in deal.products or []:
		item_code = (
			frappe.db.get_value("CRM Product", row.product_code, "erpnext_item_code")
			if row.product_code
			else None
		)
		qty = flt(row.qty) or 1
		rate = flt(row.rate)
		amount = flt(row.amount) or round(qty * rate, 2)
		items.append(
			{
				"item_code": item_code or default_item_code,
				"item_name": row.product_name or row.product_code or _deal_display_name(deal),
				"description": row.product_name or _deal_display_name(deal),
				"qty": qty,
				"rate": rate,
				"amount": amount,
			}
		)

	fallback_value = flt(deal.net_total) or flt(deal.deal_value) or flt(deal.expected_deal_value) or 0.0
	if not items:
		items.append(
			{
				"item_code": default_item_code,
				"item_name": f"Fenestration Package — {_deal_display_name(deal)}",
				"description": f"Quotation for confirmed deal {deal.name} ({_deal_display_name(deal)})",
				"qty": 1,
				"rate": fallback_value,
				"amount": fallback_value,
			}
		)

	total_value = round(
		sum(flt(i.get("amount") or flt(i.get("qty", 1)) * flt(i.get("rate", 0))) for i in items), 2
	)
	partner_type = resolve_partner_type(deal, customer)

	return {
		"crm_deal": deal.name,
		"deal_name": _deal_display_name(deal),
		"status": deal.status,
		"is_confirmed": _is_confirmed_deal(deal),
		"can_create_quotations": bool(can_create_quotations()),
		"currency": deal.currency
		or frappe.db.get_single_value("Global Defaults", "default_currency")
		or "INR",
		"transaction_date": nowdate(),
		"valid_till": add_days(nowdate(), 30),
		"quotation_value": total_value,
		"dealer": {
			"customer": customer or "",
			"customer_name": (
				frappe.db.get_value("Customer", customer, "customer_name")
				if customer
				else _deal_display_name(deal)
			),
			"partner_type": partner_type,
			"contact_person": primary_contact_name or (primary_contact.contact if primary_contact else ""),
			"contact_display": (primary_contact.full_name if primary_contact else deal.lead_name) or "",
			"contact_email": (primary_contact.email if primary_contact else deal.email) or "",
			"contact_mobile": (primary_contact.mobile_no if primary_contact else deal.mobile_no) or "",
			"territory": deal.territory or "",
			"address_display": ", ".join(address_parts),
		},
		"items": items,
	}


@frappe.whitelist()
def get_item_quotation_defaults(item_code: str, currency: str | None = None) -> dict:
	"""Return item_name, description, uom, and default selling rate for a selected ERPNext Item."""
	if not item_code or not frappe.db.exists("Item", item_code):
		return {}
	if not frappe.has_permission("Item", "read", item_code):
		frappe.throw(_("Not permitted to read Item"), frappe.PermissionError)

	item = frappe.db.get_value(
		"Item",
		item_code,
		["item_code", "item_name", "description", "stock_uom", "standard_rate"],
		as_dict=True,
	)
	if not item:
		return {}

	rate = flt(item.standard_rate)
	if frappe.db.exists("DocType", "Item Price"):
		price_filters = {"item_code": item_code, "selling": 1}
		if currency:
			price_filters["currency"] = currency
		price = frappe.db.get_value(
			"Item Price",
			price_filters,
			"price_list_rate",
			order_by="modified desc",
		)
		if price is None and currency:
			price = frappe.db.get_value(
				"Item Price",
				{"item_code": item_code, "selling": 1},
				"price_list_rate",
				order_by="modified desc",
			)
		if price is not None:
			rate = flt(price)

	return {
		"item_code": item.item_code,
		"item_name": item.item_name or item.item_code,
		"description": item.description or item.item_name or item.item_code,
		"uom": item.stock_uom or "Nos",
		"rate": rate,
	}


@frappe.whitelist(methods=["POST"])
def create_quotation_from_deal(
	crm_deal: str,
	valid_till: str | None = None,
	partner_type: str | None = None,
	items: str | list | None = None,
	quotation_value: float | str | None = None,
	tc_name: str | None = None,
	terms: str | None = None,
) -> dict:
	"""Create an ERPNext Quotation directly from a confirmed (Won) CRM Deal."""
	from crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings import (
		_get_enabled_settings,
		check_customer_for_deal,
		get_organization_address,
		get_primary_contact,
		notify_deal_quotation_change,
	)

	settings = _get_enabled_settings()
	if settings.is_erpnext_in_different_site:
		frappe.throw(_("Direct quotation creation is supported only for same-site ERPNext."))

	if not crm_deal or not frappe.db.exists("CRM Deal", crm_deal):
		frappe.throw(_("CRM Deal {0} not found").format(crm_deal))
	if not frappe.has_permission("CRM Deal", "read", crm_deal):
		frappe.throw(_("Not permitted to read CRM Deal"), frappe.PermissionError)
	if not frappe.has_permission("Quotation", "create"):
		frappe.throw(_("Not permitted to create Quotation"), frappe.PermissionError)

	deal = frappe.get_doc("CRM Deal", crm_deal)
	if not _is_confirmed_deal(deal):
		frappe.throw(
			_("Only confirmed (Won) deals can create a Quotation. Current status: {0}").format(deal.status),
			frappe.ValidationError,
		)

	customer = check_customer_for_deal(crm_deal)
	if not customer:
		frappe.throw(_("Could not resolve or create ERPNext Customer for deal {0}").format(crm_deal))

	resolved_partner_type = resolve_partner_type(deal, customer, override=partner_type)
	sync_customer_partner_type(customer, resolved_partner_type)
	if (
		frappe.db.has_column("CRM Deal", "fen_partner_type")
		and deal.get("fen_partner_type") != resolved_partner_type
	):
		frappe.db.set_value(
			"CRM Deal", deal.name, "fen_partner_type", resolved_partner_type, update_modified=False
		)

	parsed_items = frappe.parse_json(items) if isinstance(items, str) else (items or [])
	if not parsed_items:
		preview = get_deal_quotation_preview(crm_deal)
		parsed_items = preview["items"]

	fallback_item_code = None
	quotation_items = []
	for row in parsed_items:
		item_code = (row.get("item_code") or "").strip()
		if not item_code or not frappe.db.exists("Item", item_code):
			if not fallback_item_code:
				fallback_item_code = _get_or_create_deal_quotation_item()
			item_code = fallback_item_code
		qty = flt(row.get("qty")) or 1.0
		rate = flt(row.get("rate"))
		if len(parsed_items) == 1 and quotation_value is not None and flt(quotation_value) > 0 and rate == 0:
			rate = round(flt(quotation_value) / qty, 2)
		quotation_items.append(
			{
				"item_code": item_code,
				"item_name": row.get("item_name") or _deal_display_name(deal),
				"description": row.get("description") or row.get("item_name") or _deal_display_name(deal),
				"qty": qty,
				"price_list_rate": rate,
				"rate": rate,
			}
		)

	if not quotation_items:
		fallback_item_code = _get_or_create_deal_quotation_item()
		val = flt(quotation_value) or flt(deal.net_total) or flt(deal.deal_value) or 0.0
		quotation_items.append(
			{
				"item_code": fallback_item_code,
				"item_name": f"Fenestration Package — {_deal_display_name(deal)}",
				"description": f"Quotation for confirmed deal {deal.name} ({_deal_display_name(deal)})",
				"qty": 1.0,
				"price_list_rate": val,
				"rate": val,
			}
		)

	contact_person = get_primary_contact(crm_deal)
	address = get_organization_address(deal.organization)
	address_name = address.get("name") if address else None

	quotation = frappe.new_doc("Quotation")
	quotation.quotation_to = "Customer"
	quotation.party_name = customer
	quotation.company = _default_company(settings)
	quotation.transaction_date = nowdate()
	quotation.valid_till = valid_till or add_days(nowdate(), 30)
	quotation.crm_deal = deal.name
	if deal.currency:
		quotation.currency = deal.currency
	if contact_person and frappe.db.exists("Contact", contact_person):
		quotation.contact_person = contact_person
	if address_name and frappe.db.exists("Address", address_name):
		quotation.customer_address = address_name
	if tc_name and frappe.db.exists("Terms and Conditions", tc_name):
		quotation.tc_name = tc_name
	if terms:
		quotation.terms = terms
	if frappe.db.has_column("Quotation", "fen_deal_name"):
		quotation.fen_deal_name = _deal_display_name(deal)
	if frappe.db.has_column("Quotation", "fen_partner_type"):
		quotation.fen_partner_type = resolved_partner_type

	for row in quotation_items:
		quotation.append("items", row)

	quotation.set_missing_values()
	quotation.calculate_taxes_and_totals()
	quotation.insert()
	notify_deal_quotation_change(quotation)

	return {
		"name": quotation.name,
		"crm_deal": deal.name,
		"deal_name": _deal_display_name(deal),
		"customer": customer,
		"customer_name": quotation.customer_name or customer,
		"partner_type": resolved_partner_type,
		"contact_display": quotation.contact_display or "",
		"contact_email": quotation.contact_email or "",
		"contact_mobile": quotation.contact_mobile or "",
		"status": quotation.status,
		"transaction_date": str(quotation.transaction_date),
		"valid_till": str(quotation.valid_till) if quotation.valid_till else "",
		"grand_total": flt(quotation.grand_total),
		"rounded_total": flt(quotation.rounded_total or quotation.grand_total),
		"currency": quotation.currency,
		"url": _desk_form_path("Quotation", quotation.name),
	}


@frappe.whitelist()
def get_deal_quotations(crm_deal: str) -> list[dict]:
	"""Override crm's get_deal_quotations to enrich rows with deal_name, contact details, and partner_type."""
	from crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings import (
		_get_enabled_settings,
	)
	from crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings import (
		get_deal_quotations as crm_get_deal_quotations,
	)

	if not crm_deal or not frappe.has_permission("CRM Deal", "read", crm_deal):
		return []

	try:
		settings = _get_enabled_settings()
	except Exception:
		return []

	if settings.is_erpnext_in_different_site:
		return crm_get_deal_quotations(crm_deal)

	if not frappe.has_permission("Quotation", ptype="read"):
		return []

	deal_title = ""
	if frappe.db.exists("CRM Deal", crm_deal):
		d = frappe.db.get_value("CRM Deal", crm_deal, ["organization", "lead_name"], as_dict=True)
		deal_title = (d.organization or d.lead_name or crm_deal) if d else crm_deal

	fields = list(QUOTATION_LIST_FIELDS)
	if frappe.db.has_column("Quotation", "fen_deal_name"):
		fields.append("fen_deal_name")
	if frappe.db.has_column("Quotation", "fen_partner_type"):
		fields.append("fen_partner_type")

	rows = frappe.get_list(
		"Quotation",
		filters={"crm_deal": crm_deal},
		fields=fields,
		order_by="modified desc",
		limit_page_length=0,
	)
	has_customer_partner = frappe.db.has_column("Customer", "fen_partner_type")
	for row in rows:
		row["url"] = _desk_form_path("Quotation", row["name"])
		row["deal_name"] = row.get("fen_deal_name") or deal_title or crm_deal
		partner_type = row.get("fen_partner_type")
		if not partner_type and has_customer_partner and row.get("party_name"):
			partner_type = frappe.db.get_value("Customer", row["party_name"], "fen_partner_type")
		row["partner_type"] = partner_type or "Dealer"
	return rows
