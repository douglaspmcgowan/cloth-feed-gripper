# Revision B gripper thermal check

The script models the **DSServo DS3230 MG** selected by `params.json`, revision B, and the 35 s cycle. All figures are predictions. R26 requires case temperature ≤60 °C after 30 minutes.

## 0. Answer

<!-- THERMAL-ACCEPT:BEGIN -->
**Verdict: not safe without back-off; with back-off, acceptable only when every section-0 condition holds; discontinuous conduction: do not operate.**

**Regime classifier:** Bond the type K case bead with paste and Kapton to the exposed aluminium shell per [TP-07](../test/procedures/TP-07-thermal-soak.md). The C3 Ø1 hole measures the PETG mount; it is not the classifier. Commissioning needs a third, calibrated ambient channel in TP-07, pending in the test plan. Measure ambient with the shaded type K/MAX31855 bead 20 cm away; its expanded uncertainty is ±1.560 °C, including a 0.9 °C shaded-air representativeness term (assumed, unmeasured, until TP-07's third ambient channel measures it). The accepted ambient range is 21.560–38.440 °C, so ambient ± uncertainty stays inside the model's 20–40 °C domain. At 30 minutes, the reading ± expanded instrument uncertainty U = 1.639 °C is continuous only when that interval contains only the continuous prediction, and discontinuous only when it contains only the discontinuous prediction; otherwise it is indeterminate. The model's prediction uncertainty is not quantified, so any indeterminate outcome means do not operate. The command evaluates each regime at ambient ± its uncertainty and uses the widest prediction span. Rows marked not separable have predictions closer than 2U.

`python analysis/gripper/thermal/thermal.py --classify --ambient <°C> --reading <°C>` uses back-off on; add `--no-backoff` to select back-off off. Exit codes: continuous 0, discontinuous 2, indeterminate 3, refused ambient 4.

| Ambient (°C) | Continuous prediction (°C) | Discontinuous prediction (°C) | Separable at U? |
|---:|---:|---:|---|
| 22 | 34.4 | 68.1 | yes |
| 25 | 37.9 | 71.2 | yes |
| 30 | 43.0 | 75.8 | yes |
| 35 | 48.1 | 80.4 | yes |
| 38 | 51.6 | 83.5 | yes |

Worked example: at 22 °C ambient and a 35.0 °C case reading, run `python analysis/gripper/thermal/thermal.py --classify --ambient 22 --reading 35.0`; the generated model classifies the result as continuous.

**Separate R26 safety check:** PASS at or below 58.3 °C; FAIL at or above 61.7 °C; indeterminate between. Derivation: the exact limits 60 °C ∓ 1.639 °C are 58.360640369 °C and 61.639359631 °C; the governing thresholds round them inward to 0.1 °C. Any indeterminate outcome means do not operate.

Commissioning gates:
1. Back-off is enabled.
2. At least 5.0 N per pad is proven throughout the hold.
3. Stop at 30 minutes unless the steady-state F4 current limit for the row is met (continuous: 0.479 A at 25 °C; 0.241 A at 40 °C).

For acceptance, the combined expanded uncertainty must be ≤0.040 A for the reference chain at each applicable threshold. Firmware trips read the same INA219; its gain, offset, drift, and shunt tolerance are not established in firmware/gripper/config.h, so calibrate trips against the reference and apply a guard band before operation.

| Ambient (°C) | Conduction | Duration | F4 limit (A) | Predicted back-off (A) | Margin (A / %) | Predicted no back-off (A) |
|---:|---|---|---:|---:|---:|---:|
| 25 | continuous | 30 min | 0.534 | 0.152 | +0.382 / +71.5% | 1.055 |
| 25 | continuous | steady state | 0.479 | 0.155 | +0.325 / +67.8% | 1.109 |
| 40 | continuous | 30 min | 0.277 | 0.160 | +0.117 / +42.2% | 1.105 |
| 40 | continuous | steady state | 0.241 | 0.162 | +0.079 / +32.7% | 1.157 |
| 25 | discontinuous | 30 min | 0.512 | 0.727 | -0.215 / -42.0% | 1.739 |
| 25 | discontinuous | steady state | 0.457 | 0.727 | -0.270 / -59.1% | 1.739 |
| 40 | discontinuous | 30 min | 0.253 | 0.727 | -0.474 / -187.2% | 1.739 |
| 40 | discontinuous | steady state | 0.217 | 0.727 | -0.510 / -234.7% | 1.739 |
<!-- THERMAL-ACCEPT:END -->

<!-- THERMAL-R26:BEGIN -->
| Reading | Conduction | Back-off | Ambient (°C) | Case 30 min (°C) | Case steady (°C) | R26 |
|---|---|---:|---:|---:|---:|---|
| high | continuous | off | 25 | 86.7 | 92.4 | FAIL |
| high | continuous | on | 25 | 37.9 | 40.0 | PASS |
| high | continuous | off | 40 | 102.5 | 107.5 | FAIL |
| high | continuous | on | 40 | 53.1 | 55.0 | PASS |
| high | discontinuous | off | 25 | 117.4 | 120.7 | FAIL |
| high | discontinuous | on | 25 | 71.2 | 74.5 | FAIL |
| high | discontinuous | off | 40 | 129.8 | 132.6 | FAIL |
| high | discontinuous | on | 40 | 84.9 | 87.8 | FAIL |
| low | continuous | off | 25 | 83.3 | 88.8 | FAIL |
| low | continuous | on | 25 | 37.3 | 39.3 | PASS |
| low | continuous | off | 40 | 99.0 | 103.9 | FAIL |
| low | continuous | on | 40 | 52.5 | 54.3 | PASS |
| low | discontinuous | off | 25 | 113.8 | 117.1 | FAIL |
| low | discontinuous | on | 25 | 69.3 | 72.5 | FAIL |
| low | discontinuous | off | 40 | 126.2 | 129.1 | FAIL |
| low | discontinuous | on | 40 | 83.1 | 85.9 | FAIL |
<!-- THERMAL-R26:END -->

If a condition is not met, do not run the gripper: without back-off the predicted 30-minute case temperature is 82.7–129.2 °C. The generated R26 table gives each case temperature and `mount_steady_C`; compare the mount with the script's assumed 50 °C PETG creep onset. The only servo-case rating in this repository is the older DS3218's 70 °C rating. Until a DS3230 rating is sourced, use R26's 60 °C case limit only.

Measure first at 6.5 V and 5 N per pad: log the F4 INA219 hold-current reading, the case bead on the aluminium shell, the C3 Ø1-hole PETG-mount reading, ambient temperature, and pad force together, first with back-off enabled and then without it only for a brief characterized test.


## 1. Servo and loads

| Input | Value | Status |
|---|---:|---|
| Stall torque at 6.5 V | 2.877 N·m | sourced vendor claim via T1; unmeasured |
| Stall current, low / high reading | 3.80 / 3.99 A | sourced listing / derived T1 sizing reading; both unmeasured |
| Output torque constant, low / high | 0.757 / 0.721 N·m/A | derived from stall torque/current |
| Winding resistance, low / high | 1.711 / 1.629 Ω | derived as 6.5 V/current |
| Gearbox efficiency | 0.65 | assumed from the DS3218 dyno model; measure because it dominates current |
| No-load speed | 328 °/s | sourced T1 |
| Mass; body | 60 g; 40 × 20 × 40.5 mm | sourced listing via `params.json`; dimensions are rounded |
| Hold torque, 5 N / regulated 6 N | 0.792 / 0.944 N·m | derived, including 2 N cloth tension |
| Model hold current, 5 N low / high | 1.609 / 1.690 A | derived |
| T1 simulated hold current at about 6 N | 1.62 A median / 2.12 A 95th | cross-check: model predicts 1.92 / 2.02 A, +0.30 / −0.10 A against those references |

The old DS3218MG result is comparison only: its earlier model gave 71.0 °C (Fit A) and 50.7 °C (Fit B) at 25 °C, continuous conduction, 5 N, no back-off. It is not the revision B answer.

## 2. Revision B geometry and model

Geometry is read from `params.json`: selected servo, 38 mm case plus 2.5 mm boss, 10 mm ear offset, 2.5 mm housing wall, 5.0 × 3.2 × 2.55 mm limiter, 7 × 3.2 × 0.5 mm washer, and Ø1 mm thermocouple hole. The exposed length is **40.5 − 10 − 2×2.5 = 25.5 mm**, open on four faces. The body heat capacity is the previous composition scaled from 58 to 60 g [assumed]. Contact conductance, winding-to-case resistance, convection, emissivity, PETG properties and gearbox efficiency remain assumptions described in the result JSON.

Continuous means average-value copper loss, I²R(T). Discontinuous is the conservative I×V bound. Back-off uses the inherited friction threshold η_g² = 0.4225; it must still demonstrate ≥5 N pad force.

## 3. Mount and washer ruling

Preload is 250–500 N from 0.15–0.30 N·m tightening torque [assumed]. With the limiter, compression passes through metal.

| Washer | PETG annulus pressure (MPa) | Limiter sleeve pressure (MPa) | Judgement |
|---|---:|---:|---|
| Ø7 × 3.2 × 0.5 mm | 13.3–26.5 | 21.6–43.1 | keep in CAD |
| ISO 7092 M3, Ø6 class | 28.9–57.9 | 21.6–43.1 | conditional after inspection |

**Ruling: keep the Ø7 × 3.2 × 0.5 mm washer. Permit Ø6 only when the installed sleeve end stands above the compressed PETG seat by at least the generated minimum below. Measure the step across the sleeve end and adjacent compressed seat with a depth micrometer resolving 0.01 mm while the joint is at its specified preload. Reject a flush or recessed sleeve.**

<!-- THERMAL-WASHER:BEGIN -->
Computed minimum sleeve protrusion: **0.081 mm** at 500 N; elastic compression is 0.0404–0.0808 mm over 250–500 N, using **1790 MPa [D from S]**.
<!-- THERMAL-WASHER:END -->

The minimum is the script's elastic compression of the Ø6 PETG annulus at the 500 N maximum preload, using the 23 °C short-time modulus tagged [D from S]. The deciding tolerance stack is sleeve length minus wall thickness. Both tolerances are unknown, so measure both incoming sleeve length and printed wall thickness, then inspect the assembled loaded step. Inspect again for washer embedment after the first hot cycle.


## 4. Sensitivity and measurement

The motor/drive hold-current reading dominates. F4 settles the combined motor constant, winding loss and conduction regime more directly than vendor stall claims. Bench at 6.5 V, 5 N plus cloth tension, back-off off: log rail current, the case bead on the aluminium shell, and the C3 Ø1-hole PETG-mount reading for 30 minutes at room ambient; repeat with back-off while proving pad force ≥5 N. Reject operation if the case reaches 60 °C or the extrapolated hot-ambient case does.

## 5. Reproduction

Run `python analysis/gripper/thermal/thermal.py` to regenerate LF-only JSON, stdout, and the marked R26 table. Add `--figures` to also render the two platform-dependent PNGs. Run with `--check` to recompute and verify the committed JSON and table without writing anything. No timestamp or random data enters an output.
