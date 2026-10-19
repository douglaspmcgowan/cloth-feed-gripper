"""Statistical cross-checks against the independent NumPy sampler."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

from loop_sampler import percentile_limits, sample_id
from test_loop_goldens import CASES, STACKS

sys.path.insert(0, str(STACKS.parent))
from tolcalc import run_all  # noqa: E402


N = 75_000
LIVE_N = 25_000
SEED = 817_231
QUANTILES = (0.00135, 0.99865)
SAMPLE_CACHE = {}


def _samples(stack_id, overrides, n=N):
    return sample_id(STACKS, stack_id, overrides, n=n, seed=SEED, cache=SAMPLE_CACHE)


def _quantile_se(values, probability, other_n):
    width = 0.0005
    lo, hi = np.quantile(values, [probability - width, probability + width])
    density = 2 * width / max(float(hi - lo), np.finfo(float).eps)
    variance = probability * (1 - probability) * (1 / len(values) + 1 / other_n)
    return math.sqrt(variance) / density


def _fraction_se(count, total, other_count, other_total):
    pooled = (count + other_count + 0.5) / (total + other_total + 1)
    return math.sqrt(pooled * (1 - pooled) * (1 / total + 1 / other_total))


def _capability(values, spec):
    mean = float(np.mean(values))
    sigma = float(np.std(values, ddof=1))
    low, high = percentile_limits(values)
    median = float(np.median(values))
    sides = []
    if "usl" in spec:
        sides.append((spec["usl"] - median) / (high - median))
    if "lsl" in spec:
        sides.append((median - spec["lsl"]) / (median - low))
    out = np.zeros(len(values), dtype=bool)
    if "usl" in spec:
        out |= values > spec["usl"]
    if "lsl" in spec:
        out |= values < spec["lsl"]
    normal = []
    if "usl" in spec:
        normal.append((spec["usl"] - mean) / (3 * sigma))
    if "lsl" in spec:
        normal.append((mean - spec["lsl"]) / (3 * sigma))
    return low, high, min(sides), int(np.count_nonzero(out)), min(normal), mean, sigma


def _cpk_normal_se(values, mean, sigma, spec, other_n):
    distances = [spec["usl"] - mean] if "usl" in spec else []
    distances += [mean - spec["lsl"]] if "lsl" in spec else []
    distance = min(distances)
    sign = -1 if "usl" in spec and distance == spec["usl"] - mean else 1
    centered = values - mean
    influence = sign * centered / (3 * sigma) - distance * (centered**2 - sigma**2) / (6 * sigma**3)
    return float(np.std(influence, ddof=1)) * math.sqrt(1 / len(values) + 1 / other_n)


def _cpk_percentile_se(values, spec, low, high, cpk, other_n):
    median = float(np.median(values))
    upper = (spec["usl"] - median) / (high - median) if "usl" in spec else math.inf
    tail = high if upper <= cpk + 1e-12 else low
    probability = QUANTILES[1] if tail == high else QUANTILES[0]
    tail_se = _quantile_se(values, probability, other_n)
    median_se = _quantile_se(values, 0.5, other_n)
    limit = spec.get("usl", spec.get("lsl"))
    gap = abs(tail - median)
    return math.hypot(median_se / gap, abs(limit - median) * math.hypot(tail_se, median_se) / gap**2)


@pytest.mark.parametrize("revision,result,overrides", CASES,
                         ids=[f"{revision}:{result['id']}" for revision, result, _ in CASES])
def test_engine_statistics_match_independent_sampler(revision, result, overrides):
    del revision
    stack_id = result.get("picked_variant") or result["id"]
    values = _samples(stack_id, overrides)
    low, high, cpk, out_count, normal_cpk, mean, sigma = _capability(values, result["spec"])
    engine = result["mc"]
    for probability, sampled, key in zip(QUANTILES, (low, high), ("p0135", "p99865")):
        tolerance = 3 * _quantile_se(values, probability, engine["n"])
        assert abs(sampled - engine[key]) <= tolerance
    cpk_se = _cpk_percentile_se(values, result["spec"], low, high, cpk, engine["n"])
    assert abs(cpk - engine["cpk_percentile"]) <= 3 * cpk_se
    engine_count = round(engine["out_pct"] * engine["n"] / 100)
    fraction_se = _fraction_se(out_count, N, engine_count, engine["n"])
    assert abs(out_count / N - engine_count / engine["n"]) <= 3 * fraction_se
    if "cpk_normal" in engine:
        se = _cpk_normal_se(values, mean, sigma, result["spec"], engine["n"])
        assert abs(normal_cpk - engine["cpk_normal"]) <= 3 * se


def test_t04_dependency_is_sampled_as_a_random_radius():
    expected = {
        "T04": (0.002856, 0.169768),
        "T04-relax40": (0.003535, 0.192569),
        "T04-stock20": (0.011792, 0.422743),
    }
    for stack_id, limits in expected.items():
        values = sample_id(STACKS, stack_id, n=1_000_000, seed=SEED)
        assert percentile_limits(values) == pytest.approx(limits, abs=1e-6)


def test_sampler_uses_exact_published_percentiles():
    values = _samples("T16B", {})
    correct = percentile_limits(values)
    mutated = np.percentile(values, [1, 99])
    assert not np.allclose(correct, mutated, rtol=0, atol=max(_quantile_se(values, q, N) for q in QUANTILES) * 3)


@pytest.mark.parametrize("stack_id", ["T16B", "T04", "T07"])
def test_live_engine_matches_sampler_for_decisive_mutations(stack_id):
    result = run_all([STACKS], n=LIVE_N, only={stack_id})[0]
    values = _samples(stack_id, {}, LIVE_N)
    low, high, cpk, _, _, _, _ = _capability(values, result["spec"])
    for probability, sampled, key in zip(QUANTILES, (low, high), ("p0135", "p99865")):
        assert abs(sampled - result["mc"][key]) <= 3 * _quantile_se(values, probability, LIVE_N)
    se = _cpk_percentile_se(values, result["spec"], low, high, cpk, LIVE_N)
    assert abs(cpk - result["mc"]["cpk_percentile"]) <= 3 * se


def _own_verdict(result, values):
    low, high, cpk, count, _, _, _ = _capability(values, result["spec"])
    del low, high
    if result["method"] in {"wc", "rss"}:
        passed = result.get("pass", {}).get(result["method"], result["own_verdict3"] == "pass")
    else:
        passed = cpk >= result.get("cpk_min", 1.33)
        passed &= 100 * count / len(values) <= result.get("accept", {}).get("max_out_pct", math.inf)
    return "pass" if passed else ("marginal" if cpk >= 1.0 else "fail")


def test_revision_b_verdicts_match_independent_sampler():
    cases = [(result, overrides) for revision, result, overrides in CASES if revision == "revision_b"]
    sampled = {}
    for result, overrides in cases:
        stack_id = result.get("picked_variant") or result["id"]
        sampled[result["id"]] = _own_verdict(result, _samples(stack_id, overrides))
    order = {"pass": 0, "marginal": 1, "fail": 2}
    covered_by_band = []
    for result, _ in cases:
        verdict = sampled[result["id"]]
        for blocker in result["blocked_by"]:
            verdict = max((verdict, sampled[blocker]), key=order.get)
        agreed = verdict == result["verdict3"]
        bands = [result] + [{"verdict_decided": len(run["verdict_band"]) == 1,
                             "verdict_band": run["verdict_band"]}
                            for run in result.get("sampling_runs", [])]
        covered = any(not run["verdict_decided"] and verdict in run["verdict_band"] for run in bands)
        if covered and not agreed:
            covered_by_band.append(result["id"])
        assert agreed or covered, (
            f"{result['id']}: sampler {verdict}, engine {result['verdict3']}"
        )
    print("sampler agreement covered only by uncertainty band: " + ", ".join(covered_by_band))
