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

	def test_has_permission_returns_true_not_none_for_system_manager_and_hilux_staff(self):
		doc = frappe._dict(
			name="FP-TEST-1",
			owner="dealer@example.com",
			fen_is_dealer_private=0,
			fen_shared_with_hilux=1,
		)
		with patch.object(sharing.frappe, "get_roles", return_value=["System Manager"]):
			self.assertIs(sharing.project_has_permission(doc, ptype="write", user="admin@example.com"), True)
			self.assertIs(sharing.design_has_permission(frappe._dict(name="WD-1", owner="dealer@example.com", project="FP-TEST-1"), ptype="write", user="admin@example.com"), True)

		with patch.object(sharing.frappe, "get_roles", return_value=["Fenestration Engineer"]):
			self.assertIs(sharing.project_has_permission(doc, ptype="read", user="eng@hilux.com"), True)

	def test_docshare_permission_is_ptype_aware_and_blocks_delete(self):
		doc = frappe._dict(
			name="FP-TEST-2",
			owner="other@example.com",
			fen_is_dealer_private=1,
			fen_shared_with_hilux=0,
		)
		with (
			patch.object(sharing.frappe, "get_roles", return_value=["Fenestration Dealer"]),
			patch.object(
				sharing.frappe.db,
				"exists",
				side_effect=lambda dt, flt: dt == "DocShare" and flt.get("read") == 1,
			),
		):
			self.assertIs(sharing.project_has_permission(doc, ptype="read", user="dealer@example.com"), True)
			self.assertIs(sharing.project_has_permission(doc, ptype="write", user="dealer@example.com"), False)
			self.assertIs(sharing.project_has_permission(doc, ptype="delete", user="dealer@example.com"), False)

	def test_share_project_requires_share_permission_and_hides_staff_emails(self):
		fake_project = frappe._dict(
			name="FP-TEST-DEALER",
			fen_partner_type="Dealer",
			customer=None,
			fen_shared_with_hilux=0,
			fen_is_dealer_private=1,
			fen_manufacturing_status="Private Draft",
			flags=frappe._dict(),
			db_set=lambda *a, **kw: None,
		)

		def deny_share(dt, ptype, doc=None, throw=False):
			if ptype == "share" and throw:
				raise frappe.PermissionError
			return ptype != "share"

		with (
			patch.object(sharing.frappe, "has_permission", side_effect=deny_share),
			patch.object(sharing.frappe, "get_doc", return_value=fake_project),
		):
			with self.assertRaises(frappe.PermissionError):
				sharing.share_project_with_hilux("FP-TEST-DEALER")

		with (
			patch.object(sharing.frappe, "has_permission", return_value=True),
			patch.object(sharing.frappe, "get_doc", return_value=fake_project),
			patch.object(sharing, "now_datetime", return_value="2026-11-27 00:00:00"),
			patch.object(
				sharing.frappe,
				"get_all",
				return_value=[frappe._dict(name="WD-1", design_ref="W01", qty=1, error_count=0)],
			),
			patch.object(sharing, "_grant_hilux_docshares", return_value=["eng@hilux.com"]),
			patch.object(sharing, "_notify_hilux_team"),
		):
			result = sharing.share_project_with_hilux("FP-TEST-DEALER")
			self.assertEqual(result["shared_user_count"], 1)
			self.assertNotIn("shared_users", result)


