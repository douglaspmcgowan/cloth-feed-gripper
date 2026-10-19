# T09H-relfloor — Largest hold force the firmware can reach on the softest finger (R14 under the R15 cap)

Variant of `T09H` (option): firmware round 2: floor = calibrated contact - 6.2 deg, so the squeeze is limited by u_max alone

- Requirement: The controller can reach the 5 N hold force (R14) on every finger within its squeeze cap. The squeeze cap stays sized for F_CAP_N 10 (9.5 N basis, config.h) under the ruled 8 N R15, which the floor and the trip hold (T09F, T09P); a cap sized for 8 N is T09H-r15p8.
- Spec: LSL 5.000 N (pad force at the firmware squeeze cap or the jaw floor, whichever comes first)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: expression; source file `T09H_hold_force_reach.yaml`; seed 20260922

The firmware limits the squeeze past the calibrated contact to u_max (4.867 deg for a 10 N cap) and never goes below the absolute floor. F = k_pair * 2 r_c * radians(min(u_max, theta_c - floor)).

Var % from Monte Carlo freeze-one (non-linear model); Sens. is a central difference at the mids and does not rank contributors. Worst case is taken over the corners only, so a minimum inside the box (the kink of abs()) can be missed.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| k_pair | linear | 0.572 | 0.000 | -0.049 / +0.049 | 11.0429 | uniform | 0.0283 | 60.6 | D | finger.md 6.2 |
| u_max | linear | 4.867 | 0.000 | -0.000 / +0.000 | 1.2978 | normal | 0.0000 | 0.0 | D | firmware squeeze cap at F_CAP 10 N |
| cal_repeat | linear | 0.000 | 0.000 | -0.300 / +0.300 | 1.2978 | normal | 0.1000 | 10.4 | A | calibrated contact repeatability (same term as T09F-relfloor) |
| servo_angle_error | linear | 0.000 | 0.000 | -0.500 / +0.500 | 1.2978 | normal | 0.1667 | 29.0 | A | position error at the squeeze point |

| Result | Value |
|---|---|
| Nominal | 6.317 |
| Mean-shifted centre | 6.317 |
| Worst case | 4.826 … 7.985 (fail) |
| RSS classic (t = 3σ) | 5.386 … 7.247 |
| RSS distribution-adjusted | 5.112 … 7.521 (pass) |
| MC mean / σ | 6.317 / 0.4011 |
| MC 0.135 % … 99.865 % | 5.283 … 7.447 |
| MC min … max | 4.928 … 7.907 |
| MC out of spec | <92 ppm (4 of 100,000 samples; 95% upper bound) |
| Cpk percentile / normal | 1.28 ± 0.01 / 1.09 ± 0.00 |
| Yield (MC) | 99.996 % (<92 ppm (4 of 100,000 samples; 95% upper bound) out) |
| Dominant contributor | k_pair (61 %) |
| Pass/fail by the declared method (MC) | FAIL |
| **Verdict (pass / marginal / fail)** | **MARGINAL** |

![T09H-relfloor histogram](figures/tol_T09H-relfloor.png)
