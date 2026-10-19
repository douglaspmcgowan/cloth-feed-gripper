# TP-14 Work cell layout and arm load

<!-- hardware-scope:begin -->
**Hardware scope — arm: `gated`; gripper: `on-arm`.** The arm may be powered only by generated steps after their generated measurement gates pass. The gripper is installed on the arm; obey the arm scope above before applying power.
<!-- hardware-scope:end -->

<!-- procedure-body:begin -->
**What it proves:** that the arm sits where the cloth tension cannot overload its shoulder (R24), and replaces work-cell assumptions with measured M1, M3, M5, M5b and M19 values. CAD revision B fails R10 at full reach, so that powered pose is prohibited. About 40 min, on the arm. Data sheet: [`../datasheets/TP-14.html`](../datasheets/TP-14.html) (CSV: `TP-14.csv`).

| | |
|---|---|
| Requirements | R24 (work cell); measurements M1, M3, M5, M5b, M19 |
| Pass | R24: shoulder_lift axis within ±50 mm (vertically) of the cloth tension line; feed-pose reach ≤ 300 mm; shoulder load ≤ 50 % of stall (M19) |
| Instrument | Tape measure ±1 mm [A], plumb line, luggage scale or the TAL220 as a pull gauge, stopwatch, LeRobot motor-bus reads |
| Sample size | 1 layout; 3 load readings per pose |

## Expected values

| Quantity | Expected | Source |
|---|---|---|
| Arm servos and supply (M1) | STS3215 C001 at 7.4 V (alternatives C001 at 5 V, C018 at 12 V) | [A] DB D5, section 5 |
| Shoulder_lift stall, C001 at 7.4 V | 1.912 N·m; hold allowance 50 % = 0.956 N·m | [S] `research/so101.md`; [A] 50 % rule (DB section 5) |
| Bed height above the arm's table (M5) | 100 mm | [A] DB section 6 |
| Needle position (M5) | 159 mm left of the tower (Singer 4423 reference) | [S] DB section 6 |
| Feed speed at the demo setting (M5b) | 10 mm/s = 240 stitches/min × 2.5 mm, i.e. 40 stitches in 10 s | [A]/[D] DB section 6 |
| Process tension (M3) | 2 N | [A] DB LC4 |
<!-- current-prediction:begin -->
| Gripper, cloth and wiring: CAD revision B | 153.9 g | [D] `fitcheck.json` |
| COM past H: CAD revision B | 37.5 mm | [D] `fitcheck.json` |
| Full-extension mass-moment | 53342 g·mm = 122.0 % of the R10 budget (predicted FAIL) | [D] `fitcheck.json` |
| Full-extension shoulder torque | Not predicted here: the repository has no validated mapping from revision B mass-moment to total shoulder torque; measure at the safe pose and extrapolate as steps 8–10 specify | [A] explicit linear gravity scaling |
<!-- current-prediction:end -->
| Feed pose inside 300 mm reach | passes: allowance ≥ 217 g at 40 mm | [D] `torque_and_actuator.md` section 0 |

## Equipment

Tape measure, plumb line (a nut on a thread), spirit level, painter's tape, stopwatch or phone timer, luggage scale (0-5 kg) or the TAL220 + HX711 with an M5 eye bolt in the free end and `probe.ino`, a bulldog clip, the demo cloth, the laptop running LeRobot for the arm, the stock gripper if available (for the load reference in step 9).

## Setup

```
 Side view of the work cell (feed direction into the page at the needle).

        shoulder_lift axis  (+)--------- arm ---------\
              |   ^                                     gripper, pads on the cloth
              |   | h_off = axis height - bed height     |
   ===========|===v==========  cloth tension line: bed surface, through the needle
   [ arm base ]   |        [  sewing machine bed  ]  needle
   ===========|===========================================  table
              |<---------------- reach to the fingertip ------------->|
          shoulder_pan axis (vertical, plumb line)
```

1. Arm and machine on the table in the demo layout. Arm supply connected as in the demo.

## Steps

**A. Labels (M1).**

1. Read the label on the shoulder_lift servo (and one other arm servo): C001, C018 or other. Read the arm supply's label: voltage and current. Photograph both.

**B. Machine (M5, M5b).**

2. Bed height: tape from the table to the bed surface beside the needle plate, 3 readings.
3. Needle position: tape from the needle to the tower face, to the bed's front edge and to the bed's left end.
4. Feed speed: sew a scrap at the demo pedal setting for 10 s by stopwatch; count the stitches (mark the start). Measure the stitch length over 10 stitches with the tape. Speed = stitches × stitch length / 10 s. 3 runs.

**C. Process tension (M3).**

5. Clip the bulldog clip to the cloth's trailing edge and hook the luggage scale (or the TAL220 eye bolt, probe reader streaming) to it. Keep the scale in line with the feed, level with the bed, and let the machine feed at the demo speed while your hand moves with the cloth, keeping it taut and straight as the gripper will. The scale reads the pull the gripper must resist. Read the steady value over 5 s. 3 runs. Convert kg to N with × 9.81.

**D. Layout (R24).**

<!-- reach-rule:begin -->
The revision B R10 rule limits horizontal reach to **284.1 mm from the shoulder_lift axis to the gripper COM**. The fingertip is 58.5 mm beyond that COM (`fitcheck.json` pad position 96.0 minus COM 37.5), so the equivalent fingertip limit is 342.6 mm. The existing 300.0 mm fingertip rule is tighter. Step 7 measures to the **fingertip** with the arm unpowered, then records COM reach = fingertip reach − 58.5 mm.
<!-- reach-rule:end -->

6. Find the shoulder_lift axis height above the table (centre of the servo horn; tape from the table). h_off = axis height − bed height (step 2). [D `design_basis.py`: the ±50 mm rule is a vertical offset.]
<!-- feed-gate:begin -->
7. Turn the arm motor rail off. Put a rigid prop under the wrist link so the arm cannot drop, then place it by hand in the feed pose. Datum: shoulder_lift horn-screw centre. Measure horizontal fingertip reach using largest of three independent plumb-line placements. PASS if largest fingertip reach ≤ 297.0 mm; FAIL if largest fingertip reach ≥ 303.0 mm; INDETERMINATE in between or if spread > 4.0 mm. Do not energize or command this pose unless it passes. <!-- gate-record:tp14-feed -->
<!-- feed-gate:end -->

**E. Shoulder load (M19).** Read `shoulder_lift`'s present load and present current through LeRobot's motor bus (the same connection and config used for teleoperation; use its read call for the present-load and present-current items of the Feetech control table; do not write any register).

<!-- powered-poses:begin -->
8. Turn the arm motor rail off. Put a rigid prop under the wrist link so the arm cannot drop, then place it by hand in the farthest measurement pose. Datum: shoulder_lift horn-screw centre. Measure horizontal fingertip reach using largest of three independent plumb-line placements. PASS if largest fingertip reach ≤ 297.0 mm; FAIL if largest fingertip reach ≥ 303.0 mm; INDETERMINATE in between or if spread > 4.0 mm. Do not energize or command this pose unless it passes. <!-- gate-record:tp14-farthest --> The revision B full-extension pose (COM reach 346.6 mm) is therefore **not commanded or held with the rail on**.
9. Only after the feed pose gate and farthest measurement pose gate passed, turn the motor rail on. Command only the feed pose and the farthest measurement pose (target fingertip reach 297.0 mm), with gripper and cloth installed. Read shoulder load and current 3 times at each; hold each ≤ 10 s. No other powered pose is permitted by this procedure. <!-- poses:feed pose|farthest measurement pose gate-records:tp14-feed|tp14-farthest -->
10. Calculate the analysed full-extension torque as `T_full = T_arm,full + (T_meas − T_arm,meas) × r_g,full / r_g,meas`. `T_meas` is the step-9 reading converted using the documented servo-load calibration. `T_arm,meas` and `T_arm,full` are model assumptions from `docs/gripper/research/so101.md`: arm-only torque is 0.527 N·m at full extension and is scaled linearly by horizontal reach. `r_g,meas` is the measured horizontal shoulder_lift-to-COM reach; `r_g,full` is 346.6 mm. This is analysis only; full extension is not commanded.
<!-- powered-poses:end -->

## Data to record

One row per item: servo label, supply label, bed height, needle offsets, stitch count and length, feed speed, tension (3), shoulder axis height, h_off, reach (3), checked fingertip and COM reach before each powered pose, load and current readings per pose (3 each), reference readings, analysed full-reach result. Columns: item, measured, unit, limit, pass, notes.

## Calculation

- Feed speed v = n·ℓ/10 s. Tension F = 9.81·m_scale.
- Shoulder torque T = a + b·reading (step 9). Fraction of stall = T / 1.912 N·m (C001 at 7.4 V), or the stall of the variant read in step 1 (`so101.md`: C001 at 6 V 1.62 N·m; C018 at 12 V 2.94 N·m).

## Pass / fail

<!-- reach-pass:begin -->
- **R24 layout / R10 reach rule** (tape and repeated plumb-line placement U = 3 mm; use the largest of three reaches; spread over 4.0 mm is INDETERMINATE): **pass** if |h_off| ≤ 47 mm, computed COM reach ≤ 281.1 mm, and measured fingertip reach ≤ 297.0 mm. The fingertip criterion is tighter than the R10-equivalent 342.6 mm. **Fail** if |h_off| ≥ 53 mm, COM reach ≥ 287.1 mm, or fingertip reach ≥ 303.0 mm; **indeterminate** otherwise.
<!-- reach-pass:end -->
- **M19 / R24 load:** limit 50 % of stall (0.956 N·m on C001 at 7.4 V) in the feed pose. U of T = the load-register resolution plus the 3 repeats: use their spread as U. **Pass** if T + U ≤ limit, **fail** if T − U ≥ limit, else **indeterminate**. Report the step-10 analysed full-extension result too: TP-09's R10 result corresponds to full extension, which is analysed here and never commanded.
- **M1, M3, M5, M5b:** measurements, no pass; enter them in `cad/gripper/params.json` and re-run `design_basis.py` if they differ from the defaults. A tension over 2 N re-opens the slip margin of R14 (TP-02).

## Hazards

- **Arm:** a loaded shoulder near its limit can sag or fault. Keep clear of the arm, stop on any overload alarm, and never power the revision B gripper at full horizontal extension.
- **Sewing machine:** keep fingers off the needle; the arm must never reach under the presser foot.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| h_off over 50 mm | Arm base on a different surface than the machine; shim the base or the machine | Integration owner |
| Reach over 300 mm | Arm too far from the needle; move the base closer | Integration owner |
| Shoulder load over 50 % in the feed pose | Gripper heavier than the BOM (TP-09), or a 5 V C001 kit (M1) | DB owner |
| Tension well above 2 N | Presser-foot pressure or feed-dog drag; R14 slip margin shrinks | Grip / DB owner |
<!-- procedure-body:end -->
