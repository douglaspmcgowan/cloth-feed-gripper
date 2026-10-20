"""Regenerate the seven committed tolerance sweep pairs with their recorded inputs."""
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HERE = ROOT / "analysis/gripper/tolstack"
for path in sorted((HERE / "results").glob("sweep_*.json")):
    info = json.loads(path.read_text(encoding="utf-8"))
    command = ["uv", "--cache-dir", "C:/Users/dougl/AppData/Local/Temp/uv-dog-b40", "run",
               "--no-project", "--with", "pyyaml", "--with", "numpy", "python",
               str(HERE / "tolstack.py"), "sweep", str(HERE / "stacks"),
               "--stack", info["stack"], "--param", info["param"], "--values", info["values"],
               "--samples", str(info["samples"]), "--seed", str(info["seed"]),
               "--out", str(path.with_suffix(".md"))]
    for key, value in info.get("overrides", {}).items():
        command += ["--set", f"{key}={value}"]
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors="replace", timeout=1200)
    lines = result.stdout.strip().splitlines()
    print(f"{path.name}: exit {result.returncode}: {lines[-1] if lines else ''}", flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
