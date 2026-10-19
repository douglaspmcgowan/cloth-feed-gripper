# T07-slotted — Gear backlash jt (circumferential)

Variant of `T07`: slotted idler B

- Requirement: jt between 0.05 (no binding) and 0.45 (open-jaw repeatability), design jt0 = 0.25 by flank offset.
- Spec: LSL 0.050, USL 0.450 mm circumferential backlash
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T07_backlash.yaml`; seed 20260922

jt = jt0 + 2 tan(alpha) (a - a0) - ds_A - ds_B, plus pitch-circle runout of each gear (KHK Table 4.1 via W1).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| centre_distance | linear | 30.000 | 0.000 | from T06-slotted | 0.7279 | empirical | 0.0488 | 59.7 | D | T06 |
| tooth_thickness_A | linear | 0.000 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 13.2 | A | W1 assumption 3 |
| tooth_thickness_B | linear | 0.000 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 13.2 | A | W1 assumption 3 |
| runout_A | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.7279 | normal | 0.0167 | 7.0 | A | pitch circle vs bore |
| runout_B | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.7279 | normal | 0.0167 | 7.0 | A | pitch circle vs bore |

| Result | Value |
|---|---|
| Nominal | 0.250 |
| Mean-shifted centre | 0.250 |
| Worst case | -0.043 … 0.543 (fail) |
| RSS classic (t = 3σ) | 0.143 … 0.357 |
| RSS distribution-adjusted | 0.112 … 0.388 (pass) |
| MC mean / σ | 0.250 / 0.0460 |
| MC 0.135 % … 99.865 % | 0.116 … 0.384 |
| MC min … max | 0.029 … 0.431 |
| MC out of spec | 0.001 % (± 0.001 % s.e.) |
| Cpk percentile / normal | 1.49 / 1.45 |
| **Verdict (MC)** | **PASS** |
