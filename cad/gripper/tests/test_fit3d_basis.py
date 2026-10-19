"""Direct tests of fit3d.basis() and of the digest that hashes only the tolerance values fit3d.py reads."""
import ast
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

CAD = Path(__file__).resolve().parents[1]
ROOT = CAD.parents[1]
sys.path.insert(0, str(CAD / "viewer_src"))
sys.path.insert(0, str(CAD))
from fit3d_inputs import (  # noqa: E402
    BASIS_CONSTANTS, BASIS_FILE, input_digest, input_paths, parse_basis, tolstack_projection,
)

BASIS = ROOT / "analysis/gripper/tolstack/stacks/basis.yaml"
SUMMARY_FILE = "../../analysis/gripper/tolstack/results/summary.json"  # not read by the digest; kept to prove that


@pytest.fixture(scope="module")
def basis():
    pytest.importorskip("cadquery")
    import fit3d
    return fit3d.basis()


def test_basis_values_match_the_file(basis):
    for name in ("keepout_min_clear", "axial_min_clear", "gear_m", "gear_z", "fdm_z_tol"):
        m = re.search(rf"^\s+{name}:\s+\{{value:\s*([-\d.]+)", BASIS.read_text(encoding="utf-8"), re.M)
        assert basis[name]["value"] == float(m.group(1))
        assert basis[name]["tag"] and basis[name]["source"]


def test_basis_skips_cad_and_cad_derived_fields(basis):
    text = BASIS.read_text(encoding="utf-8")
    assert re.search(r"gear_m:.*\bcad: gear\.module", text), "gear_m must keep its cad: binding for this test to bite"
    assert basis["gear_m"]["value"] == 1.5 and basis["gear_m"]["source"].startswith("params.json gear.module")
    assert re.search(r"cad_derived:", text)
    assert basis["cradle_pocket_w"]["source"].startswith("params.json housing.cradle_pocket_clear")
    assert all(set(v) == {"value", "tag", "source"} for v in basis.values())


def test_basis_returns_every_constant_fit3d_reads(basis):
    tree = ast.parse((CAD / "fit3d.py").read_text(encoding="utf-8"))
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "B" \
                and isinstance(node.slice, ast.Constant):
            used.add(node.slice.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "c" \
                and node.args and isinstance(node.args[0], ast.Constant):
            used.add(node.args[0].value)
    assert used == set(BASIS_CONSTANTS), "BASIS_CONSTANTS in fit3d_inputs.py must list every name fit3d.py reads"
    assert used <= set(basis)


def copy_inputs(tmp_path):
    copy = tmp_path / "repo" / "cad" / "gripper"
    for name in [*input_paths(CAD), BASIS_FILE, SUMMARY_FILE]:
        source = CAD / name
        if source.exists():
            (copy / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, copy / name)
    return copy


def test_digest_ignores_unread_tolerance_values(tmp_path):
    copy = copy_inputs(tmp_path)
    before = input_digest(copy)
    basis = copy / BASIS_FILE
    text = basis.read_text(encoding="utf-8")
    unread = next(n for n in parse_basis(text) if n not in BASIS_CONSTANTS)
    edited = re.sub(rf"({unread}:\s+\{{value:\s*)[-\d.]+", r"\g<1>987.5", text, count=1)
    assert edited != text
    basis.write_text(edited, encoding="utf-8", newline="\n")
    summary = copy / SUMMARY_FILE
    data = json.loads(summary.read_text(encoding="utf-8"))
    data["stacks"][0]["nominal"] = -123.0  # any stack but the one fit3d.py reads
    summary.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    assert input_digest(copy) == before


def test_digest_follows_read_tolerance_values(tmp_path):
    copy = copy_inputs(tmp_path)
    before = input_digest(copy)
    basis = copy / BASIS_FILE
    text = basis.read_text(encoding="utf-8")
    edited = re.sub(r"(keepout_min_clear:\s+\{value:\s*)[-\d.]+", r"\g<1>0.37", text, count=1)
    assert edited != text
    basis.write_text(edited, encoding="utf-8", newline="\n")
    assert input_digest(copy) != before
    assert tolstack_projection(copy)["basis"]["keepout_min_clear"]["value"] == 0.37
