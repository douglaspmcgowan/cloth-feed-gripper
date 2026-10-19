"""Sampling uncertainty, rerun, cap, and reporting regression tests."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parents[1]))

from tolcalc import RERUN_SEED_OFFSET, run_all
from tolcalc.engine import BATCH_COUNT, SampleBank, VERDICT_SE_MULTIPLE, analyse
from tolcalc.model import load_stacks
from tolcalc import report, scenarios

STACKS = Path(__file__).parents[1] / "stacks"


def _revision_b_inputs():
    overlay = scenarios.load_overlay(STACKS / "rev_b.yaml")
    return scenarios.case_plan(overlay, "revb")[0]


def _stack(filename, stack_id, overrides):
    return next(s for s in load_stacks(STACKS / filename, overrides) if s.id == stack_id)


@pytest.fixture(scope="module")
def validation():
    overrides = _revision_b_inputs()
    targets = [
        ("T14B", _stack("T14B_dog_coupling.yaml", "T14B-boss34", overrides)),
        ("T16", _stack("T16_pin_tilt.yaml", "T16", overrides)),
        ("radial", _stack("T01_bolt_pattern_fit.yaml", "T01", overrides)),
    ]
    output = {}
    for name, stack in targets:
        cpks, estimates = [], []
        for seed in range(200):
            result = analyse(stack, bank=SampleBank(100_000, 50_000 + seed))
            cpks.append(result["mc"]["cpk_percentile"])
            estimates.append(result["mc"]["cpk_percentile_se"])
        observed = float(np.std(cpks, ddof=1))
        estimated = float(np.mean(estimates))
        output[name] = (estimated, observed, estimated / observed)
    return output


def test_batch_means_estimator_matches_200_seed_observation(validation):
    assert BATCH_COUNT == 20
    for estimated, observed, ratio in validation.values():
        assert estimated > 0
        assert observed > 0
        assert ratio == pytest.approx(1.0, rel=0.25)


def test_verdict_multiple_and_t14_first_run_decision_shape():
    assert VERDICT_SE_MULTIPLE == pytest.approx(2.576)
    result = run_all([STACKS], n=100_000, const_overrides=_revision_b_inputs(),
                     only={"T14B-boss34"})[0]
    runs = result.get("sampling_runs")
    if not runs:
        assert result["verdict_decided"]
        assert len(result["verdict_band"]) == 1
        assert result["mc"]["n"] == 100_000
        return
    first, second = runs
    assert len(first["verdict_band"]) > 1
    assert first["sample_head_sha256"] != second["sample_head_sha256"]
    assert second["n"] == 1_000_000
    assert second["seed"] - first["seed"] == RERUN_SEED_OFFSET


def test_wc_pass_is_deterministic_but_fail_boundary_can_be_uncertain():
    result = run_all([STACKS], n=20_000, only={"T01"}, _allow_rerun=False)[0]
    if result["pass"]["wc"]:
        assert result["verdict_band"] == ["pass"]
    trial = {**result, "pass": {**result["pass"], "wc": False}, "method": "wc"}
    trial["mc"] = {**result["mc"], "cpk_percentile": 1.0,
                   "cpk_percentile_se": result["mc"]["cpk_percentile_se"] or 0.01}
    from tolcalc.engine import verdict_band
    assert set(verdict_band(trial)) == {"marginal", "fail"}


def test_required_stack_uncertainty_caps_dependent_band(tmp_path):
    base = {"id": "A", "parts": [], "title": "a", "contributors": [
        {"name": "x", "nominal": 0, "tol": 0.3, "dist": "normal"}],
        "spec": {"usl": 0.3}, "accept": {"method": "mc", "cpk_min": 1.0}}
    dep = {"id": "B", "parts": [], "title": "b", "contributors": [
        {"name": "y", "nominal": 0, "tol": 0.01, "dist": "normal"}],
        "spec": {"usl": 1}, "accept": {"method": "mc", "requires": ["A"]}}
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(base), encoding="utf-8", newline="\n")
    (tmp_path / "b.yaml").write_text(yaml.safe_dump(dep), encoding="utf-8", newline="\n")
    results = {r["id"]: r for r in run_all([tmp_path], n=20_000, _allow_rerun=False)}
    assert results["A"]["verdict_decided"] is False
    assert results["B"]["verdict_band"] == results["A"]["verdict_band"]


def test_release_gate_uses_worse_band_and_names_undecided(tmp_path):
    item = {"base_id": "X", "verdict3": "fail", "verdict_decided": False,
            "verdict_band": ["marginal", "fail"],
            "mc": {"n": 100_000, "cpk_percentile": 1.0, "cpk_percentile_se": 0.01}}
    payload = {"stacks": [item]}
    for name in ("revb.json", "hot.json"):
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8", newline="\n")
    (tmp_path / "x.yaml").write_text(yaml.safe_dump(
        {"id": "X", "parts": ["part"], "title": "loop"}), encoding="utf-8", newline="\n")
    text = report.release_gate(tmp_path / "revb.json", tmp_path / "hot.json", tmp_path)
    assert "Do not print" in text
    assert "Undecided (gated as worse): X" in text
    assert "UNDECIDED (FAIL or MARGINAL; N=100,000)" in text


def test_undecided_report_never_prints_bare_verdict():
    result = {"verdict3": "fail", "verdict_decided": False,
              "verdict_band": ["marginal", "fail"], "mc": {"n": 100_000}}
    assert report.v3_str(result) == "UNDECIDED (FAIL or MARGINAL; N=100,000)"
