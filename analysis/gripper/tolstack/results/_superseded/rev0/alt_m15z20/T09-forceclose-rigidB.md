# T09-forceclose-rigidB — Finger closure gap at theta = 0 (at the fingertip pinch point)

Variant of `T09`: force-closed to theta_min, finger B rigid (DB D7)

- Requirement: At theta_min the interference is at least F_target / k_min at the pad (only A deflects), so the FSR stop comes first.
- Spec: USL -6.119 mm (pad B - pad A at the tip; < 0 = pad interference)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T09_closure_gap.yaml`; seed 20260922

gap_tip = a - xf_A - xf_B - pads + finger root float (X, each finger) + servo angle error (both fingers) + finger-B backlash lag. The CAD mesh is centred (README tooth phasing), so when A drives B closed B lags the CAD theta = 0 by jt/(2r), not jt/r. theta = 0 means rigid pads 1 mm apart (DESIGN-BASIS R18). Interference-to-force: the base force variants use 2F/k at the pad (both fingers compliant, equal k). DESIGN-BASIS D7 backs finger B with a rigid FSR plate, so the -rigidB variants use k_B -> infinity: only A deflects and the pad interference for force F is F/k_A. The -pinned variant is the fix-9 layout (T06-bushed / T07-bushed) plus the dog coupling's lash, which rotates both fingers together (tip sensitivity 2 L_tip, like the servo angle error).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| centre_distance | linear | 30.000 | 0.000 | from T06 | 1.0000 | empirical | 0.1135 | 5.2 | D | T06 |
| xf_A | linear | 14.500 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 0.4 | D | params.json closed_gap 1.0 |
| xf_B | linear | 14.500 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 0.4 | D | params.json |
| pad_A_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | -1.0000 | normal | 0.0500 | 1.0 | A | TPU pad |
| pad_B_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | -1.0000 | normal | 0.0500 | 1.0 | A | TPU pad |
| finger_A_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | -1.0000 | disk | 0.1050 | 4.4 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame; replaces W1 S2 seat float (same joint) |
| finger_B_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | 1.0000 | disk | 0.1050 | 4.4 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame |
| servo_angle_error | linear | 0.000 | 0.000 | -0.009 / +0.009 | -140.0000 | normal | 0.0029 | 66.4 | A | rad; both fingers rotate |
| backlash_lag_B | linear | 0.250 | 0.000 | from T07 | 2.3333 | empirical | 0.0876 | 16.7 | D | centred mesh: B lags the CAD angle by jt/(2r) rad |
| command_theta_min | linear | -26.878 | 0.000 | -0.000 / +0.000 | 1.0000 | normal | 0.0000 | 0.0 | D | DB R18 position limit |

| Result | Value |
|---|---|
| Nominal | -25.295 |
| Mean-shifted centre | -25.295 |
| Worst case | -29.351 … -21.239 (pass) |
| RSS classic (t = 3σ) | -26.697 … -23.892 |
| RSS distribution-adjusted | -26.794 … -23.795 (pass) |
| MC mean / σ | -25.295 / 0.5400 |
| MC 0.135 % … 99.865 % | -26.903 … -23.678 |
| MC min … max | -27.568 … -22.949 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 11.86 / 11.84 |
| **Verdict (MC)** | **PASS** |
