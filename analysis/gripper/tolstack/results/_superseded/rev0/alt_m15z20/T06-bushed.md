# T06-bushed — Gear centre distance a (servo shaft A to idler pin B)

Variant of `T06`: fix-9 layout: pinned + plate holes line-reamed together (+/-0.03) + bronze sleeve in each knuckle (clearance 0.02)

- Requirement: a stays inside the band that keeps backlash between jt_min and jt_max for the design jt0 (T07).
- Spec: LSL 29.725, USL 30.275 mm
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T06_gear_center_distance.yaml`; seed 20260922

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| pin_float | linear | 0.000 | 0.000 | -0.010 / +0.010 | 1.0000 | uniform | 0.0058 | 20.0 | D | knuckle B reamed 3.075 bore on the m6 pin (pin pressed into the plates: no plate float) |
| pinA_to_pinB_holes | linear | 0.000 | 0.000 | -0.030 / +0.030 | 1.0000 | normal | 0.0100 | 60.0 | A | pin A and pin B holes line-reamed together, 24 mm apart |
| pinA_float | linear | 0.000 | 0.000 | -0.010 / +0.010 | -1.0000 | uniform | 0.0058 | 20.0 | A | bronze sleeve in knuckle A on its pin |

| Result | Value |
|---|---|
| Nominal | 30.000 |
| Mean-shifted centre | 30.000 |
| Worst case | 29.950 … 30.050 (pass) |
| RSS classic (t = 3σ) | 29.967 … 30.033 |
| RSS distribution-adjusted | 29.961 … 30.039 (pass) |
| MC mean / σ | 30.000 / 0.0129 |
| MC 0.135 % … 99.865 % | 29.963 … 30.039 |
| MC min … max | 29.945 … 30.050 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 7.12 / 7.08 |
| **Verdict (MC)** | **PASS** |
