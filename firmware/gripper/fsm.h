// fsm.h -- the gripper state machine and its control core (hardware-free).
// States follow DESIGN-BASIS section 8: BOOT -> HOME -> CALIBRATE -> IDLE -> APPROACH -> TOUCHDOWN -> CLOSE
// -> HOLD -> FEED -> RELEASE -> RETRACT -> IDLE, plus FAULT. Every transition is one row of kTransitions
// (fsm.cpp); docs/gripper/analysis/controls.md section 2 prints the same table, and
// firmware/gripper/test/test_fsm.cpp drives every row.
//
// gripper.ino calls, without blocking:
//   coreSampleForce()   at 1 kHz with the filtered pad force -> FSR edge events
//   coreSampleCurrent() at 50 Hz with the servo-rail current -> over-current / table-touch events
//   coreControl()       at 50 Hz -> commanded jaw angle (motion profile or force loop)
//   coreTick()          every loop pass -> state timeouts and CALIBRATE phases
//   coreDispatch()      for each queued event
#pragma once
#include "platform.h"
#include "config.h"
#include "events.h"
#include "motion.h"
#include "force_ctrl.h"

enum State : uint8_t {
  ST_BOOT = 0, ST_HOME, ST_CALIBRATE, ST_IDLE, ST_APPROACH, ST_TOUCHDOWN, ST_CLOSE, ST_HOLD, ST_FEED,
  ST_RELEASE, ST_RETRACT, ST_FAULT, ST_COUNT,
  ST_ACTIVE = 0xFE,  // table wildcard: every state except BOOT and FAULT
  ST_SAME = 0xFF     // table target: internal transition, no exit/entry
};

enum CalPhase : uint8_t { CAL_SETTLE = 0, CAL_ZERO, CAL_SEARCH, CAL_END };
enum ClosePhase : uint8_t { CLOSE_SEARCH = 0, CLOSE_FORCE };
enum BackoffPhase : uint8_t { BO_WAIT = 0, BO_STEP, BO_DONE };   // thermal F1 in HOLD/FEED

// Hardware hooks the core needs. All may be null on the host except report.
struct CoreIo {
  void  (*report)(const char *line);   // one line to the host, no newline
  void  (*fsrZeroStart)();             // start averaging CAL_SAMPLES unloaded FSR samples
  bool  (*fsrZeroBusy)();
  float (*fsrZeroMv)();                // last zero offset (mV)
  bool  (*limitClosed)();              // debounced jaw-open limit switch
};

struct Core {
  CoreIo         io;
  uint32_t       now;          // last time handed in by tick / control / sample (ms)
  uint8_t        state;
  uint32_t       enteredAt;
  bool           timeoutPosted;
  Motion         motion;
  ForceCtrl      fc;
  ForceMonitor   fm;
  CurrentMonitor cm;
  float          thetaC0;      // calibrated contact angle (deg), THETA_C0_DEFAULT until CALIBRATE
  bool           calibrated;
  float          sp;           // grip setpoint (N) for the next or current grip
  uint8_t        fault;        // FaultCode of the last fault (FAULT_NONE once cleared)
  uint8_t        calPhase;
  uint32_t       calT0;
  uint8_t        closePhase;
  float          lastF;        // last filtered force handed in (N)
  float          lastI;        // last servo-rail current (A)
  bool           lastIValid;
  int16_t        lastRow;      // table row taken by the last dispatch, -1 if the event was ignored
  bool           relax;        // FAULT with the over-current still present: gripper.ino stops the servo pulse
  bool           limitRequired; // LIMIT_REQUIRED at init; a field so the host test can exercise both guards
  float          holdILimit;   // HOLD/FEED servo-rail current limit (A), 0 = off (thermal hook, R26; "ILIM <A>")
  uint32_t       iLimSince;    // first tick above holdILimit, 0 = below
  uint32_t       limStuckSince; // first tick with the open limit closed while the command is well closed, 0 = no
  bool           limStuckPosted;
  // Thermal F1 / F2 / F4 (thermal.md 5)
  float          backoffFactor; // F1 motor-current factor, 0 = off ("BACKOFF <f>")
  uint8_t        boPhase;      // BackoffPhase
  uint32_t       boSince;      // HOLD entry or last setpoint change (back-off timer)
  uint32_t       boT;          // last back-off step
  float          iSum;         // F4 averaging (rail current and measured force)
  float          fSum;
  float          boFRef;       // F1 keeps the measured force >= this - HOLD_BACKOFF_MARGIN_N
  float          boGood;       // F1 back-off to return to after a re-close
  bool           boReclose;    // F1 re-closing after a step that lost force
  uint16_t       iN;
  float          iHoldRef;     // F4: rail current in this hold with the back-off off (A), -1 = not measured
  uint32_t       holdSince;    // HOLD entry (F2 timer)
  bool           longHoldDone; // F2 clamp applied in this hold
  bool           iPresent;     // INA219 answered at boot: from then on an invalid reading is a fault
  uint32_t       iBadSince;    // first invalid current reading, 0 = valid
  bool           iBadPosted;
};

struct Transition {
  uint8_t   from;                                  // State or ST_ACTIVE
  EventType ev;
  bool    (*guard)(Core &c, const Event &e);       // null = always
  void    (*action)(Core &c, const Event &e);      // null = none; runs before exit/entry
  uint8_t   to;                                    // State or ST_SAME
  const char *note;                                // short reason, printed by the docs generator
};

extern const Transition kTransitions[];
extern const uint16_t   kTransitionCount;

const char *stateName(uint8_t s);
uint32_t    stateTimeoutMs(uint8_t s);

void  coreInit(Core &c, const CoreIo &io, uint32_t now_ms);
int   coreDispatch(Core &c, const Event &e);       // returns the row index taken, or -1 (ignored)
void  coreTick(Core &c, uint32_t now_ms);
void  coreSampleForce(Core &c, uint32_t now_ms, float f);
void  coreSampleCurrent(Core &c, uint32_t now_ms, bool valid, float amps);
float coreControl(Core &c, uint32_t now_ms, float dt_s);
float coreTheta(const Core &c);                    // current commanded jaw angle (deg)
bool  coreSetHoldCurrentLimit(Core &c, float amps); // thermal hook: 0 = off; false (unchanged) if not finite or < 0
bool  coreSetBackoffFactor(Core &c, float f);
void  coreSetCurrentPresent(Core &c, bool present);  // INA219 found at boot (default true); false = degraded, no fault      // thermal F1 factor: 0 = off, else (0, 1]; false (unchanged) otherwise
