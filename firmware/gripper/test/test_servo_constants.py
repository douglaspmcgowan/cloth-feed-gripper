"""config.h servo constants must match the built servo (parts.json servo_model) per params.json, actuators.csv, actuation_trade.json."""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "firmware" / "gripper" / "config.h"
KGCM_TO_NM = 0.0980665


def _load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def _defs():
    out = {}
    for m in re.finditer(r"^#define\s+(\w+)\s+(-?[0-9.]+)\b", CONFIG.read_text(encoding="utf-8"), re.M):
        out[m.group(1)] = float(m.group(2))
    return out


def _model():
    return _load("cad/gripper/out/parts.json")["servo_model"]


def _row(model_id):
    with (ROOT / "docs/gripper/research/actuators.csv").open(encoding="utf-8", newline="") as f:
        return next(r for r in csv.DictReader(f) if r["id"] == model_id)


def _servo():
    return _load("cad/gripper/params.json")["servo"]["models"][_model()]


def test_header_names_built_servo():
    text = CONFIG.read_text(encoding="utf-8")
    block = text.split("// Servo (default actuator):", 1)[1].split("\n", 1)[0]
    assert _model() in block
    other = [m for m in _load("cad/gripper/params.json")["servo"]["models"] if m != _model()]
    assert not any(o in block for o in other)


def test_stall_torque():
    s = _servo()
    nm = s["stall_torque_kgcm"]["6.5V"] * KGCM_TO_NM
    assert abs(_defs()["SERVO_STALL_NM"] - nm) < 0.002


def test_stall_current():
    row = _row(_servo()["id"])
    rows = _load("analysis/gripper/actuation/results/actuation_trade.json")["decision"]["rows"].values()
    sizing = next(r["I_stall_sizing_A"] for r in rows if _model() in r["model"])
    assert abs(_defs()["SERVO_STALL_A"] - sizing) < 0.01
    assert _defs()["SERVO_STALL_A"] >= float(row["stall_current_A"])


def test_speed():
    row = _row(_servo()["id"])
    lo, hi = float(row["speed_low_s_per_60deg"]), float(row["speed_high_s_per_60deg"])
    v_lo, v_hi = float(row["torque_low_at_V"]), float(row["torque_high_at_V"])
    t = lo + (hi - lo) * (_servo()["rail_V"] - v_lo) / (v_hi - v_lo)
    assert abs(_defs()["SERVO_SPEED_DPS"] - 60.0 / t) < 1.0
