import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from onebook_fenestration.setup.custom_fields import CUSTOM_FIELDS

ENGINEER_ROLE = "Fenestration Engineer"


def after_install():
	_sync()


def after_migrate():
	_sync()


def before_uninstall():
	for custom_field in frappe.get_all(
		"Custom Field",
		filters={"dt": ("in", list(CUSTOM_FIELDS)), "fieldname": ("like", "fen\\_%")},
		pluck="name",
	):
		frappe.delete_doc("Custom Field", custom_field, force=True)


def _sync():
	create_custom_fields(CUSTOM_FIELDS, update=True)
	_ensure_engineer_role()
	seed_pricing()
	seed_quote_masters()
	setup_production_items()


def _ensure_engineer_role():
	if frappe.db.exists("Role", ENGINEER_ROLE):
		return
	frappe.get_doc({"doctype": "Role", "role_name": ENGINEER_ROLE, "desk_access": 1}).insert(
		ignore_permissions=True
	)


STANDARD_HEADS = (
	("profile", "Profile Cost", "Formula", 0, "profile_cost", "", ""),
	("profile_waste", "Profile Wastage", "Percentage", 5, "", "profile", ""),
	("powder", "Powder Coating", "Per Visible Perimeter Sqft", 25, "", "", "finish_type == 'Powder Coat'"),
	("anodize", "Anodizing", "Per Total Perimeter Sqft", 40, "", "", "finish_type == 'Anodized'"),
	("wood", "Wood Finish", "Per Visible Perimeter Sqft", 70, "", "", "finish_type == 'Wood'"),
	("hardware", "Hardware Cost", "Formula", 0, "hardware_cost + gasket_cost", "", ""),
	("glass", "Glass Cost", "Formula", 0, "glass_cost", "", ""),
	("glass_waste", "Glass Wastage", "Percentage", 1, "", "glass", ""),
	("fabrication", "Fabrication Labour", "Per Area Sqft", 100, "", "", ""),
	("installation", "Installation Labour", "Per Area Sqft", 80, "", "", ""),
	(
		"profit",
		"Profit",
		"Percentage",
		20,
		"",
		"profile,profile_waste,powder,anodize,wood,hardware,glass,glass_waste,fabrication,installation",
		"",
	),
)
STANDARD_FINISHES = (
	("GREY", "Grey", "Powder Coat", "#8A8F98", 0),
	("BROWN-5104", "5104 PC Brown", "Powder Coat", "#6B3E26", 0),
	("MILL", "Mill Finish", "Mill", "#B8BCC2", 0),
	("WOOD", "Wooden Finish", "Wood", "#8B5A2B", 12),
)


def seed_pricing():
	"""Create the Standard price structure, finishes and Settings defaults; never overwrites existing data."""
	for code, name, finish_type, color, surcharge_pct in STANDARD_FINISHES:
		if not frappe.db.exists("Profile Finish", code):
			frappe.get_doc(
				{
					"doctype": "Profile Finish",
					"finish_code": code,
					"finish_name": name,
					"finish_type": finish_type,
					"color": color,
					"surcharge_pct": surcharge_pct,
				}
			).insert(ignore_permissions=True)
	if not frappe.db.exists("Price Structure", "Standard"):
		frappe.get_doc(
			{
				"doctype": "Price Structure",
				"structure_name": "Standard",
				"is_default": 1,
				"heads": [
					dict(
						zip(
							("key", "label", "calc", "rate", "formula", "base", "condition"),
							head,
							strict=True,
						)
					)
					for head in STANDARD_HEADS
				],
			}
		).insert(ignore_permissions=True)
	_seed_settings()


def _seed_settings():
	settings = frappe.get_single("Fenestration Settings")
	defaults = {
		"default_price_structure": "Standard",
		"default_finish": "GREY",
		"billing_area_basis": "Frame size",
		"cost_price_list": "Standard Selling" if frappe.db.exists("Price List", "Standard Selling") else None,
	}
	changed = False
	for fieldname, value in defaults.items():
		if value and not settings.get(fieldname):
			settings.set(fieldname, value)
			changed = True
	if changed:
		settings.save(ignore_permissions=True)


QUOTE_ITEMS = (
	("FEN-WINDOW", "Window (custom fabricated)", "761010", "Aluminium windows, doors and their frames"),
	("FEN-TRANSPORT", "Transportation", "996511", "Road transport services of goods"),
)
STANDARD_TERMS = "Hilux Standard Terms"
STANDARD_TERMS_LINES = (
	"Payment: 90% advance along with the work order; the balance 10% before dispatch.",
	"This quotation is valid for 10 days from its date.",
	"Delivery within 60 days of receiving the advance and the confirmed colour and window types.",
	"The advance cannot be refunded once production has started.",
	"Prices are not reduced when finished site sizes turn out smaller than quoted.",
	"A size change of more than 25 mm either way, or any change to opening type, colour, glass, quantity or"
	" hardware, is treated as a new order and priced again.",
	"Materials: 6063-T6 aluminium; Saint-Gobain, AIS or Guardian glass; SS304 mesh; Jotun, AkzoNobel or Pulver"
	" powder coating.",
	"Profiles, hardware and coating carry a 10-year warranty, excluding misuse, accidents, structural movement"
	" and glass breakage.",
	"Finish surcharge over the quoted price: Matt 0%, Texture 2%, Wooden 12%.",
	"The client keeps the site ready and the openings finished; final sizes are measured on site before production.",
	"Installation covers fixing the windows only; civil, electrical and finishing work is outside our scope.",
	"Scaffolding, where needed, is provided by the client.",
	"Delays caused by site conditions are not our responsibility.",
	"The client provides site access, power and water during installation.",
	"The client provides safe, dry storage for delivered material.",
	"Breakage or damage after delivery to site is at the client's risk.",
	"Neither party is liable for delays caused by events beyond its reasonable control.",
	"Prices are final once the order is confirmed and are not open to further negotiation.",
	"Any dispute is subject to the jurisdiction of courts in Karur, Tamil Nadu.",
	"Prices may be revised if raw material costs rise sharply before production starts.",
	"Quoted prices include material, fabrication and installation labour; GST is extra as shown.",
)


def seed_quote_masters():
	"""Generic quote items with their HSN codes and the standard terms; never overwrites existing records."""
	has_hsn = frappe.db.exists("DocType", "GST HSN Code") and frappe.get_meta("Item").has_field(
		"gst_hsn_code"
	)
	for code, item_name, hsn, hsn_description in QUOTE_ITEMS:
		if has_hsn and not frappe.db.exists("GST HSN Code", hsn):
			frappe.get_doc(
				{"doctype": "GST HSN Code", "hsn_code": hsn, "description": hsn_description}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Item", code):
			item = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": item_name,
					"item_group": _quote_item_group(),
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"is_sales_item": 1,
				}
			)
			if has_hsn:
				item.gst_hsn_code = hsn
			item.insert(ignore_permissions=True)
	_seed_terms()


def _quote_item_group() -> str:
	if not frappe.db.exists("Item Group", "Fenestration"):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "Fenestration",
				"parent_item_group": "All Item Groups",
			}
		).insert(ignore_permissions=True)
	return "Fenestration"


def _seed_terms():
	if frappe.db.exists("Terms and Conditions", STANDARD_TERMS):
		return
	items = "".join(f"<li>{line}</li>" for line in STANDARD_TERMS_LINES)
	frappe.get_doc(
		{
			"doctype": "Terms and Conditions",
			"title": STANDARD_TERMS,
			"selling": 1,
			"terms": f"<ol>{items}</ol>",
		}
	).insert(ignore_permissions=True)


PRODUCTION_UOMS = ("Kg", "Meter", "Square Meter")


def setup_production_items():
	"""D6 item setup: FEN-WINDOW batched, and material Items stocked in the units the BOM uses. Idempotent."""
	for uom in PRODUCTION_UOMS:
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)
	_batch_window_item()
	for item in _items_to_restock():
		if frappe.db.exists("Item", item[0]) and _is_unused(item[0]):
			_restock(*item)


def _batch_window_item():
	if not frappe.db.exists("Item", "FEN-WINDOW"):
		return
	if frappe.db.exists("Stock Ledger Entry", {"item_code": "FEN-WINDOW"}):
		frappe.log_error("FEN-WINDOW has stock; left as is", "Fenestration production setup")
		return
	frappe.db.set_value(
		"Item",
		"FEN-WINDOW",
		{"is_stock_item": 1, "has_batch_no": 1, "create_new_batch": 1, "include_item_in_manufacturing": 0},
	)


def _items_to_restock() -> list[tuple[str, str]]:
	"""(item, uom) for profile, gasket and glass Items not yet stocked in the BOM unit (stock UOM and UOM row)."""
	wanted = {"Profile": "Kg", "Gasket": "Meter"}
	pairs = [
		(name, wanted[kind])
		for name, kind in frappe.get_all(
			"Item", {"fen_item_kind": ("in", tuple(wanted))}, ["name", "fen_item_kind"], as_list=True
		)
	]
	glass = frappe.get_all("Fenestration Glass", {"item": ("is", "set")}, pluck="item")
	pairs += [(name, "Square Meter") for name in glass if frappe.db.exists("Item", name)]
	return [(name, uom) for name, uom in pairs if not _stocked_in(name, uom)]


def _stocked_in(item_code: str, uom: str) -> bool:
	return frappe.db.get_value("Item", item_code, "stock_uom") == uom and bool(
		frappe.db.exists("UOM Conversion Detail", {"parenttype": "Item", "parent": item_code, "uom": uom})
	)


def _is_unused(item_code: str) -> bool:
	return not (
		frappe.db.exists("Stock Ledger Entry", {"item_code": item_code})
		or frappe.db.exists("BOM Item", {"item_code": item_code})
	)


def _restock(item_code: str, uom: str) -> None:
	"""Change the stock UOM; the old UOM row stays so Item Prices already saved in it remain valid."""
	item = frappe.get_doc("Item", item_code)
	item.stock_uom = uom
	if not any(row.uom == uom for row in item.uoms):
		item.append("uoms", {"uom": uom, "conversion_factor": 1})
	item.save(ignore_permissions=True)
