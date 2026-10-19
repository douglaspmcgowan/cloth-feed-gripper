# T16-pinned — Axis tilt between plates, centre-distance change across the gear face

Variant of `T16`: line-reamed + knuckle A on its own pressed pin, servo drives it through a floating dog coupling

- Requirement: Centre distance varies <= 0.07 mm across the 6 mm face (axes A and B parallel in the plane of centres).
- Spec: LSL -0.070, USL 0.070 mm (a at front face - a at back face)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T16_pin_tilt.yaml`; seed 20260922

Fit ruling: pin B is pressed into both plates (no float in the plate holes); knuckle B runs on the pin in its reamed bore, so it can cock by pin_clear / bore length. Axis A is the servo output shaft: it wobbles in the servo's own bearings and tilts with the servo flange seat. Every term is the change of a across face_b.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| mid_plate_hole_B | linear | 0.000 | 0.000 | -0.030 / +0.030 | -0.6000 | normal | 0.0100 | 1.1 | A | printed hole position, same print |
| front_plate_hole_B | linear | 0.000 | 0.000 | -0.030 / +0.030 | 0.6000 | normal | 0.0100 | 1.1 | A |  |
| knuckleB_tilt_on_pin | linear | 0.000 | 0.000 | -0.070 / +0.070 | 1.0000 | uniform | 0.0404 | 47.9 | D | reamed knuckle bore clearance over the bore length |
| mid_plate_hole_A | linear | 0.000 | 0.000 | -0.030 / +0.030 | 0.6000 | normal | 0.0100 | 1.1 | A | line-reamed with B |
| front_plate_hole_A | linear | 0.000 | 0.000 | -0.030 / +0.030 | -0.6000 | normal | 0.0100 | 1.1 | A |  |
| knuckleA_tilt_on_pin | linear | 0.000 | 0.000 | -0.070 / +0.070 | -1.0000 | uniform | 0.0404 | 47.9 | D | reamed knuckle A bore |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -0.212 … 0.212 (fail) |
| RSS classic (t = 3σ) | -0.105 … 0.105 |
| RSS distribution-adjusted | -0.175 … 0.175 (fail) |
| MC mean / σ | -0.000 / 0.0584 |
| MC 0.135 % … 99.865 % | -0.142 … 0.142 |
| MC min … max | -0.174 … 0.163 |
| MC out of spec | 25.7 % (± 0.14 % s.e.) |
| Cpk percentile / normal | 0.49 / 0.40 |
| **Verdict (MC)** | **FAIL** |

![T16-pinned histogram](../../../../docs/gripper/figures/tol_T16-pinned.png)
