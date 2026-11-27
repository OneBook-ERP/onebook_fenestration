from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from onebook_fenestration.fenestration import flow


class TestFlowHelpers(unittest.TestCase):
	def setUp(self):
		self.patches = [
			patch.object(flow, "_", side_effect=lambda msg: msg),
			patch.object(flow, "nowdate", return_value="2026-11-19"),
			patch.object(flow.frappe, "db", MagicMock()),
			patch.object(
				flow.frappe,
				"throw",
				side_effect=lambda msg: (_ for _ in ()).throw(frappe.ValidationError(msg)),
			),
		]
		for p in self.patches:
			p.start()

	def tearDown(self):
		for p in reversed(self.patches):
			p.stop()

	def test_submit_rejects_disallowed_doctype(self):
		res = flow.submit_document("User", "Administrator")
		self.assertFalse(res["ok"])
		self.assertIn("not supported", res["message"])

	def test_submit_rejects_cancelled_doc(self):
		doc = MagicMock(docstatus=2, doctype="Sales Order", name="SO-1")
		with patch.object(flow.frappe, "get_doc", return_value=doc):
			res = flow.submit_document("Sales Order", "SO-1")
		self.assertFalse(res["ok"])
		self.assertIn("cancelled", res["message"])

	def test_submit_handles_validation_error_with_savepoint_rollback(self):
		doc = MagicMock(docstatus=0, doctype="Quotation", name="QTN-1")
		doc.submit.side_effect = frappe.ValidationError("Changed since quotation")
		with patch.object(flow.frappe, "get_doc", return_value=doc):
			res = flow.submit_document("Quotation", "QTN-1")
		self.assertFalse(res["ok"])
		self.assertIn("Changed since quotation", res["message"])
		flow.frappe.db.savepoint.assert_called_once()
		flow.frappe.db.rollback.assert_called_once()

	def test_create_next_rejects_unsupported_transition(self):
		res = flow.create_next_document("Purchase Order", "PO-1", "Delivery Note")
		self.assertFalse(res["ok"])
		self.assertIn("Cannot create Delivery Note from Purchase Order", res["message"])

	def test_create_next_requires_submitted_source(self):
		src = MagicMock(docstatus=0, doctype="Purchase Order", name="PO-1")
		with (
			patch.object(flow.frappe, "get_doc", return_value=src),
			patch.object(flow.frappe, "has_permission"),
		):
			res = flow.create_next_document("Purchase Order", "PO-1", "Purchase Receipt")
		self.assertFalse(res["ok"])
		self.assertIn("Submit Purchase Order PO-1", res["message"])
		flow.frappe.db.rollback.assert_called_once()

	def test_prepare_sales_order_sets_distributor_po_and_delivery_date(self):
		item = frappe._dict({"item_code": "FEN-W01"})
		doc = frappe._dict({"items": [item], "meta": SimpleNamespace(has_field=lambda f: f == "fen_project")})
		src = frappe._dict({"doctype": "Quotation", "name": "QTN-1", "fen_project": "FP-1"})
		flow._prepare_sales_order(doc, src, po_no=" DIST-42 ")
		self.assertEqual(doc["po_no"], "DIST-42")
		self.assertTrue(doc["delivery_date"])
		self.assertTrue(item["delivery_date"])
		self.assertEqual(doc["fen_project"], "FP-1")

	def test_ensure_payment_reference_for_bank_account(self):
		doc = frappe._dict({"paid_from_account_type": "Bank", "paid_to_account_type": "Payable"})
		flow._ensure_payment_reference(doc, "ACC-PINV-1")
		self.assertEqual(doc["reference_no"], "ACC-PINV-1")
		self.assertTrue(doc["reference_date"])

	def test_header_actions_follow_quotation_to_procurement_chain(self):
		q = {"name": "QTN-1", "docstatus": 0, "status": "Draft"}
		flow._attach_actions(
			quotation=q,
			sales_orders=[],
			material_requests=[],
			purchase_orders=[],
			purchase_receipts=[],
			purchase_invoices=[],
			delivery_notes=[],
			sales_invoices=[],
			payment_entries=[],
		)
		primary, _ = flow._build_header_actions(
			project="FP-1",
			design_count=1,
			quotation=q,
			sales_orders=[],
			material_requests=[],
			purchase_orders=[],
			purchase_receipts=[],
			purchase_invoices=[],
			delivery_notes=[],
			sales_invoices=[],
			payment_entries=[],
		)
		self.assertEqual(primary["kind"], "submit")
		self.assertEqual(primary["doctype"], "Quotation")

		q["docstatus"] = 1
		so = [{"name": "SO-1", "docstatus": 1, "per_delivered": 0, "per_billed": 0}]
		po = [
			{
				"name": "PO-1",
				"docstatus": 1,
				"per_received": 0,
				"per_billed": 0,
				"grand_total": 100,
				"advance_paid": 0,
			}
		]
		flow._attach_actions(
			quotation=q,
			sales_orders=so,
			material_requests=[],
			purchase_orders=po,
			purchase_receipts=[],
			purchase_invoices=[],
			delivery_notes=[],
			sales_invoices=[],
			payment_entries=[],
		)
		primary, opts = flow._build_header_actions(
			project="FP-1",
			design_count=1,
			quotation=q,
			sales_orders=so,
			material_requests=[],
			purchase_orders=po,
			purchase_receipts=[],
			purchase_invoices=[],
			delivery_notes=[],
			sales_invoices=[],
			payment_entries=[],
		)
		self.assertEqual(primary["kind"], "create")
		self.assertEqual(primary["target_doctype"], "Purchase Receipt")
		self.assertTrue(any(o["target_doctype"] == "Purchase Invoice" for o in opts))


if __name__ == "__main__":
	unittest.main()
