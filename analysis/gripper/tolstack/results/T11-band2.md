# T11-band2 — Radial keep-out, r 11.6 hub band (H-1..H+1) vs wrist-link lip r 12.6

Variant of `T11` (scenario): second band: hub r 14.6 (H+1..H+5.0) vs lip r 15.4, not a first layer

- Requirement: Rolling hub clears the stationary lip by >= 0.1 mm at every roll angle.
- Spec: LSL 0.100 mm radial clearance, worst angle over 320 deg roll
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T11_keepout_radial.yaml`; seed 20260922

Roll sweeps every angle, so hub offset (T04) and lip eccentricity add as magnitudes. This band starts on the bed, so it carries first-layer flare.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| lip_radius | linear | 15.400 | 0.000 | -0.200 / +0.200 | 1.0000 | normal | 0.0667 | 48.7 | D | so101.md keep-out table [D]; tol [A] |
| hub_radius | linear | 14.600 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 3.0 | S | params.json hub_r_low 11.6; first-layer flare [A]; XY band / 2 on a radius [S] |
| hub_offset | linear | 0.000 | 0.000 | from T04 | -1.0000 | empirical | 0.0327 | 11.7 | D | T04 radial |
| lip_eccentricity | linear | 0.000 | 0.000 | 0.000 / +0.200 | -1.0000 | uniform | 0.0577 | 36.5 | A |  |

| Result | Value |
|---|---|
| Nominal | 0.800 |
| Mean-shifted centre | 0.575 |
| Worst case | 0.100 … 1.050 (pass) |
| RSS classic (t = 3σ) | 0.331 … 0.819 |
| RSS distribution-adjusted | 0.288 … 0.862 (pass) |
| MC mean / σ | 0.633 / 0.0955 |
| MC 0.135 % … 99.865 % | 0.353 … 0.906 |
| MC min … max | 0.201 … 0.997 |
| MC out of spec | <30 ppm (0 of 100,000 samples; 95% upper bound) |
| Cpk percentile / normal | 1.90 ± 0.01 / 1.86 ± 0.00 |
| Yield (MC) | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) |
| Dominant contributor | lip_radius (49 %) |
| Pass/fail by the declared method (MC) | PASS |
| **Verdict (pass / marginal / fail)** | **PASS** |

![T11-band2 histogram](figures/tol_T11-band2.png)
