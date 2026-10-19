"""Run the firmware proving commands and record their real exit codes and summary lines in
results/gates.json (read by cad/gripper/viewer_src/viewer_build.py). Run from anywhere:
    python analysis/gripper/firmware_sim/gates.py
arduino-cli is taken from $ARDUINO_CLI or PATH (or /opt/arduino-cli in the cloud container), with
--config-file $ARDUINO_CLI_CONFIG when set (or /opt/arduino-gripper/arduino-cli.yaml when it exists);
if absent, the compile gate is recorded as "not run".

Only run-independent fields are written: no date, no timings, repository-relative commands, "\n" newlines. A compile
result is recorded only from a run that could compile (arduino-cli present and its Python tools importable); otherwise
the gate says why it did not run, with exit null, and the last compile that did run is recorded in controls.md."""
import json
import re
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def run(cmd):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    lines = [l for l in (p.stdout + p.stderr).splitlines() if l.strip()]
    return p.returncode, lines


def main():
    gates = []
    cli = os.environ.get("ARDUINO_CLI") or shutil.which("arduino-cli")
    if not cli and Path("/opt/arduino-cli/arduino-cli").exists():
        cli = "/opt/arduino-cli/arduino-cli"
    cfg = os.environ.get("ARDUINO_CLI_CONFIG") or (
        "/opt/arduino-gripper/arduino-cli.yaml" if Path("/opt/arduino-gripper/arduino-cli.yaml").exists() else None)
    if cli and cfg:
        cli = [cli, "--config-file", cfg]
    elif cli:
        cli = [cli]
    compile_cmd = "arduino-cli compile --fqbn esp32:esp32:esp32 --warnings all firmware/gripper"
    if cli:
        rc, lines = run(cli + ["compile", "--clean", "--fqbn", "esp32:esp32:esp32", "--warnings", "all", "firmware/gripper"])
        missing = [l for l in lines if l.startswith("ModuleNotFoundError")]
        if missing:   # the toolchain itself could not run: not a result about the firmware
            gates.append({"name": "arduino-cli compile", "cmd": compile_cmd, "exit": None,
                          "summary": ["not run: the esp32 core's tools need a Python module this machine lacks"] + missing})
        else:
            ver = run(cli + ["core", "list"])[1]
            root = str(ROOT).replace("\\", "/")
            rel = lambda l: l.replace("\\", "/").replace(root + "/", "")  # noqa: E731
            sketch_warn = [rel(l) for l in lines if "warning" in l and "firmware/gripper" in l.replace("\\", "/")]
            lib_warn = sorted({re.sub(r"^.*/libraries/", "libraries/", rel(l)) for l in lines
                               if "warning" in l and "firmware/gripper" not in l.replace("\\", "/")})
            gates.append({"name": "arduino-cli compile", "cmd": compile_cmd, "exit": rc,
                          "summary": [l for l in lines if l.startswith(("Sketch uses", "Global variables"))] or lines[-3:],
                          "sketch_warnings": sketch_warn, "library_warnings": lib_warn,
                          "core": [l for l in ver if l.startswith("esp32:esp32")]})
    else:
        gates.append({"name": "arduino-cli compile", "cmd": compile_cmd, "exit": None,
                      "summary": ["not run: arduino-cli not found"]})
    rc, lines = run([sys.executable, "firmware/gripper/test/run_host_tests.py"])
    gates.append({"name": "host FSM test", "cmd": "python firmware/gripper/test/run_host_tests.py", "exit": rc,
                  "summary": [l for l in lines if l.startswith(("PASS", "FAIL", "rows covered", "INFO"))]})
    rc, lines = run([sys.executable, "-m", "pytest", "analysis/gripper/firmware_sim", "analysis/gripper/controls", "-q",
                    "-p", "no:cacheprovider"])
    gates.append({"name": "simulation pytest", "cmd": "python -m pytest analysis/gripper/firmware_sim analysis/gripper/controls -q", "exit": rc,
                  "summary": [re.sub(r" in [0-9.]+s( \([0-9:]+\))?", "", l.strip("= ")) for l in lines[-1:]]})
    out = {"gates": gates}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results/gates.json").write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    for g in gates:
        print(g["name"], "exit", g["exit"], g["summary"][-1] if g["summary"] else "")
    # A compile that could not run is reported, not failed: the conducting session compiles on a workstation.
    return 0 if all(g["exit"] in (0, None) for g in gates) else 1


if __name__ == "__main__":
    sys.exit(main())
