# TP-12 Finger tip stiffness and fold load

<!-- hardware-scope:begin -->
**Hardware scope — arm: `absent`; gripper: `none`.** The arm is not used in this procedure. The gripper is not powered or commanded in this procedure.
<!-- hardware-scope:end -->

<!-- procedure-body:begin -->
**What it proves:** that each printed TPU finger, with its D7 part (nail on A, FSR backing and puck on B), has a tip-pad stiffness inside the R12 window of 0.88-1.63 N/mm, and at what load a spare finger folds. Stiffness sets how far the jaw turns past contact to reach 5 N, so it feeds TP-01, TP-03 and TP-04. About 40 min plus printing the fixture. Data sheet: [`../datasheets/TP-12.html`](../datasheets/TP-12.html) (CSV: `TP-12.csv`).

| | |
|---|---|
| Requirements | R12 (0.88 ≤ k ≤ 1.63 N/mm per finger); measurement M10 (tip stiffness and fold) |
| Pass | Secant k from 0.5 N to 5 N inside 0.88-1.63 N/mm by more than U on both fingers (clear pass 0.92-1.57 N/mm) |
| Instrument | Dial indicator 0.01 mm + hanger masses; U = 4.5 % of k, dominated by the load point (k ∝ s⁻³) [D `test_plan.py`] |
| Sample size | 3 load-unload runs per finger (printed TPU has hysteresis and creep) |

## Expected values

| Quantity | Expected | Source |
|---|---|---|
| k, bare finger | 0.92 (E 56 MPa) - 1.10 (E 67 MPa) N/mm | [D] `analysis/finger.md` section 1 |
| k, with the D7 parts | 1.07-1.29 N/mm | [D] `finger.md` section 1 |
| Tip deflection at 5 N, D7 finger | about 3.9-4.7 mm | [D, equation δ = F/k] |
| Fold (back-flank buckle), bare, E 56 | 8.88 N | [D] `finger.md` 1, `fea_summary.json` |
| Fold with the nail (finger A), E 56 | 8.41 N | same |
| Smallest k that reaches 5 N under the proposed 8 N cap | 1.05 N/mm; 1.26 N/mm with the 0.64° servo-lag margin | [D] `test_plan_out.json` → `expected.cap.proposed` |
| Same under the written 10 N cap | 0.82 N/mm; 0.94 N/mm with the lag margin (the firmware simulation still holds 5.22 N at 0.88 N/mm, so the lag margin is conservative) | [D] `expected.cap.written` |

## Equipment

Printed root block (a copy of the knuckle's root: two cheeks, web, two Ø2.0 peg holes, M2 hole) or a spare knuckle; a vise; the printed load saddle (below); wire stirrup and hanger; masses weighed on the lab balance to 0.1 g (51 g, then 51 g and 102 g increments to 510 g; for the fold test to 1020 g); dial indicator 0.01 mm on a magnetic or clamp base; calipers; both fingers with their D7 parts; one **spare** finger for the fold test; a catch tray.

## Fixture

The finger is clamped by its root exactly as on the knuckle (two Ø2.0 pegs and the M2 bolt), lying horizontal with the **pad face up**, so a weight on the pad pushes it the way the cloth does. The load must land at s = 40 mm from the root (the pad centre, 5 mm below the 45 mm tip): k goes as s⁻³, so 0.5 mm of misplacement is 3.75 % of k.

```
 Side view. Load direction = into the pad face (down on this page).

                         dial plunger (on the saddle, over the load line)
                                   |
                                   v
          root block       +-------+-------+   load saddle: printed, locates on the
  vise   [=cheeks=]        |  pocket fits  |   FSR puck seat (finger B) or the nail
 [#####] [ pegs, M2 ]====pad face=====o===+-|  (finger A); its load line is s = 40 mm
 [#####] [=========]======finger back=====+    from the root, 5 mm short of the tip
                                   |
                       wire stirrup round both sides of the finger
                                   |
                                [hanger]  masses
```

- Saddle plus stirrup plus hanger together weigh **51 g** (0.50 N): print the saddle, weigh the set, and top up with tape or a nut to 51.0 g. That is the first load.
- Mark the load line on the saddle; set the dial plunger on it, square to the pad.

## Setup

1. Clamp the root block in the vise, web vertical, so the finger lies horizontal with the pad face up. Check level with a square on the pad face.
2. Fit finger A (with its nail) in the block with its two pegs and the M2 bolt at about 0.2 N·m (ASSEMBLY step 19), no crushing of the cheeks.
3. Mount the dial base on the vise body, not the bench, so the clamp moves with the reading.

## Steps

**A. Stiffness (R12), finger A, then finger B.**

1. Without the saddle, zero the dial on the pad at the load line. Then place the saddle set (0.50 N), wait 10 s [A, TPU creep], read δ_0.5.
2. Add masses for totals of 102, 204, 306, 408, 510 g (1.0, 2.0, 3.0, 4.0, 5.0 N at g = 9.80 m/s²). Lower each on gently; wait 10 s; read δ.
3. Unload in reverse, reading at each step, then remove the saddle and read the dial at zero load (the return offset; more than 0.1 mm means the root block slipped or the TPU crept: note it).
4. Run 3 times on finger A. Swap to finger B (FSR backing and puck fitted, puck on the saddle seat) and run 3 times.

**B. Fold test, spare finger only (M10).** The fold can damage the finger: never fold a finger that will go on the gripper.

5. Fit the spare finger (bare; or with a nail if a second spare exists). Load 0.5-5 N as in step 2, then continue: 612, 714, 816, 918, 1020 g (6.0-10.0 N). At each step watch for the **fold**: the dial jumps (deflection grows much more than the previous step, or keeps creeping), and the back flank bows outward between the root and the first rib.
6. Stop at the fold, or at 1020 g. Record the last load held and the load at which it folded. Lift the masses off by hand at once.

## Data to record

Per reading: finger (A, B, spare), load_N, deflection_mm, k_secant_N_per_mm (on the 5 N row of each run), folded (yes/no), notes (run number, loading or unloading, return offset, what the fold looked like).

## Calculation

- Per run: **k = (F₅ − F₀.₅)/(δ₅ − δ₀.₅)** = 4.5 N / (δ₅ − δ₀.₅), using the loading branch.
- Hysteresis = largest difference between loading and unloading δ at the same load.
- Per finger: mean k and s over the 3 runs. Two-sided check with the one-sided factor on each side: lower bound mean − 5.31·s, upper bound mean + 5.31·s (k(3) = 5.31, `analyze_log.py` table).
- Fold load F_fold = (mass at the fold step)·9.80/1000 N; report the bracket (last held, first folded).

## Pass / fail

- **R12 pass:** every run's k is inside 0.92-1.57 N/mm (0.88 + U to 1.63 − U) **and** both tolerance bounds sit inside 0.88-1.63. If every run passes but a bound does not, run 3 more (n = 6, factor 3.09) before calling it.
- **Indeterminate:** any run's k within 0.88 ± 0.04 or 1.63 ± 0.07 N/mm.
- **Fail:** any run's k below 0.84 or above 1.69 N/mm.
- **Report against both R15 caps:** written 10 N (needs k ≥ 0.82, or ≥ 0.94 with lag margin); proposed 8 N (needs k ≥ 1.05, or ≥ 1.26 with lag margin). A finger between 0.88 and 1.26 N/mm passes R12 but would not hold 5 N under the 8 N firmware. These bounds use the firmware's squeeze cap with its 0.5 N `F_CAP_MARGIN_N` (4.87° at 10 N, 3.79° at 8 N).
- **Fold:** report F_fold against the 8 N trip (`config.h` `F_TRIP_N`), the 10 N written cap and the 8 N proposed cap. Fold below 8 N: the finger folds before the trip can fire, a fail for the force-cap design. Fold between 8 and 10 N: the written 10 N cap cannot be reached without a fold (expected).

## Hazards

- Masses up to 1.02 kg hang from a soft finger: catch tray under the hanger, feet clear. A folding finger drops the hanger suddenly.
- Do not exceed 1020 g on any finger that will be used.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| k under 0.88 N/mm | Softer TPU than E 56 (wet filament, other brand) or thin walls; `finger.md` section 1 fixes | Finger / FEA owner |
| k over 1.63 N/mm | Wall or ribs printed thick, or 100 % infill not used; nail or backing bonded too far down | Finger owner |
| Large return offset | Root clamp slip or TPU creep; tighten M2, use longer wait | Test owner |
| Fold below 8 N | Back-flank panel too thin (`finger.md` 1 next step: thicker back wall or extra rib) | Finger / FEA owner |
<!-- procedure-body:end -->
