"""Regression tests for generated tolerance-note drift."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tolstack  # noqa: E402
from tolcalc import report  # noqa: E402


RESULTS = ROOT / "results"
NOTE = ROOT.parents[2] / "docs" / "gripper" / "analysis" / "tolerance_stacks.md"


def _copy_generated(tmp_path: Path) -> tuple[Path, Path]:
    results = tmp_path / "results"
    shutil.copytree(RESULTS, results)
    note = tmp_path / "tolerance_stacks.md"
    note.write_text(NOTE.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    return results, note


def test_generated_number_drift_names_block_line_and_values(tmp_path):
    results, note = _copy_generated(tmp_path)
    text = note.read_text(encoding="utf-8")
    note.write_text(text.replace("99.996 %", "99.995 %", 1), encoding="utf-8", newline="\n")
    errors, _, _ = report.check_generated(results, note, ROOT)
    assert errors and "verdicts line" in errors[0]
    assert "99.995" in errors[0] and "99.996" in errors[0]


def test_deleted_generated_line_names_block_and_line(tmp_path):
    results, note = _copy_generated(tmp_path)
    text = note.read_text(encoding="utf-8")
    line = next(item for item in text.splitlines() if item.startswith("| T02 |"))
    note.write_text(text.replace(line + "\n", "", 1), encoding="utf-8", newline="\n")
    errors, _, _ = report.check_generated(results, note, ROOT)
    assert errors and "verdicts line" in errors[0]
    assert "committed" in errors[0] and "generated" in errors[0]


def test_stack_change_without_regeneration_reports_digest(tmp_path):
    results, note = _copy_generated(tmp_path)
    root = tmp_path / "tolstack"
    shutil.copytree(ROOT / "stacks", root / "stacks")
    shutil.copytree(ROOT / "tolcalc", root / "tolcalc")
    shutil.copy2(ROOT / "tolstack.py", root / "tolstack.py")
    stack = next((root / "stacks").glob("*.yaml"))
    stack.write_text(stack.read_text(encoding="utf-8") + "# tolerance changed\n",
                     encoding="utf-8", newline="\n")
    errors, _, _ = report.check_generated(results, note, root)
    assert errors and "input digest drift" in errors[0]


def test_check_mode_writes_nothing(monkeypatch):
    def reject_write(*_args, **_kwargs):
        pytest.fail("--check attempted to write generated output")

    monkeypatch.setattr(report, "write_generated_text", reject_write)
    assert tolstack.cmd_check() == 0


def test_every_result_records_current_input_digest():
    expected = report.input_digest(ROOT)
    paths = sorted(path for path in RESULTS.rglob("*.json") if "_superseded" not in path.parts)
    assert paths
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        stored = payload.get("input_digest") if isinstance(payload, dict) else payload[-1].get("input_digest")
        assert stored == expected, f"{path}: input digest drift"


@pytest.mark.parametrize("field", ["verdict3", "own_verdict3", "verdict_decided"])
def test_stored_verdict_drift_names_file_field_and_values(tmp_path, field):
    results, note = _copy_generated(tmp_path)
    path = results / "T16.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    committed = payload[field]
    payload[field] = not committed if isinstance(committed, bool) else "fail"
    path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
    errors, _, checked = report.check_generated(results, note, ROOT)
    assert checked > 0
    assert errors and str(path) in errors[0] and field in errors[0]
    assert repr(payload[field]) in errors[0] and repr(committed) in errors[0]


def test_check_covers_every_top_level_stored_verdict(tmp_path):
    results, note = _copy_generated(tmp_path)
    expected = sum(
        "verdict3" in json.loads(path.read_text(encoding="utf-8"))
        for path in results.glob("*.json")
    )
    errors, _, checked = report.check_generated(results, note, ROOT)
    assert not errors
    assert checked == expected
