# Competitor Screens and User Flow: EvA ERP Cloud and LogiKal

Sources:

- `doc/evaerp.mp4`: a 24-minute screen recording of Hilux's live EvA tenant (evaerp.cloud) on 28 Oct 2026. The file is git-ignored. Frames were reviewed; the audio transcript is pending.
- Public web research, with links at the end.

## 1. EvA ERP Cloud, as Hilux uses it (from the recording)

### Shell

- **Left icon rail:** Dashboard, Opportunities, Quotes, Locations, Inventory, Reports, Settings (gear).
- **Top bar:** help (?), help videos, app switcher (grid), avatar.
- **"All apps" switcher:**
  - Sales Management: Portfolio, Quote, Survey
  - Production Management: Plan, Shop floor, Manufacture, FG inventory
  - Installation & Delivery: Dispatch, Install, Quality, Complaints
- **Help videos modal:** links to YouTube how-tos per screen.

### Sales dashboard (`/qms/dashboard`)

- KPI cards: Created opportunity (count and ₹), Newly quoted, Won, Lost.
- Sales analytics bar chart, weekly: created / won / lost / quoted.
- Sales by location: city list with count and ₹ (Coimbatore, Erode, Karur, Madurai…).
- Further down: lost-opportunity reasons, opportunity source donut, active opportunities by stage.

### Inventory dashboard (`/inventory/dashboard`)

Out-of-stock items, with tabs Profile / Reinforcement / Hardware. Columns: item name, code, surface finish, size (mm, e.g. 5800), billing unit (KG), min threshold, in-stock qty, out-of-stock qty, storage location.

### Quote list (`/qms/quotes`)

- Tabs: Active / Won / Lost / All. Also custom views, search, "Last 90 days" filter, owner filter, sort.
- Columns: Project name, Default quote (HIL-QT-…), Revision no. (badge count), Revision title (Rev 02), Parent quote ID, Area (sq.ft), Qty. Rows expand to show revisions.
- **Create quote** modal: Opportunity* (required), expected supply start date, expected supply end date. A quote always hangs off an opportunity.

### Quote workspace (`/qms/process-new/{opp}/{quote}/1`)

- **Header:** Back, project name + quote number, tabs **Documents | Design | Pricing | Report**, a cart showing ₹ total and quantity (₹54,36,711.97, Qty 321), and a **Quick quote** split button.
- **Design tab ("Project"):**
  - Buttons: Create design, Choose from library designs, search, Refresh designs, Design orders (reorder), filter, grid/list toggle, Global edits (dropdown), Project defaults.
  - **Design card:** elevation thumbnail with dimensions, ref (W01), qty, typology name, location, series, glass (with "+1" when a design has several glasses), surface-finish chip, price. Actions: View details, Edit design.
  - **View details drawer:** design name, qty, location, floor, system, glass, glass supplier, colour, price, size, area, rate/sq.ft, total weight ("9.88 kg including hardware"), handle, hardware material type.
- **Pricing tab:**
  - Left menu: Project Price Structure, Profile Rate, Reinforcement Rate, Hardware Rate, Glass Rate, Mesh Rate, Design Add-on Cost Heads, Design Manual Rate.
  - A price structure is chosen per project (e.g. "Commercial Projects"). It has an Update Pricing button and a Price Summary panel.
  - Cost-head table: Sl, cost head, calculation type, rate. **This confirms cost-plus pricing (D7):**

```
 1 Profile Cost            CustomFormula                1
 2 Profile Wastage         Percentage                   5
 3 Powder Coating          ProfileVisiblePerimeterSqft  25*#POWDERCOATING
 4 Anodizing               ProfileTotalPerimeterSqft    40*#ANODIZING
 5 Wood Finish             ProfileVisiblePerimeterSqft  70*#WOODFINISH
 6 RI Cost (reinforcement) CustomFormula                1
 7 RI Wastage              Percentage                   5
 8 Hardware Cost           CustomFormula                1
 9 Glass Cost              CustomFormula                1
10 Glass Wastage           Percentage                   1
11 Total Raw Material Cost CustomFormula                1
12 Fabrication Labour      AreaSqftFg                   100
13 Installation Labour     AreaSqftFg                   80
14 Sub Total               CustomFormula                1
15 Profit                  Percentage                   20
```

  Finish cost depends on the profile's **visible** or **total perimeter in sq.ft**. We need per-profile visible and total perimeter values, which we can derive from the DXF import.

- **Report tab:** a report hub.
  - Left categories: Favourite Reports, Project Basic Details, Quotation & Costing, Material Purchase Orders, Production Reports, Dispatch & Installation, Labels & Stickers.
  - Each report is a card with favourite, download PDF, view and menu actions.
  - Project Basic Details: Basic Dimensions, Elevation, Estimate Confirmation, Design-wise Project Status Analysis.
  - Production: Cutting Schedule, Design Assembly, Job Sheet, Profile Linear Cutting List, Design-wise BOM, Design Assembly Detail.
  - The cutting schedule draws each bar graphically: pieces labelled `1) W01-H`, the green bar is the rest, the red bar is waste.

### Window designer (full-screen modal)

- **Top bar:** design ref, Undo, Redo, Clear, Fit to view, Design summary (drawer), Save Design (split button), warnings triangle, more, maximise, close.
- **Left accordion (properties):**
  - Basic info: design ref*, qty*, name, location, floor number, W×H mm, note.
  - Surface finish: custom colour with No colour / Single / **Dual colour** (different inside and outside).
  - Framing (F1), Sash, Divider (mullion/transom).
  - Glazing item: one glass per glazing group, G1/G2; "Change glazing/mesh".
  - Bead.
- **Tool rail beside the canvas:** split, sash, frame and similar tools, picked by icon.
- **Canvas:** grid background, dimension chains (750 | 750, 1500 overall), panel ids (F1, S1, M1, glass 1/2), opening label OUT, handle height `GHH = 732`, floor aperture distance (sill 900) shown with a floor line, and an **Inside / Outside** view toggle.
- **Right rail views:**
  - 3D view.
  - **Section view**, which extrudes the real profile cross-sections. EvA holds actual section geometry, so the DXF import is essential.
  - Realistic view.
  - Wall view: the window placed in a brick wall at sill height.
- **Design summary drawer:** system, glass, supplier, colour, size, area, weight, handle, mesh.

### Settings (`/qms/settings`)

- Menu: Favourite settings, Roles & Permissions, Users & Teams, Locations & Territories, Raw Material Pricing, Glazing Pricing, Price & Calculation, Payment, Opportunity, Transportation, Import Data, Raw Material Settings, Data Schemas, Other.
- **Raw material pricing:** Profile, Reinforcement and Hardware price levels, plus a raw material price list imported from Excel ("units other than Meter and Kilogram cannot be updated for Profile & Reinforcement").
- **Glazing pricing:** Glazing price levels, glazing price list via Excel, glazing supplier.
- **Price & Calculation:** price structure, i.e. the cost-head templates above.
- Excel import everywhere: download a sample format, then upload (10 MB max).
- **What Hilux cannot do here:** add profile series, profiles or rules. Only prices and settings are self-service. That gap is our opening.

### Observed Hilux flow in EvA

Dashboard → Quotes → open quote → Design tab (cards) → Edit design (designer) → Save → Pricing tab (check structure) → Report tab → download PDFs.

Separately: Settings → price lists (Excel import).

## 2. LogiKal (Orgadata, now part of Forterro): public sources

- **Platform:** Windows desktop (ribbon UI). No cloud version of LogiKal itself. The SimplyTag iOS app reads QR tags on finished elements.
- **Catalogs:** 450+ supplier catalogs. Orgadata or a licensee builds each dataset together with the system house; base licence includes one supplier package. This is the vendor-built model again: proprietary systems need Orgadata's data service.
- **Flow:**
  1. Home (recent projects, news)
  2. Project centre (folders, Projects / Fabrication phases tabs, tile or list positions, info pane)
  3. Project (position list, inline-edit qty and status)
  4. **New position:** pick Profile system → Subsystem → Rule package, plus statics and U-value standard
  5. **Element input** with a step timeline and Back/Next: grid (fields across × down, typed dimensions, formulas) → mullions/transoms → profiles, reinforcement, wall connection → sash type and opening → glazing → hardware (packages, hinges, locking, cylinder) → extra articles → costs
  6. Estimation
  7. Printouts manager, grouped:
     - Estimation: estimation, material analysis, labour hours, CE/U-value.
     - Quote / Invoice: quotation, order confirmation, delivery note, invoice.
     - Orders: profile, glass, hardware and coating orders.
     - Fabrication: cut optimisation, cutting list, assembly list, glass plan, installation plan.
  8. CNC / MES export
- **Engineering depth:** statics, U-value, CE marking, labour hours, CNC. This is why Hilux trusts LogiKal for precision.

## 3. EvA public extras (from web research)

- Opportunity **Kanban**: Enquiry → Sales Call → Quoted → Negotiation → Advance Received. Stage totals; a card turns red when its last contact was more than 15 days ago. Create Opportunity is a 2-step form.
- Refresh designs, with an optional "update price during refresh". Per-design manual price (per window or per sq.ft/m²). Add-on cost heads. Copy designs. Revision comparison.
- Units entered in ft/in are converted to mm.
- **Mobile app "EvA ERP – Survey"** (Android): offline with sync, **BLE laser distance meter pairing**, three width and three height readings, site photos, site checklists. Quoting uses the responsive web app.
- Dispatch and installation use barcode/QR scanning. Clients scan a QR to track their project. WhatsApp sending. 3D link in the quotation.

## 4. Implications for OneBook

**Copy:**

- Quote workspace pattern: tabs Documents / Design / Pricing / Report, design cards, a running ₹/qty total, quick quote.
- Designer layout: left property accordion, tool rail, grid canvas, dimension chains, panel ids, GHH, sill line, inside/outside toggle, summary drawer, warnings badge.
- Price structure as an ordered list of cost heads with calculation types (formula, %, per perimeter sq.ft, per area sq.ft) and `#TOKEN` variables. Multiple structures (commercial / residential) chosen per project.
- Report hub as cards grouped by stage, with favourites.
- Opportunity Kanban with a stale-contact flag.
- Refresh designs / re-price old quotes, with versions frozen by default.
- Revision tree: parent quote → Rev 01, Rev 02.
- Dual colour finish (inside ≠ outside).
- Survey: three readings each way, photos, checklists, BLE laser (Web Bluetooth works in Chrome on Android).

**Beat:**

- **Self-service series + rules + DXF import (Series Studio).** Neither EvA nor LogiKal lets the system house do this alone. This is the core pitch.
- Native ERP depth: accounting, GST, stock, purchase, the Hilux ↔ dealer supply loop.
- LogiKal-style typed grid entry plus a step guide (Back/Next) for new users, alongside free editing for power users.

**Revisit D1 (frontend):** EvA's own survey app is native and offline with BLE. Our plan: PWA with offline cache plus Web Bluetooth, Android Chrome only. iOS Safari has no Web Bluetooth, so if Hilux surveyors use iPhones, D1's native trigger fires.

**Scope impact:** 3D, section and wall views are table stakes in EvA demos. Plan a three.js extrusion of DXF sections for P2/P3, not "later". Our SVG designer stays 2D; 3D is a separate viewer.

## Sources

- LogiKal: https://www.logikal-software.com/en/product/module-overview, https://help.orgadata.com/en/documentation/ (home-screen, project-centre, create-positions, input-of-elements, printouts, dataservices), https://apps.apple.com/app/id6465746259, https://glasstimes.co.uk/news/bm-aluminium-announces-database-partnership-with-kawneer
- EvA: brochure (FIT Show 2023 PDF), https://evawinoptimize.com/website/, https://play.google.com/store/apps/details?id=com.evawinoptimize.bafcom, https://www.youtube.com/@EvACloudSoftware

## 5. Audio from the recording (Hilux walkthrough, low confidence)

The speech is mostly Tamil with some English. It was machine-translated with Whisper-small, so the translation quality is poor. Treat every point below as a lead to confirm with Hilux, not as fact.

- **Modules in use:** Hilux appears to use EvA for quotes and inventory only. The manufacturing, FG inventory, dispatch, install and quality modules appear not to be in use or accessible to them.
- **Tools:** Hilux uses Orgadata/LogiKal for engineering, and EvA perhaps ~10% of the time. An EvA renewal may be due in about 6 months, which could be a timeline driver.
- **Designer walkthrough:**
  - Frame types: window frame or door frame.
  - Shutter type.
  - Lock type: single-point or multi-point.
  - Glass: thickness chosen first (12mm and 24mm mentioned), then quality, which drives price.
- **Pricing:** margins are discussed and adjusted at project level.
- **Engineering knowledge:** Hilux stressed that the builder needs window engineering knowledge. They seemed to offer access or licence help, and **profile cross-sections by mail ("three sections")**. This is likely the DXF source; follow up.
- **Timeline:** the transcript mentions a first release in about 1–2 weeks with test-and-feedback cycles, and full replacement in about 5–6 weeks. Who said this, and whether it was meant as a target, is unclear; confirm with Hilux. A German package was quoted at about ₹4 lakh.
- **Survey:**
  - Hilux does **not** use EvA's survey module.
  - Final measurement is done on the **Estimate Confirmation Report**: tick W, H, qty and location (room names such as kitchen or dining hall), mark deviations, note plaster/finish size changes, then get the **customer's signature**.
  - This protects Hilux, because measurement responsibility sits with the customer (risky villa projects).
  - So the survey need is mainly a digital confirmation with sign-off, not a laser-meter app. D9 priority drops.
