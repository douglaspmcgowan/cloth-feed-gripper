# T11-r15band — Radial keep-out, r <= 12 hub band (z 0..+1) vs wrist-link lip

Variant of `T11`: r <= 15 band (z +2..+5.3), not a first layer

- Requirement: Rolling hub clears the stationary lip by >= 0.1 mm at every roll angle.
- Spec: LSL 0.100 mm radial clearance, worst angle over 320 deg roll
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T11_keepout_radial.yaml`; seed 20260922

Roll sweeps every angle, so hub offset (T04) and lip eccentricity add as magnitudes.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| lip_radius | linear | 15.400 | 0.000 | -0.200 / +0.200 | 1.0000 | normal | 0.0667 | 29.1 | D | so101.md keep-out table [D]; tol [A] |
| hub_radius | linear | 15.000 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 1.8 | A | hub printed face-down: first-layer flare |
| hub_offset | linear | 0.000 | 0.000 | from T04 | -1.0000 | empirical | 0.0849 | 47.2 | D | T04 radial |
| lip_eccentricity | linear | 0.000 | 0.000 | 0.000 / +0.200 | -1.0000 | uniform | 0.0577 | 21.8 | A |  |

| Result | Value |
|---|---|
| Nominal | 0.400 |
| Mean-shifted centre | 0.025 |
| Worst case | -0.600 … 0.650 (fail) |
| RSS classic (t = 3σ) | -0.298 … 0.348 |
| RSS distribution-adjusted | -0.346 … 0.396 (fail) |
| MC mean / σ | 0.079 / 0.1238 |
| MC 0.135 % … 99.865 % | -0.271 … 0.438 |
| MC min … max | -0.441 … 0.561 |
| MC out of spec | 57 % (± 0.16 % s.e.) |
| Cpk percentile / normal | -0.07 / -0.06 |
| **Verdict (MC)** | **FAIL** |

![T11-r15band histogram](../../../../docs/gripper/figures/tol_T11-r15band.png)
