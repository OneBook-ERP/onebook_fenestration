# Plan 5: Production Outputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take a quoted project into production: Sales Order → BOM + batch → Work Order, a profile cutting plan with a 1D optimizer and wastage summary, and assembly summary/detail reports.

**Architecture:**
- The cutting optimizer is pure Python in `engine/cutting.py`, deterministic and DB-free (CLAUDE.md ground rule).
- Frappe glue lives in a new `production` module:
  - Sales Order hooks build one BOM per design line (D6);
  - a submittable **Cutting Plan** doctype batches Sales Orders, groups pieces by profile + finish and stores the optimizer result.
- Designs on submitted quotations or orders are locked so every production document matches what the customer accepted.

**Tech Stack:** Frappe v16, ERPNext v16 (BOM, Work Order, Batch), Jinja print formats, Vue 3 + frappe-ui (lock banner only).

**Spec:** `doc/context.md` (§3 "Cutting schedule facts" and "Report structures"; §ERPNext mapping), `doc/decisions.md` D6 (decided 2026-10-30), `doc/app-map.md` J4.

## Global Constraints

- **D6:**
  - Shared Item `FEN-WINDOW`; one BOM per Sales Order design line, set on `Sales Order Item.bom_no`. Never the Item's default BOM (`is_default` 0).
  - `FEN-WINDOW` becomes `is_stock_item` 1, `has_batch_no` 1, `create_new_batch` 1, so Work Order submit makes one batch per Work Order. Batch-wise valuation is ERPNext's default for new batches; do not override Stock Settings.
- **Cutting:**
  - Kerf 10 mm. One profile may use several stock bar lengths in the same job. Group by profile + finish.
  - "Rest" is a reusable offcut and "Waste" is scrap.
  - The wastage summary is per profile + finish: bars by length, pieces, mm, kg, % incl. and excl. rest, and kg/m.
- **Reports:** Assembly summary groups by W × H. Assembly detail lists each piece with Position (B/T/L/R/H/W) and Panel id (F1, F1-S1, F1-S1-G1).
- **Units:** profile Items are stocked in **Kg**, the unit their Item Price is already read in by `pricing/rates.py`. Gasket Items use **Meter**, glass **Square Meter**, and hardware its rule UOM.
- **Naming:** custom fields are prefixed `fen_` and go in `setup/custom_fields.py`. Settings go on `Fenestration Settings`.
- **Rules as data:** no series numbers in code. Kerf and minimum rest length are settings; bar lengths come from `Fenestration Profile.bar_lengths`.
- **Tests:** never modify or save existing dev-site records. Tests create their own data. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Out of scope** (Plan 6):
  - the SPA production board and bar diagrams;
  - Rest-offcut stock reuse in the optimizer;
  - Production Plan batching UI;
  - Job Card operations / routing.

## Review Focus

1. **A piece longer than every stock bar** (or a profile with an empty `bar_lengths`): the Cutting Plan still saves, lists the piece under "Unplaced", and the print shows it. It must not crash or drop the piece silently. Pinned by Task 1 `test_unplaced_piece` and Task 4 `test_unplaced_piece_is_reported`.
2. **Sales Order lines without a design** (FEN-TRANSPORT, manual lines): skipped by BOM creation and by the cutting plan. Pinned by Task 3 `test_transport_line_gets_no_bom` and Task 4 `test_non_design_lines_skipped`.
3. **Sales Order amended or re-submitted:** BOMs are reused when the design hash matches, so no duplicates. Pinned by Task 3 `test_amended_order_reuses_bom`.
4. **Sales Order qty differs from design qty:** the Sales Order qty is authoritative for Work Order and cutting. Pinned by Task 4 `test_order_qty_drives_piece_count`.
5. **Glass or profile without a linked Item:** Sales Order submit is refused with a message naming the codes, and no partial BOMs are left behind. Pinned by Task 3 `test_missing_glass_item_refuses_submit`.

---

### Task 1: 1D cutting optimizer (pure engine)

**Files:**
- Create: `onebook_fenestration/engine/cutting.py`
- Modify: `onebook_fenestration/engine/__init__.py` (export the new names)
- Test: `onebook_fenestration/engine/tests/test_cutting.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class Piece: length: float; label: str            # label e.g. "W01 F1-S1 T"
  @dataclass(frozen=True)
  class BarPlan: bar_length: float; pieces: tuple[Piece, ...]; used_mm: float; remainder_mm: float; is_rest: bool
  @dataclass
  class CuttingResult: bars: list[BarPlan]; unplaced: list[Piece]
  def optimize(pieces: list[Piece], bar_lengths: list[float], kerf: float = 10.0, min_rest: float = 500.0) -> CuttingResult
  def wastage(result: CuttingResult, kg_per_m: float) -> dict
  ```
  `wastage` keys: `bars` ({bar_length: count}), `bar_count`, `pieces`, `bar_mm`, `cut_mm`, `kerf_mm`, `rest_mm`, `waste_mm`, `kg_bars`, `kg_used`, `waste_pct_incl_rest`, `waste_pct_excl_rest`, `kg_per_m`.

**Rules the tests do not fully determine:**
- A bar fits its pieces when `Σ length + kerf × n ≤ bar_length` (each piece costs one kerf).
- `used_mm = Σ length + kerf × n`.
- `remainder = bar_length − used_mm`, and `is_rest = remainder ≥ min_rest`.
- `waste_mm` = non-rest remainders + all kerf.
- Percentages are of `bar_mm`, rounded to 2 dp; mm and kg are rounded to 3 dp.
- **Algorithm:**
  1. Sort pieces by (−length, label).
  2. First-fit-decreasing with best fit (the open bar with the smallest remainder that still fits; ties go to the earlier bar), opening new bars at the **longest** stock length.
  3. Shrink each bar to the **shortest** stock length that still fits its pieces.
- Pieces with `length + kerf` greater than the longest bar go to `unplaced`. Empty `bar_lengths` sends every piece to `unplaced`.
- Output is deterministic for the same input.

- [ ] **Step 1: Write the failing tests** in `test_cutting.py` (unittest, like the other engine tests):
  - `test_ffd_two_bars`: pieces 3000 "a", 3000 "b", 1500 "c", bars [6000] → 2 bars. Bar 0 holds a and c (used 4520, remainder 1480, is_rest True). Bar 1 holds b (used 3010, remainder 2990).
  - `test_shrinks_to_shortest_bar`: bars [4880, 5800], piece 4000 → one bar of 4880, remainder 870. Piece 5000 → one bar of 5800.
  - `test_mixed_lengths_one_profile`: bars [4880, 5800], pieces 5000 and 4000 → bar lengths {5800, 4880}.
  - `test_short_remainder_is_waste`: bars [6000], piece 5590 → remainder 400, is_rest False.
  - `test_unplaced_piece`: bars [5800], pieces 6000 and 1000 → unplaced holds the 6000 piece, and the 1000 piece is still placed. Empty bar_lengths → everything unplaced.
  - `test_deterministic`: the same input in shuffled order gives an equal result.
  - `test_wastage_summary`: for the `test_ffd_two_bars` result with kg_per_m 1.0:
    - bar_count 2, bars {6000: 2}, pieces 3;
    - bar_mm 12000, cut_mm 7500, kerf_mm 30, rest_mm 4470, waste_mm 30;
    - kg_bars 12.0, kg_used 7.5;
    - waste_pct_incl_rest 37.5, waste_pct_excl_rest 0.25.
- [ ] **Step 2: Run and watch them fail.** From the app dir run `/workspace/development/window-bench-16/env/bin/python -m unittest onebook_fenestration.engine.tests.test_cutting`. Expected: ImportError / FAIL.
- [ ] **Step 3: Implement** `cutting.py` per the rules above, and export `Piece`, `BarPlan`, `CuttingResult`, `optimize` and `wastage`.
- [ ] **Step 4: Run the engine suite.** Run `/workspace/development/window-bench-16/env/bin/python -m unittest discover -s onebook_fenestration/engine/tests -t .`. Expected: all OK (82 existing + new).
- [ ] **Step 5: Commit** with message `feat(engine): 1D cutting optimizer with kerf, rest and wastage summary`.

### Task 2: Sales Order fields, quotation mapping and design lock

**Files:**
- Modify: `onebook_fenestration/setup/custom_fields.py`
- Modify: `onebook_fenestration/fenestration/doctype/window_design/window_design.py`
- Modify: `onebook_fenestration/api/design.py` (add `copy_design`)
- Modify: the frontend designer view (lock banner + Copy). Find the view that calls `save_design`.
- Test: `onebook_fenestration/tests/test_design_lock.py`, plus a frontend vitest next to the designer tests.

**Interfaces:**
- Consumes: `quotation.design_hash(design) -> str` (exists), and `Quotation Item.fen_window_design` / `fen_design_hash` (exist).
- Produces:
  - Custom fields:
    - `Sales Order.fen_project` (Link Fenestration Project, read_only, insert_after `customer_name`);
    - `Sales Order Item.fen_window_design` (Link Window Design, read_only, insert_after `item_code`);
    - `Sales Order Item.fen_design_hash` (Data, read_only, hidden).
  - The names match the Quotation fields, so ERPNext's `make_sales_order` maps them.
  - `window_design.locking_document(design_name: str) -> tuple[str, str] | None` returns (doctype, name) of the first referencing document: a submitted (docstatus 1) Sales Order, or a submitted Quotation whose status is not "Lost".
  - `api.design.copy_design(name: str) -> str`: whitelisted; requires write on the project. It returns a new Window Design with the same inputs, `design_ref` = the first free of `"{ref}-R1"`, `"{ref}-R2"`, …
  - `get_design` response gains `locked_by: {doctype, name} | null`.

**Lock rule:** when `locking_document` is not None, `WindowDesign.validate` refuses changes to `design_json`, `series_version`, `finish`, `price_structure`, `qty` and `design_svg`, and refuses `flags.force_reprice`. The message is:

`"{design_ref} is on {doctype} {name}. Copy the design to change it."`

Location and design_name stay editable.

- [ ] **Step 1: Write the failing tests:**
  - `test_quotation_maps_design_fields_to_sales_order`: build a project and quotation like `test_quotation` does, submit the quotation, run `erpnext.selling.doctype.quotation.quotation.make_sales_order`. Then the Sales Order has `fen_project`, and each design line has `fen_window_design` and `fen_design_hash` equal to the quotation's.
  - `test_submitted_quotation_locks_design_inputs`: after submit, changing design_json raises a ValidationError containing "Copy the design", and changing `location` saves.
  - `test_lost_quotation_does_not_lock`: set the quotation status to Lost (`declare_enquiry_lost`), after which design_json can change.
  - `test_reprice_project_skips_or_reports_locked`: `reprice_project` reports locked designs in `failed`, with the lock message.
  - `test_copy_design_gets_next_ref`: the copy of W01 is "W01-R1", then "W01-R2". The copy is unlocked, has the same `design_json`, and has no quotation.
  - Frontend: when `locked_by` is set, the designer shows a frappe-ui Alert with the lock message and a "Copy design" button that calls `copy_design` and routes to the copy. Save is disabled.
- [ ] **Step 2: Run and watch them fail.** Run `bench --site window.localhost run-tests --app onebook_fenestration --module onebook_fenestration.tests.test_design_lock` and `cd frontend && yarn test`. Expected: FAIL.
- [ ] **Step 3: Implement.** Add the custom fields, then `bench --site window.localhost migrate`. Then add `locking_document`, the validate check, `copy_design`, `locked_by` in `get_design`, and the SPA banner.
- [ ] **Step 4: Run the suites.** Expected: the backend module plus `test_quotation`, `test_save_design` and `test_api` pass, and `yarn test && yarn build` pass.
- [ ] **Step 5: Commit** with message `feat: sales order design fields and lock designs on submitted quotations`.

### Task 3: Sales Order → BOM per design line (D6)

**Files:**
- Create: `onebook_fenestration/production/__init__.py`, `onebook_fenestration/production/bom.py`
- Modify: `onebook_fenestration/modules.txt` (add `Production`), `hooks.py` (`doc_events` "Sales Order": `before_submit`), `setup/install.py` (FEN-WINDOW flags; custom fields on BOM)
- Modify: `onebook_fenestration/series_studio/importer.py` (new profile Items use stock_uom "Kg")
- Create: `onebook_fenestration/patches/v0_1/production_item_setup.py` (registered in `patches.txt`)
- Test: `onebook_fenestration/tests/test_production_bom.py`

**Interfaces:**
- Consumes: `get_snapshot(series_version)`, `engine.compute(design_dict, snapshot) -> EngineResult` (members, bom, glass), `quotation.design_hash`, and the Task 2 Sales Order fields.
- Produces:
  - Custom fields `BOM.fen_window_design` (Link) and `BOM.fen_design_hash` (Data, hidden), both read_only.
  - `production.bom.bom_rows(design) -> list[dict]` returns BOM item rows `{item_code, qty, uom}` for one window (quantity 1), aggregated by item_code and sorted by item_code:
    - profiles: Σ member length / 1000 × `kg_per_m`, in Kg, 3 dp, item = `Fenestration Profile.item`;
    - gaskets: Σ BomLine length / 1000, in Meter;
    - hardware: Σ BomLine qty in its UOM;
    - glass: Σ pane area in m² (from `GlassPane`; see `engine/types.py`), item = `Fenestration Glass.item`.
    - It throws listing every profile or glass code without an Item.
  - `production.bom.ensure_bom(design_name: str, design_hash: str) -> str` reuses a submitted, active BOM with the same `fen_window_design` and `fen_design_hash`. Otherwise it creates and submits one (item FEN-WINDOW, quantity 1, is_default 0, is_active 1, `rm_cost_as_per` "Valuation Rate").
  - `production.bom.set_order_boms(doc, method=None)` is the Sales Order `before_submit` hook:
    - for every item with `fen_window_design`: check that `fen_design_hash` equals the current `design_hash` (else throw `"{ref} changed since the quotation. Requote before ordering."`);
    - set `item.bom_no = ensure_bom(...)`;
    - lines without a design are untouched.
- **Setup** (idempotent, in `after_migrate` and the patch):
  - FEN-WINDOW gets `is_stock_item` 1, `has_batch_no` 1, `create_new_batch` 1, `include_item_in_manufacturing` 0, but only when it has no Stock Ledger Entry. Otherwise leave it and log.
  - Profile Items (`fen_item_kind` "Profile") with stock_uom "Nos" and no Stock Ledger Entry or BOM Item reference are switched to "Kg".
  - Create UOMs "Kg", "Meter" and "Square Meter" if missing.

- [ ] **Step 1: Write the failing tests** (build their own project, design, quotation and order like Task 2's tests; use a test Customer and the `_Test Company` style setup already used in `test_quotation`):
  - `test_bom_rows_w01`:
    - rows are sorted by item_code;
    - the profile row qty for E104156 equals Σ(member lengths of E104156)/1000 × kg_per_m from the snapshot (compute the expected value in the test from `engine.compute`, not a literal);
    - gasket rows are in Meter, and the glass row is in m² equal to Σ pane areas.
  - `test_order_submit_creates_bom_per_design`: submit the Sales Order → each design line has a `bom_no`, and the BOM has `item` FEN-WINDOW, `is_default` 0, docstatus 1 and matching `fen_window_design`.
  - `test_transport_line_gets_no_bom`: the FEN-TRANSPORT line's `bom_no` stays empty.
  - `test_amended_order_reuses_bom`: cancel and amend the order, then submit the amendment → the same `bom_no`, and the BOM count for that design is still 1.
  - `test_changed_design_refuses_submit`: alter the line's `fen_design_hash` before submit → ValidationError "Requote before ordering".
  - `test_missing_glass_item_refuses_submit`: a design whose glass has no Item → ValidationError naming the glass code. No BOM exists for any line of that order (the hook runs in the submit transaction; assert via `frappe.db.count("BOM", {"fen_window_design": ...}) == 0` after rollback to a savepoint).
  - `test_work_order_from_order_uses_design_bom_and_batch`:
    - run `erpnext.selling.doctype.sales_order.sales_order.make_work_orders` for one line;
    - the Work Order's `bom_no` equals the line's;
    - after Work Order submit, one Batch exists with `reference_doctype` "Work Order", and `use_batchwise_valuation` is 1.
  - `test_setup_is_idempotent_and_respects_stock`: run setup twice → FEN-WINDOW flags set. A test profile Item with a Stock Ledger Entry keeps "Nos".
- [ ] **Step 2: Run and watch them fail.** Run `bench --site window.localhost run-tests --app onebook_fenestration --module onebook_fenestration.tests.test_production_bom`. Expected: FAIL.
- [ ] **Step 3: Implement.** Write `production/bom.py`, the hook, the setup and patch, and the importer UOM change. Then run `bench --site window.localhost migrate`.
- [ ] **Step 4: Run the full backend suite and the engine suite.** Expected: all pass, including the existing `test_quotation` (FEN-WINDOW being a stock item must not break quoting).
- [ ] **Step 5: Commit** with message `feat(production): bom per design line on sales order submit (D6)`.

### Task 4: Cutting Plan doctype and Profile Cutting Schedule

**Files:**
- Create the doctypes under `onebook_fenestration/production/doctype/`, created with `bench new-doctype`-equivalent JSON plus a migrate (no manual `mkdir` of doctype folders without the JSON):
  - `cutting_plan`
  - `cutting_plan_order` (child)
  - `cutting_plan_summary` (child)
- Create: `onebook_fenestration/production/cutting_plan.py` (pure glue: collect pieces → optimize → rows)
- Create: print format `onebook_fenestration/production/print_format/profile_cutting_schedule/` (on Cutting Plan)
- Modify: `Fenestration Settings` JSON, adding `cut_kerf_mm` (Float, default 10) and `min_rest_mm` (Float, default 500)
- Test: `onebook_fenestration/tests/test_cutting_plan.py`

**Interfaces:**
- Consumes: Task 1 `optimize`, `wastage`, `Piece`; Task 2 Sales Order Item `fen_window_design`; `get_snapshot`, `engine.compute`.
- Produces:
  - **Cutting Plan** (submittable, autoname `CUT-.YYYY.-.#####`). Fields:
    - `company`
    - `kerf_mm` and `min_rest_mm` (defaulted from settings)
    - `orders` (Table Cutting Plan Order: `sales_order` Link, docstatus-1 orders only)
    - `plan_json` (JSON, read_only, hidden)
    - `summary` (Table Cutting Plan Summary: `profile`, `finish`, `bars` (Data, e.g. "4880 × 3, 5800 × 2"), `bar_count`, `pieces`, `cut_mm`, `rest_mm`, `waste_mm`, `kg_bars`, `kg_used`, `waste_pct_incl_rest`, `waste_pct_excl_rest`, `kg_per_m`)
    - `unplaced_count` (Int)
  - `production.cutting_plan.collect_pieces(order_names: list[str]) -> dict[tuple[str, str], list[Piece]]` is keyed by (profile, finish). For each Sales Order Item with a design, it takes each member × the **Sales Order line qty**. The label is `"{design_ref} {panel} {position}"`, with `#k` appended for k > 1 copies.
  - `production.cutting_plan.build_plan(doc) -> None`: when the doc is draft, `validate` regenerates `plan_json` and `summary`. `plan_json` = `{"groups": [{profile, finish, bars: [{bar_length, pieces: [{length, label}], remainder_mm, is_rest}], unplaced: [...]}]}`, sorted by profile, finish.
  - Bar lengths are parsed from `Fenestration Profile.bar_lengths` ("4880, 5800").
- **Print "Profile Cutting Schedule":**
  - per group: a header (profile code and name, finish), then one table row per bar: bar length, cut list "label length", remainder and Rest/Waste;
  - an "Unplaced" block when present;
  - a wastage summary table at the end with the summary columns.
  - All text goes through `frappe.utils.escape_html`, matching the existing print formats.

- [ ] **Step 1: Write the failing tests:**
  - `test_groups_by_profile_and_finish`: two designs, same profiles, finishes GREY and BROWN-5104 → separate groups per (profile, finish).
  - `test_order_qty_drives_piece_count`: design qty 4, Sales Order line qty 2 → pieces per member = 2.
  - `test_non_design_lines_skipped`: a FEN-TRANSPORT line contributes nothing.
  - `test_summary_matches_engine_wastage`: for one group, the summary row equals `wastage(optimize(...), kg_per_m)`, rounded as stored.
  - `test_unplaced_piece_is_reported`: in-test, set a test profile's `bar_lengths` to "1000" → `unplaced_count` > 0, the plan saves, and the print HTML contains "Unplaced".
  - `test_submitted_plan_is_frozen`: after submit, `plan_json` does not change when settings kerf changes and the plan is reloaded.
  - `test_print_renders`: `frappe.get_print("Cutting Plan", name, "Profile Cutting Schedule")` contains the profile code, "Rest" and the wastage header.
- [ ] **Step 2: Run and watch them fail.** Run `bench --site window.localhost run-tests --app onebook_fenestration --module onebook_fenestration.tests.test_cutting_plan`. Expected: FAIL.
- [ ] **Step 3: Implement.** Create the doctypes, settings fields, glue and print format, then migrate.
- [ ] **Step 4: Run the full backend and engine suites.** Expected: all pass.
- [ ] **Step 5: Commit** with message `feat(production): cutting plan with optimizer and profile cutting schedule`.

### Task 5: Assembly summary and detail print formats

**Files:**
- Modify: `onebook_fenestration/fenestration/print_context.py`, `onebook_fenestration/utils/jinja.py`
- Create print formats (on Fenestration Project, module Fenestration):
  - `fenestration_assembly_summary`
  - `fenestration_assembly_detail`
- Modify: `frontend/src/components/QuotePanel.vue` or `print.ts`, adding both PDFs to the existing documents list
- Test: extend `onebook_fenestration/tests/test_print_formats.py`, plus vitest for the new links.

**Interfaces:**
- Consumes: `print_context._row(design)`-style data; `engine.compute` members (`panel`, `position`, `profile`, `length`, `angles`).
- Produces:
  - `print_context.assembly_summary(doc) -> list[dict]` groups the project's designs by (width, height). Each group has `width`, `height`, `refs` (comma-joined, ordered), `qty` (Σ design qty), `area_sqft` (Σ area × qty), `series`, `typology`. Groups are sorted by width desc, then height desc.
  - `print_context.assembly_detail(doc) -> list[dict]` has one block per design (`ref`, `name`, `qty`, `width`, `height`, `svg data uri`), each with `pieces` rows: `panel`, `position`, `profile`, `profile_name`, `length`, `angles` ("45/45"), `qty_per_window` (count of identical panel+position+profile+length). Pieces are sorted by panel, then position in the order B, T, L, R, H, W.
  - Jinja methods `fen_assembly_summary` and `fen_assembly_detail`.
  - Deleted or missing designs are skipped, as in `_quoted_row`.

- [ ] **Step 1: Write the failing tests:**
  - `test_assembly_summary_groups_same_size`: two designs both 1200 × 930 with qty 2 and 3, and one 600 × 600 → 2 groups. The first has refs "W01, W02", qty 5, and area = Σ.
  - `test_assembly_detail_positions_and_panels`: the W01 block has panel ids starting "F1", positions limited to {B, T, L, R, H, W}, and the order B before T.
  - `test_assembly_prints_render`: both formats render with `frappe.get_print("Fenestration Project", ...)` and escape a design name containing `<b>`.
  - vitest: the documents list includes "Assembly Summary" and "Assembly Detail" links through `download_pdf`.
- [ ] **Step 2: Run and watch them fail.** Run `bench --site window.localhost run-tests --app onebook_fenestration --module onebook_fenestration.tests.test_print_formats` and `cd frontend && yarn test`. Expected: FAIL.
- [ ] **Step 3: Implement** the helpers, jinja methods, print formats and SPA links.
- [ ] **Step 4: Run all suites** (backend, engine, `yarn test && yarn build`). Expected: all pass.
- [ ] **Step 5: Commit** with message `feat: assembly summary and detail print formats`.
