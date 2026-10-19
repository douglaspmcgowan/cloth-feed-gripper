# T13-tab — Wrist-camera aim angle error (pitch of the optical axis)

Variant of `T13`: locating tab kills bracket rotation float

- Requirement: Optical axis within +/-3 deg of nominal so the fingertips stay in view without re-aiming (extrinsics are calibrated anyway).
- Spec: LSL -3.000, USL 3.000 deg
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T13_camera_aim.yaml`; seed 20260922

Bracket held by 2x M3 + hex nuts through clearance holes in both parts (floating fastener, T = H - F each part). Each part can float f = (H - F)/2 on each screw, so the relative float per screw is up to 2f, and with the two screws moving in opposite directions the rotation reaches 4f/s. f is built from limits (review fix): largest printed hole (CAD 3.6 - 0.25 bias + 0.10 scatter = 3.45) less the smallest 6g screw (2.874), f = 0.288, so the WC column is a true worst case (+/-8.15 deg). The MC treats that full float as uniform, which is conservative.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| bracket_rotation_float | linear | 0.000 | 0.000 | -0.849 / +0.849 | 1.0000 | uniform | 0.4901 | 50.0 | D | 2 holes 8.1 apart, CAD 3.6, f from hole and screw limits (basis cam_float), float in both parts |
| housing_boss_perpendicularity | linear | 0.000 | 0.000 | -0.573 / +0.573 | 1.0000 | normal | 0.1910 | 7.6 | A | perp 0.2 over 20 to A |
| bracket_face_perpendicularity | linear | 0.000 | 0.000 | -0.573 / +0.573 | 1.0000 | normal | 0.1910 | 7.6 | A |  |
| board_float | linear | 0.000 | 0.000 | -0.409 / +0.409 | 1.0000 | uniform | 0.2363 | 11.6 | A | 4x M2 |
| lens_tilt | linear | 0.000 | 0.000 | -1.000 / +1.000 | 1.0000 | normal | 0.3333 | 23.1 | A |  |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -3.404 … 3.404 (fail) |
| RSS classic (t = 3σ) | -1.595 … 1.595 |
| RSS distribution-adjusted | -2.079 … 2.079 (pass) |
| MC mean / σ | 0.002 / 0.6910 |
| MC 0.135 % … 99.865 % | -1.923 … 1.928 |
| MC min … max | -2.492 … 2.592 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 1.56 / 1.45 |
| **Verdict (MC)** | **PASS** |

![T13-tab histogram](../../../../docs/gripper/figures/tol_T13-tab.png)
