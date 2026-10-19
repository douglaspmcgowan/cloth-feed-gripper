// gripper.ino -- ME102B cloth-feed gripper firmware (W2b-1).
// Board: ESP32 DevKitC (ESP32-WROOM-32), FQBN esp32:esp32:esp32, esp32 core 2.0.17, library ESP32Servo 1.2.1.
// Design basis: docs/gripper/DESIGN-BASIS.md section 8; control design: docs/gripper/analysis/controls.md.
//
// Event-driven: loop() never blocks and never calls delay(). It runs four schedules off micros()/millis()
//   1 kHz  FSR sample -> EMA -> force -> force monitor (contact, target, slip, lost, over-force events)
//   1 kHz  button + limit debounce (press, long press, limit events)
//   50 Hz  INA219 current -> over-current / table-touch events; motion profile or force loop -> servo pulse
//   every pass: serial line assembly, state timeouts, then up to EVENTS_PER_LOOP queued events dispatched
//   through the transition table in fsm.cpp; the task watchdog is fed once per pass (WDT_TIMEOUT_S).
#include "config.h"
#ifdef ACTUATOR_DC_GEARMOTOR
#error "The DC gearmotor branch (TA 3.3) is not implemented; build the default PWM servo branch."
#endif
#include <ESP32Servo.h>
#include <esp_task_wdt.h>   // ESP-IDF 4.4 task watchdog (esp32 core 2.0.17): esp_task_wdt_init(timeout_s, panic)
#include <esp_system.h>     // esp_reset_reason()
#include "events.h"
#include "inputs.h"
#include "fsm.h"
#include "protocol.h"
#include "servo_map.h"

static Servo    g_servo;
static Core     g_core;
static uint32_t g_tAdcUs, g_tDigMs, g_tCtlMs, g_tLedMs, g_tStatusMs;
static uint32_t g_statusPeriodMs = STATUS_PERIOD_MS_DEF;
static uint32_t g_txDropped = 0;
static bool     g_led = false;
static char     g_line[SERIAL_LINE_MAX + 1];
static uint8_t  g_lineLen = 0;
static bool     g_lineOverflow = false;
#if FB_ENABLED
static uint32_t g_stallSince = 0;
static bool     g_stallPosted = false;
#endif

// One line to the host. Dropped (and counted) rather than blocking when the TX buffer is full.
static void hostLine(const char *s) {
  const size_t n = strlen(s) + 2;
  if ((size_t)Serial.availableForWrite() < n) { g_txDropped++; return; }
  Serial.print(s);
  Serial.print("\r\n");
}

static void statusLine() {
  char b[192];
  // Ih = rail current in this hold with the F1 back-off off (thermal F4; -1.00 until measured), bo = back-off (deg).
  snprintf(b, sizeof b, "ST %s %lu th=%.2f F=%.2f sp=%.1f I=%.2f%s c0=%.2f%s fault=%s q=%u drop=%lu/%lu Ih=%.2f bo=%.2f",
           stateName(g_core.state), (unsigned long)millis(), (double)coreTheta(g_core), (double)g_core.lastF,
           (double)g_core.sp, (double)g_core.lastI, g_core.lastIValid ? "" : "(n/a)", (double)g_core.thetaC0,
           g_core.calibrated ? "" : "(default)", faultName(g_core.fault), (unsigned)eventsPending(),
           (unsigned long)eventsDropped(), (unsigned long)g_txDropped, (double)g_core.iHoldRef, (double)g_core.fc.boff);
  hostLine(b);
}

static void handleLine(const char *line) {
  const Command c = parseCommand(line);
  char b[64];
  switch (c.kind) {
    case CMD_NONE: break;
    case CMD_EVENT:
      if (!eventPost(c.ev, c.arg)) hostLine("ERR queue full");
      break;
    case CMD_STATUS: statusLine(); break;
    case CMD_STREAM: {
      float hz = c.arg > (float)STREAM_HZ_MAX ? (float)STREAM_HZ_MAX : c.arg;
      g_statusPeriodMs = hz > 0.0f ? (uint32_t)(1000.0f / hz) : 0;
      snprintf(b, sizeof b, "OK STREAM %lu ms", (unsigned long)g_statusPeriodMs);
      hostLine(b);
      break;
    }
    case CMD_CALF: {
      const float raw = fsrForceUnscaledN();
      if (raw < (float)F_TOUCH_N || !fsrSetSpan(c.arg / raw)) {
        snprintf(b, sizeof b, "ERR CALF raw=%.2f", (double)raw);
      } else {
        snprintf(b, sizeof b, "OK CALF span=%.3f", (double)fsrSpan());
      }
      hostLine(b);
      break;
    }
    case CMD_ILIM:
      if (coreSetHoldCurrentLimit(g_core, c.arg)) {
        snprintf(b, sizeof b, "OK ILIM %.2f", (double)g_core.holdILimit);
      } else {
        snprintf(b, sizeof b, "ERR ILIM");
      }
      hostLine(b);
      break;
    case CMD_BACKOFF:
      if (coreSetBackoffFactor(g_core, c.arg)) {
        snprintf(b, sizeof b, "OK BACKOFF %.2f", (double)g_core.backoffFactor);
      } else {
        snprintf(b, sizeof b, "ERR BACKOFF");
      }
      hostLine(b);
      break;
    default: hostLine("ERR command"); break;
  }
}

static void serialPoll() {
  while (Serial.available() > 0) {
    const int ch = Serial.read();
    if (ch < 0) break;
    if (ch == '\r' || ch == '\n') {
      if (g_lineOverflow) hostLine("ERR line too long");
      else if (g_lineLen) { g_line[g_lineLen] = 0; handleLine(g_line); }
      g_lineLen = 0;
      g_lineOverflow = false;
    } else if (g_lineLen < SERIAL_LINE_MAX) {
      g_line[g_lineLen++] = (char)ch;
    } else {
      g_lineOverflow = true;
    }
  }
}

static void ledTick(uint32_t now) {
  const uint32_t half = g_core.state == ST_FAULT ? LED_BLINK_FAULT_MS
                      : g_core.state == ST_IDLE  ? LED_BLINK_IDLE_MS : LED_BLINK_BUSY_MS;
  if (now - g_tLedMs >= half) {
    g_tLedMs = now;
    g_led = !g_led;
    digitalWrite(PIN_STATUS_LED, g_led ? HIGH : LOW);
  }
}

#if FB_ENABLED
// R20 with a pot tap: command and measured jaw angle disagree by STALL_ERR_DEG for STALL_TIME_MS.
static void stallCheck(uint32_t now) {
  if (!feedbackValid()) return;
  if (fabsf(coreTheta(g_core) - feedbackTheta()) > (float)STALL_ERR_DEG) {
    if (!g_stallSince) g_stallSince = now ? now : 1;
    if (!g_stallPosted && now - g_stallSince >= (uint32_t)STALL_TIME_MS) {
      g_stallPosted = true;
      eventPost(EV_FAULT_STALL, feedbackTheta());
    }
  } else {
    g_stallSince = 0;
    g_stallPosted = false;
  }
}
#endif

void setup() {
  // Safe output first: after a power-up, brown-out or watchdog reset the jaw is commanded open before anything else
  // (the I2C probe in inputsInit() can take up to its 5 ms timeout).
  ESP32PWM::allocateTimer(0);
  g_servo.setPeriodHertz(SERVO_PWM_HZ);
  g_servo.attach(PIN_SERVO_PWM, SERVO_US_LIMIT_MIN, SERVO_US_LIMIT_MAX);
  g_servo.writeMicroseconds(jawToUs((float)JAW_OPEN_DEG));
  // Task watchdog on this (loop) task: a hung loop() resets the MCU instead of freezing the last pulse (a squeeze).
  esp_task_wdt_init(WDT_TIMEOUT_S, true);
  esp_task_wdt_add(NULL);

  Serial.setTxBufferSize(SERIAL_TX_BUF);
  Serial.begin(SERIAL_BAUD);
  pinMode(PIN_STATUS_LED, OUTPUT);
  eventsInit();
  inputsInit();

  CoreIo io;
  io.report = hostLine;
  io.fsrZeroStart = fsrZeroStart;
  io.fsrZeroBusy = fsrZeroBusy;
  io.fsrZeroMv = fsrZeroMv;
  io.limitClosed = limitClosed;
  const uint32_t now = millis();
  coreInit(g_core, io, now);
  coreSetCurrentPresent(g_core, INA219_ENABLED && currentPresent());
  if (INA219_ENABLED && !currentPresent()) hostLine("WARN INA219_ABSENT 0 0.00 (no over-current stall detection, R20)");
  const esp_reset_reason_t rr = esp_reset_reason();
  if (rr == ESP_RST_TASK_WDT || rr == ESP_RST_INT_WDT || rr == ESP_RST_WDT || rr == ESP_RST_PANIC || rr == ESP_RST_BROWNOUT) {
    char b[48];
    snprintf(b, sizeof b, "WARN RESET 0 %d (watchdog, panic or brown-out)", (int)rr);
    hostLine(b);
  }
  g_tAdcUs = micros();
  g_tDigMs = g_tCtlMs = g_tLedMs = g_tStatusMs = now;
}

void loop() {
  esp_task_wdt_reset();
  const uint32_t nowUs = micros();
  uint32_t now = millis();

  if (nowUs - g_tAdcUs >= (uint32_t)ADC_PERIOD_US) {
    g_tAdcUs += ADC_PERIOD_US;
    if (nowUs - g_tAdcUs >= 10u * ADC_PERIOD_US) g_tAdcUs = nowUs;  // fell behind: resynchronise, no burst
    inputsSampleFsr();
    coreSampleForce(g_core, now, fsrForceN());
  }

  if (now - g_tDigMs >= (uint32_t)BUTTON_POLL_MS) {
    g_tDigMs = now;
    inputsPollDigital();
  }

  if (now - g_tCtlMs >= (uint32_t)CONTROL_PERIOD_MS) {
    g_tCtlMs += CONTROL_PERIOD_MS;
    if (now - g_tCtlMs >= 5u * CONTROL_PERIOD_MS) g_tCtlMs = now;
    inputsReadCurrent();
    coreSampleCurrent(g_core, now, currentValid(), currentA());
    inputsReadFeedback();
#if FB_ENABLED
    stallCheck(now);
#endif
    const float theta = coreControl(g_core, now, (float)CONTROL_PERIOD_MS * 0.001f);
    // FAULT with the over-current persisting: stop the pulse so the servo goes limp (R20, R26).
    if (g_core.relax && g_servo.attached()) {
      g_servo.detach();
    } else if (!g_core.relax && !g_servo.attached()) {
      g_servo.attach(PIN_SERVO_PWM, SERVO_US_LIMIT_MIN, SERVO_US_LIMIT_MAX);
    }
    if (g_servo.attached()) g_servo.writeMicroseconds(jawToUs(theta));
  }

  serialPoll();
  now = millis();
  coreTick(g_core, now);

  Event e;
  char b[64];
  for (uint8_t n = 0; n < EVENTS_PER_LOOP && eventPop(e); n++) {
    snprintf(b, sizeof b, "EVT %s %lu %.2f", eventName(e.type), (unsigned long)e.t_ms, (double)e.arg);
    hostLine(b);
    coreDispatch(g_core, e);
  }

  ledTick(now);
  if (g_statusPeriodMs && now - g_tStatusMs >= g_statusPeriodMs) {
    g_tStatusMs = now;
    statusLine();
  }
}
