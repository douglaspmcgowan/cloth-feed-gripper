# TP-11 Fit of the printed parts and the wrist interface

<!-- hardware-scope:begin -->
**Hardware scope — arm: `absent`; gripper: `none`.** The arm is not used in this procedure. The gripper is not powered or commanded in this procedure.
<!-- hardware-scope:end -->

<!-- procedure-body:begin -->
**What it proves:** that holes, the horn pilot, inserts and pins print at sizes that fit, on the team's own printer, before the real parts are printed; and that the wrist plate fits the real SO-101 horn (R22) and the front plate takes the camera screws (R23). It also replaces the assumed FDM bias and scatter in the tolerance stacks with measured ones (M12) and measures the real horn (M15). It is also the measurement gate for CAD rev B: servo body width on three servos and the shaft offset (part F) decide the cradle pocket width and whether the servo must be located by its boss (`tolerance_stacks.md` rev B rows 1 and 3). About 55 min plus printing. Data sheet: [`../datasheets/TP-11.html`](../datasheets/TP-11.html) (CSV: `TP-11.csv`).

| | |
|---|---|
| Requirements | R22 (wrist interface), R23 (camera provision); measurements M12 (printer fits), M15 (real horn dimensions) |
| Pass | R22: coupon slides onto the real horn pilot by hand with no rock; 4 × M3×6 seat with ≥ 1.5 mm thread engagement. R23: both camera insert bores take an insert and an M3 screw |
| Instrument | Digital calipers, U = 0.049 mm on a printed surface [D `test_plan.py`]; drill-bit shanks as pin gauges; an M3 screw; feeler gauges |
| Sample size | 5 coupons for bias and scatter (`tolerance_stacks.md` section 8); 1 coupon per CAD size tried on the horn |

## Expected values

| Feature | CAD | Expected as printed / fit | Source |
|---|---|---|---|
| M3 clearance hole | Ø3.6 (or print Ø3.0, drill Ø3.3) | about Ø3.35; smallest Ø3.25; an M3 passes freely | [D] `tolerance_stacks.md` fix 1, section 2 (MMC hole 3.25) |
| Small-hole bias (up to about Ø8) | – | −0.25 mm on diameter | [S] CNC Kitchen, via `tolerance_stacks.md` section 4 |
| Head counterbore | Ø6.5 | about Ø6.25; an M3 pan head (dk 5.3-5.6) seats freely | [D] fix 2; dk [A ISO 7045 in the stacks] |
| Pilot recess, with 0.3×45° chamfer | Ø19.51 (also try 19.45, 19.56) | about Ø19.36 ± 0.10 for CAD 19.51; clearance on the horn 0.02-0.30 mm diametral | [D] fix 4; window [A] T02 |
| Heat-set insert bore | Ø4.2 × 3.5 deep | prints about Ø3.95; insert melts in flush and square | [D] `assembly/ASSEMBLY.md` step 2 note |
| Pin bores in the plates | Ø2.9, line-reamed with a 3 mm reamer | a 3 m6 dowel starts by hand into both bores after reaming | [D] ASSEMBLY step 1; `params.json` `knuckle.pin_hole_cad` |
| Knuckle bore | reamed Ø3.05, or a 3×5×8 bronze sleeve pressed in | running clearance on the pin: 3.05-3.10 reamed; about 0.02 with the sleeve | [D] `tolerance_stacks.md` section 2 ruling; sleeve [A] |
| Finger pegs | Ø2.0 dowels, 2 per finger | float ≤ 0.05 mm | [A] fix 10 |
| Servo body width W (part F) | CAD 20.0; rev A pocket 20.4, rev B pocket 20.5 | listed DS3218MG width 20.1 mm; the CAD value (20.0) and a 20.5 mm reading are the two edges the stack is unsure of; measure 3 servos | [S] servodatabase.com/servo/dsservo/ds3218-mg (2026-10-11, low-medium confidence) via `tolerance_stacks.md`; tolerance ±0.10 [A] |
| Shaft offset s (part F) | 0 (shaft on the case centre line) | ±0.20 mm unpublished for hobby servos | [A] `tolerance_stacks.md` inputs (`servo_shaft_pos_tol`) |
| Real horn (M15) | – | pilot Ø19.2, bolt circle Ø14.0 (9.90 mm square), holes 2.5 deep | [D] `research/so101.md` rows 2, 4 |

## Equipment

Calipers with depth rod, drill-bit set (Ø2.0-4.0 in 0.1 mm steps) as pin gauges, M3×6 pan-head screws (10), 6 M3 heat-set inserts and the soldering-iron insert tip, 3 mm hand reamer, 3 m6 × 15 dowels, a 3×5×8 bronze sleeve, feeler gauges, the real SO-101 arm (or its spare wrist-roll horn), the servo, a steel square.

## The coupon (print 5, same settings and orientation as the housing, mount face on the bed)

Print the nine items of `tolerance_stacks.md` section 8, in PETG at the housing's settings:

| # | Item | Measure |
|---|---|---|
| 1 | Holes CAD Ø3.0/3.2/3.4/3.6/3.8, 3 of each; counterbores Ø6.0/6.5, 2 of each | gauge each hole; M3 go/no-go; pan head in each counterbore; caliper the counterbore ID |
| 2 | Recess CAD Ø19.40/19.45/19.51/19.56/20.0, 1.0 deep, with and without the 0.3×45° chamfer | fit on the **real horn**; caliper ID |
| 3 | 4× hole pattern on the Ø14.0 bolt circle | screw onto the real horn; hole positions from the recess edge |
| 4 | Hub OD Ø23.2 and Ø24.0, 2 mm tall | caliper at the first layer and at 1.5 mm |
| 5 | Pocket widths 20.2/20.3/20.4/20.5 | drop in the real DS3218MG; caliper the servo case |
| 6 | Steps 1.0/3.0/5.0 mm | depth rod |
| 7 | Two 2.5 mm plates on standoffs, 2 × Ø2.9 holes, line-reamed together; press in m6 pins | pin tilt: square on the plate, feeler at the pin tip |
| 8 | Knuckle coupons: reamed Ø3.05 bore and a bronze-sleeve bore, both 7.7 long; a printed dog coupling on a spare horn | rock on the pin; feeler at the end; dog lash |
| 9 | Two holes at the pin spacing | caliper centre to centre |

Add three features section 8 lacks: two Ø4.2 × 3.5 insert bores, two Ø4.2 × 4.5 bores 8.1 mm apart (the camera pad, `params.json` `camera_pad`), and one finger root block with its two Ø2.0 peg holes. Use the current pin spacing, **28.50 mm** (`params.json` `gear.center_distance`, PA6-CF m1.5 z19), for items 7 and 9; section 8 still says 24.00 (old m1 z24 gear).

## Steps

**A. Gauge the drill shanks (once).** Caliper each shank you will use, 3 readings; record its real diameter. A shank is a go gauge: it enters the hole by hand without force.

**B. Coupon features (M12), each of the 5 coupons.**

1. Holes: find the largest shank that enters each hole. Record it as the hole size. Try an M3 screw in each: passes / tight / no.
2. Counterbores: caliper the ID at mid-depth (2 readings at 90°); drop a pan head in.
3. Hub OD (item 4): caliper at the first layer and at 1.5 mm, 3 readings each at 60° steps.
4. Steps, pockets (items 5, 6): as in the table above.
5. Insert bores: heat-set one insert per bore (iron about 220 °C, push only until flush, ASSEMBLY step 2). Check flush and square with the steel square; thread an M3×6 in and out by hand.
6. Pin plates (item 7): ream the two plates together with the 3 mm reamer. Press the pins in. Stand the square on the plate against each pin and slide feelers between pin tip and square: the thickest that enters is the tilt over the pin length.
7. Knuckle coupons (item 8): slide each onto a pin; rock it and feel for play; feeler between knuckle face and plate for end play. Press the bronze sleeve into its bore and repeat.
8. Finger root: push the two Ø2.0 dowels through block and finger; wiggle the finger along its length and read the float with a feeler.

**C. Real horn (M15), calipers on the arm's wrist-roll horn.**

9. Horn OD (pilot): 3 readings at 60° steps.
10. Bolt circle: caliper across two diagonally opposite holes, inside-to-inside and outside-to-outside; centre distance = mean of the two. Repeat on the other diagonal. Expect 14.0 mm (adjacent holes 9.90 mm).
11. Hole depth: depth rod down a hole, or the largest shank that enters, marked at the horn face. If a hole is open at the bottom, record "through". Decides the screw: with the 3.0 mm clamp an M3×6 protrudes 3.0 mm below H.

**D. Fit on the real horn (R22).**

12. Take the coupon with the chosen recess (CAD 19.51 with chamfer unless step B says otherwise) and Ø3.6 holes, Ø6.5 counterbores. Slide it onto the horn by hand. It must go on without force and must not rock when pressed at its edge.
13. Fit 4 × M3×6. Each head must seat in its counterbore before the screw bottoms (stop if a screw bottoms first: ASSEMBLY step 4 risk). Measure the clamp thickness t (counterbore floor to recess floor) with the depth rod.

**E. Camera bores (R23).** On the real front plate (or a spare print of it): heat-set one insert in each of the two camera bores and run an M3 screw in by hand. The BOM has no line for these two inserts (ASSEMBLY step 16 note); buy two extra. Inserts add mass: weigh them for TP-09.

**F. Servo body width and shaft offset (the CAD rev B gate).** Use three servos from the same lot as the flight servo (the spare DS3218MG counts); do not use a servo with a bent case.

14. Servo body width W: with the calipers across the two long flat faces of the aluminium middle shell, 3 readings per servo at 120° apart along the case length (avoid the ears and the label). Record each servo's largest reading; W_max is the largest of the three servos, W_min the smallest.
15. Shaft offset s: with the calipers' depth rod, measure from the output shaft's outer edge to the nearest long face, on both sides (a on one side, b on the other). The shaft centre sits (a − b)/2 off the case centre line, so s = (a − b)/2 (U 0.05 mm). Record s for each servo.
16. Printed pocket width P: from the item-5 pockets (20.2, 20.3, 20.4, 20.5), the width as printed, 3 readings each (calipers on the inside jaws). Find the CAD pocket whose printed width P gives the gap g = P − W_max between 0.05 and 0.30 mm.

## Data to record

One row per feature and coupon: feature, cad_mm, measured_mm, gauge_result (shank that enters, screw passes / tight / no, insert flush), limit, pass, notes. Plus the horn rows (M15) and the R22, R23 rows.

## Calculation

- Bias = mean(printed − CAD); scatter ±T = 3 × standard deviation over the 5 coupons. Feed both into `basis.yaml` as `tolerance_stacks.md` section 8 names them, and re-run the stacks.
- Pilot clearance c = recess ID − horn OD.
- Thread engagement e = min(6.0 − t, depth) − 0.5 mm tip chamfer (T03). Tip clearance = depth − (6.0 − t) (T03B; ignore if the holes are through).

## Pass / fail

- Gauge U for every length below: 0.049 mm (calipers). For a window, **pass** needs the reading inside the window by at least U at each end, **fail** needs it outside by at least U, anything else is **indeterminate** (re-measure with a better gauge or print another coupon).
- **R22:** pass if the coupon slides on by hand with no rock **and** 0.02 ≤ c ≤ 0.30 mm **and** all four heads seat **and** e ≥ 1.5 mm **and** tip clearance ≥ 0.2 mm (or through holes). Record horn OD and bolt circle (M15) against Ø19.2 and Ø14.0.
- **R23:** pass if both inserts sit flush and square and an M3 screw runs in by hand. The 10 g camera allowance is counted in R10 (TP-09).
- **M12 features:** M3 hole passes if an M3 screw passes freely and the hole gauges ≥ 3.25 mm; counterbore if the head seats freely; insert if flush, square and threads by hand; pins if a dowel starts by hand after reaming; pegs if float ≤ 0.05 mm. Record the knuckle bore clearance and pin tilt for the stacks; they have no single pass number here.

**F. Servo width and shaft offset: what each result means (U 0.049 mm).** g = P − W_max (printed pocket minus widest servo).

| Result | Meaning for CAD rev B |
|---|---|
| W_max ≤ 20.15 mm and the CAD 20.4 pocket prints P ≥ 20.30 | The listed 20.1 mm width is right. The rev A pocket (20.4) still drops the servo in (g ≥ 0.15). Keep 20.4 only if the servo is also located by its Ø9 boss; rev B row 3 (20.5) is then optional |
| 20.15 < W_max ≤ 20.35 mm | The body is wider than listed but fits 20.4 (g ≥ 0.05 + U needs P ≥ W_max + 0.10). Adopt rev B row 3 (pocket 20.5) **together with** row 1 (boss location); the pocket alone is rejected (T14-cad205, 49.9 % yield) |
| 20.35 < W_max ≤ 20.45 mm (the "20.5 mm body" case) | The servo does not drop into 20.4 and sits at g ≈ 0.05-0.15 in 20.5. Pocket 20.6 with the boss bore (rev B row 1), and update `servo_body_w` in `params.json` |
| W_max > 20.45 mm | Not a DS3218MG-class case, or a measuring error: re-measure, then stop and tell the CAD owner before printing rev B |
| \|s\| ≤ 0.06 − 0.05 = 0.01 mm on all three | The dog slot (3.14 mm, half-clearance about 0.06 mm [D `basis.yaml` `dog_clear`]) can work without the boss: row 1 is optional |
| \|s\| larger on any servo (expected, ±0.20 mm [A]) | Locate the servo by its Ø9 boss (rev B row 1) and open the dog slots to 3.4 mm; the shaft offset is then taken up by the boss bore, not the dog |

Pass for the gate: W_max, W_min and s recorded for 3 servos, and one pocket CAD size chosen with g between 0.05 and 0.30 mm (g ≥ 0.05 + U = 0.10 mm for PASS, g ≤ 0.00 mm for FAIL, 0.00-0.10 mm INDETERMINATE: print the next pocket size). Enter W_max, W_min and the s values into `basis.yaml` (`servo_body_w_tol`, `servo_shaft_pos_tol`) and re-run the stacks.

## Hazards

- Soldering iron at 220 °C: use a stand; PETG fumes, ventilate.
- Do not force a screw that bottoms: the SO-101 horn threads are aluminium and strip.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| M3 will not pass a Ø3.6 hole | Bias worse than −0.25: drill Ø3.3 (fix 1) or raise the CAD size | Tolerancing owner |
| Coupon will not slide on, or rocks | Pilot bias differs from −0.15 [A]; pick the coupon size that fits (C5) | Tolerancing owner |
| Screw bottoms before the head seats | Horn holes shallower than 3.0 mm below H: use a shorter screw only if e ≥ 1.5 still holds (fix 3) | CAD owner |
| Insert tilts or sinks | Bore too big or iron too hot; reprint the bore 0.1 mm smaller | CAD owner |
<!-- procedure-body:end -->
