"""Which addresses and GST template a quotation uses."""

import frappe

# india_compliance treats supplies to these categories as inter-state (IGST) wherever the party is.
INTER_STATE_CATEGORIES = ("SEZ", "Overseas")


def customer_addresses(customer: str) -> tuple[str | None, str | None]:
	"""(billing, shipping) addresses, picked the way ERPNext fills them on a new transaction."""
	from erpnext.accounts.party import get_party_shipping_address
	from frappe.contacts.doctype.address.address import get_default_address

	billing = _first(_linked("Customer", customer, address_type="Billing", is_primary_address=1))
	billing = billing or get_default_address("Customer", customer)
	return billing, get_party_shipping_address("Customer", customer) or None


def tax_address(billing: str | None, shipping: str | None) -> str | None:
	"""The address that decides the place of supply, honouring Accounts Settings."""
	basis = frappe.get_cached_value(
		"Accounts Settings", "Accounts Settings", "determine_address_tax_category_from"
	)
	return shipping if basis == "Shipping Address" and shipping else billing


def gst_template(company: str, customer: str, address: str | None) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	state = address and frappe.db.get_value("Address", address, "gst_state")
	company_state = _company_state(company)
	out_of_state = is_export(customer, address) or (state and company_state and state != company_state)
	return f"Output GST {'Out' if out_of_state else 'In'}-state - {abbr}"


def is_export(customer: str, address: str | None) -> bool:
	"""SEZ or Overseas party: the address's GST category, else the customer's."""
	category = address and frappe.db.get_value("Address", address, "gst_category")
	category = category or frappe.db.get_value("Customer", customer, "gst_category")
	return category in INTER_STATE_CATEGORIES


def company_address(company: str) -> str | None:
	"""The company's own address carrying a GSTIN; india_compliance needs one on every quotation."""
	return _first(_linked("Company", company, is_your_company_address=1, gstin=("is", "set")))


def _first(filters: list) -> str | None:
	names = frappe.get_all("Address", filters, pluck="name", order_by="is_primary_address desc", limit=1)
	return names[0] if names else None


def _linked(link_doctype: str, link_name: str, **filters) -> list:
	return [
		["Dynamic Link", "link_doctype", "=", link_doctype],
		["Dynamic Link", "link_name", "=", link_name],
		["disabled", "=", 0],
		*(
			["Address", field, *(value if isinstance(value, tuple) else ("=", value))]
			for field, value in filters.items()
		),
	]


def _company_state(company: str) -> str | None:
	address = company_address(company)
	state = address and frappe.db.get_value("Address", address, "gst_state")
	if state:
		return state
	gstin = (
		frappe.get_cached_value("Company", company, "gstin")
		if frappe.get_meta("Company").has_field("gstin")
		else None
	)
	if not gstin:
		return None
	from india_compliance.gst_india.constants import STATE_NUMBERS

	return next((name for name, number in STATE_NUMBERS.items() if number == gstin[:2]), None)
