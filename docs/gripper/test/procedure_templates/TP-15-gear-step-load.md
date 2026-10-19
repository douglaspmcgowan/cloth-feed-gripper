**What it proves:** that the printed gear sector pair carries the grip torque (LC1, 0.38 N·m) up to a full servo stall through the mesh (LC3, 2.11 N·m) without cracking or opening up its backlash (R13), and, taken on to failure, what the real safety factor is (M17). It also shows how evenly the teeth touch across the face (M21). **Destructive:** use a spare pair, never the one that goes on the gripper. About 60 min. Data sheet: [`../datasheets/TP-15.html`](../datasheets/TP-15.html) (CSV: `TP-15.csv`).

| | |
|---|---|
| Requirements | R13 (strong gear profile); measurements M17 (printed pair strength and life), M21 (contact pattern across the face) |
| Pass | Holds every step from 0.38 to 2.11 N·m for 60 s with no crack and backlash growth ≤ 0.1 mm at the pad [A] |
| Instrument | Lever + hanger masses, torque ±1 % [D]; dial indicator, backlash U = 0.026 mm [D `test_plan.py`]; loupe or phone macro |
| Sample size | 1 destructive pair (2 if PETG is still a candidate): the cost of a pair |

## Expected values

| Quantity | Expected | Source |
|---|---|---|
| Gear under test | PA6-CF, m 1.5, z 19, 25° pressure angle, face 8 mm, centre distance 28.5 mm, dried and annealed | [D] `analysis/gears.md` section 0; `params.json` `gear` |
| Root safety factor at LC1 / LC2 / LC3 / shock | 5.09 / 2.82 / 1.61 / 1.59 | [D] `gears.md` section 5 |
| Root stress at LC3 | 51.1 MPa against 82.4 MPa allowable | [D] `gears.md` section 0 |
| Root SF at the worst jam 2.69 N·m / jam at 2.6× rotor inertia 3.60 N·m | 1.33 / 1.04 | [D] `dyno.md` section 0 |
| Predicted root failure torque | about 3.4 N·m | [D, equation] SF 1.61 × 2.11 N·m |
| Backlash, design (range) | 0.25 (0.16-0.34) mm at the pitch circle = 1.01°, 1.14 mm at the 65 mm pad radius (0.73-1.55 mm) | [D] `gears.md` 5; pad value [D, equation jt/r_pitch × 65, r_pitch 14.25 mm] |
| Backlash growth from 1e5 grips of wear | 0.13 mm worst | [D] `gears.md` 5 |
| PETG (if tested) | not recommended; best PETG option static SF 0.90 at the jam | [D] `gears.md` 0, `dyno.md` 0 |

## Equipment

Spare sector pair (knuckles A and B) on their pins in a spare housing and front plate built to the pinned layout (`tolerance_stacks.md` fix 9: 3 mm pins pressed into both plates, line-reamed, bronze sleeves, shims to 0.3 mm end play); a printed lever for knuckle B with a hanger notch at 100.0 mm from pin B and a dial pad at 65.0 mm; a locking pin or clamp for knuckle A; hanger and masses to about 4.5 kg (slotted masses or water bottles weighed on the balance); dial indicator; loupe or phone macro lens; blue layout dye or a marker; catch tray; eye protection.

## Fixture

```
 Front view. Knuckle A locked; masses hang on knuckle B's lever.

       front plate (clamped in the vise, pin axes horizontal)
   +--------------------------------------------------+
   |   pin A  (A)  locking pin through knuckle A's     |
   |          \/\/  arm into a drilled hole in the     |
   |   pin B  (B)  plate                               |
   +----------|---------------------------------------+
              +======================o========o   lever on knuckle B, horizontal
              |<------- 65.0 ------->|        |   o at 65 mm: dial plunger (backlash)
              |<---------- L = 100.0 -------->|   notch at 100 mm: hanger
                                              |
                                           [masses]     catch tray below
```

- The lever bolts to knuckle B's finger root (cheeks, pegs and M2) in place of the finger.
- Balance the empty lever with its hanger on a knife edge to find its own moment about pin B: T_lever = m_lever·g·x_cg. It is part of every step's torque.

## Steps

**A. Before loading.**

1. Lock knuckle A: a 3 mm pin through its arm into a hole drilled in the plate, or clamp the arm to the plate.
2. **M21 contact pattern.** Paint dye (or marker) on 3 teeth of sector A. Hang the step-0 mass, lift it off, rock the lever twice through the backlash. Remove the lever and photograph the dye worn off the flanks under the loupe. Note how much of the 8 mm face carries contact and which end (toward the front plate or the housing). Clean off the dye.
3. **Backlash zero.** Lever level, dial plunger on the 65 mm pad. Push the lever gently up then down with about 0.1 N at the pad (a 10 g mass on and off is enough) [A]; the dial difference is the backlash at the pad, b₀. 3 readings.

**B. Steps to LC3 (R13).** Torque per step T = m·g·L + T_lever, with g = 9.80 m/s² and L = 0.100 m. The table gives the hanger mass that makes the step torque on its own; subtract T_lever/(g·L) from each.

| Step | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 (LC3) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Torque N·m | 0.380 | 0.456 | 0.547 | 0.657 | 0.788 | 0.946 | 1.135 | 1.362 | 1.634 | 1.961 | 2.110 |
| Hanger kg | 0.388 | 0.465 | 0.558 | 0.670 | 0.804 | 0.965 | 1.158 | 1.389 | 1.667 | 2.001 | 2.153 |

[D, equation: T_n = 0.38 × 1.2ⁿ, last step capped at LC3 2.11 N·m (`gears.md` 0: full DS3218MG stall at 6.8 V through the mesh); m = T/(g·L).]

4. Lower the step's masses onto the hanger without a drop. Hold 60 s. Watch and listen: a click, a sudden lever drop, or creep is a tooth event.
5. Lift the masses off. Measure the backlash at the pad as in step 3 (b_n). Inspect the loaded flanks and roots of the teeth in mesh with the loupe: white stress marks (PA6-CF whitens under strain), cracks at the tooth root, tip rolled over or flattened.
6. Repeat for every step to LC3.

**C. To failure (M17), only if this pair is spare.**

7. Continue in +10 % steps from LC3: 2.321, 2.553, 2.808, 3.089, 3.398, 3.738, 4.112 N·m (hanger 2.368, 2.605, 2.866, 3.152, 3.468, 3.814, 4.196 kg), 60 s each, the same checks. Stop when a tooth breaks, the lever drops, a plate cracks, or a pin bends. Record the last torque held (T_held) and the torque at failure (T_fail), and what broke first.
8. **Optional, `dyno.md` section 8 (M17):** on a second spare assembled gripper, 20 drop-jams: block finger B's knuckle arm with a rigid stop at about 12° jaw angle, send `G 5` from the open stop (pre-close at 120 °/s), let the firmware fault (`FAULT_OVERCURRENT` or `TIMEOUT`), send `H` to re-home. Inspect the teeth after every 5.

## Data to record

Per step: step, torque_Nm (including T_lever), hanger_kg, held_60s (yes/no), backlash_after_mm, damage (none / whitening / crack / tooth broken / other part), notes (M21 pattern, photo file name). Also T_lever, b₀ and the failure description.

## Calculation

- Backlash growth Δb = b_n − b₀.
- Measured safety factors: SF_LC3 = T_fail / 2.11; SF_jam = T_fail / 2.69; SF_jam,2.6 = T_fail / 3.60. Compare with the predicted 1.61 / 1.33 / 1.04.

## Pass / fail

- **R13 pass:** every step through 2.11 N·m held 60 s, no crack (whitening alone is noted, not a fail), and Δb ≤ 0.1 mm at the pad [A] after LC3 (Δb ≤ 0.074 mm clears U; 0.074-0.126 is indeterminate).
- **Fail:** a crack, a broken tooth, or Δb > 0.126 mm at or below LC3.
- **M17:** report T_fail and the three SFs. SF_jam,2.6 < 1 means the 120 °/s jam can break the pair: `dyno.md` then recommends the robust PA6-CF x 0.25 b 10 profile or a slower pre-close.
- **M21:** report the contact length across the face. Contact on less than half the face [A] at LC1 means the flanks edge-load more than the derived F_βy 0.067 mm assumes (`gears.md` 8).

## Hazards

- **Falling masses:** when a tooth breaks the lever and up to 4.2 kg drop. Catch tray under the hanger at 50 mm drop height, feet and hands clear, eye protection (printed teeth and carbon-fibre fragments fly).
- Lower masses by hand; never drop them onto the hanger.
- Do not use the pair or plates from this test on the gripper afterwards.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| Tooth root cracks below LC3 | Wet PA6-CF (M23) or not annealed; low layer fusion | Gear owner |
| Backlash grows but no crack | Pins bend or plates yield, not the teeth; check pins with the square | Gear / mechanical owner |
| Contact only at one face end | Pin bores not parallel; re-ream the plates together (ASSEMBLY step 1) | Mechanical owner |
| Breaks between LC3 and 3.6 N·m | Pair is fine for stall but not for the fast jam: switch to the robust profile (`dyno.md` 0) | Gear owner |
