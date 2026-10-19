// shim.cpp -- C ABI over the real firmware core so the Python simulations run the shipped control code.
// Compiled by build.py: g++ -shared -I firmware/gripper shim.cpp + the hardware-free firmware sources.
// The scheduler below is the same as loop() in firmware/gripper/gripper.ino: 1 kHz FSR sample through the
// shipped FsrFilter (fsr_filter.cpp), 50 Hz current + control, state tick, then the event queue drained through
// the transition table. Only the hardware reads (ADC, INA219, pins) are replaced by the values handed in.
#include <cstring>
#include <cstdio>
#include "fsm.h"
#include "servo_map.h"
#include "fsr_model.h"
#include "fsr_filter.h"

static uint32_t g_now = 0;
uint32_t millis() { return g_now; }

static Core      g_core;
static FsrFilter g_fsr;
static bool      g_limit = true;
static bool      g_relaxed = false;     // servo pulse detached (gripper.ino: FAULT with persisting over-current)

struct EvRec { uint32_t t; int type; float arg; int state_after; };
static EvRec g_ev[4096];
static int   g_evN = 0;
static char  g_lines[64][96];
static int   g_lineN = 0;

static void rep(const char *s) {
  if (g_lineN < 64) { strncpy(g_lines[g_lineN], s, 95); g_lines[g_lineN][95] = 0; g_lineN++; }
}
static void zStart() { fsrFilterZeroStart(g_fsr); }
static bool zBusy() { return g_fsr.zeroBusy; }
static float zMv() { return g_fsr.zeroMv; }
static bool lim() { return g_limit; }

static void drain() {
  Event e;
  for (int n = 0; n < EVENTS_PER_LOOP && eventPop(e); n++) {
    coreDispatch(g_core, e);
    if (g_evN < 4096) g_ev[g_evN++] = {g_now, (int)e.type, e.arg, (int)g_core.state};
  }
}

static void boot(float firstMv) {
  eventsInit();
  fsrFilterInit(g_fsr, firstMv);
  g_relaxed = false;
  CoreIo io;
  io.report = rep;
  io.fsrZeroStart = zStart;
  io.fsrZeroBusy = zBusy;
  io.fsrZeroMv = zMv;
  io.limitClosed = lim;
  coreInit(g_core, io, g_now);
}

extern "C" {

void sim_init() {
  g_now = 1000;
  g_evN = 0;
  g_lineN = 0;
  g_limit = true;
  boot(0.0f);
}

// Brown-out or watchdog reset: RAM is lost, setup() runs again (the clock keeps going for the plant).
void sim_reset_mcu(float firstMv) { boot(firstMv); }

void sim_set_limit(int closed) { g_limit = closed != 0; }

// One millisecond. rawMv is this sample's ADC reading of the FSR node (mV), amps the INA219 servo-rail current
// (negative = INA219 absent / read failed). forceN_unused is kept for older callers. Returns the pulse (us), or 0
// while the servo is detached.
int sim_step(float rawMv, float forceN_unused, float amps) {
  (void)forceN_unused;
  g_now++;
  const uint8_t fl = fsrFilterSample(g_fsr, rawMv);
  if (fl & FSRF_SHORT) eventPost(EV_FAULT_SENSOR, (float)FAULT_FSR_SHORT);
  if (fl & FSRF_STUCK) eventPost(EV_FAULT_SENSOR, (float)FAULT_FSR_STUCK);
  coreSampleForce(g_core, g_now, fsrFilterForce(g_fsr));
  if (g_now % CONTROL_PERIOD_MS == 0) {
    coreSampleCurrent(g_core, g_now, amps >= 0.0f, amps >= 0.0f ? amps : 0.0f);
    coreControl(g_core, g_now, CONTROL_PERIOD_MS * 0.001f);
    g_relaxed = g_core.relax;
  }
  coreTick(g_core, g_now);
  drain();
  return g_relaxed ? 0 : jawToUs(coreTheta(g_core));
}

void sim_post(int type, float arg) {
  eventPost((EventType)type, arg);
  drain();
}

uint32_t sim_now() { return g_now; }
int   sim_state() { return g_core.state; }
float sim_theta_cmd() { return coreTheta(g_core); }
float sim_theta_c0() { return g_core.thetaC0; }
float sim_zero_mv() { return g_fsr.zeroMv; }
float sim_force_fw() { return fsrFilterForce(g_fsr); }
int   sim_force_on() { return g_core.fc.on ? 1 : 0; }
float sim_theta_ref() { return g_core.fc.thetaRef; }
float sim_sp_ramp() { return g_core.fc.spRamp; }
float sim_u() { return g_core.fc.u; }
float sim_k_est() { return g_core.fc.kEst; }
int   sim_set_hold_limit(float a) { return coreSetHoldCurrentLimit(g_core, a) ? 1 : 0; }
void  sim_set_current_present(int p) { coreSetCurrentPresent(g_core, p != 0); }
int   sim_set_backoff(float f) { return coreSetBackoffFactor(g_core, f) ? 1 : 0; }
float sim_hold_i_ref() { return g_core.iHoldRef; }
float sim_boff() { return g_core.fc.boff; }
float sim_sp() { return g_core.fc.spTarget; }
int   sim_fault() { return g_core.fault; }
int   sim_relaxed() { return g_relaxed ? 1 : 0; }
int   sim_calibrated() { return g_core.calibrated ? 1 : 0; }
int   sim_set_span(float s) { return fsrFilterSetSpan(g_fsr, s) ? 1 : 0; }

int sim_events(uint32_t *t, int *type, float *arg, int *st, int max) {
  int n = g_evN < max ? g_evN : max;
  for (int i = 0; i < n; i++) { t[i] = g_ev[i].t; type[i] = g_ev[i].type; arg[i] = g_ev[i].arg; st[i] = g_ev[i].state_after; }
  return n;
}
void sim_clear_events() { g_evN = 0; g_lineN = 0; }
int  sim_line_count() { return g_lineN; }
const char *sim_line(int i) { return (i >= 0 && i < g_lineN) ? g_lines[i] : ""; }

const char *sim_event_name(int t) { return eventName((EventType)t); }
const char *sim_state_name(int s) { return stateName((uint8_t)s); }
float sim_fsr_mv_from_force(float f) { return fsrMvFromForce(f); }
float sim_fsr_force_from_mv(float mv) { return fsrForceFromMv(mv); }
int   sim_jaw_to_us(float th) { return jawToUs(th); }

float sim_k_stiff() { return K_STIFF_N_PER_DEG; }
float sim_kp() { return CTRL_KP_DEG_PER_N; }
float sim_ti() { return CTRL_TI_S; }
float sim_u_max() { return CTRL_U_MAX_DEG; }
float sim_lag_comp() { return CTRL_LAG_COMP_DEG; }
int   sim_transition_count() { return kTransitionCount; }

}  // extern "C"
