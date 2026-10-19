# Tolerancing and stack-up reference: cloth-feed gripper

Research lane: GD&T and tolerance stack-up. Scope: the ME102B single-servo, 1:1 geared, Fin Ray TPU finger gripper in `cad/gripper/` (m = 1, z = 24, a = 24 mm, 20° pressure angle, Ø3 idler pin, FDM PLA housing). Compiled 2026-09-22.

**Number tags.** `[S#]` = sourced (see Sources, bottom). `[D]` = derived here from sourced values or `params.json`. `[A]` = assumed; measure or test before relying on it.

ASME Y14.5 and Machinery's Handbook are paywalled; nothing here is copied from them. The ISO 286 numbers come from a vendor-hosted reprint of ANSI B4.2 tables `[S5]`, checked against RoyMech `[S6]`.

---

## 1. Stack-up methods

Linear stack model `[S1 §3–4]`: assembly quantity `A = a0 + Σ aᵢ·Xᵢ`. Here `aᵢ` is the sensitivity: +1 or −1 for a simple loop, and a lever ratio for angular links.

| Method | Formula | Assumes | Use here when |
|---|---|---|---|
| Worst case (arithmetic) | `T_WC = Σ |aᵢ|·Tᵢ` `[S1 §3]`, `[S2]` | Every part can be at its limit at the same time. Guarantees 100 % assembly. | There are few contributors, or a failure means a jam or a broken part (gear binding, servo not fitting). |
| RSS (statistical) | `T_RSS = √(Σ (aᵢ·Tᵢ)²)`, with `Tᵢ = 3σᵢ`, giving ±3σ, which covers 99.73 % `[S1 eq. 2]`, `[S2]` | Independent, normal, centred distributions | There are 4 or more contributors and the process is stable. With n equal tolerances it gives `T·√n` against `n·T` for worst case `[S1]`. |
| RSS, inflated for distribution | `T = c·T_RSS`. `c` = 1 for a normal distribution, 1.732 for uniform, 1.225 for triangular `[S1 p. 17]` | Distribution shape is known but not normal | Clearance float (a part rattling in a pocket) is uniform, not normal, so use c = 1.732 on it. |
| Bender / modified RSS | `T = 1.5·T_RSS` `[S1 p. 18]` | Accounts for mean shift, e.g. a printer that runs oversize every time | Default for FDM. A printer's bias is a mean shift, not random scatter. |
| Monte Carlo | Sample each `Xᵢ` from its distribution N times, compute `A`, then read percentiles and yield `[S2]`, `[S3]` | Any distribution. Handles nonlinear links such as angles and involute geometry. | Nonlinear stacks: backlash to fingertip play, and the jaw angle. The standard error on a yield fraction p is `√(p(1−p)/N)` `[D]`. |

Capability: `Cpk = min(USL − μ, μ − LSL)/(3σ)`. The usual minimum target is 1.33 `[S4]`.

Monte Carlo results in §7 used N = 200,000 samples (numpy, seed 1) `[D]`. Clearance floats were sampled as uniform and print or vendor scatter as normal with T = 3σ.

---

## 2. GD&T controls that matter here

| Control | Datum needed? | Meaning (`[S12]`) | Where it applies on this gripper |
|---|---|---|---|
| Datum reference frame | n/a | Primary datum: 3 contact points, fixes 3 DOF. Secondary: 2 points, 2 DOF. Tertiary: 1 point, 1 DOF (3-2-1 rule). | A = mid-plate mating face. B = servo cradle pocket, a width feature whose centre plane locates the servo shaft in X. C = cradle end wall (Y). |
| Flatness | No | Surface lies between two parallel planes | Datum A face. FDM first layers warp, and elephant's foot needs about 0.2 mm first-layer compensation on a 0.4 mm nozzle `[S27]`. Proposed callout: flatness 0.2 `[A]`. |
| Perpendicularity | Yes | Axis or surface within a zone at 90° to the datum | Idler-pin bore B and the standoff bores ⊥ A. A tilted pin varies the center distance across the 6 mm face width (§5). Proposed: ⊥ Ø0.1 to A `[A]`. |
| Position | Yes | `Ø = 2·√(Δx² + Δy²)` from true position. The MMC bonus is (actual hole size − MMC size) `[S12]`. | Hole B relative to A\|B\|C at basic 24.000 (this sets the center distance). Also the wrist bolt pattern (4× on Ø14.0) relative to A\|D, where D = the pilot recess on the Ø19.2 wrist-roll horn (`so101.md`). |
| Profile of a surface or line | Usually | 3D zone around the true shape `[S12]` | Finger pad faces (sets closed gap and parallelism) and the involute flanks relative to the bore. Proposed: pad profile 0.4 \|A\|B\|, tooth profile 0.1 relative to bore `[A]`. |

**Fastener formulas** `[S11]`:
- Floating fastener: both parts have clearance holes and a nut is used. `T = H − F` per part.
- Fixed fastener: one part is threaded or pressed. `H = F + T₁ + T₂`, so `T = (H − F)/2` each when the two are split equally.

H = hole MMC (smallest actual hole), F = fastener MMC (largest actual screw). M3 6g major diameter max is 2.980 mm `[S9]`.

---

## 3. ISO 286 fits (basic size 3 mm, range "over 0 to 3")

A 3 mm size falls in the "up to and including 3" band. For that band IT6 = 6 µm, IT7 = 10 µm, IT8 = 14 µm, IT11 = 60 µm, IT12 = 0.10 mm, IT13 = 0.14 mm, IT14 = 0.25 mm `[S5 Table 6-30]`.

### 3a. Deviations and limits (all `[S5]` Tables 6-10, 6-20…6-26; limits `[D]`)

| Zone | Upper / lower dev. (µm) | Limits for Ø3 (mm) | Zone | Upper / lower dev. (µm) | Limits for Ø3 (mm) |
|---|---|---|---|---|---|
| **H7** hole | +10 / 0 | 3.000 – 3.010 | **g6** | −2 / −8 | 2.992 – 2.998 |
| **H8** hole | +14 / 0 | 3.000 – 3.014 | **h6** | 0 / −6 | 2.994 – 3.000 |
| **H11** hole | +60 / 0 | 3.000 – 3.060 | **h7** | 0 / −10 | 2.990 – 3.000 |
| **G7** hole | +12 / +2 | 3.002 – 3.012 | **k6** | +6 / 0 | 3.000 – 3.006 |
| **N7** hole | −4 / −14 | 2.986 – 2.996 | **m6** | +8 / +2 | 3.002 – 3.008 |
| **P7** hole | −6 / −16 | 2.984 – 2.994 | **n6** | +10 / +4 | 3.004 – 3.010 |
| **f7** | −6 / −16 | 2.984 – 2.994 | **p6** | +12 / +6 | 3.006 – 3.012 |
| | | | **s6** | +20 / +14 | 3.014 – 3.020 |

For comparison, the 3–6 mm band: H7 is +12/0 and g6 is −4/−12 `[S5]`, `[S6]`.

### 3b. Hole-basis fits at Ø3 (clearance +, interference −) `[D]` from 3a; descriptions `[S5 Table 6-1]`, `[S7]`

| Fit | Type | Max clearance | Min clearance / max interference | Use on gripper |
|---|---|---|---|---|
| H8/f7 | Close running | +0.030 | +0.006 | Metal bushing on pin, free running |
| H7/g6 | Sliding | +0.018 | +0.002 | Precision pivot (bushing or bearing bore) |
| H7/h6 | Locational clearance | +0.016 | 0.000 | Locating dowel, removable |
| H7/k6 | Transition | +0.010 | −0.006 | Mallet fit |
| H7/m6 | Transition | +0.008 | −0.008 | Standard dowel (m6) in a reamed metal hole |
| H7/n6 | Transition | +0.006 | −0.010 | Light press |
| H7/p6 | Transition *at ≤3 mm* | +0.004 | −0.012 | Listed as "interference" for general sizes, but a transition fit from 0 to 3 mm `[S5 note 1]` |
| H7/s6 | Interference | −0.004 | −0.020 | Drive fit (metal only) |

**What this means for printed parts.** Calibrated FDM holds roughly ±0.1–0.2 mm (§4). That is IT12–IT14 at this size, 10 to 25 times the IT7 band `[D]`. ISO fits therefore apply only to metal-on-metal interfaces, or to printed holes that are drilled or reamed after printing. Printed-to-metal fits are set by the clearance or interference values in §4c instead.

### 3c. Standard parts

| Part | Size spec | Source |
|---|---|---|
| Hardened dowel ISO 8734 / DIN 6325 | m6, so a Ø3 pin is 3.002–3.008 | `[S10]` (class), limits `[D]` from 3a |
| Unhardened dowel ISO 2338 | m6 or h8 | `[S10b]` |
| M3×0.5 6g screw | Major Ø 2.874–2.980; pitch Ø 2.580–2.655 | `[S9]`, `[S9b]` |
| M2×0.4 6g screw | Major Ø 1.886–1.981; pitch Ø 1.654–1.721 | `[S9b]` |

### 3d. Clearance holes ISO 273 (fine H12 / medium H13 / coarse H14) `[S8]`

| Thread | Fine | Medium | Coarse | Suggested CAD Ø for FDM Z-axis hole (medium + print undersize ~0.25) |
|---|---|---|---|---|
| M2 | 2.2 | 2.4 | 2.6 | 2.6–2.7 `[D]` |
| M2.5 | 2.7 | 2.9 | 3.1 | 3.1–3.2 `[D]` |
| M3 | 3.2 | 3.4 | 3.6 | 3.6–3.7 `[D]` |

---

## 4. Printing tolerances, holes, press fits, inserts

### 4a. Process tolerance (general, as-printed)

| Process | Tolerance | Source |
|---|---|---|
| Prototyping (desktop) FDM | ±0.5 %, lower limit ±0.5 mm | `[S13]` |
| Industrial FDM | ±0.3 %, lower limit ±0.3 mm | `[S13]` |
| Prototyping SLA/DLP | ±0.3 %, lower limit ±0.3 mm | `[S13]` |
| Industrial SLA | ±0.2 %, lower limit ±0.13 mm | `[S13]` |
| Protolabs SLA | X/Y ±0.0508 mm for the first 25.4 mm + 0.1 %; Z ±0.127 mm + 0.1 % | `[S15]` |
| Formlabs SLA | ±0.15 % (1–30 mm features), lower limit ±0.02 mm | `[S16]` |
| SLS / MJF | ±0.3 %, lower limit ±0.3 mm (Hubs); Protolabs SLS ±0.254 mm + 0.1 % | `[S13]`, `[S15]` |
| Calibrated desktop FDM, short features (<30 mm), after a calibration print | ±0.1–0.15 | `[A]`, and the basis of the §7 numbers. The SO-101 build guide gates printer accuracy with a servo-fit gauge `[S25]`. |

Vendor lower limits (±0.5 mm FDM) are service-bureau guarantees. A tuned team printer does better, but only a measured test coupon proves it `[A]`.

### 4b. Holes: Z-axis vs XY-axis

- **Z-axis holes** (axis ⊥ bed, e.g. every pivot bore in a flat-printed plate or knuckle) are round but undersized. CNC Kitchen measured about 0.25 mm undersize on every hole `[S18]`. Causes: STL faceting (sides sit inside the circle by a factor cos(π/n)), arc shrinkage and corner cutting `[S17]`.
  - Polyhole correction (nophead): `n = max(round(2d), 3)` sides and `r = (d/2)/cos(180°/n)` `[S17]`.
  - For Ø3 that gives n = 6 and r = 1.732, a CAD circumscribed Ø3.46 `[D]`.
  - Practical rule: add 0.2–0.3 mm in CAD for small holes `[S18]`.
- **XY-axis holes** (axis ∥ bed) sag at the top where the perimeter bridges, and come out oval. Bridges under 5 mm are acceptable `[S14]`. A teardrop profile, or drilling afterwards, fixes it.
  - Measured roundness on industrial-FDM ABS cylinders was 0.10–0.22 mm depending on orientation and measuring method. 45° was best in that study `[S21]`.
- **Critical holes:** print undersize, then drill to size `[S14]`. Every pivot and pin hole on this gripper should be Z-axis `[D]`, which the current geometry allows: the gear plane is XY and parts extrude along Z.

### 4c. Printed fit allowances (FDM PLA/PETG, as-modelled diametral difference) `[S20]`

| Fit | CAD allowance | Behaviour | Gripper use |
|---|---|---|---|
| Press | −0.10 | Firm thumb or vise pressure | Steel pin into plate. The 0.05–0.10 mm per-side figure is for a 22 mm bearing and is too much for a 3 mm pin `[S20]` |
| Snug / transition | +0.05 | Light friction, holds position | Servo cradle, horn pocket |
| Running | +0.15 | Moves freely, no visible play | Knuckle B bore on pin (if not reamed) |
| Loose | +0.35 | Never binds | Wire channels |

Other guidance:
- FDM interlocking joints: Hubs recommends 0.5 mm tolerance (0.2 mm for SLA/SLS) `[S26]`.
- SLA mating parts: Formlabs Form 4 guide recommends at least 0.4 mm clearance between separate parts printed together (e.g. a gear pair), or they may fuse; minimum hole Ø0.5 mm `[S16b]`. That is a print-in-place limit, not a fit for separately printed parts; for those, start at +0.10 (static) / +0.15 (rotating) and confirm with a coupon `[A]`.
- SO-101 print baseline: PLA+, 0.4 mm nozzle, 0.2 mm layers, 15 % infill, no supports in horizontal-axis screw holes `[S25]`.

### 4d. Heat-set inserts

| Item | Value | Source |
|---|---|---|
| M3 hole | Datasheet 4.0 mm; 4.2 mm in CAD is the as-printed sweet spot (easy install, ~90 % of max strength) | `[S18]` |
| M3 test range | 4.0–4.4 mm coupon | `[S18b]` |
| M2 hole | 3.1 mm starting value (verify with a coupon) | `[S19]` |
| Hole depth | Insert length + ~1 mm (blind) | `[S18b]` |
| Iron temperature | ~225 °C for PLA (print temperature + 10–20 °C) | `[S18b]` |
| Method | Melt about 90 % of the way, then press flush with a flat tool | `[S18b]` |

---

## 5. Gear center distance and backlash

Relations for spur gears `[S22 PDF p. 22, Table 4.1]`:
- `jn = jt·cos α`
- `jr = jt/(2·tan α)`
- `jθ = jt·360/(π·d)` degrees

where jt = circumferential backlash, jn = normal backlash, jr = radial (center-distance) backlash and jθ = angular backlash. Thinning either gear's teeth by Δs adds Δs of jt `[S22b]`.

So a center-distance change gives `Δjt = 2·tan α·Δa = 0.728·Δa` at α = 20° `[D]`.

**Total backlash:** `jt = jt₀ + 0.728·Δa − Δs_A − Δs_B` `[D]`. Negative Δs (thicker teeth) adds to it. jt must stay above 0 at the tight corner, or the mesh binds.

**Lever to the fingertip (this gripper)** `[D]`, using pitch radius r = 12 and fingertip about 85 mm below the pivot (root_offset 22 + root 3 + length 60):
- Finger B tip play = `jt·(85/12) = 7.08·jt`
- Angular play = `4.775°/mm × jt`

| jt (mm) | Play at gear B (°) | Finger-B tip play (mm) |
|---|---|---|
| 0.05 | 0.24 | 0.35 |
| 0.10 | 0.48 | 0.71 |
| 0.15 | 0.72 | 1.06 |
| 0.20 | 0.95 | 1.42 |
| 0.30 | 1.43 | 2.12 |

The STS3215's output backlash is listed as 0.87° `[S24]`, or 1.29 mm at an 85 mm tip `[D]`; the gripper's PWM servo has no published figure, so measure it (§6). That moves both fingers together (it is upstream of the mesh), so it shifts the jaw's center, not its symmetry `[D]`.

One STS3215 step is 0.088° `[S23]`, or 0.13 mm at the tip `[D]`. The PWM design-point servo resolves about its 3 µs deadband, ≈ 0.27° or 0.40 mm at the tip `[D]` (§6).

**Reading.** Under grip load the drive flank stays in contact, so backlash costs position repeatability when the jaw opens or is unloaded, not grip force `[D]`. The 1.0 mm closed_gap is the same size as the tip play from 0.15 mm of jt, so closing the jaw must be calibrated in software (§7, S2).

**Controlling backlash** `[S22 PDF p. 26, §4.4]`:
- Static, by center distance: linear (slotted idler, set, then lock) or rotary (eccentric bushing).
- Static, by tooth thickness.
- Dynamic: an external force that keeps the flanks loaded, e.g. a light spring biasing finger B.

**Recommendation for this gripper** `[D]`: slot the idler-B pin in X. It removes the servo, cradle and print contributors from the stack (§7 S1b) and roughly halves the backlash spread.

**FDM gear practice.** Sovol recommends 0.2–0.4 mm total backlash, made by offsetting each gear's flanks inward 0.1–0.2 mm; module 1.5–2.0 is the sweet spot for a 0.4 mm nozzle, module 1.0 needs careful calibration; print gears flat with the axis along Z `[S28]`. So at m = 1 plan jt₀ ≈ 0.2–0.3 for fixed centers, consistent with S1→jt in §7 `[D]`.

**Axis tilt** `[D]`: pin B is held in the mid plate and the front plate, about 10 mm apart. A front-plate hole offset e tilts the pin by e/10. Across the 6 mm face width that changes center distance by 0.6·e from one face to the other, so perpendicularity of pin B to datum A is a mesh control.

---

## 6. Servo spline and horn

Two different servos meet this gripper, and they must not be mixed up (`docs/gripper/DESIGN-BASIS.md`):

1. **Arm wrist-roll servo 5 (Feetech STS3215, serial bus, stays on the arm).** Its horn is the gripper's mounting interface. Measured from the upstream CAD (`so101.md`): horn OD Ø19.2, 4× Ø2.5 tapped holes on a Ø14.0 bolt circle, 2.5 deep; spline 25 features on ≈ Ø5.3; centre screw reached through a Ø5.4 hole `[D]`. Tolerance it as S4 in §7.
2. **Gripper jaw actuator (a PWM hobby servo, chosen in the W2a trade study).** Knuckle A bolts to that servo's own supplied horn. Its spline, horn diameter, screw size, resolution and backlash come from the chosen part; none is known yet.

| Item | Wrist-roll STS3215 (arm) | Gripper PWM servo (design point DS3218MG) | Tag |
|---|---|---|---|
| Output spline | 25T `[S23]`, `[S24]`; ≈ Ø5.3 in the CAD `[D]`. The 5.9 mm listing value `[A]` is superseded | 25T is common on standard-size metal-gear servos; not verified for DS3218MG | `[A]`, measure |
| Horn used by the gripper | Wrist-roll horn, Ø19.2, 4× M3 on Ø14.0 `[D]` | Supplied metal disc or arm horn; diameter and hole pattern not published | `[A]`, measure |
| Horn screws | M3×6 into the horn `[D]` | From the servo kit | `[A]` |
| Resolution | 4096 counts/rev, 0.088° `[S23]` | Deadband 3 µs `[S: actuators.csv A17]` ≈ 0.27° at 180° per 2000 µs `[D]` | |
| Backlash | 0.87° measured `[S24]` | Not published | `[A]`, measure |
| Body | 45.2 × 24.7 × 35 mm, 55 ± 1 g `[S23]`, `[S24]` | 40 × 20 × 40.5 mm, 58 g `[S: actuators.csv A17]` | |

Guidance `[D]` unless tagged:
- A 25-tooth spline on about Ø5.3–5.9 has a pitch of 0.67–0.74 mm (π·d/25). That is under two 0.4 mm extrusion widths, so a printed female spline will not reproduce the serration. Use the servo's supplied horn and bolt knuckle A to it.
- Locate knuckle A on the gripper servo horn's outer diameter with a snug pocket at CAD +0.05 to +0.10 `[S20]`, once that diameter is measured. Do not locate on the screws.
- The horn's screws carry torque and clamp only. Their clearance holes should not also be the locating feature. That is the fixed-fastener case (§2): `T = (H − F)/2`.
- If a printed spline is ever needed, use SLA (§4a) and verify it against a test coupon `[A]`.
- The SO-101 build guide ships STS3215 fit gauges ("Gauge Zero", "Gauge Tight"). Print them first to calibrate the cradle fit `[S25]`.

---

## 7. Stack-ups this gripper needs (draft)

Contributor tolerances are `[A]` unless tagged. Worst case (WC), RSS and Monte Carlo (MC, 99.73 % band) are `[D]` from the §1 formulas.

| # | Stack (loop) | Contributors (± tolerance, distribution) | WC | RSS | MC 99.73 % | Design target / action |
|---|---|---|---|---|---|---|
| **S1** | Gear center distance a = 24.000 (servo shaft → pin B) | Shaft position in servo case ±0.10 N; servo float in cradle ±0.10 U; cradle wall → hole B (print) ±0.10 N; knuckle B bore float ±0.05 U; knuckle A on horn ±0.05 U; horn on spline ±0.02 U | ±0.42 | ±0.19 (±0.26 with c = 1.732 on the U terms) | −0.24 / +0.24 | Too loose for m = 1 with a fixed center. Go to S1b. |
| **S1b** | Same, with slotted idler B set at assembly | Setting error ±0.03 U; bore float ±0.05 U; horn ±0.05 U; spline ±0.02 U | ±0.15 | ±0.08 | −0.12 / +0.12 | **Recommended.** Lock with 2× M2 screws. |
| **S1→jt** | Backlash jt = jt₀ + 0.728·Δa − Δs_A − Δs_B, with tooth thickness ±0.05 N per gear | S1 or S1b, plus teeth | fixed ±0.41; slotted ±0.21 | n/a | fixed ±0.19; slotted ±0.12 | Fixed centers: jt₀ ≥ 0.2 (MC) to 0.41 (WC). Slotted: set jt₀ ≈ 0.10–0.15 by feel. Tip play 0.7–1.1 mm (§5), so add a spring bias on B if repeatability matters. |
| **S2** | Jaw closed gap 1.0 at θ = 0 (pad A face → pad B face) | a (S1 as 3σ = 0.19) N; knuckle pad line x_f A, B ±0.10 N each; TPU pad face A, B ±0.15 N each; finger seat float A, B ±0.05 U each | ±0.79 | ±0.33 | −0.34 / +0.34 | Geometry alone cannot hold 1.0 ± 0.3. Calibrate the closed position in firmware (close to a position or current threshold, which is a state-machine CALIBRATE state). Tolerance the pads for **symmetry** (profile to A\|B), not for absolute gap. |
| **S3** | Servo cradle X clearance (cavity − 24.7) | Printed cavity ±0.15 N; servo case ±0.05 N `[A]`, measure several | ±0.20 | ±0.16 | ±0.16 | Nominal CAD clearance **+0.25** gives about 0.05 minimum and 0.45 maximum (WC). Add crush ribs or a clamping screw so the float does not feed S1. Validate with the SO-101 gauges `[S25]`. |
| **S4** | Gripper–wrist interface (measured, `so101.md`): 4× M3×6 into the tapped wrist-roll horn on a **Ø14.0 BC** (9.90 mm square), pilot recess over the **Ø19.2 horn OD** (stock recess Ø20.0 × 1.0), centre access hole ≥ Ø5.4, clamp 3.0 | Fixed fastener, H = F + T₁ + T₂ `[S11]`, F = 2.98 `[S9]`, horn pattern 0.05 `[A]` | H = 3.2: T₁+T₂ = 0.22, so printed part gets Ø0.17 (±0.06 per axis). H = 3.4: T₁+T₂ = 0.42, part gets Ø0.37 (±0.13). H = 3.6: T₁+T₂ = 0.62, part gets Ø0.57 (±0.20). | n/a | n/a | Use **medium ISO 273 3.4 as-printed** (CAD 3.6–3.7, §3d) so FDM can hold it. The stock Ø20.0 recess has 0.8 mm diametral clearance on the horn, so it centres only to ±0.4 `[D]`; model the pilot at ≈ Ø19.45 (19.2 + 0.05 snug + ≈ 0.2 FDM undersize) and confirm with a coupon `[D/A]`. Locate on the pilot, not the bolts. Datum D = horn-OD pilot. Values in `cad/gripper/params.json` → `wrist_interface`. |
| **S5** | Pin/bore fits, Ø3 pin B | Steel pin ISO 8734 m6, 3.002–3.008 `[S10]`. Plate hole: CAD 2.9, drill 2.9, press (≈ −0.1 interference) `[S20]`, `[D]`. Knuckle B bore: CAD 3.2 then drill or ream 3.05–3.10, giving clearance ≈ 0.04–0.10 `[D]`. Better: press-fit bronze bushing or bearing in knuckle B, H7/g6-class clearance (+0.002…+0.018) `[S5]` | n/a | n/a | n/a | Bore float feeds S1 directly: each 0.1 mm of diametral clearance is ±0.05 of Δa. Reaming is worth it. |
| **S6** | Finger-to-knuckle joint (TPU finger root on PLA root plate) | Root-plate face → bore (same print) ±0.10 N; 2× M3 through TPU into heat-set inserts (M3 hole CAD 4.2 `[S18]`); screw-hole float (floating fastener T = H − F = 3.4 − 2.98 = 0.42); TPU pad profile ±0.15 `[A]` | yaw ±0.42/spacing rad | n/a | MC (uniform float, 12 mm spacing): ±2.0° | Add a tongue-and-groove or 2 locating pegs (snug +0.05) so the screws only clamp. With 12 mm screw spacing `[A]`, each hole can shift ±0.21 relative to its screw, so the pair allows ±0.42/12 rad = ±2.0° of finger yaw, about ±2.1 mm at the 60 mm tip `[D]`. |
| **S7** | Gear face alignment in Z (knuckle A on horn vs knuckle B on standoff/pin) | Horn seat height ±0.10; knuckle A thickness ±0.10; standoff/washer stack ±0.10; knuckle B thickness ±0.10 (all N) `[A]` | ±0.40 | ±0.20 | n/a | Offset reduces the effective 6 mm face width. Keep WC under 1 mm (17 % of b). Shim washers on pin B. |

Recomputing the numbers: the §1 formulas with the contributor values in each row. The Monte Carlo (numpy, N = 2×10⁵, seed 1; N terms sampled normal σ = T/3, U terms uniform ±T; 99.73 % band = 0.135/99.865 percentiles) was rerun 2026-09-22 and reproduced S1 ±0.24, S1b ±0.12, jt ±0.19/±0.12, S2 ±0.34, S3 ±0.16, S6 ±2.0°. The script is scratch work, not committed; rerun if contributor values change.

### Priority order `[D]`

1. **S1/S1b.** Adopt the slotted idler.
2. **S5.** Ream or bush knuckle B.
3. **S2.** Firmware calibration and pad symmetry.
4. **S4.** Horn measured (`so101.md`); print a pilot and bolt-pattern coupon.
5. **S3, S6, S7.**

---

## Assumptions (all `[A]`, to replace with measurements)

1. Calibrated team FDM printer holds ±0.10 (short features) to ±0.15 (cavities) mm, 3σ, after a calibration coupon.
2. STS3215 shaft is centred on the case width within ±0.10 mm, and the case width tolerance is ±0.05 mm. Neither is published.
3. Printed tooth thickness is within ±0.05 mm per gear at m = 1.
4. Horn centering ±0.05 mm, horn-on-spline radial play ±0.02 mm, SO-101 horn bolt pattern position Ø0.05.
5. TPU 95A pad face ±0.15 mm, a looser print than PLA.
6. Fingertip lever 85 mm (from `params.json`: 22 + 3 + 60).
7. SLA clearances for separately printed mating parts (+0.10 static / +0.15 rotating) are starting values; the only fetched Formlabs number is the 0.4 mm print-in-place minimum. STS3215 spline OD 5.9 mm is from an unfetchable listing; the upstream CAD shows about Ø5.3 (`so101.md`).
8. GD&T callout values in §2 (flatness 0.2, ⊥ Ø0.1, profile 0.4 / 0.1) are starting proposals, not requirements.

## Sources (accessed 2026-09-22)

- `[S1]` F. Scholz, *Tolerance Stack Analysis Methods: A Critical Review*, Boeing ISS, Nov 1995 (UW-hosted). https://faculty.washington.edu/fscholz/DATAFILES498B2008/TOLSTACK.pdf
- `[S2]` Blackrock Engineering, Statistical Tolerance Analysis: RSS and Monte Carlo. https://www.blackrock-engineering.ca/blog/statistical-tolerance-analysis-rss-monte-carlo/
- `[S3]` Wikipedia, Tolerance analysis. https://en.wikipedia.org/wiki/Tolerance_analysis
- `[S4]` Six Sigma Study Guide, Process Capability (Cp & Cpk). https://sixsigmastudyguide.com/process-capability-cp-cpk/
- `[S5]` *Chapter 6: The ISO System of Limits and Fits, Tolerances and Deviations* (ANSI B4.2 / ISO 286 tables; KOK / GoMetricUSA), vendor-hosted. https://kiralytool.com/wp-content/uploads/2017/05/hole-shaft-tolerance-chart.pdf
- `[S6]` RoyMech, ISO 286-2 hole tolerances. https://www.roymech.co.uk/Useful_Tables/ISO_Tolerances/ISO_286_2H.html
- `[S7]` Wikipedia, Engineering fit. https://en.wikipedia.org/wiki/Engineering_fit
- `[S8]` Engineering Hardware, Clearance Hole Sizes (ISO 273). https://engineeringhardware.com/fastener/clearance-hole-sizes/
- `[S9]` Brighton-Best, Metric thread details (ISO 965 6g limits). https://www.brightonbest.com/download/pds/PDS_Thread_Details_Metric_Series.pdf
- `[S9b]` AmesWeb, Metric external thread dimensions chart (6g limits). https://amesweb.info/Screws/metric-external-thread-dimensions-chart.aspx
- `[S10]` Engineers Edge, ISO metric dowel pins per DIN EN ISO 8734. https://www.engineersedge.com/hardware/iso_metric_dowel_pins_13805.htm
- `[S10b]` FastenerMart, ISO 2338 dowel pins (m6/h8). https://www.fastenermart.com/iso-2338-dowel-pins.html
- `[S11]` Tec-Ease, GD&T Tips: Position formulas. https://www.tec-ease.com/gdt-tips-view.php?q=110
- `[S12]` GD&T Basics: True Position https://www.gdandtbasics.com/true-position/ ; Symbols https://www.gdandtbasics.com/gdt-symbols/ ; Datums https://www.gdandtbasics.com/datums/
- `[S13]` Protolabs Network (Hubs), Manufacturing Standards. https://www.hubs.com/manufacturing-standards/
- `[S14]` Hubs, How to design parts for FDM 3D printing. https://www.hubs.com/knowledge-base/how-design-parts-fdm-3d-printing/
- `[S15]` Protolabs, Understanding 3D Printing Tolerances. https://www.protolabs.com/resources/design-tips/3d-printing-tolerances/
- `[S16]` Formlabs, Guide to 3D Printing Tolerances, Accuracy, and Precision. https://formlabs.com/blog/understanding-accuracy-precision-tolerance-in-3d-printing/
- `[S16b]` Formlabs, Form 4 Design Guide (min clearance 0.4 mm, min hole 0.5 mm). https://formlabs.com/white-papers/form-4-design-guide/
- `[S17]` nophead (HydraRaptor), Polyholes. https://hydraraptor.blogspot.com/2011/02/polyholes.html
- `[S18]` CNC Kitchen, Are Our Heat-Set Insert Datasheets Wrong? https://www.cnckitchen.com/blog/are-our-heat-set-insert-datasheets-wrong
- `[S18b]` CNC Kitchen, Tips & Tricks for Heat-Set Inserts. https://www.cnckitchen.com/blog/tips-and-tricks-for-heat-set-inserts
- `[S19]` InsertGuide, Heat Set Insert Hole Size Guide. https://insertguide.com/guides/heat-set-insert-hole-size/
- `[S20]` Creative3DP, Press-Fit Tolerances for 3D Printing. https://tools.creative3dp.com/blog/press-fit-tolerances-3d-printing/
- `[S21]` Bujarska, Zmarzły, Szczygieł, *Sensors* 2025, 25(18):5855, form deviations of FDM cylinders. https://pmc.ncbi.nlm.nih.gov/articles/PMC12473876/
- `[S22]` KHK, *Practical Information on Gears*, §4 Backlash (PDF pp. 22, 26; university-hosted copy). http://ftp.demec.ufpr.br/disciplinas/TMEC038/Prof.Walter_Kapp/khk/gear_guide2.pdf
- `[S22b]` KHK, Gear Backlash. https://khkgears.net/new/gear_knowledge/gear_technical_reference/gear_backlash.html
- `[S23]` DRUAV, Feetech STS3215 listing (25T spline, 4096 steps, M3×6). https://druav.com/en-us/products/feetech-sts3215-20kg-servo
- `[S24]` ServoDatabase, Feetech STS3215 (25T, 0.870° backlash). https://servodatabase.com/servo/feetech/sts3215
- `[S25]` TheRobotStudio, SO-ARM100 / SO-101 README (print settings, STS3215 gauges, TPU finger + 2× M3). https://github.com/TheRobotStudio/SO-ARM100/tree/eecbe3e0a9ebb23e25ad7b2759b03884c6660903
- `[S26]` Hubs, How to design interlocking joints for 3D printed parts. https://www.hubs.com/knowledge-base/how-design-interlocking-joints-fastening-3d-printed-parts/
- `[S27]` Prusa Knowledge Base, Elephant foot compensation. https://help.prusa3d.com/article/elephant-foot-compensation_114487
- `[S28]` Sovol, 3D Printing Gears That Actually Work: Backlash, Orientation, and Material Tips. https://www.sovol3d.com/blogs/news/3d-printing-gears-that-actually-work-backlash-orientation-and-material-tips
