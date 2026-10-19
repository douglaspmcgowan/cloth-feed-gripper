# T04-tight — Gripper datum B axis vs wrist-roll axis (concentricity)

Variant of `T04`: recess CAD 19.55

- Requirement: Gripper axis (datum B) within 0.30 mm radial of the wrist-roll axis.
- Spec: USL 0.300 mm radial offset
- Acceptance: MC (Cpk ≥ 1.33, percentile method)
- Model: radial; source file `T04_concentricity.yaml`; seed 20260922

Screws clamp but do not locate; the part sits anywhere inside the pilot clearance (area-uniform disk).

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| pilot_float | radial | 0.000 | 0.000 | R 0.100 | 1.0000 | disk | 0.0500 | 66.7 | D | mean T02 clearance / 2 |
| horn_od_eccentricity | radial | 0.000 | 0.000 | R 0.050 | 1.0000 | disk | 0.0250 | 16.7 | A | horn OD vs spline |
| servo5_radial_play | radial | 0.000 | 0.000 | R 0.050 | 1.0000 | disk | 0.0250 | 16.7 | A | unpublished |

| Result | Value |
|---|---|
| Nominal | 0.000 |
| Mean-shifted centre | 0.000 |
| Worst case | 0.000 … 0.200 (pass) |
| RSS classic (t = 3σ) | 0.000 … 0.122 |
| RSS distribution-adjusted | 0.000 … 0.211 (pass) |
| MC mean / σ | 0.079 / 0.0359 |
| MC 0.135 % … 99.865 % | 0.004 … 0.177 |
| MC min … max | 0.000 … 0.193 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 2.22 / 2.05 |
| **Verdict (MC)** | **PASS** |

![T04-tight histogram](../../../../docs/gripper/figures/tol_T04-tight.png)
