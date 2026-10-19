# T14B-boss34 — Dog coupling — servo shaft offset from pin A against the dog slot clearance

Variant of `T14B` (option): servo located by its Ø9 boss in a reamed bore + dog slots 3.4

- Requirement: The servo shaft axis and pin A are two separate axes. The two M3 dogs on the horn sit in radial slots in knuckle A, so the slots absorb any offset along the slot, but an offset across the slot must fit inside the tangential half-clearance, or the coupling side-loads the servo bearing and pin A.
- Spec: USL 0.000 mm tangential interference at a dog (> 0 = the dogs force knuckle A sideways)
- Acceptance: WC
- Model: expression; source file `T14B_dog_coupling.yaml`; seed 20260922

Once the boss locates the servo (boss, boss34), the servo case width does not enter this stack at all; only the cradle-located layouts use servo_body_w. Offset across the slot = shaft in case + servo float in the cradle + cradle to pin A hole + spline play + dog screw position + knuckle A float on its pin. For boss variants, wall lean moves the web bore by boss_web_to_pinA * pin_perp_zone / pin_span = 6.30 * 0.10 / 15 = 0.042 mm. Servo-axis direction is set by the ear seats and cradle floor, not the 1.6 mm bore engagement; ear-seat flatness moves the dog plane by boss_to_dog_lever * mount_flatness / servo_ear_span = 3.05 * 0.20 / 54.5 = 0.011 mm. Both levers are CAD derived. Half-clearance = (printed slot width - screw major) / 2. Rev A has 0.06 nominal half-clearance against an offset that can reach 0.5.

Var % from Monte Carlo freeze-one (non-linear model); Sens. is a central difference at the mids and does not rank contributors. Worst case is taken over the corners only, so a minimum inside the box (the kink of abs()) can be missed.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| spline_play | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.0000 | uniform | 0.0289 | 15.0 | A |  |
| dog_pos | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.0000 | normal | 0.0167 | 5.5 | A | dog screw holes in the horn |
| pinA_float | linear | 0.000 | 0.000 | -0.007 / +0.007 | 0.0000 | uniform | 0.0040 | 0.3 | D | knuckle A sleeve on pin A |
| slot_w | linear | 3.400 | -0.100 | -0.150 / +0.150 | -0.5000 | normal | 0.0500 | 32.4 | A | params.json dog_slot_w 3.14 [D]; slot bias and scatter [A] |
| dog_d | linear | 2.927 | 0.000 | -0.053 / +0.053 | 0.5000 | uniform | 0.0306 | 12.6 | S | M3 6g major |
| hot_servo_shift | linear | 0.000 | 0.000 | -0.000 / +0.000 | 0.0000 | uniform | 0.0000 | 0.0 | A | hot scenario only (0 when cold): PETG seat relaxes, servo shifts |
| hot_shaft_shift | linear | 0.000 | 0.000 | -0.000 / +0.000 | 0.0000 | normal | 0.0000 | 0.0 | A | hot scenario only (0 when cold): shaft position term widens |
| boss_bore_to_pinA | linear | 0.000 | 0.000 | -0.100 / +0.100 | 0.0000 | normal | 0.0333 | 22.3 | S | boss bore and pin A hole, one print |
| boss_fit | linear | 0.000 | 0.000 | -0.010 / +0.010 | 0.0000 | uniform | 0.0058 | 0.7 | A | boss in a reamed Ø9 bore: assumed a near line-to-line fit (H7 reamer on a molded boss), no measured data; check the boss diameter on 3 servos |
| boss_to_shaft | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.0000 | normal | 0.0167 | 5.3 | A | output boss to shaft, unpublished |
| boss_web_tilt | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.0000 | normal | 0.0168 | 5.8 | A | wall perpendicularity propagated over the CAD lever; measured bore-centre offset replaces it |
| servo_axis_tilt | linear | 0.000 | 0.000 | -0.011 / +0.011 | 0.0000 | normal | 0.0037 | 0.2 | A | ear-seat flatness propagated over the CAD lever; clamped servo-axis measurement replaces it |

| Result | Value |
|---|---|
| Nominal | -0.236 |
| Mean-shifted centre | -0.186 |
| Worst case | -0.283 … 0.244 (fail) |
| RSS classic (t = 3σ) | -0.266 … -0.107 — not valid: non-linear model, use Monte Carlo |
| RSS distribution-adjusted | -0.274 … -0.099 (pass) — not valid: non-linear model, use Monte Carlo |
| MC mean / σ | -0.144 / 0.0435 |
| MC 0.135 % … 99.865 % | -0.254 … 0.006 |
| MC min … max | -0.286 … 0.098 |
| MC out of spec | 0.196 % |
| Cpk percentile / normal | 0.96 ± 0.01 / 1.10 ± 0.00 |
| Yield (MC) | 99.80 % |
| Dominant contributor | slot_w (32 %) |
| Pass/fail by the declared method (WC) | FAIL |
| **Verdict (pass / marginal / fail)** | **FAIL** |

![T14B-boss34 histogram](figures/tol_T14B-boss34.png)
