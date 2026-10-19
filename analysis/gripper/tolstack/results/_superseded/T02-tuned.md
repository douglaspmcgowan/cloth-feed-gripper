# T02-tuned — Horn pilot recess radial fit (Ø19.2 horn in Ø20.0 recess)

Variant of `T02`: recess CAD 19.52 + 0.3x45 mouth chamfer (no first-layer residual)

- Requirement: Recess slides onto the horn by hand (clearance >= 0.02) and float stays small enough to centre the gripper (<= 0.30).
- Spec: LSL 0.020, USL 0.300 mm diametral clearance
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T02_pilot_recess_fit.yaml`; seed 20260922

so101.md row 12 states 0.4 mm diametral clearance; 20.0 - 19.2 = 0.8 diametral (0.4 radial). The recess is only 1.0 mm (5 layers) deep, so first-layer squish affects all of it when the mount face prints on the bed.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| recess_d_printed | linear | 19.520 | -0.150 | -0.100 / +0.100 | 1.0000 | normal | 0.0333 | 80.0 | A | CAD (so101.md) + large-hole bias [A] |
| first_layer_residual | linear | 0.000 | 0.000 | -0.000 / +0.000 | 1.0000 | uniform | 0.0000 | 0.0 | A | Prusa KB elephant-foot compensation (via W1) |
| horn_od | linear | 19.200 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 20.0 | A | so101.md row 2 nominal [D]; tol [A] |

| Result | Value |
|---|---|
| Nominal | 0.320 |
| Mean-shifted centre | 0.170 |
| Worst case | 0.020 … 0.320 (fail) |
| RSS classic (t = 3σ) | 0.058 … 0.282 |
| RSS distribution-adjusted | 0.058 … 0.282 (pass) |
| MC mean / σ | 0.170 / 0.0374 |
| MC 0.135 % … 99.865 % | 0.059 … 0.282 |
| MC min … max | 0.007 … 0.329 |
| MC out of spec | 0.03 % (± 0.0055 % s.e.) |
| Cpk percentile / normal | 1.16 / 1.16 |
| **Verdict (MC)** | **FAIL** |

![T02-tuned histogram](../../../../docs/gripper/figures/tol_T02-tuned.png)
