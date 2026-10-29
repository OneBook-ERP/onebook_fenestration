import frappe
from frappe.tests import IntegrationTestCase

from onebook_fenestration.pricing.doctype.price_structure.price_structure import to_cost_heads
from onebook_fenestration.series_studio.snapshot import build_snapshot_dict
from onebook_fenestration.setup.install import after_migrate, seed_pricing
from onebook_fenestration.tests.test_profile_dxf import FIXTURE, make_file, profile_doc
from onebook_fenestration.tests.test_series import make_masters, make_version

STANDARD_KEYS = [
	"profile", "profile_waste", "powder", "anodize", "wood", "hardware",
	"glass", "glass_waste", "fabrication", "installation", "profit",
]  # fmt: skip


def structure(name, heads):
	return frappe.get_doc({"doctype": "Price Structure", "structure_name": name, "heads": heads})


def head(key, calc="Fixed", **kwargs):
	return {"key": key, "label": key.title(), "calc": calc, **kwargs}


class TestPricingMasters(IntegrationTestCase):
	def setUp(self):
		make_masters()

	def test_seeds_exist_after_migrate(self):
		after_migrate()
		heads = to_cost_heads("Standard")
		self.assertEqual([h.key for h in heads], STANDARD_KEYS)
		self.assertEqual(heads[1].base, "profile")
		self.assertEqual(heads[2].rate, 25.0)
		for code in ("GREY", "BROWN-5104", "MILL", "WOOD"):
			self.assertTrue(frappe.db.exists("Profile Finish", code), code)
		settings = frappe.get_single("Fenestration Settings")
		self.assertEqual(settings.default_price_structure, "Standard")
		self.assertEqual(settings.default_finish, "GREY")
		self.assertEqual(settings.billing_area_basis, "Frame size")

	def test_price_structure_validates_formulas(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			structure("TPS Bad", [head("a", "Formula", formula="nope_var + 1")]).insert()
		self.assertIn("a", str(ctx.exception))
		with self.assertRaises(frappe.ValidationError) as ctx:
			structure(
				"TPS Later",
				[head("a", "Percentage", rate=5, base="b"), head("b")],
			).insert()
		self.assertIn("Cost head a", str(ctx.exception))
		with self.assertRaises(frappe.ValidationError):
			structure("TPS Dup", [head("a"), head("a")]).insert()
		with self.assertRaises(frappe.ValidationError):
			structure("TPS NoFormula", [head("a", "Formula")]).insert()

	def test_valid_structure_and_single_default(self):
		doc = structure(
			"TPS Ok",
			[head("a", "Formula", formula="profile_cost"), head("b", "Percentage", rate=5, base="a", condition="finish_type == 'Mill'")],
		).insert()
		doc.is_default = 1
		doc.save()
		other = structure("TPS Ok2", [head("a")])
		other.is_default = 1
		other.insert()
		self.assertEqual(frappe.db.get_value("Price Structure", "TPS Ok", "is_default"), 0)

	def test_profile_snapshot_includes_perimeters(self):
		profile = frappe.get_doc("Fenestration Profile", "TP1")
		profile.visible_perimeter_mm = 123.4
		profile.save()
		profiles = build_snapshot_dict(make_version())["profiles"]
		self.assertEqual(profiles["TP1"]["visible_perimeter_mm"], 123.4)
		self.assertEqual(profiles["TP1"]["total_perimeter_mm"], 0)

	def test_dxf_sets_total_perimeter(self):
		file_doc = make_file(FIXTURE.read_bytes())
		profile = profile_doc("TPPM1", file_doc.file_url).insert()
		self.assertGreater(profile.total_perimeter_mm, 0)
		self.assertEqual(profile.total_perimeter_mm, profile.perimeter_mm)

	def test_include_in_total_maps_to_cost_heads(self):
		structure("TPS Info", [head("a"), head("sub", "Formula", formula="a", include_in_total=0)]).insert()
		heads = to_cost_heads("TPS Info")
		self.assertEqual([h.include_in_total for h in heads], [True, False])

	def test_wood_surcharge_seeded_on_insert_only(self):
		frappe.db.delete("Profile Finish", "WOOD")
		seed_pricing()
		self.assertEqual(frappe.db.get_value("Profile Finish", "WOOD", "surcharge_pct"), 12)
		self.assertEqual(frappe.db.get_value("Profile Finish", "GREY", "surcharge_pct"), 0)
		frappe.db.set_value("Profile Finish", "WOOD", "surcharge_pct", 5)
		seed_pricing()
		self.assertEqual(frappe.db.get_value("Profile Finish", "WOOD", "surcharge_pct"), 5)

	def test_cost_price_list_description(self):
		field = frappe.get_meta("Fenestration Settings").get_field("cost_price_list")
		self.assertIn("profile rate per kg, glass per m², gaskets per m, hardware per unit", field.description)
