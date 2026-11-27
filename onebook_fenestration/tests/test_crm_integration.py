"""Tests for onebook_fenestration's Frappe CRM extensions (Priority, sorting, Quick Filters, Deal quotation)."""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from onebook_fenestration.crm import doc_api, lead, quotation, scripts
from onebook_fenestration.setup import crm as crm_setup


class TestCRMIntegration(FrappeTestCase):
	def test_validate_lead_priority_sets_rank_and_rejects_missing_or_invalid(self):
		with patch.object(lead.frappe.db, "has_column", return_value=True):
			doc = frappe._dict(priority="High", flags={})
			lead.validate_lead_priority(doc)
			self.assertEqual(doc.priority, "High")
			self.assertEqual(doc.priority_rank, 1)

			doc_med = frappe._dict(priority=" Medium ", flags={})
			lead.validate_lead_priority(doc_med)
			self.assertEqual(doc_med.priority, "Medium")
			self.assertEqual(doc_med.priority_rank, 2)

			doc_low = frappe._dict(priority="Low", flags={})
			lead.validate_lead_priority(doc_low)
			self.assertEqual(doc_low.priority_rank, 3)

			with self.assertRaises(frappe.MandatoryError):
				lead.validate_lead_priority(frappe._dict(priority="", flags={}))

			with self.assertRaises(frappe.ValidationError):
				lead.validate_lead_priority(frappe._dict(priority="Urgent", flags={}))

			ignored = frappe._dict(priority="", flags={"ignore_mandatory": True})
			lead.validate_lead_priority(ignored)
			self.assertEqual(ignored.priority_rank, 4)

	def test_validate_deal_and_task_priority(self):
		with patch.object(lead.frappe.db, "has_column", return_value=True):
			deal_blank = frappe._dict(priority="")
			lead.validate_deal_priority(deal_blank)
			self.assertEqual(deal_blank.priority, "Medium")
			self.assertEqual(deal_blank.priority_rank, 2)

			deal_high = frappe._dict(priority="High")
			lead.validate_deal_priority(deal_high)
			self.assertEqual(deal_high.priority_rank, 1)

			with self.assertRaises(frappe.ValidationError):
				lead.validate_deal_priority(frappe._dict(priority="Critical"))

			task_low = frappe._dict(priority="Low")
			lead.sync_task_priority_rank(task_low)
			self.assertEqual(task_low.priority_rank, 3)

			task_empty = frappe._dict(priority="")
			lead.sync_task_priority_rank(task_empty)
			self.assertEqual(task_empty.priority_rank, 4)

	def test_normalize_order_by_translates_priority_semantically_across_doctypes(self):
		with patch.object(doc_api.frappe.db, "has_column", return_value=True):
			for dt in ("CRM Lead", "CRM Deal", "CRM Task"):
				self.assertEqual(
					doc_api.normalize_order_by(dt, ""),
					"priority_rank asc, modified desc",
				)
				self.assertEqual(
					doc_api.normalize_order_by(dt, "priority desc"),
					"priority_rank desc, modified desc",
				)
				self.assertEqual(
					doc_api.normalize_order_by(dt, "`priority` asc, creation desc"),
					"priority_rank asc, creation desc, modified desc",
				)
				self.assertEqual(
					doc_api.normalize_order_by(dt, "creation desc"),
					"creation desc",
				)

			self.assertEqual(
				doc_api.normalize_order_by("CRM Organization", ""),
				"modified desc",
			)
			self.assertEqual(
				doc_api.normalize_order_by("CRM Organization", "priority asc"),
				"priority asc",
			)

	def test_resolve_partner_type_precedence(self):
		deal = frappe._dict(fen_partner_type="Fabrication Partner")
		self.assertEqual(quotation.resolve_partner_type(deal), "Fabrication Partner")
		self.assertEqual(quotation.resolve_partner_type(deal, override="Own Client"), "Own Client")
		self.assertEqual(quotation.resolve_partner_type(frappe._dict()), "Dealer")

	def test_desk_form_path_is_relative_and_host_independent(self):
		path = quotation._desk_form_path("Quotation", "SAL-QTN-2026-00008")
		self.assertTrue(path.startswith("/"))
		self.assertIn("SAL-QTN-2026-00008", path)
		self.assertNotIn("http://", path)
		self.assertNotIn("https://", path)

	def test_item_quotation_defaults_returns_empty_for_missing_item(self):
		self.assertEqual(quotation.get_item_quotation_defaults("__NON_EXISTENT_ITEM__"), {})
		self.assertIn("options: 'Quotation Item'", scripts.DEAL_QUOTATION_FORM_SCRIPT)
		self.assertIn("fieldtype: 'Table'", scripts.DEAL_QUOTATION_FORM_SCRIPT)

	def test_sync_crm_customizations_noops_safely_when_crm_not_installed(self):
		with patch.object(crm_setup.frappe.db, "exists", return_value=None):
			crm_setup.sync_crm_customizations()

	def test_live_crm_priority_views_quick_filters_and_scripts_when_crm_installed(self):
		if not frappe.db.exists("DocType", "CRM Lead"):
			self.skipTest("Frappe CRM is not installed on this site")

		from frappe.model.base_document import get_controller

		for dt in ("CRM Lead", "CRM Deal"):
			meta = frappe.get_meta(dt)
			self.assertIsNotNone(meta.get_field("priority"))
			self.assertIsNotNone(meta.get_field("priority_rank"))
			self.assertIsNotNone(meta.get_field("fen_partner_type"))

			controller = get_controller(dt)
			list_data = controller.default_list_data()
			col_keys = [c.get("key") for c in list_data.get("columns", []) if isinstance(c, dict)]
			self.assertIn("priority", col_keys)
			self.assertIn("priority", list_data.get("rows", []))

			kanban = controller.default_kanban_settings()
			kanban_fields = json.loads(kanban.get("kanban_fields") or "[]")
			self.assertIn("priority", kanban_fields)

			qf_name = frappe.db.exists("CRM Global Settings", {"dt": dt, "type": "Quick Filters"})
			if qf_name:
				qf = json.loads(frappe.db.get_value("CRM Global Settings", qf_name, "json") or "[]")
				self.assertIn("priority", qf)

		self.assertEqual(frappe.get_meta("CRM Lead").get_field("priority").reqd, 1)
		self.assertIsNotNone(frappe.get_meta("CRM Task").get_field("priority_rank"))

		for dt in ("CRM Lead", "CRM Deal", "CRM Task"):
			std_view = frappe.db.get_value(
				"CRM View Settings",
				{"dt": dt, "is_standard": 1, "type": "list"},
				["name", "order_by"],
				as_dict=True,
			)
			self.assertIsNotNone(std_view, f"Missing standard list view for {dt}")
			self.assertEqual(std_view.order_by, "priority asc")

		for script_name in (
			scripts.DEAL_QUOTATION_SCRIPT_NAME,
			scripts.LEAD_LIST_UI_SCRIPT_NAME,
			scripts.DEAL_LIST_UI_SCRIPT_NAME,
			scripts.TASK_LIST_UI_SCRIPT_NAME,
			scripts.LEAD_FORM_UI_SCRIPT_NAME,
		):
			self.assertTrue(frappe.db.exists("CRM Form Script", script_name))
			self.assertEqual(frappe.db.get_value("CRM Form Script", script_name, "enabled"), 1)

		res = doc_api.get_data("CRM Lead", filters={}, order_by="priority asc")
		ranks = [lead.PRIORITY_RANKS.get(r.get("priority"), 4) for r in res.get("data", [])]
		self.assertEqual(ranks, sorted(ranks))
