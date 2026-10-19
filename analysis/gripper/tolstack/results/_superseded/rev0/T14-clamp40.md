# T14-clamp40 — Gripper servo body in cradle fit (20.0 width)

Variant of `T14`: CAD clearance 0.40 + clamp screw (float no longer matters)

- Requirement: Servo drops in (>= 0) and floats <= 0.30 (float feeds T06 through the cradle).
- Spec: LSL 0.000 mm clearance (pocket - body)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T14_servo_cradle.yaml`; seed 20260922

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| pocket_width | linear | 20.400 | -0.100 | -0.150 / +0.150 | 1.0000 | normal | 0.0500 | 36.0 | A | W1 S3 |
| pocket_first_layer_residual | linear | 0.000 | 0.000 | -0.100 / +0.100 | -1.0000 | uniform | 0.0577 | 48.0 | A | pocket walls start on the bed |
| servo_body_width | linear | 20.000 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 16.0 | S | DS3218MG 20.0 [S]; tol [A] |

| Result | Value |
|---|---|
| Nominal | 0.400 |
| Mean-shifted centre | 0.300 |
| Worst case | -0.050 … 0.650 (fail) |
| RSS classic (t = 3σ) | 0.094 … 0.506 |
| RSS distribution-adjusted | 0.050 … 0.550 (pass) |
| MC mean / σ | 0.300 / 0.0833 |
| MC 0.135 % … 99.865 % | 0.065 … 0.533 |
| MC min … max | -0.014 … 0.618 |
| MC out of spec | 0.001 % (± 0.001 % s.e.) |
| Cpk percentile / normal | 1.28 / 1.20 |
| **Verdict (MC)** | **FAIL** |

![T14-clamp40 histogram](../../../../docs/gripper/figures/tol_T14-clamp40.png)
