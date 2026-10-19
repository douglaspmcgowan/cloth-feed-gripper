# T05-pinned — Jaw centreline offset at the fingertips vs roll axis (X, closing axis)

Variant of `T05`: fix-9 layout: both knuckles on pressed pins, line-reamed, bronze sleeves, dog coupling + pilot 19.51

- Requirement: Pinch point within +/-0.5 mm of its calibrated position. The systematic shift from finger B lagging by half the design backlash (the CAD mesh is centred, so B lags the CAD theta = 0 by jt/(2r); the centre moves half of that: 0.25 * jt0 * L_tip / r) is calibrated into the TCP, so the spec is centred on it.
- Spec: LSL -0.135, USL 0.865 mm (pinch point x vs roll axis, gripper frame G)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T05_jaw_centerline.yaml`; seed 20260922

Kinematics. The jaw centre is x_c = (x_A + x_B)/2 + finger terms. Base layout: pivot A is the servo shaft (x_A = cradle + float + shaft + spline + knuckle A on horn) and pin B is a hole in the housing (x_B = pin B hole + pin float), so every term enters at 0.5. Slotted idler (review fix): pin B is set against gear A at assembly, so x_B = x_A + a and x_c = x_A + (a - a0)/2 with a from T06-slotted (same shared names). The servo chain then enters at 1.0, pinB_pos_to_B drops out, and slot setting and pin float enter at 0.5. spline_play and knuckleA_on_horn enter x_A at +1 and a at -1 (T06-slotted), so they net +0.5. Pinned layout (fix 9): x_A = pin A hole to datum B + knuckle A float; a from T06-bushed, so pin A float nets +0.5 and the hole-to-hole term and pin B float enter at 0.5. The dog coupling's lash rotates A and (through the 1:1 mesh) B by equal and opposite angles, so the tips move symmetrically and the centre does not move (sensitivity 0, carried so the loop is complete; it matters for T09-pinned).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| pilot_float | radial (X proj.) | 0.000 | 0.000 | from T02-cad1951 | 1.0000 | empirical | 0.0411 | 10.1 | D | X component of the T04 pilot float (same samples); frame I X-Y maps onto G X-Z |
| horn_od_eccentricity | radial (X proj.) | 0.000 | 0.000 | -0.050 / +0.050 | 1.0000 | disk | 0.0250 | 3.7 | A | X component of the T04 term |
| servo5_radial_play | radial (X proj.) | 0.000 | 0.000 | -0.050 / +0.050 | 1.0000 | disk | 0.0250 | 3.7 | A | X component of the T04 term |
| xf_A | linear | 0.000 | 0.000 | -0.100 / +0.100 | 0.5000 | normal | 0.0333 | 1.7 | A | pad line A |
| xf_B | linear | 0.000 | 0.000 | -0.100 / +0.100 | -0.5000 | normal | 0.0333 | 1.7 | A | pad line B |
| pad_A_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | 0.5000 | normal | 0.0500 | 3.7 | A | TPU pad |
| pad_B_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | -0.5000 | normal | 0.0500 | 3.7 | A | TPU pad |
| finger_A_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | 0.5000 | disk | 0.1050 | 16.5 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame |
| finger_B_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | 0.5000 | disk | 0.1050 | 16.5 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame |
| backlash_lag_B | linear | 0.250 | 0.000 | from T07-bushed | 1.4583 | empirical | 0.0307 | 12.0 | D | centred CAD mesh: B lags the CAD angle by jt/(2r) rad while A drives it closed; centre moves half |
| pinA_pos_to_B | linear | 0.000 | 0.000 | -0.200 / +0.200 | 1.0000 | normal | 0.0667 | 26.5 | A | pin A plate hole to datum B (recess), ~45 mm apart |
| pinA_float | linear | 0.000 | 0.000 | -0.010 / +0.010 | 0.5000 | uniform | 0.0058 | 0.0 | A | +1 in x_A, -1 in a (T06-bushed): net 0.5 |
| pinA_to_pinB_holes | linear | 0.000 | 0.000 | -0.030 / +0.030 | 0.5000 | normal | 0.0100 | 0.1 | A | in a (T06-bushed): 0.5 |
| pin_float | linear | 0.000 | 0.000 | -0.010 / +0.010 | 0.5000 | uniform | 0.0058 | 0.0 | A | knuckle B sleeve, in a (T06-bushed): 0.5 |
| dog_lash | linear | 0.000 | 0.000 | -0.010 / +0.010 | 0.0000 | uniform | 0.0058 | 0.0 | A | symmetric rotation of A and B: centre does not move |

| Result | Value |
|---|---|
| Nominal | 0.365 |
| Mean-shifted centre | 0.365 |
| Worst case | -0.880 … 1.610 (fail) |
| RSS classic (t = 3σ) | 0.011 … 0.718 |
| RSS distribution-adjusted | -0.024 … 0.753 (pass) |
| MC mean / σ | 0.365 / 0.1297 |
| MC 0.135 % … 99.865 % | -0.017 … 0.749 |
| MC min … max | -0.169 … 1.003 |
| MC out of spec | 0.007 % (± 0.0026 % s.e.) |
| Cpk percentile / normal | 1.30 / 1.28 |
| **Verdict (MC)** | **FAIL** |

![T05-pinned histogram](../../../../docs/gripper/figures/tol_T05-pinned.png)
