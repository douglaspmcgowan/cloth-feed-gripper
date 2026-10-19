# T09P-trip55 — Peak pad force when the FSR over-force trip fires (R15)

Variant of `T09P` (scenario): firmware: F_TRIP_N 5.5, F_TRIP_MS 10, against the ruled 8 N cap

- Requirement: R15 ruled 8 N (Douglas 2026-10-12, DESIGN-BASIS R15): pad force <= 8 N.
- Spec: USL 8.000 N (largest true pad force before the trip opens the jaw)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: expression; source file `T09P_force_at_trip.yaml`; seed 20260922

The trip fires when the FSR reads F_TRIP_N (7.75 N) for 20 ms. The true force is the reading divided by (1 + FSR error), and the jaw keeps squeezing at up to 60 deg/s through the 20 ms hold plus the 9.5 ms filter lag, adding up to k_pair * 2 r_c * radians(60 * 0.0295) = 2.5 N on the stiff finger. The base stack ignores the jaw floor.

Var % from Monte Carlo freeze-one (non-linear model); Sens. is a central difference at the mids and does not rank contributors. Worst case is taken over the corners only, so a minimum inside the box (the kink of abs()) can be missed.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| F_trip | linear | 5.500 | 0.000 | -0.000 / +0.000 | 1.0000 | normal | 0.0000 | 0.0 | D | config.h F_TRIP_N |
| fsr_error | linear | 0.000 | 0.000 | -0.100 / +0.100 | -5.5000 | normal | 0.0333 | 14.7 | A | FSR error after span calibration |
| k_pair | linear | 0.572 | 0.000 | -0.049 / +0.049 | 1.3273 | uniform | 0.0283 | 0.7 | D | finger.md 6.2 |
| squeeze_deg | linear | 0.585 | 0.000 | -0.585 / +0.585 | 1.2978 | uniform | 0.3377 | 84.5 | D | 60 deg/s for 20 ms + 9.5 ms (config.h) |

| Result | Value |
|---|---|
| Nominal | 6.259 |
| Mean-shifted centre | 6.259 |
| Worst case | 5.000 … 7.760 (pass) |
| RSS classic (t = 3σ) | 5.319 … 7.199 |
| RSS distribution-adjusted | 5.000 … 7.689 † (pass); clipped to WC, unclipped 4.829 … 7.689 |
| MC mean / σ | 6.266 / 0.4771 |
| MC 0.135 % … 99.865 % | 5.182 … 7.439 |
| MC min … max | 4.903 … 7.831 |
| MC out of spec | <30 ppm (0 of 100,000 samples; 95% upper bound) |
| Cpk percentile / normal | 1.48 ± 0.01 / 1.21 ± 0.00 |
| Yield (MC) | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) |
| Dominant contributor | squeeze_deg (85 %) |
| Pass/fail by the declared method (MC) | PASS |
| **Verdict (pass / marginal / fail)** | **PASS** |

![T09P-trip55 histogram](figures/tol_T09P-trip55.png)
