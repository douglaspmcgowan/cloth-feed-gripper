# T06-slotted — Gear centre distance a (servo shaft A to idler pin B)

Variant of `T06`: slotted idler B, set at assembly

- Requirement: a stays inside the band that keeps backlash between jt_min and jt_max for the design jt0 (T07).
- Spec: LSL 29.725, USL 30.275 mm
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
| Nominal | 30.000 |
| Mean-shifted centre | 30.000 |
| Worst case | 29.835 … 30.165 (pass) |
| RSS classic (t = 3σ) | 29.916 … 30.084 |
| RSS distribution-adjusted | 29.854 … 30.146 (pass) |
| MC mean / σ | 30.000 / 0.0488 |
| MC 0.135 % … 99.865 % | 29.870 … 30.131 |
| MC min … max | 29.845 … 30.157 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 2.09 / 1.88 |
| **Verdict (MC)** | **PASS** |
