# T10-pegs — Finger pad parallelism in the closing plane (root gap at tip contact)

Variant of `T10`: 2 locating pegs per finger (float 0.05) + closed_gap 0

- Requirement: Root gap at tip contact within +/-1.0 mm over the 45 mm pad (pad_len = L_tip - L_root).
- Spec: LSL -1.000, USL 1.000 mm root gap when the tips first touch (> 0 = V open toward the root)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T10_pad_parallelism.yaml`; seed 20260922

Rotation errors (servo angle, backlash) cancel at tip contact; only translation errors g scale by (1 - L_root/L_tip), plus pad face tilt and root-plate angle. The finger's screw float on its root plate is X-Z translation plus twist about Y (the clamped -Y face stops rotation in the closing plane), so it enters as an X translation.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| closed_gap_design | linear | 0.000 | 0.000 | -0.000 / +0.000 | 0.6429 | normal | 0.0000 | 0.0 | S | params.json |
| centre_distance | linear | 30.000 | 0.000 | from T06 | 0.6429 | empirical | 0.1135 | 12.0 | D | T06 |
| xf_A | linear | 0.000 | 0.000 | -0.100 / +0.100 | -0.6429 | normal | 0.0333 | 1.0 | A |  |
| xf_B | linear | 0.000 | 0.000 | -0.100 / +0.100 | -0.6429 | normal | 0.0333 | 1.0 | A |  |
| pad_A_tilt | linear | 0.000 | 0.000 | -0.300 / +0.300 | 1.0000 | normal | 0.1000 | 22.6 | A | profile zone used as tilt over the pad |
| pad_B_tilt | linear | 0.000 | 0.000 | -0.300 / +0.300 | 1.0000 | normal | 0.1000 | 22.6 | A |  |
| finger_A_root_float | radial (X proj.) | 0.000 | 0.000 | -0.050 / +0.050 | -0.6429 | disk | 0.0250 | 0.6 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame |
| finger_B_root_float | radial (X proj.) | 0.000 | 0.000 | -0.050 / +0.050 | 0.6429 | disk | 0.0250 | 0.6 | D | finger on root plate -Y face, 2x M3 along Y (README, W1 S6): X component of its X-Z float disk, gripper frame |
| root_plate_A_angle | linear | 0.000 | 0.000 | -0.281 / +0.281 | 1.0000 | normal | 0.0938 | 19.8 | A |  |
| root_plate_B_angle | linear | 0.000 | 0.000 | -0.281 / +0.281 | 1.0000 | normal | 0.0938 | 19.8 | A |  |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -1.715 … 1.715 (fail) |
| RSS classic (t = 3σ) | -0.615 … 0.615 |
| RSS distribution-adjusted | -0.632 … 0.632 (pass) |
| MC mean / σ | 0.000 / 0.2106 |
| MC 0.135 % … 99.865 % | -0.638 … 0.635 |
| MC min … max | -0.947 … 0.894 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 1.57 / 1.58 |
| **Verdict (MC)** | **PASS** |
