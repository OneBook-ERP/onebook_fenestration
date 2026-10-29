# Plan 2: Masters, Series Snapshot and Compute API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the Plan 1 engine behind real Frappe data:
- series, profiles, glass and rules become DocTypes that Hilux edits in Desk;
- a submitted Series Version becomes a `SeriesSnapshot`;
- Window Designs compute on save;
- a whitelisted `compute_design` API serves the Plan 3 designer.

**Architecture:**
- The app owns its DocTypes as JSON in two new modules:
  - **Series Studio** — masters.
  - **Fenestration** — projects and designs.
- Fields added to ERPNext DocTypes are declared in code and applied with `create_custom_fields` from `after_install` and `after_migrate`. This follows india_compliance's pattern, not fixtures.
- A Series Version is submittable: **submit = publish**. A submitted version is immutable. A new version is an amendment.
- The snapshot builder maps DocType rows to the engine's `SeriesSnapshot.from_dict` shape.

**Tech Stack:** Frappe v16.54 / ERPNext v16.53 on site `window.localhost` (developer_mode on), `frappe.tests.IntegrationTestCase`, Plan 1 `onebook_fenestration.engine`.

**Spec:** `doc/context.md` §4–5, `doc/decisions.md` (D2, D3), `doc/app-map.md` §4, `doc/plans/2026-10-29-roadmap.md` (Plan 2 row).

## Global Constraints

- Site: always pass `--site window.localhost`. Use bare `bench`.
- DocTypes are created by writing `<app>/<module>/doctype/<name>/<name>.json` plus `__init__.py` and running `bench --site window.localhost migrate`. Never `mkdir` a DocType folder by hand for any other purpose. Never create DocTypes through the Desk UI.
- Custom fields on ERPNext DocTypes live only in `onebook_fenestration/setup/custom_fields.py` (a `CUSTOM_FIELDS` dict). No `fixtures` hook. Every custom fieldname starts with `fen_`.
- Engine code (`onebook_fenestration/engine/`) is not modified in this plan. Exception: Task 3 may add exports to `engine/__init__.py`.
- DocType names, exactly: `Profile Series`, `Series Version`, `Fenestration Profile`, `Fenestration Glass`, `Fenestration Project`, `Window Design`. Child tables: `Series Deduction`, `Series Member Rule`, `Series Hardware Rule`, `Series Validation Rule`, `Series Constant`.
- Permissions:
  - Masters: `System Manager` full access, plus role `Fenestration Engineer` (created by install) with create/write/submit/amend on Series Version.
  - Projects and designs: `System Manager` and `Sales User` read/write/create.
- Test command, per module: `bench --site window.localhost run-tests --app onebook_fenestration --module <dotted.module>`. The engine suite must stay green: `/workspace/development/window-bench-16/env/bin/python -m unittest discover -s onebook_fenestration/engine/tests -t .` (63 tests).
- Commits on branch `feat/masters-api`. Each message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never commit `doc/*.pdf|mp4|dxf` or `.superpowers/`.

## Review Focus

1. **Editing a published Series Version is impossible.** A submitted version cannot be saved with changed rules (Frappe blocks it). Quotes stay on their version. Owned by Task 2: `test_submitted_version_is_immutable`.
2. **An incomplete series is caught at publish, not at quote time.** Submitting a version whose snapshot fails `SeriesSnapshot.check()` raises `frappe.ValidationError` with the missing keys. Owned by Task 3: `test_submit_incomplete_version_fails`.
3. **A bad design never blocks saving a Window Design silently, and never 500s the API.**
   - Design errors are shown as a validation message that names the node path.
   - The API returns `{"ok": false, ...}` instead of raising.
   - Owned by Task 5 (`test_bad_design_raises_with_path`) and Task 6 (`test_api_bad_design_returns_error`).
4. **Snapshot cache goes stale when a version is cancelled or amended.** The cache key is the version name, and it is cleared on submit and cancel. Owned by Task 3: `test_cache_cleared_on_cancel`.
5. **DXF on a profile that isn't a section** (bad or empty file) shows a readable error and keeps the profile saveable without section data. Owned by Task 4: `test_bad_dxf_message`.

---

## File Structure

```
onebook_fenestration/
  modules.txt                       + "Series Studio", "Fenestration"
  hooks.py                          + after_install, after_migrate, before_uninstall
  setup/__init__.py
  setup/install.py                  after_install(), after_migrate(), before_uninstall()
  setup/custom_fields.py            CUSTOM_FIELDS = {"Item": [fen_item_kind]}
  series_studio/__init__.py
  series_studio/doctype/{profile_series,series_version,fenestration_profile,fenestration_glass,
                         series_deduction,series_member_rule,series_hardware_rule,
                         series_validation_rule,series_constant}/   (json, py, __init__)
  series_studio/snapshot.py         build_snapshot_dict(name) -> dict; get_snapshot(name) -> SeriesSnapshot
  series_studio/importer.py         import_snapshot_json(series_code, data, title) -> str
  fenestration/__init__.py
  fenestration/doctype/{fenestration_project,window_design}/
  api/__init__.py
  api/design.py                     compute_design(design, series_version) -> dict
  tests/__init__.py
  tests/test_install.py, test_series.py, test_snapshot.py, test_profile_dxf.py,
  tests/test_window_design.py, test_api.py
```

---

### Task 1: Install app, modules, custom-field mechanism

**Files:**
- Modify: `onebook_fenestration/modules.txt`, `onebook_fenestration/hooks.py`
- Create: `onebook_fenestration/setup/__init__.py`, `setup/install.py`, `setup/custom_fields.py`, `series_studio/__init__.py`, `fenestration/__init__.py`, `api/__init__.py`, `tests/__init__.py`, `tests/test_install.py`

**Interfaces:**
- Produces:
  - `CUSTOM_FIELDS: dict[str, list[dict]]`
  - `after_install() -> None`
  - `after_migrate() -> None`
  - `before_uninstall() -> None`
  - Role `Fenestration Engineer`.
- `CUSTOM_FIELDS["Item"]` = one field:
  - fieldname `fen_item_kind`, label "Fenestration Kind", fieldtype `Select`
  - options `"\nProfile\nHardware\nGlass\nGasket\nConsumable"`
  - `insert_after` `"item_group"`, `in_standard_filter` 1
- `after_install` and `after_migrate` both call `create_custom_fields(CUSTOM_FIELDS, update=True)` and ensure the role exists.
- `before_uninstall` deletes every `Custom Field` whose `dt` is in CUSTOM_FIELDS and whose fieldname starts with `fen_`.

- [ ] **Step 1: Branch and install the app on the site**

```bash
git checkout -b feat/masters-api
bench --site window.localhost install-app onebook_fenestration
bench --site window.localhost set-config allow_tests true
```

Expected: `onebook_fenestration` appears in `bench --site window.localhost list-apps`.

- [ ] **Step 2: Write the failing test** `tests/test_install.py`

```python
class TestInstall(IntegrationTestCase):
    def test_item_kind_custom_field(self):
        self.assertTrue(frappe.get_meta("Item").has_field("fen_item_kind"))
    def test_engineer_role(self):
        self.assertTrue(frappe.db.exists("Role", "Fenestration Engineer"))
    def test_after_migrate_is_idempotent(self):
        after_migrate(); after_migrate()
        self.assertEqual(frappe.db.count("Custom Field", {"dt": "Item", "fieldname": "fen_item_kind"}), 1)
```

- [ ] **Step 3: Run; expect FAIL** (ImportError on `setup.install`)

Run: `bench --site window.localhost run-tests --app onebook_fenestration --module onebook_fenestration.tests.test_install`

- [ ] **Step 4: Implement**
  - Add the hooks: `after_install = "onebook_fenestration.setup.install.after_install"`, the same for `after_migrate` and `before_uninstall`.
  - Add the two module names to `modules.txt`.
  - Run `bench --site window.localhost migrate`.
- [ ] **Step 5: Run; expect PASS. Commit** `feat: install hooks, modules and fen_ custom fields`

---

### Task 2: Series Studio DocTypes

**Files:**
- Create the 9 DocTypes under `series_studio/doctype/` (json, `.py` controller, `__init__.py`)
- Test: `tests/test_series.py`

**DocType fields** (all `module: "Series Studio"`; child tables `istable: 1`, no permissions):

| DocType | autoname | fields (fieldname: type [options] flags) |
|---|---|---|
| Fenestration Glass | `field:glass_code` | glass_code: Data reqd unique; glass_name: Data reqd; thickness_mm: Float reqd; item: Link [Item] |
| Profile Series | `field:series_code` | series_code: Data reqd unique; series_title: Data reqd; system_type: Select [Casement\nSliding\nDoor] reqd; published_version: Link [Series Version] read_only |
| Fenestration Profile | `field:profile_code` | profile_code: Data reqd unique; profile_name: Data reqd; series: Link [Profile Series] reqd; item: Link [Item]; role: Select [frame\nsash\nmullion\ntransom\nbead\naccessory] reqd; kg_per_m: Float reqd; bar_lengths: Data reqd (comma-separated mm, e.g. `4880, 5800`); dxf_file: Attach; use_computed_weight: Check; Section Break "Section (from DXF)" collapsible; area_mm2, width_mm, depth_mm, perimeter_mm, ix_mm4, iy_mm4, computed_kg_per_m: Float read_only; section_svg: Long Text read_only hidden; section_warnings: Small Text read_only |
| Series Version | `format:{series}-V{##}`, `is_submittable` 1, `track_changes` 1 | series: Link [Profile Series] reqd; version_note: Small Text; deductions: Table [Series Deduction]; member_rules: Table [Series Member Rule]; hardware_rules: Table [Series Hardware Rule]; validation_rules: Table [Series Validation Rule]; constants: Table [Series Constant] |
| Series Deduction | – | deduction_key: Data reqd in_list_view; value: Float reqd in_list_view |
| Series Constant | – | constant_key: Data reqd in_list_view; value: Float reqd in_list_view |
| Series Member Rule | – | rule_id: Data reqd; role: Select [frame\nsash\nmullion\ntransom] reqd; profile: Link [Fenestration Profile] reqd; angle_start: Int default 45; angle_end: Int default 135; length_expr: Data reqd (all in_list_view) |
| Series Hardware Rule | – | rule_id: Data reqd; item: Link [Item] reqd; item_name: Data fetch_from `item.item_name` reqd; per: Select [frame_member\nsash_member\nmullion\ntransom_member\nsash\nglass\nwindow] reqd; when_expr: Data default `True`; qty_expr: Data reqd; length_expr: Data; uom: Link [UOM] default `Nos`; bom_group: Data default `Fabrication Hardware` |
| Series Validation Rule | – | rule_id: Data reqd; when_expr: Data reqd; severity: Select [error\nwarn] reqd; message: Small Text reqd; hint: Small Text |

**Interfaces:**
- Produces the DocTypes above.
- `SeriesVersion.on_submit` sets `Profile Series.published_version` to this version.
- `on_cancel` clears it when it pointed here.
- (Task 3 adds the snapshot check to `before_submit`.)

- [ ] **Step 1: Write failing tests** `tests/test_series.py`
  - `test_create_glass_profile_series_version`: insert Glass `6CTG`, Series `TST1` (Casement), Profile `TP1` (role frame, kg 0.649, bars `4880, 5800`), and a draft Version with one deduction row. Assert the version name starts with `TST1-V`.
  - `test_submit_sets_published_version`: after submit, `Profile Series TST1` has `published_version` equal to the version name.
  - `test_submitted_version_is_immutable`: after submit, changing `deductions[0].value` and calling `save()` raises `frappe.ValidationError`. (Frappe raises `frappe.exceptions.UpdateAfterSubmitError`, a subclass.)
- [ ] **Step 2: Run; expect FAIL** (DocType not found)
- [ ] **Step 3: Write the 9 DocType JSONs and controllers; migrate**
- [ ] **Step 4: Run; expect PASS. Commit** `feat(series-studio): series, version, profile and glass doctypes`

---

### Task 3: Snapshot builder, cache, importer

**Files:**
- Create: `series_studio/snapshot.py`, `series_studio/importer.py`
- Modify: `series_studio/doctype/series_version/series_version.py`
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes the Task 2 DocTypes and `onebook_fenestration.engine` (`SeriesSnapshot`, `compute`, `RuleError`).
- Produces:
  - `build_snapshot_dict(series_version: str) -> dict`: the exact `SeriesSnapshot.from_dict` shape. Mapping:
    - `code` = series, `version` = version name
    - deductions and constants: `{key: value}`
    - `profiles`: `{profile_code: {name: profile_name, kg_per_m: (computed_kg_per_m if use_computed_weight and computed_kg_per_m else kg_per_m), bar_lengths: [floats parsed from bar_lengths]}}` for every Fenestration Profile with `series` = the version's series
    - member rows → `{id: rule_id, role, profile, angles: [angle_start, angle_end], length: length_expr}`
    - hardware rows → `{id: rule_id, item, name: item_name, per, qty: qty_expr, uom, when: when_expr or "True", length: length_expr or None, group: bom_group}`. **The item_name→name mapping is a ledger ruling from Plan 1.**
    - validation rows → `{id: rule_id, when: when_expr, severity, message, hint}`
    - `glasses`: `{glass_code: {name: glass_name, thickness_mm}}` for all Fenestration Glass
  - `get_snapshot(series_version: str) -> SeriesSnapshot`: cached in `frappe.cache` under hash key `fen_snapshot`, field = version name, value = the dict. Only submitted versions are cached; a draft is rebuilt every call. `clear_snapshot(series_version)` deletes the field.
  - `SeriesVersion.before_submit` builds the snapshot and calls `.check()`. A `RuleError` becomes `frappe.throw(str(exc), title="Series is incomplete")`.
  - `on_submit` and `on_cancel` call `clear_snapshot`.
  - `import_snapshot_json(series_code: str, data: dict, title: str, system_type: str = "Casement") -> str`:
    - creates any missing Glass and Profile Series records;
    - creates Profiles from `data["profiles"]` (role taken from the first member rule using that profile, else `accessory`);
    - creates any missing Items for hardware and profiles: `item_group` "Fenestration" (created if missing as a non-group child of "All Item Groups"; ERPNext rejects group nodes on Items), `stock_uom` from the rule or "Nos", `fen_item_kind` set accordingly;
    - creates any missing UOM the rules use (`Pairs`, `m`, `CAN` may not exist on a fresh site);
    - creates and submits a Series Version with every row;
    - returns the version name.

    Plan 3/4 reuse this as the "import series" path.

- [ ] **Step 1: Write failing tests** `tests/test_snapshot.py`
  - Load `onebook_fenestration/engine/tests/fixtures/cs400_snapshot.json` and `w01.json`.
  - `test_import_and_compute_w01`: `v = import_snapshot_json("CS400", data, "CS400 Economical Casement")`. Then `r = compute(w01, get_snapshot(v))`. Assert:
    - `r.issues == []`
    - `r.area_sqft == 12.013`
    - `abs(r.window_kg - 20.698) <= 0.02`
    - summed qty for item `H912` == 10
  - `test_snapshot_dict_roundtrip_equals_fixture`: `SeriesSnapshot.from_dict(build_snapshot_dict(v))` equals `SeriesSnapshot.from_dict(data)` on `deductions`, `member_rules`, `hardware_rules`, `constants`.
  - `test_submit_incomplete_version_fails`: a version with no deductions raises `frappe.ValidationError` on submit, and the message contains `sash_glass`.
  - `test_cache_cleared_on_cancel`: `get_snapshot(v)` (fills the cache), then `frappe.get_doc("Series Version", v).cancel()`. Assert `frappe.cache.hget("fen_snapshot", v)` is None.
- [ ] **Step 2: Run; expect FAIL** (ImportError)
- [ ] **Step 3: Implement** `snapshot.py`, `importer.py` and the controller hooks.
- [ ] **Step 4: Run; expect PASS, plus the engine suite green. Commit** `feat(series-studio): snapshot builder, cache and json importer`

---

### Task 4: DXF section on Fenestration Profile

**Files:**
- Modify: `series_studio/doctype/fenestration_profile/fenestration_profile.py`
- Test: `tests/test_profile_dxf.py`

**Interfaces:**
- Consumes `onebook_fenestration.engine.analyze_dxf`, `SectionError`.
- `FenestrationProfile.validate`: when `dxf_file` is set and changed (`self.has_value_changed("dxf_file")`, or the section fields are empty):
  - resolve the File by `file_url` and call `analyze_dxf(file_doc.get_full_path())`;
  - fill the section fields (rounded: area 1 dp, mm 1 dp, inertia 0 dp, kg 3 dp), `section_svg`, and `section_warnings` (comma-joined).
- When `dxf_file` is cleared, blank the section fields.
- A `SectionError` → `frappe.throw(_("Could not read section from DXF: {0}").format(exc), title=_("DXF error"))`.

- [ ] **Step 1: Write failing tests**
  - `test_flush_cap_fills_section`: create a `File` (`file_name` "flush_cap.dxf", `content` = bytes of `engine/tests/fixtures/flush_cap.dxf`, `is_private` 1), then a Profile with `dxf_file` = its `file_url`. Assert:
    - `area_mm2` ≈ 1412.0 (±1)
    - `computed_kg_per_m` ≈ 3.812 (±0.005)
    - `section_svg` starts with `"M"`
  - `test_bad_dxf_message`: a File with content `b"not a dxf"` → insert raises `frappe.ValidationError` whose message contains "Could not read section from DXF".
- [ ] **Step 2: Run; expect FAIL** (section fields stay empty)
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run; expect PASS. Commit** `feat(series-studio): compute profile section from DXF`

---

### Task 5: Fenestration Project and Window Design

**Files:**
- Create DocTypes `fenestration/doctype/fenestration_project/`, `fenestration/doctype/window_design/`
- Test: `tests/test_window_design.py`

**DocType fields** (`module: "Fenestration"`):

| DocType | autoname | fields |
|---|---|---|
| Fenestration Project | `naming_series:` with `naming_series` Select options `FP-.YYYY.-` | project_title: Data reqd; customer: Link [Customer]; opportunity: Link [Opportunity]; site_address: Small Text; default_series_version: Link [Series Version] |
| Window Design | `format:{project}-{design_ref}` | project: Link [Fenestration Project] reqd; design_ref: Data reqd; design_name: Data; qty: Int default 1 reqd; location: Data; series_version: Link [Series Version] reqd; design_json: JSON reqd; Section "Results" — area_m2, area_sqft, window_kg: Float read_only; error_count, warning_count: Int read_only; result_json: JSON read_only; design_svg: Long Text hidden |

**Interfaces:**
- Consumes `get_snapshot`, `compute`, `DesignError`, `RuleError`.
- Produces `result_to_dict(result: EngineResult) -> dict`, defined in `fenestration/doctype/window_design/window_design.py`: `dataclasses.asdict`, with tuples turned into lists so it is JSON-safe. Task 6 imports it.
- `WindowDesign.validate`:
  - `series_version` must have docstatus 1; otherwise throw "Series Version must be published".
  - Parse `design_json` (str → dict).
  - Run `compute(design, get_snapshot(series_version))`.
  - Fill the results: `error_count` / `warning_count` from issue severity, and `result_json` = `result_to_dict(r)`.
  - `DesignError` or `RuleError` → `frappe.throw(str(exc), title="Design is invalid")`. The message already starts with the node path.
  - Issues do **not** block saving.

- [ ] **Step 1: Write failing tests** (import CS400 via `import_snapshot_json` in `setUpClass`; create a Project)
  - `test_w01_design_computes_on_save`: `area_sqft == 12.013`, `abs(window_kg - 20.698) <= 0.02`, `error_count == 0`, `result_json["members"]` has 13 entries.
  - `test_wall_12x6_saves_with_errors`: the design saves, and `error_count == 2` (both sashes over the stay limit).
  - `test_bad_design_raises_with_path`: `design_json` with `"at": [0]` raises `frappe.ValidationError` whose message contains `"F1"`.
  - `test_draft_version_rejected`: a draft Series Version raises `frappe.ValidationError` "Series Version must be published".
- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement; migrate**
- [ ] **Step 4: Run; expect PASS. Commit** `feat(fenestration): project and window design compute on save`

---

### Task 6: `compute_design` API

**Files:**
- Create: `api/design.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces `@frappe.whitelist() def compute_design(design: dict | str, series_version: str) -> dict`.
  - `frappe.has_permission("Series Version", "read", series_version, throw=True)`.
  - Parse the design when it is a str.
  - Success → `{"ok": True, "result": result_to_dict(r)}`.
  - `DesignError` → `{"ok": False, "error_type": "design", "message": str(exc)}`.
  - `RuleError` → `{"ok": False, "error_type": "series", "message": str(exc)}`.
  - Invalid JSON string → `{"ok": False, "error_type": "design", "message": "design is not valid JSON"}`.
  - Never raises for these cases.

- [ ] **Step 1: Write failing tests**
  - `test_api_w01`: `compute_design(json.dumps(w01), v)["ok"] is True`, and `["result"]["area_sqft"] == 12.013`.
  - `test_api_bad_design_returns_error`: `at: [0]` → `ok False`, `error_type == "design"`, `"F1"` in the message.
  - `test_api_invalid_json`: `compute_design("{", v)["error_type"] == "design"`.
  - `test_api_requires_read_permission`: `frappe.set_user("Guest")`, then call → raises `frappe.PermissionError`. Reset the user in `tearDown`.
- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run all Plan 2 test modules and the engine suite; expect PASS. Commit** `feat(api): compute_design endpoint`

## Done when

- The app is installed on `window.localhost`, `fen_item_kind` is on Item, and the role exists.
- The CS400 JSON imports into DocTypes, publishes as a Series Version, and computes W01 to the EvA golden values **through the database**.
- A profile DXF fills section properties.
- Window Designs compute on save.
- `compute_design` returns structured results and errors.
- All Plan 2 test modules and the 63 engine tests are green.
