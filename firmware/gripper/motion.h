// motion.h -- jaw angle profile generator (hardware-free).
// The DS3230 MG is a position servo with no feedback wire, so the firmware owns a commanded angle and
// moves it at a set speed; the servo follows with its own lag. A "search" move runs fast down to a slow-zone
// angle, then at the near-contact speed (R19), and reports NO_CONTACT if it reaches its end.
// Events are reported JAW_SETTLE_MS after the profile ends, so the servo has caught up; arg = move id (seq).
#pragma once
#include "platform.h"
#include "events.h"

struct Motion {
  float    cmd;          // commanded jaw angle theta (deg), always inside [JAW_MIN_DEG, JAW_OPEN_DEG]
  float    target;       // end of the current move
  float    slowStart;    // closing below this angle runs at vSlow (search moves only)
  float    midStart;     // closing below this angle (and above slowStart) runs at vMid; = slowStart when unused
  float    vMid;         // deg/s
  float    vFast;        // deg/s
  float    vSlow;        // deg/s
  bool     active;       // profile still moving
  bool     search;       // the move is a contact search
  bool     pending;      // profile ended; event due at doneAt
  uint32_t doneAt;
  float    vNow;         // speed of the last profile step (deg/s), 0 when idle: sets the contact lag reference
  uint16_t seq;          // move id, carried as the event arg so the FSM drops events from superseded moves
};

float     jawClamp(float theta);
void      motionInit(Motion &m, float theta);
void      motionMove(Motion &m, float target, float speedDps);
void      motionSearch(Motion &m, float slowStart, float end, float vFast, float vSlow);
void      motionSetMid(Motion &m, float midStart, float vMid);   // search moves: a middle-speed zone above slowStart
void      motionStop(Motion &m);                    // freeze at the current command, cancel any pending event
void      motionHold(Motion &m, float theta);       // force mode writes the command directly
EventType motionStep(Motion &m, float dt_s, uint32_t now_ms);  // EV_NONE, EV_POSITION_REACHED or EV_NO_CONTACT
