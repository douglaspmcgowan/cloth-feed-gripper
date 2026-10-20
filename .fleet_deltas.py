"""Write an exhaustive numeric old/new audit for the B40 generated JSON results."""
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "cad/gripper/out/B40_numeric_deltas.json"
SOURCES = [
    ROOT / "cad/gripper/out/dog_check.json",
    ROOT / "cad/gripper/out/parts.json",
    ROOT / "cad/gripper/out/fitcheck.json",
    ROOT / "cad/gripper/out/fit3d.json",
    ROOT / "analysis/gripper/results/dyno.json",
    ROOT / "analysis/gripper/thermal/results/thermal.json",
    ROOT / "docs/gripper/test/test_plan_out.json",
    *(ROOT / "analysis/gripper/tolstack/results").rglob("*.json"),
]


def values(node, prefix=""):
    if isinstance(node, dict):
        for key, item in node.items():
            yield from values(item, f"{prefix}.{key}" if prefix else key)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from values(item, f"{prefix}[{index}]")
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        yield prefix, node


def main():
    records = []
    counts = {}
    for path in sorted(set(SOURCES)):
        rel = path.relative_to(ROOT).as_posix()
        if not path.exists():
            continue
        old_process = subprocess.run(["git", "show", f"44b146d:{rel}"], cwd=ROOT,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        old = dict(values(json.loads(old_process.stdout))) if old_process.returncode == 0 else {}
        new = dict(values(json.loads(path.read_text(encoding="utf-8"))))
        differences = []
        for key in sorted(old.keys() | new.keys()):
            if old.get(key) != new.get(key):
                differences.append({"value": key, "old": old.get(key), "new": new.get(key)})
        if differences:
            counts[rel] = len(differences)
            records.append({"file": rel, "changes": differences})
    payload = {"basis": "numeric scalar diff against pre-B40 commit 44b146d for generated JSON only",
               "files": counts, "values": records}
    TARGET.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{TARGET.relative_to(ROOT).as_posix()}: {sum(counts.values())} numeric old/new values in {len(counts)} files")


if __name__ == "__main__":
    main()
