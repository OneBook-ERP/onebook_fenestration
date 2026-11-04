"""Rate sheet: download the items a series needs priced, import the filled-in rates as Item Prices."""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from frappe.utils.xlsxutils import make_xlsx, read_xlsx_file_from_attached_file

from onebook_fenestration.pricing.rates import _item_prices
from onebook_fenestration.series_studio.snapshot import get_snapshot

ROLES = ("System Manager", "Fenestration Engineer")
COLUMNS = ["item_code", "item_name", "kind", "uom", "rate_basis", "current_rate", "series", "new_rate", "valid_from"]
GLASS_BASIS = "per m2"
PROFILE_BASIS = "per kg"


def series_items(series_versions: list[str] | None = None) -> list[dict]:
	"""Distinct items used by the versions (default: all submitted): profiles, glasses, hardware and gaskets.

	Each dict has item_code, item_name, kind, uom (stock uom), rate_basis and series (comma list of series codes).
	Glasses are the version's snapshot catalogue mapped through Fenestration Glass.item.
	"""
	submitted = frappe.get_all(
		"Series Version",
		filters={"docstatus": 1, **({"name": ["in", series_versions]} if series_versions else {})},
		pluck="name",
	)
	versions = submitted
	used = {}  # item_code -> (kind, set of series)
	for version in versions:
		series = frappe.db.get_value("Series Version", version, "series")
		for item_code, kind in _version_items(version):
			used.setdefault(item_code, (kind, set()))[1].add(series)
	details = {
		row.name: row
		for row in frappe.get_all("Item", filters={"name": ["in", list(used)]}, fields=["name", "item_name", "stock_uom"])
	}
	rows = []
	for item_code, (kind, series) in sorted(used.items()):
		if item_code not in details:
			continue
		uom = details[item_code].stock_uom
		rows.append(
			{
				"item_code": item_code,
				"item_name": details[item_code].item_name,
				"kind": kind,
				"uom": uom,
				"rate_basis": _rate_basis(kind, uom),
				"series": ", ".join(sorted(series)),
			}
		)
	return rows


@frappe.whitelist()
def rate_sheet_rows(series_versions: list[str] | None = None) -> list[dict]:
	frappe.only_for(ROLES)
	if isinstance(series_versions, str):
		series_versions = frappe.parse_json(series_versions)
	rows = series_items(series_versions)
	price_list = _cost_price_list(required=False)
	prices = _item_prices(price_list, {r["item_code"] for r in rows}) if price_list else {}
	return [{**row, "current_rate": prices.get(row["item_code"])} for row in rows]


@frappe.whitelist()
def download_rate_sheet() -> None:
	frappe.only_for(ROLES)
	data = [COLUMNS] + [[row.get(col) for col in COLUMNS] for row in rate_sheet_rows()]
	frappe.response["filename"] = "rate-sheet.xlsx"
	frappe.response["filecontent"] = make_xlsx(data, "Rates").getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def import_rate_sheet(file_url: str) -> dict:
	frappe.only_for(ROLES)
	price_list = _cost_price_list(required=True)
	rows = _read_rows(file_url)
	if not rows:
		frappe.throw(_("The rate sheet is empty"))
	header = [str(h or "").strip() for h in rows[0]]
	if "item_code" not in header or "new_rate" not in header:
		frappe.throw(_("The rate sheet needs item_code and new_rate columns"))
	result = {"created": 0, "updated": 0, "unchanged": 0, "skipped": []}
	for number, cells in enumerate(rows[1:], start=2):
		row = dict(zip(header, cells, strict=False))
		if row.get("new_rate") in (None, ""):
			continue
		outcome = _import_row(price_list, row)
		if outcome in result:
			result[outcome] += 1
		else:
			result["skipped"].append({"row": number, "item_code": row.get("item_code"), "reason": outcome})
	return result


def _read_rows(file_url: str) -> list:
	"""Rows of an uploaded .xlsx the user may read; anything else is a clean error."""
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name") if file_url else None
	if not file_name:
		frappe.throw(_("File not found"))
	file_doc = frappe.get_doc("File", file_name)
	unattached = not file_doc.attached_to_doctype or file_doc.attached_to_doctype == "Fenestration Settings"
	if not (unattached or file_doc.has_permission("read")):
		frappe.throw(_("You cannot read this file"), frappe.PermissionError)
	if not (file_doc.file_name or "").lower().endswith(".xlsx"):
		frappe.throw(_("Not a valid .xlsx file"))
	try:
		return read_xlsx_file_from_attached_file(file_url=file_doc.file_url) or []
	except Exception:
		frappe.throw(_("Not a valid .xlsx file"))


def _import_row(price_list: str, row: dict) -> str:
	"""'created' / 'updated' / 'unchanged', or the reason the row is skipped."""
	item_code = str(row.get("item_code") or "").strip()
	uom = frappe.db.get_value("Item", item_code, "stock_uom") if item_code else None
	if not uom:
		return _("Unknown item")
	try:
		rate = flt(row["new_rate"]) if not isinstance(row["new_rate"], str) else float(row["new_rate"])
	except ValueError:
		return _("Rate is not a number")
	if rate <= 0:
		return _("Rate must be greater than zero")
	try:
		valid_from = getdate(row.get("valid_from")) if row.get("valid_from") else getdate(today())
	except Exception:
		return _("Invalid valid_from date")
	return _upsert_price(price_list, item_code, uom, rate, valid_from)


def _upsert_price(price_list: str, item_code: str, uom: str, rate: float, valid_from) -> str:
	name = frappe.db.get_value(
		"Item Price",
		{"price_list": price_list, "item_code": item_code, "valid_from": valid_from, "uom": uom, "customer": ["is", "not set"], "supplier": ["is", "not set"], "batch_no": ["is", "not set"]},
		"name",
	)
	if not name:
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"price_list": price_list,
				"item_code": item_code,
				"uom": uom,
				"price_list_rate": rate,
				"valid_from": valid_from,
			}
		).insert()
		return "created"
	if flt(frappe.db.get_value("Item Price", name, "price_list_rate")) == rate:
		return "unchanged"
	frappe.db.set_value("Item Price", name, "price_list_rate", rate)
	return "updated"


def _cost_price_list(required: bool) -> str | None:
	price_list = frappe.db.get_single_value("Fenestration Settings", "cost_price_list")
	if not price_list and required:
		frappe.throw(_("Set the cost price list in Fenestration Settings first"))
	return price_list


def _rate_basis(kind: str, uom: str) -> str:
	if kind == "Profile":
		return PROFILE_BASIS
	if kind == "Glass":
		return GLASS_BASIS
	return f"per {uom}"


def _version_items(version: str) -> list[tuple[str, str]]:
	"""(item code, kind) for every priced item a version uses."""
	found = []
	profiles = {r.profile for r in frappe.get_all("Series Member Rule", filters={"parent": version}, fields=["profile"])}
	found += [(item, "Profile") for item in _linked_items("Fenestration Profile", "profile_code", profiles)]
	glasses = set(get_snapshot(version).glasses)
	found += [(item, "Glass") for item in _linked_items("Fenestration Glass", "glass_code", glasses)]
	for rule in frappe.get_all("Series Hardware Rule", filters={"parent": version}, fields=["item", "bom_group"]):
		if rule.item:
			found.append((rule.item, "Gasket" if rule.bom_group == "Gasket" else "Hardware"))
	return found


def _linked_items(doctype: str, code_field: str, codes: set) -> list[str]:
	if not codes:
		return []
	return frappe.get_all(doctype, filters={code_field: ["in", list(codes)], "item": ["is", "set"]}, pluck="item")
