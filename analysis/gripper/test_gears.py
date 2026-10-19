import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import gears

ROOT = Path(__file__).resolve().parents[2]
RESULT = json.loads((ROOT / "analysis/gripper/results/gears.json").read_text(encoding="utf-8"))
SUBPROCESS_TIMEOUT_SECONDS = 600


def _assert_subprocess_timeouts(source):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    assignments = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    value = assignments["SUBPROCESS_TIMEOUT_SECONDS"]
    assert isinstance(value, ast.Constant) and value.value >= 600

    subprocess_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        direct_call = isinstance(owner, ast.Name) and owner.id == "subprocess" and node.func.attr in {"run", "check_output"}
        communicate = node.func.attr == "communicate" and isinstance(owner, ast.Call) and isinstance(owner.func, ast.Attribute) and owner.func.attr == "Popen"
        if direct_call or communicate:
            subprocess_calls.append(node)

    assert subprocess_calls
    for call in subprocess_calls:
        timeout = next((keyword.value for keyword in call.keywords if keyword.arg == "timeout"), None)
        assert timeout is not None, f"subprocess call on line {call.lineno} has no timeout"
        assert isinstance(timeout, ast.Name) and timeout.id == "SUBPROCESS_TIMEOUT_SECONDS", (
            f"subprocess call on line {call.lineno} does not use SUBPROCESS_TIMEOUT_SECONDS"
        )


def test_all_subprocess_calls_use_named_timeout():
    _assert_subprocess_timeouts(Path(__file__))


def test_generated_block_equals_json():
    note = (ROOT / "docs/gripper/analysis/gears.md").read_text(encoding="utf-8")
    begin, end = "<!-- GEARS-AS-DRAWN:BEGIN -->", "<!-- GEARS-AS-DRAWN:END -->"
    actual = note[note.index(begin):note.index(end) + len(end)]
    assert actual == gears.render_as_drawn_block(RESULT["as_drawn"])


def _outside_historical(note):
    begin, end = "<!-- GEARS-HISTORICAL:BEGIN -->", "<!-- GEARS-HISTORICAL:END -->"
    assert note.count(begin) == note.count(end) == 1
    return note[:note.index(begin)] + note[note.index(end) + len(end):]


def _assert_no_historical_recommendations(note):
    outside = _outside_historical(note)
    for stale in ("b 8", "8 mm printed face", "DS3218MG sizing"):
        assert stale not in outside


def test_historical_sizing_is_confined_to_appendix():
    note = (ROOT / "docs/gripper/analysis/gears.md").read_text(encoding="utf-8")
    _assert_no_historical_recommendations(note)


def test_historical_sentence_moved_out_of_appendix_fails():
    note = (ROOT / "docs/gripper/analysis/gears.md").read_text(encoding="utf-8")
    begin = "<!-- GEARS-HISTORICAL:BEGIN -->"
    moved = note.replace(begin, "The historical recommendation was b 8.\n" + begin, 1)
    with pytest.raises(AssertionError):
        _assert_no_historical_recommendations(moved)


def test_generated_downstream_block_equals_json():
    note = (ROOT / "docs/gripper/analysis/gears.md").read_text(encoding="utf-8")
    begin, end = "<!-- GEARS-DOWNSTREAM:BEGIN -->", "<!-- GEARS-DOWNSTREAM:END -->"
    actual = note[note.index(begin):note.index(end) + len(end)]
    assert actual == gears.render_downstream_block(RESULT["as_drawn"])
    assert f"b {RESULT['as_drawn']['geometry']['face_width_mm']:g} mm" in actual


def _run_with_params(tmp_path, mutate):
    params = json.loads((ROOT / "cad/gripper/params.json").read_text(encoding="utf-8"))
    mutate(params)
    copied = tmp_path / "params.json"
    copied.write_text(json.dumps(params), encoding="utf-8", newline="\n")
    out = tmp_path / "out"
    env = os.environ | {"GRIPPER_PARAMS": str(copied)}
    run = subprocess.run([sys.executable, "analysis/gripper/gears.py", "--out-dir", str(out)], cwd=ROOT, env=env,
                         text=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT_SECONDS)
    assert run.returncode == 0, run.stderr
    return json.loads((out / "gears.json").read_text(encoding="utf-8"))["as_drawn"]


def test_selected_servo_changes_stall_torque(tmp_path):
    changed = _run_with_params(tmp_path, lambda p: p["servo"].update(model="DSServo DS3218MG"))
    assert changed["mesh_torque_Nm"]["stall_6p5V"] != RESULT["as_drawn"]["mesh_torque_Nm"]["stall_6p5V"]


def test_face_width_changes_factor(tmp_path):
    changed = _run_with_params(tmp_path, lambda p: p["gear"].update(face_width=9.5))
    assert changed["checks"]["F_LC3"]["value"] != RESULT["as_drawn"]["checks"]["F_LC3"]["value"]
    assert gears.render_downstream_block(changed) != gears.render_downstream_block(RESULT["as_drawn"])


def test_text_io_calls_name_utf8_encoding():
    for source in (Path(gears.__file__), Path(__file__)):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
            if name not in {"read_text", "write_text", "open"}:
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            assert "encoding" in keywords, f"{source}:{node.lineno} {name} lacks encoding"


def test_warning_as_error_full_run(tmp_path):
    run = subprocess.run(
        [sys.executable, "-W", "error::RuntimeWarning", "analysis/gripper/gears.py", "--out-dir", str(tmp_path / "out")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    assert run.returncode == 0, run.stderr


def test_root_factor_rejects_nonphysical_notch_geometry():
    shift = 2.209172275375704
    unit = gears.geometry(1.0, 19, 25, shift, 0.25)
    invalid = gears.geometry(28.5 / unit["a_w"], 19, 25, shift, 0.25)
    with pytest.raises(ValueError, match=r"root-factor domain requires sFn > 0; got -"):
        gears.root_factors(invalid)


def test_results_contain_only_finite_numbers():
    def numbers(value):
        if isinstance(value, dict):
            for child in value.values():
                yield from numbers(child)
        elif isinstance(value, list):
            for child in value:
                yield from numbers(child)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            yield value

    assert all(__import__("math").isfinite(value) for value in numbers(RESULT))


def _solution_factor(width, shift):
    p = gears.P["gear"]
    unit = gears.geometry(1.0, p["teeth"], p["pressure_angle"], shift, p["backlash_jt"])
    g = gears.geometry(p["center_distance"] / unit["a_w"], p["teeth"], p["pressure_angle"], shift, p["backlash_jt"])
    servo = gears.P["servo"]["models"][gears.P["servo"]["model"]]
    torque = servo["stall_torque_kgcm"]["6.5V"] * gears.KGCM
    shock = RESULT["as_drawn"]["mesh_torque_Nm"]["snag_shock"]
    drawn = gears.geometry(p["module"], p["teeth"], p["pressure_angle"], p["profile_shift"], p["backlash_jt"])
    e = gears.evaluate(g, width, "PA6-CF", Fby=gears.fby(p["face_width"], drawn["alpha_w"]), T3=torque, Tsh=shock)
    req = {"F_LC1": 1.5, "F_LC2": 1.5, "F_LC3": 1, "F_shock": 1, "H_LC1": 1, "H_LC3": 1}
    return min(e["SF"][key] / value for key, value in req.items())


@pytest.mark.parametrize("name,decrement", [("face_width_only", (0.1, 0)), ("profile_shift_only", (0, 0.01)), ("both", (0.1, 0))])
def test_smallest_change_reaches_rule_and_less_fails(name, decrement):
    row = RESULT["as_drawn"]["smallest_change"][name]
    assert _solution_factor(row["face_width_mm"], row["profile_shift"]) >= 1.5
    assert _solution_factor(row["face_width_mm"] - decrement[0], row["profile_shift"] - decrement[1]) < 1.5


def test_break_even_fraction_reproduces_1p5():
    row = RESULT["as_drawn"]
    fraction = row["stall_break_even"]["SF_1p5_fraction_of_servo_stall"]
    assert row["checks"]["F_LC3"]["value"] / fraction == pytest.approx(1.5, abs=0.001)


def test_missing_thermal_key_names_key(tmp_path):
    thermal = json.loads((ROOT / "analysis/gripper/thermal/results/thermal.json").read_text(encoding="utf-8"))
    thermal.pop("r26_verdict_table")
    copied = tmp_path / "thermal.json"
    copied.write_text(json.dumps(thermal), encoding="utf-8", newline="\n")
    env = os.environ | {"GRIPPER_THERMAL_RESULTS": str(copied)}
    code = "import sys;sys.path.insert(0,'analysis/gripper');import gears;gears._thermal_case_temperatures()"
    run = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, text=True, capture_output=True,
                         timeout=SUBPROCESS_TIMEOUT_SECONDS)
    assert run.returncode != 0
    assert "r26_verdict_table" in run.stderr
