"""The one command that regenerates every number in docs/gripper/analysis/controls.md. From the repository root:
    python analysis/gripper/controls/run_all.py          (about 16 min on 4 cores: 7 min measured before step 13, 9 min for it)
Runs, in order, each writing JSON plus a stdout capture under its results/ directory:
  1. analysis/gripper/firmware_sim/sim.py     the W2b-1 linear-plant simulation (kept as a regression)
  2. linear.py                                margins at three operating points
  3. faults.py                                fault injection and the Fit A / Fit B current scenarios
  4. montecarlo.py                            2,000 grips, shipped firmware, seed 20261011 (also worst_cases.json)
  5. montecarlo.py --tag before               the same draws through the W2b-1 control settings
  6. montecarlo.py --tag bench                the same draws IF the M8 / M10 / M11 bench confirms the assumed nominals
  7. montecarlo.py --tag bench_k14            ... if instead M10 measures k 1.4 N/mm (1,000 grips)
  8. montecarlo.py --tag g6 / g7              setpoints G 6 and G 7 (1,000 grips each)
  9. montecarlo.py --tag nocal                CALF skipped: span_mount 0.5-1.5 (1,000 grips)
 10. montecarlo.py --tag early                early contact 0-10 deg drawn (1,000 grips)
 11. design_sweep.py                          the variants behind the config.h choices
 12. early_contact.py                         the R15 early-contact knobs and their cost to R14 / R19
 13. firmware_requests.py                     the tolerance study's firmware requests and the 8 N cap (about 9 min)
 14. figures.py                               Monte Carlo distribution figure
 15. analysis/gripper/firmware_sim/gates.py   host FSM test, pytest, ESP32 compile (if arduino-cli can run here);
                                              exits 1 if a gate that ran failed
A rerun leaves `git status` clean apart from the PNG figures (matplotlib output is not byte-stable across versions).
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PY = sys.executable
BEFORE = "GAIN_SCHED_ENABLED=0,F_HOLD_BIAS_N=0,F_CAP_MARGIN_N=0,STALL_CURRENT_HOLD_A=1.8"
# "If the bench confirms the nominals": ranges narrowed around ASSUMED bench results (k 1.1 N/mm, CALF +/-3 %, servo
# lag as assumed), not measurements. "bench_k14": the bench measures k 1.4 N/mm instead (FINGER_K_MAX set by the same
# 1.1 x rule, 1.54). Both assume CALF done to within 3 % (R14 figures assume within 10 % in the shipped column).
BENCH_FW = "FINGER_K_MAX_N_PER_MM=1.21"
BENCH_RANGE = "k_tip_n_per_mm=1.045:1.155,span_mount=0.97:1.03,tau_s=0.035:0.045,dead_ms=8:12"
BENCH_K14_FW = "FINGER_K_MAX_N_PER_MM=1.54"
BENCH_K14_RANGE = "k_tip_n_per_mm=1.33:1.47,span_mount=0.97:1.03,tau_s=0.035:0.045,dead_ms=8:12"
MC = "analysis/gripper/controls/montecarlo.py"

STEPS = [
    ["analysis/gripper/firmware_sim/sim.py"],
    ["analysis/gripper/controls/linear.py"],
    ["analysis/gripper/controls/faults.py"],
    [MC],
    [MC, "--tag", "before", "--set", BEFORE],
    [MC, "--tag", "bench", "--set", BENCH_FW, "--range", BENCH_RANGE],
    [MC, "--tag", "bench_k14", "--n", "1000", "--set", BENCH_K14_FW, "--range", BENCH_K14_RANGE],
    [MC, "--tag", "g6", "--n", "1000", "--sp", "6"],
    [MC, "--tag", "g7", "--n", "1000", "--sp", "7"],
    [MC, "--tag", "nocal", "--n", "1000", "--range", "span_mount=0.5:1.5"],     # CALF skipped
    [MC, "--tag", "early", "--n", "1000", "--early"],                          # early contact 0-10 deg drawn
    ["analysis/gripper/controls/design_sweep.py"],
    ["analysis/gripper/controls/early_contact.py"],
    ["analysis/gripper/controls/firmware_requests.py"],
    ["analysis/gripper/controls/figures.py"],
    ["analysis/gripper/firmware_sim/gates.py"],   # last: its pytest replays the worst cases written above
]


def main():
    rc = 0
    for s in STEPS:
        print("==>", " ".join(s), flush=True)
        out = ROOT / "analysis/gripper/firmware_sim/results/sim_stdout.txt" if s[0].endswith("sim.py") else None
        if out:
            with open(out, "w", encoding="utf-8", newline="\n") as fh:
                r = subprocess.run([PY] + s, cwd=ROOT, stdout=fh)
        else:
            r = subprocess.run([PY] + s, cwd=ROOT)
        print("    exit", r.returncode, flush=True)
        rc = rc or r.returncode
    return rc


if __name__ == "__main__":
    sys.exit(main())
