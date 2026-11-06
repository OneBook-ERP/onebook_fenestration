"""`before_tests` hook: give an empty test site (CI) the company the tests expect.

A site that already has a company or a finished setup wizard (any dev site) is left untouched.
"""

import frappe
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
from frappe.utils import getdate

from onebook_fenestration.tests.constants import COMPANY


def before_tests():
	frappe.clear_cache()
	if frappe.db.a_row_exists("Company") or frappe.is_setup_complete():
		return
	token = frappe.generate_hash(length=10)
	today = getdate()
	year = today.year if today.month > 3 else today.year - 1
	setup_complete(
		{
			"language": "English",
			"country": "India",
			"timezone": "Asia/Kolkata",
			"currency": "INR",
			"full_name": "Test User",
			"email": f"ci-{token}@example.com",  # a new user, so no existing one is touched
			"password": frappe.generate_hash(length=32),
			"company_name": COMPANY,
			"company_abbr": "Hilux",
			"chart_of_accounts": "Standard",
			"fy_start_date": f"{year}-04-01",
			"fy_end_date": f"{year + 1}-03-31",
			"enable_audit_trail": 0,
		}
	)
	frappe.db.set_default("company", COMPANY)
	frappe.db.commit()  # nosemgrep: the hook runs outside a test transaction
