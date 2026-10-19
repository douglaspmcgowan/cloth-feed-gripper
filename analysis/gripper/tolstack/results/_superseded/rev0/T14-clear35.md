# T14-clear35 — Gripper servo body in cradle fit (20.0 width)

Variant of `T14`: CAD clearance 0.35 + crush ribs

- Requirement: Servo drops in (>= 0) and floats <= 0.30 (float feeds T06 through the cradle).
- Spec: LSL 0.000, USL 0.300 mm clearance (pocket - body)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T14_servo_cradle.yaml`; seed 20260922

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| pocket_width | linear | 20.350 | -0.100 | -0.150 / +0.150 | 1.0000 | normal | 0.0500 | 36.0 | A | W1 S3 |
| pocket_first_layer_residual | linear | 0.000 | 0.000 | -0.100 / +0.100 | -1.0000 | uniform | 0.0577 | 48.0 | A | pocket walls start on the bed |
| servo_body_width | linear | 20.000 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 16.0 | S | DS3218MG 20.0 [S]; tol [A] |

| Result | Value |
|---|---|
| Nominal | 0.350 |
| Mean-shifted centre | 0.250 |
| Worst case | -0.100 … 0.600 (fail) |
| RSS classic (t = 3σ) | 0.044 … 0.456 |
| RSS distribution-adjusted | 0.000 … 0.500 (fail) |
| MC mean / σ | 0.250 / 0.0833 |
| MC 0.135 % … 99.865 % | 0.015 … 0.483 |
| MC min … max | -0.064 … 0.568 |
| MC out of spec | 28.4 % (± 0.14 % s.e.) |
| Cpk percentile / normal | 0.21 / 0.20 |
| **Verdict (MC)** | **FAIL** |

![T14-clear35 histogram](../../../../docs/gripper/figures/tol_T14-clear35.png)
