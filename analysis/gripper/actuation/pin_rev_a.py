"""Pin the actuation trade study to its rev A reference (DS3218MG, A17) so later firmware revisions do not move it.

The study compared candidate actuators against the servo the rev A firmware was built for and recommended the
DSServo DS3230 MG (A32), which rev B.1 now builds. Rev B.1 re-based firmware/gripper/config.h, fw_sim.json and
thermal.json on the DS3230, so read live they would turn the study's "present servo" into the winner it chose. This
script copies the three inputs the study reads from the commit below into rev_a/:

  rev_a/config.json            every #define of firmware/gripper/config.h (fwconfig.load), DS3218MG rev A values
  rev_a/fw_sim_cases.json      the four fw_sim.json cases the vectorised mirror is validated against
  rev_a/thermal_reference.json the thermal.json rows extras.thermal_reference / thermal_estimate read

Run from the repository root:  python analysis/gripper/actuation/pin_rev_a.py [--check]
--check rebuilds in memory and exits 1 if a committed file differs.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "analysis/gripper/firmware_sim"))
import fwconfig  # noqa: E402

PIN_COMMIT = "7e1039ab7a26077e6d6c8f15673adca6bc907eae"   # master before rev B.1 (PR 54 base); DS3218MG config.h
OUT = HERE / "rev_a"
FW_CASES = ("0.88 R12 min", "1.05 FEA E56+D7", "1.24 FEA E67+D7", "1.63 R12 max")
FW_KEYS = ("c0_deg", "t_contact_s", "t_F90_s", "F_max_N", "F_hold_mean_N")
FITS = ("A_mech", "B_elec")
CONDS = ("avg", "pwm")


def _show(path: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{PIN_COMMIT}:{path}"], check=True,
                          capture_output=True, text=True, encoding="utf-8").stdout


def _prov(path: str, what: str) -> dict:
    return {"pinned_from": f"{path} at {PIN_COMMIT}", "what": what,
            "generator": "analysis/gripper/actuation/pin_rev_a.py"}


def build() -> dict[str, str]:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "config.h"
        p.write_text(_show("firmware/gripper/config.h"), encoding="utf-8")
        cfg = fwconfig.load(p)
    fw = json.loads(_show("analysis/gripper/firmware_sim/results/fw_sim.json"))
    th = json.loads(_show("analysis/gripper/thermal/results/thermal.json"))
    files = {
        "config.json": {"_provenance": _prov("firmware/gripper/config.h", "rev A firmware constants, DS3218MG (A17) "
                                             "servo; each value's source tag is on its line in that file"),
                        "config": cfg},
        "fw_sim_cases.json": {"_provenance": _prov("analysis/gripper/firmware_sim/results/fw_sim.json",
                                                   "compiled-firmware simulation, A17 1:1 plant, rev A config"),
                              "cases": {c: {k: fw["cases"][c][k] for k in FW_KEYS} for c in FW_CASES}},
        "thermal_reference.json": {
            "_provenance": _prov("analysis/gripper/thermal/results/thermal.json", "rev A thermal model of the "
                                 "DS3218MG at 6.5 V, 5 N hold: the rows extras.py reads"),
            "step2_steady": {f"{f}|{c}|F5": th["step2_steady"][f"{f}|{c}|F5"] for f in FITS for c in CONDS},
            "step1_heat_sources": {f"{f}|F5|{c}": th["step1_heat_sources"][f"{f}|F5|{c}"] for f in FITS for c in CONDS},
            "step4b_mitigated_matrix": {k: v for k, v in th["step4b_mitigated_matrix"].items()
                                        if k.split("|")[0] in FITS and k.split("|")[1] in CONDS
                                        and k.split("|")[3] in ("backoff_none", "backoff_0.4225")}},
    }
    return {name: json.dumps(obj, indent=1, sort_keys=True) + "\n" for name, obj in files.items()}


def main(argv: list[str]) -> int:
    texts = build()
    if "--check" in argv:
        stale = [n for n, t in texts.items() if not (OUT / n).exists() or (OUT / n).read_text(encoding="utf-8") != t]
        print("rev A pin: " + ("stale " + ", ".join(stale) if stale else "fresh"))
        return 1 if stale else 0
    OUT.mkdir(exist_ok=True)
    for n, t in texts.items():
        (OUT / n).write_bytes(t.encode("utf-8"))
    print(f"rev A pin: wrote {len(texts)} files from {PIN_COMMIT[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
