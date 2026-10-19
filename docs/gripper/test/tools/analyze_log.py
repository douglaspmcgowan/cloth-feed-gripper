"""Read a `gripper_log.py` CSV and print the numbers the procedures ask for.

    python docs/gripper/test/tools/analyze_log.py close TP-03_log.csv      # TP-03 close times
    python docs/gripper/test/tools/analyze_log.py faults TP-04_log.csv     # TP-04 / TP-05 fault timing
    python docs/gripper/test/tools/analyze_log.py probe TP-01_probe.csv --windows TP-01_log.csv  # hold min/mean per HOLD
    python docs/gripper/test/tools/analyze_log.py probe TP-01_probe.csv --windows TP-01_log.csv --attribute  # softest pair: judged hold by hold
    python docs/gripper/test/tools/analyze_log.py hold-current TP-07_log.csv   # TP-07 M7: mean rail A in HOLD, last 5 holds; F4 Ih= and drive regime
    python docs/gripper/test/tools/analyze_log.py judge --value 65.2 --limit 65 --u 0.049 --side upper  # any one limit

Every comparison with a limit ends in one of three words: PASS (clear of the limit by U), FAIL
(beyond it by U) or INDETERMINATE (within U: take more samples or use a better instrument).

Times come from the firmware's own millis() in the EVT and ST lines, so the USB latency
does not enter. Plain Python 3.9+, no extra packages.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
import sys
from pathlib import Path

# One-sided normal tolerance factors k(n), 95 % coverage, 90 % confidence, printed by
# docs/gripper/test/test_plan.py (exact, noncentral t). Kept here so this tool needs no scipy.
K_95_90 = {3: 5.311, 4: 3.957, 5: 3.400, 6: 3.092, 7: 2.894, 8: 2.754, 9: 2.650, 10: 2.568,
           11: 2.503, 12: 2.448, 15: 2.329, 20: 2.208, 22: 2.172, 25: 2.132, 30: 2.080}
FSR_LAG_S = 0.0105  # FSR EMA tau 9.5 ms + 1 ms poll (controls.md section 3) [D]
FAULT_GAP_CEILING_MS = 40  # two nominal 20 ms periods; larger gaps void timing evidence


# Expanded uncertainties U (k = 2) of the instruments, printed by test_plan.py [D]
# (MEASUREMENT-SIZING.md section 1). test_test_plan.py fails if these drift from the budgets.
U = {"contact_s": 0.0035590, "force_time_s": 0.0129099, "force_5N": 0.0964059, "force_8N": 0.1034216,
     "force_10N": 0.1094993, "current_A": 0.0207847, "fault_s": 0.0200000, "case_C": 1.6393596, "caliper_mm": 0.0489898, "rc_mm": 0.0765942}

PASS, FAIL, INDETERMINATE = "PASS", "FAIL", "INDETERMINATE"
WHAT_TO_DO = {
    PASS: "",
    FAIL: "",
    INDETERMINATE: ("INDETERMINATE: the value is within U of the limit. Take more samples if the spread (s) is large; "
                    "use a better instrument (smaller U) if the spread is small. Do not record a pass or a fail."),
}


def decide(value: float, limit: float, U_: float, side: str = "upper") -> str:
    """The one rule for every limit. side 'upper': the value must stay at or under the limit;
    'lower': at or over. PASS = clear of the limit by at least U; FAIL = beyond it by at least U;
    INDETERMINATE = within U (a value exactly on the limit is INDETERMINATE for any U > 0)."""
    margin = (limit - value) if side == "upper" else (value - limit)
    if U_ <= 0:  # an exact quantity such as a firmware constant
        return PASS if margin >= 0 else FAIL
    if margin >= U_:
        return PASS
    if margin <= -U_:
        return FAIL
    return INDETERMINATE


def combine(verdicts) -> str:
    """Several decisions behind one sign-off line: any FAIL fails, else any INDETERMINATE
    stays indeterminate, else PASS."""
    v = list(verdicts)
    if FAIL in v:
        return FAIL
    if INDETERMINATE in v or not v:
        return INDETERMINATE
    return PASS


def k_factor(n: int) -> float:
    if n in K_95_90:
        return K_95_90[n]
    keys = sorted(K_95_90)
    lo = max(k for k in keys if k <= n) if n >= keys[0] else keys[0]
    return K_95_90[lo]  # conservative: the factor for the next smaller tabulated n


def read_lines(path: Path):
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            yield float(row["host_s"]), row["line"]


EVT = re.compile(r"^EVT (\S+) (\d+)(?: (-?[0-9.]+))?")
ST = re.compile(r"^ST (\S+) (\d+) th=(-?[0-9.]+) F=(-?[0-9.]+) sp=(-?[0-9.]+) I=(-?[0-9.]+)")
IH = re.compile(r"\bIh=(-?[0-9.]+)")   # F4 hold current, back-off off; -1.00 until measured (gripper.ino status line)
REGIME_A = 0.75   # Ih above this: the servo drive conducts discontinuously (controls.md 4.3, thermal.md F4)


def parse(path: Path):
    events, status = [], []
    for host, line in read_lines(path):
        m = EVT.match(line)
        if m:
            events.append({"host": host, "name": m.group(1), "ms": int(m.group(2)),
                           "arg": float(m.group(3)) if m.group(3) else None})
            continue
        m = ST.match(line)
        if m:
            ih = IH.search(line)
            status.append({"host": host, "state": m.group(1), "ms": int(m.group(2)), "th": float(m.group(3)),
                           "F": float(m.group(4)), "sp": float(m.group(5)), "I": float(m.group(6)),
                           "Ih": float(ih.group(1)) if ih else None})
    return events, status


def crossing_ms(status, t0_ms, t1_ms, level):
    """First time the ST force crosses `level` between t0 and t1, linear interpolation."""
    prev = None
    for s in status:
        if s["ms"] < t0_ms or s["ms"] > t1_ms:
            continue
        if prev is not None and prev["F"] < level <= s["F"]:
            frac = (level - prev["F"]) / (s["F"] - prev["F"])
            return prev["ms"] + frac * (s["ms"] - prev["ms"])
        prev = s
    return None


def summarize(name, xs, limit=None, side="upper", U_=None):
    """One line per quantity. With a limit and U the line ends in PASS, FAIL or INDETERMINATE
    for the 95/90 tolerance bound against the limit (see decide)."""
    return summary(name, xs, limit, side, U_)[0]


def summary(name, xs, limit=None, side="upper", U_=None):
    """Returns (text line, verdict or None)."""
    xs = [x for x in xs if x is not None]
    if not xs:
        return "%-22s no data" % name, None
    n = len(xs)
    m = statistics.mean(xs)
    s = statistics.stdev(xs) if n > 1 else 0.0
    out = "%-22s n %2d  mean %.4f  sd %.4f  min %.4f  max %.4f" % (name, n, m, s, min(xs), max(xs))
    verdict = None
    if n >= 3:
        k = k_factor(n)
        bound = m + k * s if side == "upper" else m - k * s
        out += "  95/90 %s bound %.4f (k %.3f)" % ("upper" if side == "upper" else "lower", bound, k)
        if limit is not None:
            verdict = decide(bound, limit, U_ or 0.0, side)
            out += "  vs %.3f (U %.4f): %s" % (limit, U_ or 0.0, verdict)
            if verdict == INDETERMINATE:
                out += "\n    " + WHAT_TO_DO[INDETERMINATE]
    return out, verdict


def cmd_close(path: Path, slow_zone_deg: float = 6.0):
    events, status = parse(path)
    grips = [e for e in events if e["name"] == "CMD_GRIP"]
    rows = []
    for i, g in enumerate(grips):
        t0 = g["ms"]
        t_end = grips[i + 1]["ms"] if i + 1 < len(grips) else t0 + 5000
        nxt = lambda name: next((e["ms"] for e in events if e["name"] == name and t0 <= e["ms"] < t_end), None)
        contact = nxt("FSR_CONTACT")
        hold = nxt("ENTER_HOLD")
        f45 = crossing_ms(status, t0, t_end, 4.5)
        f50 = crossing_ms(status, t0, t_end, 5.0)
        # jaw command speed over the last 3 deg before contact, from the ST theta (command) trace
        speed = None
        if contact is not None:
            pts = [s for s in status if t0 <= s["ms"] <= contact]
            th_c = pts[-1]["th"] if pts else None
            win = [s for s in pts if th_c is not None and s["th"] <= th_c + 3.0]
            if len(win) >= 2 and win[-1]["ms"] > win[0]["ms"]:
                speed = (win[0]["th"] - win[-1]["th"]) / ((win[-1]["ms"] - win[0]["ms"]) / 1000.0)
        rows.append({"trial": i + 1, "t_contact_s": None if contact is None else (contact - t0) / 1000.0 - FSR_LAG_S,
                     "t_F4p5_s": None if f45 is None else (f45 - t0) / 1000.0 - FSR_LAG_S,
                     "t_F5_s": None if f50 is None else (f50 - t0) / 1000.0 - FSR_LAG_S,
                     "t_hold_s": None if hold is None else (hold - t0) / 1000.0,
                     "cmd_speed_last3_dps": speed})
    print("trial  contact_s  F4.5_s  F5.0_s  HOLD_s  cmd_speed_last3deg_dps   (FSR lag %.1f ms subtracted)" % (1000 * FSR_LAG_S))
    fmt = lambda x: "   -   " if x is None else "%7.3f" % x
    for r in rows:
        print("%5d  %s  %s  %s  %s  %s" % (r["trial"], fmt(r["t_contact_s"]), fmt(r["t_F4p5_s"]), fmt(r["t_F5_s"]),
                                          fmt(r["t_hold_s"]), fmt(r["cmd_speed_last3_dps"])))
    print(summarize("contact (R19 0.50 s)", [r["t_contact_s"] for r in rows], 0.50, "upper", U["contact_s"]))
    print(summarize("4.5 N (R19 0.75 s)", [r["t_F4p5_s"] for r in rows], 0.75, "upper", U["force_time_s"]))
    print(summarize("5.0 N (R19 0.75 s)", [r["t_F5_s"] for r in rows], 0.75, "upper", U["force_time_s"]))
    print(summarize("HOLD entry", [r["t_hold_s"] for r in rows]))
    return rows


def cmd_faults(path: Path):
    events, status = parse(path)
    rows = []
    for e in events:
        if e["name"].startswith("FAULT_") or e["name"] in ("FSR_OVER", "ENTER_FAULT"):
            rows.append(e)
    print("ms        event               arg")
    for e in rows:
        print("%-9d %-19s %s" % (e["ms"], e["name"], "" if e["arg"] is None else e["arg"]))
    # Over-current: onset = first ST line of the run of I above the trip before each FAULT_OVERCURRENT event;
    # back-off begin = first ST line after the event whose command angle opens. The trip is 2.0 A while the
    # force loop runs (after FSR_CONTACT, in HOLD and FEED: config.h STALL_CURRENT_HOLD_A) and 1.8 A in every
    # other state (STALL_CURRENT_A).
    out = []
    voided = False
    last_ms = None
    for e in events:
        if e["name"] != "FAULT_OVERCURRENT":
            continue
        # Each trip logs FAULT_OVERCURRENT twice (the event, then the fault code on FAULT
        # entry, same pass): count one trip per 50 ms.
        if last_ms is not None and e["ms"] - last_ms < 50:
            continue
        last_ms = e["ms"]
        before = [s for s in status if s["ms"] <= e["ms"]]
        marks = [x["name"] for x in events if x["ms"] <= e["ms"] and (x["name"].startswith("ENTER_") or x["name"] == "FSR_CONTACT")
                 and x is not e]
        trip_a = 2.0 if marks and marks[-1] in ("FSR_CONTACT", "ENTER_HOLD", "ENTER_FEED") else 1.8
        onset = None
        for s in reversed(before):
            if s["I"] > trip_a:
                onset = s["ms"]
            else:
                break
        after = [s for s in status if s["ms"] > e["ms"]]
        th0 = before[-1]["th"] if before else None
        begin = next((s["ms"] for s in after if th0 is not None and s["th"] > th0 + 0.5), None)
        out.append((onset, e["ms"], begin))
        gap = None if (onset is None or begin is None) else begin - onset
        window = [s for s in status if onset is not None and begin is not None
                  and onset - 20 <= s["ms"] <= begin + 20]
        gaps = [b["ms"] - a["ms"] for a, b in zip(window, window[1:])]
        largest = max(gaps, default=None)
        onset_i = next((i for i, s in enumerate(status) if s["ms"] == onset), None)
        begin_i = next((i for i, s in enumerate(status) if s["ms"] == begin), None)
        brackets = []
        for i in (onset_i, begin_i):
            if i is not None and i > 0:
                brackets.append(status[i]["ms"] - status[i - 1]["ms"])
        run_u_ms = max(brackets, default=None)
        bad_stream = run_u_ms is None or run_u_ms > FAULT_GAP_CEILING_MS
        if bad_stream:
            verdict = INDETERMINATE
            voided = True
        else:
            verdict = "no data" if gap is None else decide(gap, 200.0, run_u_ms, "upper")
        print("over-current (trip %.1f A) onset %s ms, FAULT_OVERCURRENT %d ms, back-off begins %s ms: onset to back-off %s ms "
              "(R20 limit 200 ms, observed U %s ms; largest status gap %s ms; ceiling %d ms): %s%s" %
              (trip_a, onset, e["ms"], begin, gap, run_u_ms, largest, FAULT_GAP_CEILING_MS, verdict,
               " — VOID: repeat run" if bad_stream else ""))
    peaks = [s["F"] for s in status]
    if peaks:
        print("highest FSR force in the log: %.2f N" % max(peaks))
    return rows, out, voided


def cmd_probe(path: Path, windows: Path | None, skip_s: float = 0.5, attribute: bool = False):
    """Probe CSV lines are `t_ms,force_N[,temp_C]` (probe.ino). With --windows, report each
    HOLD window of the gripper log (host time) from HOLD + skip_s to the next CMD_RELEASE.
    attribute=True (TP-01 softest finger pair): the R14 verdict is the zero-failure run of the
    per-hold minimums; the 95/90 bound is printed but not judged (MEASUREMENT-SIZING.md section 3)."""
    samples = []
    for host, line in read_lines(path):
        parts = line.split(",")
        try:
            samples.append((host, float(parts[1])))
        except (IndexError, ValueError):
            continue
    if not samples:
        print("no probe samples")
        return []
    if windows is None:
        fs = [f for _, f in samples]
        print("probe: n %d  mean %.3f  min %.3f  max %.3f N" % (len(fs), statistics.mean(fs), min(fs), max(fs)))
        return []
    events, _ = parse(windows)
    holds = [e for e in events if e["name"] == "ENTER_HOLD"]
    rels = [e for e in events if e["name"] in ("CMD_RELEASE", "ENTER_RELEASE", "ENTER_FAULT")]
    res = []
    for h in holds:
        r = next((x for x in rels if x["host"] > h["host"]), None)
        if r is None:
            continue
        w = [f for t, f in samples if h["host"] + skip_s <= t <= r["host"]]
        if w:
            res.append({"hold_s": r["host"] - h["host"], "mean": statistics.mean(w), "min": min(w), "max": max(w)})
    for i, r in enumerate(res, 1):
        print("hold %d: %.1f s  mean %.3f  min %.3f  max %.3f N" % (i, r["hold_s"], r["mean"], r["min"], r["max"]))
    for i, r in enumerate(res, 1):
        r["verdict"] = decide(r["min"], 5.0, U["force_5N"], "lower")
        print("hold %d minimum %.3f N vs 5.0 N (U %.3f): %s" % (i, r["min"], U["force_5N"], r["verdict"]))
    line, bound_verdict = summary("hold minimum (R14 5 N)", [r["min"] for r in res], 5.0, "lower", U["force_5N"])
    print(line)
    if res and attribute:
        print("R14 hold part: %s  (zero-failure run: every hold minimum must PASS; the bound is reported, not judged)"
              % combine([r["verdict"] for r in res]))
    elif res:
        print("R14 hold part: %s  (every hold minimum and the 95/90 lower bound must each PASS; any FAIL fails)"
              % combine([r["verdict"] for r in res] + [bound_verdict or INDETERMINATE]))
    return res


def cmd_hold_current(path: Path, last: int = 5, skip_s: float = 1.0):
    """M7: mean rail current (`I=` in the ST lines) in HOLD, from ENTER_HOLD + skip_s to the
    release, over the last `last` holds of the log (TP-07 step: hold current)."""
    events, status = parse(path)
    holds = [e for e in events if e["name"] == "ENTER_HOLD"]
    ends = [e for e in events if e["name"] in ("CMD_RELEASE", "ENTER_RELEASE", "ENTER_FAULT")]
    means = []
    for h in holds[-last:]:
        e = next((x for x in ends if x["ms"] > h["ms"]), None)
        if e is None:
            continue
        w = [s["I"] for s in status if h["ms"] + skip_s * 1000 <= s["ms"] <= e["ms"]]
        if w:
            means.append(statistics.mean(w))
    if means:
        print("hold current: %d holds, mean %.3f A, min %.3f, max %.3f (rail A from the INA219, U %.3f A)" %
              (len(means), statistics.mean(means), min(means), max(means), U["current_A"]))
    else:
        print("no complete HOLD with status lines in the log (use STREAM 2 or faster)")
    hold_ih(events, status, holds[-last:], ends)
    return means


def hold_ih(events, status, holds, ends):
    """F4 (TP-07): the firmware's own hold-current reading per hold, `EVT HOLD_I <ms> <A>` or else the `Ih=` field of
    the last status line of the hold, and the drive regime it gives (over 0.75 A: discontinuous conduction)."""
    vals = []
    for h in holds:
        e = next((x for x in ends if x["ms"] > h["ms"]), None)
        t1 = e["ms"] if e else float("inf")
        ev = next((x["arg"] for x in events if x["name"] == "HOLD_I" and h["ms"] <= x["ms"] <= t1 and x["arg"] is not None), None)
        st = [s["Ih"] for s in status if h["ms"] <= s["ms"] <= t1 and s.get("Ih") is not None and s["Ih"] >= 0]
        v = ev if ev is not None else (st[-1] if st else None)
        if v is not None:
            vals.append(v)
    if not vals:
        print("Ih: no F4 reading in these holds (EVT HOLD_I or Ih= >= 0; needs BACKOFF 0 and 0.3 s of HOLD)")
        return None, None
    m = statistics.mean(vals)
    v = decide(m, REGIME_A, U["current_A"], "upper")
    regime = {PASS: "continuous conduction", FAIL: "discontinuous conduction", INDETERMINATE: INDETERMINATE}[v]
    print("Ih (F4, back-off off): %d holds, mean %.3f A, min %.3f, max %.3f; vs %.2f A (U %.3f A): %s" %
          (len(vals), m, min(vals), max(vals), REGIME_A, U["current_A"], regime))
    return m, regime


def cmd_judge(value: float, limit: float, U_: float, side: str):
    """Any single comparison: print PASS, FAIL or INDETERMINATE and what to do."""
    v = decide(value, limit, U_, side)
    print("value %g, limit %g (%s), U %g: %s" % (value, limit, side, U_, v))
    if WHAT_TO_DO[v]:
        print(WHAT_TO_DO[v])
    return v


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["close", "faults", "probe", "judge", "hold-current"])
    ap.add_argument("log", nargs="?", type=Path, help="log file (not used by judge)")
    ap.add_argument("--value", type=float, help="judge: the measured value")
    ap.add_argument("--limit", type=float, help="judge: the requirement's limit")
    ap.add_argument("--u", type=float, help="judge: expanded uncertainty U (k = 2), same unit as the value")
    ap.add_argument("--side", choices=["upper", "lower"], default="upper",
                    help="judge: upper = value must stay at or under the limit; lower = at or over")
    ap.add_argument("--windows", type=Path, help="gripper log that marks the HOLD windows (probe mode)")
    ap.add_argument("--attribute", action="store_true",
                    help="probe: judge the holds as a zero-failure run on their minimums (TP-01 softest finger pair)")
    a = ap.parse_args(argv)
    if a.what == "judge":
        if a.value is None or a.limit is None or a.u is None:
            ap.error("judge needs --value, --limit and --u")
        cmd_judge(a.value, a.limit, a.u, a.side)
        return
    if a.log is None:
        ap.error("%s needs a log file" % a.what)
    if a.what == "hold-current":
        cmd_hold_current(a.log)
    elif a.what == "close":
        cmd_close(a.log)
    elif a.what == "faults":
        _, _, voided = cmd_faults(a.log)
        return 2 if voided else 0
    else:
        cmd_probe(a.log, a.windows, attribute=a.attribute)


if __name__ == "__main__":
    raise SystemExit(main())
