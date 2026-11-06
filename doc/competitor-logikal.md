# Competitor analysis: Orgadata LogiKal 12.6 (client sample outputs)

Source: seven PDFs in `doc/German app files/` (git-ignored, contain client data; none reproduced here). Product identified from page footers: **Logikal 12.6, Orgadata AG, Leer, Germany**. Series in the samples: a Kömmerling aluminium window system (KWD46.1) with a frame, sash, transom-mullion and glazing bead profile, in powder-coated finish. Language is English with metric units. A 780 MB demo video was not reviewed.

All PDFs come from "Microsoft: Print To PDF", so layouts are the app's own print templates. Sample job = one 2-sash casement position, quantity 2.

Our baseline (checked in code): engine geometry/cut members/glazing/hardware/weights (`engine/`), 1D cutting optimiser with kerf and rest (`engine/cutting.py`, `production/cutting_plan.py`), BOM and Work Order glue (`production/bom.py`, `work_order.py`), pricing stack (`pricing/rates.py`), Desk print formats: quotation, elevation, assembly summary/detail, estimate confirmation (all `fenestration/print_format/`) and Profile Cutting Schedule (`production/print_format/`). No supplier-grouped order documents exist.

## 1. Quotation (1 page)
- Purpose: customer offer. Per position: interior-view drawing, system name, finishes, glazing spec, profile codes (frame / mullion / vent).
- Pricing basis: **total area (sqm), unit count, price per sqm**, GST line. Not an itemised build-up; the commercial summary is area x rate.
- Large terms block: rate inclusions, payment split, validity (15 days), lead time, colour approval lead time, advance non-refundable, glass make clause, warranty, site-readiness (cavity squareness, signed size sheet), cleaning/re-packing charge per sqm, finish surcharges as % (matt 0, texture 2, wood 12), scaffolding scope, post-order negotiation rule (size change threshold in mm), bank details, signature block ("in duplicate, sign and return one copy").
- Notable: finish surcharge in % per finish; size-change threshold clause; accepted-copy workflow.

## 2. Position Drawing (1 page)
- Purpose: shop/approval drawing of one position, **interior view**, fixed scale (1:35 shown in header).
- Header: date/time, page, scale, project ref, customer block, person in charge, position tag, quantity, system, finish, floor/room tag.
- Body: frame outer size, sash sizes listed, glass size per pane with thickness, overall width and height dimension lines, sub-dimension chain (sash widths), opening symbol (diagonal triangle lines).
- Notable: floor and room tags on every position; sash size and glass size printed on the drawing itself.

## 3. Cross-section Drawing (1 page)
- Purpose: technical drawing, **exterior view** of the position plus a horizontal section (B-B) through the whole width and a vertical section (A-A) through the height, drawn to scale from real DXF profile geometry (we have these DXFs for Hilux series).
- Section content: each profile labelled by code; gasket/gasket-chamber items highlighted by colour; glass/beads shown; **dimension chains** (overall, per-sash, per-profile visible width, glass sight size, overlaps, glazing rebate); section marker lines A-A / B-B on the elevation; glass thickness callouts.
- Footer list on the sheet: hardware qty + name per position (hinges, handle with hand, stay, strikers, wedges, packers), glass spec with area and size, gasket code.
- Notable: sections show hand-of-handle in hardware names; section cut positions chosen automatically.

## 4. Cutting Sheet (3 pages)
- Purpose: saw list. One block per profile + finish, in profile code order.
- Block header: profile code and name, finish, **bars used x bar length**, profile width/height, **wastage mm and % including residual lengths**, usable-residual threshold, saw-cut deduction, end-deduction total.
- Per bar: repeat count ("1x" = pattern repeated N bars), then rows: count, **member label (side letter / number, e.g. R/1, T/4)**, length, **end angles (45/45, 90/90)**, position tag.
- Page 1 top: summary strip per profile (count, finish, bar number, usage). Last page: **summary table** per profile: finish, bars, bar length, waste mm, waste %.
- Footer: software name/version, disclaimer, page x of y, timestamp, operator.
- Notable: identical bars grouped with a repeat count; member labels trace back to the drawing; end angles shown per piece; the same label is reused (e.g. "T/13" cut from two bars).

## 5. Profile Order (2 pages)
- Purpose: purchase order of raw bars from the profile supplier.
- Header: date, project, systems included, finish group heading.
- Columns: packing units (PU) with bars-per-PU and bar length (e.g. 12 x 5.8 m), item code, description, finish, **required length (m)**, **weight (kg)** for required and for the full PU. Bars needed shown in brackets (2 x 5.8).
- Notable: orders are in **packing units** (round up bars to the supplier carton size), not loose bars; both required-weight and PU-weight shown.

## 6. Hardware Order (2 pages)
- Purpose: purchase order of hardware, consumables and gaskets.
- Columns: qty as PU with pack size (1 PU @ 10) and pieces needed in brackets, article code, description (incl. hand), unit price, line total. Loose items (qty = pcs) when no pack. Gaskets in metres (needed length in brackets).
- Contents: hinges, handles, wedges, strikers, stays, packers, run-up blocks, fastener by size, glazing shims by thickness, corner pieces, chevrons, drain valves, hole caps, mullion connector linked to its profile, gaskets (universal, centre, 2 mm).
- Notable: PU rounding on quantity; no grouping by hardware set in the sample (flat list); price per PU.

## 7. Glass Order (1 page)
- Purpose: order to the glass processor.
- Grouping: by **glass configuration** (build-up, thickness, spacer type).
- Columns: position / pane number, quantity, width, height, area per piece; group totals; document total pieces and total area.
- Notable: panes are listed by position and index; sizes are **sight/cut sizes after rebate deduction** (differs from frame opening); spacer shown ("free value" when not applicable).

## Cross-cutting features
- Header on every document: date, project, person in charge; footer: product/version + plausibility disclaimer + page x of y.
- Position tag + floor + room on every output.
- Every output traces to the same engine data (member labels, glass, hardware, weight) so documents always agree.
- Supplier-facing orders aggregated across all positions of a job.

## Gap table

| Feature in LogiKal | We have? | Suggested plan |
|---|---|---|
| Quotation with per-position drawing | Yes: `fenestration_quotation` print format, elevation | Done; Plan 6 visual polish |
| Rate = area x price/sqm summary and GST | Partial: price stack in `pricing/rates.py`, quotation lines; no sqm summary row | Plan 6: add total sqm / units / rate-per-sqm summary option |
| Finish surcharge in % per finish | Partial: `Profile Finish`, cost heads; check % surcharge field | Plan 6: confirm and add if missing |
| Configurable T&C block, validity, payment split, bank details, signature | Partial: `Fenestration Settings`, standard ERPNext terms | Plan 6: terms template + bank block on quote print |
| Position drawing, interior view, scale, dimension lines | Partial: SVG renderer (D4), elevation print; no interior/exterior toggle, no scale label | Plan 6 |
| Floor and room tags on positions | Check `Window Design` fields; likely missing | Plan 6 (acceptance) |
| Opening symbols | Yes in SVG renderer (swing lines); verify handing | Plan 6 acceptance |
| Cross-section drawing from DXF with dimension chains and callouts | Partial: `engine/section.py` gives outline, area, weight; no chains, no assembly section | Later (post Plan 8); high effort, high wow |
| Auto section cut lines A-A / B-B on elevation | No | Later |
| Sheet footer with hardware list and glass summary | No | Plan 6 |
| Cutting sheet per profile + finish, bars with cut list | Yes: `profile_cutting_schedule` | Done |
| Identical-bar grouping with "Nx" repeat | No (every bar listed) | Plan 8 |
| Member label per cut piece (side + number) tied to drawing | Partial: members exist; label on drawing/print unclear | Plan 8 |
| End angles per piece (45/45, 90/90) | Check print; engine has mitre data | Plan 8 |
| Kerf and end deduction as settings | Partial: kerf and min rest yes; end deduction no | Plan 8 |
| Usable residual length and waste % incl/excl rest | Yes (`waste_pct_incl_rest`, `excl_rest`) | Done |
| Summary table per profile at end of cutting sheet | Yes (summary child table) | Done |
| Profile order in packing units, weight required vs PU | No (Cutting Plan gives bars, kg; no PU) | Plan 8: Profile Order document, supplier-grouped, PU rounding |
| Hardware order, PU rounding, price | Partial: BOM rows and Work Order raw material; no PU, no order doc | Plan 8 (Material Request / PO grouped by supplier) |
| Hardware grouped by set | Not in sample either; our hardware is rule driven | Plan 7 doors, Plan 8 |
| Gaskets by metre, shims by thickness, fasteners by size | Partial: gasket and hardware rule lines in `engine/hardware.py` | Plan 6 acceptance vs golden |
| Glass order by configuration, with sight sizes | Partial: `GlassPane` and glazing engine; no order doc | Plan 8: Glass Order print/doc grouped by build-up with totals |
| Glass order spacer / coating / edge work / tempered flag | Spacer yes in IGU config? unclear | Plan 8 |
| Doc footer with version, page x of y, timestamp, operator | Partial: Frappe print footer | Plan 6 |
| Weight per profile and per order | Yes (engine weights) | Done |
| Interior/exterior view choice on documents | No | Plan 6 |

## Where we can beat LogiKal
- Web/Vue designer, dealer franchise portal, quote-to-order-to-work-order in one system (ERPNext), GST and Indian terms natively.
- Offcut (rest) stock reuse across jobs (LogiKal shows only a residual threshold).
- Orders grouped by supplier, auto-created as Purchase Orders, stock netting before ordering.
- Rules as data: HQ adds a series without a vendor update.
- Pricing transparency: dealer margin, finish surcharge, scenario quotes.

## Open questions for Hilux
- Is the sqm-rate quotation the preferred format, or itemised lines (we have both)?
- Which suppliers get which orders (profile, hardware, glass), and what are their PU sizes?
- Do they want the section drawing in the quote pack or only for production?
- Spacer and glass processing fields required on the glass order?
