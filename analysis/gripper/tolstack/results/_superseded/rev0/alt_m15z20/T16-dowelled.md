# T16-dowelled — Axis tilt between plates, centre-distance change across the gear face

Variant of `T16`: front plate located on pin B + pivot stub (no screw float)

- Requirement: Centre distance varies <= 0.07 mm across the 6 mm face (axes A and B parallel in the plane of centres).
- Spec: LSL -0.070, USL 0.070 mm (a at front face - a at back face)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T16_pin_tilt.yaml`; seed 20260922

Fit ruling: pin B is pressed into both plates (no float in the plate holes); knuckle B runs on the pin in its reamed bore, so it can cock by pin_clear / bore length. Axis A is the servo output shaft: it wobbles in the servo's own bearings and tilts with the servo flange seat. Every term is the change of a across face_b.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| mid_plate_hole_B | linear | 0.000 | 0.000 | -0.100 / +0.100 | -0.6000 | normal | 0.0333 | 9.2 | A | printed hole position, same print |
| front_plate_hole_B | linear | 0.000 | 0.000 | -0.100 / +0.100 | 0.6000 | normal | 0.0333 | 9.2 | A |  |
| knuckleB_tilt_on_pin | linear | 0.000 | 0.000 | -0.070 / +0.070 | 1.0000 | uniform | 0.0404 | 37.8 | D | reamed knuckle bore clearance over the bore length |
| shaftA_tilt | linear | 0.000 | 0.000 | -0.075 / +0.075 | -1.0000 | uniform | 0.0433 | 43.4 | A | 2 x per-bearing radial play / bearing span (basis servo_shaft_tilt) |
| servo_tilt_on_flange_seat | linear | 0.000 | 0.000 | -0.012 / +0.012 | -1.0000 | normal | 0.0041 | 0.4 | A | flange seat flatness over the ear-hole span |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -0.277 … 0.277 (fail) |
| RSS classic (t = 3σ) | -0.134 … 0.134 |
| RSS distribution-adjusted | -0.197 … 0.197 (fail) |
| MC mean / σ | -0.000 / 0.0657 |
| MC 0.135 % … 99.865 % | -0.176 … 0.175 |
| MC min … max | -0.229 … 0.227 |
| MC out of spec | 30.5 % (± 0.15 % s.e.) |
| Cpk percentile / normal | 0.40 / 0.35 |
| **Verdict (MC)** | **FAIL** |
