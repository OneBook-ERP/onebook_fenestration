# App Map: Vue SPA vs Desk, Navigation, User Journeys

Planning document. Nothing is built yet. Decisions referenced: [decisions.md](decisions.md).

## 1. Split principle

- **Vue SPA** (`/fenestration`): anything visual, workflow-heavy or dealer-facing. Dealers live here only.
- **Desk** (`/app`): masters, standard ERPNext transactions, accounting/GST, admin, back-office reports. Used by HQ staff.
- The SPA creates ERPNext documents (Quotation, Sales Order, Material Request, Purchase Order, Delivery Note, Invoice) through whitelisted APIs. Users never have to re-key data in Desk.

## 2. Personas

| Persona | Where they work |
|---|---|
| HQ Engineer (series, rules) | SPA Series Studio + Desk masters |
| HQ / Dealer Sales & Estimator | SPA |
| Surveyor | SPA on mobile |
| Planner, Shop floor lead | SPA Production board (+ Desk for HQ) |
| Stores, Purchase, Finance, Accounts | Desk |
| Installer crew | SPA on mobile |
| Dealer Owner | SPA (dashboard, orders from Hilux, approvals) |
| HQ Management | Desk workspace + SPA dashboard |
| End customer (later) | Shared quote link / PDF, sign-off on installer tablet |

## 3. Vue SPA screens

```
/fenestration                         Home: role dashboard
/fenestration/projects                Project list (filter: stage, dealer, sales rep)
/fenestration/projects/:p             Project workspace (tabs below)
    Overview   customer, site address, opportunity, stage timeline
    Designs    grid of window thumbnails: ref, size, qty, series, finish, price, issues badge
    Quote      revisions A/B/C, totals, discount (approval above limit), T&C,
               generate PDFs (Quotation, Elevation, Confirmation), share
    Survey     final measurement per design/location, photos, deviations
    Order      advance status, Sales Order link, frozen series version
    Production batch, cutting status, job progress per window
    Install    schedule, crew, checklist, commissioning certificate
/fenestration/projects/:p/designs/:d  Window Designer (full screen)
/fenestration/survey/:p               Mobile survey mode
/fenestration/production              Board: batches, cutting plans (bar diagrams), kanban
                                      cut > assemble > glaze > pack > QC, QR scan
/fenestration/install                 Crew schedule and job list (mobile)
/fenestration/orders                  Dealer: buy from Hilux (catalog, dealer price, cart from
                                      shortages, order status, outstanding)
/fenestration/studio                  HQ: Series Studio
    /series/:s                        DXF import + preview, profile properties, deduction table,
                                      member/hardware/validation rules with formula editor,
                                      test panel (sample windows vs expected), publish version
```

### Window Designer layout

```
+-----------+----------------------------------+------------------+
| Templates | SVG canvas                       | Properties       |
| casement  |  click cell: split V/H,          | W, H, qty, loc   |
| fixed     |  set leaf (sash/fixed/louver/fan)|  series, finish  |
| louver    |  drag mullion, type exact mm     | glass per leaf   |
| sliding   |  dims auto-labelled              | opening, GHH     |
| saved     |  view from inside                | hardware options |
+-----------+----------------------------------+------------------+
| Live: sq.ft | window kg | shutter kg | unit price | issues (2) | BOM preview |
+-----------------------------------------------------------------+
```

Actions: duplicate design, same typology in many sizes (bulk), save as template, undo/redo.

## 4. Desk usage

- **Workspace "Fenestration"**: shortcuts, KPIs, "Open Studio" / "Open Projects" buttons.
- **Masters (raw CRUD)**: Profile Series, Series Version, Profile, rules, Finish, Glass Spec, Typology Template, Bar Stock Length. Series Studio is the friendly editor on top of these.
- **ERPNext standard**: Lead/Opportunity, Customer, Quotation, Sales Order, Item/Item Price/Price List, BOM, Production Plan, Work Order, Job Card, Material Request, Purchase Order/Receipt, Stock Entry, Delivery Note/Trip, Sales Invoice, Payment Entry, GST (india_compliance), Quality Inspection, Serial No, Warranty Claim, Maintenance Visit, Project/Task.
- **Print formats** on Fenestration Project / Window Design: Quotation, Elevation, Estimate Confirmation, Assembly summary, Assembly detail, Cutting schedule + wastage. The SPA opens these as PDFs.
- **Admin**: Fenestration Settings, roles, users, dealer onboarding (Company/permissions, depends on D5), approval workflows.

## 5. Navigation

- **Login redirect by role**: dealer roles get Role home page `/fenestration` and no desk access. HQ roles land on the Desk workspace.
- **Deep links both ways**:
  - Desk → SPA: Quotation/Sales Order/Opportunity forms have an "Open in Designer" button that opens the SPA project.
  - SPA → Desk: HQ users see "Open in Desk" links on linked documents. Dealers get the PDF or a read-only view instead.
- **SPA chrome**:
  - Desktop: left sidebar (Home, Projects, Production, Install, Orders, Studio [HQ only]).
  - Mobile: bottom tabs (Projects, Survey, Install, Scan).
- **Global search**: project, customer, design ref, window serial (QR).

## 6. User journeys

### J1. HQ engineer: new series in an hour
Studio → New Series → upload DXFs → confirm computed kg/m and dimensions, tag roles → copy rules from a similar series → edit deductions → test panel compares sample windows → Publish Series Version. Available to HQ and all dealers immediately.

### J2. Sales: enquiry to quote
1. Home → New Project (customer, site; creates or links Opportunity).
2. Add designs: template → W×H → series, finish, glass → live price, weight and issues.
3. Fix issues using the hints; duplicate the design for other sizes.
4. Quote tab: discount (approval above limit) → generate Quotation + Elevation PDFs → share by WhatsApp or email.
5. Customer feedback → revision B. Each revision freezes its prices.

### J3. Confirmation to order
1. Accept → Estimate Confirmation PDF (spec checkboxes, deviations, site checklist) signed.
2. Advance (90%) recorded → Payment Entry.
3. Survey: final measurement on mobile → design sizes updated → re-validate. Size changes beyond ±25 mm need re-pricing approval.
4. Create Sales Order (frozen series version, final designs).

### J4. Production
1. Sales Order → planner batches designs by series + finish → Production Plan.
2. Cutting Plan: optimize bars (uses Rest offcut stock first) → shortages list.
3. Shortages → Material Request. A dealer turns it into an order to Hilux (J5); HQ uses its own stock or purchases.
4. Work Order / Job Cards → shop floor board, QR label per window → QC → packed.

### J5. Dealer buys from Hilux
Dealer: Orders → cart (pre-filled from shortages or manual) → submit PO → Hilux receives a Sales Order (inter-company or portal, per D5) → Hilux dispatch + invoice → dealer receipt updates dealer stock.

### J6. Dispatch, install, commission
Delivery Note / Trip → install schedule → crew on tablet: checklist, photos, issues → Commissioning Certificate signed by the customer on the tablet → final 10% invoice → window serials activate warranty.

### J7. After-sales
Customer reports an issue (scans the window QR, or calls) → serial lookup shows design, batch and install date → Warranty Claim → Maintenance Visit.

## 7. Open UX questions

- Do dealers need their own CRM (leads) in the SPA, or is a light lead list enough?
- Customer-facing quote link with online accept, or PDF only?
- Survey/install offline need (ties to D1 revisit trigger).
- HQ quoting directly vs only through dealers in some regions?
