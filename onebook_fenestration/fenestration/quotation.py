import hashlib
import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate

from onebook_fenestration.engine.layout import layout
from onebook_fenestration.fenestration.doctype.fenestration_project.fenestration_project import (
	default_company,
)
from onebook_fenestration.fenestration.quote_party import (
	company_address,
	customer_addresses,
	gst_template,
	is_export,
	tax_address,
)
from onebook_fenestration.series_studio.snapshot import get_snapshot

WINDOW_ITEM = "FEN-WINDOW"
TRANSPORT_ITEM = "FEN-TRANSPORT"
DEFAULT_TERMS = "Hilux Standard Terms"
DEFAULT_LETTER_HEAD = "Company Letterhead"
QUOTE_VALIDITY_DAYS = 10
# Party-derived fields ERPNext and india_compliance only fill when empty; cleared so a requote re-derives them.
PARTY_FIELDS = (
	"customer_name",
	"customer_address",
	"address_display",
	"shipping_address_name",
	"shipping_address",
	"contact_person",
	"contact_display",
	"contact_email",
	"contact_mobile",
	"customer_group",
	"territory",
	"billing_address_gstin",
	"gst_category",
	"place_of_supply",
)
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
	"price_structure",
	"pricing_json",
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
	fields = ("docstatus", "status", "grand_total", "rounded_total", "net_total", "total_taxes_and_charges")
	values = name and frappe.db.get_value("Quotation", name, fields, as_dict=True)
	if not values:
		return {"quotation": None}
	values["rounded_total"] = values.rounded_total or values.grand_total
	stale = _staleness(project, name)
	return {"quotation": name, **values, "stale": stale, "is_stale": _is_stale(stale)}


def design_hash(design) -> str:
	"""Short fingerprint of what a quotation line was priced from; a different value later means the line is stale."""
	spec = design.design_json
	payload = {
		"design_json": json.loads(spec) if isinstance(spec, str) else spec,
		"series_version": design.series_version,
		"finish": design.finish,
		"price_structure": design.price_structure,
		"unit_price": flt(design.unit_price),
	}
	return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _is_stale(stale: dict) -> bool:
	return bool(stale["changed"] or stale["added"] or stale["removed"] or stale["transport_changed"])


def _staleness(project: str, quotation: str) -> dict:
	"""How the project's designs and transport differ from what the quotation was built from."""
	lines = frappe.get_all(
		"Quotation Item",
		{"parent": quotation, "parenttype": "Quotation"},
		["item_code", "item_name", "amount", "fen_window_design", "fen_design_hash"],
		order_by="idx",
	)
	designs = frappe.get_all("Window Design", {"project": project}, DESIGN_FIELDS, order_by="design_ref")
	by_name = {design.name: design for design in designs}
	quoted = {line.fen_window_design for line in lines if line.fen_window_design}
	# Deleting a design on a draft clears the line's link, so an unlinked window line also means "removed".
	removed = [
		line.item_name
		for line in lines
		if line.item_code == WINDOW_ITEM and line.fen_window_design not in by_name
	]
	changed = [
		by_name[line.fen_window_design].design_ref
		for line in lines
		if line.fen_window_design in by_name
		and line.fen_design_hash
		and line.fen_design_hash != design_hash(by_name[line.fen_window_design])
	]
	transport = sum(flt(line.amount) for line in lines if line.item_code == TRANSPORT_ITEM)
	project_transport = flt(frappe.db.get_value("Fenestration Project", project, "transport_charges"))
	return {
		"changed": changed,
		"added": [design.design_ref for design in designs if design.name not in quoted],
		"removed": removed,
		"transport_changed": abs(transport - project_transport) > 0.005,
	}


def check_quotable(project, designs: list[dict]) -> None:
	if not project.customer:
		raise QuoteNotReady(_("Set a customer on the project"))
	if not project.company:
		raise QuoteNotReady(_("Set a company on the project"))
	if not company_address(project.company):
		raise QuoteNotReady(_("Add your company address (with GSTIN) before quoting"))
	if not designs:
		raise QuoteNotReady(_("Add at least one window design"))
	problems = []
	for design in designs:
		reasons = [_("errors")] if cint(design.error_count) else []
		if cint(design.pricing_warning_count):
			reasons.append(_("missing prices") + _missing_items_suffix(design))
		if reasons:
			problems.append(f"{design.design_ref} ({', '.join(reasons)})")
	if problems:
		raise QuoteNotReady(_("Fix these designs before quoting: {0}").format(", ".join(problems)))


def _missing_items_suffix(design) -> str:
	"""": G21, G23" from the design's no_rate pricing issues, or "" when none are recorded."""
	pricing = json.loads(design.pricing_json or "{}")
	codes = [
		issue["message"].removesuffix(": no rate").split(" (")[0]  # "G21 (Price List): no rate"
		for issue in pricing.get("issues", [])
		if issue.get("code") == "no_rate"
	]
	return f": {', '.join(codes)}" if codes else ""


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
			self.add_line(
				WINDOW_ITEM, design.qty, design.unit_price, design_line_text(design), design.name, design_hash(design)
			)
		if flt(self.project.transport_charges) > 0:
			self.add_line(TRANSPORT_ITEM, 1, self.project.transport_charges)
		self.set_taxes()
		self.quotation.save()

	def set_header(self):
		quotation, project = self.quotation, self.project
		today = nowdate()
		if not quotation.is_new():
			for fieldname in PARTY_FIELDS:
				if quotation.meta.has_field(fieldname):
					quotation.set(fieldname, None)
		billing, shipping = customer_addresses(project.customer)
		quotation.update(
			{
				"company": project.company,
				# A customer's own currency must not leak in: design prices are in company currency.
				"currency": frappe.get_cached_value("Company", project.company, "default_currency"),
				"conversion_rate": 1,
				"plc_conversion_rate": 1,
				"quotation_to": "Customer",
				"party_name": project.customer,
				"customer_address": billing,
				"shipping_address_name": shipping,
				"ignore_pricing_rule": 1,
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

	def add_line(self, item_code, qty, rate, text=None, design=None, hash_=None):
		# price_list_rate pinned to the rate so an Item Price on the generic item never overrides it
		row = {"item_code": item_code, "qty": qty, "rate": rate, "price_list_rate": rate, "uom": "Nos"}
		if text:
			row.update(item_name=text[0], description=text[1])
		if design:
			row.update(fen_window_design=design, fen_design_hash=hash_)
		self.quotation.append("items", row)

	def set_taxes(self):
		"""Choose the GST template; ERPNext loads its rows and india_compliance validates them against the place of supply."""
		address = tax_address(self.quotation.customer_address, self.quotation.shipping_address_name)
		self.quotation.taxes_and_charges = gst_template(self.project.company, self.project.customer, address)
		if self.quotation.meta.has_field("is_export_with_gst"):
			# The quote shows IGST for SEZ/Overseas; india_compliance rejects GST rows on exports under LUT.
			self.quotation.is_export_with_gst = int(is_export(self.project.customer, address))
		self.quotation.set("taxes", [])
		self.quotation.run_method("set_missing_values")
		self.quotation.calculate_taxes_and_totals()


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
