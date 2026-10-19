# T01-drill33 — Horn-to-mount bolt pattern fit (4x M3 on the 14.0 BC)

Variant of `T01`: print 3.0, drill 3.3 after printing

- Requirement: All 4 M3 screws pass the printed clearance holes and thread into the horn with no hole-wall contact, crediting no pilot float. Fixed-fastener case (screw threads into the horn): H = F + T1 + T2.
- Spec: USL 0.000 mm radial interference (> 0 = screw hits hole wall)
- Acceptance: WC
- Model: radial; source file `T01_bolt_pattern_fit.yaml`; seed 20260922

y = |e_hole + e_thread| + F/2 - H/2. The task brief names the floating-fastener formula H = F + T; it does not apply here because the horn is threaded (fixed fastener, H = F + T1 + T2). With the MMC hole H = 3.25 (CAD 3.6) and F = 2.98, floating would give T = 0.27 per part; fixed with T2 = 0.05 leaves T1 = 0.22.

| Contributor | Kind | Nominal | Bias | Tol (−/+) | Sens. | Dist | σ | Var % | Tag | Source |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|
| hole_d_printed | linear | 3.300 | 0.030 | -0.030 / +0.030 | -0.5000 | normal | 0.0100 | 0.4 | A | CAD 3.2 (so101.md) + CNC Kitchen -0.25 bias [S]; scatter [A] |
| screw_major_d | linear | 2.927 | 0.000 | -0.053 / +0.053 | 0.5000 | uniform | 0.0306 | 4.2 | S | ISO 965 6g (Brighton-Best) |
| hole_position | radial | 0.000 | 0.000 | R 0.100 | 1.0000 | disk | 0.0500 | 89.7 | A | position dia 0.2 to A|B|C, printed |
| horn_thread_position | radial | 0.000 | 0.000 | R 0.025 | 1.0000 | disk | 0.0125 | 5.6 | A | molded horn pattern, W1 assumption 4 |

| Result | Value |
|---|---|
| Nominal | -0.186 |
| Mean-shifted centre | -0.201 |
| Worst case | -0.243 … -0.035 (pass) |
| RSS classic (t = 3σ) | -0.232 … -0.094 |
| RSS distribution-adjusted | -0.243 … -0.035 † (pass); clipped to WC, unclipped -0.250 … -0.018 |
| MC mean / σ | -0.133 / 0.0303 |
| MC 0.135 % … 99.865 % | -0.217 … -0.060 |
| MC min … max | -0.233 … -0.046 |
| MC out of spec | 0 % (± 3.2e-151 % s.e.) |
| Cpk percentile / normal | 1.83 / 1.47 |
| **Verdict (WC)** | **PASS** |

![T01-drill33 histogram](../../../../docs/gripper/figures/tol_T01-drill33.png)
