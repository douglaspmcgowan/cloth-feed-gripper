"""Static CAD overlaps follow named, dimensioned interface intent."""
import json
import sys
from pathlib import Path

import pytest


CAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CAD))
pytest.importorskip("cadquery")
import fit3d  # noqa: E402


def test_static_interfaces_match_declared_dimensions():
    fit3d._init()
    rows = fit3d.static_task(0)
    declarations = json.loads((CAD / "fit_requirements.json").read_text(encoding="utf-8"))["interface_intents"]
    assert rows
    for row in rows:
        classification, reason, intent = fit3d.static_intent(row, declarations)
        assert classification == "design", (row, reason)
        assert intent["source"]
    boss = next(row for row in rows if (row["a"], row["b"]) == ("housing", "servo"))
    assert boss["v"] > 4.0
    assert boss["finished_v"] == 0.0
    classification, reason, _ = fit3d.static_intent(rows[0], {})
    assert classification == "error"
    assert "no declared interface intent" in reason


@pytest.mark.parametrize("fault", ("clearance", "sampling", "overlap", "roll", "section"))
def test_verdict_rejects_invalid_measurements(fault):
    record = json.loads((CAD / "out/fit3d.json").read_text(encoding="utf-8"))
    assert fit3d.verdict_record(record)["pass"]
    spec = json.loads((CAD / "fit_requirements.json").read_text(encoding="utf-8"))
    pairs = {row["a"] + "|" + row["b"]: row for row in record["jaw_pairs"]}
    if fault == "clearance":
        pairs["horn|housing"]["d_min"] = spec["requirements"]["horn|housing"]["minimum_clearance_mm"] - 0.001
        expected = "horn|housing"
    elif fault == "sampling":
        key = "finger_a|knuckle_b"
        pairs[key]["d_min"] = spec["requirements"][key]["minimum_clearance_mm"] + spec["sampling"]["allowance_mm"][key] - 0.001
        expected = "sampling allowance"
    elif fault == "overlap":
        record["overlaps"].append({"a": "housing", "b": "undeclared pin", "cls": "error",
                                   "why": "no declared interface intent"})
        expected = "undeclared pin"
    elif fault == "roll":
        record["roll_error"] = "probe failure"
        expected = "roll audit failed"
    else:
        record["detail"].pop("horn|housing")
        expected = "required section evidence is missing"
    verdict = fit3d.verdict_record(record)
    assert not verdict["pass"]
    assert any(expected in reason for reason in verdict["reasons"])
