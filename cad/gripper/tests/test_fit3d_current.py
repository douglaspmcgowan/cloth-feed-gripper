"""The committed 3D fit audit must describe the current CAD inputs."""
import json
import sys
from pathlib import Path

import pytest


GRIPPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRIPPER / "viewer_src"))
from fit3d_inputs import input_digest, kernel_versions


def test_fit3d_uses_current_inputs():
    result = json.loads((GRIPPER / "out" / "fit3d.json").read_text(encoding="utf-8"))
    assert result.get("input_digest_sha256") == input_digest(GRIPPER, result.get("kernel")), (
        "fit3d.json is stale; run uv run --with cadquery python cad/gripper/fit3d.py"
    )
    assert result.get("roll") and result.get("detail") and result.get("builds"), (
        "fit3d.json is incomplete; run uv run --with cadquery python cad/gripper/fit3d.py"
    )
    assert "roll_error" not in result


def test_fit3d_records_the_kernel_it_ran_on():
    result = json.loads((GRIPPER / "out" / "fit3d.json").read_text(encoding="utf-8"))
    kernel = result.get("kernel") or {}
    assert kernel.get("cadquery") and kernel.get("cadquery-ocp")
    installed = kernel_versions()
    if installed["cadquery"] != "missing":
        if installed != kernel:
            pytest.skip(f"fit3d.json was measured on {kernel}; rerun on {installed} or install that kernel")
