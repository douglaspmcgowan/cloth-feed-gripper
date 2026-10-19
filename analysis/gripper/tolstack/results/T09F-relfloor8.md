# T09F-relfloor8 — Pad force at the jaw floor with the FSR trip failed (position-only cap, R15)

Variant of `T09F` (option): firmware: floor = calibrated contact - 4.9 deg (config.h JAW_FLOOR_BELOW_C0_DEG), against the ruled 8 N cap

- Requirement: R15 ruled 8 N (Douglas 2026-10-12, DESIGN-BASIS R15): pad force <= 8 N even if the FSR trip fails.
- Spec: USL 8.000 N (pad force with the jaw at JAW_MIN_DEG -7.4)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: expression; source file `T09F_force_at_floor.yaml`; seed 20260922

F = k_pair * 2 r_c * (theta_c - theta), finger.md 6.2 linear model. theta_c is the T09 first-contact angle (same samples); the floor is absolute, so the uncalibrated spread of theta_c moves the force at the floor. Reading used: the servo position errors at contact and at the floor are independent (deadband and gear play settle afresh at each stop), so the floor error has its own sample key (shared: servo_angle_error_at_floor) and T09's contact error stays inside theta_c. With one common bias instead (contact error cancelled explicitly) the stack is still FAIL (third review, B1: Cpk 0.95 against 0.90 here); the shared T09 key used before cancelled the floor error sample for sample and made the stack read MARGINAL.

Var % from Monte Carlo freeze-one (non-linear model); Sens. is a central difference at the mids and does not rank contributors. Worst case is taken over the corners only, so a minimum inside the box (the kink of abs()) can be missed.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| k_pair | linear | 0.572 | 0.000 | -0.049 / +0.049 | 11.1177 | uniform | 0.0283 | 60.6 | D | finger.md 6.2, E 56-67 MPa |
| servo_angle_error | linear | 0.000 | 0.000 | -0.500 / +0.500 | -1.2978 | normal | 0.1667 | 28.9 | A | position error at the floor (independent of the T09 contact error) |
| cal_repeat | linear | 0.000 | 0.000 | -0.300 / +0.300 | 1.2978 | normal | 0.1000 | 10.5 | A | calibrated contact repeatability |

| Result | Value |
|---|---|
| Nominal | 6.359 |
| Mean-shifted centre | 6.359 |
| Worst case | 4.865 … 8.031 (fail) |
| RSS classic (t = 3σ) | 5.427 … 7.292 |
| RSS distribution-adjusted | 5.150 … 7.569 (pass) |
| MC mean / σ | 6.360 / 0.4035 |
| MC 0.135 % … 99.865 % | 5.307 … 7.480 |
| MC min … max | 4.971 … 7.904 |
| MC out of spec | <30 ppm (0 of 100,000 samples; 95% upper bound) |
| Cpk percentile / normal | 1.46 ± 0.00 / 1.35 ± 0.00 |
| Yield (MC) | 100.000 % (<30 ppm (0 of 100,000 samples; 95% upper bound) out) |
| Dominant contributor | k_pair (61 %) |
| Pass/fail by the declared method (MC) | PASS |
| **Verdict (pass / marginal / fail)** | **PASS** |

![T09F-relfloor8 histogram](figures/tol_T09F-relfloor8.png)
