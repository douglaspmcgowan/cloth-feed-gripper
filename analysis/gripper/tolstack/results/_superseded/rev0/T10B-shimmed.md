# T10B-shimmed — Fingertip out-of-plane mismatch (Z) from pivot perpendicularity and wobble

Variant of `T10B`: T08 shimmed

- Requirement: Tips within +/-2.0 mm in Z (pads keep >= 90 % of the 20 mm depth overlapping).
- Spec: LSL -2.000, USL 2.000 mm (tip A z - tip B z)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T10B_pad_out_of_plane.yaml`; seed 20260922

Frame G, Z = pivot-axis direction, normal to datum D (mid-plate front face). The base and the shimmed/bushed variants keep the servo-shaft layout (shaft A wobble, horn face runout). The -pinned variants are the fix-9 layout: knuckle A on its own pressed pin, so those two terms become pin A perpendicularity to D and knuckle A wobble on its pin. T08-shimmed still models gear A Z through the servo flange (not re-modelled for pinned).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| mesh_axial_offset | linear | 0.000 | 0.000 | from T08-shimmed | 1.0000 | empirical | 0.1282 | 2.6 | D | T08 |
| pinB_perpendicularity | linear | 0.000 | 0.000 | -0.700 / +0.700 | -1.0000 | normal | 0.2333 | 8.6 | A | perp dia 0.1 to A over 10 mm |
| knuckleB_wobble_on_pin | linear | 0.000 | 0.000 | -0.817 / +0.817 | -1.0000 | uniform | 0.4715 | 35.1 | D | bore clearance over bore length |
| shaftA_wobble | linear | 0.000 | 0.000 | -0.875 / +0.875 | 1.0000 | uniform | 0.5052 | 40.3 | A | 2 x per-bearing radial play / bearing span (basis servo_shaft_tilt) |
| hornA_face_runout | linear | 0.000 | 0.000 | -0.175 / +0.175 | 1.0000 | normal | 0.0583 | 0.5 | A | FIM over ~20 mm horn |
| finger_A_root_float | radial (2nd-axis proj.) | 0.000 | 0.000 | -0.210 / +0.210 | 1.0000 | disk | 0.1050 | 1.7 | D | Z component of the same X-Z float disk as T05/T09/T10 |
| finger_B_root_float | radial (2nd-axis proj.) | 0.000 | 0.000 | -0.210 / +0.210 | -1.0000 | disk | 0.1050 | 1.7 | D | Z component, same disk |
| finger_A_root_twist | linear | 0.000 | 0.000 | -0.280 / +0.280 | 1.0000 | uniform | 0.1617 | 4.1 | A | twist about Y moves the pad face (8 mm from the screw pattern) in Z; bounded separately from translation, so conservative |
| finger_B_root_twist | linear | 0.000 | 0.000 | -0.280 / +0.280 | -1.0000 | uniform | 0.1617 | 4.1 | A | same |
| finger_A_z_on_root | linear | 0.000 | 0.000 | -0.100 / +0.100 | 1.0000 | uniform | 0.0577 | 0.5 | A |  |
| finger_B_z_on_root | linear | 0.000 | 0.000 | -0.100 / +0.100 | -1.0000 | uniform | 0.0577 | 0.5 | A |  |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -4.397 … 4.397 (fail) |
| RSS classic (t = 3σ) | -1.512 … 1.512 |
| RSS distribution-adjusted | -2.386 … 2.386 (fail) |
| MC mean / σ | 0.003 / 0.7939 |
| MC 0.135 % … 99.865 % | -2.138 … 2.159 |
| MC min … max | -2.812 … 2.915 |
| MC out of spec | 0.636 % (± 0.025 % s.e.) |
| Cpk percentile / normal | 0.93 / 0.84 |
| **Verdict (MC)** | **FAIL** |

![T10B-shimmed histogram](../../../../docs/gripper/figures/tol_T10B-shimmed.png)
