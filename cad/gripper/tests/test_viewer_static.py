import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
VIEWER = ROOT / "cad/gripper/viewer.html"
SOURCE = ROOT / "cad/gripper/viewer_src"
FIT_PATH = ROOT / "cad/gripper/out/fit3d.json"
REQ_PATH = ROOT / "cad/gripper/fit_requirements.json"
FIT_SHA256 = "1b80cebb002168f269c05dc97b7b32028b40c5a998bd4c99a490dbbd11f2cd46"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build(path):
    env = dict(os.environ)
    env["VW_OUT"] = str(path)
    subprocess.run(
        [sys.executable, str(SOURCE / "viewer_build.py")],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
    )
    return path.read_bytes()


@pytest.fixture(scope="module")
def data():
    return load(FIT_PATH), load(REQ_PATH)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    return build(tmp_path_factory.mktemp("viewer") / "viewer.html")


def pair_map(fit):
    return {row["a"] + "|" + row["b"]: row for row in fit["jaw_pairs"]}


def status(pair, requirement, allowance, governed=None):
    if requirement is None:
        return "governed elsewhere" if governed else "no requirement"
    margin = pair["d_min"] - requirement["minimum_clearance_mm"]
    if margin < 0:
        return "fail"
    return "at risk" if margin <= allowance else "met"


def headline_status(row):
    checks = [check["status"] for check in row.get("governing_checks", [])]
    if row["status"] != "governed elsewhere":
        return row["status"]
    if "fail" in checks or not checks:
        return "fail"
    return "at risk" if "at risk" in checks else row["status"]


def test_headline_counts_a_failing_or_at_risk_governed_row():
    row = {"status": "governed elsewhere", "governing_checks": [{"status": "met"}, {"status": "fail"}]}
    assert headline_status(row) == "fail"
    row["governing_checks"][1]["status"] = "at risk"
    assert headline_status(row) == "at risk"
    source = (SOURCE / "viewer_build.py").read_text(encoding="utf-8")
    assert "counts = {status: sum(headline_status(pair) == status" in source


def test_page_grades_governed_rows_and_shows_decimal_angles():
    source = (SOURCE / "vw_11.html").read_text(encoding="utf-8")
    assert 'checks.some(c=>c.status==="at risk")?"risk":"pass"' in source
    assert '"feature at risk"' in source
    assert "const deg=v=>fmt(v,Number.isInteger(" in source
    assert not re.search(r"fmt\([^(),]+,0\)\}°", source)
    assert "touching at ${deg(p.thmin)}°" in source


def position_words(at):
    words = []
    for value, negative, positive, zero in zip(
        at,
        ("left", "rear", "lower"),
        ("right", "front", "upper"),
        ("centre", "midline", "mid-height"),
    ):
        words.append(negative if value < -0.05 else positive if value > 0.05 else zero)
    return ", ".join(words)


def test_built_page_is_utf8(built):
    assert b'<meta charset="utf-8">' in built[:1024]
    assert "\ufffd" not in built.decode("utf-8")


def test_requirements_name_existing_pairs_and_sources(data):
    fit, spec = data
    pairs = pair_map(fit)
    changelog = (ROOT / "cad/gripper/CHANGELOG.md").read_text(encoding="utf-8")
    stacks = (ROOT / "docs/gripper/analysis/tolerance_stacks.md").read_text(encoding="utf-8")
    for key, requirement in spec["requirements"].items():
        assert key in pairs
        assert requirement["source"] in changelog or requirement["source"] in stacks
    for key, sources in spec["governed_elsewhere"].items():
        assert key in pairs
        assert sources
        assert all(source in spec["feature_requirements"] for source in sources)
        assert pairs[key]["status"] == "governed elsewhere"
        assert [check["requirement_id"] for check in pairs[key]["governing_checks"]] == sources
        assert all(check["status"] in ("met", "at risk") for check in pairs[key]["governing_checks"])
        for check in pairs[key]["governing_checks"]:
            rule = spec["feature_requirements"][check["requirement_id"]]
            assert rule["minimum_mm"] <= check["measured_mm"] <= rule["maximum_mm"]
    assert len(spec["governed_elsewhere"]) == 12
    assert not set(spec["governed_elsewhere"]) & set(spec["no_requirement"])


NAMES_A_CHECK = r"\bchecked by\b|\banaly[sz]\w*|\b[TBRF]\d+[A-Z]?\b|governed|controlled"


def test_no_requirement_reasons_have_no_governing_claim(data):
    _, spec = data
    for key, reason in spec["no_requirement"].items():
        assert key in spec["governed_elsewhere"] or not re.search(NAMES_A_CHECK, reason, re.IGNORECASE), key


@pytest.mark.parametrize("reason", (
    "Backlash and tooth contact are checked by the gear analysis.", "Covered by stack T07.",
    "See B4.", "Design-basis row R9.", "RISK F03 owns it.", "The gear analyses cover it."))
def test_reason_naming_a_check_is_refused(reason):
    assert re.search(NAMES_A_CHECK, reason, re.IGNORECASE)


def test_gear_mesh_is_graded_by_t07(data):
    fit, spec = data
    params = load(ROOT / "cad/gripper/params.json")
    mesh = pair_map(fit)["knuckle_a|knuckle_b"]
    assert "knuckle_a|knuckle_b" not in spec["no_requirement"]
    assert spec["governed_elsewhere"]["knuckle_a|knuckle_b"] == ["T07"]
    rule = spec["feature_requirements"]["T07"]
    assert (rule["minimum_mm"], rule["maximum_mm"]) == (0.05, 0.45)
    (check,) = mesh["governing_checks"]
    cos_alpha = math.cos(math.radians(params["gear"]["pressure_angle"]))
    assert check["measured_mm"] == pytest.approx(2 * mesh["d_min"] / cos_alpha, abs=2 * 0.0005 / cos_alpha + 0.0005)
    assert check["status"] == "met"


def test_dog_slot_pair_is_graded_by_f09(data):
    fit, spec = data
    pair = pair_map(fit)["fasteners_a|housing"]
    assert "fasteners_a|housing" not in spec["no_requirement"]
    assert "F09" in pair["requirement_id"]
    assert spec["requirements"]["fasteners_a|housing"]["source"] == "F09"
    assert spec["requirements"]["fasteners_a|housing"]["minimum_clearance_mm"] == 0.0
    assert pair["status"] == "met"
    assert all(value is not None and value > 0 for value in pair["d"].values())
    assert len(pair["d"]) == len(fit["thetas"])
    assert fit["detail"]["fasteners_a|housing"]["section"]
    assert len(spec["governed_elsewhere"]) == 12


def test_zero_margin_prints_without_a_sign():
    pytest.importorskip("cadquery")  # fit3d.py imports cadquery at load time
    sys.path.insert(0, str(SOURCE.parent))
    from fit3d import margin_text
    assert margin_text(-0.0) == margin_text(-1e-17) == "0.0000"
    assert margin_text(-0.0004) == "-0.0004"


def test_zero_margin_has_no_sign_in_the_verdict(data):
    fit, _ = data
    at_risk = fit["verdict"]["at_risk"]
    assert at_risk
    assert not any("-0.0000" in line for line in at_risk), at_risk
    assert not any(check["margin_mm"] == 0 and str(check["margin_mm"]).startswith("-")
                   for row in fit["jaw_pairs"] for check in row.get("governing_checks", []))
    built_headline = (SOURCE / "vw_11.html").read_text(encoding="utf-8")
    assert "F3.verdict.at_risk.join" in built_headline


def test_met_governing_checks_clear_the_rounding_resolution(data):
    fit, spec = data
    rounding = spec["sampling"]["rounding_allowance_mm"]
    checks = [check for row in fit["jaw_pairs"] for check in row.get("governing_checks", [])]
    assert checks
    for check in checks:
        rule = spec["feature_requirements"][check["requirement_id"]]
        margin = min(check["measured_mm"] - rule["minimum_mm"], rule["maximum_mm"] - check["measured_mm"])
        assert check["margin_mm"] == pytest.approx(margin, abs=0.0006)
        if check["status"] == "met":
            assert margin > rounding, check
        else:
            assert check["status"] == "at risk" and abs(check["margin_mm"]) <= rounding, check


def test_b4_assembly_disposition_is_recorded_in_audit(data):
    fit, spec = data
    expected = spec["feature_requirements"]["B4"]["disposition"]
    assert "Grade the drawn bore at assembly" in expected
    checks = [check for row in fit["jaw_pairs"] for check in row.get("governing_checks", [])
              if check["requirement_id"] == "B4"]
    assert checks
    assert all(check["disposition"] == expected for check in checks)


def test_required_pair_statuses(data):
    fit, spec = data
    pairs = pair_map(fit)
    requirements = spec["requirements"]
    allowances = spec["sampling"]["allowance_mm"]
    for key in ("horn|housing", "finger_a|knuckle_b", "knuckle_a|finger_b",
                "fasteners_a|finger_b", "finger_a|fasteners_b"):
        assert status(pairs[key], requirements[key], allowances[key]) == "met"
        assert pairs[key]["status"] == "met"
        assert fit["detail"][key]["section"]
        assert fit["detail"][key]["near"]
        assert fit["detail"][key]["tol"]
    assert status(pairs["horn|fasteners"], None, None) == "no requirement"


def test_fixed_allowances_and_current_sampling_margins(data):
    fit, spec = data
    pairs = pair_map(fit)
    thetas = fit["thetas"]
    rounding = spec["sampling"]["rounding_allowance_mm"]
    for key, recorded in spec["sampling"]["allowance_mm"].items():
        pair = pairs[key]
        values = [pair["d"].get(f"{theta:g}") for theta in thetas]
        index = values.index(pair["d_min"])
        changes = [abs(values[index] - values[j]) for j in (index - 1, index + 1) if 0 <= j < len(values)]
        observed_bound = max(changes, default=0) / 2 + rounding
        assert recorded == pytest.approx({"horn|housing": 0.0005, "fasteners_a|housing": 0.001,
                                          "fasteners_a|finger_b": 0.4065,
                                          "finger_a|fasteners_b": 0.4065}.get(key, 0.4155))
        required = spec["requirements"][key]["minimum_clearance_mm"]
        assert pair["d_min"] - required > max(recorded, observed_bound)


def test_page_has_no_fallback_numeric_requirement(built):
    source = (SOURCE / "vw_11.html").read_text(encoding="utf-8")
    assert "const TIGHT" not in source
    pair_block = source[source.index("function requirementStatus"):source.index("/* worst gap")]
    assert "DISPLAY_TIGHT" not in pair_block
    assert "requirementFor(p)" in source
    assert b'"fitreq":' in built


def test_embedded_pair_counts_match_audit_and_requirements(built, data):
    fit, spec = data
    embedded = json.loads(built.split(b"const D=", 1)[1].split(b";\nconst GLB_B64", 1)[0])
    page = embedded["fit3d"]
    counts = {word: sum(headline_status(row) == word for row in fit["jaw_pairs"])
              for word in ("fail", "at risk", "met", "governed elsewhere", "no requirement")}
    assert page["pair_status_counts"] == counts
    assert page["verdict"] == fit["verdict"]
    assert len(page["pairs"]) == len(fit["jaw_pairs"])
    for pair in page["pairs"]:
        key = pair["a"] + "|" + pair["b"]
        assert pair["status"] == status(pairs := pair_map(fit)[key], spec["requirements"].get(key),
                                        spec["sampling"]["allowance_mm"].get(key),
                                        spec["governed_elsewhere"].get(key))
        if pair["status"] == "no requirement":
            assert spec["no_requirement"][key]
        if pair["status"] == "governed elsewhere":
            assert pair["governing_checks"] == pairs["governing_checks"]


def test_arm_clearance_is_last_in_integration_notes():
    source = (SOURCE / "vw_11.html").read_text(encoding="utf-8")
    assert 'title:"Unverified arm clearance",st:"integration"' in source.replace("\n    ", "")
    assert '["integration","Unverified arm clearance"]' in source
    assert "integration:6" in source
    assert 'class="integration-heading"' in source
    assert 'integration:"open"' in source
    assert "ENV_OUT.forEach" in source


def test_overlap_titles_are_unique_and_discriminated(data):
    fit, _ = data
    overlaps = [row for row in fit["overlaps"] if row.get("theta") is None and row["cls"] == "error"]
    titles = [f'{row["b"]} at {position_words(row["at"])} overlaps the {row["a"]}' for row in overlaps]
    assert len(titles) == len(set(titles))
    source = (SOURCE / "vw_11.html").read_text(encoding="utf-8")
    assert "overlapPosition(o.at)" in source


def test_servo_name_keeps_case(built):
    source = (SOURCE / "vw_11.html").read_text(encoding="utf-8")
    assert "nm.toLowerCase()" not in source
    assert "`The ${nm} (${o.b})" in source
    assert b"DSServo DS3230 MG" in built


def test_finding_picker_label_is_short_and_full_reading_is_shown(built):
    # a 375 px select cuts a long label off: the picker shows the title only, and the full finding sits in #fitPickRead
    source = (SOURCE / "vw_11.html").read_text(encoding="utf-8")
    assert '<option value="${f.id}">${esc(f.title)}</option>' in source
    assert 'f.title+(f.title.includes(f.val)?"":": "+f.val)' in source
    assert '$("#fitPickRead").textContent=f?full:"Whole assembly"' in source
    assert 'id="fitPickRead"' in (SOURCE / "vw_2.html").read_text(encoding="utf-8")
    assert b'id="fitPickRead"' in built


def test_build_is_deterministic(tmp_path):
    first, second = build(tmp_path / "a.html"), build(tmp_path / "b.html")
    assert hashlib.sha256(first).digest() == hashlib.sha256(second).digest()
    assert first == second
    assert not re.search(rb"[A-Za-z]:\\[A-Za-z]", first)
    for slash in re.finditer(rb"\\", first):
        fragment = first[max(0, slash.start() - 256):slash.start() + 512]
        assert not re.search(rb"[A-Za-z0-9_.-]+\\[A-Za-z0-9_.-]+\\[A-Za-z0-9_.-]+", fragment)
    assert not re.search(rb"\b20\d{2}-\d{2}-\d{2}\b", first)


def test_committed_viewer_matches_build(built):
    assert VIEWER.read_bytes() == built


def test_stored_fit_audit_is_unchanged():
    assert hashlib.sha256(FIT_PATH.read_bytes()).hexdigest() == FIT_SHA256


def test_dependency_waiting_has_recovery_and_distinct_terminal_state():
    markup = (SOURCE / "vw_2.html").read_text(encoding="utf-8")
    engine = (SOURCE / "vw_6.html").read_text(encoding="utf-8")
    assert markup.count('class="v3dreload"') == 4
    assert markup.count('role="status" aria-live="polite"') == 4
    assert 'Still loading the 3D library.' in engine
    assert 'V3.stillTimer=setTimeout' in engine
    assert 'V3.failTimer=setTimeout' in engine
    assert 'V3.waiting=false;V3.failed=false;V3.started=false;init3D()' in engine
    assert 'if(!window.THREE&&!V3.failed)' in engine
    assert '},20000)' not in engine


def test_finding_frame_uses_projected_content_bounds():
    source = (SOURCE / "vw_11.html").read_text(encoding="utf-8")
    assert 'function findingFramePoints(f)' in source
    assert 'const pq=f.pair.p[thIdx(FST.th)]' in source
    assert 'new THREE.Vector3(-16,12,0)' in source
    assert 'halfW=Math.max' in source and 'halfH=Math.max' in source
    assert '/asp)*pad' in source
    assert '55)/Math.sqrt' not in source
