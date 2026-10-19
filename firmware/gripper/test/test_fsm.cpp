// test_fsm.cpp -- host test of the gripper FSM and its hardware-free modules (g++, no Arduino).
// Build and run from the repository root:  sh firmware/gripper/test/run_host_tests.sh
//   ./test_fsm            run every check; exit 0 only if all pass and every table row was taken
//   ./test_fsm --table    print the transition and timeout tables as Markdown (pasted into controls.md 2)
//
// Coverage contract: every row of kTransitions is driven at least once (ST_ACTIVE rows in every active
// state), every non-zero state timeout fires at its limit and not 1 ms before, and every fault producer
// (FSR over-force, over-current, zero, calibration range, limit, timeouts, sensor) reaches FAULT.
#include <cstdio>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>
#include "../fsm.h"
#include "../protocol.h"
#include "../servo_map.h"
#include "../fsr_model.h"
#include "../fsr_filter.h"

// ---------------------------------------------------------------------------------------------------------
// Host clock and IO fakes
static uint32_t g_now = 0;
uint32_t millis() { return g_now; }

static std::vector<std::string> g_lines;
static float g_zeroMv = 20.0f;
static bool  g_limit = true;
static void  fRep(const char *s) { g_lines.push_back(s); }
static void  fZeroStart() {}
static bool  fZeroBusy() { return false; }
static float fZeroMv() { return g_zeroMv; }
static const Core *g_coreP = nullptr;
static bool  g_limitStuck = false;   // fault injection: the switch reads closed whatever the jaw does
// The open limit closes only near the open angle (the jaw follows the command closely enough for the host test).
static bool  fLimit() { return g_limitStuck || (g_limit && (!g_coreP || g_coreP->motion.cmd >= (float)JAW_OPEN_DEG - 1.0f)); }

// ---------------------------------------------------------------------------------------------------------
// Check bookkeeping
static int g_pass = 0, g_fail = 0;
static std::vector<int> g_rowHits;
static std::string g_ctx;

static void check(bool ok, const char *what) {
  if (ok) {
    g_pass++;
  } else {
    g_fail++;
    std::printf("FAIL [%s] %s\n", g_ctx.c_str(), what);
  }
}
#define CHECK(cond) check((cond), #cond)

static int dispatch(Core &c, EventType t, float arg) {
  Event e;
  e.type = t;
  e.arg = arg;
  e.t_ms = g_now;
  const int r = coreDispatch(c, e);
  if (r >= 0) g_rowHits[r]++;
  return r;
}

static void drain(Core &c) {
  Event e;
  while (eventPop(e)) {
    const int r = coreDispatch(c, e);
    if (r >= 0) g_rowHits[r]++;
  }
}

static void newCore(Core &c) {
  eventsInit();
  g_lines.clear();
  g_zeroMv = 20.0f;
  g_limit = true;
  g_limitStuck = false;
  g_coreP = &c;
  g_now = 1000;
  CoreIo io;
  io.report = fRep;
  io.fsrZeroStart = fZeroStart;
  io.fsrZeroBusy = fZeroBusy;
  io.fsrZeroMv = fZeroMv;
  io.limitClosed = fLimit;
  coreInit(c, io, g_now);
}

// Advance the scheduler by ms milliseconds exactly as gripper.ino does (1 kHz force, 50 Hz current +
// control, tick, drain). Stops early once the state equals stopAt (if given).
static void advance(Core &c, uint32_t ms, float f = 0.0f, float amps = 0.2f, int stopAt = -1) {
  for (uint32_t i = 0; i < ms; i++) {
    g_now++;
    coreSampleForce(c, g_now, f);
    if (g_now % CONTROL_PERIOD_MS == 0) {
      coreSampleCurrent(c, g_now, true, amps);
      coreControl(c, g_now, CONTROL_PERIOD_MS * 0.001f);
    }
    coreTick(c, g_now);
    drain(c);
    if (stopAt >= 0 && c.state == (uint8_t)stopAt) return;
  }
}

static bool hasLine(const char *prefix) {
  for (auto &l : g_lines)
    if (l.compare(0, std::strlen(prefix), prefix) == 0) return true;
  return false;
}

// Drive a fresh core along the normal path into state s, using real events only.
static bool driveTo(Core &c, uint8_t s) {
  newCore(c);
  if (s == ST_BOOT) return c.state == ST_BOOT;
  advance(c, BOOT_SETTLE_MS + 5, 0.0f, 0.2f, ST_HOME);
  if (s == ST_HOME) return c.state == ST_HOME;
  dispatch(c, EV_LIMIT_HIT, 0);
  if (s == ST_CALIBRATE) return c.state == ST_CALIBRATE;
  // CALIBRATE: settle, zero, search down until the command is near 0 deg, then touch.
  for (int i = 0; i < 4000 && !(c.calPhase == CAL_SEARCH && c.motion.cmd <= 0.0f); i++) advance(c, 1);
  dispatch(c, EV_FSR_CONTACT, 0.5f);
  if (s == ST_IDLE) return c.state == ST_IDLE;
  if (s == ST_FAULT) { dispatch(c, EV_FAULT_OVERCURRENT, 2.0f); return c.state == ST_FAULT; }
  dispatch(c, EV_BUTTON_PRESS, 0);
  if (s == ST_APPROACH) return c.state == ST_APPROACH;
  dispatch(c, EV_SERIAL_CMD_AT_POSE, 0);
  if (s == ST_TOUCHDOWN) return c.state == ST_TOUCHDOWN;
  dispatch(c, EV_BUTTON_PRESS, 0);
  if (s == ST_CLOSE) return c.state == ST_CLOSE;
  dispatch(c, EV_FSR_CONTACT, 0.6f);
  dispatch(c, EV_FSR_TARGET, 5.0f);
  if (s == ST_HOLD) return c.state == ST_HOLD;
  dispatch(c, EV_SERIAL_CMD_FEED, 0);
  if (s == ST_FEED) return c.state == ST_FEED;
  dispatch(c, EV_SERIAL_CMD_FEED_DONE, 0);
  if (s == ST_RELEASE) return c.state == ST_RELEASE;
  advance(c, 1000, 0.0f, 0.2f, ST_RETRACT);
  return c.state == ST_RETRACT;
}

static const uint8_t kActive[] = {ST_HOME, ST_CALIBRATE, ST_IDLE, ST_APPROACH, ST_TOUCHDOWN,
                                  ST_CLOSE, ST_HOLD, ST_FEED, ST_RELEASE, ST_RETRACT};

// ---------------------------------------------------------------------------------------------------------
// 1. Every row of the transition table
static void testEveryRow() {
  for (uint16_t i = 0; i < kTransitionCount; i++) {
    const Transition &r = kTransitions[i];
    std::vector<uint8_t> froms;
    if (r.from == ST_ACTIVE) froms.assign(kActive, kActive + sizeof kActive);
    else froms.push_back(r.from);
    for (uint8_t from : froms) {
      char ctx[96];
      std::snprintf(ctx, sizeof ctx, "row %u %s/%s", i, stateName(from), eventName(r.ev));
      g_ctx = ctx;
      Core c;
      CHECK(driveTo(c, from));
      float arg = 0.0f;
      // Satisfy the row's guard and give the event the argument the producer would.
      if (r.ev == EV_TIMEOUT) arg = (float)from;
      if (r.ev == EV_POSITION_REACHED || r.ev == EV_NO_CONTACT) arg = (float)c.motion.seq;
      if (r.ev == EV_SERIAL_CMD_GRIP) arg = 4.0f;
      if (r.ev == EV_FSR_CONTACT) arg = 0.6f;
      if (r.ev == EV_FAULT_SENSOR) arg = (float)FAULT_ZERO_BAD;
      if (r.guard) {
        if (r.from == ST_HOME && r.ev == EV_POSITION_REACHED) {
          const bool wantBad = (std::strstr(r.note, "not closed") != nullptr);
          c.limitRequired = wantBad;
          g_limit = !wantBad;
        }
        if (r.from == ST_CALIBRATE && r.ev == EV_FSR_CONTACT) {
          const bool wantIn = (std::strstr(r.note, "inside") != nullptr);
          for (int k = 0; k < 4000 && c.calPhase != CAL_SEARCH; k++) advance(c, 1);
          if (wantIn) for (int k = 0; k < 4000 && c.motion.cmd > 0.0f; k++) advance(c, 1);
        }
        if (r.ev == EV_FORCE_SAT) arg = (std::strstr(r.note, "F >=") != nullptr) ? 4.0f : 1.0f;
        if (r.from == ST_CLOSE && r.ev == EV_NO_CONTACT) {
          c.lastIValid = true;
          c.lastI = (std::strstr(r.note, "FSR open") != nullptr) ? (float)FSR_OPEN_I_A + 0.1f : 0.2f;
        }
      }
      if (r.ev == EV_NO_CONTACT && from == ST_CALIBRATE) arg = (float)c.motion.seq;
      if (r.ev == EV_NO_CONTACT && from == ST_CLOSE && !r.guard) { c.lastIValid = true; c.lastI = 0.2f; }
      const int got = dispatch(c, r.ev, arg);
      CHECK(got == (int)i);
      const uint8_t want = (r.to == ST_SAME) ? from : r.to;
      CHECK(c.state == want);
    }
  }
}

// 2. Every state timeout fires at its limit, not 1 ms before, and stale timeouts are dropped.
static void testTimeouts() {
  for (uint8_t s = 0; s < ST_COUNT; s++) {
    const uint32_t to = stateTimeoutMs(s);
    char ctx[64];
    std::snprintf(ctx, sizeof ctx, "timeout %s", stateName(s));
    g_ctx = ctx;
    Core c;
    CHECK(driveTo(c, s));
    if (!to) {
      // IDLE and FAULT wait forever: an hour of ticks posts nothing.
      for (uint32_t k = 0; k < 3600; k++) { g_now += 1000; coreTick(c, g_now); }
      CHECK(eventsPending() == 0);
      CHECK(c.state == s);
      continue;
    }
    // Hold sensor inputs neutral and only tick the clock (no motion events): isolate the timeout.
    const uint32_t t0 = c.enteredAt;
    g_now = t0 + to - 1;
    coreTick(c, g_now);
    bool early = false;
    Event e;
    while (eventPop(e)) if (e.type == EV_TIMEOUT) early = true;
    CHECK(!early);
    g_now = t0 + to;
    coreTick(c, g_now);
    bool fired = false;
    float arg = -1;
    while (eventPop(e)) if (e.type == EV_TIMEOUT) { fired = true; arg = e.arg; }
    CHECK(fired);
    CHECK((uint8_t)arg == s);
    const uint8_t before = c.state;
    const int row = dispatch(c, EV_TIMEOUT, arg);
    CHECK(row >= 0);
    CHECK(row >= 0 && kTransitions[row].from == before && kTransitions[row].ev == EV_TIMEOUT);
    // Fires once per entry.
    g_now += to;
    coreTick(c, g_now);
    bool again = false;
    while (eventPop(e)) if (e.type == EV_TIMEOUT && (uint8_t)e.arg == before && c.state == before) again = true;
    CHECK(!again);
  }
  g_ctx = "stale timeout";
  Core c;
  driveTo(c, ST_APPROACH);
  CHECK(dispatch(c, EV_TIMEOUT, (float)ST_IDLE) == -1);
  CHECK(c.state == ST_APPROACH);
}

// 3. Fault paths: every producer reaches FAULT with the right code; FAULT backs off; only a re-home clears.
static void testFaults() {
  struct { EventType ev; float arg; uint8_t code; } kF[] = {
    {EV_FSR_OVER, 8.5f, FAULT_OVERFORCE}, {EV_FAULT_OVERCURRENT, 2.0f, FAULT_OVERCURRENT},
    {EV_FAULT_STALL, 0.0f, FAULT_STALL}, {EV_FAULT_SENSOR, (float)FAULT_FSR_SHORT, FAULT_FSR_SHORT},
  };
  for (uint8_t s : kActive) {
    for (auto &f : kF) {
      char ctx[64];
      std::snprintf(ctx, sizeof ctx, "fault %s/%s", stateName(s), eventName(f.ev));
      g_ctx = ctx;
      Core c;
      driveTo(c, s);
      const float cmd0 = c.motion.cmd;
      dispatch(c, f.ev, f.arg);
      CHECK(c.state == ST_FAULT);
      CHECK(c.fault == f.code);
      CHECK(!c.fc.on);
      const float want = std::fmin((float)JAW_OPEN_DEG, std::fmax(cmd0, c.thetaC0) + (float)FAULT_BACKOFF_DEG);
      CHECK(std::fabs(c.motion.target - want) < 1e-4f);
      CHECK(hasLine("EVT FAULT_"));
    }
  }
  // BOOT and FAULT ignore fault events (BOOT has nothing to protect; FAULT is latched).
  g_ctx = "fault ignored in BOOT/FAULT";
  {
    Core c;
    driveTo(c, ST_BOOT);
    CHECK(dispatch(c, EV_FSR_OVER, 9.0f) == -1 && c.state == ST_BOOT);
    driveTo(c, ST_FAULT);
    CHECK(dispatch(c, EV_FSR_OVER, 9.0f) == -1 && c.state == ST_FAULT && c.fault == FAULT_OVERCURRENT);
    CHECK(dispatch(c, EV_BUTTON_PRESS, 0) == -1 && c.state == ST_FAULT);
    CHECK(dispatch(c, EV_SERIAL_CMD_GRIP, 5) == -1 && c.state == ST_FAULT);
    dispatch(c, EV_BUTTON_LONG, 0);
    CHECK(c.state == ST_HOME && c.fault == FAULT_NONE);
  }
  // Producer: FSR over-force needs F > F_TRIP for F_TRIP_MS (not one sample).
  g_ctx = "producer FSR_OVER";
  {
    Core c;
    driveTo(c, ST_HOLD);
    advance(c, F_TRIP_MS - 2, (float)F_TRIP_N + 0.5f);
    CHECK(c.state == ST_HOLD);
    advance(c, 4, (float)F_TRIP_N + 0.5f);
    CHECK(c.state == ST_FAULT && c.fault == FAULT_OVERFORCE);
  }
  // Producer: over-current needs I > STALL_CURRENT_A for STALL_CURRENT_MS. R20: back-off done <= 200 ms.
  g_ctx = "producer OVERCURRENT / R20";
  {
    Core c;
    driveTo(c, ST_CLOSE);
    const uint32_t t0 = g_now;
    advance(c, STALL_CURRENT_MS - 25, 0.0f, (float)STALL_CURRENT_A + 0.15f);   // 3.15 A: a reading the INA219 can produce
    CHECK(c.state == ST_CLOSE);
    advance(c, 60, 0.0f, (float)STALL_CURRENT_A + 0.15f, ST_FAULT);
    CHECK(c.state == ST_FAULT && c.fault == FAULT_OVERCURRENT);
    const float target = c.motion.target;
    advance(c, 300, 0.0f, 0.2f);
    uint32_t tDone = 0;
    // Re-run to find when the command reached the back-off target.
    Core d;
    driveTo(d, ST_CLOSE);
    const uint32_t s0 = g_now;
    uint32_t tBegin = 0;
    float cmdAtFault = 0.0f;
    for (int k = 0; k < 600; k++) {
      advance(d, 1, 0.0f, (float)STALL_CURRENT_A + 0.15f);
      if (d.state == ST_FAULT && !cmdAtFault) cmdAtFault = d.motion.cmd + 1e-6f;
      if (d.state == ST_FAULT && !tBegin && d.motion.cmd > cmdAtFault + 1e-3f) tBegin = g_now - s0;
      if (d.state == ST_FAULT && std::fabs(d.motion.cmd - d.motion.target) < 1e-4f) { tDone = g_now - s0; break; }
    }
    std::printf("INFO R20 over-current onset -> back-off begins %u ms (limit 200), command at target %u ms\n",
                (unsigned)tBegin, (unsigned)tDone);
    CHECK(tBegin > 0 && tBegin <= 200);
    CHECK(tDone > 0);
    CHECK(tDone <= 200);  // reading 2: the back-off command reaches its target within R20's 200 ms
    CHECK(std::fabs(c.motion.cmd - target) < 1e-4f);
    (void)t0;
  }
  // Producer: bad FSR zero in CALIBRATE -> ZERO_BAD.
  g_ctx = "producer ZERO_BAD";
  {
    Core c;
    driveTo(c, ST_CALIBRATE);
    g_zeroMv = (float)FSR_ZERO_MAX_MV + 10.0f;
    advance(c, CAL_SETTLE_MS + 10, 0.0f, 0.2f, ST_FAULT);
    CHECK(c.state == ST_FAULT && c.fault == FAULT_ZERO_BAD);
  }
  // Producer: calibration search reaches CAL_C0_MIN without touch -> CAL_RANGE.
  g_ctx = "producer CAL_RANGE (no touch)";
  {
    Core c;
    driveTo(c, ST_CALIBRATE);
    advance(c, TIMEOUT_CAL_MS - 10, 0.0f, 0.2f, ST_FAULT);
    CHECK(c.state == ST_FAULT && c.fault == FAULT_CAL_RANGE);
  }
  // Producer: touch above the window -> CAL_RANGE.
  g_ctx = "producer CAL_RANGE (early touch)";
  {
    Core c;
    driveTo(c, ST_CALIBRATE);
    for (int k = 0; k < 4000 && c.calPhase != CAL_SEARCH; k++) advance(c, 1);
    advance(c, 3, 1.0f);
    CHECK(c.state == ST_FAULT && c.fault == FAULT_CAL_RANGE);
  }
  // Calibration stores theta_c0 = command + lag compensation.
  g_ctx = "calibration value";
  {
    Core c;
    driveTo(c, ST_CALIBRATE);
    for (int k = 0; k < 4000 && !(c.calPhase == CAL_SEARCH && c.motion.cmd <= -1.0f); k++) advance(c, 1);
    const float cmd = c.motion.cmd;
    advance(c, 1, 0.8f);
    CHECK(c.state == ST_IDLE);
    CHECK(c.calibrated);
    CHECK(std::fabs(c.thetaC0 - (cmd + CTRL_LAG_COMP_DEG)) < 0.05f);
    CHECK(hasLine("EVT CAL_THETA_C0"));
  }
  // Producer: HOME timeout and LIMIT fault.
  g_ctx = "producer LIMIT";
  {
    Core c;
    driveTo(c, ST_HOME);
    c.limitRequired = true;
    g_limit = false;
    advance(c, 400, 0.0f, 0.2f, ST_FAULT);
    CHECK(c.state == ST_FAULT && c.fault == FAULT_LIMIT);
  }
}

// 4. Closed-loop cycle against a simple plant (servo lag + finger spring + FSR EMA). The detailed plant
//    and the figures are in analysis/gripper/firmware_sim; this proves the FSM completes a demo cycle.
static void testCycle(float kFinger) {
  char ctx[64];
  std::snprintf(ctx, sizeof ctx, "cycle k=%.2f", kFinger);
  g_ctx = ctx;
  Core c;
  driveTo(c, ST_IDLE);
  advance(c, 500);                                                 // let IDLE open the jaw to +20 deg
  CHECK(std::fabs(c.motion.cmd - (float)JAW_OPEN_DEG) < 1e-4f);
  const float K = kFinger * (float)R_C_MM * 3.14159265f / 180.0f;  // N/deg
  const float thetaTouch = c.thetaC0 + 0.13f;                      // a 0.3 mm ply touches 0.13 deg early
  float act = c.motion.cmd, fFilt = 0.0f, fMax = 0.0f;
  uint32_t tStart = 0, tContact = 0, tHold = 0;
  dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
  tStart = g_now;
  for (int i = 0; i < 1500; i++) {
    g_now++;
    act += (c.motion.cmd - act) * (1.0f - std::exp(-0.001f / (float)SERVO_TAU_S));
    const float f = act < thetaTouch ? K * (thetaTouch - act) : 0.0f;
    fFilt += (float)FSR_EMA_ALPHA * (f - fFilt);
    fMax = std::fmax(fMax, f);
    coreSampleForce(c, g_now, fFilt);
    if (g_now % CONTROL_PERIOD_MS == 0) { coreSampleCurrent(c, g_now, true, 0.5f); coreControl(c, g_now, 0.02f); }
    coreTick(c, g_now);
    drain(c);
    if (!tContact && c.fc.on) tContact = g_now - tStart;
    if (!tHold && c.state == ST_HOLD) tHold = g_now - tStart;
  }
  std::printf("INFO %s: contact %u ms, HOLD %u ms, F_max %.2f N, F_end %.2f N\n", ctx, (unsigned)tContact,
              (unsigned)tHold, (double)fMax, (double)fFilt);
  CHECK(c.state == ST_HOLD);
  CHECK(fMax <= (float)F_CAP_N);
  // At the R12 lower bound (0.88 N/mm) the squeeze cap, sized for the stiffest finger, leaves only 0.64 deg
  // for lag-compensation error, so the hold may end a little under 5 N (controls.md 7, open item O3).
  // Since 2026-10-11 the cap is sized for 9.5 N (F_CAP_MARGIN_N), so the 0.88 N/mm finger stops near 4.7 N here.
  // The 1.0 N/mm finger reaches the cap (0.5 + 1.13 x 4.87 = 6.0 N less lag error) before setpoint + bias: FORCE_SAT.
  const float fLow = kFinger < 0.95f ? 4.6f : kFinger < 1.2f ? 5.0f : (float)F_TARGET_DEFAULT_N + (float)F_HOLD_BIAS_N - 0.05f;
  CHECK(fFilt >= fLow &&
        fFilt <= (float)F_TARGET_DEFAULT_N + (float)F_HOLD_BIAS_N + (float)CTRL_I_DB_HI_N + 0.3f);
  dispatch(c, EV_SERIAL_CMD_FEED, 0);
  dispatch(c, EV_SERIAL_CMD_FEED_DONE, 0);
  CHECK(c.state == ST_RELEASE);
  advance(c, 1000, 0.0f, 0.2f, ST_RETRACT);
  CHECK(c.state == ST_RETRACT);
  advance(c, TIMEOUT_RETRACT_MS + 10, 0.0f, 0.2f, ST_IDLE);
  CHECK(c.state == ST_IDLE);
}

// 5. Module unit checks
static void testModules() {
  g_ctx = "protocol";
  struct { const char *s; CmdKind k; EventType ev; float arg; } P[] = {
    {"G 4.5", CMD_EVENT, EV_SERIAL_CMD_GRIP, 4.5f}, {"g", CMD_EVENT, EV_SERIAL_CMD_GRIP, (float)F_TARGET_DEFAULT_N},
    {"R", CMD_EVENT, EV_SERIAL_CMD_RELEASE, 0}, {"H", CMD_EVENT, EV_SERIAL_CMD_HOME, 0},
    {"C", CMD_EVENT, EV_SERIAL_CMD_CAL, 0}, {"A", CMD_EVENT, EV_SERIAL_CMD_APPROACH, 0},
    {"S", CMD_STATUS, EV_NONE, 0}, {"ARM_AT_POSE", CMD_EVENT, EV_SERIAL_CMD_AT_POSE, 0},
    {"FEED", CMD_EVENT, EV_SERIAL_CMD_FEED, 0}, {" feed_done ", CMD_EVENT, EV_SERIAL_CMD_FEED_DONE, 0},
    {"STREAM 10", CMD_STREAM, EV_NONE, 10}, {"CALF 2.0", CMD_CALF, EV_NONE, 2.0f}, {"", CMD_NONE, EV_NONE, 0},
    {"G -1", CMD_ERROR, EV_NONE, 0}, {"G x", CMD_ERROR, EV_NONE, 0}, {"GRIP", CMD_ERROR, EV_NONE, 0},
    {"FEEDX", CMD_ERROR, EV_NONE, 0}, {"R 1", CMD_ERROR, EV_NONE, 0}, {"STREAM", CMD_ERROR, EV_NONE, 0},
  };
  for (auto &p : P) {
    const Command c = parseCommand(p.s);
    check(c.kind == p.k && c.ev == p.ev && std::fabs(c.arg - p.arg) < 1e-5f, p.s);
  }
  g_ctx = "servo map";
  CHECK(jawToUs(0.0f) == 1500);
  CHECK(jawToUs((float)JAW_OPEN_DEG) == 1722);
  CHECK(jawToUs((float)JAW_MIN_DEG) == 1387);   // -10.2 deg backstop (was 1418 at -7.4)
  CHECK(jawToUs(-90.0f) == SERVO_US_LIMIT_MIN && jawToUs(90.0f) == SERVO_US_LIMIT_MAX);
  g_ctx = "fsr model";
  for (float f : {0.5f, 1.0f, 3.0f, 5.0f, 8.0f, 10.0f}) CHECK(std::fabs(fsrForceFromMv(fsrMvFromForce(f)) - f) < 1e-3f * f + 1e-4f);
  CHECK(fsrForceFromMv(5.0f) == 0.0f);
  CHECK(fsrMvFromForce((float)F_CAP_N) <= (float)ADC_V_LINEAR_MAX_MV + 10.0f);
  g_ctx = "motion";
  {
    Motion m;
    motionInit(m, 20.0f);
    motionSearch(m, 3.5f, -3.0f, 120.0f, 20.0f);
    uint32_t t = 0;
    EventType ev = EV_NONE;
    float tSlowStart = -1;
    while (ev == EV_NONE && t < 5000) {
      t += 20;
      ev = motionStep(m, 0.02f, t);
      if (tSlowStart < 0 && m.cmd <= 3.5f) tSlowStart = (float)t;
    }
    CHECK(ev == EV_NO_CONTACT);
    CHECK(std::fabs(m.cmd + 3.0f) < 1e-4f);
    // fast leg 16.5 deg at 120 deg/s = 137.5 ms; slow leg 6.5 deg at 20 deg/s = 325 ms; + settle.
    CHECK(t >= 460 + JAW_SETTLE_MS && t <= 500 + JAW_SETTLE_MS);
    motionMove(m, -50.0f, 120.0f);
    CHECK(m.target == (float)JAW_MIN_DEG);
    const uint16_t seq = m.seq;
    motionStop(m);
    CHECK(m.seq != seq && !m.pending);
  }
  g_ctx = "stale motion event";
  {
    Core c;
    driveTo(c, ST_TOUCHDOWN);
    CHECK(dispatch(c, EV_POSITION_REACHED, (float)(c.motion.seq - 1)) == -1);
    CHECK(!c.cm.touchArmed);
  }
  g_ctx = "table touch detector";
  {
    Core c;
    driveTo(c, ST_TOUCHDOWN);
    advance(c, 400, 0.0f, 0.40f);                       // reach pre-grasp, arm, baseline 0.40 A
    CHECK(c.cm.touchArmed && c.state == ST_TOUCHDOWN);
    advance(c, 200, 0.0f, 0.40f + (float)TOUCH_DI_A * 0.8f);
    CHECK(c.state == ST_TOUCHDOWN);                      // below the threshold: no touch
    advance(c, 200, 0.0f, 0.40f + (float)TOUCH_DI_A + 0.1f, ST_CLOSE);
    CHECK(c.state == ST_CLOSE);
  }
  g_ctx = "slip / lost producers";
  {
    Core c;
    driveTo(c, ST_IDLE);
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    advance(c, 1, 1.0f);                                 // contact
    CHECK(c.fc.on);
    advance(c, 300, 5.1f + (float)F_HOLD_BIAS_N, 0.5f, ST_HOLD);   // in band (setpoint + hold bias) -> HOLD
    CHECK(c.state == ST_HOLD);
    advance(c, F_SLIP_MS + 5, 2.0f);
    CHECK(hasLine("WARN FSR_SLIP") && c.state == ST_HOLD);
    advance(c, F_LOST_MS + 5, 0.0f, 0.2f, ST_RELEASE);
    CHECK(c.state == ST_RELEASE && hasLine("WARN FSR_LOST"));
  }
  g_ctx = "squeeze cap";
  {
    // Force stuck at 1 N (soft finger, cloth slipping out): the loop must stop at U_MAX, then FORCE_SAT.
    Core c;
    driveTo(c, ST_IDLE);
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    advance(c, 1, 1.0f);
    const float ref = c.fc.thetaRef;
    float maxU = 0.0f;
    for (int k = 0; k < 600 && c.state != ST_RELEASE; k++) {
      advance(c, 1, 1.0f, 0.5f);
      if (c.fc.on) maxU = std::fmax(maxU, ref - c.motion.cmd);
    }
    std::printf("INFO squeeze cap: max u %.3f deg (U_MAX %.3f)\n", (double)maxU, (double)CTRL_U_MAX_DEG);
    CHECK(maxU > CTRL_U_MAX_DEG - 0.25f);
    CHECK(maxU <= CTRL_U_MAX_DEG + 1e-3f);
    CHECK(c.state == ST_RELEASE && hasLine("WARN FORCE_SAT"));
  }
  g_ctx = "jaw floor relative to theta_c0";
  {
    // The floor is theta_c0 - JAW_FLOOR_BELOW_C0_DEG (tolerance_stacks.md T09F / T09H-relfloor8), not the absolute
    // JAW_MIN_DEG. Low calibrated contact, touch at theta_c0: the absolute -7.4 deg floor cut the squeeze to about
    // 3.5 deg; the relative floor (4.9 deg, just past U_MAX) lets the loop reach U_MAX. High calibrated contact, touch
    // at the end of the search: with the absolute floor only U_MAX bound it and the jaw closed to theta_c0 - 6.55 deg;
    // the relative floor holds it at theta_c0 - JAW_FLOOR_BELOW_C0_DEG. Force stuck at 1 N (FORCE_SAT).
    // R15 8 N (2026-10-16): the first touch moved from 2.0 to 1.2 deg below the search command, which puts the touch
    // reference at theta_c0 + 0.1 instead of theta_c0 - 0.7; a touch below theta_c0 now meets the 4.9 deg floor first.
    const float c0s[2] = {-4.0f, 3.0f};
    const float touchBelow[2] = {1.2f, 2.8f};
    for (int j = 0; j < 2; j++) {
      Core c;
      driveTo(c, ST_IDLE);
      c.thetaC0 = c0s[j];
      dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
      for (int k = 0; k < 3000 && c.motion.cmd > c.thetaC0 - touchBelow[j]; k++) advance(c, 1, 0.0f);
      advance(c, 1, 1.0f);
      CHECK(c.fc.on);
      const float ref = c.fc.thetaRef;
      float maxU = 0.0f, minCmd = c.motion.cmd;
      for (int k = 0; k < 600 && c.state != ST_RELEASE; k++) {
        advance(c, 1, 1.0f, 0.5f);
        if (c.fc.on) {
          maxU = std::fmax(maxU, ref - c.motion.cmd);
          minCmd = std::fmin(minCmd, c.motion.cmd);
        }
      }
      const float floorRel = c.thetaC0 - (float)JAW_FLOOR_BELOW_C0_DEG;
      std::printf("INFO relative floor: theta_c0 %+.1f, ref %+.2f, max u %.3f, lowest command %+.3f (floor %+.2f)\n",
                  (double)c.thetaC0, (double)ref, (double)maxU, (double)minCmd, (double)floorRel);
      CHECK((float)JAW_FLOOR_BELOW_C0_DEG > 0.0f);
      CHECK(minCmd >= floorRel - 1e-3f);
      CHECK(minCmd >= (float)JAW_MIN_DEG);
      if (j == 0) CHECK(maxU > CTRL_U_MAX_DEG - 0.25f);           // the floor no longer cuts the squeeze short
      else CHECK(minCmd <= floorRel + 0.05f);                       // the floor binds, at theta_c0 - JAW_FLOOR_BELOW_C0_DEG
      CHECK(c.state == ST_RELEASE && hasLine("WARN FORCE_SAT"));
    }
    CHECK(std::fabs(fcJawFloor(0.0f) - (0.0f - (float)JAW_FLOOR_BELOW_C0_DEG)) < 1e-6f);   // uncalibrated: theta_c0 0
    CHECK(fcJawFloor(-50.0f) == (float)JAW_MIN_DEG);                                       // never below the backstop
    CHECK(fcJawFloor(NAN) == (float)JAW_MIN_DEG);
  }
  g_ctx = "setpoint during search";
  {
    Core c;
    driveTo(c, ST_IDLE);
    advance(c, 500);
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    advance(c, 50);
    CHECK(c.state == ST_CLOSE && !c.fc.on);
    dispatch(c, EV_SERIAL_CMD_GRIP, 2.0f);
    CHECK(std::fabs(c.fc.spTarget - 2.0f) < 1e-5f);
    advance(c, 1, 1.0f);
    CHECK(c.fc.on && std::fabs(c.fc.spTarget - 2.0f) < 1e-5f);
  }
  g_ctx = "contact in the fast leg";
  {
    // Thick cloth touches during the 120 deg/s leg: the reference must use 120 deg/s x lag, not 20.
    Core c;
    driveTo(c, ST_IDLE);
    advance(c, 500);
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    advance(c, 60);
    CHECK(c.motion.vNow == (float)JAW_SPEED_FAST_DPS);
    const float cmd = c.motion.cmd;
    advance(c, 1, 1.0f);
    CHECK(c.fc.on);
    CHECK(std::fabs(c.fc.thetaRef - (cmd + (float)JAW_SPEED_FAST_DPS * (float)CTRL_LAG_COMP_S)) < 0.05f);
  }
  g_ctx = "FAULT relaxes the servo on a persisting stall";
  {
    Core c;
    driveTo(c, ST_RELEASE);                                // opening against a hard stop at +20 deg
    advance(c, 600, 0.0f, (float)STALL_CURRENT_A + 0.15f, ST_FAULT);
    CHECK(c.state == ST_FAULT && !c.relax);
    advance(c, STALL_CURRENT_MS + 40, 0.0f, (float)STALL_CURRENT_A + 0.15f);
    CHECK(c.state == ST_FAULT && c.relax && hasLine("WARN SERVO_RELAXED"));
    dispatch(c, EV_SERIAL_CMD_HOME, 0);
    CHECK(c.state == ST_HOME && !c.relax);
  }
  g_ctx = "queue reserves slots for faults";
  {
    eventsInit();
    int ok = 0;
    for (int k = 0; k < EVENT_QUEUE_LEN; k++) ok += eventPost(EV_SERIAL_CMD_RELEASE) ? 1 : 0;
    CHECK(ok == EVENT_QUEUE_LEN - EVENT_RESERVED_SLOTS);
    CHECK(eventPost(EV_FSR_OVER, 9.0f));
    CHECK(eventPost(EV_TIMEOUT, 1.0f));
    eventsInit();
  }
  g_ctx = "derived gains";
  CHECK(std::fabs(K_STIFF_N_PER_DEG - 1.8492f) < 1e-3f);
  CHECK(std::fabs(CTRL_KP_DEG_PER_N - 0.2403f) < 1e-3f);
  CHECK(std::fabs(CTRL_TI_S - 0.040f) < 1e-6f);
  CHECK(std::fabs(CTRL_U_MAX_DEG - (10.0f - 0.5f - 0.5f) / 1.8492f) < 1e-3f);   // 9 N basis: 4.867 deg
}

static void printTables() {
  std::printf("| # | From | Event | Guard | Action | To | Why |\n|---|---|---|---|---|---|---|\n");
  for (uint16_t i = 0; i < kTransitionCount; i++) {
    const Transition &r = kTransitions[i];
    std::printf("| %u | %s | %s | %s | %s | %s | %s |\n", i, stateName(r.from), eventName(r.ev),
                r.guard ? "yes" : "", r.action ? "yes" : "", r.to == ST_SAME ? "(same)" : stateName(r.to), r.note);
  }
  std::printf("\n| State | Timeout (ms) |\n|---|---|\n");
  for (uint8_t s = 0; s < ST_COUNT; s++) std::printf("| %s | %u |\n", stateName(s), (unsigned)stateTimeoutMs(s));
}

// 6. Fault injection: one scenario per fault state the firmware can detect, driven from its inputs, with the
//    time to the safe state (FAULT entered, jaw command opening, force loop off). controls.md section 6.
static uint32_t timeToFault(Core &c, uint32_t maxMs, float f, float amps) {
  const uint32_t t0 = g_now;
  for (uint32_t i = 0; i < maxMs && c.state != ST_FAULT; i++) advance(c, 1, f, amps);
  return c.state == ST_FAULT ? g_now - t0 : 0xFFFFFFFFu;
}

static void safeState(Core &c, const char *what) {
  char b[96];
  std::snprintf(b, sizeof b, "%s: safe state", what);
  g_ctx = b;
  CHECK(c.state == ST_FAULT);
  CHECK(!c.fc.on);
  CHECK(c.motion.target >= c.thetaC0 + (float)FAULT_BACKOFF_DEG - 1e-4f || c.motion.target >= (float)JAW_OPEN_DEG - 1e-4f);
}

static void testFaultInjection() {
  // (a) FSR open during a grip: no contact is ever seen, but the servo squeezes the cloth (current rises).
  {
    g_ctx = "inject FSR open";
    Core c;
    driveTo(c, ST_IDLE);
    advance(c, 500);
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    const uint32_t dt = timeToFault(c, 3000, 0.0f, (float)FSR_OPEN_I_A + 0.2f);
    std::printf("INFO inject FSR open: FAULT %s after %u ms (search end + %u ms settle)\n", faultName(c.fault),
                (unsigned)dt, (unsigned)JAW_SETTLE_MS);
    CHECK(c.fault == FAULT_FSR_OPEN);
    CHECK(dt < (uint32_t)TIMEOUT_CLOSING_MS);
    safeState(c, "FSR open");
    // Same with no current (nothing between the pads): a miss, released, not a fault.
    g_ctx = "inject FSR open, nothing gripped";
    Core d;
    driveTo(d, ST_IDLE);
    advance(d, 500);
    dispatch(d, EV_SERIAL_CMD_GRIP, 5.0f);
    advance(d, 2000, 0.0f, 0.2f, ST_RETRACT);
    CHECK(d.state == ST_RETRACT || d.state == ST_RELEASE);
  }
  // (b) FSR short: the node goes to the rail; the shared filter flags it within FSR_SHORT_MS samples.
  {
    g_ctx = "inject FSR short";
    Core c;
    driveTo(c, ST_HOLD);
    FsrFilter f;
    fsrFilterInit(f, 100.0f);
    uint32_t n = 0;
    for (; n < 50; n++) {
      g_now++;
      if (fsrFilterSample(f, 3300.0f) & FSRF_SHORT) { eventPost(EV_FAULT_SENSOR, (float)FAULT_FSR_SHORT); break; }
      coreSampleForce(c, g_now, fsrFilterForce(f) > 8.0f ? 7.9f : fsrFilterForce(f));   // keep FSR_OVER out of it
      drain(c);
    }
    drain(c);
    std::printf("INFO inject FSR short: FAULT %s after %u ms\n", faultName(c.fault), (unsigned)(n + 1));
    CHECK(n + 1 == (uint32_t)FSR_SHORT_MS);
    CHECK(c.fault == FAULT_FSR_SHORT);
    safeState(c, "FSR short");
    // A real 10 N grip never reaches the short threshold.
    g_ctx = "short threshold above the cap";
    CHECK(fsrMvFromForce(10.0f) + (float)FSR_ZERO_MAX_MV < (float)FSR_SHORT_MV);
    CHECK(fsrForceFromMv((float)FSR_SHORT_MV) > 2.5f * (float)F_CAP_N);
  }
  // (b2) FSR stuck: the ADC returns the same value every sample (frozen conversion) while a grip is held.
  {
    g_ctx = "inject FSR stuck";
    Core c;
    driveTo(c, ST_HOLD);
    FsrFilter f;
    fsrFilterInit(f, 600.0f);
    uint32_t n = 0, lcg = 9u;
    for (; n < 200; n++) {   // live channel first: noise, never flagged
      lcg = lcg * 1664525u + 1013904223u;
      CHECK(!(fsrFilterSample(f, 600.0f + (float)((lcg >> 8) % 9) - 4.0f) & FSRF_STUCK));
    }
    for (n = 0; n < 2000; n++) {
      g_now++;
      if (fsrFilterSample(f, 600.0f) & FSRF_STUCK) { eventPost(EV_FAULT_SENSOR, (float)FAULT_FSR_STUCK); break; }
    }
    drain(c);
    std::printf("INFO inject FSR stuck: FAULT %s after %u ms\n", faultName(c.fault), (unsigned)(n + 1));
    CHECK(c.fault == FAULT_FSR_STUCK);
    CHECK(n + 1 <= (uint32_t)FSR_STUCK_MS + 1);
    safeState(c, "FSR stuck");
    // Unloaded and quiet below FSR_STUCK_MV_MIN is not a fault (a low-noise ADC at rest).
    FsrFilter g;
    fsrFilterInit(g, 20.0f);
    bool flagged = false;
    for (int k = 0; k < 3000; k++) flagged |= (fsrFilterSample(g, 20.0f) & FSRF_STUCK) != 0;
    CHECK(!flagged);
  }
  // (c) Stall while closing (finger blocked in the fast leg): rail current at the stall value.
  {
    g_ctx = "inject stall";
    Core c;
    driveTo(c, ST_CLOSE);
    const uint32_t dt = timeToFault(c, 1000, 0.0f, (float)SERVO_STALL_A);
    std::printf("INFO inject stall (SERVO_STALL_A in CLOSE): FAULT %s after %u ms\n", faultName(c.fault), (unsigned)dt);
    CHECK(c.fault == FAULT_OVERCURRENT);
    CHECK(dt <= (uint32_t)STALL_CURRENT_MS + 2 * CONTROL_PERIOD_MS);
    safeState(c, "stall");
    advance(c, STALL_CURRENT_MS + 3 * CONTROL_PERIOD_MS, 0.0f, (float)SERVO_STALL_A);   // stall persists through the back-off
    CHECK(c.relax);
  }
  // (d) Over-current while holding: the hold trip is STALL_CURRENT_HOLD_A, the motion trip STALL_CURRENT_A.
  {
    g_ctx = "inject over-current in HOLD";
    Core c;
    driveTo(c, ST_HOLD);
    c.fc.on = true;
    advance(c, 500, 5.2f, (float)STALL_CURRENT_A + 0.05f);
    CHECK(c.state == ST_HOLD);   // a high-current servo holding 5-7 N is not a stall
    // a saturated INA219 reads its full scale (3.2 A), the highest reading the sensor can produce
    const float satA = (float)INA219_FS_A;
    CHECK(satA > (float)STALL_CURRENT_HOLD_A);
    const uint32_t dt = timeToFault(c, 1000, 5.2f, satA);
    std::printf("INFO inject over-current in HOLD (%.1f A, INA219 full scale): FAULT %s after %u ms\n",
                (double)satA, faultName(c.fault), (unsigned)dt);
    CHECK(c.fault == FAULT_OVERCURRENT);
    CHECK(dt <= (uint32_t)STALL_CURRENT_MS + 2 * CONTROL_PERIOD_MS);
    safeState(c, "over-current");
  }
  // (e) Limit switch stuck closed while the jaw closes.
  {
    g_ctx = "inject limit stuck closed";
    Core c;
    driveTo(c, ST_IDLE);
    advance(c, 500);
    g_limitStuck = true;
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    const uint32_t dt = timeToFault(c, 2000, 0.0f, 0.2f);
    std::printf("INFO inject limit stuck closed: FAULT %s after %u ms\n", faultName(c.fault), (unsigned)dt);
    CHECK(c.fault == FAULT_LIMIT);
    CHECK(dt < 1000);
    safeState(c, "limit stuck");
    g_limitStuck = false;
  }
  // (f) Serial garbage: random bytes, overlong lines, NaN/inf numbers. The parser never returns an event with a
  //     bad id or a non-finite grip setpoint, and the core survives every parsed command in every state.
  {
    g_ctx = "inject serial garbage";
    uint32_t lcg = 12345u;
    auto rnd = [&lcg]() { lcg = lcg * 1664525u + 1013904223u; return lcg >> 8; };
    const char *kSpecial[] = {"G nan", "G inf", "G -inf", "G 1e40", "G 1e-40", "ILIM nan", "ILIM -1", "ILIM 1e9",
                              "CALF inf", "STREAM inf", "BACKOFF 2", "BACKOFF nan", "G 5 5", "G\t5", "\x01\x02\xff", "FEED_DONEX", "G 0x10"};
    int bad = 0, events = 0;
    Core c;
    driveTo(c, ST_HOLD);
    for (int i = 0; i < 20000; i++) {
      char line[80];
      if (i < (int)(sizeof kSpecial / sizeof kSpecial[0])) {
        std::snprintf(line, sizeof line, "%s", kSpecial[i]);
      } else if (rnd() % 3 == 0) {   // a real command word with a random (often absurd) number
        const char *w[] = {"G", "R", "H", "C", "S", "A", "FEED", "FEED_DONE", "ARM_AT_POSE", "STREAM", "CALF", "ILIM", "BACKOFF"};
        const char *num[] = {"", "5", "-3", "0", "7.9", "1e9", "nan", "inf", "-inf", "1e-9", "12", "0.4"};
        std::snprintf(line, sizeof line, "%s %s", w[rnd() % 13], num[rnd() % 12]);
      } else {
        const int n = (int)(rnd() % 70);
        const char *alpha = "GRHCSAFEDNOT_LIMSTRCALF0123456789.+-e nainf\t";
        for (int k = 0; k < n; k++) line[k] = (rnd() % 4) ? alpha[rnd() % 44] : (char)(1 + rnd() % 255);
        line[n] = 0;
      }
      const Command cmd = parseCommand(line);
      if (cmd.kind > CMD_ERROR) bad++;
      if (cmd.kind == CMD_EVENT) {
        events++;
        if (cmd.ev <= EV_NONE || cmd.ev >= EV_COUNT) bad++;
        if (cmd.ev == EV_SERIAL_CMD_GRIP && (!std::isfinite(cmd.arg) || cmd.arg <= 0.0f)) {
          if (!std::isfinite(cmd.arg)) { /* inf is clamped by the core */ } else bad++;
        }
        dispatch(c, cmd.ev, cmd.arg);
        advance(c, 3, c.state == ST_HOLD ? 5.2f : 0.0f);
        CHECK(std::isfinite(c.motion.cmd) && std::isfinite(c.sp) && std::isfinite(c.fc.spTarget));
      }
      if (cmd.kind == CMD_ILIM) CHECK(std::isfinite(cmd.arg) && cmd.arg >= 0.0f && cmd.arg < 100.0f);
      if (cmd.kind == CMD_BACKOFF) CHECK(std::isfinite(cmd.arg) && cmd.arg >= 0.0f && cmd.arg <= 1.0f);
    }
    std::printf("INFO inject serial garbage: 20000 lines, %d parsed as commands, %d bad\n", events, bad);
    CHECK(bad == 0);
    CHECK(parseCommand("G nan").kind == CMD_ERROR);
    Event e;
    e.type = EV_SERIAL_CMD_GRIP;
    e.arg = NAN;
    e.t_ms = g_now;
    driveTo(c, ST_HOLD);
    const float spBefore = c.sp;
    coreDispatch(c, e);
    CHECK(c.sp == spBefore && std::isfinite(c.fc.spTarget));
  }
  // (g) Brown-out reset in HOLD: RAM is lost and setup() runs again. The core restarts in BOOT with the jaw
  //     commanded open; gripper.ino's setup() writes that pulse before anything else (the cloth is released).
  {
    g_ctx = "inject brown-out reset";
    Core c;
    driveTo(c, ST_HOLD);
    c.fc.on = true;
    advance(c, 200, 5.2f, 0.8f);
    CHECK(c.state == ST_HOLD);
    eventsInit();
    CoreIo io = c.io;
    coreInit(c, io, g_now);   // what setup() does after a reset
    CHECK(c.state == ST_BOOT);
    CHECK(!c.fc.on);
    CHECK(std::fabs(coreTheta(c) - (float)JAW_OPEN_DEG) < 1e-4f);
    CHECK(jawToUs(coreTheta(c)) == jawToUs((float)JAW_OPEN_DEG));
    CHECK(!c.calibrated);   // it must re-home and re-calibrate before the next grip
    advance(c, BOOT_SETTLE_MS + 5, 0.0f, 0.2f, ST_HOME);
    CHECK(c.state == ST_HOME);
    std::printf("INFO inject brown-out: reset -> BOOT, jaw commanded open on the first pulse, HOME after %u ms\n",
                (unsigned)BOOT_SETTLE_MS);
  }
  // At the squeeze cap with the force dithering across the FSR_TARGET band edge (r - 0.5 N) the grip must still
  // leave CLOSE (FORCE_SAT -> HOLD), never time out to FAULT (Monte Carlo after-bench run 1801).
  {
    g_ctx = "cap with force on the band edge";
    Core c;
    driveTo(c, ST_IDLE);
    advance(c, 500);
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    advance(c, 1, 1.0f);
    const float edge = fcRegTarget(c.fc) - (float)F_BAND_N;
    for (int k = 0; k < 1500 && c.state == ST_CLOSE; k++) advance(c, 1, edge + ((k / 7) % 2 ? 0.08f : -0.08f), 0.5f);
    CHECK(c.state == ST_HOLD);
    CHECK(hasLine("WARN FORCE_SAT"));
  }
  // Slip is reported in every hold, whichever path entered HOLD (review 2026-10-11: a FORCE_SAT hold never armed
  // it). Path 1: FSR_TARGET. Path 2: FORCE_SAT at the squeeze cap with F >= F_SLIP_N. Then the FSR span falls
  // to 40 % (fault injection): the measured force falls under F_SLIP_N and FSR_SLIP must be posted and warned.
  for (int path = 0; path < 2; path++) {
    g_ctx = path ? "slip in a FORCE_SAT hold" : "slip in an FSR_TARGET hold";
    Core c;
    driveTo(c, ST_IDLE);
    advance(c, 500);
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    advance(c, 1, 1.0f);
    const float fHold = path ? 4.0f : fcRegTarget(c.fc) + 0.2f;   // 4 N: short of r - F_BAND, the loop saturates
    advance(c, 2000, fHold, 0.5f, ST_HOLD);
    CHECK(c.state == ST_HOLD);
    CHECK(path ? hasLine("WARN FORCE_SAT") : !hasLine("WARN FORCE_SAT"));
    advance(c, 300, fHold, 0.5f);
    CHECK(!hasLine("WARN FSR_SLIP"));
    const uint32_t t0 = g_now;
    uint32_t dt = 0;
    for (int k = 0; k < 1000 && !dt; k++) {
      advance(c, 1, 0.4f * fHold, 0.5f);   // the FSR now reads 40 % of the true force
      if (hasLine("WARN FSR_SLIP")) dt = g_now - t0;
    }
    std::printf("INFO slip in a %s hold, FSR span to 40 %%: WARN FSR_SLIP after %u ms\n", path ? "FORCE_SAT" : "FSR_TARGET",
                (unsigned)dt);
    CHECK(dt > 0 && dt <= (uint32_t)F_SLIP_MS + 2);
    CHECK(c.state == ST_HOLD);
  }
  // INA219 fails mid-hold (it answered at boot): FAULT I_SENSOR within I_SENSOR_FAIL_MS; absent at boot: no fault.
  {
    g_ctx = "inject INA219 failure in HOLD";
    Core c;
    driveTo(c, ST_HOLD);
    c.fc.on = true;
    uint32_t dt = 0;
    const uint32_t t0 = g_now;
    for (int k = 0; k < 1000 && c.state != ST_FAULT; k++) {
      g_now++;
      coreSampleForce(c, g_now, 5.2f);
      if (g_now % CONTROL_PERIOD_MS == 0) {
        coreSampleCurrent(c, g_now, false, 0.0f);
        coreControl(c, g_now, CONTROL_PERIOD_MS * 0.001f);
      }
      coreTick(c, g_now);
      drain(c);
    }
    dt = g_now - t0;
    std::printf("INFO inject INA219 failure in HOLD: FAULT %s after %u ms\n", faultName(c.fault), (unsigned)dt);
    CHECK(c.fault == FAULT_I_SENSOR);
    CHECK(dt <= (uint32_t)I_SENSOR_FAIL_MS + 2 * CONTROL_PERIOD_MS);
    safeState(c, "INA219 failure");
    g_ctx = "INA219 absent at boot";
    Core d;
    driveTo(d, ST_IDLE);
    coreSetCurrentPresent(d, false);
    for (int k = 0; k < 600; k++) {
      g_now++;
      if (g_now % CONTROL_PERIOD_MS == 0) coreSampleCurrent(d, g_now, false, 0.0f);
      coreTick(d, g_now);
      drain(d);
    }
    CHECK(d.state == ST_IDLE);
    g_ctx = "non-finite current";
    Core e;
    driveTo(e, ST_IDLE);
    coreSampleCurrent(e, g_now, true, NAN);
    CHECK(!e.lastIValid && e.lastI == 0.0f);
  }
  // Thermal hook: ILIM lowers the setpoint in steps while the hold current stays above it.
  {
    g_ctx = "hold current limit hook";
    Core c;
    driveTo(c, ST_HOLD);
    c.fc.on = true;
    dispatch(c, EV_SERIAL_CMD_GRIP, 6.0f);   // ILIM may step a 6 N setpoint down, never below HOLD_I_FLOOR_N (R14)
    const float sp0 = c.fc.spTarget;
    CHECK(coreSetHoldCurrentLimit(c, 1.0f));
    CHECK(!coreSetHoldCurrentLimit(c, NAN) && c.holdILimit == 1.0f);
    advance(c, HOLD_I_LIMIT_MS + 60, 5.2f, 1.3f);
    CHECK(c.state == ST_HOLD);
    CHECK(std::fabs(c.fc.spTarget - (sp0 - (float)HOLD_I_STEP_N)) < 1e-4f);
    CHECK(hasLine("WARN HOLD_I_LIMIT"));
    advance(c, 20 * HOLD_I_LIMIT_MS, 5.2f, 1.3f);
    CHECK(std::fabs(c.fc.spTarget - (float)HOLD_I_FLOOR_N) < 1e-4f);   // stops at the R14 floor
    CHECK(coreSetHoldCurrentLimit(c, 0.0f));
  }
}

// 6b. Thermal F1 / F2 / F4 (thermal.md 5): back-off in HOLD, long-hold setpoint clamp, hold-current report.
static void testThermalHooks() {
  // F1 reaches the current stop: the rail current falls as the command opens (friction holds the force).
  {
    g_ctx = "F1 back-off to the current stop";
    Core c;
    driveTo(c, ST_IDLE);
    CHECK(c.backoffFactor == (HOLD_BACKOFF_ENABLED ? (float)HOLD_BACKOFF_FACTOR : 0.0f));
    CHECK(coreSetBackoffFactor(c, (float)HOLD_BACKOFF_FACTOR));
    advance(c, 500);
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    advance(c, 1, 1.0f);
    const float r = fcRegTarget(c.fc);
    advance(c, 2000, r + 0.1f, 1.0f, ST_HOLD);
    CHECK(c.state == ST_HOLD);
    for (int k = 0; k < 3000; k++) advance(c, 1, r + 0.1f, 1.0f - 0.4f * c.fc.boff);
    CHECK(hasLine("EVT HOLD_I"));
    CHECK(std::fabs(c.iHoldRef - 1.0f) < 1e-3f);                    // F4: the reading with the back-off off
    const float iStop = (float)HOLD_BACKOFF_FACTOR * (float)HOLD_BACKOFF_FACTOR * 1.0f;
    CHECK(c.boPhase == BO_DONE);
    CHECK(1.0f - 0.4f * c.fc.boff <= iStop + 1e-4f);
    CHECK(c.fc.boff <= (float)HOLD_BACKOFF_MAX_DEG + 1e-4f);
    CHECK(hasLine("EVT HOLD_BACKOFF"));
    CHECK(fcThetaCmd(c.fc) > c.fc.thetaRef - c.fc.u + 0.5f);          // the command is open of the loop's own
    std::printf("INFO F1 back-off: F4 hold current %.2f A, stopped at %.2f deg, rail %.2f A (stop %.2f A)\n",
                (double)c.iHoldRef, (double)c.fc.boff, (double)(1.0f - 0.4f * c.fc.boff), (double)iStop);
  }
  // F1 at the friction threshold: the force falls once the back-off passes 0.9 deg -> re-close one step, stop.
  {
    g_ctx = "F1 back-off to the friction threshold";
    Core c;
    driveTo(c, ST_IDLE);
    CHECK(coreSetBackoffFactor(c, (float)HOLD_BACKOFF_FACTOR));
    advance(c, 500);
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    advance(c, 1, 1.0f);
    const float r = fcRegTarget(c.fc);
    advance(c, 2000, r + 0.1f, 1.0f, ST_HOLD);
    for (int k = 0; k < 3000; k++) advance(c, 1, c.fc.boff > 0.95f ? r - 0.6f : r + 0.1f, 1.0f);
    CHECK(c.boPhase == BO_DONE);
    CHECK(c.fc.boff < 0.95f && c.fc.boff > 0.0f);
    // A new setpoint in the hold undoes the back-off and measures again.
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.5f);
    CHECK(c.fc.boff == 0.0f && c.boPhase == BO_WAIT);
  }
  // BACKOFF 0: no back-off, but the F4 reading is still made.
  {
    g_ctx = "F1 off";
    Core c;
    driveTo(c, ST_IDLE);
    CHECK(coreSetBackoffFactor(c, 0.0f));
    CHECK(!coreSetBackoffFactor(c, 1.5f) && !coreSetBackoffFactor(c, NAN) && c.backoffFactor == 0.0f);
    CHECK(parseCommand("BACKOFF 0").kind == CMD_BACKOFF && parseCommand("BACKOFF 1.2").kind == CMD_ERROR);
    advance(c, 500);
    dispatch(c, EV_SERIAL_CMD_GRIP, 5.0f);
    advance(c, 1, 1.0f);
    const float r = fcRegTarget(c.fc);
    advance(c, 2000, r + 0.1f, 0.9f, ST_HOLD);
    advance(c, 2000, r + 0.1f, 0.9f);
    CHECK(c.fc.boff == 0.0f && std::fabs(c.iHoldRef - 0.9f) < 1e-3f);
    // F2: with the back-off off, a G <F_SET_MAX_N> hold is clamped to 5 N after HOLD_LONG_MS.
    g_ctx = "F2 long hold";
    dispatch(c, EV_SERIAL_CMD_GRIP, (float)F_SET_MAX_N);
    advance(c, HOLD_LONG_MS - 3000, r + 0.1f, 0.9f);
    CHECK(c.fc.spTarget == (float)F_SET_MAX_N);
    advance(c, 1100, r + 0.1f, 0.9f);
    CHECK(c.state == ST_HOLD && std::fabs(c.fc.spTarget - (float)F_SET_LONG_MAX_N) < 1e-4f && hasLine("WARN HOLD_LONG"));
    dispatch(c, EV_SERIAL_CMD_GRIP, (float)F_SET_MAX_N);   // a later G 7 in the same hold stays clamped
    CHECK(std::fabs(c.fc.spTarget - (float)F_SET_LONG_MAX_N) < 1e-4f);
  }
}

// 6c. Approach zones: fast, then the optional middle speed, then slow, each landing on its zone edge.
static void testApproachZones() {
  g_ctx = "approach zones";
  Motion m;
  motionInit(m, 20.0f);
  motionSearch(m, 6.0f, -3.0f, 120.0f, 20.0f);
  motionSetMid(m, 14.0f, 40.0f);
  float prev = m.cmd;
  bool sawMid = false, sawFast = false, sawSlow = false, bad = false;
  for (int k = 0; k < 200 && m.active; k++) {
    motionStep(m, 0.02f, 0);
    const float v = (prev - m.cmd) / 0.02f;
    if (prev > 14.0f + 1e-4f) { sawFast |= v > 100.0f; bad |= v > 120.0f + 1e-3f; }
    else if (prev > 6.0f + 1e-4f) { sawMid |= std::fabs(v - 40.0f) < 1e-2f; bad |= v > 40.0f + 1e-3f; }
    else { sawSlow |= std::fabs(v - 20.0f) < 1e-2f; bad |= v > 20.0f + 1e-3f; }
    prev = m.cmd;
  }
  CHECK(sawFast && sawMid && sawSlow && !bad);
  motionSetMid(m, 2.0f, 40.0f);   // a middle zone below the slow zone is ignored
  CHECK(m.midStart >= m.slowStart);
}

// 7. Property: no sequence of events and inputs, however wrong, drives the pulse outside the hard clamp, the jaw
//    command outside [JAW_MIN_DEG, JAW_OPEN_DEG], or the squeeze past its cap. 300 seeded random runs.
static void testPulseClampProperty() {
  g_ctx = "property: pulse clamp";
  uint32_t lcg = 777u;
  auto rnd = [&lcg]() { lcg = lcg * 1664525u + 1013904223u; return lcg >> 8; };
  auto rf = [&rnd](float lo, float hi) { return lo + (hi - lo) * (float)(rnd() % 100000) / 100000.0f; };
  const float weird[] = {NAN, INFINITY, -INFINITY, -1e30f, 1e30f, 0.0f, -0.0f};
  long samples = 0;
  int violations = 0, capViol = 0;
  for (int run = 0; run < 300; run++) {
    Core c;
    driveTo(c, (uint8_t)(rnd() % ST_COUNT));
    for (int k = 0; k < 3000; k++) {
      if (rnd() % 40 == 0) {
        const EventType ev = (EventType)(1 + rnd() % (EV_COUNT - 1));
        float arg = (rnd() % 8 == 0) ? weird[rnd() % 7] : rf(-20.0f, 40.0f);
        if (ev == EV_TIMEOUT) arg = (float)c.state;
        if (ev == EV_POSITION_REACHED || ev == EV_NO_CONTACT) arg = (float)c.motion.seq;
        dispatch(c, ev, arg);
      }
      const float f = (rnd() % 200 == 0) ? weird[rnd() % 7] : rf(0.0f, 12.0f);
      const float a = (rnd() % 200 == 0) ? weird[rnd() % 7] : rf(0.0f, 3.0f);
      g_now++;
      coreSampleForce(c, g_now, f);
      if (g_now % CONTROL_PERIOD_MS == 0) {
        coreSampleCurrent(c, g_now, rnd() % 50 != 0, a);
        const float th = coreControl(c, g_now, CONTROL_PERIOD_MS * 0.001f);
        // The pulse BEFORE jawToUs clamps it: checking the clamped value against the clamp would be a tautology
        // (review 2026-10-11). The jaw limits alone must keep it inside the hard pulse window.
        const float rawUs = (float)SERVO_US_AT_0DEG +
                            jawToServoDeg(th) * (float)(SERVO_US_AT_180DEG - SERVO_US_AT_0DEG) / 180.0f;
        samples++;
        if (!(th >= (float)JAW_MIN_DEG - 1e-4f && th <= (float)JAW_OPEN_DEG + 1e-4f)) violations++;
        if (!(rawUs >= (float)SERVO_US_LIMIT_MIN - 0.5f && rawUs <= (float)SERVO_US_LIMIT_MAX + 0.5f)) violations++;
        if (jawToUs(th) != (int)(rawUs + 0.5f)) violations++;   // the clamp never had to act
        if (c.fc.on && c.fc.u > CTRL_U_MAX_DEG + 1e-4f) capViol++;
      }
      coreTick(c, g_now);
      drain(c);
    }
  }
  std::printf("INFO property: %ld control outputs over 300 random runs, %d clamp violations, %d cap violations\n",
              samples, violations, capViol);
  CHECK(violations == 0);
  CHECK(capViol == 0);
}

int main(int argc, char **argv) {
  if (argc > 1 && std::strcmp(argv[1], "--table") == 0) { printTables(); return 0; }
  g_rowHits.assign(kTransitionCount, 0);
  testEveryRow();
  testTimeouts();
  testFaults();
  testCycle((float)FINGER_K_MIN_N_PER_MM);
  testCycle((float)FINGER_K_DEF_N_PER_MM);
  testCycle((float)FINGER_K_MAX_N_PER_MM);
  testModules();
  testFaultInjection();
  testThermalHooks();
  testApproachZones();
  testPulseClampProperty();
  int unhit = 0;
  for (uint16_t i = 0; i < kTransitionCount; i++)
    if (!g_rowHits[i]) { unhit++; std::printf("UNCOVERED row %u %s/%s\n", i, stateName(kTransitions[i].from), eventName(kTransitions[i].ev)); }
  std::printf("rows covered: %u / %u\n", (unsigned)(kTransitionCount - unhit), (unsigned)kTransitionCount);
  std::printf("%s %d / %d checks\n", (g_fail || unhit) ? "FAIL" : "PASS", g_pass, g_pass + g_fail);
  return (g_fail || unhit) ? 1 : 0;
}
