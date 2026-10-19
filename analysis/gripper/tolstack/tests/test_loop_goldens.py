"""Production-loop regression checks against independent YAML calculations."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from loop_reference import calculate_id, materialize


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
STACKS = ROOT / "stacks"
EXCLUSIONS = {}
sys.path.insert(0, str(ROOT))
from tolcalc.engine import analyse  # noqa: E402
from tolcalc.model import load_stacks  # noqa: E402
from tolcalc.report import out_str  # noqa: E402


def result_cases():
    ignored = {"summary.json", "sens.json"}
    cases = []
    for path in sorted(RESULTS.glob("*.json"), key=lambda item: item.name.lower()):
        if path.name in ignored or path.name.startswith("sweep_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "id" in data:
            cases.append(("revision_a", data, {}))
    overlay = yaml.safe_load((STACKS / "rev_b.yaml").read_text(encoding="utf-8"))
    revb = json.loads((RESULTS / "rev_b" / "revb.json").read_text(encoding="utf-8"))
    cases += [("revision_b", item, overlay["rev_b"]["set"]) for item in revb["stacks"]]
    return cases


CASES = result_cases()


def comparison_kind(result):
    base, _, variant = result["id"].partition("-")
    path = next(STACKS.glob(f"{base}_*.yaml"))
    data, _ = materialize(path, variant or None)
    return "sampled" if any(item.get("from_stack") for item in data["contributors"]) else "analytic"


@pytest.mark.parametrize("revision,result,overrides", CASES,
                         ids=[f"{revision}:{result['id']}" for revision, result, _ in CASES])
def test_loop_limits_match_independent_reference(revision, result, overrides):
    del revision
    expected_wc, expected_rss, rows = calculate_id(STACKS, result["id"], overrides)
    actual_wc = tuple(result["wc"])
    actual_rss = result.get("rss_dist_unclipped", result.get("rss_dist"))
    if result["id"].startswith("T14B"):
        # abs() has an interior kink.  The engine's corner bound may only inflate the lower limit,
        # conservatively, by the documented 0.008 mm allowance; its upper limit remains exact.
        assert expected_wc[0] - 0.008 - 1e-9 <= actual_wc[0] <= expected_wc[0] + 1e-9
        assert actual_wc[1] == pytest.approx(expected_wc[1], abs=1e-6)
    else:
        assert actual_wc == pytest.approx(expected_wc, abs=1e-6)
    kind = comparison_kind(result)
    assert kind in {"analytic", "sampled"}
    if kind == "analytic" and actual_rss is not None:
        assert tuple(actual_rss) == pytest.approx(expected_rss, abs=1e-6)


def test_fingerprints_match_resolved_stack_structure(tmp_path):
    generated = tmp_path / "fingerprints.json"
    command = [sys.executable, str(ROOT / "tolstack.py"), "fingerprints", "--out", str(generated)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    expected = json.loads((Path(__file__).parent / "loop_fingerprints.json").read_text(encoding="utf-8"))
    actual = json.loads(generated.read_text(encoding="utf-8"))
    for revision in sorted(expected):
        assert set(actual[revision]) == set(expected[revision]), f"{revision}: stack set changed"
        for stack in sorted(expected[revision]):
            old = {item["name"]: item for item in expected[revision][stack]}
            new = {item["name"]: item for item in actual[revision][stack]}
            assert set(new) == set(old), f"{revision} {stack}: contributor names changed"
            for contributor in sorted(old):
                for field in ("sign", "sensitivity", "distribution", "tolerance"):
                    assert new[contributor][field] == old[contributor][field], (
                        f"{revision} {stack} {contributor}: {field} changed from "
                        f"{old[contributor][field]!r} to {new[contributor][field]!r}"
                    )


def test_live_engine_rss_matches_reference():
    path = STACKS / "T16B_sleeve_running_fit.yaml"
    stack = load_stacks(path)[0]
    actual = analyse(stack, n=20_000)
    _, expected, _ = calculate_id(STACKS, "T16B")
    assert tuple(actual["rss_dist_unclipped"]) == pytest.approx(expected, abs=1e-6)


def test_generated_fractions_are_sample_honest():
    for path in sorted(RESULTS.rglob("*.md"), key=lambda item: item.as_posix().lower()):
        text = path.read_text(encoding="utf-8")
        assert "under 100 ppm" not in text, f"{path}: obsolete unbounded sampling claim"
        for line in text.splitlines():
            if " ppm" in line and "<" in line:
                assert " of " in line and "95% upper bound" in line, f"{path}: {line}"


def test_six_events_are_reported_as_a_bounded_count():
    text = out_str({"n": 100_000, "out_pct": 0.006})
    assert text == "<120 ppm (6 of 100,000 samples; 95% upper bound)"
