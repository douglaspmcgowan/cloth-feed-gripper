# TP-05 Stall detection and back-off

<!-- hardware-scope:begin -->
**Hardware scope — arm: `off`; gripper: `bench`.** The arm is off and its power supply is disconnected for this whole procedure. The gripper is fixed in the bench fixture; the arm is not powered.
<!-- hardware-scope:end -->

<!-- procedure-body:begin -->
**What it proves:** when a finger is blocked and the servo stalls, the firmware sees the rail current stay above 3.3 A for 100 ms, enters FAULT and starts opening the jaw within 200 ms of the current rising. R20 has two readings and both are logged: back-off **begins** within 200 ms (the analysis predicts 140 ms) and the train is **unloaded** within 200 ms (the command reaches its target at 200 ms; the jaw follows about 50 ms later). A fourth part blocks the jaw just after contact, for the 3.1 A trip that runs with the force loop. About 40 min with the cooling waits. Data sheet: [`../datasheets/TP-05.html`](../datasheets/TP-05.html) (CSV: `TP-05.csv`).

| | |
|---|---|
| Requirements | R20 (detect stall and back off within 200 ms) |
| Pass | Over-current onset → back-off begins ≤ 200 ms in 22 of 22 blocked closes, and the 95 %/90 % upper bound ≤ 200 ms. The "unloaded" reading is recorded, not judged (`controls.md` O11) |
| Instrument | Firmware event log and `ST` lines with the INA219 current (`I=`), `STREAM 50`; bench supply current readout as a cross-check |
| Sample size | 22 blocked closes: zero failures in 22 shows reliability 0.90 at 90 % confidence (safety function) |

## Expected values (from the analysis; a result far from these means a setup error)

| Quantity | Expected | Source |
|---|---|---|
| Onset → back-off command begins | 140 ms (100 ms `STALL_CURRENT_MS` + ticks) | [D] `controls.md` 0, 3 (host test) |
| Onset → back-off command at its target | 200 ms; jaw about 50 ms later | [D] `controls.md` 3, O11 |
| Stall current | 3.5-3.8 A (A32 datasheet at 5-6.8 V) to 3.99 A (actuation sizing) | [D] `test_plan_out.json` → `expected.stall.I_stall_A_fitA_fitB` |
| Trip threshold | 3.3 A for 100 ms before contact, the case parts A and B block (`STALL_CURRENT_A`, `STALL_CURRENT_MS`); 3.1 A while the force loop runs, after contact and in HOLD (`STALL_CURRENT_HOLD_A`), the case part D blocks | [D] `config.h` |
| Stall after contact (part D) | `FAULT_OVERCURRENT` 100-119 ms after the rail passes 3.1 A, for Fit A and Fit B, continuous and discontinuous drive; host test: 3.99 A in HOLD faults in 120 ms | [D] `controls.md` 4.3, 7 (`faults.py`, `test_stall_detected_after_contact_and_in_hold`) |
| Back-off target with the block at +10° | about +8.3°: command at the fault ≈ θ_c0 + 6° − 20 °/s × 0.1 s ≈ +3.3°, plus 5° `FAULT_BACKOFF_DEG` (θ_c0 −0.7°, sim). Still closed of the block, so the servo may stay stalled until a second over-current detaches the pulse (`WARN SERVO_RELAXED`, row 63) | [D, equation] `controls.md` 4.2, 1 |
| Winding heating at stall | about 3 K per 0.2 s; 125 °C winding after 8.1-11.1 s of continuous stall | [D] `expected.stall`, `dyno.md` 3 |

**Two ways this can fail that are not timing** (`controls.md` O6): if the real stall current is under 3.3 A the trip never fires (the log then shows `NO_CONTACT` and a normal RELEASE): that is a **FAIL**, report the current. In HOLD the trip is 3.1 A, not 3.3 A. If dyno Fit A is right (3.77 A stall), a servo conducting discontinuously can reach it while holding 6–7 N (`controls.md` O6: 2 of 2,000 simulated grips), so it may also fire on a normal `G 7`; note any over-current in TP-01 and TP-04.

## Equipment

Gripper in the vise with the 6.5 V rail from a bench supply with a current readout (limit set to 4 A: a 3 A supply sags at a Fit A stall, `dyno.md` 3), INA219 fitted (no `WARN INA219_ABSENT` at boot), an aluminium block about 20 × 20 × 40 mm on a pivot bolt or hinge so it swings clear without unclamping, a G-clamp, the TP-08 protractor, the thermocouple from TP-07 (or an IR thermometer), laptop with `gripper_log.py`.

## Setup

```
 Top view, jaw open at +20 deg. Block on the closing side of finger B's knuckle.

        finger A            finger B
           \                  /
            \                / <- jaw stops here, about +10 deg, pads ~24 mm apart
        [knuckle A]==gears==[knuckle B]
                              |#| aluminium block, swings on a pivot bolt,
                              |#| pivot clamped to the bench
```

1. Rail 6.50 V, supply limit 4 A. `C` on bare pads; record θ_c0.
2. Rail off. Turn the jaw by hand until the protractor reads about +10° (pads apart, no FSR contact), swing the block against finger B's knuckle and clamp the pivot. Mark the block's swung-in position, then swing it clear. Rail on, `H`, wait for IDLE (with the block in, the re-home calibration would stall on it).
3. Thermocouple bead on the servo case (TP-07 method), logged by `probe.ino`.

## Steps

**A. 22 blocked closes (R20).**

1. `python docs/gripper/test/tools/gripper_log.py --port <port> --out TP-05_log.csv --sequence trip --n 22` (sends `STREAM 50`).
2. Each trial: block in. Enter (sends `G 5`). The servo stalls on the block; expect `EVT FAULT_OVERCURRENT` and `EVT ENTER_FAULT` within about 0.3 s. Read the bench supply's current while it stalls. Note any `WARN SERVO_RELAXED`.
3. **Swing the block clear before the second Enter**: Enter sends `H`, which re-homes and recalibrates (CALIBRATE closes to find θ_c0 and would stall on the block). Wait for `ENTER_IDLE`.
4. Wait 30 s from the stall before the next trial (winding cooling). Read the case temperature; stop if it passes 45 °C [A: well under the 60 °C R26 limit, so the trials do not heat-soak the motor].
5. `python docs/gripper/test/tools/analyze_log.py faults TP-05_log.csv`. Per over-current it prints onset, back-off begin, elapsed time, largest status gap and the observed per-run U. Record the largest gap. A voided run exits non-zero: repeat it. The firmware prints `FAULT_OVERCURRENT` twice per trip; the analyser uses the first.

**B. Information: block near contact (the "unloaded" reading), 3 trials.**

6. With gripper power off, move the block by hand so the jaw stops about 2° above θ_c0 (pads about 4 mm apart [D, `finger.md` 6.1 linearised]). The back-off target (≥ θ_c0 + 5°) now clears the block, so the jaw should leave it. Repeat steps 2-4.

**C. Optional: stall at the open stop (relax, row 63).**

7. With a ply between the pads, `G 5` and wait for HOLD. Then place the block on the *opening* side of finger B's knuckle at about +15°. `R`: RELEASE drives open into the block, over-current → FAULT; the back-off opens further into the block, a second over-current sets `relax` and the pulse stops: expect `WARN SERVO_RELAXED`. `H` to recover.

**D. Stall after contact: the 3.1 A trip in the force loop (R20), 3 trials.**

The blocks in A and B stop the jaw before contact, so only the 3.3 A trip (`STALL_CURRENT_A`) is exercised. After `FSR_CONTACT` the force loop runs and the trip is `STALL_CURRENT_HOLD_A` 3.1 A. Here the jaw touches the cloth, then the block stops the knuckle before the force reaches the target: the loop keeps squeezing toward its cap, the servo stalls, the rail draws the stall current (3.99 A or more) and the 3.1 A trip must fire.

8. Rail off (the servo turns freely by hand only unpowered; the ESP32 stays on USB, so `ST` lines keep coming with `STREAM 50`). Put one ply of cloth between the pads. Turn the jaw by hand until the pads just pinch the ply: `F=` in the `ST` lines reaches about 0.5 N (or, by feel, the ply just stops sliding). Read the protractor, then turn about 1° further closed. Use the same pivoting block and G-clamp as in setup step 2: swing the block in until it touches finger B's knuckle on its closing side at this angle, and clamp the pivot bolt to the bench there. Mark the block's swung-in position, swing it clear, rail on, `H`, wait for `ENTER_IDLE`.
9. Block in, ply in, `G 5`. Expect `EVT FSR_CONTACT`, then `EVT FAULT_OVERCURRENT` and `ENTER_FAULT` about 0.1-0.3 s later, with `I=` above 3.1 A for 100 ms before it, and `th=` opening by 5°. If instead the log shows `FORCE_SAT` followed by `ENTER_RELEASE` (or `ENTER_HOLD`) with `I=` never above 3.1 A, the stall current of this servo is under the force-loop trip: that is the O6 failure, record it.
10. Swing the block clear, `H`, wait 30 s, case under 45 °C. Three trials.
11. `analyze_log.py faults` labels these trips "trip 3.1 A" (the last mark before them is `FSR_CONTACT`) and prints onset to back-off for each.

## Data to record

Per trial: trial, part (A, B, C or D), blocked-at angle (protractor), over-current onset ms, `FAULT_OVERCURRENT` ms, back-off begin ms, peak `I=` and the bench readout, `WARN SERVO_RELAXED` yes/no, notes: unloaded time (first `ST` line after FAULT with `I=` under 0.5 A [A]), case temperature.

## Calculation

- Begin time t_b = back-off begin ms − onset ms; unloaded time t_u = unloaded ms − onset ms.
- Upper bound B = mean(t_b) + 2.172·s for n = 22.
- Both endpoints come from the status stream. Use the generated observed-gap rule below.

## Pass / fail

<!-- timing-verdict:begin -->
- For each onset-to-back-off run, `analyze_log.py` prints the largest status gap and uses U equal to the larger gap bracketing onset or back-off begin. PASS if value ≤ limit − U; FAIL if value ≥ limit + U; INDETERMINATE in between. A bracketing gap over 40 ms voids the run as INDETERMINATE with a non-zero exit; repeat it. The ceiling allows one delayed nominal period but rejects lost timing resolution. Use the largest run U for the 95 %%/90 %% upper bound.
<!-- timing-verdict:end -->
- A blocked close without `FAULT_OVERCURRENT` is a functional FAIL. An unclear timing verdict requires more trials or faster logging.
- Record t_u for both readings of R20 (begins / unloaded); Douglas rules which applies (O11). Expect t_u to exceed 200 ms in part A if the back-off target stays inside the block.
- **Part D (stall after contact):** an attribute check of the force-loop path. All three trials must show `FAULT_OVERCURRENT`, and each t_b is judged only by the generated rule above. A missing event fails. Part D does not enter the n = 22 bound.

## Hazards

- **Part D stalls the servo after contact** for at least the 100 ms trip time at the stall current (3.99 A or more): same limits as part A, a 30 s wait and the case under 45 °C between trials, and STOP or rail off if no `FAULT_OVERCURRENT` within 1 s.
- **Gear overload:** every trial puts the full stall torque (about 2.07 N·m, LC3) through the gear mesh for 0.1-0.3 s. The printed gears are sized for it, but check for a skipped tooth (jaw angle shifted at IDLE) every 5 trials. Stop if θ_c0 jumps by more than 1°.
- **Motor heat:** a stall that does not clear (trip not firing) heats the winding to 125 °C in 8-11 s. If no FAULT within 1 s, press STOP (long press) or cut the rail.
- **Pinch:** the block, jaw and clamp make a pinch point; fingers clear before Enter.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| No `FAULT_OVERCURRENT`; peak `I=` under 3.3 A | Real stall current below the trip (O6), or rail current limit set too low | Firmware / electrical owner: set the trip from the TP-13 measured currents |
| `I=` always 0 | INA219 absent or miswired (`WARN INA219_ABSENT`) | Electrical owner |
| t_b well over 140 ms | Loop overruns (O7) or slow I²C | Firmware owner |
| Jaw stays on the block until `SERVO_RELAXED` | Back-off 5° too small for a stall far above θ_c0 | Firmware owner (`FAULT_BACKOFF_DEG`), Douglas (R20 reading) |
<!-- procedure-body:end -->
