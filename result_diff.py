"""Temporary lane helper: compare committed and regenerated JSON values."""

import argparse
import json
import subprocess
from pathlib import Path


def walk(before, after, stem=""):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            path = f"{stem}.{key}" if stem else key
            if key not in before:
                yield path, None, after[key]
            elif key not in after:
                yield path, before[key], None
            else:
                yield from walk(before[key], after[key], path)
    elif isinstance(before, list) and isinstance(after, list):
        for index in range(max(len(before), len(after))):
            path = f"{stem}[{index}]"
            if index >= len(before):
                yield path, None, after[index]
            elif index >= len(after):
                yield path, before[index], None
            else:
                yield from walk(before[index], after[index], path)
    elif before != after:
        yield stem, before, after


parser = argparse.ArgumentParser()
parser.add_argument("revision")
parser.add_argument("output", type=Path)
parser.add_argument("paths", nargs="+")
args = parser.parse_args()
lines = []
for name in args.paths:
    path = Path(name)
    before = json.loads(subprocess.check_output(["git", "show", f"{args.revision}:{name}"], text=True))
    after = json.loads(path.read_text(encoding="utf-8"))
    changed = list(walk(before, after))
    lines += [f"### `{name}` ({len(changed)} changed leaves)", "", "| Key | Old → new |", "|---|---|"]
    for key, old, new in changed:
        left = json.dumps(old, ensure_ascii=False, separators=(",", ":"))
        right = json.dumps(new, ensure_ascii=False, separators=(",", ":"))
        lines.append(f"| `{key}` | `{left}` → `{right}` |")
    lines.append("")
args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} lines, {args.output.stat().st_size} bytes")
