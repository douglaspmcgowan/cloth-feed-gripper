// fsr_filter.cpp -- see fsr_filter.h.
#include "fsr_filter.h"
#include <math.h>
#include "fsr_model.h"

void fsrFilterInit(FsrFilter &f, float firstMv) {
  f.emaMv = isfinite(firstMv) ? firstMv : 0.0f;
  f.zeroMv = 0.0f;
  f.span = (float)FSR_SPAN_DEFAULT;
  f.zeroBusy = false;
  f.zeroN = 0;
  f.zeroSum = 0.0f;
  f.shortLatched = false;
  f.shortMs = 0;
  f.lastRaw = f.emaMv;
  f.sameMs = 0;
  f.stuckLatched = false;
}

uint8_t fsrFilterSample(FsrFilter &f, float raw) {
  uint8_t out = 0;
  if (!isfinite(raw)) raw = (float)ADC_VREF_MV;   // treat a bad conversion as the worst case (reads high)
  f.emaMv += (float)FSR_EMA_ALPHA * (raw - f.emaMv);
  if (f.zeroBusy) {
    f.zeroSum += raw;
    if (++f.zeroN >= (uint16_t)CAL_SAMPLES) {
      f.zeroMv = f.zeroSum / (float)f.zeroN;
      f.zeroBusy = false;
    }
  }
  // Shorted FSR: the node sits near the rail. The threshold is the node voltage for about 30 N, three times
  // the cap, so a real grip cannot reach it, and it is below where the 11 dB ADC saturates (controls.md 6).
  if (raw > (float)FSR_SHORT_MV) {
    if (f.shortMs < 0xFFFF) f.shortMs++;
  } else {
    f.shortMs = 0;
  }
  if (!f.shortLatched && f.shortMs >= (uint16_t)FSR_SHORT_MS) {
    f.shortLatched = true;
    out |= FSRF_SHORT;
  } else if (f.shortLatched && f.emaMv < (float)FSR_SHORT_MV - 200.0f) {
    f.shortLatched = false;
  }
  // Stuck ADC: a live channel always shows noise; an unchanged reading above the touch level for FSR_STUCK_MS
  // means the conversion is frozen and the force loop is flying blind (review 2026-10-11, controls.md 7).
  if (raw > (float)FSR_STUCK_MV_MIN && fabsf(raw - f.lastRaw) <= (float)FSR_STUCK_TOL_MV) {
    if (f.sameMs < 0xFFFF) f.sameMs++;
  } else {
    f.sameMs = 0;
    f.stuckLatched = false;
  }
  f.lastRaw = raw;
  if (!f.stuckLatched && f.sameMs >= (uint16_t)FSR_STUCK_MS) {
    f.stuckLatched = true;
    out |= FSRF_STUCK;
  }
  return out;
}

float fsrFilterForceUnscaled(const FsrFilter &f) { return fsrForceFromMv(f.emaMv - f.zeroMv); }

float fsrFilterForce(const FsrFilter &f) {
  const float v = f.span * fsrFilterForceUnscaled(f);
  return isfinite(v) && v > 0.0f ? v : 0.0f;
}

void fsrFilterZeroStart(FsrFilter &f) {
  f.zeroSum = 0.0f;
  f.zeroN = 0;
  f.zeroBusy = true;
}

bool fsrFilterSetSpan(FsrFilter &f, float span) {
  if (!isfinite(span) || span < (float)FSR_SPAN_MIN || span > (float)FSR_SPAN_MAX) return false;
  f.span = span;
  return true;
}
