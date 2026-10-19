# Cloth-feed gripper: design basis

Single source of truth for every later lane (concept, trade study, FEA, gears, tolerancing, firmware, CAD). Dated 2026-09-22. Where this file and a research note disagree, this file wins; the research notes keep the evidence.

- **Numbers:** every derived number here comes from `docs/gripper/design_basis.py`. Its inputs are `cad/gripper/params.json`, `docs/gripper/research/actuators.csv` and the MuJoCo model `cad/so101/Simulation/SO101/so101_old_calib.xml`. Its output is `docs/gripper/design_basis_out.json`. Re-run with `uv run --with mujoco --with numpy python docs/gripper/design_basis.py` (about 5 s).
- **Machine-readable copy:** `cad/gripper/params.json` blocks `materials` (extended), `grip`, `payload_scenarios`, `wrist_interface`, `work_cell`, `duty_cycle`, `mcu`.
- **Tags:** **[S]** sourced (URL in the Sources list, or the research note named), **[D]** derived (by the script, or by the equation shown), **[A]** assumed. Every [A] is reversible. Each one that matters has a measurement in section 10.
- **Rulings applied** (Douglas, 2026-09-22, `LOG.md`): the actuator is PWM-controlled, not the STS3215 serial bus; it costs ≤ $50; the gripper is compact and light; only public, cited sources are used; reversible assumptions are recorded and do not stop the work.

## 0. Decisions at a glance

| # | Decision | Why | Tag |
|---|---|---|---|
| D1 | Actuator class: **PWM hobby servo** at a dedicated **6.0 V** rail. A PWM DC gearmotor, H-bridge and extra reduction stage are kept only as a documented fallback in the trade study | PWM ruling. The servo contains a brushed DC motor and is PWM-driven, so we assume it meets the course DC-motor rule. **Confirm with the GSI** | A *Superseded 2026-10-09: rail is 6.5 ± 0.15 V (DS3218MG 21.08 kg·cm stall at 6.5 V, LC3 2.09 N·m at 6.65 V); see `analysis/torque_and_actuator.md` and `firmware/gripper/config.h`.* |
| D2 | Grip contact = **tip pad**. Moment arm r_c = perpendicular distance from the pivot to the pad-normal line of action; it does not change with jaw angle | Cloth is pinched at the tip (`cloth_and_camera.md` 2.4) | D |
| D3 | Design moment arm **r_c = 65 mm**, which means a 45 mm finger with the current 25 mm knuckle root. The current CAD has r_c = 80 mm | At 80 mm only one PWM servo in the scan (DS3235, out of stock) holds LC1 within the hold rule. At 65 mm four do, two of them in stock at ≤ $19 | D |
| D4 | Design-point servo for bookkeeping: **DS3218MG** (A17: $12.99, 58 g, 20.4 kg·cm at 6.0 V). In-stock alternative: DS3225 (A18). The W2a trade study makes the final pick | The lightest in-stock servo that passes | D *Superseded 2026-10-16: rev B.1 builds the DSServo DS3230 MG (A32: $27.00, 60 g, 29.33 kg·cm stall at 6.5 V = 2.876 N·m, 3.99 A sizing stall current per `analysis/gripper/actuation/results/actuation_trade.json`; `cad/gripper/out/parts.json` `servo_model`); see `firmware/gripper/config.h`.* *Superseded 2026-10-09: rail is 6.5 ± 0.15 V (DS3218MG 21.08 kg·cm stall at 6.5 V, LC3 2.09 N·m at 6.65 V); see `analysis/torque_and_actuator.md` and `firmware/gripper/config.h`.* |
| D5 | Arm design point: **C001 at 7.4 V**. C001 at 5 V and C018 at 12 V are carried as scenarios | Brief; the math confirms C001 at 7.4 V closes (section 5) | D |
| D6 | MCU: **ESP32 DevKitC**, Arduino IDE, ESP32Servo. Section 8 lists what changes on an Uno | Brief | A |
| D7 | Fingers are asymmetric. **A** (driven) carries a stiff 1.0 mm PLA tip "nail". **B** (idler) carries the FSR behind a rigid backing | The nail slides under the cloth edge (`cloth_and_camera.md` 2.2). Table contact then loads the servo shaft, not the mesh | A |
| D8 | The force cap is enforced by **position** (θ_min = −11°) and by an FSR trip at 8 N. It is never enforced by FSR saturation | The FSR range ends at 10 N [S], above the 8 N cap | D *Superseded 2026-10-12 (Douglas): the cap is 8 N (R15); the FSR range end no longer equals it.* *Superseded 2026-10-09: firmware floor is θ_min −7.4° (10 N angle for the L45 finger); see `analysis/finger.md` section 6.3 and `firmware/gripper/config.h` `JAW_MIN_DEG`.* |
| D9 | Camera: a **fixed overhead** camera is primary. The housing reserves a wrist-camera pad with 2× M3 hex-nut points (upstream Hex-Nut adapter pattern) and a 10 g mass allowance | `cloth_and_camera.md` 3; upstream mounts at `eecbe3e` | A |
| D10 | Fabrication: FDM print in PLA/PETG, TPU 95A fingers, gears in PETG or PA6-CF (section 9). CNC POM/Al only if printed gears fail the bench tests | Lead time and cost | A |

## 1. Requirements

Source: **course** = ME102B project rules as given in the brief; **team** = Douglas's rulings and goals; **derived** = computed here from the two.

| ID | Requirement | Value | Source | Proof (observable) |
|---|---|---|---|---|
| R1 | ≥ 1 moving transmission DOF | Jaw DOF: servo → knuckle A → 1:1 spur sector → knuckle B. **Confirm with the GSI that a 1:1 pair counts** [A]. Fallback: add a ≥ 2:1 pinion stage ahead of sector A | course | Demo plus assembly drawing |
| R2 | ≥ 1 DC motor | PWM hobby servo (brushed DC motor inside) [A, confirm with the GSI]. Fallback: Pololu HPCB gearmotor + H-bridge + extra reduction ≥ 3.12:1 for hold, ≥ 6.24:1 if the gearbox must carry the cap, or a worm [D] | course | GSI answer recorded in `LOG.md` |
| R3 | ≥ 1 analog input | FSR on finger B → ESP32 ADC1 (GPIO 34). Optional second: servo pot tap on GPIO 32 | course | `analogRead` trace during a grip |
| R4 | ≥ 1 digital button | START/STOP button (GPIO 25, pull-up). Plus a jaw-open limit switch (GPIO 26) for homing | course | Event log shows a press event |
| R5 | Microcontroller | ESP32 DevKitC, Arduino IDE [A] | course | `arduino-cli compile` passes |
| R6 | State machine + event-driven code | States and events in section 8. No blocking `delay()` | course | Code review; event log |
| R7 | Actuator is PWM-controlled, not the STS3215 bus | 50 Hz, 500–2500 µs [A] | team | BOM |
| R8 | ≤ $50 per actuator | DS3218MG $12.99 [S] *Superseded 2026-10-16: rev B.1 builds the DS3230 MG, $27.00 [S A32, `cad/gripper/params.json`]; still under $50.* | team | BOM with vendor link |
| R9 | Compact | Stays inside the stock gripper's rolling envelope by z band (`so101.md`), or wrist-flex clearance is re-checked. Hub ≤ Ø24 for z ≤ H+1 and ≤ Ø30 for z ≤ H+4.5 [D] | team | CAD interference check |
<!-- r10-work-cell-rule:begin -->
| R10 | Light | **Keep R10 at 43,720 g·mm**, cloth included. That equals ≤ 125 g at 40 mm past H. Current estimate: **53,342 g·mm** (122.0 %, 153.9 g, rev B.1 CAD, `cad/gripper/out/fitcheck.json`) [D]; the budget is exceeded at full reach. *Superseded 2026-10-16: the earlier estimate 40,507 g·mm (93 %, 115.8 g) was the pre-CAD number; rev A as built was 50,131.* Stretch goal: ≤ 33,380 g·mm, the stock loading [D]. Work-cell rule: no holds with the gripper COM farther than r_limit = 284.1 mm from the shoulder_lift axis (43,720 g·mm / 153.9 g); the equivalent fingertip limit is 342.6 mm. Douglas ruled this disposition on 2026-10-11. [D `cad/gripper/out/fitcheck.json`; owner ruling] | team / derived | Weigh the part and balance it for the COM; enforce the reach gate in TP-14 |
<!-- r10-work-cell-rule:end -->
| R11 | Public, cited sources only | No pirated PDFs | team | Source list |
| R12 | Compliant fingers | Fin Ray, TPU 95A. Tip stiffness per finger at the tip pad **0.88 ≤ k ≤ 1.63 N/mm**, default 1.0 [D] | team / derived | Weight-and-deflection test (M10) |
| R13 | Strong gear profile | Passes LC1 fatigue, LC2 static and LC3 overload with the allowables in section 4 | team / derived | Gear script; bench step-load test |
| R14 | Hold force | ≥ **5.0 N** per pad at the tip pad through the 25.5 s hold. This resists 2 N of tension with slip SF 2 at μ = 0.4 [D] | derived | FSR reads ≥ 5 N; no slip in the pull test |
| R15 | Force cap | Pad force ≤ **8 N**. Enforced by θ ≥ −11° and an FSR trip (`F_TRIP_N`, `config.h`) | owner ruling | FSR log never exceeds 8 N *Superseded 2026-10-12 (Douglas): the 10 N cap [A] was lowered to about 8 N; firmware settings and simulation in `analysis/controls.md` 4.4 and 6.4.* *2026-10-16 (T09): the firmware jaw floor is θ_c0 − 4.9° (`JAW_FLOOR_BELOW_C0_DEG`, was 6.2°), which holds 8 N with the trip failed (T09F) and bounds the peak at the trip (T09P); trip 7.75 N and the squeeze cap unchanged; `analysis/controls.md` 6.4.* *Superseded 2026-10-09: firmware floor is θ_min −7.4° (10 N angle for the L45 finger); see `analysis/finger.md` section 6.3 and `firmware/gripper/config.h` `JAW_MIN_DEG`.* |
| R16 | Servo hold rule | Hold torque ≤ 40 % of stall at 6.0 V [A]. So stall ≥ **19.5 kg·cm** at r_c = 65 mm [D] | derived | Datasheet plus bench stall test (M6) *Superseded 2026-10-09: rail is 6.5 ± 0.15 V (DS3218MG 21.08 kg·cm stall at 6.5 V, LC3 2.09 N·m at 6.65 V); see `analysis/torque_and_actuator.md` and `firmware/gripper/config.h`.* |
| R17 | Moment arm | r_c ≤ 65 mm (finger length ≤ 45 mm with a 25 mm knuckle root) [D] | derived | CAD |
| R18 | Motion range | θ ∈ **[−11°, +20°]**. θ = 0 means the rigid pads are 1 mm apart; negative θ is overtravel into the grip [D] | derived | Servo limits in firmware; CAD at both ends *Superseded 2026-10-09: firmware floor is θ_min −7.4° (10 N angle for the L45 finger); see `analysis/finger.md` section 6.3 and `firmware/gripper/config.h` `JAW_MIN_DEG`.* |
| R19 | Jaw speed | Full close in ≤ **0.75 s**. The last 3° before contact at ≤ 20 °/s to limit impact [A] | owner ruling | Timed video *Superseded 2026-10-12 (Douglas): was full close in ≤ 0.5 s [A]; the 0.75 s close time funds the slower approach that holds the 8 N cap (`analysis/controls.md` 4.4).* |
| R20 | Stall protection | Detect stall and back off within ≤ 200 ms (INA219 servo current, or FSR/pot) [A] | derived | Block a finger; log the time to back-off |
| R21 | Calibration | A CALIBRATE state after HOME closes with no cloth until FSR ≥ 0.5 N and stores θ_c0. This replaces the ±0.34 mm closed-gap stack (tolerancing S2) | derived | Boot log shows θ_c0 |
| R22 | Wrist interface | Section 3, block `wrist_interface` (measured from the upstream CAD) | derived | Coupon fit on the real horn |
| R23 | Camera provision | 2× M3 hex-nut camera points on the housing; 10 g allowance. The camera is off until CV starts | team | CAD |
| R24 | Work cell | Shoulder_lift axis within ±50 mm of the cloth tension line. Feed-pose reach ≤ 300 mm [A] | derived | Layout sketch |
| R25 | Life | Gears and fingers survive 1e5 grip cycles [A] | derived | Fatigue check; bench run |
| R26 | Thermal | Servo case ≤ 60 °C after 30 min of the section 7 duty cycle at LC1 [A] | derived | IR thermometer |
| R27 | Power | Dedicated 6.0 V servo rail rated ≥ 3 A (≥ 1.3 × the 2.2 A DS3218 stall current [S]), 1000 µF bulk capacitor at the servo, common ground with the ESP32 [D/A] | derived | Scope on the rail during a stall *Superseded 2026-10-09: rail is 6.5 ± 0.15 V (DS3218MG 21.08 kg·cm stall at 6.5 V, LC3 2.09 N·m at 6.65 V); see `analysis/torque_and_actuator.md` and `firmware/gripper/config.h`.* |

## 2. Load cases

Symbols: F = pad normal force per finger; r_c = 65 mm; η = 0.85 (mesh plus pivots) [A]; T_servo = 2·F·r_c/η [D, statics: finger A's moment goes straight to the shaft, finger B's crosses the 1:1 mesh]; T_mesh = T_servo/2 in a symmetric pinch (conservative, because η is taken on the whole path).

| LC | Condition | Loads [D unless tagged] | Occurrence | Check against |
|---|---|---|---|---|
| LC1 | **Grip hold** (target) | F = 5.0 N. T_servo = 0.765 N·m (7.80 kg·cm). T_mesh = 0.383 N·m | 1e5 cycles [A]; 25.5 s dwell each; R ≈ 0 on one flank | Fatigue allowable / 1.5; servo hold ≤ 40 % of stall; finger strain ≤ 10 % |
| LC2 | **Grip peak / cap** | F = 10 N. T_servo = 1.529 N·m (15.6 kg·cm). T_mesh = 0.765 × K_A 1.25 = 0.956 N·m | ≤ 1e3 events [A] (impact at contact, over-command) | X-Y tensile / 1.5 *Superseded 2026-10-12 (Douglas): cap 8 N (R15): T_servo = 1.223 N·m, T_mesh = 0.612 × 1.25 = 0.765 N·m; the 10 N case stays the bounding margin.* |
| LC3 | **Stall overload, one finger blocked** (for example finger B snagged, servo still driving) | The whole stall torque crosses the mesh: T_mesh = DS3218MG stall at 6.0 V = 2.00 N·m | Rare; ≤ 0.2 s each (R20) | X-Y tensile / 1.0 (no fracture) *Superseded 2026-10-09: rail is 6.5 ± 0.15 V (DS3218MG 21.08 kg·cm stall at 6.5 V, LC3 2.09 N·m at 6.65 V); see `analysis/torque_and_actuator.md` and `firmware/gripper/config.h`.* |
| LC4 | **Process tension** | 2 N [A] along the feed, carried by pad friction. Moment on a finger about its pivot ≤ 1 N × 11.5 mm (x_f) = 0.012 N·m [D, equation]. Arm: 0.10 N·m at shoulder_lift under the work-cell rule (2 N × 50 mm). The worst direction at full extension would give 0.84 N·m [D] | Every feed, 20 s | Arm hold budget (section 5); slip (R14) |
| LC5 | **Dynamic** (arm moves) | Gravity × (1 + 0.5 g/g) [A]. Shoulder_lift at full extension: 0.924 × 1.5 = 1.39 N·m, against 0.8 × stall = 1.53 N·m on C001 at 7.4 V: passes [D] | Every move | 80 % of arm stall [A] |
| LC6 | **Static payload** | Gripper + cloth 115.8 g, COM 40.7 mm past H. Shoulder_lift at full extension 0.924 N·m (stock gripper 0.855) [D, MuJoCo] | Holding pose | 50 % of arm stall [A] |

What the load cases imply for the gear lane (Lewis, b = 6 mm, allowables from section 4) [D]:

| Gear | σ per N·m | LC1 / LC2 / LC3 σ (MPa) | Materials that pass all three |
|---|---|---|---|
| m 1.0, z 24 (current) | 41.2 | 15.8 / 39.4 / 82.4 | PA6-CF, Al 6061 (PLA fails all three) |
| m 1.25, z 24 | 26.4 | 10.1 / 25.2 / 52.7 | PA6-CF, POM, Al |
| m 1.5, z 18 | 26.6 | 10.2 / 25.5 / 53.3 | PA6-CF, POM, Al |
| m 1.5, z 20 (a = 30) | 23.0 | 8.8 / 22.0 / 46.0 | **PETG**, PA6-CF, POM, Al |

LC3 dominates. Either the gear is sized for LC3 (m 1.5 z 20 in PETG, or m 1 z 24 in PA6-CF), or the gear lane shows that R20 plus a slip clutch keeps the mesh below LC2. The gear lane decides.

## 3. Design point

| Item | Value | Tag |
|---|---|---|
| Arm kit | SO-101 follower, STS3215 C001 at 7.4 V, stall 1.912 N·m | S (`so101.md`) |
| Gripper servo | DS3218MG at 6.0 V: 20.4 kg·cm stall (interpolated between 19 at 5 V and 21.5 at 6.8 V), 58 g, $12.99, 3 µs deadband, 40 × 20 × 40.5 mm | S values; D interpolation *Superseded 2026-10-16: rev B.1 builds the DSServo DS3230 MG (A32: $27.00, 60 g, 29.33 kg·cm stall at 6.5 V = 2.876 N·m, 3.99 A sizing stall current per `analysis/gripper/actuation/results/actuation_trade.json`; `cad/gripper/out/parts.json` `servo_model`); see `firmware/gripper/config.h`.* *Superseded 2026-10-09: rail is 6.5 ± 0.15 V (DS3218MG 21.08 kg·cm stall at 6.5 V, LC3 2.09 N·m at 6.65 V); see `analysis/torque_and_actuator.md` and `firmware/gripper/config.h`.* |
| Servo hold available | 0.40 × 20.4 kg·cm = 0.80 N·m → maximum r_c 68.0 mm | D *Superseded 2026-10-09: rail is 6.5 ± 0.15 V (DS3218MG 21.08 kg·cm stall at 6.5 V, LC3 2.09 N·m at 6.65 V); see `analysis/torque_and_actuator.md` and `firmware/gripper/config.h`.* |
| Other servos passing at r_c = 65 | DS3235 (105 mm, out of stock), DS3225 (77.4 mm), PDI-6221MG (67.8 mm, out of stock). Best feedback servo: FS5115M-FB, maximum r_c 51.7 mm, which fails | D |
| Grip | F_target 5.0 N (μ 0.3 → 6.7 N; μ 0.6 → 3.3 N), F_cap 10 N (*Superseded 2026-10-12: 8 N, R15*), contact centroid 5 mm above the tip | D / A |
| Moment arm | r_c 65 mm design, 80 mm current CAD. `viewer.html` uses 56.2 mm (radial distance to finger mid-length): stale | D |
| Servo torque | LC1 0.765 N·m; LC2 1.529 N·m | D |
| Finger stiffness | Window 0.88–1.63 N/mm per finger. The lower bound means F_cap is reached within 10° past contact [A]. The upper bound means 0.5 N per deadband step (0.27°) [A]. Default 1.0 N/mm gives 5.0 mm / 4.4° of overtravel at LC1 and 10 mm / 8.8° at the cap | D |
| Finger estimate | Scaling the tools.md FEA smoke run (2.80 mm/N at E = 26 MPa) to the TDS modulus gives 1.09 (E_xy) to 1.30 (E_z) mm/N at L = 60. At L = 45 (∝ L³) that is 0.46–0.55 mm/N, i.e. k ≈ 1.8–2.2 N/mm, **too stiff** for the window. That FEA was also stiff-biased (P1 locking). The FEA lane tunes wall, rib count and rib angle (sweep 0–45°; the published Fin Ray reference used 45° [S, `tools.md`]) to land in the window | D / A |
| Jaw angles | θ_open +20°, θ_hold ≈ −4.7° (contact at −0.3° with a 0.3 mm ply, plus 4.4°), θ_min −11° (worst-case overtravel −10.4° plus margin) | D *Superseded 2026-10-09: firmware floor is θ_min −7.4° (10 N angle for the L45 finger); see `analysis/finger.md` section 6.3 and `firmware/gripper/config.h` `JAW_MIN_DEG`.* |
| Gear | Baseline m 1 z 24 b 6 fails in PLA; candidates in section 2 | D |
| Mass estimate | 115.8 g including cloth, COM 40.7 mm past H; 125.8 g with the camera (itemised in `design_basis_out.json` → `arm.mass_items`) | D / A |
| MCU / power | ESP32 DevKitC; 6.0 V ≥ 3 A servo rail; USB 5 V logic | A *Superseded 2026-10-09: rail is 6.5 ± 0.15 V (DS3218MG 21.08 kg·cm stall at 6.5 V, LC3 2.09 N·m at 6.65 V); see `analysis/torque_and_actuator.md` and `firmware/gripper/config.h`.* |

## 4. Material allowables

Allowables: LC1 = fatigue σ_max at 1e5 cycles / 1.5; LC2 = X-Y tensile / 1.5; LC3 = X-Y tensile / 1.0 [A: safety factors]. Printed values assume 100 % solid, gear axis along Z, X-Y in-layer (`gears.md` 2.1).

| Material | ρ g/cm³ | E X-Y / Z MPa | Tensile X-Y / Z MPa | Fatigue basis | LC1 / LC2 / LC3 allow MPa | Source |
|---|---|---|---|---|---|---|
| PLA (Bambu PLA Basic) | 1.24 | 2580 / 2060 | 35 / 31 | 22.5 at 1e5, 15.5 at 1e6 (Basquin fit) [D] | 15.0 / 23.3 / 35.0 | S TDS; `gears.md` 2.1 |
| PETG (Bambu PETG Basic) | 1.25 | 2780 / 2550 | 51 / 35 | 30.6 at 1e5 [A: PLA ratio 0.60 × UTS] | 20.4 / 34.0 / 51.0 | S TDS; fatigue A |
| PA6-CF (Bambu, dried and annealed) | 1.09 | 4430 / 2170 | 102 / 48 | 57 gear-level Lewis at 6.3e6 [D from the sourced Onyx m1 z20 b6 test, 1.1 N·m] | 38.0 / 68.0 / 102 | S TDS; `gears.md` 3 |
| POM-H (machined Delrin) | 1.42 [A] | 2800 | 69 | 32 flexural at 1e6 [S] | 21.3 / 46.0 / 69.0 | S DuPont guide |
| Al 6061-T6 (machined) | 2.70 | 69,000 | 276 yield | 97 at 5e8 [S] | 64.7 / 184 / 276 | S `gears.md` 2.2 |
| **TPU 95A** (Ultimaker, printed, 0.4 mm core, 0.15 mm layers, 100 % infill) | 1.22 | 67 (XY), 67 (YZ) / 56 (Z) | Break 23.7 (XY), 37.9 (YZ) / 6.4 (Z) | No S-N data. Design by strain: ε ≤ 10 % [A]; ISO 178 flexural ran past 10 % without break [S] | Flexural strength 4.1 MPa at 9.4 % strain [S] | S Ultimaker TDS |

TPU notes. Elongation at break: > 560 % (XY), 82.3 % (Z) [S]. Flexural modulus: 62.6 MPa [S]. Hardness: 96 Shore A [S]. HDT: 50.3 °C [S]. ν = 0.45 [A]. Z (inter-layer) break strength is only 6.4 MPa [S], so print the fingers flat with the rib-bending plane in X-Y (the current extrusion along the 20 mm depth does this). `tools.md`'s E = 26 MPa is superseded. `params.json` `materials.TPU = 1.21` is kept for the script; the TDS value is 1.22 (0.8 % mass effect).

## 5. Arm kit scenarios

Static check at shoulder_lift (the binding joint) with the arm fully extended horizontally, computed in MuJoCo (`qfrc_bias`, `so101_old_calib.xml` zero pose). Arm joints hold ≤ 50 % of stall [A]. The model reproduces `so101.md`: arm alone 0.527 N·m, stock gripper 0.855 N·m [D]. Lever from shoulder_lift to H: 309.1 mm [D].

| Scenario | Stall [S] | Hold allow | Mass-moment budget (g·mm) | Max mass at 40 mm past H | New gripper at full extension, no camera | Feed pose (gravity + 0.10 N·m tension) OK up to reach | Dynamic LC5 |
|---|---|---|---|---|---|---|---|
| C001 at 5 V | 1.618 N·m (6 V rating; 5 V gives somewhat less [A]) | 0.809 | 28,720 | 82.3 g | **Fails** (0.924 N·m) | 0.36 m | Fails |
| **C001 at 7.4 V (design point)** | 1.912 N·m | 0.956 | 43,720 | 125.2 g | Passes at 97 % | Whole sweep (to 0.39 m) | Passes |
| C018 at 12 V | 2.942 N·m | 1.471 | 96,220 | 275.6 g | Passes | Whole sweep | Passes |

- **Feed-pose sweep** [D]: 1661 poses with the fingertip at bed height ± 8 mm and the gripper within 45° of straight down [A]. Reach runs 0.103–0.391 m. The best-configuration shoulder torque stays within the hold rule of all three kits up to 0.36 m (C001 at 5 V) and across the whole sweep for the others.
- **Camera:** with the 10 g wrist camera the mass-moment is 43,798 g·mm, 100.2 % of the C001 7.4 V budget. So the camera needs about 1 g saved elsewhere, or a rule that the arm never holds the gripper at full horizontal extension [D].
- **Tension:** held in the worst direction at full extension, 2 N would add 0.84 N·m and break every kit's budget. The work-cell rule R24 exists for this reason [D].
- **C001 at 5 V:** restrict the envelope (no holds at full extension) or trim the mass to ≤ 82 g at 40 mm.

## 6. Work-cell assumptions

| Item | Value | Tag |
|---|---|---|
| Sewing machine | Generic domestic. Reference Singer 4423: 1100 stitches/min maximum, 6.25 in (159 mm) needle-to-tower, 15.5 × 6.25 × 12 in (394 × 159 × 305 mm) | S (singer.com) |
| Bed height above the table the arm base sits on | 100 mm | A |
| Needle position | 159 mm left of the tower. Needle-to-front-edge and needle-to-left-end not known | S / A, measure |
| Stitch length / demo speed | 2.5 mm; 240 stitches/min → **10 mm/s** feed. Machine maximum ≈ 45.8 mm/s | A / D |
| Seam | 200 mm straight seam on one ply | A |
| Cloth | 300 × 300 mm woven cotton, 150 g/m², 0.3 mm, 13.5 g, one flat ply | A / D (`cloth_and_camera.md`) |
| Release point | ≥ 20 mm before the presser foot | A |
| Arm placement | Base on the same table. Shoulder_lift axis within ±50 mm of the cloth tension line; feed-pose reach ≤ 300 mm | A (R24) |
| Overhead camera | Fixed, about 500 mm above the bed, offset past the machine head (0.35 mm/px at 1080p) | A / D (`cloth_and_camera.md` 3.2) |
| Ambient | ≤ 40 °C | A |

## 7. Duty cycle

| Item | Value | Tag |
|---|---|---|
| Phases (s) | Approach and touchdown 4.0 · close 0.5 · lift and move to needle 5.0 · feed hold 20.0 · release 0.5 · return 5.0 | A |
| Cycle | 35 s → 102.9 cycles/h | D |
| Grip-held fraction | 72.9 % (25.5 s of 35 s) | D |
| Design life | 1e5 grips (≈ 972 h at this rate; about 10× a semester's use) for fatigue sizing | A / D |
| Servo heating proxy | Mean I²R ≈ 0.40² × 0.729 = 11.7 % of the continuous-stall loss [D, current ∝ torque, A]. Verify with R26 | D |

## 8. Electronics, firmware and power

| Item | Decision | Tag |
|---|---|---|
| Board | ESP32 DevKitC (ESP32-WROOM-32), Arduino IDE with the esp32 core; libraries ESP32Servo, Button2, Adafruit_INA219 | A |
| Analog rule | Use ADC1 pins only: ADC2 is shared with the Wi-Fi driver [S, ESP-IDF ADC oneshot]. Raw results are 12-bit by default [S, ESP-IDF ADC] | S / A |
| Pins | Servo PWM 18 · FSR 34 (ADC1) · optional servo pot 32 (ADC1) · START button 25 · open limit 26 · I²C 21/22 (INA219) · LED 2 | A |
| Servo signal | 50 Hz, 500–2500 µs. 3.3 V logic high is assumed accepted; if the servo ignores it, add a 74AHCT125 level shifter | A, measure (M16) |
| FSR | Interlink FSR 402 class (Adafruit 166), 0.3–10 N [S]. Mounted on finger B with a 1.0 mm PLA backing plate and a 6 mm puck over the active area [A]. Thresholds: touch 0.5 N, grip setpoint 5.0 N, slip below 3.0 N, over-force trip 7.75 N [A] *Superseded 2026-10-12: trip and soft limit follow the 8 N cap, `config.h` `F_TRIP_N`, `F_SOFT_LIMIT_N`.* | S / A |
| Current sense | INA219, high side of the 6 V servo rail. Used for stall detection (R20) and hold-current logging | A |
| Power | 6.0 V rail ≥ 3 A from a buck/UBEC (fed from the arm supply or a separate adapter), 1000 µF bulk capacitor, common ground. ESP32 powered from USB 5 V | A / D *Superseded 2026-10-09: rail is 6.5 ± 0.15 V (DS3218MG 21.08 kg·cm stall at 6.5 V, LC3 2.09 N·m at 6.65 V); see `analysis/torque_and_actuator.md` and `firmware/gripper/config.h`.* |
| Host link | USB serial, 115200 baud, ASCII lines. Host → MCU: `G <newtons>` (grip), `R` (release), `H` (home), `C` (calibrate), `S` (status). MCU → host: `EVT <name> <millis>`. The PC runs LeRobot for the arm and sends `ARM_AT_POSE` / `FEED_DONE` as commands | A |
| States | BOOT → HOME → CALIBRATE → IDLE → APPROACH → TOUCHDOWN → CLOSE → HOLD → FEED → RELEASE → RETRACT → IDLE, plus FAULT | A |
| Events | Button press (debounced), limit hit, FSR crosses touch / setpoint / slip / trip thresholds, over-current, host command, state timeout | A |
| Grip control | CLOSE ramps the servo angle toward θ_hold in small steps until FSR ≥ 5 N, and never below θ_min. HOLD re-steps if the FSR reads < 4.5 N. Below 3 N raises SLIP | A |
| Uno differences | 5 V logic, 10-bit ADC, `Servo.h` disables `analogWrite` on its timer's pins once the first servo attaches [S, Servo.h]; on the Uno that is Timer1, pins 9 and 10 [A], external interrupts only on D2/D3, 2 KB SRAM, no Wi-Fi | S / A |

## 9. Fabrication

| Item | Decision | Tag |
|---|---|---|
| Printer | 0.4 mm-nozzle Bambu/Prusa-class machine, direct drive for TPU. Prints PLA, PETG, TPU 95A; PA-CF optional (hardened nozzle, dried filament) | A (brief) |
| Housing and knuckles | PETG (HDT 71 °C against 57 °C for PLA, and better LC2 margin), 100 % solid in the gear region, gear axis along Z | A / S |
| Fingers | TPU 95A, printed flat | S (TDS orientation data) |
| Gears | Printed PETG (m 1.5 z 20) or PA6-CF (m 1 z 24), per section 2 | D |
| Printed vs CNC | Printed: filament cost about $1–2 per gripper set (≈ 50 g at ≈ $25/kg), same-day turnaround [A]. CNC POM/Al: quote-dependent, typically days to weeks by service [A]. Get an instant quote before switching. CNC only if printed gears fail the bench step-load test (`gears.md` 7) | A |
| Holes and fits | Per `tolerancing.md` §3d/§4: M3 clearance CAD Ø3.6–3.7, heat-set M3 Ø4.2, pilot Ø19.45 | S / D |

## 10. Team must measure

Each item has a default that is in use now. Replace it in `params.json` and re-run `docs/gripper/design_basis.py`.

| # | Quantity | Default used now | How to measure |
|---|---|---|---|
| M1 | Arm kit: servo variant and supply voltage | C001 at 7.4 V | Read the servo labels (C001 / C018) and the PSU label |
| M2 | Pad–cloth friction μ | 0.4 | Incline test: TPU pad on a board covered with the demo fabric; μ = tan θ at slip; 5 trials |
| M3 | Process tension | 2 N | Spring or luggage scale on the cloth while the machine feeds at demo speed |
| M4 | Cloth areal density and thickness | 150 g/m², 0.3 mm | Weigh a 100 × 100 mm swatch; calipers on a 10-ply stack ÷ 10 |
| M5 | Machine bed height, needle position, throat | 100 mm, 159 mm | Tape measure from the table and the machine edges |
| M5b | Feed speed at the demo pedal setting | 10 mm/s | Count stitches in 10 s × stitch length |
| M6 | Gripper servo stall torque and current at 6.0 V | 20.4 kg·cm, 2.2 A | Lever arm on the horn pressing a kitchen scale; bench supply current readout *Superseded 2026-10-09: rail is 6.5 ± 0.15 V (DS3218MG 21.08 kg·cm stall at 6.5 V, LC3 2.09 N·m at 6.65 V); see `analysis/torque_and_actuator.md` and `firmware/gripper/config.h`.* |
| M7 | Servo heating in the hold | ≤ 60 °C after 30 min | IR thermometer on the case during the section 7 cycle |
| M8 | Servo deadband / resolution | 3 µs, 0.27° | Step the pulse by 1 µs and watch a 100 mm pointer |
| M9 | Servo horn: spline, OD, hole pattern | 25T, unknown | Calipers; photograph the horn |
| M10 | Finger tip stiffness k | Target 1.0 N/mm | Clamp the printed finger at its root, hang 0.5–10 N at the tip pad, measure deflection |
| M11 | FSR force curve behind the backing | Adafruit curve | Known weights 0.5–10 N on the puck; log `analogRead` |
| M12 | Printer fits | `tolerancing.md` §4 values | Coupon: Ø3.0 / 3.4 / 3.6 holes, Ø19.45 pilot, M3 insert bore; one TPU 95A finger |
| M13 | Stock gripper mass | 99 g (URDF) | Kitchen scale |
| M14 | New gripper mass and COM | 115.8 g, 40.7 mm past H | Scale; balance on a knife edge |
| M15 | Wrist-roll horn real dimensions | Ø19.2, BC 14.0, hole depth 2.5 | Calipers on the arm's horn |
| M16 | ESP32 3.3 V PWM drives the servo | Yes | Sweep test; if it fails, add a level shifter |
| M17 | Printed gear pair life | Section 4 allowables | Step-load bench test (`gears.md` 7) |
| M18 | Mesh + pivot efficiency η | 0.85 | Measured servo torque (current) against FSR force at known r_c |
| M19 | Arm shoulder hold with the gripper at full extension | 50 % rule | Read the STS3215 load/current register while holding the pose |
| M20 | Course compliance of R1 / R2 | Servo counts; 1:1 pair counts | Ask the ME102B GSI; record the answer in `LOG.md` |

## 11. Stale values the next lanes must fix (not edited here)

| Where | Stale | Correct |
|---|---|---|
| `cad/gripper/viewer.html` | `PLA_ALLOW = 40` | LC1 15.0 / LC2 23.3 / LC3 35.0 MPa (PLA) |
| `viewer.html` | `wristOff: 35` | 61.55 mm, wrist-flex axis to H (`so101.md`) |
| `viewer.html` | Lever `rc = hypot(xf, y0 − L/2)` = 56.2 mm | r_c = root + L − 5 = 80 mm (current) / 65 mm (design) |
| `viewer.html`, `gripper_concept.py`, `params.json` `servo`, `README.md` | STS3215 envelope, 55 g, 19.5/30 kg·cm | The chosen PWM servo (design point DS3218MG) |
| `params.json` `housing.mount_*`, `README.md` | 32 mm square mount, 4× Ø3.2 on Ø20 BC, Ø8 centre | `wrist_interface` block |
| `params.json` `motion.open_angle_max` only | θ ≥ 0 | θ ∈ [−11°, +20°] (`grip.theta_min_deg`) *Superseded 2026-10-09: firmware floor is θ_min −7.4° (10 N angle for the L45 finger); see `analysis/finger.md` section 6.3 and `firmware/gripper/config.h` `JAW_MIN_DEG`.* |
| `params.json` `finger.length` | 60 | 45 (design) |
| `viewer.html` "Copy params.json" | Regenerates only the geometry blocks | Merge its output; do not paste over the file, or the new blocks are lost |
| `actuators.csv` | No spline/horn/mount columns; no worm gearmotors or linear actuators | W2a trade study adds them |
| `tolerancing.md` §7 | Monte Carlo script not committed | W2b commits a stack-up calculator |

## 12. Critic gaps and where each is resolved

| Gap | Resolution |
|---|---|
| Course compliance (servo as DC motor; 1:1 as transmission) | R1, R2, M20: assumed yes, confirm with the GSI; fallback in R2 |
| DC gearmotor cannot direct-drive (2.5 kg·cm limit) | Extra reduction ≥ 3.12:1 (LC1) / ≥ 6.24:1 (LC2), or a worm [D] |
| No sourced TPU data; load case undefined | Section 4 (Ultimaker TDS); LC1 / LC2 at the tip pad |
| Shortlist fails the 5 / 10 N budget | D3 / D4: r_c 65 mm; stall ≥ 19.5 kg·cm class; the feedback servos fail |
| Lever disagreement (56 vs 85 mm) | D2: perpendicular distance to the pad-normal line; 80 mm current, 65 mm design; the viewer is stale |
| Overtravel for compliance; θ ≥ 0 only | R12, R18: stiffness window; θ_min −11° *Superseded 2026-10-09: firmware floor is θ_min −7.4° (10 N angle for the L45 finger); see `analysis/finger.md` section 6.3 and `firmware/gripper/config.h` `JAW_MIN_DEG`.* |
| Research notes still STS3215-based | `gears.md` header note; `tolerancing.md` §5–§6 split arm and gripper servos; README/viewer in section 11 |
| Tolerancing S4 wrong interface | Fixed (Ø14.0 BC, Ø19.2 horn pilot, Ø5.4 centre) |
| `so101.md` pilot clearance | Fixed: 0.8 diametral, 0.4 per side |
| Payload depends on kit | Section 5, three scenarios |
| Payload static only; tension ignored | LC4, LC5, R24, feed-pose sweep |
| Only stall torque; hold rule assumed; power undefined | R16 (40 %, M6 / M7), R27, section 8 |
| Missing worm gearmotors and linear actuators | Section 11 → W2a |
| μ and tension assumed | M2, M3 |
| Gear loads at the force cap | LC2, LC3, gear table |
| Printed vs CNC; printer unknown | Section 9 |
| Work cell, machine, duty cycle unknown | Sections 6 and 7 |
| MuJoCo files not in the repo | Vendored at `cad/so101/Simulation/SO101/` (`cad/so101/SOURCE.md`) |
| Firmware MCU / driver / protocol / power undecided | Section 8 |
| Stale constants | Section 11 |
| M3×6 engagement vs 2.5 mm hole | `so101.md` item 2 clarified; screw = clamp + 2.5…3.0 |
| Camera mount ambiguity | D9 |
| Scratch scripts not committed | `design_basis.py` committed with its output; stack-up script → W2b |
| `gears.md` 10 vs 11.25 MPa | Fixed (11.25 → 0.27 N·m; 15.5 → 0.38 N·m) |
| Include m 1.5 z 18–20 | Section 2 gear table |
| No Fin Ray rib-angle data | FEA lane sweeps 0–45° to hit the stiffness window |
| FSR saturates at the cap | D8; backing and puck; 8 N trip; asymmetric fingers (D7) |
| No CALIBRATE state or jaw-speed requirement | R19, R21 |
| Pin citations to `eecbe3e` | Done in `so101.md`, `tolerancing.md`, `tools.md`, `cloth_and_camera.md` |

## Sources

- Ultimaker TPU 95A technical data sheet (v5.00 file; document version 2.00, 2022-04-29): https://um-support-files.ultimaker.com/materials/2.85mm/tds/TPU-95A/Ultimaker-TPU95A-TDS-v5.00.pdf
- Singer Heavy Duty 4423 product page: https://www.singer.com/products/singer-4423-heavy-duty-sewing-machine
- Pololu micro metal gearmotors (gearbox torque limits): https://www.pololu.com/category/60/micro-metal-gearmotors
- ESP-IDF ADC oneshot (ADC2 shared with Wi-Fi): https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/adc/adc_oneshot.html
- ESP-IDF ADC overview (12-bit default): https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/adc/index.html
- Arduino Servo library header (timer PWM disabled on attach): https://raw.githubusercontent.com/arduino-libraries/Servo/master/src/Servo.h
- ESP32Servo: https://github.com/madhephaestus/ESP32Servo
- Adafruit FSR 402 (product 166): https://www.adafruit.com/product/166
- SO-ARM100 at `eecbe3e`: https://github.com/TheRobotStudio/SO-ARM100/tree/eecbe3e0a9ebb23e25ad7b2759b03884c6660903 (Hex-Nut wrist camera adapter: `Optional/SO101_Wrist_Cam_Hex-Nut_Mount_32x32_UVC_Module/`; one-piece wrist camera: `Optional/Wrist_Cam_Mount_32x32_UVC_Module/`)
- Everything else is cited in the research notes: `research/so101.md`, `research/actuators.csv` / `.md`, `research/gears.md`, `research/tolerancing.md`, `research/tools.md`, `research/cloth_and_camera.md`.
