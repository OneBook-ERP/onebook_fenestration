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
- The app enables Manufacturing Settings `make_serial_no_batch_from_work_order` (in setup) so Work Order submit creates the batch.

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
