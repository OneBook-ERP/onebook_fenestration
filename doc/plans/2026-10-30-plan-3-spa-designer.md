# Plan 3: Vue SPA Shell + Window Designer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `/fenestration` Vue single-page app. A sales user or dealer can:
- open a project and see its window designs as cards;
- draw a window by splitting cells (mullion/transom) and setting leaves (sash/fixed/louver);
- get the live cut list, weights and issues from `compute_design`;
- save the design (JSON + SVG snapshot) to a Window Design.

**Architecture:**
- The app is Vue 3 + TypeScript + frappe-ui + Pinia in `frontend/`. It is built by Vite into the app's `public/frontend` and served at `/fenestration` through `website_route_rules`.
- The design tree is the engine's JSON contract (Plan 1, Task 2). It is edited by pure TypeScript functions (unit-tested with Vitest) inside a Pinia store that keeps undo/redo history.
- The canvas is plain SVG drawn from a TypeScript mirror of the layout geometry. That geometry is for **drawing only**: lengths, weights and validation always come from the server engine (D2).
- Saving goes through a whitelisted `save_design` API. That API sanitizes the SVG snapshot (D4) against an allowlist before storing it.

**Tech Stack:**
- Node 24, yarn 1.22.
- Exact versions: frappe-ui `1.1.0`, vue `3.5.44`, vue-router `4.6.4`, pinia `3.0.4`, vite `6.4.5`, @vitejs/plugin-vue `5.2.4`, tailwindcss `3.4.19`, postcss `8.5.32`, autoprefixer `10.6.2`, typescript `5.9.3`, vitest `3.2.7`, @vue/test-utils `2.5.1`, jsdom `26.1.0`.
- frappe-ui 1.1.0 peers require vue-router 4 and tailwind below 4.
- Backend: Frappe v16 on `window.localhost`.

**Spec:**
- `doc/app-map.md` §3 (screens, designer layout) and §5 (navigation)
- `doc/decisions.md` D1 (Vue + frappe-ui), D2 (server engine, debounce), D4 (single SVG renderer)
- `doc/competitor-ux.md` §4 (patterns to copy)
- Mockup: https://claude.ai/artifact/FP2nfZygPtHHJQ4NXRehq9 (Window Designer + Project workspace boards)

## Global Constraints

- The frontend lives only in `frontend/`.
  - Build output goes to `onebook_fenestration/public/frontend/` and the entry HTML to `onebook_fenestration/www/fenestration.html`.
  - Both are git-ignored and produced by `yarn build`.
  - The app root `package.json` has `"build": "cd frontend && yarn build"` so `bench build --app onebook_fenestration` builds the SPA.
- Pin exact dependency versions (no `^`/`~`) to the Tech Stack list. Commit `frontend/yarn.lock`.
- The SPA route is `/fenestration` (frappe-ui vite plugin `frontendRoute: '/fenestration'`). The router base is `/fenestration`.
- **Design JSON contract** (must match `onebook_fenestration/engine/layout.py`):

  ```
  {width, height, series?, finish?, root: Node}
  Node = {type:"split", dir:"v"|"h", at:number[], children:Node[]}
       | {type:"sash", glass, opening?, hinge?, ghh?}
       | {type:"fixed", glass}
       | {type:"louver", glass, blades}
  ```

  - `at` holds centreline offsets in mm, measured from the cell's left (`v`) or bottom (`h`) edge, strictly increasing inside (0, span).
  - Node paths are `"F1"` for the root, then `"F1.<i>"`, `"F1.<i>.<j>"`. These are the same paths the engine puts on Issue/CutMember/GlassPane `path`.
- The frontend never computes lengths, weights or prices. It only draws geometry and calls `onebook_fenestration.api.design.compute_design`.
- Live compute is debounced at **300 ms** after the last edit. The canvas updates immediately.
- Frontend tests: `cd frontend && yarn test` (Vitest, jsdom). Backend tests: `bench --site window.localhost run-tests --app onebook_fenestration --module <module>`. The existing 32 app tests and 63 engine tests must stay green.
- UI copy is in English, with no emoji. Every icon-only button has an `aria-label`. Touch targets are at least 36 px. Follow the look of the mockup: Inter, neutral greys, a near-black primary button, blue (#2563EB) for selection.
- Commits on branch `feat/spa-designer`. Each ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never commit `node_modules`, build output, `doc/*.pdf|mp4|dxf` or `.superpowers/`.

## Review Focus

1. **Dragging a mullion past its neighbour or the frame edge.**
   - The tree must stay valid: positions strictly increasing and at least `MIN_CELL` = 100 mm from neighbours and edges.
   - The drag clamps; it never produces an invalid `at` that the server then rejects.
   - Owned by Task 2 (`clamps split move to keep min cell`).
2. **Rapid edits.**
   - Only the latest compute response may update the results, so a stale slow response arriving late must be ignored.
   - Owned by Task 5 (`ignores out-of-order compute responses`).
3. **SVG snapshot injection.**
   - A client could post SVG containing `<script>`, `on*=` handlers, `href`/`xlink:href`, or `<foreignObject>`. The server rejects or strips these before storing, because the SVG is later embedded in PDFs and cards.
   - Owned by Task 4 (`test_svg_sanitizer_strips_scripts_and_handlers`).
4. **Server errors shown inline, not as a crash.**
   - `{ok:false}` from `compute_design` shows a banner with the message and keeps the last good results greyed out.
   - Issues with a `path` highlight that cell.
   - Owned by Task 5.
5. **Duplicate design ref on save** (Window Design name is `{project}-{design_ref}`).
   - The user sees "A design with this ref already exists in this project", not a raw error.
   - Owned by Task 4 (`test_save_design_duplicate_ref_message`).

---

## File Structure

```
package.json                         root: {"private":true,"scripts":{"build":"cd frontend && yarn build","dev":"cd frontend && yarn dev"}}
frontend/
  package.json, yarn.lock, vite.config.ts, tsconfig.json, tailwind.config.js, postcss.config.js, index.html
  src/main.ts, src/App.vue, src/router.ts, src/index.css
  src/design/types.ts                DesignNode, Design, Rect, CellGeom, BarGeom
  src/design/tree.ts                 pure tree ops + validation
  src/design/geometry.ts             layout mirror for drawing
  src/stores/designer.ts             Pinia store: design, selection, history, compute state
  src/api.ts                         thin wrappers: computeDesign, saveDesign
  src/components/WindowCanvas.vue    SVG renderer + interactions
  src/components/PropertiesPanel.vue
  src/components/ResultsBar.vue
  src/components/AppShell.vue
  src/pages/Projects.vue, src/pages/ProjectWorkspace.vue, src/pages/Designer.vue
  src/**/*.spec.ts                   vitest
onebook_fenestration/hooks.py        + website_route_rules
onebook_fenestration/api/design.py   + save_design, get_design
onebook_fenestration/fenestration/svg.py   sanitize_svg(svg: str) -> str
onebook_fenestration/tests/test_save_design.py
.gitignore                           + frontend/node_modules, onebook_fenestration/public/frontend, onebook_fenestration/www/fenestration.html
```

---

### Task 1: Frontend scaffold, route and build

**Files:**
- Create: root `package.json`, everything under `frontend/` except `src/design`, `src/stores`, `src/components`, and `src/pages/*` beyond a placeholder `Home.vue`
- Modify: `onebook_fenestration/hooks.py`, `.gitignore`

**Interfaces:**
- Produces:
  - Vite config with the frappe-ui plugin. `frontendRoute: '/fenestration'`. The build writes to `../onebook_fenestration/public/frontend` with the index HTML at `../onebook_fenestration/www/fenestration.html`. Read `node_modules/frappe-ui/vite/index.js` for the exact option names (`buildConfig.outDir`, `indexHtmlPath`).
  - The `@` alias points to `src`.
  - `src/main.ts` mounts App with the router, Pinia, and frappe-ui's plugin/setup as frappe-ui 1.1.0 documents it. Read `node_modules/frappe-ui/src/index.ts` and README.
  - `hooks.py`: `website_route_rules = [{"from_route": "/fenestration/<path:app_path>", "to_route": "fenestration"}]`.
  - `yarn test` runs Vitest with the jsdom environment.

- [ ] **Step 1: Branch; write `frontend/src/smoke.spec.ts`** — `it('mounts App', ...)` mounts `App.vue` with a memory router and expects the text "Fenestration".
- [ ] **Step 2: `yarn install`, then `yarn test`; expect FAIL** (App.vue missing).
- [ ] **Step 3: Implement the scaffold.** App.vue renders `<RouterView/>`, and `Home.vue` shows the heading "Fenestration".
- [ ] **Step 4: Verify.**
  - `yarn test` passes.
  - `yarn build` exits 0 and creates `onebook_fenestration/www/fenestration.html` and `onebook_fenestration/public/frontend/assets/*.js`.
  - `curl -s -o /dev/null -w '%{http_code}' -H 'Host: window.localhost' http://localhost:8000/fenestration` returns 200 when `bench start` is running. If it isn't running, start it in the background first; never start a second instance.
- [ ] **Step 5: Commit** `feat(frontend): scaffold vue spa at /fenestration`

---

### Task 2: Design tree model and store

**Files:**
- Create: `frontend/src/design/types.ts`, `tree.ts`, `geometry.ts`, `frontend/src/stores/designer.ts`
- Test: `frontend/src/design/tree.spec.ts`, `geometry.spec.ts`, `frontend/src/stores/designer.spec.ts`

**Interfaces** (all pure; tree ops return a new Design and never mutate):
- `MIN_CELL = 100`
- `newDesign(width: number, height: number, root?: DesignNode): Design`. The default root is `{type:"fixed", glass:"6CTG"}`.
- `getNode(design, path: string): DesignNode`. Throws `Error("no node at <path>")`.
- `splitCell(design, path, dir: "v"|"h", count = 2): Design`. Replaces the leaf with a split into `count` equal children, each a copy of the leaf. `at` is rounded to 0.1 mm.
- `moveSplit(design, path, index: number, pos: number): Design`. Clamps `pos` to `[prev + MIN_CELL, next - MIN_CELL]`, where prev/next are the neighbouring `at` values or 0/span.
- `removeSplit(design, path): Design`. Replaces the split with its first child.
- `setLeaf(design, path, leaf: LeafNode): Design`
- `setSize(design, width, height): Design`. Scales every `at` proportionally, then clamps.
- `validateDesign(design): string | null`. Returns null when valid. Mirrors the engine rules: finite positive width/height, strictly increasing `at` inside (0, span), `len(at) == children-1`, known types, string glass.
- `layoutGeom(design): {cells: CellGeom[], bars: BarGeom[]}`, where `CellGeom = {path, x, y, w, h, node}` (y measured from the bottom, mm) and `BarGeom = {id, dir, splitPath, index, x, y, length}`. Ids `M1..`/`T1..` are numbered in the same tree order as the engine.
- Pinia `useDesignerStore()`:
  - state: `design`, `selectedPath`, `past: Design[]`, `future: Design[]` (history cap 50), `result`, `error`, `computing`, `requestSeq`
  - actions: `apply(fn: (d: Design) => Design)` (pushes history, clears future), `undo()`, `redo()`, `select(path)`

- [ ] **Step 1: Write failing tests:**
  - `splitCell` on a 915×1220 fixed root with `v` → `at: [457.5]` and two children.
  - `moveSplit` clamps (`at:[457.5]`, pos 5 → 100; pos 900 → 815).
  - `setSize` from 915 to 1830 doubles `at`.
  - `validateDesign` rejects `at:[0]` and unknown types, and accepts the W01 JSON (copy `onebook_fenestration/engine/tests/fixtures/w01.json` into `frontend/src/design/__fixtures__/w01.json`).
  - `layoutGeom(W01)`: two cells at x 0 and 457.5, width 457.5; bar `M1` at x 457.5 with length 1220.
  - Nested transom: ids in tree order.
  - Store: apply/undo/redo restore designs; history is capped at 50.
- [ ] **Step 2: `yarn test`; expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: `yarn test`; expect PASS. Commit** `feat(frontend): design tree model and designer store`

---

### Task 3: WindowCanvas SVG component

**Files:**
- Create: `frontend/src/components/WindowCanvas.vue`
- Test: `frontend/src/components/WindowCanvas.spec.ts`

**Interfaces:**
- Props: `design: Design`, `selectedPath: string | null`, `issuePaths: string[]`, `view: "inside" | "outside"`.
- Emits: `select(path)`, `move-split({splitPath, index, pos})`.
- Rendering (drawing constants only):
  - `FRAME_FACE = 42`, `BAR_FACE = 40`, `SASH_FACE = 50` mm, scaled to fit the viewBox with 60 px padding for dimension chains.
  - Frame band; one `<rect data-path>` per cell.
  - Sash leaves: an inner sash band plus dashed opening lines with the apex on the hinge side. Hinge left/right is mirrored when `view === "outside"`.
  - Louver: horizontal blade lines.
  - Fixed: a "+" mark.
  - Glass numbers in tree order; labels `F1`, `S<n>`, `M<n>`/`T<n>`; `GHH = <ghh>` when set.
  - A dimension chain below the frame (each column width, then the total) and one on the left (each row height, then the total), in mm.
  - The selected cell is outlined in `#2563EB` (3 px). Cells in `issuePaths` get an amber outline (`#D97706`).
  - The root `<svg>` has `role="img"` and an `aria-label` summarising W×H and the leaf count.
- Interactions:
  - Clicking a cell emits `select`.
  - Pointer-dragging a bar converts pointer deltas to mm through the current scale and emits `move-split` on every move. The store clamps. Use pointer events with `setPointerCapture`.
- Exposes `getSvgMarkup(): string` (`outerHTML` of the root `<svg>`) for the save snapshot.

- [ ] **Step 1: Write failing tests:**
  - W01 renders 2 cell rects with `data-path` `F1.0` and `F1.1`, the label `M1`, and the dimension texts `457.5` and `915`.
  - Clicking `[data-path="F1.1"]` emits `select` with `"F1.1"`.
  - A bar `pointerdown` + `pointermove` of +20 px emits `move-split` with `index 0` and a pos greater than 457.5.
  - With `selectedPath "F1.0"`, that rect has stroke `#2563EB`.
  - `getSvgMarkup()` starts with `<svg` and contains no `<script`.
- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run; expect PASS. Commit** `feat(frontend): svg window canvas with selection and mullion drag`

---

### Task 4: Backend `save_design`, `get_design` and SVG sanitizer

**Files:**
- Create: `onebook_fenestration/fenestration/svg.py`
- Modify: `onebook_fenestration/api/design.py`, `onebook_fenestration/fenestration/doctype/window_design/window_design.py`
- Test: `onebook_fenestration/tests/test_save_design.py`

**Interfaces:**
- `sanitize_svg(svg: str) -> str`:
  - Parse with `xml.etree.ElementTree`, with DTDs and entities rejected: check the raw text for `<!DOCTYPE` / `<!ENTITY`, and raise `frappe.ValidationError` if found.
  - Allowed elements: `svg g rect line path text tspan circle polygon polyline title`.
  - Allowed attributes: `x y x1 y1 x2 y2 width height d points cx cy r fill stroke stroke-width stroke-dasharray font-size font-family font-weight text-anchor transform viewBox xmlns role aria-label class data-path opacity`.
  - Disallowed elements are removed together with their subtree. Disallowed attributes are dropped.
  - Return the serialized string. Inputs over 500 KB raise "SVG too large".
- `WindowDesign.validate` runs `design_svg = sanitize_svg(design_svg)` when `design_svg` is set and changed.
- `@frappe.whitelist() save_design(project: str, design_ref: str, series_version: str, design: dict|str, svg: str = "", qty: int = 1, design_name: str = "", location: str = "", name: str | None = None) -> dict`:
  - Inserts a new Window Design, or updates `name` if given.
  - Checks permissions: `frappe.has_permission("Window Design", "write" if name else "create", name, throw=True)`.
  - Returns `{"ok": True, "name": doc.name, "results": {area_sqft, window_kg, error_count, warning_count}}`.
  - `frappe.DuplicateEntryError` → `{"ok": False, "message": _("A design with this ref already exists in this project")}`.
  - `frappe.ValidationError` → `{"ok": False, "message": str(exc)}`.
- `@frappe.whitelist() get_design(name: str) -> dict` returns `{name, project, design_ref, design_name, qty, location, series_version, design_json (dict), result_json (dict), design_svg}` after a read-permission check.

- [ ] **Step 1: Write failing tests** (CS400 imported in `setUpClass`, as in `test_window_design`):
  - `test_svg_sanitizer_strips_scripts_and_handlers`: input contains `<script>`, `onclick=`, `<foreignObject>` and `href=`. The output has none of them and keeps `<rect data-path="F1.0">`.
  - `test_svg_sanitizer_rejects_entities`: `<!DOCTYPE ... <!ENTITY` raises `frappe.ValidationError`.
  - `test_save_design_insert_and_update`: insert W01 → `ok True`, `area_sqft == 12.013`. Update with qty 3 → the same name, and qty 3 is stored.
  - `test_save_design_duplicate_ref_message`: saving a second time with the same ref and no name → `ok False` with the exact message.
  - `test_get_design_roundtrip`: `design_json` comes back as a dict equal to W01.
- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run, plus all earlier backend modules; expect PASS. Commit** `feat(api): save_design with sanitized svg snapshot`

---

### Task 5: Designer page

**Files:**
- Create: `frontend/src/api.ts`, `frontend/src/components/PropertiesPanel.vue`, `frontend/src/components/ResultsBar.vue`, `frontend/src/pages/Designer.vue`
- Modify: `frontend/src/stores/designer.ts` (compute action), `frontend/src/router.ts`
- Test: `frontend/src/pages/Designer.spec.ts`, `frontend/src/stores/compute.spec.ts`

**Interfaces:**
- `api.ts`:
  - `computeDesign(design: Design, seriesVersion: string): Promise<ComputeResponse>` calls `onebook_fenestration.api.design.compute_design` through frappe-ui's call helper, with the design JSON-stringified.
  - `saveDesign(args): Promise<SaveResponse>`
  - `getDesign(name): Promise<...>`
  - Each one is a single function so tests can mock it with `vi.mock('@/api')`.
- Store additions:
  - `scheduleCompute()`: debounce 300 ms, then `requestSeq += 1`, call `computeDesign`, and apply the response only if its seq equals the latest `requestSeq`.
  - `ok:true` → `result = response.result`, `error = null`.
  - `ok:false` → `error = response.message`, and keep the previous `result`.
  - Every `apply()` calls `scheduleCompute()`.
- Routes: `/fenestration/projects/:project/designs/new` and `/fenestration/projects/:project/designs/:name`. The query `series_version` is required for new designs.
- Layout per the mockup:
  - **Header:** back link to the project, the ref, the series chip, Undo/Redo, the Inside/Outside toggle, and Save.
  - **Left tools:** Split vertical, Split horizontal, Sash, Fixed glass, Louver. These act on the selected leaf.
  - **Centre:** `WindowCanvas`.
  - **Right `PropertiesPanel`:**
    - basic info: ref, qty, W, H, location;
    - the selected leaf: opening (in/out), hinge (left/right/top), GHH, glass code text input;
    - split fields: the `at` positions as numeric inputs.
  - **Bottom `ResultsBar`:** area m²/sq.ft, window kg, shutter kg per panel, error and warning counts, and tabs for cut list, hardware, glass and issues. The tabs read `result.members`, `result.bom`, `result.glass` and `result.issues`. Issue rows show the path, and clicking one selects that path.
  - **Error banner** when `error` is set.
- Save calls `saveDesign` with `svg = canvas.getSvgMarkup()`, then routes to the saved name. `{ok:false}` shows the message in a toast or banner.

- [ ] **Step 1: Write failing tests:**
  - Compute store with fake timers:
    - three `apply()` calls within 300 ms → `computeDesign` is called once;
    - out-of-order: the first call resolves after the second → `result` equals the second response (**Review Focus 2**).
  - `ok:false` → `error` is set and the previous `result` is kept.
  - Designer page with a mocked api:
    - clicking a cell, then "Split vertical" → the canvas shows `M1`;
    - the ResultsBar shows `12.013` after the mocked compute;
    - Save calls `saveDesign` with an svg starting `<svg` and `design.width` 915;
    - an issue row with path `F1.0`, when clicked, selects `F1.0`.
- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: `yarn test` PASS; `yarn build` exits 0. Commit** `feat(frontend): window designer page with live compute and save`

---

### Task 6: App shell, projects list and project workspace

**Files:**
- Create: `frontend/src/components/AppShell.vue`, `frontend/src/pages/Projects.vue`, `frontend/src/pages/ProjectWorkspace.vue`
- Modify: `frontend/src/router.ts`, `frontend/src/App.vue`; remove `Home.vue`
- Test: `frontend/src/pages/Projects.spec.ts`, `ProjectWorkspace.spec.ts`

**Interfaces:**
- **AppShell** (user request: frappe-ui's two-layer sidebar, frappe-ui 1.1.0 `SidebarRail` + `Sidebar`):
  - **`SidebarRail`** (50 px icon column):
    - top: app logo/home;
    - middle (`flex-1`): one `SidebarRailItem` per module, each with an icon and a tooltip label:
      - Projects (`lucide-folder-kanban`, route `/projects`);
      - Production (`lucide-factory`), Install (`lucide-wrench`) and Orders (`lucide-package`), all disabled with the description "Soon";
      - Series Studio (`lucide-layers`), shown only to roles System Manager / Fenestration Engineer, opening `/app/profile-series` in Desk for now;
    - bottom: `SidebarRailItem` with the user `Avatar` and a menu containing "Open Desk" (`/app`) and "Log out".
  - **`Sidebar`** (wide column, collapsible with `SidebarCollapseToggle`) holds the **active module's** sub-navigation. For Projects:
    - `SidebarHeader` "Projects";
    - items "All projects" and "Recent", plus a `SidebarSection` "Recent projects" listing the 5 most recently modified projects (`route` to each).
  - Below 768 px the `Sidebar` is collapsed by default and the rail stays visible.
  - Unauthenticated users are redirected to `/login?redirect-to=/fenestration`.
  - Read `node_modules/frappe-ui/src/components/Sidebar/*.md` and `SidebarRail/*.md` for the exact props.
- **Routes:** `/fenestration` redirects to `/fenestration/projects`; `/fenestration/projects`; `/fenestration/projects/:project`; plus the Task 5 designer routes.
- **Projects:**
  - A list of Fenestration Project (fields `name, project_title, customer, modified`) through frappe-ui's list helper, with a search box.
  - A "New project" dialog: title, customer (optional), default series version, chosen from published versions only (`docstatus = 1`). It creates the project and routes to it.
- **ProjectWorkspace:**
  - Header: project title and totals, computed client-side from the designs' stored results (count Σqty, Σ area_sqft×qty, Σ window_kg×qty).
  - A grid of design cards. Each card shows the sanitized `design_svg` as an `<img>` with the src `data:image/svg+xml;utf8,` plus the encoded SVG, so no inline injection. It also shows ref × qty, series, area, an error badge, and an "Edit design" link.
  - A "New design" button opens the designer with the project's default series version.

- [ ] **Step 1: Write failing tests** (mock the frappe-ui list/resource helpers):
  - AppShell renders a `SidebarRail` with items Projects, Production, Install and Orders (the last three disabled), plus a `Sidebar` containing "All projects".
  - Projects renders two mocked projects and filters by search.
  - Workspace renders cards for two mocked designs and the totals (qty 260 + 60 = 320 windows).
  - A card thumbnail is an `<img>` whose src starts with `data:image/svg+xml`.
  - "New design" routes to `/fenestration/projects/FP-2026-00001/designs/new?series_version=CS400-V01`.
- [ ] **Step 2: Run; expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: `yarn test` PASS; `yarn build` exits 0; all backend modules and the engine suite still green.**
  - Manual smoke with `bench start` running: log in as Administrator, open `/fenestration`, create a project, create a 2-sash design, save, and see its card.
  - Record a screenshot path, or the observed result, in the report.
- [ ] **Step 5: Commit** `feat(frontend): app shell, projects list and project workspace`

## Done when

- `/fenestration` serves the SPA.
- A user can create a project, draw W01 by splitting and setting sashes, and see live results matching the engine (12.013 sq.ft).
- Saving stores the JSON and a sanitized SVG, and the card shows the thumbnail.
- `yarn test` passes, `yarn build` passes, and the backend and engine suites are green.
