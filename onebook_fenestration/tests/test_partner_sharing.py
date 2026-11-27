"""Tests for Dealer vs Fabrication Partner workflows and Dealer-to-Hilux project sharing."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from onebook_fenestration.fenestration import flow, sharing


class TestPartnerSharing(FrappeTestCase):
	def test_fabrication_partner_stages_omit_hilux_manufacturing_procurement(self):
		stages = flow._build_stages(
			quotation=None,
			sales_orders=[],
			material_requests=[],
			purchase_orders=[],
			purchase_receipts=[],
			purchase_invoices=[],
			delivery_notes=[],
			sales_invoices=[],
			payment_entries=[],
			partner_type="Fabrication Partner",
		)
		ids = [s["id"] for s in stages]
		self.assertEqual(ids, ["quote", "order", "install", "payment"])
		self.assertNotIn("po", ids)
		self.assertNotIn("receipt", ids)

	def test_dealer_stages_include_full_turnkey_manufacturing_pipeline(self):
		stages = flow._build_stages(
			quotation=None,
			sales_orders=[],
			material_requests=[],
			purchase_orders=[],
			purchase_receipts=[],
			purchase_invoices=[],
			delivery_notes=[],
			sales_invoices=[],
			payment_entries=[],
			partner_type="Dealer",
		)
		ids = [s["id"] for s in stages]
		self.assertEqual(ids, ["quote", "order", "po", "receipt", "payment", "install"])

	def test_own_client_stages_include_full_supply_and_install_pipeline(self):
		stages = flow._build_stages(
			quotation=None,
			sales_orders=[],
			material_requests=[],
			purchase_orders=[],
			purchase_receipts=[],
			purchase_invoices=[],
			delivery_notes=[],
			sales_invoices=[],
			payment_entries=[],
			partner_type="Own Client",
		)
		ids = [s["id"] for s in stages]
		self.assertEqual(ids, ["quote", "order", "po", "receipt", "payment", "install"])

	def test_resolve_project_partner_type_recognizes_own_client(self):
		proj = frappe._dict(fen_partner_type="Own Client", customer=None)
		self.assertEqual(sharing.resolve_project_partner_type(proj), "Own Client")

	def test_own_client_cannot_share_project_as_dealer_handover(self):
		fake_project = frappe._dict(
			name="FP-TEST-OWN",
			fen_partner_type="Own Client",
			customer=None,
		)
		with (
			patch.object(sharing.frappe, "has_permission", return_value=True),
			patch.object(sharing.frappe, "get_doc", return_value=fake_project),
		):
			with self.assertRaises(frappe.ValidationError):
				sharing.share_project_with_hilux("FP-TEST-OWN")

	def test_fabrication_partner_cannot_share_project_for_hilux_manufacturing(self):
		fake_project = frappe._dict(
			name="FP-TEST-FAB",
			fen_partner_type="Fabrication Partner",
			customer=None,
		)
		with (
			patch.object(sharing.frappe, "has_permission", return_value=True),
			patch.object(sharing.frappe, "get_doc", return_value=fake_project),
		):
			with self.assertRaises(frappe.ValidationError):
				sharing.share_project_with_hilux("FP-TEST-FAB")

	def test_dealer_permission_query_scopes_private_drafts(self):
		with (
			patch.object(sharing.frappe, "get_roles", return_value=["Fenestration Dealer"]),
		):
			cond = sharing.project_permission_query("dealer@example.com")
			self.assertIn("`tabFenestration Project`.owner = 'dealer@example.com'", cond)

		with (
			patch.object(sharing.frappe, "get_roles", return_value=["Fenestration Engineer"]),
		):
			cond = sharing.project_permission_query("eng@hilux.com")
			self.assertIn("fen_is_dealer_private", cond)
			self.assertIn("fen_shared_with_hilux", cond)

