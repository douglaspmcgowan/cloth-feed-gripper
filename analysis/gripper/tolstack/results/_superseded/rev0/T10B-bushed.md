# T10B-bushed — Fingertip out-of-plane mismatch (Z) from pivot perpendicularity and wobble

Variant of `T10B`: T08 shimmed + bronze sleeve in knuckle B, bore length 7.7

- Requirement: Tips within +/-2.0 mm in Z (pads keep >= 90 % of the 20 mm depth overlapping).
- Spec: LSL -2.000, USL 2.000 mm (tip A z - tip B z)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T10B_pad_out_of_plane.yaml`; seed 20260922

Frame G, Z = pivot-axis direction, normal to datum D (mid-plate front face). The base and the shimmed/bushed variants keep the servo-shaft layout (shaft A wobble, horn face runout). The -pinned variants are the fix-9 layout: knuckle A on its own pressed pin, so those two terms become pin A perpendicularity to D and knuckle A wobble on its pin. T08-shimmed still models gear A Z through the servo flange (not re-modelled for pinned).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| mesh_axial_offset | linear | 0.000 | 0.000 | from T08-shimmed | 1.0000 | empirical | 0.1282 | 3.9 | D | T08 |
| pinB_perpendicularity | linear | 0.000 | 0.000 | -0.700 / +0.700 | -1.0000 | normal | 0.2333 | 12.9 | A | perp dia 0.1 to A over 10 mm |
| knuckleB_wobble_on_pin | linear | 0.000 | 0.000 | -0.182 / +0.182 | -1.0000 | uniform | 0.1050 | 2.6 | D | bore clearance over bore length |
| shaftA_wobble | linear | 0.000 | 0.000 | -0.875 / +0.875 | 1.0000 | uniform | 0.5052 | 60.5 | A | 2 x per-bearing radial play / bearing span (basis servo_shaft_tilt) |
| hornA_face_runout | linear | 0.000 | 0.000 | -0.175 / +0.175 | 1.0000 | normal | 0.0583 | 0.8 | A | FIM over ~20 mm horn |
| finger_A_root_float | radial (2nd-axis proj.) | 0.000 | 0.000 | -0.210 / +0.210 | 1.0000 | disk | 0.1050 | 2.6 | D | Z component of the same X-Z float disk as T05/T09/T10 |
| finger_B_root_float | radial (2nd-axis proj.) | 0.000 | 0.000 | -0.210 / +0.210 | -1.0000 | disk | 0.1050 | 2.6 | D | Z component, same disk |
| finger_A_root_twist | linear | 0.000 | 0.000 | -0.280 / +0.280 | 1.0000 | uniform | 0.1617 | 6.2 | A | twist about Y moves the pad face (8 mm from the screw pattern) in Z; bounded separately from translation, so conservative |
| finger_B_root_twist | linear | 0.000 | 0.000 | -0.280 / +0.280 | -1.0000 | uniform | 0.1617 | 6.2 | A | same |
| finger_A_z_on_root | linear | 0.000 | 0.000 | -0.100 / +0.100 | 1.0000 | uniform | 0.0577 | 0.8 | A |  |
| finger_B_z_on_root | linear | 0.000 | 0.000 | -0.100 / +0.100 | -1.0000 | uniform | 0.0577 | 0.8 | A |  |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -3.762 … 3.762 (fail) |
| RSS classic (t = 3σ) | -1.285 … 1.285 |
| RSS distribution-adjusted | -1.948 … 1.948 (pass) |
| MC mean / σ | 0.002 / 0.6476 |
| MC 0.135 % … 99.865 % | -1.719 … 1.744 |
| MC min … max | -2.277 … 2.289 |
| MC out of spec | 0.025 % (± 0.005 % s.e.) |
| Cpk percentile / normal | 1.15 / 1.03 |
| **Verdict (MC)** | **FAIL** |

![T10B-bushed histogram](../../../../docs/gripper/figures/tol_T10B-bushed.png)
