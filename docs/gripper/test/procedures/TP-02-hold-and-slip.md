# TP-02 Hold under tension, cloth slip and pad friction

<!-- hardware-scope:begin -->
**Hardware scope — arm: `off`; gripper: `bench`.** The arm is off and its power supply is disconnected for this whole procedure. The gripper is fixed in the bench fixture; the arm is not powered.
<!-- hardware-scope:end -->

<!-- procedure-body:begin -->
**What it proves:** the 5 N grip keeps the cloth still under the 2 N process tension for a whole 25.5 s feed hold, and how much pull it takes to drag the cloth out. It also measures the pad-cloth friction coefficient μ (M2), which decides the pull-to-slip verdict: the analysis predicts a pull to slip *exactly* at the 4.0 N limit, because the limit was set from the same assumed μ. About 45 min. Data sheet: [`../datasheets/TP-02.html`](../datasheets/TP-02.html) (CSV: `TP-02.csv`).

| | |
|---|---|
| Requirements | R14 (slip part: "no slip in the pull test"); measurements M2 (μ), M3 (process tension, used here) |
| Pass | (b) slip ≤ 0.5 mm [A threshold] after 25.5 s at 2.0 N in 11 of 11 holds, no `FSR_SLIP` / `FSR_LOST`; (c) 95 %/90 % lower tolerance bound of 11 pulls to slip ≥ 4.0 N |
| Instrument | Pinch-probe load cell rebuilt as a pull gauge, U = 0.096 N at 4 N; ink mark on a 0.5 mm grid, U = 0.23 mm; phone inclinometer ±0.5° [A] [D `test_plan.py`] |
| Sample size | 5 incline trials (DB M2); 11 holds and 11 pulls: zero failures in 11 shows reliability 0.80 at 90 % confidence (`MEASUREMENT-SIZING.md` section 3) |

## Expected values (from the analysis; a result far from these means a setup error)

| Quantity | Expected | Source |
|---|---|---|
| μ, TPU pad on the demo cotton | 0.4 (incline slip angle 21.8°) | [A] DB M2; angle [D, equation θ = atan μ] |
| Pull to slip, 2·μ·F | 4.00 N at μ 0.4, F 5.0 N: equal to the limit, margin/U 0 | [D] `test_plan_out.json` → `expected.slip`, `resolvability` |
| Safety factor against 2 N tension | 2.0 | same |
| Older dyno model, 2× snag (2 → 4 N) | slips: capacity 3.81 N with a 4.76 N hold (old 0.3 N integrator band) | [D] `dyno.md` 4a; the current firmware regulates its FSR reading to 6.0-6.6 N (setpoint + 1 N bias) |
| Hold force on the probe | 5.22-6.20 N | [D] `expected.close` (TP-01) |

The 4.0 N limit equals 2·μ·F at the *assumed* μ, so the measured μ settles it: μ ≥ 0.41 at a 5.0 N hold gives about one U of margin [D, equation (4.0 + 0.1)/(2·5.0)]; μ under 0.40 predicts a fail.

## Equipment

The TP-01 pinch probe and `probe.ino` reader, a 20 × 20 mm TPU 95A pad coupon (printed in the finger's material and layer direction, same face texture as the pad), a flat board about 300 mm long covered with the demo fabric, a phone with an inclinometer app or a printed protractor, a 50 g mass, a 50 mm wide strip of demo fabric about 250 mm long, a fine felt pen, a 0.5 mm grid printed at 100 % on paper, a phone with a macro mode, 204 g of masses (2.0 N at g = 9.80 m/s²) on a thread loop with a clip, an M4 or M5 eye bolt, a foam pad, the gripper in a vise with its 6.5 V rail.

## Setup

```
 Front view. Wrist plate in the vise, fingers pointing DOWN, pads squeeze left-right.

            ===== vise =====
            |  wrist plate  |
            |    housing    |
          finger A       finger B (FSR)
             \               /
              \  grid card  /      0.5 mm grid taped to finger B's side face,
               [A]|cloth|[B]       edge level with the pad's lower edge
                  | ink |  <-- ink line across the strip at the pad's lower edge
                  |strip|
                  |  o  |  clip, thread
                  |     |
                  v pull: 204 g hung, or the load cell's eye bolt pulled down
              (2.0 N in the cloth plane, square to the pad normal)
```

1. Pulling straight down draws the cloth out past the fingertips, in the cloth plane and square to the pad normal [A: the feed pulls the cloth this way]. Keep the pull line within 5° of vertical (the probe budget assumes it).
2. Gripper rail at 6.50 V (DMM). Calibrate on bare pads: `C`. FSR span as set in TP-01 (`CALF`).
3. `python docs/gripper/test/tools/gripper_log.py --port <gripper port> --out TP-02_log.csv` (interactive input), then `STREAM 50`.

## Steps

**A. Friction μ, incline test (M2).**

1. Lay the fabric board flat. Put the coupon pad-face down on it with the 50 g mass on top (so surface tack does not dominate [A]). Pad texture lines run the same way as on the finger relative to the pull.
2. Raise one end slowly, about 1° per second, until the coupon starts to slide. Read the board angle θ_s with the inclinometer on the board. Record.
3. Repeat 5 times, moving the coupon to fresh fabric each time. μ = tan θ_s.

**B. Hold force on the probe (before the rebuild).**

4. Put the probe between the pads (TP-01 step 6), `C`, then one `G 5` hold of 25.5 s. Record the probe hold mean as `hold_N_probe` for every row. `R`, take the probe out, `C` on bare pads again.

**C. Rebuild the probe as a pull gauge.**

5. Unscrew plates P1 and P2. Screw the eye bolt into the free end's thread. Hang 102 g and 408 g (1.0 and 4.0 N) from the eye with the fixed end clamped: readings must agree with the TP-01 scale within 0.05 N, else refit the scale.

**D. Hold under 2.0 N tension (R14 slip), 11 holds.**

6. Slide the strip between the pads so 20 mm sits above the pad's lower edge. `G 5`. Wait for `EVT ENTER_HOLD`.
7. Draw the ink line across the strip along the pad's lower edge, touching the grid card. Take macro photo 1 (strip, ink line, grid in one frame, phone square to the card).
8. Within 2 s, lower the 204 g slowly onto the strip clip until it hangs free (no jerk). Start a 25.5 s timer. Or pull the eye bolt down to 2.0 N on the probe readout and hold it there.
9. At 25.5 s take macro photo 2, then lift the mass off. `R`.
10. Move the strip so fresh cloth is under the pads; repeat 11 times in all.

**E. Pull to slip, 11 pulls.**

11. Log the probe: `python docs/gripper/test/tools/gripper_log.py --port <probe port> --out TP-02_probe.csv` in a second terminal.
12. Clip the strip to the eye-bolt thread. `G 5`, wait for HOLD, ink line as in step 7.
13. Pull the load cell down by hand (or with a screw slide) at about 0.5 N/s: from 0 to 4 N in about 8 s. Watch the ink line; stop when it moves off the pad edge. The peak probe reading is the pull to slip.
14. `R`; new cloth; repeat 11 times.

## Data to record

Per row: trial, fabric (name, weave direction), incline slip angle (rows 1-5), probe hold mean (step 4), tension (2.0 N in holds), slip after 25.5 s in mm, pull to slip in N, lowest FSR `F=` in the `ST` lines between `ENTER_HOLD` and the `R`, any `FSR_SLIP` or `FSR_LOST` event, notes. Keep both photos per hold and both logs.

## Calculation

- μ = mean of tan θ_s over the 5 trials; u(μ) from one angle reading: sec²θ·0.5° ≈ 0.010 at μ 0.4 [D, equation].
- Slip per hold: distance the ink line moved against the grid between photos 1 and 2 (count 0.5 mm squares, interpolate to 0.1 mm).
- Predicted pull to slip P = 2·μ·F_hold (two pad faces) with the step-4 probe hold. Compare with the measured mean.
- Lower tolerance bound: L = mean − 2.503·s over the 11 pulls (k for n = 11, one-sided 95 % / 90 %; `analyze_log.py` table).
- Safety factor SF = mean pull to slip / process tension. Tension: the TP-14 value of M3 if measured, else 2.0 N [A, DB M3].

## Pass / fail

- **Pass, hold:** every slip ≤ 0.27 mm (0.5 mm − U 0.23 mm) in 11 of 11, and no `FSR_SLIP` / `FSR_LOST` event. **Indeterminate:** any slip 0.27-0.73 mm. **Fail:** any slip > 0.73 mm or any `FSR_SLIP` / `FSR_LOST`.
- **Pass, pull to slip:** L ≥ 4.1 N (4.0 + probe U 0.096). **Indeterminate:** L from 3.90 to 4.1 N. **Fail:** L ≤ 3.90 N. Expected to land near the limit; the μ from part A says why.
- R14 needs TP-01 (hold) and both parts here.

## Hazards

- **Pinch:** the jaw closes at up to 120 °/s with up to 10 N. Draw the ink line with the pen, not a finger in the jaw.
- The mass falls when the jaw opens: foam pad underneath, feet clear.
- Stop the pull at 8 N even if nothing slips: the vise grip on the wrist plate is not designed for it [A], and a cloth that suddenly lets go whips the load cell.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| μ well under 0.4 | Smooth pad face or a slippery fabric. R14's 5 N basis no longer gives SF 2 | DB owner (grip, M2) |
| Slip grows steadily through the hold | Pad creep, or hold force sagging; check FSR `F=` against the step-4 probe hold | Controls owner; finger owner |
| `FSR_SLIP` / `FSR_LOST` while the mark is still | Cloth pull unloads the FSR puck (FSR off the pad centre) | Firmware / FSR mounting |
| Pull to slip far under 2·μ·F | Pull not square to the pad normal, or only one pad in contact (pad faces not parallel) | Finger owner |
<!-- procedure-body:end -->
