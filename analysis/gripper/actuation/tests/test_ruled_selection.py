"""Pin Douglas's held selections while keeping refreshed rankings observable."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def test_ruled_actuators_are_distinct_from_computed_rank():
    params = json.loads((ROOT / "cad/gripper/params.json").read_text(encoding="utf-8"))
    result = json.loads((ROOT / "analysis/gripper/results/payload_torque.json").read_text(encoding="utf-8"))
    selection = params["ruled_selection"]
    recommendation = result["recommendation"]
    assert recommendation["primary"] == selection["primary_actuator"]["id"] == "A17"
    assert recommendation["backup"] == selection["backup_actuator"]["id"] == "A19"
    assert recommendation["computed_rank"] == result["runs"]["r40_design"]["trade_vendor_consistent"]["rank"]
    assert recommendation["computed_top"] == recommendation["computed_rank"][0] == "A39"
    for role, actuator in (("primary", "A17"), ("backup", "A19")):
        check = result["selected_actuator_R19_check"][role]
        assert check["actuator"] == actuator
        assert check["limit_s"] == params["grip"]["close_time_max_s"] == 0.75
        assert check["passes"] is True


def test_ruled_concept_keeps_the_computed_pugh_rank():
    result = json.loads((ROOT / "docs/gripper/figures/concept_numbers.json").read_text(encoding="utf-8"))
    assert result["selected_concept"] == "C0"
    assert result["computed_rank"] == result["pugh"]["rank"] == ["C3b", "C1", "C0"]
    assert result["computed_top"] == "C3b"
    assert result["selected_concept_R19_check"]["concept"] == "C0"
    assert result["selected_concept_R19_check"]["limit_s"] == 0.75
    assert result["selected_concept_R19_check"]["passes"] is True
