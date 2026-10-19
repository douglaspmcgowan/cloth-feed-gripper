// events.h -- event types and a fixed-size ring-buffer queue.
// Producers (inputs, motion, force monitors, comms, fsm timeouts) call eventPost(); loop() drains the
// queue through fsmDispatch(). ISRs never post: they only set volatile flags read by the poll tasks.
// Hardware-free: compiles on the host (platform.h).
#pragma once
#include "platform.h"
#include "config.h"

enum EventType : uint8_t {
  EV_NONE = 0,
  EV_BUTTON_PRESS,        // debounced short press (released before BUTTON_LONG_MS)
  EV_BUTTON_LONG,         // held >= BUTTON_LONG_MS
  EV_LIMIT_HIT,           // jaw-open limit switch closed (debounced edge)
  EV_FSR_CONTACT,         // force rose through F_TOUCH_N (arg = force N)
  EV_FSR_TARGET,          // |F - F_sp| < F_BAND_N for F_SETTLE_MS (arg = force N)
  EV_FSR_SLIP,            // F < F_SLIP_N for F_SLIP_MS while holding (arg = force N)
  EV_FSR_LOST,            // F < F_TOUCH_N - F_HYST_N for F_LOST_MS after contact
  EV_FSR_OVER,            // F > F_TRIP_N for F_TRIP_MS (arg = force N)
  EV_FORCE_SAT,           // force loop at the theta_min position cap, force below target
  EV_POSITION_REACHED,    // actuator motion profile finished and settled (arg = theta deg)
  EV_NO_CONTACT,          // contact search ran past its end without touch
  EV_TABLE_TOUCH,         // TOUCHDOWN: servo current rose TOUCH_DI_A over baseline for TOUCH_MS (nail on table)
  EV_TIMEOUT,             // state timeout (arg = state id); BOOT uses it as its normal exit
  EV_SERIAL_CMD_GRIP,     // "G <newtons>"   (arg = setpoint N)
  EV_SERIAL_CMD_RELEASE,  // "R"
  EV_SERIAL_CMD_HOME,     // "H"
  EV_SERIAL_CMD_CAL,      // "C"
  EV_SERIAL_CMD_APPROACH, // "A"             arm moves over the cloth, jaw open -> APPROACH
  EV_SERIAL_CMD_AT_POSE,  // "ARM_AT_POSE"   arm is over the edge -> TOUCHDOWN (jaw to pre-grasp, arm lowers)
  EV_SERIAL_CMD_FEED,     // "FEED"          arm starts feeding
  EV_SERIAL_CMD_FEED_DONE,// "FEED_DONE"     arm finished -> release
  EV_FAULT_STALL,         // command/feedback disagreement too long (FB_ENABLED builds only)
  EV_FAULT_OVERCURRENT,   // INA219 servo-rail current > STALL_CURRENT_A for STALL_CURRENT_MS
  EV_FAULT_SENSOR,        // FSR shorted/open, bad zero, calibration out of window (arg = FaultCode)
  EV_COUNT
};

// Fault codes carried by FAULT events and reported by STATUS.
enum FaultCode : uint8_t {
  FAULT_NONE = 0,
  FAULT_OVERFORCE,
  FAULT_STALL,
  FAULT_OVERCURRENT,
  FAULT_FSR_SHORT,
  FAULT_ZERO_BAD,
  FAULT_CAL_RANGE,
  FAULT_TIMEOUT,
  FAULT_LIMIT,
  FAULT_FSR_OPEN,         // CLOSE search ended with no FSR contact while the servo was squeezing (current)
  FAULT_FSR_STUCK,        // raw FSR reading frozen (no noise) for FSR_STUCK_MS while above FSR_STUCK_MV_MIN
  FAULT_I_SENSOR,         // INA219 present at boot but no valid reading for I_SENSOR_FAIL_MS: over-current blind
  FAULT_COUNT
};

struct Event {
  EventType type;
  float     arg;
  uint32_t  t_ms;
};

void        eventsInit();
bool        eventPost(EventType type, float arg = 0.0f);   // false (and a drop counted) if full
bool        eventPop(Event &out);
uint16_t    eventsPending();
uint32_t    eventsDropped();
const char *eventName(EventType type);
const char *faultName(uint8_t code);
