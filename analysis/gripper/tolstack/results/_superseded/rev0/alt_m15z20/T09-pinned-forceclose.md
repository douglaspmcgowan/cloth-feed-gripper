# T09-pinned-forceclose — Finger closure gap at theta = 0 (at the fingertip pinch point)

Variant of `T09`: fix-9 layout + dog-coupling lash, force-closed to theta_min (symmetric k)

- Requirement: Fix 7 (close on force) still holds in the fix-9 layout with the dog lash added.
- Spec: USL -12.238 mm (pad B - pad A at the tip; < 0 = pad interference)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T09_closure_gap.yaml`; seed 20260922

gap_tip = a - xf_A - xf_B - pads + finger root float (X, each finger) + servo angle error (both fingers) + finger-B backlash lag. The CAD mesh is centred (README tooth phasing), so when A drives B closed B lags the CAD theta = 0 by jt/(2r), not jt/r. theta = 0 means rigid pads 1 mm apart (DESIGN-BASIS R18). Interference-to-force: the base force variants use 2F/k at the pad (both fingers compliant, equal k). DESIGN-BASIS D7 backs finger B with a rigid FSR plate, so the -rigidB variants use k_B -> infinity: only A deflects and the pad interference for force F is F/k_A. The -pinned variant is the fix-9 layout (T06-bushed / T07-bushed) plus the dog coupling's lash, which rotates both fingers together (tip sensitivity 2 L_tip, like the servo angle error).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| centre_distance | linear | 30.000 | 0.000 | from T06-bushed | 1.0000 | empirical | 0.0129 | 0.0 | D | T06 |
| xf_A | linear | 14.500 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 0.1 | D | params.json closed_gap 1.0 |
| xf_B | linear | 14.500 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 0.1 | D | params.json |
| pad_A_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | -1.0000 | normal | 0.0500 | 0.3 | A | TPU pad |
| pad_B_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | -1.0000 | normal | 0.0500 | 0.3 | A | TPU pad |
| finger_A_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | -1.0000 | disk | 0.1050 | 1.3 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame; replaces W1 S2 seat float (same joint) |
| finger_B_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | 1.0000 | disk | 0.1050 | 1.3 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame |
| servo_angle_error | linear | 0.000 | 0.000 | -0.009 / +0.009 | -140.0000 | normal | 0.0029 | 19.4 | A | rad; both fingers rotate |
| backlash_lag_B | linear | 0.250 | 0.000 | from T07-bushed | 2.3333 | empirical | 0.0307 | 0.6 | D | centred mesh: B lags the CAD angle by jt/(2r) rad |
| dog_lash | linear | 0.000 | 0.000 | -0.010 / +0.010 | -140.0000 | uniform | 0.0058 | 76.5 | A | rad; dog clearance / (2 x drive radius) |
| command_theta_min | linear | -26.878 | 0.000 | -0.000 / +0.000 | 1.0000 | normal | 0.0000 | 0.0 | D | DB R18 position limit |

| Result | Value |
|---|---|
| Nominal | -25.295 |
| Mean-shifted centre | -25.295 |
| Worst case | -29.375 … -21.215 (pass) |
| RSS classic (t = 3σ) | -27.206 … -23.384 |
| RSS distribution-adjusted | -28.067 … -22.523 (pass) |
| MC mean / σ | -25.295 / 0.9212 |
| MC 0.135 % … 99.865 % | -27.589 … -23.030 |
| MC min … max | -28.239 … -22.386 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 5.77 / 4.72 |
| **Verdict (MC)** | **PASS** |
