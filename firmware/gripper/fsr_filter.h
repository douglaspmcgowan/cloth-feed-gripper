// fsr_filter.h -- FSR sample chain, hardware-free: raw node voltage -> EMA -> zero offset -> force -> span,
// plus the zeroing average and the shorted-sensor check. inputs.cpp runs it on the ESP32 ADC; the host test
// and analysis/gripper/firmware_sim/shim.cpp run the same code, so the simulation exercises the shipped filter.
#pragma once
#include "platform.h"
#include "config.h"

struct FsrFilter {
  float    emaMv;       // EMA of the node voltage (mV)
  float    zeroMv;      // unloaded offset from the last zeroing (mV)
  float    span;        // CALF scale factor
  bool     zeroBusy;
  uint16_t zeroN;
  float    zeroSum;
  bool     shortLatched;
  uint16_t shortMs;     // consecutive samples above FSR_SHORT_MV
  float    lastRaw;
  uint16_t sameMs;      // consecutive samples equal to the last one (stuck-ADC check)
  bool     stuckLatched;
};

enum : uint8_t { FSRF_SHORT = 1, FSRF_STUCK = 2 };   // fsrFilterSample() flags: post EV_FAULT_SENSOR(FAULT_FSR_*)

void    fsrFilterInit(FsrFilter &f, float firstMv);
uint8_t fsrFilterSample(FsrFilter &f, float rawMv);   // one 1 kHz sample; returns FSRF_* flags
float   fsrFilterForceUnscaled(const FsrFilter &f);   // zeroed force before the span factor (N)
float   fsrFilterForce(const FsrFilter &f);           // span-scaled force (N), >= 0, finite
void    fsrFilterZeroStart(FsrFilter &f);
bool    fsrFilterSetSpan(FsrFilter &f, float span);   // false if outside [FSR_SPAN_MIN, FSR_SPAN_MAX] or not finite
