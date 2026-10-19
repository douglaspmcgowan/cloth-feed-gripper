# Gripper verification tests: how to run them

Test plan for the built ME102B cloth-feed gripper. Dated 2026-10-11. `DESIGN-BASIS.md` (DB) owns the requirements; this folder says how to prove each one on the bench. Where this folder and DB disagree, DB wins, except where DB is marked superseded (then `firmware/gripper/config.h` and the note it names win).

- **Who it is for:** a teammate with the built gripper, the arm, the equipment in [EQUIPMENT.md](EQUIPMENT.md) and an afternoon. You do not need to have read the analysis.
- **What you end with:** [datasheets/SIGNOFF.html](datasheets/SIGNOFF.html) filled in, one line per requirement R1-R27, each PASS, FAIL, INDETERMINATE or NOT RUN, with the data sheets behind it.
- **Numbers:** every number here comes from `test_plan.py` (output `test_plan_out.json`, stdout `test_plan_stdout.txt`) or carries a tag: [S] sourced (URL and retrieval date), [D] derived by a committed script, [A] assumed with the reason. Re-run: `python docs/gripper/test/test_plan.py` (needs numpy and scipy). The bench tools need pyserial on the laptop (`python -m pip install pyserial`).
- **Before every logged run with the probe:** `probe.ino` keeps its tare and scale in RAM. After a logger opens the probe's port, send `t` (probe unloaded) and `s <scale>` (your TP-01 fit) again. Check coverage: `python docs/gripper/test/check_matrix.py`.

## 0. Answer

| Item | Result |
|---|---|
| Coverage | All 27 requirements have a method and a procedure ([VERIFICATION-MATRIX.md](VERIFICATION-MATRIX.md); `check_matrix.py` enforces it). 16 procedures under [procedures/](procedures/) |
| Time | Core afternoon about 4.8 h decides R14, R15, R19 and R20. The whole plan is about 12.1 h of bench time in four sessions (session 1 includes about 1.5 h to build and calibrate the probe board) plus one unattended overnight run (table below) |
| Cost | US$98.14 to buy (US$77.20 without the spares), against a US$100 budget [A]; the rest is borrowed from the teaching lab ([EQUIPMENT.md](EQUIPMENT.md)) |
| Key instrument | A pinch-force probe: a 10 kg bar load cell (TAL220) on an HX711, held between the pads. Expanded uncertainty about 0.10 N at 5-10 N, so it resolves the 5 N and 10 N limits about 50 to 90 times over ([MEASUREMENT-SIZING.md](MEASUREMENT-SIZING.md)) |
| Expected to fail on the bench, from the analysis | **R10 fails at full reach:** CAD revision B predicts 52,995 g·mm, 121.2 % of budget; this settles the older BOM/design-basis disagreement. The disposition is no holds beyond 285.9 mm COM reach, with TP-14 enforcing the tighter 300 mm fingertip rule; **historical R19, superseded 2026-10-12** (contact at 0.50-0.51 s); **R26 likely** (servo case model 43-167 °C over the 12 dyno cases at 25-40 °C ambient, an upper bound); R25 is not provable in an afternoon (a zero-failure 1e5 demo needs about 2.6e5 cycles) |
| Too close to call with any affordable instrument | R16 stall at 6.35 V (2.02 against 1.98 N·m). Since the firmware regulates 1 N above the setpoint (`F_HOLD_BIAS_N`), R14 on the softest R12 finger (5.22 N, margin 0.22 N = 2.2 U), R15 with the FSR reading half (9.66 N against 10 N) and ruled R19 to 5.0 N (latest 0.691 s against 0.75 s) are decidable; the softest-finger R14 hold is still too close for a 95/90 bound at a bench-sized n, so TP-01 judges it as a zero-failure run |

## Three words, one rule

Every comparison with a limit gives one of three results, using the expanded uncertainty U (k = 2) of the instrument that made the reading:

- **PASS**: the reading is clear of the limit by at least U.
- **FAIL**: the reading is beyond the limit by at least U.
- **INDETERMINATE**: the reading is within U of the limit (a reading exactly on the limit is INDETERMINATE). Record it as that, never as a pass. Then take more samples (if the spread between trials is large) or measure with a better instrument (if the spread is small).

For an arm pose, a generated gate record owns the pose, datum, measurement, combination, limit, uncertainty and decision. Measure and pass that gate with the arm unpowered before any step powers or commands the pose.

`tools/analyze_log.py` applies this rule to every limit it prints (`decide()`), and `analyze_log.py judge --value V --limit L --u U --side upper|lower` checks any single reading by hand. Each procedure's *Pass / fail* section lists the numbers for its own limits; the same three-way split is in [VERIFICATION-MATRIX.md](VERIFICATION-MATRIX.md).

**Session header.** Every data sheet starts with the same eight fields: date, tester, unit serial, firmware version or commit, ambient °C, supply voltage measured at the servo, instrument ids with calibration date, FSR calibration id. In the CSVs they are the first eight lines, `#date,` and so on (fill the value after the comma; a CSV reader skips lines starting with `#`). The HTML sheets print the same block at the top. The generator `test_plan.py` writes them; do not edit the generated files.

Where each value comes from: **date, tester**: you. **Unit serial**: the number on the gripper's wrist plate (write one with a marker if none; keep it for all sessions). **Firmware**: the short commit of the flashed sketch, `git rev-parse --short HEAD` in the repository you flashed from (add `-dirty` if `git status` was not clean). **Ambient**: the room thermometer or the second thermocouple bead in air, at the start. **Supply voltage at the servo**: the DMM on the servo connector while the servo is powered (not the supply's front-panel display). **Instruments**: each instrument's label or asset tag plus its last calibration date; for the thermocouples, the date and offset of today's ice-point check; for the load-cell probe, the TP-01 calibration date. **FSR calibration id**: the id from `FSR-CAL.csv` for the `CALF` you ran this session (TP-01 part C2); write `none` if the session does not use force.

## 1. Order and time

Run the sessions in order. Parts tests come first because a failure there changes what gets built. Inside a session, run the rows top to bottom: each one leaves the gripper in the state the next one needs (calibrated, probe fitted, and so on).

<!-- phases:begin -->
| Session | Minutes [A] | Hours |
|---|---|---|
| 0 Desk checks and first power-up | 40 | 0.7 |
| 1 Parts, before assembly | 280 | 4.7 |
| 2 Core afternoon (R14, R15, R19, R20) | 314 | 5.2 |
| 3 On the arm | 90 | 1.5 |
| 4 Unattended | 30 | 0.5 |
<!-- phases:end -->

<!-- order:begin -->
| # | Session | Procedure | What | Requirements and measurements | Minutes | Tell if it fails |
|---|---|---|---|---|---|---|
| 1 | 0 Desk checks and first power-up | [TP-10](procedures/TP-10-course-rules.md) | Course rules and firmware inspection | R1, R2, R3, R4, R5, R6, R7, R8, R11, M16, M20 | 40 | team lead |
| 2 | 1 Parts, before assembly | [TP-01 probe build](procedures/TP-01-pad-force.md) | Build and calibrate the probe board: pinch probe, load-cell and two-thermocouple reader, cutoff relay, TP-01 part A | (needed by TP-01, 02, 04, 05, 06, 07, 13) | 90 | controls / firmware |
| 3 | 1 Parts, before assembly | [TP-11](procedures/TP-11-printed-fit.md) | Fit of the printed parts and the wrist interface | R22, R23, M12, M15 | 55 | CAD / tolerancing |
| 4 | 1 Parts, before assembly | [TP-12](procedures/TP-12-finger-stiffness.md) | Finger tip stiffness and fold load | R12, M10 | 40 | finger / FEA |
| 5 | 1 Parts, before assembly | [TP-13](procedures/TP-13-servo-and-rail.md) | Servo stall torque, hold current and power rail | R16, R27, M6, M16 | 35 | actuator / electrical |
| 6 | 1 Parts, before assembly | [TP-15](procedures/TP-15-gear-step-load.md) | Gear sector step-load test (destructive, spare pair) | R13, M17, M21 | 60 | gears |
| 7 | 2 Core afternoon (R14, R15, R19, R20) | [TP-09](procedures/TP-09-mass-envelope.md) | Mass, centre of mass, envelope and moment arm | R9, R10, R17, M13, M14 | 25 | CAD / design basis |
| 8 | 2 Core afternoon (R14, R15, R19, R20) | [TP-08](procedures/TP-08-backlash-repeatability.md) | Backlash, calibration repeatability and motion range | R18, R21, M8 | 25 | mechanical / firmware |
| 9 | 2 Core afternoon (R14, R15, R19, R20) | [TP-01](procedures/TP-01-pad-force.md) | Pad force against command and FSR calibration | R14, R3, M11, M18 | 64 | controls / firmware |
| 10 | 2 Core afternoon (R14, R15, R19, R20) | [TP-04](procedures/TP-04-force-cap-and-trip.md) | Force cap and over-force trip | R15, R18 | 45 | controls (R15 owner: Douglas) |
| 11 | 2 Core afternoon (R14, R15, R19, R20) | [TP-05](procedures/TP-05-stall-backoff.md) | Stall detection and back-off | R20 | 40 | firmware / electrical |
| 12 | 2 Core afternoon (R14, R15, R19, R20) | [TP-16](procedures/TP-16-fault-detection.md) | Sensor and limit-switch fault detection | R15, R18, R20 | 45 | firmware / electrical |
| 13 | 2 Core afternoon (R14, R15, R19, R20) | [TP-03](procedures/TP-03-close-time.md) | Close time and approach speed | R19, R6 | 25 | firmware (R19 owner: Douglas) |
| 14 | 2 Core afternoon (R14, R15, R19, R20) | [TP-02](procedures/TP-02-hold-and-slip.md) | Hold under tension with cloth slip detection | R14, M2, M3 | 45 | grip / design basis |
| 15 | 3 On the arm | [TP-07](procedures/TP-07-thermal-soak.md) | Thermal soak over the duty cycle | R26, M7 | 50 | electrical / actuator |
| 16 | 3 On the arm | [TP-14](procedures/TP-14-work-cell.md) | Work cell layout and arm load | R24, M1, M3, M5, M5b, M19 | 40 | integration |
| 17 | 4 Unattended | [TP-06](procedures/TP-06-endurance.md) | Endurance cycling screen | R25, R13, M22 | 30 | mechanical (gears, finger) |
<!-- order:end -->

Build and calibrate the pinch probe (TP-01 parts A and the probe build) during session 1, because TP-13 uses the calibrated load cell. TP-13's hold-current ratio (R16) is completed after TP-01 in session 2. TP-10 part A is desk work; part B needs the powered gripper on the bench. TP-09's wrist-sweep step (R9) needs the arm, so it runs in session 3.

"Tell if it fails" names the requirement owner to contact. Douglas owns DB and both open requirements (R15 cap, R19 close time).

## 2. The two open requirements

Douglas ruled on R15 and R19 on 2026-10-12: pad force <= 8 N and full close <= 0.75 s (the second, ruled value of each pair is the requirement; the written 10 N and 0.50 s are superseded 2026-10-12 and kept as a history column). Every procedure that touches them still records the result against both values, so the 10 N and 0.50 s columns are informational only; [VERIFICATION-MATRIX.md](VERIFICATION-MATRIX.md) section 1 lists what each value changes in the design.

- **R15 force cap: 10 N as written, about 8 N proposed.** The finger folds at 8.4-8.9 N (`finger.md`), so a written 10 N cap has no margin. At 8 N the firmware must change before TP-04 can pass (trip 7 N, soft limit 6.5 N, squeeze cap 3.79°), and the softest finger R12 allows (0.88 N/mm) can then no longer reach 5 N.
- **R19 close time: 0.75 s ruled; 0.5 s superseded 2026-10-12.** As written it fails on contact by about 10 ms. At 0.75 s it passes to 4.5 N and to 5.0 N on every finger in the R12 window (latest 5.0 N 0.691 s at 0.88 N/mm).

## 3. What a failure means, and whom to tell

| Procedure fails | What it means for the design | Tell |
|---|---|---|
| TP-01 pad force | The FSR span or the force loop is off; R14 cannot be claimed. Re-run `CALF` against the probe first; if the true force still sits under 5 N, the finger is softer than R12 allows | Controls / firmware owner |
| TP-02 slip | The cloth friction μ is under 0.4, or the hold force is low. Raises the hold setpoint, which the servo (R16) and the cap (R15) may not allow | DB owner (grip, M2) |
| TP-03 close time | R19 is not met at the value in force. The fix is firmware speed (with a shock re-check) or a ruling on R19 | Douglas (R19), firmware owner |
| TP-04 force cap | **Safety.** A grip can exceed the cap: stop using the gripper on the arm until the trip or the squeeze cap is fixed | Controls owner, Douglas (R15) |
| TP-05 stall back-off | **Safety.** A blocked finger keeps full stall on the mesh: gear and servo life (LC3) are at risk | Firmware / electrical owner |
| TP-06 endurance | A part wears or cracks before 1e4 grips: the life claim (R25) fails for that part. Note which part | Mechanical owner (gears, finger) |
| TP-07 thermal | The servo runs hotter than 60 °C: shorten the hold, add the back-off-on-friction firmware option (`dyno.md` section 4), or change servo | Actuator / electrical owner |
| TP-08 backlash, calibration | The jaw does not repeat: calibration (R21) or the knuckle pins (tolerancing fix 9) | Mechanical / firmware owner |
| TP-09 mass, envelope | Too heavy for the arm at full reach (R10) or hits the wrist (R9). Mass must come off, or the arm must not reach full extension | CAD owner, DB owner |
| TP-10 course rules | A course rule is not met: this is a grading risk, fix before the demo | Team lead |
| TP-11 printed fit | Holes, pilot or inserts do not fit as printed: change the CAD sizes per `tolerance_stacks.md` | CAD / tolerancing owner |
| TP-12 finger stiffness | Finger outside R12: change ribs or wall (`finger.md` section 1) | Finger / FEA owner |
| TP-13 servo, rail | Servo weaker than assumed or rail sags: R16 margin is gone; consider DS3235 (backup) | Actuator / electrical owner |
| TP-14 work cell | The cell layout puts too much tension moment on the arm (R24) | Integration owner |
| TP-16 fault detection | A failed FSR or a bad calibration is not caught: the force loop can run on a dead sensor. Safety | Firmware / electrical owner |
| TP-15 gear step-load | The printed gear breaks below LC3: switch material per `gears.md` (PA6-CF or POM) | Gear owner |

## 4. Files

| File | What |
|---|---|
| [VERIFICATION-MATRIX.md](VERIFICATION-MATRIX.md), `verification_matrix.csv` | One row per requirement: method, procedure, pass number, instrument, sample size, status |
| [MEASUREMENT-SIZING.md](MEASUREMENT-SIZING.md) | Uncertainty budgets, whether each instrument resolves its criterion, sample sizes |
| [EQUIPMENT.md](EQUIPMENT.md) | Shopping list with prices and sources; what to borrow |
| [procedures/](procedures/) | TP-01 to TP-16, one page each |
| [datasheets/](datasheets/) | One CSV and one printable HTML page per procedure; `SIGNOFF.csv` / `SIGNOFF.html`; `FSR-CAL.csv` (one row per FSR calibration, TP-01 part C2) |
| [tools/](tools/) | `gripper_log.py` (log the gripper's serial port), `analyze_log.py` (close times, trip times from a log), `probe/probe.ino` (load-cell and thermocouple reader) |
| `test_plan.py`, `test_plan_out.json`, `test_plan_stdout.txt` | The calculator and its results |
| `check_matrix.py`, `check_firmware.py`, `test_test_plan.py` | Coverage check; firmware-name check (every event, fault, state, command and `config.h` constant the procedures and tools use exists in `firmware/gripper/`); unit tests (`python -m pytest docs/gripper/test -q`). Run `check_firmware.py` again whenever the firmware changes |

## 5. Requested changes (outside this folder; nothing here was edited for them)

These need an owner other than the test plan. Each says the file, the change and the number behind it.

| # | File | Change | Number behind it |
|---|---|---|---|
| 1 | `cad/gripper/` (CAD rev B), `docs/gripper/DESIGN-BASIS.md` R17 | The CAD nominal r_c is 65.0 mm and R17 is r_c ≤ 65 mm, so a perfect part measures INDETERMINATE (U 0.049 mm). Either aim r_c ≤ 64.9 mm in CAD (finger 0.1 mm shorter) or restate R17 with a tolerance | PASS needs r_c ≤ 64.95 mm |
| 2 | `docs/gripper/DESIGN-BASIS.md` R19 | State the last-3° clause for the command (20 °/s) and give the jaw its own limit (25 °/s screening limit used here [A]); as written (jaw ≤ 20 °/s) a conforming jaw cannot be cleared | Design speed 20 °/s, modelled jaw 21 °/s at contact + 3° (`controls.md` 4.2), video U 2.2 °/s |
| 3 | `docs/gripper/DESIGN-BASIS.md` R10; `docs/gripper/RISK.md`; `cad/gripper/README.md` | Record the owner-ruling disposition: CAD revision B settles the older BOM/design-basis estimate disagreement, R10 fails at full reach, and holds are prohibited beyond the computed COM reach. Keep the test-plan wording and risk controls aligned | 52,995 g·mm / 43,720 g·mm; 285.9 mm COM reach |
| 4 | `firmware/gripper/inputs.cpp`, `protocol.*` | The FSR span from `CALF` lives in RAM and returns to 1.0 at every power-up. Persist it (NVS) or add a `SPAN <x>` command so a stored calibration can be re-applied; until then TP-01 part C2 redoes `CALF` after every power cycle | `FSR_SPAN_DEFAULT` 1.0, `inputs.cpp` line 12 |
| 5 | `firmware/gripper/` (PR 20, merged) | Mostly done here: TP-16 rows E-H (limit stuck closed, FSR open, FSR frozen, current sensor lost), TP-05 part D (stall after contact, the 2.0 A `STALL_CURRENT_HOLD_A` trip), TP-07 reads the F4 `Ih=` field. Still open: no procedure step exercises `ILIM <A>` (a TP-07 variant would) | PR 20, `config.h` |
