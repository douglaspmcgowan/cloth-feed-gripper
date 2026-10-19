# T12-widen50 — Axial keep-out, gripper widens above the wrist-link lip top

Variant of `T12`: widen at 5.0 above H

- Requirement: Any part wider than r 15 starts >= 0.1 mm above the lip top (z +5.3).
- Spec: LSL 0.100 mm (z where the part widens past r 15) - (lip top z)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T12_keepout_axial.yaml`; seed 20260922

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| widen_height_above_H | linear | 5.000 | 0.000 | -0.100 / +0.100 | 1.0000 | uniform | 0.0577 | 23.5 | D | so101.md rule 4.5 above H |
| datum_A_flatness_lift | linear | 0.000 | 0.000 | 0.000 / +0.200 | 1.0000 | uniform | 0.0577 | 23.5 | A | raises the part |
| lip_top_above_H | linear | 4.300 | 0.000 | -0.100 / +0.100 | -1.0000 | normal | 0.0333 | 7.8 | D | so101.md |
| horn_height | linear | 0.000 | 0.000 | -0.100 / +0.100 | 1.0000 | normal | 0.0333 | 7.8 | A |  |
| servo5_seat | linear | 0.000 | 0.000 | -0.200 / +0.200 | -1.0000 | normal | 0.0667 | 31.4 | A |  |
| servo5_axial_play | linear | 0.000 | 0.000 | -0.050 / +0.050 | 1.0000 | uniform | 0.0289 | 5.9 | A |  |

| Result | Value |
|---|---|
| Nominal | 0.700 |
| Mean-shifted centre | 0.800 |
| Worst case | 0.150 … 1.450 (pass) |
| RSS classic (t = 3σ) | 0.513 … 1.087 |
| RSS distribution-adjusted | 0.443 … 1.157 (pass) |
| MC mean / σ | 0.800 / 0.1190 |
| MC 0.135 % … 99.865 % | 0.459 … 1.140 |
| MC min … max | 0.267 … 1.297 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 2.05 / 1.96 |
| **Verdict (MC)** | **PASS** |

![T12-widen50 histogram](../../../../docs/gripper/figures/tol_T12-widen50.png)
