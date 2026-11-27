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
CUSTOM_FIELDS["Customer"] = [
	{
		"fieldname": "fen_partner_type",
		"label": "Partner Type",
		"fieldtype": "Select",
		"options": "Dealer\nFabrication Partner\nOwn Client",
		"default": "Dealer",
		"insert_after": "customer_group",
		"in_standard_filter": 1,
		"in_list_view": 1,
	},
]
CUSTOM_FIELDS["Quotation"] = [
	{
		"fieldname": "fen_project",
		"label": "Fenestration Project",
		"fieldtype": "Link",
		"options": "Fenestration Project",
		"insert_after": "customer_name",
		"read_only": 1,
	},
	{
		"fieldname": "fen_deal_name",
		"label": "Deal Name",
		"fieldtype": "Data",
		"insert_after": "fen_project",
		"read_only": 1,
	},
	{
		"fieldname": "fen_partner_type",
		"label": "Partner Type",
		"fieldtype": "Select",
		"options": "Dealer\nFabrication Partner\nOwn Client",
		"default": "Dealer",
		"insert_after": "fen_deal_name",
		"in_standard_filter": 1,
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
	{
		"fieldname": "fen_design_hash",
		"label": "Design Hash",
		"fieldtype": "Data",
		"insert_after": "fen_window_design",
		"read_only": 1,
		"hidden": 1,
	},
]
CUSTOM_FIELDS["Sales Order"] = [
	{
		"fieldname": "fen_project",
		"label": "Fenestration Project",
		"fieldtype": "Link",
		"options": "Fenestration Project",
		"insert_after": "customer_name",
		"read_only": 1,
	},
	{
		"fieldname": "fen_partner_type",
		"label": "Partner Type",
		"fieldtype": "Select",
		"options": "Dealer\nFabrication Partner\nOwn Client",
		"default": "Dealer",
		"insert_after": "fen_project",
		"in_standard_filter": 1,
	},
]
CUSTOM_FIELDS["CRM Lead"] = [
	{
		"fieldname": "priority",
		"label": "Priority",
		"fieldtype": "Select",
		"options": "\nHigh\nMedium\nLow",
		"reqd": 1,
		"in_list_view": 1,
		"in_standard_filter": 1,
		"search_index": 1,
		"insert_after": "status",
	},
	{
		"fieldname": "priority_rank",
		"label": "Priority Rank",
		"fieldtype": "Int",
		"default": "2",
		"hidden": 1,
		"read_only": 1,
		"search_index": 1,
		"insert_after": "priority",
	},
	{
		"fieldname": "fen_partner_type",
		"label": "Partner Type",
		"fieldtype": "Select",
		"options": "\nDealer\nFabrication Partner\nOwn Client",
		"insert_after": "priority_rank",
		"in_standard_filter": 1,
	},
]
CUSTOM_FIELDS["CRM Deal"] = [
	{
		"fieldname": "priority",
		"label": "Priority",
		"fieldtype": "Select",
		"options": "\nHigh\nMedium\nLow",
		"default": "Medium",
		"in_list_view": 1,
		"in_standard_filter": 1,
		"search_index": 1,
		"insert_after": "status",
	},
	{
		"fieldname": "priority_rank",
		"label": "Priority Rank",
		"fieldtype": "Int",
		"default": "2",
		"hidden": 1,
		"read_only": 1,
		"search_index": 1,
		"insert_after": "priority",
	},
	{
		"fieldname": "fen_partner_type",
		"label": "Partner Type",
		"fieldtype": "Select",
		"options": "\nDealer\nFabrication Partner\nOwn Client",
		"insert_after": "priority_rank",
		"in_standard_filter": 1,
	},
]
CUSTOM_FIELDS["CRM Task"] = [
	{
		"fieldname": "priority_rank",
		"label": "Priority Rank",
		"fieldtype": "Int",
		"default": "2",
		"hidden": 1,
		"read_only": 1,
		"search_index": 1,
		"insert_after": "priority",
	},
]
CUSTOM_FIELDS["Sales Order Item"] = [
	{
		"fieldname": "fen_window_design",
		"label": "Window Design",
		"fieldtype": "Link",
		"options": "Window Design",
		"insert_after": "item_code",
		"read_only": 1,
	},
	{
		"fieldname": "fen_design_hash",
		"label": "Design Hash",
		"fieldtype": "Data",
		"insert_after": "fen_window_design",
		"read_only": 1,
		"hidden": 1,
	},
]
CUSTOM_FIELDS["BOM"] = [
	{
		"fieldname": "fen_window_design",
		"label": "Window Design",
		"fieldtype": "Link",
		"options": "Window Design",
		"insert_after": "item",
		"read_only": 1,
	},
	{
		"fieldname": "fen_design_hash",
		"label": "Design Hash",
		"fieldtype": "Data",
		"insert_after": "fen_window_design",
		"read_only": 1,
		"hidden": 1,
	},
]
CUSTOM_FIELDS["Material Request"] = [
	{
		"fieldname": "fen_project",
		"label": "Fenestration Project",
		"fieldtype": "Link",
		"options": "Fenestration Project",
		"insert_after": "company",
		"allow_on_submit": 1,
	},
]
CUSTOM_FIELDS["Material Request Item"] = [
	{
		"fieldname": "fen_cut_length_mm",
		"label": "Cut Length (mm)",
		"fieldtype": "Float",
		"precision": "1",
		"insert_after": "qty",
	},
	{
		"fieldname": "fen_piece_count",
		"label": "Pieces",
		"fieldtype": "Int",
		"insert_after": "fen_cut_length_mm",
	},
	{
		"fieldname": "fen_spec_note",
		"label": "Cut / Size Spec",
		"fieldtype": "Data",
		"insert_after": "fen_piece_count",
	},
]
CUSTOM_FIELDS["Purchase Order"] = [
	{
		"fieldname": "fen_project",
		"label": "Fenestration Project",
		"fieldtype": "Link",
		"options": "Fenestration Project",
		"insert_after": "project",
		"allow_on_submit": 1,
	},
	{
		"fieldname": "fen_proforma_section",
		"label": "Supplier Proforma Invoice",
		"fieldtype": "Section Break",
		"insert_after": "schedule_date",
	},
	{
		"fieldname": "fen_proforma_no",
		"label": "Proforma Invoice No.",
		"fieldtype": "Data",
		"insert_after": "fen_proforma_section",
		"allow_on_submit": 1,
	},
	{
		"fieldname": "fen_proforma_date",
		"label": "Proforma Date",
		"fieldtype": "Date",
		"insert_after": "fen_proforma_no",
		"allow_on_submit": 1,
	},
	{
		"fieldname": "fen_proforma_col_break",
		"fieldtype": "Column Break",
		"insert_after": "fen_proforma_date",
	},
	{
		"fieldname": "fen_proforma_file",
		"label": "Proforma Attachment",
		"fieldtype": "Attach",
		"insert_after": "fen_proforma_col_break",
		"allow_on_submit": 1,
	},
	{
		"fieldname": "fen_proforma_confirmed",
		"label": "Proforma Confirmed",
		"fieldtype": "Check",
		"insert_after": "fen_proforma_file",
		"allow_on_submit": 1,
	},
]
CUSTOM_FIELDS["Purchase Order Item"] = [
	{
		"fieldname": "fen_cut_length_mm",
		"label": "Cut Length (mm)",
		"fieldtype": "Float",
		"precision": "1",
		"insert_after": "qty",
	},
	{
		"fieldname": "fen_piece_count",
		"label": "Pieces",
		"fieldtype": "Int",
		"insert_after": "fen_cut_length_mm",
	},
	{
		"fieldname": "fen_spec_note",
		"label": "Cut / Size Spec",
		"fieldtype": "Data",
		"insert_after": "fen_piece_count",
	},
]
