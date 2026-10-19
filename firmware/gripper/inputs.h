// inputs.h -- button, limit switch, FSR (ADC1), optional servo pot, INA219 servo-rail current.
// No ISRs: the button and limit are polled at 1 kHz; debounce, long-press and every event post happen in
// the poll functions, which loop() calls on the millis()/micros() schedule in gripper.ino. Arduino only.
#pragma once
#include <Arduino.h>
#include "config.h"

void  inputsInit();
void  inputsSampleFsr();      // ADC_PERIOD_US: one FSR sample, EMA, force conversion, zeroing
void  inputsPollDigital();    // BUTTON_POLL_MS: button + limit debounce, posts BUTTON_* / LIMIT_HIT
void  inputsReadCurrent();    // INA219_PERIOD_MS: servo-rail current over I2C
void  inputsReadFeedback();   // CONTROL_PERIOD_MS: servo pot tap (FB_ENABLED builds only)

// FSR
float fsrForceN();            // filtered, zeroed, span-scaled pad force (N), >= 0
float fsrForceUnscaledN();    // same before the CALF span factor
float fsrMv();                // filtered divider-node voltage (mV)
float fsrZeroMv();            // unloaded offset from the last zeroing (mV)
void  fsrZeroStart();         // average the next CAL_SAMPLES raw samples as the zero offset
bool  fsrZeroBusy();
float fsrSpan();
bool  fsrSetSpan(float span); // false if outside [FSR_SPAN_MIN, FSR_SPAN_MAX]

// Digital
bool  buttonDown();           // debounced
bool  limitClosed();          // debounced; false when LIMIT_ENABLED == 0

// Servo pot tap
bool  feedbackValid();
float feedbackTheta();        // jaw theta (deg) from the pot

// INA219
bool  currentPresent();       // INA219 answered at boot
bool  currentValid();
float currentA();             // |servo-rail current| (A)
