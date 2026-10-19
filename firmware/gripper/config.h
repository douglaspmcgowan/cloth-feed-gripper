// config.h -- every tunable constant for the cloth-feed gripper firmware.
// Tags: [S] sourced (URL in docs/gripper/analysis/controls.md), [D] derived, [A] assumed (reversible).
// "DB" = docs/gripper/DESIGN-BASIS.md / cad/gripper/params.json (mcu, grip blocks). "TA" = analysis/torque_and_actuator.md.
// analysis/gripper/firmware_sim/fwconfig.py and analysis/gripper/dyno.py parse the numeric #defines below:
// keep ONE "#define NAME <literal number>" per line. Derived gains are computed in force_ctrl.h and checked
// against the same formula by analysis/gripper/firmware_sim/test_firmware_sim.py.
// Values changed by the W2b-1 firmware lane (2026-10-09) carry "W2b-1" and the reason; see controls.md 6.
#pragma once

// ---------------------------------------------------------------------------
// Board: ESP32 DevKitC (ESP32-WROOM-32, classic ESP32), FQBN esp32:esp32:esp32, core 2.0.17 [DB D6, A].
// Analog inputs on ADC1 only: ADC2 is unavailable while Wi-Fi runs [S: ESP-IDF ADC docs].
// ---------------------------------------------------------------------------
#define PIN_SERVO_PWM        18   // servo signal, 3.3 V logic (M16: add 74AHCT125 if the servo ignores it) [DB]
#define PIN_FSR_ADC          34   // ADC1_CH6, input-only; FSR divider node [DB]
#define PIN_SERVO_FB_ADC     32   // ADC1_CH4; optional servo pot tap (DS3230 MG has no 4th wire) [DB]
#define PIN_BUTTON           25   // START/STOP momentary to GND, INPUT_PULLUP [DB]
#define PIN_LIMIT_OPEN       26   // jaw-open limit switch to GND, INPUT_PULLUP [DB]
#define PIN_I2C_SDA          21   // INA219 current sense [DB]
#define PIN_I2C_SCL          22   // [DB]
#define PIN_STATUS_LED        2   // on-board LED on most DevKit clones; external LED + 330 R otherwise [A]

// Compile-time actuator branch. Default = PWM hobby servo through ESP32Servo.
// The DC gearmotor fallback (TA 3.3) is NOT implemented in this firmware: defining ACTUATOR_DC_GEARMOTOR is a
// compile error (gripper.ino). Its pins and constants below are kept for that future branch only.
// #define ACTUATOR_DC_GEARMOTOR

#define PIN_DRV_AIN1         16   // DRV8833 AIN1 (PWM)                 [DC branch, A]
#define PIN_DRV_AIN2         17   // DRV8833 AIN2 (PWM)                 [DC branch, A]
#define PIN_DRV_NSLEEP       13   // DRV8833 nSLEEP, high = enabled     [DC branch, A]
#define PIN_DRV_NFAULT        4   // DRV8833 nFAULT, open-drain low = fault [DC branch, S: Pololu 2130]
#define PIN_ENC_A            27   // encoder channel A                  [DC branch, A]
#define PIN_ENC_B            33   // encoder channel B                  [DC branch, A]

// Optional peripherals (1 = present). A missing INA219 is detected at boot and disabled, not faulted.
#define INA219_ENABLED       1    // [DB]
#define INA219_ADDR          64   // 0x40 default address [S: TI INA219 datasheet]
#define INA219_SHUNT_OHM     0.1  // Adafruit INA219 breakout shunt [S: Adafruit 904]
#define I2C_HZ               400000 // INA219 supports 400 kHz fast mode [S: TI INA219]
#define FB_ENABLED           0    // 1 only if a pot tap is added to the servo [A]
#define FB_MV_AT_JAW0        1650.0 // pot tap voltage at theta = 0 (bench-fit when FB_ENABLED) [A]
#define FB_MV_PER_DEG        12.0 // pot slope, signed (bench-fit) [A]
#define LIMIT_ENABLED        1    // jaw-open limit switch fitted [DB]
#define LIMIT_REQUIRED       0    // 1 = HOME faults if the switch is not closed at the open angle [A]

// ---------------------------------------------------------------------------
// Timing (all non-blocking, scheduled from micros()/millis()).
// ---------------------------------------------------------------------------
#define SERIAL_BAUD          115200 // [DB mcu.host_link]
#define SERIAL_TX_BUF        1024   // bytes; Serial.print never blocks on a status line [A]
#define SERIAL_LINE_MAX      64     // longest accepted command line [A]
#define ADC_PERIOD_US        1000   // FSR sampling, 1 kHz [A]
#define CONTROL_PERIOD_MS    20     // motion + force loop, 50 Hz = one servo PWM frame [D]
#define SERVO_PWM_HZ         50     // standard hobby-servo frame [DB, S]
#define STATUS_PERIOD_MS_DEF 0      // periodic status line; 0 = only on STATUS (STREAM <hz> changes it)
#define EVENT_QUEUE_LEN      16     // ring buffer slots [A]
#define EVENTS_PER_LOOP      8      // dispatch at most this many per loop pass [A]
#define EVENT_RESERVED_SLOTS 4      // queue slots only faults and timeouts may use [A]

// ---------------------------------------------------------------------------
// Servo (default actuator): DSServo DS3230 MG, 180 deg version [DB D4, S: actuators.csv A32].
// 26 / 30 kg*cm stall at 5.0 / 6.8 V, 0.20 / 0.18 s per 60 deg, 3.5 / 3.8 A stall (aifitlab), 3 us deadband.
// Rail: 6.5 V +/- 0.15 V buck, below the 6.8 V rating [TA section 1, A]. Values below are linear between the
// 5.0 V and 6.8 V datasheet points, evaluated at 6.5 V [D].
// Rev B.1 (2026-10-16): re-based from the DS3218MG (cad/gripper/out/parts.json servo_model; test_servo_constants.py).
// ---------------------------------------------------------------------------
#define SERVO_US_AT_0DEG     500    // pulse at servo 0 deg [DB mcu.pulse_us, S]
#define SERVO_US_AT_180DEG   2500   // pulse at servo 180 deg [DB, S]
#define SERVO_US_LIMIT_MIN   1200   // hard pulse clamp, last line of defence behind the jaw limits [A]
#define SERVO_US_LIMIT_MAX   1900   // [A]
#define SERVO_DEADBAND_US    3.0    // [A: A32 lists no deadband; A17's 3 us kept, measure M8]
#define SERVO_SPEED_DPS      327.0  // 60 deg / 0.1833 s at 6.5 V (interp. 0.20 s @5.0, 0.18 s @6.8, A32 [S]) [D]
#define SERVO_STALL_NM       2.876  // 29.33 kg*cm at 6.5 V (params.json servo.models, interp. 26 @5.0, 30 @6.8 [S]) x 0.0981 [D]
#define SERVO_STALL_A        3.99   // [D actuation_trade.md I_stall_sizing_A for A32; datasheet 3.8 A at 6.8 V]
#define SERVO_TAU_S          0.040  // small-signal position-loop lag of the servo [A, measure M8]
#define SERVO_INT_DELAY_S    0.010  // pulse decode + internal loop delay [A]

// Jaw coordinate theta (deg): + = open, 0 = rigid pads 1 mm apart, - = overtravel into the grip [DB R18].
// servo_deg = SERVO_DEG_AT_JAW0 + SERVO_DIR * theta. Set both when the horn is fitted (bench step 1).
#define SERVO_DEG_AT_JAW0    90.0   // horn fitted at mid-travel [A]
#define SERVO_DIR            1.0    // +1 or -1 by horn orientation [A]
#define JAW_OPEN_DEG         20.0   // [DB grip.theta_open_max_deg]
#define JAW_MIN_DEG          -10.2  // absolute backstop, at or below CAL_C0_MIN_DEG - JAW_FLOOR_BELOW_C0_DEG (-8.9), inside DB
                                    // R18 -11; it binds only without a calibrated contact. The force loop's floor is
                                    // relative (next line). Round 2: was -7.4, finger.md 6.3's 10 N angle as an absolute
                                    // floor, which moved with the contact-angle spread (T09F). Kept at round 2's -10.2 (the
                                    // 6.2 deg floor's value) when the floor moved to 4.9 [D]
#define JAW_FLOOR_BELOW_C0_DEG 4.9  // the force loop never commands below theta_c0 - this (never below JAW_MIN_DEG); 0 =
                                    // absolute JAW_MIN_DEG only. R15 8 N (T09, 2026-10-16): was 6.2 (10 N on the stiff
                                    // finger). 4.9 deg holds 8 N with the trip failed: tolerance stack T09F-relfloor8 PASS,
                                    // Cpk 1.46 (5.0 deg MARGINAL, 6.2 FAIL); it also bounds the trip peak (T09P-floor49
                                    // PASS). The squeeze cap (4.867 deg) still binds first: T09H unchanged, no new false
                                    // trip in any simulated grip (controls.md 6.4)
                                    // (controls.md 6.4) [D tolerance_stacks.md]
#define JAW_PREGRASP_DEG     6.0    // APPROACH parks this far above theta_c0 [A]
#define JAW_SLOW_ZONE_DEG    6.0    // slow search starts this far above theta_c0. The servo trails the 120 deg/s command
                                    // by ~7 deg, so the JAW only slows to ~21 deg/s by touch + 3 deg and <= 20 by + 2
                                    // (sim, controls.md 5.1; review issue 2). W2b-1: was 4.0 [D]
#define JAW_SPEED_FAST_DPS   120.0  // open / pre-close speed [A]
#define JAW_SPEED_NEAR_DPS   20.0   // last degrees before contact [DB R19]
#define JAW_SETTLE_MS        120    // POSITION_REACHED this long after the profile ends (no feedback) [A]
#define JAW_POS_TOL_DEG      1.5    // feedback agreement for POSITION_REACHED when feedback exists [A]
#define THETA_C0_DEFAULT     0.0    // contact angle before calibration [DB]
#define CAL_C0_MIN_DEG       -4.0   // calibrated contact must fall in this window, else SENSOR fault [A]
#define CAL_C0_MAX_DEG       4.0    // [A]
#define NO_CONTACT_MARGIN_DEG 3.0   // search this far past theta_c0; no touch -> NO_CONTACT (miss) [A]
#define CTRL_LAG_COMP_S      0.076  // FSR detection lag: mean frame wait 10 ms + SERVO_INT_DELAY_S 10 + SERVO_TAU_S 40
                                    // + FSR EMA tau 9.5 + servo half-deadband 0.135 deg at 20 deg/s 6.75 = 76 ms [D]
#define FAULT_BACKOFF_DEG    5.0    // FAULT entry opens the jaw this much to unload the train [A]
#define FAULT_BACKOFF_DPS    120.0  // ... at this command speed (2000 = one step; early-contact sweep, controls.md 4.4) [A]
#define JAW_MID_ZONE_DEG     12.0   // middle speed from theta_c0 + this down to the slow zone; 0 = off. R15 8 N: was 0; holds the
                                    // stiff-finger early-contact peak under 8 N at 4-10 deg (7.89 N worst; controls.md 4.4) [D]
#define JAW_SPEED_MID_DPS    45.0   // [D controls.md 4.4: 45 deg/s; 50 deg/s gives 8.11 N at 8 deg]

// Finger / transmission model (sets the force-loop gains; see force_ctrl.h) [DB grip block].
#define R_C_MM               65.0   // pivot to pad-normal line of action [DB D3]
#define FINGER_K_MIN_N_PER_MM 0.88  // tip stiffness window per finger [DB R12]
#define FINGER_K_MAX_N_PER_MM 1.63  // [DB R12]
#define FINGER_K_DEF_N_PER_MM 1.0   // [DB R12 default]
#define ETA_TRAIN            0.85   // mesh + pivots [DB]

// ---------------------------------------------------------------------------
// FSR 402 class (Interlink, Adafruit 166) on finger B, divider: 3V3 -- FSR -- node -- R_FSR_FIXED -- GND.
// Power-law fit to the Adafruit table (0.2 N 30k, 1 N 6k, 10 N 1k, 100 N 250R) [S][D]:
// R = FSR_FIT_R1N_OHM * F^(-FSR_FIT_EXP). test/fsr_divider.py prints the fit and picks R_FSR_FIXED_OHM.
// ---------------------------------------------------------------------------
#define ADC_VREF_MV          3300.0 // divider supply = ESP32 3V3 rail
#define ADC_V_LINEAR_MAX_MV  2450.0 // top of the ESP32 11 dB recommended range [S: ESP-IDF v4.4 ADC]
#define ADC_V_LINEAR_MIN_MV  150.0  // bottom of the same range [S]
#define R_FSR_FIXED_OHM      2700.0 // chosen by test/fsr_divider.py [D]
#define FSR_FIT_R1N_OHM      6109.0 // fit coefficient [D]
#define FSR_FIT_EXP          0.8195 // fit exponent [D]
#define FSR_EMA_ALPHA        0.10   // EMA at 1 kHz -> tau = 9.5 ms [D]
#define FSR_MV_NOISE_FLOOR   15.0   // below this (after zero offset) force = 0 [A]
#define FSR_NOISE_MV_RMS     8.0    // ADC noise used by the simulation [A, measure M11]
#define FSR_SPAN_DEFAULT     1.0    // per-unit scale; CALF <N> sets it from a known weight [A]
#define FSR_SPAN_MIN         0.5    // CALF accepted only inside [MIN, MAX] [A]
#define FSR_SPAN_MAX         2.0    // [A]
#define FSR_ZERO_MAX_MV      150.0  // unloaded reading above this at CAL -> ZERO_BAD fault [A]
#define FSR_SHORT_MV         2900.0 // raw node above this = shorted FSR -> SENSOR fault. 2900 mV = about 30 N on the
                                    // fsr_model.h curve, 3x the cap, and below the ~3.1 V 11 dB ADC saturation, so
                                    // a short is reachable (was 3150, O10). Gripper lane 2026-10-11 [D]
#define FSR_SHORT_MS         5      // ... for this many consecutive 1 kHz samples [A]
#define FSR_STUCK_MV_MIN     150.0  // stuck-ADC check: only above this node voltage (about 0.4 N), where a grip is held [A]
#define FSR_STUCK_MS         500    // raw reading unchanged (within FSR_STUCK_TOL_MV) this many samples -> FSR_STUCK.
                                   // Real ADC noise is 4-20 mV RMS (controls.md 3), so 500 equal samples cannot happen
                                   // on a live channel; a frozen conversion or a stuck mux does it [A]
#define FSR_STUCK_TOL_MV     0.5    // [A]

// ---------------------------------------------------------------------------
// Force thresholds (N) [DB grip.fsr]: touch 0.5, setpoint 5.0, slip < 3.0, trip 7.75, pad force <= 8 N (R15, ruling 2026-10-12).
// ---------------------------------------------------------------------------
#define F_TOUCH_N            0.5    // [DB]
#define F_HYST_N             0.15   // re-arm hysteresis for touch / slip / trip [A]
#define F_TARGET_DEFAULT_N   5.0    // [DB R14]
#define F_SET_MIN_N          1.0    // CLOSE <force> clamp [A]
#define F_SET_MAX_N          6.5    // CLOSE <force> clamp, 1 N below the trip. R15 8 N: was 7.0 [A]
#define F_SLIP_N             3.0    // [DB]
#define F_SLIP_MS            100    // below F_SLIP this long -> FSR_SLIP [A]
#define F_LOST_MS            150    // below F_TOUCH - hyst this long after touch -> FSR_LOST [A]
#define F_SOFT_LIMIT_N       7.5    // above this the controller steps back and bleeds the integrator [A]
#define F_TRIP_N             7.75   // R15 8 N cap with 0.25 N for the trip-to-stop overshoot; was 8.0 [DB D8, D]
#define F_TRIP_MS            20     // above F_TRIP this long -> FSR_OVER -> FAULT [A]
#define F_CAP_N              10.0   // never exceeded; sized for 9.5 N (R15 is 8 N: sizing it for 8 N drops R14 to 31 %, controls.md 6.4) [DB R15]
#define F_CAP_MARGIN_N       0.5    // the squeeze cap is sized for F_CAP_N - this on the stiffest finger: with the gain
                                    // schedule the loop reaches the cap faster, and a 50 %-reading FSR then peaked at
                                    // 10.16 N on the linear W2b-1 plant (controls.md 5; O4 asked for this margin) [D]
#define F_BAND_N             0.5    // FSR_TARGET band: sp - 0.5 < F < sp + CTRL_I_DB_HI_N + 0.5 [A]
#define F_SETTLE_MS          100    // time in band before FSR_TARGET [A]
#define F_RAMP_NPS           100.0  // setpoint ramp, 0.5 -> 5 N in 0.045 s (the servo lag then dominates). W2b-1: was 25;
                                    // feedforward-only during the ramp, so no overshoot cost (controls.md 4) [D]

// ---------------------------------------------------------------------------
// Force PI (outer loop). Output u = squeeze angle past the touch angle (deg, + = closing).
// SIMC (Skogestad 2003) on FOPDT: K = stiff-finger gain, tau = SERVO_TAU_S, theta = CTRL_DELAY_S.
// Kp = tau / (K (tau_c + theta)), Ti = min(tau, 4 (tau_c + theta)). Computed in force_ctrl.h.
// Feedforward u_ff = F_sp / K_stiff: never over-squeezes a softer finger; the integrator adds the rest.
// ---------------------------------------------------------------------------
#define CTRL_DELAY_S         0.030  // 10 ms mean PWM-frame ZOH + 10 ms servo decode + 10 ms EMA [D/A]
#define CTRL_TAU_CL_S        0.060  // SIMC closed-loop target (2 x theta), checked by test/sim_force.py [D]
#define CTRL_U_MIN_DEG       -2.0   // may back off 2 deg behind the touch angle [A]
#define CTRL_RATE_LIMIT_DPS  60.0   // squeeze-rate limit in force mode [A]
#define CTRL_I_DEADBAND_N    0.30   // legacy: read only by analysis/gripper/dyno.py (its own PI model, now stale;
                                    // controls.md 7 O5). The firmware does not use it.
#define CTRL_I_DB_HI_N       0.60   // asymmetric integrator deadband: integrate while F < F_sp or F > F_sp + this.
                                    // Servo deadband 0.27 deg = 0.5 N at stiff K; holds F in [F_sp, F_sp+0.6] so R14
                                    // (>= 5 N) is met. W2b-1: replaces the symmetric 0.30 N band (dyno.md: 4.76 N) [D]
#define CTRL_SOFT_BACKOFF_DEG 0.5   // step back per tick above F_SOFT_LIMIT_N [A]
// Gripper lane 2026-10-11 (controls.md 4): stiffness estimate and gain schedule, hold bias.
#define GAIN_SCHED_ENABLED   1      // 1 = scale feedforward and PI by K_STIFF / K_est (loop gain held at the stiff-finger
                                    // design point for any finger in the window) [D Monte Carlo, controls.md 5]
#define KEST_F_MIN_N         1.5    // estimate stiffness only once the measured force is above this [A]
#define KEST_LAG_TICKS       4      // squeeze command this many control ticks back (80 ms ~ servo lag) is the one the
                                    // force answers to [D: dead 10 + frame 10 + tau 40 + EMA 10 = 70 ms]
#define KEST_ALPHA           0.5    // per-tick smoothing of the estimate [A]
#define K_SCHED_MIN_N_PER_MM 0.70   // the schedule never assumes a finger softer than this (gain <= 1.63/0.70 = 2.3x) [A]
#define F_HOLD_BIAS_N        1.0    // regulate the measured force this far above the setpoint: margin for an FSR that
                                    // reads high (span, ADC gain, creep, hysteresis) so the TRUE force stays >= 5 N (R14).
                                    // Chosen by results/design_sweep (0 / 0.3 / 0.6 / 1.0 / 1.2); peak stays < 8 N [D]
#define CTRL_SAT_TOL_DEG     0.2    // "at the position cap" tolerance for the saturation-stall test [A]

// ---------------------------------------------------------------------------
// Stall / over-current (R20: detect and back off within 200 ms).
// ---------------------------------------------------------------------------
#define STALL_CURRENT_A      3.0    // servo-rail current trip (was 1.8 A on the DS3218MG, 3.3 A before this fix) [D]
                                    // Upper bound: INA219 at PGA /8 over 0.1 ohm saturates at 0.320 V / 0.1 = 3.2 A [S]; a stalled
                                    // finger (Fit A 3.77 A) reads at best 3.2 x (1 - 1 %) - 0.2 mV / 0.1 = 3.166 A [A], so the
                                    // trip must stay below 3.166 A or it never fires (3.3 A could not). Lower bound: Fit A hold
                                    // at the 10 N cap with offset 2.246 A (8 N cap 1.891 A) plus the worst-case trip spread
                                    // 0.064 A. 3.0 A: margin 0.166 A to the saturated reading, 0.69 A over the 10 N hold at
                                    // the low end of the trip range (2.937 A)
#define STALL_CURRENT_MS     100    // [A]
#define STALL_CURRENT_HOLD_A 3.1    // trip while the force loop runs (CLOSE after contact, HOLD, FEED) (3.6 A before this fix,
                                    // above the 3.2 A INA219 full scale, so it could never fire; 2.0 A on the DS3218MG) [D]
                                    // Upper bound 3.166 A: worst saturated reading 3.2 x (1 - 1 %) - 2 mA [S, A] (force_ctrl.h
                                    // static_assert). Lower bound: Fit A hold at the 10 N cap with offset 2.246 A plus the worst
                                    // trip spread 0.066 A (ina219_budget.py); at 3.1 A the low end is 3.036 A, 0.79 A above it.
                                    // Kept at or above STALL_CURRENT_A so motion trips first. Bench step M6: set it to
                                    // min(0.9 x the measured stall current read on the INA219, INA219_SAT_READING_MIN_A - margin)
                                    // (controls.md 4.3) [D]. 0.9 x a measured stall of about 3.4-3.6 A is above 3.166 A and fails
                                    // the force_ctrl.h static_assert; a higher trip needs a smaller shunt or a lower PGA gain
                                    // (a hardware change)
#define HOLD_I_LIMIT_A       0.0    // HOLD/FEED current limit for the thermal track (R26); 0 = off. "ILIM <A>" sets it [A]
#define HOLD_I_LIMIT_MS      500    // above the limit this long -> setpoint steps down HOLD_I_STEP_N, WARN HOLD_I_LIMIT [A]
#define HOLD_I_STEP_N        0.25   // [A]
#define HOLD_I_FLOOR_N       5.0    // ILIM never steps the setpoint below this (R14). A lower value is a thermal override
                                    // of R14 and must be written here on purpose (bench step, controls.md 4.3) [DB R14]
// Thermal F1 (thermal.md 5): friction back-off in HOLD. After HOLD_BACKOFF_DELAY_MS the rail current is averaged over
// HOLD_I_AVG_MS with the back-off off (F4: EVT HOLD_I and the ST field Ih=), with the held force, then the command
// steps open by HOLD_BACKOFF_STEP_DEG every HOLD_BACKOFF_STEP_MS while the measured force stays >= the held force
// (at most the regulated target) - HOLD_BACKOFF_MARGIN_N. The first step that drops it below (the gear train's friction threshold) closes fully and
// returns two steps short of it (friction leaves the jaw where it slipped, so thermal's "re-close one step" does not
// restore the force on the plant model). It also stops at a rail current <= HOLD_BACKOFF_FACTOR^2 x the F4 reading
// (motor current x factor if the drive conducts continuously, rail ~ I^2) or at HOLD_BACKOFF_MAX_DEG. "BACKOFF <factor>" sets the factor, 0 = off.
#define HOLD_BACKOFF_ENABLED 0      // F1 off at boot: in the Monte Carlo it cut R14 from 48.5 % to 13.5 % (n 200), because
                                    // FSR creep and hysteresis read high while the force falls, hiding the drop F1 stops
                                    // on (controls.md 4.3). "BACKOFF 0.5" turns it on for the M7 bench check [D]
#define HOLD_BACKOFF_FACTOR  0.5    // motor-current factor; thermal.md 4.4 window: >= eta_g^2 (0.4225 at eta_g 0.65) and
                                    // <= 0.63 (Fit A) / 0.87 (Fit B) at 40 C. Below the friction threshold the force
                                    // criterion stops it first [D thermal.md]
#define HOLD_BACKOFF_DELAY_MS 300   // hold settled before the F4 reading and the back-off [A]
#define HOLD_I_AVG_MS        100    // F4 averaging window, 5 INA219 reads [A]
#define HOLD_BACKOFF_STEP_DEG 0.33  // one servo deadband (3 us = 0.27 deg [S A17]) rounded up [D]. T09 round 2 (2026-10-16): was
                                    // 0.3. The pulse is whole us (0.09 deg), so the settled back-off (two steps short of the
                                    // losing step) is 6 or 7 us by where the hold command rounds; at the 4.9 deg floor 0.3 gave
                                    // 6 us (0.54 deg, rail 0.58 of F4, test limit 0.55). 0.33 settles at 0.66 deg: rail 0.48-0.50,
                                    // true force down 0.02-0.03 N at the 4.9 and 6.2 deg floors (faults.py hold fixture) [D]
#define HOLD_BACKOFF_STEP_MS 100    // servo lag + frame + dead time ~80 ms between steps [D controls.md 5]
#define HOLD_BACKOFF_MARGIN_N 0.2   // the force has fallen when it is this far below the held force. Rev B.1: was 0.3; on the DS3230 MG plant 0.3 let the true force drop 0.14 N (test_hold_current_reading_sorts_the_regime needs < 0.1), 0.2 drops 0.02 N [A]
#define HOLD_BACKOFF_MAX_DEG 3.0    // never back off further than this [A]
// Thermal F2 (thermal.md 5): a hold longer than HOLD_LONG_MS without the F1 back-off reaching its stop clamps the
// setpoint to F_SET_LONG_MAX_N (WARN HOLD_LONG).
#define HOLD_LONG_MS         15000  // [S thermal.md F2]
#define F_SET_LONG_MAX_N     5.0    // [S thermal.md F2]
#define I_SENSOR_FAIL_MS     100    // INA219 found at boot, then no valid reading this long -> FAULT I_SENSOR (the
                                    // over-current trip and the FSR-open check are blind without it) [A]
#define WDT_TIMEOUT_S        1      // ESP32 task watchdog on loop(): a hang resets the MCU and setup() writes the open
                                    // pulse first (loop passes take < 1 ms; 1 s is the API's smallest unit) [A]
#define FSR_OPEN_I_A         0.60   // CLOSE search ended with no FSR contact but the rail draws this much: the pads are
                                    // squeezing something the FSR cannot see -> FAULT FSR_OPEN (idle ~0.15 A) [A]
#define LIMIT_STUCK_DEG      10.0   // jaw-open limit closed while the command is this far below open ... [A]
#define LIMIT_STUCK_MS       300    // ... for this long -> FAULT LIMIT (switch stuck closed) [A]
#define STALL_ERR_DEG        8.0    // |command - feedback| (feedback builds only) ... [A]
#define STALL_TIME_MS        150    // ... for this long -> STALL; also force-loop saturation time [A]
#define TOUCH_DI_A           0.30   // TOUCHDOWN: current rise over baseline that means nail-on-table [A, bench]
#define TOUCH_MS             40     // ... sustained this long -> TABLE_TOUCH [A]
#define TOUCH_BASE_MS        200    // baseline averaging window after TOUCHDOWN reaches pre-grasp [A]

// ---------------------------------------------------------------------------
// DC gearmotor branch: Pololu 380:1 HPCB 6 V + 12 CPR encoder (#5200) + printed 8:1 [S / TA].
// ---------------------------------------------------------------------------
#define DC_PWM_HZ            20000  // above audible [A]
#define DC_PWM_BITS          10     // [A]
#define DC_LEDC_CH_A         4      // LEDC channels (core 2.x API) [A]
#define DC_LEDC_CH_B         5      // [A]
#define ENC_COUNTS_PER_REV   4550.0 // at the gearbox output [S: Pololu 5200]
#define DC_EXTRA_RATIO       8.0    // printed two-stage spur [D: TA]
#define DC_DIR               1.0    // +1 or -1 so that + duty opens the jaw [A]
#define DC_JAW_MAX_DPS       60.0   // 85 rpm / 8 = 64 deg/s at the jaw, less margin [D/A]
#define DC_POS_KP_PER_DEG    0.08   // duty per jaw degree, inner position loop [A, bench-tune]
#define DC_DUTY_MAX          0.90   // [A]
#define DC_DUTY_MIN_MOVE     0.10   // breakaway [A]
#define DC_HOME_DUTY         0.35   // open-direction duty while homing to the limit switch [A]

// ---------------------------------------------------------------------------
// Button, limit switch and state timeouts (ms). 0 = no timeout.
// ---------------------------------------------------------------------------
#define BUTTON_DEBOUNCE_MS   25     // [A]
#define BUTTON_LONG_MS       800    // held this long -> BUTTON_LONG [A]
#define LIMIT_DEBOUNCE_MS    10     // [A]
#define BOOT_SETTLE_MS       300    // BOOT timeout: rails settle before HOME [A]
#define TIMEOUT_HOME_MS      1500   // [A]
#define TIMEOUT_CAL_MS       4000   // [A]
#define TIMEOUT_APPROACH_MS  15000  // arm has this long to reach the cloth -> back to IDLE [A]
#define TIMEOUT_CLOSING_MS   2000   // contact search + force ramp -> FAULT [A]
#define TIMEOUT_GRIPPING_MS  60000  // hold without FEED -> release (servo heating, R26) [A]
#define TIMEOUT_FEEDING_MS   30000  // max feed hold (duty cycle feeds 20 s) -> release [DB section 7, A]
#define TIMEOUT_TOUCHDOWN_MS 10000  // arm lowering to the table; no touch -> release [A]
#define TIMEOUT_RETRACT_MS   5000   // arm return after release (DB section 7 return 5.0 s) -> IDLE [DB/A]
#define TIMEOUT_RELEASING_MS 1500   // [A]
#define TIMEOUT_DC_HOME_MS   4000   // DC branch homes slowly [A]
#define CAL_SETTLE_MS        400    // jaw open and still before zeroing the FSR [A]
#define CAL_SAMPLES          64     // [A]

// ---------------------------------------------------------------------------
// Added by the firmware-code lane (2026-09-22).
// ---------------------------------------------------------------------------
#define BUTTON_POLL_MS       1      // button + limit poll period [A]
#define INA219_PERIOD_MS     20     // current-sense read, one per control tick [A]
#define INA219_SHUNT_LSB_UV  10.0   // shunt-voltage register LSB [S: TI INA219 datasheet]
#define CAL_SEARCH_START_DEG 5.0    // CALIBRATE slow search starts here (CAL_C0_MAX + 1) [D]
#define LED_BLINK_IDLE_MS    1000   // heartbeat half-period in IDLE_OPEN [A]
#define LED_BLINK_BUSY_MS    250    // half-period in motion / grip states [A]
#define LED_BLINK_FAULT_MS   60     // half-period in FAULT [A]
#define STREAM_HZ_MAX        50     // STREAM <hz> clamp = control rate [D]
