import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate

from onebook_fenestration.engine.layout import layout
from onebook_fenestration.fenestration.doctype.fenestration_project.fenestration_project import (
	default_company,
)
from onebook_fenestration.series_studio.snapshot import get_snapshot

WINDOW_ITEM = "FEN-WINDOW"
TRANSPORT_ITEM = "FEN-TRANSPORT"
DEFAULT_TERMS = "Hilux Standard Terms"
DEFAULT_LETTER_HEAD = "Company Letterhead"
QUOTE_VALIDITY_DAYS = 10
DESIGN_FIELDS = (
	"name",
	"design_ref",
	"design_name",
	"qty",
	"unit_price",
	"area_sqft",
	"finish",
	"series_version",
	"design_json",
	"error_count",
	"pricing_warning_count",
)


class QuoteNotReady(frappe.ValidationError):
	"""The project fails the quotable gate; the message says what to fix."""


def reprice_project(project: str) -> dict:
	"""Re-price every design of the project from current Item Prices; one bad design does not stop the rest."""
	frappe.has_permission("Fenestration Project", "write", project, throw=True)
	names = frappe.get_all("Window Design", {"project": project}, pluck="name", order_by="design_ref")
	repriced, failed = 0, []
	for name in names:
		try:
			frappe.get_doc("Window Design", name).reprice()
			repriced += 1
		except frappe.ValidationError as exc:
			failed.append({"design": name, "message": str(exc)})
	return {"repriced": repriced, "failed": failed}


def make_quotation(project: str) -> str:
	"""Build (or rebuild the draft of) the project's ERPNext Quotation; returns its name."""
	frappe.has_permission("Fenestration Project", "write", project, throw=True)
	project_doc = frappe.get_doc("Fenestration Project", project)
	project_doc.company = project_doc.company or default_company()
	quotation = _target_quotation(project_doc)
	if quotation.is_new():
		frappe.has_permission("Quotation", "create", throw=True)
	else:
		frappe.has_permission("Quotation", "write", doc=quotation, throw=True)
	designs = frappe.get_all("Window Design", {"project": project}, DESIGN_FIELDS, order_by="design_ref")
	check_quotable(project_doc, designs)

	frappe.db.savepoint("fen_make_quotation")
	try:
		QuotationBuilder(project_doc, quotation).build(designs)
		project_doc.db_set("quotation", quotation.name)
	except Exception:
		frappe.db.rollback(save_point="fen_make_quotation")
		raise
	return quotation.name


def quote_status(project: str) -> dict:
	frappe.has_permission("Fenestration Project", "read", project, throw=True)
	name = frappe.db.get_value("Fenestration Project", project, "quotation")
	fields = ("docstatus", "status", "grand_total", "net_total", "total_taxes_and_charges")
	values = name and frappe.db.get_value("Quotation", name, fields, as_dict=True)
	if not values:
		return {"quotation": None}
	return {"quotation": name, **values}


def check_quotable(project, designs: list[dict]) -> None:
	if not project.customer:
		raise QuoteNotReady(_("Set a customer on the project"))
	if not designs:
		raise QuoteNotReady(_("Add at least one window design"))
	problems = []
	for design in designs:
		reasons = [_("errors")] if cint(design.error_count) else []
		if cint(design.pricing_warning_count):
			reasons.append(_("missing prices"))
		if reasons:
			problems.append(f"{design.design_ref} ({', '.join(reasons)})")
	if problems:
		raise QuoteNotReady(_("Fix these designs before quoting: {0}").format(", ".join(problems)))


def _target_quotation(project):
	"""The project's draft Quotation to update in place; a new one when it is missing, submitted or cancelled."""
	if project.quotation and frappe.db.get_value("Quotation", project.quotation, "docstatus") == 0:
		return frappe.get_doc("Quotation", project.quotation)
	return frappe.new_doc("Quotation")


class QuotationBuilder:
	def __init__(self, project, quotation):
		self.project = project
		self.quotation = quotation

	def build(self, designs: list[dict]) -> None:
		self.set_header()
		self.quotation.set("items", [])
		for design in designs:
			self.add_line(WINDOW_ITEM, design.qty, design.unit_price, design_line_text(design), design.name)
		if flt(self.project.transport_charges) > 0:
			self.add_line(TRANSPORT_ITEM, 1, self.project.transport_charges)
		self.set_taxes()
		self.quotation.save()

	def set_header(self):
		quotation, project = self.quotation, self.project
		today = nowdate()
		address = billing_address("Customer", project.customer)
		quotation.update(
			{
				"company": project.company,
				"quotation_to": "Customer",
				"party_name": project.customer,
				"customer_address": address,
				"transaction_date": today,
				"valid_till": add_days(today, QUOTE_VALIDITY_DAYS),
				"fen_project": project.name,
			}
		)
		if frappe.db.exists("Letter Head", DEFAULT_LETTER_HEAD):
			quotation.letter_head = DEFAULT_LETTER_HEAD
		terms = project.terms or (
			DEFAULT_TERMS if frappe.db.exists("Terms and Conditions", DEFAULT_TERMS) else None
		)
		if terms:
			from erpnext.setup.doctype.terms_and_conditions.terms_and_conditions import (
				get_terms_and_conditions,
			)

			quotation.tc_name = terms
			quotation.terms = get_terms_and_conditions(terms, quotation.as_dict())

	def add_line(self, item_code, qty, rate, text=None, design=None):
		# price_list_rate pinned to the rate so an Item Price on the generic item never overrides it
		row = {"item_code": item_code, "qty": qty, "rate": rate, "price_list_rate": rate, "uom": "Nos"}
		if text:
			row.update(item_name=text[0], description=text[1])
		if design:
			row["fen_window_design"] = design
		self.quotation.append("items", row)

	def set_taxes(self):
		"""Choose the GST template; ERPNext loads its rows and india_compliance validates them against the place of supply."""
		self.quotation.taxes_and_charges = gst_template(self.project.company, self.quotation.customer_address)
		self.quotation.set("taxes", [])
		self.quotation.run_method("set_missing_values")
		self.quotation.calculate_taxes_and_totals()


def gst_template(company: str, customer_address: str | None) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	customer_state = customer_address and frappe.db.get_value("Address", customer_address, "gst_state")
	company_state = _company_state(company)
	out_of_state = customer_state and company_state and customer_state != company_state
	return f"Output GST {'Out' if out_of_state else 'In'}-state - {abbr}"


def billing_address(link_doctype: str, link_name: str, company_address: bool = False) -> str | None:
	"""The party's billing address, primary first."""
	address = frappe.qb.DocType("Address")
	link = frappe.qb.DocType("Dynamic Link")
	query = (
		frappe.qb.from_(address)
		.join(link)
		.on(link.parent == address.name)
		.select(address.name)
		.where(link.parenttype == "Address")
		.where(link.link_doctype == link_doctype)
		.where(link.link_name == link_name)
		.where(address.disabled == 0)
		.orderby(address.is_primary_address, order=frappe.qb.desc)
		.limit(1)
	)
	query = (
		query.where(address.is_your_company_address == 1)
		if company_address
		else query.where(address.address_type == "Billing")
	)
	rows = query.run()
	return rows[0][0] if rows else None


def _company_state(company: str) -> str | None:
	address = billing_address("Company", company, company_address=True)
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


def design_line_text(design) -> tuple[str, str]:
	"""(item_name, description) for a design line: "W01 — 2 sash" and a one-line spec."""
	spec = json.loads(design.design_json) if isinstance(design.design_json, str) else design.design_json
	cells, _bars = layout(spec)
	snapshot = get_snapshot(design.series_version)
	glass_codes = dict.fromkeys(cell.node["glass"] for cell in cells if cell.node.get("glass"))
	glasses = [snapshot.glasses[code].name if code in snapshot.glasses else code for code in glass_codes]
	finish = frappe.db.get_value("Profile Finish", design.finish, "finish_name") or design.finish
	parts = [
		f"{spec['width']:g} × {spec['height']:g} mm",  # noqa: RUF001
		frappe.db.get_value("Series Version", design.series_version, "series"),
		finish,
		", ".join(glasses),
		f"{flt(design.area_sqft):g} sq.ft",
	]
	item_name = f"{design.design_ref} — {design.design_name or _typology(cells)}"
	return item_name, " · ".join(part for part in parts if part)


def _typology(cells) -> str:
	counts = {}
	for cell in cells:
		counts[cell.node["type"]] = counts.get(cell.node["type"], 0) + 1
	return " + ".join(f"{count} {kind}" for kind, count in counts.items())
