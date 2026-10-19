# Payload, finger torque and PWM actuator trade study

Lane W2a, 2026-09-22 (fix pass 2). This note works backwards: the arm's payload sets a mass budget, the grip sets a torque, and the torque picks the actuator. It then scores every PWM actuator in the market scan. The design basis is `docs/gripper/DESIGN-BASIS.md` (it wins where the two disagree).

- **Script:** `analysis/gripper/payload_torque.py`. Inputs are `cad/gripper/params.json`, `cad/so101/so101_old_calib.urdf`, `cad/so101/Simulation/SO101/so101_old_calib.xml` and `docs/gripper/research/actuators.csv`. Outputs are `analysis/gripper/results/payload_torque.json`, its stdout `analysis/gripper/results/payload_torque_stdout.txt`, and the figures `docs/gripper/figures/payload_*.png` and `actuator_*.png`.
- **Re-run** from the repository root (about 60 s): `uv run --with mujoco --with numpy --with scipy --with matplotlib python analysis/gripper/payload_torque.py > analysis/gripper/results/payload_torque_stdout.txt`
- **Tags:** [S] sourced (URL), [D] derived by the script, [A] assumed. Every input carries its tag in `payload_torque.json` → `inputs`. Every number below is [D] unless it is tagged otherwise.
- **CSV:** the script appends 3 rows (W01, W02, L01) and 9 columns (`output_interface`, `horn_included`, `mount_pattern`, `stock_checked`, `interface_source`, `torque_mid_kgcm`, `torque_mid_at_V`, `flange_span_mm`, `ear_hole_pattern_mm`) to `actuators.csv`, and fills published dimensions into empty cells only (M02, L01). It never changes a filled original cell. This pass settled the CSV once; a second run leaves it unchanged (`csv_extended_this_run: false`), MD5 **b97d52efdccf80a415a61d725cfef437**.
- **Runs:** the actuator study is evaluated four ways (`runs` in the JSON): hold rule 40 % or 25 % of stall, applied to **every** brushed-DC-driven actuator alike (servos contain brushed or coreless DC motors), on the 6.0 V baseline rail or the design rail band 6.5 ± 0.15 V [A]. On the band, hold capacity, speed and break-even use the low end (6.35 V); LC3 mesh torque and the voltage-rating check use the high end (6.65 V). The headline is `r40_design`.

## 0. Answer

| Item | Result |
|---|---|
| Arm payload (design point C001 at 7.4 V), worst pose | The worst pose over the joint ranges (optimised, sl −0.21, el 0.25, wf −0.04 rad) loads shoulder_lift with 0.934 N·m, 1 % above the zero pose (0.924). The arm can carry **103.9 g of gripper hardware at its current COM (31.7 mm)**, net of cloth and FSR wiring. The current estimate is 97.3 g, so the margin is **6.6 g (97.7 % use)**. With the 10 g wrist camera the allowance is 94.2 g: **use 101.1 %, the camera case fails by 3.1 g**. Inside the work cell (reach ≤ 0.30 m) the allowance is ≥ 217 g at d = 40 mm |
| Hold torque | **0.792 N·m (8.07 kg·cm)** at r_c = 65 mm: the design-basis 0.765 N·m plus 0.027 N·m from the tension moment on the pads. Peak at the 10 N cap: 1.556 N·m |
| Stall needed | ≥ 20.2 kg·cm at the 40 % hold rule [A]; ≥ 32.3 kg·cm at 25 % [S, Pololu brushed-DC guidance] |
| Speed needed | ≥ 81 °/s with no load (≤ 0.74 s/60°). Every standard servo exceeds this by 4× or more |
| Servo rail | **6.5 ± 0.15 V** [A] from an adjustable buck, below the DS3218MG's 6.8 V maximum rating [S]. At the 6.35 V low end the DS3218MG hold margin is 1.034 (SpeedyFPV) / 1.022 (Miuzei) |
| Passing every hard constraint (40 % rule, design rail) | Servos **A17 DS3218MG, A19 DS3235**. A18 DS3225 now fails the arm budget at the worst pose (100.8 %); A20 PDI-6221MG fails the rail (6.0 V maximum). Three DC gearmotor + printed-stage configurations also pass, but only by running their Pololu motors above Pololu's own 25 % rule (section 3.3) |
| **Primary** | **DS3218MG (A17) on the 6.5 ± 0.15 V rail.** Scripted rule (`recommendation.rule`). In stock, $12.99, 58 g, 25T spline. LC3 at 6.65 V is 2.09 N·m, so PETG m1.5 z20 gears pass |
| **Backup** | **DS3235 (A19).** Drop-in (same 40 × 20 body, 25T spline, 54.5 mm ear span), hold margin 1.62, the only servo that holds at the 25 % rule (1.014). Sold out at the cited vendor; its 3.28 N·m LC3 needs PA6-CF gears |
| DC gearmotor branch | **M02 Pololu 380:1 HPCB + encoder + printed two-stage 8:1 + DRV8833** (scripted `dc_pick`, same pick under both hold rules). Holds at Pololu's 25 % rule (1.006), 15.9 g, gripper at 83 % of the arm budget. Closes in **0.58 s, so R19 must be relaxed to 0.6 s**. No DC configuration that respects its vendor's hold rule meets 0.5 s within the arm budget |
| Score (design rail, vendor-consistent pool) | A19 0.514 ≈ A17 0.502. Monte Carlo over weights ±50 %: P(rank 1) A19 58 %, A17 42 %. A statistical tie; stock decides |

## 1. SO-101 payload

### 1.1 Cross-check: hand calculation against MuJoCo

The hand calculation does its own forward kinematics on the URDF (numpy), then sums m g × r projected on each joint axis. MuJoCo reports `qfrc_bias` on `so101_old_calib.xml`. The zero pose is the arm horizontal. The new gripper is the DS3218MG mass model (section 3.7), entered as point masses.

| Joint (N·m, zero pose) | Stock: URDF hand / MuJoCo | Arm only: hand / MuJoCo | New gripper: hand / MuJoCo Jacobian / MuJoCo lumped |
|---|---|---|---|
| shoulder_lift | 0.855 / 0.855 | 0.527 / 0.527 | 0.924 / 0.924 / 0.924 |
| elbow_flex | 0.453 / 0.453 | 0.234 / 0.235 | 0.503 / 0.503 / 0.503 |
| wrist_flex | 0.117 / 0.117 | 0.030 / 0.030 | 0.146 / 0.146 / 0.146 |

All three methods agree within 0.001 N·m and reproduce the `so101.md` values (0.527 / 0.855). The lever from shoulder_lift to the gripper origin is 309.1 mm.

### 1.2 Worst-case poses

A grid sweep (36 × 36 × 13 over shoulder_lift, elbow and wrist_flex) seeds a bounded Nelder-Mead maximisation of each joint torque (`worst_pose_sweep`). The optimiser can only equal or exceed its grid seed, so the maximum is real, not a grid artefact.

| Joint | Optimised max, no camera / camera (N·m) | Worst pose sl, el, wf (rad) | Grid max | Zero pose |
|---|---|---|---|---|
| shoulder_lift | **0.9339 / 0.9665** | −0.21, 0.25, −0.04 | 0.934 / 0.966 | 0.924 / 0.956 |
| elbow_flex | 0.5036 / 0.5248 | −1.16, 1.20, −0.04 | 0.504 / 0.525 | 0.503 / 0.525 |
| wrist_flex | 0.1455 / 0.1535 | −0.60, 2.39, 1.36 | 0.146 / 0.154 | 0.146 / 0.154 |

The worst shoulder_lift pose is about 1 % above the zero pose: a slight shoulder rotation with the elbow bent back puts the combined COM marginally further out than the nominal horizontal. Everything payload-related below (allowable mass, budget use, the hard filter) is evaluated at this optimised worst pose; zero-pose values are kept in the JSON as `*_zero_pose_*_reference` only.

### 1.3 Process tension as a TCP force

A 2 N external force is applied at the pad centroid (105.7 mm past the gripper origin) with `mj_applyFT`, cross-checked against Jᵀ F. Both agree.

| Direction at full extension | shoulder_lift | elbow_flex | wrist_flex (N·m) |
|---|---|---|---|
| Along the arm (±x) | 0.000 | 0.000 | 0.000 |
| Lateral (±y) | ±0.046 | ∓0.010 | 0.000 |
| Vertical (±z) | ±0.829 | ±0.603 | ±0.334 |

At the feed poses (fingertip at bed height, tension horizontal in the worst of four directions, 1661 poses) the tension adds at most **0.093 N·m** at shoulder_lift, in the **0.10 m reach bin** (also 0.17 m for C001 7.4 V and C018; `feed_pose.tension_sl_max_in_work_cell`). That is below the design basis's hand rule of 0.10 N·m (2 N × 50 mm). A vertical pull at full extension (0.83 N·m) would break every kit, which is why the work-cell rule R24 exists.

### 1.4 Allowable gripper mass against COM offset

"Hardware" means everything except three fixed items: the cloth (13.5 g at the pad), the FSR wiring (5 g at 40 mm) and, optionally, the camera (10 g at 20 mm). Each fixed item is entered at its own position. Each value is the minimum over the joint ranges (optimised).

- **Static:** |τ| ≤ 50 % of stall on shoulder_lift, elbow and wrist_flex [A].
- **Dynamic:** 1.5 × gravity ≤ 80 % of stall [A].

Static hold governs at every d (the dynamic limit is 14–31 g looser). Plot: `docs/gripper/figures/payload_allowable_mass.png`.

| Kit (stall) | d = 20 | d = 30 | d = 40 | d = 50 mm | With camera, d = 30 |
|---|---|---|---|---|---|
| C001 at 5 V (1.618 N·m [A]: the 6 V rating, so these values are optimistic) | 62.4 | 60.5 | 58.8 | 57.2 | 50.8 |
| **C001 at 7.4 V (1.912 N·m [S])** | 107.5 | 104.4 | 101.4 | 98.6 | 94.7 |
| C018 at 12 V (2.942 N·m [S]) | 265.7 | 257.9 | 250.6 | 243.7 | 248.2 |

The current hardware (DS3218MG build) is **97.3 g at d = 31.7 mm**. At that COM the allowance is 103.9 g without the camera and 94.2 g with it (`rollup_design_point_A17.allowable_at_hardware_com_worst_pose`):

| Kit | Budget use, no camera | Margin | Budget use, camera | Margin |
|---|---|---|---|---|
| C001 5 V [A, optimistic] | 115.4 % | −37.1 g | 119.5 % | −46.7 g |
| **C001 7.4 V** | **97.7 %** | **+6.6 g** | **101.1 %** | **−3.1 g** |
| C018 12 V | 63.5 % | +159.3 g | 65.7 % | +149.7 g |

To fly the camera at the worst pose on C001 7.4 V, save about 3–4 g of hardware (for example the housing at a lower infill, or shorter fasteners), or keep the arm out of the worst pose.

**Feed poses** (plot `payload_feed_reach.png`). Best configuration per 10 mm reach bin, 2 N tension, allowable hardware at d = 40 mm:

| Reach | 0.20 m | 0.25 m | 0.29 m | 0.30 m (work-cell limit) | 0.35 m | 0.39 m |
|---|---|---|---|---|---|---|
| C001 5 V [A] | 217 g | 185 g | 156 g | 149 g | 105 g | 54 g |
| C001 7.4 V | 327 g | 261 g | 226 g | 217 g | 160 g | 102 g |
| C018 12 V | 673 g | 541 g | 487 g | 471 g | 352 g | 272 g |

Inside the work cell (reach ≤ 0.30 m) every kit, including C001 at 5 V, carries the 97 g gripper with at least 1.5× margin. **Only the extended worst pose binds.** Operating rule: never hold the gripper horizontal at full reach. That rule also makes the camera affordable.

### 1.5 Dynamic margin

A min-jerk shoulder_lift swing of 0.5 rad [A] was run in both directions, ending at or starting from full extension, with the gripper lumped. Peak shoulder_lift torque from `mj_inverse`:

| Swing time | 0.3 s | 0.4 s | 0.5 s | 1.0 s | 2.0 s | 5.0 s |
|---|---|---|---|---|---|---|
| Rigid body (N·m) | 1.777 | 1.405 | 1.233 | 1.003 | 0.946 | 0.930 |
| With the model's joint damping and armature (N·m) | 3.830 | 2.848 | 2.357 | 1.574 | 1.259 | 1.085 |

The shortest swing that stays within 80 % of stall:

| Kit | Rigid body | With model damping |
|---|---|---|
| C001 5 V [A, optimistic] | 0.5 s | 2.0 s |
| C001 7.4 V | 0.4 s | 1.5 s |
| C018 12 V | 0.3 s | 0.75 s |

The duty cycle's 5 s lift-and-move is well clear in both models. The 0.5 g rule in LC5 corresponds to a swing of about 0.4 s. The damping row treats the simulator's identified `sts3215` damping (0.6 N·m·s/rad, from `joints_properties.xml`) as a real loss. That is conservative, and M19 should settle it.

## 2. Finger force and torque

### 2.1 Force: target and cap

Friction model: the cloth is pinched between two pads, and each pad supplies friction μN. Pads that open into a V at angle θ push the cloth out toward the tips with 2 N sin θ. At slip:

N = SF · T / ((μ_A + μ_B) cos θ − 2 sin θ)

| Case | Required N per pad |
|---|---|
| Base: μ 0.4 on both pads [A], T 2 N [A], SF 2 [A], θ = 0 | **5.00 N** (matches R14) |
| Finger A contacts through its PLA nail (μ_A 0.25 [A], μ_B 0.4) | **6.15 N** (+23 %) |
| Ejection limit, with no tension held | θ < atan μ = 21.8° |

The asymmetric-finger design (D7) puts a PLA nail on finger A. If the nail touches the cloth instead of TPU, the target rises 23 %. Put a TPU skin on the nail's inner face, or keep the nail below the pad centroid.

**Pad angle at contact.** θ_c = asin((n·t − g₀)/(2 r_c)): −0.31° for 1 ply, −0.18° for 2, +0.09° for 4, +0.88° for 10 plies (3 mm hem). The pads are effectively parallel at contact, so ejection is negligible in the demo. The sensitivity row in section 2.4 shows what happens if a thick seam forces θ = 5°.

### 2.2 Lever

r_c is the perpendicular distance from the pivot to the pad-normal line: r_c = root (25 mm) + L − 5 mm (D2). It does not change with jaw angle, because the pad rotates with the finger.

| Finger L (mm) | 30 | 40 | **45** | 50 | 60 | 70 |
|---|---|---|---|---|---|---|
| r_c (mm) | 50 | 60 | **65** | 70 | 80 | 90 |
| T_hold (kg·cm) | 6.27 | 7.47 | **8.07** | 8.67 | 9.87 | 11.07 |

If the cloth is caught 10 mm up the pad instead of at the centroid, r_c drops to 60 mm (−8 % torque). Plot: `actuator_torque_vs_lever.png` shows the required hold torque against r_c for μ 0.3–0.6, with each candidate's 40 %-of-stall line at 6.35 V.

### 2.3 Torque, η and the tension term

T_servo = (2 F r_c + T x_f) / η, where x_f = m z/2 − g₀/2 = 11.5 mm and η = 0.85 [A]. Derivation: the friction force that carries the tension acts along the finger axis at the pad's x offset from each pivot. On both fingers it acts in the opening direction, and through the 1:1 mesh it adds to the servo load.

| Load | Value |
|---|---|
| T_hold (LC1 + tension) | **0.792 N·m = 8.07 kg·cm** (the tension term is 0.027 N·m, 3.5 %) |
| T_peak (F_cap 10 N) | 1.556 N·m = 15.87 kg·cm |
| Stall needed at the 40 % hold rule [A] | **20.2 kg·cm** (the design basis had 19.5) |
| Stall needed at 25 % of stall [S, Pololu brushed-DC guidance] | 32.3 kg·cm |

### 2.4 Sensitivity of T_hold (base 8.07 kg·cm)

Plot: `actuator_torque_tornado.png`. Ordered by swing:

| Parameter range | T_hold (kg·cm) |
|---|---|
| Tension 1–3 N (M3) | 4.04 – 12.11 |
| μ 0.6–0.3 on both pads (M2) | 5.47 – 10.67 |
| Slip SF 1.5–2.5 | 6.12 – 10.02 |
| r_c 55–80 mm | 6.87 – 9.87 |
| Pad angle 0–5° | 8.07 – 10.29 |
| η 0.95–0.70 (M18) | 7.22 – 9.80 |
| Nail μ_A 0.40–0.25 | 8.07 – 9.87 |
| x_f 11.5–14.5 mm (m1 z24 → m1.5 z20) | 8.07 – 8.15 |

Tension and μ dominate, and both are team measurements (M3, M2). Break-even at the 6.35 V low end of the rail (`breakeven_design_rail_low_end`): the DS3218MG fails the 40 % hold rule if the tension exceeds **2.07 N** or μ falls below **0.386**. The DS3235 holds up to 3.25 N, or down to μ 0.243 (at the 25 % rule: 2.03 N, μ 0.394). Past either DS3218MG limit, switch to the DS3235 or shorten r_c.

### 2.5 Preload and overtravel from finger stiffness

The finger stiffness k (N/mm at the tip pad) is assumed; the FEA lane refines it. Each finger deflects δ = F/k, which is θ_over = δ/r_c of extra servo rotation past contact. At θ_min = −11° the position limit alone caps the force at F = k r_c (θ_c − θ_min).

| k (N/mm) | Overtravel at 5 N | θ_hold | Overtravel at the 10 N cap | Force at θ_min | Force per degree |
|---|---|---|---|---|---|
| 0.42 (preliminary FEA lane, tip) | 11.9 mm / 10.5° | −10.8° | 21.0° | 5.1 N | 0.48 N |
| 0.76 (preliminary FEA lane, tip) | 6.6 mm / 5.8° | −6.1° | 11.6° | 9.2 N | 0.86 N |
| 0.88 (design-basis minimum) | 5.7 mm / 5.0° | −5.3° | 10.0° | 10.7 N | 1.00 N |
| **1.00 (default)** | 5.0 mm / 4.4° | −4.7° | 8.8° | 12.1 N | 1.13 N |
| 1.63 (design-basis maximum) | 3.1 mm / 2.7° | −3.0° | 5.4° | 19.8 N | 1.85 N |

The preliminary FEA-lane values (0.42–0.76 N/mm, `analysis/gripper/results/fea_stdout.txt`; not this lane's result) fall below the design-basis window. At 0.42 N/mm the 5 N hold needs −10.8°, only 0.2° inside θ_min, and the position cap tops out at 5.1 N. Either stiffen the tip toward ≥ 0.88 N/mm, or widen θ_min to about −15° and let the FSR trip (8 N) enforce the cap. The torque does not depend on k: the servo sees the same 2 F r_c/η at the hold.

### 2.6 Speed

The close runs from +20° to θ_hold within 0.5 s (R19):

- The last 3° before contact are held to 20 °/s, which takes 0.15 s.
- The 4.4° of overtravel is limited to 60 °/s [A] so the FSR loop can ramp force, which takes 0.073 s.
- That leaves 0.277 s for the remaining 17.3°. With a trapezoid factor of 1.3 [A], the actuator needs **≥ 81 °/s with no load (≤ 0.74 s/60°)**.

Loaded speed during overtravel is taken as ω₀(1 − T/(2 T_stall)). The passing servos close in 0.27–0.28 s. Speed does not constrain servos. It does constrain every gearmotor, worm and linear option (section 3).

## 3. Actuator trade study

### 3.1 Rows and columns added to `actuators.csv` (append only)

| id | Part | Price [S] | Key data [S] | Why it was added |
|---|---|---|---|---|
| W01 | NFP-WG1218S-N20 6 V 1030:1 worm gearmotor (B45 type) | $12.50 | Stall ≤ 3 kg·cm; rated 1.2 kg·cm at 15 rpm; 22 rpm with no load; ≤ 0.65 A; about 13 g; 3 mm shaft; self-locking | Worm micro gearmotor class (critic gap) |
| W02 | Same with encoder (NFP-WG1218S-N20-EN-SD) | $16.50 | Gearbox specs assumed equal to W01 [A] | Worm + feedback |
| L01 | Actuonix PQ12-100-6-R micro linear servo, RC PWM input | $149.95 (SparkFun) | 40 N at 6 mm/s peak power; 50 N maximum; 35 N back-drive; 10 mm/s with no load; 20 mm stroke; 21 g; 36.5 × 21.5 × 15 mm retracted; 1.0–2.0 ms pulses; 20 % maximum duty | Micro linear actuator class (critic gap) |

Interface columns for the shortlisted parts, from public text or drawings only [S]:

| id | Output | Horn | Mount | Ear span | Stock when checked (2026-09-22) | Source |
|---|---|---|---|---|---|---|
| A17 | 25T spline, 5.9 mm | 1× aluminium arm + 4× plastic | Standard flange; body 40.0 × 20.5 × 40.5 mm; 4 ear holes on 49.5 × 10 mm | 54.5 mm | In stock, 14 units | [SpeedyFPV](https://speedyfpv.com/products/ds3218mg-digital-servo-high-speed-high-torque-metal-gear-waterproof-20kg-torque-180-degrees-w-accessories); [Miuzei drawing](https://images-na.ssl-images-amazon.com/images/I/81Lbgu+nG6L.pdf) |
| A18 | 25T spline | 2× 25T adjustable metal arm | Standard flange; body 40 × 20 × 40.5; ear-hole spacing not published | not published | **Unavailable** (the design basis said in stock) | [MakerFocus](https://www.makerfocus.com/products/digital-servo-25kg) |
| A19 | 25T spline | Optional arm (datasheet §8) | Standard flange; body 40 × 20 × 38.5; 4 ear holes on 49.5 × 10 mm | 54.5 mm | Sold out | [DS3235 datasheet](https://hajim.rochester.edu/me/sites/kelley/me240/DS3235-270_datasheet.pdf) §1, 3, 4, 7 |
| A20 | 25T ("Metal Teeth:25T" stated for the -360 variant; "25T Arm" listing option) | 25T arm offered as an option; inclusion not stated | Standard flange; body 40.5 × 20.2 × 38; mounting pattern not published | not published | Sold out | [RCDrone](https://rcdrone.top/products/jx-20kg-servo-pdi-6221mg) (JX site not retrievable: certificate error) |
| M02 | 3 mm D-shaft, 9 mm long | None (hub or printed coupler) | No holes on the motor; Pololu bracket pair #989 ($2.95, #2-56 screws), captures the 10 × 12 mm gearbox; body 32 × 12 × 10 mm | n/a | Listed $32.45, "Active and Preferred"; 11 g | [Pololu 5200](https://www.pololu.com/product/5200), [specs](https://www.pololu.com/product/5200/specs), [bracket 989](https://www.pololu.com/product/989) |
| M01 / M04 | 3 mm D-shaft (same gearbox family as M02 [A]) | None | Bracket pair #989 | n/a | Listed $32.45 / $29.95 | [Pololu 5193](https://www.pololu.com/product/5193/specs), [5173](https://www.pololu.com/product/5173) |
| A13 | Not published | Not published | Not published | not published | Listed $35.77 | [Pololu 3443](https://www.pololu.com/product/3443) |
| W01/W02 | 3 mm shaft, 8 mm, right-angle worm | None | N20 + worm gearbox; dimensions only in the page's outline image | n/a | Listed | [NFP](https://nfpshop.com/product/12mm-metal-gear-motor-model-nfp-n20-gm1218s) |
| L01 | 20 mm stroke rod, 3 mm rod-eye hole | n/a | 2 brackets + M3 hardware included | n/a | In stock | [PQ12 datasheet](https://www.actuonix.com/assets/images/datasheets/ActuonixPQ12Datasheet.pdf) |

A17 and A19 share the ear pattern (49.5 × 10 mm, 54.5 mm across), so one housing bay fits both. A18 and A20 do not publish it; measure on the part (M9) before committing the housing to them.

### 3.2 Hard filter (all 38 rows, design rail 6.5 ± 0.15 V, 40 % rule)

Constraints, in order:

1. PWM control with position hold. Continuous-rotation servos fail.
2. Price ≤ $50 [S ruling].
3. Rail: the band's high end (6.65 V) must not exceed the part's rated maximum [S row data].
4. Hold capacity ≥ 0.792 N·m at the band's low end (6.35 V):
   - every brushed-DC drive (servo or gearmotor): hold fraction × stall, 40 % in this run and 25 % in the `r25_*` runs; gearmotors are further capped at the Pololu gearbox limit [S];
   - worm: the gearbox rating, because it self-locks [A];
   - linear: back-drive force × crank arm.
5. Close ≤ 0.5 s (R19).
6. Arm budget: worst-pose hold utilisation ≤ 100 % of C001 7.4 V (section 1.2).
7. Envelope: body ≤ 45 × 25 × 45 mm [A], **mounting ears excluded**; the ear-to-ear span is checked separately against the 56 mm servo bay [A] where `flange_span_mm` is published (A17, A19: 54.5 mm, pass). Rows whose dimensions are not in public text (W01/W02, some micros and gearmotors) are marked "not checked" in the JSON.

Stall torque at a rail voltage is interpolated piecewise-linearly over every published (V, torque) point, including the DS3235's 32 kg·cm at 6 V (datasheet §4, `torque_mid_kgcm`).

| Outcome | Rows |
|---|---|
| **Pass** | A17 DS3218MG (margin 1.034, r_c,max 67.3 mm, close 0.278 s, arm 97.7 %), A19 DS3235 (1.622, 106.9 mm, 0.268 s, 98.4 %) |
| Fails the arm budget only | A18 DS3225: hold 1.189, but 100.8 % of the arm budget at the worst pose (67 g) |
| Fails the rail only | A20 PDI-6221MG: rated 6.0 V maximum. On the 6.0 V baseline it passes (margin 1.006) |
| Fails hold (closest) | A13 FS5115M-FB 0.77 (best feedback servo, r_c,max 49 mm; also rated 6.0 V), A16 MG996R 0.50, A14/A12/A15 ≈ 0.3 |
| Fails hold (micro servos, feedback micros) | A01–A11, A24–A27 (0.03–0.20 N·m; A26 has no torque data). All are also rated below 6.65 V |
| Continuous rotation | A21–A23 |
| DC gearmotors, direct drive | M01–M08: 0.02–0.35 N·m, far short. M07/M08 also exceed the arm budget (111–116 %); M07 exceeds the envelope |
| Worm, direct drive | W01/W02: 0.29 N·m (2.7× short) |
| Linear | L01: the torque passes (1.29 N·m passive through a 37 mm crank), but it fails price ($149.95) and speed (2.03 s close) |

**Rail voltage and the DS3218MG datasheet conflict** (`datasheet_conflict_A17`). The DS3218MG is rated 4.8–6.8 V [S Miuzei, SpeedyFPV]. A 6.8 V rail would sit exactly at the maximum, with no room for buck set-point tolerance, load regulation or back-drive transients, so the rail is set to **6.5 V ± 0.15 V** [A, reversible]. The two datasheets disagree at 5 V (Miuzei 18 kg·cm, SpeedyFPV 19 kg·cm) and agree at 6.8 V (21.5 kg·cm):

| Rail | SpeedyFPV stall / hold margin (40 %) | Miuzei stall / hold margin (40 %) | Margin at 25 % (SpeedyFPV / Miuzei) |
|---|---|---|---|
| 6.0 V (baseline) | 20.39 kg·cm / 1.010 | 19.94 / **0.988 (fails)** | 0.631 / 0.617 |
| **6.35 V (band low end)** | 20.88 / **1.034** | 20.63 / **1.022** | 0.646 / 0.639 |
| 6.5 V (nominal) | 21.08 / 1.044 | 20.92 / 1.036 | 0.653 / 0.648 |
| 6.65 V (band high end) | 21.29 / 1.055 | 21.21 / 1.050 | 0.659 / 0.657 |

The pick survives the derated rail on either datasheet. The DS3218MG stall current is 2.2 A at 6.8 V [S Miuzei]; the ≥ 3 A rail of R27 still covers it.

### 3.3 Servo against DC on one hold rule, and the gearmotor + reduction branch

Each DC motor gets a printed spur stage (m0.8, z12 pinion, one or two stages, largest gear ≤ 45 mm [A], η 0.9 per stage [A]), sized two ways: for the hold alone, and also to keep the gearbox under its limit at the 10 N cap. Where both sizings give the same ratio the JSON lists one configuration with both tags. A DRV8833-class H-bridge sits with the MCU (+$5 [A], 0 g on the gripper).

**Both branches under the same rule** (design rail; `runs.r40_design`, `runs.r25_design`):

| Hold rule | Servos that pass | DC configurations that pass every hard constraint | Best DC near-miss |
|---|---|---|---|
| **40 % for all** | A17 (1.034), A19 (1.622) | M02 + 4.5:1 one stage (43 mm gear, 16.8 g, 0.42 s), M01 + 12.75:1 (18.5 g, 0.44 s), M04 + 6.25:1 (14.9 g, 0.46 s) | M02 + 8:1 (cap-sized, margin 1.60, 0.58 s) |
| **25 % for all** | A19 only (1.014; 0.991 at 6.0 V, so it needs the design rail) | **None within the arm budget.** M07 JGA25 + 11.25:1 closes in 0.36 s but loads the arm to 113 % | M02 + 8:1 (1.006, 0.58 s), M01 + 20:1 (1.002, 0.57 s) |

So the earlier claim "no DC configuration closes within 0.5 s" was true only on a mixed basis. Under one 40 % rule, three Pololu configurations pass. But Pololu publishes its own rule for exactly these motors: **"25% or less of the stall current"** [S, Pololu micro metal gearmotor page]. At that rule the three 40 %-passing configurations hold only 0.63–0.64 of the requirement (`hold_margin_vendor_rule`). The 40 % rule for servos is an open assumption that M6/M7 test; for the Pololu motors it contradicts the vendor. The recommendation therefore draws only from configurations that also hold under their vendor's published rule (`vendor_hold_rule` input [S], `trade_vendor_consistent`).

Fallback table (40 % run; in the 25 % run the hold-sized M01, M02, M04 and M06–M08 configurations need larger N, as shown in the extra M01 + 20:1 row):

| Configuration | N (stages) | Largest gear | Mass | Hold margin 40 % / vendor rule | Close | LC3 mesh | Arm use | Result |
|---|---|---|---|---|---|---|---|---|
| M02 380:1 HPCB + enc + 4.5:1 | 4.5 (1) | 43 mm | 16.8 g | 1.002 / 0.63 | 0.42 s | 0.99 N·m | 83 % | Passes at 40 %; exceeds Pololu's 25 % |
| M01 150:1 HPCB + enc + 12.75:1 | 12.75 (2) | 34 mm | 18.5 g | 1.017 / 0.64 | 0.44 s | 2.03 | 84 % | Same |
| M04 298:1 HP + enc + 6.25:1 | 6.25 (2) | 24 mm | 14.9 g | 1.004 / 0.63 | 0.46 s | 0.99 | 83 % | Same |
| **M02 380:1 HPCB + enc + 8:1** | 8 (2) | 27 mm | **15.9 g** | 1.604 / **1.006** | **0.58 s** | 1.59 | 83 % | Fails R19 by 0.08 s |
| M04 298:1 HP + enc + 10:1 | 10 (2) | 30 mm | 17.0 g | 1.606 / 1.002 | 0.61 s | 1.59 | 83 % | Fails R19; precious-metal brushes [S] |
| M01 150:1 + 20:1 (25 % run) | 20 (2) | 43 mm | 22.4 g | – / 1.002 | 0.57 s | 3.18 | 85 % | Fails R19; LC3 needs PA6-CF |
| M03 1000:1 HPCB + enc + 3.75:1 / 8:1 | 3.75 / 8 | 36 / 27 mm | 15.1 / 15.9 g | 1.04 / 2.0 | 0.67 / 1.25 s | 0.83 / 1.59 | 83 % | Fails R19 |
| M06 DFRobot 100:1 + 16.75:1 | 16.75 (2) | 39 mm | 27.6 g | 1.01 | 0.65 s | 2.00 | 87 % | Fails R19 |
| M07 JGA25 20:1 + 7:1 | 7 (2) | 25 mm | 100.3 g | 1.01 | 0.31 s | 2.00 | 113 % | Fails the arm budget |
| M08 JGA25-370 + 2.5:1 | 2.5 (1) | 24 mm | 112.0 g | 1.00 | 1.12 s | 1.99 | 117 % | Fails R19 and arm budget |
| W01/W02 worm + 3:1 (hold) / 6.75:1 (cap) | 3 / 6.75 | 29 / 25 mm | 15.7 / 17.2 g | 1.0 / 2.0 | 0.86 / 1.60 s | 0.79 / 1.61 | 83 % | Fails R19. Self-locking, so zero hold current |

**DC pick** (scripted `dc_pick`, `recommendation.dc`): best score among vendor-consistent DC configurations that pass every hard constraint; if none, best among those whose only failure is R19 with close ≤ 0.6 s. None passes, so the pool is the R19 near-misses. **Pick: M02 + 8:1 under both rules** (score 0.743 at 40 %, 0.545 at 25 %). M01 + 20:1 closes 15 ms faster but is 6.5 g heavier and doubles LC3 (3.18 N·m, PA6-CF gears), so it scores lower (0.493). The DC branch saves about 42 g against the servo, keeps LC3 at 1.59 N·m (PETG m1.5 z20 passes at 36.5 MPa) and meets the DC-motor rule without argument, but it needs **R19 relaxed to 0.6 s** and closed-loop position control on the encoder in firmware.

### 3.4 Weighted scoring

| Criterion | Weight | Utility rule |
|---|---|---|
| Torque margin | 0.20 | margin 1.0 → 0, ≥ 1.6 → 1 |
| Mass | 0.20 | 80 g → 0, 10 g → 1 |
| Availability | 0.15 | in stock 1, listed 0.5, sold out 0 |
| Cost | 0.10 | $50 → 0, ≤ $10 → 1 |
| Spec confidence | 0.10 | [A]: A19 0.8 (a full datasheet with currents; weight listings disagree, 60 vs 80 g); A17 0.5 (two datasheets disagree on 5 V torque and current); A18 / A20 0.4 (vendor page plus conflicting listings); Pololu 0.9 |
| Overload (gear burden) | 0.05 | LC3 4 N·m → 0, ≤ 1.5 → 1 |
| Sensing (pot / encoder) | 0.05 | 1 / 0 |
| Course DC-motor certainty | 0.05 | servo 0.5 (pending the GSI), DC motor 1 |
| Simplicity | 0.05 | servo 1, motor + driver + stage 0.3 |
| Speed margin | 0.05 | 1 − t_close / 0.5 s |

Plots: `actuator_scores.png` (stacked utilities of every passing configuration at 6.35 V; `*` marks those that exceed their vendor's rule) and `actuator_weight_sensitivity.png` (rank under each weight × 0.5 / × 1.5).

All passing configurations, design rail, 40 % rule (`runs.r40_design.trade`):

| Rank | Configuration | Score | P(rank 1), weights ±50 %, Monte Carlo n = 4000 | Vendor rule |
|---|---|---|---|---|
| 1 | M02 + 4.5:1 | 0.550 | 59 % | exceeds (0.63) |
| 2 | M01 + 12.75:1 | 0.538 | 0 % | exceeds (0.64) |
| 3 | M04 + 6.25:1 | 0.519 | 0 % | exceeds (0.63) |
| 4 | A19 DS3235 | 0.514 | 31 % | ok |
| 5 | A17 DS3218MG | 0.502 | 10 % | ok |

The DC configurations score high on mass, course certainty and sensing, but each holds only by over-running its motor past Pololu's rule. Vendor-consistent pool (`runs.r40_design.trade_vendor_consistent`, the pool the recommendation uses):

| Rank | Part | Score | P(rank 1) | P(top 2) |
|---|---|---|---|---|
| 1 | A19 DS3235 | 0.514 | 58 % | 100 % |
| 2 | A17 DS3218MG | 0.502 | 42 % | 100 % |

One weight at a time (× 0.5 / × 1.5): A19 stays first in 15 of 20 cases. A17 takes first when the torque-margin or spec-confidence weight halves, or when overload, availability or cost gains 50 %. On the 6.0 V baseline the order is the same (A19 0.511, A17 0.496, A20 0.310; P(rank 1) 60 / 40 %). The top pair is a statistical tie, and the tie breaks on stock: A17 can be bought now; A19 cannot at its cited vendor.

### 3.5 Top 3: tradeoffs

The three are the primary, the backup and the DC branch (A18 is out on the arm budget, A20 on the rail rating).

| | A17 DS3218MG | A19 DS3235 | M02 + 8:1 (DC branch) |
|---|---|---|---|
| Hold margin, 6.0 V / 6.35 V (40 %) | 1.010 / 1.034 | 1.585 / 1.622 | 1.604 (motor at 6 V) |
| At the 25 % hold rule | 0.631 / 0.646 | 0.991 / 1.014 | 1.006 |
| r_c,max at 6.35 V (40 %) | 67.3 mm | 106.9 mm | – |
| Close time | 0.28 s | 0.27 s | **0.58 s (fails R19 0.5 s)** |
| LC3 through the mesh (6.65 V) | 2.09 N·m | 3.28 N·m | 1.59 N·m |
| Gear that survives LC3 (b = 6) | m1.5 z20 PETG (48.0 MPa ≤ 51) | m1.5 z20 PA6-CF only (75.3 MPa) | m1.5 z20 PETG (36.5 MPa) |
| Actuator mass / price | 58 g / $12.99 | 60 g (80 g in some listings) / $24.49 | 15.9 g / $37.45 incl. H-bridge [A] |
| Stock (2026-09-22) | In stock | Sold out | Listed |
| Arm use, C001 7.4 V, worst pose (no camera / camera) | 97.7 % / 101.1 % | 98.4 % / 101.8 % | 83.0 % / 86.4 % |
| Hardware margin, C001 7.4 V (no camera / camera) | +6.6 / −3.1 g | +4.6 / −5.1 g | +48.0 / +38.4 g |
| Firmware | Servo PWM, FSR loop | Same | Encoder position loop + H-bridge PWM |

### 3.6 Recommendation

Scripted rule (`recommendation.rule`): from the vendor-consistent passing pool, primary = best score that is in stock at its cited vendor, backup = next best; DC branch = `dc_pick`.

- **Primary: A17 DS3218MG on a 6.5 ± 0.15 V servo rail** [D; the rail is a reversible assumption, A]. It is the best in-stock part in the pool. At the 6.35 V low end both datasheets give a hold margin ≥ 1.022, and PETG m1.5 z20 gears survive LC3 at the 6.65 V high end. Buy 3 (two spares for the M6/M7 destructive tests). Downstream change: `mcu.power.servo_rail_V` goes from 6.0 to 6.5 V with a ±0.15 V tolerance, which needs an adjustable buck rather than a fixed 6 V UBEC.
- **Backup: A19 DS3235.** Drop-in (same ear pattern, 25T spline). Switch to it if M6 measures the DS3218MG stall below 20.2 kg·cm at the rail, if M7 shows the 40 % hold overheats (the 25 % rule would then govern, and A19 is the only servo that passes it), if tension (M3) exceeds 2.07 N, or if μ (M2) falls below 0.386. Switching costs PA6-CF gears, or a firmware current limit that keeps LC3 under 2.1 N·m. It also cuts the hardware margin to 4.6 g.
- **Under the 25 % rule** (`recommendation_25pct_rule`): primary A19 (flagged: not in stock at the cited vendor), no servo backup, DC branch M02 + 8:1.
- **DC branch (if the GSI says a servo does not count, or the 25 % rule governs and A19 cannot be bought):** M02 380:1 HPCB + encoder + printed 8:1 two-stage + DRV8833, with R19 relaxed to 0.6 s. Same pick under both rules.
- **Rejected:** feedback servos (A06–A13; the best, FS5115M-FB, reaches only 77 %); A18 (arm budget), A20 (6.0 V rating); worm gearmotors (too slow once geared to torque); PQ12-R (3× over budget, 4× too slow).

### 3.7 Mass roll-up with the primary

Plot: `actuator_mass_rollup.png` (primary, backup, DC branch).

| Item | g | d past the gripper origin (mm) | Tag |
|---|---|---|---|
| Housing (PLA, 60 % fill) | 18.7 | 25.0 | D (gripper_concept.py) |
| Knuckles | 6.0 | 40.7 | D |
| Fingers TPU, L = 45 | 6.6 | 80.7 | D (scaled from 8.8 g at 60) |
| DS3218MG | 58.0 | 29.0 | S mass |
| Horn, pins, fasteners | 8.0 | 20.0 | A |
| FSR + wiring | 5.0 | 40.0 | A |
| Cloth at the pad | 13.5 | 105.7 | D |
| **Total** | **115.8** | COM 40.7 | |
| Wrist camera (optional) | 10.0 | 20.0 | A |

Budget use (worst pose over the joint ranges, 50 % of stall; `rollup_design_point_A17`):

| Kit | No camera | With camera |
|---|---|---|
| C001 5 V [A, optimistic] | 115.4 % (fails) | 119.5 % |
| **C001 7.4 V** | **97.7 %** | **101.1 % (fails)** |
| C018 12 V | 63.5 % | 65.7 % |

In the feed envelope (≤ 0.30 m) every kit passes. If the camera must fly at the worst pose on C001 7.4 V, save about 3–4 g of hardware.

## 4. What this changes downstream

| Where | Change | Tag |
|---|---|---|
| `DESIGN-BASIS.md` R16 / `params.json grip` | Stall needed 20.2 kg·cm, not 19.5: add the tension term (T x_f/η = 0.027 N·m) | D |
| `params.json mcu.power.servo_rail_V`, R27 | 6.0 → **6.5 V ± 0.15 V** (adjustable buck, ≥ 3 A); state the tolerance in R27 and verify it with the R27 scope test at stall | A, reversible |
| `DESIGN-BASIS.md` section 5 | Tag C001 at 5 V as [A], optimistic (1.618 N·m is the 6 V rating) | A |
| `DESIGN-BASIS.md` D4 | DS3225 is no longer in stock at its cited vendor, and at 67 g it exceeds the worst-pose arm budget | S / D |
| Payload budget | Worst pose, not the zero pose: 6.6 g hardware margin; the camera needs about 3–4 g saved | D |
| Gear lane | LC3 = 2.09 N·m with A17 at 6.65 V (m1.5 z20 PETG passes at 48.0 MPa); 3.28 N·m with the A19 backup (PA6-CF) | D |
| Finger / FEA lane | Preliminary k 0.42–0.76 N/mm is below the 0.88 window: θ_min −11° then caps force at 5.1–9.2 N. Stiffen the tip or widen θ_min | D |
| Finger A nail | Keep the PLA nail out of the pad contact, or skin it with TPU: 23 % more force otherwise | D |
| Operating rule | Never hold the gripper horizontal at full extension. Inside 0.30 m reach the payload margin is ≥ 1.5× on every kit | D |
| R19 | Relax to 0.6 s only if the DC branch is taken | D |

## 5. Team must measure (in priority order)

| # | What | Why it decides |
|---|---|---|
| M6 / M7 | DS3218MG stall at 6.35–6.65 V; case temperature after 30 min at the hold | The margin is 3.4 %; the hold rule (40 % vs 25 %) is the largest unknown and flips the primary to A19 |
| M3 | Process tension | T_hold swings from 4.0 to 12.1 kg·cm over 1–3 N; A17 breaks even at 2.07 N |
| M2 | Pad–cloth μ (and nail–cloth μ) | 5.5–10.7 kg·cm over μ 0.6–0.3; A17 breaks even at 0.386 |
| R27 | Buck output at servo stall | Confirms the 6.35–6.65 V band |
| M20 | GSI ruling on servo = DC motor | Chooses between the servo and the DC branch |
| M10 | Tip stiffness | Sets θ_hold and whether θ_min caps force |
| M9 | Horn and ear-hole pattern on the bought part | A17 drawing gives 49.5 × 10 mm; confirm before printing the housing |
| M19 | Arm shoulder load at the worst pose | Validates the 50 % rule, the 6.6 g margin and the damping row in section 1.5 |

## Sources

- SpeedyFPV DS3218MG (price, stock, 25T spline, horns, 4.8–6.8 V): https://speedyfpv.com/products/ds3218mg-digital-servo-high-speed-high-torque-metal-gear-waterproof-20kg-torque-180-degrees-w-accessories
- Miuzei DS3218 datasheet (18 / 21.5 kg·cm at 5 / 6.8 V, 1.8 / 2.2 A, 4.8–6.8 V, ear drawing): https://images-na.ssl-images-amazon.com/images/I/81Lbgu+nG6L.pdf
- DS3235 datasheet (29 / 32 / 35 kg·cm at 5 / 6 / 7.4 V, 25T spline, ear drawing): https://hajim.rochester.edu/me/sites/kelley/me240/DS3235-270_datasheet.pdf
- MakerFocus DS3225 (25T, stock): https://www.makerfocus.com/products/digital-servo-25kg
- RCDrone PDI-6221MG (25T, stock): https://rcdrone.top/products/jx-20kg-servo-pdi-6221mg
- Pololu micro metal gearmotors (2.5 / 2 kg·cm gearbox limit; "25% or less of the stall current"; HP vs HPCB brushes): https://www.pololu.com/category/60/micro-metal-gearmotors
- Pololu 380:1 HPCB + encoder (M02; shaft, 10 × 12 × 32 mm, 11 g): https://www.pololu.com/product/5200 and https://www.pololu.com/product/5200/specs; bracket pair: https://www.pololu.com/product/989
- Pololu FS5115M-FB: https://www.pololu.com/product/3443
- NFP N20 worm gearmotor (6 V B45 table, price): https://nfpshop.com/product/12mm-metal-gear-motor-model-nfp-n20-gm1218s
- Actuonix PQ12 datasheet: https://www.actuonix.com/assets/images/datasheets/ActuonixPQ12Datasheet.pdf; SparkFun PQ12-100-6-R (price): https://www.sparkfun.com/products/18591
- Everything else: the row URLs in `docs/gripper/research/actuators.csv` and the sources list in `DESIGN-BASIS.md`.
