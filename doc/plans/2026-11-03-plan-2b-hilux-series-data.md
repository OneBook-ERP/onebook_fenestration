# Plan 2b: Real Hilux Series Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the reverse-engineered CS400 placeholder data with Hilux's own CS400 and CS4800 hardware, gasket and glass lists, and move the last hard-coded series data (gaskets) out of the engine.

**Architecture:**
- Gaskets become ordinary series hardware rules: the existing `HardwareRule` already supports `per`, `when`, `length` and `group`. The engine's `GASKETS` constant and its gasket loops are removed.
- Sash rule contexts expose the sash's design options (`hinge`, `handle`, `limiter`, `mesh`), so hardware choices are data (`when`) and not code.
- New series versions are snapshot JSON files under `onebook_fenestration/series_studio/data/`, loaded by the existing `import_snapshot_json`.
- Profile shapes and weights come later, from the DXF exports of Hilux's DWG files (Task 5, blocked until the DXFs arrive).

**Tech Stack:** pure Python engine, Frappe v16 doctypes and importer, Vue 3 + frappe-ui (sash options only).

**Spec:**
- `doc/Casement_Series_Designs_–_CS400_&_CS4800/` (git-ignored client files): `Hilux CS400 HARDWARE LIST.xls` (sheet CS400) and `Hilux CS4800 HARDWARE LIST.xls` (sheet CS4800): "Rule of Quantity" column plus per-typology counts (Fixed, Fixed with mullion, Single, Double, Triple open). The DWG profile cutting formats arrive as DXF later.
- `doc/context.md` (EvA rules, W01/W02/123 golden outputs), `doc/decisions.md` D3 (rules as data).
- Controller extract of both sheets: `/tmp/claude-1000/-workspace-development-window-bench-16-apps-onebook-fenestration/735fc85f-6c15-4a2c-9de3-1d160b46d7ee/scratchpad/hw_rules.txt`.

## Global Constraints

- **CLAUDE.md:** the engine is pure and deterministic, with no DB access. Series rules are data evaluated by the existing formula evaluator. Never hard-code series numbers or item codes in engine code.
- **Golden tests stay green:** W01 and W02 must still reproduce the EvA outputs in `doc/context.md`. Gasket lines must keep the same items, positions and lengths (G21 around frame and sashes; G23 4 lines per pane at `glass side − 2 × glazing_gasket`).
- **Client data:** never commit anything from `doc/Casement_Series_Designs_*/` or `doc/*.pdf`. The snapshot JSON files written by this plan contain rules and item codes only — no prices, no customer names.
- **Unclear Hilux rules:** take the per-typology counts from the sheet where given. Otherwise pick the narrowest reasonable rule, mark it in the rule's `note` field as `ASSUMPTION: …`, and list it in `doc/hilux-questions.md`.
- **Naming:** new doctype fields are prefixed only where they live on ERPNext doctypes (`fen_`). Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Tests never modify existing dev-site records.**

## Review Focus

1. **A glass with no matching glazing-gasket rule** (e.g. a new 10 mm glass): the design still computes and an issue names the glass, instead of silently skipping the gasket. Pinned by Task 1 `test_glass_without_gasket_rule_warns`.
2. **A DGU or laminated glass:** gasket choice uses the unit's total thickness, and weight uses only the glass thickness (`glass_mm`), not the air gap. Pinned by Task 3 `test_dgu_weight_ignores_air_gap`.
3. **Old saved designs without the new sash options:** they compute with series defaults and unchanged results. Pinned by Task 2 `test_missing_sash_options_use_defaults`.
4. **Re-importing a series version:** existing published versions are never modified; a new version is created and existing designs stay on the old one. Pinned by Task 4 `test_reimport_creates_new_version`.
5. **A rule naming an Item that doesn't exist:** import creates the Item with the right kind and UOM rather than failing halfway. Pinned by Task 4 `test_import_creates_missing_hardware_items`.

---

### Task 1: Gaskets as series data (engine)

**Files:**
- Modify: `onebook_fenestration/engine/glazing.py`, `onebook_fenestration/engine/hardware.py`, `onebook_fenestration/engine/types.py` (add `note: str = ""` to `HardwareRule`)
- Modify: `onebook_fenestration/engine/tests/fixtures/cs400_snapshot.json` (add the gasket rules)
- Test: `onebook_fenestration/engine/tests/test_glazing.py` (or the existing glazing/golden test files)

**Interfaces:**
- Produces:
  - Hardware rule contexts gain `per: "frame_side"` (one context per side of the outer frame and of each sash: variables `side_len`, `position` B/T/L/R, `panel`) and `per: "pane_side"` (one per side of each glass pane: `side_len`, `position` W/H, `glass_t`, `glass`, `panel`).
  - `glaze()` no longer emits gasket BomLines; it returns panes and issues only.
  - `GASKETS` is deleted.
  - When a pane gets no BomLine of group "Gasket" from any rule, the engine adds `Issue("warn", "no_glazing_gasket", "{panel}: no glazing gasket rule for glass {code}")`.
- Fixture rules that reproduce today's output exactly:
  - G21 "FRAME GASKET CASEMENT": `per frame_side`, qty `1`, length `side_len`, group `Gasket`, uom `Nos`.
  - G23 "GASKET 3MM": `per pane_side`, qty `1`, length `side_len - 2*glazing_gasket`, group `Gasket`, when `glass_t >= 5 and glass_t <= 6` (ASSUMPTION note), and it must yield W, W, H, H (each pane side once).

- [ ] **Step 1: Write the failing tests:**
  - `test_gaskets_come_from_rules`: with the fixture's gasket rules removed, W01 has no G21/G23 lines (proves no hard-coding). With them, W01's gasket lines equal the current golden lines (item, panel, position, length, in the same order).
  - `test_glass_without_gasket_rule_warns`: a pane of a glass whose thickness no rule matches → issue `no_glazing_gasket` naming the glass, other output unchanged.
  - `test_rule_note_is_optional`: a rule dict with and without `note` both load.
- [ ] **Step 2: Run** `/workspace/development/window-bench-16/env/bin/python -m unittest discover -s onebook_fenestration/engine/tests -t .` from the app dir. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** Keep `pricing.py`'s gasket costing working (it reads `group == "Gasket"` and `length`).
- [ ] **Step 4: Run** the engine suite and the backend suite. Expected: all pass, W01/W02 golden unchanged.
- [ ] **Step 5: Commit** `refactor(engine): gaskets as series hardware rules`.

### Task 2: Sash hardware options

**Files:**
- Modify: `onebook_fenestration/engine/hardware.py` (sash context), `onebook_fenestration/engine/types.py` (series option defaults)
- Modify: `frontend/src/design/types.ts`, `frontend/src/components/PropertiesPanel.vue`
- Test: engine tests + `frontend/src/components/PropertiesPanel.spec.ts`

**Interfaces:**
- Produces:
  - `SashNode` gains optional `hinge: "friction" | "butt"`, `handle: "multipoint" | "single"`, `limiter: boolean`, `mesh: boolean`. (`hinge` already exists for side; rename the side field only if it clashes — read `design/types.ts` and the engine first and record the decision.)
  - Sash rule contexts add these four variables, filled from the design node, else from series constants `default_hinge`, `default_handle`, `default_limiter`, `default_mesh`.
  - The PropertiesPanel shows them for a selected sash as frappe-ui Selects/Checkboxes.

- [ ] **Step 1: Write the failing tests:**
  - `test_sash_options_reach_rules`: a rule `when: "handle == 'single'"` fires only for a sash with `handle: "single"`.
  - `test_missing_sash_options_use_defaults`: W01 (no options) computes exactly as before with constants set to `friction`/`multipoint`/False/False.
  - vitest: selecting a sash shows Hinge, Handle, Opening limiter and Fly mesh controls; changing Handle updates the design node.
- [ ] **Step 2: Run** and watch them fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** engine, backend and `yarn test && yarn build`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: sash hardware options as rule inputs`.

### Task 3: Glass catalogue with weight thickness

**Files:**
- Modify: `onebook_fenestration/engine/types.py` (`GlassSpec.glass_mm: float | None`), `onebook_fenestration/engine/weights.py`
- Modify: Fenestration Glass doctype (add `glass_mm` Float, "Glass thickness for weight (mm)"), `series_studio/snapshot.py`, `series_studio/importer.py`
- Test: engine weights tests, `onebook_fenestration/tests/test_snapshot.py`

**Interfaces:**
- Produces:
  - `thickness_mm` stays the overall unit thickness (used for gasket choice); `glass_mm` is the total glass in the unit (DGU 6+12+6 → 12, laminated 6+6 → 12). Weight uses `glass_mm` when set, else `thickness_mm`.
  - The 21 Hilux glasses as a catalogue file `onebook_fenestration/series_studio/data/hilux_glasses.json`: code (short, uppercase, e.g. `5CTG`, `24DGU-6C12-6C`), name as in the sheet, `thickness_mm`, `glass_mm`. Laminated interlayer thickness (0.76/1.52/2.28) counts in `thickness_mm` but not in `glass_mm`.

- [ ] **Step 1: Write the failing tests:**
  - `test_dgu_weight_ignores_air_gap`: a 1000 × 1000 DGU 6+12+6 pane weighs the same as a 12 mm monolithic pane.
  - `test_glass_mm_defaults_to_thickness`: existing 6CTG weight unchanged.
  - `test_catalogue_is_complete`: the JSON has 21 entries with unique codes, every `glass_mm <= thickness_mm`.
- [ ] **Step 2: Run** and watch them fail.
- [ ] **Step 3: Implement**, then `bench --site window.localhost migrate`.
- [ ] **Step 4: Run** engine + backend suites. Expected: all pass.
- [ ] **Step 5: Commit** `feat: glass catalogue with weight thickness`.

### Task 4: CS400 v2 and CS4800 v1 rule data + import

**Files:**
- Create: `onebook_fenestration/series_studio/data/cs400_v2.json`, `onebook_fenestration/series_studio/data/cs4800_v1.json`
- Create: `doc/hilux-questions.md`
- Modify: `onebook_fenestration/series_studio/importer.py` (glass catalogue, `note`, item kinds/UOMs for Gasket and Hardware rows)
- Test: `onebook_fenestration/engine/tests/test_series_data.py`, `onebook_fenestration/tests/test_series_import.py`

**Interfaces:**
- Consumes: Tasks 1–3 rule contexts and fields.
- Produces:
  - Both files use the existing snapshot shape. Profiles, member rules and deductions are copied from today's CS400 fixture for CS400 v2, and are **placeholders** for CS4800 (copied from CS400, every one noted `PLACEHOLDER until DXF`).
  - Hardware rules translate every row of the Hilux sheet. Where the sheet gives per-typology counts, the rule must reproduce them for Fixed, Fixed with mullion, Single, Double and Triple open windows of 1200 × 1200.
  - Door-only rows (CS4800 H402 door, H415, H418–H421, H424) are imported with `when: "False"` and note `door — no door typology yet`.
  - `doc/hilux-questions.md` lists every `ASSUMPTION`, grouped by item, each as a yes/no or pick-one question.
  - `import_snapshot_json` creates missing Items with kind Gasket (uom Meter) / Hardware (rule uom) and never edits existing Items or published versions.

- [ ] **Step 1: Write the failing tests:**
  - `test_typology_counts_match_sheet` (parametrised over both series and every row with counts): build the five reference designs at 1200 × 1200, compute, and compare each item's total qty with the sheet's count (the expected counts are typed into the test from the sheet, not read from the XLS).
  - `test_every_sheet_row_has_a_rule`: the set of item codes in each JSON equals the sheet's code list (typed into the test).
  - `test_w01_golden_on_cs400_v2`: W01 on CS400 v2 still matches the EvA golden output for the items EvA listed.
  - `test_reimport_creates_new_version`, `test_import_creates_missing_hardware_items`.
- [ ] **Step 2: Run** and watch them fail.
- [ ] **Step 3: Write the JSON files and questions doc; extend the importer.**
- [ ] **Step 4: Run** engine + backend suites. Expected: all pass.
- [ ] **Step 5: Commit** `feat(series): Hilux CS400 v2 and CS4800 v1 hardware, gasket and glass rules`.

### Task 5: CS4800 profiles, beads and adaptors from the Hilux DXF

The DXFs arrived. The controller inspected them: profile shapes are loose LINE/ARC entities on layer `0` (no closed polylines, no per-profile blocks), so `engine/section.py` cannot compute areas from them. Every number this task needs is TEXT/MTEXT in the drawings, already extracted below, plus EvA's own output for design 123 (from the git-ignored Design Assembly Detail PDF). Do not open the client folder or the PDFs; use only the values in this brief.

**Files:**
- Modify: `onebook_fenestration/engine/types.py`, `onebook_fenestration/engine/members.py` (and/or a new `engine/glazing_members.py`), `onebook_fenestration/engine/glazing.py` only if needed
- Modify: `onebook_fenestration/series_studio/data/cs4800_v1.json` → **create `cs4800_v2.json`** (v1 stays as the record of what was imported; the importer's data list loads v2 instead of v1 for CS4800)
- Create: `onebook_fenestration/series_studio/data/hilux_profile_perimeters.json`
- Modify: `onebook_fenestration/series_studio/data/__init__.py`, `onebook_fenestration/series_studio/importer.py`, the Series Member Rule doctype (add `when`, Small Text, optional), `onebook_fenestration/series_studio/snapshot.py` if it builds MemberRule
- Create: `onebook_fenestration/engine/tests/fixtures/d123.json`
- Modify: `onebook_fenestration/engine/tests/test_series_data.py`, `onebook_fenestration/tests/test_series_import.py`, `doc/hilux-questions.md`, `doc/decisions.md`

**DXF profile table** (Section Details sheet; columns: code, standard bar, kg/m, anodised perimeter mm, powder-coat perimeter mm — the two perimeter columns are equal in every row):

| Code | Name (use EvA's where given) | Bar | kg/m | Perimeter | Role |
|---|---|---|---|---|---|
| CS4801 | CMT WINDOW OUTER 48MM X 45.5MM | 5800 | 0.732 | 234 | frame |
| CS4802 | CMT WINDOW MULLION 40MM X 64MM | 5800 | 0.88 | 273 | mullion |
| CS4803 | CMT WINDOW SHUTTER 48MM X 70MM | 5800 | 0.942 | 303 | sash |
| CS4804 | 48MM CASEMENT DOOR SHUTTER | 5800 | 1.20 | 337 | accessory (door, unused) |
| CS4805 | 48MM CASEMENT DOOR FRAME | 5800 | 0.92 | 278 | accessory (door, unused) |
| CS4806 | 48MM CASEMENT DOOR MULLION | 5800 | 1.05 | 316 | accessory (door, unused) |
| CS4807 | GLAZING BEAD 23MM X 20MM (5, 6 & 8 mm glass) | 5800 | 0.216 | 140 | bead |
| CS4808 | GLAZING BEAD 16MM X 20MM (12 & 13.5 mm glass) | 5800 | 0.216 | 139 | bead |
| CS4809 | GLAZING BEAD (24 mm glass) | 5800 | 0.19 | 98 | bead |
| CS4810 | CASEMENT MESH SHUTTER | 5800 | 0.53 | 199 | accessory |
| CS4811 | GRILL MESH FRAME | 5800 | 0.637 | 181 | accessory |
| CS4812 | FLYING MULLION | 5800 | 0.713 | 235 | accessory |
| CS4813 | DOOR BOTTOM ADAPTOR | 3660 | 0.21 | 120 | accessory (door, unused) |
| CS4814 | THRESHOLD | 3660 | 0.23 | 130 | accessory (door, unused) |
| HSL3409 | SINGLE GLASS ADAPTOR | 5800 | 0.21 | 127 | bead (sash glass adaptor) |
| HSL3410 | SLD LAMINATED GLASS ADAPTOR 28.9MM X 16.8MM (12 mm / laminated) | 5800 | 0.21 | 127 | bead (sash glass adaptor) |
| E104157 | MESH INTERLOCK | 4880 | 0.434 | 120 | accessory |

The DXF table prints the descriptions of CS4801 and CS4802 swapped ("mullion" next to CS4801). EvA's reports and the DXF cutting lists both use CS4801 = frame (0.732) and CS4802 = mullion (0.880): follow those, and add a question.

CS400 profile perimeters from the CS400 DXF: E104156 202, E104159 269, E104160 282, E104161 150, CS4807 140, CS4808 139, CS4809 98. The CS400 DXF also gives bar lengths 4880 + 5800 for E104159 and E104160, while CS400 v2 (from EvA) has 4800 + 5800 — do NOT change CS400 data; add a question.

**DXF cutting formulas (CS4800):** frame W/H 45°; mullion `H-(25.5*2)` 90°; fixed bead horizontal `W-(25.5*2)` (single fixed), vertical `H-((25.5+20)*2)` 90°; fixed glass `W-((25.5*2)+8)`, `H-((25.5*2)+8)`; sash `W-(18.5*2)`, `H-(18.5*2)` 45°; sash glass `HS-((52.7*2)+8)`.

**EvA golden design 123** (CS4800, 1500 × 1500, glass 12 mm reflective toughened; one fixed pane F1-G1 and one outward sash F1-S1 separated by one vertical mullion; take the mullion at 750). EvA output:
- CS4801 frame: 1500 × 4 (B, T, R, L), 45°/135°
- CS4802 mullion: 1449 × 1, 90°/90°
- CS4803 sash F1-S1: 727 (B, T), 1463 (R, L), 45°/135°
- CS4808 bead F1-G1: 713 (T, B), 1409 (L, R), 90°/90°
- HSL3410 adaptor F1-S1-G2: 621 (B, T), 1357 (R, L), 45°/135°
- glass F1-G1 705 × 1441; glass F1-S1-G2 613 × 1349
- weights: window 66.829 kg, shutter S1 29.766 kg (profiles + glass at 2.5 kg/m²/mm; hardware ignored)
- for reference only (not asserted; CS4800 hardware follows the Hilux sheet per D10): G29 673/1409 on F1-G1, G23 673/1409 on F1-G1 and 587/1323 ×2 on F1-S1-G2, G21 on frame, sash and mullion (1449 ×2).

Deductions that reproduce it (EvA wins over the DXF where they differ by rounding — note each `CHECK`): `bar_end_*` 25.5; `sash_side_frame` 18.5, `sash_side_mullion`/`_transom` 4.5; `sash_glass` 57 (DXF 52.7 + 4 = 56.7); `fixed_glass_side_frame` 29.5, `fixed_glass_side_mullion`/`_transom` 15.5 (DXF implies 16.6 per side for two fixed panes); `glazing_gasket` keep the v1 value unless a CS4800 gasket rule uses it.

**Interfaces:**
- Produces:
  - `MemberRule` gains `when: str = ""` (empty = always). It is evaluated with the same formula evaluator and the member's context; a rule whose `when` is false yields no member.
  - Two new member roles driven by glass panes:
    - `bead` — one member per side of each **fixed** pane: variables `opening_w`, `opening_h` (pane glass size + 2 × `glass_clearance`), `position` (T/B/L/R), `glass_t`, `glass`. 123 uses `length` = `opening_w` for T/B and `opening_h - 2*bead_depth` for L/R (`bead_depth` 20 and `glass_clearance` 4 are series constants).
    - `glass_adaptor` — one member per side of each **sash** pane, same variables; 123 uses `length` = `opening_w` / `opening_h`, angles 45/135.
  - Bead / adaptor members carry the pane's panel id (`F1-G1`, `F1-S1-G2`, matching EvA's panel naming used elsewhere in the engine) and count in profile weight, shutter weight (adaptor belongs to its sash), cutting list and BOM like any other member.
  - CS4800 v2 member rules choose the profile by `when` on `glass_t` (bead: 5–8 → CS4807, 12–13.5 → CS4808, 24 and DGU 20–28 → CS4809; adaptor: 12–13.5 and laminated → HSL3410, single 5–8 → HSL3409, DGU → none). Ranges not in the DXF are `ASSUMPTION` notes + questions.
  - Series without bead/adaptor rules (CS400 v1, CS400 v2) produce exactly today's output.
  - `hilux_profile_perimeters.json`: `{code: {"perimeter_mm": n}}` for both series. `import_hilux_series` fills `visible_perimeter_mm` on Fenestration Profile **only where it is empty/0**, never overwrites, and the file is NOT part of any series `source_hash`. `total_perimeter_mm` stays untouched (question: is the DXF value visible or total?).
  - The `CS4800-PH-*` placeholders are gone from v2; the `placeholders` key is removed.
- [ ] **Step 1: Write the failing tests:**
  - engine `test_123_golden_on_cs4800_v2`: every profile cut above (code, panel, position, length, angles, count), both glass sizes, window kg 66.829 ± 0.005, shutter kg 29.766 ± 0.005.
  - engine `test_bead_profile_follows_glass_thickness`: the 123 fixed pane with 6 mm glass gets CS4807, with 24 mm DGU gets CS4809; sash with 6 mm gets HSL3409.
  - engine `test_member_rule_when_false_yields_nothing` and `test_cs400_has_no_bead_members` (W01/W02 unchanged).
  - backend `test_member_rule_when_imports`, `test_perimeters_fill_only_empty` (a profile with a perimeter keeps it; one with 0 gets the DXF value; uses its own test profile codes, never existing dev records).
  - Existing `test_typology_counts_match_sheet` for CS4800 still passes on v2 (hardware rules carried over unchanged).
- [ ] **Step 2: Run** engine + backend suites; the new tests fail.
- [ ] **Step 3: Implement** engine roles + `when`, doctype field + importer + snapshot, `cs4800_v2.json`, perimeters file. Update `doc/hilux-questions.md` (CS4801/CS4802 label swap; CS400 4800 vs 4880 bars; perimeter visible vs total; every CHECK deduction; bead/adaptor ranges; the CS400 DXF drawing sheet titled "series = CS4800") and `doc/decisions.md` (D11: bead and adaptor are glass-driven member rules).
- [ ] **Step 4: Run** engine, backend and frontend suites. Expected: all pass.
- [ ] **Step 5: Commit** `feat(series): CS4800 v2 profiles, glazing beads and adaptors from Hilux DXF`.
