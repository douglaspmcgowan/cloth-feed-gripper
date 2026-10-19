**What it proves:** how long the jaw takes from the `G 5` command at the open stop to touch the cloth, to reach 4.5 N and 5.0 N, and to enter HOLD; how fast the jaw moves over the last 3° before contact; and that one full cycle steps through the states in the design-basis order. R19 was ruled on 2026-10-12, so the requirement is **{{tp03.proposed_limit}} to 4.5 N and to 5.0 N**; every time is still also judged against the superseded 2026-10-12 **{{tp03.written_limit}} to contact (written)**. The analysis predicts a fail as written and a pass as ruled except to 5.0 N on the softest fingers (`test_plan_out.json` → `expected.close`). About 25 min. Data sheet: [`../datasheets/TP-03.html`](../datasheets/TP-03.html) (CSV: `TP-03.csv`).

| | |
|---|---|
| Requirements | R19 (close time, last 3° at ≤ 20 °/s), R6 (event-driven state machine: event order of one full cycle) |
| Pass | Ruled R19: upper 95 %/90 % tolerance bounds of the 4.5 N and 5.0 N times each ≤ {{tp03.proposed_limit}}. Historical contact bound ≤ {{tp03.written_limit}} is superseded 2026-10-12. Both: last 3° before contact: commanded speed 20 °/s (inspected, `JAW_SPEED_NEAR_DPS`) and the video fit v + 2.2 °/s ≤ 25 °/s. R6: `ENTER_` events in the DB section 8 order |
| Instrument | Firmware event log, U = 3.6 ms (contact); `STREAM 50` lines, U = 12.9 ms (force crossings); 240 fps video, U = 6.8 ms [D `test_plan.py`] |
| Sample size | 10 closes: the bound clears {{tp03.proposed_limit}} at n = 3 on the predicted 7.6 ms scatter; 10 estimate the scatter itself (`MEASUREMENT-SIZING.md` section 3) |

## Expected values (from the analysis; a result far from these means a setup error)

| Finger k (N/mm) | Contact | 4.5 N | 5.0 N | HOLD entry | Source |
|---|---|---|---|---|---|
| 0.88 (R12 min) | 0.510 s | 0.643 s | 0.691 s | 0.718 s | [D] `test_plan_out.json` → `expected.close` (firmware sim) |
| 1.05 (E56 + D7) | 0.510 s | 0.621 s | 0.637 s | 0.768 s | same |
| 1.24 (E67 + D7) | 0.507 s | 0.607 s | 0.616 s | 0.738 s | same |
| 1.63 (R12 max) | 0.503 s | 0.589 s | 0.595 s | 0.853 s | same |

- Ranges (`close_range`): contact 0.503-0.510 s; 4.5 N 0.589-0.643 s; 5.0 N 0.595-0.637 s at k ≥ 1.0 N/mm, 0.691 s at k 0.88; HOLD 0.718-0.853 s. Scatter between closes 7.6 ms (20 ms servo frame phase 5.8 ms [D], servo 5 ms [A]).
- Jaw speed: 21 °/s at contact + 3°, ≤ 20 °/s from contact + 2° (the jaw trails the 120 °/s command by about 7°) [D] `controls.md` 4.2, `config.h` `JAW_SLOW_ZONE_DEG`.
- Predicted verdicts: the historical comparison (superseded 2026-10-12) fails on every finger (contact > {{tp03.written_limit}}); the ruled requirement passes to 4.5 N and to 5.0 N on every finger in the R12 window. The latest is 5.0 N at k 0.88, 0.691 s; the 95/90 bound of ten closes is about 0.691 + 2.57 × 0.010 = 0.717 s (σ: 7.6 ms close scatter with the stream's u_c), under {{tp03.proposed_limit}}. What changed: the firmware now regulates its FSR reading 1 N above the setpoint (`F_HOLD_BIAS_N`), so the loop crosses 5.0 N on its way up instead of creeping to it; before, 5.0 N took 0.748 s at k 1.05 and 1.075 s at k 0.88.

## Equipment

Gripper on the bench (wrist plate in a vise) with its 6.5 V rail, laptop running `../tools/gripper_log.py`, one ply of demo fabric (about 100 × 100 mm) on a light card frame, a phone filming at 240 fps on a tripod, the printed protractor and pointer from TP-08 (1° marks, pointer on knuckle A), a lamp (slow motion needs light).

## Setup

```
 Front view (camera's view). Phone square to the knuckle face, about 250 mm away.

        protractor card on the front plate, 1 deg marks, -10 ... +25 deg
             . ' ' ' ' ' ' ' ' .
           /    pointer on        \
          |     knuckle A          |
          |        \               |
          [ knuckle A ]--gears--[ knuckle B ]
               |                     |
            finger A   | cloth |   finger B (FSR)
               [A]     |  ply  |     [B]
                       card frame holds the ply mid-gap, slack
```

1. Rail 6.50 V. No cloth between the pads: send `C`, record `EVT CAL_THETA_C0`. The bare-pad θ_c0 is the reference the close profile uses.
2. Hang the ply on its card frame so it sits midway between the open pads and does not touch either.
3. Phone in slow motion at 240 fps; check the protractor marks are readable on one frame. Frame the pads and the pointer together.

## Steps

**A. Ten closes from the open stop (R19).**

1. Start the video, then run:
   `python docs/gripper/test/tools/gripper_log.py --port <port> --out TP-03_log.csv --sequence close --n 10 --hold 1`
   It sends `STREAM 50`, then ten times: `G 5`, wait for HOLD, hold 1 s, `R`, wait for IDLE (each close starts at +20° in IDLE).
2. Stop the video. Check the log has ten `EVT ENTER_HOLD` and no `FAULT`.
3. `python docs/gripper/test/tools/analyze_log.py close TP-03_log.csv`. It prints, per close, the contact, 4.5 N, 5.0 N and HOLD times from the `CMD_GRIP` event, using the firmware's own millisecond clock, with the 10.5 ms FSR lag (EMA 9.5 ms + 1 ms poll, `controls.md` 3) subtracted from the force times; then mean, s and the 95/90 bound with PASS/FAIL against ruled {{tp03.proposed_limit}} for all three arrival events, plus historical {{tp03.written_limit}} contact (superseded 2026-10-12).

**B. Video (jaw speed and an independent close time).**

4. For each close, step frame by frame. Record the first frame where the pointer moves (`video_start_frame`) and the first frame where both pads touch the ply (`video_contact_frame`).
5. Read the pointer angle on every frame over the last 5° before contact. Fit a straight line to angle against frame over the last 3° (contact angle to contact + 3°); jaw speed = slope × 240 frames/s. A single 3°/(frames/240) reading is too coarse (see Calculation).
6. Do not use the `cmd_speed_last3deg_dps` column that `analyze_log.py` prints for R19: the `ST` line `th=` is the *reported target* angle, not the jaw. It reads 20 °/s by construction.

**C. Information: close from the pre-grasp pose, and one full cycle (R6).** Three times, interactive (`gripper_log.py --port <port> --out TP-03_cycle.csv`):

7. `A` (APPROACH, jaw stays open), `ARM_AT_POSE` (TOUCHDOWN: jaw parks at θ_c0 + 6°). Wait for `EVT POSITION_REACHED`, then within 10 s (`TIMEOUT_TOUCHDOWN_MS`) send `G 5`.
8. In HOLD send `FEED`, wait 2 s, `FEED_DONE`. Wait 5 s for RETRACT to time out to IDLE.
9. `analyze_log.py close TP-03_cycle.csv` gives the close times from pre-grasp (expected about 0.38 s to contact: 6° at 20 °/s plus 76 ms lag [D, equation]). Not judged against R19.

## Data to record

Per close: trial, start state (IDLE or TOUCHDOWN), `CMD_GRIP` time in ms, contact / 4.5 N / 5.0 N / HOLD times in ms after the command, video start and contact frames, jaw speed over the last 3° from the video, notes. Also the bare-pad θ_c0, the TP-12 finger k, both logs and the video file.

## Calculation

- Times t = (event ms − `CMD_GRIP` ms) − 10.5 ms for FSR-based times (done by `analyze_log.py`). The data-sheet columns `t_*_ms` are raw: if you judge by hand from them, subtract 10.5 ms from the force times first, or copy the tool's seconds instead. Judge with the tool's words.
- Upper bound B = mean + 2.568·s for n = 10 (one-sided 95 % / 90 %).
- Video close time = (contact frame − start frame)/240 s. It starts at first motion, after the frame wait and servo decode (about 10-30 ms, `controls.md` 4.1), so it should read that much less than the log's contact time. A larger gap means the log or the video is wrong.
- **Jaw speed: quantity, limit, U.** Quantity: jaw speed over the last 3° before contact, as the slope of a straight line fitted to the pointer angle on the 36 frames inside those 3° (240 fps). U: one protractor reading is ±0.58° (U), so a two-point 3° reading is ±27 % (±5.5 °/s) [D, equation]; the least-squares slope has standard error σ·√12/(Δt·N^1.5) with σ 0.29°, Δt 1/240 s and N = 3°/(20 °/s)·240 = 36, which is 1.11 °/s, so **U = 2.2 °/s** [D `test_plan.py`].
  - **Why the DB limit cannot be the video criterion.** DB R19 says "≤ 20 °/s [A]" and the firmware's own constant is `JAW_SPEED_NEAR_DPS` = 20.0 °/s. The servo trails the command: the modelled jaw is at 21 °/s at contact + 3° and ≤ 20 °/s from contact + 2° (`controls.md` 4.2). A conforming gripper reads 20-21 °/s, and 21 − 20 = 1 °/s is less than U = 2.2 °/s, so against 20 °/s it can only be INDETERMINATE.
  - **Two checks that a conforming gripper passes.** (1) *Command*: `JAW_SPEED_NEAR_DPS` ≤ 20.0 in the flashed `config.h` (read the file; U = 0 for a constant) → 20.0 ≤ 20.0, **PASS**. (2) *Jaw, from video*: limit 25 °/s [A] = 21 (modelled maximum) + 2.2 (U) + 1 (margin), rounded up. 21 + 2.2 = 23.2 ≤ 25, so a conforming jaw is **PASS**; the first-build fault (30 °/s at contact + 3°, `controls.md` review item 2) has 30 − 2.2 = 27.8 ≥ 25, so it is **FAIL**. Between (fit 22.8-27.2 °/s) is **INDETERMINATE**: film again with a better camera angle.
  - Also state the video fit against 20 °/s as information; record the DB number-for-number request in the README (Requested changes).

## Pass / fail

| Reading | Limit | Pass | Indeterminate | Fail |
|---|---|---|---|---|
| Historical R19 (superseded 2026-10-12): contact (U 3.6 ms) | {{tp03.written_limit}} | B ≤ 0.4964 s | B between 0.4964 and 0.5036 s, **including exactly 0.500 s** | B ≥ 0.5036 s |
| Ruled R19: 4.5 N (U 12.9 ms) | {{tp03.proposed_limit}} | B ≤ 0.737 s | between 0.737 and 0.763 s | B ≥ 0.763 s |
| Ruled R19: 5.0 N (U 12.9 ms) | {{tp03.proposed_limit}} | B ≤ 0.737 s | between 0.737 and 0.763 s | B ≥ 0.763 s |
| Both: jaw speed, last 3°, command | 20 °/s | `JAW_SPEED_NEAR_DPS` ≤ 20.0 | (constant: U = 0) | > 20.0 |
| Both: jaw speed, last 3°, video fit v (U 2.2 °/s) | 25 °/s | v ≤ 22.8 °/s | 22.8-27.2 °/s | v ≥ 27.2 °/s |
| R6: event order | DB section 8 | `ENTER_APPROACH, TOUCHDOWN, CLOSE, HOLD, FEED, RELEASE, RETRACT, IDLE` in that order, no other `ENTER_` between | | any other order or a `FAULT` |

`analyze_log.py close` prints the same word (PASS, FAIL or INDETERMINATE) next to each bound, with the same U. A close time measured at exactly the limit is INDETERMINATE in the procedure and in the tool: add closes or time with a better instrument. Record the ruled R19 value on the sign-off; keep the superseded 2026-10-12 value as a separate historical comparison. Report contact time against {{tp03.proposed_limit}} and the force times against {{tp03.written_limit}} too, as information.

## Hazards

- **Pinch:** the jaw closes at up to 120 °/s. Fingers out of the jaw while the sequence runs; hang the ply before starting.
- Keep the lamp off the servo and fingers (TPU softens near 50 °C, HDT 50.3 °C, DB section 4).

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| Contact later than 0.52 s | Rail sag (servo slower), or θ_c0 wrong (calibrated with the ply in) | Firmware owner; electrical |
| 5.0 N much later than 4.5 N | Soft finger (TP-12): the PI integrates slowly near the soft end | Douglas (R19), controls owner |
| Jaw speed fit ≥ 27.2 °/s at the end (or the commanded speed above 20 °/s) | Servo lag longer than the 7° the slow zone allows for | Firmware owner (`JAW_SLOW_ZONE_DEG`) |
| No HOLD, `FORCE_SAT` or `NO_CONTACT` | Ply thicker than one layer, or FSR span off (TP-01) | Controls owner |
| `ENTER_` order differs | State-table change since `controls.md` section 2 | Firmware owner |
