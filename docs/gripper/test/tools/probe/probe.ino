// Bench reader for the gripper tests: pinch-force probe (TAL220 + HX711) and case
// thermocouple (type K + MAX31855). Runs on a second board (Arduino Uno or ESP32),
// never on the gripper's ESP32. Prints one CSV line per sample:  <ms>,<force_N>,<case_C>,<mount_C>,<rail_on>
// at the HX711's rate (set RATE high on the SparkFun board for 80 SPS; 10 SPS otherwise).
//
// Libraries (Arduino Library Manager): "HX711" by Bogdan Necula (bogde),
// "Adafruit MAX31855 library". Not compiled in the lane that wrote it (no arduino-cli in
// that container): compile once before the test day.
//
// Thermal cutoff (TP-06 unattended run, TP-07 soak). Two type K channels: the servo case and the
// printed mount. A relay (or a logic-level MOSFET) in the servo's +6.5 V supply line is driven by
// PIN_RAIL_RELAY: HIGH = rail on. Wire it normally-open, so a probe board that loses power, resets
// or hangs also drops the rail. The relay stays off after power-up until you send `e`, and `e` is
// refused while a channel reads NaN or above its re-arm temperature. A trip latches until `e`.
//
// Serial commands (115200 baud, end with newline):
//   t           tare: zero the force with the probe unloaded in its use position
//   r           print the mean raw count of 20 readings (calibration, TP-01 step 2)
//   s <scale>   set counts per newton from the TP-01 fit (stored in RAM only; note it down)
//   q / g       stop / start the stream
//   e           enable the servo rail (relay on) if both thermocouples read and are below RESET_C
//   x           force the rail off now (relay off)
//   l <c> <m>   set the trip temperatures (case, mount) in RAM; power-up values are the constants below

#include <HX711.h>
#include <SPI.h>
#include <Adafruit_MAX31855.h>

// Pins: change to match your wiring. Uno defaults below; on an ESP32 use any free GPIOs.
const int PIN_HX_DT = 3;
const int PIN_HX_SCK = 2;
const int PIN_TC_CS = 10;   // MAX31855 CS; SCK and MISO on the hardware SPI pins
const int PIN_TC2_CS = 9;   // MAX31855 for the mount thermocouple; shares SCK and MISO
const int PIN_RAIL_RELAY = 7;  // HIGH = servo rail on (normally-open relay, so a dead probe cuts the rail)
const bool HAVE_TC = true;  // false if the case thermocouple is not fitted (the rail can then never be enabled)
const bool HAVE_TC2 = true; // false if the mount thermocouple is not fitted

// Trip temperatures: the limit in analysis/gripper/thermal.md minus the thermocouple's U (1.6 C, test_plan.py).
// Case: R26 60 C. Mount: 50 C for bare PETG, 60 C with the C1 metal sleeves (set MOUNT_TRIP_C to 58.4).
float CASE_TRIP_C = 58.4f;   // `l <case> <mount>` changes both in RAM (TP-07 uses its FAIL thresholds)
float MOUNT_TRIP_C = 48.4f;
const float RESET_C = 45.0f;         // re-arm only below this
const uint8_t BAD_READS_TRIP = 3;    // consecutive NaN readings on a fitted channel trip the rail

HX711 cell;
Adafruit_MAX31855 tc(PIN_TC_CS);
Adafruit_MAX31855 tc2(PIN_TC2_CS);
bool railOn = false;
uint8_t badReads = 0;
uint32_t lastTcMs = 0;
float caseC = NAN, mountC = NAN;
float countsPerN = 1.0f;  // replace with the TP-01 fit; 1.0 prints raw counts minus the tare
bool streaming = true;
char buf[32];
uint8_t n = 0;

void handle(const char *line) {
  if (line[0] == 't') {
    cell.tare(20);
    Serial.println(F("# tared"));
  } else if (line[0] == 'r') {
    Serial.print(F("# raw "));
    Serial.println(cell.read_average(20));
  } else if (line[0] == 's') {
    float v = atof(line + 1);
    if (v != 0.0f) {
      countsPerN = v;
      cell.set_scale(countsPerN);
    }
    Serial.print(F("# scale "));
    Serial.println(countsPerN, 3);
  } else if (line[0] == 'e') {
    float c = HAVE_TC ? (float)tc.readCelsius() : NAN;
    float m = HAVE_TC2 ? (float)tc2.readCelsius() : 0.0f;
    if (isnan(c) || isnan(m) || c >= RESET_C || m >= RESET_C) {
      Serial.println(F("# ENABLE REFUSED: thermocouple unreadable or still warm"));
    } else {
      railOn = true;
      digitalWrite(PIN_RAIL_RELAY, HIGH);
      Serial.println(F("# RAIL ON"));
    }
  } else if (line[0] == 'x') {
    railOn = false;
    digitalWrite(PIN_RAIL_RELAY, LOW);
    Serial.println(F("# RAIL OFF (manual)"));
  } else if (line[0] == 'l') {
    char *rest = nullptr;
    float c = (float)strtod(line + 1, &rest);
    float m = (float)atof(rest);  // sscanf("%f") is not available on an Arduino Uno
    if (rest != line + 1 && c > 0.0f && m > 0.0f) {
      CASE_TRIP_C = c;
      MOUNT_TRIP_C = m;
    }
    Serial.print(F("# trip case "));
    Serial.print(CASE_TRIP_C, 1);
    Serial.print(F(" mount "));
    Serial.println(MOUNT_TRIP_C, 1);
  } else if (line[0] == 'q') {
    streaming = false;
  } else if (line[0] == 'g') {
    streaming = true;
  }
}

void setup() {
  Serial.begin(115200);
  cell.begin(PIN_HX_DT, PIN_HX_SCK);
  cell.set_scale(countsPerN);
  pinMode(PIN_RAIL_RELAY, OUTPUT);
  digitalWrite(PIN_RAIL_RELAY, LOW);  // rail off until `e`
  if (HAVE_TC) tc.begin();
  if (HAVE_TC2) tc2.begin();
  Serial.println(F("# ms,force_N,case_C,mount_C,rail_on"));
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (n > 0) {
        buf[n] = 0;
        handle(buf);
        n = 0;
      }
    } else if (n < sizeof(buf) - 1) {
      buf[n++] = c;
    }
  }
  // Cutoff: every 100 ms, independent of the load cell and of `q` (stream off).
  if (millis() - lastTcMs >= 100) {
    lastTcMs = millis();
    caseC = HAVE_TC ? (float)tc.readCelsius() : NAN;
    mountC = HAVE_TC2 ? (float)tc2.readCelsius() : NAN;
    bool bad = (HAVE_TC && isnan(caseC)) || (HAVE_TC2 && isnan(mountC));
    badReads = bad ? (uint8_t)min(badReads + 1, 255) : 0;
    bool hot = (!isnan(caseC) && caseC >= CASE_TRIP_C) || (!isnan(mountC) && mountC >= MOUNT_TRIP_C);
    if (railOn && (hot || badReads >= BAD_READS_TRIP)) {
      railOn = false;
      digitalWrite(PIN_RAIL_RELAY, LOW);
      Serial.print(F("# CUTOFF case "));
      Serial.print(caseC, 1);
      Serial.print(F(" mount "));
      Serial.println(mountC, 1);
    }
  }
  if (streaming && cell.is_ready()) {
    float f = cell.get_units(1);
    Serial.print(millis());
    Serial.print(',');
    Serial.print(f, 4);
    Serial.print(',');
    Serial.print(caseC, 2);
    Serial.print(',');
    Serial.print(mountC, 2);
    Serial.print(',');
    Serial.println(railOn ? 1 : 0);
  }
}
