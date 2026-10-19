# TP-06 Endurance cycling screen

<!-- hardware-scope:begin -->
**Hardware scope — arm: `off`; gripper: `bench`.** The arm is off and its power supply is disconnected for this whole procedure. The gripper is fixed in the bench fixture; the arm is not powered.
<!-- hardware-scope:end -->

<!-- procedure-body:begin -->
**What it proves:** the gripper survives 1e4 grip cycles on cloth with no fault, no crack and no meaningful growth in backlash, and still holds 5 N afterwards. **This is a screen, not a life demonstration.** Showing 1e5 grips (R25) with zero failures on one unit needs about 2.6e5 cycles (`test_plan_out.json` → `sample_sizes.R25_life`: wear-out shape β 2 [A], reliability 0.9, confidence 0.5), about 12 days of cycling. R25 therefore rests on the analysis in `dyno.md`; this run catches early wear-out and gross errors in it. About 30 min attended plus an unattended run of 9-11 h. Data sheet: [`../datasheets/TP-06.html`](../datasheets/TP-06.html) (CSV: `TP-06.csv`).

| | |
|---|---|
| Requirements | R25 (life, screen only), R13 (gear profile: no crack, backlash growth); measurement M22 (gear wear and backlash after 1e4 grips, `gears.md` 8) |
| Pass | 1e4 cycles with no FAULT, no crack; backlash growth ≤ 0.1 mm at the tip pad [A]; hold still ≥ 5.0 N on the probe; θ_c0 shift ≤ 0.5° [A] |
| Instrument | Dial indicator 0.01 mm (U 0.026 mm at the dial); pinch probe U 0.096 N; event log θ_c0 to 0.01°; type K thermocouples (case and mount) U 1.6 °C, which also trip the cutoff |
| Sample size | 1 unit, 1e4 cycles, checkpoints at 0, 1e3, 5e3 and 1e4 cycles |

## Expected values (from the analysis; a result far from these means a setup error)

| Quantity | Expected | Source |
|---|---|---|
| Gear life, printed PA6-CF m 1.5 z 19 | 6.2e7 grips (flank) | [D] `dyno.md` 0, 6 |
| TPU finger life | 3.1e6 grips at a × 0.5 printed knockdown; **4.3e3** at × 0.27 | [D] `dyno.md` 6 |
| Gear wear, worst-case face mean | 0.058 mm (limit 0.15 mm) | [D] `gears.md` 0 |
| Backlash at the tip pad, new | 0.72-1.56 mm (gear) plus dog lash; TP-08 measures it | [D] TP-08 |
| Cycle time | 3.1-3.8 s: close to HOLD 0.73-0.81 s + 2.0 s hold + open 24° at 120 °/s (0.2 s) + 0.12 s settle ≈ 3.1 s; host and USB turnaround up to 3.8 s [A] → 1e4 cycles in 8.6-10.6 h | [D, equation] `expected.close`, `config.h` |

The 4.3e3 finger figure is driven by 1e3 force-cap events at 10 N and by tip collisions with the arm (`dyno.md` 6). **This run has neither**, so passing 1e4 cycles here does not refute it; it only shows the 5 N duty itself does no early damage.

## Equipment

Gripper in the vise with its 6.5 V rail and a supply that can run overnight, laptop that will not sleep (power settings), a strip of demo fabric clamped above and below the jaw so one ply always sits between the pads, plus spare strips, the TP-01 probe, dial indicator with base, the TP-12 load saddle and masses, a 10× loupe, a camera, the thermocouple board (`../tools/probe/probe.ino`, two type K beads: servo case and printed mount, TP-07 method) with a relay in the servo's +6.5 V line (the **thermal cutoff** below), a second USB port on the laptop for it.

## Thermal cutoff (required; the run is never left without it)

The 1e4-cycle run is unattended for 9-11 h and a stalled or hot servo heats fast. The probe board stops it by itself, from two directions. The board checks both beads every 100 ms whether or not it is streaming (`q`) or the load cell is plugged in; a board that is powered off, reset or hung drops the rail through the normally-open relay:

| Part | What it does |
|---|---|
| Stop temperature | **Case 58.4 °C** (R26 limit 60 °C, `thermal.md` section 3, minus the thermocouple's U 1.6 °C [D `test_plan.py`]). **Mount 48.4 °C** with bare PETG (limit 50 °C, `thermal.md` section 3 and R26 note); with the C1 metal sleeves fitted use 58.4 °C (limit 60 °C): send `l 58.4 58.4` to the probe board after each power-up and pass `--stop-mount-c 58.4` to the logger. A case thermocouple that reads NaN (unplugged, open) trips at once in the logger; on either fitted channel the probe board trips after 3 bad reads in a row (0.3 s). The board's thresholds can be changed with `l <case> <mount>`; the logger's with `--stop-case-c` / `--stop-mount-c`. With the C1 sleeves, set both to 58.4 °C |
| Case bead | On the centre of the exposed top face of the aluminium middle shell, 14 mm behind the seat, under Kapton tape and a dab of paste (`thermal.md` section 6). Mount bead: in the 1 mm hole under one ear (C3). If the C3 hole is not drilled, the cutoff has no mount channel: set `HAVE_TC2 = false` and keep the case stop only |
| What trips | **1. Probe board:** it opens a normally-open relay in the servo's +6.5 V line (pin `PIN_RAIL_RELAY`) and prints `# CUTOFF case <C> mount <C>`. A dead or reset probe board also drops the rail. The gripper's ESP32 stays powered from its own supply. **2. Logger:** `gripper_log.py --probe-port` sees the same temperature lines, sends `R` (jaw opens), prints `THERMAL STOP ...` and ends the run. It also stops if the probe board is silent for 5 s |
| Re-arm | The rail stays off. Wait until both beads read under 45 °C, send `e` to the probe board (it prints `# RAIL ON`), then restart the block |
| Log lines | `TP-06_temp.csv` keeps every probe line (`ms,force_N,case_C,mount_C,rail_on`); the `# CUTOFF` line and the logger's `THERMAL STOP` message are the record. Enter the stop in the data sheet notes |

**Do not start the unattended block until all four checks pass, and write the result on the data sheet:**

1. Ice-point check of both beads within ±1 °C (TP-07 step 1).
2. Send `e`: the probe prints `# RAIL ON` and the servo powers.
3. Heat test: dip the case bead in 60 °C water (kettle water cooled, checked with the DMM thermocouple or a kitchen thermometer). Within 1 s the probe prints `# CUTOFF`, the rail drops and the servo goes limp. Re-arm after cooling.
4. Unplug test: pull the case thermocouple; within 3 samples the probe prints `# CUTOFF` (NaN). Plug it back.

No cutoff test, no unattended run: write the four results in the `cutoff_checks_1to4_ok` column of the sheet before you leave the room, and photograph the `# CUTOFF` line from check 3. The software cannot see the relay, so this step is on you. If the relay or probe board is not available, run only attended blocks (someone in the room, hand on the supply switch).

## Setup

```
 Front view. The ply is held taut-ish, not tight, so each close grips fresh-looking cloth.

          clamp ---- fabric strip ----
                       |   |
               finger A|ply|finger B
                       |   |
          clamp ---- fabric strip ----      thermocouple bead on the servo case
```

1. Run TP-08 part B and TP-12 first if they have not been run: checkpoint 0 needs their methods.
2. The probe board prints `ms,force_N,case_C,mount_C,rail_on`; the logger below reads it (`--probe-port`). Plug the servo's +6.5 V through the relay, send `e`, and pass the four checks above.

## Steps

**A. Checkpoint (at 0, 1e3, 5e3 and 1e4 cycles). About 25 min.**

1. Fabric out. `C` on bare pads, three times; record each `EVT CAL_THETA_C0` and the mean.
2. Backlash at the tip pad by the TP-08 part B method (dial on knuckle B, scaled to the pad).
3. Probe in (TP-01 step 6), `C`, then three `G 5` holds of 10 s; record the lowest probe hold mean. Probe out.
4. Finger B stiffness at one point: TP-12 method, one load of 510 g (5.0 N) on the saddle; k = 5.0 N / tip deflection.
5. Look with the loupe at: every rib corner of both fingers (whitening, cracks), the gear teeth at both face ends (wear steps, pitting, a polished band, M22), both knuckle pins and sleeves (play, dust), the dog coupling. Photograph each at the same angle every checkpoint.
6. Fabric back in. `C` on bare pads (fabric pushed clear), then fabric between the pads.

**B. Cycle blocks.**

7. Run, for the block to the next checkpoint (`--n 1000`, then `--n 4000`, then `--n 5000`):
   `python docs/gripper/test/tools/gripper_log.py --port <gripper port> --out TP-06_log.csv --sequence cycle --n 1000 --hold 2.0 --probe-port <probe port> --probe-out TP-06_temp.csv`
   Each cycle: `G 5`, wait for HOLD, hold 2.0 s, `R`, wait for RETRACT, `A`, `R`, wait for IDLE. It prints every 100 cycles and **stops on the first FAULT**, printing the cycle number.
8. Time the first 100 cycles; recompute the block's duration.
9. Watch the case temperature for the first hour. It should level off (thermal time constant about 7.5 min, `dyno.md` 1 [A]). If it levels under 55 °C, leave the run. The cutoff stops the run at 58.4 °C (case) or 48.4 °C (mount) by itself; if it trips, run TP-07 first.
10. Replace the fabric strip at each checkpoint (worn cloth grips differently).

## Data to record

Per checkpoint: cycles done, backlash at the tip pad, mean θ_c0, lowest probe hold, finger k, visible damage (with photo names), faults since the last checkpoint (from the log: any `FAULT_`, `FORCE_SAT`, `NO_CONTACT`, `FSR_SLIP`, `FSR_LOST`), notes: peak case temperature, cycle time.

## Calculation

- Growth from checkpoint 0: Δbacklash, Δθ_c0, Δhold, Δk.
- Count events: `python docs/gripper/test/tools/analyze_log.py faults TP-06_log.csv` lists every fault; count `FSR_SLIP` and `FORCE_SAT` lines in the CSV by text search.

## Pass / fail

- **Pass:** 1e4 cycles with no `FAULT_` event; no crack on any rib corner, tooth or pin; Δbacklash ≤ 0.06 mm at the pad (0.1 mm [A] − the dial's U scaled to the pad, about 0.04 mm at r_d 40 mm); lowest hold ≥ 5.10 N (5.0 + probe U); |Δθ_c0| ≤ 0.5° [A].
- **Indeterminate:** Δbacklash 0.06-0.14 mm, or hold 4.90-5.10 N.
- **Fail:** any FAULT, crack, Δbacklash > 0.14 mm, hold < 4.90 N, or |Δθ_c0| > 0.5° on the 3-reading mean.
- Report Δk; k must stay inside R12, 0.88-1.63 N/mm (TP-12).
- Sign-off: R25 "analysis + screen passed" or "screen failed at N cycles", never "R25 demonstrated".

## Hazards

- **Unattended motion:** the jaw closes at up to 120 °/s about once every 3-4 s for hours. Put a guard (a box) over the jaw and a "running" sign on it. Nothing else in the vise.
- **Heat:** the cutoff above stops the run at a 58.4 °C case. A stalled servo heats fast; the over-current trip (TP-05) must have passed before an unattended run, and so must the four cutoff checks.
- Overnight supply: use a bench supply with a current limit of 4 A, not a bare battery.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| Backlash grows steadily | Tooth flank wear (printed PA6-CF), or sleeve wear on the pins | Gear owner (M22, `gears.md` wear model) |
| θ_c0 drifts one way | Finger creep (TPU) or pad wear | Finger owner |
| Hold drops toward 5.0 N | Finger softening (k falls) or FSR drift; re-run TP-01 `CALF` | Controls / finger owner |
| Crack at a rib corner | Rib corner stress (the × 0.27 hot spot is real) | Finger / FEA owner: R25 fails |
| `FAULT_OVERCURRENT` during cycling | Hold trip at 3.6 A (`STALL_CURRENT_HOLD_A`) too near a hot servo's hold current (`controls.md` O6) | Firmware / electrical owner |
<!-- procedure-body:end -->
