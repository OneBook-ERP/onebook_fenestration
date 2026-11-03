"""Hilux CS400 v2 / CS4800 v1 series data against the Hilux hardware sheets and the EvA W01 golden."""

import json
import re
import unittest
from pathlib import Path

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.tests.helpers import load
from onebook_fenestration.engine.types import SeriesSnapshot

APP = Path(__file__).resolve().parents[2]
DATA = APP / "series_studio" / "data"
QUESTIONS = APP.parent / "doc" / "hilux-questions.md"
FILES = {"CS400": "cs400_v2.json", "CS4800": "cs4800_v1.json"}
TYPOLOGIES = ("fixed", "fixed_mullion", "single", "double", "triple")

# Hardware and gasket codes from the Hilux sheets, typed in from the sheets (glass rows are the glass catalogue).
SHEET_CODES = {
	"CS400": {
		"H401", "H266", "H407", "H408", "H411", "H412", "H413", "H416", "H417", "H422A", "H422B", "H422C", "H423", "H425",
		"H426", "H428", "H429", "G21", "G22", "G23", "G24", "G25", "G27", "G29", "H901", "H902", "H903", "H904", "H905",
		"H906", "H910", "H911", "H912", "H913", "H914", "H915",
	},
	"CS4800": {
		"H401", "H402", "H403", "H404", "H405", "H266", "H407", "H409", "H410", "H411", "H412", "H413", "H414", "H415",
		"H416", "H417", "H418", "H419", "H420", "H421", "H422A", "H422B", "H422C", "H423", "H424", "H425", "H426", "H427",
		"H428", "H429", "G21", "G22", "G23", "G24", "G25", "G27", "G29", "H901", "H902", "H903", "H904", "H905", "H906",
		"H910", "H911", "H912", "H913", "H914", "H915",
	},
}
DOOR_CODES = {"H402", "H415", "H418", "H419", "H420", "H421", "H424"}

# Sheet counts for Fixed / Fixed with mullion / Single / Double / Triple open (blank = 0), typed in from the sheets.
# CS4800 H402 (door frame and door shutter corners) also has counts; door rows never fire, so they are left out.
SHEET_COUNTS = {
	"CS400": {
		"H266": (4, 4, 8, 12, 16),
		"H407": (4, 4, 4, 4, 4),
		"H408": (0, 0, 4, 8, 12),
		"H411": (0, 0, 1, 2, 3),
		"H412": (0, 4, 4, 8, 12),
		"H913": (3, 3, 4, 4, 4),
		"H914": (1, 1, 1, 1, 1),
	},
	"CS4800": {
		"H401": (4, 4, 4, 4, 4),
		"H403": (0, 0, 4, 8, 12),
		"H404": (0, 0, 4, 8, 12),
		"H405": (4, 4, 4, 4, 4),
		"H266": (4, 4, 8, 12, 16),
		"H407": (4, 4, 4, 4, 4),
		"H409": (0, 0, 4, 8, 12),
		"H410": (0, 2, 2, 4, 8),
		"H411": (0, 0, 1, 2, 3),
		"H412": (0, 4, 4, 8, 12),
		"H913": (3, 3, 4, 4, 4),
		"H914": (1, 1, 1, 1, 1),
	},
}
# Cells where no consistent rule reproduces the sheet: (series, item, typology) -> what the rule gives. See rule notes.
SHEET_DEVIATIONS = {("CS4800", "H410", "triple"): 6}

# EvA W01 golden totals (test_hardware.test_w01_hardware_totals / test_w01_consumables on the v1 fixture).
EVA_W01 = {
	"H401": 12, "H266": 12, "H912": 10, "H913": 2, "H904": 10, "H903": 10, "H902": 6, "H901": 6, "H911": 10, "H412": 4,
	"H411": 2, "H416": 2, "H429": 12, "H425": 2, "H422C": 2, "H423": 4, "H905": 16, "H914": 1.423,
}
# Where the Hilux sheet changes an EvA golden quantity: item -> CS400 v2 total. Reported, not resolved here.
EVA_CONFLICTS = {"H412": 8, "H913": 3, "H425": 4, "H429": 24, "H914": 1}


def series_data(series: str) -> dict:
	return json.loads((DATA / FILES[series]).read_text())


def series_snapshot(series: str) -> SeriesSnapshot:
	return SeriesSnapshot.from_dict(series_data(series))


def reference_design(typology: str, size: float = 1200, **sash_options) -> dict:
	sash = {"type": "sash", "opening": "out", "hinge": "left", "glass": "6CTG", **sash_options}
	fixed = {"type": "fixed", "glass": "6CTG"}
	leaves = {
		"fixed": [fixed],
		"fixed_mullion": [fixed, fixed],
		"single": [sash],
		"double": [sash, sash],
		"triple": [sash, sash, sash],
	}[typology]
	if len(leaves) == 1:
		root = leaves[0]
	else:
		step = size / len(leaves)
		root = {"type": "split", "dir": "v", "at": [step * i for i in range(1, len(leaves))], "children": leaves}
	return {"width": size, "height": size, "root": root}


def totals(bom) -> dict[str, float]:
	t: dict[str, float] = {}
	for line in bom:
		t[line.item] = round(t.get(line.item, 0) + line.qty, 3)
	return t


class TestSeriesData(unittest.TestCase):
	def test_snapshots_are_complete(self):
		for series in FILES:
			with self.subTest(series=series):
				snap = series_snapshot(series)
				snap.check()
				self.assertEqual(snap.code, series)

	def test_every_sheet_row_has_a_rule(self):
		for series, codes in SHEET_CODES.items():
			with self.subTest(series=series):
				self.assertEqual({r.item for r in series_snapshot(series).hardware_rules}, codes)

	def test_glasses_are_the_hilux_catalogue(self):
		catalogue = json.loads((DATA / "hilux_glasses.json").read_text())["glasses"]
		for series in FILES:
			with self.subTest(series=series):
				self.assertEqual(
					{code: (g.name, g.thickness_mm, g.glass_mm) for code, g in series_snapshot(series).glasses.items()},
					{g["code"]: (g["name"], g["thickness_mm"], g["glass_mm"]) for g in catalogue},
				)

	def test_rules_carry_no_prices(self):
		for series in FILES:
			text = (DATA / FILES[series]).read_text().lower()
			for word in ("price", "rate", "cost", "₹", "inr"):
				self.assertNotIn(f'"{word}', text, (series, word))

	def test_typology_counts_match_sheet(self):
		for series, rows in SHEET_COUNTS.items():
			snap = series_snapshot(series)
			for i, typology in enumerate(TYPOLOGIES):
				result = compute(reference_design(typology), snap)
				self.assertEqual([x for x in result.issues if x.severity == "error"], [], (series, typology))
				got = totals(result.bom)
				for item, counts in rows.items():
					expected = SHEET_DEVIATIONS.get((series, item, typology), counts[i])
					with self.subTest(series=series, item=item, typology=typology):
						self.assertEqual(got.get(item, 0), expected)

	def test_door_rows_never_fire(self):
		snap = series_snapshot("CS4800")
		door = [r for r in snap.hardware_rules if r.item in DOOR_CODES]
		self.assertEqual({r.item for r in door}, DOOR_CODES)
		for rule in door:
			self.assertEqual((rule.when, rule.note), ("False", "door — no door typology yet"), rule.id)
		for typology in TYPOLOGIES:
			self.assertFalse(DOOR_CODES & {b.item for b in compute(reference_design(typology), snap).bom}, typology)

	def test_cs4800_structure_is_placeholder(self):
		data = series_data("CS4800")
		for code, profile in data["profiles"].items():
			self.assertIn("PLACEHOLDER until DXF", profile["name"], code)
		for rule in data["member_rules"]:
			self.assertIn("PLACEHOLDER until DXF", rule["note"], rule["id"])
		self.assertEqual(set(data["placeholders"]), {"deductions", "profiles", "member_rules"})
		self.assertIn("PLACEHOLDER until DXF", data["version_note"])

	def test_cs400_structure_is_the_v1_fixture(self):
		data, fixture = series_data("CS400"), load("cs400_snapshot.json")
		for section in ("deductions", "profiles", "member_rules", "validation_rules"):
			self.assertEqual(data[section], fixture[section], section)

	def test_every_assumption_is_a_question(self):
		questions = QUESTIONS.read_text()
		for series in FILES:
			for rule in series_snapshot(series).hardware_rules:
				if re.search(r"ASSUMPTION|CONFLICT|CHECK", rule.note):
					with self.subTest(series=series, rule=rule.id):
						self.assertIn(f"`{rule.id}`", questions)


class TestSashOptionSwaps(unittest.TestCase):
	def items(self, series, **options):
		return totals(compute(reference_design("single", **options), series_snapshot(series)).bom)

	def test_butt_hinge_replaces_friction_hinge_and_screws(self):
		t = self.items("CS400", hinge_type="butt")
		self.assertEqual((t.get("H413"), t.get("H416"), t.get("H417"), t.get("H429")), (2, None, None, None))

	def test_friction_hinge_size_by_sash_width(self):
		self.assertEqual(self.items("CS400").get("H417"), 1)
		self.assertEqual(totals(compute(reference_design("double"), series_snapshot("CS400")).bom).get("H416"), 2)

	def test_single_point_handle_replaces_multipoint_set(self):
		t = self.items("CS400", handle="single")
		self.assertEqual(t.get("H428"), 1)
		self.assertFalse({"H425", "H422A", "H422B", "H422C", "H423"} & t.keys())

	def test_rod_by_sash_height(self):
		snap = series_snapshot("CS400")
		for height, rod in ((700, "H422A"), (900, "H422B"), (1200, "H422C")):
			design = {"width": 600, "height": height, "root": {"type": "sash", "glass": "6CTG"}}
			rods = {k for k in totals(compute(design, snap).bom) if k.startswith("H422")}
			self.assertEqual(rods, {rod}, height)

	def test_limiter_and_mesh_options(self):
		self.assertNotIn("H426", self.items("CS400"))
		self.assertEqual(self.items("CS400", limiter=True).get("H426"), 1)
		mesh = self.items("CS4800")
		self.assertEqual((mesh.get("H427"), mesh.get("H404"), mesh.get("G27")), (2, 4, 1))
		self.assertFalse({"H427", "H404", "G27"} & self.items("CS4800", mesh=False).keys())


class TestW01OnCs400V2(unittest.TestCase):
	def setUp(self):
		self.result = compute(load("w01.json"), series_snapshot("CS400"))
		self.totals = totals(self.result.bom)

	def test_w01_golden_on_cs400_v2(self):
		agreed = {k: v for k, v in EVA_W01.items() if k not in EVA_CONFLICTS}
		self.assertEqual({k: self.totals.get(k) for k in agreed}, agreed)
		self.assertEqual(next(b.length for b in self.result.bom if b.item == "H915"), 8.54)
		self.assertEqual(self.result.issues, [])

	def test_w01_gaskets_unchanged(self):
		fixture = SeriesSnapshot.from_dict(load("cs400_snapshot.json"))
		lines = lambda r: [(b.item, b.panel, b.position, b.length) for b in r.bom if b.group == "Gasket"]
		self.assertEqual(lines(self.result), lines(compute(load("w01.json"), fixture)))

	def test_eva_conflicts_are_the_hilux_values(self):
		"""Documents each Hilux-vs-EvA difference on W01 until Hilux answers (doc/hilux-questions.md)."""
		self.assertEqual({k: self.totals.get(k) for k in EVA_CONFLICTS}, EVA_CONFLICTS)
		for item in EVA_CONFLICTS:
			notes = " ".join(r.note for r in series_snapshot("CS400").hardware_rules if r.item == item)
			self.assertIn("CONFLICT", notes, item)
