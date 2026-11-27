import unittest

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.hardware import calc_hinge_count
from onebook_fenestration.engine.tests.helpers import snapshot
from onebook_fenestration.engine.types import HardwareRule, MemberRule, ProfileSpec, SeriesSnapshot


def cs4800_door_snapshot() -> SeriesSnapshot:
	"""Build a CS4800-like SeriesSnapshot with door frame, low threshold, door sash, and height/weight hardware rules."""
	base = snapshot()
	profiles = dict(base.profiles)
	profiles["CS4805"] = ProfileSpec("CS4805", "CMT DOOR FRAME 48MM X 69.5MM", 0.92, (3660.0,))
	profiles["CS4814"] = ProfileSpec("CS4814", "THRESHOLD 35MM X 17MM", 0.23, (3660.0,))
	profiles["CS4804"] = ProfileSpec("CS4804", "CMT DOOR SHUTTER 48MM X 87MM", 1.20, (3660.0,))
	profiles["CS4813"] = ProfileSpec("CS4813", "DOOR BOTTOM ADAPTOR 31MM X 9MM", 0.21, (3660.0,))
	profiles["HSL3409"] = ProfileSpec("HSL3409", "SLD SGU GLASS ADAPTOR 28.9MM", 0.21, (3660.0,))

	member_rules = (
		*base.member_rules,
		MemberRule("m_thresh", "threshold", "CS4814", (90, 90), "span - 99"),
		MemberRule("m_dsash", "door_sash", "CS4804", (45, 45), "span"),
		MemberRule("m_badapt", "door_bottom_adaptor", "CS4813", (45, 45), "span - 37"),
		MemberRule(
			"m_bead_thin",
			"bead",
			"HSL3409",
			(45, 45),
			"opening_w if position in 'BT' else opening_h",
			"glass_t <= 12",
		),
	)
	hardware_rules = (
		*base.hardware_rules,
		HardwareRule(
			"h_door_hinge", "H415", "DOOR HINGE 3 WING", "sash", "hinge_count", when="sash_config == 'door'"
		),
		HardwareRule(
			"h_door_lock",
			"H420",
			"DOOR HANDLE SET",
			"sash",
			"1",
			when="sash_config == 'door' and active_leaf",
		),
		HardwareRule(
			"h_win_hinge",
			"H412",
			"WINDOW BUTT HINGE",
			"sash",
			"hinge_count",
			when="sash_config == 'window' and hinge_stay == 'hinges'",
		),
	)
	constants = {**base.constants, "glass_clearance": 4.0}
	return SeriesSnapshot(
		code="CS4800",
		version="v1",
		deductions=base.deductions,
		profiles=profiles,
		member_rules=member_rules,
		hardware_rules=hardware_rules,
		validation_rules=base.validation_rules,
		glasses=base.glasses,
		constants=constants,
	)


class TestEvaPhase1Rules(unittest.TestCase):
	def test_3_side_frame_omits_bottom_and_squares_jambs(self):
		d = {
			"width": 1500,
			"height": 1500,
			"frameConfig": "3-side",
			"root": {"type": "fixed", "glass": "6CTG"},
		}
		res = compute(d, cs4800_door_snapshot())
		frame_cuts = [(m.position, m.length, m.angles) for m in res.members if m.role == "frame"]
		self.assertEqual(
			sorted(frame_cuts), [("L", 1500.0, (90, 45)), ("R", 1500.0, (45, 90)), ("T", 1500.0, (45, 45))]
		)

	def test_w6_3_side_low_threshold_and_active_passive_door(self):
		d = {
			"width": 1500,
			"height": 1500,
			"frameConfig": "3-side-threshold",
			"profiles": {"F1.T": "CS4805", "F1.L": "CS4805", "F1.R": "CS4805"},
			"root": {
				"type": "split",
				"dir": "v",
				"at": [750],
				"children": [
					{
						"type": "sash",
						"glass": "6CTG",
						"sashConfig": "door",
						"activeLeaf": False,
						"hinge": "left",
					},
					{
						"type": "sash",
						"glass": "6CTG",
						"sashConfig": "door",
						"activeLeaf": True,
						"hinge": "right",
					},
				],
			},
		}
		res = compute(d, cs4800_door_snapshot())
		frame_cuts = [
			(m.position, m.profile, m.length, m.angles)
			for m in res.members
			if m.role in ("frame", "threshold")
		]
		self.assertEqual(
			sorted(frame_cuts),
			[
				("B", "CS4814", 1401.0, (90, 90)),
				("L", "CS4805", 1500.0, (90, 45)),
				("R", "CS4805", 1500.0, (45, 90)),
				("T", "CS4805", 1500.0, (45, 45)),
			],
		)
		door_sashes = [m for m in res.members if m.role == "sash"]
		self.assertTrue(all(m.profile == "CS4804" for m in door_sashes))
		adaptors = [m for m in res.members if m.role == "door_bottom_adaptor"]
		self.assertEqual(len(adaptors), 2)
		hinges = [b for b in res.bom if b.item == "H415"]
		self.assertEqual(sum(b.qty for b in hinges), 8)
		handles = [b for b in res.bom if b.item == "H420"]
		self.assertEqual([(b.panel, b.qty) for b in handles], [("F1-S2", 1)])

	def test_calc_hinge_count_by_height_and_weight(self):
		self.assertEqual(calc_hinge_count(1200, 18.0, is_door=True), 3)
		self.assertEqual(calc_hinge_count(1500, 22.0, is_door=True), 4)
		self.assertEqual(calc_hinge_count(2150, 35.0, is_door=True), 5)
		self.assertEqual(calc_hinge_count(1200, 68.0, is_door=True), 5)
		self.assertEqual(calc_hinge_count(900, 10.0, is_door=False), 2)
		self.assertEqual(calc_hinge_count(1200, 15.0, is_door=False), 3)
		self.assertEqual(calc_hinge_count(1700, 25.0, is_door=False), 4)

	def test_auto_bead_and_gasket_change_with_frame_depth_and_glass_thickness(self):
		base = cs4800_door_snapshot()
		profiles = dict(base.profiles)
		profiles["F40"] = ProfileSpec("F40", "40MM FRAME", 0.72, (3660.0,), width_mm=42.0, depth_mm=40.0)
		profiles["F48"] = ProfileSpec("F48", "48MM FRAME", 0.88, (3660.0,), width_mm=48.0, depth_mm=48.0)
		profiles["B40_THIN"] = ProfileSpec("B40_THIN", "40MM BEAD THIN", 0.18, (3660.0,))
		profiles["B48_THIN"] = ProfileSpec("B48_THIN", "48MM BEAD THIN", 0.21, (3660.0,))
		snap = SeriesSnapshot(
			code=base.code,
			version=base.version,
			deductions=base.deductions,
			profiles=profiles,
			member_rules=(
				*[r for r in base.member_rules if r.role != "bead"],
				MemberRule(
					"m_b40",
					"bead",
					"B40_THIN",
					(45, 45),
					"opening_w if position in 'BT' else opening_h",
					"frame_depth <= 42 and glass_t <= 8",
				),
				MemberRule(
					"m_b48",
					"bead",
					"B48_THIN",
					(45, 45),
					"opening_w if position in 'BT' else opening_h",
					"frame_depth > 42 and glass_t <= 12",
				),
			),
			hardware_rules=(
				*[r for r in base.hardware_rules if r.group != "Gasket"],
				HardwareRule(
					"g_3mm",
					"G23",
					"GASKET 3MM",
					"pane_side",
					"1",
					"m",
					"glass_t <= 6",
					"side_len / 1000",
					"Gasket",
				),
				HardwareRule(
					"g_2mm",
					"G22",
					"GASKET 2MM",
					"pane_side",
					"1",
					"m",
					"glass_t > 6",
					"side_len / 1000",
					"Gasket",
				),
				HardwareRule(
					"g_f48",
					"G21-48",
					"FRAME GASKET 48MM",
					"frame_side",
					"1",
					"m",
					"frame_depth > 42",
					"side_len / 1000",
					"Gasket",
				),
				HardwareRule(
					"g_f40",
					"G21-40",
					"FRAME GASKET 40MM",
					"frame_side",
					"1",
					"m",
					"frame_depth <= 42",
					"side_len / 1000",
					"Gasket",
				),
			),
			validation_rules=base.validation_rules,
			glasses=base.glasses,
			constants=base.constants,
		)
		res_f40 = compute(
			{
				"width": 1200,
				"height": 1200,
				"frameProfileId": "F40",
				"root": {"type": "fixed", "glass": "6CTG"},
			},
			snap,
		)
		res_f48 = compute(
			{
				"width": 1200,
				"height": 1200,
				"frameProfileId": "F48",
				"root": {"type": "fixed", "glass": "6CTG"},
			},
			snap,
		)
		self.assertEqual({m.profile for m in res_f40.members if m.role == "bead"}, {"B40_THIN"})
		self.assertEqual({m.profile for m in res_f48.members if m.role == "bead"}, {"B48_THIN"})
		self.assertIn("G21-40", {b.item for b in res_f40.bom})
		self.assertIn("G21-48", {b.item for b in res_f48.bom})
		self.assertIn("G23", {b.item for b in res_f48.bom})
