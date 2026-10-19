import copy
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import margins


def test_every_row_has_evidence_or_names_missing_figure():
    result = margins.run()
    assert len(result["rows"] + result["faults"]) == 34
    for row in result["rows"]:
        assert margins.validate_uncertainty(row)
        assert "not stated" not in row["uncertainty_source"].lower()
        for component in row["uncertainty_components"]:
            assert component["input"]
            assert component["source"]
            if component["band"] is None:
                assert component["source"].startswith("missing:")


def test_positive_missing_uncertainty_blocks_order_gate():
    result = margins.run()
    missing = [row for row in result["rows"] if row["margin"] > 0 and row["missing_figures"]]
    assert missing
    assert all(row["status"] == margins.UNEVIDENCED for row in missing)
    block = margins.order_block(result)
    assert "DO NOT ORDER" in block
    assert all("`%s`" % row["id"] in block for row in missing)


def test_literal_uncertainty_mutation_is_rejected():
    row = copy.deepcopy(margins.run()["rows"][0])
    row["uncertainty"] = 0.1
    with pytest.raises(AssertionError, match="endpoint sensitivities"):
        margins.validate_uncertainty(row)


def test_deleting_required_extreme_is_rejected():
    row = copy.deepcopy(next(x for x in margins.run()["rows"] if x["id"] == "servo-voltage-max"))
    row["extreme_inputs"] = []
    with pytest.raises(AssertionError, match="neither uncertainty components nor extreme inputs"):
        margins.validate_uncertainty(row)


def test_loop_cases_are_readable():
    rows = {row["id"]: row for row in margins.run()["rows"]}
    for row_id in ("loop-phase", "loop-gain"):
        case = rows[row_id]["case"]
        assert isinstance(case, str)
        assert all(word in case for word in ("Vin", "load", "bulk", "ceramic", "ESR", "crossover"))


def test_inputs_are_recorded_without_a_declared_copy():
    for row in margins.run()["rows"]:
        assert row["observed_inputs"], row["id"]
        assert "declared_inputs" not in row
        assert "recorded_inputs" not in row


def test_missing_figures_are_specific_and_grouped_once():
    result = margins.run()
    block = margins.order_block(result)
    for row in result["rows"]:
        for item in row["uncertainty_components"]:
            if item.get("class") != "missing":
                continue
            assert item["part"]
            assert item["parameter"]
            assert item["where"]
            assert item["source"] != "missing: quote or measure the error band"
    keys = {
        (item["part"], item["parameter"], item["where"])
        for row in result["rows"]
        for item in row["uncertainty_components"]
        if item.get("class") == "missing"
    }
    assert block.count("### Missing figures by part") == 1
    assert all(block.count("**%s:** %s" % key[:2]) == 1 for key in keys)


def test_input_evidence_mutation_names_row_and_input():
    row = copy.deepcopy(margins.run()["rows"][0])
    removed = row["observed_inputs"].pop()
    assert removed in row["input_evidence"]


def test_toleranced_input_cannot_be_marked_exact():
    component = {
        "input": "RS1 resistance",
        "class": "exact",
        "constant": "rs1_tol",
        "reason": "nominal value",
    }
    with pytest.raises(AssertionError, match="rs1_tol.*tolerance"):
        margins.validate_input_class(component)


def test_quoted_sensitivity_is_recomputed_from_band():
    row = copy.deepcopy(next(x for x in margins.run()["rows"] if x["id"] == "shunt-power"))
    row["uncertainty_components"][0]["sensitivity"] = 0.123
    row["uncertainty"] = 0.123
    with pytest.raises(AssertionError, match="endpoint recomputation.*RS1"):
        margins.validate_uncertainty(row)


def test_generic_missing_entry_is_rejected():
    item = copy.deepcopy(margins.run()["rows"][0]["uncertainty_components"][0])
    item["source"] = "missing: quote or measure the error band"
    with pytest.raises(AssertionError, match="generic missing"):
        margins.validate_input_class(item)


def test_quoted_tolerance_changes_exactly_declared_rows(monkeypatch):
    before = margins.run()
    listed = {
        row["id"]
        for row in before["rows"]
        if any(item.get("constant") == "rs1_tol" for item in row["uncertainty_components"])
    }
    original = margins.cm.K.C["rs1_tol"]["value"]
    monkeypatch.setitem(margins.cm.K.C["rs1_tol"], "value", original * 2)
    after = margins.run()
    changed = {
        old["id"]
        for old, new in zip(before["rows"], after["rows"])
        if old["uncertainty"] != new["uncertainty"] or old["demand"] != new["demand"]
    }
    assert listed == {"shunt-power"}
    assert changed == {"current-error", "shunt-power"}
