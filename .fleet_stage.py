"""Stage only the generated outputs owned by the B40 fleet brief."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent

def listed(*args):
    result = subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE)
    return {p.decode("utf-8", "surrogateescape") for p in result.stdout.split(b"\0") if p}

changed = listed("diff", "--name-only", "-z") | listed("ls-files", "--others", "--exclude-standard", "-z")
prefixes = ("analysis/gripper/tolstack/results/", "cad/gripper/out/", "cad/gripper/drawings/")
exact = {"cad/gripper/viewer.html", "analysis/gripper/results/dyno.json",
         "analysis/gripper/thermal/results/thermal.json",
         "analysis/gripper/thermal/results/thermal_stdout.txt",
         "docs/gripper/test/test_plan_out.json"}
owned = sorted(p for p in changed if p.startswith(prefixes) or p in exact)
if not owned or not (root / "cad/gripper/out/fit3d.json").exists():
    raise SystemExit("required generated outputs absent")
subprocess.run(["git", "add", "--", *owned], cwd=root, check=True)
print(f"staged {len(owned)} exact owned generated paths")
