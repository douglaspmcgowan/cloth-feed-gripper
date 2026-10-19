// inputs.cpp -- ESP32 hardware reads (Arduino only). See inputs.h.
// Every function returns at once: one ADC conversion, one pin read, or one 2-byte I2C register read.
#include "inputs.h"
#include <Wire.h>
#include "events.h"
#include "fsr_filter.h"

// ---------------------------------------------------------------------------------------------------------
// FSR
static FsrFilter s_fsr;                  // shared, host-tested sample chain (fsr_filter.cpp)

// Digital
static bool     s_btnRaw = false, s_btnStable = false, s_btnLongSent = false;
static uint32_t s_btnChange = 0, s_btnDownAt = 0;
static bool     s_limRaw = false, s_limStable = false;
static uint32_t s_limChange = 0;

// INA219
static bool  s_inaPresent = false;
static bool  s_iValid = false;
static float s_iA = 0.0f;

// Servo pot
static bool  s_fbValid = false;
static float s_fbTheta = 0.0f;

void inputsInit() {
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_LIMIT_OPEN, INPUT_PULLUP);
  analogReadResolution(12);                          // 12-bit is the ESP32 default [S: ESP-IDF ADC]
  analogSetPinAttenuation(PIN_FSR_ADC, ADC_11db);    // 150-2450 mV recommended range [S]
#if FB_ENABLED
  analogSetPinAttenuation(PIN_SERVO_FB_ADC, ADC_11db);
#endif
  fsrFilterInit(s_fsr, (float)analogReadMilliVolts(PIN_FSR_ADC));
#if INA219_ENABLED
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, I2C_HZ);
  Wire.setTimeOut(5);                                // ms; a hung bus never stalls the loop for long
  Wire.beginTransmission((uint8_t)INA219_ADDR);
  s_inaPresent = (Wire.endTransmission() == 0);      // missing breakout: disabled, not a fault
#endif
}

void inputsSampleFsr() {
  const uint8_t fl = fsrFilterSample(s_fsr, (float)analogReadMilliVolts(PIN_FSR_ADC));
  if (fl & FSRF_SHORT) eventPost(EV_FAULT_SENSOR, (float)FAULT_FSR_SHORT);
  if (fl & FSRF_STUCK) eventPost(EV_FAULT_SENSOR, (float)FAULT_FSR_STUCK);
}

float fsrMv() { return s_fsr.emaMv; }
float fsrZeroMv() { return s_fsr.zeroMv; }
float fsrForceUnscaledN() { return fsrFilterForceUnscaled(s_fsr); }
float fsrForceN() { return fsrFilterForce(s_fsr); }
void  fsrZeroStart() { fsrFilterZeroStart(s_fsr); }
bool  fsrZeroBusy() { return s_fsr.zeroBusy; }
float fsrSpan() { return s_fsr.span; }
bool  fsrSetSpan(float span) { return fsrFilterSetSpan(s_fsr, span); }

// ---------------------------------------------------------------------------------------------------------
void inputsPollDigital() {
  const uint32_t now = millis();
  const bool b = (digitalRead(PIN_BUTTON) == LOW);
  if (b != s_btnRaw) { s_btnRaw = b; s_btnChange = now; }
  if (b != s_btnStable && now - s_btnChange >= (uint32_t)BUTTON_DEBOUNCE_MS) {
    s_btnStable = b;
    if (b) {
      s_btnDownAt = now;
      s_btnLongSent = false;
    } else if (!s_btnLongSent) {
      eventPost(EV_BUTTON_PRESS);
    }
  }
  if (s_btnStable && !s_btnLongSent && now - s_btnDownAt >= (uint32_t)BUTTON_LONG_MS) {
    s_btnLongSent = true;
    eventPost(EV_BUTTON_LONG);
  }
#if LIMIT_ENABLED
  const bool l = (digitalRead(PIN_LIMIT_OPEN) == LOW);
  if (l != s_limRaw) { s_limRaw = l; s_limChange = now; }
  if (l != s_limStable && now - s_limChange >= (uint32_t)LIMIT_DEBOUNCE_MS) {
    s_limStable = l;
    if (l) eventPost(EV_LIMIT_HIT);
  }
#endif
}

bool buttonDown() { return s_btnStable; }
bool limitClosed() { return LIMIT_ENABLED ? s_limStable : false; }

// ---------------------------------------------------------------------------------------------------------
void inputsReadCurrent() {
  s_iValid = false;
  if (!s_inaPresent) return;
  Wire.beginTransmission((uint8_t)INA219_ADDR);
  Wire.write((uint8_t)0x01);                         // shunt-voltage register [S: TI INA219]
  if (Wire.endTransmission(false) != 0) return;
  if (Wire.requestFrom((uint8_t)INA219_ADDR, (uint8_t)2) != 2) return;
  const int16_t raw = (int16_t)(((uint16_t)Wire.read() << 8) | (uint16_t)Wire.read());
  const float shuntV = (float)raw * (float)INA219_SHUNT_LSB_UV * 1e-6f;
  s_iA = fabsf(shuntV / (float)INA219_SHUNT_OHM);
  s_iValid = true;
}

bool  currentPresent() { return s_inaPresent; }
bool  currentValid() { return s_iValid; }
float currentA() { return s_iA; }

// ---------------------------------------------------------------------------------------------------------
void inputsReadFeedback() {
#if FB_ENABLED
  const float mv = (float)analogReadMilliVolts(PIN_SERVO_FB_ADC);
  s_fbTheta = (mv - (float)FB_MV_AT_JAW0) / (float)FB_MV_PER_DEG;
  s_fbValid = true;
#else
  s_fbValid = false;
#endif
}

bool  feedbackValid() { return s_fbValid; }
float feedbackTheta() { return s_fbTheta; }
