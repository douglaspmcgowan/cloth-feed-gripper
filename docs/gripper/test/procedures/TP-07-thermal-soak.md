# TP-07 Thermal soak over the duty cycle

<!-- hardware-scope:begin -->
**Hardware scope — arm: `off`; gripper: `on-arm`.** The arm is off and its power supply is disconnected for this whole procedure. The gripper is installed on the arm; obey the arm scope above before applying power.
<!-- hardware-scope:end -->

<!-- procedure-body:begin -->
**What it proves:** the servo case stays at or under 60 °C after 30 min of the design-basis duty cycle (35 s cycle, 25.5 s hold at 5 N), and how much current the servo draws in the hold (M7). The cool-down afterwards gives the case's thermal time constant and resistance, which replace the borrowed constants in `dyno.md`. The analysis expects a likely **fail**: its model puts the case at 42.8-166.6 °C over 12 cases (an upper bound). About 50 min plus 20 min cool-down. Data sheet: [`../datasheets/TP-07.html`](../datasheets/TP-07.html) (CSV: `TP-07.csv`).

| | |
|---|---|
| Requirements | R26 (servo case ≤ 60 °C after 30 min of the DB section 7 cycle at LC1); measurement M7 (servo heating in the hold, hold current, cool-down constant) |
| Pass | Case at 30 min ≤ 58.4 °C (60 − U) **and** printed mount ≤ 48.4 °C (50 − U, bare PETG; ≤ 58.4 °C with the C1 metal sleeves); report ambient |
| Instrument | Two type K thermocouples on MAX31855 boards (`probe.ino`): case and mount, U = 1.6 °C each after the ice-point check [D `test_plan.py`]; IR thermometer as a cross-check only |
| Sample size | 1 soak of 30 min; 1 repeat if the result is within 5 °C of 60 °C [A] |

## Expected values (from the analysis; a result far from these means a setup error)

| Case (dyno two-node model, motor housing node = upper bound on the outer case) | 30 min, °C | Source |
|---|---|---|
| Fit B (2.2 A stall), 25 °C ambient, Rth2 22 K/W | **62.8** (predicted fail, margin/U −1.7) | [D] `test_plan_out.json` → `expected.thermal`, `dyno.md` 4 |
| Fit A (3.77 A stall), 25 °C, Rth2 22 K/W | 96.2 | same |
| Rth2 halved, 25 °C: Fit B / Fit A | 42.8 / 56.9 (the only passing cases at 25 °C) | same |
| All 12 cases (2 fits × 25 / 40 °C × Rth2 × 0.5 / 1 / 1.5) | 42.8-166.6 | `expected.thermal_range_C` |
| Hold motor current | 0.80 A (Fit B) to 1.35 A (Fit A) | [D] `dyno.md` 0 |
| Housing time constant τ_h | 450 s (7.5 min) | [A] `dyno.md` 1, borrowed from a maxon structure |

**Limits (`analysis/thermal.md` section 3 and the R26 note):** servo case 60 °C (R26); printed mount (PETG cradle seat under the servo ear screws) 50 °C bare, 60 °C with the C1 metal sleeves; servo rating 70 °C. The predicted 30-min values at 25 °C ambient with no back-off are case 71 °C / mount 67.5 °C (Fit A) and 50.7 / 48.9 °C (Fit B); the dyno values below are the older upper bound.

## Equipment

Two thermocouples (type K bead, Adafruit 270) and two MAX31855 boards on the `probe.ino` board (case and mount; its relay cuts the servo rail at the trip temperatures, see TP-06), the TP-01 pinch probe (on the same board), crushed ice and water in an insulated cup, thermal paste, Kapton tape, IR thermometer, DMM, bench supply 6.5 V with a current readout, laptop with two `gripper_log.py` terminals, a timer.

## Setup

```
 Servo inside the housing: case bead on the centre of the exposed top face of the aluminium
 middle shell, 14 mm behind the seat (thermal.md section 6, the same place as TP-06), under
 Kapton tape on a dab of paste.

        +-------------------------+
        |  servo case             |  output spline end
        |                [bead]<--+-- Kapton tape, paste under the bead
        |  motor end              |
        +-------------------------+
     ambient: IR thermometer reading, or a second bead in air 20 cm away, shaded

 Mount bead (the hottest contact of the printed part): in the 1 mm hole drilled from the front
 face of the cradle seat to 0.5 mm short of one servo ear (C3 in thermal.md), the ear that
 sits on the motor end. This is where the servo case heat enters the PETG and where the
 screw clamp is; it is the creep-critical spot. Paste in the hole, Kapton over the mouth.
```

0. **Fill the header block** of the data sheet (README "Session header" says where each value comes from): date, tester, unit serial, firmware commit, ambient °C, supply voltage at the servo (step 3 below, DMM), instrument ids with calibration dates (both thermocouples, the DMM; the ice-point offsets from step 1), and the FSR calibration id from `FSR-CAL.csv` (the pinch probe and `C` in step 3 use the calibrated FSR).
1. **Ice-point check.** Fill the cup with crushed ice, top up with cold water, stir. Put the bead in the middle, not touching the cup; stir and read for 2 min. Record the mean. It must read 0 ± 1 °C; record the offset and subtract it from every reading. Outside ±1 °C: replace the thermocouple or the MAX31855.
2. Dry the bead. Fix it to the case as drawn. Reach the case through the housing opening; if the case face is covered, use the nearest exposed face and note which.
3. Gripper on the bench (or on the arm with the arm unpowered and disconnected), gripper rail 6.50 V at the servo connector (DMM), switched through the probe board's relay (TP-06 cutoff section). Probe between the pads (TP-01 step 6, so the soak holds a real 5 N; this is the one place `C` runs with the probe in), then run TP-01 step 8 (`CALF`) and note the FSR calibration id for the header. Room still: no fan or draught on the gripper. Open a terminal on the probe board (`gripper_log.py --port <probe port> --out TP-07_pre.csv`), type `l 61.6 51.6` (the FAIL thresholds, below), then `e`: it answers `# RAIL ON` once both beads read under 45 °C. Close that terminal before step 2 (only one program may hold the probe port).
4. Note the start temperature: case, mount and ambient must agree within 1 °C (servo cold). If the C3 hole is not drilled, tape the bead to the seat face next to the ear screw and write that on the sheet (reads low: the hole reading is the one the limit is written for).

## Steps

**A. 30-minute soak.**

1. Only one terminal: gripper plus probe board, `python docs/gripper/test/tools/gripper_log.py --port <gripper port> --out TP-07_log.csv --sequence soak --minutes 30 --probe-port <probe port> --probe-out TP-07_probe.csv --stop-case-c 61.6 --stop-mount-c 51.6`. It sends `STREAM 2` (status twice a second, with `I=`), repeats the DB section 7 cycle (`G 5`, hold 25.5 s from HOLD, `R`, rest to 35 s), logs the probe lines (`ms,force_N,case_C,mount_C,rail_on`) itself, and ends the run, opening the jaw, if the case reads ≥ 61.6 °C or the mount ≥ 51.6 °C (≥ 61.6 °C with the C1 sleeves: pass `--stop-mount-c 61.6` and send `l 61.6 61.6`).
2. Every 5 min (0, 5, ... 30): record the case and mount thermocouple readings, ambient, an IR reading of the case next to the bead (emissivity 0.95 [A], plastic), the rail voltage on the DMM, the supply's current readout, and the cycle count the script prints.
3. **A stop is a result.** The stop thresholds are the FAIL thresholds (60 + U = 61.6 °C case; 50 + U = 51.6 °C mount bare, 61.6 °C with sleeves), so if the rig stops the run the answer is FAIL, and you record the time and which bead tripped. A run that reaches 30 min is judged on the readings by Pass / fail below. The probe board itself cuts the rail at the same thresholds. Afterwards check that θ_c0 (`C`, bare pads) has not moved; the servo rating is 70 °C and PETG's heat-deflection point is 65 °C at 1.8 MPa (`thermal.md` section 3).

**B. Cool-down (20 min).**

4. When the script ends at 30 min, open a terminal on the probe board (`gripper_log.py --port <probe port> --out TP-07_cool.csv`), type `x` (rail off; the ESP32 and the probe board stay on) and keep logging both beads for 20 min. Do not move the gripper.

## Data to record

Rows every 5 min of the soak and every 2 min of the cool-down: time, case temperature and mount temperature (offsets applied), ambient, IR check, rail voltage, mean rail current over the last 5 min (from the `ST` `I=` values), cycles done, notes. Also write on the sheet: whether the C1 metal sleeves are fitted (decides the mount limit), whether the C3 hole is drilled, the hold current, the firmware's `Ih=` reading and the drive regime it gives, τ and Rth2, and the time and bead if the rig stopped the run. Keep the CSV logs and the ice-point readings.

## Calculation

- T_case(30) = thermocouple reading at 30 min, minus the ice-point offset.
- Rise ΔT = T_case(30) − T_amb. Information only: T_case at a 40 °C ambient ≈ T_case(30) + (40 − T_amb) [A: the rise does not depend on ambient]; DB section 6 allows ambient up to 40 °C.
- Hold current (M7): `python docs/gripper/test/tools/analyze_log.py hold-current TP-07_log.csv` (mean `I=` in HOLD, from `ENTER_HOLD` + 1 s to the `R`, over the last 5 holds).
- Drive regime (F4, `thermal.md` F4; `controls.md` 4.3): the same command also prints the firmware's own hold-current reading, the `EVT HOLD_I <ms> <A>` line 0.3 s into each HOLD (100 ms of rail current with the back-off off, `HOLD_I_AVG_MS`) and the `Ih=` field that every later `ST` line carries (`-1.00` until measured). The soak runs with the F1 back-off off (`HOLD_BACKOFF_ENABLED` 0 at boot; send `BACKOFF 0` if anything turned it on), so `Ih=` is the F4 reading. Mean `Ih=` under 0.75 A: the servo drive conducts continuously (rail ≈ motor current² / stall current); over 0.75 A: discontinuously (rail = motor current); the tool prints which, or INDETERMINATE within the INA219's U of 0.75 A. Write the mean `Ih=` and the regime on the sheet (`hold_Ih_A`, `drive_regime`): it decides the FSR-open check (TP-16 F, 0.60 A) and the F1 factor.
- Time constant: τ = time after rail-off for the case to fall 63 % of ΔT (to T_amb + 0.37·ΔT).
- Rth2 ≈ ΔT / P with P = rail voltage × mean rail current over the last 5 min [D, equation: all rail power ends up as heat inside the case in a static hold]. Compare with the 22 K/W and 450 s in `dyno.md`.

## Pass / fail

- **R26 case (limit 60 °C, U 1.6 °C):** PASS T_case(30) ≤ 58.4 °C; FAIL ≥ 61.6 °C; INDETERMINATE between.
- **Mount limit (U 1.6 °C):** bare PETG, limit 50 °C: PASS T_mount(30) ≤ 48.4 °C, FAIL ≥ 51.6 °C. With the C1 metal sleeves, limit 60 °C: PASS ≤ 58.4 °C, FAIL ≥ 61.6 °C. Between is INDETERMINATE. Which limit applies is decided by whether the sleeves are fitted: write it on the sheet.
- The numbers above are rounded to 0.1 °C (U is 1.64 °C); within 0.1 °C of a threshold use the tool, which is exact.
- **Overall:** the worse of the two (any FAIL fails; else any INDETERMINATE). Check one reading by hand: `python docs/gripper/test/tools/analyze_log.py judge --value 49.0 --limit 50 --u 1.639 --side upper`.
- **Repeat once** (after a full cool-down) if T_case(30) is 55-65 °C or T_mount(30) is within 5 °C of its limit; report both.
- Always report the ambient, the 40 °C extrapolation, the hold current, the `Ih=` reading and drive regime, τ and Rth2.

## Hazards

- **Burns:** the case can pass 60 °C; touch it only with the IR thermometer.
- **Pinch:** the jaw cycles every 35 s for 30 min. Hands out; the probe stays on its foam.
- **Housing creep:** see step 4. Stop at 70 °C.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| Case over 60 °C at 30 min | Hold current too high for the case (dyno predicted it). Options: shorter hold, the back-off-on-friction firmware option (`dyno.md` 4), a bigger servo | Actuator / electrical owner, DB owner (R26) |
| Hold current far above 1.35 A | Over-squeeze (check the probe force), or binding pins | Controls owner; mechanical owner |
| Temperature still rising steeply at 30 min | τ much longer than 7.5 min: R26 at 30 min understates the steady state | Actuator owner |
| IR and bead differ by > 5 °C | Bead not seated, or IR emissivity wrong | Re-seat the bead, repeat |
<!-- procedure-body:end -->
