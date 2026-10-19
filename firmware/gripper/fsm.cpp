// fsm.cpp -- transition table, entry actions, timeouts and the control core. See fsm.h.
#include "fsm.h"
#include <stdio.h>
#include <stdarg.h>
#include <math.h>

static const char *const kStateNames[] = {
  "BOOT", "HOME", "CALIBRATE", "IDLE", "APPROACH", "TOUCHDOWN", "CLOSE", "HOLD", "FEED", "RELEASE", "RETRACT", "FAULT"
};
static_assert(sizeof(kStateNames) / sizeof(kStateNames[0]) == ST_COUNT, "kStateNames out of step with State");

const char *stateName(uint8_t s) {
  if (s < ST_COUNT) return kStateNames[s];
  if (s == ST_ACTIVE) return "ACTIVE";
  if (s == ST_SAME) return "SAME";
  return "?";
}

uint32_t stateTimeoutMs(uint8_t s) {
  switch (s) {
    case ST_BOOT:      return BOOT_SETTLE_MS;        // normal exit
    case ST_HOME:      return TIMEOUT_HOME_MS;
    case ST_CALIBRATE: return TIMEOUT_CAL_MS;
    case ST_APPROACH:  return TIMEOUT_APPROACH_MS;
    case ST_TOUCHDOWN: return TIMEOUT_TOUCHDOWN_MS;
    case ST_CLOSE:     return TIMEOUT_CLOSING_MS;
    case ST_HOLD:      return TIMEOUT_GRIPPING_MS;
    case ST_FEED:      return TIMEOUT_FEEDING_MS;
    case ST_RELEASE:   return TIMEOUT_RELEASING_MS;
    case ST_RETRACT:   return TIMEOUT_RETRACT_MS;     // normal exit
    default:           return 0;                      // IDLE, FAULT: wait forever
  }
}

static void report(Core &c, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
static void report(Core &c, const char *fmt, ...) {
  if (!c.io.report) return;
  char buf[96];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  c.io.report(buf);
}

// ---------------------------------------------------------------------------------------------------------
// Entry / exit
static void enterState(Core &c, uint8_t s);

static void onExit(Core &c) {
  if (c.state == ST_TOUCHDOWN) cmDisarmTouch(c.cm);
  if (c.state == ST_FAULT) c.relax = false;
}

static void onEnter(Core &c) {
  switch (c.state) {
    case ST_BOOT:
      break;
    case ST_HOME:
    case ST_IDLE:
    case ST_APPROACH:
    case ST_RELEASE:
      c.fc.on = false;
      motionMove(c.motion, (float)JAW_OPEN_DEG, (float)JAW_SPEED_FAST_DPS);
      break;
    case ST_CALIBRATE:
      c.fc.on = false;
      motionMove(c.motion, (float)JAW_OPEN_DEG, (float)JAW_SPEED_FAST_DPS);
      c.calPhase = CAL_SETTLE;
      c.calT0 = c.now;
      break;
    case ST_TOUCHDOWN:
      c.fc.on = false;
      motionMove(c.motion, c.thetaC0 + (float)JAW_PREGRASP_DEG, (float)JAW_SPEED_FAST_DPS);
      break;
    case ST_CLOSE:
      fcReset(c.fc);
      fcSetFloor(c.fc, fcJawFloor(c.thetaC0));
      fcSetpoint(c.fc, c.sp);
      fmNewGrip(c.fm);
      c.closePhase = CLOSE_SEARCH;
      motionSearch(c.motion, c.thetaC0 + (float)JAW_SLOW_ZONE_DEG, c.thetaC0 - (float)NO_CONTACT_MARGIN_DEG,
                   (float)JAW_SPEED_FAST_DPS, (float)JAW_SPEED_NEAR_DPS);
      if ((float)JAW_MID_ZONE_DEG > (float)JAW_SLOW_ZONE_DEG)
        motionSetMid(c.motion, c.thetaC0 + (float)JAW_MID_ZONE_DEG, (float)JAW_SPEED_MID_DPS);
      break;
    case ST_HOLD:
      fmArmHold(c.fm);  // slip is reported in every hold, entered by FSR_TARGET or by FORCE_SAT
      c.holdSince = c.now;
      c.longHoldDone = false;
      c.iHoldRef = -1.0f;
      c.fc.boff = 0.0f;
      c.boPhase = BO_WAIT;
      c.boSince = c.now;
      c.iSum = c.fSum = 0.0f;
      c.iN = 0;
      break;
    case ST_FEED:
    case ST_RETRACT:
      break;  // HOLD/FEED keep the force loop running; RETRACT keeps the jaw open
    case ST_FAULT: {
      c.fc.on = false;
      // Open past the contact angle as well as past the command: during the fast leg the command can be
      // ~9 deg ahead of the jaw, so cmd + 5 alone might still squeeze (review issue 3).
      const float base = c.motion.cmd > c.thetaC0 ? c.motion.cmd : c.thetaC0;
      const float back = base + (float)FAULT_BACKOFF_DEG;
      motionMove(c.motion, back > (float)JAW_OPEN_DEG ? (float)JAW_OPEN_DEG : back, (float)FAULT_BACKOFF_DPS);
      // Re-arm the over-current monitor: if the stall persists through the back-off (e.g. a stall in the
      // opening direction at +20 deg), a fresh OVERCURRENT in FAULT relaxes the servo (row FAULT/OVERCURRENT).
      c.cm.inOver = false;
      c.cm.overPosted = false;
      report(c, "EVT FAULT_%s %lu", faultName(c.fault), (unsigned long)c.now);
      break;
    }
    default:
      break;
  }
}

static void enterState(Core &c, uint8_t s) {
  onExit(c);
  c.state = s;
  c.enteredAt = c.now;
  c.timeoutPosted = false;
  report(c, "EVT ENTER_%s %lu", stateName(s), (unsigned long)c.now);
  onEnter(c);
}

// ---------------------------------------------------------------------------------------------------------
// Guards
static bool gLimitOk(Core &c, const Event &) {
  return !c.limitRequired || (c.io.limitClosed && c.io.limitClosed());
}
static bool gLimitBad(Core &c, const Event &e) { return !gLimitOk(c, e); }
static float lagRef(const Core &c) { return c.motion.cmd + c.motion.vNow * (float)CTRL_LAG_COMP_S; }
static bool calInWindow(const Core &c) {
  const float th = lagRef(c);
  return th >= (float)CAL_C0_MIN_DEG && th <= (float)CAL_C0_MAX_DEG;
}
static bool gCalIn(Core &c, const Event &) { return c.calPhase == CAL_SEARCH && calInWindow(c); }
static bool gCalOut(Core &c, const Event &) { return c.calPhase == CAL_SEARCH && !calInWindow(c); }
static bool gSearching(Core &c, const Event &) { return c.closePhase == CLOSE_SEARCH; }
static bool gSatUsable(Core &, const Event &e) { return e.arg >= (float)F_SLIP_N; }
static bool gSatUnusable(Core &, const Event &e) { return e.arg < (float)F_SLIP_N; }
// The search ended with no FSR contact but the servo is loaded: the pads hold something the FSR cannot see.
static bool gFsrBlind(Core &c, const Event &) { return c.lastIValid && c.lastI >= (float)FSR_OPEN_I_A; }

// ---------------------------------------------------------------------------------------------------------
// Actions
static void aFaultTimeout(Core &c, const Event &) { c.fault = FAULT_TIMEOUT; }
static void aFaultLimit(Core &c, const Event &) { c.fault = FAULT_LIMIT; }
static void aFaultCal(Core &c, const Event &) { c.fault = FAULT_CAL_RANGE; }
static void aFaultOverforce(Core &c, const Event &) { c.fault = FAULT_OVERFORCE; }
static void aFaultOvercurrent(Core &c, const Event &) { c.fault = FAULT_OVERCURRENT; }
static void aFaultStall(Core &c, const Event &) { c.fault = FAULT_STALL; }
static void aFaultFsrOpen(Core &c, const Event &) { c.fault = FAULT_FSR_OPEN; }
static void aFaultSensor(Core &c, const Event &e) {
  const uint8_t code = (uint8_t)e.arg;
  c.fault = (code > FAULT_NONE && code < FAULT_COUNT) ? code : (uint8_t)FAULT_FSR_SHORT;
}
static void aClearFault(Core &c, const Event &) { c.fault = FAULT_NONE; }
static void aStoreC0(Core &c, const Event &) {
  c.thetaC0 = lagRef(c);
  c.calibrated = true;
  motionStop(c.motion);
  report(c, "EVT CAL_THETA_C0 %lu %.2f", (unsigned long)c.now, (double)c.thetaC0);
}
static void aSetpoint(Core &c, const Event &e) {
  float sp = e.arg;
  if (!isfinite(sp)) sp = c.sp;   // never let a NaN reach the loop
  if (sp < (float)F_SET_MIN_N) sp = (float)F_SET_MIN_N;
  if (sp > (float)F_SET_MAX_N) sp = (float)F_SET_MAX_N;
  // Thermal F2 stays in force for the rest of a long hold: a later "G 7" cannot lift it (review 2026-10-11).
  if ((c.state == ST_HOLD || c.state == ST_FEED) && c.longHoldDone && sp > (float)F_SET_LONG_MAX_N) sp = (float)F_SET_LONG_MAX_N;
  c.sp = sp;
  fcSetpoint(c.fc, sp);  // also before contact: fcStart keeps spTarget (review issue 1)
  if (c.state == ST_HOLD || c.state == ST_FEED) {   // new setpoint in a hold: undo the F1 back-off and measure again
    c.fc.boff = 0.0f;
    c.boPhase = BO_WAIT;
    c.boSince = c.now;
    c.iSum = c.fSum = 0.0f;
    c.iN = 0;
  }
}
static void aContact(Core &c, const Event &) {
  const float v = c.motion.vNow;
  motionStop(c.motion);
  fcStart(c.fc, c.motion.cmd, v);
  c.closePhase = CLOSE_FORCE;
}
static void aArmTouch(Core &c, const Event &) { cmArmTouch(c.cm, c.now); }
static void aRelax(Core &c, const Event &e) {
  c.relax = true;
  report(c, "WARN SERVO_RELAXED %lu %.2f", (unsigned long)c.now, (double)e.arg);
}
static void aWarn(Core &c, const Event &e) {
  report(c, "WARN %s %lu %.2f", eventName(e.type), (unsigned long)c.now, (double)e.arg);
}

// ---------------------------------------------------------------------------------------------------------
// Transition table. First matching row wins; state rows come before the ST_ACTIVE wildcard rows.
// Events with no matching row are ignored (the host still sees them in the EVT log).
const Transition kTransitions[] = {
  // BOOT: rails settle, then home.
  {ST_BOOT,      EV_TIMEOUT,              nullptr,      nullptr,           ST_HOME,      "BOOT_SETTLE_MS elapsed"},
  // HOME: open to +20 deg; the limit switch or the settled profile ends it.
  {ST_HOME,      EV_LIMIT_HIT,            nullptr,      nullptr,           ST_CALIBRATE, "open limit closed"},
  {ST_HOME,      EV_POSITION_REACHED,     gLimitOk,     nullptr,           ST_CALIBRATE, "open; limit closed or not required"},
  {ST_HOME,      EV_POSITION_REACHED,     gLimitBad,    aFaultLimit,       ST_FAULT,     "open but limit not closed (LIMIT_REQUIRED)"},
  {ST_HOME,      EV_TIMEOUT,              nullptr,      aFaultTimeout,     ST_FAULT,     "TIMEOUT_HOME_MS"},
  // CALIBRATE (R21): settle, zero the FSR, slow search with no cloth until F >= F_TOUCH, store theta_c0.
  {ST_CALIBRATE, EV_FSR_CONTACT,          gCalIn,       aStoreC0,          ST_IDLE,      "theta_c0 inside [CAL_C0_MIN, CAL_C0_MAX]: store it"},
  {ST_CALIBRATE, EV_FSR_CONTACT,          gCalOut,      aFaultCal,         ST_FAULT,     "theta_c0 outside the window"},
  {ST_CALIBRATE, EV_NO_CONTACT,           nullptr,      aFaultCal,         ST_FAULT,     "search reached CAL_C0_MIN without touch"},
  {ST_CALIBRATE, EV_TIMEOUT,              nullptr,      aFaultTimeout,     ST_FAULT,     "TIMEOUT_CAL_MS"},
  // IDLE: jaw open, waiting for the host or the button.
  {ST_IDLE,      EV_BUTTON_PRESS,         nullptr,      nullptr,           ST_APPROACH,  "START (host-less demo: advance one step)"},
  {ST_IDLE,      EV_SERIAL_CMD_APPROACH,  nullptr,      nullptr,           ST_APPROACH,  "\"A\": arm moves over the cloth"},
  {ST_IDLE,      EV_SERIAL_CMD_GRIP,      nullptr,      aSetpoint,         ST_CLOSE,     "\"G <N>\": grip now"},
  {ST_IDLE,      EV_SERIAL_CMD_HOME,      nullptr,      nullptr,           ST_HOME,      "\"H\": re-home"},
  {ST_IDLE,      EV_SERIAL_CMD_CAL,       nullptr,      nullptr,           ST_CALIBRATE, "\"C\": recalibrate"},
  // APPROACH: arm moves, jaw open.
  {ST_APPROACH,  EV_SERIAL_CMD_AT_POSE,   nullptr,      nullptr,           ST_TOUCHDOWN, "\"ARM_AT_POSE\""},
  {ST_APPROACH,  EV_BUTTON_PRESS,         nullptr,      nullptr,           ST_TOUCHDOWN, "START: advance"},
  {ST_APPROACH,  EV_SERIAL_CMD_GRIP,      nullptr,      aSetpoint,         ST_CLOSE,     "\"G <N>\": grip now"},
  {ST_APPROACH,  EV_SERIAL_CMD_RELEASE,   nullptr,      nullptr,           ST_IDLE,      "\"R\": abort"},
  {ST_APPROACH,  EV_BUTTON_LONG,          nullptr,      nullptr,           ST_IDLE,      "STOP: abort"},
  {ST_APPROACH,  EV_TIMEOUT,              nullptr,      nullptr,           ST_IDLE,      "TIMEOUT_APPROACH_MS: arm never arrived"},
  // TOUCHDOWN: jaw to pre-grasp, arm lowers until nail A touches the table (D7).
  {ST_TOUCHDOWN, EV_POSITION_REACHED,     nullptr,      aArmTouch,         ST_SAME,      "at pre-grasp: arm the current-rise detector"},
  {ST_TOUCHDOWN, EV_TABLE_TOUCH,          nullptr,      nullptr,           ST_CLOSE,     "servo current rose: nail on the table"},
  {ST_TOUCHDOWN, EV_SERIAL_CMD_GRIP,      nullptr,      aSetpoint,         ST_CLOSE,     "\"G <N>\": host saw the touch"},
  {ST_TOUCHDOWN, EV_BUTTON_PRESS,         nullptr,      nullptr,           ST_CLOSE,     "START: advance"},
  {ST_TOUCHDOWN, EV_SERIAL_CMD_RELEASE,   nullptr,      nullptr,           ST_RELEASE,   "\"R\": abort"},
  {ST_TOUCHDOWN, EV_BUTTON_LONG,          nullptr,      nullptr,           ST_RELEASE,   "STOP: abort"},
  {ST_TOUCHDOWN, EV_TIMEOUT,              nullptr,      aWarn,             ST_RELEASE,   "TIMEOUT_TOUCHDOWN_MS: no table touch"},
  // CLOSE (R19): fast to theta_c0 + JAW_SLOW_ZONE_DEG, 20 deg/s search, then the force loop ramps to the setpoint.
  {ST_CLOSE,     EV_FSR_CONTACT,          gSearching,   aContact,          ST_SAME,      "touch: stop the search, start the force loop"},
  {ST_CLOSE,     EV_FSR_TARGET,           nullptr,      nullptr,           ST_HOLD,      "F on target for F_SETTLE_MS (slip armed)"},
  {ST_CLOSE,     EV_NO_CONTACT,           gFsrBlind,    aFaultFsrOpen,     ST_FAULT,     "no FSR contact but rail current >= FSR_OPEN_I_A: FSR open"},
  {ST_CLOSE,     EV_NO_CONTACT,           nullptr,      aWarn,             ST_RELEASE,   "searched NO_CONTACT_MARGIN past theta_c0: miss"},
  {ST_CLOSE,     EV_FORCE_SAT,            gSatUsable,   aWarn,             ST_HOLD,      "at the squeeze cap, F >= F_SLIP: hold what we have (slip armed)"},
  {ST_CLOSE,     EV_FORCE_SAT,            gSatUnusable, aWarn,             ST_RELEASE,   "at the squeeze cap, F < F_SLIP: give up"},
  {ST_CLOSE,     EV_FSR_LOST,             nullptr,      aWarn,             ST_RELEASE,   "contact vanished"},
  {ST_CLOSE,     EV_SERIAL_CMD_GRIP,      nullptr,      aSetpoint,         ST_SAME,      "new setpoint"},
  {ST_CLOSE,     EV_SERIAL_CMD_RELEASE,   nullptr,      nullptr,           ST_RELEASE,   "\"R\""},
  {ST_CLOSE,     EV_BUTTON_LONG,          nullptr,      nullptr,           ST_RELEASE,   "STOP"},
  {ST_CLOSE,     EV_TIMEOUT,              nullptr,      aFaultTimeout,     ST_FAULT,     "TIMEOUT_CLOSING_MS"},
  // HOLD: lift and move to the needle; the force loop keeps F in [F_sp, F_sp + 0.6].
  {ST_HOLD,      EV_SERIAL_CMD_FEED,      nullptr,      nullptr,           ST_FEED,      "\"FEED\""},
  {ST_HOLD,      EV_BUTTON_PRESS,         nullptr,      nullptr,           ST_FEED,      "START: advance"},
  {ST_HOLD,      EV_FSR_SLIP,             nullptr,      aWarn,             ST_SAME,      "F < 3 N for 100 ms, either HOLD path: report SLIP"},
  {ST_HOLD,      EV_FORCE_SAT,            nullptr,      aWarn,             ST_SAME,      "at the squeeze cap: report"},
  {ST_HOLD,      EV_SERIAL_CMD_GRIP,      nullptr,      aSetpoint,         ST_SAME,      "new setpoint"},
  {ST_HOLD,      EV_FSR_LOST,             nullptr,      aWarn,             ST_RELEASE,   "cloth gone"},
  {ST_HOLD,      EV_SERIAL_CMD_RELEASE,   nullptr,      nullptr,           ST_RELEASE,   "\"R\""},
  {ST_HOLD,      EV_SERIAL_CMD_FEED_DONE, nullptr,      nullptr,           ST_RELEASE,   "\"FEED_DONE\""},
  {ST_HOLD,      EV_BUTTON_LONG,          nullptr,      nullptr,           ST_RELEASE,   "STOP"},
  {ST_HOLD,      EV_TIMEOUT,              nullptr,      aWarn,             ST_RELEASE,   "TIMEOUT_GRIPPING_MS (servo heat, R26)"},
  // FEED: the machine pulls the cloth; same loop.
  {ST_FEED,      EV_SERIAL_CMD_FEED_DONE, nullptr,      nullptr,           ST_RELEASE,   "\"FEED_DONE\""},
  {ST_FEED,      EV_BUTTON_PRESS,         nullptr,      nullptr,           ST_RELEASE,   "START: advance"},
  {ST_FEED,      EV_FSR_SLIP,             nullptr,      aWarn,             ST_SAME,      "F < 3 N for 100 ms: report SLIP"},
  {ST_FEED,      EV_FORCE_SAT,            nullptr,      aWarn,             ST_SAME,      "at the squeeze cap: report"},
  {ST_FEED,      EV_SERIAL_CMD_GRIP,      nullptr,      aSetpoint,         ST_SAME,      "new setpoint"},
  {ST_FEED,      EV_FSR_LOST,             nullptr,      aWarn,             ST_RELEASE,   "cloth gone"},
  {ST_FEED,      EV_SERIAL_CMD_RELEASE,   nullptr,      nullptr,           ST_RELEASE,   "\"R\""},
  {ST_FEED,      EV_BUTTON_LONG,          nullptr,      nullptr,           ST_RELEASE,   "STOP"},
  {ST_FEED,      EV_TIMEOUT,              nullptr,      aWarn,             ST_RELEASE,   "TIMEOUT_FEEDING_MS"},
  // RELEASE: open to +20 deg.
  {ST_RELEASE,   EV_POSITION_REACHED,     nullptr,      nullptr,           ST_RETRACT,   "jaw open"},
  {ST_RELEASE,   EV_TIMEOUT,              nullptr,      aFaultTimeout,     ST_FAULT,     "TIMEOUT_RELEASING_MS"},
  // RETRACT: arm returns with the jaw open.
  {ST_RETRACT,   EV_TIMEOUT,              nullptr,      nullptr,           ST_IDLE,      "TIMEOUT_RETRACT_MS: arm clear"},
  {ST_RETRACT,   EV_SERIAL_CMD_APPROACH,  nullptr,      nullptr,           ST_APPROACH,  "\"A\": next cycle at once"},
  {ST_RETRACT,   EV_BUTTON_PRESS,         nullptr,      nullptr,           ST_IDLE,      "START: advance"},
  // FAULT: jaw backed off FAULT_BACKOFF_DEG on entry; only a re-home clears it.
  {ST_FAULT,     EV_BUTTON_LONG,          nullptr,      aClearFault,       ST_HOME,      "STOP held: clear, re-home"},
  {ST_FAULT,     EV_SERIAL_CMD_HOME,      nullptr,      aClearFault,       ST_HOME,      "\"H\": clear, re-home"},
  {ST_FAULT,     EV_FAULT_OVERCURRENT,    nullptr,      aRelax,            ST_SAME,      "still over-current after back-off: stop the pulse"},
  // Any state except BOOT and FAULT.
  {ST_ACTIVE,    EV_FSR_OVER,             nullptr,      aFaultOverforce,   ST_FAULT,     "F > 8 N for F_TRIP_MS (D8)"},
  {ST_ACTIVE,    EV_FAULT_OVERCURRENT,    nullptr,      aFaultOvercurrent, ST_FAULT,     "rail current > 1.8 A for 100 ms (R20)"},
  {ST_ACTIVE,    EV_FAULT_STALL,          nullptr,      aFaultStall,       ST_FAULT,     "command/feedback disagree (FB builds)"},
  {ST_ACTIVE,    EV_FAULT_SENSOR,         nullptr,      aFaultSensor,      ST_FAULT,     "FSR short or stuck / bad zero / limit stuck (arg = FaultCode)"},
};
const uint16_t kTransitionCount = sizeof(kTransitions) / sizeof(kTransitions[0]);

// ---------------------------------------------------------------------------------------------------------
// Core
void coreInit(Core &c, const CoreIo &io, uint32_t now) {
  c.io = io;
  c.now = now;
  motionInit(c.motion, (float)JAW_OPEN_DEG);
  fcReset(c.fc);
  fmInit(c.fm);
  cmInit(c.cm);
  c.thetaC0 = (float)THETA_C0_DEFAULT;
  c.calibrated = false;
  c.sp = (float)F_TARGET_DEFAULT_N;
  c.fault = FAULT_NONE;
  c.calPhase = CAL_END;
  c.calT0 = now;
  c.closePhase = CLOSE_SEARCH;
  c.lastF = 0.0f;
  c.lastI = 0.0f;
  c.lastIValid = false;
  c.lastRow = -1;
  c.relax = false;
  c.limitRequired = (LIMIT_REQUIRED != 0);
  c.holdILimit = (float)HOLD_I_LIMIT_A;
  c.iLimSince = 0;
  c.limStuckSince = 0;
  c.limStuckPosted = false;
  c.backoffFactor = HOLD_BACKOFF_ENABLED ? (float)HOLD_BACKOFF_FACTOR : 0.0f;
  c.boPhase = BO_DONE;
  c.boSince = c.boT = now;
  c.iSum = c.fSum = 0.0f;
  c.iN = 0;
  c.iHoldRef = -1.0f;
  c.boFRef = c.boGood = 0.0f;
  c.boReclose = false;
  c.holdSince = now;
  c.longHoldDone = false;
  c.iPresent = true;
  c.iBadSince = 0;
  c.iBadPosted = false;
  c.state = ST_BOOT;
  c.enteredAt = now;
  c.timeoutPosted = false;
  report(c, "EVT ENTER_%s %lu", stateName(ST_BOOT), (unsigned long)now);
}

int coreDispatch(Core &c, const Event &e) {
  c.lastRow = -1;
  // Drop stale self-generated events: a timeout from an earlier state, or a motion event of a superseded move.
  if (e.type == EV_TIMEOUT && (uint8_t)e.arg != c.state) return -1;
  if ((e.type == EV_POSITION_REACHED || e.type == EV_NO_CONTACT) && (uint16_t)e.arg != c.motion.seq) return -1;
  for (uint16_t i = 0; i < kTransitionCount; i++) {
    const Transition &r = kTransitions[i];
    if (r.ev != e.type) continue;
    if (r.from == ST_ACTIVE) {
      if (c.state == ST_BOOT || c.state == ST_FAULT) continue;
    } else if (r.from != c.state) {
      continue;
    }
    if (r.guard && !r.guard(c, e)) continue;
    if (r.action) r.action(c, e);
    if (r.to != ST_SAME) enterState(c, r.to);
    c.lastRow = (int16_t)i;
    return i;
  }
  return -1;
}

void coreTick(Core &c, uint32_t now) {
  c.now = now;
  const uint32_t to = stateTimeoutMs(c.state);
  if (to && !c.timeoutPosted && now - c.enteredAt >= to) {
    c.timeoutPosted = eventPost(EV_TIMEOUT, (float)c.state);  // retried next pass if the queue was full
  }
  // Jaw-open limit stuck closed: closed while the command has been well away from open for LIMIT_STUCK_MS.
  const bool active = c.state != ST_BOOT && c.state != ST_FAULT;
  if (active && c.io.limitClosed && c.motion.cmd < (float)JAW_OPEN_DEG - (float)LIMIT_STUCK_DEG && c.io.limitClosed()) {
    if (!c.limStuckSince) c.limStuckSince = now ? now : 1;
    if (!c.limStuckPosted && now - c.limStuckSince >= (uint32_t)LIMIT_STUCK_MS) {
      c.limStuckPosted = eventPost(EV_FAULT_SENSOR, (float)FAULT_LIMIT);
    }
  } else {
    c.limStuckSince = 0;
    if (!active || !c.io.limitClosed || !c.io.limitClosed()) c.limStuckPosted = false;
  }
  // Thermal F2: a long hold without the F1 back-off having reached its stop clamps the setpoint.
  if ((c.state == ST_HOLD || c.state == ST_FEED) && !c.longHoldDone && now - c.holdSince >= (uint32_t)HOLD_LONG_MS) {
    c.longHoldDone = true;
    const bool f1Held = c.backoffFactor > 0.0f && c.boPhase == BO_DONE && c.fc.boff > 0.0f;
    if (!f1Held && c.fc.spTarget > (float)F_SET_LONG_MAX_N) {
      fcSetpoint(c.fc, (float)F_SET_LONG_MAX_N);
      c.sp = c.fc.spTarget;
      report(c, "WARN HOLD_LONG %lu %.2f", (unsigned long)now, (double)c.fc.spTarget);
    }
  }
  if (c.state != ST_CALIBRATE) return;
  if (c.calPhase == CAL_SETTLE && now - c.calT0 >= (uint32_t)CAL_SETTLE_MS) {
    if (c.io.fsrZeroStart) c.io.fsrZeroStart();
    c.calPhase = CAL_ZERO;
  } else if (c.calPhase == CAL_ZERO && !(c.io.fsrZeroBusy && c.io.fsrZeroBusy())) {
    const float z = c.io.fsrZeroMv ? c.io.fsrZeroMv() : 0.0f;
    if (z > (float)FSR_ZERO_MAX_MV) {
      c.calPhase = CAL_END;
      eventPost(EV_FAULT_SENSOR, (float)FAULT_ZERO_BAD);
    } else {
      fmNewGrip(c.fm);
      motionSearch(c.motion, (float)CAL_SEARCH_START_DEG, (float)CAL_C0_MIN_DEG - CTRL_LAG_COMP_DEG,
                   (float)JAW_SPEED_FAST_DPS, (float)JAW_SPEED_NEAR_DPS);
      c.calPhase = CAL_SEARCH;
    }
  }
}

void coreSampleForce(Core &c, uint32_t now, float f) {
  c.now = now;
  c.lastF = f;
  const uint8_t b = fmUpdate(c.fm, now, f, c.fc.on, fcRegTarget(c.fc));
  if (b & FM_OVER) eventPost(EV_FSR_OVER, f);
  if (b & FM_CONTACT) eventPost(EV_FSR_CONTACT, f);
  if (b & FM_TARGET) eventPost(EV_FSR_TARGET, f);
  if (b & FM_SLIP) eventPost(EV_FSR_SLIP, f);
  if (b & FM_LOST) eventPost(EV_FSR_LOST, f);
}

void coreSetCurrentPresent(Core &c, bool present) {
  c.iPresent = present;
  c.iBadSince = 0;
  c.iBadPosted = false;
}

void coreSampleCurrent(Core &c, uint32_t now, bool valid, float amps) {
  c.now = now;
  if (!isfinite(amps)) valid = false;
  c.lastI = valid ? amps : 0.0f;
  c.lastIValid = valid;
  // An INA219 that answered at boot and then stops giving valid readings blinds the over-current trip (R20) and the
  // FSR-open check: a fault, not a silent degradation (review 2026-10-11).
  if (c.iPresent && !valid) {
    if (!c.iBadSince) c.iBadSince = now ? now : 1;
    if (!c.iBadPosted && now - c.iBadSince >= (uint32_t)I_SENSOR_FAIL_MS) {
      c.iBadPosted = eventPost(EV_FAULT_SENSOR, (float)FAULT_I_SENSOR);
    }
  } else if (valid) {
    c.iBadSince = 0;
    c.iBadPosted = false;
  }
  // While the force loop runs, the FSR and the squeeze cap bound the force, so the trip is set above the hold
  // current of a high-current servo (config.h STALL_CURRENT_HOLD_A); every other state keeps the R20 trip.
  const float trip = c.fc.on ? (float)STALL_CURRENT_HOLD_A : (float)STALL_CURRENT_A;
  const uint8_t b = cmUpdate(c.cm, now, valid, amps, trip);
  if (b & CM_OVERCURRENT) eventPost(EV_FAULT_OVERCURRENT, amps);
  if (b & CM_TABLE_TOUCH) eventPost(EV_TABLE_TOUCH, amps);
  // Thermal hook (R26): in HOLD/FEED, a current above holdILimit for HOLD_I_LIMIT_MS steps the setpoint down.
  if (c.holdILimit > 0.0f && valid && (c.state == ST_HOLD || c.state == ST_FEED) && amps > c.holdILimit) {
    if (!c.iLimSince) c.iLimSince = now ? now : 1;
    if (now - c.iLimSince >= (uint32_t)HOLD_I_LIMIT_MS) {
      c.iLimSince = now;
      const float floorN = (float)HOLD_I_FLOOR_N;   // R14; lower only as a deliberate thermal override in config.h
      const float sp = c.fc.spTarget - (float)HOLD_I_STEP_N;
      if (sp >= floorN) {
        fcSetpoint(c.fc, sp);
        c.sp = c.fc.spTarget;
      }
      report(c, "WARN HOLD_I_LIMIT %lu %.2f", (unsigned long)now, (double)c.fc.spTarget);
    }
  } else {
    c.iLimSince = 0;
  }
}

bool coreSetBackoffFactor(Core &c, float f) {
  if (!isfinite(f) || f < 0.0f || f > 1.0f) return false;
  c.backoffFactor = f;
  if (f == 0.0f && c.boPhase == BO_STEP) c.boPhase = BO_DONE;
  return true;
}

// Thermal F1 + F4 (thermal.md 5), once per control tick in HOLD/FEED with the force loop on.
static void holdBackoff(Core &c) {
  if (!(c.state == ST_HOLD || c.state == ST_FEED) || !c.fc.on) return;
  const uint32_t t = c.now - c.boSince;
  if (c.boPhase == BO_WAIT) {
    if (t + (uint32_t)HOLD_I_AVG_MS >= (uint32_t)HOLD_BACKOFF_DELAY_MS && c.lastIValid) {
      c.iSum += c.lastI;
      c.fSum += c.lastF;
      c.iN++;
    }
    if (t >= (uint32_t)HOLD_BACKOFF_DELAY_MS) {
      c.iHoldRef = c.iN ? c.iSum / (float)c.iN : -1.0f;
      // The force to keep: the held force (a FORCE_SAT hold sits below the regulated target), at most that target.
      const float fHeld = c.iN ? c.fSum / (float)c.iN : 0.0f;
      c.boFRef = fHeld < fcRegTarget(c.fc) ? fHeld : fcRegTarget(c.fc);
      if (c.iN) report(c, "EVT HOLD_I %lu %.2f", (unsigned long)c.now, (double)c.iHoldRef);   // F4, back-off off
      c.boPhase = (c.backoffFactor > 0.0f && c.iN) ? BO_STEP : BO_DONE;
      c.boReclose = false;
      c.boT = c.now;
    }
    return;
  }
  if (c.boPhase != BO_STEP || c.now - c.boT < (uint32_t)HOLD_BACKOFF_STEP_MS) return;
  c.boT = c.now;
  const float iStop = c.backoffFactor * c.backoffFactor * c.iHoldRef;
  if (c.boPhase == BO_STEP && c.boReclose) {
    // Second half of a re-close: the jaw is back at the held force; settle two steps short of the step that lost it.
    c.fc.boff = c.boGood;
    c.boPhase = BO_DONE;
  } else if (c.lastF < c.boFRef - (float)HOLD_BACKOFF_MARGIN_N) {
    // This step let the train back-drive and the force fell. Friction keeps the jaw where it slipped to, so one step
    // back (thermal F1 as written) does not restore it: close fully, then return two steps short of the losing step.
    c.boGood = c.fc.boff > 2.0f * (float)HOLD_BACKOFF_STEP_DEG ? c.fc.boff - 2.0f * (float)HOLD_BACKOFF_STEP_DEG : 0.0f;
    c.fc.boff = 0.0f;
    c.boReclose = true;
    return;
  } else if (!c.lastIValid || c.lastI <= iStop || c.fc.boff + (float)HOLD_BACKOFF_STEP_DEG > (float)HOLD_BACKOFF_MAX_DEG) {
    c.boPhase = BO_DONE;
  } else {
    c.fc.boff += (float)HOLD_BACKOFF_STEP_DEG;
  }
  if (c.boPhase == BO_DONE) report(c, "EVT HOLD_BACKOFF %lu %.2f", (unsigned long)c.now, (double)c.fc.boff);
}

bool coreSetHoldCurrentLimit(Core &c, float amps) {
  if (!isfinite(amps) || amps < 0.0f) return false;
  c.holdILimit = amps;
  c.iLimSince = 0;
  return true;
}

float coreControl(Core &c, uint32_t now, float dt) {
  c.now = now;
  if (c.fc.on) {
    bool sat = false;
    holdBackoff(c);
    const float th = fcStep(c.fc, c.lastF, dt, &sat);
    motionHold(c.motion, th);
    if (sat) eventPost(EV_FORCE_SAT, c.lastF);
  } else {
    const EventType ev = motionStep(c.motion, dt, now);
    if (ev != EV_NONE) eventPost(ev, (float)c.motion.seq);
  }
  return c.motion.cmd;
}

float coreTheta(const Core &c) { return c.motion.cmd; }
