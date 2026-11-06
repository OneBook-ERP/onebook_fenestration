# Decision Log

Each entry records status, choice, reasoning and what would make us revisit. Domain context lives in [context.md](context.md).

## D1. Frontend framework: Vue 3 + frappe-ui (DECIDED 2026-10-29)

**Scope:** SPA for the window designer, estimates and the dealer portal. Masters and back-office screens stay in Desk.

**Framing fact:** the engine (geometry, rules, weights, validation, price) runs server-side in Python. The frontend only edits the design tree and draws SVG, so this choice carries less risk than it seems.

**Weighted comparison** (score 1–5, weight 1–5):

| Criterion | Wt | Vue 3 + frappe-ui | React + frappe-react-sdk |
|---|---|---|---|
| Frappe platform fit: auth, session, realtime, resources, bench build, embedding in Desk | 5 | 5: official kit; Desk already compiles `.vue` (form/workflow/print builders) | 4: proven by Raven (React 19 + frappe-react-sdk, on this bench); no Desk convention |
| UI kit consistent with Frappe products | 3 | 5: frappe-ui is the kit used by CRM, Helpdesk, Insights, Builder | 3: shadcn or custom, needs theming to match |
| Designer canvas: rect tree, drag splits, zoom, undo | 4 | 4: plain SVG + Pinia is enough | 5: more libraries (react-konva, xyflow, tldraw) |
| Native mobile path | 2 | 3: PWA / Capacitor | 5: React Native, code shared via monorepo (Raven `apps/native`) |
| Talent pool (India) | 3 | 3 | 5 |
| Open-source reference code in the same shape (CRM flows, list/kanban, portals) | 3 | 5: Frappe CRM, Helpdesk | 3: Raven |
| Long-term upkeep tracking Frappe releases | 3 | 5: maintained by Frappe | 4: community SDK, active |
| General ecosystem | 2 | 4 | 5 |
| **Total** | | **109** | **105** |

**Result:** close call, Vue wins. The deciding weights are Frappe fit, UI consistency and reference code. React's advantages (canvas libraries, native mobile, hiring) matter less here because:

- The designer edits constrained rectangles, not free-form CAD. Hand-rolled SVG is enough.
- The engine is server-side, so a native app would reuse little logic anyway.
- EvA itself is a responsive web app. Nothing in the BRD requires a native or offline app.

**Sensitivity:** raising the native mobile weight from 2 to 5 flips the result (Vue 118, React 120). The decision therefore depends on native mobile not being a requirement.

**Stack:** Vue 3 + TypeScript + Vite + frappe-ui + Pinia (tree state, undo/redo). The designer is a hand-written SVG component. Mobile is the same SPA as a responsive PWA.

**Revisit if:**

- The client requires a native or offline app (survey/quote with no network).
- We need a canvas capability only available in React.
- The team becomes React-only.

### D1 addendum: performance and usability (2026-10-29)

| Criterion | Wt | Vue | React |
|---|---|---|---|
| Runtime performance: fine-grained reactivity vs re-rendering subtrees; bundle size on low-end Android tablets | 4 | 5: only components that read changed state update; runtime ~35 KB gz | 4: re-renders subtrees unless memoized (React Compiler automates this); react + react-dom ~55–60 KB gz |
| Usability primitives: accessible headless components, touch, focus management | 4 | 4: Reka UI / Headless UI under frappe-ui | 5: Radix, React Aria (best in class) |

**New totals: Vue 145, React 141. Decision unchanged.**

Neither framework is the bottleneck. These architecture choices decide perceived speed:

- **Dragging a split:** client-only SVG geometry from split positions runs at 60 fps. The engine call (BOM, validation, price) happens on drop and debounced input, not on every pointer move.
- **Element count is small:** one window is about 10–80 SVG elements. Project and elevation lists use stored SVG snapshots, not live trees.
- **Large tables** (BOM, cutting schedule with thousands of pieces, 300+ designs): use row virtualization (TanStack Virtual has both Vue and React adapters). Paginate server-side.
- **Engine latency budget:** under 150 ms per design on the server. Cache the series snapshot per Series Version.
- **Undo/redo:** immutable tree snapshots in Pinia, capped history.

Usability comes from interaction design, not the framework:

- Pointer events for touch and mouse, large hit targets
- Snapping and numeric input for every dimension
- Live validation messages with fix hints
- Keyboard shortcuts, undo/redo
- Typology templates as starting points

frappe-ui also gives a look familiar to ERPNext and Frappe CRM users.

**Not counted:** Vue Vapor mode (no virtual DOM) as possible future upside. Check its stability before relying on it.

**Optional evidence spike (1 day):** drag-split prototype with about 200 SVG elements, profiled on a low-end Android tablet. Run it only if the perf concern persists. Expected result: both meet 60 fps.

### D1 addendum 2: competitor evidence (2026-10-29)

Evidence from [competitor-ux.md](competitor-ux.md):

- EvA's survey app is native Android, works offline, and pairs with BLE laser meters.
- EvA demos 3D, section and wall views.

Impact on the frontend choice:

- **3D viewer:** three.js works in both frameworks (TresJS for Vue, react-three-fiber for React; R3F is more mature). The viewer is an isolated widget that takes the computed geometry and renders it. Plain three.js inside a Vue component is enough, so this has a small effect on the choice.
- **Offline survey with BLE:** decouple it from the main SPA. Survey is a small app: site list, three width and three height readings, photos, checklist, sync. Options:
  - (a) PWA within the Vue SPA, with offline cache and Web Bluetooth (Android Chrome only).
  - (b) A separate small native app (Expo / React Native, the same shape as Raven `apps/native`) talking to the same APIs.

  Either way the main SPA choice is unaffected.

**Status: Vue 3 + frappe-ui is still decided for the main SPA.** The survey client is a separate decision, D9.

## D2. Engine runs server-side in Python (DECIDED)

Gives one source of truth, rules are evaluated with `frappe.safe_eval`, and results are unit-testable against the EvA golden PDFs. The designer calls a whitelisted API with debounce.

Trade-off: no offline design. Revisit only if D1's offline trigger fires.

## D3. Rules as data, not code (DECIDED)

Deductions, member, hardware and validation rules are doctype rows with text formulas. The Hilux engineer edits them, with no developer and no 25-day wait. Each quote freezes the Series Version it used.

## D4. One renderer, SVG snapshot (DECIDED)

The client draws SVG while editing. On save, the SVG snapshot is stored on the Window Design and reused in Quotation and Elevation PDFs. There is no separate Python renderer that could drift from the client one.

Action: verify the v16 PDF engine renders inline SVG correctly early on.

## D5. Dealer tenancy (OPEN)

- **A: single site, multi-company.** Each dealer is a Company. Gives inter-company PO→SO and a shared live catalog. Risk: data isolation, and dealers may not want Hilux seeing their customers.
- **B: site per dealer.** Clean isolation, but needs catalog sync from HQ plus an order bridge back to Hilux.

Hilux is also a fabricator, so HQ runs the same flow as a dealer either way.

## D6. Window as Item / BOM strategy (DECIDED 2026-10-30)

Work Order needs a BOM, and a BOM needs an Item. An Item may have many BOMs, and Sales Order Item carries `bom_no`, which Work Order creation uses.

**Decision:** keep the shared `FEN-WINDOW` Item (no Item per design).
- On Sales Order submit, create one BOM per Window Design line from the engine BOM (profiles, hardware, gaskets, glass) and set it on that Sales Order Item's `bom_no`. The BOM is never the Item's default: ERPNext makes the first active BOM of an Item its default, so a BOM hook resets `is_default` and clears `FEN-WINDOW`'s `default_bom` whenever it would point to a design BOM.
- The Sales Order "Work Order" button reads ERPNext's `get_work_order_items`, which offers the Item's default BOM. The app overrides that whitelisted method: design lines are offered with their own `bom_no` (same pending-qty rules), every other line comes from ERPNext unchanged.
- `FEN-WINDOW` becomes batch-tracked with batch-wise valuation. Each design line gets its own Batch, so a window keeps its own BOM cost through Work Order, stock, Delivery Note and invoice, and the batch identifies the window.
- Production then uses standard Work Order and Job Cards.
- The app enables Manufacturing Settings `make_serial_no_batch_from_work_order` so Work Order submit creates the batch. This production setup (that flag, the `FEN-WINDOW` stock and batch flags, moving material Items to Kg/Meter/Square Meter) runs once, at install or through the `production_item_setup` patch; migrate only creates missing records, so an admin's later changes stay.

Rejected:
- an Item per design (item explosion);
- a custom job flow without Work Order (stock and costing rebuilt by hand);
- BOM without Batch (finished-goods cost averaged across windows).

## D7. Pricing basis (OPEN)

BOM cost-plus expressed per sq.ft (what the data suggests) vs a flat sq.ft rate per series and finish. Needs Hilux confirmation.

## D8. Billing area (OPEN)

Frame size (what EvA does) vs wall opening. Note: the T&C say a size reduction after order does not reduce the price.

## D9. Survey client (OPEN)

The survey must handle offline sites, a BLE laser meter, photos and checklists, and sync later.

- **A: PWA within the Vue SPA.** One codebase. Web Bluetooth only works in Android Chrome; iOS Safari has none.
- **B: separate Expo/React Native app** on the same whitelisted APIs. Works on iOS and Android, with full offline and BLE support.

Decide after asking Hilux two questions: are surveyors' phones Android or iPhone, and how often are sites without network?

Update from the recording audio (low confidence): Hilux does not use EvA survey. Measurement is confirmed on a signed Estimate Confirmation Report. The first need is therefore digital confirmation and customer sign-off inside the Vue SPA. The BLE/offline survey app is deferred.

## D10. Hilux sheet vs EvA as the source of hardware quantities (OPEN, 2026-11-03)

The CS400 v2 and CS4800 v1 series data (`series_studio/data/`) translate the Hilux hardware sheets. The sheet's open window types are read as 1/2/3 shutters plus one fixed pane (mullions = shutters), which makes the sheet's per-mullion prose and its counts agree.

Current behaviour: the CLAUDE.md golden rule wins. Where the sheet and the EvA golden disagree (H425 handles, H429 hinge screws, H913 drain caps on open windows, H914 sealant, and the items EvA never produces: H407 and H408 chevrons and the G29 fixed-glass gasket), CS400 v2 reproduces EvA and the rule note says `SHEET SAYS: … (question Qx)`. CS4800 has no EvA golden for these items, so it follows the sheet. Hilux decides per item (`doc/hilux-questions.md` section 1); this stays OPEN until then.

Related choices made while translating the sheets (each is a rule note and a question in `doc/hilux-questions.md`):
- Rules tell sash glass from frame-glazed (fixed) glass by the engine variable `in_sash`, never by panel names. Thresholds used by several rules are series constants: `fastener_spacing` (500), `friction_hinge_12_max_w` (600), `rod_800_min_h` (700), `rod_1200_min_h` (1000).
- Typology counts come from plain per-frame, per-mullion, per-sash and per-window rules. Counts that no plain rule reproduces are expected deviations in `test_series_data`, each with its question id.
- CS4800 v1 had placeholder profiles, member rules and deductions copied from CS400 (codes `CS4800-PH-*`). CS4800 v2 replaces them with the DXF values (D11); `cs4800_v1.json` stays as the record of what v1 imported.
- A new glass imported from a series snapshot gets its own Item `FEN-GLASS-<code>` (Square Meter, kind Glass, HSN 70071900). Existing glasses and Items are never edited.
- Deploy path: `bench --site X execute onebook_fenestration.series_studio.data.import_hilux_series` imports the Hilux glass catalogue, CS400 v2 and CS4800 v2 (System Manager or Fenestration Engineer only). It is idempotent: each imported Series Version stores a SHA-256 of its merged data in the read-only field `source_hash`, and a series whose latest submitted version has the same hash is skipped. Versions created before the field existed have no hash, so the first run imports once.

## D11. Glazing beads and sash glass adaptors are glass-driven member rules (DECIDED 2026-11-03)

EvA cuts a glazing bead around every fixed pane and a glass adaptor around every sash pane, and picks the profile by glass thickness. The engine does the same from series data:

- Member rules have two more roles, `bead` (one member per side of each fixed pane) and `glass_adaptor` (one per side of each sash pane). Their formulas see `opening_w` / `opening_h` (glass size + 2 × the series constant `glass_clearance`), `position` (B/T/L/R), `glass_t`, `glass` and the series constants and deductions.
- Every member rule has an optional `when` condition (empty = always). For beads and adaptors every rule whose `when` holds cuts a member, so the profile follows the glass thickness by data (CS4800: CS4807 / CS4808 / CS4809 beads, HSL3409 / HSL3410 adaptors). Frame, sash and bar roles are cut once, so the first rule whose `when` holds wins. A fixed pane that no bead rule covers gets a `no_glazing_bead` warning when the series has bead rules.
- Bead and adaptor members carry their pane's panel id (fixed pane `F1`, sash pane `F1-S1`, the engine's names for EvA's F1-G1 / F1-S1-G2). They count in the cutting list, BOM and window weight like any member; an adaptor also weighs on its shutter (every member of a sash panel does).
- Series without bead or adaptor rules (CS400) compute exactly as before.
- A Fenestration Profile belongs to one series, but a member rule may use another series' profile (CS4807 is a CS400 profile and a CS4800 bead). The snapshot therefore includes every profile the version's member rules use as well as the series' own profiles.
- DXF profile perimeters live in `series_studio/data/hilux_profile_perimeters.json`, outside the series data and its `source_hash`. `import_hilux_series` copies them into `total_perimeter_mm` only where it is empty and never touches `visible_perimeter_mm`. The DXF value is taken as the total (coated) perimeter: the dev site's hand-entered visible perimeters (E104156 90, E104159 110, E104160 120, CS4807 40) are far below the DXF values (202, 269, 282, 140). Hilux to confirm and send visible perimeters (`doc/hilux-questions.md` 9.2).

Rejected: hard-coding bead and adaptor sizes in the engine (series numbers belong in data, D3); one bead profile per series without a thickness condition (EvA and the DXF use three beads and two adaptors).

## D12. Rate sheets and series readiness (DECIDED 2026-11-05)

- The rate sheet lists every item a series version uses (profiles, glass, hardware, gaskets). Importing it writes Item Prices on `Fenestration Settings.cost_price_list`, keyed by item + price list + stock uom + `valid_from`, non-batch, no customer or supplier, `packing_unit` 0. A new `valid_from` is a new price row; the same key updates in place.
- Import and download are gated to System Manager / Fenestration Engineer and bypass Item Price permissions on purpose (only the ERPNext master managers hold them). Import is POST only and reads only the user's own or readable files.
- Rates are read per kg (profiles), per m2 (glass) and per stock uom (others) without conversion, per the earlier ruling.
- The readiness report lists what still blocks pricing a version; a draft whose rules do not compile reports one blocking `rules` check.

## D13. Cross-section view (DECIDED 2026-11-05)

- The engine cuts the section from the layout and deductions; the API takes a design dict/JSON like `compute_design`.
- Profile outlines come from the Hilux section DXFs and are stored in the DB only, never committed.
- Orientation (changed 2026-11-06): the Hilux sheet draws some profiles with the depth along x (E104156, E104159, CS4801) and others with the face along x. Each Fenestration Profile has a `section_rotation` (0/90/180/270, editable data). The outline is stored as drawn; `width_mm` (face, along the cut) and `depth_mm` are its extents after rotation, and the `cross_section` API returns outlines already rotated. The section importer guesses 90 or 0 from Hilux's "DEPTH X FACE" names (e.g. "40MM X 60MM") against the drawn extents (1.5 mm tolerance), keeps any non-zero rotation already set, and lists profiles it cannot guess. Which quarter turn puts the outside at the top (90 vs 270) is for the engineer to correct.
- Glass is drawn as thick as its glass spec's overall `thickness_mm`.
- PROVISIONAL until checked visually: the mirror convention.

