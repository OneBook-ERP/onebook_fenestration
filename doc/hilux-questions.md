# Questions for Hilux: CS400 and CS4800 hardware, gaskets and glass

These questions come from turning the Hilux CS400 and CS4800 hardware lists into series rules (`onebook_fenestration/series_studio/data/cs400_v2.json` and `cs4800_v1.json`). Each rule we had to guess is marked `ASSUMPTION`, `CONFLICT` or `CHECK` in its note, and the rule id is listed in backticks below. Please answer each question with yes/no or pick one option. Option (a) is what the rules do today.

We tested the sheet counts on 1200 × 1200 windows of five types: Fixed (one fixed pane), Fixed with mullion (fixed | fixed), Single open (one shutter), Double open (shutter | shutter) and Triple open (shutter | shutter | shutter).

## 0. Window types behind the sheet counts

0.1 The counts for H412 (4 per mullion) and H410 (2 per mullion) only fit the prose if "Single open" also has a mullion, i.e. shutter + fixed. Which windows did you count?
  (a) Single = 1 shutter, Double = 2 shutters, Triple = 3 shutters, with no fixed panes. This is what our tests assume, and it forces the extra "+4 / +2 for open windows" rules `hl_h412_open` and `hl_h410_open`.
  (b) Single = shutter + fixed, Double = 2 shutters + fixed, Triple = 3 shutters + fixed. In that case H412 is simply 4 per mullion.
  (c) Something else (please describe).

## 1. Where the Hilux sheet and EvA disagree (W01, CS400, 915 × 1220, 2 shutters + T mullion)

For each item, which one is right: (a) the Hilux sheet or (b) EvA?

| Rule | Item | (a) Hilux sheet gives | (b) EvA gives |
|---|---|---|---|
| `hl_h412_open` | H412 mullion screw 8×50 | 8 (sheet count 8 for Double open) | 4 (4 per mullion) |
| `hl_h913_drain_frame` | H913 drainage cap | 3 (1 per 600 mm of frame bottom + 1, +1 for open windows) | 2 |
| `hl_h425_handle` | H425 multipoint handle | 4 (2 per shutter) | 2 (1 per shutter) |
| `hl_h429_hinge_screw` | H429 friction hinge screw 8×13 | 24 (6 per hinge, 2 hinges per shutter) | 12 (6 per shutter) |
| `hl_h914_sealant` | H914 sealant | 1 bottle (up to 6 m frame) | 1.423 cans (2 × perimeter / 6) |

## 2. Corner joints and chevrons

2.1 `hl_h404_mesh_sash`: the CS4800 counts for H404 (mesh shutter corner) are 4/8/12 for Single/Double/Triple open. Does every CS4800 open shutter come with a fly mesh shutter by default? (yes = CS4800 `default_mesh` stays 1; no = mesh only when ordered)
2.2 `hl_h427_mesh_hinge`, `hl_g27_mesh`: fly mesh hinges (2 per mesh shutter) and mesh gasket are added only to shutters with the fly mesh option. Is that right? (yes/no)
2.3 `hl_h405_mesh_frame`: the sheet counts 4 H405 mesh frame corner joints even for Fixed windows. Is a mesh frame fitted on fixed windows too? (yes/no)
2.4 `hl_h410_open`: CS4800 H410 mullion connector counts are 2/2/4/8. Our rule gives 6 for Triple open. Should it be (a) 6 or (b) 8? If (b), what is the rule?

## 3. Hinges

3.1 `hl_h413_butt`: Window hinge 2 wing, "2 to 4 per shutter". (a) 2 per shutter whatever the size, (b) 3 when the shutter is taller than ___ mm, (c) other.
3.2 `hl_h414_butt3`: CS4800 window hinge 3 wing, "3 to 4 per shutter". When is the 3-wing hinge used instead of the 2-wing? (a) never by default, (b) always on CS4800, (c) above ___ mm shutter height or ___ kg.
3.3 `hl_h416_friction12`, `hl_h417_friction14`: how do you choose the friction hinge size? (a) 12 inch up to 600 mm shutter width, 14 inch above, (b) by shutter height, (c) by shutter weight. Please give the limit.
3.4 `hl_h416_friction12`, `hl_h417_friction14`: "2 nos per shutter". Is one H416/H417 stock unit (a) a pair (as the H416 Item is stocked today) or (b) a single hinge?
3.5 `hl_h429_hinge_screw`: is it 6 screws (a) per hinge (12 per shutter) or (b) per shutter? (see section 1)

## 4. Handles, rods and locking plates

4.1 `hl_h425_handle`: is it (a) 2 multipoint handles per shutter or (b) 1? (see section 1)
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

## 7. Site fixing and consumables

7.1 `hl_h911_fastener`: wall fasteners "every 600 to 800 mm". EvA uses ceil(side length / 500), giving 2 on a 915 mm side and 3 on a 1220 mm side. Keep this? (yes/no; if no, give spacing and end distance)
7.2 `hl_h912_hole_cap`: "fixed windows not required". Should fixed-only windows get (a) hole caps like other windows, as EvA does on W02 today, or (b) no hole caps?
7.3 `hl_h913_drain_frame`: drainage caps "2 to 6 per window, every 600 to 800 mm of frame bottom". The counts give 3 for fixed and 4 for open windows 1200 wide. Is it (a) 1 per 600 mm of bottom + 1, + 1 for open windows, max 6, or (b) other?
7.4 `hl_h914_sealant`: is it (a) 1 bottle per window up to 6 m frame length, 2 up to 12 m, or (b) EvA's 2 × perimeter / 6 cans? (see section 1)
7.5 `hl_h915_masking`: "frame running meter 2 sides × 2". Is masking tape (a) 2 × frame perimeter (EvA W01 8.54 m) or (b) 4 × frame perimeter?
7.6 `hl_h910_guide_rail`: SS guide rail 13 mm "per track × bottom". Is it only for sliding windows (yes = never on CS400/CS4800 casements)?

## 8. CS4800 doors

H402 (door frame and door shutter corners), H415, H418–H421 and H424 are kept as rules that never fire, because the designer has no door type yet. No question; they will get rules when doors are added.
