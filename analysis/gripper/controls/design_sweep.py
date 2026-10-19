"""Compare firmware design variants with a smaller Monte Carlo each (same seed, same plant draws), to choose the
values committed in config.h. Run from the repository root (about 1 min per 400-grip variant on 4 cores):
    python analysis/gripper/controls/design_sweep.py
Writes results/design_sweep.json and results/design_sweep_stdout.txt."""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import loop  # noqa: E402
import montecarlo as mc  # noqa: E402

N = 300
# Each variant: name, config.h values that differ from the committed file, plant ranges that differ from plant.py.
# "bench confirms the nominals" = the measurements controls.md section 8 asks for come back at the assumed nominals:
# k measured 1.1 N/mm within +/-5 % (M10) and FINGER_K_MAX set to 1.1 x that; CALF span residual +/-3 % (M11); servo
# lag and dead time as assumed (M8). "bench does not confirm" = M10 measures k 1.4 N/mm (+/-5 %); FINGER_K_MAX set by
# the same rule (1.54). These narrow ranges around assumed values; they are not measurements.
BENCH = {"k_tip_n_per_mm": (1.045, 1.155), "span_mount": (0.97, 1.03), "tau_s": (0.035, 0.045), "dead_ms": (8.0, 12.0)}
BENCH_FW = {"FINGER_K_MAX_N_PER_MM": 1.21}
BENCH_K14 = dict(BENCH, k_tip_n_per_mm=(1.33, 1.47))
BENCH_K14_FW = {"FINGER_K_MAX_N_PER_MM": 1.54}
VARIANTS = [
    ("no schedule, no bias", {"GAIN_SCHED_ENABLED": 0, "F_HOLD_BIAS_N": 0}, {}),
    ("gain schedule", {"GAIN_SCHED_ENABLED": 1, "F_HOLD_BIAS_N": 0}, {}),
    ("schedule + bias 0.6", {"GAIN_SCHED_ENABLED": 1, "F_HOLD_BIAS_N": 0.6}, {}),
    ("schedule + slow zone 4", {"GAIN_SCHED_ENABLED": 1, "F_HOLD_BIAS_N": 0, "JAW_SLOW_ZONE_DEG": 4}, {}),
    ("shipped, slow zone 3 (tolerance T09T-slow3)", {"JAW_SLOW_ZONE_DEG": 3}, {}),
    ("schedule + 240 deg/s, zone 8", {"GAIN_SCHED_ENABLED": 1, "F_HOLD_BIAS_N": 0, "JAW_SPEED_FAST_DPS": 240,
                                      "JAW_SLOW_ZONE_DEG": 8}, {}),
    ("shipped", {}, {}),
    ("shipped with F1 back-off on (BACKOFF 0.5)", {"HOLD_BACKOFF_ENABLED": 1}, {}),
    ("shipped, cap for R15 = 8 N", {"F_CAP_N": 8.0}, {}),
    ("shipped, Kp 0.30 (CTRL_TAU_CL_S 0.042)", {"CTRL_TAU_CL_S": 0.042}, {}),
    ("bench confirms nominals: shipped", dict(BENCH_FW), BENCH),
    ("bench confirms nominals: cap for R15 = 8 N", dict(BENCH_FW, F_CAP_N=8.0), BENCH),
    ("bench confirms nominals: no schedule, no bias", dict(BENCH_FW, GAIN_SCHED_ENABLED=0, F_HOLD_BIAS_N=0), BENCH),
    ("bench does not confirm (k 1.4): shipped", dict(BENCH_K14_FW), BENCH_K14),
]
KEYS = ("grip_ok", "R14", "R15_10N", "R15_8N", "R19_0.5s_F90", "R19_0.75s_F5", "R19_contact_0.5s")


def run_variant(ovr, rng=None, n=N, seed=mc.SEED, early=False, sp=5.0, fix=None, keep_runs=False):
    mc.RANGE, mc.FIX, mc.EARLY, mc.SP = dict(rng or {}), dict(fix or {}), early, sp
    loop.configure(ovr)
    loop.lib()
    with Pool(4) as pool:
        runs = pool.map(mc.one, [(seed, i, mc.context()) for i in range(n)], chunksize=10)
    mc.RANGE, mc.FIX, mc.EARLY, mc.SP = {}, {}, False, 5.0
    s = mc.summarise(runs)
    v3 = [r["m"].get("v_touch3_dps") for r in runs if r["m"].get("v_touch3_dps") is not None]
    s["P_v3_le_20"] = sum(1 for v in v3 if v <= 20.0) / max(1, len(v3))
    if keep_runs:
        s["runs"] = runs
    return s


def main():
    out = []
    lines = [f"design sweep, n={N} per variant, seed {mc.SEED}"]
    for name, ovr, rng in VARIANTS:
        s = run_variant(ovr, rng)
        row = {"name": name, "overrides": ovr, "plant_ranges": rng, "prob": {k: s["prob"][k]["p"] for k in KEYS},
               "P_v3_le_20": s["P_v3_le_20"], "t_90_p50": s["dist"]["t_90_s"]["p50"], "t_90_p95": s["dist"]["t_90_s"]["p95"],
               "F_peak_p99": s["dist"]["F_peak_N"]["p99"], "F_peak_max": s["dist"]["F_peak_N"]["max"],
               "hold_min_p05": s["dist"]["F_hold_min_N"]["p05"], "events": s["event_counts"]}
        out.append(row)
        lines.append(f"{name:42s} " + " ".join(f"{k} {row['prob'][k]:.3f}" for k in KEYS)
                     + f" v3<=20 {row['P_v3_le_20']:.2f} t90 p50/p95 {row['t_90_p50']:.3f}/{row['t_90_p95']:.3f}"
                     + f" Fpk p99/max {row['F_peak_p99']:.2f}/{row['F_peak_max']:.2f} hold p05 {row['hold_min_p05']:.2f}"
                     + f" {row['events']}")
        print(lines[-1], flush=True)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results/design_sweep.json").write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    (HERE / "results/design_sweep_stdout.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
