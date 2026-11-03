# Questions for Hilux: CS400 and CS4800 hardware, gaskets and glass

These questions come from turning the Hilux CS400 and CS4800 hardware lists into series rules (`onebook_fenestration/series_studio/data/cs400_v2.json` and `cs4800_v1.json`). Each rule we had to guess is marked `ASSUMPTION`, `SHEET SAYS` or `CHECK` in its note, and the rule id is listed in backticks below. Please answer each question with yes/no or pick one option. Option (a) is what the rules do today. Where your sheet and the EvA outputs we were given disagree, CS400 follows EvA for now (so existing quotations do not change) and CS4800 follows your sheet; section 1 lists these.

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

## 2. Corner joints and chevrons

2.1 `hl_h404_mesh_sash`: the CS4800 counts for H404 (mesh shutter corner) are 4/8/12 for Single/Double/Triple open. Does every CS4800 open shutter come with a fly mesh shutter by default? (yes = CS4800 `default_mesh` stays 1; no = mesh only when ordered)
2.2 `hl_h427_mesh_hinge`, `hl_g27_mesh`: fly mesh hinges (2 per mesh shutter) and mesh gasket are added only to shutters with the fly mesh option. Is that right? (yes/no)
2.3 `hl_h405_mesh_frame`: the sheet counts 4 H405 mesh frame corner joints even for Fixed windows. Is a mesh frame fitted on fixed windows too? (yes/no)
2.4 `hl_h410_mullion`: CS4800 H410 mullion connector is "2 per mullion" and the counts are 2/2/4/8. The Triple open window has 3 mullions, so the rule gives 6. Should Triple open be (a) 6 or (b) 8? If (b), what is the rule?

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

5.1 `hl_g21_frame`: the CS400 sheet says G21 goes on "frames around and shutter outer sides and fixed glass". Around fixed glass, do you use (a) G29 frame glass gasket or (b) G21 as well?
5.2 `hl_g29_fixed`: is G29 fitted on (a) every side of every fixed pane, at the same length as the glazing gasket, or (b) only the frame sides of fixed panes?
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
