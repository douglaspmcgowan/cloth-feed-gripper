**What it proves:** that each sensor fault the firmware on `master` can detect ends in `FAULT` with the right name and a jaw that opens, instead of a grip on a lying sensor. Over-current is TP-05 and over-force is TP-04; this procedure covers the rest: shorted FSR, a bad FSR zero at calibration, a calibration outside its window, the open-limit switch (missing at HOME, or stuck closed), an open FSR, a frozen FSR reading and a current sensor that stops answering. About 45 min. Data sheet: [`../datasheets/TP-16.html`](../datasheets/TP-16.html) (CSV: `TP-16.csv`).

| | |
|---|---|
| Requirements | R15 (a failed FSR must not leave the force loop running blind), R18 (calibration window θ_c0 in −4…+4°), R20 (the over-current trip needs a live current sensor); firmware fault list in `firmware/gripper/events.cpp` (`kFaultNames`) |
| Pass | For each injected fault, in 3 of 3 trials: `EVT FAULT_<name>` logged, then `EVT ENTER_FAULT`, `ST` shows `fault=<NAME>`, and `th=` rises by 5° after the fault (except calibration faults, where no grip is running). FSR open has a second allowed outcome, below |
| Instrument | Firmware event and status log (1 ms timestamps, 20 ms status); labelled fault-injection breakout; 14 mm spacer; foam block |
| Sample size | 3 per fault: each is deterministic code on a single input, so a repeat only rules out a mis-set injection |

## Expected values (firmware on `master`, `config.h`)

| Injection | Expected log | Source |
|---|---|---|
| A. FSR connector shorted (node at 3.3 V, above `FSR_SHORT_MV` 2900 mV for `FSR_SHORT_MS` 5 samples) | `EVT FAULT_FSR_SHORT` about 5 ms after the short, `ENTER_FAULT`, `fault=FSR_SHORT` | [D] `fsr_filter.cpp` `fsrFilterSample`; `controls.md` 7 (host test: FAULT after 5 ms) |
| B. Pad loaded during `C` (unloaded node above `FSR_ZERO_MAX_MV` 150 mV) | `EVT FAULT_ZERO_BAD` | [D] `fsm.cpp` `coreTick` (CALIBRATE) |
| C. Spacer stack that puts θ_c0 outside −4…+4° (`CAL_C0_MIN_DEG`, `CAL_C0_MAX_DEG`) | `EVT FAULT_CAL_RANGE` | [D] `fsm.cpp` `calInWindow`; TP-04 notes the same fault with spacers in |
| D. Open-limit switch not closed at the open stop, **only on a build with `LIMIT_REQUIRED` 1 (shipped 0)** | `EVT FAULT_LIMIT` in HOME | [D] `fsm.cpp` row HOME / POSITION_REACHED. The shipped `config.h` has `LIMIT_REQUIRED` 0: record NOT RUN |
| E. Open-limit switch stuck closed (switch terminals jumpered) while the command is more than `LIMIT_STUCK_DEG` 10° below open for `LIMIT_STUCK_MS` 300 ms | `EVT FAULT_LIMIT` about 400 ms after `G 5` (83 ms to close past +10° at 120 °/s, then 300 ms), `ENTER_FAULT`, `fault=LIMIT` | [D] `fsm.cpp` `coreTick`; `controls.md` 7 (host test: FAULT 400 ms after `G`; simulation 394 ms) |
| F. FSR unplugged after calibration, foam block between the pads, `G 5`: the search runs `NO_CONTACT_MARGIN_DEG` 3° past θ_c0 with no FSR contact | Rail current at the end of the search ≥ `FSR_OPEN_I_A` 0.60 A: `EVT FAULT_FSR_OPEN`, `ENTER_FAULT`. Under 0.60 A (a servo whose drive conducts continuously, TP-07 F4 reading under 0.75 A): `WARN NO_CONTACT` and `ENTER_RELEASE`, a miss. Either way the jaw opens about 0.8 s after `G` | [D] `fsm.cpp` `gFsrBlind`; `controls.md` 7 (simulation: FAULT and unloaded at 796 ms with a discontinuous drive; a miss, peak 3.13 N, with a continuous drive) |
| G. FSR reading frozen: a **debug build** with `FSR_STUCK_TOL_MV` 200 (shipped 0.5), so a steady hold looks frozen. In HOLD, raw node above `FSR_STUCK_MV_MIN` 150 mV and within the tolerance sample to sample for `FSR_STUCK_MS` 500 samples | `EVT FAULT_FSR_STUCK` about 0.5 s after `ENTER_HOLD`, `ENTER_FAULT`, `fault=FSR_STUCK` | [D] `fsr_filter.cpp` `fsrFilterSample`; `controls.md` 7 (host test: FAULT after 501 ms; simulation 500 ms). On a live channel the ADC noise (4-20 mV RMS) keeps the shipped 0.5 mV check from firing, so only the debug build reaches it |
| H. Current sensor stops answering: INA219 found at boot (no `WARN INA219_ABSENT`), then its SDA wire pulled in IDLE | `EVT FAULT_I_SENSOR` about 120 ms after the pull (`I_SENSOR_FAIL_MS` 100 ms, read every `INA219_PERIOD_MS` 20 ms), `ENTER_FAULT`, `fault=I_SENSOR`. An INA219 missing at boot is not a fault: `WARN INA219_ABSENT` | [D] `fsm.cpp` `coreSampleCurrent`; `controls.md` 7 (host test: FAULT after 120 ms) |

## Equipment

The gripper on the bench (rail 6.50 V), `gripper_log.py`, a labelled fault-injection breakout, a finger-sized foam block, one 14 mm spacer plate (TP-04), a firmware build with `LIMIT_REQUIRED` 1 (shipped 0) for D (or skip it), and a debug build with `FSR_STUCK_TOL_MV` 200 (shipped 0.5) for G. The breakout has keyed connectors, shrouded test points and insulated latching switches for FSR signal-to-3V3, FSR open, limit open, limit closed and INA219 SDA open. Verify continuity and labels before connection. Write each debug build's commit and changed constant on the sheet, then restore the production build.

<!-- breakout:begin -->
### Fault-injection breakout build

Repository names the ESP32 pins but does not name physical connector families or connector pin numbers; label the harness ends with the signal names below and record the chosen connector/pin mapping on the enclosure. Do not invent or rely on an unrecorded pin number.

| Interrupted/injected line | Firmware name and endpoint | Switch | NORMAL circuit | Path voltage/current; minimum rating |
|---|---|---|---|---|
| FSR signal | `PIN_FSR_ADC`, GPIO34, FSR-divider node | One break-before-make SPDT, centre-off: common to GPIO34; throws to the FSR node and 3V3; centre = OPEN | GPIO34 connected to FSR node | 0-3.3 V, ADC leakage only; ≥5 VDC, ≥10 mA |
| Jaw-open limit | `PIN_LIMIT_OPEN`, GPIO26, switch-to-GND input | One break-before-make SPDT, centre-off: common to GPIO26; throws to the real limit switch and GND; centre = OPEN | GPIO26 connected to the real normally-open limit switch, which closes to GND at open stop | 3.3 V pull-up, <1 mA; ≥5 VDC, ≥10 mA |
| INA219 data | `PIN_I2C_SDA`, GPIO21, INA219 SDA | One SPST, normally closed, in series | GPIO21 connected to INA219 SDA | 3.3 V I2C, <1 mA; ≥5 VDC, ≥10 mA |

`PIN_I2C_SCL` is GPIO22 and remains uninterrupted. The breakout never carries the 6.5 V servo rail or either INA219 shunt/current path. Use latching switches whose position is visible. Put all conductors and terminals in a rigid, non-conductive enclosure; use keyed connectors, captive covers over test points, and clamp strain relief on both cable entries so a 20 N hand pull cannot load a solder joint or expose conductor.

**Pre-use inspection, USB and motor rail off:**

1. Covers fitted: PASS only when no bare conductor or probe-accessible live metal is visible; cable clamps resist a 20 N hand pull without movement.
2. NORMAL continuity: meter resistance is <1 Ω from each harness input to output for FSR, limit and SDA; record all three readings.
3. With the rail and USB off, select each path position before placing meter probes; never move a selector while taking a reading. Record this generated table:

| Pair | Selector state | Expected resistance | Tolerance |
|---|---|---:|---:|
| FSR node–GND | FSR NORMAL | 2.7 kΩ plus the FSR parallel path | 2.43–2.97 kΩ when the FSR is open/unloaded |
| FSR node–3V3 | FSR SHORT | continuity | <1 Ω |
| FSR node–3V3 | FSR OPEN | isolation | >1 MΩ |
| Limit–GND | LIMIT CLOSED | continuity | <1 Ω |
| Limit–GND | LIMIT OPEN | isolation | >1 MΩ |
| SDA input–SDA output | SDA NORMAL | continuity | <1 Ω |
| SDA input–SDA output | SDA OPEN | isolation | >1 MΩ |
| Any unrelated signal pair (FSR/limit/SDA) | all NORMAL, limit not at stop | isolation | >1 MΩ |

4. PASS the breakout only if every row passes and the enclosure labels match the recorded connector/pin mapping. Do not power a failed or uninspected breakout.
<!-- breakout:end -->

## Steps

Install the breakout with USB and the 6.5 V rail off, with all switches in NORMAL. Mechanically secure every connector and cover every test point before applying power. Start from IDLE (`S` shows `ST IDLE`), calibrated on bare pads (`C`). Log: `python docs/gripper/test/tools/gripper_log.py --port <gripper port> --out TP-16_log.csv`, then `STREAM 50`. For every electrical injection: rail off, select and mechanically secure the labelled path, rail on, then operate only its insulated switch. Rail off before changing or removing any connection. After each fault, rail off, return the switch to NORMAL, rail on, `H`, and check `ENTER_IDLE`.

**A. FSR shorted (3 trials).**

1. Rail off; select FSR SHORT on the breakout and mechanically secure its cover. Rail on, `G 5`, then in CLOSE operate the insulated FSR SHORT switch. Expect `EVT FAULT_FSR_SHORT` within about 0.1 s, then `ENTER_FAULT`, and `th=` rising by 5°.
2. `H`, check `ENTER_IDLE`. Repeat twice more.

**B. Bad zero (3 trials).**

3. Press the pad lightly (about 2 N, a thumb on finger B's pad) and send `C`. The unloaded reading is above the zero limit: expect `EVT FAULT_ZERO_BAD`. Release the pad, `H`, expect IDLE. Three times.

**C. Calibration outside its window (3 trials).**

4. Put the 14 mm spacer between the pads (θ_c0 would read above +4°). `C`: expect `EVT FAULT_CAL_RANGE`. Remove the spacer, `H`, IDLE. Three times.

**D. Limit switch missing at HOME (only with `LIMIT_REQUIRED` 1 (shipped 0)).**

5. Rail off; select LIMIT OPEN and secure it. Rail on, operate the insulated switch, then `H`: expect `EVT FAULT_LIMIT` during HOME. Rail off and return to NORMAL before recovery. Three times. Otherwise write NOT RUN on the sheet with the reason.

**E. Limit switch stuck closed (3 trials, shipped build).**

6. Flash the shipped `master` build, then check `EVT ENTER_IDLE` and a normal `G 5` hold. Rail off; select LIMIT CLOSED and secure it. Rail on, operate the insulated switch, then `G 5` with nothing between the pads. Expect `EVT FAULT_LIMIT` about 0.4 s later, `ENTER_FAULT`, `fault=LIMIT`, `th=` up by 5°. Rail off and return to NORMAL before recovery. Three times.

**F. FSR open (3 trials, shipped build).**

7. In IDLE and calibrated, rail off; select FSR OPEN, secure it, and place the foam block. Rail on, operate the insulated switch, then `G 5`. Expect, about 0.7-0.8 s later, either `EVT FAULT_FSR_OPEN` then `ENTER_FAULT`, or `WARN NO_CONTACT` then `ENTER_RELEASE`. Note which and the last `I=`. Rail off and return to NORMAL before removing the foam and recovery. Three times.

**G. FSR frozen (3 trials, debug build `FSR_STUCK_TOL_MV` 200 (shipped 0.5)).**

8. Flash the debug build, `C` on bare pads, put one ply of cloth between the pads, `G 5`. Expect `ENTER_HOLD`, then `EVT FAULT_FSR_STUCK` about 0.5 s later, `ENTER_FAULT`, `th=` up by 5°. `H`. Three times. Flash `master` back and check `EVT ENTER_IDLE` and a normal `G 5` hold before step 9.

**H. Current sensor lost (3 trials, shipped build).**

9. Boot with INA219 SDA in NORMAL and check there is no `WARN INA219_ABSENT`. In IDLE, operate only the insulated SDA OPEN switch. Expect `EVT FAULT_I_SENSOR` about 0.12 s later, `ENTER_FAULT`, `fault=I_SENSOR`. Rail off and return to NORMAL; power-cycle before `H` because the INA219 is probed at boot. Three times.

10. `python docs/gripper/test/tools/analyze_log.py faults TP-16_log.csv` lists every `FAULT_` and `ENTER_FAULT` with times.

## Data to record

Per trial: trial, injected fault (A-H), `EVT FAULT_<name>` seen (name; for F also `NO_CONTACT`), `ENTER_FAULT` ms (for F a miss: `ENTER_RELEASE` ms), `fault=` in the next `ST`, `th=` before and after, notes (for F: `I=` at the end of the search; for G and D: the debug build's commit).

## Pass / fail

Each fault is an attribute test (right fault name, jaw opens) with no measured margin, so U does not enter; INDETERMINATE means the log is not clear enough to call it.

- **PASS:** 3 of 3 trials show the expected `FAULT_<name>` followed by `ENTER_FAULT`, and (grip faults A, E, F, G) `th=` up by 5° ± 0.5°. For F, `WARN NO_CONTACT` followed by `ENTER_RELEASE` (then `th=` rises to the open stop, not by 5°) also passes when the `I=` at the end of the search is under 0.60 A (the firmware cannot tell an open FSR from a miss there; `controls.md` 7, O13); write which outcome on the sheet.
- **FAIL:** a trial shows no fault, a different fault name than the one expected, the jaw keeps closing after the injection, `th=` below θ_c0 − 6.2° (`JAW_FLOOR_BELOW_C0_DEG`; θ_c0 is `c0=` in `ST`), or, for F, `NO_CONTACT` with `I=` at or above 0.60 A.
- **INDETERMINATE:** the injection could not be confirmed (jumper intermittent, a second fault logged first, status lines missing). Redo the trial; do not count it.
- Sign-off: R15 gets "FSR short, bad zero, FSR open and FSR frozen detected" only if A, B, F and G pass; R20 needs H. A FAIL here is safety: the force loop could run on a dead sensor; tell the firmware owner and do not use the gripper on the arm.

## Hazards

- **Pinch:** the jaw closes at up to 120 °/s in steps 1, 6, 7 and 8. Hands out of the jaw; make every injection at the connector, not at the fingers.
- Never touch a live conductor. Connections change only with the rail and USB off; while powered, operate only an insulated breakout switch. The breakout never routes the 6.5 V rail or INA219 shunt leads.
- In F the pads close on foam with no force feedback; the search stops 3° past θ_c0 (simulated peak 3.1-6.0 N). Use foam, never a finger or a rigid part.
- Never leave a debug build on the gripper: it either never faults (`LIMIT_REQUIRED` 0 on D) or faults in every hold (G).

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| No fault in A, force reads 0 | The short is on the FSR side of the divider but the ADC still reads low: check the wiring against `config.h` (3V3 -- FSR -- node -- 2.7 kΩ -- GND) | Electrical / firmware owner |
| `FAULT_ZERO_BAD` never fires with a load | `FSR_ZERO_MAX_MV` too high for your pad preload | Firmware owner |
| `FAULT_CAL_RANGE` fires with no spacer | θ_c0 outside the window with bare pads: pads worn or wrong zero (TP-08) | Mechanical owner |
| E: no `FAULT_LIMIT` | Jumper on the wrong pins, or the switch disabled in the build (`LIMIT_ENABLED`) | Electrical / firmware owner |
| F: `NO_CONTACT` with `I=` ≥ 0.60 A | FSR-open guard not reached (state or event order); a firmware defect | Firmware owner |
| F: `FSR_CONTACT` logged with the FSR unplugged | The node floats instead of reading 0: check the 2.7 kΩ pull-down | Electrical owner |
| G: no `FAULT_FSR_STUCK` | Debug constant not in the flashed build, or ADC noise above 200 mV sample to sample (a wiring fault in itself) | Firmware / electrical owner |
| H: fault only after seconds | I²C timeout longer than `Wire.setTimeOut(5)` on this core | Firmware owner |
| `th=` does not rise after the fault | Back-off blocked, or `FAULT_BACKOFF_DEG` not applied | Firmware owner |
