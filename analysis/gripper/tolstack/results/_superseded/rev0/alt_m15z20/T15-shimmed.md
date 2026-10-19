# T15-shimmed — Standoff length / plate parallelism, knuckle B end play at pin B

Variant of `T15`: 1.7 mm of hub bosses/spacers (end play 0.3)

- Requirement: Knuckle B turns freely (>= 0.05) with <= 0.5 axial float.
- Spec: LSL 0.050, USL 0.500 mm axial end play
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T15_standoff_endplay.yaml`; seed 20260922

Plate gap at pin B (x = 12) interpolates between standoffs at x = -27 and +27, so a length mismatch tilts the front plate.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| standoff_L1_x_neg | linear | 8.000 | 0.000 | -0.100 / +0.100 | 0.2683 | uniform | 0.0577 | 3.9 | D | README geometry |
| standoff_L2_x_pos | linear | 8.000 | 0.000 | -0.100 / +0.100 | 0.7317 | uniform | 0.0577 | 28.8 | D |  |
| mid_plate_flatness | linear | 0.000 | 0.000 | -0.050 / +0.050 | 1.0000 | normal | 0.0167 | 4.5 | A |  |
| front_plate_flatness | linear | 0.000 | 0.000 | -0.050 / +0.050 | 1.0000 | normal | 0.0167 | 4.5 | A |  |
| knuckle_B_hub | linear | 6.000 | 0.000 | -0.100 / +0.100 | -1.0000 | uniform | 0.0577 | 53.8 | D | hub = face width |
| spacers | linear | 1.700 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 4.5 | A |  |

| Result | Value |
|---|---|
| Nominal | 0.300 |
| Mean-shifted centre | 0.300 |
| Worst case | -0.050 … 0.650 (fail) |
| RSS classic (t = 3σ) | 0.146 … 0.454 |
| RSS distribution-adjusted | 0.064 … 0.536 (fail) |
| MC mean / σ | 0.300 / 0.0787 |
| MC 0.135 % … 99.865 % | 0.093 … 0.503 |
| MC min … max | 0.014 … 0.556 |
| MC out of spec | 0.176 % (± 0.013 % s.e.) |
| Cpk percentile / normal | 0.99 / 0.85 |
| **Verdict (MC)** | **FAIL** |
