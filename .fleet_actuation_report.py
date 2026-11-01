"""Temporary local evidence helper for the actuation fleet lane."""

import difflib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULT = "analysis/gripper/actuation/results/actuation_trade.json"
STDOUT = "analysis/gripper/actuation/results/actuation_trade_stdout.txt"


def old_bytes(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"origin/main:{path}"])


def changed(left, right, path="$"):
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(left.keys() | right.keys()):
            yield from changed(left.get(key, "<missing>"), right.get(key, "<missing>"), f"{path}.{key}")
    elif isinstance(left, list) and isinstance(right, list):
        for index in range(max(len(left), len(right))):
            a = left[index] if index < len(left) else "<missing>"
            b = right[index] if index < len(right) else "<missing>"
            yield from changed(a, b, f"{path}[{index}]")
    elif left != right or type(left) is not type(right):
        yield path, left, right


def report():
    before = json.loads(old_bytes(RESULT))
    after = json.loads((ROOT / RESULT).read_bytes())
    changes = list(changed(before, after))
    for path, left, right in changes:
        print(f"{path}: {left!r} -> {right!r}")
    print(f"JSON changed leaves: {len(changes)}")
    a = old_bytes(STDOUT).decode().splitlines()
    b = (ROOT / STDOUT).read_text(encoding="utf-8").splitlines()
    lines = list(difflib.unified_diff(a, b, fromfile="old stdout", tofile="new stdout", lineterm=""))
    for line in lines:
        print(line)
    print(f"stdout diff lines: {len(lines)}")


def safety():
    diff = subprocess.check_output(["git", "-C", str(ROOT), "diff", "origin/main...HEAD", "--", "analysis/gripper/actuation", "docs/gripper/analysis/actuation_trade.md"], text=True)
    patterns = [r"C:[\\/]Users", r"/home/", r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]+"]
    for pattern in patterns:
        for match in re.finditer(pattern, diff):
            print(match.group())
    return 0


def bodycheck():
    before = json.loads(old_bytes(RESULT))
    after = json.loads((ROOT / RESULT).read_bytes())
    body = (ROOT / ".fleet-pr-body.md").read_text(encoding="utf-8")
    missing = [path for path, _, _ in changed(before, after) if f"`{path[2:]}`" not in body]
    for path in missing:
        print(f"missing from PR body: {path}")
    print(f"bodycheck: {42 - len(missing)} of 42 changed leaves listed")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(safety() if sys.argv[1:] == ["safety"] else bodycheck() if sys.argv[1:] == ["bodycheck"] else report())
