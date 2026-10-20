"""Keep B40 F61 risk quotes focused on the stack result, not a decimal shoulder diameter."""
from pathlib import Path

path = Path(__file__).resolve().parent / "docs/gripper/RISK.md"
lines = path.read_text(encoding="utf-8").splitlines()
count = 0
for index, line in enumerate(lines):
    if line.startswith("| 6 | F61 |") or line.startswith("| F61 |"):
        old = line
        line = line.replace("hardened Ø2.9 shoulder dogs", "hardened shoulder dogs")
        line = line.replace("boss-located Ø2.9 hardened shoulders", "boss-located hardened shoulders")
        line = line.replace("[A; (3.4 − 0.1 − 2.9) / (2 × 7 mm) rad]", "[A; T14B shoulder/slot geometry]")
        if line == old:
            raise SystemExit(f"expected B40 F61 text at line {index + 1}")
        lines[index] = line
        count += 1
if count != 2:
    raise SystemExit(f"expected two F61 rows, found {count}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("refined two owned F61 rows")
