"""D6: batch FEN-WINDOW, let Work Orders make batches and restock material Items in Kg, Meter and Square Meter
where nothing has moved yet. The one migration path for existing sites; new sites get it from after_install."""

from onebook_fenestration.setup.install import setup_production_items


def execute():
	setup_production_items()
