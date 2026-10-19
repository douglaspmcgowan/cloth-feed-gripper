"""Hand-checked tests for tolcalc.

Run from the repository root (Python 3.13 with numpy, PyYAML, matplotlib, pytest already installed):
    python -m pytest analysis/gripper/tolstack/tests -q
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tolcalc import analyse, gdt, report, run_all  # noqa: E402
from tolcalc.model import Stack, parse_contributor  # noqa: E402
import tolstack  # noqa: E402


def mk(contribs, spec=None, mode="linear", expr=None, accept=None, const=0.0):
    return Stack(id="t", title="t", mode=mode, contributors=[parse_contributor(c, {}) for c in contribs],
                 spec=spec or {}, accept=accept or {"method": "mc"}, constant=const, expression=expr)


# Hand example: housing 50.00 +/-0.10 minus part1 20.00 +/-0.05 minus part2 29.50 +/-0.08.
# Gap nominal 0.50. WC = +/-(0.10+0.05+0.08) = +/-0.23 -> 0.27 .. 0.73.
# RSS = sqrt(0.10^2 + 0.05^2 + 0.08^2) = sqrt(0.0189) = 0.137477 -> 0.362523 .. 0.637477.
HAND = [
    {"name": "housing", "nominal": 50.0, "tol": 0.10},
    {"name": "part1", "nominal": 20.0, "tol": 0.05, "direction": -1},
    {"name": "part2", "nominal": 29.5, "tol": 0.08, "direction": -1},
]


def test_hand_worst_case_and_rss():
    r = analyse(mk(HAND, {"lsl": 0.2, "usl": 0.8}), n=200_000)
    assert r["nominal"] == pytest.approx(0.50)
    assert r["wc"] == pytest.approx((0.27, 0.73))
    rss = math.sqrt(0.10**2 + 0.05**2 + 0.08**2)
    assert rss == pytest.approx(0.137477, abs=1e-6)
    assert r["rss_classic"] == pytest.approx((0.5 - rss, 0.5 + rss))
    # all normal with t = 3 sigma: distribution-adjusted RSS equals classic RSS
    assert r["rss_dist"] == pytest.approx(r["rss_classic"])
    # MC sigma converges to RSS/3
    assert r["mc"]["std"] == pytest.approx(rss / 3, rel=0.01)
    assert r["mc"]["mean"] == pytest.approx(0.5, abs=0.001)
    assert r["verdict"] and r["pass"]["wc"]


def test_worst_case_fails_when_limit_inside():
    r = analyse(mk(HAND, {"lsl": 0.30, "usl": 0.70}, accept={"method": "wc"}))
    assert not r["pass"]["wc"] and not r["verdict"]
    assert r["pass"]["rss"]


def test_unilateral_and_bias_shift_mean():
    r = analyse(mk([{"name": "hole", "nominal": 3.2, "upper": 0.1, "lower": 0.0, "bias": -0.25}]))
    assert r["nominal"] == pytest.approx(3.2)
    assert r["mid"] == pytest.approx(3.2 - 0.25 + 0.05)
    assert r["wc"] == pytest.approx((2.95, 3.05))


def test_uniform_rss_inflation():
    r = analyse(mk([{"name": "float", "tol": 0.1, "dist": "uniform"}]))
    assert r["rss_classic"][1] == pytest.approx(0.1)
    # Scholz c = 1.732 inflation, then clipped to the worst-case band (a bounded term cannot exceed WC)
    assert r["rss_dist_unclipped"][1] == pytest.approx(0.1 * math.sqrt(3))
    assert r["rss_dist"][1] == pytest.approx(0.1) and r["rss_clipped"]
    assert r["mc"]["max"] <= 0.1 + 1e-12


def test_seed_reproducible():
    a = analyse(mk(HAND), seed=7)["mc"]
    b = analyse(mk(HAND), seed=7)["mc"]
    assert a == b


def test_cpk_known_normal():
    # sigma = 0.1, mean 0, USL 0.4 -> Cpk = 0.4/0.3 = 1.333
    r = analyse(mk([{"name": "x", "tol": 0.3}], {"usl": 0.4}), n=400_000)
    assert r["mc"]["cpk_normal"] == pytest.approx(4 / 3, rel=0.01)
    assert r["mc"]["cpk_percentile"] == pytest.approx(4 / 3, rel=0.03)
    assert r["mc"]["out_pct"] == pytest.approx(100 * 3.167e-5, abs=0.004)


def test_gdt_conversions():
    assert gdt.convert({"type": "position", "zone": 0.2}) == pytest.approx((0.1, -0.1))
    assert gdt.convert({"type": "position", "zone": 0.2, "bonus": 0.1}) == pytest.approx((0.15, -0.15))
    assert gdt.convert({"type": "circular_runout", "zone": 0.1}) == pytest.approx((0.05, -0.05))
    assert gdt.convert({"type": "perpendicularity", "zone": 0.1, "length": 10, "lever": 85}) == \
        pytest.approx((0.85, -0.85))
    assert gdt.convert({"type": "flatness", "zone": 0.2}) == pytest.approx((0.1, -0.1))
    assert gdt.convert({"type": "profile", "zone": 0.4, "outer": 0.1}) == pytest.approx((0.1, -0.3))
    assert gdt.coords_to_position(0.1, 0.1) == pytest.approx(0.28284, abs=1e-5)


def test_fastener_formulas():
    # M3: F = 2.98 (6g major max). Hole MMC 3.4.
    assert gdt.floating_fastener_T(3.4, 2.98) == pytest.approx(0.42)
    assert gdt.fixed_fastener_total(3.4, 2.98) == pytest.approx(0.42)
    assert gdt.fixed_fastener_H(2.98, 0.21, 0.21) == pytest.approx(3.4)
    assert gdt.floating_fastener_H(2.98, 0.42) == pytest.approx(3.4)


def test_radial_disk():
    r = analyse(mk([{"name": "e", "kind": "radial", "radius": 0.2}]), n=200_000)
    assert r["wc"] == pytest.approx((0.0, 0.2))
    assert r["mc"]["max"] <= 0.2 + 1e-12
    assert r["mc"]["p50"] == pytest.approx(0.2 / math.sqrt(2), rel=0.01)  # area-uniform disk


def test_radial_two_aligned_wc():
    r = analyse(mk([{"name": "e1", "kind": "radial", "radius": 0.2},
                    {"name": "e2", "kind": "radial", "radius": 0.05},
                    {"name": "c", "nominal": -0.3, "tol": 0.0}]))
    assert r["wc"] == pytest.approx((-0.3, -0.3 + 0.25))  # zones: magnitude can reach 0


def test_expression_corners():
    # y = x1 * x2, x1 = 2 +/- 0.1, x2 = 3 +/- 0.2 -> corners 1.9*2.8 .. 2.1*3.2
    r = analyse(mk([{"name": "x1", "nominal": 2, "tol": 0.1}, {"name": "x2", "nominal": 3, "tol": 0.2}],
                   mode="expression", expr="x1*x2"))
    assert r["wc"] == pytest.approx((1.9 * 2.8, 2.1 * 3.2))
    assert r["rss_classic"][1] - r["mid"] == pytest.approx(math.hypot(3 * 0.1, 2 * 0.2), rel=1e-4)


def test_from_stack_and_cli(tmp_path):
    base = {"id": "A", "parts": [], "title": "a", "contributors": HAND, "spec": {"lsl": 0.2}}
    dep = {"id": "B", "parts": [], "title": "b", "contributors": [
        {"name": "gap", "from_stack": "A"}, {"name": "shim", "nominal": 0.1, "tol": 0.02, "direction": -1}],
        "spec": {"lsl": 0.0}, "accept": {"method": "wc"}}
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(base))
    (tmp_path / "b.yaml").write_text(yaml.safe_dump(dep))
    res = {r["id"]: r for r in run_all([tmp_path], n=50_000)}
    assert res["B"]["wc"] == pytest.approx((0.27 - 0.12, 0.73 - 0.08))
    assert res["B"]["mc"]["mean"] == pytest.approx(0.4, abs=0.002)
    out = tmp_path / "out"
    rc = tolstack.main(["run", str(tmp_path), "--out", str(out), "--samples", "20000", "--no-doc", "--plots"])
    assert rc == 0
    assert (out / "A.md").exists() and (out / "figures" / "tol_B.png").exists() and (out / "SUMMARY.md").exists()
    from PIL import Image  # matplotlib depends on Pillow
    at_cli_n = {r["id"]: r for r in run_all([tmp_path], n=20_000)}  # the --plots run's N and seed
    for sid in ("A", "B"):  # each PNG's Description chunk is the caption built from that stack's result
        stored = json.loads(report.dumps({k: v for k, v in at_cli_n[sid].items() if not k.startswith("_")}))
        assert Image.open(out / "figures" / f"tol_{sid}.png").info["Description"] == report.histogram_caption(stored)
    assert (out / "run_stdout.txt").exists() and (out / "summary.json").exists()


def test_variants(tmp_path):
    (tmp_path / "basis.yaml").write_text(yaml.safe_dump({"constants": {"d": 3.2, "r": "=d/2"}}))
    s = {"id": "V", "parts": [], "title": "v", "constants": "basis.yaml",
         "contributors": [{"name": "rad", "nominal": "=r", "tol": 0.01}],
         "variants": [{"id": "big", "label": "big", "set": {"d": 3.6}}]}
    (tmp_path / "v.yaml").write_text(yaml.safe_dump(s))
    res = {r["id"]: r for r in run_all([tmp_path / "v.yaml"], n=1000)}
    assert res["V"]["nominal"] == pytest.approx(1.6)
    assert res["V-big"]["nominal"] == pytest.approx(1.8)


def test_shared_contributor_keeps_correlation(tmp_path):
    # A = x + y ; B = A - x = y exactly. With per-name shared samples B's sigma is y's alone.
    # (Re-shuffling A's samples, as the old runner did, would give sqrt(sx^2 + sx^2 + sy^2).)
    a = {"id": "A", "parts": [], "title": "a", "contributors": [{"name": "x", "tol": 0.3}, {"name": "y", "tol": 0.03}]}
    b = {"id": "B", "parts": [], "title": "b", "contributors": [{"name": "a", "from_stack": "A"},
                                                   {"name": "x", "tol": 0.3, "direction": -1}]}
    c = {"id": "C", "parts": [], "title": "c", "contributors": [{"name": "a", "from_stack": "A"},
                                                   {"name": "x", "tol": 0.3, "direction": -1,
                                                    "shared": "other_x"}]}
    for d in (a, b, c):
        (tmp_path / f"{d['id']}.yaml").write_text(yaml.safe_dump(d))
    res = {r["id"]: r for r in run_all([tmp_path], n=100_000)}
    assert res["B"]["mc"]["std"] == pytest.approx(0.01, rel=0.02)
    assert res["B"]["mc"]["max"] - res["B"]["mc"]["min"] < 0.1
    # an explicit different `shared` key makes it independent again
    assert res["C"]["mc"]["std"] == pytest.approx(math.sqrt(2 * 0.1**2 + 0.01**2), rel=0.02)


def test_chain_reaches_leaf_twice(tmp_path):
    # T -> A and T -> B -> A: y = A - B = A - (A + z) = -z exactly
    a = {"id": "A", "parts": [], "title": "a", "contributors": [{"name": "x", "tol": 0.3}]}
    b = {"id": "B", "parts": [], "title": "b", "contributors": [{"name": "a", "from_stack": "A"}, {"name": "z", "tol": 0.03}]}
    t = {"id": "T", "parts": [], "title": "t", "contributors": [{"name": "a", "from_stack": "A"},
                                                   {"name": "b", "from_stack": "B", "direction": -1}]}
    for d in (a, b, t):
        (tmp_path / f"{d['id']}.yaml").write_text(yaml.safe_dump(d))
    res = {r["id"]: r for r in run_all([tmp_path], n=50_000)}
    assert res["T"]["mc"]["std"] == pytest.approx(0.01, rel=0.02)


def test_mismatched_shape_warns(tmp_path):
    a = {"id": "A", "parts": [], "title": "a", "contributors": [{"name": "x", "tol": 0.3}]}
    b = {"id": "B", "parts": [], "title": "b", "contributors": [{"name": "x", "tol": 0.3, "dist": "uniform"}]}
    for d in (a, b):
        (tmp_path / f"{d['id']}.yaml").write_text(yaml.safe_dump(d))
    res = {r["id"]: r for r in run_all([tmp_path], n=1000)}
    assert any("rank-correlated" in w for w in res["B"]["warnings"])


def test_radial_radius_from_stack_and_projection(tmp_path):
    # clearance c = 0.4 +/- 0.2 (normal); float disk radius c/2 per sample
    c = {"id": "C", "parts": [], "title": "c", "contributors": [{"name": "clr", "nominal": 0.4, "tol": 0.2}]}
    r = {"id": "R", "parts": [], "title": "r", "mode": "radial", "contributors": [
        {"name": "float", "kind": "radial", "from_stack": "C", "radius_scale": 0.5, "dist": "disk"}]}
    x = {"id": "X", "parts": [], "title": "x", "contributors": [
        {"name": "float", "kind": "radial", "project": True, "from_stack": "C", "radius_scale": 0.5,
         "dist": "disk"}]}
    for d in (c, r, x):
        (tmp_path / f"{d['id']}.yaml").write_text(yaml.safe_dump(d))
    res = {q["id"]: q for q in run_all([tmp_path], n=100_000)}
    assert res["R"]["wc"] == pytest.approx((0.0, 0.3))          # WC uses the WC clearance 0.6 / 2
    assert np.all(res["R"]["_samples"] <= 0.5 * np.clip(res["C"]["_samples"], 0, None) + 1e-12)
    assert res["X"]["wc"] == pytest.approx((-0.3, 0.3))
    # the projection is the X component of the same vector R samples
    assert np.all(np.abs(res["X"]["_samples"]) <= res["R"]["_samples"] + 1e-12)
    # per-axis sigma of a disk with random radius R = c/2: sqrt(E[R^2]/4), E[R^2] = (0.4^2 + (0.2/3)^2)/4
    assert res["X"]["mc"]["std"] == pytest.approx(math.sqrt((0.4**2 + (0.2 / 3)**2) / 4 / 4), rel=0.02)


def test_requires_blocks_verdict(tmp_path):
    ok = {"id": "OK", "parts": [], "title": "ok", "contributors": [{"name": "x", "tol": 0.1}], "spec": {"usl": 1.0},
          "accept": {"method": "wc", "requires": ["BAD"]}}
    bad = {"id": "BAD", "parts": [], "title": "bad", "contributors": [{"name": "x", "tol": 0.1}], "spec": {"usl": 0.0},
           "accept": {"method": "wc"}}
    for d in (ok, bad):
        (tmp_path / f"{d['id']}.yaml").write_text(yaml.safe_dump(d))
    res = {r["id"]: r for r in run_all([tmp_path], n=1000)}
    assert res["OK"]["own_verdict"] and not res["OK"]["verdict"] and res["OK"]["blocked_by"] == ["BAD"]


def test_min_expression_caps_engagement():
    # engagement = min(L - t, depth): L 6 +/-0.2, t 3 +/-0.1, depth 2.5 +/-0.1 -> capped by depth
    r = analyse(mk([{"name": "L", "nominal": 6, "tol": 0.2}, {"name": "t", "nominal": 3, "tol": 0.1},
                    {"name": "depth", "nominal": 2.5, "tol": 0.1}], mode="expression",
                   expr="minimum(L - t, depth)"))
    assert r["nominal"] == pytest.approx(2.5)
    assert r["wc"] == pytest.approx((2.4, 2.6))


def test_norm_ppf():
    from tolcalc.engine import norm_ppf
    assert norm_ppf(np.array([0.5, 0.975, 0.00135]))[1] == pytest.approx(1.959964, abs=1e-6)
    assert norm_ppf(np.array([0.00135]))[0] == pytest.approx(-3.0, abs=2e-3)


def test_projection_second_axis_shares_the_disk(tmp_path):
    # one X-Z float disk, radius 0.2: X component in one stack, Z component in another (same samples)
    x = {"id": "X", "parts": [], "title": "x", "contributors": [
        {"name": "f", "kind": "radial", "project": "first", "radius": 0.2, "dist": "disk"}]}
    z = {"id": "Z", "parts": [], "title": "z", "contributors": [
        {"name": "f", "kind": "radial", "project": "second", "radius": 0.2, "dist": "disk"}]}
    for d in (x, z):
        (tmp_path / f"{d['id']}.yaml").write_text(yaml.safe_dump(d))
    res = {q["id"]: q for q in run_all([tmp_path], n=100_000)}
    r = np.hypot(res["X"]["_samples"], res["Z"]["_samples"])
    assert r.max() <= 0.2 + 1e-12                                 # a point of the disk, not a square
    assert res["Z"]["wc"] == pytest.approx((-0.2, 0.2))
    assert res["Z"]["mc"]["std"] == pytest.approx(0.1, rel=0.02)  # disk per-axis sigma R/2
    assert abs(np.corrcoef(res["X"]["_samples"], res["Z"]["_samples"])[0, 1]) < 0.01
    with pytest.raises(ValueError):
        parse_contributor({"name": "bad", "kind": "radial", "project": "z", "radius": 0.1}, {})


def test_sweep_unknown_stack_id(tmp_path):
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(
        {"id": "A", "parts": [], "title": "a", "contributors": HAND, "spec": {"lsl": 0.2}}))
    with pytest.raises(SystemExit, match="not found"):
        tolstack.main(["sweep", str(tmp_path), "--stack", "NOPE", "--param", "p", "--values", "1,2",
                       "--samples", "1000"])


def test_min_minus_chamfer_engagement():
    # T03 form: min(L - t, depth) - chamfer. Short screw: L 5, t 3, depth 2.5, chamfer 0.5 -> 1.5, not 2.0
    r = analyse(mk([{"name": "L", "nominal": 5, "tol": 0.0}, {"name": "t", "nominal": 3, "tol": 0.0},
                    {"name": "depth", "nominal": 2.5, "tol": 0.0}, {"name": "ch", "nominal": 0.5, "tol": 0.0}],
                   mode="expression", expr="minimum(L - t, depth) - ch"))
    assert r["nominal"] == pytest.approx(1.5)


def test_yield_matches_normal_tail():
    # One normal contributor, t = 3 sigma = spec half-width: 0.27 % out (99.73 % yield), Cpk 1.0.
    # Spec at 4 sigma: 0.0063 % out (63 ppm), Cpk 1.33. (Physics: Phi(-3) = 0.00135, Phi(-4) = 3.17e-5.)
    r = analyse(mk([{"name": "x", "nominal": 0.0, "tol": 0.3}], {"lsl": -0.3, "usl": 0.3}), n=400_000)
    assert r["yield_pct"] == pytest.approx(99.73, abs=0.03)
    assert r["mc"]["cpk_percentile"] == pytest.approx(1.0, abs=0.02)
    r4 = analyse(mk([{"name": "x", "nominal": 0.0, "tol": 0.3}], {"lsl": -0.4, "usl": 0.4}), n=400_000)
    assert 100 - r4["yield_pct"] == pytest.approx(0.0063, abs=0.004)
    assert r4["mc"]["cpk_percentile"] == pytest.approx(4 / 3, abs=0.03)


def test_classify_three_levels():
    from tolcalc import classify, worst
    x = [{"name": "x", "nominal": 0.0, "tol": 0.3}]
    assert classify(analyse(mk(x, {"lsl": -0.45, "usl": 0.45}))) == "pass"       # Cpk 1.5
    assert classify(analyse(mk(x, {"lsl": -0.35, "usl": 0.35}))) == "marginal"   # Cpk 1.17
    assert classify(analyse(mk(x, {"lsl": -0.25, "usl": 0.25}))) == "fail"       # Cpk 0.83
    # WC-accepted: worst case 0.3 > usl 0.29 but Cpk 0.97 -> fail; usl 0.31 -> pass
    assert classify(analyse(mk(x, {"usl": 0.31}, accept={"method": "wc"}))) == "pass"
    assert classify(analyse(mk(x, {"usl": 0.29}, accept={"method": "wc"}))) == "fail"
    # WC breaks but the stack-up is rare (three terms, Cpk > 1): marginal
    xs = [{"name": f"x{i}", "nominal": 0.0, "tol": 0.1} for i in range(3)]
    assert classify(analyse(mk(xs, {"usl": 0.25}, accept={"method": "wc"}))) == "marginal"
    assert worst("pass", "marginal") == "marginal" and worst("pass", "fail", "marginal") == "fail"


def test_dominant_contributor_variance_share():
    # variance shares 0.3^2 : 0.1^2 = 90 % : 10 %
    r = analyse(mk([{"name": "big", "tol": 0.3}, {"name": "small", "tol": 0.1}], {"usl": 1.0}))
    assert r["dominant"]["name"] == "big"
    assert r["dominant"]["var_pct"] == pytest.approx(90.0)


ABS_STACK = [{"name": "a", "nominal": 0.0, "tol": 0.3}, {"name": "b", "nominal": 0.0, "tol": 0.03}]


def test_expression_variance_share_at_abs_kink():
    # y = |a| - b, a ~ N(0, 0.1^2) sits on the kink of abs(), b ~ N(0, 0.01^2). Central differences read
    # d|a|/da = 0 at a = 0, so the old shares were 0 % for a. Freeze-one: Var|a| = (1 - 2/pi) 0.1^2 = 3.63e-3
    # against Var(b) = 1e-4, so a carries about 97 %.
    r = analyse(mk(ABS_STACK, {"usl": 1.0}, mode="expression", expr="abs(a) - b"), n=200_000)
    shares = {c["name"]: c["var_pct"] for c in r["contributors"]}
    assert r["dominant"]["name"] == "a" and r["dominant"]["var_pct"] > 80.0
    var_a, var_b = (1 - 2 / math.pi) * 0.1**2, 0.01**2
    assert shares["a"] == pytest.approx(100 * var_a / (var_a + var_b), abs=1.0)
    assert shares["a"] + shares["b"] == pytest.approx(100.0)


def test_linear_variance_share_unchanged():
    # linear mode keeps the closed form (a_i sigma_i)^2 / sum: a = 2, 1 +/- 0.3 (sigma 0.1); b = -1, +/- 0.15 (sigma 0.05)
    r = analyse(mk([{"name": "a", "tol": 0.3, "direction": 2}, {"name": "b", "tol": 0.15, "direction": -1}],
                   {"usl": 1.0}))
    sh = {c["name"]: c["var_pct"] for c in r["contributors"]}
    va, vb = (2 * 0.1) ** 2, 0.05**2
    assert sh["a"] == pytest.approx(100 * va / (va + vb), rel=1e-12)
    assert sh["b"] == pytest.approx(100 * vb / (va + vb), rel=1e-12)


def test_rss_nonlinear_flag():
    r = analyse(mk(ABS_STACK, {"usl": 1.0}, mode="expression", expr="abs(a) - b"))
    assert r["rss_nonlinear"]
    r = analyse(mk(HAND, {"lsl": 0.2, "usl": 0.8}))
    assert not r["rss_nonlinear"]
    # an expression that is linear in its inputs is not flagged
    r = analyse(mk(ABS_STACK, {"usl": 1.0}, mode="expression", expr="a - b"))
    assert not r["rss_nonlinear"]


def test_sample_floor():
    with pytest.raises(SystemExit, match="floor"):
        tolstack.main(["run", "--samples", "19999", "--no-doc"])


def test_roles_and_fix_fields(tmp_path):
    s = {"id": "R", "parts": [], "title": "r", "fix": "ream it", "fix_variant": "ream",
         "contributors": [{"name": "x", "tol": 0.3}], "spec": {"usl": 0.25},
         "variants": [{"id": "ream", "label": "reamed", "drop": ["x"], "add": [{"name": "x", "tol": 0.05}]},
                      {"id": "old", "label": "old layout", "role": "rejected"}]}
    (tmp_path / "r.yaml").write_text(yaml.safe_dump(s))
    res = {q["id"]: q for q in run_all([tmp_path], n=20_000)}
    assert res["R"]["role"] == "baseline" and res["R"]["fix_variant"] == "R-ream"
    assert res["R"]["verdict3"] == "fail" and res["R-ream"]["verdict3"] == "pass"
    assert res["R-ream"]["role"] == "option" and res["R-old"]["role"] == "rejected"
    with pytest.raises(ValueError):
        (tmp_path / "r.yaml").write_text(yaml.safe_dump({**s, "variants": [{"id": "z", "role": "maybe"}]}))
        run_all([tmp_path], n=1000)


STACKS = ROOT / "stacks"


def test_real_stack_T06_worst_case_by_hand():
    # Hand calculation from stacks/T06_gear_center_distance.yaml and basis.yaml (rev A):
    # a0 = m z = 1.5 * 19 = 28.5. Contributors (half-widths): hole spacing 0.10 (XY band), two sleeve floats
    # of pin_clear / 2 = (3.016 - 3.002) / 2 = 0.007 each (the centre moves +/- half the diametral clearance),
    # two sleeve eccentricities 0.015 each. WC = 28.5 +/- (0.10 + 2*0.007 + 2*0.015) = 28.5 +/- 0.144.
    res = {r["id"]: r for r in run_all([STACKS], n=20_000, only={"T06"})}
    hw = 0.10 + 2 * (3.016 - 3.002) / 2 + 2 * 0.015
    assert hw == pytest.approx(0.144)
    assert res["T06"]["wc"] == pytest.approx((28.5 - hw, 28.5 + hw))
    # backlash band on a: (jt0 - jt_min)/k_jt and (jt_max - jt0)/k_jt with k_jt = 2 tan 25 deg
    k = 2 * math.tan(math.radians(25))
    assert res["T06"]["spec"]["lsl"] == pytest.approx(28.5 - 0.20 / k)
    assert res["T06"]["spec"]["usl"] == pytest.approx(28.5 + 0.20 / k)


def test_real_stack_T16B_running_fit_by_hand():
    # Bush bore 3.000..3.016 (H7 pressed .. F7 free) on an m6 pin 3.002..3.008: clearance -0.008 .. +0.014.
    res = {r["id"]: r for r in run_all([STACKS], n=20_000, only={"T16B", "T16B-h8pin"})}
    assert res["T16B"]["wc"] == pytest.approx((3.000 - 3.008, 3.016 - 3.002))
    assert res["T16B"]["verdict3"] == "fail"
    assert res["T16B-h8pin"]["wc"] == pytest.approx((0.0, 0.030), abs=1e-12)


def test_sweep_T03B_depth_threshold_by_hand(tmp_path):
    # T03B tip clearance worst case shifts 1:1 with the horn hole depth: at 3.5 the lower WC is -0.015
    # (results/T03B-depth35.md), so WC acceptance (>= 0.2 LSL) first holds at 3.5 + 0.215 = 3.715 mm.
    # On a 0.05 grid the first PASS is 3.75 and 3.70 must not pass.
    out = tmp_path / "s.md"
    tolstack.main(["sweep", str(STACKS), "--stack", "T03B", "--param", "horn_hole_depth",
                   "--values", "3.5,3.7,3.75", "--samples", "20000", "--out", str(out)])
    data = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    lo = {p["horn_hole_depth"]: p["wc"][0] for p in data["points"]}
    assert lo[3.5] == pytest.approx(-0.015, abs=1e-9)
    assert lo[3.75] - lo[3.5] == pytest.approx(0.25, abs=1e-9)
    assert data["first"]["pass"] == 3.75
    assert {p["horn_hole_depth"]: p["verdict3"] for p in data["points"]}[3.5] == "marginal"


def test_real_stack_T09F_force_physics():
    # F = k_pair * 2 r_c * (theta_c - theta_floor). At the nominal contact angle the stiff finger (0.621 N/mm)
    # with r_c 65 sees 0.621 * 130 N/rad per radian of over-travel.
    res = {r["id"]: r for r in run_all([STACKS], n=20_000, only={"T09", "T09F"})}
    thc = res["T09"]["nominal"]
    k_mid = (0.523 + 0.621) / 2
    assert res["T09F"]["nominal"] == pytest.approx(k_mid * 130 * math.radians(thc + 7.4), rel=1e-9)


# ---------------------------------------------------------------- review follow-up (rev B overlay, sens, fixes)
from tolcalc import report, scenarios  # noqa: E402
from tolcalc.model import REPO_ROOT, load_constants  # noqa: E402
from tolcalc.cad import validate_bindings  # noqa: E402

OVERLAY = scenarios.load_overlay(STACKS / "rev_b.yaml")


def test_revb_constants_match_cad():
    cad_path = REPO_ROOT / "cad/gripper/params.json"
    errors = validate_bindings(STACKS / "basis.yaml", STACKS / "rev_b.yaml", cad_path)
    assert not errors, "\n".join(errors)


def test_t14b_boss_variants_hold_web_tilt_terms():
    from tolcalc.model import load_stacks
    stacks = {stack.id: stack for stack in load_stacks(STACKS / "T14B_dog_coupling.yaml")}
    required = {"boss_web_tilt", "servo_axis_tilt"}
    for variant in ("T14B-boss34", "T14B-boss"):
        names = {contributor.name for contributor in stacks[variant].contributors}
        assert required <= names, f"{variant} missing required contributors: {sorted(required - names)}"


def test_t14b_web_tilt_terms_are_positive_and_contribute_variance():
    from tolcalc.model import load_stacks
    stacks = {stack.id: stack for stack in load_stacks(STACKS / "T14B_dog_coupling.yaml")}
    result = analyse(stacks["T14B-boss34"], n=20_000, seed=1)
    by_name = {item["name"]: item for item in result["contributors"]}
    for name in ("boss_web_tilt", "servo_axis_tilt"):
        assert by_name[name]["half"] > 0, f"{name} tolerance must be positive"
        assert by_name[name]["var_pct"] > 0, f"{name} must contribute positive variance share"


def test_note_revb_tally_matches_generated_summary():
    note = (REPO_ROOT / "docs/gripper/analysis/tolerance_stacks.md").read_text(encoding="utf-8")
    summary = (STACKS.parent / "results/rev_b/REVB.md").read_text(encoding="utf-8")
    prefix = "**Rev B, all changes at once, servo case 20.1 mm** (`revb`)."
    note_line = next(line for line in note.splitlines() if line.startswith(prefix))
    summary_line = next(line for line in summary.splitlines() if line.startswith(prefix))
    assert note_line == summary_line


def test_params_sources_have_machine_bindings(tmp_path):
    basis = yaml.safe_load((STACKS / "basis.yaml").read_text(encoding="utf-8"))
    basis["constants"]["unbound_new_constant"] = {
        "value": 1.0,
        "tag": "D",
        "source": "params.json new.path",
    }
    basis_path = tmp_path / "basis.yaml"
    basis_path.write_text(yaml.safe_dump(basis, sort_keys=False), encoding="utf-8", newline="\n")
    cad_path = REPO_ROOT / "cad/gripper/params.json"
    errors = validate_bindings(basis_path, STACKS / "rev_b.yaml", cad_path)
    assert any("unbound_new_constant" in error and "no cad" in error for error in errors)


def test_revb_overlay_applies_every_change():
    consts, pick = scenarios.case_plan(OVERLAY, "revb")
    ns, _ = load_constants(STACKS / "basis.yaml", consts)
    assert ns["dog_slot_w"] == 3.4                       # row 1
    assert (ns["pin_d_min"], ns["pin_d_max"]) == (ns["pin_h8_min"], ns["pin_h8_max"]) == (2.986, 3.000)  # row 2
    assert ns["pin_clear"] == 0.020                      # row 2, graded
    assert ns["cradle_pocket_w"] == 20.5                 # row 3
    assert ns["closed_gap"] == 0.0                       # row 4, toe-in
    assert ns["recess_d_cad"] == 19.56 and ns["pilot_clear_max"] == 0.40   # row 6
    assert ns["hole_cad_d"] == 3.7                       # row 7
    assert ns["horn_hole_depth"] == 3.75                 # row 8 (assumed, a gate)
    # structural rev B changes ride on picked variants that exist
    from tolcalc.model import load_stacks
    ids = {s.id for f in STACKS.glob("T*.yaml") for s in load_stacks(f)}
    for base, var in pick.items():
        assert f"{base}-{var}" in ids
    assert {"T05", "T14", "T14B", "T15"} <= set(pick)
    # the drawn case applies none of it
    d_consts, d_pick = scenarios.case_plan(OVERLAY, "drawn")
    assert d_consts == {} and d_pick == {}
    # the servo-width and hot cases extend the rev B overlay, not replace it
    c205, _ = scenarios.case_plan(OVERLAY, "revb_servo205")
    assert c205["servo_body_w"] == 20.5 and c205["cradle_pocket_w"] == 20.9 and c205["dog_slot_w"] == 3.4
    hot, _ = scenarios.case_plan(OVERLAY, "revb_hot")
    assert hot["hot_servo_float"] == 0.10 and hot["dog_slot_w"] == 3.4


def test_revb_combined_run_uses_overlay_values():
    res, also = scenarios.run_case(STACKS, OVERLAY, "revb", 20_000, 1)
    by = {r["_base_id"]: r for r in res}
    assert len(res) == 26 and set(by) >= {"T01", "T16B", "T14B"}
    assert by["T14B"]["id"] == "T14B-boss34" and by["T05"]["id"] == "T05-tcpcal"
    # pin_clear 0.020 over a 10 mm sleeve across the 10.5 mm face, plus line-ream tilt over 15 mm.
    expected_tilt = 2 * 0.020 / 10.0 * 10.5 + 2 * 10.5 / 15.0 * 0.03
    assert by["T16"]["wc"][1] == pytest.approx(expected_tilt, abs=1e-9)
    # toe-in: the root-gap constant of T10 loses the 1.0 mm contact gap term
    assert by["T10"]["nominal"] == pytest.approx(0.0, abs=1e-9)    # as drawn it is 0.643 (the design V)
    t = scenarios.tally(res)
    assert t["n"] == 26 and t["pass"] + t["marginal"] + t["fail"] == 26
    # firmware round 2 (controls.md 6.4): the declined trip and slow-zone requests are alternatives, the base stacks count;
    # T09 (2026-10-16): the shipped floor theta_c0 - 4.9 deg is the pick for T09F, T09H and T09P
    assert {a["id"] for a in also} == {"T05-deckpegs", "T09H", "T09P-trip7", "T09T-slow3"}
    assert by["T09P"]["id"] == "T09P-floor49" and by["T09T"]["id"] == "T09T" and by["T09F"]["id"] == "T09F-relfloor8"
    assert by["T09H"]["id"] == "T09H-relfloor8"


def test_sensitivity_scaling():
    fx = next(f for f in OVERLAY["sensitivity"]["factors"] if f["id"] == "xy_band")
    ov = scenarios.scaled_overrides(STACKS, {}, fx, 2.0)
    assert ov["fdm_xy_tol_short"] == pytest.approx(0.20) and ov["fdm_xy_tol"] == pytest.approx(0.40)
    ns, _ = load_constants(STACKS / "basis.yaml", ov)
    assert ns["plate_hole_pos_tol"] == pytest.approx(0.20)          # derived constants follow the scaled input
    half = scenarios.scaled_overrides(STACKS, {}, fx, 0.5)
    assert half["fdm_xy_tol_short"] == pytest.approx(0.05)
    # scaling starts from the design's own value, here rev B's graded pin clearance
    consts, _ = scenarios.case_plan(OVERLAY, "revb")
    f2 = {"id": "x", "consts": ["pin_clear"]}
    assert scenarios.scaled_overrides(STACKS, consts, f2, 2.0)["pin_clear"] == pytest.approx(0.040)
    # an input that cannot change a verdict leaves the table empty for it
    data = {"changes": [], "factors": [fx], "scales": [0.5, 2.0]}
    assert "No verdict changes" in "\n".join(scenarios.sens_tables(data))


def test_t09t_slow3_saving_is_0_125_s():
    res = {r["id"]: r for r in run_all([STACKS], n=20_000, only={"T09T", "T09T-slow3"})}
    saving = res["T09T"]["nominal"] - res["T09T-slow3"]["nominal"]
    assert saving == pytest.approx(3 / 20 - 3 / 120) == pytest.approx(0.125)
    assert saving != pytest.approx(0.15)


def test_t15_barycentric_weights_in_basis():
    # standoff tops at (-24.5, 13), (24.5, 13), (0, 15.5); pin B at (14.25, 0): plane weights of the three tops
    pts = np.array([[-24.5, 13.0], [24.5, 13.0], [0.0, 15.5]])
    A = np.vstack([pts.T, np.ones(3)])
    w = np.linalg.solve(A, np.array([14.25, 0.0, 1.0]))      # weights for (x, y, 1)
    ns, _ = load_constants(STACKS / "basis.yaml")
    assert w.sum() == pytest.approx(1.0)
    assert w[1] == pytest.approx(ns["w_near"], abs=5e-4)     # standoff on the pin's side
    assert w[0] == pytest.approx(ns["w_far"], abs=5e-4)
    assert w[2] == pytest.approx(ns["w_top"], abs=5e-4)
    assert ns["w_near"] + ns["w_far"] + ns["w_top"] == pytest.approx(1.0, abs=1e-9)


def test_results_store_repository_relative_paths(tmp_path):
    out = tmp_path / "out"
    assert tolstack.main(["run", str(STACKS / "T16_pin_tilt.yaml"), "--out", str(out), "--samples", "20000", "--no-doc"]) == 0
    r = json.loads((out / "T16.json").read_text(encoding="utf-8"))
    assert r["path"] == "analysis/gripper/tolstack/stacks/T16_pin_tilt.yaml"
    assert (REPO_ROOT / r["path"]).exists()
    assert "\\" not in r["path"] and ":" not in r["path"] and not r["path"].startswith("/")
    assert not (out / "figures").exists()                    # plots are opt-in
    # a rerun writes the same bytes
    first = (out / "T16.json").read_text(encoding="utf-8")
    tolstack.main(["run", str(STACKS / "T16_pin_tilt.yaml"), "--out", str(out), "--samples", "20000", "--no-doc"])
    assert (out / "T16.json").read_text(encoding="utf-8") == first


def test_stable_rounding_and_ppm_wording():
    assert report.stable({"a": [0.1 + 0.2, 1e-17 + 1.0]}) == {"a": [0.3, 1.0]}
    r = {"mc": {"out_pct": 0.004, "n": 100_000}}
    # Four events: exact 95% upper limit is 9.154 events, hence 91.54 ppm rounds up to 92 ppm.
    assert report.yield_str(r) == "99.996 % (<92 ppm (4 of 100,000 samples; 95% upper bound) out)"
    assert report.yield_str({"mc": {"out_pct": 0.024, "n": 100_000}}) == "99.976 % (240 ppm out)"


def test_count_line_reports_independent_failures():
    mk_ = lambda i, v, own: {"id": i, "role": "baseline", "verdict3": v, "own_verdict3": own}  # noqa: E731
    line = report.count_line([mk_("A", "fail", "fail"), mk_("B", "fail", "pass"), mk_("C", "pass", "pass")])
    assert "1 PASS, 0 MARGINAL, 2 FAIL as reported" in line
    assert "2 PASS, 0 MARGINAL, 1 independent FAIL" in line and "B reported as blocked" in line
