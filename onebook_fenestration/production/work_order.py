"""Sales Order "Work Order" button: design lines use their own BOM (D6), everything else is ERPNext's."""

import frappe
from erpnext.manufacturing.doctype.work_order.work_order import qty_against_sales_order
from erpnext.selling.doctype.sales_order import sales_order as erpnext_sales_order
from frappe import qb
from frappe.query_builder.functions import Sum
from frappe.utils import flt


@frappe.whitelist()
def get_work_order_items(sales_order: str, for_raw_material_request: int = 0):
	"""ERPNext's rows, except that a Window Design line is offered with its line's bom_no.

	ERPNext looks up the Item's default BOM, and FEN-WINDOW has none on purpose: every design line carries its own.
	"""
	rows = erpnext_sales_order.get_work_order_items(sales_order, for_raw_material_request)
	if not sales_order:
		return rows
	so = frappe.get_doc("Sales Order", sales_order)
	design_lines = {line.name: line for line in so.items if line.fen_window_design and line.bom_no}
	if not design_lines:
		return rows

	by_line = {row["sales_order_item"]: row for row in rows if row["sales_order_item"] not in design_lines}
	overproduction = (
		flt(frappe.get_single_value("Manufacturing Settings", "overproduction_percentage_for_sales_order")) / 100
	)
	for name, line in design_lines.items():
		pending_qty = _pending_qty(so.name, line, for_raw_material_request, overproduction)
		if pending_qty > 0:
			by_line[name] = _row(line, pending_qty, for_raw_material_request)

	# ERPNext's order: order lines first, then packed items.
	order = [line.name for line in so.items] + [row.name for row in so.packed_items]
	return [by_line[name] for name in order if name in by_line]


def _pending_qty(sales_order: str, line, for_raw_material_request, overproduction: float) -> float:
	"""ERPNext's pending quantity for one order line: stock qty less submitted Work Orders, or the overproduction
	allowance once it is fully covered."""
	stock_qty = line.stock_qty
	if for_raw_material_request:
		pending_qty = stock_qty
	else:
		wo = qb.DocType("Work Order")
		ordered = flt(
			qb.from_(wo)
			.select(Sum(qty_against_sales_order(wo, wo.qty - wo.process_loss_qty)))
			.where(
				(wo.production_item == line.item_code)
				& (wo.sales_order == sales_order)
				& (wo.sales_order_item == line.name)
				& (wo.docstatus == 1)
			)
			.run()[0][0]
		)
		pending_qty = stock_qty - ordered
	if not pending_qty:
		pending_qty = stock_qty * overproduction
	return pending_qty


def _row(line, pending_qty: float, for_raw_material_request) -> dict:
	return dict(
		name=line.name,
		item_code=line.item_code,
		item_name=line.item_name,
		description=line.description,
		bom=line.bom_no,
		warehouse=line.warehouse,
		pending_qty=pending_qty,
		required_qty=pending_qty if for_raw_material_request else 0,
		sales_order_item=line.name,
	)
