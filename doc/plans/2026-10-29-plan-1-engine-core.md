# Plan 1: Engine Core + DXF Section Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pure-Python, deterministic `onebook_fenestration.engine` package. It turns a window design tree plus a series snapshot into cut members, hardware, glass, weights and validation issues, and it turns a profile DXF into section properties. It must reproduce the EvA outputs for W01 and W02.

**Architecture:**
- Plain dataclasses in, plain dataclasses out. The engine never touches the DB (CLAUDE.md ground rule); Plan 2 builds `SeriesSnapshot` from doctypes.
- Series-specific numbers live only in snapshot data. Formulas are strings evaluated with `frappe.utils.safe_exec.safe_eval`, which works without a site.
- Pipeline: `layout` (tree → cells and members) → `members` (cut list) → `glazing` → `hardware` → `weights` → `validate`, orchestrated by `engine.compute`.

**Tech Stack:** Python 3.14 (bench env), `frappe.utils.safe_exec.safe_eval`, `ezdxf~=1.4` (DXF parsing, curve flattening), stdlib `unittest`.

**Spec:** `doc/context.md` (§3 rules, §4 engine model), `doc/decisions.md` (D2, D3), `doc/plans/2026-10-29-roadmap.md`.

## Global Constraints

- No `frappe.db`, `frappe.get_doc` or any site access anywhere under `onebook_fenestration/engine/`. Only `frappe.utils.safe_exec.safe_eval` may be imported from frappe.
- Lengths are in mm. Cut lengths are rounded to 0.1 mm (`round(x, 1)`). Weights are in kg, rounded to 3 dp. Areas are in m², rounded to 3 dp. sq.ft = m² (3 dp) × 10.764.
- Glass density is 2.5 kg/m² per mm of thickness. Aluminium kg/m = area_mm² × 0.0027.
- Panel ids: the frame is `F1`. Sashes are `S1..Sn` and glass panes `1..n`, numbered in tree order (depth-first, children left→right / bottom→top). Mullions are `M1..`, transoms `T1..`. A child path looks like `F1-S1`. Positions are `B`/`T`/`L`/`R` for frame and sash members, `H` for a vertical mullion, `W` for a horizontal transom.
- Angles: frame and sash members are mitred `(45, 135)`; mullions, transoms and beads are `(90, 90)`, as recorded in the member rule.
- Window weight = profiles + glass only (hardware excluded), matching EvA's PDF figures.
- New runtime dependency `ezdxf~=1.4` goes in `pyproject.toml` `[project] dependencies`.
- Test command (from the app root `apps/onebook_fenestration`): `../../env/bin/python -m unittest discover -s onebook_fenestration/engine/tests -t . -v`
- Work on branch `feat/engine-core`. Never commit `doc/*.pdf`, `doc/*.mp4` or `doc/*.dxf`. Test fixtures copy what they need into `onebook_fenestration/engine/tests/fixtures/`.

## Review Focus

1. **Bad split positions** (unsorted, ≤0, ≥ span, or count ≠ children−1): `compute` raises `DesignError` naming the node path. It must not produce negative cuts. Owned by Task 2.
2. **Cell too small, giving a zero or negative cut or glass size**: returns an `Issue(severity="error", code="non_positive_size")`, does not crash, and still returns the other results. Owned by Task 3.
3. **Rule formula that is broken or uses an unknown variable**: raises `RuleError` with the rule id and expression. It must not surface as a bare `NameError`. Owned by Task 1.
4. **DXF with no closed loops, or units unset or unknown**: `SectionError("no closed polylines")`. Units `0` are assumed mm, with `warnings` containing `"units_assumed_mm"`. Owned by Task 6.
5. **Float drift on cut lengths** (457.5 − 18 − 5.5 must give exactly 434.0): the rounding rule is applied once, at member creation. Owned by Task 3.

---

## File Structure

```
onebook_fenestration/engine/
  __init__.py          exports compute, analyze_dxf, dataclasses, errors
  types.py             dataclasses + errors (DesignError, RuleError, SectionError)
  formula.py           evaluate(expr, variables, rule_id) -> float | bool
  layout.py            parse tree -> Cell rects + structural Member stubs
  members.py           Member stubs + MemberRules -> CutMember list
  glazing.py           glass panes + gasket cuts
  hardware.py          HardwareRules -> BomLine list
  weights.py           shutter/window kg
  validate.py          ValidationRules -> Issue list
  engine.py            compute(design: dict, snapshot: SeriesSnapshot) -> EngineResult
  section.py           analyze_dxf(path) -> SectionProperties
  tests/
    __init__.py
    fixtures/cs400_snapshot.json
    fixtures/w01.json, w02.json, wall_12x6.json
    fixtures/flush_cap.dxf      (copy of doc/flush cap.dxf)
    test_formula.py, test_layout.py, test_members.py, test_glazing.py,
    test_hardware.py, test_weights_validate.py, test_section.py
```

---

### Task 1: Types and formula evaluator

**Files:**
- Create: `onebook_fenestration/engine/__init__.py`, `onebook_fenestration/engine/types.py`, `onebook_fenestration/engine/formula.py`, `onebook_fenestration/engine/tests/__init__.py`
- Test: `onebook_fenestration/engine/tests/test_formula.py`

**Interfaces:**
- Produces, in `types.py` (all `@dataclass(frozen=True)` unless noted):
  - `ProfileSpec(code: str, name: str, kg_per_m: float, bar_lengths: tuple[float, ...])`
  - `MemberRule(id: str, role: str, profile: str, angles: tuple[int, int], length: str)`. `role` ∈ `frame|sash|mullion|transom`; `length` is a formula over `span, d_start, d_end`.
  - `HardwareRule(id: str, item: str, name: str, per: str, qty: str, uom: str = "Nos", when: str = "True", length: str | None = None, group: str = "Fabrication Hardware")`. `per` ∈ `frame_member|sash_member|mullion|sash|glass|window`.
  - `ValidationRule(id: str, when: str, severity: str, message: str, hint: str = "")`
  - `GlassSpec(code: str, name: str, thickness_mm: float)`
  - `SeriesSnapshot(code: str, version: str, deductions: dict[str, float], profiles: dict[str, ProfileSpec], member_rules: tuple[MemberRule, ...], hardware_rules: tuple[HardwareRule, ...], validation_rules: tuple[ValidationRule, ...], glasses: dict[str, GlassSpec], constants: dict[str, float])`, plus `@classmethod from_dict(cls, data: dict) -> "SeriesSnapshot"`
  - `CutMember(panel: str, role: str, position: str, profile: str, length: float, angles: tuple[int, int])`
  - `GlassPane(panel: str, number: int, glass: str, width: float, height: float)`
  - `BomLine(item: str, name: str, qty: float, uom: str, panel: str = "", position: str = "", length: float | None = None, group: str = "")`
  - `Issue(severity: str, code: str, message: str, panel: str = "", hint: str = "")`
  - `EngineResult(members: list[CutMember], glass: list[GlassPane], bom: list[BomLine], shutter_kg: dict[str, float], window_kg: float, area_m2: float, area_sqft: float, issues: list[Issue])` (not frozen)
  - Errors: `class EngineError(Exception)`, plus `DesignError`, `RuleError` and `SectionError` subclassing it.
- Produces, in `formula.py`: `evaluate(expr: str, variables: dict[str, float], rule_id: str) -> float | bool`. Allowed names are `ceil, floor, round, min, max, abs` plus the variables.

- [ ] **Step 1: Create branch and write failing tests**

```bash
git checkout -b feat/engine-core
```

```python
# test_formula.py
class TestFormula(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(evaluate("span - d_start - d_end", {"span": 457.5, "d_start": 18, "d_end": 5.5}, "r1"), 434.0)
    def test_math_funcs(self):
        self.assertEqual(evaluate("ceil(len/500)", {"len": 1220}, "r2"), 3)
    def test_bool(self):
        self.assertIs(evaluate("position == 'B'", {"position": "B"}, "r3"), True)
    def test_unknown_variable_names_rule(self):
        with self.assertRaises(RuleError) as cm:
            evaluate("foo + 1", {}, "hw_hole_cap")
        self.assertIn("hw_hole_cap", str(cm.exception)); self.assertIn("foo + 1", str(cm.exception))
    def test_syntax_error_names_rule(self):
        with self.assertRaises(RuleError):
            evaluate("len /", {"len": 1}, "r4")
    def test_snapshot_from_dict_roundtrip_minimal(self):
        s = SeriesSnapshot.from_dict({"code": "X", "version": "1", "deductions": {}, "profiles": {}, "member_rules": [], "hardware_rules": [], "validation_rules": [], "glasses": {}, "constants": {}})
        self.assertEqual(s.code, "X")
```

Note: `variables` may contain strings (e.g. `position`); the signature's `float` is the common case.

- [ ] **Step 2: Run tests; expect FAIL (ImportError)**

Run: `../../env/bin/python -m unittest discover -s onebook_fenestration/engine/tests -t . -v`

- [ ] **Step 3: Implement `types.py` and `formula.py`**

`evaluate` calls `safe_eval(expr, {"ceil": math.ceil, "floor": math.floor, "round": round, "min": min, "max": max, "abs": abs}, variables)` and wraps any exception in `RuleError(f"{rule_id}: {expr!r}: {exc}")`. `from_dict` converts the nested lists and dicts into the dataclasses; tuples come from lists.

- [ ] **Step 4: Run tests; expect PASS**

- [ ] **Step 5: Commit**

```bash
git add onebook_fenestration/engine
git commit -m "feat(engine): types and safe formula evaluator"
```

---

### Task 2: Design tree layout

**Files:**
- Create: `onebook_fenestration/engine/layout.py`
- Test: `onebook_fenestration/engine/tests/test_layout.py`

**Design JSON schema** (the contract Plan 3's designer writes):

```json
{"width": 915, "height": 1220, "series": "CS400", "finish": "GREY",
 "root": {"type": "split", "dir": "v", "at": [457.5],
          "children": [
            {"type": "sash", "opening": "out", "hinge": "left", "ghh": 732, "glass": "6CTG"},
            {"type": "sash", "opening": "out", "hinge": "right", "ghh": 732, "glass": "6CTG"}]}}
```

- Node types:
  - `split`: `dir` `v|h`; `at` holds centreline positions in mm measured from the cell's left (`v`) or bottom (`h`) edge; `len(at) == len(children) - 1`.
  - `sash`: carries `glass`.
  - `fixed`: carries `glass`.
  - `louver`: carries `glass`, `blades`.
- `root` is the frame interior; the frame itself is implicit.

**Interfaces:**
- Consumes: `DesignError` (Task 1).
- Produces:
  - `Cell(path: str, x: float, y: float, w: float, h: float, sides: dict[str, str], node: dict)`. `sides` maps `L/R/B/T` to `"frame"` or `"mullion"` (an adjacent split member).
  - `Bar(kind: str, id: str, length_span: float, ends: tuple[str, str])`. `kind` is `mullion` (from a `v` split) or `transom` (from an `h` split). `ends` are the adjacency types at each end: `"frame"`, `"mullion"` or `"transom"`.
  - `layout(design: dict) -> tuple[list[Cell], list[Bar]]`.
  - Leaf cells come out in tree order. Ids `M1..`/`T1..` are assigned in tree order.

- [ ] **Step 1: Write failing tests**

```python
def test_w01_two_cells(self):
    cells, bars = layout(load("w01.json"))
    self.assertEqual([(c.x, c.w, c.h) for c in cells], [(0, 457.5, 1220), (457.5, 457.5, 1220)])
    self.assertEqual(cells[0].sides, {"L": "frame", "R": "mullion", "B": "frame", "T": "frame"})
    self.assertEqual(cells[1].sides, {"L": "mullion", "R": "frame", "B": "frame", "T": "frame"})
    self.assertEqual(bars, [Bar("mullion", "M1", 1220, ("frame", "frame"))])
def test_nested_transom_ends_on_mullion(self):
    d = {"width": 1500, "height": 1500, "root": {"type": "split", "dir": "v", "at": [750], "children": [
        {"type": "fixed", "glass": "6CTG"},
        {"type": "split", "dir": "h", "at": [1000], "children": [{"type": "sash", "glass": "6CTG"}, {"type": "fixed", "glass": "6CTG"}]}]}}
    cells, bars = layout(d)
    self.assertEqual(len(cells), 3)
    self.assertEqual(bars[1], Bar("transom", "T1", 750, ("mullion", "frame")))
def test_bad_split_positions(self):
    for at in ([0], [915], [500, 400], []):
        d = {"width": 915, "height": 1220, "root": {"type": "split", "dir": "v", "at": at, "children": [{"type": "fixed"}, {"type": "fixed"}]}}
        with self.assertRaises(DesignError):
            layout(d)
```

- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement `layout`** as a recursive walk carrying `(x, y, w, h, sides)`. A `v` split at offset `a` creates a child cell whose right side is `"mullion"` and a next child whose left side is `"mullion"`. A bar's `ends` are the parent cell's sides perpendicular to the bar. Validate `at` (strictly increasing, inside `(0, span)`, correct count) and raise `DesignError(f"{path}: ...")` otherwise.
- [ ] **Step 4: Run; expect PASS**
- [ ] **Step 5: Commit** `feat(engine): design tree layout`

---

### Task 3: Cut members

**Files:**
- Create: `onebook_fenestration/engine/members.py`
- Create: `onebook_fenestration/engine/tests/fixtures/cs400_snapshot.json`, `w01.json`, `w02.json`
- Test: `onebook_fenestration/engine/tests/test_members.py`

**cs400_snapshot.json values.** Copy these verbatim. They come from context.md §3; mark the file `"version": "placeholder-from-eva-pdfs"`.
- `deductions`:
  - `{"bar_end_frame": 24, "bar_end_mullion": 24, "bar_end_transom": 24, "sash_side_frame": 18, "sash_side_mullion": 5.5, "sash_glass": 50.5, "fixed_glass_side_frame": 30, "fixed_glass_side_mullion": 30, "glazing_gasket": 14}`
  - `fixed_glass_*` = 30 is a **placeholder (K unknown)**. `bar_end_mullion` and `bar_end_transom` are placeholders.
- `profiles`:
  - `E104156` Cmt Outer 40x42, 0.649 kg/m, bars `[4880, 5800]`
  - `E104159` Cmt T Mullion 40x60, 0.809, `[4800, 5800]`
  - `E104160` Cmt Sash 40x64.5, 0.950, `[4800, 5800]`
  - `CS4807` Glazing Bead 23x20, 0.216, `[5800]`
- `member_rules`:
  - `frame` → `E104156`, `[45, 135]`, `"span"`
  - `sash` → `E104160`, `[45, 135]`, `"span - d_start - d_end"`
  - `mullion` → `E104159`, `[90, 90]`, `"span - d_start - d_end"`
  - `transom` → `E104159`, `[90, 90]`, `"span - d_start - d_end"`
- `glasses`: `6CTG` 6 MM CLEAR TOUGHNED GLASS 6; `5TGT` 5 MM TINTED GREY TG GLASS 5.
- `constants`: `{"glass_density": 2.5}`.

**Interfaces:**
- Consumes: `layout`, `Cell`, `Bar` (Task 2); `evaluate`, `SeriesSnapshot`, `CutMember`, `Issue` (Task 1).
- Produces: `cut_members(design: dict, snapshot: SeriesSnapshot, cells: list[Cell], bars: list[Bar]) -> tuple[list[CutMember], list[Issue], dict[str, tuple[float, float]]]`. The returned dict maps sash panel (`F1-S1`) to sash `(width, height)` for later tasks.
- Frame: 4 members `B, T` (span = width) and `L, R` (span = height), panel `F1`.
- Bars: panel `F1`, position `H` for a mullion and `W` for a transom. `d_start` and `d_end` = `deductions[f"bar_end_{end}"]`.
- Sash: 4 members, panel `F1-S{n}`. Width = `cell.w - sash_side_{sides.L} - sash_side_{sides.R}`, height uses `B`/`T`.
- A non-positive length yields `Issue("error", "non_positive_size", ..., panel)` and no member.

- [ ] **Step 1: Write failing tests (golden W01 from the EvA Design Assembly Detail PDF)**

```python
def test_w01_cut_list(self):
    m = compute_members("w01.json")  # helper: layout + cut_members
    got = sorted((x.panel, x.position, x.profile, x.length, x.angles) for x in m)
    self.assertEqual(got, sorted([
        ("F1", "B", "E104156", 915.0, (45, 135)), ("F1", "T", "E104156", 915.0, (45, 135)),
        ("F1", "L", "E104156", 1220.0, (45, 135)), ("F1", "R", "E104156", 1220.0, (45, 135)),
        ("F1", "H", "E104159", 1172.0, (90, 90)),
        *[(p, s, "E104160", 434.0, (45, 135)) for p in ("F1-S1", "F1-S2") for s in ("B", "T")],
        *[(p, s, "E104160", 1184.0, (45, 135)) for p in ("F1-S1", "F1-S2") for s in ("L", "R")]]))
def test_tiny_cell_gives_issue_not_crash(self):
    d = {"width": 60, "height": 1220, "root": {"type": "sash", "glass": "6CTG"}}
    members, issues, _ = run(d)
    self.assertTrue(any(i.code == "non_positive_size" for i in issues))
    self.assertEqual(len([x for x in members if x.panel == "F1"]), 4)
```

- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement `cut_members`**. Apply `round(length, 1)` once at `CutMember` creation.
- [ ] **Step 4: Run; expect PASS**
- [ ] **Step 5: Commit** `feat(engine): cut members from series rules`

---

### Task 4: Glazing and gaskets

**Files:**
- Create: `onebook_fenestration/engine/glazing.py`
- Test: `onebook_fenestration/engine/tests/test_glazing.py`

**Interfaces:**
- Consumes: `Cell` (Task 2), the sash sizes dict (Task 3), `SeriesSnapshot`, `GlassPane`, `BomLine`, `Issue`.
- Produces: `glaze(cells: list[Cell], sash_sizes: dict[str, tuple[float, float]], snapshot: SeriesSnapshot) -> tuple[list[GlassPane], list[BomLine], list[Issue]]`.
- Glass in a sash = sash − 2 × `sash_glass`. Fixed glass = cell − `fixed_glass_side_{side}` per side.
- Glass panel is `F1-S{n}` (sash) or `F1` (fixed); `number` counts 1..n in tree order.
- Gasket BomLines:
  - `G23` "GASKET 3MM": per pane, 2 pieces each of length `w − 2·glazing_gasket` and `h − 2·glazing_gasket`.
  - `G21` "FRAME GASKET CASEMENT": the 4 frame lengths, plus each sash's 4 lengths.

  Each BomLine has `qty = 1`, `length` = the cut length and `group = "Gasket"`.
- Louver leaves produce `blades` panes `cell.w − 2·fixed_glass_side × cell-blade-height`. That is out of scope for W02 golden values, so just emit an `Issue("warn", "louver_placeholder")`.

- [ ] **Step 1: Write failing tests**

```python
def test_w01_glass(self):
    panes = run_glaze("w01.json")[0]
    self.assertEqual([(p.panel, p.number, p.width, p.height) for p in panes],
                     [("F1-S1", 1, 333.0, 1083.0), ("F1-S2", 2, 333.0, 1083.0)])
def test_w01_glazing_gasket_lengths(self):
    bom = run_glaze("w01.json")[1]
    g23 = sorted(b.length for b in bom if b.item == "G23")
    self.assertEqual(g23, [305.0] * 4 + [1055.0] * 4)
```

- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement `glaze`**
- [ ] **Step 4: Run; expect PASS**
- [ ] **Step 5: Commit** `feat(engine): glass sizes and gaskets`

---

### Task 5: Hardware rules, weights, validation, `compute`

**Files:**
- Create: `onebook_fenestration/engine/hardware.py`, `weights.py`, `validate.py`, `engine.py`; fixture `wall_12x6.json`
- Modify: `onebook_fenestration/engine/tests/fixtures/cs400_snapshot.json` (add `hardware_rules` and `validation_rules`)
- Modify: `onebook_fenestration/engine/__init__.py` (export `compute`)
- Test: `onebook_fenestration/engine/tests/test_hardware.py`, `test_weights_validate.py`

**Hardware rules to add to the fixture.** Each was verified against both W01 and W02 in the EvA PDFs.

| id | item | per | when | qty |
|---|---|---|---|---|
| hw_corner_cleat | H401 | frame_member, sash_member | `position in ('B','T')` | `2` |
| hw_chevron | H266 | frame_member, sash_member | `position in ('B','T')` | `2` |
| hw_hole_cap | H912 | frame_member | `True` | `ceil(len/500)` |
| hw_drain_cap | H913 | frame_member | `position == 'B'` | `2` |
| hw_packer_1 | H904 | frame_member | `True` | `ceil(len/500)` |
| hw_packer_2 | H903 | frame_member | `True` | `ceil(len/500)` |
| hw_packer_3 | H902 | frame_member | `True` | `ceil(len/1000)` |
| hw_packer_5 | H901 | frame_member | `True` | `ceil(len/1000)` |
| hw_wall_fastener | H911 | frame_member | `True` | `ceil(len/500)` |
| hw_mullion_screw | H412 | mullion | `True` | `4` |
| hw_lifting_wedge | H411 | sash | `True` | `1` |
| hw_friction_stay | H416 (uom Pairs) | sash | `True` | `1` |
| hw_stay_screw | H429 | sash | `True` | `6` |
| hw_espag_handle | H425 | sash | `True` | `1` |
| hw_espag_1200 | H422C | sash | `True` | `1` |
| hw_locking_plate | H423 | sash | `True` | `2` |
| hw_glass_packer | H905 | glass | `True` | `8` |
| hw_masking_tape | H915 (uom m) | window | `True` | `1` with `length` = `round(2*perimeter_m, 3)` |
| hw_sealant | H914 (uom CAN) | window | `True` | `round(2*perimeter_m/6, 3)` |

Notes on the table:
- `per` with two values means two rule rows (`_frame`/`_sash` suffix on the id).
- Formula variables:
  - member rules: `len`, `position`, `role`
  - sash rules: `sash_w`, `sash_h`, `shutter_kg`
  - glass rules: `glass_w`, `glass_h`, `glass_t`
  - window rules: `W`, `H`, `perimeter_m` (= 2·(W+H)/1000), `window_kg`

**Validation rules to add:**
- `v_shutter_kg`: when `max_shutter_kg > 0 and shutter_kg > max_shutter_kg`, severity `error`, message `"Shutter {panel} weighs {shutter_kg} kg, above friction stay limit {max_shutter_kg} kg"`, hint `"Use a larger stay, add a transom, or split the sash"`.
- Add `constants.max_shutter_kg = 25` (**placeholder**; replace with Hilux's stay table).
- Messages use `str.format(**variables)`.

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces:
  - `hardware_bom(...) -> list[BomLine]`
  - `weights(members, panes, snapshot, sash_panels) -> tuple[dict[str, float], float]`
  - `validate(...) -> list[Issue]`
  - **`compute(design: dict, snapshot: SeriesSnapshot) -> EngineResult`**: the single entry point that Plan 2's API calls. Area = W·H/1e6 rounded to 3 dp; sq.ft = `round(area_m2 * 10.764, 3)`.
- Sash weight = Σ(its 4 sash members × kg/m) + its glass (w·h/1e6 × t × 2.5). Window weight = all members + all glass.

- [ ] **Step 1: Write failing tests**

```python
def totals(result):  # item -> summed qty
    ...
def test_w01_hardware_totals(self):
    t = totals(compute(load("w01.json"), SNAP).bom)
    self.assertEqual({k: t[k] for k in ["H401","H266","H912","H913","H904","H903","H902","H901","H911","H412","H411","H416","H429","H425","H422C","H423","H905"]},
        {"H401":12,"H266":12,"H912":10,"H913":2,"H904":10,"H903":10,"H902":6,"H901":6,"H911":10,"H412":4,"H411":2,"H416":2,"H429":12,"H425":2,"H422C":2,"H423":4,"H905":16})
def test_w01_consumables(self):
    bom = compute(load("w01.json"), SNAP).bom
    self.assertEqual(next(b.length for b in bom if b.item == "H915"), 8.54)
    self.assertEqual(next(b.qty for b in bom if b.item == "H914"), 1.423)
def test_w02_frame_hardware(self):   # 915 x 610, from W02 PDF
    t = totals(compute(load("w02.json"), SNAP).bom)
    self.assertEqual((t["H912"], t["H902"], t["H911"]), (8, 4, 8))
def test_w01_weights_match_eva(self):
    r = compute(load("w01.json"), SNAP)
    self.assertAlmostEqual(r.shutter_kg["F1-S1"], 8.489, delta=0.02)
    self.assertAlmostEqual(r.window_kg, 20.698, delta=0.02)
    self.assertEqual((r.area_m2, r.area_sqft), (1.116, 12.013))
def test_wall_12x6_shutter_fails_stay(self):
    r = compute(load("wall_12x6.json"), SNAP)   # 3638 x 1809, v-split at [1212.7, 2425.3]: sash|fixed|sash
    self.assertTrue(any(i.code == "v_shutter_kg" and i.panel == "F1-S1" for i in r.issues))
    self.assertAlmostEqual(r.shutter_kg["F1-S1"], 32.9, delta=0.2)
```

- `w02.json`: 915×610 frame. A `v` split at `[685]` (from the EvA elevation: 685 | 230); left child `louver` (`5TGT`, `blades: 9`), right child `fixed` (`6CTG`). Only frame-driven totals are asserted, because louver detail is a placeholder.
- In W02, `H412` = 8 in EvA because there are 2 mullions; our W02 fixture has 1, so do not assert `H412` for W02.

- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement `hardware_bom`, `weights`, `validate`, `compute`**. `compute` order: layout → cut_members → glaze → weights → hardware_bom → validate. It concatenates issues from every stage. A `DesignError` from layout propagates; nothing else raises.
- [ ] **Step 4: Run the full suite; expect PASS**
- [ ] **Step 5: Commit** `feat(engine): hardware, weights, validation and compute entry point`

---

### Task 6: DXF section analyzer

**Files:**
- Create: `onebook_fenestration/engine/section.py`; fixture `tests/fixtures/flush_cap.dxf` (copy of `doc/flush cap.dxf`)
- Modify: `pyproject.toml` (`dependencies = ["ezdxf~=1.4"]`), `onebook_fenestration/engine/__init__.py` (export `analyze_dxf`, `SectionProperties`)
- Test: `onebook_fenestration/engine/tests/test_section.py`

**Interfaces:**
- Produces:
  - `SectionProperties(area_mm2: float, width_mm: float, depth_mm: float, perimeter_mm: float, centroid: tuple[float, float], ix_mm4: float, iy_mm4: float, kg_per_m: float, loops: int, svg_path: str, warnings: tuple[str, ...])`
  - `analyze_dxf(path: str, layer: str | None = None) -> SectionProperties`. The `layer` argument filters entities when given.
- Units from `$INSUNITS`: `1` → ×25.4, `4` → ×1, `5` → ×10, `6` → ×1000. `0` or missing → ×1 plus the warning `"units_assumed_mm"`. Anything else raises `SectionError`.
- Closed `LWPOLYLINE`/`POLYLINE` entities are flattened with `ezdxf.path.make_path(e).flattening(0.01)` (inch drawings: flatten before scaling, so the distance is 0.01 drawing units). Loops contained in the largest loop are holes; others are added as separate solids.
- Area, centroid, Ix and Iy (about the centroid) come from the signed shoelace / second-moment polygon formulas summed over loops, with holes subtracted. Do not add shapely.
- `svg_path` is the outer and hole loops as `M x y L ... Z` in mm, translated to the bbox origin with y flipped.

- [ ] **Step 1: Write failing tests**

```python
def test_flush_cap_properties(self):
    p = analyze_dxf(fixture("flush_cap.dxf"))
    self.assertAlmostEqual(p.area_mm2, 1412.0, delta=1.0)
    self.assertAlmostEqual(p.width_mm, 154.3, delta=0.2)
    self.assertAlmostEqual(p.depth_mm, 48.0, delta=0.2)
    self.assertAlmostEqual(p.kg_per_m, 3.812, delta=0.005)
    self.assertEqual(p.loops, 2)
    self.assertTrue(p.svg_path.startswith("M"))
def test_rectangle_inertia(self):   # 40 x 20 mm, units mm, built with ezdxf in a tempdir
    p = analyze_dxf(make_rect_dxf(40, 20, insunits=4))
    self.assertAlmostEqual(p.ix_mm4, 40 * 20**3 / 12, delta=1)
    self.assertAlmostEqual(p.iy_mm4, 20 * 40**3 / 12, delta=1)
def test_units_missing_warns(self):
    self.assertIn("units_assumed_mm", analyze_dxf(make_rect_dxf(40, 20, insunits=0)).warnings)
def test_no_closed_loops(self):
    with self.assertRaises(SectionError):
        analyze_dxf(make_line_only_dxf())
```

- [ ] **Step 2: Install the dependency and run; expect FAIL**

Run: `../../env/bin/pip install "ezdxf~=1.4"`, then the test command. Expected: FAIL (ImportError on `section`).

- [ ] **Step 3: Implement `analyze_dxf`**
- [ ] **Step 4: Run the full suite; expect PASS**
- [ ] **Step 5: Commit** `feat(engine): DXF section analyzer` (stage `pyproject.toml` too)

---

## Done when

- The full suite passes.
- `compute(w01, cs400)` reproduces the EvA W01 cut list, glass, gaskets, all 17 hardware totals, consumables, weights (±0.02 kg) and area.
- The 12×6 ft wall example flags the shutter-weight error.
- `analyze_dxf` returns the flush-cap properties.
- No module under `engine/` imports anything from frappe except `frappe.utils.safe_exec`.
