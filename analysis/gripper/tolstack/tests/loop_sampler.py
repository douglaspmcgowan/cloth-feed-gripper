"""Independent sampler using loop_reference's SAFE, evaluate, materialize and resolve parser."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np

from loop_reference import SAFE, evaluate, materialize, resolve


NP_SAFE = {name: getattr(np, name) for name in (
    "sqrt", "sin", "cos", "tan", "arcsin", "arccos", "arctan", "arctan2",
    "radians", "degrees", "hypot", "exp", "log", "minimum", "maximum")}
NP_SAFE.update(abs=np.abs, min=np.minimum, max=np.maximum, pi=np.pi)


def percentile_limits(values):
    """Return the published central 99.73% sample limits."""
    return tuple(float(value) for value in np.percentile(values, [0.135, 99.865]))


def _rng(seed: int, key: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    return np.random.default_rng(np.frombuffer(digest[:16], dtype=np.uint32))


def _linear(row, n: int, seed: int, key: str):
    rng = _rng(seed, key)
    mid, half = row["mid"], row["half"]
    if not half:
        return np.full(n, mid)
    if row["dist"] == "normal":
        return rng.normal(mid, half / row["k"], n)
    if row["dist"] == "uniform":
        return rng.uniform(mid - half, mid + half, n)
    if row["dist"] == "triangular":
        return rng.triangular(mid - half, mid, mid + half, n)
    raise ValueError(row["dist"])


def _radial(row, radius, n: int, seed: int, key: str):
    radial = _rng(seed, key + ":radius")
    theta = _rng(seed, key + ":theta").uniform(0.0, 2.0 * math.pi, n)
    if row["dist"] == "disk":
        r = radius * np.sqrt(radial.random(n))
    elif row["dist"] == "ring":
        r = np.broadcast_to(radius, n)
    elif row["dist"] == "ring_uniform":
        r = radius * radial.random(n)
    elif row["dist"] == "normal2d":
        sigma = row["half"] / row["k"]
        return radial.normal(0.0, sigma, n), _rng(seed, key + ":y").normal(0.0, sigma, n)
    else:
        raise ValueError(row["dist"])
    return r * np.cos(theta), r * np.sin(theta)


def sample(
    path: Path, variant=None, overrides=None, stacks_dir=None, n=200_000, seed=817_231, cache=None
):
    """Return closing-dimension samples, recursively sampling every ``from_stack`` dependency."""
    data, ns = materialize(path, variant, overrides)
    rows = [resolve(item, ns) for item in data["contributors"]]
    cache = {} if cache is None else cache
    linear = []
    radial = []
    for item, row in zip(data["contributors"], rows):
        key = str(item.get("shared", item["name"]))
        dependency = item.get("from_stack")
        dep = None
        if dependency:
            dep = sample_id(stacks_dir or path.parent, dependency, overrides, n, seed, cache)
        if row["kind"] == "radial":
            radius = row["half"]
            if dep is not None:
                scale = float(evaluate(item.get("radius_scale", 1.0), ns))
                radius = scale * np.clip(dep, 0, None)
            x, y = _radial(row, radius, n, seed, key)
            if row["project"]:
                linear.append(row["sensitivity"] * x)
            else:
                radial.append((row["sensitivity"] * x, row["sensitivity"] * y))
        else:
            values = dep if dep is not None else _linear(row, n, seed, key)
            linear.append(row["sensitivity"] * values)
    if data.get("mode", "linear") == "expression":
        values = {item["name"]: value / row["sensitivity"]
                  for item, row, value in zip(data["contributors"], rows, linear)}
        return np.asarray(eval(data["expression"], {"__builtins__": {}}, {**NP_SAFE, **ns, **values}), float)
    out = np.full(n, float(evaluate(data.get("constant", 0.0), ns)))
    for values in linear:
        out += values
    if radial:
        out += np.hypot(sum(pair[0] for pair in radial), sum(pair[1] for pair in radial))
    return out


def sample_id(
    stacks_dir, stack_id, overrides=None, n=200_000, seed=817_231, cache=None
):
    cache = {} if cache is None else cache
    key = (stack_id, repr(sorted((overrides or {}).items())), n, seed)
    if key not in cache:
        base, _, variant = stack_id.partition("-")
        path = next(Path(stacks_dir).glob(f"{base}_*.yaml"))
        cache[key] = sample(path, variant or None, overrides, stacks_dir, n, seed, cache)
    return cache[key]
