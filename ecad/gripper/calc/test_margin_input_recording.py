import ast
import importlib
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import margin_inputs
import margins
import constants as K
import design


def test_calculation_modules_do_not_hide_reads_in_standard_caches():
    findings = []
    for source in sorted(HERE.glob("*.py")):
        if source.name.startswith("test_"):
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = ast.unparse(node.func)
            if target in {"functools.lru_cache", "functools.cache", "lru_cache", "cache"}:
                findings.append(f"{source.name}:{node.lineno}:{target}")
    assert findings == []


def test_recorded_cache_replays_reads_without_rerunning_body():
    calls = []

    @margin_inputs.recorded_cache
    def calculation():
        calls.append(1)
        return margin_inputs.read("trace_width_mil") + margin_inputs.read("copper_thickness_oz")

    with margin_inputs.recording() as first:
        calculation()
    with margin_inputs.recording() as second:
        calculation()
    assert first == second == {"trace_width_mil", "copper_thickness_oz"}
    assert len(calls) == 1


def test_capture_module_rejects_empty_observation_without_overwriting():
    margin_inputs.MODULE_READS["empty_probe"] = {"prior_read"}
    with pytest.raises(AssertionError, match="empty_probe"):
        margin_inputs.capture_module("empty_probe", lambda: {})
    assert margin_inputs.MODULE_READS["empty_probe"] == {"prior_read"}


def test_new_droop_rhs_read_reaches_both_dependent_rows(monkeypatch):
    baseline = margins.run()["rows"]
    droop_rows = [row for row in baseline if "droop_sim" in row["modules_read"]]
    existing = set.intersection(*(set(row["observed_inputs"]) for row in droop_rows))
    new_name = next(name for name in sorted(margin_inputs.INPUTS) if name not in existing)
    original = margins.droop_sim._rhs

    def reading_rhs(*args, **kwargs):
        margin_inputs.read(new_name)
        return original(*args, **kwargs)

    monkeypatch.setattr(margins.droop_sim, "_rhs", reading_rhs)
    margins.droop_sim.run.cache_clear()
    changed = margins.run()["rows"]
    changed_droop_rows = [row for row in changed if "droop_sim" in row["modules_read"]]
    assert {row["id"] for row in changed_droop_rows} == {row["id"] for row in droop_rows}
    assert all(new_name in row["observed_inputs"] for row in changed_droop_rows)


def test_rows_include_every_fresh_module_read():
    margins.droop_sim.run.cache_clear()
    rows = margins.run()["rows"]
    modules = sorted({name for row in rows for name in row["modules_read"]})
    fresh_reads = {}
    for name in modules:
        function = importlib.import_module(name).run
        clear = getattr(function, "cache_clear", None)
        if clear:
            clear()
        with margin_inputs.recording() as observed:
            function()
        fresh_reads[name] = {item for item in observed if not item.startswith("module:")}
    for row in rows:
        for name in row["modules_read"]:
            assert fresh_reads[name] <= set(row["observed_inputs"]), (row["id"], name)


def test_rows_derive_inputs_from_calculation_reads():
    rows = margins.run()["rows"]
    assert all(row["observed_inputs"] for row in rows)
    assert all("declared_inputs" not in row and "recorded_inputs" not in row for row in rows)
    assert all(row["modules_read"] for row in rows)


def test_registry_read_records_only_the_actual_read():
    with margin_inputs.recording() as observed:
        margin_inputs.read("trace_demand_A")
    assert observed == {"trace_demand_A"}


def test_recording_mapping_get_iteration_and_membership_are_observable():
    mapping = margin_inputs.RecordingMapping({"x": 1}, "ELEC")
    with margin_inputs.recording() as observed:
        assert mapping.get("x") == 1
        assert "x" in mapping
        assert list(mapping) == ["x"]
    assert observed == {"ELEC.x", "ELEC.*"}


def test_droop_rhs_records_inductor_read_through_mapping_get():
    params = margins.droop_sim.make_params()
    state = margins.droop_sim._initial(params)
    with margin_inputs.recording() as observed:
        margins.droop_sim._rhs(0, state, params)
    assert "inductance_H" in observed


def test_constants_do_not_duplicate_design_electrical_names():
    overlap = sorted(set(K.C) & set(design.ELEC))
    assert overlap == [], "constants.py and design.py duplicate names: %s" % overlap


def test_every_constant_retains_source_metadata():
    tree = ast.parse((HERE / "constants.py").read_text(encoding="utf-8"))
    table = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "C" for target in node.targets))
    lines = {key.value: value.lineno for key, value in zip(table.keys, table.values)}
    for name, entry in K.C.items():
        location = "constants.py:%d:%s" % (lines[name], name)
        assert entry.get("note"), location + ": source note missing"
        if entry.get("tag") == "S":
            assert entry.get("url"), location + ": source URL missing"


def test_missing_and_unclassified_inputs_block_met_status():
    for row in margins.run()["rows"]:
        classes = {item["class"] for item in row["input_evidence"].values()}
        if classes & {"missing", "unclassified"}:
            assert row["status"] != "met"


def test_registry_evidence_contains_no_values():
    assert all("value" not in item for item in margin_inputs.INPUTS.values())


def _numeric_constants(node):
    return [item for item in ast.walk(node)
            if isinstance(item, ast.Constant)
            and isinstance(item.value, (int, float))
            and not isinstance(item.value, bool)]


def _physical_binding_findings(path):
    findings = []
    for source in sorted(path.glob("*.py")):
        if source.name.startswith("test_") or source.name in {
            "constants.py", "margin_inputs.py", "design.py"
        } or source.name in LITERAL_SCAN_NOT_YET_CONVERTED:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defaults = node.args.defaults + [item for item in node.args.kw_defaults if item]
                for literal in (item for default in defaults for item in _numeric_constants(default)):
                    findings.append(f"{source.name}:{literal.lineno}:{literal.value}:default")
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "NUMERICS" for target in targets):
                continue
            for call in (item for item in ast.walk(node.value) if isinstance(item, ast.Call)):
                if isinstance(call.func, ast.Name) and call.func.id == "v":
                    findings.append(f"{source.name}:{call.lineno}:v():module constant read")
            for literal in _numeric_constants(node.value):
                findings.append(f"{source.name}:{literal.lineno}:{literal.value}:module assignment")
    return findings


def test_no_import_time_physical_value_bindings():
    findings = _physical_binding_findings(HERE)
    assert findings == [], "\n".join(findings)


def test_margins_has_no_accessor_only_observers_or_source_input_table():
    tree = ast.parse((HERE / "margins.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            calls = [item for item in node.body if isinstance(item, ast.Expr)
                     and isinstance(item.value, ast.Call)]
            assert not (len(node.body) >= 5 and len(calls) == len(node.body))
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            assert not all(isinstance(key, ast.Constant) and isinstance(key.value, str)
                           and isinstance(value, ast.Constant) and isinstance(value.value, str)
                           for key, value in zip(node.value.keys, node.value.values))


def test_empty_module_read_set_is_detectable(monkeypatch):
    monkeypatch.setitem(margin_inputs.MODULE_READS, "trace_width", set())
    rows = margins.run()["rows"]
    trace = next(row for row in rows if row["id"] == "trace-current")
    assert "trace_width" in trace["modules_read"]
    assert trace["observed_inputs"]


def test_order_gate_revalidates_tampered_unclassified_row():
    result = margins.run()
    row = next(row for row in result["rows"]
               if any(x["class"] == "unclassified" for x in row["input_evidence"].values()))
    row["status"] = "met"
    with pytest.raises(AssertionError, match="unclassified"):
        margins.order_block(result)

CONVERSION_ORDER = (
    "buck_design.py", "power_budget.py", "ina219_budget.py", "trace_width.py",
    "fsr_frontend.py", "harness.py", "fault_limit.py", "open_requirements.py",
    "pinmap_check.py", "margins.py",
)
LITERAL_SCAN_NOT_YET_CONVERTED = list(CONVERSION_ORDER[6:])


def _formula_function(node, parents):
    ancestor = parents.get(node)
    while ancestor is not None and not isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
        ancestor = parents.get(ancestor)
    if ancestor is None:
        return None
    decorators = [ast.unparse(item.func) for item in ancestor.decorator_list
                  if isinstance(item, ast.Call)]
    return ancestor if "formula" in decorators else None


def _formula_findings(function):
    findings = []
    allowed = {arg.arg for arg in function.args.args}
    doc = ast.get_docstring(function) or ""
    body = function.body[1:] if function.body and isinstance(function.body[0], ast.Expr) else function.body
    if function.args.defaults or any(function.args.kw_defaults):
        findings.append(f"{function.name}:{function.lineno}:default argument")
    if not body or any(not isinstance(item, (ast.Return, ast.If)) for item in body):
        findings.append(f"{function.name}:{function.lineno}:body is not return-only")
    for item in ast.walk(function):
        if isinstance(item, ast.Call) and ast.unparse(item.func) in {"v", "margin_inputs.read"}:
            findings.append(f"{function.name}:{item.lineno}:physical read")
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load):
            if item.id not in allowed and item.id not in {"formula"}:
                findings.append(f"{function.name}:{item.lineno}:global read {item.id}")
        if (isinstance(item, ast.Constant) and isinstance(item.value, (int, float))
                and not isinstance(item.value, bool) and str(item.value) not in doc):
            findings.append(f"{function.name}:{item.lineno}:coefficient {item.value} not documented")
    return findings


def _assigned_from_physical(function):
    names = set()
    for item in ast.walk(function):
        if not isinstance(item, (ast.Assign, ast.AnnAssign)):
            continue
        value = item.value
        if not (isinstance(value, ast.Call) and ast.unparse(value.func) == "v"):
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def _literal_class(node, parents):
    parent = parents.get(node)
    formula_function = _formula_function(node, parents)
    if formula_function:
        return "equation coefficient"
    if isinstance(parent, ast.keyword) and parent.arg == "indent" and isinstance(node.value, int):
        return "integer count"  # JSON indentation is a presentation count.
    ancestor = parent
    while ancestor is not None:
        if isinstance(ancestor, ast.Subscript) and any(item is node for item in ast.walk(ancestor.slice)):
            return "index or slice"  # Sequence positions are structural, not physical.
        if isinstance(ancestor, (ast.Assign, ast.AnnAssign)):
            targets = ancestor.targets if isinstance(ancestor, ast.Assign) else [ancestor.target]
            if any(isinstance(target, ast.Name) and target.id == "NUMERICS" for target in targets):
                return "NUMERICS setting"  # Solver and presentation settings belong in NUMERICS.
        ancestor = parents.get(ancestor)
    if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Pow) and parent.right is node:
        return "exponent"  # Dimensionless mathematical exponents are method syntax.
    if isinstance(node.value, int) and isinstance(parent, ast.Call):
        name = ast.unparse(parent.func)
        attribute = parent.func.attr if isinstance(parent.func, ast.Attribute) else name
        keyword = next((item.arg for item in parent.keywords if item.value is node), None)
        if name == "range" or attribute in {"insert", "split"} or keyword == "indent":
            return "integer count"  # These integer arguments bound iteration or structure.
    if node.value in {0, 1} and isinstance(parent, ast.Call):
        name = ast.unparse(parent.func)
        if name in {"min", "max", "np.minimum", "np.maximum"}:
            return "unit-interval clamp"
    if node.value == 0 and isinstance(parent, ast.Tuple):
        call = parents.get(parent)
        if isinstance(call, ast.Call) and ast.unparse(call.func) == "solve_ivp":
            return "integration origin"
    if node.value in {0, 1} and isinstance(parent, ast.IfExp):
        return "conditional initial value"
    if isinstance(parent, (ast.GeneratorExp, ast.ListComp, ast.SetComp)) and isinstance(node.value, int):
        return "integer count"
    if isinstance(parent, ast.Compare):
        pieces = [parent.left, *parent.comparators]
        if any(isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
               and item.func.id == "len" for item in pieces):
            return "integer count"  # Comparisons with len() are collection bounds.
        ancestor = parent
        while ancestor is not None:
            if isinstance(ancestor, (ast.For, ast.comprehension)):
                names = {item.id for item in ast.walk(ancestor.target) if isinstance(item, ast.Name)}
                if any(isinstance(item, ast.Name) and item.id in names for item in pieces):
                    return "integer count"  # A comparison with a loop variable is a loop bound.
            ancestor = parents.get(ancestor)
        if node.value == 0:
            return "sign test"  # Zero is the boundary between positive and negative.
        function = parents.get(parent)
        while function is not None and not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = parents.get(function)
        physical = _assigned_from_physical(function) if function else set()
        other_names = {item.id for item in pieces if isinstance(item, ast.Name)}
        direct_read = any(isinstance(item, ast.Call) and ast.unparse(item.func) == "v" for item in pieces)
        if node.value in {0, 1} and not direct_read and not (physical & other_names):
            return "count comparison"
    if node.value in {0, 1} and isinstance(parent, ast.BinOp):
        if ((node.value == 0 and isinstance(parent.op, (ast.Add, ast.Sub, ast.Mult)))
                or (node.value == 1 and isinstance(parent.op, (ast.Mult, ast.Div, ast.Sub)))):
            return "identity operand"
        if node.value == 1 and isinstance(parent.op, ast.Add):
            return "identity base"
    if node.value == 1 and isinstance(parent, ast.UnaryOp):
        grandparent = parents.get(parent)
        if isinstance(grandparent, ast.BinOp):
            return "signed identity operand"
    if node.value in {0, 1} and isinstance(parent, ast.Dict):
        index = parent.values.index(node)
        key = parent.keys[index]
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            if key.value in {"n_cross", "iin", "fc_max"}:
                return "accumulator initial value"
    if node.value in {0, 1} and isinstance(parent, (ast.Assign, ast.AnnAssign)):
        target = parent.targets[0] if isinstance(parent, ast.Assign) else parent.target
        function = _formula_function(parent, parents)
        enclosing = parents.get(parent)
        while enclosing is not None and not isinstance(enclosing, (ast.FunctionDef, ast.AsyncFunctionDef)):
            enclosing = parents.get(enclosing)
        if isinstance(target, ast.Name) and enclosing and any(
                isinstance(item, ast.AugAssign) and isinstance(item.target, ast.Name)
                and item.target.id == target.id for item in ast.walk(enclosing)):
            return "accumulator initial value"
        if isinstance(parent.value, ast.Dict) and enclosing and isinstance(target, ast.Name):
            if any(isinstance(item, ast.Assign) and any(
                    isinstance(child, ast.Name) and child.id == target.id
                    for child in ast.walk(item.targets[0])) for item in ast.walk(enclosing)):
                return "accumulator initial value"
        ancestor = parents.get(parent)
        if isinstance(ancestor, ast.If):
            return "sign-clamp assignment"
    if isinstance(parent, ast.BinOp) and isinstance(parent.op, (ast.Mult, ast.Div)):
        other = parent.right if parent.left is node else parent.left
        value = abs(node.value)
        power_ten = value > 0 and abs(math.log10(value) - round(math.log10(value))) < 1e-12
        named = any(isinstance(item, (ast.Name, ast.Attribute, ast.Subscript, ast.Call))
                    for item in ast.walk(other))
        if named and (power_ten or value in {2, 60, 3600}):
            return "unit conversion"  # Named quantities may use standard scale factors.
    return None


def _literal_findings(source):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    functions = [node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    findings = []
    for function in functions:
        if any(isinstance(item, ast.Call) and ast.unparse(item.func) == "formula"
               for item in function.decorator_list):
            findings.extend(f"{source.name}:{item}" for item in _formula_findings(function))
    for node in _numeric_constants(tree):
        if _literal_class(node, parents):
            continue
        enclosing = next((item.name for item in functions
                          if item.lineno <= node.lineno <= item.end_lineno), "<module>")
        findings.append(f"{source.name}:{node.lineno}:{node.value}:{enclosing}")
    return findings


def test_numeric_literal_scan_covers_every_converted_calculation_module():
    assert set(LITERAL_SCAN_NOT_YET_CONVERTED) <= set(CONVERSION_ORDER)
    assert LITERAL_SCAN_NOT_YET_CONVERTED == [name for name in CONVERSION_ORDER
                                               if name in LITERAL_SCAN_NOT_YET_CONVERTED]
    assert LITERAL_SCAN_NOT_YET_CONVERTED == list(CONVERSION_ORDER[6:])
    findings = []
    for source in sorted(HERE.glob("*.py")):
        if source.name.startswith("test_") or source.name in {
            "constants.py", "design.py", "margin_inputs.py", "run_all.py",
            } | set(LITERAL_SCAN_NOT_YET_CONVERTED):
            continue
        findings.extend(_literal_findings(source))
    assert findings == [], "\n".join(findings)


def test_module_absent_from_conversion_list_is_scanned(tmp_path):
    source = tmp_path / "converted.py"
    source.write_text("def f():\n    return 0.42\n", encoding="utf-8", newline="\n")
    assert _literal_findings(source) == ["converted.py:2:0.42:f"]


def test_structural_zero_and_one_rules(tmp_path):
    source = tmp_path / "converted.py"
    source.write_text(
        "def f(x):\n    margin = 1 - x\n    limit_a = 1\n    measured = v('x')\n"
        "    return margin, limit_a, measured > 1.0\n",
        encoding="utf-8", newline="\n")
    assert _literal_findings(source) == [
        "converted.py:3:1:f", "converted.py:5:1.0:f"]


def test_formula_rejects_physical_reads_and_undocumented_coefficients(tmp_path):
    source = tmp_path / "converted.py"
    source.write_text(
        "@formula('bad')\ndef bad(x):\n    \"\"\"Coefficients: none.\"\"\"\n"
        "    return x * 0.85 + v('efficiency')\n",
        encoding="utf-8", newline="\n")
    findings = _literal_findings(source)
    assert any("physical read" in item for item in findings)
    assert any("coefficient 0.85 not documented" in item for item in findings)


def test_infinity_sentinel_is_not_structural(tmp_path):
    source = tmp_path / "converted.py"
    source.write_text("def f():\n    return 1e9\n", encoding="utf-8", newline="\n")
    assert _literal_findings(source) == ["converted.py:2:1000000000.0:f"]


def test_candidate_constant_change_requires_regeneration(monkeypatch):
    committed = __import__("json").loads(
        (HERE / "out/constants.json").read_text(encoding="utf-8"))
    changed = dict(K.C["buck_candidate_r_ohm"])
    changed["value"] = tuple(changed["value"]) + (47000.0,)
    monkeypatch.setitem(K.C, "buck_candidate_r_ohm", changed)
    assert run_constant_value("buck_candidate_r_ohm") != committed["buck_candidate_r_ohm"]


def run_constant_value(name):
    return K.run()[name]
