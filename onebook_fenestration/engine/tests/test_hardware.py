import unittest

from onebook_fenestration.engine import compute
from onebook_fenestration.engine.tests.helpers import load, snapshot

SNAP = snapshot()


def totals(bom):
	t: dict[str, float] = {}
	for line in bom:
		t[line.item] = t.get(line.item, 0) + line.qty
	return t


class TestHardware(unittest.TestCase):
	def test_w01_hardware_totals(self):
		t = totals(compute(load("w01.json"), SNAP).bom)
		items = ["H401", "H266", "H912", "H913", "H904", "H903", "H902", "H901", "H911", "H412", "H411", "H416", "H429", "H425", "H422C", "H423", "H905"]
		self.assertEqual(
			{k: t[k] for k in items},
			{"H401": 12, "H266": 12, "H912": 10, "H913": 2, "H904": 10, "H903": 10, "H902": 6, "H901": 6, "H911": 10, "H412": 4, "H411": 2, "H416": 2, "H429": 12, "H425": 2, "H422C": 2, "H423": 4, "H905": 16},
		)

	def test_w01_consumables(self):
		bom = compute(load("w01.json"), SNAP).bom
		self.assertEqual(next(b.length for b in bom if b.item == "H915"), 8.54)
		self.assertEqual(next(b.qty for b in bom if b.item == "H914"), 1.423)

	def test_w02_frame_hardware(self):
		t = totals(compute(load("w02.json"), SNAP).bom)
		self.assertEqual((t["H912"], t["H902"], t["H911"]), (8, 4, 8))

	def test_transom_member_rule(self):
		from onebook_fenestration.engine.tests.helpers import snapshot_with

		rule = {"id": "hw_transom_screw", "item": "H412T", "name": "TRANSOM SCREW", "per": "transom_member", "qty": "4", "when": "role == 'transom' and len > 0"}
		snap = snapshot_with(lambda d: d["hardware_rules"].append(rule))
		design = {
			"width": 915,
			"height": 1220,
			"root": {"type": "split", "dir": "h", "at": [610], "children": [{"type": "fixed", "glass": "6CTG"}, {"type": "fixed", "glass": "6CTG"}]},
		}
		lines = [b for b in compute(design, snap).bom if b.item == "H412T"]
		self.assertEqual([(b.qty, b.panel, b.position) for b in lines], [(4, "F1", "W")])


def _opt_design(*leaves):
	if len(leaves) == 1:
		return {"width": 600, "height": 1200, "root": leaves[0]}
	at = [600 * (i + 1) for i in range(len(leaves) - 1)]
	return {"width": 600 * len(leaves), "height": 1200, "root": {"type": "split", "dir": "v", "at": at, "children": list(leaves)}}


def _opt_rule(when):
	return {"id": "hw_opt", "item": "HOPT", "name": "OPT", "per": "sash", "qty": "1", "when": when}


class TestSashOptions(unittest.TestCase):
	def _panels(self, when, design, mutate=None):
		from onebook_fenestration.engine.tests.helpers import snapshot_with

		def edit(d):
			d["hardware_rules"].append(_opt_rule(when))
			if mutate:
				mutate(d)

		bom = compute(design, snapshot_with(edit)).bom
		return [b.panel for b in bom if b.item == "HOPT"]

	def test_sash_options_reach_rules(self):
		plain = {"type": "sash", "glass": "6CTG"}
		single = {"type": "sash", "glass": "6CTG", "handle": "single"}
		fixed = {"type": "fixed", "glass": "6CTG"}
		self.assertEqual(self._panels("handle == 'single'", _opt_design(plain, fixed, single)), ["F1-S2"])
		butt = {"type": "sash", "glass": "6CTG", "hinge_type": "butt", "limiter": True, "mesh": True}
		self.assertEqual(self._panels("hinge_type == 'butt'", _opt_design(plain, butt)), ["F1-S2"])
		self.assertEqual(self._panels("limiter and mesh", _opt_design(butt, plain)), ["F1-S1"])

	def test_missing_sash_options_use_defaults(self):
		plain = {"type": "sash", "glass": "6CTG"}
		everything = "hinge_type == 'friction' and handle == 'multipoint' and limiter == False and mesh == False"
		self.assertEqual(self._panels(everything, _opt_design(plain)), ["F1-S1"])

	def test_series_constants_set_defaults(self):
		plain = {"type": "sash", "glass": "6CTG"}

		def consts(d):
			d["constants"].update({"default_butt_hinge": 1, "default_single_point_handle": 1, "default_mesh": 1})

		when = "hinge_type == 'butt' and handle == 'single' and mesh and not limiter"
		self.assertEqual(self._panels(when, _opt_design(plain), consts), ["F1-S1"])

	def test_design_value_overrides_opposite_series_default(self):
		node = {"type": "sash", "glass": "6CTG", "hinge_type": "friction", "handle": "multipoint", "limiter": False, "mesh": False}

		def consts(d):
			d["constants"].update(
				{"default_butt_hinge": 1, "default_single_point_handle": 1, "default_limiter": 1, "default_mesh": 1}
			)

		when = "hinge_type == 'friction' and handle == 'multipoint' and not limiter and not mesh"
		self.assertEqual(self._panels(when, _opt_design(node), consts), ["F1-S1"])
		opposite = {"type": "sash", "glass": "6CTG", "hinge_type": "butt", "handle": "single", "limiter": True, "mesh": True}
		self.assertEqual(self._panels("hinge_type == 'butt' and handle == 'single' and limiter and mesh", _opt_design(opposite)), ["F1-S1"])

	def test_invalid_default_constant_is_an_error_issue(self):
		from onebook_fenestration.engine.tests.helpers import snapshot_with

		snap = snapshot_with(lambda d: d["constants"].update({"default_butt_hinge": 0.5, "default_mesh": -1}))
		issues = [i for i in compute(_opt_design({"type": "sash", "glass": "6CTG"}), snap).issues if i.code == "invalid_series_constant"]
		self.assertEqual([i.severity for i in issues], ["error", "error"])
		self.assertIn("default_butt_hinge", issues[0].message)
		self.assertIn("default_mesh", issues[1].message)
