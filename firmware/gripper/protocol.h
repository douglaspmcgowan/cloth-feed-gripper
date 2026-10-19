// protocol.h -- host command parser (hardware-free). USB serial, 115200 baud, one ASCII command per line [DB 8].
//   Host -> MCU: G [newtons] | R | H | C | S | A | ARM_AT_POSE | FEED | FEED_DONE | STREAM <hz> | CALF <newtons> | ILIM <amps> |
//                 BACKOFF <factor>
//   MCU -> host: EVT <name> <millis> [arg], ST ... (status), ERR <text>
#pragma once
#include "platform.h"
#include "events.h"

enum CmdKind : uint8_t {
  CMD_NONE = 0,   // empty line
  CMD_EVENT,      // forward ev/arg to the FSM queue
  CMD_STATUS,     // "S": print one status line
  CMD_STREAM,     // "STREAM <hz>": periodic status, 0 = off
  CMD_CALF,       // "CALF <N>": a known weight sits on the puck; set the FSR span
  CMD_ILIM,       // "ILIM <A>": HOLD/FEED servo-rail current limit for the thermal track (R26), 0 = off
  CMD_BACKOFF,    // "BACKOFF <f>": thermal F1 back-off factor 0..1, 0 = off (F4: read Ih= with it off)
  CMD_ERROR       // unknown or malformed
};

struct Command {
  CmdKind   kind;
  EventType ev;
  float     arg;
};

Command parseCommand(const char *line);
