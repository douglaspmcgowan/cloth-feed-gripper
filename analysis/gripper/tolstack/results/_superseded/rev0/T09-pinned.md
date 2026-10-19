# T09-pinned — Finger closure gap at theta = 0 (at the fingertip pinch point)

Variant of `T09`: fix-9 layout (pinned, line-reamed, bronze sleeves) + dog-coupling lash, at theta = 0

- Requirement: Spread about the design gap. theta = 0 is defined as rigid pads 1.0 mm apart (DESIGN-BASIS R18, params.json closed_gap), and finger B's backlash lag (0.5 jt0 L_tip / r) is calibrated, so the nominal is 1.0 + lag. At a commanded theta = 0 the tip gap stays within +/-1.0 of that (gap0_spread_max): the pads never touch at rest, and first contact comes within 0.41 deg (1.5 deadband steps) of its calibrated angle.
- Spec: LSL 0.729, USL 2.729 mm (pad B - pad A at the tip; < 0 = pad interference)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T09_closure_gap.yaml`; seed 20260922

gap_tip = a - xf_A - xf_B - pads + finger root float (X, each finger) + servo angle error (both fingers) + finger-B backlash lag. The CAD mesh is centred (README tooth phasing), so when A drives B closed B lags the CAD theta = 0 by jt/(2r), not jt/r. theta = 0 means rigid pads 1 mm apart (DESIGN-BASIS R18). Interference-to-force: the base force variants use 2F/k at the pad (both fingers compliant, equal k). DESIGN-BASIS D7 backs finger B with a rigid FSR plate, so the -rigidB variants use k_B -> infinity: only A deflects and the pad interference for force F is F/k_A. The -pinned variant is the fix-9 layout (T06-bushed / T07-bushed) plus the dog coupling's lash, which rotates both fingers together (tip sensitivity 2 L_tip, like the servo angle error).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| centre_distance | linear | 24.000 | 0.000 | from T06-bushed | 1.0000 | empirical | 0.0129 | 0.0 | D | T06 |
| xf_A | linear | 11.500 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 0.1 | D | params.json closed_gap 1.0 |
| xf_B | linear | 11.500 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 0.1 | D | params.json |
| pad_A_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | -1.0000 | normal | 0.0500 | 0.3 | A | TPU pad |
| pad_B_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | -1.0000 | normal | 0.0500 | 0.3 | A | TPU pad |
| finger_A_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | -1.0000 | disk | 0.1050 | 1.3 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame; replaces W1 S2 seat float (same joint) |
| finger_B_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | 1.0000 | disk | 0.1050 | 1.3 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame |
| servo_angle_error | linear | 0.000 | 0.000 | -0.009 / +0.009 | -140.0000 | normal | 0.0029 | 19.4 | A | rad; both fingers rotate |
| backlash_lag_B | linear | 0.250 | 0.000 | from T07-bushed | 2.9167 | empirical | 0.0307 | 0.9 | D | centred mesh: B lags the CAD angle by jt/(2r) rad |
| dog_lash | linear | 0.000 | 0.000 | -0.010 / +0.010 | -140.0000 | uniform | 0.0058 | 76.3 | A | rad; dog clearance / (2 x drive radius), either direction (uncalibrated: conservative) |

| Result | Value |
|---|---|
| Nominal | 1.729 |
| Mean-shifted centre | 1.729 |
| Worst case | -2.473 … 5.931 (fail) |
| RSS classic (t = 3σ) | -0.188 … 3.647 |
| RSS distribution-adjusted | -1.047 … 4.506 (fail) |
| MC mean / σ | 1.729 / 0.9229 |
| MC 0.135 % … 99.865 % | -0.568 … 3.999 |
| MC min … max | -1.227 … 4.617 |
| MC out of spec | 31.7 % (± 0.15 % s.e.) |
| Cpk percentile / normal | 0.44 / 0.36 |
| **Verdict (MC)** | **FAIL** |

![T09-pinned histogram](../../../../docs/gripper/figures/tol_T09-pinned.png)
