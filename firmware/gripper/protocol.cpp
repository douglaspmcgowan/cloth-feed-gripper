// protocol.cpp -- see protocol.h. No heap, no sscanf: strtod on a bounded line.
#include "protocol.h"
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

static const char *skipSpace(const char *p) {
  while (*p && isspace((unsigned char)*p)) p++;
  return p;
}

// Case-insensitive match of the first word; returns the rest of the line after it, or nullptr.
static const char *word(const char *p, const char *w) {
  size_t n = strlen(w);
  for (size_t i = 0; i < n; i++) {
    if (toupper((unsigned char)p[i]) != w[i]) return nullptr;
  }
  if (p[n] && !isspace((unsigned char)p[n])) return nullptr;
  return skipSpace(p + n);
}

// Parses one number that must end the line. Returns false if absent or malformed.
static bool number(const char *p, float &out) {
  if (!*p) return false;
  char *end = nullptr;
  double v = strtod(p, &end);
  if (end == p) return false;
  end = (char *)skipSpace(end);
  if (*end) return false;
  out = (float)v;
  return true;
}

static Command make(CmdKind k, EventType ev = EV_NONE, float arg = 0.0f) {
  Command c;
  c.kind = k;
  c.ev = ev;
  c.arg = arg;
  return c;
}

Command parseCommand(const char *line) {
  const char *p = skipSpace(line);
  if (!*p) return make(CMD_NONE);
  const char *r;
  float v;
  // Longer words first so "FEED_DONE" is not read as "FEED".
  if ((r = word(p, "ARM_AT_POSE"))) return *r ? make(CMD_ERROR) : make(CMD_EVENT, EV_SERIAL_CMD_AT_POSE);
  if ((r = word(p, "FEED_DONE")))   return *r ? make(CMD_ERROR) : make(CMD_EVENT, EV_SERIAL_CMD_FEED_DONE);
  if ((r = word(p, "FEED")))        return *r ? make(CMD_ERROR) : make(CMD_EVENT, EV_SERIAL_CMD_FEED);
  if ((r = word(p, "STREAM")))      return number(r, v) && v >= 0.0f ? make(CMD_STREAM, EV_NONE, v) : make(CMD_ERROR);
  if ((r = word(p, "ILIM")))        return number(r, v) && v >= 0.0f && v < 100.0f ? make(CMD_ILIM, EV_NONE, v) : make(CMD_ERROR);
  if ((r = word(p, "BACKOFF")))     return number(r, v) && v >= 0.0f && v <= 1.0f ? make(CMD_BACKOFF, EV_NONE, v) : make(CMD_ERROR);
  if ((r = word(p, "CALF")))        return number(r, v) && v > 0.0f ? make(CMD_CALF, EV_NONE, v) : make(CMD_ERROR);
  if ((r = word(p, "G"))) {
    if (!*r) return make(CMD_EVENT, EV_SERIAL_CMD_GRIP, (float)F_TARGET_DEFAULT_N);
    return number(r, v) && v > 0.0f ? make(CMD_EVENT, EV_SERIAL_CMD_GRIP, v) : make(CMD_ERROR);
  }
  if ((r = word(p, "R"))) return *r ? make(CMD_ERROR) : make(CMD_EVENT, EV_SERIAL_CMD_RELEASE);
  if ((r = word(p, "H"))) return *r ? make(CMD_ERROR) : make(CMD_EVENT, EV_SERIAL_CMD_HOME);
  if ((r = word(p, "C"))) return *r ? make(CMD_ERROR) : make(CMD_EVENT, EV_SERIAL_CMD_CAL);
  if ((r = word(p, "A"))) return *r ? make(CMD_ERROR) : make(CMD_EVENT, EV_SERIAL_CMD_APPROACH);
  if ((r = word(p, "S"))) return *r ? make(CMD_ERROR) : make(CMD_STATUS);
  return make(CMD_ERROR);
}
