"""Gasket rules for series versions published before gaskets became series hardware rules.

Published versions are frozen, so their stored snapshot has no Gasket-group rule. The snapshot loader prepends these
(identical to the old hard-coded engine behaviour: every pane side, any glass) so old versions keep computing the same BOM.
"""

LEGACY_GASKET_RULES = (
	{
		"id": "legacy_gasket_frame",
		"item": "G21",
		"name": "FRAME GASKET CASEMENT",
		"per": "frame_side",
		"qty": "1",
		"length": "side_len",
		"group": "Gasket",
		"note": "LEGACY: injected at load, this version was published before gaskets were series rules",
	},
	{
		"id": "legacy_gasket_glazing",
		"item": "G23",
		"name": "GASKET 3MM",
		"per": "pane_side",
		"qty": "1",
		"length": "side_len - 2*glazing_gasket",
		"group": "Gasket",
		"note": "LEGACY: injected at load, this version was published before gaskets were series rules",
	},
)
GASKETS = {rule["item"]: rule["name"] for rule in LEGACY_GASKET_RULES}


def with_legacy_gaskets(data: dict) -> dict:
	"""`data` unchanged when it has any Gasket-group rule, else a copy with the legacy gasket rules first."""
	rules = data["hardware_rules"]
	if any(rule.get("group") == "Gasket" for rule in rules):
		return data
	return {**data, "hardware_rules": [*LEGACY_GASKET_RULES, *rules]}
