// motion.cpp -- see motion.h.
#include "motion.h"
#include <math.h>

float jawClamp(float theta) {
  if (theta < (float)JAW_MIN_DEG) return (float)JAW_MIN_DEG;
  if (theta > (float)JAW_OPEN_DEG) return (float)JAW_OPEN_DEG;
  return theta;
}

void motionInit(Motion &m, float theta) {
  m.cmd = m.target = m.slowStart = m.midStart = jawClamp(theta);
  m.vFast = m.vSlow = m.vMid = (float)JAW_SPEED_FAST_DPS;
  m.active = m.search = m.pending = false;
  m.doneAt = 0;
  m.vNow = 0.0f;
  m.seq = 0;
}

void motionMove(Motion &m, float target, float speedDps) {
  m.target = jawClamp(target);
  m.slowStart = m.midStart = m.target;
  m.vFast = m.vSlow = m.vMid = speedDps;
  m.search = false;
  m.pending = false;
  m.active = true;
  m.seq++;
}

void motionSearch(Motion &m, float slowStart, float end, float vFast, float vSlow) {
  m.target = jawClamp(end);
  m.slowStart = m.midStart = jawClamp(slowStart);
  m.vFast = m.vMid = vFast;
  m.vSlow = vSlow;
  m.search = true;
  m.pending = false;
  m.active = true;
  m.seq++;
}

void motionSetMid(Motion &m, float midStart, float vMid) {
  m.midStart = jawClamp(midStart);
  if (m.midStart < m.slowStart) m.midStart = m.slowStart;
  m.vMid = vMid;
}

void motionStop(Motion &m) {
  m.target = m.cmd;
  m.active = m.pending = m.search = false;
  m.seq++;
}

void motionHold(Motion &m, float theta) {
  m.cmd = m.target = jawClamp(theta);
  m.active = m.pending = m.search = false;
}

EventType motionStep(Motion &m, float dt_s, uint32_t now_ms) {
  if (m.active) {
    const float err = m.target - m.cmd;
    // Closing (err < 0) below the slow-zone angle runs at the near-contact speed.
    const float v = (err < 0.0f && m.cmd <= m.slowStart) ? m.vSlow : ((err < 0.0f && m.cmd <= m.midStart) ? m.vMid : m.vFast);
    float step = v * dt_s;
    if (err < 0.0f && m.cmd > m.slowStart && m.cmd - step < m.slowStart) step = m.cmd - m.slowStart;  // land on the zone edge
    if (err < 0.0f && m.cmd > m.midStart && m.cmd - step < m.midStart) step = m.cmd - m.midStart;
    m.vNow = v;
    if (fabsf(err) <= step) {
      m.cmd = m.target;
      m.active = false;
      m.pending = true;
      m.doneAt = now_ms + (uint32_t)JAW_SETTLE_MS;
    } else {
      m.cmd += (err > 0.0f) ? step : -step;
    }
  }
  if (!m.active) m.vNow = 0.0f;
  if (m.pending && (int32_t)(now_ms - m.doneAt) >= 0) {
    m.pending = false;
    const bool wasSearch = m.search;
    m.search = false;
    return wasSearch ? EV_NO_CONTACT : EV_POSITION_REACHED;
  }
  return EV_NONE;
}
