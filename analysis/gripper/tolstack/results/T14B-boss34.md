# T14B-boss34 — Dog coupling — servo shaft offset from pin A against the dog slot clearance

Variant of `T14B` (option): B40: Ø9 boss location, Ø2.9 hardened shoulders in Ø6 steel inserts, dog slots 3.4

- Requirement: The servo shaft axis and pin A are two separate axes. The two M3 dogs on the horn sit in radial slots in knuckle A, so the slots absorb any offset along the slot, but an offset across the slot must fit inside the tangential half-clearance, or the coupling side-loads the servo bearing and pin A.
- Spec: USL 0.000 mm tangential interference at a dog (> 0 = the dogs force knuckle A sideways)
- Acceptance: WC
- Model: expression; source file `T14B_dog_coupling.yaml`; seed 20260922

Once the boss locates the servo (boss, boss34), the servo case width does not enter this stack at all; only the cradle-located layouts use servo_body_w. Offset across the slot = shaft in case + servo float in the cradle + cradle to pin A hole + spline play + dog screw position + knuckle A float on its pin. For boss variants, wall lean moves the web bore by boss_web_to_pinA * pin_perp_zone / pin_span = 6.30 * 0.10 / 15 = 0.042 mm. Servo-axis direction is set by the ear seats and cradle floor, not the 1.6 mm bore engagement; ear-seat flatness moves the dog plane by boss_to_dog_lever * mount_flatness / servo_ear_span = 3.05 * 0.20 / 54.5 = 0.011 mm. Both levers are CAD derived. Half-clearance = (printed slot width - screw major) / 2. Rev A has 0.06 nominal half-clearance against an offset that can reach 0.5. B40's smooth shoulder diameter limits 2.895..2.905 mm are [A] pending a pin gauge on the machined parts.

Var % from Monte Carlo freeze-one (non-linear model); Sens. is a central difference at the mids and does not rank contributors. Worst case is taken over the corners only, so a minimum inside the box (the kink of abs()) can be missed.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| spline_play | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.0000 | uniform | 0.0289 | 16.9 | A |  |
| dog_pos | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.0000 | normal | 0.0167 | 6.3 | A | dog screw holes in the horn |
| pinA_float | linear | 0.000 | 0.000 | -0.007 / +0.007 | 0.0000 | uniform | 0.0040 | 0.4 | D | knuckle A sleeve on pin A |
| slot_w | linear | 3.400 | -0.100 | -0.150 / +0.150 | -0.5000 | normal | 0.0500 | 37.2 | A | params.json dog_slot_w 3.14 [D]; slot bias and scatter [A] |
| hot_servo_shift | linear | 0.000 | 0.000 | -0.000 / +0.000 | 0.0000 | uniform | 0.0000 | 0.0 | A | hot scenario only (0 when cold): PETG seat relaxes, servo shifts |
| hot_shaft_shift | linear | 0.000 | 0.000 | -0.000 / +0.000 | 0.0000 | normal | 0.0000 | 0.0 | A | hot scenario only (0 when cold): shaft position term widens |
| dog_d | linear | 2.900 | 0.000 | -0.005 / +0.005 | 0.5000 | uniform | 0.0029 | 0.2 | A | custom hardened dog screw smooth shoulder diameter [A; gauge machined parts] |
| boss_bore_to_pinA | linear | 0.000 | 0.000 | -0.100 / +0.100 | 0.0000 | normal | 0.0333 | 25.4 | S | boss bore and pin A hole, one print |
| boss_fit | linear | 0.000 | 0.000 | -0.010 / +0.010 | 0.0000 | uniform | 0.0058 | 0.8 | A | boss in a reamed Ø9 bore: assumed a near line-to-line fit (H7 reamer on a molded boss), no measured data; check the boss diameter on 3 servos |
| boss_to_shaft | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.0000 | normal | 0.0167 | 6.1 | A | output boss to shaft, unpublished |
| boss_web_tilt | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.0000 | normal | 0.0168 | 6.6 | A | wall perpendicularity propagated over the CAD lever; measured bore-centre offset replaces it |
| servo_axis_tilt | linear | 0.000 | 0.000 | -0.011 / +0.011 | 0.0000 | normal | 0.0037 | 0.2 | A | ear-seat flatness propagated over the CAD lever; clamped servo-axis measurement replaces it |

| Result | Value |
|---|---|
| Nominal | -0.250 |
| Mean-shifted centre | -0.200 |
| Worst case | -0.272 … 0.206 (fail) |
| RSS classic (t = 3σ) | -0.275 … -0.125 — not valid: non-linear model, use Monte Carlo |
| RSS distribution-adjusted | -0.272 … -0.125 † (pass); clipped to WC, unclipped -0.275 … -0.125 — not valid: non-linear model, use Monte Carlo |
| MC mean / σ | -0.157 / 0.0407 |
| MC 0.135 % … 99.865 % | -0.258 … -0.014 |
| MC min … max | -0.293 … 0.070 |
| MC out of spec | 600 ppm |
| Cpk percentile / normal | 1.10 ± 0.01 / 1.29 ± 0.00 |
| Yield (MC) | 99.940 % (600 ppm out) |
| Dominant contributor | slot_w (37 %) |
| Pass/fail by the declared method (WC) | FAIL |
| **Verdict (pass / marginal / fail)** | **MARGINAL** |

![T14B-boss34 histogram](figures/tol_T14B-boss34.png)
