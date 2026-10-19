"""Monte Carlo of closed-loop grips through the compiled firmware core (loop.py) across the plant.py ranges.

Run from the repository root (about 2 min on 4 cores):
    python analysis/gripper/controls/montecarlo.py            # N = 2000, seed 20261011
    python analysis/gripper/controls/montecarlo.py --n 200    # quick look
Writes results/montecarlo.json (summary + every run's parameters and metrics) and results/montecarlo_stdout.txt,
and results/worst_cases.json (the named worst draws that test_regression.py replays).

Requirements are scored at both values of each open one (controls.md section 0):
  R14 hold >= 5.0 N, through the hold including the compressed 25.5 s FSR creep [DB R14]
  R15 peak pad force <= 10 N as written, and <= 8.0 N as proposed (fold 8.4-8.9 N, finger.md); fold itself
  R19 time to 90 % of the setpoint (4.5 N) <= 0.5 s as written, and to the setpoint (5 N) <= 0.75 s as proposed;
      the contact time against 0.5 s is reported too.
"""
import argparse
import json
import math
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import loop  # noqa: E402
import plant as P  # noqa: E402

SEED = 20261011
N_DEFAULT = 2000
RES = HERE / "results"
SP = 5.0


FIX = {}
RANGE = {}
EARLY = False   # draw early_contact_deg over its range (a fold, seam stack or object); otherwise it is 0
_CTX_KEY = None


def context():
    """Everything a worker needs, passed with each task so the runs are the same under fork (Linux) and spawn
    (Windows), where module globals set in the parent are not inherited."""
    return {"ovr": loop._OVR, "range": dict(RANGE), "fix": dict(FIX), "early": EARLY, "sp": SP}


def _apply(ctx):
    global RANGE, FIX, EARLY, SP, _CTX_KEY
    key = repr(sorted((k, repr(v)) for k, v in ctx.items()))
    if key == _CTX_KEY:
        return
    RANGE, FIX, EARLY, SP = dict(ctx["range"]), dict(ctx["fix"]), ctx["early"], ctx["sp"]
    if ctx["ovr"] != loop._OVR:
        loop.configure(ctx["ovr"])
    _CTX_KEY = key


def draw(seed, i):
    rng = random.Random(seed * 1_000_003 + i)
    p = P.sample(rng)
    if not EARLY:
        p["early_contact_deg"] = 0.0
    for k, (lo, hi) in RANGE.items():     # a narrowed range (a bench measurement), same uniform position
        nlo, nhi = P.PARAMS[k][1], P.PARAMS[k][2]
        x = (p[k] - nlo) / (nhi - nlo) if nhi > nlo else 0.5
        p[k] = lo + x * (hi - lo)
    p.update(FIX)
    return p


def one(args):
    seed, i = args[:2]
    if len(args) > 2:
        _apply(args[2])
    p = draw(seed, i)
    m = loop.grip(p, seed=seed * 7 + i, sp=SP)
    m.pop("states", None)
    return {"i": i, "p": p, "m": m}


def score(m):
    """Pass/fail flags per requirement reading; None when the run never got that far."""
    ok_grip = m.get("booted") and m.get("final_state") in ("HOLD", "FEED")
    t90, tsp, tc = m.get("t_90_s"), m.get("t_sp_s"), m.get("t_contact_s")
    hold_min = m.get("F_hold_min_N")
    peak = m.get("F_peak_N", 0.0)
    return {
        "grip_ok": bool(ok_grip),
        "R14": bool(ok_grip and hold_min is not None and hold_min >= 5.0),
        "R15_10N": bool(m.get("booted") and peak <= 10.0 and not m.get("folded")),
        "R15_8N": bool(m.get("booted") and peak <= 8.0 and not m.get("folded")),
        "R19_0.5s_F90": bool(t90 is not None and t90 <= 0.5),
        "R19_0.75s_F5": bool(tsp is not None and tsp <= 0.75),
        "R19_0.75s_F90": bool(t90 is not None and t90 <= 0.75),
        "R19_contact_0.5s": bool(tc is not None and tc <= 0.5),
        "fold": bool(m.get("folded")),
        "peak_le_8N": bool(m.get("booted") and peak <= 8.0),
        "peak_le_10N": bool(m.get("booted") and peak <= 10.0),
        "fault": m.get("final_state") == "FAULT",
    }


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def summarise(runs):
    n = len(runs)
    flags = [score(r["m"]) for r in runs]
    probs = {}
    for key in flags[0]:
        k = sum(1 for f in flags if f[key])
        lo, hi = wilson(k, n)
        probs[key] = {"count": k, "p": k / n, "ci95": [lo, hi]}
    ms = [r["m"] for r in runs]
    dist = {}
    for key in ("t_contact_s", "t_90_s", "t_sp_s", "t_hold_s", "F_peak_N", "F_hold_min_N", "F_end_N", "sse_N",
                "v_touch3_dps", "c0_deg"):
        vals = [m.get(key) for m in ms]
        have = [v for v in vals if v is not None]
        dist[key] = {"n": len(have), "missing": n - len(have), "p01": pct(have, 0.01), "p05": pct(have, 0.05),
                     "p50": pct(have, 0.5), "p95": pct(have, 0.95), "p99": pct(have, 0.99),
                     "max": max(have) if have else None, "min": min(have) if have else None}
    c0err = [m["c0_deg"] - m["c0_true_deg"] for m in ms if m.get("calibrated")]
    dist["c0_err_deg"] = {"p01": pct(c0err, 0.01), "p50": pct(c0err, 0.5), "p99": pct(c0err, 0.99)}
    states = {}
    for m in ms:
        states[m.get("final_state")] = states.get(m.get("final_state"), 0) + 1
    fault_codes = {}
    for m in ms:
        for f in m.get("faults", []) + m.get("warns", []):
            fault_codes[f] = fault_codes.get(f, 0) + 1
    return {"n": n, "prob": probs, "dist": dist, "final_states": states, "event_counts": fault_codes,
            "fault_rate": {k: v / n for k, v in fault_codes.items()}}


def sensitivity(runs, metric, keys=None):
    """Spearman rank correlation of each parameter with a metric: which ranges drive the tails."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for j, i in enumerate(order):
            r[i] = j
        return r
    rows = [(r["p"], r["m"].get(metric)) for r in runs if r["m"].get(metric) is not None]
    if len(rows) < 10:
        return {}
    y = ranks([m for _, m in rows])
    out = {}
    for k in keys or P.PARAMS:
        x = [p[k] for p, _ in rows]
        if max(x) == min(x):
            continue
        xr = ranks(x)
        mx, my = sum(xr) / len(xr), sum(y) / len(y)
        cov = sum((a - mx) * (b - my) for a, b in zip(xr, y))
        sx = math.sqrt(sum((a - mx) ** 2 for a in xr))
        sy = math.sqrt(sum((b - my) ** 2 for b in y))
        out[k] = cov / (sx * sy)
    return dict(sorted(out.items(), key=lambda kv: -abs(kv[1]))[:6])


def worst(runs):
    """Named worst draws, replayed as regression tests."""
    ok = [r for r in runs if r["m"].get("booted")]
    pick = {}
    pick["peak_force"] = max(ok, key=lambda r: r["m"]["F_peak_N"])
    slow = [r for r in ok if r["m"].get("t_90_s") is not None]
    pick["slowest_to_90pct"] = max(slow, key=lambda r: r["m"]["t_90_s"])
    held = [r for r in ok if r["m"].get("F_hold_min_N") is not None]
    pick["lowest_hold"] = min(held, key=lambda r: r["m"]["F_hold_min_N"])
    fast = [r for r in ok if r["m"].get("v_touch3_dps") is not None]
    pick["fastest_jaw_at_touch_plus_3"] = max(fast, key=lambda r: r["m"]["v_touch3_dps"])
    failed = [r for r in runs if not score(r["m"])["grip_ok"]]
    if failed:
        pick["first_failed_grip"] = failed[0]
    return {k: {"i": v["i"], "p": v["p"], "m": {kk: vv for kk, vv in v["m"].items() if kk != "series"}}
            for k, v in pick.items()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_DEFAULT)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--tag", default="")
    ap.add_argument("--set", default="", help='firmware variant, e.g. "JAW_BRAKE_DEG=4,F_HOLD_BIAS_N=0.4"')
    ap.add_argument("--fix", default="", help='plant parameters held fixed, e.g. "k_tip_n_per_mm=1.1"')
    ap.add_argument("--range", default="", help='plant ranges replaced, e.g. "span_mount=0.97:1.03"')
    ap.add_argument("--sp", type=float, default=5.0, help="grip setpoint G <N>")
    ap.add_argument("--early", action="store_true", help="draw early contact 0-10 deg (plant.py early_contact_deg)")
    a = ap.parse_args(argv)
    ovr = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in a.set.split(",") if kv}
    global FIX, RANGE, EARLY, SP
    SP, EARLY = a.sp, a.early
    FIX = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in a.fix.split(",") if kv}
    for kv in (x for x in a.range.split(",") if x):
        name, lohi = kv.split("=")
        RANGE[name] = tuple(float(v) for v in lohi.split(":"))
    loop.configure(ovr)
    loop.lib()      # build once before forking
    t0 = time.time()
    with Pool(a.jobs) as pool:
        runs = pool.map(one, [(a.seed, i, context()) for i in range(a.n)], chunksize=20)
    s = summarise(runs)
    s["seed"] = a.seed
    elapsed = round(time.time() - t0, 1)   # printed only: run-dependent fields stay out of committed files
    s["firmware_overrides"], s["plant_fixed"], s["plant_ranges"] = ovr, FIX, RANGE
    s["setpoint_N"], s["early_contact_drawn"] = SP, EARLY
    s["sensitivity"] = {m: sensitivity(runs, m) for m in ("F_peak_N", "t_90_s", "F_hold_min_N")}
    s["params"] = {k: {"nominal": v[0], "lo": v[1], "hi": v[2], "tag": v[3], "why": v[4]} for k, v in P.PARAMS.items()}
    RES.mkdir(exist_ok=True)
    suffix = ("_" + a.tag) if a.tag else ""
    slim = [{"i": r["i"], "m": r["m"]} for r in runs]   # parameters regenerate from (seed, i): draw()
    (RES / f"montecarlo{suffix}.json").write_text(json.dumps({"summary": s, "runs": slim}, default=float),
                                                  encoding="utf-8", newline="\n")
    w = worst(runs)
    if not a.tag:
        (RES / "worst_cases.json").write_text(json.dumps(w, indent=1, default=float), encoding="utf-8", newline="\n")
    lines = [f"Monte Carlo n={s['n']} seed={s['seed']}"]
    for k, v in s["prob"].items():
        lines.append(f"  P({k:18s}) = {v['p']:.4f}  ({v['count']}/{s['n']}, 95 % CI {v['ci95'][0]:.4f}-{v['ci95'][1]:.4f})")
    for k, d in s["dist"].items():
        lines.append((f"  {k:14s} " + "  ".join(f"{q} {d[q]:.3f}" for q in d if isinstance(d.get(q), float))).rstrip())
    lines.append(f"  final states {s['final_states']}")
    lines.append(f"  event counts {s['event_counts']}")
    for m, d in s["sensitivity"].items():
        lines.append(f"  drivers of {m}: " + ", ".join(f"{k} {v:+.2f}" for k, v in d.items()))
    for k, v in w.items():
        lines.append(f"  worst {k}: run {v['i']}  peak {v['m'].get('F_peak_N', 0):.2f} N  t90 {v['m'].get('t_90_s')}"
                     f"  hold_min {v['m'].get('F_hold_min_N')}  state {v['m'].get('final_state')}")
    text = "\n".join(lines)
    print(text)
    print(f"  ({elapsed} s)")
    (RES / f"montecarlo{suffix}_stdout.txt").write_text(text + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
