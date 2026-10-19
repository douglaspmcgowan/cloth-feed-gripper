# T07-bushed — Gear backlash jt (circumferential)

Variant of `T07`: fix-9 layout (T06-bushed)

- Requirement: jt between 0.05 (no binding) and 0.45 (open-jaw repeatability), design jt0 = 0.25 by flank offset.
- Spec: LSL 0.050, USL 0.450 mm circumferential backlash
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T07_backlash.yaml`; seed 20260922

jt = jt0 + 2 tan(alpha) (a - a0) - ds_A - ds_B, plus pitch-circle runout of each gear (KHK Table 4.1 via W1).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| centre_distance | linear | 24.000 | 0.000 | from T06-bushed | 0.7279 | empirical | 0.0129 | 9.5 | D | T06 |
| tooth_thickness_A | linear | 0.000 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 29.6 | A | W1 assumption 3 |
| tooth_thickness_B | linear | 0.000 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 29.6 | A | W1 assumption 3 |
| runout_A | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.7279 | normal | 0.0167 | 15.7 | A | pitch circle vs bore |
| runout_B | linear | 0.000 | 0.000 | -0.050 / +0.050 | 0.7279 | normal | 0.0167 | 15.7 | A | pitch circle vs bore |

| Result | Value |
|---|---|
| Nominal | 0.250 |
| Mean-shifted centre | 0.250 |
| Worst case | 0.041 … 0.459 (fail) |
| RSS classic (t = 3σ) | 0.159 … 0.341 |
| RSS distribution-adjusted | 0.158 … 0.342 (pass) |
| MC mean / σ | 0.250 / 0.0307 |
| MC 0.135 % … 99.865 % | 0.158 … 0.343 |
| MC min … max | 0.112 … 0.387 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 2.15 / 2.17 |
| **Verdict (MC)** | **PASS** |

![T07-bushed histogram](../../../../docs/gripper/figures/tol_T07-bushed.png)
