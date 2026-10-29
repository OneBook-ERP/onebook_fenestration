# Plan 4b: Quotation and Quote Documents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a priced Fenestration Project into an ERPNext Quotation, with GST and transport, and produce the three customer documents Hilux sends today from EvA:
- **Quotation** (Hilux letterhead, one block per window with its elevation drawing, specifications and price, then totals and terms);
- **Elevation Report**;
- **Estimate Confirmation**, a pre-production sign-off sheet with checkboxes and site checklist.

**Architecture:**
- **Pricing stamp.** Prices are stamped with the price list and the date they were priced. A project-level `reprice_project` action re-prices on purpose; this closes the stored-vs-live gap deferred from Plan 4.
- **Quotation API.** `make_quotation(project)` builds or updates a **draft** ERPNext Quotation with one line per Window Design, using a generic non-stock item `FEN-WINDOW` (ruling for quoting; D6 manufacturing BOM stays open) plus a `FEN-TRANSPORT` line. GST comes from india_compliance's Output GST templates. ERPNext computes the totals.
- **Print formats.** These are standard, app-owned Jinja print formats. Elevation drawings are embedded as `<img src="data:image/svg+xml;base64,...">` from the stored, sanitized `design_svg`, never with `|safe` on raw SVG. PDFs are rendered by the site's wkhtmltopdf.
- **SPA.** The project workspace gains a Quote panel: customer, transport, Reprice, Create/Update Quotation, and links to the three PDFs.

**Tech Stack:** Frappe v16 / ERPNext v16 / india_compliance on `window.localhost`. The Company is "Hilux System Windows Pvt Ltd" with GSTIN 33AAHCH3108G1Z0 and Output GST templates "Output GST In-state - Hilux" / "Output GST Out-state - Hilux". Letter Head is "Company Letterhead". PDFs use wkhtmltopdf. The SPA is Vue 3 + frappe-ui 1.1.0.

**Spec:**
- The EvA sample PDFs in `doc/` (git-ignored; structure documented in `doc/context.md` §3 "Sample outputs" and "Commercial terms").
- `doc/competitor-ux.md` §1 (Report tab: card groups, favourites, download PDF).
- `doc/app-map.md` §3 (Quote tab) and §6 J2/J3.
- `doc/decisions.md` D4 (single SVG renderer) and D6 (window as Item, still open for manufacturing).

## Global Constraints

- **Generic quote items** are created idempotently by `after_install`/`after_migrate`:
  - `FEN-WINDOW` "Window (custom fabricated)": is_stock_item 0, is_sales_item 1, item_group "Fenestration", stock_uom "Nos", gst_hsn_code "761010" when the field exists (create GST HSN Code 761010 if missing).
  - `FEN-TRANSPORT` "Transportation": is_stock_item 0, gst_hsn_code "996511" (create if missing).
- **Custom fields** go in `setup/custom_fields.py` (all prefixed `fen_`):
  - Quotation: `fen_project` (Link Fenestration Project, read_only, insert_after `customer_name`)
  - Quotation Item: `fen_window_design` (Link Window Design, read_only, insert_after `item_code`)
- **New Fenestration Project fields:**
  - `transport_charges` (Currency, default 0)
  - `terms` (Link Terms and Conditions)
  - `quotation` (Link Quotation, read_only)
  - `company` (Link Company; defaults to the Global Defaults company)
- **Quotation line per design:**
  - item_code `FEN-WINDOW`, qty = design.qty, rate = design.unit_price, uom "Nos", `fen_window_design` = design name;
  - item_name = `"{design_ref} — {design_name or typology}"`;
  - description = a short HTML-free spec line: `"{W} × {H} mm · {series} · {finish_name} · {glass names} · {area_sqft} sq.ft"`.
- **Transport:** when transport_charges > 0, one `FEN-TRANSPORT` line with qty 1 and rate = transport_charges.
- **GST template:** if the customer has a billing address whose `gst_state` differs from the company's state → "Output GST Out-state - {abbr}"; otherwise "Output GST In-state - {abbr}". ERPNext/india_compliance compute the totals. Never hand-compute GST.
- **Quotable gate:** `make_quotation` refuses when the project has no customer or no designs. It also refuses when any design has `error_count > 0` or `pricing_warning_count > 0`. The message lists the offending design refs.
- **Draft handling:**
  - If `project.quotation` is a **draft**, replace its items and taxes.
  - If it is submitted or cancelled (or missing), create a new Quotation and point `project.quotation` at it.
  - `fen_project` is always set.
- **Pricing stamp:** `pricing_json` gains `price_list` and `priced_on` (ISO datetime) whenever a design is (re)priced.
- **`reprice_project(project)`:** whitelisted; needs write on the project. It forces a recompute and re-price of every design (bypassing the input-change gate) and returns `{repriced, failed: [{design, message}]}`.
- **Print formats** (standard, module "Fenestration"):
  - "Fenestration Quotation" on Quotation;
  - "Fenestration Elevation" and "Fenestration Estimate Confirmation" on Fenestration Project.

  All three use the Letter Head through Print Settings. Money uses `frappe.format(value, {"fieldtype": "Currency"})`. Elevation images use the `fen_svg_data_uri(svg)` Jinja method, registered via `jinja` hooks, which returns `data:image/svg+xml;base64,...` or "" for empty input.
- **Seed Terms and Conditions** "Hilux Standard Terms" (only if missing). It is an ordered list of the 21 commercial terms from the EvA quotation, condensed into one line each and already summarised in `doc/context.md` §3:
  - payment: 90% advance with work order, 10% before dispatch
  - validity 10 days; delivery 60 days from advance plus confirmation
  - advance non-refundable once production starts
  - no price reduction for site finishing size changes
  - changes beyond ±25 mm or to opening, colour, glass, quantity or hardware are new scope
  - materials 6063-T6, glass Saint-Gobain / AIS / Guardian, SS304 mesh, Jotun / AkzoNobel / Pulver coating
  - 10-year warranty (exclusions)
  - finish surcharges: Matt 0%, Texture 2%, Wooden 12%
  - site readiness and measurement responsibility
  - installation scope; scaffolding by client; site conditions; access and utilities; storage
  - breakage after delivery; force majeure
  - no negotiation after confirmation; jurisdiction Karur, Tamil Nadu; price escalation

  Write each term in your own words. Do not copy the PDF text.
- **Tests:** backend modules via `bench --site window.localhost run-tests --app onebook_fenestration --module <module>`; engine suite; `cd frontend && yarn test && yarn build`. All existing tests stay green. **Never modify or save existing dev-site records** (e.g. FP-2026-00001); tests create their own data.
- **Commits** on branch `feat/quote-documents`, each ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never commit build output, `doc/*.pdf|mp4|dxf` or `.superpowers/`.

## Review Focus

1. **Quoting stale or unpriced designs.** A design with a `no_rate` / `no_perimeter` warning or an engine error must never reach a Quotation line at ₹0 or the wrong price. Owned by Task 2: `test_make_quotation_refuses_unpriced_designs`.
2. **Re-running make_quotation.**
   - On a draft, it updates in place: no duplicate Quotation, and lines match the current designs (removed designs disappear).
   - On a submitted Quotation, it creates a new one and never edits the submitted one.
   - Owned by Task 2.
3. **GST correctness.** In-state gives CGST+SGST and out-state gives IGST, as computed by ERPNext/india_compliance. Grand total = net + taxes, never hand-computed. Owned by Task 2.
4. **Print safety.**
   - Design SVG appears only as a base64 data-URI `<img>`.
   - Project and design text fields are auto-escaped by Jinja.
   - A design with an empty SVG prints a placeholder, not a broken image.
   - Owned by Task 3.
5. **PDF rendering.** `frappe.get_pdf` on each format returns bytes starting `%PDF` for a project with 2 designs. A wkhtmltopdf failure must surface as a test failure, not a silent blank page. Owned by Task 3.

---

## File Structure

```
onebook_fenestration/setup/install.py              + quote items, HSN codes, Hilux Standard Terms
onebook_fenestration/setup/custom_fields.py        + Quotation.fen_project, Quotation Item.fen_window_design
onebook_fenestration/fenestration/doctype/fenestration_project/  + transport_charges, terms, quotation, company
onebook_fenestration/fenestration/doctype/window_design/window_design.py   price stamp
onebook_fenestration/fenestration/quotation.py     make_quotation(project) -> str; reprice_project(project) -> dict
onebook_fenestration/fenestration/print_format/{fenestration_quotation,fenestration_elevation,fenestration_estimate_confirmation}/
onebook_fenestration/utils/jinja.py                fen_svg_data_uri(svg) -> str
onebook_fenestration/hooks.py                      + jinja = {"methods": [...]}
onebook_fenestration/api/project.py                whitelisted wrappers: make_quotation, reprice_project, quote_status
onebook_fenestration/tests/test_quotation.py, test_print_formats.py
frontend/src/components/QuotePanel.vue (+ spec), pages/ProjectWorkspace.vue, api.ts
```

---

### Task 1: Price stamp and `reprice_project`

**Files:**
- Modify: `fenestration/doctype/window_design/window_design.py`
- Create: `fenestration/quotation.py` (only `reprice_project` for now), `api/project.py`
- Test: `tests/test_quotation.py`

**Interfaces:**
- `pricing_json` gains `price_list` (the cost price list used) and `priced_on` (`frappe.utils.now()`), set wherever a design is priced (validate gate and backfill).
- `WindowDesign.reprice()` forces `compute_results` regardless of the gate, then saves.
- `reprice_project(project: str) -> dict`: requires `frappe.has_permission("Fenestration Project", "write", project, throw=True)`. Returns `{"repriced": int, "failed": [{"design": name, "message": str}]}`.
- `api/project.py`: `@frappe.whitelist() def reprice_project(project)` delegates to it.

- [ ] **Step 1: Write failing tests** (own test data: import CS400, a test price list, a project with 2 designs):
  - `test_price_stamp_present` (`pricing_json.price_list` == the Settings list; `priced_on` is set);
  - `test_reprice_project_picks_up_new_item_price` (change an Item Price → `unit_price` unchanged after a location edit, changed after `reprice_project`);
  - `test_reprice_requires_write` (Guest → PermissionError).
- [ ] **Step 2: FAIL → Step 3: Implement → Step 4: all suites green. Commit** `feat: price stamp and project reprice`

---

### Task 2: Quotation from project

**Files:**
- Modify: `setup/install.py`, `setup/custom_fields.py`, `fenestration_project.json/.py`, `fenestration/quotation.py`, `api/project.py`
- Test: `tests/test_quotation.py`

**Interfaces:**
- `make_quotation(project: str) -> str` (the Quotation name):
  - checks write on the project and create (or write) on Quotation, then applies the quotable gate;
  - builds or updates a draft per the constraints, with company = project.company, party_name = project.customer, quotation_to "Customer", transaction_date today, valid_till = today + 10 days, tc_name = project.terms (default "Hilux Standard Terms"), terms text from it, letter_head "Company Letterhead" if it exists;
  - selects the GST template, then calls `quotation.run_method("set_missing_values")` and `calculate_taxes_and_totals()`, saves it, and sets `project.quotation`.
- `quote_status(project: str) -> dict` returns `{quotation, docstatus, status, grand_total, net_total, total_taxes_and_charges}` or `{quotation: None}`.
- `api/project.py` exposes both as whitelisted functions. `make_quotation` returns `{"ok": True, "quotation": name}` or `{"ok": False, "message": ...}` for gate failures; it never raises for them.

- [ ] **Step 1: Write failing tests** (a test Customer "Fen Test Customer" with no address, i.e. in-state; a second customer with an out-of-state billing address with `gst_state` "Karnataka"):
  - `test_make_quotation_lines_and_totals`:
    - 2 designs + transport 1000 → 3 lines;
    - each window line has rate = unit_price, qty = design qty, `fen_window_design` set;
    - the taxes template is In-state with CGST+SGST rows;
    - grand_total == net_total + total_taxes_and_charges.
  - `test_out_of_state_uses_igst`.
  - `test_make_quotation_refuses_unpriced_designs` (a design with `pricing_warning_count > 0` → ok False, and the message names its ref).
  - `test_remake_updates_draft_in_place` (remove a design → same Quotation name, that line gone).
  - `test_submitted_quotation_not_modified` (submit, then remake → a new name; the old one is unchanged).
  - `test_no_customer_refused`.
- [ ] **Step 2: FAIL → Step 3: Implement; migrate → Step 4: all suites green. Commit** `feat: build erpnext quotation from fenestration project`

---

### Task 3: Print formats and PDFs

**Files:**
- Create: the three print formats (JSON with `doc_type`, `module`, `standard: "Yes"`, `print_format_type: "Jinja"`, `custom_format: 1`, `html`), `utils/jinja.py`, hooks `jinja`
- Test: `tests/test_print_formats.py`

**Interfaces and layout** (mirror the EvA PDFs' structure, in Hilux's look: clean, black text, thin grey rules):
- **Fenestration Quotation (on Quotation):**
  - **Page 1:** cover letter: To customer, then Quote No / project / date line, a short introduction in your own words, the enclosure list, and signatory.
  - **Per design:** a block (page-break-inside: avoid):
    - the elevation image (max 60 mm wide, "View from inside" caption);
    - a spec table: Code, Name, Size, Profile system, Glass, Finish, Location;
    - computed values: Sq.Ft per window, Value per Sq.Ft, Unit price, Quantity, Value, Weight;
    - accessories: sash profile, handle, friction stay.

    Data comes from the linked Window Design via `fen_window_design`, its `result_json` (bom/members) and `pricing_json`.
  - **Quote total table:** No. of windows, Total area sq.ft, Basic value, Transportation, Total project cost, GST (from the Quotation taxes), Grand total, Average price per sq.ft without GST.
  - **Then:** Terms (from `tc_name`), the acceptance line, and the signature boxes.
- **Fenestration Elevation (on Fenestration Project):** a header table (project, project code, total qty), then a 2-column grid of cards: image, Design Ref, Qty, Location, Color, Name, Series, Glass.
- **Fenestration Estimate Confirmation (on Fenestration Project):**
  - per design a row: drawing; specification list (W, H, Qty, Location, Profile color, Glazing, System, Handle, Frame/Sash profile, Friction stay, Weight); a "Revise" checkbox per spec line; a "Deviation" column; and a "Revised drawing (only if required)" box with a "Comments for sales team" area;
  - then a site requirements checklist (Scaffolding, Unloading, Lifting, Power and water, Storage) with Yes/No boxes;
  - then customer and Hilux signature and date lines.
- `fen_svg_data_uri(svg: str | None) -> str`: base64 of the UTF-8 SVG with the `data:image/svg+xml;base64,` prefix, or "".

- [ ] **Step 1: Write failing tests:**
  - `frappe.get_print("Quotation", q, print_format="Fenestration Quotation")` contains each design ref, "Grand Total" and the grand total formatted value, and `data:image/svg+xml;base64,`;
  - the same holds for the two project formats;
  - a design whose `design_svg` contains `<script>` would already be sanitized, so instead assert that the HTML contains no `<svg` tag at all (only data URIs);
  - an empty SVG prints the placeholder text "Drawing not available";
  - `frappe.get_pdf(html)` starts with `b"%PDF"` for each.
- [ ] **Step 2: FAIL → Step 3: Implement; migrate → Step 4: all suites green.**
  - **Controller:** open each PDF in the browser for a visual check against the EvA samples.
- [ ] **Step 5: Commit** `feat: quotation, elevation and estimate confirmation print formats`

---

### Task 4: SPA Quote panel

**Files:**
- Create: `frontend/src/components/QuotePanel.vue` + spec
- Modify: `frontend/src/pages/ProjectWorkspace.vue`, `frontend/src/api.ts`

**Interfaces:**
- **QuotePanel** (frappe-ui components), placed on the workspace beside the header:
  - **Customer:** a Combobox over Customer. On change it saves `customer` on the project through `frappe.client.set_value`.
  - **Transport charges:** FormControl currency, saved the same way.
  - **Reprice:** a Button; it calls `reprice_project`, toasts "Repriced N designs", and reloads the designs.
  - **Create quotation / Update quotation:** a Button. The label depends on whether a draft exists. It calls `make_quotation`; `ok:false` shows a toast with the message.
  - **Status:** a badge showing Draft, Submitted or Cancelled, plus the grand total.
  - **Documents:** three Buttons opening `/api/method/frappe.utils.print_format.download_pdf?doctype=…&name=…&format=…` in a new tab: Quotation (needs a quotation), Elevation Report and Estimate Confirmation (project).
- Each design card shows "Priced {date}" from `pricing_json.priced_on`.

- [ ] **Step 1: Write failing tests** (mock api):
  - selecting a customer calls set_value;
  - Create calls make_quotation and shows the status with the grand total;
  - `ok:false` shows its message;
  - the PDF buttons have the correct hrefs;
  - Reprice calls the API and reloads.
- [ ] **Step 2: FAIL → Step 3: Implement → Step 4: `yarn test`, `yarn build`, backend green.**
  - **Controller:** a browser walkthrough on a NEW test project (not FP-2026-00001) through quote creation and the three PDFs.
- [ ] **Step 5: Commit** `feat(frontend): quote panel with reprice, quotation and documents`

## Done when

- Designs carry a price stamp, and a project can be re-priced on purpose.
- `make_quotation` produces a correct ERPNext Quotation (lines, transport, in-/out-state GST) and refuses unpriced or erroneous designs.
- The three print formats render to PDF with elevation images and Hilux terms.
- The SPA Quote panel drives all of it.
- All suites are green and the browser walkthrough is done.
