"""Tests for Series Auto Section Configuration: normalization, auto bead/gasket selection, and section placement."""

import json
import pathlib
import unittest

from onebook_fenestration.engine import SeriesSnapshot, compute, cross_section
from onebook_fenestration.engine.section_config import (
	PRESET_KEYS,
	TEMPLATE_KEYS,
	detect_design_context,
	match_bead_gasket_rule,
	match_global_glazing_rule,
	normalize_global_glazing_rules,
	normalize_section_config,
	resolve_template_glass_domain,
	resolve_template_placement,
)

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "cs400_snapshot.json"


def _load_snapshot(section_config: dict | None = None) -> SeriesSnapshot:
	data = json.loads(FIXTURE.read_text())
	if section_config is not None:
		data["section_config"] = section_config
	return SeriesSnapshot.from_dict(data)


class TestSectionConfig(unittest.TestCase):
	def test_normalize_creates_all_six_presets(self):
		cfg = normalize_section_config("")
		self.assertEqual(cfg["version"], 1)
		self.assertEqual(set(cfg["presets"].keys()), set(PRESET_KEYS))
		for key in PRESET_KEYS:
			p = cfg["presets"][key]
			self.assertIn("frame", p)
			self.assertIn("sash", p)
			self.assertIsInstance(p["bead_gasket_rules"], list)

	def test_detect_design_context_for_fixed_openable_sliding_and_door(self):
		self.assertEqual(detect_design_context({"width": 1200, "height": 1200}, {"type": "fixed"}), ("fixed", "window"))
		self.assertEqual(detect_design_context({"width": 1200, "height": 1200}, {"type": "sash"}, is_sash_pane=True), ("openable", "window"))
		self.assertEqual(
			detect_design_context({"width": 1200, "height": 2100, "frameConfig": "3-side-threshold"}, {"type": "sash", "sashConfig": "door"}, is_sash_pane=True),
			("openable", "door"),
		)
		self.assertEqual(detect_design_context({"width": 1800, "height": 1500, "isSliding": True}, {"type": "fixed"}), ("sliding", "window"))

	def test_match_bead_gasket_rule_by_glass_thickness_and_host(self):
		cfg = normalize_section_config(
			{
				"presets": {
					"fixed:window": {
						"bead_gasket_rules": [
							{
								"id": "thin",
								"min_glass_mm": 5,
								"max_glass_mm": 8.5,
								"host": "frame",
								"bead_profile": "CS4807-CS400",
								"bead_side": "inside",
								"inner_gasket_item": "G22",
								"outer_gasket_item": "G21",
							},
							{
								"id": "dgu",
								"min_glass_mm": 20,
								"max_glass_mm": 26,
								"host": "both",
								"bead_profile": "CS4809-CS400",
								"bead_side": "inside",
								"inner_gasket_item": "G24",
							},
						]
					}
				}
			}
		)
		r1 = match_bead_gasket_rule(cfg, "fixed", "window", 6.0, "frame")
		self.assertIsNotNone(r1)
		self.assertEqual(r1["bead_profile"], "CS4807-CS400")
		self.assertIsNone(match_bead_gasket_rule(cfg, "fixed", "window", 6.0, "sash"))
		r2 = match_bead_gasket_rule(cfg, "fixed", "window", 24.0, "sash")
		self.assertIsNotNone(r2)
		self.assertEqual(r2["bead_profile"], "CS4809-CS400")

	def test_engine_auto_selects_configured_bead_gasket_and_section_placement(self):
		raw_fixture = json.loads(FIXTURE.read_text())
		profile_codes = list(raw_fixture["profiles"].keys())
		bead_code = next((c for c in profile_codes if "bead" in raw_fixture["profiles"][c]["name"].lower()), profile_codes[0])
		glass_code = next(iter(raw_fixture["glasses"].keys()))
		glass_t = raw_fixture["glasses"][glass_code]["thickness_mm"]

		cfg = normalize_section_config(
			{
				"presets": {
					"fixed:window": {
						"frame": {
							"profile": profile_codes[0],
							"gasket_slot": {"x": 14.5, "y": 10.0, "side": "outside", "gasket_item": "GSK-OUT", "thickness_mm": 3.0},
							"bead_slot": {"x": 20.0, "y": 24.0, "side": "inside", "rotation": 90, "flip_x": True},
							"glass_slot": {"x": 22.0, "y": 18.0, "rebate_depth_mm": 14.0, "clearance_mm": 4.0},
						},
						"bead_gasket_rules": [
							{
								"id": "auto_bead",
								"min_glass_mm": max(0.0, glass_t - 1.0),
								"max_glass_mm": glass_t + 1.0,
								"host": "frame",
								"bead_profile": bead_code,
								"bead_side": "inside",
								"bead_offset_along": 2.5,
								"bead_offset_depth": -3.0,
								"bead_rotation": 90,
								"bead_flip_x": True,
								"inner_gasket_item": "GSK-IN",
								"inner_gasket_name": "Inner Glazing Gasket",
								"outer_gasket_item": "GSK-OUT",
								"outer_gasket_name": "Outer Frame Gasket",
							}
						],
					}
				}
			}
		)
		snap = _load_snapshot(cfg)
		design = {"width": 1200, "height": 1200, "root": {"type": "fixed", "glass": glass_code, "bead": True}}

		res = compute(design, snap)
		bead_members = [m for m in res.members if m.role == "bead"]
		self.assertEqual(len(bead_members), 4)
		self.assertTrue(all(m.profile == bead_code for m in bead_members))

		gasket_items = {b.item for b in res.bom if b.group == "Gasket"}
		self.assertIn("GSK-IN", gasket_items)
		self.assertIn("GSK-OUT", gasket_items)

		cut = cross_section(design, snap, "h", result=res)
		frame_pieces = [p for p in cut.pieces if p.role == "frame"]
		bead_pieces = [p for p in cut.pieces if p.role == "bead"]
		glass_pieces = [p for p in cut.pieces if p.kind == "glass"]
		self.assertTrue(frame_pieces and frame_pieces[0].config_placement is not None)
		self.assertEqual(frame_pieces[0].config_placement["gasket_slot"]["x"], 14.5)
		self.assertTrue(bead_pieces and bead_pieces[0].config_placement is not None)
		self.assertEqual(bead_pieces[0].config_placement["rotation"], 90)
		self.assertEqual(bead_pieces[0].config_placement["offsetAlong"], 2.5)
		self.assertEqual(bead_pieces[1].config_placement["offsetAlong"], -2.5)
		self.assertTrue(glass_pieces and glass_pieces[0].config_placement is not None)
		self.assertEqual(glass_pieces[0].config_placement["rebate_depth_mm"], 14.0)


	def test_glass_glazing_rules_drive_auto_bead_and_gaskets(self):
		raw_fixture = json.loads(FIXTURE.read_text())
		profile_codes = list(raw_fixture["profiles"].keys())
		bead_code = next((c for c in profile_codes if "bead" in raw_fixture["profiles"][c]["name"].lower()), profile_codes[0])
		glass_code = next(iter(raw_fixture["glasses"].keys()))
		raw_fixture["glasses"][glass_code]["glazing_rules"] = [
			{
				"series": raw_fixture["code"],
				"host": "both",
				"bead_profile": bead_code,
				"bead_side": "inside",
				"inner_gasket_item": "GLASS-GSK-IN",
				"inner_gasket_name": "Glass Inner Gasket",
				"outer_gasket_item": "GLASS-GSK-OUT",
				"outer_gasket_name": "Glass Outer Gasket",
			}
		]
		snap = SeriesSnapshot.from_dict(raw_fixture)
		design = {"width": 1200, "height": 1200, "root": {"type": "fixed", "glass": glass_code, "bead": True}}
		res = compute(design, snap)
		bead_members = [m for m in res.members if m.role == "bead"]
		self.assertEqual(len(bead_members), 4)
		self.assertTrue(all(m.profile == bead_code for m in bead_members))
		gasket_items = {b.item for b in res.bom if b.group == "Gasket"}
		self.assertIn("GLASS-GSK-IN", gasket_items)
		self.assertIn("GLASS-GSK-OUT", gasket_items)

	def test_section_templates_normalize_and_resolve_across_fixed_openable_and_mullion(self):
		cfg = normalize_section_config(
			{
				"templates": {
					"fixed_window_mullion": {
						"configured": True,
						"glass": "6CTG",
						"axis_h": {
							"roleTransforms": {
								"frame": {"offsetAlong": 0, "offsetDepth": 0, "rotation": 0, "flipX": False, "flipY": False},
								"mullion": {"offsetAlong": 0, "offsetDepth": -2.0, "rotation": 0, "flipX": False, "flipY": False},
								"bead_frame": {"offsetAlong": 3.5, "offsetDepth": 18.0, "rotation": 90, "flipX": True, "flipY": False},
								"bead_mullion": {"offsetAlong": 1.5, "offsetDepth": 17.5, "rotation": 90, "flipX": True, "flipY": False},
							},
							"beadByCode": {
								"CS4807:frame": {"offsetAlong": 4.0, "offsetDepth": 19.0, "rotation": 90, "flipX": True, "flipY": False},
							},
						},
					}
				}
			}
		)
		self.assertEqual(set(cfg["templates"].keys()), set(TEMPLATE_KEYS))
		self.assertTrue(cfg["templates"]["fixed_window_mullion"]["configured"])
		self.assertFalse(cfg["templates"]["openable_door"]["configured"])

		# Low-side frame bead resolves beadByCode[code:frame]
		left_bead = resolve_template_placement(
			cfg, "fixed", "window", "h", "bead", code="CS4807", mirrored=False, has_mullion=True, adjacent="frame"
		)
		self.assertIsNotNone(left_bead)
		self.assertEqual(left_bead["source"], "series_section_template")
		self.assertEqual(left_bead["offsetAlong"], 4.0)
		self.assertEqual(left_bead["offsetDepth"], 19.0)
		self.assertEqual(left_bead["rotation"], 90)
		self.assertTrue(left_bead["flipX"])

		# Mirrored right-side frame bead negates offsetAlong and keeps canonical rotation/flipX
		right_bead = resolve_template_placement(
			cfg, "fixed", "window", "h", "bead", code="CS4807", mirrored=True, has_mullion=True, adjacent="frame"
		)
		self.assertEqual(right_bead["offsetAlong"], -4.0)
		self.assertEqual(right_bead["rotation"], 90)
		self.assertTrue(right_bead["flipX"])

		# Mullion-side bead uses bead_mullion transform
		mullion_bead = resolve_template_placement(
			cfg, "fixed", "window", "h", "bead", code="OTHER", mirrored=False, has_mullion=True, adjacent="mullion"
		)
		self.assertEqual(mullion_bead["offsetAlong"], 1.5)
		self.assertEqual(mullion_bead["offsetDepth"], 17.5)

		# Vertical transom automatically falls back to horizontal mullion transform
		transom = resolve_template_placement(
			cfg, "fixed", "window", "v", "transom", mirrored=False, has_mullion=True
		)
		self.assertIsNotNone(transom)
		self.assertEqual(transom["offsetDepth"], -2.0)

		# Glass intentionally returns None so it auto-seats between placed profiles
		self.assertIsNone(resolve_template_placement(cfg, "fixed", "window", "h", "glass", has_mullion=True))

	def test_cross_section_applies_series_section_template_to_profiles_leaving_glass_auto(self):
		raw_fixture = json.loads(FIXTURE.read_text())
		profile_codes = list(raw_fixture["profiles"].keys())
		bead_code = next((c for c in profile_codes if "bead" in raw_fixture["profiles"][c]["name"].lower()), profile_codes[0])
		glass_code = next(iter(raw_fixture["glasses"].keys()))
		cfg = normalize_section_config(
			{
				"templates": {
					"fixed_window": {
						"configured": True,
						"glass": glass_code,
						"axis_h": {
							"roleTransforms": {
								"frame": {"offsetAlong": 0, "offsetDepth": 1.5, "rotation": 0, "flipX": False, "flipY": False},
								"bead": {"offsetAlong": 2.5, "offsetDepth": 16.0, "rotation": 90, "flipX": False, "flipY": True},
							}
						},
					}
				}
			}
		)
		snap = _load_snapshot(cfg)
		design = {"width": 1200, "height": 1200, "root": {"type": "fixed", "glass": glass_code, "bead": True, "beadProfileId": bead_code}}
		cut = cross_section(design, snap, "h")
		frames = [p for p in cut.pieces if p.role == "frame"]
		beads = [p for p in cut.pieces if p.role == "bead"]
		glasses = [p for p in cut.pieces if p.kind == "glass"]

		self.assertEqual(frames[0].config_placement["source"], "series_section_template")
		self.assertEqual(frames[0].config_placement["offsetDepth"], 1.5)
		self.assertEqual(beads[0].config_placement["source"], "series_section_template")
		self.assertEqual(beads[0].config_placement["offsetAlong"], 2.5)
		self.assertEqual(beads[1].config_placement["offsetAlong"], -2.5)
		self.assertEqual(beads[0].config_placement["rotation"], 90)
		self.assertTrue(beads[0].config_placement["flipY"])
		self.assertIsNone(glasses[0].config_placement)

	def test_glass_domain_normalizes_and_resolves_onto_glass_pieces_in_cross_section(self):
		raw_fixture = json.loads(FIXTURE.read_text())
		glass_code = next(iter(raw_fixture["glasses"].keys()))
		cfg = normalize_section_config(
			{
				"templates": {
					"fixed_window_mullion": {
						"configured": True,
						"glass": glass_code,
						"axis_h": {
							"glassDomain": {
								"configured": True,
								"minY": 6.5,
								"maxY": 28.5,
								"insetLow": -4.0,
								"insetHigh": -2.5,
								"insetMullion": -1.5,
								"align": "top",
							}
						},
					}
				}
			}
		)
		gd = cfg["templates"]["fixed_window_mullion"]["axis_h"]["glassDomain"]
		self.assertTrue(gd["configured"])
		self.assertEqual(gd["minY"], 6.5)
		self.assertEqual(gd["maxY"], 28.5)
		self.assertEqual(gd["insetLow"], -4.0)
		self.assertEqual(gd["insetMullion"], -1.5)
		self.assertEqual(gd["align"], "top")

		# Left bay (frame on low, mullion on high) gets frame inset on low, mullion inset on high
		left_bay = resolve_template_glass_domain(
			cfg, "fixed", "window", "h", has_mullion=True, low_side="frame", high_side="mullion"
		)
		self.assertIsNotNone(left_bay)
		self.assertEqual(left_bay["source"], "series_section_template_glass_domain")
		self.assertEqual(left_bay["insetLow"], -4.0)
		self.assertEqual(left_bay["insetHigh"], -1.5)

		# Right bay (mullion on low, frame on high) flips cleanly
		right_bay = resolve_template_glass_domain(
			cfg, "fixed", "window", "h", has_mullion=True, low_side="mullion", high_side="frame"
		)
		self.assertEqual(right_bay["insetLow"], -1.5)
		self.assertEqual(right_bay["insetHigh"], -4.0)

		# Cross section attaches glassDomain onto glass pieces for multi-bay design
		snap = _load_snapshot(cfg)
		design = {
			"width": 1600,
			"height": 1200,
			"root": {
				"type": "split",
				"dir": "v",
				"at": [800],
				"children": [
					{"type": "fixed", "glass": glass_code, "bead": True},
					{"type": "fixed", "glass": glass_code, "bead": True},
				],
			},
		}
		cut = cross_section(design, snap, "h")
		glasses = [p for p in cut.pieces if p.kind == "glass"]
		self.assertEqual(len(glasses), 2)
		self.assertEqual(glasses[0].config_placement["source"], "series_section_template_glass_domain")
		self.assertEqual(glasses[0].config_placement["minY"], 6.5)
		self.assertEqual(glasses[0].config_placement["maxY"], 28.5)
		self.assertEqual(glasses[0].config_placement["insetLow"], -4.0)
		self.assertEqual(glasses[0].config_placement["insetHigh"], -1.5)
		self.assertEqual(glasses[1].config_placement["insetLow"], -1.5)
		self.assertEqual(glasses[1].config_placement["insetHigh"], -4.0)

	def test_global_glazing_rules_select_bead_and_gaskets_across_any_series_by_thickness(self):
		raw_fixture = json.loads(FIXTURE.read_text())
		profile_codes = list(raw_fixture["profiles"].keys())
		bead_code = next((c for c in profile_codes if "bead" in raw_fixture["profiles"][c]["name"].lower()), profile_codes[0])
		glass_code = next(iter(raw_fixture["glasses"].keys()))
		glass_t = raw_fixture["glasses"][glass_code]["thickness_mm"]

		# Test base-code resolution (without series suffix if present)
		rules = normalize_global_glazing_rules(
			[
				{
					"id": "r1",
					"label": "Standard thin glass",
					"min_glass_mm": max(0.0, glass_t - 0.5),
					"max_glass_mm": glass_t + 0.5,
					"host": "both",
					"bead_profile": bead_code,
					"bead_side": "inside",
					"inner_gasket_hardware": "G23",
					"inner_gasket_item": "G23",
					"inner_gasket_name": "3mm Glazing Gasket",
					"outer_gasket_hardware": "G22",
					"outer_gasket_item": "G22",
					"outer_gasket_name": "2mm Glazing Gasket",
				}
			]
		)
		self.assertIsNotNone(match_global_glazing_rule(rules, glass_t, "frame"))
		raw_fixture["global_glazing_rules"] = rules
		snap = SeriesSnapshot.from_dict(raw_fixture)
		design = {"width": 1200, "height": 1200, "root": {"type": "fixed", "glass": glass_code, "bead": True}}
		res = compute(design, snap)
		bead_members = [m for m in res.members if m.role == "bead"]
		self.assertEqual(len(bead_members), 4)
		self.assertTrue(all(m.profile == bead_code for m in bead_members))
		gasket_items = {b.item for b in res.bom if b.group == "Gasket"}
		self.assertIn("G23", gasket_items)
		self.assertIn("G22", gasket_items)

	def test_global_glazing_rules_respect_profile_type_specificity_and_no_bead_for_sash(self):
		raw_fixture = json.loads(FIXTURE.read_text())
		profile_codes = list(raw_fixture["profiles"].keys())
		bead_code = next((c for c in profile_codes if "bead" in raw_fixture["profiles"][c]["name"].lower()), profile_codes[0])
		glass_code = next(iter(raw_fixture["glasses"].keys()))
		glass_t = raw_fixture["glasses"][glass_code]["thickness_mm"]

		rules = normalize_global_glazing_rules(
			[
				{
					"id": "shared_frame",
					"profile_type": "both",
					"min_glass_mm": max(0.0, glass_t - 0.5),
					"max_glass_mm": glass_t + 0.5,
					"host": "frame",
					"bead_profile": bead_code,
					"bead_side": "inside",
					"inner_gasket_item": "G25",
					"outer_gasket_item": "G23",
				},
				{
					"id": "win_sash_no_bead",
					"profile_type": "window",
					"min_glass_mm": max(0.0, glass_t - 0.5),
					"max_glass_mm": glass_t + 0.5,
					"host": "sash",
					"bead_profile": "",
					"no_bead": True,
					"inner_gasket_item": "G24",
					"outer_gasket_item": "G24",
				},
				{
					"id": "door_sash_with_bead",
					"profile_type": "door",
					"min_glass_mm": max(0.0, glass_t - 0.5),
					"max_glass_mm": glass_t + 0.5,
					"host": "sash",
					"bead_profile": bead_code,
					"inner_gasket_item": "G25",
					"outer_gasket_item": "G23",
				},
			]
		)
		self.assertEqual(match_global_glazing_rule(rules, glass_t, "frame", "window")["id"], "shared_frame")
		self.assertEqual(match_global_glazing_rule(rules, glass_t, "frame", "door")["id"], "shared_frame")
		self.assertEqual(match_global_glazing_rule(rules, glass_t, "sash", "window")["id"], "win_sash_no_bead")
		self.assertTrue(match_global_glazing_rule(rules, glass_t, "sash", "window")["no_bead"])
		self.assertEqual(match_global_glazing_rule(rules, glass_t, "sash", "door")["id"], "door_sash_with_bead")

		# Window sash with no_bead emits gaskets (G24) and NO glass_adaptor/bead members
		raw_fixture["global_glazing_rules"] = rules
		snap = SeriesSnapshot.from_dict(raw_fixture)
		win_sash_design = {
			"width": 1000,
			"height": 1200,
			"root": {"type": "sash", "opening": "out", "hinge": "left", "sashConfig": "window", "glass": glass_code, "bead": True},
		}
		res_win = compute(win_sash_design, snap)
		self.assertEqual([m for m in res_win.members if m.role in ("bead", "glass_adaptor")], [])
		self.assertIn("G24", {b.item for b in res_win.bom if b.group == "Gasket"})

	def test_only_door_sash_gets_bead_and_series_product_warnings(self):
		from onebook_fenestration.engine.section_config import (
			normalize_supported_products,
			template_keys_for_products,
		)

		raw_fixture = json.loads(FIXTURE.read_text())
		profile_codes = list(raw_fixture["profiles"].keys())
		bead_code = next((c for c in profile_codes if "bead" in raw_fixture["profiles"][c]["name"].lower()), profile_codes[0])
		glass_code = next(iter(raw_fixture["glasses"].keys()))
		glass_t = raw_fixture["glasses"][glass_code]["thickness_mm"]

		# Even if global glazing rule has host="both" with a bead_profile, window sashes must NOT get a sash bead.
		raw_fixture["global_glazing_rules"] = normalize_global_glazing_rules(
			[
				{
					"id": "both_with_bead",
					"profile_type": "both",
					"min_glass_mm": max(0.0, glass_t - 1.0),
					"max_glass_mm": glass_t + 1.0,
					"host": "both",
					"bead_profile": bead_code,
					"inner_gasket_item": "G24",
					"outer_gasket_item": "G23",
				}
			]
		)
		raw_fixture["supported_products"] = ["Window"]
		snap = SeriesSnapshot.from_dict(raw_fixture)

		win_sash = {
			"width": 1000,
			"height": 1200,
			"root": {"type": "sash", "opening": "out", "hinge": "left", "sashConfig": "window", "glass": glass_code, "bead": True},
		}
		res_win = compute(win_sash, snap)
		self.assertEqual([m for m in res_win.members if m.role in ("bead", "glass_adaptor")], [])
		self.assertFalse(any(i.code == "unsupported_series_product" for i in res_win.issues))

		door_sash = {
			"width": 1000,
			"height": 2100,
			"frameConfig": "3-side-threshold",
			"root": {"type": "sash", "opening": "out", "hinge": "left", "sashConfig": "door", "glass": glass_code, "bead": True},
		}
		res_door = compute(door_sash, snap)
		self.assertTrue(any(m.role == "glass_adaptor" and m.profile == bead_code for m in res_door.members))
		self.assertTrue(
			any(i.code == "unsupported_series_product" and "Door" in i.message for i in res_door.issues)
		)

		self.assertEqual(normalize_supported_products('["Window", "Door"]'), ["Window", "Door"])
		self.assertEqual(
			template_keys_for_products(["Window"]),
			("fixed_window", "fixed_window_mullion", "openable_window", "openable_window_mullion"),
		)
		self.assertEqual(len(template_keys_for_products(["Window", "Door"])), 8)
		self.assertNotIn("sliding_window", template_keys_for_products(["Window", "Door"]))

	def test_resolve_glazing_by_width_formula_and_engine_integration(self):
		from onebook_fenestration.engine.section_config import (
			normalize_glazing_auto_config,
			resolve_glazing_by_width,
		)

		gaskets = [
			{"code": "G22", "item": "G22", "name": "Gasket 2mm", "thickness_mm": 2.0},
			{"code": "G23", "item": "G23", "name": "Gasket 3mm", "thickness_mm": 3.0},
			{"code": "G24", "item": "G24", "name": "Gasket 4mm", "thickness_mm": 4.0},
			{"code": "G25", "item": "G25", "name": "Gasket 5mm", "thickness_mm": 5.0},
		]
		auto_cfg = normalize_glazing_auto_config(
			{
				"enabled": True,
				"max_compression_mm": 1.0,
				"thicker_gasket_side": "outer",
				"channels": [
					{
						"id": "ch_12",
						"series": "CS4800",
						"profile_type": "both",
						"host": "both",
						"bead_profile": "HSL3409",
						"no_bead": False,
						"bead_width_mm": 12.01,
						"bead_side": "inside",
					},
					{
						"id": "ch_18",
						"series": "CS4800",
						"profile_type": "both",
						"host": "both",
						"bead_profile": "HSL3410",
						"no_bead": False,
						"bead_width_mm": 18.01,
						"bead_side": "inside",
					},
					{
						"id": "ch_28",
						"series": "CS4800",
						"profile_type": "both",
						"host": "both",
						"bead_profile": "",
						"no_bead": True,
						"bead_width_mm": 28.0,
						"bead_side": "inside",
					},
				],
			}
		)

		expected_cases = [
			(5.0, "HSL3409", False, "G24", "G23"),   # R=7.01 -> Outer 4, Inner 3
			(6.0, "HSL3409", False, "G23", "G23"),   # R=6.01 -> Outer 3, Inner 3
			(8.0, "HSL3409", False, "G22", "G22"),   # R=4.01 -> Outer 2, Inner 2
			(12.0, "HSL3410", False, "G23", "G23"),  # R=6.01 -> step up to 18.01, Outer 3, Inner 3
			(13.0, "HSL3410", False, "G23", "G22"),  # R=5.01 -> Outer 3, Inner 2
			(13.5, "HSL3410", False, "G23", "G22"),  # R=4.51 -> rejects 2+2 (loose), picks 3+2 (+0.49 tight)
			(15.0, "HSL3410", False, "G22", "G22"),  # R=3.01 -> picks 2+2 (+0.99 tight <= 1mm)
			(24.0, "", True, "G22", "G22"),          # No Bead 28mm -> R=4.0 -> Outer 2, Inner 2
		]
		for gt, exp_bead, exp_no_bead, exp_outer, exp_inner in expected_cases:
			res = resolve_glazing_by_width(auto_cfg, gaskets, gt, "CS4800", "frame", "window")
			self.assertIsNotNone(res, f"GT={gt}")
			self.assertTrue(res["ok"], f"GT={gt}: {res}")
			self.assertEqual(res["bead_profile"], exp_bead, f"GT={gt}")
			self.assertEqual(res["no_bead"], exp_no_bead, f"GT={gt}")
			self.assertEqual(res["outer_gasket_item"], exp_outer, f"GT={gt}")
			self.assertEqual(res["inner_gasket_item"], exp_inner, f"GT={gt}")

		# Over-compressed (26mm in 28mm -> 2+2=4 gives +2mm > 1mm) fails
		over = resolve_glazing_by_width(auto_cfg, gaskets, 26.0, "CS4800", "frame", "window")
		self.assertFalse(over["ok"])
		self.assertEqual(over["reason"], "no_gasket_combo")

		# Exceeds max BW fails
		too_big = resolve_glazing_by_width(auto_cfg, gaskets, 30.0, "CS4800", "frame", "window")
		self.assertFalse(too_big["ok"])
		self.assertEqual(too_big["reason"], "exceeds_max_bw")

		# Different series without default channels returns None
		self.assertIsNone(resolve_glazing_by_width(auto_cfg, gaskets, 6.0, "OTHER", "frame", "window"))

		# Full engine compute integration: bead + outer/inner gaskets emitted from auto BW solver
		raw_fixture = json.loads(FIXTURE.read_text())
		series_code = raw_fixture["code"]
		profile_codes = list(raw_fixture["profiles"].keys())
		bead_code = next((c for c in profile_codes if "bead" in raw_fixture["profiles"][c]["name"].lower()), profile_codes[0])
		raw_fixture["glasses"]["5TEST"] = {"name": "5mm Test Glass", "thickness_mm": 5.0}
		raw_fixture["glasses"]["29TEST"] = {"name": "29mm Oversized", "thickness_mm": 29.0}
		raw_fixture["gasket_catalog"] = gaskets
		raw_fixture["global_glazing_auto"] = normalize_glazing_auto_config(
			{
				"enabled": True,
				"max_compression_mm": 1.0,
				"thicker_gasket_side": "outer",
				"channels": [
					{
						"id": "fit_12",
						"series": series_code,
						"profile_type": "both",
						"host": "frame",
						"bead_profile": bead_code,
						"no_bead": False,
						"bead_width_mm": 12.01,
						"bead_side": "inside",
					}
				],
			}
		)
		snap = SeriesSnapshot.from_dict(raw_fixture)
		res_ok = compute({"width": 1200, "height": 1200, "root": {"type": "fixed", "glass": "5TEST", "bead": True}}, snap)
		bead_members = [m for m in res_ok.members if m.role == "bead"]
		self.assertEqual(len(bead_members), 4)
		self.assertTrue(all(m.profile == bead_code for m in bead_members))
		gasket_items = {b.item for b in res_ok.bom if b.group == "Gasket"}
		self.assertIn("G24", gasket_items)
		self.assertIn("G23", gasket_items)

		res_warn = compute({"width": 1200, "height": 1200, "root": {"type": "fixed", "glass": "29TEST", "bead": True}}, snap)
		self.assertTrue(any(i.code == "glazing_width_mismatch" for i in res_warn.issues))

		# Verify raycast pocket metadata & glazing_gaskets round-trip through normalize_section_config and cross_section
		raw_fixture["section_config"] = normalize_section_config(
			{
				"version": 1,
				"templates": {
					"fixed_window": {
						"configured": True,
						"axis_h": {
							"beadByCode": {
								bead_code: {"offsetAlong": 1.5, "offsetDepth": 4.0, "rotation": 90, "flipX": False, "flipY": False}
							},
							"glassDomain": {
								"configured": True,
								"minY": 10.0,
								"maxY": 38.0,
								"insetLow": -11.0,
								"insetHigh": -11.0,
								"align": "center",
								"raycast": {
									"enabled": True,
									"pocketMinY": 10.0,
									"pocketMaxY": 38.0,
									"pocketInsetLow": -14.0,
									"pocketInsetHigh": -14.0,
									"probeOffsetFromLow": 4.5,
								},
							},
						},
					}
				},
			}
		)
		snap_rc = SeriesSnapshot.from_dict(raw_fixture)
		cut_rc = cross_section(
			{"width": 1200, "height": 1200, "root": {"type": "fixed", "glass": "5TEST", "bead": True}},
			snap_rc,
			"h",
		)
		glass_piece = next(p for p in cut_rc.pieces if p.kind == "glass")
		self.assertTrue(glass_piece.config_placement["raycast"]["enabled"])
		self.assertEqual(glass_piece.config_placement["raycast"]["pocketMinY"], 10.0)
		self.assertEqual(glass_piece.config_placement["glazing_gaskets"]["outer_code"], "G24")
		self.assertEqual(glass_piece.config_placement["glazing_gaskets"]["outer_mm"], 4.0)
		self.assertEqual(glass_piece.config_placement["glazing_gaskets"]["inner_code"], "G23")
		self.assertEqual(glass_piece.config_placement["glazing_gaskets"]["inner_mm"], 3.0)
		bead_piece = next(p for p in cut_rc.pieces if p.role == "bead")
		self.assertTrue(bead_piece.config_placement["matchedCode"])

	def test_profile_aware_template_matching_prevents_door_window_mismatch(self):
		cfg = normalize_section_config(
			{
				"version": 1,
				"templates": {
					"openable_window_mullion": {
						"configured": True,
						"profiles": {"frame": "CS4801", "sash": "CS4803", "mullion": "CS4802"},
						"axis_h": {
							"roleTransforms": {
								"frame": {"offsetAlong": 0.0, "offsetDepth": 0.0},
								"mullion": {"offsetAlong": 0.0, "offsetDepth": 8.0},
								"sash_frame": {"offsetAlong": -2.1, "offsetDepth": 1.0},
								"sash_mullion": {"offsetAlong": -0.7, "offsetDepth": 0.0},
							},
							"glassDomain": {
								"configured": True,
								"minY": 13.4,
								"maxY": 41.4,
								"insetLow": -3.4,
								"insetHigh": -2.0,
							},
						},
					},
					"openable_door_mullion": {
						"configured": True,
						"profiles": {"frame": "CS4805", "sash": "CS4804", "mullion": "CS4806"},
						"axis_h": {
							"roleTransforms": {
								"frame": {"offsetAlong": 0.0, "offsetDepth": 0.0},
								"mullion": {"offsetAlong": 0.0, "offsetDepth": 10.0},
								"sash_frame": {"offsetAlong": 21.6, "offsetDepth": 0.0},
								"sash_mullion": {"offsetAlong": 10.0, "offsetDepth": 0.0},
							},
							"glassDomain": {
								"configured": True,
								"minY": 12.4,
								"maxY": 40.4,
								"insetLow": 37.6,
								"insetHigh": 26.0,
							},
						},
					},
				},
			}
		)

		# Window shutter CS4803 with sashConfig='door' must match openable_window_mullion, not CS4804's +21.6 door offsets
		win_sash = resolve_template_placement(
			cfg,
			"openable",
			"door",
			"h",
			"sash",
			code="CS4803",
			has_mullion=True,
			adjacent="frame",
			active_profiles={"frame": "CS4801", "sash": "CS4803", "mullion": "CS4802"},
		)
		self.assertIsNotNone(win_sash)
		self.assertEqual(win_sash["template"], "openable_window_mullion")
		self.assertEqual(win_sash["offsetAlong"], -2.1)

		win_gd = resolve_template_glass_domain(
			cfg,
			"openable",
			"door",
			"h",
			has_mullion=True,
			low_side="frame",
			high_side="mullion",
			active_profiles={"frame": "CS4801", "sash": "CS4803", "mullion": "CS4802"},
		)
		self.assertIsNotNone(win_gd)
		self.assertEqual(win_gd["template"], "openable_window_mullion")
		self.assertEqual(win_gd["insetLow"], -3.4)

		# Door mullion CS4806 must match openable_door_mullion even if application defaults to 'window'
		door_mul = resolve_template_placement(
			cfg,
			"openable",
			"window",
			"h",
			"mullion",
			code="CS4806",
			has_mullion=True,
			design_has_sash=True,
			active_profiles={"frame": "CS4805", "sash": "CS4804", "mullion": "CS4806"},
		)
		self.assertIsNotNone(door_mul)
		self.assertEqual(door_mul["template"], "openable_door_mullion")
		self.assertEqual(door_mul["offsetDepth"], 10.0)

	def test_global_glazing_gasket_length_deducts_both_ends(self):
		raw_fixture = json.loads(FIXTURE.read_text())
		glass_code = next(iter(raw_fixture["glasses"].keys()))
		glass_t = raw_fixture["glasses"][glass_code]["thickness_mm"]
		gasket_ded = float(raw_fixture.get("deductions", {}).get("glazing_gasket", 0.0))
		raw_fixture["global_glazing_rules"] = normalize_global_glazing_rules(
			[
				{
					"id": "g1",
					"label": "Gasket deduction check",
					"min_glass_mm": max(0.0, glass_t - 0.5),
					"max_glass_mm": glass_t + 0.5,
					"host": "both",
					"bead_profile": "",
					"bead_side": "inside",
					"inner_gasket_hardware": "G23",
					"inner_gasket_item": "G23",
					"inner_gasket_name": "3mm Glazing Gasket",
					"outer_gasket_hardware": "G22",
					"outer_gasket_item": "G22",
					"outer_gasket_name": "2mm Glazing Gasket",
				}
			]
		)
		snap = SeriesSnapshot.from_dict(raw_fixture)
		design = {"width": 1200, "height": 1000, "root": {"type": "fixed", "glass": glass_code, "bead": False}}
		res = compute(design, snap)
		pane = res.glass[0]
		gasket_lines = [b for b in res.bom if b.group == "Gasket" and b.item == "G23"]
		self.assertEqual(len(gasket_lines), 4)
		by_pos = {b.position: b.length for b in gasket_lines}
		self.assertAlmostEqual(by_pos["W"], max(0.0, round(pane.width - 2 * gasket_ded, 1)))
		self.assertAlmostEqual(by_pos["H"], max(0.0, round(pane.height - 2 * gasket_ded, 1)))


if __name__ == "__main__":
	unittest.main()
