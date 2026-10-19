"""The tolerance stacks' CAD bindings equal params.json (follow-up 8, merge13).

Runs without cadquery: it only reads YAML and JSON. From the repository root or from cad/gripper/tests:

    python -m pytest -q cad/gripper/tests/test_tolstack_bindings.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TOLSTACK = REPO / "analysis" / "gripper" / "tolstack"
sys.path.insert(0, str(TOLSTACK))

from tolcalc.cad import validate_bindings  # noqa: E402


def test_basis_and_rev_b_bindings_match_params_json():
    errors = validate_bindings(TOLSTACK / "stacks" / "basis.yaml",
                               TOLSTACK / "stacks" / "rev_b.yaml",
                               REPO / "cad" / "gripper" / "params.json")
    assert errors == []
