**What it proves:** that the gripper meets the ME102B project rules (one transmission DOF, a DC motor, an analog input, a button, a microcontroller, an event-driven state machine) and the team rulings (PWM actuator, ≤ US$50, public sources). Most items are pass/fail by inspection; R7 is a timing measurement. About 40 min: part A at a desk, part B on the bench with the powered gripper. Data sheet: [`../datasheets/TP-10.html`](../datasheets/TP-10.html) (CSV: `TP-10.csv`).

| | |
|---|---|
| Requirements | R1-R8, R11; measurements M16 (3.3 V pulse drives the servo), M20 (GSI rulings on R1 and R2) |
| Pass | Each item as listed under Pass / fail; one sign-off line each |
| Instrument | Eyes, compiler exit code, `grep`, event log (1 ms), scope or logic analyser (pulse U = 1.6 µs [D `test_plan.py`]) |
| Sample size | 1 per rule (deterministic); 5 button presses (catches contact bounce); 1 full cycle |

## Expected values

| Quantity | Expected | Source |
|---|---|---|
| Transmission | Servo → knuckle A → 1:1 spur sector pair (z 19 / z 19) → knuckle B | [D] DB R1; `cad/gripper/params.json` `gear` |
| Compile | Exit 0; about 317,589 B flash, 22,780 B RAM; 2 warnings from ESP32Servo (unused `TAG`), none from the sketch | [D] `controls.md` section 0 |
| Button | One `EVT BUTTON_PRESS` per press (25 ms debounce, sent on release); `EVT BUTTON_LONG` after 800 ms held | [D] `config.h` `BUTTON_DEBOUNCE_MS`, `BUTTON_LONG_MS`; `inputs.cpp` |
| PWM frame | 20.0 ms (50 Hz) | [D] `config.h` `SERVO_PWM_HZ` |
| Pulse at the open stop θ = +20° | 1722 µs | [D, equation] 500 + (90 + θ)·2000/180 µs (`controls.md` 4.1, `servo_map.h`) |
| Pulse at the firmware's absolute backstop θ = −10.2° (`JAW_MIN_DEG`; the force loop's own floor is θ_c0 − 6.2°, `JAW_FLOOR_BELOW_C0_DEG`) | 1387 µs | same equation; host test `servo map` |
| Pulse clamp | never below 1200 or above 1900 µs | [D] `config.h` `SERVO_US_LIMIT_MIN/MAX` |
| Actuator price | DS3218MG US$12.99 | [S] `research/actuators.csv` row A17 |

## Equipment

Laptop with `arduino-cli`, the repository at the tested commit, the assembled gripper on its 6.5 V rail with USB, `../tools/gripper_log.py`, scope or USB logic analyser (≥ 1 MS/s), a strip of demo cloth, the servo receipt.

## Steps

**A. Desk (no hardware).**

1. **R5 compile.** From the repository root:
   `arduino-cli core install esp32:esp32@2.0.17` and `arduino-cli lib install "ESP32Servo@1.2.1"` (once), then
   `arduino-cli compile --fqbn esp32:esp32:esp32 --warnings all firmware/gripper`.
   Record the exit code, flash and RAM use, and every warning that comes from `firmware/gripper` (not from the library). Record the commit hash (`git rev-parse HEAD`).
2. **R6 no blocking delay.** `grep -rn "delay(" firmware/gripper` (PowerShell: `Get-ChildItem -Recurse firmware\gripper | Select-String "delay\("`). Every hit must be a comment or a string. Today there is one: the comment on line 5 of `gripper.ino`. Open each hit and confirm. A real `delay(` call in `loop()` or anything it calls is a fail. `firmware/gripper/test/` is host-side test code; record hits there but they do not count.
3. **R2 and R1, M20.** Read `LOG.md`. Pass only if it holds the GSI's written answer, dated, that (a) a PWM hobby servo counts as the DC motor and (b) a 1:1 spur sector pair counts as a transmission DOF. If not, the team lead asks the GSI and records the answer in `LOG.md`; the item stays NOT RUN until then. The DB fallbacks are in R1 (a ≥ 2:1 pinion stage) and R2 (gearmotor + H-bridge).
4. **R8 price.** Find the receipt or the vendor page for the servo actually fitted. Pass if the price is ≤ US$50.00.
5. **R11 sources.** Go through every source list and every [S] tag under `docs/gripper/` (DB "Sources", the research notes, the analysis notes, `test/EQUIPMENT.md`). For each [S], a public URL must be on the line or in the file's source list. Then run `grep -rniE "libgen|sci-hub|z-lib|bcourses|canvas|instructure|piazza|edstem|gradescope" docs/gripper`: it should return nothing. Any course file, login-only page or pirated PDF is a fail; list it in notes.

**B. Bench (powered gripper).**

6. Power the ESP32 first, then turn the gripper 6.5 V rail on. Start `python docs/gripper/test/tools/gripper_log.py --port <port> --out TP-10_log.csv`. Press the ESP32's reset button.
7. **R5 boot.** The log must show `ENTER_BOOT`, `ENTER_HOME`, `ENTER_CALIBRATE`, `CAL_THETA_C0` (inside −4…+4°) and `ENTER_IDLE`, in that order.
8. **M16.** Inspect the HOME and CALIBRATE log and video for open-stop arrival and slow calibration closure: this proves the servo follows the ESP32's 3.3 V pulse. If it did not move, or jittered, M16 fails: fit a 74AHCT125 buffer on GPIO 18 (`config.h`).
9. **R7 pulse.** Scope on GPIO 18 (or the servo signal wire) to ground. In IDLE, measure the frame period and the pulse width. Then send `G 5` with the cloth strip between the pads, and watch the pulse width through the close and the hold (scope in roll mode, or capture 5 s with the logic analyser). Record the smallest and largest widths seen. Send `R`.
10. **R6 cycle and R4 presses.** Put the cloth strip between the open pads. From IDLE, press START once per step and check the log after each press:
    IDLE → press → `ENTER_APPROACH` → press → `ENTER_TOUCHDOWN` → press → `ENTER_CLOSE` → (by itself) `ENTER_HOLD` → press → `ENTER_FEED` → press → `ENTER_RELEASE` → (by itself) `ENTER_RETRACT` → press, or wait 5 s → `ENTER_IDLE`.
    Each press must log exactly one `EVT BUTTON_PRESS` and move exactly one state. Two events for one press, or a skipped state, is contact bounce: a fail. Count at least 5 presses. If CLOSE starts by itself after an `EVT TABLE_TOUCH` (the servo-current touch detector, `controls.md` section 1), that is allowed; skip that press.
11. **R4 long press.** In IDLE, hold START for about 1.5 s. The log must show one `EVT BUTTON_LONG` (about 800 ms after the press starts) and no `BUTTON_PRESS`.
12. **R3.** Cross-reference TP-01 step 10/11: the `ST` lines' `F=` trace and the DMM reading on the FSR divider node. Copy its result here.

## Data to record

One row per item (R1-R8, R11, M16, M20) with: requirement, evidence (file and line, log excerpt, scope capture name, receipt), result, checked_by, notes. Keep `TP-10_log.csv` and the scope captures.

## Calculation

- Frame period error = |T_frame − 20.0 ms|. Pass band 50 ± 1 Hz = 19.61-20.41 ms.
- Expected open-stop pulse = 500 + (90 + 20)·2000/180 = 1722 µs. If `SERVO_DIR` is −1 on this build, it is 500 + (90 − 20)·2000/180 = 1278 µs; check `config.h`.

## Pass / fail

| Item | Pass when |
|---|---|
| R1 | The jaw opens and closes with knuckle B driven only through the sector pair (watch it during step 10), **and** the GSI answer (M20) is in `LOG.md` |
| R2 | GSI answer in `LOG.md` that the PWM servo counts as the DC motor (M20) |
| R3 | TP-01's trace rises ≥ 300 mV of FSR node voltage from 0 to 5 N [A threshold] |
| R4 | 5 of 5 presses give one `BUTTON_PRESS` each; the 1.5 s hold gives one `BUTTON_LONG` |
| R5 | Compile exits 0 with no sketch warnings, and the board boots to `ENTER_IDLE` after HOME and CALIBRATE |
| R6 | No `delay(` call in the sketch code, and the step-10 log shows the DB section 8 order: BOOT → HOME → CALIBRATE → IDLE → APPROACH → TOUCHDOWN → CLOSE → HOLD → FEED → RELEASE → RETRACT → IDLE |
| R7 (U 1.6 µs on a pulse width; three outcomes as in the README) | Frame 19.61-20.41 ms; open-stop pulse 1722 ± 3 µs (1.6 µs U plus 1 µs rounding); no pulse seen outside 1200-1900 µs; the signal is a PWM wire, not the STS3215 bus |
| R8 | Receipt ≤ US$50.00 |
| R11 | Every [S] has a public URL; no course file, login-only page or pirated PDF |
| M16 | The servo follows the 3.3 V pulse (step 8) |

## Hazards

- **Pinch:** the jaw closes at up to 120 °/s in step 10. Hold the cloth strip by its far end; keep fingers out of the jaw.
- Power the ESP32 before the servo rail, or the servo can jump.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| Compile error | Wrong core or library version (`controls.md`: core 2.0.17, ESP32Servo 1.2.1) | Firmware owner |
| Two `BUTTON_PRESS` for one press | Bounce longer than 25 ms; raise `BUTTON_DEBOUNCE_MS` or add an RC filter | Firmware owner |
| Board stops in HOME or CALIBRATE with `FAULT_*` | Limit switch or FSR wiring; θ_c0 outside −4…+4° | Firmware / electrical owner |
| Pulse outside 1200-1900 µs | Clamp bypassed or servo attached with other limits | Firmware owner |
| No GSI answer | Not asked yet | Team lead |
