"""Properties of the netlist-derived fault network."""

import copy

import pytest

import fault_limit
import netmodel


def model():
    return netmodel.NetModel(copy.deepcopy(netmodel.load_design()))


def assert_properties(result, edited):
    refs = set(edited.parts)
    emitted = [row["part"] for row in result["parts"] if row["part"] in refs]
    assert len(emitted) == len(set(emitted))
    assert set(emitted) <= refs
    for row in result["parts"]:
        if row["part"] in refs and edited.parts[row["part"]]["sym"] == "Device:R":
            resistance = netmodel.resistance_ohm(edited.parts[row["part"]]["value"])
            assert row["power_W"] == pytest.approx(row["current_A"] ** 2 * resistance, rel=2e-6)
    assert all(abs(residual) <= 1e-9 for residual in result["kcl_A"].values())


@pytest.mark.parametrize("edit", ["as_drawn", "pin", "swap", "delete", "rename", "unequal"])
def test_netlist_edits_have_physical_properties(edit):
    edited = model()
    if edit == "pin":
        edited.move_pin("J4", 3, "LIM_IN")
    elif edit == "swap":
        edited.parts["R18"]["pins"], edited.parts["D5"]["pins"] = (
            edited.parts["D5"]["pins"], edited.parts["R18"]["pins"])
    elif edit == "delete":
        del edited.parts["D5"]
    elif edit == "rename":
        for part in edited.parts.values():
            part["pins"] = {pin: ("RENAMED" if net == "LIM_SIG" else net)
                            for pin, net in part["pins"].items()}
    elif edit == "unequal":
        edited.parts["R17"]["value"] = "8.2k"
        edited.parts["R18"]["value"] = "2.2k"
    result = fault_limit.analyze(edited)
    assert_properties(result, edited)
    if edit == "delete":
        assert "D5" not in [row["part"] for row in result["parts"]]
    if edit == "rename":
        baseline = fault_limit.analyze(model())
        assert [row["current_A"] for row in result["parts"]] == [
            row["current_A"] for row in baseline["parts"]]


def test_kcl_property_catches_wrong_branch_current():
    edited = model()
    del edited.parts["D5"]
    edited.move_pin("R18", 1, "MID")
    edited.add_resistor("RX", "1k", "LIM_SIG", "MID")
    result = fault_limit.analyze(edited)
    assert result["kcl_A"]["MID"] == pytest.approx(0.0, abs=1e-9)
    next(b for b in result["branches"] if b["to"] == "MID")["current_A"] += 0.001
    signed = [b["current_A"] if b["to"] == "MID" else -b["current_A"]
              for b in result["branches"] if "MID" in (b["from"], b["to"])]
    assert abs(sum(signed)) > 1e-9
