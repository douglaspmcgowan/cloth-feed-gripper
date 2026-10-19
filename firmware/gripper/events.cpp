// events.cpp -- single-producer-context ring buffer (all posts happen in loop() context, never in an ISR).
#include "events.h"

static Event    s_buf[EVENT_QUEUE_LEN];
static uint16_t s_head = 0;   // next write
static uint16_t s_tail = 0;   // next read
static uint16_t s_count = 0;
static uint32_t s_dropped = 0;

void eventsInit() {
  s_head = s_tail = s_count = 0;
  s_dropped = 0;
}

// Faults and timeouts may use the last EVENT_RESERVED_SLOTS slots; everything else (host commands, edges)
// is refused first, so a burst of serial lines cannot crowd out a safety event (review issue 5).
static bool isPriority(EventType t) {
  return t == EV_FSR_OVER || t == EV_FAULT_OVERCURRENT || t == EV_FAULT_STALL || t == EV_FAULT_SENSOR || t == EV_TIMEOUT;
}

bool eventPost(EventType type, float arg) {
  const uint16_t limit = isPriority(type) ? EVENT_QUEUE_LEN : EVENT_QUEUE_LEN - EVENT_RESERVED_SLOTS;
  if (s_count >= limit) {
    s_dropped++;
    return false;
  }
  s_buf[s_head].type = type;
  s_buf[s_head].arg  = arg;
  s_buf[s_head].t_ms = millis();
  s_head = (uint16_t)((s_head + 1) % EVENT_QUEUE_LEN);
  s_count++;
  return true;
}

bool eventPop(Event &out) {
  if (s_count == 0) return false;
  out = s_buf[s_tail];
  s_tail = (uint16_t)((s_tail + 1) % EVENT_QUEUE_LEN);
  s_count--;
  return true;
}

uint16_t eventsPending() { return s_count; }
uint32_t eventsDropped() { return s_dropped; }

static const char *const kEventNames[] = {
  "NONE", "BUTTON_PRESS", "BUTTON_LONG", "LIMIT_HIT",
  "FSR_CONTACT", "FSR_TARGET", "FSR_SLIP", "FSR_LOST", "FSR_OVER", "FORCE_SAT",
  "POSITION_REACHED", "NO_CONTACT", "TABLE_TOUCH", "TIMEOUT",
  "CMD_GRIP", "CMD_RELEASE", "CMD_HOME", "CMD_CAL", "CMD_APPROACH",
  "CMD_AT_POSE", "CMD_FEED", "CMD_FEED_DONE",
  "FAULT_STALL", "FAULT_OVERCURRENT", "FAULT_SENSOR"
};

static_assert(sizeof(kEventNames) / sizeof(kEventNames[0]) == EV_COUNT, "kEventNames out of step with EventType");

const char *eventName(EventType type) {
  return (type < EV_COUNT) ? kEventNames[type] : "?";
}

static const char *const kFaultNames[] = {
  "NONE", "OVERFORCE", "STALL", "OVERCURRENT", "FSR_SHORT", "ZERO_BAD", "CAL_RANGE", "TIMEOUT", "LIMIT", "FSR_OPEN", "FSR_STUCK", "I_SENSOR"
};

static_assert(sizeof(kFaultNames) / sizeof(kFaultNames[0]) == FAULT_COUNT, "kFaultNames out of step with FaultCode");

const char *faultName(uint8_t code) {
  return (code < FAULT_COUNT) ? kFaultNames[code] : "?";
}
