"""Audit inputs and stored results have independent content identities."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


CAD = Path(__file__).resolve().parents[1]
ROOT = CAD.parents[1]
sys.path.insert(0, str(CAD / "viewer_src"))
from fit3d_inputs import (  # noqa: E402
    INPUT_PATHS, data_closure, input_digest, input_paths, result_hash, source_closure, validate_result,
)


def copy_inputs(tmp_path):
    copy = tmp_path / "repo" / "cad" / "gripper"
    for name in input_paths(CAD):
        source = CAD / name
        if not source.exists():
            continue
        target = copy / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return copy


def test_source_byte_change_invalidates_digest(tmp_path):
    copy = tmp_path / "repo" / "cad" / "gripper"
    for name in INPUT_PATHS:
        if not (CAD / name).exists():
            continue
        target = copy / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CAD / name, target)
    original = input_digest(copy)
    source = copy / "gripper_concept.py"
    data = bytearray(source.read_bytes())
    source.write_bytes(bytes(data).replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert input_digest(copy) == original
    data[1] ^= 1  # Change only the shebang comment; model behaviour is unchanged.
    source.write_bytes(data)
    assert input_digest(copy) != original


def test_transitive_module_and_constructed_data_are_in_closure():
    sources = source_closure(CAD)
    assert sources == source_closure(Path(os.path.relpath(CAD)))
    assert "../so101/measure_interface.py" in sources
    assert "viewer_src/fit3d_inputs.py" in sources
    data = data_closure(CAD, sources)
    assert data == data_closure(Path(os.path.relpath(CAD)), sources)
    assert "../../analysis/gripper/tolstack/stacks/basis.yaml" in data
    # no tolerance stack is read: fit3d.py names none that exists in summary.json (see its roll branch)
    assert not any("tolstack/results/" in name for name in data), sorted(name for name in data if "tolstack/results/" in name)


def test_viewer_build_refuses_transitive_source_change(tmp_path):
    copy = copy_inputs(tmp_path)
    record = json.loads((CAD / "out/fit3d.json").read_text(encoding="utf-8"))
    record["input_digest_sha256"] = input_digest(copy, record["kernel"])
    concept = copy / "gripper_concept.py"
    concept.write_text(concept.read_text(encoding="utf-8") + "\nimport gears\n",
                       encoding="utf-8", newline="\n")
    gear = copy / "gears.py"
    source = 'from pathlib import Path\nHERE = Path(__file__).parent\n'
    source += 'def profile():\n    return (HERE / ("gear_" + "input.json")).read_text(encoding="utf-8")\n'
    gear.write_text(source, encoding="utf-8", newline="\n")
    data = copy / "gear_input.json"
    data.write_text('{"teeth": 12}\n', encoding="utf-8", newline="\n")
    assert "gears.py" in source_closure(copy)
    assert "gear_input.json" in data_closure(copy, source_closure(copy))
    record["input_digest_sha256"] = input_digest(copy, record["kernel"])
    record["result_sha256"] = result_hash(record)
    stored = copy / "out" / "fit3d.json"
    stored.write_text(json.dumps(record), encoding="utf-8", newline="\n")
    gear.write_text(source + "\n# changed\n", encoding="utf-8", newline="\n")
    env = dict(os.environ, VW_ROOT=str(copy.parents[1]), VW_OUT=str(tmp_path / "viewer.html"))
    result = subprocess.run([sys.executable, str(CAD / "viewer_src/viewer_build.py")], cwd=ROOT,
                            env=env, capture_output=True, text=True, encoding="utf-8", timeout=600)
    assert result.returncode != 0
    assert "input digest is stale" in result.stderr
    assert not (tmp_path / "viewer.html").exists()
    gear.write_text(source, encoding="utf-8", newline="\n")
    data.write_text('{"teeth": 13}\n', encoding="utf-8", newline="\n")
    result = subprocess.run([sys.executable, str(CAD / "viewer_src/viewer_build.py")], cwd=ROOT,
                            env=env, capture_output=True, text=True, encoding="utf-8", timeout=600)
    assert result.returncode != 0
    assert "input digest is stale" in result.stderr


def edit_changes_digest(copy, path):
    before = input_digest(copy)
    path.write_text(path.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8", newline="\n")
    return input_digest(copy) != before


def append(path, text):
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8", newline="\n")


def test_importlib_module_is_in_closure(tmp_path):
    copy = copy_inputs(tmp_path)
    append(copy / "gripper_concept.py", '\nimport importlib\n_extra = importlib.import_module("geom_extra")\n')
    extra = copy / "geom_extra.py"
    extra.write_text("WIDTH = 1.0\n", encoding="utf-8", newline="\n")
    assert "geom_extra.py" in source_closure(copy)
    assert edit_changes_digest(copy, extra)


def test_analysis_module_is_in_closure(tmp_path):
    copy = copy_inputs(tmp_path)
    append(copy / "gripper_concept.py",
           '\nsys.path.insert(0, str(Path(__file__).resolve().parents[2] / "analysis" / "gripper"))\nimport gears\n')
    gears = copy.parents[1] / "analysis" / "gripper" / "gears.py"
    gears.parent.mkdir(parents=True, exist_ok=True)
    gears.write_text("TEETH = 19\n", encoding="utf-8", newline="\n")
    assert "../../analysis/gripper/gears.py" in source_closure(copy)
    assert edit_changes_digest(copy, gears)


def test_data_file_named_in_params_is_in_closure(tmp_path):
    copy = copy_inputs(tmp_path)
    params = json.loads((copy / "params.json").read_text(encoding="utf-8"))
    params["gear"]["profile_dxf"] = "gear_profile_v2.dxf"
    (copy / "params.json").write_text(json.dumps(params, indent=1) + "\n", encoding="utf-8", newline="\n")
    profile = copy / "gear_profile_v2.dxf"
    profile.write_text((copy / "gear_profile.dxf").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    assert "gear_profile_v2.dxf" in input_paths(copy)
    assert edit_changes_digest(copy, profile)


def mutated_closure(tmp_path, code, data=None):
    copy = copy_inputs(tmp_path)
    append(copy / "gripper_concept.py", code)
    if data:
        for name, text in data.items():
            target = copy / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
    return copy


@pytest.mark.parametrize("suffix", [".csv", ".txt", ".stl", ".svg", ".npz"])
def test_data_suffixes_are_in_closure(tmp_path, suffix):
    name = "servo_dims" + suffix
    copy = mutated_closure(tmp_path, f'\n_dims = (HERE / "{name}").read_text(encoding="utf-8")\n', {name: "a,b\n"})
    assert name in input_paths(copy)
    assert edit_changes_digest(copy, copy / name)


def test_m_a_csv_read_is_in_digest(tmp_path):
    copy = mutated_closure(tmp_path, '\nopen(HERE / "servo_dims.csv", encoding="utf-8")\n', {"servo_dims.csv": "1\n"})
    assert edit_changes_digest(copy, copy / "servo_dims.csv")


def test_m_b_fstring_path_is_in_digest(tmp_path):
    copy = mutated_closure(tmp_path, '\n_side = "a"\n(HERE / f"gear_{_side}.json").read_text(encoding="utf-8")\n',
                           {"gear_a.json": "{}\n"})
    assert "gear_a.json" in input_paths(copy)
    assert edit_changes_digest(copy, copy / "gear_a.json")


def test_m_c_computed_import_name_is_refused(tmp_path):
    copy = mutated_closure(tmp_path, '\nimport importlib\nimportlib.import_module(_name_from_params)\n')
    with pytest.raises(ValueError, match="imported module name cannot be resolved"):
        source_closure(copy)


def test_m_d_os_path_join_is_in_digest(tmp_path):
    code = ('\nimport os\nopen(os.path.join(os.path.dirname(__file__), "fsr", "stack" + ".json"), encoding="utf-8")\n')
    copy = mutated_closure(tmp_path, code, {"fsr/stack.json": "{}\n"})
    assert "fsr/stack.json" in input_paths(copy)
    assert edit_changes_digest(copy, copy / "fsr/stack.json")


@pytest.mark.parametrize("code, message", [
    ('\n_p = compute_path()\nopen(_p)\n', "input path is a variable"),
    ('\nopen(some_helper(1))\n', "cannot be resolved"),
    ('\n(HERE / "blob.dat").read_bytes()\n', "not in DATA_SUFFIXES"),
    ('\nimportStep(helper_path)\n', "input path is a variable"),
])
def test_unresolvable_read_fails_closed(tmp_path, code, message):
    copy = mutated_closure(tmp_path, code)
    with pytest.raises(ValueError, match=message):
        input_paths(copy)


def test_current_inputs_are_not_refused():
    paths = input_paths(CAD)
    assert "gear_profile.dxf" in paths and "../so101/measure_interface.py" in paths


def test_kernel_version_is_in_digest():
    record = json.loads((CAD / "out/fit3d.json").read_text(encoding="utf-8"))
    validate_result(record, CAD)
    other = dict(record["kernel"], **{"cadquery-ocp": "0.0.0"})
    assert input_digest(CAD, other) != input_digest(CAD, record["kernel"])
    tampered = dict(record, kernel=other)
    tampered["result_sha256"] = result_hash(tampered)
    with pytest.raises(ValueError, match="input digest is stale"):
        validate_result(tampered, CAD)
    unrecorded = {key: value for key, value in record.items() if key != "kernel"}
    with pytest.raises(ValueError, match="CAD kernel version"):
        validate_result(unrecorded, CAD)


def test_result_edit_invalidates_its_hash():
    record = json.loads((CAD / "out/fit3d.json").read_text(encoding="utf-8"))
    validate_result(record, CAD)
    tampered = json.loads(json.dumps(record))
    tampered["jaw_pairs"][0]["d_min"] += 0.001
    assert result_hash(tampered) != record["result_sha256"]
    with pytest.raises(ValueError, match="result hash is invalid"):
        validate_result(tampered, CAD)


def test_incomplete_audit_is_rejected():
    record = json.loads((CAD / "out/fit3d.json").read_text(encoding="utf-8"))
    record["complete"] = False
    with pytest.raises(ValueError, match="audit is incomplete"):
        validate_result(record, CAD)


@pytest.mark.parametrize("change", ("input_digest_sha256", "distance"))
def test_viewer_build_refuses_stale_audit(tmp_path, change):
    record = json.loads((CAD / "out/fit3d.json").read_text(encoding="utf-8"))
    validate_result(record, CAD)
    if change == "distance":
        record["jaw_pairs"][0]["d_min"] += 0.001
    else:
        record["input_digest_sha256"] = "0" * 64
    altered = tmp_path / "fit3d.json"
    altered.write_text(json.dumps(record), encoding="utf-8", newline="\n")
    env = dict(os.environ, VW_FIT3D=str(altered), VW_OUT=str(tmp_path / "viewer.html"))
    result = subprocess.run([sys.executable, str(CAD / "viewer_src/viewer_build.py")], cwd=ROOT,
                            env=env, capture_output=True, text=True, encoding="utf-8", timeout=600)
    assert result.returncode != 0
    assert "uv run --with cadquery python cad/gripper/fit3d.py" in result.stderr
    assert not (tmp_path / "viewer.html").exists()
