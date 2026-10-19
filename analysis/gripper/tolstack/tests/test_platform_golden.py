"""Cross-platform goldens: a seed must give the same sample bytes on Linux and Windows.

The constants were printed by this code on Linux x86-64 (glibc, numpy 2.4.6). A libm, SIMD or numpy build that
changes any sampled bit fails here instead of silently rewriting committed results.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tolcalc import detmath, run_all  # noqa: E402
from tolcalc.engine import SampleBank, norm_ppf  # noqa: E402


def _hex(values):
    return [float(v).hex() for v in values]


def test_seeded_uniforms_are_golden():
    bank = SampleBank(4, 20260922)
    assert _hex(bank.uniform("deck_float#theta")) == [
        "0x1.1ad175adc07f4p-3", "0x1.de7f627e221d4p-3", "0x1.5be2b56eab25cp-2", "0x1.5d8b7ed0ca4f4p-3"]


def test_normal_inverse_cdf_is_golden_in_both_tails():
    assert _hex(norm_ppf(np.array([1e-9, 0.01, 0.3, 0.75, 0.999]))) == [
        "-0x1.7fdc11f49a6b6p+2", "-0x1.29c5c463cecf1p+1", "-0x1.0c7e395d14936p-1",
        "0x1.5956b87564c41p-1", "0x1.8b8cbb6ee2822p+1"]


def test_libm_free_log_cos_sin_are_golden():
    cos, sin = detmath.cos_sin_turns(np.array([0.0, 0.1, 0.3, 0.55, 0.9]))
    assert _hex(cos) == ["0x1.0000000000000p+0", "0x1.9e3779b97f4a8p-1", "-0x1.3c6ef372fe94ep-2",
                         "-0x1.e6f0e134454ffp-1", "0x1.9e3779b97f4a8p-1"]
    assert _hex(sin) == ["0x0.0p+0", "0x1.2cf2304755a5ep-1", "0x1.e6f0e13445500p-1",
                         "-0x1.3c6ef372fe954p-2", "-0x1.2cf2304755a5ep-1"]
    assert _hex(detmath.log(np.array([1e-15, 0.0123, 0.5, 3.0]))) == [
        "-0x1.144f69ff9ffc4p+5", "-0x1.197b635f81342p+2", "-0x1.62e42fefa39efp-1", "0x1.193ea7aad030bp+0"]


def test_libm_free_functions_stay_within_two_ulp_of_numpy():
    u = np.random.default_rng(7).random(20_000)
    cos, sin = detmath.cos_sin_turns(u)
    assert np.max(np.abs(cos - np.cos(2 * np.pi * u))) < 2e-15
    assert np.max(np.abs(sin - np.sin(2 * np.pi * u))) < 2e-15
    p = u * 0.03 + 1e-15
    assert np.max(np.abs(detmath.log(p) / np.log(p) - 1)) < 5e-16


def test_radial_chained_stack_sample_head_is_golden():
    """T05-deckpegs (radial, normal and from_stack terms) is the stack whose hash moved on Windows."""
    result = {r["id"]: r for r in run_all([ROOT / "stacks"], n=1000, only={"T05-deckpegs"},
                                          _allow_rerun=False)}["T05-deckpegs"]
    assert _hex(result["_samples"][:3]) == ["0x1.5186b4e2215bbp-2", "0x1.5795a07399480p-2", "0x1.671ddc93c1e87p-2"]
    assert hashlib.sha256(result["_samples"].tobytes()).hexdigest() == (
        "368ccd97ea6be6b18948bcb4fd5d367b62b6fc5ef8d3c6fbcef3c767e5e37687")


def test_committed_sample_hash_reproduces():
    """The first sampling run stored in T05-deckpegs.json is recomputed bit for bit."""
    stored = json.loads((ROOT / "results" / "T05-deckpegs.json").read_text(encoding="utf-8"))["sampling_runs"][0]
    result = {r["id"]: r for r in run_all([ROOT / "stacks"], n=stored["n"], seed=stored["seed"],
                                          only={"T05-deckpegs"}, _allow_rerun=False)}["T05-deckpegs"]
    assert hashlib.sha256(result["_samples"][:1000].tobytes()).hexdigest() == stored["sample_head_sha256"]
