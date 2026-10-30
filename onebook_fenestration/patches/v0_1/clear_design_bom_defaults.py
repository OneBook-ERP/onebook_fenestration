"""D6: design BOMs submitted before the guard may have become FEN-WINDOW's default BOM; take that back."""

from onebook_fenestration.production.bom import clear_design_defaults


def execute():
	clear_design_defaults()
