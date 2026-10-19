"""Early contact (R15): the jaw meets a fold, a seam stack or an object up to 10 deg above theta_c0, partly in the
120 deg/s leg. Each firmware variant runs the same draws twice: once with early_contact_deg drawn 0-10 deg
(plant.py, rigid, the worst case for the peak) for the peak force, once with no early contact for the cost to R14 and
R19. Run from the repository root (about 4 min on 4 cores):
    python analysis/gripper/controls/early_contact.py
Writes results/early_contact.json and results/early_contact_stdout.txt."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_sweep as dsw  # noqa: E402
import montecarlo as mc  # noqa: E402
sys.path.insert(0, str(HERE.parent / "firmware_sim"))
import build  # noqa: E402
import sim  # noqa: E402

N = 300
FAST_TRIP = {"F_TRIP_MS": 5, "FAULT_BACKOFF_DPS": 2000}
VARIANTS = [   # the four knobs the brief names: trip level, cap, approach speed in the last degrees, trip-to-stop latency
    ("shipped", {}),
    ("pre-ruling (10 N basis: no mid zone, fast 120, trip 8, soft 7.5, set max 7)", {"JAW_MID_ZONE_DEG": 0.0, "JAW_SPEED_FAST_DPS": 120.0, "F_TRIP_N": 8.0, "F_SOFT_LIMIT_N": 7.5, "F_SET_MAX_N": 7.0}),
    ("trip level 7 N (soft limit 6.8)", {"F_TRIP_N": 7.0, "F_SOFT_LIMIT_N": 6.8}),
    ("squeeze cap sized for 8 N", {"F_CAP_N": 8.0}),
    ("trip-to-stop: 5 ms trip, back-off as one step", FAST_TRIP),
    ("approach: 60 deg/s from theta_c0 + 14", {"JAW_MID_ZONE_DEG": 14, "JAW_SPEED_MID_DPS": 60}),
    ("approach: 40 deg/s from theta_c0 + 14", {"JAW_MID_ZONE_DEG": 14, "JAW_SPEED_MID_DPS": 40}),
    ("trip-to-stop + 60 deg/s from + 14", dict(FAST_TRIP, JAW_MID_ZONE_DEG=14, JAW_SPEED_MID_DPS=60)),
    ("trip-to-stop + 40 deg/s from + 14", dict(FAST_TRIP, JAW_MID_ZONE_DEG=14, JAW_SPEED_MID_DPS=40)),
]
BINS = [(0, 2), (2, 4), (4, 6), (6, 8), (8, 10.01)]


def peaks_by_bin(runs):
    out = []
    for lo, hi in BINS:
        pk = [r["m"]["F_peak_N"] for r in runs if lo <= r["p"]["early_contact_deg"] < hi and r["m"].get("booted")]
        out.append({"early_deg": [lo, min(hi, 10)], "n": len(pk), "max_N": max(pk) if pk else None,
                    "p50_N": mc.pct(pk, 0.5), "share_over_8N": sum(1 for x in pk if x > 8.0) / max(1, len(pk)),
                    "share_over_10N": sum(1 for x in pk if x > 10.0) / max(1, len(pk))})
    return out


def linear_bound(ovr):
    """The W2b-1 linear plant (no softening, no droop, no fold) with the stiffest R12 finger (1.63 N/mm): the bound."""
    lib = build.load(ovr or None)
    for i in range(64):
        name = lib.sim_event_name(i).decode()
        if name == "?":
            break
        sim.EV[name] = i
    out = {}
    for d in (4.0, 6.0, 8.0, 10.0):
        m = sim.metrics(sim.grip(lib, 1.63, ms=1500, touch=sim.TH_TOUCH_NOCLOTH + d))
        out[f"{d:.0f}"] = {"F_max_N": m["F_max_N"], "final_state": m["final_state"]}
    return out


def main():
    rows, lines = [], [f"early contact sweep, n={N} per variant and reading, seed {mc.SEED}"]
    for name, ovr in VARIANTS:
        e = dsw.run_variant(ovr, early=True, n=N, keep_runs=True)
        runs = e.pop("runs")
        folds = sum(1 for r in runs if r["m"].get("folded"))
        n0 = dsw.run_variant(ovr, n=N)
        row = {"name": name, "overrides": ovr,
               "early": {"P_peak_le_8N": e["prob"]["peak_le_8N"]["p"], "P_peak_le_10N": e["prob"]["peak_le_10N"]["p"],
                         "P_fold": folds / N, "P_fault": e["prob"]["fault"]["p"], "peak_max_N": e["dist"]["F_peak_N"]["max"],
                         "peak_p95_N": e["dist"]["F_peak_N"]["p95"], "by_bin": peaks_by_bin(runs)},
               "no_early": {k: n0["prob"][k]["p"] for k in ("grip_ok", "R14", "R19_0.5s_F90", "R19_0.75s_F5",
                                                            "R19_contact_0.5s", "peak_le_8N")},
               "t_sp_p50_s": n0["dist"]["t_sp_s"]["p50"], "linear_stiff_bound": linear_bound(ovr)}
        rows.append(row)
        b = " ".join(f"[{x['early_deg'][0]:g}-{x['early_deg'][1]:g}] max {x['max_N']:.2f}" for x in row["early"]["by_bin"])
        lines.append(f"{name:46s} early: P(<=8N) {row['early']['P_peak_le_8N']:.3f} P(<=10N) {row['early']['P_peak_le_10N']:.3f}"
                     f" P(fold) {row['early']['P_fold']:.3f} max {row['early']['peak_max_N']:.2f} | {b} || no early: "
                     + " ".join(f"{k} {v:.3f}" for k, v in row["no_early"].items()) + f" t5 p50 {row['t_sp_p50_s']:.3f}"
                     + " || linear k 1.63: " + " ".join(f"{d} deg {v['F_max_N']:.2f} {v['final_state']}"
                                                       for d, v in row["linear_stiff_bound"].items()))
        print(lines[-1], flush=True)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results/early_contact.json").write_text(json.dumps(rows, indent=1), encoding="utf-8", newline="\n")
    (HERE / "results/early_contact_stdout.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
