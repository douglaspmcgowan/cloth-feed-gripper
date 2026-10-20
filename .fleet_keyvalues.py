"""Print selected numeric B40 before/after values from the pre-B40 commit and worktree."""
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent

def load(path, old=False):
    if old:
        raw = subprocess.run(["git", "show", f"44b146d:{path}"], cwd=root,
                             check=True, stdout=subprocess.PIPE).stdout
        return json.loads(raw)
    return json.loads((root / path).read_text(encoding="utf-8"))

for path in ("analysis/gripper/tolstack/results/rev_b/revb.json",
             "analysis/gripper/tolstack/results/rev_b/revb_hot.json"):
    for old in (True, False):
        data = load(path, old)
        for base in ("T09", "T14B"):
            row = next((r for r in data["stacks"] if r["base_id"] == base), None)
            if row:
                print(path, "old" if old else "new", base,
                      row["mc"]["cpk_percentile"], row["yield_pct"], row["verdict3"])

for path in ("analysis/gripper/tolstack/results/T14B-boss34.json",
             "analysis/gripper/tolstack/results/T09.json"):
    for old in (True, False):
        data = load(path, old)
        print(path, "old" if old else "new", data["mc"]["cpk_percentile"],
              data["yield_pct"], data["verdict3"])
