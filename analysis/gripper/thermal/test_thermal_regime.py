"""Tests for the 30-minute case-temperature regime classifier."""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import thermal as th  # noqa: E402


def results() -> dict:
    return json.loads((th.OUT_DIR / "thermal.json").read_text(encoding="utf-8"))


def predictions(data: dict, ambient: int = 25, backoff: str = "on") -> tuple[float, float]:
    rows = data["r26_verdict_table"]
    selected = [
        row for row in rows
        if row["reading"] == "high" and row["ambient_C"] == ambient and row["backoff"] == backoff
    ]
    continuous = next(row["case_30min_C"] for row in selected if row["conduction"] == "continuous")
    discontinuous = next(row["case_30min_C"] for row in selected if row["conduction"] == "discontinuous")
    return continuous, discontinuous


def classify(observed: float, data: dict | None = None, ambient: int = 25) -> dict:
    data = data or results()
    continuous, discontinuous = predictions(data, ambient)
    return th.classify_30min_regime(
        observed,
        ambient,
        True,
        continuous,
        discontinuous,
        data["acceptance"]["case_temperature_expanded_uncertainty_C"],
    )


def test_classifier_required_examples():
    continuous, discontinuous = predictions(results())
    assert classify(55.0)["outcome"] == "indeterminate"
    assert classify(continuous)["outcome"] == "continuous"
    assert classify(discontinuous)["outcome"] == "discontinuous"


def test_out_of_range_ambient_is_refused_with_domain_reason():
    verdict = th.classify_30min_regime(
        55.0, 10.0, True, 37.2, 70.3, th.CASE_TEMPERATURE_U_C
    )
    assert verdict["outcome"] == "refused"
    assert "model domain" in verdict["reason"]


def test_classify_command_uses_entered_ambient(monkeypatch, capsys):
    calls = []

    def prediction(ambient, conduction, backoff=True):
        calls.append((ambient, conduction, backoff))
        return ambient + {"continuous": 10.0, "discontinuous": 40.0}[conduction]

    monkeypatch.setattr(th, "model_30min_prediction", prediction)
    assert th.classify_command(32.0, 42.0, True) == 0
    limits = {round(32.0 - th.AMBIENT_TEMPERATURE_U_C, 3), 32.0,
              round(32.0 + th.AMBIENT_TEMPERATURE_U_C, 3)}
    assert {round(call[0], 3) for call in calls} == limits
    output = capsys.readouterr().out
    assert "continuous prediction:" in output


def test_supported_ambient_range_is_not_widened():
    expected = (20.0 + th.AMBIENT_TEMPERATURE_U_C, 40.0 - th.AMBIENT_TEMPERATURE_U_C)
    assert th.AMBIENT_RANGE_C == pytest.approx(expected)
    for ambient in (20.0, 40.0):
        verdict = th.classify_30min_regime(40.0, ambient, True, 40.0, 70.0, 1.0)
        assert verdict["outcome"] == "refused"


def test_ambient_uncertainty_has_its_own_representativeness_term():
    assert th.AMBIENT_REPRESENTATIVENESS_LIMIT_C == 0.9
    assert th.AMBIENT_TEMPERATURE_U_C != th.CASE_TEMPERATURE_U_C
    expected = 2.0 * (sum(value ** 2 for value in (
        th.AMBIENT_CALIBRATION_U_C,
        th.AMBIENT_RESOLUTION_U_C,
        th.AMBIENT_REPRESENTATIVENESS_U_C,
    ))) ** 0.5
    assert th.AMBIENT_TEMPERATURE_U_C == pytest.approx(expected)


def test_refusal_prints_no_predictions_or_r26(capsys):
    assert th.classify_command(18.0, 35.0, True) == 4
    output = capsys.readouterr().out
    assert "outcome: refused (outside supported range:" in output
    assert "prediction:" not in output
    assert "R26 band:" not in output


def test_ambient_uncertainty_can_make_result_indeterminate(monkeypatch, capsys):
    def prediction(ambient, conduction, backoff=True):
        offset = {"continuous": 10.0, "discontinuous": 16.0}[conduction]
        return 3.0 * (ambient - 32.0) + 32.0 + offset

    monkeypatch.setattr(th, "model_30min_prediction", prediction)
    assert th.classify_command(32.0, 42.0, True) == 3
    capsys.readouterr()
    monkeypatch.setattr(th, "AMBIENT_TEMPERATURE_U_C", 0.0)
    assert th.classify_command(32.0, 42.0, True) == 0


def test_generated_table_is_direct_model_evaluation():
    for row in results()["acceptance"]["regime_table"]:
        if row["ambient_C"] in (20.0, 30.0, 35.0):
            for conduction in ("continuous", "discontinuous"):
                expected = th.model_30min_prediction(row["ambient_C"], conduction)
                assert row["predictions"][conduction] == pytest.approx(expected)


def test_note_rejects_retired_case_bead_phrase():
    note = th.P_NOTE.read_text(encoding="utf-8")
    assert "Ø1-hole case thermocouple" not in note
    assert "case bead on the aluminium shell" in note
    assert "C3 Ø1-hole PETG-mount reading" in note


def test_classify_cli_writes_no_files():
    before = {
        path: path.stat().st_mtime_ns for path in th.OUT_DIR.iterdir() if path.is_file()
    }
    command = [
        sys.executable, str(HERE / "thermal.py"), "--classify", "--ambient", "22",
        "--reading", "35.0",
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert completed.returncode in {0, 2, 3}
    assert "outcome:" in completed.stdout
    after = {
        path: path.stat().st_mtime_ns for path in th.OUT_DIR.iterdir() if path.is_file()
    }
    assert before == after


def test_classify_cli_forces_utf8_output():
    command = [
        sys.executable, str(HERE / "thermal.py"), "--classify", "--ambient", "22",
        "--reading", "35.0",
    ]
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "cp1252"
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )
    assert completed.returncode in {0, 2, 3}
    assert "outcome:" in completed.stdout
    assert "°" in completed.stdout


def test_prediction_mutation_changes_outcome():
    data = results()
    continuous, _ = predictions(data)
    assert classify(continuous, data)["outcome"] == "continuous"
    changed = copy.deepcopy(data)
    row = next(
        row for row in changed["r26_verdict_table"]
        if row["reading"] == "high" and row["ambient_C"] == 25
        and row["backoff"] == "on" and row["conduction"] == "continuous"
    )
    row["case_30min_C"] += 5.0
    assert classify(continuous, changed)["outcome"] == "indeterminate"


def test_uncertainty_is_test_plan_value_and_tp07_rounding():
    source = json.loads(th.P_TEST_PLAN_RESULTS.read_text(encoding="utf-8"))
    assert th.CASE_TEMPERATURE_U_C == source["budgets"]["case_temp_C"]["U_k2"]
    tp07 = th.P_TP07.read_text(encoding="utf-8")
    assert f"U = {th.CASE_TEMPERATURE_U_C:.1f} °C" in tp07
    assert "--u 1.639" in tp07


def test_rendered_section_uses_classifier_inputs_and_measurement_locations():
    data = results()
    block = th.render_acceptance_table(
        data["acceptance"]["rows"], data["acceptance"], data["r26_verdict_table"]
    )
    assert "exposed aluminium shell" in block
    assert "C3 Ø1 hole measures the PETG mount" in block
    assert "indeterminate" in block
    row = data["acceptance"]["regime_table"][0]
    assert f"| {row['ambient_C']:.0f} | {row['predictions']['continuous']:.1f} |" in block
    changed = copy.deepcopy(data["acceptance"])
    changed["case_temperature_expanded_uncertainty_C"] = 2.0
    changed_block = th.render_acceptance_table(changed["rows"], changed, data["r26_verdict_table"])
    assert "U = 2.000 °C" in changed_block
    assert "58.0 °C" in changed_block and "62.0 °C" in changed_block


def test_rendered_r26_limits_are_conservative_and_shared():
    data = results()
    block = th.render_acceptance_table(
        data["acceptance"]["rows"], data["acceptance"], data["r26_verdict_table"]
    )
    assert "PASS at or below 58.3 °C" in block
    assert "FAIL at or above 61.7 °C" in block
    limits = th.r26_thresholds()
    assert limits["exact_pass_limit_C"] == pytest.approx(58.360640369)
    assert limits["exact_fail_limit_C"] == pytest.approx(61.639359631)
    assert limits["pass_at_or_below_C"] == 58.3
    assert limits["fail_at_or_above_C"] == 61.7
    committed = data["acceptance"]["r26_thresholds"]
    assert committed["pass_at_or_below_C"] == limits["pass_at_or_below_C"]
    assert committed["fail_at_or_above_C"] == limits["fail_at_or_above_C"]
    assert committed["exact_pass_limit_C"] == pytest.approx(limits["exact_pass_limit_C"])
    assert "derivation" in committed


def note_r26_rule(block: str) -> tuple[float, float]:
    match = re.search(r"PASS at or below ([0-9.]+) °C; FAIL at or above ([0-9.]+) °C", block)
    assert match, "section 0 states no R26 thresholds"
    return float(match.group(1)), float(match.group(2))


@pytest.mark.parametrize(
    ("reading", "expected"),
    [(58.30, "PASS"), (58.31, "INDETERMINATE"), (58.36, "INDETERMINATE"),
     (61.64, "INDETERMINATE"), (61.69, "INDETERMINATE"), (61.70, "FAIL")],
)
def test_cli_r26_band_matches_note_rule(capsys, reading, expected):
    data = results()
    block = th.render_acceptance_table(
        data["acceptance"]["rows"], data["acceptance"], data["r26_verdict_table"]
    )
    pass_limit, fail_limit = note_r26_rule(block)
    note_band = (
        "PASS" if reading <= pass_limit
        else "FAIL" if reading >= fail_limit
        else "INDETERMINATE"
    )
    assert th.classify_command(22.0, reading, True) in {0, 2, 3}
    cli_band = capsys.readouterr().out.split("R26 band: ")[1].split()[0]
    assert cli_band == note_band == expected


def test_assumed_ambient_term_is_labelled_in_note_and_cli(capsys):
    label = "assumed, unmeasured, until TP-07's third ambient channel measures it"
    data = results()
    block = th.render_acceptance_table(
        data["acceptance"]["rows"], data["acceptance"], data["r26_verdict_table"]
    )
    assert label in block
    assert th.classify_command(22.0, 35.0, True) in {0, 2, 3}
    assert label in capsys.readouterr().out


def test_cli_accepted_ambient_range_matches_section_zero(capsys):
    data = results()
    block = th.render_acceptance_table(
        data["acceptance"]["rows"], data["acceptance"], data["r26_verdict_table"]
    )
    range_text = th.accepted_ambient_range_text()
    assert range_text == "21.560–38.440 °C"
    assert f"The accepted ambient range is {range_text}, so" in block
    assert th.classify_command(22.0, 35.0, True) in {0, 2, 3}
    assert f"accepted ambient range: {range_text}\n" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("reading", "expected_outcome", "expected_band"),
    [(62.0, "continuous", "FAIL"), (58.0, "discontinuous", "PASS")],
)
def test_r26_band_depends_only_on_reading(
    monkeypatch, capsys, reading, expected_outcome, expected_band
):
    def prediction(ambient, conduction, backoff=True):
        return reading if conduction == expected_outcome else reading + 30.0

    monkeypatch.setattr(th, "model_30min_prediction", prediction)
    th.classify_command(32.0, reading, True)
    output = capsys.readouterr().out
    assert f"outcome: {expected_outcome}" in output
    assert f"R26 band: {expected_band}" in output


def test_safety_limit_is_not_exported_as_regime_boundary():
    data = results()
    assert "regime_case_boundary_C" not in data["acceptance"]


def test_no_exported_string_contains_retired_phrase():
    def strings(value):
        if isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)
        elif isinstance(value, str):
            yield value

    assert all("safe with a limit" not in value for value in strings(results()))
