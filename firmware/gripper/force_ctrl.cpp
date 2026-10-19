// force_ctrl.cpp -- see force_ctrl.h.
#include "force_ctrl.h"
#include <math.h>

static float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

// ---------------------------------------------------------------------------------------------------------
// Force loop
void fcReset(ForceCtrl &c) {
  c.on = false;
  c.thetaRef = 0.0f;
  c.u = c.integ = 0.0f;
  c.spTarget = (float)F_TARGET_DEFAULT_N;
  c.spRamp = (float)F_TOUCH_N;
  c.satMs = 0;
  c.satPosted = false;
  c.kEst = K_STIFF_N_PER_DEG;
  for (uint8_t i = 0; i <= KEST_LAG_TICKS; i++) c.uHist[i] = 0.0f;
  c.uHead = 0;
  c.boff = 0.0f;
  c.floor = (float)JAW_MIN_DEG;
}

float fcJawFloor(float thetaC0) {
  if ((float)JAW_FLOOR_BELOW_C0_DEG <= 0.0f || !isfinite(thetaC0)) return (float)JAW_MIN_DEG;
  const float f = thetaC0 - (float)JAW_FLOOR_BELOW_C0_DEG;
  return f > (float)JAW_MIN_DEG ? f : (float)JAW_MIN_DEG;
}

void fcSetFloor(ForceCtrl &c, float floorDeg) {
  c.floor = (isfinite(floorDeg) && floorDeg > (float)JAW_MIN_DEG) ? floorDeg : (float)JAW_MIN_DEG;
}

float fcSetpoint(ForceCtrl &c, float sp) {
  if (!isfinite(sp)) return c.spTarget;   // a NaN or inf setpoint is ignored (the parser rejects them too)
  c.spTarget = clampf(sp, (float)F_SET_MIN_N, (float)F_SET_MAX_N);
  return c.spTarget;
}

float fcGain(const ForceCtrl &c) { return GAIN_SCHED_ENABLED ? K_STIFF_N_PER_DEG / c.kEst : 1.0f; }

// Regulated (measured) force for a setpoint: the hold bias, never above the setpoint clamp.
static float spReg(float sp) {
  const float r = sp + (float)F_HOLD_BIAS_N;
  return r > (float)F_SET_MAX_N ? (sp > (float)F_SET_MAX_N ? sp : (float)F_SET_MAX_N) : r;
}

float fcRegTarget(const ForceCtrl &c) { return spReg(c.spTarget); }

static float uFeedForward(const ForceCtrl &c, float sp) {
  const float k = GAIN_SCHED_ENABLED ? c.kEst : K_STIFF_N_PER_DEG;
  return (sp - (float)F_TOUCH_N) / k;
}

static float uCap(const ForceCtrl &c) {
  // Squeeze cap: the R15 force cap at the stiffest finger, and the jaw floor of this grip (fcSetFloor).
  const float floorCap = c.thetaRef - c.floor;
  return CTRL_U_MAX_DEG < floorCap ? CTRL_U_MAX_DEG : floorCap;
}

void fcStart(ForceCtrl &c, float thetaCmdNow, float speedDps) {
  // The FSR crossed F_TOUCH while the servo trailed the command by about speed x lag, so the jaw angle at
  // which F = F_TOUCH sits speed x CTRL_LAG_COMP_S on the open side of the command. The command starts where it is
  // (u = that offset, at most the target's feedforward) and the rate limit walks it to the ramp. The integrator starts at zero: a
  // bumpless back-solve would keep the lag offset as a permanent extra squeeze (+2.8 N on the stiffest
  // finger in the simulation, controls.md 4).
  // If the command is further ahead than the squeeze the target needs on the stiffest finger (a contact in
  // the fast leg), pull it straight back to that squeeze instead of letting the servo run on (review issue 3).
  c.thetaRef = thetaCmdNow + speedDps * (float)CTRL_LAG_COMP_S;
  const float uLag = c.thetaRef - thetaCmdNow;
  c.kEst = K_STIFF_N_PER_DEG;
  for (uint8_t i = 0; i <= KEST_LAG_TICKS; i++) c.uHist[i] = 0.0f;
  c.uHead = 0;
  const float uNeed = uFeedForward(c, spReg(c.spTarget));
  c.u = uLag < uNeed ? uLag : uNeed;
  c.spRamp = (float)F_TOUCH_N;
  c.integ = 0.0f;
  c.satMs = 0;
  c.satPosted = false;
  c.boff = 0.0f;
  c.on = true;
}

float fcThetaCmd(const ForceCtrl &c) { return c.thetaRef - c.u + c.boff; }

float fcStep(ForceCtrl &c, float f, float dt_s, bool *sat) {
  if (sat) *sat = false;
  if (!c.on) return fcThetaCmd(c);
  if (!isfinite(f)) f = (float)F_TRIP_N;   // a bad reading backs off through the soft limit, never squeezes

  // Stiffness estimate from the force against the squeeze commanded one servo lag ago (gain schedule).
  const float uLagged = c.uHist[(uint8_t)((c.uHead + 1) % (KEST_LAG_TICKS + 1))];
  if (f > (float)KEST_F_MIN_N && uLagged > 0.3f) {
    const float kRaw = clampf((f - (float)F_TOUCH_N) / uLagged, K_SCHED_MIN_N_PER_DEG, K_STIFF_N_PER_DEG);
    c.kEst += (float)KEST_ALPHA * (kRaw - c.kEst);
  }
  const float g = fcGain(c);
  const float kp = CTRL_KP_DEG_PER_N * g;

  // Setpoint ramp (both directions, so a lower "G <N>" during HOLD also eases off smoothly).
  const float dsp = (float)F_RAMP_NPS * dt_s;
  if (c.spRamp < c.spTarget) c.spRamp = fminf(c.spTarget, c.spRamp + dsp);
  else if (c.spRamp > c.spTarget) c.spRamp = fmaxf(c.spTarget, c.spRamp - dsp);

  // While the setpoint ramps, the feedforward alone moves the jaw: the force trails the ramp by the servo
  // lag, and feeding that error to P or I made the stiff finger overshoot (controls.md 4). The PI acts on the
  // error once the ramp has ended (setpoint weight 0 during the ramp).
  const bool ramping = (c.spRamp != c.spTarget);
  const float spR = spReg(c.spRamp);
  const float e = spR - f;
  const float eP = ramping ? 0.0f : e;
  const float cap = uCap(c);
  const float uMin = (float)CTRL_U_MIN_DEG;
  float uRaw = uFeedForward(c, spR) + kp * eP + c.integ;

  // Asymmetric integrator deadband plus conditional integration (no wind-up into either limit).
  const bool wantI = !ramping && ((e > 0.0f) || (e < -(float)CTRL_I_DB_HI_N));
  const bool pushHigh = (uRaw >= cap) && (e > 0.0f);
  const bool pushLow = (uRaw <= uMin) && (e < 0.0f);
  if (wantI && !pushHigh && !pushLow) {
    c.integ += kp / CTRL_TI_S * e * dt_s;
    c.integ = clampf(c.integ, uMin - cap, cap);
    uRaw = uFeedForward(c, spR) + kp * eP + c.integ;
  }

  // Soft limit: step back and bleed the integrator while above F_SOFT_LIMIT_N.
  if (f > (float)F_SOFT_LIMIT_N) {
    c.integ -= (float)CTRL_SOFT_BACKOFF_DEG;
    c.integ = clampf(c.integ, uMin - cap, cap);
    const float backed = c.u - (float)CTRL_SOFT_BACKOFF_DEG;
    if (uRaw > backed) uRaw = backed;
  }

  uRaw = clampf(uRaw, uMin, cap);
  const float du = (float)CTRL_RATE_LIMIT_DPS * dt_s;
  c.u = clampf(uRaw, c.u - du - (f > (float)F_SOFT_LIMIT_N ? (float)CTRL_SOFT_BACKOFF_DEG : 0.0f), c.u + du);

  c.uHead = (uint8_t)((c.uHead + 1) % (KEST_LAG_TICKS + 1));
  c.uHist[c.uHead] = c.u;

  // Saturation: at the squeeze cap with the force short of the regulated target. The test is f < r, not the
  // FSR_TARGET band edge r - F_BAND: with both on the same edge, a force sitting at r - 0.5 N with noise reset both
  // timers forever and CLOSE timed out to FAULT (Monte Carlo after-bench run 1801, controls.md 6.2).
  if (c.u >= cap - (float)CTRL_SAT_TOL_DEG && f < spReg(c.spTarget)) {
    c.satMs += (uint32_t)(dt_s * 1000.0f + 0.5f);
    if (c.satMs >= (uint32_t)STALL_TIME_MS && !c.satPosted) {
      c.satPosted = true;
      if (sat) *sat = true;
    }
  } else {
    c.satMs = 0;
  }
  return fcThetaCmd(c);
}

// ---------------------------------------------------------------------------------------------------------
// Force monitor
void fmInit(ForceMonitor &m) {
  m.contactArmed = true;
  m.overArmed = true;
  m.touched = m.held = m.targetPosted = m.slipArmed = m.lostPosted = false;
  m.inBand = m.inSlip = m.inLost = m.inOver = false;
  m.bandSince = m.slipSince = m.lostSince = m.overSince = 0;
}

void fmNewGrip(ForceMonitor &m) {
  m.contactArmed = true;
  m.touched = m.held = m.targetPosted = m.slipArmed = m.lostPosted = false;
  m.inBand = m.inSlip = m.inLost = false;
}

// HOLD entered, by FSR_TARGET or by FORCE_SAT: slip detection is armed in every hold (review 2026-10-11: it was
// armed only by FSR_TARGET, so a hold entered at the squeeze cap never reported FSR_SLIP).
void fmArmHold(ForceMonitor &m) {
  m.held = true;
  m.slipArmed = true;
  m.inSlip = false;
}

uint8_t fmUpdate(ForceMonitor &m, uint32_t now, float f, bool forceMode, float sp) {
  uint8_t out = 0;
  const float hyst = (float)F_HYST_N;

  if (m.contactArmed && f >= (float)F_TOUCH_N) {
    out |= FM_CONTACT;
    m.contactArmed = false;
    m.touched = true;
  } else if (!m.contactArmed && f < (float)F_TOUCH_N - hyst) {
    m.contactArmed = true;
  }

  if (f > (float)F_TRIP_N) {
    if (!m.inOver) { m.inOver = true; m.overSince = now; }
    if (m.overArmed && now - m.overSince >= (uint32_t)F_TRIP_MS) { out |= FM_OVER; m.overArmed = false; }
  } else {
    m.inOver = false;
    if (f < (float)F_TRIP_N - hyst) m.overArmed = true;
  }

  // Target band is asymmetric to match the integrator deadband: the loop settles anywhere in
  // [sp, sp + CTRL_I_DB_HI_N], so that whole interval, widened by F_BAND_N each side, counts as on target.
  if (forceMode && !m.targetPosted && f > sp - (float)F_BAND_N && f < sp + (float)CTRL_I_DB_HI_N + (float)F_BAND_N) {
    if (!m.inBand) { m.inBand = true; m.bandSince = now; }
    if (now - m.bandSince >= (uint32_t)F_SETTLE_MS) {
      out |= FM_TARGET;
      m.targetPosted = m.held = m.slipArmed = true;
    }
  } else {
    m.inBand = false;
  }

  if (m.held) {
    if (f < (float)F_SLIP_N) {
      if (!m.inSlip) { m.inSlip = true; m.slipSince = now; }
      if (m.slipArmed && now - m.slipSince >= (uint32_t)F_SLIP_MS) { out |= FM_SLIP; m.slipArmed = false; }
    } else {
      m.inSlip = false;
      if (f > (float)F_SLIP_N + hyst) m.slipArmed = true;
    }
  }

  if (m.touched && forceMode && !m.lostPosted) {
    if (f < (float)F_TOUCH_N - hyst) {
      if (!m.inLost) { m.inLost = true; m.lostSince = now; }
      if (now - m.lostSince >= (uint32_t)F_LOST_MS) { out |= FM_LOST; m.lostPosted = true; }
    } else {
      m.inLost = false;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------------------------------------
// Current monitor
void cmInit(CurrentMonitor &m) {
  m.overSince = 0;
  m.inOver = m.overPosted = false;
  cmDisarmTouch(m);
}

void cmArmTouch(CurrentMonitor &m, uint32_t now) {
  m.touchArmed = true;
  m.touchPosted = m.inTouch = false;
  m.armedAt = now;
  m.touchSince = now;
  m.baseSum = 0.0f;
  m.baseN = 0;
  m.base = 0.0f;
  m.baseSet = false;
}

void cmDisarmTouch(CurrentMonitor &m) {
  m.touchArmed = m.touchPosted = m.inTouch = false;
  m.armedAt = m.touchSince = 0;
  m.baseSum = m.base = 0.0f;
  m.baseN = 0;
  m.baseSet = false;
}

uint8_t cmUpdate(CurrentMonitor &m, uint32_t now, bool valid, float amps, float tripA) {
  uint8_t out = 0;
  if (!valid || !isfinite(amps)) { m.inOver = false; m.inTouch = false; return 0; }

  if (amps > tripA) {
    if (!m.inOver) { m.inOver = true; m.overSince = now; }
    if (!m.overPosted && now - m.overSince >= (uint32_t)STALL_CURRENT_MS) { out |= CM_OVERCURRENT; m.overPosted = true; }
  } else {
    m.inOver = false;
    m.overPosted = false;
  }

  if (m.touchArmed && !m.touchPosted) {
    if (now - m.armedAt < (uint32_t)TOUCH_BASE_MS) {
      m.baseSum += amps;
      m.baseN++;
    } else {
      if (!m.baseSet) { m.base = m.baseN ? m.baseSum / (float)m.baseN : amps; m.baseSet = true; }
      if (amps > m.base + (float)TOUCH_DI_A) {
        if (!m.inTouch) { m.inTouch = true; m.touchSince = now; }
        if (now - m.touchSince >= (uint32_t)TOUCH_MS) { out |= CM_TABLE_TOUCH; m.touchPosted = true; }
      } else {
        m.inTouch = false;
      }
    }
  }
  return out;
}
