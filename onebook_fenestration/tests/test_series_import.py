import json
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

import onebook_fenestration.engine.tests as engine_tests
from onebook_fenestration.series_studio.importer import import_snapshot_json

FIXTURES = Path(engine_tests.__file__).parent / "fixtures"
DATA = Path(__file__).parent.parent / "series_studio" / "data"
# Profiles belong to one series, so fixture imports must target the series that owns them.
SERIES = "CS400"


def load_fixture(name: str) -> dict:
	return json.loads((FIXTURES / name).read_text())


def catalogue() -> list[dict]:
	return json.loads((DATA / "hilux_glasses.json").read_text())["glasses"]


def with_catalogue(data: dict) -> dict:
	"""`data` with the Hilux glass catalogue added to its glasses (fixture glasses win on a code clash)."""
	glasses = {g["code"]: {k: v for k, v in g.items() if k != "code"} for g in catalogue()}
	return {**data, "glasses": {**glasses, **data["glasses"]}}


def import_test_series(data: dict) -> str:
	version = import_snapshot_json(SERIES, data, "CS400 Economical Casement")
	frappe.cache.hdel("fen_snapshot", version)
	return version


class TestGlassCatalogueValues(IntegrationTestCase):
	def test_catalogue_spot_checks(self):
		rows = {g["code"]: g for g in catalogue()}
		for code, thickness, glass in (
			("24DGU-6C12-6C", 24, 12),
			("LAM-5C-5C-152", 11.52, 10),
			("LAM-6C-5C-152", 12.52, 11),
		):
			with self.subTest(code=code):
				self.assertEqual((rows[code]["thickness_mm"], rows[code]["glass_mm"]), (thickness, glass))

	def test_glass_thickness_fields_are_non_negative(self):
		meta = frappe.get_meta("Fenestration Glass")
		for fieldname in ("thickness_mm", "glass_mm"):
			self.assertEqual(meta.get_field(fieldname).non_negative, 1, fieldname)


class TestImportMasters(IntegrationTestCase):
	def test_import_creates_catalogue_glasses_with_items(self):
		new_codes = [g["code"] for g in catalogue() if not frappe.db.exists("Fenestration Glass", g["code"])]
		import_test_series(with_catalogue(load_fixture("cs400_snapshot.json")))
		for g in catalogue():
			self.assertTrue(frappe.db.exists("Fenestration Glass", g["code"]), g["code"])
		for code in new_codes:
			row = frappe.db.get_value(
				"Fenestration Glass", code, ["thickness_mm", "glass_mm", "item"], as_dict=True
			)
			expected = next(g for g in catalogue() if g["code"] == code)
			self.assertEqual(
				(row.thickness_mm, row.glass_mm), (expected["thickness_mm"], expected["glass_mm"]), code
			)
			self.assertEqual(row.item, f"FEN-GLASS-{code}")
			item = frappe.db.get_value("Item", row.item, ["stock_uom", "fen_item_kind"], as_dict=True)
			self.assertEqual((item.stock_uom, item.fen_item_kind), ("Square Meter", "Glass"), code)

	def test_import_never_edits_existing_glass(self):
		frappe.get_doc(
			{
				"doctype": "Fenestration Glass",
				"glass_code": "TSTGX",
				"glass_name": "Old name",
				"thickness_mm": 4,
			}
		).insert()
		data = load_fixture("cs400_snapshot.json")
		data["glasses"]["TSTGX"] = {"name": "New name", "thickness_mm": 9, "glass_mm": 9}
		import_test_series(data)
		row = frappe.db.get_value(
			"Fenestration Glass", "TSTGX", ["glass_name", "thickness_mm", "item"], as_dict=True
		)
		self.assertEqual((row.glass_name, row.thickness_mm, row.item), ("Old name", 4, None))
		self.assertFalse(frappe.db.exists("Item", "FEN-GLASS-TSTGX"))

	def test_import_creates_missing_hardware_items(self):
		data = load_fixture("cs400_snapshot.json")
		data["hardware_rules"] += [
			{
				"id": "t_hw",
				"item": "TSTHW1",
				"name": "TEST HINGE",
				"per": "sash",
				"qty": "1",
				"uom": "Pairs",
				"note": "n1",
			},
			{
				"id": "t_gk",
				"item": "TSTGK1",
				"name": "TEST GASKET",
				"per": "frame_side",
				"qty": "1",
				"length": "side_len",
				"group": "Gasket",
			},
		]
		version = import_test_series(data)
		hw = frappe.db.get_value("Item", "TSTHW1", ["stock_uom", "fen_item_kind", "item_name"], as_dict=True)
		self.assertEqual((hw.stock_uom, hw.fen_item_kind, hw.item_name), ("Pairs", "Hardware", "TEST HINGE"))
		gk = frappe.db.get_value("Item", "TSTGK1", ["stock_uom", "fen_item_kind"], as_dict=True)
		self.assertEqual((gk.stock_uom, gk.fen_item_kind), ("Meter", "Gasket"))
		notes = {r.rule_id: r.note for r in frappe.get_doc("Series Version", version).hardware_rules}
		self.assertEqual(notes["t_hw"], "n1")

	def test_import_never_edits_existing_items(self):
		item = {
			"doctype": "Item",
			"item_code": "TSTHW2",
			"item_name": "Keep me",
			"item_group": "All Item Groups",
			"stock_uom": "Nos",
		}
		if frappe.get_meta("Item").has_field("gst_hsn_code"):
			item["gst_hsn_code"] = "830241"
		frappe.get_doc(item).insert()
		data = load_fixture("cs400_snapshot.json")
		data["hardware_rules"].append(
			{"id": "t_hw2", "item": "TSTHW2", "name": "Renamed", "per": "sash", "qty": "1", "uom": "Pairs"}
		)
		import_test_series(data)
		item = frappe.db.get_value(
			"Item", "TSTHW2", ["item_name", "stock_uom", "fen_item_kind"], as_dict=True
		)
		self.assertEqual((item.item_name, item.stock_uom), ("Keep me", "Nos"))
		self.assertFalse(item.fen_item_kind)

	def test_reimport_creates_new_version(self):
		data = load_fixture("cs400_snapshot.json")
		first = import_test_series(data)

		def rows(name):
			return [
				r.as_dict(no_default_fields=True)
				for r in frappe.get_doc("Series Version", name).hardware_rules
			]

		before = rows(first)
		changed = {**data, "hardware_rules": [{**r, "qty": "99"} for r in data["hardware_rules"]]}
		second = import_test_series(changed)
		self.assertEqual(rows(first), before)
		self.assertEqual({r["qty_expr"] for r in rows(second)}, {"99"})
		self.assertNotEqual(first, second)
		self.assertEqual(frappe.db.get_value("Series Version", first, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Series Version", second, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Profile Series", SERIES, "published_version"), second)


class TestHiluxSeriesImport(IntegrationTestCase):
	def import_series(self, series: str, file: str, title: str) -> str:
		version = import_snapshot_json(series, json.loads((DATA / file).read_text()), title)
		self.addCleanup(frappe.cache.hdel, "fen_snapshot", version)
		return version

	def test_cs400_v2_imports_and_computes_w01(self):
		from onebook_fenestration.engine import compute
		from onebook_fenestration.series_studio.snapshot import get_snapshot

		version = self.import_series("CS400", "cs400_v2.json", "CS400 Economical Casement")
		self.assertIn("Hilux CS400", frappe.db.get_value("Series Version", version, "version_note"))
		result = compute(load_fixture("w01.json"), get_snapshot(version))
		self.assertEqual(result.issues, [])
		self.assertEqual(sum(b.qty for b in result.bom if b.item == "H401"), 12)
		for code in ("H407", "H417", "G22", "G29"):
			self.assertTrue(frappe.db.exists("Item", code), code)

	def test_cs4800_v1_imports_with_placeholder_profiles(self):
		from onebook_fenestration.series_studio.snapshot import get_snapshot

		data = json.loads((DATA / "cs4800_v1.json").read_text())
		version = self.import_series("CS4800", "cs4800_v1.json", "CS4800 Premium Casement")
		self.assertEqual(frappe.db.get_value("Series Version", version, "docstatus"), 1)
		snap = get_snapshot(version)
		# the snapshot reads the live profile masters of the series, which may hold more than this file
		self.assertLessEqual(set(data["profiles"]), set(snap.profiles))
		self.assertLessEqual({r.profile for r in snap.member_rules}, set(data["profiles"]))
		for code, row in data["profiles"].items():
			profile = snap.profiles[code]
			self.assertIn("PLACEHOLDER until DXF", profile.name, code)
			self.assertEqual(
				(profile.name, profile.kg_per_m, tuple(profile.bar_lengths)),
				(row["name"], row["kg_per_m"], tuple(row["bar_lengths"])),
				code,
			)
			item = frappe.db.get_value("Fenestration Profile", code, "item")
			self.assertEqual(frappe.db.get_value("Item", item, "fen_item_kind"), "Profile")
		self.assertIn("PLACEHOLDER until DXF", frappe.db.get_value("Series Version", version, "version_note"))
		door = frappe.get_all(
			"Series Hardware Rule", {"parent": version, "item": "H418"}, ["when_expr", "note"]
		)
		self.assertEqual([(d.when_expr, d.note) for d in door], [("False", "door — no door typology yet")])


class TestImportHiluxSeries(IntegrationTestCase):
	def test_second_call_creates_no_versions(self):
		from onebook_fenestration.series_studio.data import import_hilux_series

		first = import_hilux_series()
		self.addCleanup(lambda: [frappe.cache.hdel("fen_snapshot", v) for v in first.values()])
		self.assertEqual(set(first), {"CS400", "CS4800"})

		def count():
			return frappe.db.count("Series Version", {"series": ("in", ("CS400", "CS4800")), "docstatus": 1})

		before = count()
		self.assertEqual(import_hilux_series(), {})
		self.assertEqual(count(), before)
		hashes = frappe.get_all("Series Version", {"name": ("in", list(first.values()))}, pluck="source_hash")
		self.assertTrue(all(len(h) == 64 for h in hashes))

	def test_changed_data_imports_again(self):
		from onebook_fenestration.series_studio import data as hilux

		hilux.import_hilux_series()
		original = hilux.load_series_data
		self.addCleanup(setattr, hilux, "load_series_data", original)
		hilux.load_series_data = lambda f: {**original(f), "version_note": "changed"}
		self.assertEqual(set(hilux.import_hilux_series()), {"CS400", "CS4800"})


class TestMemberRuleWhen(IntegrationTestCase):
	def test_member_rule_when_imports(self):
		from onebook_fenestration.series_studio.snapshot import get_snapshot

		data = load_fixture("cs400_snapshot.json")
		data["constants"]["glass_clearance"] = 4
		data["member_rules"].append(
			{
				"id": "t_bead",
				"role": "bead",
				"profile": "E104160",
				"angles": [90, 90],
				"length": "opening_w",
				"when": "glass_t <= 8",
			}
		)
		version = import_test_series(data)
		rows = {r.rule_id: r.when_expr for r in frappe.get_doc("Series Version", version).member_rules}
		self.assertEqual((rows["t_bead"], rows["mr_frame"]), ("glass_t <= 8", None))
		rules = {r.id: r.when for r in get_snapshot(version).member_rules}
		self.assertEqual((rules["t_bead"], rules["mr_frame"]), ("glass_t <= 8", ""))


class TestProfilePerimeters(IntegrationTestCase):
	def make_profile(self, code: str, visible: float, total: float) -> None:
		frappe.get_doc(
			{
				"doctype": "Fenestration Profile",
				"profile_code": code,
				"profile_name": code,
				"series": SERIES,
				"role": "accessory",
				"kg_per_m": 1,
				"bar_lengths": "5800",
				"visible_perimeter_mm": visible,
			}
		).insert()
		# total_perimeter_mm is computed from a section DXF (cleared on save without one), so set it directly.
		frappe.db.set_value("Fenestration Profile", code, "total_perimeter_mm", total)

	def test_perimeters_fill_only_empty(self):
		from onebook_fenestration.series_studio import data as hilux

		self.make_profile("TSTPER1", 55, 300)
		self.make_profile("TSTPER2", 40, 0)
		hilux.fill_profile_perimeters(
			{
				"TSTPER1": {"perimeter_mm": 234},
				"TSTPER2": {"perimeter_mm": 139},
				"TSTNONE": {"perimeter_mm": 1},
			}
		)
		fields = ["visible_perimeter_mm", "total_perimeter_mm"]
		self.assertEqual(frappe.db.get_value("Fenestration Profile", "TSTPER1", fields), (55, 300))
		self.assertEqual(frappe.db.get_value("Fenestration Profile", "TSTPER2", fields), (40, 139))
		self.assertFalse(frappe.db.exists("Fenestration Profile", "TSTNONE"))

	def test_perimeters_are_not_series_data(self):
		from onebook_fenestration.series_studio import data as hilux

		for _, filename, _ in hilux.HILUX_SERIES:
			self.assertNotIn("perimeter_mm", json.dumps(hilux.load_series_data(filename)), filename)


class TestCs4800V2Import(IntegrationTestCase):
	def test_cs4800_v2_imports_and_computes_123(self):
		from onebook_fenestration.engine import compute
		from onebook_fenestration.series_studio import data as hilux
		from onebook_fenestration.series_studio.snapshot import get_snapshot

		self.assertIn(("CS4800", "cs4800_v2.json", "CS4800 Premium Casement"), hilux.HILUX_SERIES)
		self.assertNotIn("cs4800_v1.json", [f for _, f, _ in hilux.HILUX_SERIES])
		import_snapshot_json("CS400", hilux.load_series_data("cs400_v2.json"), "CS400 Economical Casement")
		version = import_snapshot_json(
			"CS4800", hilux.load_series_data("cs4800_v2.json"), "CS4800 Premium Casement"
		)
		self.addCleanup(frappe.cache.hdel, "fen_snapshot", version)
		result = compute(load_fixture("d123.json"), get_snapshot(version))
		cuts = {(m.profile, m.role) for m in result.members}
		self.assertEqual(
			cuts,
			{
				("CS4801", "frame"),
				("CS4802", "mullion"),
				("CS4803", "sash"),
				("CS4808", "bead"),
				("HSL3410", "glass_adaptor"),
			},
		)
		self.assertAlmostEqual(result.window_kg, 66.829, delta=0.005)
		self.assertEqual(frappe.db.get_value("Fenestration Profile", "HSL3410", "role"), "bead")
		six = load_fixture("d123.json")
		for child in six["root"]["children"]:
			child["glass"] = "6CTG"
		self.assertIn("CS4807", {m.profile for m in compute(six, get_snapshot(version)).members})
