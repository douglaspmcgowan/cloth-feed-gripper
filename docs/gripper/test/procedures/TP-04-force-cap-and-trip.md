# TP-04 Force cap and over-force trip

<!-- hardware-scope:begin -->
**Hardware scope — arm: `off`; gripper: `bench`.** The arm is off and its power supply is disconnected for this whole procedure. The gripper is fixed in the bench fixture; the arm is not powered.
<!-- hardware-scope:end -->

<!-- procedure-body:begin -->
**What it proves:** the true pad force never exceeds the force cap, in the four ways the analysis says a grip can over-squeeze: a too-high command, contact far earlier than calibrated, an FSR that reads half the true force, and a finger pushed from outside. R15 is open, so every peak is judged against both caps: **10 N (written)** and **8 N (proposed)**. With the current `config.h`, the analysis predicts a pass at 10 N and a **fail at 8 N** (the half-reading FSR case reaches 9.66 N and a contact 8-10° early 8.20-9.66 N; the pushed finger trips at 8 N, not below it). It also checks the R18 position floor (θ ≥ −7.4°). About 45 min. Data sheet: [`../datasheets/TP-04.html`](../datasheets/TP-04.html) (CSV: `TP-04.csv`).

| | |
|---|---|
| Requirements | R15 (force cap), R18 (firmware floor θ ≥ θ_c0 − 6.2°, `JAW_FLOOR_BELOW_C0_DEG`; absolute backstop −10.2°, `JAW_MIN_DEG`) |
| Pass | Every probe peak ≤ cap − U, and the 95 %/90 % upper bound of each case ≤ cap; `FSR_OVER` → `ENTER_FAULT` within 20 ms of the FSR crossing 8 N, jaw opens 5°; `ST` `th=` never below θ_c0 − 6.2° (θ_c0 from `EVT CAL_THETA_C0`, also `c0=` in `ST`) |
| Instrument | Pinch probe (TP-01), U = 0.103 N at 8 N, 0.110 N at 10 N [D `test_plan.py`] |
| Sample size | 3 per deterministic case (G 7, early contact, FSR at 50 %); 22 pushed-finger trips: zero failures in 22 shows reliability 0.90 at 90 % confidence (safety) |

## Expected values (from the analysis; a result far from these means a setup error)

| Case | Expected | Source |
|---|---|---|
| 1. `G 7` (firmware clamps any G to `F_SET_MAX_N`) | 1.0 N/mm finger: stops at the squeeze cap with `FORCE_SAT`, about 6.0 N. Finger ≥ 1.18 N/mm: reaches the clamp (7.5 N soft limit) | [D] `controls.md` 0; [D, equation 0.5 + 1.135·k·4.87° ≥ `F_SET_MAX_N`; 4.87° is CTRL_U_MAX_DEG in `force_ctrl.h` = (10 − 0.5 margin − 0.5) / 1.849, 5.14° before `F_CAP_MARGIN_N`] |
| 2. Contact 6 / 8 / 10° above θ_c0 (1.63 N/mm) | every peak within 8 N; the 8° case trips `FSR_OVER` → FAULT, 6° and 10° hold | [D] `fw_sim.json` → `sensor_faults.early_contact_*`; `controls.md` 4.4 |
| 3. FSR reads 50 % | 6.34 N at 1.0 N/mm; **9.66 N** at 1.63 N/mm (the squeeze cap, U_max 4.87°) | [D] `test_plan_out.json` → `expected.fsr50_peak_N`, `cap.written` |
| 4. Finger pushed in HOLD | `FSR_OVER` at FSR `F_TRIP_N` (20 ms `F_TRIP_MS`); probe ≈ 8 N if the TP-01 span holds | [D] `config.h` |
| Normal `G 5` peak | 5.22-7.41 N | [D] `expected.peak_range_N` |
| Finger fold | 8.4 N (finger A with nail) to 8.9 N (E56) | [D] `finger.md` 1, `cap.written.fold_*` |

**The 8 N cap holds for every case except case 3.** Case 3 predicts its table value above the cap at the stiffest finger: the squeeze cap is sized above the cap (`F_CAP_N` less `F_CAP_MARGIN_N`) because sizing it for 8 N collapses R14 in the simulation (`controls.md` 6.4), so a badly reading FSR can exceed 8 N; case 2 stays within 8 N; case 4 trips at `F_TRIP_N`. Record case 3 against 8 N as a predicted FAIL. A build that also holds case 3 needs `F_CAP_N` 8.0 (shipped 10.0), which with `F_CAP_MARGIN_N` shortens the squeeze so that softer fingers can no longer reach 5 N (U_max and the minimum finger stiffness: `test_plan_out.json` → `expected.cap.proposed`) [D].

## Equipment

The TP-01 pinch probe and `probe.ino` reader, aluminium or PETG spacer plates (14, 18 and 23 mm stacks, 15 mm wide), a 6 mm wooden dowel about 150 mm long, foam block, laptop with two `gripper_log.py` terminals, spare finger (A and B), TP-12 result for the finger stiffness.

## Setup

```
 Case 2: spacers added outside the probe plates, half on each side, on the contact marks.

  finger A  [pad]|spacer|P1 ========= TAL220 ========= P2|spacer|[pad]  finger B
                  7-12 mm  \____ 6 mm probe stack ____/   7-12 mm

 Case 4: push on the BACK of finger A, near the tip pad, slowly, square to the finger.

     dowel ===>  finger A  [pad]| probe |[pad]  finger B
```

1. Gripper in the vise, fingers horizontal, rail 6.50 V. Probe on the foam between the pads, marks on the pad centres; probe tared (TP-01 step 6). Send `C`: θ_c0 about +2.2° on the 6 mm probe. Record it.
2. FSR span from TP-01 (`OK CALF span=`). Case 3 needs a starting span of about 1.0 or more, because `CALF` refuses a span under 0.5 (`FSR_SPAN_MIN`).
3. Terminal 1: `python docs/gripper/test/tools/gripper_log.py --port <gripper port> --out TP-04_log.csv`, then `STREAM 50`. Terminal 2: `python docs/gripper/test/tools/gripper_log.py --port <probe port> --out TP-04_probe.csv`. Both stamp laptop time, so the probe and the events line up.

## Steps

**Case 1. Over-command, 3 trials.**

1. `G 7`. Wait 5 s after `ENTER_HOLD` (or `FORCE_SAT`). Record the probe peak, the FSR `F=`, any `FORCE_SAT`. `R`, wait for IDLE. Three times.

**Case 2. Early contact, 3 trials at each of 6, 8, 10°.**

2. Check the opening first: probe 6 mm + 23 mm spacers = 29 mm must enter the 46.9 mm tip-pad gap at +20° (`finger.md` 6.1) with room to centre it.
3. Do **not** recalibrate. Add spacers of 14 mm (6°), then 18 mm (8°), then 23 mm (10°): about 2.3 mm of tip-pad gap per degree near 0° [D `finger.md` 6.1, linearised].
4. Each trial: `G 5`; record the probe peak and the events; `R`. After a FAULT, take the spacers out **before** `H`: `H` re-homes and recalibrates, and with spacers in, CALIBRATE faults (contact above +4°, `CAL_C0_MAX_DEG`). Put them back after `ENTER_IDLE`.

**Case 3. FSR reading 50 %, 3 trials.**

5. Bare probe, `G 5`. In HOLD read the probe mean F_p over 2 s. Send `CALF <F_p/2>` (for example `CALF 2.66`). The reply `OK CALF span=` must be half the old span.
6. `R`, wait for IDLE, `G 5`. Expect `FORCE_SAT` and a hold at the squeeze cap. Record the probe peak and hold. `R`. Three times.
7. Restore: `G 5`, in HOLD read the probe force F_now, send `CALF <F_now>`. Check FSR and probe agree within 0.1 N.

**Case 4. Pushed finger, 22 trials.**

8. Terminal 1: stop the interactive session (Ctrl+C), then `python docs/gripper/test/tools/gripper_log.py --port <gripper port> --out TP-04_trip.csv --sequence trip --n 22`.
9. Each trial: Enter (sends `G 5`). After `ENTER_HOLD`, push the back of finger A toward B with the dowel, slowly (about 2 s from 5 to 8 N), until the log shows `EVT ENTER_FAULT`. Take the dowel away. Enter again (sends `H`: re-home and recalibrate on the probe).
10. `python docs/gripper/test/tools/analyze_log.py faults TP-04_trip.csv` lists every `FSR_OVER` (its argument is the FSR force), `FAULT_OVERFORCE` and `ENTER_FAULT` with times.
11. After the last trial, inspect both fingers for a fold crease, whitening or a cracked rib; take the probe out and `C` on bare pads.

## Data to record

Per trial: trial, case (1, 2-6°, 2-8°, 2-10°, 3, 4), FSR span set, probe peak, FSR force at the trip (`FSR_OVER` argument), fault event, lowest `ST` `th=` in the trial, notes (FSR_OVER ms, ENTER_FAULT ms, interpolated 8 N crossing ms, `th=` before and after FAULT, any fold).

## Calculation

- Probe peak per trial from `TP-0x_probe.csv` (F = (counts − zero)/scale).
- Per case: upper bound B = mean + k·s, k 5.311 (n = 3) or 2.172 (n = 22).
- Trip timing: 8 N crossing time from the `ST` `F=` values (interpolated; `STREAM 50` gives U 12.9 ms); `ENTER_FAULT` ms − crossing ms. `FSR_OVER` is posted 20 ms after the crossing by design, and `ENTER_FAULT` should carry the same ms.
- Back-off: first `ST` `th=` after FAULT minus the last before it; expect +5° (`FAULT_BACKOFF_DEG`, from the larger of the command and θ_c0).

## Pass / fail

| Reading | Written cap 10 N | Proposed cap 8 N |
|---|---|---|
| Every probe peak | ≤ 9.89 N (10 − U 0.11) | ≤ 7.90 N (8 − U 0.10) |
| Upper bound B per case | ≤ 10 N | ≤ 8 N |
| Indeterminate | any peak 9.89-10.1 N | any peak 7.90-8.10 N |
| Predicted | pass; closest are case 3 on a 1.63 N/mm finger (9.66 N) and case 2 at 10° (9.66 N), both clear of 9.89 N | **fail** (case 3 9.66 N; case 2 at 8° / 10° 8.20 / 9.66 N; case 4 ≈ 8 N) |

Both caps also need: `ENTER_FAULT` ≤ 20 ms + 13 ms (stream U) after the 8 N crossing and on the same ms as `FSR_OVER`, in 22 of 22; `th=` rises by 5° after every FAULT; `th=` never below θ_c0 − 6.2° (R18 floor, `JAW_FLOOR_BELOW_C0_DEG`; θ_c0 is `c0=` in the `ST` lines). Record R15 at both values; do not pick one.

**A fold voids the reading.** If the finger folds in a case (back flank bows out, the probe force drops while the jaw keeps closing; expected at 8.4-8.9 N, finger.md), the probe under-reads the force the cap allowed. Record that case as FAIL at the proposed 8 N cap and INDETERMINATE at the written 10 N cap, and note the fold load.

## Hazards

- **Finger fold:** the finger folds at 8.4-8.9 N (`finger.md`). Expect it in case 3 on a stiff finger and in case 4. A folded finger reads low on the probe; note it and replace the finger if it creases or whitens. Keep the spare pair at hand.
- **Pinch:** up to 10 N between the pads. Push with the dowel, never a finger, and keep hands out of the jaw while `G` is active.
- The probe can spring out when the jaw opens to FAULT: foam under it, face away.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| Peak > 10 N in case 3 | Finger stiffer than 1.63 N/mm (TP-12), or the squeeze cap not applied | Controls owner, Douglas (R15) |
| Case 4 trips with the probe well above 8 N | FSR span reads low (re-run TP-01 `CALF`), or FSR off the pad centre | Controls / FSR mounting |
| No FAULT in case 2 at 10° | Contact landed in the slow zone: spacers too thin | Re-check the spacer thickness |
| `ENTER_FAULT` long after `FSR_OVER` | Event queue or loop overrun (`controls.md` O7) | Firmware owner |
| `th=` below θ_c0 − 6.2° | Floor not enforced | Firmware owner: **safety, stop using the gripper on the arm** |
<!-- procedure-body:end -->
