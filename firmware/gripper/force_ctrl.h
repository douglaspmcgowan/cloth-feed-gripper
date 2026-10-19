// force_ctrl.h -- grip-force loop, force-event monitor and servo-current monitor (hardware-free).
//
// Plant (controls.md 3): commanded squeeze u (deg past the touch reference theta_ref) -> servo (first order,
// SERVO_TAU_S, plus delay) -> pad force F = F_TOUCH + K * u_actual, K = k_tip * r_c * pi/180 (N/deg).
// Controller: feedforward u_ff = F_sp / K_STIFF (never over-squeezes a softer finger) + PI (SIMC tuning on
// the stiffest finger in the R12 window, so a softer finger is slower but never less stable), with
//   - setpoint ramp F_RAMP_NPS from F_TOUCH,
//   - asymmetric integrator deadband [F_sp, F_sp + CTRL_I_DB_HI_N] (R14: hold >= 5 N; servo deadband),
//   - squeeze rate limit CTRL_RATE_LIMIT_DPS, conditional-integration anti-windup,
//   - soft limit: above F_SOFT_LIMIT_N step back CTRL_SOFT_BACKOFF_DEG per tick and bleed the integrator,
//   - squeeze cap U_MAX = (F_CAP - F_TOUCH) / K_STIFF, so even the stiffest finger in the R12 window cannot
//     be driven past 10 N by position alone (R15), plus the absolute floor JAW_MIN_DEG.
//   - gain schedule (gripper lane 2026-10-11): K_est = (F - F_TOUCH) / u(80 ms ago) once F > KEST_F_MIN_N, clamped
//     to [K_SCHED_MIN, K_STIFF]; feedforward and PI are scaled by K_STIFF / K_est so the loop gain stays at the
//     stiff-finger design point (controls.md 4). It starts at K_STIFF, so before an estimate exists the loop is the
//     W2b-1 loop. The squeeze cap does not use K_est: it stays FSR-independent.
//   - hold bias F_HOLD_BIAS_N on the regulated (measured) force; non-finite inputs are rejected.
#pragma once
#include "platform.h"
#include "config.h"

#define FC_PI_F 3.14159265f

// Derived constants (same formulas in analysis/gripper/firmware_sim/fwconfig.py, checked by pytest).
static const float K_STIFF_N_PER_DEG = (float)(FINGER_K_MAX_N_PER_MM * R_C_MM * 3.14159265 / 180.0);  // 1.849
static const float K_DEF_N_PER_DEG   = (float)(FINGER_K_DEF_N_PER_MM * R_C_MM * 3.14159265 / 180.0);  // 1.134
static const float CTRL_KP_DEG_PER_N = (float)(SERVO_TAU_S / ((FINGER_K_MAX_N_PER_MM * R_C_MM * 3.14159265 / 180.0) *
                                                (CTRL_TAU_CL_S + CTRL_DELAY_S)));                      // 0.240
static const float CTRL_TI_S         = (float)((SERVO_TAU_S < 4.0 * (CTRL_TAU_CL_S + CTRL_DELAY_S)) ?
                                                SERVO_TAU_S : 4.0 * (CTRL_TAU_CL_S + CTRL_DELAY_S));  // 0.040
static const float CTRL_U_MAX_DEG    = (float)((F_CAP_N - F_CAP_MARGIN_N - F_TOUCH_N) /
                                                (FINGER_K_MAX_N_PER_MM * R_C_MM * 3.14159265 / 180.0)); // 4.87
static const float CTRL_LAG_COMP_DEG = (float)(JAW_SPEED_NEAR_DPS * CTRL_LAG_COMP_S);                  // 1.52 at 20 deg/s
static_assert(STALL_CURRENT_HOLD_A < SERVO_STALL_A && STALL_CURRENT_A < SERVO_STALL_A,
              "every over-current trip must sit below the stall current, or a stall is never detected (R20)");
// INA219 at the default PGA /8 saturates at 0.320 V across the shunt. The worst reading of a saturated (stalled) rail is
// full scale x (1 - gain error) - offset; a trip at or above it can never fire [S TI INA219; A 1 % gain, 200 uV offset].
#define INA219_FS_A              (0.320 / INA219_SHUNT_OHM)
#define INA219_SAT_READING_MIN_A (INA219_FS_A * (1.0 - 0.01) - 200e-6 / INA219_SHUNT_OHM)
static_assert(STALL_CURRENT_HOLD_A < INA219_SAT_READING_MIN_A && STALL_CURRENT_A < INA219_SAT_READING_MIN_A,
              "every over-current trip must sit below the worst saturated INA219 reading, or a stall is never detected (R20)");
static const float K_SCHED_MIN_N_PER_DEG = (float)(K_SCHED_MIN_N_PER_MM * R_C_MM * 3.14159265 / 180.0);   // 0.794

struct ForceCtrl {
  bool     on;
  float    thetaRef;   // jaw angle at which F = F_TOUCH (deg)
  float    u;          // squeeze command past thetaRef (deg, + = closing)
  float    integ;      // integrator state (deg)
  float    spTarget;   // final setpoint (N)
  float    spRamp;     // ramped setpoint (N)
  uint32_t satMs;      // time spent saturated below target (ms)
  bool     satPosted;
  float    kEst;       // estimated contact stiffness (N/deg), K_STIFF until estimated
  float    uHist[KEST_LAG_TICKS + 1];   // squeeze commands of the last ticks (ring)
  uint8_t  uHead;
  float    boff;       // thermal F1 back-off (deg toward open), added to the command in HOLD/FEED; 0 otherwise
  float    floor;      // jaw floor for this grip (deg): JAW_MIN_DEG, or theta_c0 - JAW_FLOOR_BELOW_C0_DEG (fcJawFloor)
};

// Jaw floor for a grip: JAW_MIN_DEG when JAW_FLOOR_BELOW_C0_DEG is 0; otherwise theta_c0 - JAW_FLOOR_BELOW_C0_DEG, never
// below JAW_MIN_DEG. Relative to the calibrated contact, the floor no longer moves with the contact-angle spread
// (tolerance_stacks.md T09F / T09H-relfloor).
float fcJawFloor(float thetaC0);
void  fcSetFloor(ForceCtrl &c, float floorDeg);

void  fcReset(ForceCtrl &c);
float fcSetpoint(ForceCtrl &c, float sp);                 // clamps to [F_SET_MIN_N, F_SET_MAX_N]; returns value used
// Start at contact. speedDps = commanded closing speed when the FSR crossed F_TOUCH: the servo trails the
// command by speed x CTRL_LAG_COMP_S, so a contact in the 120 deg/s fast leg gets a 9 deg offset, not 1.5.
void  fcStart(ForceCtrl &c, float thetaCmdNow, float speedDps);
// One control tick: returns the commanded jaw angle. *sat is set once per grip when the loop has been at
// its squeeze cap with F below target for STALL_TIME_MS (-> EV_FORCE_SAT).
float fcStep(ForceCtrl &c, float f, float dt_s, bool *sat);
float fcThetaCmd(const ForceCtrl &c);
float fcRegTarget(const ForceCtrl &c);                    // measured force the loop regulates to (setpoint + hold bias)
float fcGain(const ForceCtrl &c);                         // schedule factor K_STIFF / kEst (1 when off)

// ---------------------------------------------------------------------------------------------------------
// Force monitor: runs at the FSR rate (1 kHz) and turns the filtered force into edge events.
enum : uint8_t { FM_CONTACT = 1, FM_TARGET = 2, FM_SLIP = 4, FM_LOST = 8, FM_OVER = 16 };

struct ForceMonitor {
  bool     contactArmed;  // re-armed when F < F_TOUCH - F_HYST
  bool     touched;       // contact seen in this grip (enables LOST)
  bool     held;          // target reached in this grip (enables SLIP)
  bool     targetPosted;
  bool     slipArmed;
  bool     overArmed;
  bool     lostPosted;
  uint32_t bandSince, slipSince, lostSince, overSince;
  bool     inBand, inSlip, inLost, inOver;
};

void    fmInit(ForceMonitor &m);
void    fmNewGrip(ForceMonitor &m);  // CLOSE entry: forget the last grip, keep the over-force latch state
void    fmArmHold(ForceMonitor &m);  // HOLD entry by either path: arm slip detection (FSR_SLIP)
uint8_t fmUpdate(ForceMonitor &m, uint32_t now_ms, float f, bool forceMode, float spTarget);

// ---------------------------------------------------------------------------------------------------------
// Servo-rail current monitor: over-current (R20) always; table touch only while armed (TOUCHDOWN).
enum : uint8_t { CM_OVERCURRENT = 1, CM_TABLE_TOUCH = 2 };

struct CurrentMonitor {
  uint32_t overSince;
  bool     inOver, overPosted;
  bool     touchArmed, touchPosted, inTouch;
  uint32_t armedAt, touchSince;
  float    baseSum;
  uint16_t baseN;
  float    base;
  bool     baseSet;
};

void    cmInit(CurrentMonitor &m);
void    cmArmTouch(CurrentMonitor &m, uint32_t now_ms);
void    cmDisarmTouch(CurrentMonitor &m);
uint8_t cmUpdate(CurrentMonitor &m, uint32_t now_ms, bool valid, float amps, float tripA = (float)STALL_CURRENT_A);
