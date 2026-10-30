"""D6: batch FEN-WINDOW and restock material Items in Kg, Meter and Square Meter where nothing has moved yet."""

from onebook_fenestration.setup.install import setup_production_items


def execute():
	setup_production_items()
