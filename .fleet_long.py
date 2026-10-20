"""Temporary background runner for long CAD commands."""
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parent
UV = ["uv", "--cache-dir", "C:/Users/dougl/AppData/Local/Temp/uv-dog-b40", "run", "--python", "3.12", "--no-project", "--with", "cadquery", "python"]
COMMANDS = {
    "fitcheck": UV + ["cad/gripper/fitcheck.py"],
    "fit3d": UV + ["cad/gripper/fit3d.py"],
    "fit3d_final": UV + ["cad/gripper/fit3d.py"],
    "viewer": ["python", "cad/gripper/viewer_src/viewer_build.py"],
    "dog_check": UV + ["cad/gripper/dog_check.py"],
    "dyno": ["uv", "--cache-dir", "C:/Users/dougl/AppData/Local/Temp/uv-dog-b40", "run", "--no-project",
             "--with", "numpy", "--with", "scipy", "--with", "matplotlib", "--with", "shapely",
             "--with", "pylife", "--with", "packaging", "python", "analysis/gripper/dyno.py"],
    "thermal": ["uv", "--cache-dir", "C:/Users/dougl/AppData/Local/Temp/uv-dog-b40", "run", "--no-project",
                "--with", "numpy", "--with", "scipy", "python", "analysis/gripper/thermal/thermal.py"],
    "test_plan": ["uv", "--cache-dir", "C:/Users/dougl/AppData/Local/Temp/uv-dog-b40", "run", "--no-project",
                  "--with", "numpy", "--with", "scipy", "--with", "pyyaml", "python", "docs/gripper/test/test_plan.py"],
    "actuation_tests": ["uv", "--cache-dir", "C:/Users/dougl/AppData/Local/Temp/uv-dog-b40", "run",
                        "--python", "3.12", "--no-project", "--with-requirements", "requirements-dev.txt",
                        "python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        "--basetemp", "C:/Users/dougl/AppData/Local/Temp/pw/pt-dog-b40-act",
                        "analysis/gripper/actuation"],
    "cad_tests": ["uv", "--cache-dir", "C:/Users/dougl/AppData/Local/Temp/uv-dog-b40", "run",
                  "--python", "3.12", "--no-project", "--with", "cadquery", "--with", "pytest",
                  "--with", "pygments", "--with", "pyyaml", "--with", "playwright", "--with", "shapely",
                  "python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                  "--basetemp", "C:/Users/dougl/AppData/Local/Temp/pw/pt-dog-b40-cad", "cad/gripper"],
    "tol_tests": ["uv", "--cache-dir", "C:/Users/dougl/AppData/Local/Temp/uv-dog-b40", "run",
                  "--python", "3.12", "--no-project", "--with-requirements", "requirements-dev.txt",
                  "python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                  "--basetemp", "C:/Users/dougl/AppData/Local/Temp/pw/pt-dog-b40-tol-final",
                  "analysis/gripper/tolstack"],
}


def main() -> None:
    name = sys.argv[1]
    result_file = ROOT / f".fleet_{name}_result.json"
    log_file = ROOT / f".fleet_{name}.log"
    command = COMMANDS[name]
    with log_file.open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=7200)
    lines = log_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    result_file.write_text(json.dumps({"command": " ".join(command), "exit": result.returncode,
                                       "last": lines[-1] if lines else ""}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
