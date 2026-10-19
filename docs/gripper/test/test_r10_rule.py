"""Consistency checks for the ruled R10 work-cell reach limit."""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def _load_test_plan():
    path = HERE / "test_plan.py"
    spec = importlib.util.spec_from_file_location("r10_test_plan", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_r10_limit_matches_cad_mass_in_all_documents():
    test_plan = _load_test_plan()
    fitcheck_path = ROOT / "cad" / "gripper" / "out" / "fitcheck.json"
    cad_mass = json.loads(fitcheck_path.read_text(encoding="utf-8"))["mass"]
    rule = test_plan.r10_work_cell_rule(cad_mass)

    documents = (
        ROOT / "docs" / "gripper" / "test" / "procedures" / "TP-14-work-cell.md",
        ROOT / "docs" / "gripper" / "DESIGN-BASIS.md",
        ROOT / "docs" / "gripper" / "RISK.md",
        ROOT / "cad" / "gripper" / "README.md",
    )
    assert all(path.resolve().is_relative_to(ROOT.resolve()) for path in documents)

    quoted_limits = []
    for path in documents:
        text = path.read_text(encoding="utf-8")
        match = re.search(
            r"(?:r_limit = |limits horizontal reach to \*\*)(\d+\.\d) mm from the shoulder_lift axis",
            text,
        )
        assert match, f"R10 COM reach limit missing from {path.relative_to(ROOT)}"
        quoted_limits.append(float(match.group(1)))

    expected_limit = round(43_720 / cad_mass["total_g_incl_cloth"], 1)
    assert quoted_limits == pytest.approx([expected_limit] * len(documents), abs=0.05)
    assert rule["com_limit_mm"] == pytest.approx(43_720 / cad_mass["total_g_incl_cloth"])

    design_basis = (ROOT / "docs" / "gripper" / "DESIGN-BASIS.md").read_text(encoding="utf-8")
    r10_row = next(line for line in design_basis.splitlines() if line.startswith("| R10 |"))
    assert f"**{rule['mass_moment_gmm']:,.0f} g·mm**" in r10_row
    assert f"Stretch goal: ≤ {rule['stock_loading_gmm']:,.0f} g·mm" in r10_row
