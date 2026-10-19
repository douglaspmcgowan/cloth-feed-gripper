# T07-pinned — Gear backlash jt (circumferential)

Variant of `T07`: both knuckles on pressed pins (T06-pinned)

- Requirement: jt between 0.05 (no binding) and 0.45 (open-jaw repeatability), design jt0 = 0.25 by flank offset.
- Spec: LSL 0.050, USL 0.450 mm circumferential backlash
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T07_backlash.yaml`; seed 20260922

jt = jt0 + 2 tan(alpha) (a - a0) - ds_A - ds_B, plus pitch-circle runout of each gear (KHK Table 4.1 via W1).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| centre_distance | linear | 30.000 | 0.000 | from T06-pinned | 0.7279 | empirical | 0.0440 | 54.7 | D | T06 |
| tooth_thickness_A | linear | 0.000 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 14.8 | A | W1 assumption 3 |
| tooth_thickness_B | linear | 0.000 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 14.8 | A | W1 assumption 3 |
| runout_A | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.7279 | normal | 0.0167 | 7.8 | A | pitch circle vs bore |
| runout_B | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.7279 | normal | 0.0167 | 7.8 | A | pitch circle vs bore |

| Result | Value |
|---|---|
| Nominal | 0.250 |
| Mean-shifted centre | 0.250 |
| Worst case | -0.047 … 0.547 (fail) |
| RSS classic (t = 3σ) | 0.131 … 0.369 |
| RSS distribution-adjusted | 0.120 … 0.380 (pass) |
| MC mean / σ | 0.250 / 0.0434 |
| MC 0.135 % … 99.865 % | 0.120 … 0.381 |
| MC min … max | 0.071 … 0.433 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 1.52 / 1.53 |
| **Verdict (MC)** | **PASS** |
