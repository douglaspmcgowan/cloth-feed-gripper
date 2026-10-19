// servo_map.h -- jaw angle theta (deg) -> servo pulse (us), hardware-free.
// servo_deg = SERVO_DEG_AT_JAW0 + SERVO_DIR * theta (1:1: the horn is on knuckle A's shaft, finger.md 6.4);
// pulse = 500 us + servo_deg * 2000 us / 180 deg [DB R7], clamped to [SERVO_US_LIMIT_MIN, SERVO_US_LIMIT_MAX].
#pragma once
#include "config.h"

static inline float jawToServoDeg(float theta) {
  return (float)SERVO_DEG_AT_JAW0 + (float)SERVO_DIR * theta;
}

static inline int jawToUs(float theta) {
  const float us = (float)SERVO_US_AT_0DEG +
                   jawToServoDeg(theta) * (float)(SERVO_US_AT_180DEG - SERVO_US_AT_0DEG) / 180.0f;
  int r = (int)(us + 0.5f);
  if (r < SERVO_US_LIMIT_MIN) r = SERVO_US_LIMIT_MIN;
  if (r > SERVO_US_LIMIT_MAX) r = SERVO_US_LIMIT_MAX;
  return r;
}
