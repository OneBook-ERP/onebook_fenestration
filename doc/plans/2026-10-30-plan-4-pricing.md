# Plan 4: Pricing (Cost Heads, Rates, Finish) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Price every window design the way Hilux prices in EvA today. Pricing is an ordered chain of cost heads: profile cost by kg, wastage %, coating per perimeter sq.ft, hardware, glass per m², labour per sq.ft, then profit %. Rates come from ERPNext Item Prices. The designer and the project workspace show unit price, ₹/sq.ft and the line total.

**Architecture:**
- **Pure pricing engine.** `engine/pricing.py` adds `price(result, snapshot, pricing) -> PriceBreakdown`. It is deterministic and has no database access, the same rule as Plan 1.
- **Price Structure DocType.** It holds the ordered cost heads, each with a calculation type, a rate, an optional base and an optional condition. This mirrors EvA's "Project Price Structure" screen (`doc/competitor-ux.md` §1).
- **Rates.** Rates come from an ERPNext Price List. Fenestration Settings names the cost price list. A rate resolver builds a `PricingInput` from Item Prices.
- **Finish.** A finish is a master (Profile Finish). Its `finish_type` drives the coating cost heads through conditions. Its colour drives the canvas.
- **Window Design.** It stores `finish`, `price_structure`, `unit_price`, `rate_per_sqft`, `line_total` and `pricing_json`. All are computed in the same gate as the engine results.

**Tech Stack:** Python engine (Plan 1), Frappe v16 DocTypes on `window.localhost`, Vue SPA (Plan 3) with frappe-ui 1.1.0.

**Spec:**
- `doc/competitor-ux.md` §1 (EvA Pricing tab, cost heads table) and §4
- `doc/context.md` §3 commercial terms (finish surcharge Matt 0 / Texture 2% / Wooden 12%) and §4 price stack
- `doc/decisions.md` D7 (pricing basis: cost-plus, answered by the EvA video) and D8 (billing area: frame size)

## Global Constraints

- **The pricing engine is pure.** `onebook_fenestration/engine/pricing.py` imports only from `onebook_fenestration.engine` plus `frappe.utils.safe_exec` (through `formula.evaluate`). No database access.
- **Money rounding.** Each cost-head amount is rounded to 2 dp. `unit_price` is the sum, rounded to 2 dp. `rate_per_sqft = round(unit_price / area_sqft, 2)`. `line_total = round(unit_price × qty, 2)`.
- **Area basis is frame size** (D8): `EngineResult.area_sqft` and `area_m2`. Fenestration Settings `billing_area_basis` has the single option "Frame size" for now.
- **Perimeter sq.ft.** For each member, `cut length (m) × perimeter (m)`. Members whose profile perimeter is 0 add nothing. Use `visible_perimeter_mm` or `total_perimeter_mm` of the profile. Convert m² to sq.ft with ×10.764.
- **Cost head calculation types** (exact strings):
  - `Formula`: the amount is `evaluate(formula, vars)`.
  - `Percentage`: amount = `rate/100 × base`, where the base is the sum of the named earlier heads (comma-separated keys).
  - `Per Area Sqft`: `rate × area_sqft`.
  - `Per Visible Perimeter Sqft`: `rate × visible_perimeter_sqft`.
  - `Per Total Perimeter Sqft`: `rate × total_perimeter_sqft`.
  - `Fixed`: `rate`.
- **Head `condition`.** An optional formula; when it is false, the head's amount is 0.
- **Formula variables:**
  - `profile_cost` (Σ profile kg × profile rate/kg)
  - `hardware_cost` (Σ bom qty × rate, excluding gasket lines)
  - `gasket_cost` (Σ gasket length m × rate/m)
  - `glass_cost` (Σ pane m² × glass rate/m²)
  - `area_sqft`, `area_m2`, `window_kg`
  - `visible_perimeter_sqft`, `total_perimeter_sqft`
  - `finish_type` (string)
  - each earlier head's amount by its `key`
- **Missing rate.** A missing Item Price is treated as rate 0 and adds an `Issue("warn", "no_rate", "<item>: no price in <price list>")`. It never raises.
- **Seed price structure.** `Standard` is created by `after_install`/`after_migrate` when missing, with Hilux's EvA values. Rows, in order, as key / label / type / rate / base / condition:

  ```
  profile         | Profile Cost         | Formula                  | formula "profile_cost"
  profile_waste   | Profile Wastage      | Percentage               | 5  | base "profile"
  powder          | Powder Coating       | Per Visible Perimeter Sqft | 25 | condition "finish_type == 'Powder Coat'"
  anodize         | Anodizing            | Per Total Perimeter Sqft | 40 | condition "finish_type == 'Anodized'"
  wood            | Wood Finish          | Per Visible Perimeter Sqft | 70 | condition "finish_type == 'Wood'"
  hardware        | Hardware Cost        | Formula                  | formula "hardware_cost + gasket_cost"
  glass           | Glass Cost           | Formula                  | formula "glass_cost"
  glass_waste     | Glass Wastage        | Percentage               | 1  | base "glass"
  fabrication     | Fabrication Labour   | Per Area Sqft            | 100
  installation    | Installation Labour  | Per Area Sqft            | 80
  profit          | Profit               | Percentage               | 20 | base "profile,profile_waste,powder,anodize,wood,hardware,glass,glass_waste,fabrication,installation"
  ```

- **Seed finishes** (created when missing):
  - `GREY`: Grey, Powder Coat, #8A8F98
  - `BROWN-5104`: 5104 PC Brown, Powder Coat, #6B3E26
  - `MILL`: Mill Finish, Mill, #B8BCC2
  - `WOOD`: Wooden Finish, Wood, #8B5A2B

  `finish_type` options: `Mill`, `Powder Coat`, `Anodized`, `Wood`.
- **Fenestration Settings** (single DocType):
  - `cost_price_list` (Link Price List; default "Standard Selling" if it exists)
  - `default_price_structure` (Link Price Structure; default "Standard")
  - `default_finish` (Link Profile Finish; default "GREY")
  - `billing_area_basis` (Select "Frame size")
- **Commands.** Backend tests: `bench --site window.localhost run-tests --app onebook_fenestration --module <module>`. Engine suite: `/workspace/development/window-bench-16/env/bin/python -m unittest discover -s onebook_fenestration/engine/tests -t .` (from the app dir). Frontend: `cd frontend && yarn test && yarn build`. Everything existing stays green.
- **Commits** on branch `feat/pricing`, each ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never commit build output, `doc/*.pdf|mp4|dxf` or `.superpowers/`.

## Review Focus

1. **Percentage base ordering.** A Percentage head whose base names a later head, or an unknown key, raises `RuleError` naming the head. It must never silently use 0. Owned by Task 1: `test_percentage_base_must_be_earlier_head`.
2. **Zero area.** `rate_per_sqft` when `area_sqft` is 0 (degenerate design) → 0, not a ZeroDivisionError. Owned by Task 1.
3. **Missing Item Price.** A missing price for a profile, hardware item or glass shows `no_rate` warnings in the designer. The price still computes. Owned by Tasks 3 and 5.
4. **Published-version freeze vs live prices.** Prices are live (read at compute time). The series snapshot stays frozen. A saved design's stored price is only recomputed when the design, series, finish or price structure changes (the Plan 2 gate, extended). Owned by Task 4: `test_price_not_recomputed_on_location_edit`.
5. **Price structure edits.** Formula, condition or base errors are caught when the Price Structure is saved, not when a design is saved. Owned by Task 2: `test_price_structure_validates_formulas`.

---

## File Structure

```
onebook_fenestration/engine/pricing.py            CostHead, PricingInput, PriceLine, PriceBreakdown, price()
onebook_fenestration/engine/types.py              ProfileSpec + visible_perimeter_mm, total_perimeter_mm (default 0)
onebook_fenestration/engine/tests/test_pricing.py
onebook_fenestration/series_studio/doctype/fenestration_profile/   + visible_perimeter_mm field; total from DXF perimeter
onebook_fenestration/series_studio/snapshot.py    profiles include perimeters
onebook_fenestration/pricing/__init__.py           (new module "Pricing" in modules.txt)
onebook_fenestration/pricing/doctype/{price_structure,cost_head,profile_finish,fenestration_settings}/
onebook_fenestration/pricing/rates.py              build_pricing_input(snapshot, result, finish, price_structure, price_list) -> PricingInput
onebook_fenestration/setup/install.py              + seed Standard price structure, finishes, settings
onebook_fenestration/fenestration/doctype/window_design/  + finish, price_structure, unit_price, rate_per_sqft, line_total, pricing_json
onebook_fenestration/api/design.py                 compute_design/save_design accept finish, price_structure; return pricing
frontend/src/...                                   finish select, price in ResultsBar + Pricing tab, card + totals value
```

---

### Task 1: Pure pricing engine

**Files:**
- Create: `onebook_fenestration/engine/pricing.py`
- Modify: `onebook_fenestration/engine/types.py` (add `visible_perimeter_mm: float = 0.0` and `total_perimeter_mm: float = 0.0` to ProfileSpec; `from_dict` accepts them optionally), `engine/__init__.py` (exports)
- Test: `onebook_fenestration/engine/tests/test_pricing.py`

**Interfaces:**
- `CostHead(key: str, label: str, calc: str, rate: float = 0, formula: str = "", base: str = "", condition: str = "")` (frozen)
- `PricingInput(heads: tuple[CostHead, ...], profile_rates: dict[str, float], item_rates: dict[str, float], glass_rates: dict[str, float], finish_type: str, missing: tuple[str, ...] = ())`
  - `profile_rates` is per kg, keyed by profile code.
  - `item_rates` is per BOM uom, keyed by item code. Gaskets G21/G23 are priced per metre: rate × length/1000 per line.
  - `glass_rates` is per m², keyed by glass code.
- `PriceLine(key, label, amount: float)`
- `PriceBreakdown(lines: list[PriceLine], unit_price: float, rate_per_sqft: float, variables: dict[str, float], issues: list[Issue])`
- `price(result: EngineResult, snapshot: SeriesSnapshot, pricing: PricingInput) -> PriceBreakdown`. Each name in `missing` becomes an `Issue("warn","no_rate", ...)`.

- [ ] **Step 1: Write failing tests** (W01 via `compute(load("w01.json"), snapshot())` from the engine fixtures, with hand-chosen rates):
  - `test_profile_hardware_glass_costs`:
    - profile rate 300/kg for all three profiles → `profile_cost` = round(Σ member kg × 300, 2). Compute the expected kg from the members in the test, not hard-coded.
    - glass 6CTG at 1000/m² → `glass_cost` = 2 × 0.333 × 1.083 × 1000.
    - hardware: every item at 10 per unit; G21/G23 at 20/m.
  - `test_percentage_and_conditions`: on the Standard head list with finish_type "Powder Coat", powder > 0 while anodize and wood are 0. Profit = 20% of the sum of the named heads.
  - `test_perimeter_sqft`: set visible_perimeter_mm=100 on E104156 only → `visible_perimeter_sqft` = Σ(frame member lengths m × 0.1 m) × 10.764.
  - `test_percentage_base_must_be_earlier_head` → RuleError mentioning the head key.
  - `test_zero_area_rate_per_sqft` → 0.0.
  - `test_missing_rates_warn`.
  - `test_unit_price_and_rate_per_sqft_rounding`.
- [ ] **Step 2: Run the engine suite; expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Engine suite green (63 + new). Commit** `feat(engine): cost-head pricing`

---

### Task 2: Pricing masters, profile perimeters, seeds

**Files:**
- Create the DocTypes `Price Structure`, `Cost Head` (child), `Profile Finish`, `Fenestration Settings` (single) in new module "Pricing" (`onebook_fenestration/pricing/`)
- Modify: `modules.txt`, `setup/install.py`, Fenestration Profile (add `visible_perimeter_mm` Float with label "Visible Perimeter (mm)"; the DXF analyser also sets `total_perimeter_mm` = perimeter_mm), `series_studio/snapshot.py` (include both perimeters)
- Test: `onebook_fenestration/tests/test_pricing_masters.py`

**Fields:**

| DocType | autoname | fields |
|---|---|---|
| Profile Finish | `field:finish_code` | finish_code Data reqd unique; finish_name Data reqd; finish_type Select [Mill\nPowder Coat\nAnodized\nWood] reqd; color Color |
| Price Structure | `field:structure_name` | structure_name Data reqd unique; is_default Check; heads Table [Cost Head] |
| Cost Head | – | key Data reqd; label Data reqd; calc Select [Formula\nPercentage\nPer Area Sqft\nPer Visible Perimeter Sqft\nPer Total Perimeter Sqft\nFixed] reqd; rate Float; formula Data; base Data; condition Data (all in_list_view except base/condition) |
| Fenestration Settings | single | cost_price_list Link Price List; default_price_structure Link Price Structure; default_finish Link Profile Finish; billing_area_basis Select [Frame size] default Frame size |

Permissions:
- System Manager: full on all four.
- Fenestration Engineer: read/write/create on Price Structure and Profile Finish; read on Settings.
- Sales User: read on all four.

**Interfaces:**
- `PriceStructure.validate`:
  - keys are unique and are Python identifiers;
  - a Percentage head needs a base whose keys are earlier heads;
  - a Formula head needs a formula;
  - every formula and condition is checked by evaluating it with all variables set to 1 and `finish_type="Mill"`; a `RuleError` becomes `frappe.throw` naming the head.
- `to_cost_heads(name) -> tuple[CostHead, ...]` in `price_structure.py`.

- [ ] **Step 1: Write failing tests:**
  - the seeds exist after `after_migrate()`: Standard has 11 heads in order, the 4 finishes exist, and Settings defaults are set;
  - `test_price_structure_validates_formulas` (a bad formula and a later-base both raise `frappe.ValidationError` naming the head);
  - the profile snapshot includes `visible_perimeter_mm`;
  - a DXF upload sets `total_perimeter_mm`.
- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement; migrate**
- [ ] **Step 4: All backend modules + engine suite green. Commit** `feat(pricing): price structure, finishes, settings and profile perimeters`

---

### Task 3: Rate resolver

**Files:**
- Create: `onebook_fenestration/pricing/rates.py`
- Test: `onebook_fenestration/tests/test_rates.py`

**Interfaces:**
- `build_pricing_input(snapshot: SeriesSnapshot, result: EngineResult, finish: str, price_structure: str, price_list: str | None = None) -> PricingInput`:
  - `price_list` defaults to Settings `cost_price_list`.
  - Profile rate: the Item Price (`price_list_rate`) of the Fenestration Profile's linked `item` in that price list, per kg. Ruling: the profile Item's price is per kg, whatever the Item's stock uom.
  - Item rates: every BOM item code's Item Price.
  - Glass rate: the Fenestration Glass `item`'s Item Price, read as per m².
  - Anything missing (no linked item, or no Item Price) goes to `missing` with rate 0.
  - `finish_type` comes from Profile Finish.
  - Item Prices are fetched in one `frappe.get_all("Item Price", filters={"price_list": pl, "item_code": ["in", codes]}, fields=[...])`; no N+1 queries.
- `price_design(design: dict, series_version: str, finish: str, price_structure: str) -> tuple[EngineResult, PriceBreakdown]`: a convenience that runs compute + price for the API and Window Design.

- [ ] **Step 1: Write failing tests** (import CS400 in setUpClass; create a test Price List "Fen Test Cost" with Item Prices for E104156/E104159/E104160 at 300 and for H401 at 5; Glass 6CTG linked to a test Item priced at 1000):
  - the rates are picked up;
  - the H912 price is missing → in `missing`;
  - `price_design` on W01 returns `unit_price` > 0 and a `no_rate` warning.
- [ ] **Step 2: FAIL → Step 3: Implement → Step 4: PASS. Commit** `feat(pricing): item-price rate resolver`

---

### Task 4: Price on Window Design and in the APIs

**Files:**
- Modify: `fenestration/doctype/window_design/window_design.json` + `.py`, `api/design.py`
- Test: extend `tests/test_window_design.py`, `tests/test_api.py`, `tests/test_save_design.py`

**Interfaces:**
- **New Window Design fields:**
  - `finish` (Link Profile Finish; defaults to Settings default)
  - `price_structure` (Link Price Structure; defaults to Settings default)
  - in Results: `unit_price` (Currency, read only), `rate_per_sqft` (Currency, read only), `line_total` (Currency, read only), `pricing_json` (JSON, read only)
- **Recompute gate:** recompute when new, or when `design_json`, `series_version`, `finish` or `price_structure` changed. `line_total` is also recomputed when `qty` changes, without re-pricing.
- **Issues:** pricing issues are appended to `warning_count`.
- **`compute_design(design, series_version, finish=None, price_structure=None)`:** the result gains `pricing: {lines, unit_price, rate_per_sqft}` and its warnings join `issues`.
- **`save_design(..., finish=None, price_structure=None)`:** passes them through. Its response `results` gains `unit_price` and `line_total`.

- [ ] **Step 1: Write failing tests:**
  - W01 with test prices saves `unit_price` > 0 and `line_total = unit_price × qty`;
  - changing qty updates `line_total` only;
  - `test_price_not_recomputed_on_location_edit` (change an Item Price, edit location, save → `unit_price` unchanged; change finish → recomputed);
  - the API returns `pricing`.
- [ ] **Step 2: FAIL → Step 3: Implement; migrate → Step 4: all backend + engine green. Commit** `feat: price window designs and expose pricing in apis`

---

### Task 5: SPA — finish, price display, project value

**Files:**
- Modify: `frontend/src/api.ts`, `stores/designer.ts` (finish and price_structure in state, passed to compute/save), `components/PropertiesPanel.vue` (Finish select), `components/WindowCanvas.vue` (frame and sash fill from the finish colour), `components/ResultsBar.vue` (Unit price, ₹/sq.ft, and a "Pricing" tab listing cost-head lines with amounts), `pages/ProjectWorkspace.vue` (card price × qty, project total value)
- Test: extend the matching specs

**Interfaces:**
- Finish options come from a Profile Finish list (`useList`). The default is Settings `default_finish`, read via `frappe.client.get_single_value` or a small whitelisted `get_fenestration_defaults()` added to `api/design.py`.
- Canvas: the frame fill is the finish colour, and the sash band is the same colour lightened by 10%.
- Money is formatted `₹16,380.72` with `Intl.NumberFormat('en-IN', {style:'currency', currency:'INR'})`.

- [ ] **Step 1: Write failing tests:**
  - choosing finish BROWN-5104 → compute is called with `finish: "BROWN-5104"` and the canvas frame fill is `#6B3E26`;
  - ResultsBar shows the unit price and ₹/sq.ft;
  - the Pricing tab lists the head labels and amounts;
  - the workspace card shows line_total, and the header total value is the Σ of the line totals.
- [ ] **Step 2: FAIL → Step 3: Implement → Step 4: `yarn test`, `yarn build`, backend green.**
  - **Browser check (controller):** open W01 and set test prices in Desk. Confirm the price, the Pricing tab and the card value.
- [ ] **Step 5: Commit** `feat(frontend): finish selection and pricing display`

## Done when

- The Standard price structure (EvA's cost heads) and the seeded finishes exist after migrate.
- The engine prices a design from Item Prices, with `no_rate` warnings for gaps.
- Window Design stores its price, and it is only re-priced when its inputs change.
- The designer shows the finish colour, unit price, ₹/sq.ft and the cost-head breakdown.
- Project cards and the header show value.
- All suites are green and a browser check is done.
