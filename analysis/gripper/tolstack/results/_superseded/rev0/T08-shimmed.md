# T08-shimmed — Gear mesh axial alignment (gear A vs gear B mid-planes, Z)

Variant of `T08`: end play shimmed to 0.3 (T15-shimmed)

- Requirement: Face mid-planes within +/-0.6 mm (10 % of the 6 mm face width).
- Spec: LSL -0.600, USL 0.600 mm (z_mid A - z_mid B)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T08_mesh_axial.yaml`; seed 20260922

Servo flange seats on the back of the mid plate; knuckle B sits on the mid plate front face through a spacer.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| mid_plate_thickness | linear | 2.500 | 0.000 | -0.100 / +0.100 | -1.0000 | uniform | 0.0577 | 20.3 | A | params.json 2.5 [S]; tol [A] |
| flange_to_horn_face | linear | 3.500 | 0.000 | -0.150 / +0.150 | 1.0000 | normal | 0.0500 | 15.3 | A | chosen servo |
| servo_axial_play | linear | 0.000 | 0.000 | -0.050 / +0.050 | 1.0000 | uniform | 0.0289 | 5.1 | A |  |
| flange_seat_flatness | linear | 0.000 | 0.000 | -0.050 / +0.050 | 1.0000 | normal | 0.0167 | 1.7 | A | proposed flatness 0.1 on the seat |
| gear_A_face_half | linear | 0.000 | 0.000 | -0.100 / +0.100 | 0.5000 | uniform | 0.0577 | 5.1 | A |  |
| spacer_B | linear | 1.000 | 0.000 | -0.050 / +0.050 | -1.0000 | normal | 0.0167 | 1.7 | D | sized to put B level with A |
| gear_B_face_half | linear | 0.000 | 0.000 | -0.100 / +0.100 | -0.5000 | uniform | 0.0577 | 5.1 | A |  |
| knuckle_B_end_float | linear | 0.000 | 0.000 | -0.150 / +0.150 | 1.0000 | uniform | 0.0866 | 45.8 | D | T15 end play / 2 |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -0.650 … 0.650 (fail) |
| RSS classic (t = 3σ) | -0.260 … 0.260 |
| RSS distribution-adjusted | -0.384 … 0.384 (pass) |
| MC mean / σ | 0.000 / 0.1282 |
| MC 0.135 % … 99.865 % | -0.351 … 0.354 |
| MC min … max | -0.473 … 0.457 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 1.69 / 1.56 |
| **Verdict (MC)** | **PASS** |

![T08-shimmed histogram](../../../../docs/gripper/figures/tol_T08-shimmed.png)
