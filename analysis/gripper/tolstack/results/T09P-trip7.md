# T09P-trip7 — Peak pad force when the FSR over-force trip fires (R15)

Variant of `T09P` (option): firmware: F_TRIP_N 7.0, F_TRIP_MS 10

- Requirement: R15 ruled 8 N (Douglas 2026-10-12, DESIGN-BASIS R15): pad force <= 8 N.
- Spec: USL 8.000 N (largest true pad force before the trip opens the jaw)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: expression; source file `T09P_force_at_trip.yaml`; seed 20260922

The trip fires when the FSR reads F_TRIP_N (7.75 N) for 20 ms. The true force is the reading divided by (1 + FSR error), and the jaw keeps squeezing at up to 60 deg/s through the 20 ms hold plus the 9.5 ms filter lag, adding up to k_pair * 2 r_c * radians(60 * 0.0295) = 2.5 N on the stiff finger. The base stack ignores the jaw floor.

Var % from Monte Carlo freeze-one (non-linear model); Sens. is a central difference at the mids and does not rank contributors. Worst case is taken over the corners only, so a minimum inside the box (the kink of abs()) can be missed.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| F_trip | linear | 7.000 | 0.000 | -0.000 / +0.000 | 1.0000 | normal | 0.0000 | 0.0 | D | config.h F_TRIP_N |
| fsr_error | linear | 0.000 | 0.000 | -0.100 / +0.100 | -7.0000 | normal | 0.0333 | 21.9 | A | FSR error after span calibration |
| k_pair | linear | 0.572 | 0.000 | -0.049 / +0.049 | 1.3273 | uniform | 0.0283 | 0.7 | D | finger.md 6.2 |
| squeeze_deg | linear | 0.585 | 0.000 | -0.585 / +0.585 | 1.2978 | uniform | 0.3377 | 77.4 | D | 60 deg/s for 20 ms + 9.5 ms (config.h) |

| Result | Value |
|---|---|
| Nominal | 7.759 |
| Mean-shifted centre | 7.759 |
| Worst case | 6.364 … 9.426 (fail) |
| RSS classic (t = 3σ) | 6.725 … 8.794 |
| RSS distribution-adjusted | 6.364 … 9.253 † (fail); clipped to WC, unclipped 6.265 … 9.253 |
| MC mean / σ | 7.767 / 0.4986 |
| MC 0.135 % … 99.865 % | 6.577 … 9.061 |
| MC min … max | 6.240 … 9.527 |
| MC out of spec | 34.6 % |
| Cpk percentile / normal | 0.18 ± 0.00 / 0.16 ± 0.00 |
| Yield (MC) | 65.44 % |
| Dominant contributor | squeeze_deg (77 %) |
| Pass/fail by the declared method (MC) | FAIL |
| **Verdict (pass / marginal / fail)** | **FAIL** |

![T09P-trip7 histogram](figures/tol_T09P-trip7.png)
