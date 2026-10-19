import ast
import copy
import hashlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import harness
import margins
import run_all


def row_by_id(rows, row_id):
    matches = [row for row in rows if row.get("id") == row_id]
    assert matches, "required row %s is missing" % row_id
    assert len(matches) == 1, "required row %s is duplicated" % row_id
    return matches[0]


def test_r15_tracks_fitted_resistor_and_markers(monkeypatch):
    before = margins.generated_blocks()[1]
    monkeypatch.setitem(margins.cm.ELEC, "r_fsr_fixed_ohm", 3000.0)
    after = margins.generated_blocks()[1]
    assert "fitted 3.00 kohm" in after and before != after
    with pytest.raises(ValueError):
        margins.render_note(
            (ROOT / "docs/gripper/analysis/electrical.md")
            .read_text(encoding="utf-8")
            .replace("<!-- R15-CHOICE:END -->", "")
        )


def test_limit_fault_controls_computed_gate():
    result = margins.run()
    fault = row_by_id(result.get("faults", []), "fault-limit-servo")
    assert fault["status"] == "not evidenced"
    clear = copy.deepcopy(result)
    for row in clear["rows"] + clear["faults"]:
        row["status"] = "met"
    assert "DO NOT ORDER" in margins.order_block(result)
    with pytest.raises(AssertionError, match="LIM_SIG.*unprotected or unevidenced D5"):
        margins.order_block(clear)
    with pytest.raises(AssertionError, match="fault-limit-servo has status but no computed parts"):
        clear["faults"][0]["parts"] = []
        margins.order_block(clear)


def test_missing_limit_fault_names_required_id():
    result = margins.run()
    result["faults"] = []
    with pytest.raises(AssertionError, match="required fault row fault-limit-servo is missing"):
        margins.order_block(result)


def test_every_ordering_surface_has_identical_block():
    wanted = margins.order_block(margins.run())
    for path in run_all.ordering_surface_paths():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        assert "<!-- ORDER-STATUS:BEGIN -->" in text, "%s start marker is missing" % relative
        assert "<!-- ORDER-STATUS:END -->" in text, "%s end marker is missing" % relative
        start = text.index("<!-- ORDER-STATUS:BEGIN -->")
        end = text.index("<!-- ORDER-STATUS:END -->") + len("<!-- ORDER-STATUS:END -->")
        assert text[start:end] == wanted, "%s ordering block is not identical" % relative
    assert len(run_all.ordering_surface_paths()) >= 5 and "DO NOT ORDER" in wanted


def test_status_policy_and_case_provenance():
    result = margins.run()
    fuse = row_by_id(result.get("rows", []), "input-fuse-hold")
    regen = [x for x in result["rows"] if x["id"].startswith("regen-energy")]
    assert margins.STATUSES == (
        "met",
        "at risk",
        "not met",
        "not evidenced",
        "not met pending measurement",
        margins.UNEVIDENCED,
    )
    assert fuse["margin"] > 0
    assert fuse["uncertainty"] == 0
    assert fuse["status"] == margins.UNEVIDENCED
    assert all(x["status"] == "not met pending measurement" for x in regen if x["margin"] < 0)
    assert all(x["case"] == x["scenario"] for x in result["rows"])


def test_single_swaps_are_exhaustive():
    swaps = harness.single_swap_rows(harness.rows())
    assert len(swaps) == 21 and sum(x["detected"] for x in swaps) == 20
    missed_rows = [x for x in swaps if not x.get("detected")]
    assert missed_rows, "expected undetected harness swap row is missing"
    assert len(missed_rows) == 1, "expected exactly one undetected harness swap row"
    missed = missed_rows[0]
    assert {missed["first"], missed["second"]} == {"J3.1", "J4.4"}


def test_all_calc_text_io_declares_encoding():
    for path in HERE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                assert any(k.arg == "encoding" for k in node.keywords), "%s:%s" % (path.name, node.lineno)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("read_text", "write_text")
            ):
                assert any(k.arg == "encoding" for k in node.keywords), "%s:%s" % (path.name, node.lineno)


def test_locked_fabrication_hashes():
    expected = {
        "gripper-bom.csv": "147d0c8527ce6f7ec8cdef90d4e73bc2b1fc97f6ff0ae6a7557f1f6226c28d08",
        "gripper-bom-jlcpcb.csv": "e4270439eb2c1db6ba527c19e9bce078b9d194264d0da932d5a774bede59d3e1",
        "gripper-harness-bom.csv": "37aea1e4c9855a52e7b3f6f41db6a49bbef663e0e7594f514c076a214a76c0fa",
    }
    for name, digest in expected.items():
        # The locked digests are of the LF bytes the generator writes; a core.autocrlf=true checkout holds CRLF.
        lf_bytes = (ROOT / "ecad/gripper/kicad/fab" / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(lf_bytes).hexdigest() == digest
