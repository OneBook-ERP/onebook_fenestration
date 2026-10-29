import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.setup.install import after_migrate


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
