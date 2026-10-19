// fsr_model.h -- FSR 402 divider conversion, hardware-free (inputs.cpp and the simulation use the same code).
// Divider: 3V3 -- FSR -- node -- R_FSR_FIXED_OHM -- GND, so V_node = Vref * Rf / (R_fsr + Rf).
// FSR resistance: power-law fit R = FSR_FIT_R1N_OHM * F^(-FSR_FIT_EXP) to the Adafruit 166 table [S][D].
#pragma once
#include <math.h>
#include "config.h"

// Pad force (N) -> divider node voltage (mV). F <= 0 gives 0 mV (open FSR).
static inline float fsrMvFromForce(float f_n) {
  if (f_n <= 0.0f) return 0.0f;
  const float r = (float)FSR_FIT_R1N_OHM * powf(f_n, -(float)FSR_FIT_EXP);
  return (float)ADC_VREF_MV * (float)R_FSR_FIXED_OHM / (r + (float)R_FSR_FIXED_OHM);
}

// Node voltage (mV, zero offset already removed) -> pad force (N). Below the noise floor -> 0.
static inline float fsrForceFromMv(float mv) {
  if (mv <= (float)FSR_MV_NOISE_FLOOR) return 0.0f;
  if (mv >= (float)ADC_VREF_MV - 1.0f) mv = (float)ADC_VREF_MV - 1.0f;
  const float r = (float)R_FSR_FIXED_OHM * ((float)ADC_VREF_MV / mv - 1.0f);
  return powf(r / (float)FSR_FIT_R1N_OHM, -1.0f / (float)FSR_FIT_EXP);
}
