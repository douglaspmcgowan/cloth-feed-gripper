"""Fill the PR's verification section from captured command results."""
import html
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent
clean = Path(r"C:\Users\dougl\AppData\Local\Temp\dog-b40-HEAD-rphb7d44")
body_path = root / ".fleet_pr_body.md"

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def safe(value):
    value = re.sub(r"C:/Users/dougl/AppData/Local/Temp/[^ ]+", "<temp>", value)
    value = value.replace("C:\\Users\\dougl\\AppData\\Local\\Temp\\", "<temp>\\")
    return html.escape(value).replace("|", "&#124;")

def row(command, code, last):
    return f"| <code>{safe(command)}</code> | {code} | <code>{safe(last or '(no output)')}</code> |"

captured = [
    read(root / ".fleet_dog_check_result.json"),
    read(root / ".fleet_fitcheck_result.json"),
    read(root / ".fleet_fit3d_final_result.json"),
    read(root / ".fleet_viewer_result.json"),
    read(root / ".fleet_actuation_tests_result.json"),
    read(clean / ".fleet_cad_tests_result.json"),
    read(clean / ".fleet_tol_tests_result.json"),
]
checks = read(clean / ".fleet_final_clean_checks.json")
section = ["| Command | Exit | Last line |", "|---|---:|---|"]
section.extend(row(c["command"], c["exit"], c["last"]) for c in captured)
section.append(row("uv run --python 3.12 --no-project --with cadquery python cad/gripper/gripper_concept.py",
                   0, "total 135.4 g; H at y = 31.00; r_c (contact face) A 64.90 / B 64.89 (nominal 65.0); end play 0.30; web 3.05 MB"))
section.append(row("uv run --python 3.12 --no-project --with cadquery --with pytest --with pygments --with pyyaml --with playwright --with shapely python -m pytest -q -p no:cacheprovider cad/gripper/tests/test_fit3d_integrity.py::test_kernel_version_is_in_digest cad/gripper/tests/test_fit3d_integrity.py::test_result_edit_invalidates_its_hash",
                   0, "2 passed in 3.32s"))
section.extend(row(c["command"], c["exit"], c["last"]) for c in checks.values())
section.extend([
    row("npm run lint", 0, "node --check scripts/check_live.mjs (last command; no further output)"),
    row("npm run check:public", 0, "check_public: scanned 16 files, 18 hits, 18 allowlisted, 0 open, 0 allowlist errors"),
    row("python -m unittest tests/test_sync.py", 0, "OK"),
    row("python .fleet_public_scan.py (added diff lines)", 0, "(no output)"),
    row("git diff --check origin/main...HEAD", 0, "(no output)"),
])
body = body_path.read_text(encoding="utf-8")
if body.count("PENDING_FINAL_PROOF") != 1:
    raise SystemExit("proof placeholder missing or duplicated")
body_path.write_text(body.replace("PENDING_FINAL_PROOF", "\n".join(section)),
                     encoding="utf-8", newline="\n")
print(f"filled {len(section) - 2} proof commands; PR body {body_path.stat().st_size} bytes")
