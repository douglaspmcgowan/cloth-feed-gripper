// platform.h -- the only place that decides between the Arduino core and a host build.
// Hardware-free modules (events, fsm, motion, force_ctrl, protocol, fsr_model) include this file instead of
// <Arduino.h>, so firmware/gripper/test/ and analysis/gripper/firmware_sim/ compile them with g++ on a PC.
#pragma once
#ifdef ARDUINO
#include <Arduino.h>
#else
#include <stdint.h>
#include <stddef.h>
// The host build supplies the clock (test harness or simulation shim).
uint32_t millis();
#endif
