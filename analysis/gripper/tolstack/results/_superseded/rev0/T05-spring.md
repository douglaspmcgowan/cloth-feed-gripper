# T05-spring — Jaw centreline offset at the fingertips vs roll axis (X, closing axis)

Variant of `T05`: slotted idler + pilot CAD 19.51 + spring bias on finger B (no lag)

- Requirement: Pinch point within +/-0.5 mm of its calibrated position. The systematic shift from finger B lagging by half the design backlash (the CAD mesh is centred, so B lags the CAD theta = 0 by jt/(2r); the centre moves half of that: 0.25 * jt0 * L_tip / r) is calibrated into the TCP, so the spec is centred on it.
- Spec: LSL -0.500, USL 0.500 mm (pinch point x vs roll axis, gripper frame G)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T05_jaw_centerline.yaml`; seed 20260922

Kinematics. The jaw centre is x_c = (x_A + x_B)/2 + finger terms. Base layout: pivot A is the servo shaft (x_A = cradle + float + shaft + spline + knuckle A on horn) and pin B is a hole in the housing (x_B = pin B hole + pin float), so every term enters at 0.5. Slotted idler (review fix): pin B is set against gear A at assembly, so x_B = x_A + a and x_c = x_A + (a - a0)/2 with a from T06-slotted (same shared names). The servo chain then enters at 1.0, pinB_pos_to_B drops out, and slot setting and pin float enter at 0.5. spline_play and knuckleA_on_horn enter x_A at +1 and a at -1 (T06-slotted), so they net +0.5. Pinned layout (fix 9): x_A = pin A hole to datum B + knuckle A float; a from T06-bushed, so pin A float nets +0.5 and the hole-to-hole term and pin B float enter at 0.5. The dog coupling's lash rotates A and (through the 1:1 mesh) B by equal and opposite angles, so the tips move symmetrically and the centre does not move (sensitivity 0, carried so the loop is complete; it matters for T09-pinned).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| pilot_float | radial (X proj.) | 0.000 | 0.000 | from T02-cad1951 | 1.0000 | empirical | 0.0411 | 6.8 | D | X component of the T04 pilot float (same samples); frame I X-Y maps onto G X-Z |
| horn_od_eccentricity | radial (X proj.) | 0.000 | 0.000 | -0.050 / +0.050 | 1.0000 | disk | 0.0250 | 2.5 | A | X component of the T04 term |
| servo5_radial_play | radial (X proj.) | 0.000 | 0.000 | -0.050 / +0.050 | 1.0000 | disk | 0.0250 | 2.5 | A | X component of the T04 term |
| xf_A | linear | 0.000 | 0.000 | -0.100 / +0.100 | 0.5000 | normal | 0.0333 | 1.1 | A | pad line A |
| xf_B | linear | 0.000 | 0.000 | -0.100 / +0.100 | -0.5000 | normal | 0.0333 | 1.1 | A | pad line B |
| pad_A_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | 0.5000 | normal | 0.0500 | 2.5 | A | TPU pad |
| pad_B_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | -0.5000 | normal | 0.0500 | 2.5 | A | TPU pad |
| finger_A_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | 0.5000 | disk | 0.1050 | 11.0 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame |
| finger_B_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | 0.5000 | disk | 0.1050 | 11.0 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame |
| cradle_pos_to_B | linear | 0.000 | 0.000 | -0.200 / +0.200 | 1.0000 | normal | 0.0667 | 17.8 | A | x_A chain at 1.0: pin B follows A |
| servo_float_in_cradle | linear | 0.000 | 0.000 | -0.125 / +0.125 | 1.0000 | uniform | 0.0722 | 20.9 | D | x_A chain |
| shaft_in_case | linear | 0.000 | 0.000 | -0.200 / +0.200 | 1.0000 | normal | 0.0667 | 17.8 | A | x_A chain |
| spline_play | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.5000 | uniform | 0.0289 | 0.8 | A | +1 in x_A, -1 in a (T06-slotted): net 0.5 |
| knuckleA_on_horn | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.5000 | uniform | 0.0289 | 0.8 | A | +1 in x_A, -1 in a (T06-slotted): net 0.5 |
| pin_float | linear | 0.000 | 0.000 | -0.035 / +0.035 | 0.5000 | uniform | 0.0202 | 0.4 | D | in a (T06-slotted): 0.5 |
| slot_setting | linear | 0.000 | 0.000 | -0.030 / +0.030 | 0.5000 | uniform | 0.0173 | 0.3 | A | in a (T06-slotted, W1 S1b): 0.5 |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -1.323 … 1.323 (fail) |
| RSS classic (t = 3σ) | -0.406 … 0.406 |
| RSS distribution-adjusted | -0.474 … 0.474 (pass) |
| MC mean / σ | 0.000 / 0.1580 |
| MC 0.135 % … 99.865 % | -0.466 … 0.470 |
| MC min … max | -0.694 … 0.681 |
| MC out of spec | 0.124 % (± 0.011 % s.e.) |
| Cpk percentile / normal | 1.06 / 1.05 |
| **Verdict (MC)** | **FAIL** |

![T05-spring histogram](../../../../docs/gripper/figures/tol_T05-spring.png)
