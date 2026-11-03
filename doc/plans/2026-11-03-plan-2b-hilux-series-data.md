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

### Task 5: Profiles from Hilux DXF (blocked until DXFs arrive)

Starts when `Hilux EvA Profile Cutting Format CS400.dxf` and `…CS4800.dxf` exist in the client folder. The controller first inspects the DXFs (layers, blocks, one profile per block or per region, units) and writes this task's brief from what is actually there:
- each profile's code, name, area → kg/m (Al 6063 density constant from the series), perimeters, bar lengths;
- CS4800 profile list and member rules replacing the Task 4 placeholders;
- golden check: the 123 design from `doc/context.md` on CS4800.
