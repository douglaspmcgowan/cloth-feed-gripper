# Actuation trade: which actuator, ratio and drive to buy

Lane gripper-actuation-trade, 2026-10-11, revised after review the same day and rerun on pull request 20's firmware the same evening (section 0, "Rerun with the merged firmware"). **Recommendation: wait for the backordered DSServo DS3230 (row A32 "MG", $27.00 [S], or row A39 "PRO", $25.00 [S]; both list the same figures) and place the backorder today (it has no ship date). Fall back to the DS3235 datasheet part (A19). The only option in stock is the DS3218MG you already have (A17) with a new 1.5:1 gear stage; its arm-weight gate is marginal and it is a redesign, not a purchase.**

What this study does and does not fix:

- **Neither servo meets R14 by itself.** The firmware study measures R14 (true pad force ≥ 5 N through the hold) in **45.1 %** of grips with the present servo, for causes that do not depend on the actuator: finger stiffness, droop and force-sensor span error (pull request 20, not merged, as of 2026-10-11). This study does not model those causes. A stronger servo meets the **R16 hold-torque margin**, which is a different test.
- **Keep:** the 1:1 drive (servo horn on knuckle A, m1.5 z19 sector pair) and the 6.5 ± 0.15 V rail.
- **Change:** gear face width 8 → 10.5 mm (C1); servo pocket 20.4 → 20.5 mm with the servo located by its output boss (tolerance note T14, revision B rows 1 and 3); supply and wiring for ≥ 5 A (E1); three firmware constants and the current trip (section 5).

**Ordering status.** No part is both in stock and clearly passing. The DS3230 MG is backordered at the one vendor checked, with no ship date. The DS3230 **PRO** product page lists the same figures as the MG, $25.00, and also says the 180° version is backordered, while the collection page read earlier the same day showed "In stock" [S, `actuators.csv` row A39]. Which is right is unresolved; check it on the day of ordering.

- **Script:** `analysis/gripper/actuation/actuation_trade.py`. The model is in `model.py`, the add-on calculations in `extras.py`, and the tests in `test_actuation.py`.
  - Inputs: `docs/gripper/research/actuators.csv`, `analysis/gripper/results/payload_torque.json`, `analysis/gripper/results/gears.json` and `gears.py`, and the rev A (DS3218MG, A17) `firmware/gripper/config.h`, `analysis/gripper/firmware_sim/results/fw_sim.json` and `analysis/gripper/thermal/results/thermal.json`, pinned from commit `7e1039a` into `analysis/gripper/actuation/rev_a/` by `pin_rev_a.py` (rev B.1 re-based the live files on the DS3230 MG this study chose; read live, they would make the winner the reference).
- **Re-run** from the repository root: `python3 analysis/gripper/actuation/actuation_trade.py`.
  - `python3 analysis/gripper/actuation/actuation_trade.py --check` recomputes without writing, prints differing JSON keys, and exits nonzero when the committed result is stale.
  - It is seeded and deterministic and takes about 12 min [A, one timed run]. A rerun leaves `git status` clean.
  - It writes `analysis/gripper/actuation/results/actuation_trade.json` and `actuation_trade_stdout.txt`. The JSON has a `definitions` block that says what each probability means.
  - Every number in this note is in that stdout file or the JSON (`decision`, `recommendation`, `configs[]`), unless it is tagged [S] or [A].
- **Tests:** `python3 -m pytest analysis/gripper/actuation -q`. They cover hand calculations, limit cases, agreement with `payload_torque.json`, `gears.py`, `thermal.json` and the compiled-firmware simulation `fw_sim.json`, and agreement of this note's section 0 with the JSON.
- **Tags:**
  - [S] sourced: URL and date are in `actuators.csv`.
  - [D] derived by a repository script.
  - [A] assumed, with the reason.
  - Each model input is listed with its tag in `actuation_trade.json` → `inputs`.

## 0. Answer

**The decision** (all numbers: `actuation_trade.json` → `decision.rows`):

| | **Order today:** DS3218MG + 1.5:1 stage (A17@1.5:1) | **Wait for the backordered part** (recommended): DS3230 MG (A32) | **Fallback:** DS3235 datasheet part (A19) |
|---|---|---|---|
| Money | $13.99 [S + A]: $12.99 servo, $1 for the stage | $27.00 [S]; the PRO (A39) is $25.00 | $24.49 [S] |
| Lead time | Servo in stock (SpeedyFPV, 2026-10-11 [S]); stage designed and printed by us, no time estimate [A] | Backordered, no ship date [S]. The PRO's stock is unresolved | Sold out at RCDrone 2026-09-22; recheck returned HTTP 403 [S] |
| CAD change | **New bay:** stage centre distance 25.0 mm, no room above the ears (8.5 mm). Gear width 10 mm. Pocket 20.5 mm + boss (T14) as for every option | Gear width 10.5 mm (C1). Pocket 20.5 mm + boss (T14). Measure the delivered part (C2) | Gear width 14.5 mm. 7.1 V rail. Pocket as T14 |
| Electrical | 6.5 V, no change | 6.5 V; supply ≥ 5 A (sizing 3.99 A) | 7.1 V; supply for 6.98 A |
| Torque evidence | Datasheets (two that disagree slightly) | One vendor's listing, no datasheet | Manufacturer datasheet |
| R16 hold margin, rail low end (nominal / 5th percentile) | 1.40 / 1.09 | 1.44 / 1.02 | 1.69 / 1.33 |
| P(R16 hold-torque rule), 10 N / 8 N cap | 1.00 / 1.00 | 0.97 / 0.97 | 1.00 / 1.00 |
| R16 margin if the hold setpoint is 6 N (median / P(R16)) | 1.14 / 0.83 | 1.07 / 0.71 | 1.38 / 1.00 |
| **R14 true force ≥ 5 N, closed loop** | not modelled; 45.1 % with the present servo (firmware study) | same | same |
| R15 peak force, worst sample (cap 10 N) | 7.44 N | 7.45 N | 7.46 N |
| P(R19 at 0.75 s) / close to 4.5 N, median, 8 N cap | 0.988 / 0.631 s | 0.992 / 0.632 s | 0.994 / 0.632 s |
| Gear safety factor at stall / jam shock (8 mm face, nominal rail, two-point fit) | 1.27 / 1.05 | 1.24 / 1.02 | 1.10 / 0.90 |
| Arm hold use (SO-101 budget) | **1.005 ± 0.015: marginal** | 0.984 ± 0.013: pass | 0.984 ± 0.008: pass |
| R10 mass moment | **99.2 % of the limit, marginal** (100.8 % if the stage is 25 % heavy) | about 94 % [A] | about 94 % [A] |
| Added backlash at the jaw | +0.95° stage (1.08 mm at the pad) on top of 1.0° | none | none |
| Weakest point | Arm gate inside its own error; R10 almost used up; new bay | One vendor's torque claim and a backorder | Sold out; wider gear; new rail |

**Why wait for the DS3230.** It is the only candidate that passes every gate with the least redesign. If its delivery date is unknown after a query to the vendor, the order-today row is the way to keep moving; the stage design is days of work, not a purchase.

**The one measurement that changes this:** the stall torque of the first delivered unit. Clamp it, command full close at 6.35 V, and read the force on a 50 mm lever. **Pass: ≥ 1.98 N·m** (`bench_stall_floor`, section 7). Below that, or if the unit weighs more than 64.6 g (where the arm gate crosses 1.00), switch to the fallback. This stays the purchase gate.

**Neither fixes the 45 % hold result by itself.** All three rows meet the R16 hold-torque margin. The 45.1 % is true force at the pad, and it comes from finger stiffness, droop and sensor span error. It needs the firmware changes in pull request 20 (hold bias 1.0 N, which moves the hold setpoint to about 6 N) and the finger measurement (M10). With the 6 N setpoint the DS3230's nominal R16 margin (rail low end) falls from 1.44 to 1.20, its Monte Carlo median from 1.28 to 1.07, and P(R16) from 0.97 to 0.71: a stronger servo helps, but the hold bias eats most of the extra margin. **R19 has the same split:** the table's P(R19) is 4.5 N with an ideal sensor; the firmware study measures 5 N within 0.75 s in 49.3 % of grips with the present servo.

**Rerun with the merged firmware (2026-10-11).** The model now runs pull request 20's force loop: the 1.0 N hold bias, the stiffness estimate and gain schedule, and the squeeze cap less its 0.5 N margin (section 2). **The recommendation and the purchase gate did not change.** What moved: the simulated hold now settles near 6 N, so the peak rises to 7.44–7.46 N (was 5.70–5.71 N) and the DS3230's simulated hold current to 1.62 A median at the 10 N cap (section 5.1); with the 8 N cap the smaller squeeze cap stops some soft fingers below 4.5 N, so P(R19 at 0.75 s) falls from 1.00 to 0.99 and P(R16 and simulated force) from 0.95 to 0.92 for the DS3230.

**Does the DS3230 run hotter than the present servo?** **It depends on which reading of the present servo is right, and it does not fix R26 (case ≤ 60 °C).** Details in section 5 and `thermal_scaling_estimate`. This is a scaling estimate from `thermal.md`, not a thermal model:

- For a nominal unit it is cooler than the DS3218MG in three of four regimes (0.4–18.5 K) and **11.3 K hotter** in Fit B with the discontinuous bound (85.7 against 74.4 °C at 25 °C, no back-off).
- **At typical-unit hold currents (the Monte Carlo medians, 1.42 A against 1.06 A, 8 N cap) the picture moves against it:** cooler in Fit A (56.8 against 71.1 °C continuous, 25 °C, no back-off) but **hotter in Fit B**: 51.9 against 50.7 °C continuous and 90.7 against 74.4 °C discontinuous. Against the present servo's *nominal* case the DS3230 at its median current reaches 69.4 °C (Fit B continuous, 25 °C), over 60 °C.
- Without `thermal.md`'s friction back-off hold (F1), it exceeds 60 °C at 40 °C ambient in every regime, and at 25 °C in both discontinuous ones. With F1 and continuous conduction it passes at 40 °C (48.1 / 45.8 °C). **But the firmware study measures F1 collapsing R14 from 45.1 % to 14 % (its O16), which is why it ships off, so F1 is not a free route to R26.**
- **Rerun the thermal lane for the chosen servo (requested change T1).**

**Why the choice comes out this way:**

- **0.5 s is out of reach for every actuator in the set.** First contact can come at 0.42–0.44 s with a faster profile, but an ideal actuator reaches 4.5 N before 0.5 s only with the fast profile and a stiff finger (0.491 s at 1.63 N/mm), never with the shipped profile on a soft one (section 3).
- **The current DS3218MG (A17) at 1:1 does not qualify.** Hold margin 1.03; the hold rule is met with probability only 0.53 once a ±15 % unit-to-unit spread is applied.
- **The DS3230's own torque is a vendor claim with no datasheet.** It must pass the bench stall test before more units are bought.

Full comparison of the three rows plus the present servo:

| Item | DS3230 MG (A32) | DS3235 (A19), fallback | DS3218MG (A17), current |
|---|---|---|---|
| Price | $27.00 [S] | $24.49 [S] | $12.99 [S] |
| Torque evidence | Vendor listing only (26 / 30 kg·cm at 5.0 / 6.8 V) | Manufacturer datasheet (29 / 32 / 35 kg·cm at 5 / 6 / 7.4 V) | Two datasheets that disagree slightly, plus a vendor listing |
| Rail | 6.5 ± 0.15 V (no change) | 7.1 ± 0.15 V | 6.5 ± 0.15 V |
| Hold margin under the 40 % rule at the rail low end (nominal / MC 5th percentile) | **1.44 / 1.02** | 1.69 / 1.33 | 1.03 / 0.81 |
| P(R16 hold-torque rule), 10 N cap / 8 N cap | **0.97 / 0.97** | 1.00 / 1.00 | 0.53 / 0.53 |
| P(simulated settled force ≥ 4.9 N, ideal sensor), 10 N / 8 N cap | 1.00 / 0.95 | 1.00 / 0.96 | 1.00 / 0.96 |
| P(R16 and simulated force), 10 N / 8 N cap | 0.97 / 0.92 | 1.00 / 0.96 | 0.53 / 0.51 |
| **R14 closed-loop true force ≥ 5 N** | not modelled; firmware study: 45.1 % with the present servo | same | **45.1 %** (firmware study) |
| P(R15), 10 N / 8 N cap | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| P(R19) with 4.5 N and an ideal sensor, 0.5 s / 0.75 s, 10 N cap (8 N cap at 0.75 s) | 0.00 / 1.00 (0.992) | 0.00 / 1.00 (0.994) | 0.00 / 1.00 (0.995) |
| R19 closed loop, 5 N within 0.75 s | not modelled; firmware study: 49.3 % with the present servo | same | 49.3 % (firmware study) |
| Close to 4.5 N, shipped profile, 8 N cap, median / 95th percentile | 0.632 / 0.656 s | 0.632 / 0.655 s | 0.632 / 0.656 s |
| Pad force if the servo stalls (firmware cap failed) | 18.9 N | 22.1 N | 13.5 N |
| Gear safety factor at stall / under jam shock (8 mm face) | 1.24 / **1.02** | 1.10 / **0.90** | 1.62 / 1.33 |
| Hold motor current: nominal (5 N) / Monte Carlo median / 95th percentile (8 N cap; simulated hold about 6 N) | 1.00 / **1.42** / 1.87 A | 0.52 / 0.68 / 0.88 A | 0.81 / 1.06 / 1.38 A |
| Hold power, nominal (V × I) | 6.53 W | 3.72 W | 5.27 W |
| Stall current for rail sizing, nominal unit | 3.99 A | 6.98 A | 3.67 A |
| Mass at the wrist; SO-101 hold use | 60 g [S, listing, unverified]; 0.984 | 60 g; 0.984 | 58 g; 0.977 |
| Fit in the current housing | Body 40 × 20 × 40.5 mm. **Width is a rounded listing figure** (section 5) | Drop-in: 49.5 × 10 mm ears, 25T spline [S] | Drop-in |

**Definitions.** *R16 hold-torque rule*: the actuator can supply the hold torque (2 F r_c + T x_f) / η at ≤ 40 % of its stall torque. *Simulated settled force*: the model's pad force settles at ≥ 4.9 N, with an ideal force sensor, 0.1 N allowed, and no span error, creep or droop. *R14 closed-loop true force*: the force a real pad sees. The first two are in `actuation_trade.json` (`P_R16_…`, `P_sim_force_…`, and the `definitions` block); the third is the firmware study's.

**The fallback is the DS3235 datasheet part** (A19), from any vendor that sells that exact unit (gear ratio 373 [S]). It has the most margin, but it needs:

- a wider gear: its jam-shock safety factor is 0.90 at 8 mm and 1.01 at 10 mm; 14.5 mm reaches 1.15 (C1)
- a 7.1 V rail sized for 6.98 A [D, power relation]. Its datasheet stall current is **2.3 A** at 7.4 V; the rail sizing uses 6.98 A because the datasheet's torque (35 kg·cm) and speed (0.11 s per 60°) imply a mechanical power that needs about 7 A at the 0.62 gearbox efficiency of `dyno.md` Fit A. The two readings of the same servo are the "Fit A / Fit B" ambiguity of `thermal.md`, and nobody has measured which is right (M6).

The aifitlab "DS3235 SG" (A34) is a different variant: gear ratio 342, and 30 kg·cm at 7.4 V against the datasheet's 35 [S]. It is treated as a vendor claim, not as the datasheet part.

**Weighted score (section 6).** The DS3230 PRO (A39, $25) scores 0.652 and the MG (A32, $27) 0.646 under the proposed values, the top two eligible scores, because their listed figures are identical and the PRO is $2 cheaper. Under random weights 81.4 % of draws recommend the DS3230 and 18.6 % the DS3218MG with the 1.5:1 stage.

## 1. What was compared

- **Candidates.** All 53 rows of `actuators.csv`:
  - 36 PWM hobby and smart servos
  - 3 continuous-rotation servos
  - 11 gearmotors
  - 2 worm gearmotors
  - 1 linear servo

  Fifteen of these were added on 2026-10-11: A28–A39 and M09–M11 (`actuators.md`, section "2026-10-11 candidate extension"). A39 is the DS3230 PRO, added after review. Each row carries a source URL and retrieval date, and a price in US dollars. The exceptions are A36 and A37, priced in pounds sterling in the notes column. `spec_basis` records whether the torque comes from a datasheet, a vendor listing or a mix.
- **Screen.** 26 rows drop out before simulation (stdout, "screened"):
  - 3 are continuous rotation (R7)
  - 1 is over $50 (R8)
  - 2 have no mass or torque data
  - 20 cannot reach a 0.6 hold margin even at their strongest ratio, including every 9 g micro servo
- **Ratios.** Each of the 27 survivors runs through the existing 1:1 sector pair and two alternatives, 81 configurations in all.
  - Servos: 1:1 (as built), then 1.5:1 and 2:1 with an added printed stage (m1.25, 8 mm face, PA6-CF [A]).
  - Gearmotors and worms: 8:1 (the `config.h` DC branch), 5:1 and 12:1.
- **Price assumptions.**
  - A UK-only price is converted at 1.35 USD/GBP [A, rounded up so the R8 check is conservative].
  - An added stage costs $1 [A].
  - A gearmotor also needs a $5 H-bridge and cable [A].

## 2. The model

A single vectorised simulation runs at 1 kHz and mirrors the shipped firmware:

- the CALIBRATE search
- the two-speed close profile (`motion.cpp`)
- contact detection on the filtered force signal
- the force PI loop with its setpoint ramp, rate limit and soft-limit back-off, the 1.0 N hold bias (it regulates setpoint + `F_HOLD_BIAS_N`), the stiffness estimate and gain schedule, and the squeeze cap less its 0.5 N `F_CAP_MARGIN_N` (`force_ctrl.cpp`)
- the force sensing of `fsr_filter.cpp`: the EMA on the divider voltage of the `fsr_model.h` power law, read back as force (no ADC noise)
- the over-force trip

The parts of the model:

- **Plant.**
  - A hobby servo is a first-order position loop with lag τ (40 ms [A]), a deadband and a torque–speed line: no-load speed falls linearly to zero at stall.
  - Torque at the jaw is stall torque × ratio × stage efficiency.
  - A gearmotor is a 1 kHz duty loop with breakaway friction and no back-drive.
- **Load.**
  - The finger is a spring at the pad with tip stiffness k.
  - Hold torque is (2 F r_c + T x_f) / η, where r_c = 65 mm, cloth tension T = 2 N acting at x_f = 11.5 mm, and link efficiency η = 0.85 [A] (`payload_torque.py`).
- **Electrics.**
  - Stall torque follows the vendor's voltage points.
  - The rail sags by I_hold × R_wire.
  - A warm winding loses torque: copper resistance rises 0.393 %/K [S] and the ferrite torque constant falls 0.2 %/K [A].
  - Hold current scales as hold torque over stall torque.
- **Validation.**
  - On the current servo the model reproduces the compiled-firmware simulation of pull request 20 for all four finger stiffnesses: contact time within 0.009 s, time to 4.5 N within 0.009 s, hold force within 0.02 N, peak force equal to 0.01 N (5.22 / 6.20 / 7.21 / 7.41 N) (stdout, "validation vs firmware sim"; `test_sim_reproduces_firmware_sim`).
  - Before the rerun the model lacked the hold bias and the voltage-domain filter and read the stiffest finger's peak low (6.02 against 6.18 N); both are now in it.
  - It also reproduces `payload_torque.py`'s hold margin and LC3 mesh torque for A17, A19 and A20 (`test_hold_margin_and_lc3_match_payload_torque`).
- **What the model leaves out, and the firmware study includes** (pull request 20, not merged, as of 2026-10-11): FSR span error, creep, droop and ADC noise, and the separate hold-current trip (2.0 A in the force loop, 1.8 A elsewhere). This is why the model's force pass-rate is near 1 while the firmware study's R14 is 45.1 %.

**Monte Carlo** (2,000 samples per configuration, seed 20261011). Each sample draws:

- rail voltage: nominal ± 0.15 V
- wire resistance: 0.03–0.10 Ω
- unit-to-unit spread: ±15 % on stall torque and on no-load speed
- a **vendor-claim factor U(0.85, 1.00)** on the stall torque of every row whose torque is a vendor listing with no datasheet. The same DS3225 is listed at 28 kg·cm (A33) and 25 kg·cm (A18) at 6.8 V [S], an 11 % spread for one part. Listings are assumed never to understate [A]. **This is one-sided.** Section 4 adds rows for a unit 20 % and 30 % below its listing.
- winding temperature: 25–80 °C [A; `dyno.md` average-value range]
- link efficiency η: 0.70–0.95
- stage efficiency: 0.85–0.95
- tip stiffness: **1.05–1.24 N/mm per finger [D, FEA E56 to E67]. This is the FEA range, not the R12 window (0.88–1.63 N/mm).** Section 3 adds a Monte Carlo at each R12 limit.
- servo lag τ: 30–60 ms, **the same draw for every candidate**. No row publishes a lag, so a per-candidate lag from listed speed would be invented; the listed speed already limits the slew in the model. What the common draw can hide is bounded by the ideal-actuator case in section 3.
- control-tick phase

Pass flags (names in the JSON):

- **`P_sim_force`:** the hold settles at ≥ 4.9 N [A: 0.1 N allowed for FSR span] with no over-force trip. The sensor is ideal. This is **not** R14.
- **`P_R16`:** the hold torque is ≤ 40 % of that sample's cold stall torque (R16).
- **`P_R16_sim_force`:** both.
- **R15:** peak pad force ≤ the cap.
- **R19:** pad force reaches 4.5 N (90 % of setpoint) within the time limit. See section 3 for the event.

## 3. The two open requirements

Both are open with Douglas, so here they are treated as parameters, and every result is reported at both values.

**R15 force cap: 10 N as written, 8 N proposed.**

| | 10 N, as written | 8 N, proposed |
|---|---|---|
| Firmware soft limit / trip | 7.5 / 8.0 N | 7.0 / 7.5 N [A] |
| Softest finger that still reaches 5.0 N | 0.815 N/mm | **1.048 N/mm** |
| Hold force of an R12-minimum finger (0.88 N/mm) | reaches 5.0 N (5.22 N simulated) | **only 4.14 N** |

- **What changes in the design is the finger stiffness floor.** The jaw angle cap is U_MAX = (cap − 0.5 N margin − 0.5 N) / K (`force_ctrl.h` CTRL_U_MAX_DEG: 4.87° at 10 N, 3.79° at 8 N), so a lower cap needs a stiffer finger. The 8 N cap requires the R12 lower bound to rise to ≥ 1.05 N/mm (requested change R-2). Before the firmware's 0.5 N cap margin these were 0.772 / 0.978 N/mm.
- **The actuator choice does not change.** The eligible servos peak at 7.44–7.46 N in the Monte Carlo (10 N cap). An R12-maximum finger (1.63 N/mm) peaks at 7.41 N in this model and in the compiled-firmware simulation. All are inside both caps; they are near the 7.5 N soft limit because the hold bias regulates about 6 N.
- **Monte Carlo at each R12 limit** (`mc_at_R12_limits`, 2,000 samples, shipped profile). All five options behave alike:

| Finger | Cap | P(simulated force ≥ 4.9 N) | 5th percentile of the held force | 99th percentile peak |
|---|---|---|---|---|
| R12 minimum, 0.88 N/mm | 10 N | 1.00 | 5.22 N | 5.58 N |
| R12 minimum, 0.88 N/mm | 8 N | **0.00** | 4.14 N | 4.50 N |
| R12 maximum, 1.63 N/mm | 10 N | 1.00 | 5.98 N | 7.67 N |
| R12 maximum, 1.63 N/mm | 8 N | 1.00 | 6.00 N | 7.34 N |

  P(R16) at these fingers is the same as in section 0, because the hold-torque rule does not depend on stiffness (DS3230 0.974, DS3218MG with the stage 0.994; these are separate 2,000-sample draws, so they differ from section 0's 0.969 and 0.996 by Monte Carlo noise).

**R19 close time: 0.5 s as written, 0.75 s proposed.**

R19 reads: *"Full close in ≤ 0.5 s. The last 3° before contact at ≤ 20 °/s to limit impact [A]"* (DESIGN-BASIS). It does not say which event ends the close. Every close-time number in this note ends on **t_45: the first millisecond at which the true pad force reaches 4.5 N** (90 % of the 5 N setpoint [A]). First contact (filtered force ≥ 0.5 N, **t_contact**) is quoted separately.

- **What changes is the close profile, not the actuator.**
- With the shipped profile (120 °/s fast leg, then 20 °/s for the last 6° above θ_c0), every servo touches the cloth at 0.50–0.52 s and reaches 4.5 N at 0.60–0.64 s.
- **The fastest profile that still respects R19's impact clause** uses a looser reading of it than R19 states. R19 says ≤ 20 °/s over the last 3°. The shipped profile commands 20 °/s but the jaw is still at about 21.5 °/s 3° before touch (stdout, `v3_worst`), so the search allows ≤ 21.5 °/s [A]; a strict 20 °/s limit would be slower still. That profile uses 240 °/s, a 4° slow zone and 1,000 °/s² deceleration. It reaches 4.5 N in 0.536 s median, and in 0.555 s for the softest finger.
- Dropping the impact clause gets the worst case to 0.426 s.
- **Result: P(R19 at 0.5 s) = 0.00 for all 81 configurations. At 0.75 s it is 1.00 for every eligible configuration with the 10 N cap, and 0.988–0.994 with the 8 N cap** (soft sampled fingers stop at the smaller squeeze cap before 4.5 N).

**The claim, demonstrated** (`ideal_actuator_R19`, committed case and test): an ideal actuator (5000 °/s, 2 ms lag, 20 N·m [A]) on the fw_sim plant, FEA E56 finger (1.05 N/mm), mean over 20 control-tick phases:

| | First contact (t_contact) | 4.5 N (t_45) |
|---|---|---|
| Shipped servo, shipped profile | 0.519 s | 0.628 s |
| **Ideal actuator, shipped profile** | **0.479 s** | **0.570 s** |
| Shipped servo, fast profile | 0.439 s | 0.548 s |
| Ideal actuator, fast profile | 0.418 s | 0.511 s |

- **For "4.5 N reached" on the shipped profile the claim holds against 0.5 s, but the ideal actuator is now earlier, not later.** With the firmware's hold bias and gain schedule the ideal actuator reaches 4.5 N 0.058 s before the servo on E56 (0.570 against 0.628 s), 0.064 s before it on E67 (0.552 against 0.616 s) and 0.027 s before it at R12 maximum (0.570 against 0.597 s); every one is still after 0.5 s. At R12 minimum it stops at 4.41 N and never reaches 4.5 N; that case was not investigated further. (Before the rerun the ideal actuator was later than the servo on soft and mid fingers.)
- **With the fast profile it reaches 4.5 N inside 0.5 s on stiff fingers:** 0.492 s on E67 and 0.491 s at R12 maximum (E56: 0.511 s). Its peak at R12 maximum is 8.16 N, over the 8 N trip level.
- **For "first contact" the claim does not hold:** servo lag moves first contact from 0.519 s to 0.479 s, 0.040 s earlier, and under 0.5 s.
- **What the common lag draw hides** is therefore up to about 0.04 s on first contact and up to about 0.06 s on t_45. A candidate with a shorter lag than the 30–60 ms draw could close that much earlier. It cannot change the verdict on 0.5 s with the shipped profile.

What this means for the choice:

- **R19 at 0.5 s cannot be met by buying a motor.** Every eligible servo is already faster at the jaw than the 120 °/s fast leg (A32: 328 °/s). The time goes into the 20 °/s approach that R19's own impact clause demands, and into the force ramp after contact.
- **Meeting 0.5 s needs a requirement change instead.** Either drop the last-3°-at-20 °/s clause, or count "closed" at contact rather than at 4.5 N: contact comes at 0.42–0.44 s with the fast profile.
- **The fast profile is not free.** It doubles the pre-close speed to 240 °/s. The jam-shock basis in `dyno.md` (2.69 N·m at 120 °/s [D, `dyno.md`]) does not cover that speed, so the fast profile must not ship until the shock is re-run (requested change FW-3).
- **Gearmotors are out.** The gearmotor configurations that reach 4.5 N take 0.95–1.7 s; the rest never reach it within 2 s (stdout table, `tc50`).

## 4. Sensitivity and vendor torque risk (one input at a time, FEA E56 finger, 10 N cap)

The base is the nominal 6.5 V rail, so the DS3230's hold margin starts at 1.45; section 0 quotes 1.44, at the rail's low end.

| Input change | DS3230 hold margin (base 1.45) | DS3218MG + 1.5:1 (base 1.41) | DS3235 (base 1.70) | DS3230 simulated hold current (base 1.23 A, hold about 6 N) |
|---|---|---|---|---|
| Rail −0.5 V | 1.39 | 1.36 | 1.65 | 1.18 A |
| Link efficiency 0.70 | 1.19 | 1.16 | 1.40 | 1.49 A |
| Stall torque −15 % | 1.23 | 1.20 | 1.44 | 1.45 A |
| **Stall torque −20 %** | **1.16** | 1.12 | 1.36 | 1.53 A |
| **Stall torque −30 %** | **1.01** | **0.98** | 1.19 | 1.75 A |
| Winding 120 °C | 1.44 | 1.40 | 1.70 | 2.08 A |
| Softest finger (R12 min, 0.88 N/mm) | 1.45 | 1.41 | 1.70 | 1.04 A |
| Stiffest finger (R12 max, 1.63 N/mm) | 1.45 | 1.41 | 1.70 | 1.19 A |

- **Hold margin** is driven by link efficiency and by the unit's real stall torque.
- **Close time** is driven only by finger stiffness and the close profile (0.628 s in every row but the finger rows: 0.636 and 0.597 s).
- **Vendor torque risk.** The Monte Carlo allows the DS3230 to be up to 15 % under its listing. A unit 20 % under still holds with margin 1.16; **30 % under holds with margin 1.01, the last point that still meets R16.** The stage option crosses 1.00 slightly earlier (0.98 at −30 %). The DS3235 datasheet part keeps 1.19.
- **A hot winding does not break the hold.** At 120 °C the DS3230 holds at 47 % of its warm stall torque; the DS3218MG is at 65 % in the same case.

**Lowest bench stall torque that still meets R16** (`bench_stall_floor`; derived and tested in `extras.bench_stall_floor`):

- Required hold torque: T_req = (2 × 5 N × 65 mm + 2 N × 11.5 mm) / 1000 / 0.85 = **0.792 N·m** [D].
- R16 says that torque must be ≤ 40 % of stall, so the stall at the servo shaft must be ≥ 0.792 / 0.40 = **1.98 N·m** for the 1:1 options (DS3230, DS3235). Their listings give 2.84 N·m (DS3230) and 3.34 N·m (DS3235) at the 6.35 V low end of the rail.
- With a 1.5:1 stage the servo shaft needs only 0.792 / (0.40 × 1.5 × 0.90) = **1.47 N·m**; the DS3218MG listing gives 2.05 N·m.
- If the link efficiency is 0.70 instead of 0.85 (M18 measures it), the floors rise to 2.40 N·m (1:1) and 1.78 N·m (stage).

## 5. What each option changes

### 5.1 Wait: DS3230 MG (A32), $27.00 (or PRO A39, $25.00)

- **Fit: the pocket and the body width are not settled.** Section 0 said "same pocket" on a rounded listing width of 20 mm. The DS3218MG itself has three widths on record: 20 mm (listing), 20.1 mm (the figure `tolerance_stacks.md` uses) and 20.5 mm (the Miuzei drawing, `actuators.csv` row A17). Stack T14 fails a 20.1 mm body in the 20.4 mm pocket (95 % out). The A32 width is **unmeasured to 0.5 mm**. Revision B rows 1 and 3 of that note (locate the servo by its Ø9 output boss; open the pocket to 20.5 mm) make a 20.5 mm body fit, but only for the width, not for the rest. **Measure on the delivered part (requested change C2):** body width, ear span and hole pattern, output boss diameter, and the spline (25T needed).
- **Gear: face width 8 → 10.5 mm (C1).** Safety factors at the rail's high end (so slightly below section 0's nominal-rail values) of the m1.5 z19 PA6-CF printed pair from `gears.py` (`gear_width_table`; torque from this study's stall torque at the high end of the rail, jam torque = 1.276 × stall as in `dyno.md`; 1.15 target covers the +15 % unit spread [A]):

| Option | LC3 stall torque | Jam torque | SF stall / jam at 8 mm | at 10 mm | at 12 mm | Width for 1.15 on both |
|---|---|---|---|---|---|---|
| DS3230 (A32) | 2.91 N·m | 3.71 N·m | 1.24 / **1.01** | 1.38 / **1.145** | 1.45 / 1.23 | **10.5 mm** |
| DS3235 SG (A34) | 3.02 | 3.85 | 1.21 / **0.98** | 1.34 / 1.11 | 1.41 / 1.19 | 11.0 mm |
| DS3235 (A19) | 3.40 | 4.34 | 1.09 / **0.89** | 1.23 / **1.01** | 1.30 / 1.10 | 14.5 mm |
| DS3218MG + 1.5:1 (A17) | 2.82 | 3.60 | 1.28 / 1.04 | 1.41 / 1.17 | 1.48 / 1.25 | 10.0 mm |

  - **The 1.01–1.02 at 8 mm is an extrapolation.** The jam torque of 3.71 N·m (and 4.34 for A19) lies beyond the 3.306 N·m upper point of the `gears.md` fit; the stall torque 2.91 N·m is inside it. It is scaled from the DS3218MG shock result, not simulated for this part. `gears.shock()` with the part's own stall torque returns a peak equal to stall (no amplification), so the 1.276 jam factor from `dyno.md` is the conservative basis; both are in the JSON.
  - The 8 mm figure has no allowance for unit spread. At 10.5 mm it reaches 1.15 for both loads.
- **Firmware** (`config.h`):
  - `SERVO_STALL_NM` 2.068 → 2.877 N·m (`stall_drive_Nm_at_V_rail`)
  - `SERVO_SPEED_DPS` 419 → 328
  - `SERVO_STALL_A` 2.2 → 3.8 A at 6.8 V [S]
  - The pulse range stays at 1387–1722 µs (1:1; the −10.2° floor backstop of firmware round 2, was 1418 at −7.4°), and the 120 °/s fast leg is unchanged.
  - **Current trips.** The firmware study (pull request 20, not merged) uses a **separate** hold-current trip of **2.0 A** while the force loop runs (it was 2.4 A) and 1.8 A elsewhere. The DS3230's simulated hold current, with the hold bias now in the model (about 6 N), is **1.62 A median and 2.12 A at the 95th percentile with the 10 N cap** (1.42 / 1.87 A with the 8 N cap, where some soft fingers stop at the squeeze cap below 6 N). **The 95th percentile at the 10 N cap is above 2.0 A**, so on a unit near the top of the spread the hold would trip. (The pre-rerun note scaled a 5 N simulation to 1.64 / 2.15 A; the simulation now agrees.) Set the hold trip from the measured hold and stall currents (M6, M7), as that study does (0.9 × measured stall, `STALL_CURRENT_HOLD_A`) (requested change FW-4).
- **Electrical:**
  - Rail unchanged at 6.5 ± 0.15 V.
  - Stall sizing current 3.99 A for a unit at the listed figures. That fills the 4 A buck that `dyno.md` recommends [D, `dyno.md`] with no headroom, and a unit above nominal exceeds it. **Supply and wiring for ≥ 5 A [A] (requested change E1).**
  - The pad force at stall (18.9 N) is above the finger's fold force (8.41 N [D, `finger.md`]). The force cap therefore depends entirely on the firmware trip and the angle floor, as it already does with the DS3218MG (13.5 N).
- **Hold current: which number to use.** The nominal 1.00 A is a unit exactly at the listing, at 25 °C, with η = 0.85. A real unit draws more, because it has less torque to spare:

| Step (`hold_current_reconciliation_A32`) | Median hold current |
|---|---|
| Nominal unit, 6.5 V, 25 °C, η 0.85 | 1.00 A |
| + sampled stall torque (spread, vendor-claim factor, 25–80 °C winding, rail and wire drop) | 1.27 A |
| + sampled link efficiency 0.70–0.95 | 1.32 A |
| Monte Carlo simulation (settled force about 6 N with the hold bias, tension included), 8 N cap / 10 N cap | **1.42 A** (95th percentile 1.87 A) / **1.62 A** (2.12 A) |

  The first three steps are the 5 N hold; the last is the firmware's hold, about 6 N. **A designer should use 1.62 A (median) and 2.12 A (95th percentile)** with the 10 N cap as built (1.42 / 1.87 A at 8 N) for the supply, the trip and the heat. The 1.00 A is a bench check for a unit at its listing at 5 N.
- **Heat against R26** (`thermal_scaling_estimate`). This is **a scaling estimate, not a thermal model**: `thermal.md`'s cycle-average heat for the present servo is rescaled by the ratio of hold heat (I²R with R ≈ V / I_stall for continuous conduction, I × V for the discontinuous bound, using the DS3230's stall current and hold fraction), then multiplied by the K/W that `thermal.json` implies. It reproduces `thermal.md`'s own present-servo numbers to 0.5 K (no back-off), and its back-off rows to 1.5 K (continuous) and 4.5 K (discontinuous, where it reads low). Steady state, 5 N hold, °C. Case limit 60 °C (R26). Present = DS3218MG as built; stage = DS3218MG + 1.5:1.

| Regime | F1 back-off | Ambient | Present (A17) | **DS3230 (A32)** | DS3235 (A19) | Stage (A17@1.5) |
|---|---|---|---|---|---|---|
| Fit A, continuous | none | 25 / 40 | 71.1 / 86.2 | **52.6 / 67.7** | 61.8 / 76.9 | 52.1 / 67.1 |
| Fit A, continuous | F1 | 25 / 40 | 36.4 / 51.4 | **33.1 / 48.1** | 34.7 / 49.8 | 33.0 / 48.0 |
| Fit B, continuous | none | 25 / 40 | 50.7 / 65.8 | **48.1 / 63.2** | 37.2 / 52.3 | 40.0 / 55.1 |
| Fit B, continuous | F1 | 25 / 40 | 31.2 / 46.3 | **30.8 / 45.8** | 28.8 / 43.8 | 29.3 / 44.3 |
| Fit A, discontinuous | none | 25 / 40 | 104.2 / 116.6 | **87.8 / 100.7** | 124.6 / 136.3 | 84.7 / 97.7 |
| Fit A, discontinuous | F1 | 25 / 40 | 60.8 / 74.6 | **53.9 / 67.9** | 69.4 / 82.9 | 52.6 / 66.7 |
| Fit B, discontinuous | none | 25 / 40 | 74.4 / 87.7 | **85.7 / 98.6** | 60.4 / 74.2 | 62.1 / 75.9 |
| Fit B, discontinuous | F1 | 25 / 40 | 47.2 / 61.4 | **52.0 / 66.0** | 41.3 / 55.7 | 42.0 / 56.4 |

  - **Better or worse than the present servo against R26?** For a nominal unit, cooler in three of four regimes (0.4 to 18.5 K); **hotter by 11.3 K (no back-off) or 4.8 K (with F1) at 25 °C in the one regime where the present servo's listed 2.1 A stall is right and the drive conducts discontinuously.** The quoted 6.53 W against 5.27 W (+24 %) is that regime's number.
  - **Without F1 the DS3230 fails R26 at 40 °C in every regime** (63.2 °C is the best) and at 25 °C in both discontinuous regimes, as the present servo does.
  - **With F1 it passes at 40 °C only with continuous conduction.** With discontinuous conduction it exceeds 60 °C at 40 °C ambient in both fits (67.9 and 66.0 °C). F1 itself is a firmware change nobody has benched (`thermal.md`, F1), and the firmware study measures R14 falling from 45.1 % to 14 % with it on (pull request 20, its O16): **the F1 route to R26 conflicts with R14.** R26 needs another remedy (strap, fin, duty limit) or a measured conduction regime.
  - **At the Monte Carlo median hold current** (`estimates_at_median_hold_current`; each unit's median current over its nominal, relative to the present servo: DS3230 ×1.085) the DS3230 case is, at 25 °C with no back-off: Fit A continuous 56.8 °C (present 71.1), Fit A discontinuous 92.8 (104.2), **Fit B continuous 51.9 (50.7), Fit B discontinuous 90.7 (74.4)**. So it is cooler if the present servo's true stall current is the high one (Fit A) and warmer if it is the listed one (Fit B). With F1: 33.8 / 56.0 / 31.4 / 54.1 °C against 36.4 / 60.8 / 31.2 / 47.2. Against the present servo's nominal case, the median-current DS3230 is `estimates_median_current_vs_present_at_nominal`: 69.4 °C in Fit B continuous, over 60 °C.
  - The cradle-seat temperature is 0.4–5.4 K below the case in all rows (see the JSON).
- **Thermal lane request T1** (below): rerun `thermal.py` for the chosen servo.

### 5.2 Order today: DS3218MG with a 1.5:1 stage (A17@1.5:1), $13.99

This is the present servo with a new gear stage between servo and sector pair. It is the only option in stock and with datasheet torque. The numbers are the same model as for every other option.

- **R16, R15, R19 (section 0):** hold margin 1.40 (5th percentile 1.09), P(R16) = 1.00 / 1.00, peak 7.44 N, P(R19 at 0.75 s) 1.00 with the 10 N cap and 0.988 with the 8 N cap (0.631 s median). P(R16 and simulated force) at the 8 N cap is 0.904, just over the 0.9 gate. At a stall torque 30 % under the listing the margin is 0.98.
- **What must be designed and bought:**
  - Two printed PA6-CF gears, module 1.25, z16 and z24 (ratio exactly 1.5), 8 mm face, centre distance 25.0 mm [D]
  - One 4 mm shaft, two 4 × 8 × 3 mm bearings, bracket screws [A: $1 of the $13.99]
  - A **new bay**: there are only 8.5 mm above the servo ears, and the stage moves the output shaft 25 mm sideways from the servo's. The knuckle-A horn mount, the pulse range (a 1.5× wider pulse swing) and the firmware ratio constant all change.
  - Gear width 10 mm for the sector pair (table in 5.1).
- **Mass and R10.** Stage 8.2 g (8.9 g with z16/z24 teeth [D]) takes the wrist to 66.2 g (the model's 8.17 g is used in the table; the z16/z24 teeth are 8.9 g and a ±25 % stage mass is up to 10.2 g). DESIGN-BASIS R10 allows 43,720 g·mm and the estimate is 40,507 g·mm (93 %). The stage adds 2,857 g·mm [A: at the gripper's 349.8 mm lever], **99.2 % of the limit** (99.8 % with the 8.9 g z16/z24 stage; **100.8 %** with the stage mass 25 % high, so R10 is marginal for this row too), using 89 % of the remaining headroom of 3,213 g·mm. The DS3230 is 2 g heavier than the DS3218MG, about 700 g·mm.
- **Arm gate: marginal.** SO-101 hold use is 1.005 on an **estimated** 8.17 g stage mass (± 25 % [A]) plus the 58 g servo (± 2 g, the vendors' disagreement), an uncertainty of ± 0.015 including the fit residual. Gate pass = use + uncertainty ≤ 1.00; fail = use − uncertainty > 1.00. This straddles it, so the gate is "marginal", not fail. The DS3230 passes at 0.984 ± 0.013 on an **unverified 60 g listing mass**; the fit crosses 1.00 at 64.6 g, so a 4.6 g error would fail it.
- **Backlash.** The stage adds 0.25 mm of tooth backlash [S, `tolerance_stacks.md` T07] at the output gear's 15 mm pitch radius: **0.95° at the jaw, 1.08 mm at the pad**, on top of the sector pair's 1.0° (1.14 mm). Total about 2.0° (2.2 mm). It enters the force loop as dead-zone before the pad moves.
- **Cost against the others:** $13.99 [S + A] against $24.49–27.00, but the design and print time is not costed.

### 5.3 Fallback: DS3235 datasheet part (A19), $24.49

- Hold margin 1.69 (5th percentile 1.33); P(R16) = 1.00 / 1.00; the strongest option.
- Gear width 14.5 mm for a 1.15 jam factor (table in 5.1); 10 mm gives 1.01.
- 7.1 V rail, sized for 6.98 A [D]. Hold current 0.52 A nominal. The heat table shows it hotter than the DS3230 in Fit A, cooler in Fit B.
- Sold out at the cited vendor; needs C1.

**The aifitlab DS3235 SG (A34, $30.00)** is a vendor claim with a 7.4 V rail (sized for 5.04 A), hold margin 1.47 (5th percentile 1.05), P(R16 and simulated force) 0.98 / 0.94. It scores 0.638 against the DS3230's 0.646: $3 more, rail change.

**DS3225 MG (A33, $20.00)** nearly qualifies: hold margin 1.34, 0.96 at the 5th percentile; P(R16 and simulated force) 0.90 / 0.86, under the 0.9 gate. At the other vendor's figures (A18: 25 kg·cm, 67 g) it falls to 0.67 / 0.63 and the SO-101 hold use is 1.008.

**Not chosen:** goBILDA 25-2 (A28), FEETECH FT5330M (A37, 67 g, hold use 1.008), any 2:1 stage (the added mass breaks the arm budget or the stage gear), and the Hitec HS-645MG (A35, 1.5:1), which cannot hold.

**DS3230 PRO (A39).** Added after review: the product page (read 2026-10-11 through a page summariser, so not a raw copy) lists exactly the MG's figures at $25.00 and says the 180° version is backordered. It is therefore evaluated as a second vendor-claim row; it scores 0.652 (the MG 0.646). What is missing: the datasheet, spline, gear material, ear pattern, and what separates PRO from MG. If its stock turns out to be real, it replaces the "wait" row and becomes the "order today" part.

## 6. Weighted matrix

Every criterion is scored 0–1 by a written rule (`actuation_trade.json` → `settings.utility_rules`).

| Criterion | Weight [A] | Utility rule (summary) |
|---|---|---|
| Requirements margin | 0.30 | Mean of P(R16 and simulated force), P(R15) and P(R19) at the requirement values |
| Mass at the wrist | 0.15 | (1.00 − SO-101 hold use) / 0.20 |
| Envelope fit | 0.15 | Drop-in 1.0 … new bay 0.1 |
| Cost | 0.10 | ($50 − cost) / $40 |
| Availability | 0.10 | In stock 1.0 … sold out 0.1 |
| Control interface | 0.10 | PWM servo at 1:1 1.0, with a stage 0.8, gearmotor 0.3 |
| Noise and life | 0.10 | Hold fraction of stall and gear safety factor; −0.15 per printed stage |

**Gates applied before ranking:**

- SO-101 hold use not clearly above 1.00 (use − uncertainty ≤ 1.00). **A gate result inside the model's own error is "marginal", not pass or fail.**
- gear safety factor at stall ≥ 1.0
- P(R16 and simulated force) ≥ 0.9 at both requirement values
- P(R15 at 8 N) ≥ 0.9
- availability ≥ 0.3

**How the eligible set changes with the arm gate** (`eligible_sets`):

| Rule | Eligible |
|---|---|
| Clear pass only | DS3230 MG (A32), DS3230 PRO (A39), DS3235 SG (A34) |
| Marginal also eligible | the three above plus A17@1.5:1, A17@2:1, A28@1.5:1, A33@1.5:1, A37@1:1 |

The score winner is the DS3230 (A39 first, A32 second) under both rules.

**Tie rule:** within 0.02 of the top score, prefer datasheet torque evidence over a vendor claim, then availability.
For the ranking itself, scores are rounded decimal half-even to three places before sorting and writing; equal rounded scores sort by candidate key in ascending lexical order.

**Stability of the result:**

- **The winner does not change with the weights.** Halving or raising by half any single weight leaves the DS3230 on top. Over 4,000 random weight draws the tie rule recommends the DS3230 in 81.4 % and the DS3218MG with the 1.5:1 stage in 18.6 %.
- **The winner does change with the gate.** At a P(R16 and simulated force) gate of 0.8 the DS3225 (A33) qualifies and wins. At 0.95 the FEETECH FT5330M (A37, marginal arm gate) wins: the DS3230's 8 N-cap value is 0.92–0.93 since the model carries the squeeze-cap margin (it was 0.95–0.96, and the PRO won).
- **With no gates, the DS3218MG at 1:1 scores highest**, because it is cheap, in stock and a drop-in. It fails only on the hold-rule probability.

## 7. Weakest assumption, and the test that removes it

**The weakest assumption is the DS3230's stall torque, 26 / 30 kg·cm at 5.0 / 6.8 V [S, vendor listing, no datasheet].**

- The Monte Carlo already allows for the claim being up to 15 % high, and a unit 20 % under still holds with margin 1.16 (section 4).
- **The link efficiency of 0.85 [A] matters as much.** Section 4 shows efficiency 0.70 costing as much hold margin (1.45 → 1.19) as a unit 15 % under its claim (1.45 → 1.23). The stall test below does not measure it; bench test M18 does, and it should be run on the same day.
- **Stock is the practical weak point:** see "Ordering status" at the top.
- Next weakest is its 60 g mass [S, listing]. The fit `util = 0.7737 + 0.00350 × mass_g` (stdout) crosses 1.00 at 64.6 g (unrounded fit).

**Bench test** (extends DESIGN-BASIS M6 and M7). Do it on the first unit before buying spares:

1. **Read the label and weigh the servo.** Pass: DS3230, ≤ 64.6 g.
2. **Stall torque.** Clamp the servo, fit a 50 mm lever to the horn pressing on a kitchen scale, and command full close at 6.35 V and at 6.65 V on a bench supply. Record stall force and supply current.
   - **Pass: stall ≥ 1.98 N·m at 6.35 V** (`bench_stall_floor`, derived in section 4). The listing gives 2.84 N·m at 6.35 V (`stall_drive_Nm_at_V_lo`).
   - The floor is the bare pass line: a unit exactly on it has hold margin 1.00 and fails R16 once the winding warms. **Treat 1.98 to 2.28 N·m (1.15 × the floor, the study's unit spread) as marginal and accept above 2.28 N·m.** If M18 finds a link efficiency of 0.70, the floor rises to 2.40 N·m.
3. **Heat.** Run the section 7 duty cycle for 30 min at 5 N. Pass: case ≤ 60 °C (R26), and the hold-current trip does not fire in the hold (FW-4). Log the rail current in the hold (`thermal.md` F4) to tell its Fit A from Fit B.

**If step 2 fails, switch to the DS3235 datasheet part (A19)** with C1 (14.5 mm) and the 7.1 V rail.

## 8. Requested changes (outside this lane's files)

IDs F1–F4 elsewhere in this note are `thermal.md`'s firmware asks (F1 is the friction back-off hold); this lane's firmware changes are numbered FW-1 to FW-4.


| ID | File | Change | Number behind it |
|---|---|---|---|
| C1 | `cad/gripper/params.json` → `gear.face_width` | 8 → **10.5 mm** in rev B for the DS3230 (11.0 mm for the DS3235 SG, 10.0 mm for the stage option, 14.5 mm for the A19 fallback). Re-run `gears.py` at the new width and at each part's jam torque | Jam-shock gear safety factor 1.01 at 8 mm (extrapolated, torque beyond the 3.306 N·m fit point), 1.15 at 10.5 mm |
| C2 | `cad/gripper/params.json` → `servo`; see `tolerance_stacks.md` T14 and revision B rows 1 and 3 | `model` DS3230 MG. Measure on the delivered part: body width, ear span and hole pattern, output boss diameter, spline (25T). Do not assume "same pocket" | A32 width unmeasured to 0.5 mm (listing 20 mm rounded; the DS3218MG row gives 20.5 mm); T14 fails 20.1 mm in 20.4 mm |
| T1 | Thermal lane: `analysis/gripper/thermal/` | Rerun for the chosen servo. Inputs: stall torque 2.877 N·m at 6.5 V, listed stall current 3.8 A at 6.8 V (sizing 3.99 A at 6.5 V), no-load speed 328 °/s, mass 60 g, body 40 × 20 × 40.5 mm, hold torque 0.792 N·m at 5 N and 0.944 N·m at the 6 N regulated hold (both with cloth tension; `thermal.md` used 0.7647, without), rail 6.5 V; simulated hold current 1.62 A median, 2.12 A at the 95th percentile (10 N cap) | Scaling estimate: DS3230 case 85.7 °C against 74.4 °C (Fit B, discontinuous, 25 °C, no F1); `thermal.md` verdict "not safe as drawn" |
| FW-1 | `firmware/gripper/config.h` | `SERVO_STALL_NM` 2.877, `SERVO_SPEED_DPS` 328, `SERVO_STALL_A` 3.8 (at 6.8 V) | Listing [S]; model at 6.5 V |
| FW-2 | `firmware/gripper/config.h` | If R15 becomes 8 N: `F_SOFT_LIMIT_N` 7.0, `F_TRIP_N` 7.5 | Keeps the 6.0–6.6 N hold band (setpoint + 1 N bias, + 0.6 N integrator deadband) below the soft limit [A] |
| FW-3 | `firmware/gripper/config.h` + `analysis/gripper/dyno.py` | Do not raise `JAW_SPEED_FAST_DPS` above 120 °/s until the jam shock is re-run at the new speed | The as-written R19 profile needs 240 °/s; the shock basis is 120 °/s |
| FW-4 | `firmware/gripper/config.h` hold-current trip (pull request 20, not merged: 2.0 A in the force loop, 1.8 A elsewhere) | Do not apply the 1.8 A trip to the hold. Set the hold trip from the measured hold and stall rail currents (M6, M7): above the hold's 95th percentile and below stall | DS3230 simulated hold current with the hold bias 1.62 A median, 2.12 A at the 95th percentile (10 N cap; above the 2.0 A trip), 1.42 / 1.87 A with the 8 N cap; stall 3.6–4.0 A |
| E1 | Electrical design, DESIGN-BASIS R27 | Rail stays at 6.5 ± 0.15 V; supply and wiring for ≥ 5 A [A] | Sizing current 3.99 A for a nominal unit, which leaves no headroom in a 4 A supply. A19 would need 6.98 A at 7.1 V |
| R-1 | DESIGN-BASIS R19 | Choose 0.75 s, define "closed" as contact, or drop the last-3°-at-20 °/s clause. With the clause and the shipped profile, 0.5 s to 4.5 N is unreachable even for an ideal actuator (0.570 s at 1.05 N/mm); only the fast profile on a stiff finger reaches it (0.491–0.492 s) | P(R19 at 0.5 s) = 0.00 for all 81 configurations |
| R-2 | DESIGN-BASIS R12 | If R15 becomes 8 N, raise the lower tip stiffness bound from 0.88 to ≥ 1.05 N/mm | Stiffness floor at 8 N is 1.048 N/mm (squeeze cap less the firmware's 0.5 N margin); an R12-minimum finger holds 4.14 N |
| R-3 | DESIGN-BASIS R8, BOM | DS3230 MG at $27.00 (or PRO at $25.00 if its stock is confirmed) | Under the $50 cap [S] |
| R-4 | DESIGN-BASIS R14 | Record that R14 (true force ≥ 5 N) is met in 45.1 % of grips with the present servo and shipped firmware, and that the cause is not the actuator | Firmware study, pull request 20, not merged, as of 2026-10-11 |

## 9. Limits of this study

- **Stock:** both eligible vendor-claim candidates (DS3230 MG and DS3235 SG) are backordered at the one vendor cited, aifitlab, the PRO's stock is unresolved, and the fallback is sold out at its cited vendor [S]. No second vendor was checked for the DS3230. Recheck on the day of ordering.
- **Fit:** "likely drop-in" means the body is expected to fit the pocket. It is not a check of the ear holes, the boss or the spline (C2).
- **R14:** this study does not model the causes of the 45.1 % result (FSR span error, creep, droop). The hold bias, gain schedule and cap margin of pull request 20 are in the model since the 2026-10-11 rerun; the separate hold-current trip is not.
- **Thermal:** section 5.1 is a scaling estimate. It is linear in power, assumes the present servo's `thermal.md` fits (Fit A or B) apply to each candidate's stall current, and reads about 4.5 K low where conduction is discontinuous. It is not a replacement for T1.
- **Assumptions bench tests replace:** the 40 % hold rule, the 0.85 link efficiency and the 40 ms servo lag are assumptions, replaced by bench tests M6, M18 and M8.
- **Servo lag** is drawn identically for all candidates (section 2).
- **Jam shock:** scaled from `dyno.md`'s DS3218MG result by the ratio of stall torques, not re-simulated for each candidate; section 5.1 shows it is beyond the `gears.md` fit.
- **Arm budget:** the SO-101 budget uses a linear fit of `payload_torque.json`'s hold use against actuator mass (maximum residual 0.0006). It assumes the actuator sits where the DS3218MG sits. R10 uses the gripper's lever for any added mass [A].
- **8 N cap failures:** the 4–5 % of samples (9 % for the stage option) that miss the simulated force pass with the 8 N cap but pass with 10 N settle under 4.9 N. They are the softer sampled fingers stopping at the 8 N squeeze cap: the E56 finger (1.05 N/mm) holds 4.92 N at that cap in the nominal run, so fingers a little softer fall below 4.9 N.
