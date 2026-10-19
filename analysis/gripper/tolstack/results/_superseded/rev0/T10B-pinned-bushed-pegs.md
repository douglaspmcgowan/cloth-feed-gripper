# T10B-pinned-bushed-pegs — Fingertip out-of-plane mismatch (Z) from pivot perpendicularity and wobble

Variant of `T10B`: fix-9 layout + sleeves + 2 locating pegs per finger (float 0.05), T08 shimmed

- Requirement: Tips within +/-2.0 mm in Z (pads keep >= 90 % of the 20 mm depth overlapping).
- Spec: LSL -2.000, USL 2.000 mm (tip A z - tip B z)
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: linear; source file `T10B_pad_out_of_plane.yaml`; seed 20260922

Frame G, Z = pivot-axis direction, normal to datum D (mid-plate front face). The base and the shimmed/bushed variants keep the servo-shaft layout (shaft A wobble, horn face runout). The -pinned variants are the fix-9 layout: knuckle A on its own pressed pin, so those two terms become pin A perpendicularity to D and knuckle A wobble on its pin. T08-shimmed still models gear A Z through the servo flange (not re-modelled for pinned).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| mesh_axial_offset | linear | 0.000 | 0.000 | from T08-shimmed | 1.0000 | empirical | 0.1282 | 10.4 | D | T08 |
| pinB_perpendicularity | linear | 0.000 | 0.000 | -0.700 / +0.700 | -1.0000 | normal | 0.2333 | 34.4 | A | perp dia 0.1 to A over 10 mm |
| knuckleB_wobble_on_pin | linear | 0.000 | 0.000 | -0.182 / +0.182 | -1.0000 | uniform | 0.1050 | 7.0 | D | bore clearance over bore length |
| finger_A_root_float | radial (2nd-axis proj.) | 0.000 | 0.000 | -0.050 / +0.050 | 1.0000 | disk | 0.0250 | 0.4 | D | Z component of the same X-Z float disk as T05/T09/T10 |
| finger_B_root_float | radial (2nd-axis proj.) | 0.000 | 0.000 | -0.050 / +0.050 | -1.0000 | disk | 0.0250 | 0.4 | D | Z component, same disk |
| finger_A_root_twist | linear | 0.000 | 0.000 | -0.067 / +0.067 | 1.0000 | uniform | 0.0385 | 0.9 | A | twist about Y moves the pad face (8 mm from the screw pattern) in Z; bounded separately from translation, so conservative |
| finger_B_root_twist | linear | 0.000 | 0.000 | -0.067 / +0.067 | -1.0000 | uniform | 0.0385 | 0.9 | A | same |
| finger_A_z_on_root | linear | 0.000 | 0.000 | -0.100 / +0.100 | 1.0000 | uniform | 0.0577 | 2.1 | A |  |
| finger_B_z_on_root | linear | 0.000 | 0.000 | -0.100 / +0.100 | -1.0000 | uniform | 0.0577 | 2.1 | A |  |
| pinA_perpendicularity | linear | 0.000 | 0.000 | -0.700 / +0.700 | 1.0000 | normal | 0.2333 | 34.4 | A | perp dia 0.1 to D over 10 mm |
| knuckleA_wobble_on_pin | linear | 0.000 | 0.000 | -0.182 / +0.182 | 1.0000 | uniform | 0.1050 | 7.0 | D | knuckle A bore clearance over bore length |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | -2.847 … 2.847 (fail) |
| RSS classic (t = 3σ) | -1.071 … 1.071 |
| RSS distribution-adjusted | -1.193 … 1.193 (pass) |
| MC mean / σ | 0.003 / 0.3962 |
| MC 0.135 % … 99.865 % | -1.184 … 1.188 |
| MC min … max | -1.722 … 1.841 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 1.69 / 1.68 |
| **Verdict (MC)** | **PASS** |

![T10B-pinned-bushed-pegs histogram](../../../../docs/gripper/figures/tol_T10B-pinned-bushed-pegs.png)
