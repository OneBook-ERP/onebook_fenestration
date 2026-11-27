"""Arrange the warehouse hierarchy, tag profile/glass item kinds, seed missing Item Prices, and reprice designs."""

from onebook_fenestration.setup.procurement import setup_procurement


def execute():
	setup_procurement()

