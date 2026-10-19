**What it proves:** that the DS3218MG makes at least {{tp13.torque_limit}} at the {{tp13.rail_low_limit}} low end of the rail, so the 5 N hold uses no more than 40 % of stall (R16), and that the gripper's 6.5 V rail holds up during a stall (R27). It also measures the stall current, which decides between the two dyno fits (M6). The margin is only 2 %, so it is also run at 6.50 V. About 35 min, on the bare servo before assembly. Data sheet: [`../datasheets/TP-13.html`](../datasheets/TP-13.html) (CSV: `TP-13.csv`).

| | |
|---|---|
| Requirements | R16 (hold ≤ 40 % of stall), R27 (power rail); measurements M6 (stall torque and current), M16 (3.3 V pulse) |
| Pass | R16: stall torque at {{tp13.rail_low_limit}} ≥ {{tp13.torque_limit}} + U on every trial, and the TP-01 hold current ≤ 0.40 × stall current. R27: rail 6.5 ± 0.15 V, ≥ {{tp13.rail_low_limit}} during a stall, 1000 µF at the servo, common ground, supply ≥ 3 A |
| Instrument | 50 mm lever on the TAL220 load cell; U = 1.6 % of T [D `test_plan.py`]. DMM U = 0.06 V at 6.5 V; current U = 0.021 A |
| Sample size | 3 stalls at each voltage, ≤ 2 s each (the winding heats about 3 K per 0.2 s) |

## Expected values

| Quantity | Expected | Source |
|---|---|---|
| Stall torque at 6.50 V / {{tp13.rail_low_limit}} | 2.051 / 2.023 N·m | [D] `test_plan_out.json` → `expected.stall` (dyno rail sensitivity) |
| Force on the 50 mm lever at 6.5 V | 41.0 N | same |
| Stall current at 6.50 V, Fit B / Fit A | 2.10 / 3.75 A | [D] `analysis/dyno.md` section 5 |
| Stall current at {{tp13.rail_low_limit}}, Fit B / Fit A | 2.05 / 3.74 A | same |
| Hold current at 6.5 V, Fit B / Fit A | 0.79 / 1.35 A → ratio 0.38 / 0.36 | [D] `dyno.md` 5; ratio [D, equation] |
| Winding to 125 °C at full stall | 8.1-11.1 s (Fit A, 40 / 25 °C) | [D] `expected.stall` |
| Stall needed for the 40 % rule | {{tp13.torque_limit}} (20.2 kg·cm) | [D] `torque_and_actuator.md` section 0 |

## Equipment

Spare-able DS3218MG (the one that will be fitted, or the spare), bench supply ≥ 7 V 4 A with current readout, DMM (also on its 10 A range), scope, the pinch-probe load cell and `../tools/probe/probe.ino` reader (calibrated in TP-01 step A), a second ESP32 for the test sketch, a printed PETG or aluminium lever, the gripper's own 6.5 V buck and 1000 µF capacitor, calipers, vise.

## Fixture

```
 Top view. Servo clamped by its ears; lever on the horn; tip presses the cell's free end.

   [ vise ]                      L = 50.0 mm (horn centre to contact)
   +--------+   horn  o==========================( )  rounded tip (M3 pan head)
   | servo  |----(+)                              |  pushes along the cell's
   | DS3218 |                                     v  bending direction
   +--------+                 [M5][M5]==============[M5][M5]  TAL220, free end
                              [ fixed-end block, clamped ]
 Lever square to the cell within 3 degrees at contact.
```

- Lever: 50.0 mm from the horn's centre to the centre of the rounded tip; caliper it (3 readings). Bolt it to the 25T horn.
- The cell is used in its normal bending direction, fixed end clamped, load through the free-end screw holes' centre line.

## Test sketch (replaces the gripper firmware on the second ESP32 for this test)

The gripper firmware has no go-to-angle command, so this sketch drives the servo. Type a pulse width (µs) to move; `p <µs>` pushes for 1.5 s and returns.

```cpp
#include <ESP32Servo.h>
Servo s;
int base = 1500;
unsigned long tEnd = 0;
bool pushing = false;

void setup() {
  Serial.begin(115200);
  s.attach(18, 500, 2500);
  s.writeMicroseconds(base);
}

void loop() {
  if (Serial.available()) {
    bool push = (Serial.peek() == 'p');
    if (push) Serial.read();
    int us = Serial.parseInt();
    if (us >= 500 && us <= 2500) {
      s.writeMicroseconds(us);
      if (push) {
        tEnd = millis() + 1500;
        pushing = true;
        Serial.printf("PUSH %d %lu\n", us, millis());
      } else {
        base = us;
        Serial.printf("AT %d\n", us);
      }
    }
  }
  if (pushing && (long)(millis() - tEnd) >= 0) {
    s.writeMicroseconds(base);
    pushing = false;
    Serial.println("BACK");
  }
}
```

## Setup

1. Servo signal to GPIO 18 of the test ESP32 (3.3 V logic), servo power from the bench supply, grounds joined. 1000 µF across the servo leads at the connector.
2. Supply current limit 4.5 A (a 5 A bench supply; EQUIPMENT.md). Set the voltage with the DMM **at the servo connector**, servo idle: 6.50 V.
3. Probe reader running; tare it with the lever clear.

## Steps

**0. Calibrate the cell at the lever contact point.** TP-01 calibrated the probe to 10 N at the P2 mark; here the lever presses the bare cell at a different point and up to about 45 N. Clamp the cell as it will be used, hang 1, 2, 3, 4 and 4.6 kg (about 10-45 N) from a thread at the exact point the lever tip will touch, and fit counts to newtons again. Use this fit for TP-13 only.

**A. Find contact.**

1. Send pulses in 10 µs steps toward the cell until the probe reads > 0.2 N, then back off 10 µs: this is the contact pulse P_c. If the servo follows the commands, M16 passes (3.3 V pulse accepted).

**B. Stall at 6.50 V, then {{tp13.rail_low_limit}} (R16, M6).**

2. Scope on the servo connector, AC-coupled, 1 V/div, trigger on a falling edge; DMM in series (10 A range) or read the supply.
3. Send `p <P_c + 100>` (about 9° past contact, enough for full drive [A, `dyno.md` 1: full duty at 3° error]). During the 1.5 s push record: probe peak and plateau force, rail current, the scope's lowest rail dip.
4. Wait 30 s. Repeat for 3 trials.
5. Reset the supply to {{tp13.rail_low_limit}} at the connector. 3 more trials, 30 s apart.

**C. The gripper's own rail (R27).**

6. Replace the bench supply with the gripper's buck (fed as in use) and its 1000 µF capacitor. Set the buck to 6.50 V with the DMM at the servo connector. Record it.
7. One push as in step 3. Record the scope minimum (DC level from the DMM minus the AC dip).
8. Inspect: 1000 µF (or larger) electrolytic at the servo end of the rail, polarity right; continuity from ESP32 GND to servo-rail GND (DMM beeper); the buck's and supply's rated current from their labels.

## Data to record

Per trial: trial, rail_set_V, lever_mm, force_N (plateau), torque_Nm, rail_A, rail_min_V, pulse_us (the push pulse), notes (peak force, P_c, case warmth). Add rows for the buck setting, the capacitor, the ground check and the supply rating, and copy the TP-01 HOLD current (the `ST` lines' `I=` in HOLD).

## Calculation

- **T = F·L** with F the plateau force (N) and L the measured lever (m).
- Per voltage: mean T, s; tolerance lower bound mean − 5.31·s (n = 3).
- Hold ratio = I_hold (TP-01, `I=` in HOLD at 6.5 V) / I_stall (mean at 6.50 V).
- Supply sizing: required ≥ max(3 A, 1.3 × I_stall) (DB R27 rule).

## Pass / fail

- **R16 torque:** pass if every {{tp13.rail_low_limit}} trial ≥ {{tp13.torque_pass}} (1.98 + U) **and** the lower bound ≥ 1.98; indeterminate if any trial is within 1.948-2.013; fail if any is below 1.948. Also report the 6.50 V trials against {{tp13.torque_limit}} and 2.051 expected.
- **R16 current:** ratio limit 0.40. U of the ratio is about 2.8 % of its value (two current readings, U 0.021 A each at 1.4 A and 2.1 A; check with `analyze_log.py judge --value <ratio> --limit 0.40 --u <ratio × 0.03> --side upper`). **Pass** if ratio + U ≤ 0.40, **fail** if ratio − U ≥ 0.40, else **indeterminate** (measure the hold current again at a second force).
- **M6:** stall current near 2.1 A means Fit B; near 3.75 A, Fit A (then R26 heat is about 1.7× worse, `dyno.md` 8).
- **R27** (DMM U = {{tp13.rail_u}}): **pass** if the buck setting is 6.41-{{tp13.rail_pass}} (6.5 ± 0.15 less U), **fail** outside 6.28-{{tp13.rail_fail}} (6.5 ± 0.15 plus U), **indeterminate** in the strips between, and the stall minimum − 0.06 V ≥ {{tp13.rail_low_limit}}, the capacitor and common ground are present, and the supply is rated ≥ 3 A and ≥ 1.3 × I_stall. With Fit A that is 4.9 A, more than the 4 A that `dyno.md` 3 advises: report it.

## Hazards

- **Heat:** at full stall the winding reaches 125 °C in 8-11 s. Never stall longer than 2 s (the sketch returns at 1.5 s); 30 s between trials; stop if the case is too hot to hold.
- **Lever:** it can fling if the cell slips. Clamp everything; eye protection; stand out of the lever's plane.
- Do not set the rail above 6.65 V (the servo's 6.8 V maximum, `torque_and_actuator.md` 0). Do not load the cell past 120 N.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| Torque under {{tp13.torque_limit}} at {{tp13.rail_low_limit}} | Weak servo sample or rail sag at the connector; the R16 margin is gone; consider the DS3235 backup | Actuator owner |
| Rail dips under {{tp13.rail_low_limit}} | Long thin leads, small capacitor, or a 3 A supply with a Fit A servo | Electrical owner |
| Stall current about 3.75 A | Fit A: rail and heat sized too small | Electrical owner |
| Servo ignores the pulse | 3.3 V logic not accepted (M16): fit a 74AHCT125 | Electrical owner |
