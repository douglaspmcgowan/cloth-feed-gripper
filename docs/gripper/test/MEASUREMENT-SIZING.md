# Measurement sizing: can each instrument resolve its pass criterion?

Dated 2026-10-11. Every number below is printed by `test_plan.py` [D] from the components listed, each tagged [S] or [A]. The method is the GUM one in short form: each error source gets a half-width (rectangular, divided by √3) or a standard deviation (normal); they add as a root sum of squares into u_c; the expanded uncertainty is U = 2·u_c (about 95 %). Reference: JCGM 100:2008, *Guide to the expression of uncertainty in measurement*, https://www.bipm.org/en/committees/jc/jcgm/publications (described in our own words, not reproduced).

For TP-05, the analyser derives each run's uncertainty from the observed controller-clock gaps bracketing onset and back-off begin; interrupted streams are voided rather than assigned a fixed uncertainty.

## 0. Answer

- **Force.** The pinch probe (TAL220 10 kg bar load cell and HX711) has U ≈ 0.10 N from 5 to 10 N. The 5 N (R14), 8 N and 10 N (R15) limits are 50-90 times U, so it resolves every force criterion. A kitchen scale used as a force gauge would not: the pads squeeze, so a scale needs a lever fixture, and 1 g resolution with ±1-2 % accuracy [A] gives about ±0.1-0.2 N plus fixture error.
- **The FSR on finger B is not a measuring instrument here.** It is the sensor under test. Its error is what TP-01 measures.
- **Time.** The firmware's own event log (1 ms timestamps, FSR lag corrected) has U ≈ 3.6 ms; the 240 fps video ≈ 6.8 ms. The historical 0.5 s limit (superseded 2026-10-12) and ruled 0.75 s limit are 70-200 times U. Force-crossing times read from the 50 Hz status stream have U ≈ 13 ms.
- **R20 interval bound.** `analyze_log.py` reads both endpoints from `ST` lines: each line carries controller `millis()` (`gripper.ino` `statusLine`), not the CSV host time. The true onset and back-off each occur after the preceding 50 Hz sample and no later than the first line that shows the condition. If their unknown delays are `q_on,q_off ∈ [0,20 ms]`, the interval error is `q_on − q_off ∈ [−20,+20] ms`, even when correlated. Therefore U is a ±20 ms bound with 100 % coverage under uninterrupted `STREAM 50`; host timestamping, serial latency and the separate `EVT` timestamp do not enter.
- **Temperature.** A type K thermocouple on a MAX31855, checked in ice water, has U ≈ 1.6 °C, 37 times inside the 60 °C limit. An IR thermometer on a plastic case depends on the emissivity setting; it is a cross-check only.
- **Where the instrument is not the limit:** R16 at 6.35 V is within about one U of its limit in the analysis. R14 on the softest R12 finger is 2.2 U clear, so each hold is decidable, but too close for a 95/90 bound at a bench-sized n (section 3). No affordable instrument changes that; more trials and the design margin do. R15 with a half-reading FSR and ruled R19 to 5.0 N were in this list until the firmware began regulating 1 N above the setpoint (`F_HOLD_BIAS_N`); both now clear their limits by more than U.

## 1. Uncertainty budgets

`pad_force_*` and `pull_force_4N` are the probe. `finger_k_rel` and `stall_torque_rel` are relative (fractions of the value).

<!-- budgets:begin -->
| Budget | Component | Half-width (rect) or σ (normal) | Distribution | Standard uncertainty u |
|---|---|---|---|---|
| pad_force_5N | load cell combined error ±0.05 % FS [S TAL220] | 0.04903 | rect | 0.02831 |
| pad_force_5N | repeatability ±0.03 % FS [S TAL220] | 0.02942 | rect | 0.01699 |
| pad_force_5N | creep ±0.05 % FS per 3 min, over a 25.5 s hold [S TAL220] | 0.04903 | rect | 0.02831 |
| pad_force_5N | span drift ±0.05 % FS/10 °C, room ±5 °C [S TAL220, A room] | 0.02452 | rect | 0.01415 |
| pad_force_5N | HX711 noise 90 nV rms at 80 SPS, 3.3 V excitation [S HX711, D] | 0.002675 | normal | 0.002675 |
| pad_force_5N | reference masses: lab balance ±0.2 g on 500 g, g = 9.80 ±0.1 % [A] | 0.007 | rect | 0.004041 |
| pad_force_5N | contact point ±1 mm on the probe, 0.5 %/mm off-centre error [A, measured in TP-01 step 4] | 0.025 | rect | 0.01443 |
| pad_force_5N | **combined u_c / expanded U (k = 2)** |  |  | **0.0482 / 0.09641** |
| pad_force_10N | load cell combined error ±0.05 % FS [S TAL220] | 0.04903 | rect | 0.02831 |
| pad_force_10N | repeatability ±0.03 % FS [S TAL220] | 0.02942 | rect | 0.01699 |
| pad_force_10N | creep ±0.05 % FS per 3 min, over a 25.5 s hold [S TAL220] | 0.04903 | rect | 0.02831 |
| pad_force_10N | span drift ±0.05 % FS/10 °C, room ±5 °C [S TAL220, A room] | 0.02452 | rect | 0.01415 |
| pad_force_10N | HX711 noise 90 nV rms at 80 SPS, 3.3 V excitation [S HX711, D] | 0.002675 | normal | 0.002675 |
| pad_force_10N | reference masses: lab balance ±0.2 g on 500 g, g = 9.80 ±0.1 % [A] | 0.014 | rect | 0.008083 |
| pad_force_10N | contact point ±1 mm on the probe, 0.5 %/mm off-centre error [A, measured in TP-01 step 4] | 0.05 | rect | 0.02887 |
| pad_force_10N | **combined u_c / expanded U (k = 2)** |  |  | **0.05475 / 0.1095** |
| pull_force_4N | load cell combined error ±0.05 % FS [S TAL220] | 0.04903 | rect | 0.02831 |
| pull_force_4N | repeatability ±0.03 % FS [S TAL220] | 0.02942 | rect | 0.01699 |
| pull_force_4N | creep ±0.05 % FS per 3 min, over a 25.5 s hold [S TAL220] | 0.04903 | rect | 0.02831 |
| pull_force_4N | span drift ±0.05 % FS/10 °C, room ±5 °C [S TAL220, A room] | 0.02452 | rect | 0.01415 |
| pull_force_4N | HX711 noise 90 nV rms at 80 SPS, 3.3 V excitation [S HX711, D] | 0.002675 | normal | 0.002675 |
| pull_force_4N | reference masses: lab balance ±0.2 g on 500 g, g = 9.80 ±0.1 % [A] | 0.0056 | rect | 0.003233 |
| pull_force_4N | contact point ±1 mm on the probe, 0.5 %/mm off-centre error [A, measured in TP-01 step 4] | 0.02 | rect | 0.01155 |
| pull_force_4N | pull line within 5° of the feed direction (cosine) [A] | 0.01522 | rect | 0.008788 |
| pull_force_4N | **combined u_c / expanded U (k = 2)** |  |  | **0.04817 / 0.09633** |
| close_time_eventlog_s | millis() resolution 1 ms [D] | 0.0005 | rect | 0.0002887 |
| close_time_eventlog_s | FSR EMA lag 9.5 ms + 1 ms poll, corrected; residual ±3 ms [D controls.md 3, A residual] | 0.003 | rect | 0.001732 |
| close_time_eventlog_s | host line to dispatch, one loop pass ≤ 1 ms [A] | 0.0005 | rect | 0.0002887 |
| close_time_eventlog_s | **combined u_c / expanded U (k = 2)** |  |  | **0.00178 / 0.003559** |
| force_time_stream_s | `STREAM 50` status lines every 20 ms, crossing interpolated ±10 ms [D config.h] | 0.01 | rect | 0.005774 |
| force_time_stream_s | FSR EMA lag 9.5 ms, corrected; residual ±3 ms [D, A] | 0.003 | rect | 0.001732 |
| force_time_stream_s | FSR span error ±2 % at 5 N on a ~25 N/s rise, ±4 ms [A] | 0.004 | rect | 0.002309 |
| force_time_stream_s | **combined u_c / expanded U (k = 2)** |  |  | **0.006455 / 0.01291** |
| close_time_video_s | start frame ±1 frame at 240 fps [D] | 0.004167 | rect | 0.002406 |
| close_time_video_s | contact frame ±1 frame at 240 fps [D] | 0.004167 | rect | 0.002406 |
| close_time_video_s | **combined u_c / expanded U (k = 2)** |  |  | **0.003402 / 0.006804** |
| case_temp_C | type K + MAX31855 after an ice-point check, residual ±1.0 °C [A; unchecked ±2 to ±6 °C S Adafruit 269] | 1 | rect | 0.5774 |
| case_temp_C | MAX31855 resolution 0.25 °C [S Adafruit 269] | 0.125 | rect | 0.07217 |
| case_temp_C | bead-to-case contact under Kapton tape and paste ±1.0 °C [A] | 1 | rect | 0.5774 |
| case_temp_C | **combined u_c / expanded U (k = 2)** |  |  | **0.8197 / 1.639** |
| mass_moment_gmm | mass: balance ±0.2 g [A] | 69.96 | rect | 40.39 |
| mass_moment_gmm | COM: knife-edge balance ±1.0 mm [A] | 153.9 | rect | 88.85 |
| mass_moment_gmm | lever 309.1 mm from MuJoCo model, ±0.5 mm [D design_basis.py, A] | 76.95 | rect | 44.43 |
| mass_moment_gmm | **combined u_c / expanded U (k = 2)** |  |  | **107.2 / 214.5** |
| finger_k_rel | deflection: dial indicator ±0.02 mm on ~4.5 mm [A] | 0.0044 | rect | 0.00254 |
| finger_k_rel | load: hanger masses ±0.2 % [A] | 0.002 | rect | 0.001155 |
| finger_k_rel | load point ±0.5 mm at s = 40 mm, k ∝ s^-3 [D beam, A placement] | 0.0375 | rect | 0.02165 |
| finger_k_rel | root clamp compliance, read off the zero-load dial [A] | 0.01 | rect | 0.005774 |
| finger_k_rel | **combined u_c / expanded U (k = 2)** |  |  | **0.02258 / 0.04516** |
| stall_torque_rel | force at the lever (probe budget at 41 N) [D] | 0.003199 | normal | 0.003199 |
| stall_torque_rel | lever 50 mm: calipers ±0.05 mm and contact ±0.5 mm [A] | 0.01 | rect | 0.005774 |
| stall_torque_rel | lever perpendicular within 3° (cosine) [A] | 0.00137 | rect | 0.0007912 |
| stall_torque_rel | rail voltage ±0.05 V at 6.35 V; stall ∝ V [A DMM] | 0.007874 | rect | 0.004546 |
| stall_torque_rel | **combined u_c / expanded U (k = 2)** |  |  | **0.008054 / 0.01611** |
<!-- budgets:end -->

Notes on the [A] entries:
- The off-centre error of the probe (0.5 % per mm) is measured in TP-01 step 4 by hanging the same mass 2 mm either side of the contact mark; replace the assumption with that number.
- The thermocouple residual (±1 °C) holds only after the ice-point check in TP-07. Unchecked, Adafruit states ±2 to ±6 °C for type K [S].
- The finger load-point term dominates the stiffness budget because tip deflection goes as the cube of the load position; TP-12 uses a printed saddle that locates on the FSR puck seat.

## 2. Resolution against each criterion

"Limit / U" ≥ 10 means the instrument can resolve the number. "Margin / U" ≥ 1 means the result the analysis predicts lands outside the uncertainty band, so the test will give a clear verdict; below 1 the verdict is indeterminate unless the real gripper differs from the model. A negative margin means the analysis predicts a fail.

<!-- resolve:begin -->
| Test | Req | Quantity | Limit | Predicted | U (k = 2) | Limit / U | Margin / U | Predicted outcome | Resolves limit / verdict decidable | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| TP-01 | R14 | hold force, softest R12 finger | 5 N | 5.22 | 0.0964 | 52 | 2.24 | PASS | yes / yes | sim hold 5.22 N at k 0.88: margin 0.22 N, outside U (F_HOLD_BIAS_N regulates 1 N above the setpoint) |
| TP-01 | R14 | hold force, D7 finger (k 1.24) | 5 N | 6.03 | 0.0964 | 52 | 10.68 | PASS | yes / yes |  |
| TP-04 | R15 | peak force, FSR reading 50 %, k 1.63 (cap written 10 N) | 10 N | 9.66 | 0.109 | 91 | 3.09 | PASS | yes / yes |  |
| TP-04 | R15 | peak force, normal G 5, k 1.63 (cap written 10 N) | 10 N | 7.41 | 0.103 | 97 | 25.00 | PASS | yes / yes |  |
| TP-04 | R15 | peak force, FSR reading 50 %, k 1.63 (cap proposed 8 N) | 8 N | 9.66 | 0.109 | 73 | -15.18 | FAIL | yes / yes |  |
| TP-04 | R15 | peak force, normal G 5, k 1.63 (cap proposed 8 N) | 8 N | 7.41 | 0.103 | 77 | 5.66 | PASS | yes / yes |  |
| TP-02 | R14 | pull to slip (SF 2 at mu 0.4) | 4 N | 4 | 0.0963 | 42 | 0.00 | INDETERMINATE | yes / **no** | predicted equals the limit by construction; the measured mu (M2) decides |
| TP-03 | R19 | contact time, event log (R19 written (superseded 2026-10-12) 0.50 s) | 0.5 s | 0.59 | 0.00356 | 140 | -25.29 | FAIL | yes / yes |  |
| TP-03 | R19 | time to 4.5 N, stream (R19 written (superseded 2026-10-12) 0.50 s) | 0.5 s | 0.723 | 0.0129 | 39 | -17.27 | FAIL | yes / yes |  |
| TP-03 | R19 | time to 5.0 N, k ≥ 1.0 (R19 written (superseded 2026-10-12) 0.50 s) | 0.5 s | 0.718 | 0.0129 | 39 | -16.89 | FAIL | yes / yes |  |
| TP-03 | R19 | time to 5.0 N, k 0.88 (R19 written (superseded 2026-10-12) 0.50 s) | 0.5 s | 0.772 | 0.0129 | 39 | -21.07 | FAIL | yes / yes |  |
| TP-03 | R19 | contact time, event log (R19 proposed (ruled 2026-10-12) 0.75 s) | 0.75 s | 0.59 | 0.00356 | 211 | 44.96 | PASS | yes / yes |  |
| TP-03 | R19 | time to 4.5 N, stream (R19 proposed (ruled 2026-10-12) 0.75 s) | 0.75 s | 0.723 | 0.0129 | 58 | 2.09 | PASS | yes / yes |  |
| TP-03 | R19 | time to 5.0 N, k ≥ 1.0 (R19 proposed (ruled 2026-10-12) 0.75 s) | 0.75 s | 0.718 | 0.0129 | 58 | 2.48 | PASS | yes / yes | k 1.05 lands 32 ms under 0.75 s: decidable |
| TP-03 | R19 | time to 5.0 N, k 0.88 (R19 proposed (ruled 2026-10-12) 0.75 s) | 0.75 s | 0.772 | 0.0129 | 58 | -1.70 | FAIL | yes / yes |  |
| TP-07 | R26 | case temperature after 30 min (Fit B, 25 °C, Rth2 ×1) | 60 °C | 61.2 | 1.64 | 37 | -0.73 | INDETERMINATE | yes / **no** | model is an upper bound; spans 43-115 °C |
| TP-09 | R17 | moment arm r_c, both fingers (CAD nominal) | 65 mm | 65 | 0.0766 | 849 | 0.00 | INDETERMINATE | yes / **no** | CAD nominal sits on the limit: a perfect part reads INDETERMINATE; see Requested changes in the README |
| TP-09 | R10 | mass-moment, CAD revision B | 4.37e+04 g·mm | 5.33e+04 | 214 | 204 | -44.86 | FAIL | yes / yes | Predicted FAIL at full reach; disposition: prohibit holds beyond 284.1 mm COM reach and enforce the tighter work-cell fingertip limit |
| TP-12 | R12 | finger tip stiffness, low end | 0.88 N/mm | 1.07 | 0.0483 | 18 | 3.93 | PASS | yes / yes |  |
| TP-12 | R12 | finger tip stiffness, high end | 1.63 N/mm | 1.29 | 0.0583 | 28 | 5.84 | PASS | yes / yes |  |
| TP-13 | R16 | stall torque at 6.35 V | 1.98 N·m | 2.02 | 0.0326 | 61 | 1.23 | PASS | yes / yes | 1 % margin: run at 6.50 V too |
| TP-05 | R20 | back-off begins after over-current onset | 0.2 s | 0.14 | 0.02 | 10 | 3.00 | PASS | yes / yes |  |
| TP-13 | R27 | rail voltage band low end | 6.35 V | 6.5 | 0.0606 | 105 | 2.47 | PASS | yes / yes | TUR about 3: set the rail to 6.50 V with the DMM |
| TP-13 | R27 | rail voltage band high end | 6.65 V | 6.5 | 0.0606 | 110 | 2.47 | PASS | yes / yes | TUR about 3: set the rail to 6.50 V with the DMM |
<!-- resolve:end -->

## 3. Sample sizes

- **Measured numbers with a one-sided limit:** n is the smallest number of trials (3 to 30) for which the predicted mean plus k(n)·σ clears the limit, where k(n) is the one-sided tolerance factor for 95 % coverage at 90 % confidence (exact form from the noncentral t; `test_plan.py` checks it by a seeded Monte Carlo) and σ combines the predicted run-to-run scatter with the instrument's u_c. If no n up to 30 clears it, either the analysis predicts a fail (5 trials confirm it) or it predicts a pass that the bound cannot show at a bench-sized n; R14 on the softest finger pair is the one such case, and it is judged as a zero-failure run (below).
- **Predicted scatter:**
  - Close time: the servo reads the pulse once per 20 ms frame, so the frame phase at the command is uniform over 20 ms (σ 5.8 ms) [D]; servo variation 5 ms [A, replace with the TP-03 scatter]; total 7.6 ms.
  - Hold force: FSR span repeatability 2 % [A] plus the probe; the simulated sensor-noise scatter is under 0.03 N (`fw_sim.json`).
- **R14 hold, per finger pair:** the force is sized for the unfavourable finger as well as the favourable one. On the stiffer finger (k 1.24 N/mm, hold 6.07 N) n = 3 clears 5.0 N. On the softest (k 0.88 N/mm) the firmware holds at the squeeze cap (`FORCE_SAT`), 5.22 N: margin 0.22 N, 2.2 times the probe's U, so every hold's minimum is decidable on its own; but at σ 0.111 N the 95/90 bound needs k ≤ 1.95, which takes n 55. TP-01 therefore judges the softest pair as a zero-failure run on its hold minimums: 11 holds, every one PASS, shows R 0.80 at C 0.90; its bound is reported, not judged. 14 holds in all. Risk: at σ 0.111 N a single hold clears 5.10 N with p 0.86 and 11 in a row with p 0.19. That σ is the FSR-span loop scatter [A], which does not set a hold at the position cap; TP-01's measured scatter decides whether 11 is realistic. What changed: the firmware now regulates its FSR reading 1 N above the setpoint (`F_HOLD_BIAS_N`, `controls.md` 4.1). Before, the softest hold was 5.02 N, 0.02 N over the limit and inside U, so it was expected INDETERMINATE and 6 holds per pair (12) only gave an estimate.
- **Pass/fail functions (attribute tests):** zero failures in n trials shows reliability R at confidence C when R^n ≤ 1 − C. Functions: R 0.8, C 0.9 → 11 trials. Safety functions (over-force trip, stall back-off): R 0.9, C 0.9 → 22 trials.
- **Life (R25):** one unit with no failure demonstrates reliability R at T cycles with confidence C when (t/T)^β = ln(1 − C)/ln(R). With a wear-out shape β = 2 [A], R 0.9 and C 0.5, that is about 2.6e5 cycles for T = 1e5: about 12 days of continuous cycling at 4 s per cycle. Not affordable, so TP-06 is a 1e4-cycle screen and R25 rests on `dyno.md`.

<!-- samples:begin -->
| Case | n | Predicted margin | Rule |
|---|---|---|---|
| R19_written_contact | 5 | -0.09 | predicted to fail: 5 trials confirm the verdict |
| R19_written_F4p5 | 5 | -0.223 | predicted to fail: 5 trials confirm the verdict |
| R19_written_F5_k_ge_1 | 5 | -0.218 | predicted to fail: 5 trials confirm the verdict |
| R19_proposed_contact | 3 | 0.16 | tolerance bound clears |
| R19_proposed_F4p5 | 9 | 0.027 | tolerance bound clears |
| R19_proposed_F5_k_ge_1 | 6 | 0.032 | tolerance bound clears |
| R14_hold | 3 | 1.029 | tolerance bound clears |
| R14_hold_softest | 5 | 0.2162 | predicted to pass, but no n <= 30 brings the 95/90 bound inside the margin: 5 trials give the estimate |
| R14_hold_per_finger | 11 |  | 11 holds on the softest pair and 3 on the stiffest (k from TP-12) = 14 holds. Softest: predicted hold 5.216 N, margin 0.216 N = 2.2 U, so each hold's F_min is decidable on its own; the 95/90 bound needs n 56 (k <= 1.95 at sigma 0.111 N), so the pair is a zero-failure run on F_min: 11 holds, every F_min PASS shows R 0.80 at C 0.90; its bound L is reported, not judged. Risk: at that sigma one hold clears 5.0 N + U with p 0.86 and 11 clean holds with p 0.19; the sigma is the FSR-span loop scatter, and this finger holds at the squeeze cap (FORCE_SAT), where position, not the FSR, sets the force, so TP-01's measured scatter decides whether the run is realistic. Stiffest: the 95/90 bound clears 5.0 N at n 3 (margin 1.029 N) |
| R15_written_peak_normal | 3 | 2.586 | tolerance bound clears |
| R15_proposed_peak_normal | 4 | 0.5856 | tolerance bound clears |
| R26_temp | 1 |  | one 30 min soak; repeat once if within 5 °C of 60 °C [A] |
| attribute_function | 11 |  | zero failures shows R 0.80 at C 0.90 |
| attribute_safety | 22 |  | zero failures shows R 0.90 at C 0.90 |
| R25_life | 256492 |  | Lipson single-unit zero-failure test: (t/T)^beta = ln(1-C)/ln(R) |
<!-- samples:end -->
