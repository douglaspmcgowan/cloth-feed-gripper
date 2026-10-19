# T16-shaftA — Axis tilt between plates, centre-distance change across the gear face

Variant of `T16`: line-reamed + bronze sleeve in knuckle B (clearance 0.02, bore 7.7); servo shaft still carries A

- Requirement: Centre distance varies <= 0.07 mm across the 6 mm face (axes A and B parallel in the plane of centres).
- Spec: LSL -0.070, USL 0.070 mm (a at front face - a at back face)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T16_pin_tilt.yaml`; seed 20260922

Fit ruling: pin B is pressed into both plates (no float in the plate holes); knuckle B runs on the pin in its reamed bore, so it can cock by pin_clear / bore length. Axis A is the servo output shaft: it wobbles in the servo's own bearings and tilts with the servo flange seat. Every term is the change of a across face_b.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| mid_plate_hole_B | linear | 0.000 | 0.000 | -0.030 / +0.030 | -0.6000 | normal | 0.0100 | 1.8 | A | printed hole position, same print |
| front_plate_hole_B | linear | 0.000 | 0.000 | -0.030 / +0.030 | 0.6000 | normal | 0.0100 | 1.8 | A |  |
| knuckleB_tilt_on_pin | linear | 0.000 | 0.000 | -0.016 / +0.016 | 1.0000 | uniform | 0.0090 | 4.0 | D | reamed knuckle bore clearance over the bore length |
| shaftA_tilt | linear | 0.000 | 0.000 | -0.075 / +0.075 | -1.0000 | uniform | 0.0433 | 91.7 | A | 2 x per-bearing radial play / bearing span (basis servo_shaft_tilt) |
| servo_tilt_on_flange_seat | linear | 0.000 | 0.000 | -0.012 / +0.012 | -1.0000 | normal | 0.0041 | 0.8 | A | flange seat flatness over the ear-hole span |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -0.139 … 0.139 (fail) |
| RSS classic (t = 3σ) | -0.082 … 0.082 |
| RSS distribution-adjusted | -0.136 … 0.136 (fail) |
| MC mean / σ | 0.000 / 0.0452 |
| MC 0.135 % … 99.865 % | -0.097 … 0.098 |
| MC min … max | -0.116 … 0.114 |
| MC out of spec | 10.8 % (± 0.098 % s.e.) |
| Cpk percentile / normal | 0.72 / 0.52 |
| **Verdict (MC)** | **FAIL** |

![T16-shaftA histogram](../../../../docs/gripper/figures/tol_T16-shaftA.png)
