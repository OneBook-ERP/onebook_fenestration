"""Sales Order submit -> one submitted BOM per design line under the shared FEN-WINDOW item (decision D6)."""

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from onebook_fenestration.engine import compute
from onebook_fenestration.fenestration.quotation import design_hash
from onebook_fenestration.series_studio.snapshot import get_snapshot

WINDOW_ITEM = "FEN-WINDOW"
GASKET_GROUP = "Gasket"


def bom_rows(design) -> list[dict]:
	"""BOM item rows for one window (quantity 1), aggregated by item and sorted by item code."""
	rows, problems = collect_rows(design)
	if problems:
		frappe.throw("<br>".join(problems))
	return rows


def collect_rows(design) -> tuple[list[dict], list[str]]:
	"""(rows, problems): the BOM rows for one window and every Item that is missing or stocked in the wrong unit."""
	snapshot = get_snapshot(design.series_version)
	spec = design.design_json
	result = compute(json.loads(spec) if isinstance(spec, str) else spec, snapshot)

	totals: dict[tuple[str, str], float] = defaultdict(float)
	missing: list[str] = []

	def add(item, uom, qty, label):
		if not item:
			missing.append(label)
			return
		totals[(item, uom)] += qty

	profile_mm: dict[str, float] = defaultdict(float)
	for member in result.members:
		profile_mm[member.profile] += member.length
	for code, mm in profile_mm.items():
		item = frappe.db.get_value("Fenestration Profile", code, "item")
		add(item, "Kg", mm / 1000 * snapshot.profiles[code].kg_per_m, f"profile {code}")

	for line in result.bom:
		if line.group == GASKET_GROUP:
			add(line.item, "Meter", flt(line.length) / 1000, f"gasket {line.item}")
		else:
			add(line.item, line.uom, line.qty, f"hardware {line.item}")

	pane_m2: dict[str, float] = defaultdict(float)
	for pane in result.glass:
		pane_m2[pane.glass] += pane.width * pane.height / 1e6
	for code, area in pane_m2.items():
		add(frappe.db.get_value("Fenestration Glass", code, "item"), "Square Meter", area, f"glass {code}")

	problems = []
	if missing:
		problems.append(
			_("{0} has no Item for: {1}. Create the Items before ordering.").format(
				design.name, ", ".join(sorted(set(missing)))
			)
		)
	for item, uom in totals:
		problem = _unit_problem(item, uom)
		if problem:
			problems.append(problem)
	rows = [{"item_code": item, "qty": round(qty, 3), "uom": uom} for (item, uom), qty in sorted(totals.items())]
	return rows, problems


def _unit_problem(item: str, uom: str) -> str | None:
	stock_uom = frappe.db.get_value("Item", item, "stock_uom")
	if stock_uom is None:
		return _("Item {0} does not exist.").format(item)
	if stock_uom != uom and not frappe.db.exists(
		"UOM Conversion Detail", {"parenttype": "Item", "parent": item, "uom": uom}
	):
		return _("Item {0} is stocked in {1}; BOM needs {2}").format(item, stock_uom, uom)
	return None


def ensure_bom(design_name: str, design_hash: str, rows: list[dict] | None = None) -> str:
	"""The submitted active BOM for this design and hash; created and submitted when none exists."""
	existing = frappe.db.get_value(
		"BOM",
		{"fen_window_design": design_name, "fen_design_hash": design_hash, "docstatus": 1, "is_active": 1},
		"name",
	)
	if existing:
		return existing
	if rows is None:
		rows = bom_rows(frappe.get_doc("Window Design", design_name))
	bom = frappe.get_doc(
		{
			"doctype": "BOM",
			"item": WINDOW_ITEM,
			"quantity": 1,
			"is_default": 0,
			"is_active": 1,
			"rm_cost_as_per": "Valuation Rate",
			"fen_window_design": design_name,
			"fen_design_hash": design_hash,
			"items": rows,
		}
	)
	bom.insert(ignore_permissions=True)
	bom.submit()
	return bom.name


def set_order_boms(doc, method=None) -> None:
	"""Sales Order before_submit: check each design line is current, then attach its BOM."""
	lines = []
	for item in doc.items:
		if not item.fen_window_design:
			continue
		design = frappe.get_doc("Window Design", item.fen_window_design)
		if design_hash(design) != item.fen_design_hash:
			frappe.throw(_("{0} changed since the quotation. Requote before ordering.").format(design.design_ref or design.name))
		lines.append((item, design))

	# Resolve every design's rows first so any problem refuses the submit before a BOM exists.
	prepared = []
	problems = []
	for item, design in lines:
		rows, design_problems = collect_rows(design)
		prepared.append((item, design, rows))
		problems += design_problems
	if problems:
		frappe.throw("<br>".join(dict.fromkeys(problems)))
	for item, design, rows in prepared:
		item.bom_no = ensure_bom(design.name, item.fen_design_hash, rows)
