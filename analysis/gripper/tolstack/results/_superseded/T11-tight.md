# T11-tight — Radial keep-out, r <= 12 hub band (z 0..+1) vs wrist-link lip

Variant of `T11`: r12 band with recess CAD 19.55

- Requirement: Rolling hub clears the stationary lip by >= 0.1 mm at every roll angle.
- Spec: LSL 0.100 mm radial clearance, worst angle over 320 deg roll
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T11_keepout_radial.yaml`; seed 20260922

Roll sweeps every angle, so hub offset (T04) and lip eccentricity add as magnitudes.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| lip_radius | linear | 12.600 | 0.000 | -0.200 / +0.200 | 1.0000 | normal | 0.0667 | 47.6 | D | so101.md keep-out table [D]; tol [A] |
| hub_radius | linear | 12.000 | 0.100 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 3.0 | A | hub printed face-down: first-layer flare |
| hub_offset | linear | 0.000 | 0.000 | from T04-tight | -1.0000 | empirical | 0.0359 | 13.8 | D | T04 radial |
| lip_eccentricity | linear | 0.000 | 0.000 | 0.000 / +0.200 | -1.0000 | uniform | 0.0577 | 35.7 | A |  |

| Result | Value |
|---|---|
| Nominal | 0.600 |
| Mean-shifted centre | 0.300 |
| Worst case | -0.150 … 0.750 (fail) |
| RSS classic (t = 3σ) | 0.063 … 0.537 |
| RSS distribution-adjusted | 0.010 … 0.590 (fail) |
| MC mean / σ | 0.321 / 0.0964 |
| MC 0.135 % … 99.865 % | 0.042 … 0.596 |
| MC min … max | -0.086 … 0.695 |
| MC out of spec | 0.978 % (± 0.031 % s.e.) |
| Cpk percentile / normal | 0.79 / 0.76 |
| **Verdict (MC)** | **FAIL** |

![T11-tight histogram](../../../../docs/gripper/figures/tol_T11-tight.png)
