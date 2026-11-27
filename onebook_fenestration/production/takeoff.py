"""Project-level BOM & Material Takeoff tree (Project -> Window -> Profile / Glass / Hardware) and procurement creation."""

import json
import math
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate

from onebook_fenestration.engine import DesignError, RuleError, compute
from onebook_fenestration.fenestration.doctype.fenestration_project.fenestration_project import (
	default_company,
)
from onebook_fenestration.production.bom import GASKET_GROUP
from onebook_fenestration.series_studio.snapshot import get_snapshot

VALID_CATEGORIES = ("all", "Profile", "Glass", "Hardware")


def project_material_tree(project_name: str) -> dict:
	"""Return the categorized BOM tree per Window Design plus a consolidated project procurement summary."""
	frappe.has_permission("Fenestration Project", "read", project_name, throw=True)
	project = frappe.get_doc("Fenestration Project", project_name)
	company = project.company or default_company() or frappe.db.get_value("Company", {}, "name")
	designs = frappe.get_all(
		"Window Design",
		filters={"project": project_name, "superseded_by": ("is", "not set")},
		fields=[
			"name",
			"design_ref",
			"design_name",
			"qty",
			"series_version",
			"finish",
			"floor",
			"location",
			"design_json",
			"design_svg",
		],
		order_by="design_ref asc, name asc",
	)

	meta_cache = _MasterLookup(company)
	windows = []
	all_problems: list[str] = []
	summary_profiles: dict[tuple[str, float], dict] = {}
	summary_glass: dict[tuple[str, float, float], dict] = {}
	summary_hardware: dict[tuple[str, str], dict] = {}

	for design in designs:
		win, problems = _build_window_entry(design, meta_cache)
		windows.append(win)
		all_problems.extend(problems)
		_accumulate_summary(win, summary_profiles, summary_glass, summary_hardware)

	warehouses = _company_warehouses(company)
	default_wh = _resolve_default_warehouse(company, warehouses)

	return {
		"project": {
			"name": project.name,
			"project_title": project.project_title,
			"customer": project.customer,
			"company": company,
		},
		"warehouses": warehouses,
		"default_warehouse": default_wh,
		"windows": windows,
		"summary": {
			"profiles": sorted(
				summary_profiles.values(),
				key=lambda r: (r["item_code"] or r["profile_code"], -r["cut_length_mm"]),
			),
			"glass": sorted(
				summary_glass.values(),
				key=lambda r: (r["item_code"] or r["glass_code"], -r["width_mm"], -r["height_mm"]),
			),
			"hardware": sorted(
				summary_hardware.values(),
				key=lambda r: (r["category"], r["item_code"]),
			),
		},
		"problems": list(dict.fromkeys(all_problems)),
	}


def create_material_request_from_project(
	project_name: str,
	category: str = "all",
	warehouse: str | None = None,
) -> str:
	"""Create a Draft Material Request (Purchase) for a project's BOM takeoff filtered by category."""
	tree, target_wh, items = _prepare_procurement_lines(project_name, category, warehouse)
	company = tree["project"]["company"]
	mr = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": "Purchase",
			"company": company,
			"transaction_date": nowdate(),
			"schedule_date": min(row["schedule_date"] for row in items),
			"set_warehouse": target_wh,
			"fen_project": project_name,
			"items": [
				{
					"item_code": row["item_code"],
					"qty": row["qty"],
					"uom": row["uom"],
					"warehouse": target_wh,
					"schedule_date": row["schedule_date"],
					"fen_cut_length_mm": row["fen_cut_length_mm"],
					"fen_piece_count": row["fen_piece_count"],
					"fen_spec_note": row["fen_spec_note"],
					"description": row["description"],
				}
				for row in items
			],
		}
	)
	mr.insert()
	return mr.name


def create_purchase_order_from_project(
	project_name: str,
	supplier: str,
	category: str = "all",
	warehouse: str | None = None,
) -> str:
	"""Create a Draft Purchase Order directly for a supplier from a project's BOM takeoff."""
	if not supplier or not frappe.db.exists("Supplier", supplier):
		frappe.throw(_("Select a valid Supplier."))
	tree, target_wh, items = _prepare_procurement_lines(project_name, category, warehouse)
	company = tree["project"]["company"]
	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"supplier": supplier,
			"company": company,
			"transaction_date": nowdate(),
			"schedule_date": max(row["schedule_date"] for row in items),
			"set_warehouse": target_wh,
			"fen_project": project_name,
			"items": [
				{
					"item_code": row["item_code"],
					"qty": row["qty"],
					"uom": row["uom"],
					"warehouse": target_wh,
					"schedule_date": row["schedule_date"],
					"fen_cut_length_mm": row["fen_cut_length_mm"],
					"fen_piece_count": row["fen_piece_count"],
					"fen_spec_note": row["fen_spec_note"],
					"description": row["description"],
				}
				for row in items
			],
		}
	)
	po.insert()
	return po.name


def _prepare_procurement_lines(
	project_name: str, category: str, warehouse: str | None
) -> tuple[dict, str, list[dict]]:
	if category not in VALID_CATEGORIES:
		frappe.throw(_("Invalid category: {0}").format(category))
	tree = project_material_tree(project_name)
	target_wh = warehouse or tree["default_warehouse"]
	if not target_wh or not frappe.db.exists("Warehouse", target_wh):
		frappe.throw(_("Select a valid target Warehouse."))
	if frappe.db.get_value("Warehouse", target_wh, "is_group"):
		frappe.throw(_("Target Warehouse {0} cannot be a group warehouse.").format(target_wh))

	selected = _select_summary_rows(tree["summary"], category)
	if not selected:
		frappe.throw(_("No items found in {0} for category {1}.").format(project_name, category))

	missing = [r["label"] for r in selected if not r["item_code"] or not frappe.db.exists("Item", r["item_code"])]
	if missing:
		frappe.throw(
			_("Missing ERP Item master for: {0}").format(", ".join(sorted(set(missing))))
		)

	lines = []
	for row in selected:
		lead_days = cint(frappe.db.get_value("Item", row["item_code"], "lead_time_days")) or 7
		lines.append(
			{
				**row,
				"schedule_date": add_days(nowdate(), lead_days),
			}
		)
	return tree, target_wh, lines


def _select_summary_rows(summary: dict, category: str) -> list[dict]:
	rows = []
	if category in ("all", "Profile"):
		for p in summary["profiles"]:
			qty = round(flt(p["kg"]), 3)
			if qty <= 0:
				continue
			rows.append(
				{
					"label": f"profile {p['profile_code']}",
					"item_code": p["item_code"],
					"qty": qty,
					"uom": p["uom"],
					"fen_cut_length_mm": p["cut_length_mm"],
					"fen_piece_count": p["pieces"],
					"fen_spec_note": p["spec_note"],
					"description": f"{p['item_name'] or p['profile_code']} | Cut: {p['spec_note']} ({qty:.3f} kg)",
				}
			)
	if category in ("all", "Glass"):
		for g in summary["glass"]:
			qty = round(flt(g["area_m2"]), 3)
			if qty <= 0:
				continue
			rows.append(
				{
					"label": f"glass {g['glass_code']}",
					"item_code": g["item_code"],
					"qty": qty,
					"uom": g["uom"],
					"fen_cut_length_mm": 0,
					"fen_piece_count": g["pieces"],
					"fen_spec_note": g["spec_note"],
					"description": f"{g['item_name'] or g['glass_code']} | Pane: {g['spec_note']} ({qty:.3f} m2)",
				}
			)
	if category in ("all", "Hardware"):
		for h in summary["hardware"]:
			qty = round(flt(h["qty"]), 3)
			if qty <= 0:
				continue
			if cint(frappe.db.get_value("UOM", h["uom"], "must_be_whole_number")):
				qty = float(math.ceil(qty))
			rows.append(
				{
					"label": f"hardware {h['item_code']}",
					"item_code": h["item_code"],
					"qty": qty,
					"uom": h["uom"],
					"fen_cut_length_mm": 0,
					"fen_piece_count": cint(qty) if h["uom"] in ("Nos", "Pair", "Pairs", "Can") else 0,
					"fen_spec_note": h["spec_note"],
					"description": h["item_name"] or h["item_code"],
				}
			)
	return rows


def _build_window_entry(design: dict, meta: "_MasterLookup") -> tuple[dict, list[str]]:
	design_qty = max(cint(design.qty), 1)
	problems: list[str] = []
	profiles_list: list[dict] = []
	glass_list: list[dict] = []
	hardware_list: list[dict] = []

	width_mm = None
	height_mm = None
	try:
		snapshot = get_snapshot(design.series_version)
		spec = json.loads(design.design_json) if isinstance(design.design_json, str) else design.design_json
		if isinstance(spec, dict):
			width_mm = spec.get("width")
			height_mm = spec.get("height")
		result = compute(spec, snapshot)
	except (DesignError, RuleError, json.JSONDecodeError, frappe.DoesNotExistError) as exc:
		problems.append(f"{design.design_ref or design.name}: {exc}")
		result = None

	if result:
		profiles_list, p_probs = _collect_window_profiles(design, design_qty, result, snapshot, meta)
		glass_list, g_probs = _collect_window_glass(design, design_qty, result, meta)
		hardware_list, h_probs = _collect_window_hardware(design, design_qty, result, meta)
		problems.extend(p_probs + g_probs + h_probs)

	return (
		{
			"name": design.name,
			"design_ref": design.design_ref or design.name,
			"design_name": design.design_name or "",
			"qty": design_qty,
			"series_version": design.series_version,
			"finish": design.finish or "",
			"floor": design.floor or "",
			"location": design.location or "",
			"width_mm": width_mm,
			"height_mm": height_mm,
			"design_svg": design.get("design_svg") or "",
			"profiles": profiles_list,
			"glass": glass_list,
			"hardware": hardware_list,
			"problems": problems,
		},
		problems,
	)


def _collect_window_profiles(design, design_qty: int, result, snapshot, meta: "_MasterLookup") -> tuple[list[dict], list[str]]:
	problems: list[str] = []
	by_profile: dict[str, dict] = {}
	cuts_map: dict[tuple[str, float, str, str], dict] = {}

	for member in result.members:
		code = member.profile
		p_info = meta.profile(code)
		if not p_info["item_code"]:
			problems.append(_("{0}: missing Item on profile {1}").format(design.design_ref or design.name, code))
		kg_per_m = flt(snapshot.profiles[code].kg_per_m) if code in snapshot.profiles else flt(p_info["kg_per_m"])
		cut_mm = round(flt(member.length), 1)
		cut_kg = cut_mm / 1000.0 * kg_per_m

		item_info = meta.item(p_info["item_code"]) if p_info["item_code"] else None
		uom = (
			item_info["stock_uom"]
			if item_info and item_info["exists"] and "Kg" not in item_info["valid_uoms"] and item_info["stock_uom"]
			else "Kg"
		)
		grp = by_profile.setdefault(
			code,
			{
				"profile_code": code,
				"item_code": p_info["item_code"],
				"item_name": p_info["item_name"] or p_info["profile_name"] or code,
				"uom": uom,
				"kg": 0.0,
				"total_mm": 0.0,
				"pieces": 0,
				"default_supplier": p_info["default_supplier"],
				"cuts": [],
			},
		)
		grp["total_mm"] += cut_mm * design_qty
		grp["kg"] += cut_kg * design_qty
		grp["pieces"] += design_qty

		cut_key = (code, cut_mm, member.angles or "", member.role or "")
		cut_row = cuts_map.setdefault(
			cut_key,
			{
				"length_mm": cut_mm,
				"pieces": 0,
				"angles": member.angles or "",
				"role": member.role or "",
				"kg": 0.0,
			},
		)
		cut_row["pieces"] += design_qty
		cut_row["kg"] += cut_kg * design_qty

	for (code, *_rest), cut_row in cuts_map.items():
		cut_row["kg"] = round(cut_row["kg"], 3)
		by_profile[code]["cuts"].append(cut_row)

	out = []
	for grp in sorted(by_profile.values(), key=lambda r: r["profile_code"]):
		grp["total_mm"] = round(grp["total_mm"], 1)
		grp["kg"] = round(grp["kg"], 3)
		grp["cuts"].sort(key=lambda c: (-c["length_mm"], c["role"]))
		out.append(grp)
	return out, problems


def _collect_window_glass(design, design_qty: int, result, meta: "_MasterLookup") -> tuple[list[dict], list[str]]:
	problems: list[str] = []
	by_glass: dict[str, dict] = {}
	panes_map: dict[tuple[str, float, float, str], dict] = {}

	for pane in result.glass:
		if pane.material == "steel":
			problems.append(
				_("{0}: steel sheet {1:g} mm ({2}) has no raw-material Item").format(
					design.design_ref or design.name, pane.thickness, pane.path
				)
			)
			continue
		code = pane.glass
		g_info = meta.glass(code)
		if not g_info["item_code"]:
			problems.append(_("{0}: missing Item on glass {1}").format(design.design_ref or design.name, code))
		w = round(flt(pane.width), 1)
		h = round(flt(pane.height), 1)
		area = w * h / 1e6

		item_info = meta.item(g_info["item_code"]) if g_info["item_code"] else None
		uom = (
			item_info["stock_uom"]
			if item_info and item_info["exists"] and "Square Meter" not in item_info["valid_uoms"] and item_info["stock_uom"]
			else "Square Meter"
		)
		grp = by_glass.setdefault(
			code,
			{
				"glass_code": code,
				"item_code": g_info["item_code"],
				"item_name": g_info["item_name"] or g_info["glass_name"] or code,
				"uom": uom,
				"area_m2": 0.0,
				"pieces": 0,
				"default_supplier": g_info["default_supplier"],
				"panes": [],
			},
		)
		grp["area_m2"] += area * design_qty
		grp["pieces"] += design_qty

		pane_key = (code, w, h, pane.material or "glass")
		pane_row = panes_map.setdefault(
			pane_key,
			{
				"width_mm": w,
				"height_mm": h,
				"pieces": 0,
				"area_m2": 0.0,
				"material": pane.material or "glass",
			},
		)
		pane_row["pieces"] += design_qty
		pane_row["area_m2"] += area * design_qty

	for (code, *_rest), pane_row in panes_map.items():
		pane_row["area_m2"] = round(pane_row["area_m2"], 3)
		by_glass[code]["panes"].append(pane_row)

	out = []
	for grp in sorted(by_glass.values(), key=lambda r: r["glass_code"]):
		grp["area_m2"] = round(grp["area_m2"], 3)
		grp["panes"].sort(key=lambda p: (-p["width_mm"], -p["height_mm"]))
		out.append(grp)
	return out, problems


def _collect_window_hardware(design, design_qty: int, result, meta: "_MasterLookup") -> tuple[list[dict], list[str]]:
	problems: list[str] = []
	by_item: dict[tuple[str, str, str], dict] = {}

	for line in result.bom:
		is_gasket = line.group == GASKET_GROUP
		info = meta.item(line.item)
		if not info["exists"]:
			problems.append(_("{0}: missing Item {1}").format(design.design_ref or design.name, line.item))
		raw_uom = "Meter" if is_gasket else line.uom
		if info["exists"] and raw_uom not in info["valid_uoms"] and info["stock_uom"]:
			uom = info["stock_uom"]
		else:
			uom = raw_uom
		qty_unit = flt(line.length) / 1000.0 if is_gasket else flt(line.qty)
		category = "Gasket" if is_gasket else "Hardware"
		key = (line.item, uom, category)
		row = by_item.setdefault(
			key,
			{
				"item_code": line.item,
				"item_name": info["item_name"] or line.name or line.item,
				"category": category,
				"group": line.group or category,
				"qty": 0.0,
				"uom": uom,
				"length_mm": 0.0,
				"default_supplier": info["default_supplier"],
			},
		)
		row["qty"] += qty_unit * design_qty
		if is_gasket:
			row["length_mm"] += flt(line.length) * design_qty

	out = []
	for row in sorted(by_item.values(), key=lambda r: (r["category"], r["item_code"])):
		row["qty"] = round(row["qty"], 3)
		row["length_mm"] = round(row["length_mm"], 1)
		out.append(row)
	return out, problems


def _accumulate_summary(
	win: dict,
	summary_profiles: dict[tuple[str, float], dict],
	summary_glass: dict[tuple[str, float, float], dict],
	summary_hardware: dict[tuple[str, str], dict],
) -> None:
	for p in win["profiles"]:
		for cut in p["cuts"]:
			key = (p["item_code"] or p["profile_code"], cut["length_mm"])
			entry = summary_profiles.setdefault(
				key,
				{
					"item_code": p["item_code"],
					"profile_code": p["profile_code"],
					"item_name": p["item_name"],
					"cut_length_mm": cut["length_mm"],
					"pieces": 0,
					"total_mm": 0.0,
					"kg": 0.0,
					"uom": p["uom"],
					"default_supplier": p["default_supplier"],
					"spec_note": "",
				},
			)
			entry["pieces"] += cut["pieces"]
			entry["total_mm"] = round(entry["total_mm"] + cut["length_mm"] * cut["pieces"], 1)
			entry["kg"] = round(entry["kg"] + cut["kg"], 3)
			entry["spec_note"] = f"{entry['cut_length_mm']:g} mm x {entry['pieces']} pcs"

	for g in win["glass"]:
		for pane in g["panes"]:
			key = (g["item_code"] or g["glass_code"], pane["width_mm"], pane["height_mm"])
			entry = summary_glass.setdefault(
				key,
				{
					"item_code": g["item_code"],
					"glass_code": g["glass_code"],
					"item_name": g["item_name"],
					"width_mm": pane["width_mm"],
					"height_mm": pane["height_mm"],
					"pieces": 0,
					"area_m2": 0.0,
					"uom": g["uom"],
					"default_supplier": g["default_supplier"],
					"spec_note": "",
				},
			)
			entry["pieces"] += pane["pieces"]
			entry["area_m2"] = round(entry["area_m2"] + pane["area_m2"], 3)
			entry["spec_note"] = f"{entry['width_mm']:g} x {entry['height_mm']:g} mm x {entry['pieces']} pcs"

	for h in win["hardware"]:
		key = (h["item_code"], h["uom"])
		entry = summary_hardware.setdefault(
			key,
			{
				"item_code": h["item_code"],
				"item_name": h["item_name"],
				"category": h["category"],
				"group": h["group"],
				"qty": 0.0,
				"uom": h["uom"],
				"default_supplier": h["default_supplier"],
				"spec_note": "",
			},
		)
		entry["qty"] = round(entry["qty"] + h["qty"], 3)
		entry["spec_note"] = f"{entry['qty']:g} {entry['uom']}"


def _company_warehouses(company: str | None) -> list[dict]:
	if not company or not frappe.has_permission("Warehouse", "read"):
		return []
	return frappe.get_list(
		"Warehouse",
		filters={"company": company, "is_group": 0, "disabled": 0},
		fields=["name", "warehouse_name"],
		order_by="warehouse_name asc",
		limit_page_length=200,
	)


def _resolve_default_warehouse(company: str | None, warehouses: list[dict]) -> str | None:
	comp_default = frappe.db.get_value("Company", company, "default_warehouse") if company else None
	if comp_default and any(w["name"] == comp_default for w in warehouses):
		return comp_default
	stores = next((w["name"] for w in warehouses if w["warehouse_name"] == "Stores"), None)
	if stores:
		return stores
	main = next((w["name"] for w in warehouses if w["warehouse_name"] == "Main Warehouse"), None)
	if main:
		return main
	return warehouses[0]["name"] if warehouses else None


class _MasterLookup:
	"""Small request-scoped cache for Fenestration Profile, Glass, Item, and default Supplier lookups."""

	def __init__(self, company: str | None):
		self.company = company
		self._profiles: dict[str, dict] = {}
		self._glasses: dict[str, dict] = {}
		self._items: dict[str, dict] = {}

	def profile(self, code: str) -> dict:
		if code not in self._profiles:
			row = frappe.db.get_value(
				"Fenestration Profile", code, ["item", "profile_name", "kg_per_m"], as_dict=True
			) or {}
			item_code = row.get("item") or ""
			item_info = self.item(item_code) if item_code else {"item_name": "", "default_supplier": None}
			self._profiles[code] = {
				"item_code": item_code,
				"profile_name": row.get("profile_name") or "",
				"kg_per_m": row.get("kg_per_m") or 0,
				"item_name": item_info["item_name"],
				"default_supplier": item_info["default_supplier"],
			}
		return self._profiles[code]

	def glass(self, code: str) -> dict:
		if code not in self._glasses:
			row = frappe.db.get_value("Fenestration Glass", code, ["item", "glass_name"], as_dict=True) or {}
			item_code = row.get("item") or ""
			item_info = self.item(item_code) if item_code else {"item_name": "", "default_supplier": None}
			self._glasses[code] = {
				"item_code": item_code,
				"glass_name": row.get("glass_name") or "",
				"item_name": item_info["item_name"],
				"default_supplier": item_info["default_supplier"],
			}
		return self._glasses[code]

	def item(self, item_code: str) -> dict:
		if item_code not in self._items:
			row = frappe.db.get_value("Item", item_code, ["item_name", "stock_uom"], as_dict=True)
			supplier = None
			valid_uoms: set[str] = set()
			if row:
				if row.get("stock_uom"):
					valid_uoms.add(row["stock_uom"])
				conv_uoms = frappe.get_all(
					"UOM Conversion Detail",
					filters={"parent": item_code, "parenttype": "Item"},
					pluck="uom",
				)
				valid_uoms.update(u for u in conv_uoms if u)
			if row and self.company and frappe.has_permission("Supplier", "read"):
				supplier = frappe.db.get_value(
					"Item Default",
					{"parent": item_code, "parenttype": "Item", "company": self.company},
					"default_supplier",
				)
			self._items[item_code] = {
				"exists": bool(row),
				"item_name": (row or {}).get("item_name") or "",
				"stock_uom": (row or {}).get("stock_uom") or "",
				"valid_uoms": valid_uoms,
				"default_supplier": supplier,
			}
		return self._items[item_code]
