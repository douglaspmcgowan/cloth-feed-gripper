"""Temporary lane runner: capture exit codes and final output lines."""
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parent
UV = ["uv", "--cache-dir", "C:/Users/dougl/AppData/Local/Temp/uv-dog-b40", "run", "--no-project"]
CHECKS = [
    ("actuation", ["--with", "numpy", "python", "analysis/gripper/actuation/pin_rev_a.py", "--check"]),
    ("tolstack", ["--with", "pyyaml", "--with", "numpy", "python", "analysis/gripper/tolstack/tolstack.py", "--check"]),
    ("ecad", ["--with", "numpy", "--with", "scipy", "python", "ecad/gripper/calc/run_all.py", "--check"]),
    ("gears", ["--with", "numpy", "--with", "scipy", "--with", "matplotlib", "--with", "shapely", "python", "analysis/gripper/gears.py", "--check"]),
    ("thermal", ["--with", "numpy", "--with", "scipy", "python", "analysis/gripper/thermal/thermal.py", "--check"]),
    ("test_plan", ["--with", "numpy", "--with", "scipy", "--with", "pyyaml", "python", "docs/gripper/test/test_plan.py", "--check"]),
    ("dyno", ["--with", "numpy", "--with", "scipy", "--with", "matplotlib", "--with", "shapely", "--with", "pylife", "--with", "packaging", "python", "analysis/gripper/dyno.py", "--check"]),
    ("finger_beam", ["--with", "numpy", "--with", "scipy", "--with", "matplotlib", "python", "analysis/gripper/finger_beam.py", "--check"]),
]


def main() -> None:
    phase = sys.argv[1]
    results = {}
    for name, args in CHECKS:
        command = UV + args
        completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, errors="replace", timeout=1200)
        lines = completed.stdout.strip().splitlines()
        last = lines[-1] if lines else ""
        results[name] = {"exit": completed.returncode, "last": last, "command": " ".join(command)}
        print(f"{name}: exit {completed.returncode}: {last}", flush=True)
    (ROOT / f".fleet_{phase}_checks.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
