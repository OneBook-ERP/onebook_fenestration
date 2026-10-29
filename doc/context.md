# OneBook Fenestration: Project Context

Living context for the `onebook_fenestration` Frappe v16 app. Read this before designing doctypes or engine code.
Decisions are tracked separately in [decisions.md](decisions.md).

## 1. Client

**Hilux System Windows Pvt Ltd**, Karur, Tamil Nadu (hiluxwindows.com, GSTIN 33AAHCH3108G1Z0).

Hilux plays three roles:

1. **System house**: owns aluminium extrusion dies and supplies profiles, hardware, gaskets and accessories.
2. **Fabricator**: manufactures windows and doors in its own factory.
3. **Installer**: does site survey, installation, commissioning and warranty.

Product range (from the website):

| Series | Type |
|---|---|
| CS400 Economical Casement | Window |
| CS4800 Premium Casement | Window, Door |
| HSL2600 | Sliding window |
| HSL3400 | Sliding window, sliding door |

The BRD only covers casement windows, but the data model must support sliding systems and doors from day 1. The HSL3410 laminated glass adaptor already shows up in the sample cutting schedule.

**Franchise model**: dealers invest ₹25L in a local micro-factory. They design, quote, manufacture and install for their own customers, and buy raw material from Hilux. Both Hilux HQ and the dealers use the platform.

## 2. What we replace

- **Orgadata Logikal**: on-prem, USB-dongle licence. Precise engineering, but no cloud access and no dealer access.
- **EvA WinOptimize / EvA ERP Cloud** (Evolutionary Algorithms Pvt Ltd, Bhubaneswar, 2012, ~3000 fabricators, claims ~70% of Indian system suppliers).
  - Runs Hilux's full chain today: opportunity `HIL-OP-*`, quote `HIL-QT-*`, production reports.
  - EvA staff configure each supplier's series library. This vendor queue causes the **~25-day delay** for every new or changed series. It is a service-model limit, not a software limit.
  - EvA modules:
    - Lead CRM and quote revisions ("Quote Alias A")
    - 3D configurator and cross-section drawings
    - Global edit and site geo-tagging
    - Cost and MIS reports
    - Cutting and optimization, off-cut management
    - Pre-production survey
    - PO, inventory, PPC, batching, shop floor
    - Pre-delivery inspection, dispatch with routes
    - Installation and post-install QC
  - Charged extras: ERP integration, SMS/WhatsApp, 3D link in quote, CNC machine integration.
  - EvA flow: Enquiry > Quote > Design confirm > Order > Final measurement > Credit approval > Sales Order > Batch plan / glass order > Cutting > Assembly > Packing > Dispatch approval > Invoice > Dispatch > Install > After-sales.

**Our edge over EvA:**

- Self-service series and rules (removes the 25 days)
- Native accounting and GST (ERPNext + india_compliance)
- Native Hilux ↔ dealer supply loop
- No per-integration fees
- Hilux owns its data

## 3. Sample outputs (golden test data)

`doc/*.pdf` holds the six EvA reports for quote HIL-QT-00000191 (Go builder, Coimbatore; 321 windows; 3507.88 sq.ft):
Quotation, Elevation, Estimate Confirmation, Design Assembly (summary), Design Assembly Detail, Profile Cutting Schedule.

These PDFs contain customer PII, so they are git-ignored and must not be committed.

Designs in the sample:

| Ref | Size (mm) | Series | Glass | Qty | Unit price | Weight |
|---|---|---|---|---|---|---|
| W01 Openable (2 sash + T mullion) | 915 x 1220 | CS400, Grey | (1,2) 6mm clear TG | 260 | 16,380.72 | 20.698 kg (S1, S2 8.489) |
| W02 Ventilator (louvers + fixed) | 915 x 610 | CS400, Grey | (1) 5mm tinted louvers, (2) 6mm clear | 60 | 5,368.18 | 9.876 kg |
| 123 (1 sash) | 1500 x 1500 | CS4800, 5104 PC Brown | 12mm reflective TG | 1 | 25,304.48 | 66.829 kg |

### Rules reverse-engineered from W01 (CS400)

Hilux must confirm these values.

```
frame B,T = W, L,R = H              45°/135° mitre      E104156 Cmt Outer 40x42      0.649 kg/m
T mullion = H - 2*24                90° straight        E104159 Cmt T Mullion 40x60  0.809 kg/m
sash height = H - 2*18              45°                 E104160 Cmt Sash 40x64.5     0.950 kg/m
sash width  = cell - 18 (frame side) - 5.5 (mullion side)   -> 434
glass       = sash - 101 each way   -> 333 x 1083
G23 glazing gasket = glass - 28     -> 305 / 1055
G21 frame gasket   = frame lengths; sash gasket = sash lengths
```

Some hardware quantities scale with member length. Hole caps, frame packers and 8x80 fasteners come out as 2/3/2/3 on B/R/T/L, so the formula must take length as an input (e.g. `ceil(len/500)`, exact form TBD).
Consumables scale with perimeter (masking tape 8.54 m, sealant 1.423 cans).

### Formulas verified against EvA numbers

```
profile kg = Σ cut length (m) x kg/m
glass kg   = m² x thickness(mm) x 2.5
shutter kg = sash profiles + its glass          W01: 3.074 + 5.41 = 8.48  (EvA 8.489)
window kg  = all profiles + all glass           W01: 20.697           (EvA 20.698)  hardware ignored
area       = frame W x H (m², 3 dp) x 10.764    W01: 1.116 m² -> 12.013 sq.ft
project    = Σ lines + transport                46,06,383.03 + 1,000.01
GST 18%    = 8,29,328.95; grand total rounded = 54,36,712
avg/sqft   = project / total sq.ft = 1,313.44
```

The price per sq.ft varies by design (1363 / 893 / 1044). This suggests a BOM cost-plus price that is then expressed per sq.ft. Not yet confirmed.

### Cutting schedule facts

- Cutting tolerance (kerf) is 10 mm.
- One profile can use several stock bar lengths in the same job (E104156 uses both 4880 and 5800).
- "Rest" is a reusable offcut and goes back to stock. "Waste" is scrap.
- The wastage summary reports per profile: bars ordered/used, pieces, mm, kg, % (incl. and excl. reusable), plus kg/m.
- Optimization groups by profile + finish.

### Report structures

- **Assembly summary**: groups by W/H.
- **Assembly detail**: per piece, with Position B/T/L/R/H/W and Panel id (F1, F1-S1, F1-S1-G1).
- Both reports are derived from one BOM table.

### Commercial terms (from the quotation T&C)

- Payment: 90% advance with work order, 10% before dispatch.
- Validity 10 days. Delivery 60 days from advance and colour/typology confirmation.
- Size change beyond ±25 mm, or any change to opening type, colour, glass, quantity or hardware, is treated as new scope.
- Finish surcharge: Matt 0%, Texture 2%, Wooden 12%.
- Materials: aluminium 6063-T6; glass Saint-Gobain/AIS/Guardian; SS304 mesh; Jotun/AkzoNobel/Pulver powder coat.
- 10-year warranty on profiles, hardware and coating.
- Price includes material, labour, transport and installation.
- Client provides scaffolding, site access, power, water and storage.

## 4. Engine model

Four layers, all in server-side Python and deterministic:

1. **Design tree** (what the user draws). Frame root, with recursive vertical/horizontal splits (mullion/transom). Each leaf is one of: sash (opening direction, handle height GHH), fixed glass, louver, or fan cutout. Each glass leaf has its own glass spec.
2. **Members**. The tree is turned into physical pieces: role, edge position, panel id, length, angle.
3. **Rules**. Series version + role + finish + glass map each member to an Item variant, quantity, hardware, gaskets and consumables.
4. **Rollup**. Weights, validation issues, cost, price.

Key principle: a profile's cross-section never scales; only cut lengths change. Resizing means re-evaluating the deduction formulas against W and H.

The wall opening converts to frame size by subtracting the fit gap, a per-series setting (assumed 10 mm per side, to be confirmed).

Item mapping:

- **Profile**: Item template with a Finish attribute (E104156 → E104156-GREY).
- **Hardware**: has its own colour attribute (e.g. MILL FINISH).
- **Glass**: Item attributes are thickness, type and toughened. Glass thickness drives bead and gasket selection, weight, rebate validation and price.

Validation rules each carry a severity (error/warn), a message and a fix hint:

- Input: size within series min/max.
- Geometry: minimum cell size; handle within sash.
- Glass: thickness within rebate range; maximum m² per thickness.
- Hardware: shutter kg against stay/hinge rating; sash height within espag range.
- Finish availability.
- Mullion deflection from Ix (later).
- Commercial floor price triggers approval.

**Worked example (12 x 6 ft wall, 3 bays S1 | fixed | S2, CS400):**

- Frame 3638 x 1809
- Mullions 1761
- Sash 1189 x 1773
- Sash glass 1088 x 1672
- Shutter ≈ 32.9 kg, which likely fails the 12" stay rating
- Window ≈ 106 kg

Suggested fixes for the failing stay:

- Larger stay
- Add a transom
- Use four bays instead of three

### CAD (DXF) profile import

1. Parse with `ezdxf` and take the closed loops.
2. Compute area, bbox (width/depth), perimeter (coating area), centroid, Ix/Iy.
3. Derive kg/m = area_mm² x 0.0027.
4. Store an SVG thumbnail.
5. The admin tags role, sightline, rebate, glass range, bar lengths and Item.

The series-level deduction table is entered by an engineer (from Logikal or die drawings). Auto-deriving it from an assembled-section DXF is a later phase.

### Price stack (proposed)

```
material = Σ profile kg x rate/kg[series, finish] + Σ glass chargeable m² x rate
         + Σ hardware qty x rate + gasket m x rate + consumables
cost     = material + fabrication labour + installation + overhead
unit     = cost x (1 + margin) x (1 + finish surcharge %)
line     = unit x qty;  project = Σ lines + transport;  GST 18%;  round grand total
```

Rates are stored in ERPNext Item Price. Separate price lists give HQ and dealers different prices.

## 5. Proposed doctypes

- **Masters**: Profile Series, Series Version (deductions, fit gap, limits), Profile (Item link, role, kg/m, bar lengths, rebate range, DXF), Member Rule, Hardware Rule, Validation Rule, Glass Spec, Finish, Typology Template, Bar Stock Length.
- **Transactions**: Fenestration Project (Opportunity/Customer), Window Design (tree JSON + computed child tables for cuts, hardware, glass, weights and issues, plus an SVG snapshot), Cutting Plan, Site Survey, Commissioning Certificate.

Rule formulas are stored as text and evaluated with `frappe.safe_eval`. Available variables: `W, H, cell_w, cell_h, sash_w, sash_h, glass_t, shutter_kg, len`.

Quotes freeze the series version they were made with.

## 6. ERPNext mapping

| Need | ERPNext / OneBook |
|---|---|
| Lead, opportunity | CRM Lead, Opportunity |
| Quote, revisions | Quotation + amend |
| Final measurement | Site Survey (custom, mobile-friendly) |
| Credit approval | Workflow on Sales Order |
| Batching | Production Plan grouped by series/finish |
| Cutting optimization, offcuts | Cutting Plan (custom); Rest offcuts tracked as stock |
| Glass ordering | Material Request to glass supplier |
| Shop floor | Work Order + Job Card (cut, assemble, glaze, pack) |
| Pre-delivery / post-install QC | Quality Inspection |
| Window labels | Serial No + QR print format |
| Dispatch | Delivery Note, Delivery Trip |
| Installation | Project + Tasks, then Commissioning Certificate |
| After-sales | Warranty Claim, Maintenance Visit |
| Dealer buys from Hilux | Inter-company PO→SO or supplier portal (depends on tenancy decision) |

## 7. Phases

- **P0**: Masters, rule schema and Excel/DXF import. Demo: "new series in 1 hour".
- **P1**: Design tree, SVG designer and engine for the three BRD typologies. W01/W02/123 serve as golden tests.
- **P2**: Pricing, plus Quotation, Elevation and Confirmation PDFs.
- **P3**: Assembly reports and cutting optimizer (FFD + offcut reuse, multiple bar lengths, 10 mm kerf, wastage summary).
- **P4**: SO > BOM/WO > MR > PO-to-Hilux; installation and commissioning; dealer onboarding.
- **Later**: Sliding/door rules depth, structural wind load, 3D view, CNC export.

## 8. Open questions for Hilux

1. Deduction sheets per series, including fixed-glass bead deduction K and the frame fit gap.
2. DXF for every profile section.
3. Friction stay, hinge and espag load/size tables.
4. Pricing basis (cost-plus vs flat sq.ft); rate per kg per finish; glass, labour and install rates.
5. Billing area: wall opening or frame size (EvA uses frame size).
6. Dealer tenancy model (see decisions.md D5).
7. Which EvA package and modules are actually used; where accounts/GST live today (Tally?).
8. Can masters and history be exported from EvA and Logikal?
9. Do dealers use EvA today? What is the annual EvA cost?
10. Current install/commissioning steps and the warranty process.
