"""Build and run the host FSM test with g++ (no Arduino core), on Linux, macOS or Windows (MinGW g++).
Same build as run_host_tests.sh. Run from anywhere; extra arguments go to the test (e.g. --table):
    python firmware/gripper/test/run_host_tests.py
Exit code = the test's exit code (0 = every check passed)."""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent
SOURCES = [HERE / "test_fsm.cpp"] + [SRC / n for n in ("fsm.cpp", "force_ctrl.cpp", "motion.cpp", "events.cpp", "fsr_filter.cpp",
                                                        "protocol.cpp")]


def main(argv):
    exe = Path(tempfile.gettempdir()) / ("gripper_test_fsm" + (".exe" if sys.platform == "win32" else ""))
    cmd = ["g++", "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", f"-I{SRC}", "-o", str(exe)]
    cmd += [str(s) for s in SOURCES] + ["-lm"]
    b = subprocess.run(cmd)
    if b.returncode:
        return b.returncode
    return subprocess.run([str(exe)] + argv).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
