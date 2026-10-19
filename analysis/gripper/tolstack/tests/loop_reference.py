"""Independent YAML-to-loop calculator; deliberately imports no production code.

This module owns the shared parser (``SAFE``, ``evaluate``, ``materialize`` and
``resolve``) also used by ``loop_sampler.py``. Non-linear stacks are the YAML
``mode: expression`` stacks. Their worst-case
limits are evaluated at every contributor corner.  Radial vector stacks are
also non-linear: their magnitude is bounded from contributor radii.
"""
from __future__ import annotations

import copy
import itertools
import math
from pathlib import Path

import yaml


SAFE = {name: getattr(math, name) for name in (
    "sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "radians", "degrees", "pi", "hypot", "exp", "log")}
SAFE.update(abs=abs, min=min, max=max)
SAFE.update(minimum=min, maximum=max)


def evaluate(value, constants):
    if isinstance(value, str) and value.strip().startswith("="):
        return float(eval(value.strip()[1:], {"__builtins__": {}}, {**SAFE, **constants}))
    return value


def constants(path: Path, overrides=None):
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["constants"]
    values = {}
    overrides = overrides or {}
    for name, item in raw.items():
        value = item.get("value") if isinstance(item, dict) else item
        values[name] = evaluate(overrides.get(name, value), values)
    for name, value in overrides.items():
        if name not in values:
            values[name] = evaluate(value, values)
    return values


def tolerance(item, ns):
    if item.get("gdt"):
        gdt = {key: evaluate(value, ns) for key, value in item["gdt"].items()}
        zone = float(gdt["zone"])
        kind = gdt["type"]
        radius = (zone + float(gdt.get("bonus", 0.0))) / 2
        if kind in {"perpendicularity", "parallelism", "angularity"}:
            radius = zone * float(gdt["lever"]) / float(gdt["length"])
        return radius, -radius
    if "tol" in item:
        value = abs(float(evaluate(item["tol"], ns)))
        return value, -value
    if "limits" in item:
        nominal = float(evaluate(item.get("nominal", 0.0), ns))
        low, high = (float(evaluate(value, ns)) for value in item["limits"])
        return high - nominal, low - nominal
    if "unilateral" in item:
        value = float(evaluate(item["unilateral"], ns))
        return (value, 0.0) if value >= 0 else (0.0, value)
    return float(evaluate(item.get("upper", 0.0), ns)), float(evaluate(item.get("lower", 0.0), ns))


def resolve(item, ns):
    upper, lower = tolerance(item, ns)
    if item.get("kind") == "radial":
        radius = float(evaluate(item.get("radius", upper), ns))
        upper, lower = radius, -radius
    nominal = float(evaluate(item.get("nominal", 0.0), ns))
    if "limits" in item and "nominal" not in item:
        low, high = (float(evaluate(value, ns)) for value in item["limits"])
        nominal = (low + high) / 2
        upper, lower = high - nominal, low - nominal
    bias = float(evaluate(item.get("bias", 0.0), ns))
    half = (upper - lower) / 2
    mid = nominal + bias + (upper + lower) / 2
    dist = item.get("dist", "disk" if item.get("kind") == "radial" else "normal")
    sensitivity = float(evaluate(item.get("sensitivity", item.get("direction", 1.0)), ns))
    return {"name": item["name"], "mid": mid, "half": half, "dist": dist,
            "sensitivity": sensitivity, "kind": item.get("kind", "linear"),
            "project": bool(item.get("project", False)), "k": float(item.get("sigma", 3.0))}


def materialize(path: Path, variant=None, overrides=None):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    ns = constants(path.parent / data["constants"], overrides)
    if variant:
        choice = next(item for item in data.get("variants", []) if item["id"] == variant)
        ns = constants(path.parent / data["constants"], {**(overrides or {}), **choice.get("set", {})})
        data = copy.deepcopy(data)
        dropped = set(choice.get("drop", []))
        data["contributors"] = [item for item in data["contributors"] if item["name"] not in dropped]
        data["contributors"] += choice.get("add", [])
        for item in data["contributors"]:
            replacement = choice.get("replace_from", {}).get(item.get("from_stack"))
            if replacement:
                item["from_stack"] = replacement
        for key in ("mode", "expression", "constant"):
            if key in choice:
                data[key] = choice[key]
    return data, ns


def calculate(path: Path, variant=None, overrides=None, stacks_dir=None, cache=None):
    data, ns = materialize(path, variant, overrides)
    rows = [resolve(item, ns) for item in data["contributors"]]
    cache = cache if cache is not None else {}
    for row, item in zip(rows, data["contributors"]):
        dependency = item.get("from_stack")
        if not dependency:
            continue
        dep_wc, dep_rss, _ = calculate_id(stacks_dir or path.parent, dependency, overrides, cache)
        scale = float(evaluate(item.get("radius_scale", 1.0), ns))
        row["mid"] = (dep_wc[0] + dep_wc[1]) / 2
        row["half"] = (dep_wc[1] - dep_wc[0]) / 2
        dep_sigma = (dep_rss[1] - dep_rss[0]) / 6
        row["dep_sigma"] = dep_sigma
        if row["kind"] == "radial":
            row["mid"] = 0.0
            row["half"] = scale * max(0.0, dep_wc[1])
            dep_mean = (dep_rss[0] + dep_rss[1]) / 2
            row["dep_sigma"] = scale * math.hypot(dep_mean, dep_sigma) / 2
    if data.get("mode", "linear") == "expression":
        return expression_limits(data, ns, rows)
    return linear_limits(data, ns, rows)


def calculate_id(stacks_dir, stack_id, overrides=None, cache=None):
    cache = cache if cache is not None else {}
    key = (stack_id, repr(sorted((overrides or {}).items())))
    if key in cache:
        return cache[key]
    base, _, variant = stack_id.partition("-")
    path = next(Path(stacks_dir).glob(f"{base}_*.yaml"))
    result = calculate(path, variant or None, overrides, stacks_dir, cache)
    cache[key] = result
    return result


def expression_limits(data, ns, rows):
    names = [row["name"] for row in rows]
    expression = data["expression"]
    def run(values):
        return float(eval(expression, {"__builtins__": {}}, {**SAFE, **ns, **dict(zip(names, values))}))
    corners = itertools.product((-1, 1), repeat=len(rows))
    values = [run([row["mid"] + sign * row["half"] for row, sign in zip(rows, signs)])
              for signs in corners]
    mid = run([row["mid"] for row in rows])
    sensitivity = []
    for index, row in enumerate(rows):
        step = max(row["half"], 1e-6) * 1e-3
        up = [item["mid"] for item in rows]
        down = list(up)
        up[index] += step
        down[index] -= step
        sensitivity.append((run(up) - run(down)) / (2 * step))
    rss = 3 * math.sqrt(sum((a * sigma(row)) ** 2 for a, row in zip(sensitivity, rows)))
    return (min(values + [mid]), max(values + [mid])), (mid - rss, mid + rss), rows


def sigma(row):
    if "dep_sigma" in row:
        return row["dep_sigma"]
    # Normal: stated tolerance is k sigma (normally 3), so sigma = half-width / k.
    if row["dist"] == "normal":
        return row["half"] / row["k"]
    # Uniform: sigma = half-width / sqrt(3).
    if row["dist"] == "uniform":
        return row["half"] / math.sqrt(3)
    if row["dist"] == "triangular":
        return row["half"] / math.sqrt(6)
    return row["half"] / 2


def linear_limits(data, ns, rows):
    constant = float(evaluate(data.get("constant", 0.0), ns))
    direct = [row for row in rows if row["kind"] == "linear" or row["project"]]
    radial = [row for row in rows if row not in direct]
    mid = constant + sum(row["sensitivity"] * row["mid"] for row in direct)
    width = sum(abs(row["sensitivity"]) * row["half"] for row in direct)
    radii = [abs(row["sensitivity"]) * row["half"] for row in radial]
    radial_max = sum(radii)
    all_rings = radial and all(row["dist"] == "ring" for row in radial)
    radial_min = max(0.0, 2 * max(radii) - radial_max) if all_rings else 0.0
    wc = (mid - width + radial_min, mid + width + radial_max)
    direct_rss = 3 * math.sqrt(sum((row["sensitivity"] * sigma(row)) ** 2 for row in direct))
    radial_rss = math.sqrt(-2 * math.log(0.0027)) * math.sqrt(
        sum((row["sensitivity"] * sigma(row)) ** 2 for row in radial))
    rss = (mid - direct_rss, mid + math.hypot(direct_rss, radial_rss))
    return wc, rss, rows
