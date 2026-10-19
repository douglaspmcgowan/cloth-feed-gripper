import ast
import copy
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _common as cm
import numerics_sensitivity as ns
import run_all


def test_no_open_named_temporary_file_is_passed_to_a_child():
    violations = []
    for path in sorted(HERE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.With):
                continue
            for item in node.items:
                call = item.context_expr
                if not (isinstance(call, ast.Call)
                        and ast.unparse(call.func) == "tempfile.NamedTemporaryFile"):
                    continue
                delete_false = any(keyword.arg == "delete"
                                   and isinstance(keyword.value, ast.Constant)
                                   and keyword.value.value is False
                                   for keyword in call.keywords)
                if not delete_false:
                    violations.append(f"{path.name}:{call.lineno}: NamedTemporaryFile without delete=False")
                    continue
                if not isinstance(item.optional_vars, ast.Name):
                    continue
                handle = item.optional_vars.id
                for child_call in (candidate for candidate in ast.walk(node)
                                   if isinstance(candidate, ast.Call)
                                   and ast.unparse(candidate.func).startswith("subprocess.")):
                    if any(isinstance(candidate, ast.Attribute)
                           and isinstance(candidate.value, ast.Name)
                           and candidate.value.id == handle
                           and candidate.attr == "name"
                           for argument in child_call.args
                           for candidate in ast.walk(argument)):
                        violations.append(
                            f"{path.name}:{child_call.lineno}: open NamedTemporaryFile passed to subprocess")
    assert not violations, "\n" + "\n".join(violations)


def test_fast_numerics_sensitivity(capsys):
    entries = ('trace_stride', 'buck_grid_points', 'solver_atol')
    assert run_all.numerics_sensitivity(entries) == 0
    assert capsys.readouterr().out.endswith("numerics sensitivity: 3 method entries passed\n")


def _stub_measure(monkeypatch, written):
    committed = json.loads((HERE / "out/numerics_sensitivity.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(ns, "measure", lambda entries=None: (committed, []))
    monkeypatch.setattr(ns, "write_table", lambda table, path: written.append(Path(path)))


def test_sensitivity_command_never_writes_without_the_flag(monkeypatch, capsys, tmp_path):
    tracked = HERE / "out/numerics_sensitivity.json"
    before = tracked.read_bytes()
    sandbox = tmp_path / "calc"
    (sandbox / "out").mkdir(parents=True)
    (sandbox / "out/numerics_sensitivity.json").write_bytes(before)
    monkeypatch.setattr(cm, "HERE", str(sandbox))
    writes = []
    real_write_text, real_write_bytes = Path.write_text, Path.write_bytes

    def record_text(self, *args, **kwargs):
        writes.append(self)
        return real_write_text(self, *args, **kwargs)

    def record_bytes(self, *args, **kwargs):
        writes.append(self)
        return real_write_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", record_text)
    monkeypatch.setattr(Path, "write_bytes", record_bytes)
    _stub_measure(monkeypatch, [])
    assert run_all.numerics_sensitivity() == 0
    assert writes == []
    assert tracked.read_bytes() == before
    assert "method entries passed" in capsys.readouterr().out


def test_committed_sensitivity_table_is_self_consistent():
    table = json.loads((HERE / "out/numerics_sensitivity.json").read_text(encoding="utf-8"))
    ns.validate_table(table)


def test_validate_table_rejects_pass_against_a_failing_fraction():
    table = json.loads((HERE / "out/numerics_sensitivity.json").read_text(encoding="utf-8"))
    entry = "inner_loop_divisor"
    run = table["entries"][entry]["runs"][1]
    worst = next(item for item in run["measurements"]
                 if item["row"] == run["worst"]["row"] and item["quantity"] == run["worst"]["quantity"])
    worst["fraction_of_margin"] = run["worst"]["fraction_of_margin"] = 0.5
    try:
        ns.validate_table(table)
    except ValueError as error:
        assert entry in str(error)
    else:
        raise AssertionError("pass recorded against a 0.5 fraction was accepted")


def test_sensitivity_command_writes_only_with_the_flag(monkeypatch):
    written = []
    _stub_measure(monkeypatch, written)
    assert run_all.numerics_sensitivity(write_table=True) == 0
    assert [path.name for path in written] == ["numerics_sensitivity.json"]


def test_sensitivity_command_compares_the_whole_committed_table(monkeypatch, capsys):
    written = []
    _stub_measure(monkeypatch, written)
    committed = json.loads((HERE / "out/numerics_sensitivity.json").read_text(encoding="utf-8"))
    changed = json.loads(json.dumps(committed))
    entry = next(iter(changed["entries"]))
    changed["entries"][entry]["modules"] = ["no_such_module"]
    monkeypatch.setattr(ns, "measure", lambda entries=None: (changed, []))
    assert run_all.numerics_sensitivity() == 1
    assert "numerics sensitivity FAIL: entry %s" % entry in capsys.readouterr().out
    assert written == []


def test_every_numeric_setting_has_a_sensitivity_declaration(monkeypatch, capsys):
    monkeypatch.setitem(cm.NUMERICS, 'undeclared_setting', 2)
    assert run_all.numerics_sensitivity(('undeclared_setting',)) == 1
    assert "undeclared entries" in capsys.readouterr().out


def test_sensitive_grid_mutation_names_entry_and_output(monkeypatch, capsys):
    monkeypatch.setitem(cm.NUMERICS, 'buck_grid_points', 4)
    assert run_all.numerics_sensitivity(('buck_grid_points',)) == 1
    output = capsys.readouterr().out
    assert "buck_grid_points" in output
    assert "numerics sensitivity FAIL" in output


def test_typed_sensitivity_result_is_rejected(monkeypatch, capsys):
    monkeypatch.setitem(cm.NUMERICS_SENSITIVITY['solver_rtol'], 'proven_baseline', '1e-6')
    assert run_all.numerics_sensitivity(('solver_rtol',)) == 1
    assert "typed sensitivity results are forbidden" in capsys.readouterr().out


def test_measurement_digest_rejects_hand_edit():
    table = {"source_digest": ns.source_digest(), "entries": {}, "measurement_digest": "bad"}
    try:
        ns.validate_table(table)
    except ValueError as error:
        assert "measured table digest is stale" in str(error)
    else:
        raise AssertionError("edited measurement was accepted")


def test_sensitivity_comparison_tolerates_platform_float_noise():
    committed = json.loads((HERE / "out/numerics_sensitivity.json").read_text(encoding="utf-8"))
    measured = copy.deepcopy(committed)
    measured["entries"]["solver_atol"]["runs"][0]["measurements"][0][
        "fraction_of_margin"] += 1e-12
    assert ns.comparison_difference(committed["entries"]["solver_atol"],
                                    measured["entries"]["solver_atol"], "solver_atol") is None


def test_worst_measurement_near_tie_uses_stable_row_and_quantity():
    measurements = [
        {"row": "z-row", "quantity": "margin", "fraction_of_margin": 0.5 + 5e-16},
        {"row": "a-row", "quantity": "limit", "fraction_of_margin": 0.5},
        {"row": "a-row", "quantity": "demand", "fraction_of_margin": 0.5},
    ]
    assert ns.worst_measurement(measurements) is measurements[2]


def test_near_zero_change_passes_within_margin_tolerance():
    committed = json.loads((HERE / "out/numerics_sensitivity.json").read_text(encoding="utf-8"))
    committed_entry = copy.deepcopy(committed["entries"]["solver_atol"])
    committed_entry["runs"][0]["measurements"][0]["absolute_change"] = 0.0
    measured_entry = copy.deepcopy(committed_entry)
    measured_entry["runs"][0]["measurements"][0]["absolute_change"] = 1e-12
    assert ns.comparison_difference(committed_entry, measured_entry, "solver_atol") is None


def test_zero_integer_and_zero_float_compare_equal():
    committed = {"absolute_change": 0}
    assert ns.comparison_difference(committed, {"absolute_change": 0.0}) is None


def test_bool_stays_distinct_from_number():
    assert ns.comparison_difference({"pass": True}, {"pass": 1}) == "entry <entry> factor <missing> row <entry> field pass"


def test_change_beyond_margin_tolerance_names_field():
    committed = json.loads((HERE / "out/numerics_sensitivity.json").read_text(encoding="utf-8"))
    committed_entry = committed["entries"]["solver_atol"]
    measured_entry = copy.deepcopy(committed_entry)
    measured_entry["runs"][0]["measurements"][0]["absolute_change"] = 1e-5
    difference = ns.comparison_difference(committed_entry, measured_entry, "solver_atol")
    assert difference is not None and difference.endswith("field absolute_change")


def test_diagnostic_names_factor_and_row_for_measurement():
    committed = json.loads((HERE / "out/numerics_sensitivity.json").read_text(encoding="utf-8"))
    committed_entry = committed["entries"]["solver_atol"]
    measured_entry = copy.deepcopy(committed_entry)
    measured_entry["runs"][0]["measurements"][3]["absolute_change"] = 0.5
    assert ns.comparison_difference(committed_entry, measured_entry, "solver_atol") == (
        "entry solver_atol factor 0.5 row input-fuse-hold field absolute_change")


def test_sensitivity_comparison_catches_decision_mutations():
    committed = json.loads((HERE / "out/numerics_sensitivity.json").read_text(encoding="utf-8"))
    cases = (
        ("pass", lambda table: table["entries"]["solver_atol"]["runs"][0].__setitem__("pass", False)),
        ("status_change", lambda table: table["entries"]["solver_atol"]["runs"][0].__setitem__(
            "status_change", {"row": "regulator-headroom"})),
        ("fraction_of_margin", lambda table: table["entries"]["solver_atol"]["runs"][0][
            "measurements"][0].__setitem__("fraction_of_margin", 2e-6)),
        ("runs.length", lambda table: table["entries"]["solver_atol"]["runs"].pop()),
    )
    for field, mutate in cases:
        measured = copy.deepcopy(committed)
        mutate(measured)
        difference = ns.comparison_difference(committed["entries"]["solver_atol"],
                                              measured["entries"]["solver_atol"], "solver_atol")
        assert all(name in difference for name in ("entry solver_atol", "factor", "row", field))


def test_module_reads_are_derived_from_source():
    reads = ns.derived_reads()
    assert "droop_sim" in reads["solver_rtol"]
    assert "buck_design" in reads["buck_grid_points"]


def _committed_table():
    return json.loads((HERE / "out/numerics_sensitivity.json").read_text(encoding="utf-8"))


def _refresh(table):
    table["measurement_digest"] = ns.measurement_digest(table)


def test_validate_table_rejects_a_fraction_edited_alone():
    table = _committed_table()
    run = table["entries"]["inner_loop_divisor"]["runs"][1]
    for item in run["measurements"]:
        if (item["row"], item["quantity"]) == (run["worst"]["row"], run["worst"]["quantity"]):
            item["fraction_of_margin"] = 0.00049
    run["worst"]["fraction_of_margin"] = 0.00049
    _refresh(table)
    with pytest.raises(ValueError, match="fraction disagrees"):
        ns.validate_table(table)


def test_validate_table_rejects_an_absolute_change_edited_alone():
    table = _committed_table()
    run = table["entries"]["inner_loop_divisor"]["runs"][1]
    for item in run["measurements"]:
        item["absolute_change"] *= 1000
    _refresh(table)
    with pytest.raises(ValueError, match="fraction disagrees"):
        ns.validate_table(table)


def test_validate_table_rejects_a_criterion_other_than_the_declared_tolerance():
    table = _committed_table()
    table["criterion"]["value"] = 1.0
    run = table["entries"]["inner_loop_divisor"]["runs"][1]
    for item in run["measurements"]:
        if item["row"] == run["worst"]["row"] and item["quantity"] == run["worst"]["quantity"]:
            item["fraction_of_margin"] = 0.5
            item["absolute_change"] = 0.5 * abs(next(
                m["baseline"] for m in run["measurements"]
                if m["row"] == item["row"] and m["quantity"] == "margin"))
    run["worst"] = ns.worst_measurement(run["measurements"])
    _refresh(table)
    with pytest.raises(ValueError, match="criterion"):
        ns.validate_table(table)


def test_validate_table_rejects_every_absolute_change_and_fraction_zeroed():
    table = _committed_table()
    run = table["entries"]["inner_loop_divisor"]["runs"][1]
    for item in run["measurements"]:
        item["absolute_change"] = 0
        item["fraction_of_margin"] = 0.0
    run["worst"]["absolute_change"] = 0
    run["worst"]["fraction_of_margin"] = 0.0
    _refresh(table)
    with pytest.raises(ValueError, match="absolute change disagrees"):
        ns.validate_table(table)


def test_validate_table_rejects_one_zeroed_absolute_change_alone():
    table = _committed_table()
    run = table["entries"]["inner_loop_divisor"]["runs"][1]
    item = next(m for m in run["measurements"] if m["quantity"] == "demand" and m["baseline"] != m["perturbed"]
                and m["fraction_of_margin"] < run["worst"]["fraction_of_margin"])
    item["absolute_change"] = 0
    item["fraction_of_margin"] = 0.0
    _refresh(table)
    with pytest.raises(ValueError, match="absolute change disagrees"):
        ns.validate_table(table)


def test_validate_table_rejects_a_status_measurement_edited_alone():
    table = _committed_table()
    run = table["entries"]["inner_loop_divisor"]["runs"][1]
    item = next(m for m in run["measurements"] if m["quantity"] == "status")
    item["perturbed"] = "changed"
    _refresh(table)
    with pytest.raises(ValueError, match="status change disagrees"):
        ns.validate_table(table)


def test_source_digest_ignores_line_endings_but_not_content(monkeypatch, tmp_path):
    sandbox = tmp_path / "calc"
    sandbox.mkdir()
    for path in HERE.glob("*.py"):
        if not path.name.startswith("test_"):
            (sandbox / path.name).write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    monkeypatch.setattr(cm, "HERE", str(sandbox))
    lf_digest = ns.source_digest()
    target = sandbox / "_common.py"
    lf_bytes = target.read_bytes()
    target.write_bytes(lf_bytes.replace(b"\n", b"\r\n"))
    assert ns.source_digest() == lf_digest
    target.write_bytes(lf_bytes.replace(b"\n", b"\r\n") + b"#")
    assert ns.source_digest() != lf_digest
