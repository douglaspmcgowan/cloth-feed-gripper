"""Log a serial port to CSV, send commands, and run the scripted test sequences.

Works for the gripper's ESP32 (115200 baud, ASCII lines, DESIGN-BASIS section 8) and for
the probe reader (`probe/probe.ino`). Every received line is written as
`host_s,line` where host_s is seconds on the laptop's clock, so two logs taken at the
same time (gripper and probe, two terminals) line up.

Needs pyserial on the laptop: `python -m pip install pyserial`. Python 3.9+, Windows,
macOS or Linux.

Interactive (type a command, Enter sends it; Ctrl+C stops):
    python docs/gripper/test/tools/gripper_log.py --port COM5 --out TP-01_log.csv

Sequences (the gripper must be calibrated and in IDLE first):
    --sequence close --n 10            TP-03: STREAM 50, then n x (G 5, wait HOLD, 1 s, R, wait IDLE)
    --sequence hold --n 6 --hold 25.5  TP-01/TP-02: n x (G 5, hold for --hold s after HOLD, R)
    --sequence soak --minutes 30       TP-07: DESIGN-BASIS section 7 cycle, 35 s, hold 25.5 s at 5 N
    --sequence cycle --n 10000 --hold 2.0   TP-06: fast cycles; stops on the first FAULT
    ... add --probe-port <port> --probe-out TP-06_temp.csv to watch the probe board's thermocouples
        (TP-06 and TP-07 require it): the run opens the jaw (R) and stops when the case reads
        >= 58.4 C or the mount >= 48.4 C, when a reading is NaN, or when the probe goes silent for 5 s.
        The probe board also cuts the servo rail itself (probe/probe.ino).
    --sequence trip --n 22             TP-04/TP-05: n x (G 5, wait HOLD or FAULT, operator acts, H to clear)
"""
from __future__ import annotations

import argparse
import csv
import sys
import threading
import time
from pathlib import Path

DUTY = {"close_s": 0.5, "hold_s": 25.5, "release_s": 0.5, "rest_s": 8.5}  # DESIGN-BASIS section 7: 35 s cycle


CASE_STOP_C = 58.4   # thermal.md R26 case limit 60 C minus U 1.6 C
MOUNT_STOP_C = 48.4  # thermal.md bare-PETG mount limit 50 C minus U 1.6 C
PROBE_SILENT_S = 5.0


class TempWatch:
    """Reads the probe board's `ms,force_N,case_C,mount_C,rail_on` lines on a second port and
    raises `reason` when the run must stop: over temperature, a NaN reading, or silence."""

    def __init__(self, port: str, baud: int, out: Path, case_stop: float, mount_stop: float):
        import serial

        self.ser = serial.Serial()
        self.ser.port, self.ser.baudrate, self.ser.timeout = port, baud, 0.1
        self.ser.dtr = False
        self.ser.rts = False
        self.ser.open()
        self.out = out.open("a", newline="", encoding="utf-8")
        self.w = csv.writer(self.out, lineterminator="\n")
        self.case_stop, self.mount_stop = case_stop, mount_stop
        self.reason: str | None = None
        self.last_rx = time.time()
        self.stop = False
        self.t = threading.Thread(target=self._read, daemon=True)
        self.t.start()

    def check_line(self, line: str) -> str | None:
        """Pure decision on one probe line; returns a stop reason or None."""
        if line.startswith("# CUTOFF"):
            return "probe board cut the rail: " + line
        parts = line.split(",")
        if len(parts) < 3:
            return None
        try:
            case = float(parts[2])
            mount = float(parts[3]) if len(parts) > 3 else float("nan")
        except ValueError:
            return None
        if case != case:
            return "case thermocouple reads NaN"
        if case >= self.case_stop:
            return "case %.1f C >= %.1f C" % (case, self.case_stop)
        if mount == mount and mount >= self.mount_stop:
            return "mount %.1f C >= %.1f C" % (mount, self.mount_stop)
        return None

    def _read(self):
        buf = b""
        while not self.stop:
            chunk = self.ser.read(256)
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("ascii", "replace").strip()
                if not line:
                    continue
                self.last_rx = time.time()
                self.w.writerow(["%.4f" % self.last_rx, line])
                self.out.flush()
                why = self.check_line(line)
                if why and self.reason is None:
                    self.reason = why

    def tripped(self) -> str | None:
        if self.reason is None and time.time() - self.last_rx > PROBE_SILENT_S:
            self.reason = "probe board silent for %.0f s" % PROBE_SILENT_S
        return self.reason

    def close(self):
        self.stop = True
        self.t.join(timeout=1)
        self.ser.close()
        self.out.close()


def thermal_stop(link, watch, where: str) -> bool:
    """True (after opening the jaw) when the watch has tripped."""
    why = watch.tripped() if watch else None
    if why:
        link.send("R")  # jaw open; the probe board has already cut the servo rail
        print("THERMAL STOP at %s: %s. Jaw opened (R). Rail is cut by the probe board. Run ended." % (where, why))
        return True
    return False


class Link:
    """Serial link with a reader thread that writes every line to the CSV and keeps the last events."""

    def __init__(self, port: str, baud: int, out: Path, echo: bool = True):
        import serial  # imported here so the parsing tools work without pyserial

        # DTR/RTS low: opening the port must not reset the board (ESP32 DevKitC and Uno auto-reset).
        self.ser = serial.Serial()
        self.ser.port, self.ser.baudrate, self.ser.timeout = port, baud, 0.1
        self.ser.dtr = False
        self.ser.rts = False
        self.ser.open()
        self.out = out.open("a", newline="", encoding="utf-8")
        self.w = csv.writer(self.out, lineterminator="\n")
        if out.stat().st_size == 0:
            self.w.writerow(["host_s", "line"])
        self.echo = echo
        self.lines: list[tuple[float, str]] = []
        self.lock = threading.Lock()
        self.stop = False
        self.t = threading.Thread(target=self._read, daemon=True)
        self.t.start()

    def _read(self):
        buf = b""
        while not self.stop:
            chunk = self.ser.read(256)
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("ascii", "replace").strip()
                if not line:
                    continue
                ts = time.time()
                with self.lock:
                    self.lines.append((ts, line))
                    self.w.writerow(["%.4f" % ts, line])
                    self.out.flush()
                if self.echo and not line.startswith("ST "):
                    print(line)

    def send(self, cmd: str):
        ts = time.time()
        self.ser.write((cmd + "\n").encode("ascii"))
        with self.lock:
            self.w.writerow(["%.4f" % ts, "> " + cmd])
            self.out.flush()

    def wait_for(self, prefixes: tuple[str, ...], timeout: float) -> str | None:
        """Wait until a line starting with one of the prefixes arrives after now."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lock:
                for ts, line in reversed(self.lines):
                    if ts < t0:
                        break
                    if line.startswith(prefixes):
                        return line
            time.sleep(0.005)
        return None

    def close(self):
        self.stop = True
        self.t.join(timeout=1)
        self.ser.close()
        self.out.close()


def seq_close(link: Link, n: int, hold_s: float, sp: float):
    link.send("STREAM 50")
    for i in range(n):
        print("trial %d of %d" % (i + 1, n))
        link.send("G %.1f" % sp)
        if link.wait_for(("EVT ENTER_HOLD", "EVT ENTER_FAULT", "EVT ENTER_RELEASE"), 5.0) is None:
            print("no HOLD within 5 s; stopping")
            return False
        time.sleep(hold_s)
        link.send("R")
        # RELEASE opens the jaw to the open stop; RETRACT times out to IDLE after 5 s
        # (TIMEOUT_RETRACT_MS), so every close starts from +20 deg in IDLE.
        if link.wait_for(("EVT ENTER_IDLE",), 8.0) is None:
            print("no IDLE after R; stopping")
            return False
        time.sleep(1.0)
    link.send("STREAM 0")
    return True


def seq_soak(link: Link, minutes: float, sp: float, watch=None):
    link.send("STREAM 2")
    t_end = time.time() + 60 * minutes
    k = 0
    while time.time() < t_end:
        if thermal_stop(link, watch, "soak cycle %d" % (k + 1)):
            break
        k += 1
        t0 = time.time()
        link.send("G %.1f" % sp)
        got = link.wait_for(("EVT ENTER_HOLD", "EVT ENTER_FAULT", "EVT ENTER_RELEASE"), 5.0)
        if got is None or "HOLD" not in got:
            print("cycle %d: no HOLD (%s); stopping" % (k, got))
            break
        time.sleep(DUTY["hold_s"])
        link.send("R")
        while time.time() - t0 < sum(DUTY.values()):
            time.sleep(0.05)
        print("cycle %d done, %.1f min left" % (k, (t_end - time.time()) / 60))
    link.send("STREAM 0")


def seq_cycle(link: Link, n: int, hold_s: float, sp: float, watch=None):
    for k in range(1, n + 1):
        if thermal_stop(link, watch, "cycle %d" % k):
            return k - 1
        link.send("G %.1f" % sp)
        got = link.wait_for(("EVT ENTER_HOLD", "EVT ENTER_FAULT", "EVT ENTER_RELEASE"), 5.0)
        if got is None or "FAULT" in got:
            print("cycle %d: %s; stopping" % (k, got))
            return k
        time.sleep(hold_s)
        link.send("R")
        if link.wait_for(("EVT ENTER_RETRACT",), 3.0) is None:
            print("cycle %d: no RETRACT; stopping" % k)
            return k
        link.send("A")  # RETRACT -> APPROACH -> ... ; R from APPROACH returns to IDLE at once
        link.send("R")
        link.wait_for(("EVT ENTER_IDLE",), 3.0)
        if k % 100 == 0:
            print("cycles done: %d" % k)
    return n


def seq_trip(link: Link, n: int, sp: float):
    link.send("STREAM 50")
    for i in range(n):
        input("trial %d of %d: Enter to close, then do the action in the procedure" % (i + 1, n))
        link.send("G %.1f" % sp)
        got = link.wait_for(("EVT ENTER_FAULT",), 30.0)
        print("result: %s" % got)
        input("Enter to clear (H) and re-home")
        link.send("H")
        link.wait_for(("EVT ENTER_IDLE",), 8.0)
    link.send("STREAM 0")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sequence", choices=["close", "hold", "soak", "cycle", "trip"])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--hold", type=float, default=1.0)
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--setpoint", type=float, default=5.0)
    ap.add_argument("--probe-port", help="probe board port: watch its thermocouples and stop on over-temperature")
    ap.add_argument("--probe-out", type=Path, help="CSV for the probe lines (required with --probe-port)")
    ap.add_argument("--stop-case-c", type=float, default=CASE_STOP_C)
    ap.add_argument("--stop-mount-c", type=float, default=MOUNT_STOP_C)
    a = ap.parse_args(argv)
    if a.sequence in ("cycle", "soak") and not a.probe_port:
        ap.error("--sequence %s needs --probe-port: it is never run without the thermal cutoff watching" % a.sequence)
    if a.probe_port and not a.probe_out:
        ap.error("--probe-port needs --probe-out")
    watch = TempWatch(a.probe_port, a.baud, a.probe_out, a.stop_case_c, a.stop_mount_c) if a.probe_port else None
    link = Link(a.port, a.baud, a.out, echo=a.sequence != "cycle")
    time.sleep(0.5)
    if a.sequence:
        # A sequence starts only from IDLE: G is ignored in BOOT, HOME and CALIBRATE.
        link.send("S")
        got = link.wait_for(("ST IDLE", "EVT ENTER_IDLE"), 15.0)
        if got is None:
            print("gripper not in IDLE after 15 s (send C or H by hand, then re-run); stopping")
            link.close()
            return
    try:
        if a.sequence == "close":
            seq_close(link, a.n, a.hold, a.setpoint)
        elif a.sequence == "hold":
            seq_close(link, a.n, a.hold, a.setpoint)
        elif a.sequence == "soak":
            seq_soak(link, a.minutes, a.setpoint, watch)
        elif a.sequence == "cycle":
            seq_cycle(link, a.n, a.hold, a.setpoint, watch)
        elif a.sequence == "trip":
            seq_trip(link, a.n, a.setpoint)
        else:
            print("interactive: type commands (G 5, R, H, C, S, STREAM 50, CALF 5.2 ...), Ctrl+C to stop")
            for line in sys.stdin:
                if line.strip():
                    link.send(line.strip())
    except KeyboardInterrupt:
        pass
    finally:
        link.close()
        if watch:
            watch.close()


if __name__ == "__main__":
    main()
