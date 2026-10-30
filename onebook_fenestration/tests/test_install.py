from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.setup.install import after_install, after_migrate


class TestInstall(IntegrationTestCase):
	def test_item_kind_custom_field(self):
		self.assertTrue(frappe.get_meta("Item").has_field("fen_item_kind"))

	def test_engineer_role(self):
		self.assertTrue(frappe.db.exists("Role", "Fenestration Engineer"))

	def test_after_migrate_is_idempotent(self):
		after_migrate()
		after_migrate()
		self.assertEqual(
			frappe.db.count("Custom Field", {"dt": "Item", "fieldname": "fen_item_kind"}), 1
		)

	def test_after_migrate_keeps_admin_production_choices(self):
		frappe.db.savepoint("fen_admin_choices")
		self.addCleanup(frappe.db.rollback, save_point="fen_admin_choices")
		frappe.db.set_single_value("Manufacturing Settings", "make_serial_no_batch_from_work_order", 0)
		frappe.db.set_value("Item", "FEN-WINDOW", "create_new_batch", 0)
		after_migrate()
		self.assertEqual(
			frappe.db.get_single_value("Manufacturing Settings", "make_serial_no_batch_from_work_order"), 0
		)
		self.assertEqual(frappe.db.get_value("Item", "FEN-WINDOW", "create_new_batch"), 0)

	def test_after_migrate_creates_missing_production_uoms(self):
		frappe.db.savepoint("fen_uoms")
		self.addCleanup(frappe.db.rollback, save_point="fen_uoms")
		with patch("onebook_fenestration.setup.install.PRODUCTION_UOMS", ("Fen Test UOM",)):
			after_migrate()
		self.assertTrue(frappe.db.exists("UOM", "Fen Test UOM"))

	def test_after_install_runs_production_setup(self):
		with patch("onebook_fenestration.setup.install.setup_production_items") as setup:
			after_install()
		setup.assert_called_once_with()
