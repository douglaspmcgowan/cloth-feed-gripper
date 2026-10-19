"""Behavior and rejection tests for the limit-lead fault solver."""

import copy

import pytest

import fault_limit
import netmodel


def model():
    return netmodel.NetModel(copy.deepcopy(netmodel.load_design()))


def test_proposed_resistor_power_is_its_own_branch_power():
    result = fault_limit.proposed()
    for row in result["parts"]:
        if row["part"].startswith("R"):
            assert row["power_basis"] == "branch"


def test_direct_clamp_is_source_limited_and_prevents_met():
    ratings = {name: {"value": 100.0, "unit": "A", "source": "test"}
               for name in ("D5", "R17", "R18", "controller pin", "+3V3 rail")}
    result = fault_limit.analyze(ratings=ratings)
    clamp = next(row for row in result["parts"] if row["part"] == "D5")
    assert clamp["power_W"] == "not evidenced"
    assert clamp["power_basis"] == "source-limited"
    assert result["status"] != "met"
    assert "D5" in result["action"]


def test_missing_entry_pin_names_pin():
    edited = model()
    del edited.parts["J4"]["pins"]["3"]
    with pytest.raises(ValueError, match=r"J4\.3"):
        fault_limit.analyze(edited)


def test_unknown_reached_kind_names_part_and_net():
    edited = model()
    edited.parts["X99"] = {"ref": "X99", "sym": "Mystery", "value": "?",
                            "pins": {"1": "LIM_SIG", "2": "NOWHERE"}}
    with pytest.raises(ValueError, match=r"X99.*LIM_SIG"):
        fault_limit.analyze(edited)


def test_floating_network_names_source_net():
    edited = model()
    del edited.parts["D5"]
    del edited.parts["R17"]
    del edited.parts["R18"]
    with pytest.raises(ValueError, match=r"LIM_SIG.*no path|no path.*LIM_SIG"):
        fault_limit.analyze(edited)
