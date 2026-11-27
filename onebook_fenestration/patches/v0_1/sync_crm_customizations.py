"""Migrate CRM Lead priority, layouts, standard views, and Deal quotation scripts into onebook_fenestration."""

from onebook_fenestration.setup.crm import sync_crm_customizations


def execute():
	sync_crm_customizations()
