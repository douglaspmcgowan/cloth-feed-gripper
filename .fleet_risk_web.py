"""Name the inner ligament in the owned B40 retention-risk row."""
from pathlib import Path

path = Path(__file__).resolve().parent / "docs/gripper/RISK.md"
lines = path.read_text(encoding="utf-8").splitlines()
matches = [i for i, line in enumerate(lines) if line.startswith("| F67 |")]
if len(matches) != 1:
    raise SystemExit(f"expected one F67 row, found {len(matches)}")
index = matches[0]
old = lines[index]
new = old.replace("the 1 mm aluminium rim cracks", "the 1 mm outer rim or 0.5 mm inner web cracks")
new = new.replace("horn rim fatigue", "outer-rim and inner-web fatigue")
new = new.replace("rim crack", "rim/web crack")
if new == old:
    raise SystemExit("B40 F67 text absent")
lines[index] = new
path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("F67 now records the 0.5 mm centre web")
