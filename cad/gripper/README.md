# Cloth-feed gripper — CAD revision B.1

**Revision B.1 adds CHANGELOG rows B42 and B43 to the revision B solid and checks their geometry with named tests.** Six earlier rows remain open (B25–B28, B33, B34), and R10 fails (B24). The DSServo DS3230 MG model uses a 10.5 mm gear face, a reamed Ø9 boss bore, h8 pins in bronze bushes, 3.2 × 7 shims for 0.3 mm end play, metal limiter sleeves, and 0.44° pad toe-in. The 2D fit check found zero moving-to-static clash volume at −11, −7.4, 0, 10, and 20°; the full 3D audit samples every degree from −11 to +20° and reports intentional contacts separately. Assembly driver rays pass, and the wrist-flex check covers the angles stated below. **R10 mass moment is 52,995 g·mm, 121.2 % of the 43,720 limit** — see *Mass*. Tags: [S] sourced, [D] derived, [A] assumed.

**The dog coupling is not strong enough at stall (CHANGELOG B40).** If lash leaves one dog carrying the DS3230's stall (LC3, 2.876 N·m at 6.5 V, 411 N at r 7), the M3 set screw sees 1,693 MPa in bending against about 1,400 for class 45H, and the 3 mm aluminium horn socket 685 MPa in bearing against about 386 [A] [D `dog_check.py`]. Both dogs sharing: 846 / 342 MPa, safety factors 1.65 / 1.13. A hardened Ø3 dowel in place of the set screw halves the bending (853 MPa one dog) but not the horn bearing, so no swap that fits the 3.4 slots and the bought horn clears stall. One dog carries 1.62 N·m (0.56 × stall). **Until the coupling is fixed:** set the bench supply's current limit to 0.5 × the stall current measured in TP-13 on the delivered servo (about 1.44 N·m if torque follows current [A]; the 5 N hold needs 0.765 N·m), and never jam the jaw on a rigid stop. **The fix needs the coupling's owner:** a deeper steel socket (a 6 mm steel horn hub or clamp disc) or the Oldham disc of B27, then the dogs as hardened dowels.

## What changed and why

Full table with sources, rev A / rev B values and the test for each row: [`CHANGELOG.md`](CHANGELOG.md). In short:

| Change | Why (source) |
|---|---|
| Servo located by its Ø9 boss in a reamed bore (a web of the housing at the case top); dog slots 3.14 → 3.4; cradle pocket = measured case width + 0.40 (20.5 for 20.1) | Dog coupling and servo fit failed (tolerance rows 1, 3: T14B 40.68 % → 99.88 %, T14 → 100 %) |
| Knuckle bore Ø6 for 3 × 6 × 10 bronze bushes; ISO 2338 h8 3 × 16 pins graded 0.000-0.020; front-plate pin holes blind | m6 dowel is a press size, not a running fit (row 2, T16B); pins walked out (row 10, F06) |
| Pad faces toed in 0.44° about the contact point | Faces parallel at first contact (row 4, T10); r_c becomes 64.90 ≤ 64.95 (test plan row 1) |
| Two h8 3 × 6 locating pins, spider → reamed deck holes; one-time TCP calibration | Jaw centreline (row 5, T05) |
| Wrist recess 19.51 → 19.56; mount holes 3.6 → 3.7; horn screw length a parameter with a measured-depth rule | Pilot fit, bolt pattern, screw bottoming (rows 6-8) |
| Ear seat holes Ø5.0 with metal limiter sleeves, washer under each nut, frame 1.5 longer per end; Ø1 thermocouple hole; servo body left open | PETG under the nut creeps hot (thermal C1-C3) |
| Gear face 8 → 10.5; servo is a named parameter set (`servo.model`) | DS3230 MG jam shock (actuation C1, C2) |
| Deck screws moved to (±30.5, 6) / (±30.5, −7.5), side standoffs to x ±23, deck half-width 34 with corners clipped to r 37.5 | Three of four deck screws could not be fitted (fit check, F19) |
| Dog pins = M3x10 set screws threaded in from the front; B.1 horn-face annular relief and centre counterbore; knuckle root relief 6 → 6.55 (peg pitch 6 → 5.45) | Fit audit: former horn gap 0.500 mm and cross-side gap 0.703 mm at −11°; fine-step B.1 minima 0.750 and 1.215 mm |

## What to print

One sheet per part in [`drawings/`](drawings/) (four views and a *check after printing* table; a triangle marks each revision B feature). STL files in [`out/`](out/).

| Part | Material, infill | Orientation | After printing |
|---|---|---|---|
| `housing` | PETG, 60 % gyroid | mid plate on the bed; supports under deck and boss web | ream pin holes 3.0 H7 (with the front plate), boss bore 9.0 H7, deck pin holes 3.0 H7. **The boss web is 1.6 mm thick, spans about 40 mm and prints on supports:** clear the support from both faces, ream with light feed, back out turning forward; a grabbing reamer tears it out |
| `front_plate` | PETG, 60 % | front face on the bed | ream the blind pin holes with the housing |
| `wrist_mount` | PETG, 100 % | recess face up | ream pin holes 3.0; 4 heat-set inserts |
| `knuckle_a`, `knuckle_b` | PA6-CF, 100 %, hardened nozzle, dried | hub face on the bed | ream 6.0 H7, press the bush so neither end stands proud (0.25 below each face), pin-gauge the bore |
| `finger_a`, `finger_b` | TPU 95A, 100 % | flat | clear the Ø2 peg holes |
| `nail_a`, `fsr_backing_b`, `fsr_puck_b` | PLA, 100 % | flat | bond with CA, jaw open 20° |

## What to buy

[`drawings/BOM.md`](drawings/BOM.md): servo, horn (tap two M3 holes at r 7), M3x6 ISO 7380 centre screw, 2 × M3x10 set screws, 2 × h8 3 × 16 pins (buy 10 to grade), 2 × 3 × 6 × 10 bushes, 3.2 × 7 shim assortment, 2 × h8 3 × 6 pins, 4 × M3 horn screws (length from the measured depth), 4 × M3x6 deck screws, 4 inserts, 4 × M3x10 ear screws with 4 limiter sleeves, washers and nuts, 3 × M3x16, finger dowels and M2 bolts, FSR 402, retaining compound 638, thread-locker 243, three H7 hand reamers (3, 6, 9 mm).

## How to assemble

[`assembly/ASSEMBLY.md`](assembly/ASSEMBLY.md) and [`assembly/steps.json`](assembly/steps.json) (generator `assembly/assembly_plan.py`, which checks every insertion path and driver ray on the STL files). Order: ream and press on the bench → wrist plate onto the arm's horn → housing on the bench (sleeves, horn slid in from below, servo in from behind, centre screw through the pin A bore, ear screws, dog set screws, pins) → housing onto the wrist plate (4 deck screws from below) → shims, knuckles, front plate → fingers, FSR and nail → jaw check and TCP calibration.

## Measure before assembly

- **Horn hole depth** on the arm (DB M15): M3x6 needs ≥ 3.75 mm; 3.5-3.7 marginal (hand-check each head); shallower: drill and re-tap to ≥ 3.75 (`wrist_mount.horn_screw_rule`).
- **Servo, on three delivered units** (the DS3230 MG dimensions are not published; every one below is the DS3218MG value [A]): case width in three places (set `servo.body_x`; pocket = largest + 0.40), case length and height, ear span, hole pattern and thickness, ear height below the case top, output boss diameter and height, shaft offset from the outboard end and from the side, spline (25T), mass (60 g listing), stall ≥ 1.98 N·m at 6.35 V (purchase gate, actuation_trade.md 0).
- **Horn centre screw:** its head must sit in the horn's counterbored centre, at most 0.4 mm above the horn face (the central pin seat is 0.5 mm above it; the relieved annular face is 0.75 mm above the horn rim); check on the delivered horn.
- **Pins and bushes:** pin-gauge each pressed bush bore and micrometer each pin; pair them for 0.000-0.020 clearance.
- **End play:** feeler gauge at each pin; 3.2 × 7 shims (they bear on the PA6-CF hub face; a 3.2 × 6 shim only reaches the recessed bush end and would leave 0.8 mm) for 0.3 ± 0.05: plate gap 12.5 − hub 10.5 − 2 × 0.85 = 0.3 [D, measured on the solids by `test_B38_end_play_measured`].
- **Service:** pin A is bonded and faces the horn, so it comes out backwards only after the servo and horn are off (ASSEMBLY step 16 note).
- **Coupon** (tolerance_stacks.md *Coupon plan*): recess, holes, pocket, boss bore, peg float — before the real parts.

## Fit check (`out/fitcheck.json`, revision B)

- **Jaw sweep (R18)** at −11, −7.4, 0, 10, 20°: 0 mm³ between every moving part (knuckles, fingers, nail, FSR stack, bushes, pegs, dog set screws) and every static part; the horn (turns with knuckle A) clashes with nothing but the set screws threaded into it. Gear mesh overlap 0; knuckle-to-plate gaps 1.0 [D].
- **Keep-out (R9 hub):** r_max 11.62 (H−1…H+1) and 14.61 (H+1…H+5.0) against 11.6 / 14.6. That is a pass because r_max is a bisection upper bound with a 0.02 mm tolerance (`fitcheck.py` passes r_max ≤ limit + 0.02) and the exact test, the BRep volume outside the r 11.6 / 14.6 ring (band ends inset 0.01 mm), is 0 mm³ in both bands [D].
- **Roll ring gap to the wrist link:** 0.95 mm at z_I 0–1, 1.27 at 1–2, **0.59 at 2–5.3** (unchanged from rev A; tolerance stack T11 passes, Cpk 2.17) [D].
- **Envelope against the stock gripper:** inside in every band except z_I 40–60 (servo r 52.5 vs stock 37.3; rev A 51.2, the servo now sits 1.5 mm further back on its boss). R9 allows this when wrist flex is re-checked: **wrist flex clear** at φ −95…+95° and roll 0/90/180/270° for both grippers [D]. The deck corners are clipped to r 37.5 so band 6–12 stays inside (37.6 vs 37.6).
- **Assembly:** every insertion path and driver ray in `assembly/steps.json` passes; no blocker [D `assembly_plan.py`].
- **End walls beside the washer / nut notches (B39):** 0.80 mm of PETG at the washer layer and 1.10 at the nut layer (was 0.55 over the full 3.5 mm notch). 1.2 is out of reach while the thermal note's Ø7 washer sits 2.05 mm from the wall face: an ISO 7092 Ø6 washer would leave 1.30 (requested from the thermal owner).

## Mass (R10)

**R10 fails: 152.9 g including 13.5 g cloth and 5 g wiring, COM 37.6 mm past H, 52,995 g·mm = 121.2 % of 43,720** (C001 at 7.4 V) [D `fitcheck.py`]. 58,505 with the wrist UVC option.

**Revision A for comparison:** 144.4 g, 50,131 g·mm, 115 % (`fitcheck.py` on master `899265a`). DESIGN-BASIS R10's 40,507 g·mm (93 %) is the pre-CAD estimate (115.8 g, `design_basis.py`), and the test plan's 50,511 used the same CAD mass. **B.1 is 8.5 g and 2,864 g·mm heavier than rev A:** the selected 60 g servo, wider gears, boss web, fasteners, and limiters dominate; the B.1 relief and counterbore reduce the rev B mass slightly.

| Item | g | u past H mm | g·mm |
|---|---:|---:|---:|
| housing | 11.71 | 21.5 | 3,871 |
| front_plate | 4.14 | 28.4 | 1,397 |
| wrist_mount | 9.25 | 5.3 | 2,908 |
| knuckle_a | 6.11 | 36.3 | 2,110 |
| knuckle_b | 6.37 | 36.0 | 2,198 |
| finger_a | 4.60 | 70.6 | 1,747 |
| finger_b | 4.60 | 70.6 | 1,747 |
| nail_a | 0.30 | 95.0 | 121 |
| fsr_backing_b | 0.53 | 91.4 | 212 |
| fsr_sensor_b | 0.60 | 92.0 | 241 |
| fsr_puck_b | 0.04 | 95.0 | 16 |
| servo | 60.00 | 31.0 | 20,406 |
| horn | 2.36 | 31.0 | 803 |
| fasteners | 15.51 | 20.7 | 5,115 |
| fasteners_a | 4.55 | 40.5 | 1,591 |
| fasteners_b | 3.69 | 42.7 | 1,298 |
| cloth at the pad [D DB] | 13.50 | 96.0 | 5,469 |
| FSR + servo wiring [A DB] | 5.00 | 40.0 | 1,746 |
| **total** | **152.9** | COM 37.6 | **52,995** |

The 309.1 mm lever makes the limit about 126 g at this COM, so 27 g has to go. **What each real option buys** (estimates, none built; `python3 cad/gripper/r10_options.py` → `out/r10_options.json`; D = the model rebuilt with that one parameter changed, A = an assumed fraction, S = sourced). Running total counts only options that reduce the moment and qualify:

| Option | Δ g | Δ g·mm | Basis | What it costs | Running total g·mm |
|---|---:|---:|---|---|---:|
| Housing and front plate 60 → 40 % gyroid | -5.28 | -1,755 | D model, A strength | pin-plate and boss-web stiffness unchecked (T14B, T16 line-ream); coupon first | 51,240 |
| Wrist plate 100 → 60 % (4 walls) | -3.70 | -1,163 | A: 40 % of the solid mass | clamp under the 4 horn screws and the Ø19.56 pilot recess (T02) unchecked | 50,077 |
| Bushes 3 × 6 × 10 → 3 × 6 × 8 | -0.74 | -252 | D model | bearing length 8 in a 10.5 hub; T16 / T10B re-base (tolerance owner) | 49,825 |
| Limiter sleeves brass → aluminium | -0.69 | -233 | D volume, A densities | aluminium creep and fretting under the nut at 60 °C (thermal owner) | 49,592 |
| Lighter servo: DS3218MG at 1:1 (58 g) | -2.00 | -680 | S mass (actuators.csv A17) | fails the actuation study: R16 hold P 0.53 (actuation_trade.md 0); not a qualifying option | not counted |
| Lighter servo: DS3218MG + 1.5:1 stage (58 + 8.2 g) | +6.20 | +2,109 | S/A (actuation_trade.md 5.2) | qualifies on torque but is heavier; new bay, +0.95° backlash | not counted |
| Servo case turned up toward the wrist (long-Y layout; case 10 mm up from pivot A, but the deck rises so pivot-to-H +18.8 mm and servo u 31.0 → 39.8) | +3.04 | +2,762 | D model | whole gripper moves away from H with the taller deck; housing redesign; wrist flex / keep-out re-check | not counted |
| Servo body 10 mm nearer the wrist on a 1:1 stage (shaft off pivot A) | +8.20 | +2,189 | D lever, A stage 8.2 g as actuation_trade.md 5.2 | net heavier: the stage's own moment exceeds the 600 g·mm the move saves | not counted |
| Lightening holes, both knuckles (20 % of each) | -2.50 | -862 | A: 20 % removed | arm and gear-root stress unchecked (gears.py); PA6-CF print | 48,730 |
| Finger 45 → 40 mm (cloth, nail, FSR 5 mm nearer H; a hollow finger buys nothing more: the Fin Ray is already open cells) | -0.40 | -244 | D model | r_c 65 → about 60 (R17, gear and servo sizing), tip stiffness R12 rises about (45/40)³, reach; finger lane | 48,486 |

**Closest combination:** every counted row together (infill trims, short bushes, aluminium limiters, knuckle lightening holes, 40 mm fingers) gives 48,486 g·mm, 110.9 % of 43,720, still 4,766 g·mm (about 13.7 g at the COM lever) over. No qualifying servo is lighter than the DS3230, and moving the servo toward the wrist adds more than it saves in both forms the model can build. The servo alone is 20,406 g·mm and the cloth 5,469.

<!-- r10-work-cell-rule:begin -->
Douglas's 2026-10-11 ruling keeps R10 at **43,720 g·mm**. No option closes R10, and R10 honestly remains **FAIL at full extension**. The required work-cell rule is no holds with the gripper COM farther than r_limit = 285.9 mm from the shoulder_lift axis (43,720 g·mm / 152.9 g); the equivalent fingertip limit is 344.3 mm. The values come from the current CAD mass in `out/fitcheck.json`; TP-14 enforces the reach gate.
<!-- r10-work-cell-rule:end -->

## Still assumed

- Every DS3230 MG dimension (listed above) [A]; horn: 25T aluminium disc Ø20 × 3 seated on the 2.5 mm boss top (`servo.horn_gap`), two M3 holes tapped by hand [A].
- The horn centre screw can be an M3x6 ISO 7380 (2.0 mm hex) driven through the Ø3.0 pin A bore [A].
- Bush length 10 (catalogue class 3 × 6 × 10) [A]; h8 limits 2.986-3.000 [A, `basis.yaml`].
- Dog coupling allowables: 45H set screw about 1,400 MPa, hardened dowel about 1,700, aluminium horn socket bearing about 386 (6061-T6 class; the horn alloy is unknown) [A, `dog_check.py`]; see the top of this page.
- Torques for every screw are starting values [A]; printed hole bias and scatter from `basis.yaml` until the coupon is measured.

## Files and commands

| File | What it is |
|---|---|
| `params.json` | Every dimension, `"revision": "B"`. `_provenance` says which analysis set each value; `servo.models` holds the named servo rows. Keys the viewer writes are kept |
| `gripper_concept.py` | `params.json` → `out/` (STEP + STL per part, `assembly.step`, `parts.json`, `web/gripper_closed.glb`) and `drawings/` (one SVG sheet per printed part, `BOM.md`) |
| `fitcheck.py` | Gripper on the SO-101 horn frame: keep-outs, roll ring gaps, envelope against the stock gripper, wrist flex, jaw sweep, mass moment → `out/fitcheck.json`, `drawings/fitcheck*.svg` |
| `tests/test_revb.py` | Tests named by `CHANGELOG.md` row (`test_B<n>_…`), measured on the built solids; rows proved by a file or command say so in the CHANGELOG |
| `dog_check.py` | Dog coupling at stall (bending at the horn face, bearing in the horn socket) → `out/dog_check.json` |
| `r10_options.py` | R10 options table (model rebuilt per option) → `out/r10_options.json` |
| `CHANGELOG.md` | Revision A → B, row by row, with conflicts between sources |
| `gear_profile.dxf` / `.svg` | Gear profile from `analysis/gripper/gears.py` (unchanged in rev B) |
| `viewer.html`, `out/fit3d.json` | B.1 review page and content-checked 3D audit. The input digest follows local Python imports and opened data files; the result hash detects edited measurements. |

From the repository root, install Python 3.12, `uv`, Playwright and its Chromium browser. `uv run` obtains the named Python packages; cadquery is pinned to 2.8.0 (OCP 7.9.3.1.1), the kernel recorded in `out/fit3d.json` `kernel`, because a different OCP can move the measured distances. Regenerate in this order; allow about an hour for the complete 3D audit. Keep subset output outside `cad/gripper/out/`.

```powershell
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/gripper_concept.py
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/fitcheck.py
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 --with manifold3d --with trimesh python cad/gripper/assembly/assembly_plan.py
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/dog_check.py
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/r10_options.py
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/fit3d.py --pairs 'horn|housing,finger_a|knuckle_b,knuckle_a|finger_b' --thetas=-11:-9:0.1 --output "$env:TEMP\fitb1\subset.json"
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/fit3d.py
python cad/gripper/viewer_src/viewer_build.py
uv run --with pytest --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python -m pytest cad/gripper/tests -q -p no:cacheprovider --basetemp "$env:TEMP\fitb1\pytest"
python cad/gripper/viewer_src/vw_test.py --shots "$env:TEMP\fitb1\shots"
python cad/gripper/viewer_src/fit_shots.py --shots "$env:TEMP\fitb1\fit-shots"
```

The same commands in bash (Linux, macOS):

```bash
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/gripper_concept.py
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/fitcheck.py
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 --with manifold3d --with trimesh python cad/gripper/assembly/assembly_plan.py
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/dog_check.py
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/r10_options.py
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/fit3d.py --pairs 'horn|housing,finger_a|knuckle_b,knuckle_a|finger_b' --thetas=-11:-9:0.1 --output "${TMPDIR:-/tmp}/fitb1/subset.json"
uv run --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python cad/gripper/fit3d.py
python cad/gripper/viewer_src/viewer_build.py
uv run --with pytest --with cadquery==2.8.0 --with cadquery-ocp==7.9.3.1.1 python -m pytest cad/gripper/tests -q -p no:cacheprovider --basetemp "${TMPDIR:-/tmp}/fitb1/pytest"
python cad/gripper/viewer_src/vw_test.py --shots "${TMPDIR:-/tmp}/fitb1/shots"
python cad/gripper/viewer_src/fit_shots.py --shots "${TMPDIR:-/tmp}/fitb1/fit-shots"
```

The committed `out/fit3d.json` comes from a full `python cad/gripper/fit3d.py` run on 2026-10-14 (F09 grades `fasteners_a|housing`) on a Linux cloud container (4 CPUs, Python 3.11.17, cadquery 2.8.0, cadquery-ocp 7.9.3.1.1): wall time 2522 s (`runtime_s` 2491.9), exit code 0, `VERDICT PASS`. The 2026-10-13 run (start 04:09:29 UTC, wall time 1746 s, `runtime_s` 1724.0, exit code 0, `VERDICT PASS`) measured the same geometry before F09 grading.

The subset command samples the named pairs and jaw angles without replacing the hash-checked full result. The full audit exits nonzero on a failed clearance, an unintended overlap, or a sampling margin violation. `--report-only` saves a failing result with exit zero for review. Build the page only from the current, complete result; its input and result hashes are checked. The browser suite exercises 1440×900, 768×1024 and 375×812 viewports. `analysis/gripper/gears.py` owns the independent, unchanged gear sweep.

STL, GLB and per-part STEP files rebuild byte-identical on one machine (STEP headers normalised by `normalise_step`). **`out/assembly.step` is not byte-stable:** the OCC writer orders its colour (STYLED_ITEM) records differently from run to run, so a second build shows it modified; compare it by the per-part volume, bounding box and face count in `out/parts.json`. Across machines or OCC versions the tessellation can differ: compare parts by volume, bounding box and face count in `out/parts.json`.

**Geometry frame.** Frame G, mm: X = jaw closing axis, Y = up (wrist on top, tips at −Y), Z = out of the gear plane. Pivot A (servo) at (−14.25, 0), B at (+14.25, 0). Wrist-roll axis x = 0, z = 0. Horn face H at y = 31.00. **Z stack [D]:** servo case z −46.5…−8.5, boss web −8.35…−6.75, horn −6…−3, mid plate −2.5…0 (datum D = front face), shim 3.2 × 7 × 0.85 on the hub face, knuckles 1…11.5 (bush 1.25…11.25), shim 0.85, front plate 12.5…15, end play 0.3 (shims picked at assembly). Finger mid-plane z 6.25.

`viewer_src/fit_shots.py` captures focused B18, both B19, printed/finished boss and roll views in the supported light/dark viewport sizes. It checks page errors and complements the complete browser suite.

The audit classifies whole-solid gaps with direct clearance limits separately from pairs whose feature fit is checked by B4 pin/bush diametral clearance, B38 knuckle end play or T07 gear backlash (jt = 2 d / cos α from the mesh gap d). The latter show both the whole-solid gap and the governing measured value and status; a feature value within `sampling.rounding_allowance_mm` (0.0005 mm) of either limit is at risk, not met. The page groups the arm-clearance note under **Unverified arm clearance** because wrist-flex clearance needs an arm check under R9.
