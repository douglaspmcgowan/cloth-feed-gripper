"""Check that every firmware name the procedures and tools use exists in the firmware as merged.

    python docs/gripper/test/check_firmware.py

Reads `firmware/gripper/events.cpp` (event and fault names), `fsm.cpp` (state names), `protocol.cpp`
(host commands) and `config.h` (#defines), then scans `procedures/*.md` and `tools/*.py` for:
- `EVT <NAME>` / `WARN <NAME>` and backticked `ENTER_<STATE>`, `FAULT_<NAME>` names,
- host commands that `gripper_log.py` sends and that the procedures show in `code` spans,
- backticked ALL_CAPS_WITH_UNDERSCORES words that look like `config.h` constants.
Prints each name that is missing and exits 1; exits 0 when all agree. Plain Python 3.9+, pathlib only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FW = HERE.parents[2] / "firmware" / "gripper"

# Names that belong to the test tools, not the firmware.
TOOL_WORDS = {"THERMAL STOP", "MOUNT_TRIP_C", "CASE_TRIP_C", "PIN_RAIL_RELAY", "HAVE_TC2", "RESET_C", "BAD_READS_TRIP",
              "CASE_STOP_C", "MOUNT_STOP_C"}


def string_list(text: str, var: str) -> list[str]:
    m = re.search(r"%s\[\]\s*=\s*\{(.*?)\};" % re.escape(var), text, flags=re.S)
    return re.findall(r'"([A-Z0-9_]+)"', m.group(1)) if m else []


def firmware_names(fw: Path = FW) -> dict:
    ev = (fw / "events.cpp").read_text(encoding="utf-8")
    fsm = (fw / "fsm.cpp").read_text(encoding="utf-8")
    proto = (fw / "protocol.cpp").read_text(encoding="utf-8")
    cfg = (fw / "config.h").read_text(encoding="utf-8")
    events = set(string_list(ev, "kEventNames"))
    faults = set(string_list(ev, "kFaultNames"))
    states = set(string_list(fsm, "kStateNames"))
    commands = set(re.findall(r'word\(p,\s*"([A-Z_]+)"\)', proto))
    defines = set(re.findall(r"^\s*#define\s+(\w+)", cfg, flags=re.M))
    # literal "WARN <NAME>" strings printed by fsm.cpp and gripper.ino
    ino = (fw / "gripper.ino").read_text(encoding="utf-8")
    warns = set(re.findall(r'"WARN ([A-Z0-9_]+)', fsm + ino))
    # literal "EVT <NAME>" lines printed directly (EVT HOLD_I, EVT HOLD_BACKOFF, EVT CAL_THETA_C0)
    evt_lit = {n for n in re.findall(r'"EVT ([A-Z0-9_]+)', fsm + ino) if not n.endswith("_")}
    values = {m.group(1): float(m.group(2)) for m in re.finditer(r"^\s*#define\s+(\w+)\s+(-?[0-9.]+)\b", cfg, flags=re.M)}
    # `EVT FAULT_<name>` is printed for every fault code (fsm.cpp), `ENTER_<state>` for every state.
    return {"events": events, "faults": faults, "states": states, "commands": commands, "defines": defines, "warns": warns,
            "values": values,
            "evt_names": events | {"FAULT_" + f for f in faults} | {"ENTER_" + s for s in states} | evt_lit}


def scan(fw: Path = FW, root: Path = HERE) -> list[str]:
    n = firmware_names(fw)
    problems: list[str] = []
    files = sorted((root / "procedures").glob("*.md")) + sorted((root / "tools").glob("*.py"))
    for p in files:
        text = p.read_text(encoding="utf-8")
        for name in set(re.findall(r"\bEVT ([A-Z][A-Z0-9_]+)", text)):
            if name.endswith("_"):  # a placeholder such as FAULT_<name>
                continue
            if name not in n["evt_names"] and name not in TOOL_WORDS:
                problems.append("%s: EVT %s is not an event the firmware prints" % (p.name, name))
        for name in set(re.findall(r"\bWARN ([A-Z][A-Z0-9_]+)", text)):
            if name not in n["events"] and name not in n["warns"]:
                problems.append("%s: WARN %s is not a warning the firmware prints" % (p.name, name))
        for name in set(re.findall(r"`(ENTER_[A-Z]+)`", text)):
            if name[len("ENTER_"):] not in n["states"]:
                problems.append("%s: %s is not a state" % (p.name, name))
        for name in set(re.findall(r"`(FAULT_[A-Z0-9_]+)`", text)):
            if name == "FAULT_BACKOFF_DEG":
                if name not in n["defines"]:
                    problems.append("%s: %s is not in config.h" % (p.name, name))
            elif name not in n["evt_names"]:
                problems.append("%s: %s is not a fault the firmware names" % (p.name, name))
        for name in set(re.findall(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`", text)):
            if (name.startswith(("EVT", "ENTER_", "FAULT_", "FAULT")) or name in n["evt_names"] or name in TOOL_WORDS
                    or name in n["commands"] or name in n["warns"]):
                continue
            if re.match(r"^(F|FSR|JAW|SERVO|STALL|TIMEOUT|CAL|PIN|INA219|BUTTON|CTRL|CONTROL|LIMIT|R_|SERIAL|STREAM|I2C|HOLD|I_)", name):
                if name not in n["defines"]:
                    problems.append("%s: %s is not a config.h constant" % (p.name, name))
        # A config.h constant quoted with its value, "`NAME` 2900", must quote the value config.h has; a value meant
        # for a debug build is written "`NAME` <value> (shipped <value>)" and only the shipped one is checked.
        for m in re.finditer(r"`([A-Z][A-Z0-9_]+)`\s+(-?[0-9]+(?:\.[0-9]+)?)(?![0-9.])(\s*\(shipped\s+(-?[0-9]+(?:\.[0-9]+)?))?", text):
            name = m.group(1)
            if name not in n["values"]:
                continue
            quoted = float(m.group(4) if m.group(4) else m.group(2))
            if abs(quoted - n["values"][name]) > 1e-9:
                problems.append("%s: `%s` quoted as %g, config.h has %g" % (p.name, name, quoted, n["values"][name]))
        # commands the logger sends
        if p.suffix == ".py":
            for cmd in set(re.findall(r'send\("([A-Z_]+)(?: |")', text)):
                if cmd not in n["commands"]:
                    problems.append("%s: command %s is not parsed by protocol.cpp" % (p.name, cmd))
    return problems


def main(argv=None) -> int:
    n = firmware_names()
    print("firmware: %d events, %d fault codes, %d states, %d commands (%s)" %
          (len(n["events"]), len(n["faults"]), len(n["states"]), len(n["commands"]), ", ".join(sorted(n["commands"]))))
    problems = scan()
    for p in problems:
        print("MISSING", p)
    print("PASS procedures and tools agree with the firmware" if not problems else "FAIL %d disagreement(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
