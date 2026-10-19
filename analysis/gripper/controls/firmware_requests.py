"""The tolerance study's firmware requests (docs/gripper/analysis/tolerance_stacks.md, *Requests outside CAD*) and the
proposed 8 N force cap, each run through the compiled firmware before it is applied or declined
(controls.md section 6.4). Request 3 (the relative jaw floor) is applied in config.h, so "shipped" includes it and
"absfloor" is the firmware before it. Run from the repository root (about 9 min on 4 cores, measured):
    python analysis/gripper/controls/firmware_requests.py
Writes results/firmware_requests.json and results/firmware_requests_stdout.txt, and the table between the
<!-- requests:begin/end --> markers in docs/gripper/analysis/controls.md section 6.4.

Every variant is a set of config.h values on top of the committed file, compared on the same draws:
  window   the W2b-1 linear plant (firmware_sim/sim.py) across the R12 stiffness window 0.88-1.63 N/mm, G 5:
           peak, hold, contact and hold times, and any FSR_OVER trip (a trip here is a false trip: nothing is wrong)
  mc       N_MC grips of the drawn plant (montecarlo.py), no early contact, G 5: R14, R19, R15, false trips
  g7       N_SIDE grips at G 7, the largest setpoint the parser accepts: false trips at the top of the hold band
  early    N_SIDE grips with early contact 0-10 deg drawn (a fold or an object): peaks, trips
  faults   linear plant, k 1.63: FSR reading 50 % (trip blind; the squeeze cap and the floor bound the force) and the
           early-contact bound at 6 / 8 / 10 deg
A "false trip" is an FSR_OVER in a grip with no fault injected and no early contact."""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_sweep as dsw  # noqa: E402
import montecarlo as mc  # noqa: E402
sys.path.insert(0, str(HERE.parent / "firmware_sim"))
import build  # noqa: E402
import fwconfig  # noqa: E402
import sim  # noqa: E402

N_MC = 1000
N_SIDE = 300
K_WINDOW = [0.88] + [round(float(k), 2) for k in np.arange(0.90, 1.631, 0.05)] + [1.63]
ABSFLOOR = {"JAW_FLOOR_BELOW_C0_DEG": 0, "JAW_MIN_DEG": -7.4}   # the floor before request 3: absolute -7.4 deg
VARIANTS = [   # (id, label, config.h overrides)
    ("shipped", "shipped (trip 7.75 N / 20 ms, slow zone 6 deg, floor theta_c0 - 4.9 deg: request 3 at the 8 N cap)", {}),
    ("absfloor", "before request 3: absolute floor JAW_MIN_DEG -7.4", ABSFLOOR),
    ("floor62", "round 2 floor theta_c0 - 6.2 deg (10 N basis)", {"JAW_FLOOR_BELOW_C0_DEG": 6.2}),
    ("floor50", "floor theta_c0 - 5.0 deg", {"JAW_FLOOR_BELOW_C0_DEG": 5.0}),
    ("trip7_10", "request 1: F_TRIP_N 7.0, F_TRIP_MS 10", {"F_TRIP_N": 7.0, "F_TRIP_MS": 10}),
    ("trip7_20", "trip 7.0 N, 20 ms", {"F_TRIP_N": 7.0}),
    ("trip75_10", "trip 7.5 N, 10 ms", {"F_TRIP_N": 7.5, "F_TRIP_MS": 10}),
    ("trip8_10", "trip 7.75 N, 10 ms", {"F_TRIP_MS": 10}),
    ("trip6_10", "trip 6.0 N, 10 ms", {"F_TRIP_N": 6.0, "F_TRIP_MS": 10}),
    ("trip55_10", "trip 5.5 N, 10 ms (T09P-trip55)", {"F_TRIP_N": 5.5, "F_TRIP_MS": 10}),
    ("slow3", "request 2: JAW_SLOW_ZONE_DEG 3", {"JAW_SLOW_ZONE_DEG": 3}),
    ("slow4", "slow zone 4 deg", {"JAW_SLOW_ZONE_DEG": 4}),
    ("slow5", "slow zone 5 deg", {"JAW_SLOW_ZONE_DEG": 5}),
    ("cap8", "R15 proposed: F_CAP_N 8 (squeeze cap sized for 8 - 0.5 margin)", {"F_CAP_N": 8.0}),
]


def tripped(m):
    return "FSR_OVER" in (m.get("faults") or [])


def window(lib):
    rows = []
    for k in K_WINDOW:
        m = sim.metrics(sim.grip(lib, k))
        rows.append({"k": k, "F_max_N": m["F_max_N"], "F_hold_mean_N": m["F_hold_mean_N"],
                     "t_contact_s": m["t_contact_s"], "t_hold_s": m["t_hold_s"], "final_state": m["final_state"],
                     "v3_dps": m["v_jaw_at_touch_plus_3_dps"], "trip": "FSR_OVER" in m["faults"]})
    return rows


def fault_cases(lib):
    out = {}
    for lab, kw in (("fsr_50pct_k1.63", {"span": 0.5}), ("fsr_150pct_k1.0", {"span": 1.5})):
        k = 1.63 if "1.63" in lab else 1.0
        m = sim.metrics(sim.grip(lib, k, **kw))
        out[lab] = {"F_max_N": m["F_max_N"], "F_hold_mean_N": m["F_hold_mean_N"], "final_state": m["final_state"]}
    for d in (6.0, 8.0, 10.0):
        m = sim.metrics(sim.grip(lib, 1.63, touch=sim.TH_TOUCH_NOCLOTH + d))
        out[f"early_{d:.0f}deg_k1.63"] = {"F_max_N": m["F_max_N"], "final_state": m["final_state"]}
    return out


def mc_block(ovr, n, **kw):
    s = dsw.run_variant(ovr, n=n, keep_runs=True, **kw)
    runs = s.pop("runs")
    ms = [r["m"] for r in runs]
    trips = [m for m in ms if tripped(m)]
    return {
        "n": n, "grip_ok": s["prob"]["grip_ok"]["p"], "R14": s["prob"]["R14"]["p"],
        "R19_0.75s_F5": s["prob"]["R19_0.75s_F5"]["p"], "R19_0.5s_F90": s["prob"]["R19_0.5s_F90"]["p"],
        "R19_contact_0.5s": s["prob"]["R19_contact_0.5s"]["p"], "P_v3_le_20": s["P_v3_le_20"],
        "R15_10N": s["prob"]["R15_10N"]["p"], "R15_8N": s["prob"]["R15_8N"]["p"],
        "peak_max_N": s["dist"]["F_peak_N"]["max"], "peak_p99_N": s["dist"]["F_peak_N"]["p99"],
        "hold_min_p05_N": s["dist"]["F_hold_min_N"]["p05"], "hold_min_p50_N": s["dist"]["F_hold_min_N"]["p50"],
        "t_contact_p50_s": s["dist"]["t_contact_s"]["p50"], "t_contact_max_s": s["dist"]["t_contact_s"]["max"],
        "t_sp_p50_s": s["dist"]["t_sp_s"]["p50"], "v3_max_dps": s["dist"]["v_touch3_dps"]["max"],
        "trips": len(trips), "trips_true_peak_le_8N": sum(1 for m in trips if m["F_peak_N"] <= 8.0),
        "folds": sum(1 for m in ms if m.get("folded")), "final_states": s["final_states"],
    }


def run(ovr):
    lib = build.load(ovr or None)
    for i in range(64):
        name = lib.sim_event_name(i).decode()
        if name == "?":
            break
        sim.EV[name] = i
    cfg = dict(fwconfig.load())
    cfg.update(ovr)
    return {"u_max_deg": float(lib.sim_u_max()), "u_max_formula_deg": fwconfig.derived(cfg)["CTRL_U_MAX_DEG"],
            "window": window(lib), "faults": fault_cases(lib),
            "mc": mc_block(ovr, N_MC), "g7": mc_block(ovr, N_SIDE, sp=7.0), "early": mc_block(ovr, N_SIDE, early=True)}


def line(vid, r):
    w = r["window"]
    wpk = max(x["F_max_N"] for x in w)
    whold = [x["F_hold_mean_N"] for x in w]
    wtc = [x["t_contact_s"] for x in w if x["t_contact_s"] is not None]
    wth = [x["t_hold_s"] for x in w if x["t_hold_s"] is not None]
    a, g, e, f = r["mc"], r["g7"], r["early"], r["faults"]
    return (f"{vid:10s} u_max {r['u_max_deg']:.3f} | window k 0.88-1.63: peak max {wpk:.2f} N, hold {min(whold):.2f}-{max(whold):.2f} N,"
            f" contact {min(wtc):.3f}-{max(wtc):.3f} s, HOLD by {max(wth):.3f} s, v@+3 max {max(x['v3_dps'] or 0 for x in w):.0f} deg/s,"
            f" false trips {sum(x['trip'] for x in w)}/{len(w)}, states {sorted({x['final_state'] for x in w})}"
            f" | mc n={a['n']}: R14 {a['R14']:.3f} R19 5N<=0.75 {a['R19_0.75s_F5']:.3f} contact<=0.5 {a['R19_contact_0.5s']:.3f}"
            f" 4.5N<=0.5 {a['R19_0.5s_F90']:.3f} last3<=20 {a['P_v3_le_20']:.2f} peak max {a['peak_max_N']:.2f}"
            f" R15<=8 {a['R15_8N']:.3f} grip_ok {a['grip_ok']:.3f} false trips {a['trips']} (true peak<=8 N: {a['trips_true_peak_le_8N']})"
            f" hold min p05/p50 {a['hold_min_p05_N']:.2f}/{a['hold_min_p50_N']:.2f}"
            f" | G 7 n={g['n']}: false trips {g['trips']} grip_ok {g['grip_ok']:.3f} peak max {g['peak_max_N']:.2f}"
            f" | early n={e['n']}: P(<=8N) {e['R15_8N']:.3f} P(<=10N) {e['R15_10N']:.3f} max {e['peak_max_N']:.2f} trips {e['trips']} folds {e['folds']}"
            f" | linear k 1.63: FSR 50 % {f['fsr_50pct_k1.63']['F_max_N']:.2f} N {f['fsr_50pct_k1.63']['final_state']},"
            f" FSR 150 % k 1.0 hold {f['fsr_150pct_k1.0']['F_hold_mean_N']:.2f} N {f['fsr_150pct_k1.0']['final_state']},"
            f" early 6/8/10 deg " + " / ".join(f"{f[f'early_{d}deg_k1.63']['F_max_N']:.2f} {f[f'early_{d}deg_k1.63']['final_state']}"
                                             for d in (6, 8, 10)))


def md_table(rows):
    """The controls.md section 6.4 table (between <!-- requests:begin --> and <!-- requests:end -->)."""
    out = ["| Variant | Window: false trips of 17, peak max (N), contact (s), jaw speed at touch + 3° max (°/s) | Drawn: R14 "
           "| R19 5 N ≤ 0.75 s | Contact ≤ 0.5 s | 4.5 N ≤ 0.5 s | Last 3° ≤ 20 °/s | False trips of 1,000 "
           "| G 7: false trips of 300 | Early 0–10°: max (N), P(≤ 8 N) | Linear bound k 1.63: early 6 / 8 / 10° (N); FSR 50 % (N) |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        w, a, g, e, f = r["window"], r["mc"], r["g7"], r["early"], r["faults"]
        tc = [x["t_contact_s"] for x in w]
        lb = " / ".join("%.2f%s" % (f[f"early_{d}deg_k1.63"]["F_max_N"], "*" if f[f"early_{d}deg_k1.63"]["final_state"] == "FAULT" else "")
                        for d in (6, 8, 10))
        out.append("| %s | %d, %.2f, %.3f–%.3f, %.0f | %.1f %% | %.1f %% | %.1f %% | %.1f %% | %.1f %% | %d | %d | %.2f, %.1f %% | %s; %.2f |" % (
            r["label"], sum(x["trip"] for x in w), max(x["F_max_N"] for x in w), min(tc), max(tc),
            max(x["v3_dps"] or 0 for x in w), 100 * a["R14"], 100 * a["R19_0.75s_F5"], 100 * a["R19_contact_0.5s"],
            100 * a["R19_0.5s_F90"], 100 * a["P_v3_le_20"], a["trips"], g["trips"], e["peak_max_N"], 100 * e["R15_8N"], lb,
            f["fsr_50pct_k1.63"]["F_max_N"]))
    return "\n".join(out)


def replace_block(path, name, body):
    text = path.read_text(encoding="utf-8")
    a, b = f"<!-- {name}:begin -->", f"<!-- {name}:end -->"
    i, j = text.index(a) + len(a), text.index(b)
    path.write_text(text[:i] + "\n" + body + "\n" + text[j:], encoding="utf-8", newline="\n")


def main():
    rows, lines = [], [f"firmware requests, seed {mc.SEED}; mc n={N_MC}, G 7 and early n={N_SIDE}"]
    for vid, label, ovr in VARIANTS:
        r = run(ovr)
        rows.append({"id": vid, "label": label, "overrides": ovr, **r})
        lines.append(line(vid, r))
        print(lines[-1], flush=True)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results/firmware_requests.json").write_text(json.dumps(rows, indent=1, default=float), encoding="utf-8",
                                                         newline="\n")
    (HERE / "results/firmware_requests_stdout.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    replace_block(HERE.parents[2] / "docs/gripper/analysis/controls.md", "requests", md_table(rows))


if __name__ == "__main__":
    main()
