# T06-slotted — Gear centre distance a (servo shaft A to idler pin B)

Variant of `T06`: slotted idler B, set at assembly

- Requirement: a stays inside the band that keeps backlash between jt_min and jt_max for the design jt0 (T07).
- Spec: LSL 23.725, USL 24.275 mm
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T06_gear_center_distance.yaml`; seed 20260922

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| pin_float | linear | 0.000 | 0.000 | -0.035 / +0.035 | 1.0000 | uniform | 0.0202 | 17.2 | D | knuckle B reamed 3.075 bore on the m6 pin (pin pressed into the plates: no plate float) |
| spline_play | linear | 0.000 | 0.000 | -0.050 / +0.050 | -1.0000 | uniform | 0.0289 | 35.1 | A |  |
| knuckleA_on_horn | linear | 0.000 | 0.000 | -0.050 / +0.050 | -1.0000 | uniform | 0.0289 | 35.1 | A | snug pocket |
| slot_setting | linear | 0.000 | 0.000 | -0.030 / +0.030 | 1.0000 | uniform | 0.0173 | 12.6 | A | W1 S1b |

| Result | Value |
|---|---|
| Nominal | 24.000 |
| Mean-shifted centre | 24.000 |
| Worst case | 23.835 … 24.165 (pass) |
| RSS classic (t = 3σ) | 23.916 … 24.084 |
| RSS distribution-adjusted | 23.854 … 24.146 (pass) |
| MC mean / σ | 24.000 / 0.0488 |
| MC 0.135 % … 99.865 % | 23.870 … 24.131 |
| MC min … max | 23.845 … 24.157 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 2.09 / 1.88 |
| **Verdict (MC)** | **PASS** |

![T06-slotted histogram](../../../../docs/gripper/figures/tol_T06-slotted.png)
