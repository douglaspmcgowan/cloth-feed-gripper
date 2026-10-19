# Gear profile, fatigue and wear: 3D printed vs CNC

Lane W2 gears, 2026-09-22 (fix pass 2). 1:1 spur sector pair (finger A on the servo spline, finger B on the idler pin). The design basis (`docs/gripper/DESIGN-BASIS.md`) wins on disagreement, except where section 7 lists a deliberate departure. Tags: [S] sourced, [D] derived by the script, [A] assumed. Every number is [D] unless tagged.

- **Script:** `analysis/gripper/gears.py`. Output `analysis/gripper/results/gears.json` (every input with its tag, the sweep, sensitivity, validation), stdout in `results/gears_stdout.txt`, figures `docs/gripper/figures/gear_*.png`, profile `cad/gripper/gear_profile.svg` / `.dxf`.
- **Re-run** (about 35 s): `python analysis/gripper/gears.py` refreshes JSON, stdout, SVG, and DXF; add `--figures` to also refresh PNGs; use `--check` for a read-only comparison against committed JSON. PNGs are byte-stable on one machine, not across font rasterisers or library versions.

## 0. Answer

<!-- GEARS-AS-DRAWN:BEGIN -->
### Revision B as drawn (generated)

| Item | Generated result |
|---|---|
| Product | DSServo DS3230 MG; m 1.5, z 19, α 25°, x 0, a 28.5 mm, b 10.5 mm |
| Mesh torque: hold / cap / stall / snag | 0.397 / 0.974 / 2.876 / 2.876 N·m |
| F_LC1 | SF 5.049; required 1.500; rule ratio 2.244; **meets rule** |
| F_LC2 | SF 2.892; required 1.500; rule ratio 1.285; **meets rule** |
| F_LC3 | SF 1.412; required 1.000; rule ratio 0.941; **passes below rule** |
| F_shock | SF 1.412; required 1.000; rule ratio 0.941; **passes below rule** |
| H_LC1 | SF 2.398; required 1.000; rule ratio 1.599; **meets rule** |
| H_LC3 | SF 1.485; required 1.000; rule ratio 0.990; **passes below rule** |
| wear | SF 3.431; required 1.000; rule ratio 2.287; **meets rule** |
| fatigue_Miner | SF 4560.963; required 1.000; rule ratio 3040.642; **meets rule** |
| Overall | **passes below rule**; governed by F_LC3 |

<!-- GEARS-AS-DRAWN:END -->

The revision-B pair passes the required stall and snag-shock checks at SF 1.412, but it is below this note's 1.5 recommendation rule. Holding the existing housing-axis error fixed, face width 11.668 mm closes the rule; alternatively x = 1.588 with a compensating module change holds the 28.5 mm centre distance, while changing both needs b = 11.946 mm and x = 0.088. Housing room is `could-not-tell` because `params.json` has no `housing.available_gear_face_width_mm`.

At the repository-supported 40 °C PA6-CF knockdown, stall SF is 1.412. At the thermal lane's 54.25 °C back-off and 106.99 °C no-back-off cases, strength is `could-not-tell`: the repository quotes no PA6-CF knockdown there. The gear therefore cannot be declared acceptable even when back-off works; without back-off it is also thermally unacceptable. Measure hot PA6-CF tooth strength at both temperatures (M24).

The actuation trade's 1.24 / 1.02 at b = 8 mm differs from this script's 1.256 / 1.256 because the study used a different face-load factor and load definitions; this script applies one 2.876 N·m stall/shock result and its current F_β model. Face width also differs from the as-drawn 10.5 mm case.


<!-- GEARS-HISTORICAL:BEGIN -->
Earlier sizing, kept for the record; do not build it.
| Item | Result |
|---|---|
| **Historical DS3218MG sizing: printed primary** | **PA6-CF, m 1.5, z 19, α 25°, x 0, b 8, a = 28.5 mm.** Every SF ≥ 1.58× its required value with F_βy derived per face width (0.067 mm at b 8). LC3 stall root 51.1 MPa vs 82.4 allowable (SF 1.61). DS3235 backup stall and shock: SF 1.12 / 1.11, passes. Pair mass 2.06 g (exact polygon). Wear 0.058 mm face-mean worst case (limit 0.15) |
| **CNC** | **Machined POM, m 1.5, z 21, α 25°, x 0, b 9, a = 31.5 mm.** Every SF ≥ 1.55× required. LC3 root 39.5 MPa vs 62.1. Pair mass 2.9 g. Wear 0.009 mm greased, 0.027 dry |
| Robust printed alternative | PA6-CF m 1.5 z 19 α 25 x 0.25 b 10, a 29.2: every SF ≥ 1.68× required; DS3235 1.25×. Costs 0.7 mm more centre distance and 2 mm more face |
| Previous pick (m 1.25 z 19 b 10, a 23.75) | **Withdrawn.** It rested on F_βy fixed at 0.03 mm for every face width. With F_βy scaled to b it falls to 1.22× (0.08 mm at b 10), below the 1.5× rule, and it fails the DS3235 backup stall (0.89) |
| PETG | **Not recommended on the lane's stress basis.** 3 of 1848 geometries pass every check; none reaches 1.5×. The best is m 1.5 z 21 α 25 x 0.5 b 10 (a 32.9) at 1.06×, wear at 90 % of the limit. m 1.5 z 20 b 6 fails LC2, LC3, shock, flank LC3, wear and Miner. The verdict depends on the basis (see below); M17 decides |
| PLA | Fails everywhere (0 of 1848) |
| Al 6061 / brass | 0 of 1848 Al geometries pass in a printed housing; the flank fails at LC3 in 1841 of them. Stiff teeth edge-load under the housing misalignment (K_Hβ 4.8-20 at the hold over the α 20°, x 0 grid). The best Al margin over all geometries is 1.00×. Brass also fails on its 140 MPa yield [S]. Neither is worth the mass |
| Current CAD (m 1, z 24, b 6) | Fails in every material. PA6-CF fails LC3, shock, wear and Miner; POM fails LC2, LC3, shock and Miner |
| Shock | A finger snag at full closing speed peaks at **1.02× stall** (motor back-EMF damps it); DS3235 1.01×. A rigid stop on a knuckle would peak at **1.9× stall** (4.1 N·m). No hard stop may load the mesh |
| Temperature | Tooth heating +0.02 °C over the duty cycle (+0.8 °C if the squeeze ran continuously), from the VDI root-temperature form that `research/gears.md` 5 says not to trust until checked against VDI 2736-2. The result is about 1000× below any significant rise, so the conclusion holds even if the form is off by an order of magnitude |

**PETG and the stress basis.** The lane compares the VDI local root stress (tip load, YSa ≈ 1.55, K_Fβ) with a 0.81 knockdown against coupon X-Y tensile strength (51 MPa [S TDS]), as the DESIGN-BASIS LC3 rule says. That basis is conservative for tooth bending: the lane's own Onyx gear data carry VDI stresses of 58-69 MPa for more than 1e6 cycles in a material rated 36 MPa tensile. On a flexural basis (PETG 75 MPa [S TDS]) the PETG static allowable would rise 1.47×. The torque note's "PETG m1.5 z20 passes LC3" is not an arithmetic error; it uses Lewis stress without YSa or K_Fβ, the definition the design basis's own gear table used. So PETG is out by method, not by a disproved number. The M17 step-load test decides; until then PA6-CF is the printed material.

**Why this profile (historical DS3218MG sizing at b = 8 mm).** LC3 (full DS3218MG stall at 6.8 V, 2.11 N·m through the mesh) sizes the gear; LC1 fatigue has 5× margin. Root stress ∝ T/(a·b·m), so the coarsest module that keeps z ≥ 18 wins (z ≥ 18 avoids undercut with no shift; the sweep's lower bound). 25° cuts YFa·YSa from 4.39 to 4.04 at z 19, but the lower contact ratio (εα 1.40 vs 1.54) takes most of that back through Yε (3.23 → 3.17 net); its real gains are on the flank and in wear, where 20° options fail first. **Face width stops paying once the teeth edge-load.** F_βy grows with b (every T16 term scales with b). In the edge-loaded regime the peak line load K_Hβ·F_t/b = √(2 c_γ F_βy F_t/b) is then independent of b, so a wider face lowers the root stress only through K_Fβ = K_Hβ^N_F. At the hold K_Hβ is 3.4, so the extra strength must come from a larger module and centre distance. b 8 is the narrowest face that gives ≥ 1.5× at a 28.5. The next options are m 1.5 z 18 b 9 (a 27, 1.53×) and z 18 b 10 (1.54×). The ranking score a + b [A] picks z 19 b 8.

## 1. Load cases (mesh torque)

| LC | Definition | T_mesh N·m | Count over life |
|---|---|---|---|
| LC1 hold | (2·5 N·r_c + 2 N·x_f)/η/2, x_f = a/2 − 0.5 | 0.399 (at a 28.5) | 1e5 [A] |
| LC2 cap | same at 10 N, × K_A 1.25 | 0.976 | 1e3 [A] |
| LC3 stall (historical DS3218MG sizing at b = 8 mm) | DS3218MG 21.5 kg·cm at 6.8 V [S actuators.csv A17], finger B blocked | **2.108** | 1e2 [A] |
| Shock | finger B snags at full speed (0.14 s/60° [S]); ODE J θ'' = T_s(1 − ω/ω₀) − kθ; J = J_rotor·N², J_rotor 5e-8 kg·m² [A], N 300 [A], k = 1.63 N/mm · r_c² | 2.155 (1.02× stall; 1.20× at J_rotor 1e-7) | 1e2 [A] |
| Backup LC3 | DS3235 at 6.8 V: linear between 32 kg·cm (6 V) and 35 (7.4 V) [S A19] = 33.71 kg·cm | 3.306 | sensitivity |
| Backup shock | same ODE with the DS3235 stall, 0.115 s/60° (interpolated 0.13 at 5 V / 0.11 at 7.4 V [S A19]), N 373 [S A19] | 3.352 (1.01×) | sensitivity |

The brief sets a 6.8 V rail. `torque_and_actuator.md` now uses a 6.5 ± 0.15 V rail and evaluates LC3 at 6.65 V (2.09 N·m DS3218MG, 3.28 N·m DS3235), so the lane's 6.8 V figures are about 1 % conservative. Figure: `gear_shock.png`. Rigid-knuckle case (k 50 N·m/rad [A]): 2.9-5.5 N·m. **Rule: firmware angle limits only; if a hard stop is added, put it on knuckle A (servo side), never on B.**

## 2. Method

| Check | Polymers (VDI 2736-2 structure) | Metals (ISO 6336 / AGMA style) |
|---|---|---|
| Root | σF = Ft/(b m)·YFa·YSa·Yε·K_A·K_Fβ, load at the tip | σF = Ft/(b m)·YF·YS·K_A·K_Fβ, ISO 6336-3 Method B (outer point of single-pair contact) |
| Flank | σH = ZE·ZH·Zε·ZB·√(Ft/(b d)·(u+1)/u)·√(K_A K_Hβ) | same |
| Face load | K_Hβ from c_γ·F_βy (ISO 6336-1 form), c_γ = 1/(7.5(1/E1 + 1/E2)) (VDI λ relation); K_Fβ = K_Hβ^N_F | same |
| F_βy | **(b/6)·√((Δa_ip·sin α_w)² + (Δa_op·cos α_w)²)**. Δa_ip = 0.050 mm, the T16-bushed MC 99.73 % band at b 6 [D tolerance stacks]. Δa_op = 0.050 mm, the same hole and bore terms acting out of plane [A isotropic]. An in-plane tilt moves the flank along the line of action by × sin α_w, an out-of-plane tilt by × cos α_w [D geometry]; JGMA 1102 / ISO/TR 10064-3 allow half as much out-of-plane deviation for that reason [S KG Gear 6.3]. RSS [A]; WC is a sensitivity row. Gives 0.033 / 0.050 / 0.083 mm at b 4 / 6 / 10 | same; CNC housing 0.01 mm at b 6 × b/6 [A] |
| Deformation | λ = 7.5·(Ft/b)(1/E1 + 1/E2) ≤ 0.07 m [S gears.md] | trivial |
| Wear | Local Archard, VDI form W = Σ (Fn/b)·ζ·k_w, **face-mean line load** (VDI). Per grip: squeeze + release over 4.4° (ramped), 3 re-steps at hold load, closing/opening at 5 % load [A]. The loaded face end sees K_Hβ × the mean before running-in; that worst-end value is reported beside (section 5), not gated, on the assumption that edge wear runs in and flattens the load [A] | same |
| Temperature | VDI root-temperature form, k_ϑ 2100 [S], duty exponent 0.64. Unverified against VDI 2736-2 (`research/gears.md` 5) | n/a |
| Geometry | undercut, form circle vs start of active profile, εα ≥ 1.2, tip land ≥ max(0.25 m, 0.45 mm printed / 0.20 mm CNC) [A], a ≤ 34 mm [A] | same |

K_V = K_α = 1 (pitch-line speed < 0.02 m/s). Racks: 20° ISO 53 profile A (h_fP 1.25 m, ρ_fP 0.38 m) [S]; 25° h_fP 1.25 m, ρ_fP 0.30 m (near full round) [A].

**Validation** (`gears.json` → `validation`): YF·YS (Method B) = 3.505 / 3.154 / 2.879 / 2.729 / 2.636 for z 14/18/24/30/36, matching the `gears.md` table to 0.01. YFa = 2.80, YSa = 1.55 at z 20 (the familiar ISO chart values). YFa × Lewis Y = 0.90-0.91 for z 20/24/30 [S Lewis Y]. Generated profile: tooth thickness on the reference circle 2.226 vs 2.231 mm analytic, root and tip radii exact, zero overlap in mesh.

## 3. Materials, S-N and knockdowns

Allowable σ_max at R ≈ 0 (one flank). Knockdowns multiply the S-N curve and the static strength.

| Material | Static (design) MPa | S-N basis | Fatigue knockdown | σ at 1e5 (design) MPa | k_w mm³/(N·m) greased / dry |
|---|---|---|---|---|---|
| PLA | 35 × 0.72 | Basquin 68.159 N^−0.161 (R 0.05) [S] → 22.5 at 1e5 | 0.80 temp (40 °C, Tg 60) × 0.90 raster [A] × 1/1.14 notch [S Kf 1.12-1.16] = 0.63 | 14.2 | 1e-4 / 5e-4 [S weak, PETG pin-on-disc] |
| PETG | 51 × 0.81 | 30.6 at 1e5, PLA slope [A] | 0.90 × 0.90 × 1/1.14 = 0.71 | 21.7 | same |
| PA6-CF | 102 × 0.81 | gear-level fit to printed Onyx m1 z20 b6 (58.3 MPa at 4.5e6, 68.9 at 1.4e6, 90 % survival) [D from S Hriberšek 2024]: 497·N^−0.140 | 0.95 temp × 0.85 moisture [A] = 0.81 | 80.3 | 1.48e-5 (Onyx back-calculated 7.4e-6 [D] × 2 self-mated [A]) |
| POM (machined) | 69 × 0.90 | gear-level lower bound = PA6 lives in POM/PA6 m1 z20 b6 tests [D from S Pogacnik & Tavcar]: 797·N^−0.229; gives 33.5 at 1e6 vs 32 coupon [S DuPont] | 0.90 temp | 51.2 | 3.4e-6 [A] / 1e-5 [A] |
| Al 6061-T6 | 276 yield | 0.9 Su at 1e3 [A], 97 at 5e8 [S], Goodman to R 0 | 0.90 surface [A] | 214 | 1e-5 / 1e-3 galling [A] |
| Brass C36000 H02 | 140 yield [S makeitfrom] | 0.35 Su at 1e8 [A], Goodman | 0.90 | 126 (capped at yield × 0.9) | 1e-5 / 1e-3 [A] |

**PA6-CF k_w.** Back-calculated from the Onyx mean wear, W = T·2π·N·(1+u)·H_V·k_w/(b·z·l_Fl), so k_w ∝ l_Fl. VDI 2736-2's exact definition of l_Fl could not be checked (paywalled; no public source found). At the Onyx test gear three lengths are possible: contact-path length 4.60 mm, involute arc from the start of active profile to the tip 1.67 mm, radial flank height 1.54 mm. The script uses the path length [A]. It is the largest, so k_w and every PA6-CF wear depth are **2.75× the arc-length value**: conservative, and no verdict depends on it. The arc-length k_w would be 2.7e-6 (× 2 self-mated).

**POM/POM k_w.** The greased value is the POM-vs-steel dry value (3.4e-6 [S VDI 2736 via Muratović 2024]), so it is [A]: no greased POM/POM coefficient was found, and grease is assumed to offset the self-mating penalty. Dry POM/POM is × 3 [A], because POM/POM wore most in Pogacnik. Even dry, the CNC pick wears 0.027 mm against a 0.15 limit.

**Why self-mated pairs.** `research/gears.md` advises pairing dissimilar polymers (PA6/PA6 μ 0.45). Both picks stay self-mated because the two sectors are one part design printed or cut in one batch. One material also means one moisture state, one thermal expansion, one supply route and one M17 test. Wear passes even on the dry, self-mated k_w. The one dissimilar printed pair evaluated, PETG (A) / PA6-CF (B), is limited by PETG strength, not wear (8 pass, none at 1.5×). A PA6-CF / POM pair would mix a printed and a machined part and was not evaluated.

Printed orientation: gear axis along Z, so the tooth bends in X-Y and X-Y strengths apply [S TDS]. Onyx is weaker than Bambu PA6-CF (36 vs 102 MPa tensile), so the PA6-CF curve is conservative. Flank allowable: Hertz subsurface-yield onset p₀ = 1.67 σ_y (Tresca, line contact) × static knockdown, scaled to N by the root S-N ratio [D/A]; POM gives 85 MPa at 1e5 and 30 MPa at 1e7, below DuPont's 39-42 MPa wear-limited operating level at > 1e7 cycles [S], so the rule is conservative. Figure: `gear_sn.png`.

## 4. Design-space sweep

4 modules × 11 tooth counts × 7 widths × 2 pressure angles × 3 shifts (0, 0.25, 0.5; x1 = x2, working centre distance adjusts) = 1848 geometries per pair, 8 pairs, each at its own F_βy(b, α_w). Figure `gear_design_space.png` shows the narrowest passing b over (m, z).

| Pair | Pass all checks | Pass with every SF ≥ 1.5× required |
|---|---|---|
| PLA | 0 | 0 |
| PETG | 3 (best 1.06×) | 0 |
| PA6-CF | 424 | 130; smallest a + b: m1.5 z19 α25 b8 |
| PETG (A) / PA6-CF (B) | 8 (best 1.05×) | 0 (PETG side governs) |
| POM | 308 | 30; smallest a + b: m1.5 z21 α25 b9 |
| Al 6061 | 0 (best margin over all 1.00×) | 0 |
| Brass, Al/brass | 0 | 0 |

The recommendation rule: pass every check, every SF ≥ 1.5× required [A], then the smallest a + b, then the largest margin.

Named geometries (b 6, α 20, x 0):

| Geometry | PETG | PA6-CF | POM | Al 6061 |
|---|---|---|---|---|
| m1 z24 (current CAD) | fails all | fails LC3, shock, wear, Miner | fails LC2, LC3, shock, Miner | fails flank |
| m1.25 z24 | fails LC1-LC3, shock, flank LC3, wear, Miner | passes | fails LC3, shock | fails flank |
| m1.5 z20 | fails LC2, LC3, shock, flank LC3, wear, Miner | passes | passes | fails flank |

## 5. Historical DS3218MG options (8 mm printed face)

| | Printed PA6-CF m1.5 z19 α25 b8 | CNC POM m1.5 z21 α25 b9 | Printed robust PA6-CF m1.5 z19 α25 x0.25 b10 |
|---|---|---|---|
| a_w / d_a | 28.5 / 31.5 mm | 31.5 / 34.5 mm | 29.21 / 32.2 mm |
| εα / tip land | 1.40 / 0.62 mm | 1.42 / 0.73 mm | 1.30 / 0.54 mm |
| F_βy / K_Hβ at LC1 | 0.067 mm / 3.36 | 0.075 mm / 3.15 | 0.083 mm / 4.19 |
| Root SF: LC1 / LC2 / LC3 / shock | 5.09 / 2.82 / 1.61 / 1.59 | 4.13 / 2.75 / 1.57 / 1.55 | 5.06 / 2.89 / 1.74 / 1.72 |
| Flank SF: LC1 / LC3 | 2.40 / 1.58 | 2.34 / 1.81 | 2.49 / 1.68 |
| σF LC1 / LC3 (MPa) | 15.8 / 51.1 | 12.4 / 39.5 | 15.9 / 47.2 |
| σH LC1 / LC3 (MPa) | 56.0 / 87.0 | 36.5 / 57.3 | 53.8 / 81.7 |
| Life at LC1 / Miner D over 1e5 grips | 1.1e10 / 1.0e-4 | 4.8e7 / 3.0e-3 | 1.1e10 / 6e-5 |
| λ at LC1 (limit) | 0.012 (0.105) mm | 0.015 (0.105) mm | 0.010 (0.105) mm |
| Wear, 1e5 grips, face-mean: worst / phased (limit) | 0.058 / 0.003 (0.15) mm | 0.009 / 0.0004 (0.15) mm greased; 0.027 dry | 0.032 / 0.002 (0.15) mm |
| Wear at the loaded face end (× K_Hβ, before running-in) | 0.19 mm (0.07 with the arc-length k_w) | 0.028 mm | 0.13 mm |
| Backlash design / range | 0.25 / 0.16-0.34 mm; 1.01°; 1.14 mm lag at the tip pad | 0.08 / 0.05-0.11 mm; 0.29°; 0.33 mm lag | 0.25; 0.98°; 1.11 mm lag |
| Backlash growth from wear (worst) | 0.13 mm | 0.02 mm | 0.07 mm |
| Mass, both sectors (teeth + 3 mm rim) | 2.06 g (exact polygon) | 2.9 g | 2.1 g |
| DS3235 backup (LC3 / shock SF) | 1.12 / 1.11, passes | 1.09 / 1.08, passes | 1.26 / 1.25, passes |
| Cost / lead [A] | $0.05-0.20 filament; hardened nozzle about $20 once; same day | $60-200 per pair from an online CNC service at qty 2; 5-15 business days | as printed |

**F_βy sensitivity** (minimum SF / required over all checks; `recommendation.sensitivity`):

| F_βy basis | Printed m1.5 z19 b8 | CNC POM m1.5 z21 b9 | Robust m1.5 z19 x0.25 b10 | Previous pick m1.25 z19 b10 |
|---|---|---|---|---|
| Fixed 0.03 mm | 1.76 | 1.77 | 2.00 | 1.52 |
| Fixed 0.05 mm | 1.66 | 1.66 | 1.86 | 1.39 |
| Fixed 0.08 mm | 1.52 | 1.52 | 1.70 | 1.24 |
| **Derived, RSS (design)** | **1.58** (0.067) | **1.55** (0.075) | **1.68** (0.083) | 1.22 (0.083) |
| Derived, WC | 1.48 (0.089) | 1.45 (0.100) | 1.55 (0.113) | 1.12 (0.111) |
| CNC housing (0.01 × b/6) | 1.86 | 1.87 | 2.11 | 1.63 |

Both picks pass every check in every row. Only the worst-case sum drops them just under the 1.5× rule. The loaded-end wear of the printed pick exceeds the 0.15 limit (0.19 mm) only on the conservative path-length k_w and before running-in; M21 and M22 check it. Figure `gear_safety_factors.png`.

**Printed vs CNC.** Printed PA6-CF is smaller than machined POM (a 28.5 vs 31.5), costs cents and turns around the same day, because its design static allowable is higher (82 vs 62 MPa). CNC buys backlash (0.08 vs 0.25 mm, so 0.8 mm less tip-pad lag) and a known material; it does not buy strength. Metal teeth are the wrong answer here: at these light loads the stiff flanks edge-load in a printed housing.

**Wear phasing.** Worst-case wear assumes the hold contact sits at the root end of the flank (ζ ≈ 2.0). With the contact at the pitch point at θ_hold ≈ −4.7°, wear falls about 20× (section 6).

<!-- GEARS-HISTORICAL:END -->

## 2. Method domain

The ISO 6336-3 root stress-correction expression requires positive notch geometry: tooth-root thickness, bending height, root-fillet radius, slenderness, and notch parameter must all be greater than zero. `root_factors` rejects a geometry outside that physical domain and names the invalid quantity and value. Design-space and sizing searches deliberately discard those rejected trial geometries rather than treating an undefined fractional power as a result.

## 6. Profile for CAD

`cad/gripper/gear_profile.dxf` (R12, closed POLYLINEs; mm) and `.svg`: printed primary, m 1.5 z 19 α 25° x 0, j_t 0.25 mm (each tooth thinned 0.125 mm at the reference circle). Generated by rolling the rack (h_fP 1.25 m, ρ_fP 0.30 m) in 0.2° steps, so the flanks are exact involutes and the root is the true trochoidal fillet (r_f 12.375, form circle 13.10 < start of active profile 13.27: no fillet interference). Layers: GEAR_A (pivot at (−14.25, 0), 6 teeth, gap on the +X centre line), GEAR_B (pivot at (+14.25, 0), 7 teeth, tooth on the −X centre line), PITCH_WORKING, CENTRE. Each sector spans the 31° jaw range + the contact path + one pitch each side, and ends at tooth-space centres. The band runs from r 9.375 (3 mm under the root) to the tip; union it with the knuckle. Revision B extrudes the `params.json` face width, **b = 10.5 mm** (the former DS3218MG profile-selection study used b = 8 mm). Render: `gear_profile.png`. For POM, rerun with that option's `m, z` and `jt 0.08` (change `rec_print` in `main()`).

**Phasing is already in the DXF.** The drawn position is jaw angle θ = 0. A's loaded flank reaches the pitch point at θ = −4.99°. At θ_hold −4.7° (design basis, k 1.0 N/mm) the hold contact sits 0.065 mm from the pitch point (ζ 0.02), with B lagging by the backlash (`profile.phasing`). θ_hold moves with finger stiffness and cloth thickness:

| Case | θ_hold | Contact offset from pitch point | ζ (root end 1.98) |
|---|---|---|---|
| k 0.88 N/mm | −5.30° | −0.070 mm | 0.02 |
| k 1.00 N/mm (design) | −4.70° | +0.065 mm | 0.02 |
| k 1.63 N/mm | −3.00° | +0.448 mm | 0.14 |

**Re-phasing rule.** The contact moves r_b·Δθ along the line of action: 0.225 mm per degree of θ_hold (r_b 12.91 mm). If the measured θ_hold (finger stiffness M-series, cloth thickness) differs by more than about 2° [A: 0.45 mm, ζ 0.14], rotate both sectors' tooth pattern by (θ_hold,new − θ_hold) about their own pivots, A and B by the same angle in opposite senses. Rerun `contact_offset()` in the script to confirm.

## 7. What this changes downstream, and departures from the design basis

<!-- GEARS-DOWNSTREAM:BEGIN -->
### Revision B downstream requests (generated)

| Where | Request |
|---|---|
| `params.json` gear and CAD | Build the drawn DSServo DS3230 MG pair: m 1.5, z 19, α 25°, x 0, a 28.5 mm, b 10.5 mm |
| Housing-width decision | First record available housing width (absent from `params.json`), then choose either the drawn b 10.5 mm at stall root SF 1.412 with a recorded acceptance reason, or widen to b 11.668 mm for the 1.5 rule |
| Firmware | Keep stall back-off ≤ 0.2 s; do not put a hard stop through the mesh |

<!-- GEARS-DOWNSTREAM:END -->

| Departure from DESIGN-BASIS | DB value | Lane value | Effect |
|---|---|---|---|
| LC3 torque | DS3218MG stall at 6.0 V, 2.00 N·m | at 6.8 V, 2.108 N·m (the brief; torque note now 2.09 at 6.65 V) | conservative; at 2.00 N·m the printed LC3 SF would be 1.70 |
| LC3 allowable | X-Y tensile / 1.0 (PA6-CF 102, POM 69) | × static knockdown (82.4, 62.1) | conservative |
| LC1 allowable | PA6-CF 38.0 (Lewis anchor 57 / 1.5), POM 21.3 | VDI gear-level S-N / 1.5: 53.5, 34.1 | less conservative; against the DB values the picks still give 2.41 (PA6-CF) and 1.72 (POM) |
| Root stress | Lewis (DB gear table) | VDI local stress with YSa and K_Fβ | conservative; the reason PETG fails here and passes in the torque note |
| F_βy | not in DB | derived from T16-bushed (section 2) | sets K_Hβ |
| Temperature | not in DB | VDI root-temperature form, unverified against VDI 2736-2 | none (1000× below significance) |

## 8. Team must measure

| # | What | Why |
|---|---|---|
| M17 | Step-load test of printed PA6-CF sector pairs (start at LC1, +20 %/step) and a static stall test at 2.1 N·m; the same for one PETG pair | Every printed allowable is a knockdown on coupon or Onyx data; decides PETG |
| M21 | Flank misalignment across the face, as built (feeler or blue-dye contact pattern), in plane and out of plane | F_βy 0.067 mm (derived) sets K_Hβ ≈ 3.4; WC drops the margin to 1.48× |
| M22 | Wear and backlash after 1e4 grips (dial on the tip-pad lag), both face ends | k_w for printed pairs is weak-sourced; edge wear before running-in |
| M23 | PA6-CF moisture state (weigh a dried coupon over a week) | 0.85 moisture knockdown [A] |
| M6 | Servo stall at the rail voltage | Sets LC3 directly |
| M24 | PA6-CF gear-root strength after soaking at 54.25 °C and 106.99 °C | Repository has no temperature knockdown at either thermal result |

## Sources

- Hriberšek et al. 2024, printed Onyx gear life and wear: https://pmc.ncbi.nlm.nih.gov/articles/PMC11269922/
- Pogacnik & Tavcar, POM/PA6 gear tests, VDI 2736 temperature: http://globasdistribution.com/wp-content/uploads/2017/01/article_kisssoft_vdi_2736_gear_temperature.pdf
- PLA fatigue (Polymers 2026): https://pmc.ncbi.nlm.nih.gov/articles/PMC12787623/
- JGMA 1102 axis-parallelism allowances, consistent with ISO/TR 10064-3:1996 (KG Stock Gears technical data 6.3): https://www.kggear.co.jp/en/wp-content/themes/bizvektor-global-edition/pdf/6.3_Parallelism-of-axes-for-Spur-and-Helical-gears_TechnicalData_KGSTOCKGEARS.pdf ; ISO/TR 10064-3 abstract: https://www.iso.org/standard/23866.html
- T16-bushed stack: `analysis/gripper/tolstack/results/T16-bushed.md`, `docs/gripper/analysis/tolerance_stacks.md` section 6
- Bambu PLA / PETG / PA6-CF TDS, DuPont Delrin guide, VDI deformation check, Muratović 2024 wear, ISO 6336-2/-3 structure, Lewis Y: URLs in `docs/gripper/research/gears.md`
- Brass C36000 H02: https://www.makeitfrom.com/material-properties/Half-Hard-H02-C36000-Brass
- DS3218MG / DS3235 data: rows A17 / A19 in `docs/gripper/research/actuators.csv`
