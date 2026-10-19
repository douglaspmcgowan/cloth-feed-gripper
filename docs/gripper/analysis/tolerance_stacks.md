# Tolerance stacks: gripper-wrist interface and gear mesh (CAD rev A)

<!-- tolstack:release:start -->
Do not print revision B parts in these loops: T14B

| Stack | Loop | Verdict | Cpk cold | Cpk hot | Parts in loop | What clears it |
|---|---|---|---:|---:|---|---|
| T09H | Largest hold force the firmware can reach on the softest finger (R14 under the R15 cap) | MARGINAL | 1.28 ± 0.01 | 1.28 | servo horn, knuckle A, knuckle B, finger A, finger B, TPU pads | Needed only once the dog slots open to 3.4 (rev B row 1): the 1.5 deg of dog lash moves the first contact toward the jaw floor, and the absolute floor then cuts the squeeze short (T09H falls to Cpk 0.99 in the combined rev B run). The floor relative to the calibrated contact angle (the T09F firmware request, APPLIED in config.h JAW_FLOOR_BELOW_C0_DEG 4.9 for the ruled 8 N; 6.2 in round 2): T09H-relfloor8. The 4.9 deg floor sits just past the 4.867 deg squeeze cap, so it is MARGINAL exactly as with 6.2 (T09H-relfloor); the softest pair at the cap is the limit, not the floor. |
| T14B | Dog coupling — servo shaft offset from pin A against the dog slot clearance | FAIL | 0.98 ± 0.00 | 0.66 | mid plate, servo cradle, gripper servo, servo horn, knuckle A, pin A | Locate the servo by its Ø9 output boss in a reamed bore in the 1.6 mm housing web at the case top (the boss is concentric with the shaft) and open the dog slots to 3.4 (lash about +/-1.5 deg [A: arithmetic here, (3.4 - 0.1 - 2.927) / (2 x 7 mm) rad]). With the web terms T14B-boss34 fails at Cpk 0.98. A 3.42 mm slot adds 0.010 mm half-clearance and restores about Cpk 1.05, but costs the closure window; the robust fix is a zero-lash coupling that takes offset, such as an Oldham disc. |
| T16 | Pin axis tilt, centre-distance change across the 8 mm gear face | MARGINAL | 1.30 ± 0.01 | 1.30 | mid plate, front plate, knuckle A, knuckle B, pin A, pin B | none recorded |

Clear to print on the assumed inputs: camera bracket, deck, finger A, finger B, front plate, knuckle B, M3 horn screws, pin B, servo 5, spider, TPU pads, wrist link, wrist mount.
Every verdict rests on at least one assumed input until coupon measurements replace them.
<!-- tolstack:release:end -->

**Rev B as one set: 23 of 26 checks PASS, 2 are MARGINAL, 1 FAIL** (on assumed inputs: T16 is MARGINAL at Cpk 1.30, T16B accepts exactly 0.000 worst-case clearance, and T07 passes at 1.43) (R15 = 8 N ruled, R19 = 0.75 s; with the gates below and the firmware as shipped) [D `tolstack.py revb`]. T09T now passes the ruled 0.75 s limit at first contact (Cpk 8.28); the declined 3° slow-zone alternative remains a historical comparison (`controls.md` 6.4). The relative jaw floor, moved from θ_c0 − 6.2° to θ_c0 − 4.9° on 2026-10-16 for the ruled 8 N, gives T09F PASS (T09F-relfloor8, Cpk 1.46) and bounds the peak at the over-force trip: T09P PASS (T09P-floor49, Cpk 1.46; the 7.75 N trip alone holds 8 N in only 11.53 % of builds, and no trip that passes the stack avoids false trips, `controls.md` 6.4). T09H (the softest finger reaching 5 N) is MARGINAL, Cpk 1.28, since the firmware's squeeze cap fell from 5.137° to 4.867° (0.5 N cap margin, `F_CAP_MARGIN_N`). The remaining FAIL is mechanical: T14B, the dog coupling, Cpk 0.98, 99.84 % yield. No dog slot up to 3.8 mm reaches PASS: at 3.8 mm T14B Cpk 2.27 is still MARGINAL because its worst case breaks the spec by 0.044 mm, and from 3.6 mm the closure window (T09) fails (`results/sweep_T14B_dog_slot.md`, `results/sweep_T09_dog_slot.md`). Coupon items 8 and 10 decide it, or use an Oldham disc. Hot (PETG seat relaxed) it fails: Cpk 0.66. The combined run changed the rev B list in three places that one-fix-at-a-time proofs missed: pins graded to 0.020 mm clearance, a firmware relative jaw floor for T09H, and a TCP calibration for T05 (see *Combined rev B run*). Rev A as drawn: 10 of 26 checks are reported as FAIL, 2 are marginal, 14 pass; nine of the ten fail on their own, because T03 passes by itself and is reported as a failure only while T03B fails (counts printed in `analysis/gripper/tolstack/results/SUMMARY.md`) [D]. T09F (the force at the absolute jaw floor) is a FAIL, Cpk −0.04 against the ruled 8 N (0.90 against the superseded 10 N), because the servo position errors at first contact and at the floor are sampled as independent (`stacks/T09F_force_at_floor.yaml` notes). Worst as drawn: T03B, the screw tip against the horn hole floor, 0.00 % yield at the CAD 2.5 mm hole depth [D]. It depends on the real horn hole depth, which nobody has measured: measure it (DB M15); M3x6 is MARGINAL from 3.5 mm deep and PASSES from 3.75 mm deep (`results/sweep_T03B_horn_hole_depth.md` [D]); shallower than 3.5 mm, drill and re-tap the horn holes deeper. The worst that needs a CAD change is T14B, 40.68 % yield as drawn [D]. At the ruled R15 = 8 N, T09H (the softest finger reaching the 5 N hold) stays MARGINAL, Cpk 1.28, because the 4.9° floor enforces 8 N and the squeeze cap stays at 4.867° (`F_CAP_N` 10); compiling `F_CAP_N` 8 instead fails it (T09H-r15p8, 39.50 %; see *Ruled R19 and historical limits*).

**Print now or wait?** Print the coupon now (*Coupon plan* below) on rev A dimensions; it measures your printer and sets the recess, pocket and hole sizes. Wait on the coupled mid plate, servo cradle, gripper servo, servo horn, knuckle A and pin A until coupon items 8 and 10 clear T14B, or use a different coupling. Use the generated release gate above for every other revision B part.

<!-- tolstack:verdicts:start -->
| Stack | Checks | Verdict | Yield (MC) | Cpk | Worst case | Spec | Dominant contributor (variance share) | Cheapest fix (proved by) |
|---|---|---|---|---:|---|---|---|---|
| T01 | Horn-to-mount bolt pattern fit (4x M3 on the 14.0 BC) | **MARGINAL** | 99.996 % (<92 ppm (4 of 100,000 samples; 95% upper bound) out) | 1.31 ± 0.02 | -0.313 … 0.015 (out) | USL 0.000 mm radial interference | hole_position (81 %) | Open the 4 mount holes to CAD 3.7 (T01-cad37). The recess locates the mount, so larger holes cost nothing. (T01-cad37: PASS, Cpk 1.77) |
| T01H | M3 pan head clears its counterbore (rev A Ø6.5) | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.02 ± 0.01 | -0.550 … -0.075 (in) | USL 0.000 mm radial interference | cbore_position (55 %) | none needed |
| T02 | Horn pilot recess radial fit (Ø19.2 horn in the printed Ø19.51 recess) | **MARGINAL** | 99.976 % (240 ppm out) | 1.16 ± 0.02 | 0.000 … 0.300 (out) | LSL 0.020, USL 0.300 mm diametral clearance | recess_d_printed (80 %) | Open the recess to CAD 19.56 and accept up to 0.40 diametral clearance (T02-relax40). The radial float then stays inside the 0.30 concentricity budget (T04-relax40). Better still, print the coupon and size the recess from the measured hole. (T02-relax40: PASS, Cpk 1.61) |
| T03 | Axial stack horn face to clamp to screw — thread engagement | **FAIL (blocked by T03B; own check PASS)** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 4.99 ± 0.04 | 1.885 … 2.100 (in) | LSL 1.500 mm full-thread engagement below horn face H | horn_hole_depth (100 %) | Measure the real horn hole depth (DB M15) before buying screws. At 3.5 deep, M3x6 engages fully but is marginal on bottoming (T03-depth35), so run each screw in by hand and check the head seats before torquing. (T03-depth35: MARGINAL, Cpk 2.46) |
| T03B | Axial stack — screw tip clear of the horn hole floor | **FAIL** | 0.00 % | -1.55 ± 0.02 | -1.015 … 0.215 (out) | LSL 0.200 mm | clamp_thickness (41 %) | Measure the horn hole depth (DB M15) before buying screws. At the CAD 2.5, M3x6 bottoms and M3x5 engages too little (T03-m3x5); at 3.5 deep M3x6 is marginal (T03B-depth35), so check each head seats by hand. (T03B-depth35: MARGINAL, Cpk 1.04) |
| T04 | Gripper datum B axis vs wrist-roll axis (concentricity) | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.25 ± 0.01 | 0.000 … 0.250 (in) | USL 0.300 mm radial offset | pilot_float (54 %) | none needed |
| T05 | Jaw centreline offset at the fingertips vs roll axis (X, closing axis) | **FAIL** | 99.36 % | 0.92 ± 0.01 | -1.330 … 1.944 (out) | LSL -0.193, USL 0.807 mm | deck_float (64 %) | Locate the deck on the spider with two bonded ISO 2338 h8 pins in reamed deck holes. That removes the deck screw float; T05-deckpegs includes translation clearance and rotation about the two-pin pattern. (T05-deckpegs: PASS, Cpk 1.35) |
| T06 | Gear centre distance a (pin A to pin B, rev A pinned layout) | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.04 ± 0.00 | 28.356 … 28.644 (in) | LSL 28.286, USL 28.714 mm | pinA_to_pinB_holes (93 %) | none needed |
| T07 | Gear backlash jt (circumferential, m 1.5 z 19, alpha 25) | **PASS** | 99.998 % (<63 ppm (2 of 100,000 samples; 95% upper bound) out) | 1.44 ± 0.02 | -0.078 … 0.578 (out) | LSL 0.050, USL 0.450 mm circumferential backlash | centre_distance (50 %) | none needed |
| T08 | Gear mesh axial alignment (gear A vs gear B mid-planes, Z) | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.49 ± 0.01 | -0.490 … 0.490 (in) | LSL -0.800, USL 0.800 mm | float_A (46 %) | none needed |
| T09 | Closure gap — first-contact angle of the jaw before calibration | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.37 ± 0.03 | -3.875 … 1.566 (in) | LSL -4.000, USL 4.000 deg | horn_trim (68 %) | none needed |
| T09F | Pad force at the jaw floor with the FSR trip failed (position-only cap, R15) | **FAIL** | 44.91 % | -0.04 ± 0.00 | 3.589 … 13.338 (out) | USL 8.000 N | theta_c (57 %) | APPLIED in the firmware (config.h JAW_FLOOR_BELOW_C0_DEG 4.9, JAW_MIN_DEG -10.2 backstop; controls.md 6.4): the floor is relative to the calibrated contact angle (theta_c0 - 4.9 deg) instead of the absolute -7.4 deg, so the contact spread drops out, and 4.9 deg holds the ruled 8 N on the stiff pair (T09F-relfloor8). Round 2's 6.2 deg floor (T09F-relfloor) held the superseded 10 N only; 5.0 deg is MARGINAL. The base stack is the firmware before round 2. (T09F-relfloor8: PASS, Cpk 1.46) |
| T09H | Largest hold force the firmware can reach on the softest finger (R14 under the R15 cap) | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.44 ± 0.01 | 4.183 … 6.858 (out) | LSL 5.000 N | k_pair (100 %) | Needed only once the dog slots open to 3.4 (rev B row 1): the 1.5 deg of dog lash moves the first contact toward the jaw floor, and the absolute floor then cuts the squeeze short (T09H falls to Cpk 0.99 in the combined rev B run). The floor relative to the calibrated contact angle (the T09F firmware request, APPLIED in config.h JAW_FLOOR_BELOW_C0_DEG 4.9 for the ruled 8 N; 6.2 in round 2): T09H-relfloor8. The 4.9 deg floor sits just past the 4.867 deg squeeze cap, so it is MARGINAL exactly as with 6.2 (T09H-relfloor); the softest pair at the cap is the limit, not the floor. (T09H-relfloor8: MARGINAL, Cpk 1.28) |
| T09P | Peak pad force when the FSR over-force trip fires (R15) | **FAIL** | 11.53 % | -0.52 ± 0.00 | 7.045 … 11.105 (out) | USL 8.000 N | squeeze_deg (86 %) | APPLIED in the firmware (config.h JAW_FLOOR_BELOW_C0_DEG 4.9; controls.md 6.4): the jaw floor theta_c0 - 4.9 deg is a position bound the squeeze cannot pass whether or not the trip fires, so the peak is the smaller of the trip peak and the force at the floor (T09P-floor49, same floor samples as T09F-relfloor8). No trip setting does it alone: the only trip that passes by itself, F_TRIP_N 5.5 with F_TRIP_MS 10 (T09P-trip55), sits inside the hold band and falsely trips grips, as F_TRIP_N 7.0 did (T09P-trip7, declined: 10 of 17 window grips, 34 of 1,000 drawn grips). (T09P-floor49: PASS, Cpk 1.46) |
| T09T | Close time to first contact after calibration (R19) | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 8.28 ± 0.10 | 0.463 … 0.551 (in) | USL 0.750 s | servo_angle_error (70 %) | No timing fix needed for first contact under the ruled 0.75 s limit. Retain the 6 deg slow zone: the 3 deg alternative (T09T-slow3) was declined after firmware simulation found excessive contact speed and early-contact force (controls.md 6.4). (T09T-slow3: PASS, Cpk 12.54) |
| T10 | Finger pad parallelism in the closing plane (root gap at tip contact) | **FAIL** | 96.42 % | 0.60 ± 0.00 | -0.805 … 2.091 (out) | LSL -1.000, USL 1.000 mm root gap when the tips first touch | pad_A_tilt (25 %) | Toe the rigid contact faces in by 0.44 deg (contact_gap / (2 r_c) = 1.0 / 130 rad, hinged at the pad-contact point, the same -0.44 deg touch the firmware sim uses) so they are parallel at first contact, not at theta = 0 (T10-toein). The 0.64 mm design V then goes away and the tolerance band is centred. (T10-toein: PASS, Cpk 1.67) |
| T10B | Fingertip out-of-plane mismatch (Z) from pin perpendicularity and knuckle wobble | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.95 ± 0.01 | -2.465 … 2.465 (out) | LSL -2.000, USL 2.000 mm | pinA_perpendicularity (29 %) | none needed |
| T11 | Radial keep-out, r 11.6 hub band (H-1..H+1) vs wrist-link lip r 12.6 | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.26 ± 0.01 | 0.200 … 1.150 (in) | LSL 0.100 mm radial clearance, worst angle over 320 deg roll | lip_radius (49 %) | none needed |
| T12 | Axial keep-out, gripper widens (r > 15) above the wrist-link lip top | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.85 ± 0.01 | 0.100 … 1.500 (in) | LSL 0.100 mm | widen_height_above_H (41 %) | none needed |
| T12B | Axial gap, gripper rim to servo-5 case top | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 14.04 ± 0.04 | 3.500 … 4.100 (in) | LSL 0.500 mm | rim_below_H (79 %) | none needed |
| T13 | Wrist-camera aim angle error (optional UVC bracket on the front-plate pad) | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.83 ± 0.01 | -3.033 … 3.033 (out) | LSL -3.000, USL 3.000 deg | lens_tilt (35 %) | none needed |
| T14 | Gripper servo body in cradle fit (20.4 pocket, DS3218MG 20.1 wide) | **FAIL** | 95.16 % | 0.55 ± 0.00 | -0.050 … 0.450 (out) | LSL 0.000, USL 0.300 mm clearance | pocket_width (69 %) | Locate the servo by its output boss (the T14B fix) so the cradle no longer has to locate it, then open the pocket to CAD 20.5 so it always drops in (T14-boss205). The listed DS3218MG width is 20.1, not the CAD 20.0. (T14-boss205: PASS, Cpk 1.68) |
| T14B | Dog coupling — servo shaft offset from pin A against the dog slot clearance | **FAIL** | 40.68 % | -0.06 ± 0.00 | -0.151 … 0.552 (out) | USL 0.000 mm tangential interference at a dog | shaft_in_case (38 %) | Locate the servo by its Ø9 output boss in a reamed bore in the 1.6 mm housing web at the case top (the boss is concentric with the shaft) and open the dog slots to 3.4 (lash about +/-1.5 deg [A: arithmetic here, (3.4 - 0.1 - 2.927) / (2 x 7 mm) rad]). With the web terms T14B-boss34 fails at Cpk 0.98. A 3.42 mm slot adds 0.010 mm half-clearance and restores about Cpk 1.05, but costs the closure window; the robust fix is a zero-lash coupling that takes offset, such as an Oldham disc. (T14B-boss34: FAIL, Cpk 0.96) |
| T15 | Knuckle end play at pin B (three standoffs, shims 0.85 per side) | **FAIL** | 89.67 % | 0.50 ± 0.01 | -0.710 … 1.310 (out) | LSL 0.050, USL 0.500 mm axial end play | standoff_top (41 %) | Pick the shims at assembly: measure the gap at each pin with feeler gauges and stack shims from a 0.05-step set so the end play lands at 0.3 +/- 0.05 (T15-shimselect). No CAD change; buy a shim assortment. (T15-shimselect: PASS, Cpk 4.35) |
| T16 | Pin axis tilt, centre-distance change across the 8 mm gear face | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.67 ± 0.01 | -0.067 … 0.067 (in) | LSL -0.070, USL 0.070 mm | knuckleA_tilt_on_pin (32 %) | none needed |
| T16B | Knuckle sleeve running fit on its pin (bronze bush bore vs m6 dowel) | **FAIL** | 68.93 % | 0.29 ± 0.00 | -0.008 … 0.014 (out) | LSL 0.000 mm diametral clearance | sleeve_bore (88 %) | Use an h8 pin (ISO 2338, 2.986-3.000) instead of the m6 dowel (T16B-h8pin). The bush maker recommends a running shaft of f7 or h7, and m6 is a press-fit size. Buy 3 x 6 bushes (no 3 x 5 bush was found in the catalogue searched [A]; confirm with the supplier) and open the knuckle bore to 6. The worst case of the fix is exactly 0.000 clearance (3.000 pin in a 3.000 bore), so check a few pins and pressed bores. (T16B-h8pin: PASS, Cpk 1.05) |
<!-- tolstack:verdicts:end -->

How to read the verdict: PASS = Cpk at least 1.33 (Monte Carlo accepted) or worst case inside the spec (worst-case accepted); MARGINAL = Cpk from 1.0 up to 1.33, or a worst-case-accepted stack whose worst case breaks the spec while Cpk is at least 1.0; FAIL = anything else (rule from `analysis/gripper/tolstack/results/SUMMARY.md` line 3 [D]).

The generated table uses the ruled limits (R15 8 N, R19 0.75 s). T09T passes at first contact (Cpk 8.28). The 0.5 s R19 limit is superseded; the 8 N force-cap scenarios below remain historical comparisons to the current firmware configuration. T09F-relfloor8 and T09P-floor49 pass at the ruled 8 N cap (both Cpk 1.46). See *Ruled R19 and historical limits*.

**Words used here.**
- **Stack** (tolerance stack): a chain of part dimensions that add up to one gap or fit. Each dimension varies a little from part to part.
- **Worst case (WC):** every dimension at its limit in the bad direction at once. If that still fits, the fit never fails.
- **RSS** (root sum square): a statistical estimate that assumes the errors partly cancel. Not valid for a non-linear stack (marked in the per-stack report).
- **Monte Carlo (MC):** 100,000 simulated builds with random dimensions.
- **Yield:** the share of simulated builds inside the spec.
- **Cpk:** how many "3 sigma" widths fit between the centre of the results and the nearest limit. Cpk 1.33 is about 63 out-of-spec parts per million; 1.0 is about 2,700.
- **Datum:** the surface or axis that a part is measured from and located by.
- **MMC** (maximum material condition): a hole at its smallest or a pin at its largest.
- **GD&T:** geometric dimensioning and tolerancing, the drawing symbols for position, flatness and the like.
- **BC:** bolt circle.
- **TCP:** the tool centre point the arm is programmed to.
- **FSR:** the force-sensing resistor on the pad.
- **Oldham coupling:** a three-piece shaft coupling whose middle disc slides, so it takes a parallel offset with no lash.
- **DB:** `docs/gripper/DESIGN-BASIS.md`.

Tags: **[S]** sourced (URL and retrieval date), **[D]** derived (a repo file or a tool run), **[A]** assumed (reason given). Every yield, Cpk and range below is [D] from `analysis/gripper/tolstack/results/SUMMARY.md` (100,000 samples per stack, seed 20260922) unless tagged otherwise. Units are mm unless stated. Per-stack reports are in `analysis/gripper/tolstack/results/<id>.md`.

## CAD rev B change list (complete; apply every row)

This list is complete on its own. A CAD author who makes every row, and does the gate on each row before releasing its dimension, gets the design that the combined table below proves. The tolerance basis is now re-based to the drawn rev B 10 mm sleeves, 15 mm plate-mid-plane pin span, 10.5 mm gear face, 12.5 mm plate gap, 6 mm finger-peg pitch, and bought deck-pin clearance and rotation. T16 changes from PASS to MARGINAL; T05 with pins remains MARGINAL, while T08, T10B, T15 and T16B keep their prior rev B verdicts. T14B changes from MARGINAL to FAIL; every other combined rev B check keeps its verdict. Earlier drafts proved each row alone; the combined run (`tolstack.py revb`, inputs in `analysis/gripper/tolstack/stacks/rev_b.yaml`) applies all of them at once, because the rows touch each other (pin clearance enters five stacks; the dog slot enters the closure window). Order follows how far rev A is from passing. "Yield" is the share of 100,000 simulated builds inside spec.

| # | Feature (`cad/gripper/params.json` key) | Dimension to draw | Stack or risk row behind it | Gate before the dimension is released |
|---|---|---|---|---|
| 1 | Case-top housing web: new reamed Ø9 servo-boss bore, position to the pin A hole within +/-0.10; `knuckle.dog_slot_w` | Ø9 bore (`servo.boss_d` 9.0 [D]); dog slots 3.14 -> 3.4 | T14B-boss34: 40.68 % -> 99.84 % yield (FAIL -> FAIL, Cpk 0.98). The added web and servo-axis tilt terms make it the only rev B failure. RISK F61 | Coupon items 8 and 10 (printed slot width, boss to shaft offset on 3 servos). If the measured values do not beat the assumed ones, switch to an Oldham disc (not modelled) |
| 2 | `knuckle.sleeve_od` 5.0 -> 6.0 (knuckle bore Ø6); bush; pins | Ø6 bore for a 3 x 6 sintered bronze bush (no 3 x 5 found [A]); pins h8, 2.986-3.000 mm [A limits], **graded to the pressed bush bore so each pair runs 0.000-0.020 mm** | T16B: 68.93 % -> 100 % (FAIL -> PASS, Cpk 1.05, worst case exactly 0.000). T16 pin tilt: the 10 mm sleeve, 15 mm plate-mid-plane span and 10.5 mm face make ungraded h8 (0.030) FAIL at Cpk 0.98; graded to 0.020 is MARGINAL at Cpk 1.30. (The T16B row of the combined run is the ungraded h8 batch, 0.000-0.030; grading only narrows it, so that row is conservative.) RISK F62, F02 | Pin gauge the pressed bores of 5 coupon bushes and micrometer the pins (coupon item 8). If pressed bores spread more than 0.016 mm, grading cannot reach 0.020 and T16 stays MARGINAL |
| 3 | `housing.cradle_pocket_clear` (cradle pocket 20.4) | **Pocket 20.5 mm for a 20.1 mm servo; 20.9 mm for a 20.5 mm servo** (pocket = largest measured case width + 0.40). Only together with row 1 | T14 with the boss locating the servo: 95.16 % -> 100 % (FAIL -> PASS, Cpk 1.68 for either servo). Without row 1 it fails: T14-cad205, 49.90 %. RISK F18 | **Measure case width (3 places) and shaft offset from the case side on three servos before the pocket is released.** Sources disagree three ways (20.0 mm `actuators.csv` A17 `dim_W_mm`; 20.1 mm servodatabase; 20.5 mm `actuators.csv` A17 `mount_pattern` text and `torque_and_actuator.md` row A17, from a Miuzei drawing). In `params.json` the pocket is `servo.body_x` plus twice `housing.cradle_pocket_clear`: set `body_x` to the measured width and the clearance so that the pocket equals width + 0.40 mm (0.20 per side) |
| 4 | Finger contact faces, both fingers | Toe in 0.44 deg (1.0 mm contact gap / (2 x 65 mm moment arm) [D]) | T10: 96.42 % -> 100 % (FAIL -> PASS, Cpk 1.67). RISK F15 | none |
| 5 | Deck-to-spider location (`housing.deck_screws` region) | Two bought ISO 2338 h8 3 × 6 pins bonded in the spider and slipping in reamed Ø3 holes; **plus** a one-time pinch-point TCP calibration | T05 with pins alone: MARGINAL, Cpk 1.31 in the combined run (99.36 % -> 99.988 %). With the TCP calibration (T05-tcpcal): PASS, Cpk 1.84. RISK F60 | Measure the pinch point once with a pin gauge on the arm and set the TCP. With this step the pegs add nothing to the number; keep them for repeat assembly |
| 6 | `wrist_mount.recess_d_cad` | 19.51 -> 19.56; accept up to 0.40 diametral clearance (was 0.30) | T02: MARGINAL -> PASS, Cpk 1.61; T04 stays PASS, Cpk 1.96. RISK F21 | Coupon item 2 sizes it from the measured hole |
| 7 | `wrist_mount.clearance_hole_cad` | 3.6 -> 3.7 | T01: MARGINAL -> PASS, Cpk 1.77. RISK F22 | none |
| 8 | `wrist_interface.horn_hole_depth` (2.5 in CAD) | No CAD change: measure the real depth (DB M15). M3x6 needs 3.75 mm or more; 3.5-3.7 MARGINAL; under 3.5, drill and re-tap to at least 3.75 | T03B: 0.00 % -> 100 % at 3.75 mm (PASS). The combined run **assumes** 3.75 mm. RISK F20 | Depth gauge in each horn hole before screws are bought |
| 9 | Housing: deck screws 1-3 (`housing.deck_screws`) | Deck screws 1 to 3 get driver access of at least 40 mm free length in the -Y driver direction: today screws 1 and 2 have 1.3 mm and screw 3 has 9.8 mm; screw 4 has 300 mm or more [D ASSEMBLY.md, Driver access; RISK F19] | RISK F19 (RPN 100). No stack: assembly finding | Dry-fit a driver in the CAD or a printed sample before release |
| 10 | Pins A and B in the plates | Add axial retention to each pin: a captured end or a CA bead at each end (no stack; the CAD author sizes it from the pull-out coupon) Only 2.5 mm of press fit per plate holds a pin today [D ASSEMBLY.md step 5 note] | RISK F06 (RPN 192). No stack | Pull-out coupon, coupon item 7 extended; fail if a pin moves under a 10 N hand pull [A] |
| 11 | Finger back flank (finger CAD, `docs/gripper/analysis/finger.md`) | Thicken the back-flank panel between root and first rib, or add a rib near the root, until the fold load clears the 9.426 N worst-case peak of T09P-trip7 with margin (fold today: 8.41 N with the nail, 8.88 N bare) | RISK F11, F12, F36; T09P-trip7 | Rerun the fold check; M10 loaded to 10 N. At R15 = 8 N the fold (8.41-8.88 N) sits only 0.4-0.9 N above the cap (F12), so the stiffer flank is still advisable. The thickness or rib size is not a tolerance-stack output: the finger owner sets it from the fold check |
| 12 | Stale `cad/gripper/params.json` values | Edit the `wrist_interface` block to the rev B values in the table under *Requests outside CAD* (F21, F23) | RISK F21, F23; T11, T12 (hub envelope) | none |

Firmware, assembly and purchasing items that the combined run needs are under *Requests outside CAD*.

**Why row 2 accepts line-to-line (0.000 mm) at the tight end.** The running-fit lower limit stays at 0.000 mm (`run_clear_min`). A bush and pin at exactly the same size still turn: the bush is oil-impregnated sintered bronze, and the standard H7/h6 sliding fit has zero minimum clearance [A: from the ISO 286 fit tables, not re-fetched here]. Zero clearance occurs only with the pressed bore at its H7 low limit and the pin at its h8 top limit at once (the worst case, not a typical pair), and the assembly check ("turns freely by hand", `ASSEMBLY.md` steps 13 and 15) rejects any pair that does not; swap the pin and regrade. The rock criterion in RISK F07 and F62 is 0.020 mm and applies to a graded pair (0.000 to 0.020 mm); an ungraded h8 pin can rock 0.030 mm, which is why the pins are graded.

### Combined rev B run

Every check, rerun with rows 1 to 8 and the firmware as shipped together at the written values (R15 = 8 N, R19 = 0.75 s): the relative jaw floor is in it; the trip and slow-zone requests were declined (`controls.md` 6.4), so T09P and T09T run as their base stacks and the requested variants are shown as alternatives. "Run as" names the variant used, or the base stack when the change is a constant. Rows marked "alternative, not counted" are shown for comparison only. Reproduce: `python analysis/gripper/tolstack/tolstack.py revb`; per-case JSON is in `analysis/gripper/tolstack/results/rev_b/`.

<!-- tolstack:revb:start -->
**Rev B, all changes at once, servo case 20.1 mm** (`revb`). 26 checks: 23 PASS, 2 MARGINAL, 1 FAIL, 0 UNDECIDED (gated worse) (1 independent). MARGINAL: T09H, T16. FAIL: T14B. Thinnest by Cpk: T14B, Cpk 0.98.

| Stack | Run as | Verdict | Yield (MC) | Cpk | Worst case | Spec | Rev A as drawn |
|---|---|---|---|---:|---|---|---|
| T01 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.77 ± 0.02 | -0.363 … -0.035 (in) | USL 0.000 mm radial interference | MARGINAL, Cpk 1.31 |
| T01H | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.02 ± 0.01 | -0.550 … -0.075 (in) | USL 0.000 mm radial interference | PASS, Cpk 2.02 |
| T02 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.61 ± 0.02 | 0.050 … 0.350 (in) | LSL 0.020, USL 0.400 mm diametral clearance | MARGINAL, Cpk 1.16 |
| T03 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.46 ± 0.01 | 1.885 … 2.915 (in) | LSL 1.500 mm full-thread engagement below horn face H | FAIL, Cpk 4.99 |
| T03B | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.68 ± 0.02 | 0.235 … 1.465 (in) | LSL 0.200 mm | FAIL, Cpk -1.55 |
| T04 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.96 ± 0.01 | 0.000 … 0.275 (in) | USL 0.300 mm radial offset | PASS, Cpk 2.25 |
| T05 | T05-tcpcal | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.84 ± 0.02 | -0.552 … 1.166 (out) | LSL -0.193, USL 0.807 mm | FAIL, Cpk 0.92 |
| T06 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.01 ± 0.01 | 28.350 … 28.650 (in) | LSL 28.286, USL 28.714 mm | PASS, Cpk 2.04 |
| T07 | base stack | **PASS** | 99.998 % (<63 ppm (2 of 100,000 samples; 95% upper bound) out) | 1.43 ± 0.01 | -0.083 … 0.583 (out) | LSL 0.050, USL 0.450 mm circumferential backlash | PASS, Cpk 1.44 |
| T08 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.49 ± 0.01 | -0.490 … 0.490 (in) | LSL -0.800, USL 0.800 mm | PASS, Cpk 2.49 |
| T09 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.49 ± 0.02 | -4.948 … 0.510 (out) | LSL -4.000, USL 4.000 deg | PASS, Cpk 2.37 |
| T09F | T09F-relfloor8 | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.46 ± 0.00 | 4.865 … 8.031 (out) | USL 8.000 N | FAIL, Cpk -0.04 |
| T09H | T09H-relfloor8 | **MARGINAL** | 99.996 % (<92 ppm (4 of 100,000 samples; 95% upper bound) out) | 1.28 ± 0.01 | 4.826 … 7.985 (out) | LSL 5.000 N | PASS, Cpk 2.44 |
| T09P | T09P-floor49 | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.46 ± 0.00 | 4.865 … 8.031 (out) | USL 8.000 N | FAIL, Cpk -0.52 |
| T09T | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 8.28 ± 0.10 | 0.463 … 0.551 (in) | USL 0.750 s | PASS, Cpk 8.28 |
| T10 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.67 ± 0.01 | -1.452 … 1.452 (out) | LSL -1.000, USL 1.000 mm root gap when the tips first touch | FAIL, Cpk 0.60 |
| T10B | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.05 ± 0.01 | -2.397 … 2.397 (out) | LSL -2.000, USL 2.000 mm | PASS, Cpk 1.95 |
| T11 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.17 ± 0.03 | 0.175 … 1.150 (in) | LSL 0.100 mm radial clearance, worst angle over 320 deg roll | PASS, Cpk 2.26 |
| T12 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.85 ± 0.01 | 0.100 … 1.500 (in) | LSL 0.100 mm | PASS, Cpk 1.85 |
| T12B | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 14.04 ± 0.04 | 3.500 … 4.100 (in) | LSL 0.500 mm | PASS, Cpk 14.04 |
| T13 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.83 ± 0.01 | -3.033 … 3.033 (out) | LSL -3.000, USL 3.000 deg | PASS, Cpk 1.83 |
| T14 | T14-boss | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.68 ± 0.02 | 0.050 … 0.550 (in) | LSL 0.000 mm clearance | FAIL, Cpk 0.55 |
| T14B | T14B-boss34 | **FAIL** | 99.84 % | 0.98 ± 0.00 | -0.287 … 0.238 (out) | USL 0.000 mm tangential interference at a dog | FAIL, Cpk -0.06 |
| T15 | T15-shimselect | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 4.35 ± 0.05 | 0.245 … 0.355 (in) | LSL 0.050, USL 0.500 mm axial end play | FAIL, Cpk 0.50 |
| T16 | base stack | **MARGINAL** | 99.998 % (<63 ppm (2 of 100,000 samples; 95% upper bound) out) | 1.30 ± 0.01 | -0.084 … 0.084 (out) | LSL -0.070, USL 0.070 mm | PASS, Cpk 1.67 |
| T16B | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.05 ± 0.00 | -0.000 … 0.030 (in) | LSL 0.000 mm diametral clearance | FAIL, Cpk 0.29 |
| T05 | T05-deckpegs (alternative, not counted) | **MARGINAL** | 99.988 % (120 ppm out) | 1.31 ± 0.01 | -1.073 … 1.687 (out) | LSL -0.193, USL 0.807 mm | FAIL, Cpk 0.92 |
| T09H | T09H (alternative, not counted) | **FAIL** | 99.85 % | 0.99 ± 0.00 | 2.910 … 6.858 (out) | LSL 5.000 N | PASS, Cpk 2.44 |
| T09P | T09P-trip7 (alternative, not counted) | **FAIL** | 65.44 % | 0.18 ± 0.00 | 6.364 … 9.426 (out) | USL 8.000 N | FAIL, Cpk -0.52 |
| T09T | T09T-slow3 (alternative, not counted) | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 12.54 ± 0.15 | 0.338 … 0.426 (in) | USL 0.750 s | PASS, Cpk 8.28 |

**Rev B, A17 servo case 20.5 mm, pocket opened to 20.9** (`revb_servo205`). 26 checks: 23 PASS, 2 MARGINAL, 1 FAIL, 0 UNDECIDED (gated worse) (1 independent). MARGINAL: T09H, T16. FAIL: T14B. Thinnest by Cpk: T14B, Cpk 0.98. Only the checks that differ from the `revb` run are listed.

Every check is identical to that run.

**Rev B with ungraded h8 pins (pin clearance 0.000-0.030)** (`revb_ungraded`). 26 checks: 23 PASS, 1 MARGINAL, 2 FAIL, 0 UNDECIDED (gated worse) (2 independent). MARGINAL: T09H. FAIL: T14B, T16. Thinnest by Cpk: T14B, Cpk 0.97. Only the checks that differ from the `revb` run are listed.

| Stack | Run as | Verdict | Yield (MC) | Cpk | Worst case | Spec | Rev A as drawn |
|---|---|---|---|---:|---|---|---|
| T05 | T05-tcpcal | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.83 ± 0.01 | -0.569 … 1.183 (out) | LSL -0.193, USL 0.807 mm | FAIL, Cpk 0.92 |
| T06 | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.94 ± 0.02 | 28.340 … 28.660 (in) | LSL 28.286, USL 28.714 mm | PASS, Cpk 2.04 |
| T07 | base stack | **PASS** | 99.998 % (<63 ppm (2 of 100,000 samples; 95% upper bound) out) | 1.41 ± 0.02 | -0.092 … 0.592 (out) | LSL 0.050, USL 0.450 mm circumferential backlash | PASS, Cpk 1.44 |
| T10B | base stack | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.92 ± 0.01 | -2.537 … 2.537 (out) | LSL -2.000, USL 2.000 mm | PASS, Cpk 1.95 |
| T14B | T14B-boss34 | **FAIL** | 99.82 % | 0.97 ± 0.01 | -0.286 … 0.243 (out) | USL 0.000 mm tangential interference at a dog | FAIL, Cpk -0.06 |
| T16 | base stack | **FAIL** | 99.65 % | 0.98 ± 0.01 | -0.105 … 0.105 (out) | LSL -0.070, USL 0.070 mm | PASS, Cpk 1.67 |

**Rev B, hot seat (PETG relaxed)** (`revb_hot`). 26 checks: 22 PASS, 3 MARGINAL, 1 FAIL, 0 UNDECIDED (gated worse) (1 independent). MARGINAL: T09H, T14, T16. FAIL: T14B. Thinnest by Cpk: T14B, Cpk 0.66. Only the checks that differ from the `revb` run are listed.

| Stack | Run as | Verdict | Yield (MC) | Cpk | Worst case | Spec | Rev A as drawn |
|---|---|---|---|---:|---|---|---|
| T14 | T14-boss | **MARGINAL** | 99.996 % (<92 ppm (4 of 100,000 samples; 95% upper bound) out) | 1.27 ± 0.01 | -0.050 … 0.650 (out) | LSL 0.000 mm clearance | FAIL, Cpk 0.55 |
| T14B | T14B-boss34 | **FAIL** | 97.64 % | 0.66 ± 0.01 | -0.277 … 0.388 (out) | USL 0.000 mm tangential interference at a dog | FAIL, Cpk -0.06 |
| T15 | T15-shimselect | **PASS** | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 2.43 ± 0.01 | 0.195 … 0.405 (in) | LSL 0.050, USL 0.500 mm axial end play | FAIL, Cpk 0.50 |

**CAD rev A as drawn, hot seat (PETG relaxed)** (`drawn_hot`). 26 checks: 14 PASS, 2 MARGINAL, 10 FAIL, 0 UNDECIDED (gated worse) (9 independent). MARGINAL: T01, T02. FAIL: T03, T03B, T05, T09F, T09P, T10, T14, T14B, T15, T16B. Thinnest by Cpk: T03B, Cpk -1.55. Only the checks that differ from the rev A as drawn run are listed.

| Stack | Run as | Verdict | Yield (MC) | Cpk | Worst case | Spec | Rev A as drawn |
|---|---|---|---|---:|---|---|---|
| T14 | base stack | **FAIL** | 87.26 % | 0.43 ± 0.00 | -0.150 … 0.550 (out) | LSL 0.000, USL 0.300 mm clearance | FAIL, Cpk 0.55 |
| T14B | base stack | **FAIL** | 35.74 % | -0.09 ± 0.00 | -0.115 … 0.702 (out) | USL 0.000 mm tangential interference at a dog | FAIL, Cpk -0.06 |
| T15 | base stack | **FAIL** | 88.94 % | 0.48 ± 0.00 | -0.760 … 1.360 (out) | LSL 0.050, USL 0.500 mm axial end play | FAIL, Cpk 0.50 |
<!-- tolstack:revb:end -->

What the combined run found that one-fix-at-a-time proofs missed [D, the cases above]:
- **Ungraded h8 pins break T16.** `pin_clear` rises from 0.014 to 0.030 mm. T16 drops from MARGINAL (Cpk 1.30) to FAIL (Cpk 0.98), T10B from 2.05 to 1.92, and T14B and T07 thin as well (case `revb_ungraded`). Grading the pins to 0.020 mm brings T16 back to MARGINAL, Cpk 1.30, in the combined run. On rev A alone, at 0.020 the pin clearance sweep gives T16 Cpk 1.35 (`results/sweep_T16_pin_clear.md`: PASS up to 0.020, MARGINAL from 0.022).
- **Dog slots at 3.4 add 1.5 deg of lash to the closure window.** T09 (first contact inside the +/-4 deg calibration window) drops from Cpk 2.37 to 1.49, and T09H (the softest finger reaching 5 N under the 10 N cap) drops from PASS, Cpk 2.44, to FAIL, Cpk 0.99 with the absolute jaw floor (the "alternative, not counted" row). The relative floor (already needed for T09F, now in the firmware) lifts it to T09H-relfloor, MARGINAL, Cpk 1.28: with the floor out of the way the 4.867° squeeze cap on the softest pair is the limit (it was Cpk 1.58 at the old 5.137° cap). Wider slots help T14B but cost T09: slot 3.5 gives T14B Cpk 1.29 and T09 Cpk 1.15 (MARGINAL); 3.6 gives T14B 1.61 and T09 0.80 (FAIL) (`results/sweep_T14B_dog_slot.md`, `results/sweep_T09_dog_slot.md`).
- **Deck pins alone leave T05 MARGINAL** (Cpk 1.31), because the larger pin clearance of row 2 enters the pin float terms and, through the centre distance and backlash (T06, T07), the pinch-point shift. The one-time TCP calibration passes it (Cpk 1.84).

**Rev B does not pass as a whole: T14B FAILS; T09H and T16 stay MARGINAL. T09T passes the ruled R19 limit.** The thinnest mechanical check under the combined set is T14B (dog coupling), Cpk 0.98, 99.84 % yield, worst case -0.287 ... 0.238 mm against 0 mm interference. No slot width up to 3.8 mm lifts it to PASS: at 3.8 mm T14B Cpk 2.27 still has a worst case 0.044 mm into interference, and T09 Cpk 0.12 fails (`results/sweep_T14B_dog_slot.md`, `results/sweep_T09_dog_slot.md`). The measurement that decides it is coupon items 8 and 10 (printed slot width, boss to shaft offset): if they come in tighter than the assumed 0.15 mm slot scatter and 0.05 mm boss-to-shaft term, T14B clears; if not, use an Oldham disc. The next thinnest are T16B (Cpk 1.05, worst-case accepted, exactly 0.000 clearance at the extreme) and T16 (MARGINAL, Cpk 1.30).

Rev B no longer "leaves the gears unchanged". Row 2 changes the knuckle bore and the pins, which enter the gear centre distance (T06 Cpk 2.04 -> 2.01), the backlash (T07 1.44 -> 1.43) and the pin tilt (T16 1.67 -> 1.35); row 1 moves T09 and T09H as above.

### Servo case width: 20.1 mm or 20.5 mm

**The sources conflict three ways.** The stacks use a 20.1 mm case (servodatabase.com listing, `servo_body_w` in `basis.yaml` [S, low-medium confidence]). `docs/gripper/research/actuators.csv` row A17 gives `dim_W_mm` 20 but its `mount_pattern` text and row A17 of `docs/gripper/analysis/torque_and_actuator.md` say 40.0 x 20.5 x 40.5 (a Miuzei drawing and the SpeedyFPV listing) [S]. `cad/gripper/params.json` draws 20.0 mm. None states a tolerance. The 20.1 and 20.5 widths are both run (20.0 is covered by the 20.1 case); only a caliper can settle it.

| Servo case | Layout | Pocket | Result (stack) |
|---|---|---|---|
| 20.1 mm | rev A, cradle locates the servo | 20.4 | FAIL, 95.16 % yield, Cpk 0.55 (T14) |
| 20.5 mm | rev A, cradle locates the servo | 20.4 | FAIL, the servo does not fit: 0.03 % yield (T14-w205) |
| 20.5 mm | cradle locates the servo, pocket opened | 20.9 | FAIL, 49.90 % yield: the float exceeds 0.30 (T14-w205p209); dog coupling 33.89 % yield, Cpk -0.11 (T14B-w205) |
| 20.1 mm | rev B, boss locates the servo | **20.5** | PASS, 100 % yield, Cpk 1.68 (T14-boss, case `revb`) |
| 20.5 mm | rev B, boss locates the servo | **20.9** | PASS, 100 % yield, Cpk 1.68 (T14-boss, case `revb_servo205`) |

**Pocket dimension for each case:** 20.5 mm for a 20.1 mm servo, 20.9 mm for a 20.5 mm servo; in general the largest measured case width plus 0.40 mm (`results/sweep_T14_pocket_servo201.md` and `sweep_T14_pocket_servo205.md`: PASS from width + 0.35 mm, MARGINAL at width + 0.30 mm). The servo width does not enter T14B once the boss locates the servo. With the boss locating, a looser pocket costs nothing in the tolerance stacks; the thermal note models the pocket air gap and the ear seat, so check it again if the pocket grows (`docs/gripper/analysis/thermal.md`).

**Gate: measure before the pocket is released.** Measure the case width in three places and the shaft offset from the case side on three servos (coupon item 5 and the *Also measure* list). Do not release `housing.cradle_pocket_clear` or `servo.body_x` until all three are recorded; take the largest width. Rev B row 3 depends on this.

## What a hobby printer can and cannot do

Bottom line: most fits print fine on a calibrated hobby FDM printer (0.4 mm nozzle, 0.2 mm layers). Holes that must be a running or press fit (pins, bushes, servo boss) are reamed or bought. End play is shimmed at assembly. Two features (recess, cradle pocket) get a coupon print first. Values are mm; rev A is the CAD as drawn (`basis.yaml` [D]) and rev B is the change list above.

| Fit / feature | Rev A / rev B value | Do this | Proved by |
|---|---|---|---|
| Mount holes 4 x M3 | 3.6 / 3.7 | As printed | T01, T01-cad37 |
| Head counterbores | 6.5 / 6.5 | As printed | T01H |
| Pilot recess | 19.51 / 19.56 | Print a coupon first and size the recess from the measured hole; the scatter of a printed 20 mm hole sets the result | T02, T02-relax40 |
| Horn hole depth (on the arm, not printed) | 2.5 in CAD; measure | Inspect (DB M15). M3x6 needs 3.75 or more to PASS (3.5 to 3.7 MARGINAL); shallower than 3.5, drill and re-tap | T03B, `results/sweep_T03B_horn_hole_depth.md` |
| Plate pin holes (pin A, pin B) | 2.9 printed, reamed to the pin | Ream through the stacked plates; printed holes alone fail | T16, T16-noream |
| Servo boss bore | none / Ø9 | Ream | T14B-boss34 |
| Knuckle bush bore | 5.0 / 6.0 | Ream, or press the bush in; the pressed bore lands between H7 and F7 | T16B |
| Pins (knuckle shafts) | m6 dowel / h8 pin 2.986-3.000, graded to the bush bore (0.000-0.020 clearance) | Buy a precise part and grade it against the pressed bore; ungraded, T16 is MARGINAL | T16B-h8pin, T16, case `revb_ungraded` |
| Dog coupling slot | 3.14 / 3.4 | Prints, but fails: slot 3.4 gives T14B Cpk 0.96 in the sweep (0.98 with every rev B change, `results/rev_b/REVB.md`), and 3.4 costs the closure window; consider an Oldham disc (buy) | T14B-boss34, T09, `results/sweep_T14B_dog_slot.md` |
| Knuckle end play | shims 0.85 per side / picked at assembly | Shim at assembly from a 0.05 step set | T15, T15-shimselect |
| Servo cradle pocket | 20.4 / 20.5 for a 20.1 mm servo, 20.9 for a 20.5 mm servo | Measure 3 servos first; print a coupon; once the boss locates the servo, only drop-in matters | T14, T14-boss, `results/sweep_T14_pocket_servo20*.md` |
| Deck-to-spider location | 4 screws in Ø3.6 / plus 2 pegs in reamed Ø3 holes | Ream the deck peg holes; print the pegs | T05, T05-deckpegs |
| Gear centre distance and backlash | 28.5 / 28.5 | As printed, on line-reamed pin holes (the pin clearance of rev B enters both) | T06, T07 |
| Gear mesh Z alignment | unchanged | As printed | T08 |
| Finger contact-face toe-in | 0 deg / 0.44 deg | As printed (a CAD angle) | T10, T10-toein |
| Radial and axial keep-outs | unchanged | As printed | T11, T12, T12B |
| Camera bracket locating tab | unchanged | As printed; without the tab it fails (T13-notab, 68.01 %) | T13 |

## Requests outside CAD

**Firmware** (`firmware/gripper/config.h`; evaluated against the ruled R15 = 8 N and R19 = 0.75 s; historical firmware requests are compared below). Each request was run through the compiled firmware before it was taken (`analysis/gripper/controls/firmware_requests.py`, `controls.md` 6.4: the R12 stiffness window, 1,000 drawn grips, 300 at `G 7`, 300 with early contact):
- **Declined:** `F_TRIP_N` 8.0 -> 7.0 N with `F_TRIP_MS` 20 -> 10 ms (T09P-trip7 would lift T09P from 85.98 % to 100 %). The firmware regulates the FSR reading 1 N above the setpoint and settles up to 0.6 N above that, so a 7 N trip sits inside the hold band: it falsely tripped 10 of 17 grips across the R12 window (every finger from 1.2 N/mm up), 16 of 1,000 drawn `G 5` grips and 9 of 300 `G 7` grips (none at 8 N / 20 ms), and it did not lower the early-contact peaks it was for (8.20 N drawn, 9.62 N on the linear stiff bound at 10° early, both unchanged), because the jaw's lag sets them before any trip acts. 7.5 N / 10 ms still falsely trips 3 of 300 `G 7` grips; 8.0 N / 10 ms trips nothing and changes no peak. Since the R15 8 N ruling the trip is 7.75 N / 20 ms and T09P passes through the 4.9 deg floor instead (T09P-floor49; RISK F57, F58).
- **Declined:** `JAW_SLOW_ZONE_DEG` 6 -> 3 deg (T09T-slow3 also passes the ruled timing limit but is unnecessary). In the firmware it brings first contact within 0.5 s in every grip (55.3 % now) and 4.5 N within 0.5 s in 41.4 % (0 % now), but the jaw meets the cloth at up to 41 °/s in the window (62 °/s drawn; R19 asks for the last 3° at 20 °/s; now 21 °/s), and an 8° early contact on the stiff finger peaks at 10.48 N on the linear bound, past the 10 N cap (now 9.62 N at worst). Zones of 4° and 5° also pass 10 N at 10° early (12.03 N, 10.66 N). The current 6° zone passes the ruled 0.75 s first-contact limit (T09T Cpk 8.28); 0.5 s is superseded (RISK F33).
- **Applied:** the jaw floor is relative to the calibrated contact angle, floor = theta_c0 - 4.9 deg since 2026-10-16 (theta_c0 - 6.2 deg from round 2, the absolute -7.4 deg before; `JAW_FLOOR_BELOW_C0_DEG` 4.9; `JAW_MIN_DEG` -10.2 stays as the backstop, the floor of the lowest calibrated contact, inside DB R18's -11). Against the superseded 10 N this lifted the force-at-floor check from 99.63 % to 100 % within spec; against the ruled 8 N the 6.2 deg floor is FAIL (T09F-relfloor, Cpk -0.03), and the 4.9 deg floor now shipped PASSES (T09F-relfloor8, Cpk 1.46; 5.0 deg is MARGINAL at Cpk 1.32) and bounds the trip peak (T09P-floor49 PASS, Cpk 1.46), with no new false trip in the simulation (`controls.md` 6.4). With dog slots at 3.4 (rev B row 1) it also keeps T09H from failing: with the absolute floor T09H falls to Cpk 0.99; T09H-relfloor is MARGINAL, Cpk 1.28, now that the squeeze cap is 4.867°. It changed no simulated grip (every metric equal to the absolute floor); the host test `jaw floor relative to theta_c0` fails without it.

**Assembly:**
- Line-ream the pin holes through the stacked plates in one pass. Skipping it (T16-noream) fails T16: 96.83 % yield, Cpk 0.71.
- Pick shims at assembly: measure the gap at each pin with feeler gauges and stack shims from a 0.05 mm step set to land end play at 0.3 +/- 0.05 mm. T15 89.67 % -> 100 % (T15-shimselect). No CAD change.
- Ream the Ø9 servo-boss bore (row 1) and the deck peg holes (row 5).
- Grade the h8 pins to the pressed bush bores (row 2): pin-gauge each pressed bore, micrometer each pin, and pair them so the clearance is 0.000 to 0.020 mm. Ungraded, T16 falls to MARGINAL.
- One-time pinch-point TCP calibration after assembly (row 5): pegs alone leave T05 MARGINAL in the combined run.
- Measure the horn hole depth (row 8) before buying screws: M3x6 needs at least 3.75 mm (PASS), and 3.5 to 3.7 mm is MARGINAL [D sweep]. Run each M3 screw in by hand and check the head seats before torquing.

**Purchasing:** h8 pins 2.986-3.000 mm (ISO 2338; limits are [A] in `basis.yaml`, confirm on the supplier sheet), several more than needed so they can be graded, with a micrometer and a pin-gauge set; 3 x 6 sintered bronze bushes; a 0.05 mm step shim assortment; M3 screws sized to the measured horn hole depth; an Oldham disc coupling only if row 1 goes that way.

**Electrical:** none. The tolerance stacks ask for no wiring or board change. T09P assumes the FSR is span-calibrated against a known weight to within 10 % of reading (`fsr_err` [A], reason in the basis table below); that is a bench step.

**`cad/gripper/params.json` values that disagree with rev A** (not edited; the file's `wrist_mount` block already carries the rev A values, the older `wrist_interface` block does not):

| Key | Value in params.json | Rev A value [D `basis.yaml`] |
|---|---|---|
| `wrist_interface.counterbore_d` | 6.0 mm | 6.5 mm (`wrist_mount.counterbore_d`) |
| `wrist_interface.pilot_recess_d_cad_fdm` | 19.45 mm | 19.51 mm rev A, 19.56 mm rev B (row 6), with a 0.3 mm x 45 deg mouth chamfer (`recess_d_cad`) |
| `wrist_interface.hub_od_max` | 24.0 mm | 23.2 mm (hub r 11.6 mm, `r_keepout_1`) |
| `wrist_interface.keepout[0].r_max` | 12.0 mm (H-1 to H+1) | 11.6 mm |
| `wrist_interface.keepout[1]` | r 15.0 mm from H+1 to H+4.5 | r 14.6 mm from H+1 to H+5.0; full widening (r above 15 mm) only above H+5.0 (`r_keepout_2`, `widen_z_above_H`) |
| `servo.body_x` | 20.0 mm | 20.1 mm (servodatabase) or 20.5 mm (`actuators.csv` A17): the measured width of 3 servos; do not release before that |
| `grip.fsr.overforce_trip_N` | 8.0 N | 8.0 N: the 7.0 N request was declined (firmware row above), so params.json agrees with `config.h` |

## Ruled R19 and historical limits

DESIGN-BASIS R19 now requires full close within 0.75 s (Douglas ruling, 2026-10-12; 0.5 s is superseded). T09T measures first pad contact, so its passing result does not settle whether “full close” means first contact, 4.5 N, or HOLD; RISK F34 tracks that event definition. The table keeps the superseded 0.5 s timing and earlier R15 force-cap alternatives for comparison. Yield is the share of 100,000 builds inside spec.

| Check | What it tests | Historical limit | Ruled limit or comparison | Firmware option that passes |
|---|---|---|---|---|
| T09T (R19) | Close time **to first pad contact** (not HOLD) | Superseded 0.5 s: FAIL, 24.04 %, Cpk −0.24 | Ruled 0.75 s: PASS, 100 %, Cpk 8.28. HOLD misses 0.75 s in two of four stiffness cases (0.718, 0.768, 0.738, 0.853 s); 4.5 N passes in all four (0.589 to 0.643 s) [D `analysis/gripper/firmware_sim/results/fw_sim.json`; `docs/gripper/RISK.md` F34] | No timing change needed for first contact. The 3° slow zone passes the old timing stack but was declined for contact-speed and early-force reasons (*Requests outside CAD*) |
| T09P (R15) | Peak pad force when the FSR over-force trip fires | 10 N: FAIL, 85.98 % | 8 N: FAIL, 11.53 % with the 7.75 N trip alone (T09P-r15p8) | 10 N: `F_TRIP_N` 7.0, `F_TRIP_MS` 10 passes the stack (T09P-trip7) but was declined by the firmware simulation (false trips in normal holds, no change to the early-contact peaks). 8 N: the floor theta_c0 - 4.9 deg bounds the peak, PASS 100 %, Cpk 1.46 (T09P-floor49), **applied 2026-10-16**; `F_TRIP_N` 5.5, `F_TRIP_MS` 10 also passes the stack (T09P-trip55) but false-trips normal holds (see the conflict below) |
| T09F (R15) | Pad force at the jaw floor with the trip failed (position-only cap) | 10 N: FAIL, 99.63 % | 8 N: FAIL, 44.91 % (T09F-r15p8) | 10 N: floor = theta_c0 - 6.2 deg, PASS 100 % (T09F-relfloor), applied in round 2. 8 N: floor = theta_c0 - 4.9 deg, PASS 100 %, Cpk 1.46 (T09F-relfloor8), **applied 2026-10-16** |
| T09H (R14 under R15) | Softest finger can still reach the 5 N hold (R14) inside the squeeze cap | 10 N: PASS, 100 %, Cpk 2.44 (MARGINAL, Cpk 1.28, with the rev B dog slots: T09H-relfloor) | 8 N with `F_CAP_N` compiled at 8: FAIL, 39.50 % (T09H-r15p8) | 10 N: none needed. 8 N: keep `F_CAP_N` 10 and enforce 8 N with the 4.9 deg floor: MARGINAL, Cpk 1.28 (T09H-relfloor8, unchanged from T09H-relfloor), **applied 2026-10-16** |

**The conflict.** Under an 8 N cap the squeeze cap shrinks to 3.785 deg (`u_max_8_deg`: the firmware compiled with `F_CAP_N` 8, keeping the 0.5 N `F_CAP_MARGIN_N`; `analysis/gripper/controls/results/firmware_requests_stdout.txt`, row cap8). The softest finger (pair stiffness 0.523 N/mm [D `k_pair_min`]) then reaches only 4.183 N at its worst case, below the R14 hold of 5.0 N (`F_target`, T09H-r15p8: 39.50 % of builds reach 5 N). The firmware simulation agrees: with the 8 N cap, fingers up to 1.05 N/mm hold under 5 N across the R12 window (4.14 N at 0.88 N/mm), and R14 is met in 9.0 % of drawn grips against 46.7 % at 10 N. R15 at 8 N and R14 at 5 N cannot both be met on every finger with this controller. The one trip setting that passes T09P at 8 N, 5.5 N (T09P-trip55), sits below the normal hold: the hold setpoint is 5.0 N (`F_target`, `basis.yaml`), the controller settles anywhere in 5.0 to 5.6 N (`CTRL_I_DB_HI_N` 0.60 N), and the on-target band extends another 0.5 N (`F_BAND_N`) to 6.1 N (`firmware/gripper/config.h` lines 142 and 159 [D]; those two constants live in `config.h`, not in `basis.yaml`). A 5.5 N trip would fire during an ordinary hold.

The R15 alternatives below are historical; DESIGN-BASIS records the 8 N ruling. For R19, the remaining question is which close event the 0.75 s rule ends on:
- **R15 at 10 N:** R14 and R15 both stay satisfiable in the stacks except T09P, which has no firmware fix: the stack's trip fix was declined in the firmware simulation, and there the peaks that matter come from early contact, which only a slower approach lowers (`controls.md` 4.4). The relative floor is in (T09F PASS). Pads can see up to 10 N, and the finger's back flank folds at 8.4 to 8.9 N (`docs/gripper/analysis/finger.md` 5.2 [D]): an 8 to 10° early contact on a stiff finger peaks at 8.20 to 9.62 N on the linear bound. So 10 N also needs the stiffer finger (`docs/gripper/RISK.md` F11), or the fold limit, not R15, is the real cap.
- **R15 at 8 N:** a gentler cap. Cost: either R14 drops below 5 N on the softer fingers (39.50 % of builds reach 5 N in T09H-r15p8; 9.0 % of drawn grips meet R14 in the firmware simulation), or the cap and trip are set so tightly that normal holds trip it. The 8 N cap does not lower the 8 to 10° early-contact peaks either (8.20 and 9.62 N, unchanged). Needs a new R14 value or a stiffer-finger rule before it can pass. *2026-10-16 (T09):* the firmware takes the third route instead: `F_CAP_N` stays 10 (squeeze cap 4.867°) and the jaw floor θ_c0 − 4.9° enforces 8 N in the stacks (T09F-relfloor8 and T09P-floor49 PASS, Cpk 1.46; T09H MARGINAL, Cpk 1.28, unchanged), with no new false trip in the firmware simulation (`controls.md` 6.4).
- **Superseded R19 at 0.5 s, ending at first contact:** T09T FAILS (24.04 %; the stack's contact times are now the firmware simulation's 0.503 to 0.511 s across the R12 window, `fw_sim.json`, which settles the earlier 486-498 ms against 0.503-0.510 s question). The slow-zone cut that would pass it was declined (jaw speed at contact, early-contact peaks past 10 N). Meeting 0.5 s needs a faster actuator or a slower-approach trade that this firmware cannot make (`controls.md` O1).
- **Ruled R19 at 0.75 s, ending at first contact:** no firmware change; T09T passes with the current slow zone. Ending at 4.5 N also passes; ending at hold force misses for two of four stiffnesses (see the table row).

## Heat, and what these stacks do not model

Every stack above is cold, dry and new: room temperature, no creep, parts at their printed size. The thermal note (`docs/gripper/analysis/thermal.md`) says that is optimistic for the servo mount. In the 5 N hold the PETG under the servo ears reaches 67.5 C on the pessimistic datasheet reading (Fit A, PETG glass transition 68 C) or 48.9 C on the optimistic one (Fit B). The four ear screws squeeze bare PETG, and the clamp left after a semester is about 69 % at 25 C, 30 % at the Fit B mount temperature and 6 % at the Fit A temperature [D thermal.md 0, 3]. A servo that shifts in its seat moves the gear centre distance and the dog coupling, the two things the stacks hold tight.

**Hot scenario [A].** `tolstack.py revb` reruns the stacks with the servo's float and shaft position terms widened, in cases `revb_hot` and `drawn_hot` (`stacks/rev_b.yaml`, constants `hot_*` in `basis.yaml`):

| Term | Cold | Hot | Reason for the amount |
|---|---|---|---|
| Servo shift in its seat (T14, T14B), uniform | 0 | +/-0.10 mm | Stand-in: the radial float of an M3 in its ear hole, the order of the cold float. Not measured |
| Servo shaft position (T14B), normal 3 sigma | 0 extra | +/-0.05 mm extra | A quarter of the +/-0.20 mm cold band. Judgement |
| Knuckle end play at pin B (T15), uniform | 0 | +/-0.05 mm | Warm PETG plates against PA6-CF knuckles. The expansion coefficients were not sourced, so this is a stand-in, not a calculation |

Replace the three amounts with the clamped-coupon creep test and the thermocouple in the cradle seat that thermal.md section 6 describes. The hot terms apply to the boss-located design too, which is conservative: if the Ø9 boss bore holds the servo, the ear seat can relax without moving it.

**Result.** Rev B hot: T14 falls from PASS (Cpk 1.68) to MARGINAL (Cpk 1.27), T14B from FAIL (Cpk 0.98) to FAIL (Cpk 0.66, 97.64 % yield), and T15 stays PASS (Cpk 2.43) (rows `revb_hot` in the combined run above). Rev A as drawn is already failing and only gets worse. So rev B does not hold hot unless the seat does: put the metal compression limiters of thermal.md C1 in the four ear-screw holes, and treat T14B as unproven until the seat creep is measured. RISK F63 carries this.

**Not modelled** (each can move a stack and none is in a number above):
- Temperature and moisture effects on size: thermal expansion of the PETG plates, PA6-CF knuckles and gears, TPU fingers and the aluminium servo case; moisture swell of PA6-CF gears and knuckles (`gears.md` takes a 0.85 moisture knockdown on strength, not on size, and plans a weighing test, M23). Swell changes the centre distance, the backlash and the sleeve fit (T06, T07, T16, T16B).
- Creep and relaxation of any plastic over time: the screw preload (only the hot stand-in above), the pressed pins and bushes in their plates, the TPU finger under a 25.5 s hold.
- FSR and servo drift with temperature, and wear (the stacks start from new parts).
- Lint, thread or debris in the gear mesh (RISK F66) and dog-screw loosening (RISK F67); moisture swell is RISK F65; pinch and the open mesh are RISK F64.

## Process basis

Process band per feature type, from `analysis/gripper/tolstack/stacks/basis.yaml` [D]. Every band is plus or minus 3 sigma, so sigma = band / 3 [D]. Retrieval date for every URL is 2026-10-11 as written in `basis.yaml`.

| Feature type | Band (mm) | Sigma (mm) | Tag | Source or reason |
|---|---|---|---|---|
| XY, outer features 3-18 mm (also applied to the 28.5 mm pin pitch and the boss-bore and cradle spacings, outside the sourced range, so those uses are [A]) | +/-0.10 | 0.033 | S | Gebre et al. 2026, Table 3: a 3 mm feature has a Pmk >= 1.33 interval of X 2.90-3.09, Y 2.90-3.05. https://iris.unitn.it/retrieve/aaecc8a0-0420-472b-9a40-4d43d7df5e0b/Material%20Design%20%20%20Processing%20Communications%20-%202026%20-%20Gebre%20-%20Influence%20of%20Geometry%20and%20Size%20on%20Precision%20and%20Accuracy%20in.pdf, 2026-10-11 |
| XY, features more than 30 mm apart | +/-0.20 | 0.067 | A | The measured data stop at 18 mm; a service bureau guarantees +/-0.5 % (0.23 mm at 45 mm), https://www.hubs.com/manufacturing-standards/ (search snippet), 2026-10-11. Short-feature band doubled |
| Z features | +/-0.15 | 0.050 | S | Same paper, Table 3: Z interval of a 3 mm feature is 2.81-3.09. Same URL, 2026-10-11 |
| Small hole bias (about Ø3.6-4.6 mm) | -0.25 on diameter | n/a | S | Printed holes come out about 0.25 mm under CAD. https://www.cnckitchen.com/blog/are-our-heat-set-insert-datasheets-wrong, 2026-10-11. A PETG table gives +0.27 mm CAD enlargement at 3 mm, https://tools.creative3dp.com/blog/3d-printing-hole-compensation-typical-values/ (low confidence) |
| Large hole bias (about Ø20 mm) | -0.16 on diameter | n/a | S | PETG hole near 20 mm needs +0.16 mm CAD enlargement. https://tools.creative3dp.com/blog/3d-printing-hole-compensation-typical-values/, 2026-10-11 (vendor guide, low confidence) |
| Hole diameter scatter | +/-0.15 | 0.050 | A | Blog tables imply +/-0.10-0.15 mm and no dataset with a sample size exists; took the upper end |
| Hole position to datums on one print | Ø0.20 | n/a | A | +/-0.1 mm per axis, the XY short-feature band; no public hole-position data for hobby printers found |
| Pocket bias | -0.10 | n/a | A | Rectangular pockets and slots print small, less than round holes; no measured slot data found |
| Pocket width scatter | +/-0.15 | 0.050 | A | Between the XY band (0.10 mm) and the small-hole band (0.15 mm) |
| First-layer flare residual | +/-0.10 on diameter | n/a | A | What is left after slicer compensation; the Ender study compensates -0.2 mm, https://mdpi-res.com/d_attachment/processes/processes-11-02810/article_deploy/processes-11-02810.pdf, 2026-10-11 |
| Line-reamed plate holes, coaxial | +/-0.03 | 0.010 | A | Mid and front plate holes reamed in one pass with the plates bolted together |
| TPU 95A pad faces | +/-0.30 | 0.100 | A | No measured data exists; vendors quote +/-0.2 to +/-0.5 mm, https://craftcloud3d.com/en/material-guide/fdm-tpu, 2026-10-11 |
| m6 dowel pin | 3.002-3.008 | n/a | S | ISO 8734 m6, shown at 2.5 mm, same IT band at 3 mm. https://www.mcmaster.com/dowel-pins/diameter~2-5mm/, 2026-10-11 |
| h8 pin (ISO 2338) | 2.986-3.000 | n/a | A | h8 band is 14 um below nominal (ISO 286 grade table); the limits were not on a public catalogue page, confirm on the supplier sheet |
| Bronze bush bore, as pressed | 3.000-3.016 | n/a | S low / A high | Bore becomes H7 in a rigid H7 housing, https://www.hpceurope.com/docFichesTechniques/OiliteBushings.pdf pp. 40-43, 2026-10-11 [S]. 3.016 is the F7 as-supplied bore from the ISO 286 table [A]: a printed knuckle is not rigid, so the pressed bore can sit anywhere in between |
| M3 6g major diameter | 2.874-2.980 | n/a | S | ISO 965 6g, https://www.brightonbest.com/download/pds/PDS_Thread_Details_Metric_Series.pdf (date as in `basis.yaml` header: 2026-10-11) |
| M3 pan head diameter | 5.6 max | n/a | S | ISO 7045, https://ns1.engineersedge.com/iso_phillips_Pan_head_screw.htm, 2026-10-11 (medium confidence) |
| DS3218MG case width | 20.1 (20.5 run as a second case) | +/-0.10 | S / A | Case 39.9 x 20.1 x 40.4 mm, https://servodatabase.com/servo/dsservo/ds3218-mg, 2026-10-11 (low-medium) [S]; the repository's A17 row says 40.0 x 20.5 x 40.5 in `actuators.csv` `mount_pattern` text and `torque_and_actuator.md` (its `dim_W_mm` says 20) [S]; CAD uses 20.0. Tolerance [A]: listings disagree by 0.4 mm, measure 3 servos before the pocket is released |
| Servo shaft position in case | +/-0.20 | 0.067 | A | Unpublished for hobby servos |
| Servo angle repeatability | +/-0.5 deg | n/a | A | A 3 us deadband is 0.27 deg (180 deg over 2000 us) plus gear-train play |
| M3 screw length | +/-0.24 | 0.080 | A | ISO 4759-1 tolerance for a 6 mm screw is not public; measure 10 screws |
| Steel shim thickness | +/-0.02 | 0.007 | A | Steel shim washer |
| FSR force error after span calibration | +/-10 % | n/a | A | No public data for a calibrated FSR 402 behind a rigid backing |

## Sensitivity to the assumed inputs

Most inputs in the process basis are assumed [A], so the verdicts are only as good as those guesses. `python analysis/gripper/tolstack/tolstack.py sens` reruns every stack with each assumed input at 0.5x and 2x, for the rev A design as drawn and for the combined rev B design, and lists the checks whose verdict changes (inputs and factors in `stacks/rev_b.yaml`; full data in `results/sens/sens.json`). Same samples, same seed, so a change comes from the input alone.

**The 0.10 mm XY band is applied outside the range it was sourced for.** The measured data behind it cover outer features of 3 to 18 mm (Gebre et al. 2026, Table 3 [S]). The stacks also use it for the pin A to pin B hole spacing, a 28.5 mm pitch (`plate_hole_pos_tol`, T06, T07, T05, T10), and for the cradle-to-pin hole spacing. The longer-range band (0.20) is [A]. This is the input to measure first (coupon items 3 and 9). Doubling the XY band moves T06 from PASS (Cpk 2.04) to MARGINAL (Cpk 1.05) and T07 from PASS (Cpk 1.44) to FAIL (Cpk 0.93) as drawn.

<!-- tolstack:sens:start -->
**CAD rev A as drawn**

| Input scaled | x | Stack | Verdict change | Cpk | Yield (MC) |
|---|---:|---|---|---|---|
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 0.5 | T02 | MARGINAL -> **PASS** | 1.16 ± 0.040 -> 1.83 ± 0.036 | 99.98 % -> 100 % |
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 0.5 | T05 | FAIL -> **MARGINAL** | 0.92 ± 0.030 -> 1.07 ± 0.011 | 99.36 % -> 99.93 % |
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 2 | T02 | MARGINAL -> **FAIL** | 1.16 ± 0.040 -> 0.63 ± 0.011 | 99.98 % -> 95.51 % |
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 2 | T06 | PASS -> **MARGINAL** | 2.04 ± 0.010 -> 1.05 ± 0.015 | 100 % -> 99.85 % |
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 2 | T07 | PASS -> **FAIL** | 1.44 ± 0.039 -> 0.93 ± 0.024 | 99.998 % -> 99.50 % |
| hole diameter scatter (0.15) | 0.5 | T01 | MARGINAL -> **PASS** (at threshold: before within sampling error of 1.33) | 1.31 ± 0.047 -> 1.72 ± 0.046 | 99.996 % -> 100 % |
| hole diameter scatter (0.15) | 2 | T01 | MARGINAL -> **FAIL** (at threshold: before within sampling error of 1.33) | 1.31 ± 0.047 -> 0.83 ± 0.029 | 99.996 % -> 99.37 % |
| line-reamed coaxiality (0.03) | 2 | T16 | PASS -> **MARGINAL** | 1.67 ± 0.031 -> 1.08 ± 0.027 | 100 % -> 99.89 % |

No verdict change at 0.5x or 2x: XY print band over 30 mm only (0.20); Z print band (0.15); pocket width scatter (0.15); TPU pad face band (0.30); servo shaft position in case (0.20); servo angle repeatability (0.5 deg); servo case width tolerance (0.10); plate flatness / standoff top (0.05); FSR force error (10 %).

**CAD rev B, all changes at once**

| Input scaled | x | Stack | Verdict change | Cpk | Yield (MC) |
|---|---:|---|---|---|---|
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 0.5 | T14B | FAIL -> **MARGINAL** | 0.98 ± 0.006 -> 1.16 ± 0.016 | 99.84 % -> 99.97 % |
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 2 | T02 | PASS -> **FAIL** | 1.61 ± 0.056 -> 0.87 ± 0.016 | 100 % -> 99.35 % |
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 2 | T06 | PASS -> **MARGINAL** | 2.01 ± 0.031 -> 1.04 ± 0.016 | 100 % -> 99.84 % |
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 2 | T07 | PASS -> **FAIL** | 1.43 ± 0.033 -> 0.93 ± 0.019 | 99.998 % -> 99.48 % |
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 2 | T09 | PASS -> **MARGINAL** | 1.49 ± 0.046 -> 1.25 ± 0.032 | 100 % -> 99.990 % |
| XY print band, features 3-18 mm (0.10) and over 30 mm (0.20) together | 2 | T10 | PASS -> **MARGINAL** | 1.67 ± 0.033 -> 1.08 ± 0.057 | 100 % -> 99.88 % |
| Z print band (0.15) | 2 | T03 | PASS -> **MARGINAL** | 2.46 ± 0.032 -> 1.82 ± 0.013 | 100 % -> 100 % |
| Z print band (0.15) | 2 | T03B | PASS -> **MARGINAL** | 1.68 ± 0.055 -> 1.27 ± 0.032 | 100 % -> 100 % |
| hole diameter scatter (0.15) | 2 | T01 | PASS -> **MARGINAL** | 1.77 ± 0.064 -> 1.13 ± 0.039 | 100 % -> 99.96 % |
| pocket width scatter (0.15) | 0.5 | T14B | FAIL -> **MARGINAL** | 0.98 ± 0.006 -> 1.07 ± 0.022 | 99.84 % -> 99.93 % |
| pocket width scatter (0.15) | 2 | T14 | PASS -> **FAIL** | 1.68 ± 0.043 -> 0.94 ± 0.039 | 100 % -> 99.77 % |
| TPU pad face band (0.30) | 2 | T10 | PASS -> **MARGINAL** | 1.67 ± 0.033 -> 1.05 ± 0.024 | 100 % -> 99.85 % |
| servo angle repeatability (0.5 deg) | 0.5 | T09H | MARGINAL -> **PASS** | 1.28 ± 0.025 -> 1.54 ± 0.038 | 99.996 % -> 100 % |
| servo angle repeatability (0.5 deg) | 2 | T09 | PASS -> **MARGINAL** | 1.49 ± 0.046 -> 1.20 ± 0.031 | 100 % -> 99.98 % |
| servo angle repeatability (0.5 deg) | 2 | T09F | PASS -> **FAIL** | 1.46 ± 0.008 -> 0.98 ± 0.005 | 100 % -> 99.83 % |
| servo angle repeatability (0.5 deg) | 2 | T09H | MARGINAL -> **FAIL** | 1.28 ± 0.025 -> 0.86 ± 0.012 | 99.996 % -> 99.45 % |
| servo angle repeatability (0.5 deg) | 2 | T09P | PASS -> **FAIL** | 1.46 ± 0.009 -> 0.99 ± 0.007 | 100 % -> 99.85 % |
| servo case width tolerance (0.10) | 2 | T14 | PASS -> **MARGINAL** | 1.68 ± 0.043 -> 1.21 ± 0.036 | 100 % -> 99.99 % |
| line-reamed coaxiality (0.03) | 0.5 | T16 | MARGINAL -> **PASS** | 1.30 ± 0.021 -> 1.56 ± 0.019 | 99.998 % -> 100 % |
| line-reamed coaxiality (0.03) | 2 | T16 | MARGINAL -> **FAIL** | 1.30 ± 0.021 -> 0.91 ± 0.016 | 99.998 % -> 99.32 % |

No verdict change at 0.5x or 2x: XY print band over 30 mm only (0.20); servo shaft position in case (0.20); plate flatness / standoff top (0.05); FSR force error (10 %).

Cpk ± is the 99 % sampling uncertainty: 2.576 x the delete-a-batch jackknife standard error of the percentile Cpk (20 interleaved batches of the run's samples). A change is marked *at threshold* when the Cpk before or after lies within that uncertainty of 1.00 or of the stack's cpk_min (1.33 unless set); the label names that side, whose verdict is not resolved; a side not named is resolved.
<!-- tolstack:sens:end -->

Reading it: the XY band decides the most (T02, T05, T06, T07, T09, T10, T14B). Then come hole-diameter scatter (T01), pocket-width scatter and servo case width (T14, T14B), the Z band (the horn screw stack T03, T03B), the line-reamed coaxiality (T16), and servo angle repeatability (T09, T09F, T09H); FSR error changes no verdict, because T09P already fails in both designs. Halving any input only improves verdicts. At 2x the rev B set shows 15 verdict changes against 5 as drawn (the rev A T01 hole-scatter changes start at Cpk 1.31 ± 0.047, so their before side is at threshold, within sampling error; the 2x side, FAIL at 0.83, is resolved), partly because rev A's eleven FAILs cannot get worse. The first rev B checks to fail are T02, T07, T09H, T14 and T16 (T14B already fails), and every one rests on an assumed input.

## Options, rejected layouts and scenarios

<!-- tolstack:options:start -->
| Variant | Role | Change | Verdict | Yield (MC) | Cpk | Worst case |
|---|---|---|---|---|---:|---|
| T01-cad37 | option | mount holes CAD 3.7 | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.77 ± 0.02 | -0.363 … -0.035 |
| T01-stock32 | rejected | stock CAD hole 3.2 (SO-101 gripper) | FAIL | 7.81 % | -0.53 ± 0.01 | -0.113 … 0.215 |
| T01H-stock60 | rejected | stock counterbore 6.0 | FAIL | 89.11 % | 0.47 ± 0.00 | -0.300 … 0.175 |
| T02-relax40 | option | recess CAD 19.56 and accept clearance up to 0.40 (checked by T04-relax40) | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.61 ± 0.02 | 0.050 … 0.350 |
| T02-stock20 | rejected | stock Ø20.0 recess, no chamfer | FAIL | 0.00 % | -1.89 ± 0.01 | 0.390 … 0.890 |
| T03-depth35 | scenario | horn holes measured 3.5 deep (M15 outcome to confirm) | MARGINAL (blocked by T03B-depth35; own check PASS) | 100.000 % (<3 ppm (0 of 1,000,000 samples; 95% upper bound) out) | 2.46 ± 0.01 | 1.885 … 2.915 |
| T03-m3x5 | option | M3x5 screws in the 2.5 CAD hole | FAIL (blocked by T03B-m3x5; own check FAIL) | 23.15 % | -0.27 ± 0.00 | 0.885 … 1.915 |
| T03B-depth35 | scenario | horn holes measured 3.5 deep (M15 outcome to confirm) | MARGINAL | 99.916 % (835 ppm out) | 1.04 ± 0.00 | -0.015 … 1.215 |
| T03B-m3x5 | option | M3x5 screws | MARGINAL | 99.916 % (835 ppm out) | 1.04 ± 0.00 | -0.015 … 1.215 |
| T04-relax40 | scenario | recess CAD 19.56, clearance up to 0.40 (T02-relax40) | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.96 ± 0.01 | 0.000 … 0.275 |
| T04-stock20 | rejected | stock Ø20.0 recess (T02-stock20) | FAIL | 82.80 % | 0.39 ± 0.00 | 0.000 … 0.545 |
| T05-deckpegs | option | deck located by two bought h8 pins in reamed holes | PASS | 99.996 % (43 ppm out) | 1.35 ± 0.00 | -1.037 … 1.651 |
| T05-tcpcal | option | measure the pinch point once and set the TCP (removes every fixed offset; leaves the T04 float) | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.96 ± 0.02 | -0.517 … 1.131 |
| T06-servoshaft | rejected | pre-rev-A layout: knuckle A on the servo shaft, pin B in the housing | FAIL | 97.25 % | 0.75 ± 0.01 | 28.028 … 28.972 |
| T07-servoshaft | rejected | pre-rev-A layout (T06-servoshaft) | FAIL | 96.14 % | 0.69 ± 0.00 | -0.383 … 0.883 |
| T09F-r15p8 | scenario | R15 ruled: cap 8 N | FAIL | 44.91 % | -0.04 ± 0.00 | 3.589 … 13.338 |
| T09F-relfloor | option | firmware round 2: floor = calibrated contact - 6.2 deg (held the superseded 10 N at the stiff finger) | FAIL | 47.07 % | -0.03 ± 0.00 | 6.408 … 9.863 |
| T09F-relfloor8 | option | firmware: floor = calibrated contact - 4.9 deg (config.h JAW_FLOOR_BELOW_C0_DEG), against the ruled 8 N cap | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.46 ± 0.00 | 4.865 … 8.031 |
| T09H-relfloor8 | option | firmware: floor = calibrated contact - 4.9 deg (JAW_FLOOR_BELOW_C0_DEG), the squeeze still limited by u_max | MARGINAL | 99.996 % (<92 ppm (4 of 100,000 samples; 95% upper bound) out) | 1.28 ± 0.01 | 4.826 … 7.985 |
| T09H-relfloor | option | firmware round 2: floor = calibrated contact - 6.2 deg, so the squeeze is limited by u_max alone | MARGINAL | 99.996 % (<92 ppm (4 of 100,000 samples; 95% upper bound) out) | 1.28 ± 0.01 | 4.826 … 7.985 |
| T09H-r15p8 | scenario | squeeze cap sized for the ruled 8 N: 3.785 deg (basis u_max_8_deg, the firmware compiled with F_CAP_N 8) | FAIL | 39.50 % | -0.21 ± 0.00 | 4.183 … 5.333 |
| T09P-r15p8 | scenario | R15 ruled: cap 8 N | FAIL | 11.53 % | -0.52 ± 0.00 | 7.045 … 11.105 |
| T09P-trip7 | option | firmware: F_TRIP_N 7.0, F_TRIP_MS 10 | FAIL | 65.44 % | 0.18 ± 0.00 | 6.364 … 9.426 |
| T09P-trip55 | scenario | firmware: F_TRIP_N 5.5, F_TRIP_MS 10, against the ruled 8 N cap | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.48 ± 0.01 | 5.000 … 7.760 |
| T09P-floor49 | option | firmware: trip 7.75 N / 20 ms, peak bounded by the jaw floor theta_c0 - 4.9 deg (JAW_FLOOR_BELOW_C0_DEG) | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.46 ± 0.00 | 4.865 … 8.031 |
| T09T-r19p075 | scenario | Historical R19 limit: 0.5 s (legacy r19p075 scenario id) | FAIL | 24.04 % | -0.24 ± 0.00 | 0.463 … 0.551 |
| T09T-slow3 | option | firmware: JAW_SLOW_ZONE_DEG 6 -> 3 (0.125 s less: 3 deg at 120 instead of 20 deg/s) | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 12.54 ± 0.15 | 0.338 … 0.426 |
| T10-toein | option | contact faces toed in 0.44 deg: parallel at first contact | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.67 ± 0.01 | -1.448 … 1.448 |
| T11-band2 | scenario | second band: hub r 14.6 (H+1..H+5.0) vs lip r 15.4, not a first layer | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.90 ± 0.01 | 0.100 … 1.050 |
| T11-stock12 | rejected | pre-rev-A hub r 12.0 | FAIL | 99.33 % | 0.83 ± 0.00 | -0.200 … 0.750 |
| T12-stock45 | rejected | pre-rev-A widen at 4.5 above H | FAIL | 92.96 % | 0.53 ± 0.00 | -0.400 … 1.000 |
| T13-notab | rejected | no locating tab: rotation set by 2 screws in Ø3.6 holes | FAIL | 68.01 % | 0.58 ± 0.00 | -6.983 … 6.983 |
| T14-w205 | scenario | servo body 20.5 (actuators.csv A17) in the rev A 20.4 pocket: it does not fit | FAIL | 0.03 % | -1.12 ± 0.01 | -0.450 … 0.050 |
| T14-w205p209 | scenario | servo body 20.5 in a pocket opened to 20.9 while the cradle still locates it: float over the 0.30 limit | FAIL | 49.90 % | -0.00 ± 0.00 | 0.050 … 0.550 |
| T14-boss | option | boss-located servo: only drop-in matters; pocket width from the case constants | MARGINAL | 99.958 % (420 ppm out) | 1.12 ± 0.01 | -0.050 … 0.450 |
| T14-boss205 | option | boss-located servo (T14B-boss34) + pocket CAD 20.5: only drop-in matters | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.68 ± 0.02 | 0.050 … 0.550 |
| T14-cad205 | rejected | pocket CAD 20.5 while the cradle still locates the servo | FAIL | 49.90 % | -0.00 ± 0.00 | 0.050 … 0.550 |
| T14B-w205 | scenario | servo body 20.5 (actuators.csv A17) in a pocket opened to 20.9, rev A cradle-located: servo float 0.15 per side | FAIL | 33.89 % | -0.11 ± 0.00 | -0.115 … 0.602 |
| T14B-boss34 | option | servo located by its Ø9 boss in a reamed bore + dog slots 3.4 | FAIL | 99.80 % | 0.96 ± 0.01 | -0.283 … 0.244 |
| T14B-boss | option | servo located by its boss, slots unchanged at 3.14 | FAIL | 64.54 % | 0.11 ± 0.00 | -0.153 … 0.374 |
| T15-shimselect | option | shims picked at assembly from a 0.05-step set | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 4.35 ± 0.05 | 0.245 … 0.355 |
| T16-noream | scenario | line reaming skipped: plate holes as printed, front plate located by the pins | FAIL | 96.83 % | 0.71 ± 0.01 | -0.157 … 0.157 |
| T16B-h8pin | option | ISO 2338 h8 pin 2.986-3.000 as the knuckle shaft | PASS | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) | 1.05 ± 0.00 | -0.000 … 0.030 |
<!-- tolstack:options:end -->

## Stack notes

Each note: what it checks, what dominates (variance share, [D]), what to do. Frame I = interface (axis along the wrist roll); frame G = gripper (X closing axis, Z along the pivot axes).

**T01 / T01H, mount bolt pattern and counterbores (frame I).** Do the 4 x M3 screws pass the printed holes and thread into the horn, and does the pan head clear its counterbore. Hole position dominates T01 (81 %). T01 is marginal at CAD Ø3.6; open to Ø3.7. The Ø6.5 counterbore passes with margin.

**T02 / T04, pilot recess and concentricity (frame I).** The Ø19.2 horn must slide into the printed recess by hand (at least 0.02 mm diametral clearance) with at most 0.30 mm of float. The recess prints about Ø19.35 [D, large-hole bias -0.16 mm S]. The printed recess diameter dominates T02 (80 %), pilot float dominates T04 (54 %). Print the coupon, then size the recess; or take the relax40 option.

**T03 / T03B, screw engagement and bottoming (frame I).** T03 (thread engagement 1.885-2.100 mm against a 1.5 mm minimum) passes alone but is conditional on T03B, where the M3x6 tip bottoms at the CAD hole depth 2.5 mm. Horn hole depth dominates T03 (100 %); clamp thickness dominates T03B (41 %). Measure the horn first.

**T05, jaw centreline (frame G, X).** Pinch point within -0.193 to +0.807 mm of the roll axis: +/-0.5 mm (`jaw_center_tol` [A]: half of the +/-1 mm cloth-edge target in `cloth_and_camera.md` 3.2) around the known design offset of the pinch point. Chain: roll axis, pilot float, spider inserts, deck (floating on 4 M3 screws in Ø3.6 holes), pin A holes, knuckle A. The deck float dominates (64 %). Locate the deck with pegs or calibrate the TCP.

**T06 / T07, gear centre distance and backlash (frame G).** Centre distance 28.5 mm against a 28.286-28.714 mm window; backlash 0.050-0.450 mm. Both pass; the pin A to pin B hole spacing dominates T06 (93 %) and the centre distance dominates T07 (50 %). Keep the plate holes line-reamed together.

**T08, mesh Z alignment (frame G, Z).** Gear A and B mid-planes within +/-0.8 mm. Passes; gear A float dominates (46 %). Nothing to do.

**T09 and companions, closing, force and speed (frame G).** T09 (first-contact angle before calibration) passes; horn trim dominates (68 %). The companions T09T, T09P, T09F, T09H test R19 and R15 and are covered in the ruled-limit and historical-comparison section above.

**T10 / T10B, pad parallelism and out-of-plane tip (frame G).** T10 is the root gap when the tips first touch, within +/-1.0 mm; it fails because the design V (0.64 mm [D]) is built in, so toe the faces in 0.44 deg. T10B (tip Z mismatch within +/-2.0 mm) passes by Monte Carlo although worst case is +/-2.465 mm; pin A perpendicularity dominates (29 %).

**T11, T12, T12B, keep-outs (frame I).** Hub r 11.6 mm against the wrist-link lip r 12.6 mm (clearance at least 0.1 mm), axial clearance above the lip, and rim-to-servo-5 case gap. All pass; lip radius dominates T11 (49 %). Do not grow the hub back to the stock envelope.

**T13, camera aim (frame G).** Optional wrist-camera bracket. Passes by Monte Carlo (Cpk 1.83) with the locating tab, but worst case is +/-3.033 deg against +/-3.000 deg; lens tilt dominates (35 %). Keep the tab; without it the stack fails (T13-notab).

**T14B web and direction re-base.** The web-bore centre is 6.30 mm behind (boss-web case gap 0.15 mm, B42) the pin-A mid-plate plane: `plate/2 + front_gap/2 + horn_t + horn_gap - boss_web_gap - boss_web_t/2`. A 0.10 mm perpendicularity zone over the CAD 15 mm pin span therefore adds 0.042 mm lateral position. The 1.6 mm web does not establish servo direction: the ear seats and cradle floor do. Their existing 0.20 mm `mount_flatness` over the CAD 54.5 mm ear span acts across the 3.05 mm boss-web-to-dog lever, `horn_gap + horn_t/2 - boss_web_gap - boss_web_t/2`, adding 0.011 mm. T14B-boss34 therefore changes MARGINAL → FAIL. A slot of 3.42 mm is the smallest 0.02 mm increment that restores the prior margin: its extra 0.010 mm half-clearance raises Cpk by about 0.07, from 0.98 to 1.05; this is not a design change and T09 must still be checked. A zero-lash offset coupling remains robust.

**T14 / T14B, servo cradle and dog coupling (frame G).** T14: the servo body (listed 20.1 mm wide) in the 20.4 mm pocket; pocket width dominates (69 %). T14B: the servo shaft and pin A are two axes, and an offset across the dog slot must fit the half-clearance (about 0.06 mm at slot 3.14 mm [D `basis.yaml` `dog_clear`]); the shaft position in the servo case dominates (38 %; slot width 14 %; Monte Carlo freeze-one, because abs() has no usable sensitivity at 0), and the RSS rows are not valid for this non-linear model. Both are fixed by locating the servo by its boss (rows 1 and 3).

**T15, knuckle end play (frame G, Z).** Three standoffs and 0.85 mm shims per side leave 0.3 mm nominal against 0.05-0.50 mm. Standoff top height dominates (41 %). Pick shims at assembly.

**T16 / T16B, pin tilt and sleeve running fit (frame G).** T16: centre-distance change across the 8 mm gear face, within +/-0.07 mm; passes only with line-reamed holes. T16B: bush bore against pin; the bush bore dominates (88 %). Use the h8 pin.

## Datum frame and GD&T

Two frames, as in each note above:
- **Frame I (interface):** +Z along the wrist-roll axis, from horn face H into the gripper; X-Y in the plane of the mount face. Used by T01, T01H, T02, T03, T03B, T04, T11, T12, T12B.
- **Frame G (gripper):** X = jaw closing axis, Y = up (wrist on top, fingertips at -Y), Z = along the pivot axes. Used by T05-T10B, T13-T16B.
- **Mapping:** I +Z = G -Y. I's X-Y plane is G's X-Z plane, clocked by datum C. The pivot axes (G-Z) are parallel to datum A, not perpendicular to it.

```
            +Z_I (roll axis, into gripper)  =  -Y_G
             ^
             |      C = 4x hole pattern (clocking about Z_I), at MMC
   ----------+----------  <- A: recess floor (contacts horn face H), primary
  |  |<--- recess -->|  |   B: recess bore (on the 19.2 horn OD), secondary, at MMC
  |__|               |__|
        [ horn ]            servo 5

   side view of the housing, looking along -X_G:
      A (mount face, top) ══════════════  ^ +Y_G
                        |
                        | D (mid-plate front face)
      pins A and B  ────┼──────  → +Z_G  (perpendicular to D, parallel to A)
                        |
```

- **A (primary): the mount face, the recess floor that seats on horn face H.** Flatness 0.2 mm [A, reason: proposed callout, `mount_flatness`].
- **B (secondary): the recess bore**, which centres the part on the horn, at MMC. The clearance that shifts this datum is real float (T04).
- **C (tertiary): the 4 hole pattern**, clocking about Z_I at MMC. Jaw clocking is calibrated in software at wrist-roll zero, so C only has to let the screws in.
- **D: the mid-plate front face**, the face the knuckles and gears run against. It orients the pivot axes: pin holes are perpendicular to D.
- Rev A pinned layout: knuckle A and knuckle B each turn in a bronze bush on their own pressed pin, with the plate holes line-reamed together, and the servo drives knuckle A through a dog coupling. Pivot positions (centre distance, jaw centre) are located to A, B, C; pivot orientation (tilt) is controlled to D.

Proposed callouts, rev A with rev B changes marked:

| Feature | Callout | Why | Stack |
|---|---|---|---|
| Mount face (A) | Flatness 0.2 mm [A] | Seat on the horn; the part rests on its high points | T03, T03B, T12 |
| Recess (B), CAD Ø19.51 (rev B Ø19.56), 0.3 mm x 45 deg mouth chamfer | Prints about Ø19.35 +/-0.10 mm [D] | Pilot fit and float | T02, T04, T11 |
| 4 mount holes, CAD Ø3.6 (rev B Ø3.7) | Position Ø0.2 mm at MMC to A, B [A] | Fixed fastener: the hole at MMC (CAD less 0.25 bias less 0.15 scatter = 3.20 mm; 3.30 mm at CAD 3.7 [D]) less the screw (2.98 mm) less the horn thread position (0.05 mm [A]) leaves 0.17 mm of position zone at CAD 3.6 and 0.27 mm at CAD 3.7. The 0.2 mm callout fits only at 3.7 | T01 |
| 4 counterbores, CAD Ø6.5 | Position Ø0.2 mm [A] | Head clearance | T01H |
| Hub r 11.6 mm to H+1, then r 14.6 mm to H+5.0; full widening above H+5.0 | As stated; first-layer flare +0.10 mm radial [A] | Keep-out | T11, T12 |
| Servo cradle pocket 20.4 (rev B 20.5) | Width | Rev B: drop-in only | T14 |
| Servo boss bore Ø9 (rev B) | Reamed; position to pin A hole +/-0.10 mm [S for features of 3-18 mm; [A] at this spacing] | Locates the servo | T14B |
| Pin A and pin B holes, both plates | Line-reamed together; coaxial +/-0.03 mm [A]; position +/-0.10 mm (reaming sizes the hole but follows the printed position, https://newscrewdriver.com/2020/11/27/sawppy-issue-8mm-hole-precision/, retrieved 2026-10-11 [S]; the 0.10 band itself is [A] at the 28.5 mm pitch); perpendicular Ø0.10 mm to D [A] | Centre distance, axis tilt | T05, T06, T10B, T16 |
| Pins | h8, 2.986-3.000 mm (rev B) | Running fit | T16B |
| Knuckle bores | Ø6 for 3 x 6 bronze bush (rev B), bore length 10.0 mm [D] | Knuckle cocking, running fit | T10B, T16, T16B |
| Gear teeth | Backlash 0.25 mm [D], pitch-circle runout 0.05 mm [A] | Backlash | T07 |
| Finger contact faces | Toed in 0.44 deg (rev B) | Parallel at first contact | T10 |
| Camera boss | Perpendicular 0.2 mm [A], plus a locating tab | Aim | T13 |

Conversions the tool uses (position Ø t = +/- t/2 per axis or radius t/2; runout t = eccentricity t/2; profile t = +/- t/2; perpendicularity t over length L = +/- t x lever / L; fixed fastener H = F + T1 + T2, floating fastener H = F + T) are available from the command line (next section).

## Calculator

`analysis/gripper/tolstack/` holds the `tolcalc` package, the `tolstack.py` command line, `tests/`, `stacks/` and `results/`. Needs Python 3.13 with numpy, PyYAML and matplotlib. Run from the repository root.

```
python analysis/gripper/tolstack/tolstack.py run
python -m pytest analysis/gripper/tolstack/tests -q
python analysis/gripper/tolstack/tolstack.py run analysis/gripper/tolstack/stacks --out <scratch folder> --no-doc --set hole_cad_d=3.6
python analysis/gripper/tolstack/tolstack.py sweep analysis/gripper/tolstack/stacks --stack T02 --param recess_d_cad --values 19.40:19.60:0.01
python analysis/gripper/tolstack/tolstack.py gdt position 0.2
python analysis/gripper/tolstack/tolstack.py gdt perpendicularity 0.1 --length 10 --lever 85
python analysis/gripper/tolstack/tolstack.py fastener fixed --H 3.25 --F 2.98 --T2 0.05
```

- `run` regenerates every stack result, `results/SUMMARY.md`, `results/summary.json`, `results/run_stdout.txt`, the histograms in `results/figures/`, and the three generated blocks in this file (verdicts, options, all numbers).
- `sweep` reruns one stack over a range of one constant and reports Cpk for each value. Sweep a base stack: a variant's own `set:` wins over the swept constant.
- Stack files are YAML in `analysis/gripper/tolstack/stacks/`; every design input lives in `stacks/basis.yaml`, so a different printer, gear or finger changes one file. `T05_jaw_centerline.yaml` is a long worked example with variants.
- A run draws each leaf contributor once, from a seeded stream, and shares it across stacks, so stacks that chain on each other (T09 on T07 on T06) keep their correlation.
- Use worst case for jams (screws, bottoming) and Monte Carlo Cpk of at least 1.33 for everything else.

## Coupon plan

Print one coupon in PETG, with the housing's settings and orientation (mount face on the bed), 5 copies [A: enough for a rough mean and spread at one print plate's cost; more copies give a better sigma]. With 5 copies, bias = the mean deviation and band = 3 x the standard deviation; 5 parts give a rough sigma, so keep the `basis.yaml` value when it is larger. Replaces the named constants in `basis.yaml`.

| # | Coupon feature | Measure | Replaces |
|---|---|---|---|
| 1 | Holes CAD Ø3.4 / 3.6 / 3.7 / 3.8, 3 of each; counterbores Ø6.5 / 6.0 | Pin gauges; M3 screw go/no-go; pan head in each counterbore | `fdm_hole_bias_small_d`, `fdm_hole_scatter_d` |
| 2 | Recess CAD Ø19.46 / 19.51 / 19.56 / 19.60, 1.0 mm deep, with the 0.3 mm x 45 deg chamfer | Fit on the real servo-5 horn; caliper the inside diameter | `recess_d_cad`, `fdm_hole_bias_large_d`, `efc_resid_d` |
| 3 | 4-hole pattern on the 14.0 mm bolt circle | Screw onto the real horn; caliper hole positions from the recess edge | `fdm_pos_dia` |
| 4 | Hub OD Ø23.2, 2 mm tall | Caliper at the first layer and at 1.5 mm | `efc_hub_bias_r` |
| 5 | Pocket widths 20.4 / 20.5 / 20.6 / 20.9 mm | Drop-in with the real DS3218MG; caliper the case width in 3 places on 3 servos (gate for the pocket dimension) | `fdm_pocket_bias`, `fdm_cavity_tol`, `servo_body_w_tol` |
| 6 | Steps 1.0 / 3.0 / 5.0 mm | Caliper depth rod | `fdm_z_tol`, `mount_flatness` |
| 7 | Two 2.5 mm plates on standoffs, two holes 28.5 mm apart, line-reamed together; press in h8 pins | Pin tilt to the plate face (datum D): square on the plate, feeler at the pin tip | `plate_hole_pos_tol`, `pin_span`, `pin_perp_zone` |
| 8 | Knuckle bores Ø6 with 3 x 6 bronze bush, 7.7 mm long; dog slots 3.14 and 3.4 mm on a spare horn | Rock the knuckle on the pin; feeler gauge at the end; dog circumferential lash | `sleeve_bore_max`, `dog_slot_w`, `dog_clear` |
| 9 | Two holes 28.5 mm apart on one print | Caliper centre to centre | `fdm_xy_tol_short` |
| 10 | Servo boss bore Ø9, printed undersize and reamed (rev B) | Fit the real servo boss; measure position to a pin hole | `servo_shaft_pos_tol`, boss-fit terms in T14B |
| 11 | Deck peg and reamed peg hole (rev B) | Float of a printed Ø3 peg in a reamed hole | peg float in T05-deckpegs |

Also measure: the real horn hole depth (`horn_hole_depth`); 10 M3x6 screw lengths (`screw_len_tol`); 3 servo case widths and the shaft offset from the case side (the gate for the pocket dimension, rev B row 3); each printed finger's tip stiffness (DB M10); the shim assortment's actual thickness.

## Assumptions

- Every contributor tagged [A] in `basis.yaml` is an assumption, with the reason in the process basis table above. The biggest drivers: servo shaft position in case (+/-0.20 mm), servo angle repeatability (+/-0.5 deg), printed hole position (Ø0.20 mm), TPU pad faces (+/-0.30 mm), hole scatter (+/-0.15 mm), FSR error (+/-10 %), bush bore upper limit (3.016 mm).
- Distributions [A]: print scatter is normal with the band as 3 sigma; clearance float is uniform. Reason: scatter around a process mean is bell-shaped, while a float is equally likely anywhere in its limits; printer bias enters as a mean shift, not as scatter.
- Stacks are one-dimensional along the stated direction, or radial where the offset direction is free (T01, T01H, T04). Angular terms are linearised through lever arms. Keep-out stacks treat the 320 deg roll as a full ring. [A, standard simplification]
- Fixed-fastener rule for T01: the screws thread into the horn, so the two parts share the hole-to-screw margin (H = F + T1 + T2) [D].
- Requirement limits are [A] in `basis.yaml` unless the table says otherwise; change them there and rerun. R15 = 8 N and R19 = 0.75 s are ruled in DESIGN-BASIS; see the historical comparisons above.
- Dog coupling lash, finger peg float (0.05 mm) and camera tab float (0.05 mm) are uncalibrated [A]. They are conservative guesses, to be replaced by coupon data.
- Rev A servo mounting is by the cradle pocket; the boss-location rows (1 and 3) are rev B and run only as variants.
- The hot amounts and the 0.5x/2x sensitivity factors are judgement [A]; heat, moisture and wear are not modelled (section *Heat, and what these stacks do not model*).

## All numbers

<!-- tolstack:summary:start -->
Nominal is the drawn value with no process bias and no radial term; the other columns include both, so Nominal can lie outside the WC band (T01, T01H, T04, T14B). Mean (MC) is the Monte Carlo mean with the bias.

| Stack | Role | Nominal | Mean (MC) | WC | RSS (dist.) | MC 99.73 % band | Out % | Cpk | Spec | Accept | Verdict |
|---|---|---:|---:|---|---|---|---:|---:|---|---|---|
| T01 Horn-to-mount bolt pattern fit (4x M3 on the 14.0 BC) | baseline | -0.337 | -0.143 | -0.313 … 0.015 | -0.299 … -0.014 | -0.259 … -0.034 | <92 ppm (4 of 100,000 samples; 95% upper bound) | 1.31 ± 0.02 | USL 0.000 | WC | **MARGINAL** |
| T01-cad37 (mount holes CAD 3.7) | option | -0.387 | -0.193 | -0.363 … -0.035 | -0.349 … -0.064 | -0.309 … -0.084 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.77 ± 0.02 | USL 0.000 | WC | **PASS** |
| T01-stock32 (stock CAD hole 3.2 (SO-101 gripper)) | rejected | -0.137 | 0.057 | -0.113 … 0.215 | -0.099 … 0.186 | -0.059 … 0.166 | 92.2 % | -0.53 ± 0.01 | USL 0.000 | WC | **FAIL** |
| T01H M3 pan head clears its counterbore (rev A Ø6.5) | baseline | -0.525 | -0.326 | -0.550 … -0.075 | -0.550 … -0.152 | -0.485 … -0.165 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 2.02 ± 0.01 | USL 0.000 | WC | **PASS** |
| T01H-stock60 (stock counterbore 6.0) | rejected | -0.275 | -0.076 | -0.300 … 0.175 | -0.300 … 0.098 | -0.235 … 0.085 | 10.9 % | 0.47 ± 0.00 | USL 0.000 | WC | **FAIL** |
| T02 Horn pilot recess radial fit (Ø19.2 horn in the printed Ø19.51 recess) | baseline | 0.310 | 0.150 | 0.000 … 0.300 | 0.038 … 0.262 | 0.038 … 0.262 | 240 ppm | 1.16 ± 0.02 | LSL 0.020, USL 0.300 | MC | **MARGINAL** |
| T02-relax40 (recess CAD 19.56 and accept clearance up to 0.40 (checked by T04-relax40)) | option | 0.360 | 0.200 | 0.050 … 0.350 | 0.088 … 0.312 | 0.088 … 0.312 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.61 ± 0.02 | LSL 0.020, USL 0.400 | MC | **PASS** |
| T02-stock20 (stock Ø20.0 recess, no chamfer) | rejected | 0.800 | 0.640 | 0.390 … 0.890 | 0.434 … 0.846 | 0.462 … 0.819 | 100 % | -1.89 ± 0.01 | LSL 0.020, USL 0.300 | MC | **FAIL** |
| T03 Axial stack horn face to clamp to screw — thread engagement | baseline | 2.000 | 2.000 | 1.885 … 2.100 | 1.900 … 2.100 † | 1.900 … 2.101 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 4.99 ± 0.04 | LSL 1.500 | WC | **FAIL (blocked by T03B; own check PASS)** |
| T03-depth35 (horn holes measured 3.5 deep (M15 outcome to confirm)) | scenario | 2.500 | 2.400 | 1.885 … 2.915 | 2.005 … 2.795 | 2.034 … 2.768 | <3 ppm (0 of 1,000,000 samples; 95% upper bound) | 2.46 ± 0.01 | LSL 1.500 | WC | **MARGINAL (blocked by T03B-depth35; own check PASS)** |
| T03-m3x5 (M3x5 screws in the 2.5 CAD hole) | option | 1.500 | 1.400 | 0.885 … 1.915 | 1.005 … 1.795 | 1.034 … 1.773 | 76.9 % | -0.27 ± 0.00 | LSL 1.500 | WC | **FAIL (blocked by T03B-m3x5; own check FAIL)** |
| T03B Axial stack — screw tip clear of the horn hole floor | baseline | -0.500 | -0.400 | -1.015 … 0.215 | -0.807 … 0.007 | -0.787 … -0.021 | 100 % | -1.55 ± 0.02 | LSL 0.200 | WC | **FAIL** |
| T03B-depth35 (horn holes measured 3.5 deep (M15 outcome to confirm)) | scenario | 0.500 | 0.600 | -0.015 … 1.215 | 0.193 … 1.007 | 0.217 … 0.981 | 835 ppm | 1.04 ± 0.00 | LSL 0.200 | WC | **MARGINAL** |
| T03B-m3x5 (M3x5 screws) | option | 0.500 | 0.600 | -0.015 … 1.215 | 0.193 … 1.007 | 0.217 … 0.981 | 835 ppm | 1.04 ± 0.00 | LSL 0.200 | WC | **MARGINAL** |
| T04 Gripper datum B axis vs wrist-roll axis (concentricity) | baseline | 0.000 | 0.066 | 0.000 … 0.250 | 0.000 … 0.180 | 0.003 … 0.168 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 2.25 ± 0.01 | USL 0.300 | MC | **PASS** |
| T04-relax40 (recess CAD 19.56, clearance up to 0.40 (T02-relax40)) | scenario | 0.000 | 0.079 | 0.000 … 0.275 | 0.000 … 0.213 | 0.003 … 0.191 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.96 ± 0.01 | USL 0.300 | MC | **PASS** |
| T04-stock20 (stock Ø20.0 recess (T02-stock20)) | rejected | 0.000 | 0.217 | 0.000 … 0.545 | 0.000 … 0.545 † | 0.012 … 0.422 | 17.2 % | 0.39 ± 0.00 | USL 0.300 | MC | **FAIL** |
| T05 Jaw centreline offset at the fingertips vs roll axis (X, closing axis) | baseline | 0.307 | 0.307 | -1.330 … 1.944 | -0.281 … 0.895 | -0.231 … 0.852 | 0.644 % | 0.92 ± 0.01 | LSL -0.193, USL 0.807 | MC | **FAIL** |
| T05-deckpegs (deck located by two bought h8 pins in reamed holes) | option | 0.307 | 0.307 | -1.037 … 1.651 | -0.048 … 0.662 | -0.063 … 0.674 | 43 ppm | 1.35 ± 0.00 | LSL -0.193, USL 0.807 | MC | **PASS** |
| T05-tcpcal (measure the pinch point once and set the TCP (removes every fixed offset; leaves the T04 float)) | option | 0.307 | 0.307 | -0.517 … 1.131 | 0.050 … 0.564 | 0.053 … 0.563 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.96 ± 0.02 | LSL -0.193, USL 0.807 | MC | **PASS** |
| T06 Gear centre distance a (pin A to pin B, rev A pinned layout) | baseline | 28.500 | 28.500 | 28.356 … 28.644 | 28.396 … 28.604 | 28.397 … 28.605 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 2.04 ± 0.00 | LSL 28.286, USL 28.714 | MC | **PASS** |
| T06-servoshaft (pre-rev-A layout: knuckle A on the servo shaft, pin B in the housing) | rejected | 28.500 | 28.500 | 28.028 … 28.972 | 28.204 … 28.796 | 28.213 … 28.787 | 2.75 % | 0.75 ± 0.01 | LSL 28.286, USL 28.714 | MC | **FAIL** |
| T07 Gear backlash jt (circumferential, m 1.5 z 19, alpha 25) | baseline | 0.250 | 0.250 | -0.078 … 0.578 | 0.113 … 0.387 | 0.111 … 0.389 | <63 ppm (2 of 100,000 samples; 95% upper bound) | 1.44 ± 0.02 | LSL 0.050, USL 0.450 | MC | **PASS** |
| T07-servoshaft (pre-rev-A layout (T06-servoshaft)) | rejected | 0.250 | 0.250 | -0.383 … 0.883 | -0.043 … 0.543 | -0.039 … 0.538 | 3.86 % | 0.69 ± 0.00 | LSL 0.050, USL 0.450 | MC | **FAIL** |
| T08 Gear mesh axial alignment (gear A vs gear B mid-planes, Z) | baseline | 0.000 | -0.000 | -0.490 … 0.490 | -0.383 … 0.383 | -0.321 … 0.321 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 2.49 ± 0.01 | LSL -0.800, USL 0.800 | MC | **PASS** |
| T09 Closure gap — first-contact angle of the jaw before calibration | baseline | -1.154 | -1.154 | -3.875 … 1.566 | -2.364 … 0.055 | -2.352 … 0.069 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 2.37 ± 0.03 | LSL -4.000, USL 4.000 | MC | **PASS** |
| T09F Pad force at the jaw floor with the FSR trip failed (position-only cap, R15) | baseline | 8.106 | 8.106 | 3.589 … 13.338 | 6.021 … 10.191 | 6.189 … 10.217 | 55.1 % | -0.04 ± 0.00 | USL 8.000 | MC | **FAIL** |
| T09F-r15p8 (R15 ruled: cap 8 N) | scenario | 8.106 | 8.106 | 3.589 … 13.338 | 6.021 … 10.191 | 6.189 … 10.217 | 55.1 % | -0.04 ± 0.00 | USL 8.000 | MC | **FAIL** |
| T09F-relfloor (firmware round 2: floor = calibrated contact - 6.2 deg (held the superseded 10 N at the stiff finger)) | option | 8.047 | 8.047 | 6.408 … 9.863 | 6.633 … 9.460 | 6.870 … 9.298 | 52.9 % | -0.03 ± 0.00 | USL 8.000 | MC | **FAIL** |
| T09F-relfloor8 (firmware: floor = calibrated contact - 4.9 deg (config.h JAW_FLOOR_BELOW_C0_DEG), against the ruled 8 N cap) | option | 6.359 | 6.360 | 4.865 … 8.031 | 5.150 … 7.569 | 5.307 … 7.480 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.46 ± 0.00 | USL 8.000 | MC | **PASS** |
| T09H Largest hold force the firmware can reach on the softest finger (R14 under the R15 cap) | baseline | 6.317 | 6.316 | 4.183 … 6.858 | 5.379 … 6.858 † | 5.777 … 6.856 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 2.44 ± 0.01 | LSL 5.000 | MC | **PASS** |
| T09H-relfloor8 (firmware: floor = calibrated contact - 4.9 deg (JAW_FLOOR_BELOW_C0_DEG), the squeeze still limited by u_max) | option | 6.317 | 6.317 | 4.826 … 7.985 | 5.112 … 7.521 | 5.283 … 7.447 | <92 ppm (4 of 100,000 samples; 95% upper bound) | 1.28 ± 0.01 | LSL 5.000 | MC | **MARGINAL** |
| T09H-relfloor (firmware round 2: floor = calibrated contact - 6.2 deg, so the squeeze is limited by u_max alone) | option | 6.317 | 6.317 | 4.826 … 7.985 | 5.112 … 7.521 | 5.283 … 7.447 | <92 ppm (4 of 100,000 samples; 95% upper bound) | 1.28 ± 0.01 | LSL 5.000 | MC | **MARGINAL** |
| T09H-r15p8 (squeeze cap sized for the ruled 8 N: 3.785 deg (basis u_max_8_deg, the firmware compiled with F_CAP_N 8)) | scenario | 4.912 | 4.912 | 4.183 … 5.333 | 4.183 … 5.333 † | 4.493 … 5.332 | 60.5 % | -0.21 ± 0.00 | LSL 5.000 | MC | **FAIL** |
| T09P Peak pad force when the FSR over-force trip fires (R15) | baseline | 8.899 | 8.908 | 7.045 … 11.105 | 7.045 … 11.040 † | 7.308 … 10.636 | 88.5 % | -0.52 ± 0.00 | USL 8.000 | MC | **FAIL** |
| T09P-r15p8 (R15 ruled: cap 8 N) | scenario | 8.899 | 8.908 | 7.045 … 11.105 | 7.045 … 11.040 † | 7.308 … 10.636 | 88.5 % | -0.52 ± 0.00 | USL 8.000 | MC | **FAIL** |
| T09P-trip7 (firmware: F_TRIP_N 7.0, F_TRIP_MS 10) | option | 7.759 | 7.767 | 6.364 … 9.426 | 6.364 … 9.253 † | 6.577 … 9.061 | 34.6 % | 0.18 ± 0.00 | USL 8.000 | MC | **FAIL** |
| T09P-trip55 (firmware: F_TRIP_N 5.5, F_TRIP_MS 10, against the ruled 8 N cap) | scenario | 6.259 | 6.266 | 5.000 … 7.760 | 5.000 … 7.689 † | 5.182 … 7.439 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.48 ± 0.01 | USL 8.000 | MC | **PASS** |
| T09P-floor49 (firmware: trip 7.75 N / 20 ms, peak bounded by the jaw floor theta_c0 - 4.9 deg (JAW_FLOOR_BELOW_C0_DEG)) | option | 6.359 | 6.360 | 4.865 … 8.031 | 5.150 … 7.569 | 5.307 … 7.480 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.46 ± 0.00 | USL 8.000 | MC | **PASS** |
| T09T Close time to first contact after calibration (R19) | baseline | 0.507 | 0.507 | 0.463 … 0.551 | 0.477 … 0.537 | 0.477 … 0.536 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 8.28 ± 0.10 | USL 0.750 | MC | **PASS** |
| T09T-r19p075 (Historical R19 limit: 0.5 s (legacy r19p075 scenario id)) | scenario | 0.507 | 0.507 | 0.463 … 0.551 | 0.477 … 0.537 | 0.477 … 0.536 | 76 % | -0.24 ± 0.00 | USL 0.500 | MC | **FAIL** |
| T09T-slow3 (firmware: JAW_SLOW_ZONE_DEG 6 -> 3 (0.125 s less: 3 deg at 120 instead of 20 deg/s)) | option | 0.382 | 0.382 | 0.338 … 0.426 | 0.352 … 0.412 | 0.352 … 0.411 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 12.54 ± 0.15 | USL 0.750 | MC | **PASS** |
| T10 Finger pad parallelism in the closing plane (root gap at tip contact) | baseline | 0.643 | 0.643 | -0.805 … 2.091 | 0.047 … 1.239 | 0.046 … 1.240 | 3.57 % | 0.60 ± 0.00 | LSL -1.000, USL 1.000 | MC | **FAIL** |
| T10-toein (contact faces toed in 0.44 deg: parallel at first contact) | option | 0.000 | 0.000 | -1.448 … 1.448 | -0.596 … 0.596 | -0.596 … 0.597 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.67 ± 0.01 | LSL -1.000, USL 1.000 | MC | **PASS** |
| T10B Fingertip out-of-plane mismatch (Z) from pin perpendicularity and knuckle wobble | baseline | 0.000 | 0.002 | -2.465 … 2.465 | -1.038 … 1.038 | -1.024 … 1.022 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.95 ± 0.01 | LSL -2.000, USL 2.000 | MC | **PASS** |
| T11 Radial keep-out, r 11.6 hub band (H-1..H+1) vs wrist-link lip r 12.6 | baseline | 1.000 | 0.733 | 0.200 … 1.150 | 0.388 … 0.962 | 0.453 … 1.006 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 2.26 ± 0.01 | LSL 0.100 | MC | **PASS** |
| T11-band2 (second band: hub r 14.6 (H+1..H+5.0) vs lip r 15.4, not a first layer) | scenario | 0.800 | 0.633 | 0.100 … 1.050 | 0.288 … 0.862 | 0.353 … 0.906 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.90 ± 0.01 | LSL 0.100 | MC | **PASS** |
| T11-stock12 (pre-rev-A hub r 12.0) | rejected | 0.600 | 0.333 | -0.200 … 0.750 | -0.012 … 0.562 | 0.053 … 0.606 | 0.673 % | 0.83 ± 0.00 | LSL 0.100 | MC | **FAIL** |
| T12 Axial keep-out, gripper widens (r > 15) above the wrist-link lip top | baseline | 0.700 | 0.800 | 0.100 … 1.500 | 0.394 … 1.206 | 0.421 … 1.179 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.85 ± 0.01 | LSL 0.100 | MC | **PASS** |
| T12-stock45 (pre-rev-A widen at 4.5 above H) | rejected | 0.200 | 0.300 | -0.400 … 1.000 | -0.106 … 0.706 | -0.079 … 0.679 | 7.04 % | 0.53 ± 0.00 | LSL 0.100 | MC | **FAIL** |
| T12B Axial gap, gripper rim to servo-5 case top | baseline | 3.800 | 3.800 | 3.500 … 4.100 | 3.508 … 4.092 | 3.565 … 4.032 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 14.04 ± 0.04 | LSL 0.500 | WC | **PASS** |
| T13 Wrist-camera aim angle error (optional UVC bracket on the front-plate pad) | baseline | 0.000 | 0.001 | -3.033 … 3.033 | -1.686 … 1.686 | -1.637 … 1.624 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.83 ± 0.01 | LSL -3.000, USL 3.000 | MC | **PASS** |
| T13-notab (no locating tab: rotation set by 2 screws in Ø3.6 holes) | rejected | 0.000 | 0.008 | -6.983 … 6.983 | -6.983 … 6.983 † | -5.173 … 5.208 | 32 % | 0.58 ± 0.00 | LSL -3.000, USL 3.000 | MC | **FAIL** |
| T14 Gripper servo body in cradle fit (20.4 pocket, DS3218MG 20.1 wide) | baseline | 0.300 | 0.200 | -0.050 … 0.450 | 0.020 … 0.380 | 0.021 … 0.380 | 4.84 % | 0.55 ± 0.00 | LSL 0.000, USL 0.300 | MC | **FAIL** |
| T14-w205 (servo body 20.5 (actuators.csv A17) in the rev A 20.4 pocket: it does not fit) | scenario | -0.100 | -0.200 | -0.450 … 0.050 | -0.380 … -0.020 | -0.379 … -0.020 | 100 % | -1.12 ± 0.01 | LSL 0.000, USL 0.300 | MC | **FAIL** |
| T14-w205p209 (servo body 20.5 in a pocket opened to 20.9 while the cradle still locates it: float over the 0.30 limit) | scenario | 0.400 | 0.300 | 0.050 … 0.550 | 0.120 … 0.480 | 0.121 … 0.480 | 50.1 % | -0.00 ± 0.00 | LSL 0.000, USL 0.300 | MC | **FAIL** |
| T14-boss (boss-located servo: only drop-in matters; pocket width from the case constants) | option | 0.300 | 0.200 | -0.050 … 0.450 | 0.020 … 0.380 | 0.021 … 0.380 | 420 ppm | 1.12 ± 0.01 | LSL 0.000 | MC | **MARGINAL** |
| T14-boss205 (boss-located servo (T14B-boss34) + pocket CAD 20.5: only drop-in matters) | option | 0.400 | 0.300 | 0.050 … 0.550 | 0.120 … 0.480 | 0.121 … 0.480 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.68 ± 0.02 | LSL 0.000 | MC | **PASS** |
| T14-cad205 (pocket CAD 20.5 while the cradle still locates the servo) | rejected | 0.400 | 0.300 | 0.050 … 0.550 | 0.120 … 0.480 | 0.121 … 0.480 | 50.1 % | -0.00 ± 0.00 | LSL 0.000, USL 0.300 | MC | **FAIL** |
| T14B Dog coupling — servo shaft offset from pin A against the dog slot clearance | baseline | -0.107 | 0.024 | -0.151 … 0.552 | -0.144 … 0.031 | -0.119 … 0.265 | 59.3 % | -0.06 ± 0.00 | USL 0.000 | WC | **FAIL** |
| T14B-w205 (servo body 20.5 (actuators.csv A17) in a pocket opened to 20.9, rev A cradle-located: servo float 0.15 per side) | scenario | -0.107 | 0.040 | -0.115 … 0.602 | -0.115 … 0.031 † | -0.117 … 0.304 | 66.1 % | -0.11 ± 0.00 | USL 0.000 | WC | **FAIL** |
| T14B-boss34 (servo located by its Ø9 boss in a reamed bore + dog slots 3.4) | option | -0.236 | -0.144 | -0.283 … 0.244 | -0.274 … -0.099 | -0.254 … 0.006 | 0.196 % | 0.96 ± 0.01 | USL 0.000 | WC | **FAIL** |
| T14B-boss (servo located by its boss, slots unchanged at 3.14) | option | -0.107 | -0.014 | -0.153 … 0.374 | -0.144 … 0.031 | -0.124 … 0.136 | 35.5 % | 0.11 ± 0.00 | USL 0.000 | WC | **FAIL** |
| T15 Knuckle end play at pin B (three standoffs, shims 0.85 per side) | baseline | 0.300 | 0.300 | -0.710 … 1.310 | -0.109 … 0.709 | -0.113 … 0.702 | 10.3 % | 0.50 ± 0.01 | LSL 0.050, USL 0.500 | MC | **FAIL** |
| T15-shimselect (shims picked at assembly from a 0.05-step set) | option | 0.300 | 0.300 | 0.245 … 0.355 | 0.247 … 0.353 | 0.255 … 0.346 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 4.35 ± 0.05 | LSL 0.050, USL 0.500 | MC | **PASS** |
| T16 Pin axis tilt, centre-distance change across the 8 mm gear face | baseline | 0.000 | -0.000 | -0.067 … 0.067 | -0.045 … 0.045 | -0.042 … 0.042 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.67 ± 0.01 | LSL -0.070, USL 0.070 | MC | **PASS** |
| T16-noream (line reaming skipped: plate holes as printed, front plate located by the pins) | scenario | 0.000 | 0.000 | -0.157 … 0.157 | -0.097 … 0.097 | -0.097 … 0.098 | 3.17 % | 0.71 ± 0.01 | LSL -0.070, USL 0.070 | MC | **FAIL** |
| T16B Knuckle sleeve running fit on its pin (bronze bush bore vs m6 dowel) | baseline | 0.003 | 0.003 | -0.008 … 0.014 | -0.008 … 0.014 † | -0.007 … 0.014 | 31.1 % | 0.29 ± 0.00 | LSL 0.000 | WC | **FAIL** |
| T16B-h8pin (ISO 2338 h8 pin 2.986-3.000 as the knuckle shaft) | option | 0.015 | 0.015 | -0.000 … 0.030 | -0.000 … 0.030 † | 0.001 … 0.029 | <30 ppm (0 of 100,000 samples; 95% upper bound) | 1.05 ± 0.00 | LSL 0.000 | WC | **PASS** |

† Distribution-adjusted RSS clipped to the worst-case band (a bounded term dominates).
<!-- tolstack:summary:end -->
