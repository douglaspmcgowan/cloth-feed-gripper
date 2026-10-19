"""Operational-verdict and generated commissioning-instruction tests."""
from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import thermal as th  # noqa: E402


def results() -> dict:
    return json.loads((th.OUT_DIR / "thermal.json").read_text(encoding="utf-8"))


def test_console_last_line_is_eight_row_verdict():
    data = results()
    last = (th.OUT_DIR / "thermal_stdout.txt").read_text(encoding="utf-8").splitlines()[-1]
    assert last == "VERDICT: " + th.render_acceptance_verdict(data["acceptance"]["rows"])


def test_continuous_failure_revokes_acceptance():
    rows = copy.deepcopy(results()["acceptance"]["rows"])
    row = next(row for row in rows if row["conduction"] == "continuous")
    row["backoff_margin_A"] = -0.001
    assert "not acceptable" in th.render_acceptance_verdict(rows)


def test_every_row_passes_is_reported():
    rows = copy.deepcopy(results()["acceptance"]["rows"])
    for row in rows:
        row["backoff_margin_A"] = 0.001
    assert "all eight acceptance rows pass" in th.render_acceptance_verdict(rows)


def test_failed_row_never_uses_old_safe_with_limit_headline():
    rows = results()["acceptance"]["rows"]
    assert any(row["backoff_margin_A"] < 0 for row in rows)
    assert "safe with a limit" not in th.render_acceptance_verdict(rows)


def test_generated_regime_condition_uses_predictions_and_separate_r26_bands():
    data = results()
    acceptance = data["acceptance"]
    block = th.render_acceptance_table(acceptance["rows"], acceptance)
    uncertainty = acceptance["case_temperature_expanded_uncertainty_C"]
    limits = th.r26_thresholds(uncertainty)
    assert f"PASS at or below {limits['pass_at_or_below_C']:.1f} °C" in block
    assert f"FAIL at or above {limits['fail_at_or_above_C']:.1f} °C" in block
    assert "exposed aluminium shell" in block
    assert "C3 Ø1 hole measures the PETG mount" in block
    assert "do not operate" in block
    assert "1. Back-off is enabled" in block
    assert "2. At least 5.0 N per pad" in block
    assert "3. Stop at 30 minutes" in block


def test_generated_instrument_error_is_half_smallest_passing_margin():
    data = results()
    acceptance = data["acceptance"]
    smallest = min(row["backoff_margin_A"] for row in acceptance["rows"] if row["backoff_margin_A"] >= 0)
    assert acceptance["maximum_total_instrument_error_A"] == pytest.approx(smallest / 2)
    block = th.render_acceptance_table(acceptance["rows"], acceptance)
    assert f"≤{smallest / 2:.3f} A" in block


def test_all_python_text_io_declares_encoding_and_lf_for_writes():
    for path in HERE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr in {"read_text", "write_text", "open"}:
                keywords = {keyword.arg: keyword.value for keyword in node.keywords}
                assert "encoding" in keywords, f"{path}:{node.lineno} lacks encoding"
            if node.func.attr == "write_text":
                assert "newline" in keywords, f"{path}:{node.lineno} lacks newline"
                assert isinstance(keywords["newline"], ast.Constant) and keywords["newline"].value == "\n"


def test_exported_verdict_is_the_rendered_headline():
    data = results()
    rendered = th.render_acceptance_verdict(data["acceptance"]["rows"])
    assert data["verdict"]["class"] == rendered


def test_positive_discontinuous_margins_render_acceptance():
    rows = copy.deepcopy(results()["acceptance"]["rows"])
    for row in rows:
        row["backoff_margin_A"] = 0.001
    assert "discontinuous conduction: acceptable" in th.render_acceptance_verdict(rows)
