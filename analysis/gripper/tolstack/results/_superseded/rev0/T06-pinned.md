# T06-pinned — Gear centre distance a (servo shaft A to idler pin B)

Variant of `T06`: both knuckles on pins pressed into the plates; servo drives A through a floating dog coupling

- Requirement: a stays inside the band that keeps backlash between jt_min and jt_max for the design jt0 (T07).
- Spec: LSL 23.725, USL 24.275 mm
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T06_gear_center_distance.yaml`; seed 20260922

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| pin_float | linear | 0.000 | 0.000 | -0.035 / +0.035 | 1.0000 | uniform | 0.0202 | 21.2 | D | knuckle B reamed 3.075 bore on the m6 pin (pin pressed into the plates: no plate float) |
| pinA_to_pinB_holes | linear | 0.000 | 0.000 | -0.100 / +0.100 | 1.0000 | normal | 0.0333 | 57.6 | A | pin A and pin B holes on one print, 24 mm apart |
| pinA_float | linear | 0.000 | 0.000 | -0.035 / +0.035 | -1.0000 | uniform | 0.0202 | 21.2 | D | knuckle A reamed bore on its pin |

| Result | Value |
|---|---|
| Nominal | 24.000 |
| Mean-shifted centre | 24.000 |
| Worst case | 23.830 … 24.170 (pass) |
| RSS classic (t = 3σ) | 23.888 … 24.112 |
| RSS distribution-adjusted | 23.868 … 24.132 (pass) |
| MC mean / σ | 24.000 / 0.0440 |
| MC 0.135 % … 99.865 % | 23.873 … 24.131 |
| MC min … max | 23.813 … 24.169 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 2.10 / 2.08 |
| **Verdict (MC)** | **PASS** |

![T06-pinned histogram](../../../../docs/gripper/figures/tol_T06-pinned.png)
