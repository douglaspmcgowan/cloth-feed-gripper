# T02-tight — Horn pilot recess radial fit (Ø19.2 horn in Ø20.0 recess)

Variant of `T02`: recess CAD 19.55

- Requirement: Recess slides onto the horn by hand (clearance >= 0.02) and float stays small enough to centre the gripper (<= 0.30).
- Spec: LSL 0.020, USL 0.300 mm diametral clearance
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T02_pilot_recess_fit.yaml`; seed 20260922

so101.md row 12 states 0.4 mm diametral clearance; 20.0 - 19.2 = 0.8 diametral (0.4 radial). The recess is only 1.0 mm (5 layers) deep, so first-layer squish affects all of it when the mount face prints on the bed.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| recess_d_printed | linear | 19.550 | -0.150 | -0.100 / +0.100 | 1.0000 | normal | 0.0333 | 23.5 | A | CAD (so101.md) + large-hole bias [A] |
| first_layer_residual | linear | 0.000 | 0.000 | -0.100 / +0.100 | 1.0000 | uniform | 0.0577 | 70.6 | A | Prusa KB elephant-foot compensation (via W1) |
| horn_od | linear | 19.200 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 5.9 | A | so101.md row 2 nominal [D]; tol [A] |

| Result | Value |
|---|---|
| Nominal | 0.350 |
| Mean-shifted centre | 0.200 |
| Worst case | -0.050 … 0.450 (fail) |
| RSS classic (t = 3σ) | 0.050 … 0.350 |
| RSS distribution-adjusted | -0.006 … 0.406 (fail) |
| MC mean / σ | 0.200 / 0.0687 |
| MC 0.135 % … 99.865 % | 0.022 … 0.376 |
| MC min … max | -0.034 … 0.420 |
| MC out of spec | 7.4 % (± 0.083 % s.e.) |
| Cpk percentile / normal | 0.57 / 0.49 |
| **Verdict (MC)** | **FAIL** |

![T02-tight histogram](../../../../docs/gripper/figures/tol_T02-tight.png)
