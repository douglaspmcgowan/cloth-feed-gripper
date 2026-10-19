# T16-bushed — Axis tilt between plates, centre-distance change across the gear face

Variant of `T16`: pinned + sintered-bronze sleeve in each knuckle (clearance 0.02), bore length 7.7

- Requirement: Centre distance varies <= 0.07 mm across the 6 mm face (axes A and B parallel in the plane of centres).
- Spec: LSL -0.070, USL 0.070 mm (a at front face - a at back face)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T16_pin_tilt.yaml`; seed 20260922

Fit ruling: pin B is pressed into both plates (no float in the plate holes); knuckle B runs on the pin in its reamed bore, so it can cock by pin_clear / bore length. Axis A is the servo output shaft: it wobbles in the servo's own bearings and tilts with the servo flange seat. Every term is the change of a across face_b.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| mid_plate_hole_B | linear | 0.000 | 0.000 | -0.030 / +0.030 | -0.6000 | normal | 0.0100 | 11.8 | A | printed hole position, same print |
| front_plate_hole_B | linear | 0.000 | 0.000 | -0.030 / +0.030 | 0.6000 | normal | 0.0100 | 11.8 | A |  |
| knuckleB_tilt_on_pin | linear | 0.000 | 0.000 | -0.016 / +0.016 | 1.0000 | uniform | 0.0090 | 26.5 | D | reamed knuckle bore clearance over the bore length |
| mid_plate_hole_A | linear | 0.000 | 0.000 | -0.030 / +0.030 | 0.6000 | normal | 0.0100 | 11.8 | A | line-reamed with B |
| front_plate_hole_A | linear | 0.000 | 0.000 | -0.030 / +0.030 | -0.6000 | normal | 0.0100 | 11.8 | A |  |
| knuckleA_tilt_on_pin | linear | 0.000 | 0.000 | -0.016 / +0.016 | -1.0000 | uniform | 0.0090 | 26.5 | D | bushed knuckle A |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -0.103 … 0.103 (fail) |
| RSS classic (t = 3σ) | -0.042 … 0.042 |
| RSS distribution-adjusted | -0.052 … 0.052 (pass) |
| MC mean / σ | -0.000 / 0.0174 |
| MC 0.135 % … 99.865 % | -0.050 … 0.050 |
| MC min … max | -0.068 … 0.072 |
| MC out of spec | 0.001 % (± 0.001 % s.e.) |
| Cpk percentile / normal | 1.40 / 1.34 |
| **Verdict (MC)** | **PASS** |
