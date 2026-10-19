# T09-hold47-rigidB — Finger closure gap at theta = 0 (at the fingertip pinch point)

Variant of `T09`: hold at -4.7 deg, finger B rigid (DB D7): interference F/k_A

- Requirement: A fixed hold angle of -4.7 deg reaches 5 N when only the softest finger A deflects (F_target / k_min at the pad).
- Spec: USL -6.119 mm (pad B - pad A at the tip; < 0 = pad interference)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T09_closure_gap.yaml`; seed 20260922

gap_tip = a - xf_A - xf_B - pads + finger root float (X, each finger) + servo angle error (both fingers) + finger-B backlash lag. The CAD mesh is centred (README tooth phasing), so when A drives B closed B lags the CAD theta = 0 by jt/(2r), not jt/r. theta = 0 means rigid pads 1 mm apart (DESIGN-BASIS R18). Interference-to-force: the base force variants use 2F/k at the pad (both fingers compliant, equal k). DESIGN-BASIS D7 backs finger B with a rigid FSR plate, so the -rigidB variants use k_B -> infinity: only A deflects and the pad interference for force F is F/k_A. The -pinned variant is the fix-9 layout (T06-bushed / T07-bushed) plus the dog coupling's lash, which rotates both fingers together (tip sensitivity 2 L_tip, like the servo angle error).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| centre_distance | linear | 24.000 | 0.000 | from T06 | 1.0000 | empirical | 0.1135 | 4.7 | D | T06 |
| xf_A | linear | 11.500 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 0.4 | D | params.json closed_gap 1.0 |
| xf_B | linear | 11.500 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 0.4 | D | params.json |
| pad_A_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | -1.0000 | normal | 0.0500 | 0.9 | A | TPU pad |
| pad_B_profile | linear | 0.000 | 0.000 | -0.150 / +0.150 | -1.0000 | normal | 0.0500 | 0.9 | A | TPU pad |
| finger_A_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | -1.0000 | disk | 0.1050 | 4.0 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame; replaces W1 S2 seat float (same joint) |
| finger_B_root_float | radial (X proj.) | 0.000 | 0.000 | -0.210 / +0.210 | 1.0000 | disk | 0.1050 | 4.0 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame |
| servo_angle_error | linear | 0.000 | 0.000 | -0.009 / +0.009 | -140.0000 | normal | 0.0029 | 60.7 | A | rad; both fingers rotate |
| backlash_lag_B | linear | 0.250 | 0.000 | from T07 | 2.9167 | empirical | 0.0876 | 23.9 | D | centred mesh: B lags the CAD angle by jt/(2r) rad |
| command_theta_hold | linear | -11.484 | 0.000 | -0.000 / +0.000 | 1.0000 | normal | 0.0000 | 0.0 | D | DB section 3 theta_hold |

| Result | Value |
|---|---|
| Nominal | -9.755 |
| Mean-shifted centre | -9.755 |
| Worst case | -14.150 … -5.360 (fail) |
| RSS classic (t = 3σ) | -11.207 … -8.304 |
| RSS distribution-adjusted | -11.323 … -8.187 (pass) |
| MC mean / σ | -9.756 / 0.5709 |
| MC 0.135 % … 99.865 % | -11.451 … -8.044 |
| MC min … max | -12.133 … -7.336 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 2.13 / 2.12 |
| **Verdict (MC)** | **PASS** |

![T09-hold47-rigidB histogram](../../../../docs/gripper/figures/tol_T09-hold47-rigidB.png)
