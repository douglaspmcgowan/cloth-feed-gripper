**What it proves:** the calibration finds the same contact angle θ_c0 every time (R21), the jaw opens to +20° (R18 open stop), how much free play the gears and the dog coupling leave at the tip pad, and the servo's smallest step (M8, deadband). It also builds the protractor and pointer that TP-03 and TP-05 use. About 25 min plus 15 min to build. Data sheet: [`../datasheets/TP-08.html`](../datasheets/TP-08.html) (CSV: `TP-08.csv`).

| | |
|---|---|
| Requirements | R21 (calibration stores θ_c0), R18 (open stop; the floor is checked in TP-04); measurement M8 (servo deadband) |
| Pass | R21: all 10 θ_c0 inside −4…+4°, spread (max − min)/2 ≤ 0.27° (one deadband) [A]. R18: open stop +20 ± 1° |
| Instrument | Event log θ_c0 to 0.01°; printed protractor read off video or by eye, U = 0.58°; dial indicator 0.01 mm, U = 0.026 mm; calipers U = 0.05 mm; feeler gauges [D `test_plan.py`] |
| Sample size | 10 calibrations (estimates the scatter itself); 3 open-stop readings; 3 backlash readings per knuckle |

## Expected values (from the analysis; a result far from these means a setup error)

| Quantity | Expected | Source |
|---|---|---|
| θ_c0, bare pads | −0.68 to −1.08° | [D] `test_plan_out.json` → `expected.close` (firmware sim). `dyno.md`'s −2.0° is a different model (command angle with lag, older firmware): ignore it |
| Gear backlash at the pitch line | 0.158-0.343 mm (pinned, bushed layout, T07-bushed) | [D] `tolerance_stacks.md` 1 item 6 |
| Gear backlash at the tip pad | 0.72-1.56 mm = 0.158-0.343 × 65 / 14.25 (r_c 65 mm; pitch radius 14.25 mm for m 1.5, z 19) | [D, equation] `gears.md` 0, 6 |
| Dog-coupling lash, knuckle A against the servo | ±0.01 rad → 1.3 mm total at the pad (2 × 0.01 × 65) | [A] `tolerance_stacks.md` fix 9; [D, equation] |
| Free play of knuckle B at the pad | about 2.0-2.9 mm plus the servo's own gear play (not modelled) | [D, sum of the two rows above] |
| Open stop | +20° (`JAW_OPEN_DEG`); tip-pad gap 46.9 mm | [D] `config.h`; `finger.md` 6.1 |
| Gap at θ = 0 (rigid pads) | 1.0 mm (definition, DB R18) | DB R18 |
| Servo deadband | 3 µs = 0.27° | [S] `actuators.csv` A17 via `config.h` `SERVO_DEADBAND_US`; 11.1 µs/° (`controls.md` 4.1) |

## Equipment

Gripper in the vise with its 6.5 V rail, laptop with `gripper_log.py` and the Arduino IDE or `arduino-cli`, dial indicator with a magnetic or clamp base, calipers, feeler gauges (1.0 mm), the protractor and pointer below, a 0.5 N push (a fingertip on a 50 g spring scale, or a light touch), a rubber band, phone camera.

## The protractor and pointer (build once, about 15 min)

```
 Front view. Card glued to the front plate, centre on the end of pin A.

                 +25 . . . . . . . . . . . -10     1 deg marks on a 100 mm radius
                     \       pointer       /       (1 deg = 1.75 mm of arc)
                      \     (100 mm)      /
                       \       |         /
                        \      |        /
                         [ pin A ]=====[ pin B ]
                         knuckle A      knuckle B
```

- Print an arc of radius 100 mm with 1° marks from −10° to +25° on paper at 100 % scale; check one 10° span with calipers (17.4 mm chord). Glue it to card and tape it to the front plate with its centre on pin A.
- Pointer: a 100 mm strip of 2 mm PETG (or a steel rule) clamped to finger A's root block, its edge in line with pin A. The zero is set in step 2.

## Steps

**A. Test sketch: zero, θ = 0 gap, deadband (M8). This replaces the gripper firmware until step 6.** The firmware has no go-to-angle command. Save this as `TP08_jog/TP08_jog.ino`, upload it to the gripper's ESP32 (Serial Monitor at 115200 baud, no line ending):

```cpp
#include <ESP32Servo.h>
const int PIN = 18, DIR = 1;              // PIN_SERVO_PWM, SERVO_DIR in config.h
const float US_PER_DEG = 2000.0 / 180.0;  // us = 500 + (90 + DIR*theta)*2000/180
Servo s; int us = 1500 + DIR * 222;       // start at +20 deg, the open stop
void setup() {
  Serial.begin(115200); s.setPeriodHertz(50);
  s.attach(PIN, 1200, 1900); s.writeMicroseconds(us);
}
void loop() {
  if (!Serial.available()) return;
  int c = Serial.peek(), n = us;
  if (isdigit(c)) n = Serial.parseInt();
  else { Serial.read(); if (c == '+') n++; else if (c == '-') n--; else return; }
  float th = DIR * (n - 1500) / US_PER_DEG;               // jaw angle for this pulse
  if (th < -0.9 || th > 20.0) { Serial.println("refused"); return; }  // pads stay apart
  us = n; s.writeMicroseconds(us);
  Serial.print(us); Serial.print(" us, theta "); Serial.println(th, 2);
}
```

It assumes `SERVO_DEG_AT_JAW0` 90 (θ = 0 at 1500 µs); if `config.h` differs, replace 1500 with 500 + SERVO_DEG_AT_JAW0 × 2000/180. Type a number (for example `1600`) to jump, `+` / `-` to step 1 µs.

1. Send `1500` (θ = 0). Measure the tip-pad gap with feeler gauges: record as the θ = 0 gap.
2. Step with `+`/`-` until a 1.0 mm feeler between the pads just drags. Rotate the protractor card so the pointer reads 0°. That makes 0° the DB R18 definition (rigid pads 1 mm apart).
3. Deadband: send `1600` (θ ≈ +9°). Stretch a rubber band so it pulls finger A gently open (keeps the dog and gear lash on one side). Put the dial on the pointer tip.
4. Press `-` once at a time and note each press after which the dial moves; repeat for 10 moves. The mean number of µs between moves is the deadband (expected 3 µs, 0.47 mm at the pointer tip).
5. Reverse (`+`) and count presses until the dial moves back: deadband plus the servo's internal play.
6. Re-flash the gripper firmware: `arduino-cli compile --fqbn esp32:esp32:esp32 firmware/gripper` then `arduino-cli upload -p <port> --fqbn esp32:esp32:esp32 firmware/gripper`. Remove the rubber band.

**B. Calibration repeatability (R21), 10 times.**

7. `python docs/gripper/test/tools/gripper_log.py --port <port> --out TP-08_log.csv`. Bare pads, nothing in the jaw. Send `C` ten times, waiting for `ENTER_IDLE` each time. Record each `EVT CAL_THETA_C0 <ms> <deg>`. Also note the boot log's `CAL_THETA_C0`.

**C. Backlash (jaw in IDLE at the open stop).**

8. Dial indicator square to finger B's root block (rigid), at a radius r_d from pin B measured with calipers (aim for 30-40 mm). Push the root block lightly closed (about 0.5 N), read; push lightly open, read. b_dial = the difference. Three times. If finger B rests on a stop or the limit switch when pushed open, record that and push only against the servo.
9. Repeat with the dial on finger A's root block (play of A against the servo: dog lash plus servo play).

**D. Open stop (R18), 3 readings.**

10. Three times: `H` (re-home to the open stop and recalibrate), wait for `ENTER_IDLE`. Read the protractor (photo square to the card) and measure the tip-pad gap with calipers. Do not use `G 5` here: on bare pads it squeezes pad on pad.

## Data to record

Per row: trial, θ_c0, θ = 0 gap (step 1), backlash at the tip pad (B; A in notes), open-stop angle, floor angle (lowest `th=` from TP-04), deadband in µs, notes (r_d, raw dial readings, open-stop gap, reverse count from step 5).

## Calculation

- R21 spread = (max − min)/2 of the ten θ_c0; also mean and s.
- Backlash at the pad: b_pad = b_dial × r_c / r_d, r_c = 65 mm. Gear backlash at the pad ≈ b_pad(B) − b_pad(A).
- Deadband in degrees = µs ÷ 11.1 µs/°.

## Pass / fail

- **R21** (U of a θ_c0 reading = 0.01°, the event-log resolution [A]): **pass** if every θ_c0 is within −3.99…+3.99° and the spread (max − min) ≤ 0.26°. **Fail** if any θ_c0 is outside −4.01…+4.01° or the spread ≥ 0.28°. **Indeterminate** otherwise (a reading within 0.01° of a limit): recalibrate 10 more times.
- **R18 open stop:** pass if all three readings are within 19.4-20.6° (20 ± (1 − U 0.58)); indeterminate within 18.4-21.6°; fail outside. The floor (θ ≥ θ_c0 − 6.2°, never below −10.2°) is judged in TP-04.
- Backlash and deadband (M8) are measurements: report against the expected values. A gear backlash over 1.56 mm at the pad, or under 0.72 mm (tight mesh), goes to the gear owner.

## Hazards

- **The test sketch has no force loop and no trip.** It refuses angles under −0.9° (pads touching) [D, equation from the θ_c0 range]; never edit that out. Keep the jaw empty while it runs.
- **Pinch:** jumps of many µs move the jaw at full servo speed (about 419 °/s). Step in small numbers near the pads.
- Re-flash the gripper firmware before any other procedure.

## If it fails

| Symptom | Likely cause | Tell |
|---|---|---|
| θ_c0 spread > 0.27° | FSR noise near 0.5 N, or knuckle pins rattling | Firmware owner (`controls.md` O2); mechanical owner |
| θ_c0 outside ±4° | Fingers mounted off angle, or `SERVO_DEG_AT_JAW0` wrong | Firmware owner (bench step 1) |
| Open stop off by > 1° | Horn fitted one spline tooth off, or `SERVO_DEG_AT_JAW0` | Firmware / assembly owner |
| Gear backlash > 1.56 mm at the pad | Pin bores not line-reamed, sleeves loose (fix 9) | Mechanical / tolerancing owner |
| Deadband > 5 µs | Servo worn, or 3.3 V pulse marginal (M16) | Actuator / electrical owner |
