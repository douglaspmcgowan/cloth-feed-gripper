"""Measured convergence evidence for numerical method settings."""
import ast
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import _common as cm

TOLERANCE_NAME = "convergence_fraction_of_margin"
TOLERANCE = float("0.01")
PERTURBATION_FACTORS = tuple(map(float, ("0.5", "2")))
QUANTITIES = ("demand", "limit", "margin")
ALLOWED_DECLARATION_KEYS = {"class"}
FRACTION_ABS_TOLERANCE = float("1e-6")
QUANTITY_REL_TOLERANCE = float("1e-9")
MEASURED_FIELDS = {"absolute_change", "fraction_of_margin"}
QUANTITY_FIELDS = {"absolute_change", "baseline", "perturbed"}
WORST_TIE_ABS_TOLERANCE = float("1e-15")


def worst_measurement(measurements):
    """Choose the largest margin fraction; near-ties use ascending (row, quantity)."""
    largest = max(item["fraction_of_margin"] for item in measurements)
    tied = [item for item in measurements if math.isclose(
        item["fraction_of_margin"], largest, rel_tol=float(), abs_tol=WORST_TIE_ABS_TOLERANCE)]
    return min(tied, key=lambda item: (item["row"], item["quantity"]))


def source_digest():
    """Hash calculation sources and numerical values that produced the evidence."""
    digest = hashlib.sha256()
    root = Path(cm.HERE)
    for path in sorted(root.glob("*.py")):
        if path.name.startswith("test_") or path.name == Path(__file__).name:
            continue
        digest.update(path.name.encode("utf-8"))
        # Normalize CRLF so core.autocrlf=true checkouts hash the same bytes as LF ones.
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    values = json.dumps(cm.NUMERICS, sort_keys=True, separators=(",", ":"))
    digest.update(values.encode("utf-8"))
    return digest.hexdigest()


def derived_reads():
    """Derive direct NUMERICS readers from Python syntax trees, never declarations."""
    reads = {name: set() for name in cm.NUMERICS}
    for path in sorted(Path(cm.HERE).glob("*.py")):
        if path.name.startswith("test_") or path.name in {"run_all.py", __file__.split("/")[-1]}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            value = node.value
            direct = isinstance(value, ast.Name) and value.id == "NUMERICS"
            if not (direct or isinstance(value, ast.Attribute) and value.attr == "NUMERICS"):
                continue
            key = node.slice.value if isinstance(node.slice, ast.Constant) else None
            if key in reads:
                reads[key].add(path.stem)
    return {key: sorted(value) for key, value in reads.items()}


def perturb(value, factor):
    if isinstance(value, tuple):
        return tuple(perturb(item, factor) for item in value)
    if value == 0:
        return sys.float_info.min
    changed = value * factor
    return max(1, round(changed)) if isinstance(value, int) else changed


def decision_rows(setting=None, value=None):
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory, "decision.json")
        command = [sys.executable, str(Path(cm.HERE, "run_all.py")),
                   "--decision-worker", str(output)]
        if setting is not None:
            command.extend(("--sensitivity-setting", setting,
                            "--sensitivity-value", json.dumps(value)))
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode:
            message = completed.stderr or completed.stdout
            raise RuntimeError("%s could not run: %s" % (setting, message))
        return json.loads(output.read_text(encoding="utf-8"))


def compare_rows(baseline, changed):
    records = []
    by_id = {row["id"]: row for row in changed}
    for row in baseline:
        other = by_id[row["id"]]
        denominator = abs(row["margin"])
        for quantity in QUANTITIES:
            absolute = abs(other[quantity] - row[quantity])
            fraction = absolute / denominator if denominator else (float() if not absolute else float("inf"))
            records.append({"row": row["id"], "quantity": quantity,
                            "baseline": row[quantity], "perturbed": other[quantity],
                            "absolute_change": absolute, "fraction_of_margin": fraction})
        records.append({"row": row["id"], "quantity": "status",
                        "baseline": row["status"], "perturbed": other["status"],
                        "absolute_change": int(), "fraction_of_margin": float()})
    return records


def measure(selected=None):
    declarations = cm.NUMERICS_SENSITIVITY
    if set(declarations) != set(cm.NUMERICS):
        raise ValueError("undeclared entries %s" % sorted(set(declarations) ^ set(cm.NUMERICS)))
    forbidden = {name: sorted(set(item) - ALLOWED_DECLARATION_KEYS)
                 for name, item in declarations.items() if set(item) - ALLOWED_DECLARATION_KEYS}
    if forbidden:
        raise ValueError("typed sensitivity results are forbidden: %s" % forbidden)
    chosen = list(selected or [key for key, item in declarations.items() if item["class"] == "method"])
    reads = derived_reads()
    baseline = decision_rows()
    entries = {}
    failures = []
    for name in chosen:
        original = cm.NUMERICS[name]
        runs = []
        for factor in PERTURBATION_FACTORS:
            value = perturb(original, factor)
            records = compare_rows(baseline, decision_rows(name, value))
            worst = worst_measurement(records)
            status = next((item for item in records if item["quantity"] == "status" and
                           item["baseline"] != item["perturbed"]), None)
            passed = worst["fraction_of_margin"] <= TOLERANCE and status is None
            runs.append({"factor": factor, "value": value, "measurements": records,
                         "worst": worst, "status_change": status, "pass": passed})
            if not passed:
                failures.append((name, factor, status or worst))
        entries[name] = {"class": declarations[name]["class"], "modules": reads[name],
                         "baseline_value": original, "runs": runs,
                         "pass": all(run["pass"] for run in runs)}
    table = {"criterion": {"name": TOLERANCE_NAME, "value": TOLERANCE,
                            "reason": "one percent of margin limits numerical error well below decisions"},
             "source_digest": source_digest(), "entries": entries}
    table["measurement_digest"] = measurement_digest(table)
    return table, failures


def _exact_evidence(value, key=None):
    """Remove platform-sensitive measurements while retaining decision evidence."""
    if isinstance(value, dict):
        return {item: _exact_evidence(child, item) for item, child in value.items()
                if item not in MEASURED_FIELDS}
    if isinstance(value, list):
        return [_exact_evidence(child, key) for child in value]
    if key in {"baseline", "perturbed"} and isinstance(value, float):
        return None
    return value


def measurement_digest(table):
    exact = _exact_evidence({key: value for key, value in table.items()
                             if key != "measurement_digest"})
    payload = json.dumps(exact, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def row_margins(table):
    """Map each row to its absolute baseline margin, read from the margin records."""
    found = {}

    def visit(value):
        if isinstance(value, dict):
            if value.get("quantity") == "margin":
                found.setdefault(value["row"], abs(value["baseline"]))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(table)
    return found


def comparison_difference(committed, measured, entry="<entry>"):
    """Return the first differing field, or None when the measurements agree.

    Solver last digits vary by platform, and a change near zero has no useful
    relative size. A quantity (absolute_change, baseline, perturbed) therefore
    agrees within a 1e-9 relative tolerance OR an absolute tolerance of
    1e-6 * |row margin|. That absolute bound is the fraction tolerance applied
    to the margin: a change of 1e-6 * |margin| is exactly a fraction_of_margin
    of 1e-6, which fraction_of_margin already accepts. The row margin is the
    baseline of the row's margin record, so no field is added to the table.
    fraction_of_margin keeps its absolute 1e-6 tolerance. Numbers compare as
    numbers (int 0 equals float 0.0); bool and every other type stay exact, and
    keys and decision-bearing fields stay exact.
    """
    margins = row_margins(committed)

    def compare(left, right, path="", row=None):
        if is_number(left) and is_number(right):
            field = path.split(".")[-1]
            if field == "fraction_of_margin":
                close = math.isclose(left, right, rel_tol=float(), abs_tol=FRACTION_ABS_TOLERANCE)
            elif field in QUANTITY_FIELDS:
                close = math.isclose(left, right, rel_tol=QUANTITY_REL_TOLERANCE,
                                     abs_tol=FRACTION_ABS_TOLERANCE * margins.get(row, float()))
            else:
                close = left == right
            return None if close else (path or "<root>")
        if type(left) is not type(right):
            return path or "<root>"
        if isinstance(left, dict):
            if set(left) != set(right):
                key = sorted(set(left) ^ set(right))[0]
                return "%s.%s" % (path, key) if path else key
            row = left.get("row", row)
            for key in sorted(left):
                found = compare(left[key], right[key],
                                "%s.%s" % (path, key) if path else key, row)
                if found:
                    return found
        elif isinstance(left, list):
            if len(left) != len(right):
                return path + ".length"
            for index, (old, new) in enumerate(zip(left, right)):
                found = compare(old, new, "%s[%d]" % (path, index), row)
                if found:
                    return found
        elif left != right:
            return path or "<root>"
        return None

    difference = compare(committed, measured)
    if not difference:
        return None
    factor = "<missing>"
    row = "<entry>"
    located = re.match(r"runs\[(?P<run>\d+)\](?:\.measurements\[(?P<measurement>\d+)\])?", difference)
    runs = measured.get("runs", []) if isinstance(measured, dict) else []
    if located and int(located.group("run")) < len(runs):
        run = runs[int(located.group("run"))]
        factor = run.get("factor", "<missing>")
        if located.group("measurement") is None:
            if isinstance(run.get("worst"), dict):
                row = run["worst"].get("row", row)
        else:
            measurements = run.get("measurements", [])
            if int(located.group("measurement")) < len(measurements):
                row = measurements[int(located.group("measurement"))].get("row", "<missing>")
    field = difference if difference.endswith(".length") else next(reversed(difference.split(".")))
    return "entry %s factor %s row %s field %s" % (entry, factor, row, field)


def validate_table(table):
    if table.get("source_digest") != source_digest():
        raise ValueError("source/settings digest is stale")
    if table.get("measurement_digest") != measurement_digest(table):
        raise ValueError("measured table digest is stale")
    method = {key for key, item in cm.NUMERICS_SENSITIVITY.items() if item["class"] == "method"}
    if set(table.get("entries", {})) != method:
        raise ValueError("measured table has missing method entries")
    if table["criterion"]["value"] != TOLERANCE:
        raise ValueError("criterion value is not the declared tolerance")
    tolerance = TOLERANCE
    margins = row_margins(table)
    for name, entry in table["entries"].items():
        outcomes = []
        for run in entry["runs"]:
            for item in run["measurements"]:
                denominator = margins[item["row"]]
                absolute = item["absolute_change"]
                expected = absolute / denominator if denominator else (float() if not absolute else float("inf"))
                if not (expected == item["fraction_of_margin"] or math.isclose(
                        expected, item["fraction_of_margin"], rel_tol=float(), abs_tol=FRACTION_ABS_TOLERANCE)):
                    raise ValueError("entry %s row %s fraction disagrees with its absolute change" % (name, item["row"]))
                if item["quantity"] == "status":
                    if item["absolute_change"] != 0:
                        raise ValueError("entry %s row %s status change carries an absolute change" % (name, item["row"]))
                elif not math.isclose(absolute, abs(item["perturbed"] - item["baseline"]), rel_tol=QUANTITY_REL_TOLERANCE,
                                      abs_tol=QUANTITY_REL_TOLERANCE * max(abs(item["baseline"]), abs(item["perturbed"]))):
                    raise ValueError("entry %s row %s absolute change disagrees with its baseline and perturbed values" % (name, item["row"]))
            expected_worst = worst_measurement(run["measurements"])
            if ((run["worst"]["row"], run["worst"]["quantity"]) !=
                    (expected_worst["row"], expected_worst["quantity"]) or
                    not math.isclose(run["worst"]["fraction_of_margin"], expected_worst["fraction_of_margin"],
                                     rel_tol=float(), abs_tol=WORST_TIE_ABS_TOLERANCE)):
                raise ValueError("entry %s worst does not follow the largest-fraction tie-break" % name)
            changed = [item for item in run["measurements"]
                       if item["quantity"] == "status" and item["baseline"] != item["perturbed"]]
            if run["status_change"] != (changed[0] if changed else None):
                raise ValueError("entry %s run status change disagrees with its status measurements" % name)
            passed = run["worst"]["fraction_of_margin"] <= tolerance and run["status_change"] is None
            if run["pass"] != passed:
                raise ValueError("entry %s run pass disagrees with its measured fraction" % name)
            outcomes.append(passed)
        if entry["pass"] != all(outcomes):
            raise ValueError("entry %s pass disagrees with its runs" % name)


def row_sensitivities(table, row_ids):
    result = {row: {"fraction_of_margin": float(), "cause": ""} for row in row_ids}
    for entry, details in table.get("entries", {}).items():
        for run in details["runs"]:
            for item in run["measurements"]:
                current = result[item["row"]]
                if item["fraction_of_margin"] > current["fraction_of_margin"]:
                    current.update(fraction_of_margin=item["fraction_of_margin"], cause=entry)
    return result


def write_table(table, path):
    text = json.dumps(table, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    Path(path).write_text(text, encoding="utf-8", newline="\n")
