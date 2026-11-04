# Questions for Hilux: CS400 and CS4800 hardware, gaskets and glass

These questions come from turning the Hilux CS400 and CS4800 hardware lists into series rules (`onebook_fenestration/series_studio/data/cs400_v2.json` and `cs4800_v2.json`; section 9 covers the CS4800 profiles, beads and adaptors taken from your DXFs). Each rule we had to guess is marked `ASSUMPTION`, `SHEET SAYS` or `CHECK` in its note, and the rule id is listed in backticks below. Please answer each question with yes/no or pick one option. Option (a) is what the rules do today. Where your sheet and the EvA outputs we were given disagree, CS400 follows EvA for now (so existing quotations do not change) and CS4800 follows your sheet; section 1 lists these.

We tested the sheet counts on 1200 × 1200 windows of five types, reading every open type as having one fixed pane: Fixed (one fixed pane), Fixed with mullion (fixed | fixed), Single open (shutter | fixed), Double open (shutter | fixed | shutter) and Triple open (shutter | shutter | fixed | shutter).

## 0. Window types behind the sheet counts

0.1 We read your "Single / Double / Triple open" counts as windows with 1 / 2 / 3 shutters plus one fixed pane, so they have as many mullions as shutters. With that reading H412 is simply 4 per mullion, as your sheet says. Is that right? (yes/no; if no, please describe the windows you counted)

## 1. Where the Hilux sheet and EvA disagree

The EvA sample W01 is CS400, 915 × 1220, 2 shutters with a T mullion. For each item, which is right: (a) EvA (what CS400 does today) or (b) the Hilux sheet (what CS4800 does today)?

| Rule | Item | (a) EvA, CS400 today | (b) Hilux sheet, CS4800 today | Question |
|---|---|---|---|---|
| `hl_h425_handle` | H425 multipoint handle | 1 per shutter (W01: 2) | 2 per shutter (W01: 4) | 4.1 |
| `hl_h429_hinge_screw` | H429 friction hinge screw 8×13 | 6 per shutter = per friction-hinge pair (W01: 12) | 6 per hinge, 12 per shutter (W01: 24) | 3.5 |
| `hl_h913_drain_frame` | H913 drainage cap | 1 per 600 mm of frame bottom + 1 (W01: 2; 1200 wide: 3) | 3 fixed / 4 open at 1200 wide | 7.3 |
| `hl_h914_sealant` | H914 sealant | 2 × perimeter / 6 cans (W01: 1.423; 1200 × 1200: 1.6) | 1 bottle per window up to 6 m frame (1) | 7.4 |
| `hl_h407_frame` | H407 SS chevron 35×14 | none | 1 per frame corner (4 on every window) | 2.5 |
| `hl_h408_sash` | H408 MS chevron 40×20.6 | none | 1 per shutter corner (W01: 8) | 2.6 |
| `hl_g29_fixed` | G29 frame glass gasket | none; fixed glass gets G23 glazing gasket only (W02) | around every fixed pane | 5.2 |

## 2. Corner joints and chevrons

2.1 `hl_h404_mesh_sash`: the CS4800 counts for H404 (mesh shutter corner) are 4/8/12 for Single/Double/Triple open. Does every CS4800 open shutter come with a fly mesh shutter by default? (yes = CS4800 `default_mesh` stays 1; no = mesh only when ordered)
2.2 `hl_h427_mesh_hinge`, `hl_g27_mesh`: fly mesh hinges (2 per mesh shutter) and mesh gasket are added only to shutters with the fly mesh option. Is that right? (yes/no)
2.3 `hl_h405_mesh_frame`: the sheet counts 4 H405 mesh frame corner joints even for Fixed windows. Is a mesh frame fitted on fixed windows too? (yes/no)
2.4 `hl_h410_mullion`: CS4800 H410 mullion connector is "2 per mullion" and the counts are 2/2/4/8. The Triple open window has 3 mullions, so the rule gives 6. Should Triple open be (a) 6 or (b) 8? If (b), what is the rule?
2.5 `hl_h407_frame`: H407 SS chevron 35×14 "1 per corner for 40 mm casement frame". EvA's W01 and W02 have none. Is it (a) not used (EvA, CS400 today) or (b) 1 per frame corner on every window (your sheet, CS4800 today)? (see section 1)
2.6 `hl_h408_sash`: H408 MS chevron 40×20.6 "1 per corner for 40 mm casement shutter". EvA's W01 has none. Is it (a) not used (EvA, CS400 today) or (b) 1 per shutter corner (your sheet)? Note: CS4800's sheet has no H408 row. (see section 1)

## 3. Hinges

3.1 `hl_h413_butt`: Window hinge 2 wing, "2 to 4 per shutter". (a) 2 per shutter whatever the size, (b) 3 when the shutter is taller than ___ mm, (c) other.
3.2 `hl_h414_butt3`: CS4800 window hinge 3 wing, "3 to 4 per shutter". When is the 3-wing hinge used instead of the 2-wing? (a) never by default, (b) always on CS4800, (c) above ___ mm shutter height or ___ kg.
3.3 `hl_h416_friction12`, `hl_h417_friction14`: how do you choose the friction hinge size? (a) 12 inch up to 600 mm shutter width, 14 inch above, (b) by shutter height, (c) by shutter weight. Please give the limit.
3.4 `hl_h416_friction12`, `hl_h417_friction14`: "2 nos per shutter". Is one H416/H417 stock unit (a) a pair (as the H416 Item is stocked today) or (b) a single hinge?
3.5 `hl_h429_hinge_screw`: is it 6 screws (a) per shutter, i.e. per friction-hinge pair (EvA, CS400 today), or (b) per hinge, 12 per shutter (your sheet, CS4800 today)? (see section 1)

## 4. Handles, rods and locking plates

4.1 `hl_h425_handle`: is it (a) 1 multipoint handle per shutter (EvA, CS400 today) or (b) 2 (your sheet, CS4800 today)? (see section 1)
4.2 `hl_h428_single`: when a shutter has a single point handle, are the transmission rod and locking plates left out? (yes/no)
4.3 `hl_h422a_rod600`, `hl_h422b_rod800`, `hl_h422c_rod1200`: which rod goes with which shutter height? (a) 600 mm rod under 700 mm, 800 mm rod from 700 to under 1000 mm, 1200 mm rod from 1000 mm, (b) the shortest rod that is at least the shutter height, (c) other. What do you use above 1200 mm?
4.4 `hl_h423_plate`: "2 / 3 per shutter / door". Is it (a) 2 per window shutter and 3 per door, or (b) 2 or 3 per window shutter depending on height?
4.5 `hl_h426_limiter`: "1 per shutter if needed". Is the opening limiter (a) an option per shutter chosen in the designer, or (b) always fitted above some size?

## 5. Gaskets

5.1 `hl_g21_frame`: the CS400 sheet says G21 goes on "frames around and shutter outer sides and fixed glass". EvA's W02 (fixed glass + louvers) has G21 only on the frame sides. Is that right (yes = G21 on frame and shutter sides only), or does fixed glass get G21 too?
5.2 `hl_g29_fixed`: EvA's W02 glazes the fixed pane with G23 only, no G29. Is G29 (a) not used (EvA, CS400 today), (b) fitted on every side of every fixed pane, at the glazing gasket length (CS4800 today), or (c) only on the frame sides of fixed panes? (see section 1)
5.3 `hl_g23_glazing`: we fit G23 (3 mm gasket) on 5 mm and 6 mm glass. Is that right for 5 mm glass, or does 5 mm glass take (a) G23 3 mm, (b) G24 4 mm?
5.4 `hl_g22_glazing`, `hl_g24_glazing`, `hl_g25_glazing`: please give the glazing gasket for each glass thickness, per series. Our guess is 1 mm thinner gasket per 1 mm thicker glass: G25 for 3–4 mm, G24 for 4–5 mm, G23 for 5–6 mm, G22 for over 6 up to 8 mm glass.
5.5 Glass above 8 mm (10 and 12 mm toughened, 24 mm DGU, laminates from 11.52 mm): which gasket do CS400 and CS4800 use? Today the rules add no gasket and the designer shows a "no glazing gasket" warning. Can CS400 take these glasses at all? (yes/no per glass)
5.6 "glass perimeter × 2 sides / 1 side": we count one side, like EvA W01. When do you count 2 sides? (a) never for these series, (b) shutter glass 2 sides and fixed glass 1 side, (c) other.
5.7 `hl_g27_mesh`: is the fly mesh gasket length the shutter perimeter? (yes/no)

## 6. Glass

6.1 8+8 Lami (LAM-8C-8C-152): the sheet labels it 17.52 mm but describes 8 mm + 1.52 PVB + 6 mm (= 15.52). Is it (a) 8 + 8 with 1.52 PVB = 17.52 mm, or (b) 8 + 6 = 15.52 mm?
6.2 8+8 Lami (2.28 Sentry Lami) (LAM-8C-8C-228S): the sheet says 17.52 mm, but 8 + 8 + 2.28 = 18.28 mm. Which is right: (a) 18.28 or (b) 17.52? This decides the glazing gasket for it (question 5.5).
6.3 `hl_h905_glass_packer2`: "8 to 10 per shutter". Is it (a) 8 per pane, fixed panes included, or (b) 8 per shutter and 10 above ___ mm?
6.4 `hl_h906_glass_packer3`: when do you use 3 mm glass packers instead of 2 mm? (a) never by default, (b) for glass thicker than ___ mm.
6.5 GST: new glass Items get HSN 70071900 (toughened safety glass). Is that right for (a) all glasses, or do laminated (7007 29) and DGU (7008) glasses need their own HSN? (a/b)

## 7. Site fixing and consumables

7.1 `hl_h911_fastener`: wall fasteners "every 600 to 800 mm". EvA uses ceil(side length / 500), giving 2 on a 915 mm side and 3 on a 1220 mm side. Keep this? (yes/no; if no, give spacing and end distance)
7.2 `hl_h912_hole_cap`: "fixed windows not required". Should fixed-only windows get (a) hole caps like other windows, as EvA does on W02 today, or (b) no hole caps?
7.3 `hl_h913_drain_frame`: drainage caps "2 to 6 per window, every 600 to 800 mm of frame bottom". Both series use 1 per 600 mm of bottom + 1, max 6 (EvA W01: 2 at 915 wide; your count 3 for fixed at 1200 wide). Your counts give 4 for open windows 1200 wide. Do open windows get (a) the same as fixed or (b) 1 more? If (b), why (sash drainage?)
7.4 `hl_h914_sealant`: is it (a) EvA's 2 × frame perimeter / 6 cans (CS400 today) or (b) 1 bottle per window up to 6 m frame length, 2 up to 12 m (your sheet, CS4800 today)? (see section 1)
7.5 `hl_h915_masking`: "frame running meter 2 sides × 2". Is masking tape (a) 2 × frame perimeter (EvA W01 8.54 m) or (b) 4 × frame perimeter?
7.6 `hl_h910_guide_rail`: SS guide rail 13 mm "per track × bottom". Is it only for sliding windows (yes = never on CS400/CS4800 casements)?

## 8. CS4800 doors

H402 (door frame and door shutter corners), H415, H418–H421 and H424 are kept as rules that never fire, because the designer has no door type yet. No question; they will get rules when doors are added.

## 9. Profiles, glazing beads and adaptors from the DXFs

CS4800 v2 takes its profiles, cutting deductions, glazing beads and sash glass adaptors from your CS4800 DXF, checked against EvA's design 123 (1500 × 1500, one fixed pane and one outward shutter with a mullion at 750, 12 mm glass). Where the DXF and EvA differ by rounding, the rules follow EvA.

9.1 `CS4801`, `CS4802`: the Section Details table in the CS4800 DXF prints the CS4801 and CS4802 descriptions swapped ("mullion" next to CS4801). EvA and the DXF cutting lists use CS4801 = frame (0.732 kg/m) and CS4802 = mullion (0.880 kg/m), and so do we. Is that right? (yes/no)
9.2 The DXF tables give one perimeter per profile (the anodised and powder-coat columns are equal). We store it as the profile's total perimeter (full outline), because the visible perimeters we already have are much smaller (E104156 90 vs DXF 202, E104159 110 vs 269, E104160 120 vs 282, CS4807 40 vs 140). Please confirm that the DXF anodised / powder-coat perimeter is the full outline (total), and send the visible (exposed) perimeter of each profile.
9.3 Deductions we could not read straight from the DXF (CS4800 v2 uses the EvA 123 values):
- `sash_glass`: sash to glass 57 mm per side (EvA 123: 727 − 2 × 57 = 613). The DXF says HS − ((52.7 × 2) + 8), which is 56.7. Which is right: (a) 57, (b) 56.7?
- `fixed_glass_side_mullion`: fixed glass next to a mullion 15.5 mm (EvA 123: 750 − 29.5 − 15.5 = 705). The DXF formula for two fixed panes implies 16.6. Which is right: (a) 15.5, (b) 16.6?
- `sash_side_mullion`: shutter next to a mullion 4.5 mm (EvA 123: 750 − 18.5 − 4.5 = 727). The DXF has no formula for it. Is 4.5 right? (yes/no)
- `bar_end_mullion`, `bar_end_transom`: a mullion or transom ending on another bar is cut like one ending on the frame (25.5 per end). Is that right? (yes/no; if no, give the deduction)
- `sash_side_transom`, `fixed_glass_side_transom`: we use the mullion values (4.5 and 15.5) next to a transom. Is that right? (yes/no)
- `glazing_gasket`: the CS4800 glazing gasket rules cut the gasket at glass size − 2 × 14 mm. EvA 123 cuts G23 at glass − 32 on the fixed pane (673 / 1409) and glass − 26 on the shutter pane (587 / 1323). What is the glazing gasket length for (a) fixed glass and (b) shutter glass?
9.4 `mr_transom`: the DXF has no transom. Does a CS4800 transom use the CS4802 mullion profile and its deductions? (yes/no; if no, which profile)
9.5 `mr_bead_single`, `mr_bead_12`, `mr_bead_dgu`: the DXF gives CS4807 for 5, 6 and 8 mm glass, CS4808 for 12 and 13.5 mm and CS4809 for 24 mm. We use CS4807 from 5 to 8 mm, CS4808 from 11.5 to 13.52 mm (so the 5+5, 6+5 and 6+6 laminates take it) and CS4809 for any DGU from 20 to 28 mm. Glass between these (10 mm, laminates above 13.52 mm) gets no bead and a "no glazing bead" warning. (a) Is that right? (b) Which bead goes with 10 mm glass and with the 15.52 to 18.28 mm laminates? (c) Do CS4807 and CS4809 also lose 20 mm at each end of the side beads, like CS4808 in EvA 123?
9.6 `mr_adaptor_single`, `mr_adaptor_12`: in a shutter we fit HSL3409 single glass adaptor for 5 to 8 mm glass and HSL3410 laminated glass adaptor for 11.5 to 13.52 mm glass (EvA 123 uses HSL3410 for 12 mm). DGU and laminates above 13.52 mm get no adaptor. Is that right? Which adaptor (if any) goes with 10 mm glass, 24 mm DGU and the thicker laminates? Is HSL3409 cut like HSL3410 (glass + 8 mm, 45°)?
9.7 EvA's design 123 shutter weighs 29.8 kg, but CS4800's shutter weight limit (`max_shutter_kg`, friction stay) is 25 kg, so our designer flags it as an error. What is the CS4800 shutter weight limit?
9.8 The CS400 DXF gives 4880 and 5800 mm bars for E104159 (mullion) and E104160 (sash). The EvA data we were given has 4800 and 5800. Which is right: (a) 4800 (what CS400 uses today), (b) 4880?
9.9 One drawing sheet in the CS400 DXF has the title block "series = CS4800". Is that sheet CS400 or CS4800?
9.10 EvA design 123 uses 12 mm reflective toughened glass, but the glass catalogue has no 12 mm reflective glass (only 12 mm clear toughened, 12CTG, which our test uses). Should a 12 mm reflective toughened glass be added? (yes/no; give its code)
