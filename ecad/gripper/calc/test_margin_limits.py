"""Margin row limits read their named constants; evidence carries the constants' source tags."""
import ast
from pathlib import Path

import _common as cm
import margins
import power_budget
import pytest


def test_row_limits_read_their_named_constants(monkeypatch):
    monkeypatch.setitem(cm.K.C["ctrl_lag_budget_s"], "value", 0.061)
    monkeypatch.setitem(cm.K.C["harness_plug_band_v"], "value", (6.30, 6.70))
    monkeypatch.setitem(cm.K.C["harness_force_error_limit_n"], "value", 0.2)
    monkeypatch.setitem(cm.K.C["fsr_adc_droop_limit_mv"], "value", 2)
    rows = {row["id"]: row for row in margins.run()["rows"]}
    assert rows["filter-delay"]["limit"] == 0.061
    assert rows["plug-band-low"]["demand"] == 6.30
    assert rows["plug-band-high"]["limit"] == 6.70
    assert rows["force-reading-error"]["limit"] == 0.2
    assert rows["adc-charge"]["limit"] == 2


def test_input_evidence_carries_constant_source_tag():
    for row in margins.run()["rows"]:
        for name, item in row["input_evidence"].items():
            assert "source_tag" in item, (row["id"], name)
            expected = cm.K.C[name]["tag"] if name in cm.K.C else None
            assert item["source_tag"] == expected, (row["id"], name)


def test_new_row_limits_read_their_named_constants(monkeypatch):
    patched = {
        "buck_junction_rise_limit_c": 86.0,
        "trace_temp_rise_limit_c": 11.0,
        "trace_servo_drop_limit_mv": 101.0,
        "ina_current_error_limit_a": 0.06,
        "buck_phase_margin_min_deg": 46.0,
        "buck_gain_margin_min_db": 7.0,
        "adapter_min_v": 13.0,
        "adapter_current_a": 3.5,
    }
    for name, value in patched.items():
        monkeypatch.setitem(cm.K.C[name], "value", value)
    rows = {row["id"]: row for row in margins.run()["rows"]}
    assert rows["buck-thermal"]["limit"] == 86.0
    assert rows["trace-temperature"]["limit"] == 11.0
    assert rows["trace-drop"]["limit"] == 101.0
    assert rows["current-error"]["limit"] == 0.06
    assert rows["loop-phase"]["demand"] == 46.0
    assert rows["loop-gain"]["demand"] == 7.0
    assert rows["uvlo-range"]["limit"] == 13.0
    assert rows["adapter-current"]["limit"] == 3.5


def _number(node):
    return (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool))


def inline_numbers(source):
    """(row id, argument index) of each numeric literal in a _row limit or demand, or an overrides.get number default.

    A literal reaches a limit or demand directly, through a name bound to a number anywhere in the module
    (lim = 85 then limit=lim), or as a keyword argument (limit=85, demand=6)."""
    tree = ast.parse(source)
    numeric_names = {target.id for node in ast.walk(tree) if isinstance(node, ast.Assign) and _number(node.value)
                     for target in node.targets if isinstance(target, ast.Name)}
    found = []
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and getattr(call.func, "id", None) == "_row"):
            continue
        operands = [(index, call.args[index]) for index in (2, 3) if index < len(call.args)]
        operands += [(2 if item.arg == "limit" else 3, item.value) for item in call.keywords
                     if item.arg in ("limit", "demand")]
        for index, operand in operands:
            indices = {id(n) for node in ast.walk(operand) if isinstance(node, ast.Subscript) for n in ast.walk(node.slice)}
            for node in ast.walk(operand):
                if id(node) in indices:
                    continue
                if _number(node) or (isinstance(node, ast.Name) and node.id in numeric_names):
                    found.append((call.args[0].value, index))
                if (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "get"
                        and getattr(node.func.value, "id", None) == "overrides"
                        and any(_number(a) for a in node.args[1:])):
                    found.append((call.args[0].value, index))
    return found


def test_no_row_limit_or_demand_is_an_inline_number():
    source = Path(margins.__file__).read_text(encoding="utf-8")
    assert inline_numbers(source) == []


def test_inline_number_scan_catches_a_literal():
    assert inline_numbers('_row("x", "y", 85, d, "C", "c", "m")') == [("x", 2)]
    assert inline_numbers('_row("x", "y", a, 6, "C", "c", "m")') == [("x", 3)]
    assert inline_numbers('_row("x", "y", overrides.get("k", 3.0), d, "A", "c", "m")')
    assert inline_numbers('_row("x", "y", cm.v("k")[1], d[0], "A", "c", "m")') == []


def test_inline_number_scan_catches_a_name_bound_to_a_literal_and_a_keyword():
    assert inline_numbers('lim = 85\n_row("x", "y", lim, d, "C", "c", "m")') == [("x", 2)]
    assert inline_numbers('lim = 85\n_row("x", "y", demand=d, limit=lim, unit="C", case="c", source="m")') == [("x", 2)]
    assert inline_numbers('_row("x", "y", demand=d, limit=85, unit="C", case="c", source="m")') == [("x", 2)]
    assert inline_numbers('_row("x", "y", limit=c, demand=6, unit="C", case="c", source="m")') == [("x", 3)]
    assert inline_numbers('_row("x", "y", limit=cm.v("k"), demand=d[0], unit="C", case="c", source="m")') == []


def _headroom_demand(monkeypatch, dropout):
    monkeypatch.setitem(cm.K.C["mcp_dropout_max"], "value", dropout)
    rows = {row["id"]: row for row in margins.run()["rows"]}
    return rows["regulator-headroom"]["demand"]


def test_regulator_headroom_demand_is_ldo_minimum_input(monkeypatch):
    low = _headroom_demand(monkeypatch, 0.0)
    high = _headroom_demand(monkeypatch, 1.3)
    assert low == pytest.approx(cm.v("power_five_volt_rail_v"))
    assert high > low + 0.5
    pb = power_budget.run()
    assert high == pytest.approx(pb["ldo_min_input_V"])
    assert pb["ldo_min_input_V"] == pytest.approx(
        cm.v("power_five_volt_rail_v") + max(c["ldo_dropout_V"] for c in pb["esp_board_power"]))


def test_loop_margin_limits_have_one_home(monkeypatch):
    monkeypatch.setitem(cm.K.C["buck_gain_margin_min_db"], "value", 8.0)
    monkeypatch.setitem(cm.K.C["buck_phase_margin_min_deg"], "value", 50.0)
    rows = {row["id"]: row for row in margins.run()["rows"]}
    assert rows["loop-gain"]["demand"] == 8.0
    assert rows["loop-phase"]["demand"] == 50.0


def test_no_second_constant_carries_a_loop_margin():
    loop = [n for n, e in cm.K.C.items() if e["unit"] in ("deg", "dB") and "margin" in (n + e["note"]).lower()]
    by_unit = {}
    for n in loop:
        by_unit.setdefault(cm.K.C[n]["unit"], []).append(n)
    assert {u: len(v) for u, v in by_unit.items()} == {"deg": 1, "dB": 1}, by_unit
