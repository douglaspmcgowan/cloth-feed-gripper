"""tolcalc: 1D / radial tolerance stack-up calculator (worst case, RSS, Monte Carlo)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from .engine import SampleBank, analyse, capability, classify, worst  # noqa: F401
from .gdt import convert as gdt_convert  # noqa: F401
from .model import Contributor, Stack, load_constants, load_stacks  # noqa: F401

UNDECIDED_RERUN_FACTOR = 10
RERUN_SEED_OFFSET = 1_000_003


def _run_record(r: dict) -> dict:
    mc = r["mc"]
    digest = hashlib.sha256(r["_samples"][:1000].tobytes()).hexdigest()
    return {"n": mc["n"], "cpk_percentile": mc["cpk_percentile"],
            "cpk_percentile_se": mc["cpk_percentile_se"], "verdict_band": r["verdict_band"],
            "seed": r["seed"], "sample_head_sha256": digest}


def run_all(paths, n=100_000, seed=20260922, const_overrides=None, only=None,
            _allow_rerun=True) -> list[dict]:
    """Load every stack (and variant) from files/dirs, resolve from_stack deps, analyse in order.

    One SampleBank serves the whole run, so a contributor name shared by chained stacks is one
    physical deviation (see engine docstring). `accept.requires: [ids]` makes a verdict
    conditional on other stacks passing. `only` limits the returned list (deps still run).
    """
    files = []
    for p in paths:
        p = Path(p)
        files += sorted(p.glob("*.yaml"), key=lambda f: f.name.lower()) if p.is_dir() else [p]
    stacks = []
    for f in files:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "id" in data and "parts" not in data:
            raise ValueError(f"{data['id']}: stack definition has no parts key")
        stacks += load_stacks(f, const_overrides)
    by_id = {s.id: s for s in stacks}
    done: dict[str, dict] = {}
    bank = SampleBank(n, seed)

    def visit(s, trail=()):
        if s.id in done:
            return
        if s.id in trail:
            raise ValueError(f"circular from_stack: {' -> '.join(trail + (s.id,))}")
        for c in s.contributors:
            if c.from_stack:
                if c.from_stack not in by_id:
                    raise ValueError(f"{s.id}: from_stack {c.from_stack} not loaded")
                visit(by_id[c.from_stack], trail + (s.id,))
                c.dep = done[c.from_stack]
        for req in s.accept.get("requires") or []:
            if req not in by_id:
                raise ValueError(f"{s.id}: accept.requires {req} not loaded")
            visit(by_id[req], trail + (s.id,))
        r = analyse(s, bank=bank)
        for req in r["requires"]:
            if not done[req]["verdict"]:
                r["blocked_by"].append(req)
        r["verdict"] = r["own_verdict"] and not r["blocked_by"]
        r["own_verdict3"] = worst(*r["verdict_band"])
        bands = [r["verdict_band"]] + [done[q]["verdict_band"] for q in r["requires"]]
        r["verdict_band"] = sorted(
            {worst(*choices) for choices in __import__("itertools").product(*bands)},
            key={"pass": 0, "marginal": 1, "fail": 2}.get,
        )
        r["verdict_decided"] = len(r["verdict_band"]) == 1
        r["verdict3"] = worst(*r["verdict_band"])
        done[s.id] = r

    todo = [s for s in stacks if only is None or s.id in only]
    for s in todo:
        visit(s)
    results = [done[s.id] for s in todo]
    undecided = {r["id"] for r in results if not r["verdict_decided"]}
    if _allow_rerun and undecided:
        larger = run_all(paths, n=n * UNDECIDED_RERUN_FACTOR, seed=seed + RERUN_SEED_OFFSET,
                         const_overrides=const_overrides, only=undecided, _allow_rerun=False)
        large_by_id = {r["id"]: r for r in larger}
        for index, first in enumerate(results):
            if first["id"] not in undecided:
                continue
            second = large_by_id[first["id"]]
            second["sampling_runs"] = [_run_record(first), _run_record(second)]
            results[index] = second
    return results
