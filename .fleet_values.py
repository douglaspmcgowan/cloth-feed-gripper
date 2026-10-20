"""Temporary comparison of committed generated JSON with this lane's outputs."""
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FILES = [
    "cad/gripper/out/dog_check.json",
    "cad/gripper/out/parts.json",
    "cad/gripper/out/fitcheck.json",
    "analysis/gripper/results/dyno.json",
    "analysis/gripper/thermal/results/thermal.json",
    "docs/gripper/test/test_plan_out.json",
]


def flatten(value, prefix=""):
    out = {}
    if isinstance(value, dict):
        for key, item in value.items():
            out.update(flatten(item, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            out.update(flatten(item, f"{prefix}[{index}]"))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        out[prefix] = value
    return out


def main():
    for rel in FILES:
        old_raw = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, check=True).stdout
        old = flatten(json.loads(old_raw))
        new = flatten(json.loads((ROOT / rel).read_text(encoding="utf-8")))
        changed = [(key, old[key], new[key]) for key in old.keys() & new.keys() if old[key] != new[key]]
        print(rel, len(changed), "changed numeric values")
        for key, a, b in changed[:30]:
            print(" ", key, a, "->", b)


if __name__ == "__main__":
    main()
