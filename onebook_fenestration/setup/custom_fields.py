CUSTOM_FIELDS = {
	"Item": [
		{
			"fieldname": "fen_item_kind",
			"label": "Fenestration Kind",
			"fieldtype": "Select",
			"options": "\nProfile\nHardware\nGlass\nGasket\nConsumable",
			"insert_after": "item_group",
			"in_standard_filter": 1,
		},
	],
}
CUSTOM_FIELDS["Quotation"] = [
	{
		"fieldname": "fen_project",
		"label": "Fenestration Project",
		"fieldtype": "Link",
		"options": "Fenestration Project",
		"insert_after": "customer_name",
		"read_only": 1,
	},
]
CUSTOM_FIELDS["Quotation Item"] = [
	{
		"fieldname": "fen_window_design",
		"label": "Window Design",
		"fieldtype": "Link",
		"options": "Window Design",
		"insert_after": "item_code",
		"read_only": 1,
	},
]
