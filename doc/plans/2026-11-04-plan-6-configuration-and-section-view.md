# Plan 6: Configured Dev Site, Rate Sheets and Cross-Section View — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the CS400/CS4800 casement model fully configurable and checkable on a site (rates, readiness, profile perimeters that stick), and add the cross-section view (A-A / B-B) the client uses in their German software to the Window Designer.

**Architecture:**
- Rates stay ERPNext Item Prices on the Fenestration Settings cost price list. A rate-sheet template (xlsx) lists every item the published series versions use; importing it upserts Item Prices. A per-version readiness report lists what still blocks quoting.
- Profile section outlines come from the Hilux DXF section tables (loose LINE/ARC, not closed polylines). A bench-run importer reads the client DXF from disk and stores an SVG outline per profile in the DB. Shapes are never committed to the repo.
- The cross-section is computed by a pure engine function from the design layout, deductions and per-profile section widths, and drawn by a new Vue component in the designer, styled like the client's sample: elevation with cut markers, each cut drawn as profile outlines with glass and a dimension chain.

**Tech Stack:** pure Python engine, Frappe v16 doctypes and whitelisted APIs, `openpyxl` (already a Frappe dependency) for xlsx, `ezdxf` (in the bench env) for DXF, Vue 3 + TS + frappe-ui SVG component.

**Spec:**
- User requests (2026-11-04): "configure the given model fully"; "they wanted to have that cross section view in the design panel".
- Client sample: `doc/German app files/Cross section Drawing.pdf` (git-ignored, contains client data — do not copy names or projects). Page 1: elevation with cut markers A–A (vertical cut) and B–B (horizontal cut); B–B drawn below the elevation as a horizontal strip, A–A drawn to its right as a vertical strip; profile outlines in black with profile codes, gaskets red, glass cyan; dimension chains along each strip (profile faces, glass/daylight sizes, overall); hardware and glass list underneath.
- Competitor notes: `doc/competitor-logikal.md` (written alongside this plan).
- `doc/decisions.md` D3 (rules as data), D11 (beads/adaptors as member rules).

## Global Constraints

- **CLAUDE.md:** engine pure and deterministic, no DB access; never hard-code series numbers or item codes in engine code.
- **Golden tests stay green:** W01, W02 (CS400) and 123 (CS4800 v2) outputs unchanged.
- **Client data:** never commit anything from `doc/Casement_Series_Designs_*/`, `doc/German app files/` or `doc/*.pdf`, nor profile outline geometry extracted from them. Tests build their own synthetic DXF with `ezdxf`.
- **Tests never modify existing dev-site records**; use own codes (`TST…`) inside IntegrationTestCase rollback.
- **No invented rates:** nothing in code, tests or setup writes placeholder prices onto the real cost price list.
- **UI:** frappe-ui components; layout works at 390 px phone width without horizontal page scroll.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01WEzM9w52GGMhhHoe9Pgdok`.

## Review Focus

1. **A rate sheet row for an unknown item code or a non-numeric rate:** the import skips it and lists it in the result; no partial silent writes. Pinned by Task 2 `test_import_reports_bad_rows`.
2. **Re-importing the same sheet:** no duplicate Item Prices; an unchanged rate is a no-op, a changed rate updates the price for that `valid_from`. Pinned by Task 2 `test_reimport_is_idempotent`.
3. **A profile with no outline in the DB:** the cross-section still draws, using a labelled rectangle of the profile's face width, and says which profiles lack outlines. Pinned by Task 5 `test_missing_outline_falls_back_to_box` (frontend) and Task 4 `test_cut_reports_missing_widths`.
4. **A cut line through a mullion or transom position, or outside the frame:** the cut snaps to the nearest cell centre and never returns an empty strip. Pinned by Task 4 `test_cut_position_snaps_to_cell`.
5. **Saving a profile in Desk without a DXF:** commercial perimeters survive. Pinned by Task 1 `test_save_without_dxf_keeps_perimeters`.

---

### Task 1: Profile perimeters survive saves

**Files:**
- Modify: `onebook_fenestration/series_studio/doctype/fenestration_profile/fenestration_profile.py`
- Test: `onebook_fenestration/series_studio/doctype/fenestration_profile/test_fenestration_profile.py` (create if missing; else the existing profile test module)

**Interfaces:**
- Produces: `SECTION_FIELDS` no longer contains `total_perimeter_mm`. Geometry is cleared only when `dxf_file` changes from a value to empty (`has_value_changed("dxf_file")`), not on every save without a DXF. Uploading a DXF still sets `total_perimeter_mm` from the analysed perimeter (explicit user action). `visible_perimeter_mm` and `total_perimeter_mm` are never cleared by the controller.

- [ ] **Step 1: Failing tests:** `test_save_without_dxf_keeps_perimeters` (profile `TSTP1` with visible 90 / total 202 and no DXF; save twice; both values unchanged); `test_save_without_dxf_keeps_outline` (a `section_svg` set by the Task 3 importer, no `dxf_file`, survives save); `test_removing_dxf_clears_geometry_not_perimeters`.
- [ ] **Step 2: Run** `cd /workspace/development/window-bench-16 && bench --site window.localhost run-tests --module onebook_fenestration.series_studio.doctype.fenestration_profile.test_fenestration_profile` — FAIL.
- [ ] **Step 3: Implement** in `FenestrationProfile.validate`.
- [ ] **Step 4: Run** the module, then the full backend suite — PASS.
- [ ] **Step 5: Commit** `fix(profile): keep perimeters and imported outlines when saving without a DXF`.

### Task 2: Rate sheet template and import

**Files:**
- Create: `onebook_fenestration/pricing/rate_sheet.py`
- Modify: `onebook_fenestration/pricing/doctype/fenestration_settings/fenestration_settings.js` (two buttons)
- Test: `onebook_fenestration/tests/test_rate_sheet.py`

**Interfaces:**
- Produces (whitelisted, System Manager or Fenestration Engineer only):
  - `rate_sheet_rows(series_versions: list[str] | None = None) -> list[dict]`: one row per distinct item used by the given (default: all submitted, non-cancelled) Series Versions — profile items (via Fenestration Profile.item), glass items (via Fenestration Glass.item), and hardware/gasket rule items. Row keys: `item_code`, `item_name`, `kind` (Profile/Glass/Hardware/Gasket), `uom` (stock uom), `rate_basis` (`per kg` for profiles, `per m2` for glass, `per <uom>` otherwise — matches `rates._item_prices` ruling), `current_rate` (from the cost price list or blank), `series` (comma list of series codes).
  - `download_rate_sheet()` → xlsx file response with those rows; columns in that order plus an empty `new_rate` and `valid_from`.
  - `import_rate_sheet(file_url: str) -> dict`: reads the xlsx; for every row with a numeric `new_rate` > 0 upserts an Item Price on `Fenestration Settings.cost_price_list` (`price_list_rate`, `uom` = stock uom, `valid_from` from the row or today; same item + price list + valid_from → update, else insert). Returns `{"created": n, "updated": n, "unchanged": n, "skipped": [{"row": i, "item_code": c, "reason": r}]}`. Unknown item codes, non-numeric or ≤ 0 rates are skipped with a reason. Throws if no cost price list is configured.
- Desk: Fenestration Settings gets "Download rate sheet" and "Import rate sheet" (file upload then a result dialog listing counts and skipped rows).

- [ ] **Step 1: Failing tests** (own test price list and `TST` items; set `cost_price_list` inside the test transaction): `test_rows_cover_profiles_glass_and_rule_items`, `test_import_creates_and_updates`, `test_reimport_is_idempotent` (second import → all `unchanged`, Item Price count unchanged), `test_import_reports_bad_rows`, `test_import_requires_price_list`, `test_rate_sheet_needs_role` (Guest/plain user → PermissionError).
- [ ] **Step 2: Run** `bench --site window.localhost run-tests --module onebook_fenestration.tests.test_rate_sheet` — FAIL.
- [ ] **Step 3: Implement** `rate_sheet.py` and the two Desk buttons.
- [ ] **Step 4: Run** module + full backend — PASS.
- [ ] **Step 5: Commit** `feat(pricing): rate sheet download and import for series items`.

### Task 3: Readiness report and profile outlines from the Hilux DXF

**Files:**
- Create: `onebook_fenestration/series_studio/readiness.py`, `onebook_fenestration/series_studio/section_import.py`
- Modify: `onebook_fenestration/series_studio/doctype/series_version/series_version.js` ("Check readiness" button + dialog)
- Test: `onebook_fenestration/tests/test_readiness.py`, `onebook_fenestration/tests/test_section_import.py`

**Interfaces:**
- Produces:
  - `readiness(series_version: str) -> dict` (whitelisted, read permission on Series Version): `{"ok": bool, "checks": [{"check": str, "status": "ok"|"warn"|"block", "items": [str]}]}` with checks: `settings` (cost price list, default price structure, default finish set → block), `item_links` (profiles/glasses without Item → block), `prices` (items without a current rate on the cost price list → block), `gasket_rules` (catalogue glasses of this version with no Gasket-group rule matching their thickness → warn), `perimeters` (profiles with total and visible perimeter both 0 → warn), `outlines` (profiles without `section_svg` → warn). Reuses `pricing.rates._item_prices` and the snapshot; no duplicate rate logic.
  - `import_profile_sections(dxf_path: str, profile_codes: list[str] | None = None) -> dict` (bench-execute only, System Manager): reads a Hilux "Section Details" DXF with `ezdxf`. Locates each profile row by the TEXT/MTEXT whose content equals a profile code; the row's section drawing is the LINE/ARC/LWPOLYLINE/ELLIPSE geometry inside the "Section Drawing" column band of that row (column x-range from the header text "Section  Drawing"; row y-range from midpoints between neighbouring row code labels). Converts that geometry to one SVG `path` string normalised so the drawing's bbox starts at 0,0 (mm, y down), and stores `section_svg`, `width_mm`, `depth_mm` (bbox) on the Fenestration Profile **only when the profile has no `dxf_file`**. Returns `{"updated": [...], "skipped": [{"code", "reason"}]}`. Never writes kg/m or perimeters.
- Engine/data rule: outline geometry lives only in the DB; tests use a synthetic DXF built with `ezdxf` in the test (two fake profile rows `TSTA`, `TSTB` with a header and rectangles/arcs).

- [ ] **Step 1: Failing tests:** readiness — `test_ready_version_is_ok`, `test_missing_price_blocks`, `test_glass_without_gasket_warns`, `test_missing_outline_warns`; section import — `test_rows_become_normalised_svg` (bbox width/depth equal the synthetic rectangle sizes ±0.01), `test_profile_with_own_dxf_is_skipped`, `test_unknown_code_is_skipped`.
- [ ] **Step 2: Run** both modules — FAIL.
- [ ] **Step 3: Implement** both modules and the Series Version button.
- [ ] **Step 4: Run** modules + full backend — PASS.
- [ ] **Step 5: Commit** `feat(series): readiness report and profile outlines from section DXF`.

### Task 4: Engine cross-section cut

**Files:**
- Create: `onebook_fenestration/engine/section_cut.py`; export from `onebook_fenestration/engine/__init__.py`
- Modify: `onebook_fenestration/api/design.py` (new whitelisted `cross_section`)
- Test: `onebook_fenestration/engine/tests/test_section_cut.py`, `onebook_fenestration/tests/test_design_api.py` (or the existing API test module)

**Interfaces:**
- Produces:
  - `cross_section(design: dict, snapshot: SeriesSnapshot, axis: str, at: float | None = None, widths: dict[str, float] | None = None) -> CrossSection` in `engine/section_cut.py`. `axis` is `"h"` (B–B, a horizontal cut at height `at`, pieces ordered left→right) or `"v"` (A–A, a vertical cut at x = `at`, pieces ordered bottom→top). `at=None` means through the centre of the first cell; any `at` snaps to the centre of the cell it falls in (outside the frame → nearest cell).
  - `CrossSection(axis, at, length, pieces: list[SectionPiece], dims: list[Dim], issues: list[Issue])`; `SectionPiece(kind: "profile"|"glass", code, role, panel, start, end, mirrored: bool)` with `start`/`end` in mm along the cut from the frame's outer edge; `Dim(start, end, label)`.
  - Profile pieces come from the members the cut crosses (frame both ends, mullions/transoms crossed, sash members of crossed sashes, beads/adaptors of crossed panes), placed with the same deductions the engine uses for cut lengths (frame at 0 and `length`; mullion centred on the bar position; sash edges at cell edge + `sash_side_*`; glass from `compute()`'s pane size centred in its opening). Piece face width comes from `widths[code]` (the profile's `width_mm`); a missing width yields an `Issue("warn", "no_section_width", …)` and a piece using the side deduction as its width.
  - `dims`: frame outer edges, each profile face, each glass size, each cell, overall — enough to draw chains like the client sample.
  - API `cross_section(design: str | dict, series_version: str, axis: str, at: float | None = None) -> dict` returns the engine result as JSON plus `outlines: {code: {"svg": str, "width": float, "depth": float}}` for every profile in the pieces (from Fenestration Profile; absent codes omitted).
- [ ] **Step 1: Failing tests:** `test_w01_horizontal_cut` (pieces: frame E104156 at 0, sash, sash glass 333 wide, sash, mullion centred at 457.5, sash, glass, sash, frame ending at 915; glass start/end equal the engine pane width), `test_123_vertical_cut_through_fixed_pane` (frame, CS4808 beads, glass 1441, frame), `test_cut_position_snaps_to_cell`, `test_cut_reports_missing_widths`, `test_cut_is_deterministic`; API `test_cross_section_api_returns_outlines`.
- [ ] **Step 2: Run** engine + API tests — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** engine, backend — PASS (W01/W02/123 goldens unchanged).
- [ ] **Step 5: Commit** `feat(engine): cross-section cut through a design`.

### Task 5: Cross-section view in the Window Designer

**Files:**
- Create: `frontend/src/components/SectionView.vue`, `frontend/src/components/SectionView.spec.ts`
- Modify: `frontend/src/pages/Designer.vue` (a "Section" view toggle next to the canvas), `frontend/src/components/WindowCanvas.vue` (draw A/B cut markers when the section view is on; clicking a cell moves the active cut)

**Interfaces:**
- Consumes: Task 4 API `onebook_fenestration.api.design.cross_section`.
- Produces: `SectionView` props `{ design: object, seriesVersion: string, axis: 'h'|'v', at: number|null }`; calls the API with frappe-ui `createResource`, re-fetches when the design changes (debounced like the existing compute). Draws an SVG strip: each profile piece placed at `start`, outline scaled from the profile's `width` to the piece width (mirrored when `mirrored`), glass as a cyan band with the code label, profile codes as labels, dimension chains from `dims` above/below the strip. Profiles without an outline draw as a labelled rectangle and the view shows a one-line note listing them. Toggle buttons "B–B horizontal" / "A–A vertical". Fits container width; at 390 px it scales down and the page has no horizontal scroll.

- [ ] **Step 1: Failing tests** (vitest, mocked resource): `renders_a_piece_per_section_piece`, `missing_outline_falls_back_to_box` (and lists the code), `axis_toggle_refetches`, `cut_marker_click_moves_cut` (WindowCanvas emits `update:cut`).
- [ ] **Step 2: Run** `cd frontend && npx vitest run src/components/SectionView.spec.ts` — FAIL.
- [ ] **Step 3: Implement**, then `npx vite build` (or the repo's build script) so the bench serves it.
- [ ] **Step 4: Run** full vitest — PASS.
- [ ] **Step 5: Commit** `feat(designer): cross-section view with A–A / B–B cuts`.

### Task 6 (controller, after merge): configure the dev site and check end to end

Not a subagent task; the controller runs it and fixes found defects through the normal task loop.
- [ ] `bench --site window.localhost migrate`; `bench --site window.localhost execute onebook_fenestration.series_studio.data.import_hilux_series`.
- [ ] `import_profile_sections` with the two client DXFs (paths in the git-ignored client folder).
- [ ] Series Version "Check readiness" for CS400 and CS4800 latest; download the rate sheet (the list of missing rates goes to the user for Hilux; no rates invented).
- [ ] Chrome: W01 (CS400-V01) design → section view B–B and A–A → quote PDF → Sales Order → Work Order → cutting plan; 123 on CS4800 latest → section view and readiness shows only the missing rates. Phone width check via the 390 px iframe trick.
