# Plan 3b: SPA UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the gaps between the Plan 3 mockups (Window Designer, Project workspace) and the shipped `/fenestration` SPA that mislead users or slow the quoting journey (J2).

**Architecture:** Frontend-only changes in `frontend/src`, using frappe-ui components throughout. The data comes from existing APIs and standard REST list calls (`useList`). No backend change: this plan runs in parallel with Plan 5 in a separate worktree, where bench cannot run its tests.

**Tech Stack:** Vue 3, frappe-ui 1.1, Pinia, Vitest + @vue/test-utils, Tailwind (frappe-ui preset).

**Spec:**
- the mockup artifact https://claude.ai/artifact/FP2nfZygPtHHJQ4NXRehq9 (artboards "Window Designer" and "Project workspace"; local copies at `/tmp/claude-1000/-workspace-development-window-bench-16-apps-onebook-fenestration/735fc85f-6c15-4a2c-9de3-1d160b46d7ee/scratchpad/mockup/project/Main.dc.html` and `Project.dc.html`)
- `doc/app-map.md` §3 and §5, `doc/competitor-ux.md` §4
- the gap analysis below, where each task names the gap ids it closes

## Global Constraints

- **Frontend only.** Do not edit any Python, doctype JSON or hooks. Also leave `frontend/src/components/QuotePanel.vue` and `frontend/src/print.ts` alone: Plan 5 Task 5 edits them in parallel.
- **Worktree:** `/workspace/development/window-bench-16/apps/onebook_fenestration/.worktrees/plan-3b`, branch `feat/ui-polish` (based on `feat/production` at 2cda5cf). Verify with `cd frontend && yarn test && yarn build` inside the worktree.
- **Components:**
  - use frappe-ui components (Button, Badge, Alert, TabButtons/Tabs, Select, FormControl, Dropdown, Tooltip) and keep the two-layer SidebarRail + Sidebar shell;
  - every interactive element is a real `<button>`/`<a>`/`<input>`, and icon-only buttons have an `aria-label`;
  - touch targets are at least 36 px (`min-h-9`).
- **Data:** never invent data in the UI. A missing value shows "—".
- **Units:** lengths are shown in mm with 1 decimal, areas in sq.ft with 3 decimals, and money with the existing `formatMoney`.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Empty or failed compute** (no result yet, or `ok: false`): every new tab, count and pill renders "—" or 0 without throwing. Pinned by Task 1 `renders with no result`.
2. **Design with only fixed glass** (no sash): the panel label, typology and derived sizes still render. Pinned by Task 2 `fixed-only selection` and Task 4 `typology fixed only`.
3. **A project with 0 designs**, or with no quotation: the header KPIs show 0 and "Not quoted", and the tabs render. Pinned by Task 4 `empty project header`.
4. **Long design lists** (200 cards): search filters on ref, name and location without re-fetching. Pinned by Task 3 `search filters cards`.
5. **Phone width (390 px):** no horizontal page scroll in the designer, and the tools, canvas and properties stack. Pinned by Task 5 class assertions, plus a controller browser check after merge.

---

### Task 1: Results bar and toolbar fixes (D2, D3, D4, D7, D9, D11)

**Files:**
- Modify: `frontend/src/components/ResultsBar.vue`, `frontend/src/pages/Designer.vue`
- Test: `frontend/src/components/ResultsBar.spec.ts` (create), `frontend/src/pages/Designer.spec.ts`

**Interfaces:**
- Produces: `useProfileNames()` in `frontend/src/composables/profiles.ts`. It returns a `Ref<Record<string, string>>` mapping profile_code to profile_name, loaded once with `useList` on doctype "Fenestration Profile" (fields `name`, `profile_name`, limit 500). Task 2 reuses it.

- [ ] **Step 1: Write the failing tests:**
  - `error pill green when zero`: when errors is 0, the badge reads "0 errors" with theme green. When warnings is 0, no warnings badge renders. When there are 2 warnings, an orange "2 warnings" badge renders.
  - `cut list columns`:
    - the header row is exactly Profile, Code, Length (mm), Angles, Qty, Position, Panel;
    - a member `{profile:'E104156', length: 1219.0, angles:'[45, 45]', position:'L', panel:'F1'}` renders "1219.0", "45° / 45°", "L" and "F1";
    - the name comes from the mocked `useProfileNames`;
    - grouping keys include position and panel, so identical lengths on different panels are separate rows.
  - `gaskets tab`: BomRows with group "Gasket" appear only in a "Gaskets" tab, with columns Item, Name, Length (m) = Σ length/1000 at 3 dp. Tab labels carry counts: "Cut list · 13", "Hardware · n", "Gaskets · n", "Glass · n", "Issues · n".
  - `renders with no result`: with `store.result` null, no throw, and the tabs show "· 0".
  - `live price label`: the price reads "Live price ₹…", with helper text "From current rates; saved designs keep their priced value until repriced."
  - `results drawer collapses`: a "Hide results" toggle (`aria-expanded`) hides the tables and leaves the summary line, and the state persists in `localStorage` key `fen.resultsCollapsed`, with try/catch.
  - `tools explain disabled state`: when no leaf is selected, the tools nav shows the text "Select a panel on the drawing to use these tools", and each disabled tool has a Tooltip with the same text.
- [ ] **Step 2: Run and watch them fail.** Run `cd frontend && yarn test`. Expected: the new specs FAIL.
- [ ] **Step 3: Implement** in `ResultsBar.vue`, `Designer.vue` and `composables/profiles.ts`.
- [ ] **Step 4: Run** `yarn test && yarn build`. Expected: all pass.
- [ ] **Step 5: Commit** with message `fix(frontend): results bar pills, cut list columns, gaskets tab, live price label, tool hints`.

### Task 2: Designer properties and header (D5, D6, D8)

**Files:**
- Modify: `frontend/src/components/PropertiesPanel.vue`, `frontend/src/pages/Designer.vue`
- Create: `frontend/src/design/typology.ts`
- Test: `frontend/src/components/PropertiesPanel.spec.ts` (create), `frontend/src/design/typology.spec.ts` (create), `frontend/src/pages/Designer.spec.ts`

**Interfaces:**
- Consumes: Task 1 `useProfileNames` (not strictly needed here); `store.result.members` / `glass` (each has `path` and `panel`).
- Produces:
  - `typology(root: DesignNode) -> string` counts leaves:
    - "Fixed" for a lone fixed;
    - "Casement" for a lone sash;
    - otherwise e.g. "2-sash casement", "Casement + fixed", "Ventilator" (any louver), "Sash · fixed · sash" (3 leaves in order sash, fixed, sash).
    - Rule order: louver present → "Ventilator"; all sash → `${n}-sash casement` (n > 1); all fixed → "Fixed"; else join the unique leaf kinds as "Casement + fixed". Task 4 reuses it.
  - `panelLabel(path: string, result) -> string` returns the engine panel id of the first member or glass row whose `path` equals the leaf path. It falls back to the path.

- [ ] **Step 1: Write the failing tests:**
  - `typology.spec`: each rule above with literal trees, including `typology fixed only` → "Fixed".
  - `panel label`: the selected-panel header reads "Selected panel F1-S1" (not "F1.0") when the result has a member with that path and panel.
  - `derived sizes`: for a sash leaf, the panel shows "Glass cut {w} × {h} mm" from the matching `result.glass` row. When there is no row, it shows "—".
  - `fixed-only selection`: a fixed leaf shows its label and glass size, with no sash-only fields.
  - `glass is a select`: the glass field is a frappe-ui Select. Its options come from `useList` on "Fenestration Glass" (`name`, `glass_name`), and its labels read "{glass_name} ({name})". The current value is kept even when it is not in the list (shown as "{code} (unknown)").
  - `breadcrumb`: the header shows a link to the project ("Projects / {project}") and "{ref} · {typology}". Undo and Redo are icon buttons with `aria-label` "Undo"/"Redo". The view toggle is a two-option segmented control (Inside / Outside) with `aria-pressed`.
- [ ] **Step 2: Run and watch them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `yarn test && yarn build`. Expected: all pass.
- [ ] **Step 5: Commit** with message `feat(frontend): panel labels, derived glass size, glass picker, designer breadcrumb`.

### Task 3: Templates, duplicate and search (D1, P5)

**Files:**
- Create: `frontend/src/design/templates.ts`
- Modify: `frontend/src/pages/Designer.vue` (the new-design route reads `?template=`), `frontend/src/pages/ProjectWorkspace.vue` (New design menu, card Duplicate, search)
- Test: `frontend/src/design/templates.spec.ts`, `frontend/src/pages/ProjectWorkspace.spec.ts`, `frontend/src/pages/Designer.spec.ts`

**Interfaces:**
- Produces: `TEMPLATES: { id: string; label: string; build(width: number, height: number): Design }[]` with these ids and trees (default size 1200 × 1200, glass from the project's default glass if known, else the first leaf glass the existing blank design uses):
  - `casement-2`: v-split at width/2, sash + sash;
  - `ventilator`: v-split at 70%, louver (blades 7) + fixed;
  - `sash-fixed-sash`: v-split at thirds, sash · fixed · sash;
  - `top-light`: h-split at 25%, fixed (top) over sash;
  - `blank`: the current single-leaf default.
- Split positions are rounded to whole mm. Templates are design shapes, not series rules, so they live in the frontend (ruling: rules-as-data covers series numbers, not layout presets).

- [ ] **Step 1: Write the failing tests:**
  - `templates.spec`: each template builds a valid tree (leaf counts 2, 2, 3, 2, 1). `casement-2` at 915 × 1220 has split `at` [457] (rounded half).
  - `new design menu`: "New design" is a Dropdown listing the five templates. Choosing "2-sash casement" routes to `/projects/{p}/designs/new?series_version=…&template=casement-2`.
  - `designer applies template`: on the NewDesign route with `template=ventilator`, the store design root is a v-split with a louver child.
  - `duplicate card`: each card has a "Duplicate" button that calls `copyDesign(name)` and routes to the copy. It is disabled while running, and an error shows a toast.
  - `search filters cards`: with 3 designs, typing "W02" in the search input (label "Search designs") shows 1 card. Matching is case-insensitive over `design_ref`, `design_name` and `location`, client-side.
- [ ] **Step 2: Run and watch them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `yarn test && yarn build`. Expected: all pass.
- [ ] **Step 5: Commit** with message `feat(frontend): design templates, duplicate and search in project workspace`.

### Task 4: Project workspace tabs, header and cards (P1, P2, P3)

**Files:**
- Modify: `frontend/src/pages/ProjectWorkspace.vue`
- Test: `frontend/src/pages/ProjectWorkspace.spec.ts`

**Interfaces:**
- Consumes: Task 2 `typology`, the existing `quoteStatus(project)` from `api.ts`, `QuotePanel` (used as is, not edited), and Task 3's toolbar.
- Produces: tab ids `designs`, `quote`, `order`, `production`, `install`, `reports`.
  - `order`, `production`, `install` and `reports` are rendered disabled, with the tooltip "Coming soon".
  - The active tab is synced to the `?tab=` query, defaulting to `designs`.

- [ ] **Step 1: Write the failing tests:**
  - `tabs`: the tab labels are "Designs · {n}", "Quote", "Order", "Production", "Install", "Reports", with the last four disabled. QuotePanel renders only on the Quote tab, and the design grid only on Designs. `?tab=quote` opens Quote.
  - `header`:
    - a breadcrumb link "Projects" → `/projects`, then the project id;
    - the title;
    - a status Badge from `quoteStatus`: "Not quoted" (gray) when no quotation, "Draft quote" (orange) for docstatus 0, the quotation `status` (blue) for docstatus 1, and "Out of date" (red) when `is_stale`;
    - the quotation name;
    - KPIs Windows, Area (sq.ft), Basic value (Σ line_total), and "Grand total incl. GST" (`rounded_total`, "—" when not quoted).
  - `empty project header`: 0 designs and no quotation → Windows 0, Area 0.000, Grand total "—", "Not quoted".
  - `card details`: the card shows "{ref} · {typology}" and "× {qty}", "{series} · {glass names}", and a finish swatch plus finish name (add `finish` and `design_json` to the list fields).
    - The swatch colour comes from `Profile Finish` via `useList` (fields `name`, `finish_name`, `color` if the field exists, else a neutral gray).
    - An OK badge (green) shows when there are no errors and no warnings.
    - The footer reads "{area_sqft} sq.ft · {window_kg} kg" with the saved price labelled "Saved price {formatMoney(line_total)}" and "Priced {date}".
  - `typology fixed only`: a card whose tree is a single fixed leaf shows "· Fixed".
- [ ] **Step 2: Run and watch them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `yarn test && yarn build`. Expected: all pass.
- [ ] **Step 5: Commit** with message `feat(frontend): project workspace tabs, status header and richer design cards`.

### Task 5: Phone layout for the designer and workspace (D10, P6)

**Files:**
- Modify: `frontend/src/pages/Designer.vue`, `frontend/src/components/PropertiesPanel.vue`, `frontend/src/pages/ProjectWorkspace.vue`
- Test: `frontend/src/pages/Designer.spec.ts`, `frontend/src/pages/ProjectWorkspace.spec.ts`

**Rules:**
- Below the `md` breakpoint (768 px), the designer body becomes a column:
  - a horizontal, scrollable tools bar (`overflow-x-auto`, `flex-row`) at the top;
  - the canvas next, at a minimum height of 50vh;
  - the properties panel full-width below the canvas (no fixed `w-72`);
  - the results drawer collapsed by default (Task 1 toggle). The stored preference wins if present.
- At `md` and up, the current side-by-side layout is unchanged.
- The workspace header KPIs wrap into a 2-column grid below `sm`, and the tab bar scrolls horizontally.

- [ ] **Step 1: Write the failing tests** (class assertions, since jsdom has no layout):
  - the designer body has `flex-col md:flex-row`;
  - the tools nav has `flex-row overflow-x-auto md:flex-col md:w-36`;
  - the properties panel root has `w-full md:w-72`;
  - the results drawer is collapsed by default when `window.matchMedia('(max-width: 767px)')` matches (mock matchMedia) and nothing is stored;
  - the workspace KPI container has `grid-cols-2 sm:flex`, and the tab bar has `overflow-x-auto`.
- [ ] **Step 2: Run and watch them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `yarn test && yarn build`. Expected: all pass.
- [ ] **Step 5: Commit** with message `feat(frontend): phone layout for designer and project workspace`.

After the merge, the controller checks the 390 px layout in Chrome (viewport resize or device emulation): no horizontal page scroll, and all tools reachable.
