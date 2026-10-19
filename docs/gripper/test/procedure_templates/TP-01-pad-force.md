**What it proves:** the true force between the pads, measured by a load-cell probe, against what the firmware commands and what its FSR reads. It calibrates the FSR span, then shows the {{tp01.limit_display}} hold of R14. About 64 min for its 14 holds (`test_plan.py`: the 62 min first sized for 12 holds plus 31.5 s per further hold); the data sheet has one row per hold. Data sheet: [`../datasheets/TP-01.html`](../datasheets/TP-01.html) (CSV: `TP-01.csv`).

| | |
|---|---|
| Requirements | R14 (hold ≥ {{tp01.limit_display}} per pad), R3 (analog input trace); measurements M11 (FSR curve), M18 (train efficiency, optional) |
| Pass | Every probe sample of each 25.5 s `G 5` hold ≥ {{tp01.limit_display}} **on each of two finger pairs: the softest and the stiffest by the TP-12 k** (the pad force is the same on both pads, but the finger spring sets how closely the loop holds it). Stiffest pair: also the 95 %/90 % lower tolerance bound of its hold minimums ≥ {{tp01.limit_display}}. Softest pair: a zero-failure run, every hold minimum PASS; its bound is reported, not judged |
| Instrument | Pinch probe (TAL220 10 kg + HX711), expanded uncertainty U = {{tp01.probe_u}} at {{tp01.hold_limit}} [D `test_plan.py`] |
| Sample size | 14 holds: **11 on the softest pair, 3 on the stiffest**. Stiffest (sized at k 1.24 N/mm, hold 6.07 N): n = 3 is the smallest n whose bound clears {{tp01.limit_display}}. Softest (k 0.88 N/mm, holds at the squeeze cap, `FORCE_SAT`): predicted hold 5.22 N, margin 0.22 N = 2.2 U, so each hold is decidable on its own, but the bound would need n 55 at σ 0.111 N; it is judged as a zero-failure run, and 11 clean holds show R 0.80 at C 0.90. Risk: at σ 0.111 N, 11 clean holds has p 0.19; that σ is the FSR-span loop scatter, which does not set a hold at the position cap, and TP-01's measured scatter decides it. <!-- prediction-history:begin -->History generated here.<!-- prediction-history:end --> |

## Expected values (from the analysis; a result far from these means a setup error)

| Quantity | Expected | Source |
|---|---|---|
| Hold force on a D7 finger (k 1.05-1.24 N/mm) | 6.07-6.20 N | [D] `fw_sim.json` via `test_plan_out.json` → `expected.close` |
| Hold force at the R12 extremes (k 0.88 / 1.63) | 5.22 (at the squeeze cap, `FORCE_SAT`) / 6.00 N | same |
| Peak during the close | 5.22-7.41 N (7.41 on the stiffest finger) | same |
| FSR reading in HOLD | 6.0-6.6 N: setpoint + `F_HOLD_BIAS_N` 1.0 N, then the 0.6 N integrator deadband (`CTRL_I_DB_HI_N`); lower on a finger that holds at the squeeze cap (`FORCE_SAT`) | [D] `config.h`, `controls.md` 4.1 |
| `G 7` result on a 1.0 N/mm finger | stops at the squeeze cap with `FORCE_SAT`, about 6.0 N (0.5 + 1.135·k·4.87°, CTRL_U_MAX_DEG in `force_ctrl.h`) | [D] `controls.md` 0, equation |
| θ_c0 with the 6 mm probe between the pads | about +2.2° (pads 1 mm apart at 0°, about 2.3 mm of gap per degree near 0°) | [D] `finger.md` 6.1, linearised |
| Probe sensitivity | 33.6 µV/N at 3.3 V excitation; noise 0.003 N rms | [D] `test_plan.py` from [S] TAL220 and HX711 datasheets |

## Equipment

Pinch probe (built below), second microcontroller running `../tools/probe/probe.ino`, lab balance, masses (water bottles weighed to 0.1 g are fine), the gripper on the bench with its 6.5 V rail, a laptop running `../tools/gripper_log.py` on the gripper's USB port and a serial monitor on the probe's port, a vise, a foam block.

## The pinch probe (build once, about 30 min plus printing)

The pads squeeze, so the force has to pass *through* the load cell from one pad to the other. Two thin plates do that: plate P1 is screwed to the load cell's fixed end, plate P2 to its free end, and both stick out past the free end, one above the other with a 2 mm gap. Pad A pushes P1, pad B pushes P2; the cell carries the difference as shear, which is what a parallel-beam cell measures.

```
 Side view. Squeeze direction is up-down on this page.

                                   pad B (FSR side) pushes down
                                              |
   fixed-end block         TAL220 10 kg        v   contact mark, 30 mm past the free end
  [ M5 ][ M5 ]======================[ M5 ][ M5 ]=====================  P2: 2 mm Al (or 3 mm PETG), on the free end
  [    ]                                                    2 mm gap
  [ M5 ]=========================== 1 mm clear of the bar ===========  P1: 2 mm Al, on the fixed end, runs under the bar
                                              ^
                                              |
                                   pad A (nail side) pushes up

 Total thickness at the contact mark: 2 + 2 + 2 = 6 mm.
```

- Keep the stack at the pads **≤ 8 mm**. CALIBRATE searches from +5° and faults if θ_c0 is outside −4…+4° (`config.h` `CAL_C0_MIN_DEG`, `CAL_C0_MAX_DEG`). A 6 mm stack calibrates near +2.2°.
- Mark the contact point on both plates (pen line 30 mm past the free end, where the pad centres will sit).
- Plate tip deflection at 10 N is about 0.13 mm each for 2 × 15 mm aluminium on a 30 mm overhang [D, cantilever FL³/3EI with E 69 GPa], so the probe is about 40 N/mm, stiff against the 1 N/mm finger.
- Wire the TAL220 to the HX711 (red E+, black E−, green A+, white A−, as the TAL220 datasheet colours them [S]), the HX711 to the probe microcontroller (DT, SCK, 3.3 V, GND as set at the top of `probe.ino`).

## Setup

1. Gripper on the bench, wrist plate in a vise, fingers horizontal, so the pads squeeze sideways. Rail at 6.50 V (DMM). USB to the laptop: `python docs/gripper/test/tools/gripper_log.py --port <COM or /dev/tty...> --out TP-01_log.csv` (it timestamps every line; it also accepts interactive input).
2. Probe microcontroller on its own USB port, logging with its serial monitor or `gripper_log.py --port <probe port> --out TP-01_probe.csv`.
3. Let the load cell warm up powered for 10 min (zero drift settles).

## Steps

**A. Calibrate the probe (once per session).**

1. Clamp the fixed-end block in the vise with the squeeze axis vertical and P2 on top. Send `t` to `probe.ino` to tare.
2. Hang masses from a thread loop sitting on the P2 contact mark: 0, 102, 204, 510, 816, 1020 g (0, 1, 2, 5, 8, 10 N at g = 9.80 m/s²). Record the mean of 20 readings at each (`r` in `probe.ino` prints the raw counts). Then unload in reverse.
3. Fit force = (counts − zero)/scale by least squares. Residuals should be under 0.0{{tp01.hold_limit}}; a larger one means P1 or P2 touches the bar or each other.
4. **Off-centre check:** hang 510 g 2 mm toward the free end of the mark, then 2 mm away. Record both. The difference divided by 4 mm is the probe's off-centre sensitivity; `test_plan.py` assumes 0.5 % per mm [A]. If it is above 1 %/mm, add a printed V-notch on P2 so the pad lands on the mark.
5. Enter the fitted scale in `probe.ino` (`s <scale>`), or keep it and convert in the spreadsheet.

**B. Calibrate the gripper with the probe in place.**

6. Rest the probe on a foam block between the open jaws, contact marks centred on the pads, P1 toward finger A (nail), P2 toward finger B (FSR). The probe must be free to float: the foam carries its weight, the pads carry nothing else. Tare the probe (`t`) in this position.
7. Send `C`. The log shows `EVT CAL_THETA_C0 <ms> <deg>`. Expect about +2°. Record it.

**C. FSR curve and span (M11).**

8. Send `STREAM 50` (status every 20 ms). Send `G 5`. When the log shows `ENTER_HOLD`, wait 5 s, read the probe's mean force F_p over 2 s, then send `CALF <F_p>` (for example `CALF 5.31`). The reply `OK CALF span=<x>` is the new FSR span; record it. An `ERR CALF` means the FSR reads under 0.{{tp01.hold_limit}}: check the FSR wiring.
9. Send `R`, wait for `ENTER_RETRACT`, then `G 5` again. The FSR (`F=` in the `ST` lines) and the probe should now agree within 0.1 N in HOLD.
10. Step the command: `G 1`, `G 2`, `G 3`, `G 4`, `G 5`, `G 6`, `G 7`, holding each for 5 s. Record the FSR reading and the probe force for each. Record any `FORCE_SAT` (the squeeze cap reached before the setpoint; expected near 6.0 N on a 1.0 N/mm finger).
11. R3 evidence: save the log of step 10. The `ST` lines' `F=` values trace the analog input.

**C2. FSR nonlinearity and calibration record (M11).** Right after step 10, with the step-10 table (command 1 to 7 N, FSR reading and probe force):

- e_i = F_FSR,i − F_probe,i at each step. **Nonlinearity = max |e_i| over the 1 to 7 N steps, taken after the {{tp01.hold_limit}} `CALF`**, as a percentage of the 0 to 10 N span (so N ÷ 10 N × 100).
- **Acceptance: ≤ 5 % of the 0-10 N span, which is 0.{{tp01.hold_limit}}** [A]. Why: 0.{{tp01.hold_limit}} is the firmware's own hold band (`F_BAND_N`, `config.h`), so a larger error means the hold loop can sit outside its band against the true force. U = 0.10 N (probe). PASS if max |e| ≤ 0.40 N; FAIL if max |e| ≥ 0.60 N; INDETERMINATE between (repeat the steps; check the pad contact point). For the 8 N trip, read the same error at the TP-04 case-4 trip.
- **Write the calibration record** on the data-sheet header and as one row in `../datasheets/FSR-CAL.csv` (columns: `fsr_cal_id, date, tester, unit_serial, probe_cal_id, cal_force_N, span, trigger, e_1N … e_7N, max_abs_e_N, verdict`). The FSR calibration id is `FSRCAL-<yyyymmdd>-<n>`. The span is the `OK CALF span=<x>` value from step 8. **The firmware keeps the span in RAM only: it returns to 1.0 at every power-up** (`inputs.cpp`, `FSR_SPAN_DEFAULT`). After a power cycle, redo `CALF` at {{tp01.hold_limit}} (probe, or a 510 g dead weight on the pad) before any force test, and write a new row.

**Recalibration schedule.** Redo `CALF` (and the step-10 table) when any of these is true, and write a row with the trigger:

| Trigger | Rule |
|---|---|
| Before each session | At the start of every session that uses force (TP-01, 02, 04, 05, 03, 07), check the FSR against the probe or a 510 g weight at {{tp01.hold_limit}} |
| Drift | FSR − probe at {{tp01.hold_limit}} differs by more than 0.2{{tp01.hold_limit}} (half the hold band) → recalibrate; more than 0.{{tp01.hold_limit}} → the FSR or its mounting is suspect, tell the controls owner |
| Cycles | At every TP-06 checkpoint (0, 1e3, 5e3, 1e4 cycles); the FSR wears and the finger creeps |
| After an over-force event | After any `FSR_OVER`, `FAULT_OVERFORCE`, `FORCE_SAT` at a high force, or a TP-04 trial; after a power cycle; after the FSR is touched or re-taped; after a `FAULT_FSR_SHORT` |

**D. R14 holds.**

12. Eleven times on the softest finger pair, then three times on the stiffest (swap the fingers between sets; record `finger_pair` and the TP-12 k): `R`, wait for `ENTER_RETRACT` and `ENTER_IDLE` (or press START), then `G 5`. From `ENTER_HOLD`, hold for **25.5 s** (the DB section 7 feed hold), then `R`. Log the probe at 80 samples/s throughout.
13. After the last hold, take the probe out and send `C` to recalibrate on bare pads. The next procedures need the bare-pad θ_c0.

## Data to record

Per trial on the data sheet: command, FSR reading in HOLD, probe peak, probe hold mean and minimum over the 25.5 s, the state at the end, notes. Keep the raw `TP-01_log.csv` and `TP-01_probe.csv`, and the probe calibration (step 2 table, step 4 numbers).

## Calculation

- Probe force F = (counts − zero)/scale from step 3.
- Per finger pair, for each of its holds: F_min = lowest probe sample from `ENTER_HOLD` + 0.5 s to the `R` (the first 0.5 s is the end of the force ramp).
- Tolerance bound: L = mean(F_min) − k·s(F_min), with k = 5.31 for the stiffest pair's n = 3 (one-sided, 95 % coverage, 90 % confidence; `test_plan.py` prints k for any n).
- FSR error per step: e = F_FSR − F_probe. Span error = mean(e)/F at {{tp01.hold_limit}}.

## Pass / fail

- Limit {{tp01.limit_display}}, U = {{tp01.probe_u}}. Each F_min and the bound L are judged the same way; `analyze_log.py probe` prints one word per hold and an "R14 hold part" line.
- Judge each finger pair on its own (run `analyze_log.py probe` once per pair, with that pair's probe and gripper logs; add `--attribute` for the softest pair, which judges the hold minimums only and reports the bound); the R14 hold sign-off is the worse of the two pairs.
- **Pass R14 (hold part):** every F_min of both pairs ≥ {{tp01.pass_bound}} ({{tp01.limit_display}} plus the probe's U) **and** the stiffest pair's L ≥ {{tp01.pass_bound}}. TP-02 finishes R14 (slip).
- **Indeterminate:** any F_min (or the stiffest pair's L) from 4.90 to {{tp01.pass_bound}} (and no fail). The analysis puts every hold above {{tp01.pass_bound}}: 5.22 N on the softest finger (0.88 N/mm), 6.00-6.20 N from 1.05 to 1.63 N/mm. An indeterminate hold on the softest pair means its real scatter or its squeeze-cap force is off the prediction. Record "indeterminate" on the sign-off, not a pass, and report the finger stiffness from TP-12.
- **Fail:** any F_min ≤ {{tp01.fail_bound}}, or the stiffest pair's L ≤ {{tp01.fail_bound}}. For INDETERMINATE: run more holds (the bound tightens) or recalibrate the probe; do not record a pass.
- **R3:** pass if the step-10 trace rises by ≥ 300 mV of FSR node voltage from 0 to {{tp01.hold_limit}} [A threshold]; the `ST` lines report force, so read the node voltage with the DMM on the FSR divider at 0 and {{tp01.hold_limit}}.

## Hazards

- **Pinch:** the jaw closes at up to 120 °/s with up to 10 N at the pads. Keep fingers out of the jaw whenever the servo is powered; use the probe or a pencil to position things.
- The servo can jump when the rail comes up before the ESP32 drives the pulse. Power the ESP32 first, then the rail.
- Do not exceed 12 kg on the load cell (120 % safe overload [S TAL220]).

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| Probe reads well under {{tp01.hold_limit}} while the FSR reads {{tp01.hold_limit}} | FSR span wrong (re-run step 8) or FSR off the pad centre | Controls / firmware owner |
| Hold sits at 4.5-{{tp01.hold_limit}} even after `CALF` | Finger softer than R12 allows; `FORCE_SAT` in the log | Finger owner (TP-12 result) |
| Force oscillates by more than 0.3 N in HOLD | Servo deadband limit-cycling; loop gains (`controls.md` 4.2) | Controls owner |
| `FAULT_*` during `G 5` | See the event's fault code; an over-current fault here means the trip (3.3 A) sits under the real hold current (`controls.md` O6) | Firmware / electrical owner |
