"""Tests for the gripper test-plan scripts. Run: python -m pytest docs/gripper/test -q

Each physics or statistics test checks a hand calculation or a published table value,
so a wrong formula in test_plan.py fails here.
"""
import csv
import ast
import copy
import importlib.util
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


tp = _load("test_plan", HERE / "test_plan.py")
cm = _load("check_matrix", HERE / "check_matrix.py")
al = _load("analyze_log", HERE / "tools" / "analyze_log.py")
gl = _load("gripper_log", HERE / "tools" / "gripper_log.py")


@pytest.fixture(scope="module")
def out():
    return tp.main()


# --- statistics -------------------------------------------------------------
def test_tolerance_factor_matches_published_table():
    # One-sided normal tolerance factor, n = 10, 95 % coverage, 95 % confidence: 2.911
    # (NIST/SEMATECH e-Handbook 7.2.6.3 tables; Natrella 1963 Table A-7).
    assert tp.k_one_sided(10, 0.95, 0.95) == pytest.approx(2.911, abs=0.002)
    # n -> large: k -> z_0.95 = 1.645
    assert tp.k_one_sided(5000, 0.95, 0.90) == pytest.approx(1.645, abs=0.03)


def test_success_run_hand_calc():
    # 0.9**22 = 0.0985 <= 0.10 and 0.9**21 = 0.109 > 0.10
    assert tp.success_run_n(0.90, 0.90) == 22
    # 0.8**11 = 0.0859 <= 0.10 and 0.8**10 = 0.107 > 0.10
    assert tp.success_run_n(0.80, 0.90) == 11


def test_rss_budget_hand_calc():
    b = tp.budget([{"name": "a", "value": math.sqrt(3) * 3, "dist": "rect"},
                   {"name": "b", "value": 4.0, "dist": "normal"}])
    assert b["u_c"] == pytest.approx(5.0)
    assert b["U_k2"] == pytest.approx(10.0)


def test_analyze_log_k_table_matches_exact_factor():
    for n, k in al.K_95_90.items():
        assert k == pytest.approx(tp.k_one_sided(n), abs=0.002), n


# --- physics against hand calculations ---------------------------------------
def test_slip_capacity_two_faces(out):
    # Two friction faces: capacity = 2 mu F = 2 x 0.4 x 5 = 4.0 N, SF 2 against 2 N (DB R14)
    s = out["expected"]["slip"]
    assert s["capacity_N"] == pytest.approx(4.0)
    assert s["sf"] == pytest.approx(2.0)


def test_mass_moment_reproduces_design_basis(out):
    m = out["expected"]["mass"]
    # DB R10: 115.8 g x (309.1 + 40.7) mm = 40,507 g mm
    assert m["db_check_gmm"] == pytest.approx(40507, abs=2)
    # Budget 43,720 g mm is 125 g at 40 mm past H (DB R10 text)
    assert 43720 / (309.1 + 40.0) == pytest.approx(125.2, abs=0.1)
    assert m["max_mass_at_db_com_g"] == pytest.approx(43720 / 349.8, rel=1e-6)


def test_probe_sensitivity_hand_calc(out):
    # 1.0 mV/V x 3.3 V over 10 kg x 9.80665 = 98.07 N full scale -> 33.65 uV/N
    assert out["budgets"]["probe_sensitivity_uV_per_N"] == pytest.approx(3300 / 98.0665, rel=1e-6)
    # HX711 90 nV rms -> 0.0027 N rms
    assert out["budgets"]["probe_noise_N_rms"] == pytest.approx(0.090 / 33.65, rel=1e-3)


def test_squeeze_cap_matches_controls_note(out):
    # force_ctrl.h CTRL_U_MAX_DEG: U_max = (10 - 0.5 margin - 0.5 touch) / 1.849 = 4.87 deg (the margin, F_CAP_MARGIN_N,
    # entered the firmware with the gain schedule; before it the cap was (10 - 0.5) / 1.849 = 5.14 deg)
    assert out["expected"]["cap"]["written"]["U_max_deg"] == pytest.approx(4.867, abs=0.002)
    # 8 N basis, same margin: (8 - 0.5 - 0.5) / 1.849 = 3.786 deg
    assert out["expected"]["cap"]["proposed"]["U_max_deg"] == pytest.approx(7.0 / 1.8492, abs=0.002)
    # Softest R12 finger (0.88 N/mm) at r_c 65: K = 0.88 x 65 x pi/180 = 0.998 N/deg -> 0.5 + 3.786 x 0.998
    assert out["expected"]["cap"]["proposed"]["F_max_softest_R12_finger_N"] == pytest.approx(0.5 + 3.786 * 0.998, abs=0.01)


def test_stall_requirement_hand_calc(out):
    # Refreshed payload evidence: hold 0.793 N m at <= 40 % of stall.
    st = out["expected"]["stall"]
    assert st["stall_needed_Nm"] == pytest.approx(0.793 / 0.40)
    assert st["stall_needed_kgcm"] == pytest.approx(0.793 / 0.40 / 0.0980665)
    # Lever force at 50 mm: T / 0.05
    assert st["force_at_lever_N"] == pytest.approx(st["predicted_6p5V_Nm"] / 0.05)


def test_frame_phase_scatter_is_uniform_sigma(out):
    # Uniform over one 20 ms PWM frame: sigma = 20 / sqrt(12) = 5.77 ms
    assert out["expected"]["close_sigma_s"]["frame_phase"] == pytest.approx(0.020 / math.sqrt(12))


def test_life_demo_cycles_hand_calc(out):
    # Lipson, beta 2, R 0.9, C 0.5: (ln 0.5 / ln 0.9) ** 0.5 = 2.565 -> 2.56e5 cycles
    assert out["sample_sizes"]["R25_life"]["cycles_needed_one_unit"] == pytest.approx(2.565e5, rel=0.002)


def test_open_requirements_reported_at_both_values(out):
    assert set(out["expected"]["cap"]) == {"written", "proposed"}
    labels = {r["quantity"] for r in out["resolvability"] if r["req"] == "R19"}
    assert any("written" in q for q in labels) and any("proposed" in q for q in labels)


def _scale_numeric_leaves(value):
    if isinstance(value, dict):
        return {key: _scale_numeric_leaves(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scale_numeric_leaves(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_scale_numeric_leaves(item) for item in value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value * 1.1
    return copy.deepcopy(value)


def test_placeholders_follow_generator_data(out):
    original = tp.placeholder_values(out["expected"], out["budgets"], out["resolvability"])
    changed = tp.placeholder_values(_scale_numeric_leaves(out["expected"]),
                                    _scale_numeric_leaves(out["budgets"]),
                                    _scale_numeric_leaves(out["resolvability"]))
    assert len(original) == 41
    assert original.keys() == changed.keys()
    assert all(original[key] != changed[key] for key in original)


def test_placeholder_table_has_no_typed_quantity():
    tree = ast.parse((HERE / "test_plan.py").read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "placeholder_values")
    parents = {}
    for node in ast.walk(function):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    for node in ast.walk(function):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not any(char.isdigit() for char in node.value), node.value
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            parent = parents[node]
            assert isinstance(parent, ast.keyword) and parent.arg == "digits" and isinstance(node.value, int), node.value


def test_boundaries_match_rule(out):
    values = tp.placeholder_values(out["expected"], out["budgets"], out["resolvability"])
    rows = out["resolvability"]
    row = lambda start: next(item for item in rows if item["quantity"].startswith(start))
    cases = [
        ("tp01.pass_bound", "tp01.fail_bound", row("hold force, softest"), 3),
        ("tp04.written_pass", "tp04.written_fail", row("peak force, FSR"), 3),
        ("tp09.moment_pass", "tp09.moment_fail", row("mass-moment"), 5),
        ("tp09.rc_pass", "tp09.rc_fail", row("moment arm"), 4),
        ("tp12.pass_high", "tp12.fail_high", row("finger tip stiffness, high"), 3),
        ("tp13.rail_pass", "tp13.rail_fail", row("rail voltage band high"), 3),
    ]
    for pass_key, fail_key, criterion, digits in cases:
        rendered = tp.rule(criterion["limit"], criterion["U_k2"], criterion["unit"], criterion["side"], digits)
        pass_value = re.search(r"PASS if value [^ ]+? ([^;]+) \(limit", rendered).group(1)
        fail_value = re.search(r"FAIL if value [^ ]+? ([^;]+) \(limit", rendered).group(1)
        assert values[pass_key] == pass_value
        assert values[fail_key] == fail_value
    torque = row("stall torque")
    rendered = tp.rule(torque["limit"], torque["U_k2"], torque["unit"], torque["side"], 4)
    assert values["tp13.torque_pass"] == re.search(r"PASS if value [^ ]+? ([^;]+) \(limit", rendered).group(1)
    mount = tp.rule(out["expected"]["thermal_limits_C"]["bare_mount"], out["budgets"]["case_temp_C"]["U_k2"], "°C", "upper", 3)
    assert values["tp07.stop_low"] == re.search(r"FAIL if value [^ ]+? ([^;]+) \(limit", mount).group(1)


# --- coverage check -----------------------------------------------------------
def _db(tmp_path, ids):
    rows = "\n".join("| %s | x | y | z | w |" % i for i in ids)
    p = tmp_path / "DB.md"
    p.write_text("# DB\n\n## 1. Requirements\n\n| ID | R | V | S | P |\n|---|---|---|---|---|\n%s\n\n## 2. Load cases\n" % rows,
                 encoding="utf-8")
    return p


def _matrix(tmp_path, rows):
    p = tmp_path / "m.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "method", "procedure", "pass_criterion"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def test_check_matrix_fails_on_missing_row(tmp_path):
    proc = tmp_path / "procedures"
    proc.mkdir()
    (proc / "TP-01-x.md").write_text("x", encoding="utf-8")
    db = _db(tmp_path, ["R1", "R2"])
    m = _matrix(tmp_path, [{"id": "R1", "method": "Test", "procedure": "TP-01", "pass_criterion": "x"}])
    assert cm.main(["--design-basis", str(db), "--matrix", str(m), "--procedures", str(proc)]) == 1


def test_check_matrix_fails_on_missing_procedure_file(tmp_path):
    proc = tmp_path / "procedures"
    proc.mkdir()
    db = _db(tmp_path, ["R1"])
    m = _matrix(tmp_path, [{"id": "R1", "method": "Test", "procedure": "TP-07", "pass_criterion": "x"}])
    assert cm.main(["--design-basis", str(db), "--matrix", str(m), "--procedures", str(proc)]) == 1


def test_check_matrix_passes_when_complete(tmp_path):
    proc = tmp_path / "procedures"
    proc.mkdir()
    (proc / "TP-01-x.md").write_text("x", encoding="utf-8")
    db = _db(tmp_path, ["R1", "R2"])
    m = _matrix(tmp_path, [{"id": "R1", "method": "Test", "procedure": "TP-01", "pass_criterion": "x"},
                           {"id": "R2", "method": "Inspection", "procedure": "TP-01", "pass_criterion": "y"}])
    assert cm.main(["--design-basis", str(db), "--matrix", str(m), "--procedures", str(proc)]) == 0


def test_real_matrix_covers_design_basis(out):
    ids = cm.requirement_ids(tp.INPUT_FILES["design_basis"])
    assert len(ids) == 27
    assert [r["id"] for r in out["matrix"]] == ids


# --- log analysis -------------------------------------------------------------
def test_close_times_from_synthetic_log(tmp_path):
    # Command at 1000 ms, contact event at 1500 ms, force ramps 0 -> 6 N from 1500 to 1800 ms
    # (20 N/s per 20 ms frame), HOLD at 1750 ms. 4.5 N is crossed at 1725 ms.
    p = tmp_path / "log.csv"
    lines = [("1.0", "EVT CMD_GRIP 1000 5.00"), ("1.5", "EVT FSR_CONTACT 1500 0.50")]
    for ms in range(1500, 1820, 20):
        F = max(0.0, (ms - 1500) * 0.02)
        lines.append(("%.3f" % (ms / 1000), "ST CLOSE %d th=-1.00 F=%.2f sp=5.0 I=0.50 c0=-0.70 fault=NONE q=0 drop=0/0" % (ms, F)))
    lines.append(("1.75", "EVT ENTER_HOLD 1750"))
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["host_s", "line"])
        w.writerows(lines)
    rows = al.cmd_close(p)
    assert len(rows) == 1
    r = rows[0]
    assert r["t_contact_s"] == pytest.approx(0.500 - al.FSR_LAG_S)
    assert r["t_F4p5_s"] == pytest.approx(0.725 - al.FSR_LAG_S)
    assert r["t_F5_s"] == pytest.approx(0.750 - al.FSR_LAG_S)
    assert r["t_hold_s"] == pytest.approx(0.750)


# --- three outcomes (steps 1 and 2) ---------------------------------------------
def test_decide_three_outcomes_upper():
    # limit 65, U 0.049: clear below, clear above, inside the band
    assert al.decide(64.9, 65.0, 0.049, "upper") == "PASS"
    assert al.decide(65.2, 65.0, 0.049, "upper") == "FAIL"
    assert al.decide(65.0, 65.0, 0.049, "upper") == "INDETERMINATE"
    assert al.decide(64.96, 65.0, 0.049, "upper") == "INDETERMINATE"
    assert al.decide(65.04, 65.0, 0.049, "upper") == "INDETERMINATE"


def test_decide_three_outcomes_lower():
    assert al.decide(5.2, 5.0, 0.096, "lower") == "PASS"
    assert al.decide(4.8, 5.0, 0.096, "lower") == "FAIL"
    assert al.decide(5.0, 5.0, 0.096, "lower") == "INDETERMINATE"


def test_r17_reading_65p2_fails_and_is_one_sided(out):
    U = out["budgets"]["rc_mm"]["U_k2"]
    assert al.decide(65.2, 65.0, U, "upper") == "FAIL"
    assert al.decide(65.2, 65.0, 0.3, "upper") == "INDETERMINATE"  # a coarse gauge cannot call it
    assert al.decide(64.5, 65.0, U, "upper") == "PASS"             # a short arm is not a fail
    assert al.decide(64.0, 65.0, U, "upper") == "PASS"
    r17 = next(r for r in out["matrix"] if r["id"] == "R17")
    assert "64.5-65.5" not in r17["pass_criterion"] and "64.55" not in r17["pass_criterion"]
    assert "PASS if value ≤ 64.92 mm" in r17["pass_criterion"]


def test_analysis_tool_uncertainties_match_budgets(out):
    b = out["budgets"]
    assert al.U["contact_s"] == pytest.approx(b["close_time_eventlog_s"]["U_k2"], abs=2e-7)
    assert al.U["force_time_s"] == pytest.approx(b["force_time_stream_s"]["U_k2"], abs=2e-7)
    assert al.U["force_5N"] == pytest.approx(b["pad_force_5N"]["U_k2"], abs=2e-7)
    assert al.U["force_8N"] == pytest.approx(b["pad_force_8N"]["U_k2"], abs=2e-7)
    assert al.U["force_10N"] == pytest.approx(b["pad_force_10N"]["U_k2"], abs=2e-7)
    assert al.U["fault_s"] == pytest.approx(b["fault_timing_s"]["U_k2"], abs=2e-7)
    assert al.U["case_C"] == pytest.approx(b["case_temp_C"]["U_k2"], abs=2e-7)
    assert al.U["caliper_mm"] == pytest.approx(b["caliper_mm"]["U_k2"], abs=2e-7)
    assert al.U["rc_mm"] == pytest.approx(b["rc_mm"]["U_k2"], abs=2e-7)
    assert al.U["current_A"] == pytest.approx(b["current_A"]["U_k2"], abs=2e-7)


def _fault_log(tmp_path, status_ms, onset_ms, event_ms, begin_ms):
    p = tmp_path / "fault.csv"
    rows = []
    for ms in status_ms:
        current = 2.1 if onset_ms <= ms <= event_ms else 0.2
        theta = 1.0 if ms >= begin_ms else 0.0
        rows.append((ms / 1000, "ST CLOSE %d th=%.2f F=0.00 sp=5.0 I=%.2f" % (ms, theta, current)))
    rows += [(event_ms / 1000, "EVT FAULT_OVERCURRENT %d 2.10" % event_ms),
             (event_ms / 1000, "EVT FAULT_OVERCURRENT %d 2.10" % event_ms)]
    rows.sort(key=lambda row: row[0])
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["host_s", "line"])
        w.writerows(rows)
    return p


@pytest.mark.parametrize("status_ms,expected_u", [
    (list(range(80, 201, 20)), 20),                         # clean stream
    ([60, 100, 120, 140, 160, 180, 200], 40),             # dropped before onset
    ([80, 100, 120, 140, 160, 200, 220], 40),             # dropped before back-off
    ([70, 100, 120, 150, 170, 200, 220], 30),             # 20--30 ms jitter
])
def test_fault_timing_uses_observed_bracketing_gaps(tmp_path, capsys, status_ms, expected_u):
    p = _fault_log(tmp_path, status_ms, 100, 150, 200)
    assert al.main(["faults", str(p)]) == 0
    assert "observed U %d ms" % expected_u in capsys.readouterr().out


def test_fault_timing_210_ms_truth_cannot_pass_with_constant_u(tmp_path, capsys):
    # True endpoints can be 80 and 290 ms although first observations are 100 and 290 ms.
    p = _fault_log(tmp_path, [80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 290, 310], 100, 260, 290)
    assert al.main(["faults", str(p)]) == 0
    out = capsys.readouterr().out
    assert "onset to back-off 190 ms" in out
    assert "INDETERMINATE" in out and ": PASS" not in out


def test_fault_timing_voids_gap_over_ceiling(tmp_path, capsys):
    p = _fault_log(tmp_path, [40, 100, 120, 140, 160, 180, 200], 100, 160, 180)
    assert al.main(["faults", str(p)]) == 2
    assert "VOID: repeat run" in capsys.readouterr().out


def _close_log(tmp_path, t_contact_ms):
    """One close: command at 1000 ms, contact t_contact_ms later (FSR lag adds nothing to the
    contact event), force ramps afterwards."""
    p = tmp_path / "log.csv"
    c = 1000 + t_contact_ms
    lines = [("1.0", "EVT CMD_GRIP 1000 5.00"), ("%.3f" % (c / 1000), "EVT FSR_CONTACT %d 0.50" % c)]
    for ms in range(c, c + 320, 20):
        F = max(0.0, (ms - c) * 0.02)
        lines.append(("%.3f" % (ms / 1000), "ST CLOSE %d th=-1.00 F=%.2f sp=5.0 I=0.50 c0=-0.70 fault=NONE q=0 drop=0/0" % (ms, F)))
    lines.append(("%.3f" % ((c + 250) / 1000), "EVT ENTER_HOLD %d" % (c + 250)))
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["host_s", "line"])
        w.writerows(lines)
    return p


def _close_summary(tmp_path, capsys, t_contact_ms):
    # three identical closes -> sd 0 -> the 95/90 bound is the mean
    p = _close_log(tmp_path, t_contact_ms)
    text = p.read_text(encoding="utf-8").splitlines()
    rows = text[1:]
    third = []
    for i in range(3):
        for r in rows:
            host, line = r.split(",", 1)
            shift = i * 10.0
            if line.startswith("EVT") or line.startswith("ST"):
                parts = line.split()
                idx = 2
                parts[idx] = str(int(parts[idx]) + int(shift * 1000))
                third.append("%.3f,%s" % (float(host) + shift, " ".join(parts)))
    q = tmp_path / "three.csv"
    q.write_text("host_s,line\n" + "\n".join('%s' % t.replace(",", ",\"", 1) + '"' for t in third) + "\n", encoding="utf-8")
    al.cmd_close(q)
    return capsys.readouterr().out


def test_close_contact_pass_fail_indeterminate(tmp_path, capsys):
    # contact time printed = event time − 10.5 ms of FSR lag; ruled limit 0.75 s, U 3.6 ms
    out_pass = _close_summary(tmp_path, capsys, 730 + 10)   # 0.730 s: clear below
    out_fail = _close_summary(tmp_path, capsys, 770 + 10)   # 0.770 s: clear above
    out_ind = _close_summary(tmp_path, capsys, 750 + 10)    # 0.750 s: exactly on the limit
    line = lambda o: next(l for l in o.splitlines() if l.startswith("contact (R19"))
    assert line(out_pass).endswith("PASS")
    assert line(out_fail).endswith("FAIL")
    assert line(out_ind).endswith("INDETERMINATE")
    assert "INDETERMINATE: the value is within U" in out_ind


def test_probe_hold_pass_fail_indeterminate(tmp_path, capsys):
    def run(minimum, attribute=False, spread=0.0):
        g = tmp_path / ("g%s_%s.csv" % (minimum, spread))
        pr = tmp_path / ("p%s_%s.csv" % (minimum, spread))
        glines = ["host_s,line"]
        plines = ["host_s,line"]
        for i in range(3):
            t0 = 10.0 * i
            glines += ["%.3f,EVT ENTER_HOLD %d" % (t0, int(t0 * 1000)), "%.3f,EVT CMD_RELEASE %d" % (t0 + 5, int((t0 + 5) * 1000))]
            for k in range(10):
                plines.append('%.3f,"%d,%.3f,25"' % (t0 + 1 + 0.2 * k, 1000 * k, minimum + spread * i + 0.2 * (k == 0)))
        g.write_text("\n".join(glines) + "\n", encoding="utf-8")
        pr.write_text("\n".join(plines) + "\n", encoding="utf-8")
        al.cmd_probe(pr, g, attribute=attribute)
        return capsys.readouterr().out
    assert "R14 hold part: PASS" in run(5.5)
    # softest pair: minimums 5.2, 5.3, 5.4 each PASS but their 95/90 bound (k 5.31) does not
    assert "R14 hold part: FAIL" in run(5.2, spread=0.1)      # L = 5.3 - 5.31 x 0.1 = 4.77
    assert "R14 hold part: PASS" in run(5.2, attribute=True, spread=0.1)
    assert "R14 hold part: INDETERMINATE" in run(5.05, attribute=True)
    assert "R14 hold part: FAIL" in run(4.5)
    assert "R14 hold part: INDETERMINATE" in run(5.0)


# --- jaw speed (step 3) and R10 expected value (step 4) ----------------------------
def test_jaw_speed_hand_calc(out):
    js = out["expected"]["jaw_speed"]
    # firmware constant JAW_SPEED_NEAR_DPS = 20.0; 3 deg / 20 deg/s * 240 fps = 36 frames
    assert js["cmd_dps"] == 20.0 and js["n_frames"] == 36
    # slope SE = sigma*sqrt(12)/(dt*N^1.5), sigma = 0.5/sqrt(3) deg; U = 2 SE = 2.22 deg/s
    assert js["U_fit_dps"] == pytest.approx(2 * (0.5 / math.sqrt(3)) * math.sqrt(12) * 240 / 36 ** 1.5, rel=1e-9)
    assert js["U_fit_dps"] == pytest.approx(2.22, abs=0.01)


def test_jaw_speed_conforming_gripper_passes_and_defect_fails(out):
    js = out["expected"]["jaw_speed"]
    U, lim = js["U_fit_dps"], js["screening_limit_dps"]
    assert lim == 25
    assert js["verdict_command"] == "PASS"
    assert js["verdict_db_limit_on_jaw"] == "INDETERMINATE"      # why 20 cannot be the video criterion
    assert al.decide(21.0, lim, U, "upper") == "PASS"             # conforming jaw, 21 deg/s
    assert al.decide(20.0, lim, U, "upper") == "PASS"
    assert al.decide(30.0, lim, U, "upper") == "FAIL"             # the first-build defect (30 deg/s)


def test_r10_expected_is_cad_revision_b_failure(out):
    m = out["expected"]["mass"]
    fit_mass = json.loads((HERE.parents[2] / "cad/gripper/out/fitcheck.json").read_text(encoding="utf-8"))["mass"]
    assert m["cad_total_g"] == fit_mass["total_g_incl_cloth"]
    assert m["cad_com_mm"] == fit_mass["com_u_past_H"]
    assert m["cad_mass_moment_gmm"] == fit_mass["mass_moment_gmm"]
    assert m["cad_fraction_of_budget"] == fit_mass["budget_use"]
    assert m["cad_revision"] == fit_mass["revision"]
    assert m["reach_limit_com_mm"] == pytest.approx(43720 / 152.9, abs=0.1)
    assert m["full_reach_com_mm"] == pytest.approx(346.7, abs=0.1)
    row = next(r for r in out["resolvability"] if r["req"] == "R10")
    assert row["predicted"] == m["cad_mass_moment_gmm"] and row["predicted_verdict"] == "FAIL"
    r10 = next(r for r in out["matrix"] if r["id"] == "R10")
    assert str(int(m["cad_mass_moment_gmm"])) in r10["pass_criterion"].replace(",", "")
    tp14 = (HERE / "procedures/TP-14-work-cell.md").read_text(encoding="utf-8")
    assert "computed COM reach ≤ %.1f mm" % (m["reach_limit_com_mm"] - 3.0) in tp14
    source = (HERE / "test_plan.py").read_text(encoding="utf-8")
    assert all(literal not in source for literal in ("53130", "53,130", "153.2"))


def test_every_commanded_powered_pose_clears_reach_limit(out):
    mass = out["expected"]["mass"]
    for pose in mass["powered_pose_rules"]:
        if pose["commanded"]:
            assert pose["max_com_reach_mm"] <= mass["reach_limit_com_mm"] - 1.0
            assert pose["max_fingertip_reach_mm"] <= mass["work_cell_existing_fingertip_limit_mm"] - 1.0
        else:
            assert pose["name"] == "full extension"
            assert pose["com_reach_mm"] > mass["reach_limit_com_mm"]


def test_procedure_uncertainty_verdict_pairs_equal_matrix(out):
    pattern = re.compile(r"PASS if value [≤≥] ([0-9.]+) ([^ ]+) \(limit [−+] U\); FAIL if value [≤≥] ([0-9.]+) \2 \(limit [−+] U\)")
    matrix_by_proc = {}
    for row in out["matrix"]:
        for pid in re.findall(r"TP-\d\d", row["procedure"]):
            matrix_by_proc.setdefault(pid, []).extend(pattern.findall(row["pass_criterion"]))
    found = 0
    for path in (HERE / "procedures").glob("TP-*.md"):
        pairs = pattern.findall(path.read_text(encoding="utf-8"))
        if pairs:
            found += len(pairs)
            assert all(pair in matrix_by_proc.get(path.name[:5], []) for pair in pairs), path.name
    assert found >= 1


def test_revision_current_mass_figures_come_from_fitcheck_or_history(out):
    fit = json.loads((HERE.parents[2] / "cad/gripper/out/fitcheck.json").read_text(encoding="utf-8"))["mass"]
    current = (fit["total_g_incl_cloth"], fit["com_u_past_H"], fit["mass_moment_gmm"])
    for name in ("TP-09-mass-envelope.md", "TP-14-work-cell.md"):
        text = (HERE / "procedures" / name).read_text(encoding="utf-8")
        active = re.sub(r"<!-- history:begin -->.*?<!-- history:end -->", "", text, flags=re.S)
        for value in current:
            assert ("%.1f" % value if value < 1000 else "%.0f" % value) in active
        assert all(old not in active for old in ("115.8 g", "125.9 g", "144.4 g", "40.7 mm", "40,507 g·mm", "50,511 g·mm"))


# --- thermal cutoff (step 5) ---------------------------------------------------------
def _watch():
    w = object.__new__(gl.TempWatch)  # no serial port in the tests
    w.case_stop, w.mount_stop = gl.CASE_STOP_C, gl.MOUNT_STOP_C
    return w


def test_cutoff_temperatures_come_from_thermal_limits_minus_u(out):
    U = out["budgets"]["case_temp_C"]["U_k2"]
    assert gl.CASE_STOP_C == pytest.approx(60.0 - U, abs=0.05)    # thermal.md: R26 60 C
    assert gl.MOUNT_STOP_C == pytest.approx(50.0 - U, abs=0.05)   # thermal.md: bare PETG 50 C


def test_cutoff_trips_on_hot_case_hot_mount_nan_and_firmware_cutoff_line():
    w = _watch()
    assert w.check_line("1000,5.01,40.0,30.0,1") is None
    assert "case" in w.check_line("1000,5.01,58.4,30.0,1")
    assert "mount" in w.check_line("1000,5.01,40.0,48.5,1")
    assert "NaN" in w.check_line("1000,5.01,nan,30.0,1")
    assert w.check_line("# CUTOFF case 58.6 mount 41.0").startswith("probe board cut the rail")


def test_unattended_sequences_refuse_to_run_without_the_watch():
    for seq in ("cycle", "soak"):
        with pytest.raises(SystemExit):
            gl.main(["--port", "none", "--out", "none.csv", "--sequence", seq])


def test_thermal_stop_opens_jaw_and_ends_run():
    sent = []

    class FakeLink:
        def send(self, c):
            sent.append(c)

    class FakeWatch:
        def tripped(self):
            return "case 59.0 C >= 58.4 C"

    assert gl.thermal_stop(FakeLink(), FakeWatch(), "cycle 7") is True
    assert sent == ["R"]
    assert gl.thermal_stop(FakeLink(), None, "x") is False


def test_r26_row_has_case_and_mount_limits(out):
    r = next(x for x in out["matrix"] if x["id"] == "R26")
    assert "58.4" in r["pass_criterion"] and "48.4" in r["pass_criterion"] and "C3" in r["pass_criterion"]
    cols = next(p for p in out["procedures"] if p["id"] == "TP-07")["datasheet_columns"]
    assert "mount_C" in cols


def test_tp11_has_the_rev_b_measurement_gate():
    text = (HERE / "procedures" / "TP-11-printed-fit.md").read_text(encoding="utf-8")
    for needle in ("F. Servo body width", "3 servos", "shaft offset", "20.1", "20.5", "rev B", "INDETERMINATE"):
        assert needle in text, needle


# --- FSR record (step 8) and R14 sample size (step 9) -------------------------------------
def test_fsr_calibration_log_header_and_tp01_rules(out):
    header = (HERE / "datasheets" / "FSR-CAL.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("fsr_cal_id,") and "span" in header and "trigger" in header
    t = (HERE / "procedures" / "TP-01-pad-force.md").read_text(encoding="utf-8")
    for needle in ("5 % of the 0-10 N span", "0.5 N", "Before each session", "After an over-force event", "RAM only"):
        assert needle in t, needle


def test_r14_sample_size_covers_the_unfavourable_finger(out):
    ss = out["sample_sizes"]
    # Since F_HOLD_BIAS_N (firmware regulates 1 N above the setpoint) the softest finger holds at the
    # squeeze cap, 0.2 N over the limit: outside U, so each hold is decidable, but inside the 95/90
    # spread, so the softest pair is a zero-failure run on the per-hold minimums.
    U5 = out["budgets"]["pad_force_5N"]["U_k2"]
    soft = ss["R14_hold_softest"]
    assert U5 <= soft["margin"] and soft["rule"] != "tolerance bound clears"
    pf = ss["R14_hold_per_finger"]
    assert pf["fingers"] == 2 and pf["softest_mode"] == "attribute"
    assert pf["n_softest"] == ss["attribute_function"]["n"] and pf["n_stiffest"] == ss["R14_hold"]["n"]
    assert pf["n_total"] == pf["n_softest"] + pf["n_stiffest"]
    assert pf["n_bound_softest"] is None or pf["n_bound_softest"] > 30
    r14 = next(r for r in out["matrix"] if r["id"] == "R14")
    assert "softest finger pair" in r14["sample_size"] and "zero-failure run" in r14["sample_size"]
    assert "finger_pair" in next(p for p in out["procedures"] if p["id"] == "TP-01")["datasheet_columns"]


# --- common session header (step 10) ---------------------------------------------------
HEADER_KEYS = ["date", "tester", "unit_serial", "firmware", "ambient_C", "supply_V_at_servo", "instruments", "fsr_cal_id"]


def test_every_datasheet_has_the_common_header(out):
    sheets = sorted((HERE / "datasheets").glob("TP-*.csv"))
    assert len(sheets) == 16
    for p in sheets:
        lines = p.read_text(encoding="utf-8").splitlines()
        assert [l.split(",")[0] for l in lines[:8]] == ["#" + k for k in HEADER_KEYS], p.name
        assert not lines[8].startswith("#"), p.name  # the column row follows the header block
    for p in list((HERE / "datasheets").glob("TP-*.html")) + [HERE / "datasheets" / "SIGNOFF.html"]:
        t = p.read_text(encoding="utf-8")
        for label in ("Unit serial", "Firmware version or commit", "Ambient temperature", "Supply voltage measured at the servo",
                      "Instrument ids with calibration date", "FSR calibration id", "Tester", "Date (yyyy-mm-dd)"):
            assert label in t, (p.name, label)


# --- equipment alternatives and session 1 time (step 11) ----------------------------------
def test_alternatives_cover_the_four_instruments_with_changed_u():
    text = (HERE / "EQUIPMENT.md").read_text(encoding="utf-8")
    block = text.split("<!-- alternatives:begin -->")[1].split("<!-- alternatives:end -->")[0]
    for name in ("Bench supply", "Oscilloscope", "IR thermometer", "240 fps"):
        assert name in block
    assert "120 fps" in block and "60 fps" in block and "INA219" in block and "micros()" in block and "contact bead" in block


def test_camera_u_scales_with_frame_rate(out):
    alts = tp.alternatives(out["expected"], out["budgets"], tp.parse_config_h(tp.INPUT_FILES["config_h"]))
    cam = next(a for a in alts if "240 fps" in a["item"])
    assert "27.2 ms" in cam["u_after"] and "13.6 ms" in cam["u_after"]   # 2x and 4x the 6.8 ms of 240 fps


def test_session_1_time_includes_building_the_probe(out):
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    assert "probe build" in readme and "Build and calibrate the probe board" in readme
    row = next(l for l in readme.splitlines() if l.startswith("| 1 Parts") or "1 Parts, before assembly | 280" in l)
    assert "280" in readme


# --- firmware agreement (step 12) ----------------------------------------------------------
cf = _load("check_firmware", HERE / "check_firmware.py")


def test_procedures_and_tools_agree_with_the_firmware():
    assert cf.scan() == []
    n = cf.firmware_names()
    assert {"FSR_SHORT", "ZERO_BAD", "CAL_RANGE", "LIMIT", "OVERCURRENT", "OVERFORCE"} <= n["faults"]
    assert {"G", "R", "H", "C", "S", "STREAM", "CALF"} <= n["commands"]


def test_firmware_check_catches_an_unknown_name(tmp_path):
    root = tmp_path / "test"
    (root / "procedures").mkdir(parents=True)
    (root / "tools").mkdir()
    # FAULT_FSR_OPEN became a real fault in 29caa80; plant a name the firmware has never had.
    (root / "procedures" / "TP-99.md").write_text("Expect `EVT FAULT_FSR_LOOSE` and `FAULT_STUCK` and `ENTER_NOWHERE`.", encoding="utf-8")
    problems = cf.scan(cf.FW, root)
    assert len(problems) == 3


def test_tp16_covers_the_faults_the_firmware_has():
    t = (HERE / "procedures" / "TP-16-fault-detection.md").read_text(encoding="utf-8")
    n = cf.firmware_names()
    # Every fault code but those owned by another procedure (TP-04 over-force, TP-05 over-current / stall) and the
    # state timeouts has a TP-16 row.
    elsewhere = {"NONE", "OVERFORCE", "OVERCURRENT", "STALL", "TIMEOUT"}
    for fault in sorted(n["faults"] - elsewhere):
        assert "FAULT_" + fault in t, fault
    assert {"FSR_OPEN", "FSR_STUCK", "I_SENSOR", "LIMIT"} <= n["faults"]


def test_firmware_check_catches_a_stale_config_value(tmp_path):
    root = tmp_path / "test"
    (root / "procedures").mkdir(parents=True)
    (root / "tools").mkdir()
    # The pre-PR-20 short threshold; and a debug-build value that is correctly marked with the shipped one.
    (root / "procedures" / "TP-99.md").write_text(
        "Short above `FSR_SHORT_MV` 3150 mV. Debug: `FSR_STUCK_TOL_MV` 200 (shipped 0.5).", encoding="utf-8")
    problems = cf.scan(cf.FW, root)
    assert len(problems) == 1 and "FSR_SHORT_MV" in problems[0]


def test_hold_current_reads_ih_and_names_the_regime(tmp_path, capsys):
    for ih, word in ((0.40, "): continuous conduction"), (1.20, "): discontinuous conduction"), (0.75, "): INDETERMINATE")):
        p = tmp_path / ("soak_%.2f.csv" % ih)
        lines = ["host_s,line"]
        for i in range(3):
            t0 = 10000 * i
            lines.append("%.3f,EVT ENTER_HOLD %d" % (t0 / 1000, t0))
            lines.append("%.3f,EVT HOLD_I %d %.2f" % ((t0 + 400) / 1000, t0 + 400, ih))
            for k in range(1, 8):
                lines.append("%.3f,ST HOLD %d th=0 F=5.00 sp=5.0 I=0.50 c0=0.00 fault=NONE q=0 drop=0/0 Ih=%.2f bo=0.00"
                             % ((t0 + 500 * k) / 1000, t0 + 500 * k, ih))
            lines.append("%.3f,EVT CMD_RELEASE %d" % ((t0 + 4000) / 1000, t0 + 4000))
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        al.cmd_hold_current(p)
        o = capsys.readouterr().out
        assert "Ih (F4, back-off off): 3 holds, mean %.3f A" % ih in o and word in o.split("Ih (F4")[1]


def test_tp01_sheet_has_a_row_per_hold_and_time_follows_the_holds(out):
    n = out["sample_sizes"]["R14_hold_per_finger"]["n_total"]
    tp01 = next(p for p in out["procedures"] if p["id"] == "TP-01")
    assert tp01["datasheet_rows"] == n
    html = (HERE / "datasheets" / "TP-01.html").read_text(encoding="utf-8")
    assert html.count("<tr class='row'>") == n
    assert tp01["minutes"] == math.ceil(62 + (n - 12) * (25.5 + 5.0 + 1.0) / 60.0)


def test_tp05_has_a_stall_after_contact_and_tp07_reads_ih():
    t5 = (HERE / "procedures" / "TP-05-stall-backoff.md").read_text(encoding="utf-8")
    assert "Stall after contact" in t5 and "`STALL_CURRENT_HOLD_A`" in t5
    t7 = (HERE / "procedures" / "TP-07-thermal-soak.md").read_text(encoding="utf-8")
    assert "`Ih=`" in t7 and "EVT HOLD_I" in t7


# --- portability (step 13) -------------------------------------------------------------------
GENERATED = ["verification_matrix.csv", "test_plan_out.json", "test_plan_stdout.txt", "datasheets"]
BLOCK_FILES = ["VERIFICATION-MATRIX.md", "MEASUREMENT-SIZING.md", "EQUIPMENT.md", "README.md",
               "procedures/TP-05-stall-backoff.md", "procedures/TP-09-mass-envelope.md",
               "procedures/TP-14-work-cell.md", "procedures/TP-16-fault-detection.md"] + ["procedures/%s" % p.name for p in (HERE / "procedures").glob("TP-*.md") if "procedures/%s" % p.name not in {"procedures/TP-05-stall-backoff.md", "procedures/TP-09-mass-envelope.md", "procedures/TP-14-work-cell.md", "procedures/TP-16-fault-detection.md"}] + ["procedure_templates/%s" % p.name for p in (HERE / "procedure_templates").glob("TP-*.md")]


def test_regenerating_into_a_temporary_folder_reproduces_committed_files_byte_for_byte(tmp_path, monkeypatch):
    import shutil
    work = tmp_path / "test"
    work.mkdir()
    for name in BLOCK_FILES:   # the tables inside these are rewritten in place
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE / name, work / name)
    # every fully generated file is absent at the start, so it has to be produced from scratch
    monkeypatch.setattr(tp, "HERE", work)
    tp.main()
    committed = [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc",)]
    generated = [p for p in committed if p.name in ("verification_matrix.csv", "test_plan_out.json", "test_plan_stdout.txt")
                 or p.parent.name == "datasheets" or p.relative_to(HERE).as_posix() in BLOCK_FILES]
    assert len(generated) >= 3 + 34 + 4
    for p in generated:
        rel = p.relative_to(HERE)
        assert (work / rel).read_bytes() == p.read_bytes(), "not byte-identical: %s" % rel


def test_generated_files_use_lf_and_utf8_and_hold_no_absolute_paths():
    for p in list(HERE.glob("*.json")) + list(HERE.glob("*.csv")) + list(HERE.glob("*.txt")) + list((HERE / "datasheets").glob("*")):
        data = p.read_bytes()
        assert b"\r" not in data, p.name
        data.decode("utf-8")
        assert b"/home/" not in data and b"C:\\" not in data and b"/root/" not in data, p.name


def test_gitattributes_pins_line_endings():
    t = (HERE / ".gitattributes").read_text(encoding="utf-8")
    assert "eol=lf" in t and "*.csv" in t and "*.html" in t


def test_input_hash_ignores_line_endings(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_bytes(b"x\ny\n")
    b.write_bytes(b"x\r\ny\r\n")
    assert tp.sha16(a) == tp.sha16(b)


# --- reviewer follow-ups ----------------------------------------------------------------------
def test_hold_current_mean_over_last_holds(tmp_path, capsys):
    p = tmp_path / "soak.csv"
    lines = ["host_s,line"]
    for i in range(7):
        t0 = 10000 * i
        lines.append("%.3f,EVT ENTER_HOLD %d" % (t0 / 1000, t0))
        for k in range(1, 8):
            lines.append("%.3f,ST HOLD %d th=0 F=5.00 sp=5.0 I=%.2f" % ((t0 + 500 * k) / 1000, t0 + 500 * k, 0.80 if i < 2 else 1.00))
        lines.append("%.3f,EVT CMD_RELEASE %d" % ((t0 + 4000) / 1000, t0 + 4000))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    means = al.cmd_hold_current(p)
    assert len(means) == 5 and all(m == pytest.approx(1.00) for m in means)  # only the last five holds


def test_tp07_flow_has_enable_disable_and_one_terminal():
    t = (HERE / "procedures" / "TP-07-thermal-soak.md").read_text(encoding="utf-8")
    assert "type `l 61.6 51.6`" in t and "then `e`" in t and "type `x`" in t
    assert "Terminal 1" not in t and "--stop-case-c 61.6" in t and "A stop is a result" in t


def test_probe_cutoff_runs_independent_of_streaming():
    ino = (HERE / "tools" / "probe" / "probe.ino").read_text(encoding="utf-8")
    cut = ino.index("// Cutoff: every 100 ms")
    stream = ino.index("if (streaming && cell.is_ready())")
    assert cut < stream                      # the cutoff block comes first and is not inside the stream branch
    assert "<case_C>,<mount_C>,<rail_on>" in ino.split("\n")[2]

# --- committed-file checker -------------------------------------------------
cp = _load("check_procedures", HERE / "check_procedures.py")


def _copy_lint_tree(tmp_path):
    import shutil
    root = HERE.parents[2]
    for rel in cp.COPY_DIRS:
        shutil.copytree(root / rel, tmp_path / rel)
    return tmp_path


def test_committed_procedures_lint_without_regeneration():
    assert cp.lint_procedures(HERE.parents[2]) == []


@pytest.mark.parametrize("mutation,expected", [
    ("full_extension", "generated file is stale"),
    ("tp09_threshold", "generated file is stale"),
    ("legacy_mass", "non-current mass figure outside history"),
    ("tp05_u", "generated file is stale"),
    ("feed_before_gate", "powered pose appears before its reach gate"),
    ("shoulder_pan", "reach uses shoulder_pan axis"),
])
def test_checker_catches_reviewer_mutations(tmp_path, mutation, expected):
    root = _copy_lint_tree(tmp_path)
    procs = root / "docs/gripper/test/procedures"
    if mutation == "full_extension":
        p = procs / "TP-14-work-cell.md"
        p.write_text(p.read_text(encoding="utf-8").replace("full extension is not commanded", "command full extension with power"), encoding="utf-8")
    elif mutation == "tp09_threshold":
        p = procs / "TP-09-mass-envelope.md"
        p.write_text(p.read_text(encoding="utf-8").replace("43507", "43508", 1), encoding="utf-8")
    elif mutation == "legacy_mass":
        p = procs / "TP-09-mass-envelope.md"
        p.write_text(p.read_text(encoding="utf-8") + "\nCurrent mass: 144.4 g\n", encoding="utf-8")
    elif mutation == "tp05_u":
        p = procs / "TP-05-stall-backoff.md"
        p.write_text(p.read_text(encoding="utf-8").replace("gap over 40 ms", "gap over 41 ms"), encoding="utf-8")
    elif mutation == "feed_before_gate":
        p = procs / "TP-14-work-cell.md"
        p.write_text(p.read_text(encoding="utf-8").replace("7. Turn the arm motor rail off.", "7. Command the powered feed pose. Turn the arm motor rail off."), encoding="utf-8")
    else:
        p = procs / "TP-14-work-cell.md"
        p.write_text(p.read_text(encoding="utf-8").replace("shoulder_lift horn-screw centre", "shoulder_pan horn-screw centre"), encoding="utf-8")
        expected = "gate tp14-feed missing: shoulder_lift horn-screw centre"
    findings = cp.lint_procedures(root)
    assert any(expected in finding for finding in findings), findings


def _append_procedure(root, filename, text):
    path = root / "docs/gripper/test/procedures" / filename
    path.write_text(path.read_text(encoding="utf-8") + "\n" + text + "\n", encoding="utf-8")
    return cp.lint_procedures(root)


def _append_template_and_regenerate(root, filename, text):
    path = root / "docs/gripper/test/procedure_templates" / filename
    path.write_text(path.read_text(encoding="utf-8") + "\n" + text + "\n", encoding="utf-8")
    subprocess.run([sys.executable, "docs/gripper/test/test_plan.py"], cwd=root, check=True,
                   stdout=subprocess.DEVNULL)
    return cp.lint_procedures(root)


@pytest.mark.parametrize("filename,step,expected", [
    ("TP-14-work-cell.md", "12. Command the arm to an unmeasured powered pose.", "arm-power step outside generated region"),
    ("TP-03-close-time.md", "12. Command the arm to an unmeasured powered pose.", "arm-power step outside generated region"),
    ("TP-14-work-cell.md", "12. Drive the arm out to full reach and hold it there.", "arm-power step outside generated region"),
    ("TP-14-work-cell.md", "12. Energise the shoulder and elbow and raise the gripper to the feed height.", "arm-power step outside generated region"),
    ("TP-01-pad-force.md", "12. Turn the arm rail on.", "arm-power step outside generated region"),
    ("TP-14-work-cell.md", "12. Bring the arm to the feed pose.", "ambiguous hardware step"),
])
def test_structural_arm_power_mutations(tmp_path, filename, step, expected):
    findings = _append_procedure(_copy_lint_tree(tmp_path), filename, step)
    assert any(expected in finding and step in finding for finding in findings), findings


def test_generated_arm_step_rejects_unknown_pose(tmp_path):
    root = _copy_lint_tree(tmp_path)
    p = root / "docs/gripper/test/procedures/TP-14-work-cell.md"
    text = p.read_text(encoding="utf-8").replace("<!-- procedure-body:end -->", "12. Command the arm to the moon pose. <!-- poses:moon pose gate-records:moon -->\n<!-- procedure-body:end -->")
    p.write_text(text, encoding="utf-8")
    findings = cp.lint_procedures(root)
    assert any("pose moon pose has no matching gate record moon" in f for f in findings), findings


def test_generated_arm_step_rejects_forged_gate_datum(tmp_path):
    root = _copy_lint_tree(tmp_path)
    p = root / "docs/gripper/test/procedures/TP-14-work-cell.md"
    p.write_text(p.read_text(encoding="utf-8").replace("gate-records:tp14-feed|tp14-farthest", "gate-records:missing|tp14-farthest"), encoding="utf-8")
    findings = cp.lint_procedures(root)
    assert any("pose feed pose has no matching gate record missing" in f for f in findings), findings


@pytest.mark.parametrize("filename,step", [
    ("TP-14-work-cell.md", "12. Command the arm to full reach and hold."),
    ("TP-14-work-cell.md", "12. Command the arm to full reach and hold. <!-- poses:feed pose gates:7 quantity:reach -->"),
    ("TP-03-close-time.md", "12. Command the arm to full reach and hold."),
    ("TP-14-work-cell.md", "12. With the rail off, fit the prop; then command the arm to full reach and hold."),
])
def test_template_arm_power_is_rejected_after_regeneration(tmp_path, filename, step):
    findings = _append_template_and_regenerate(_copy_lint_tree(tmp_path), filename, step)
    assert any("procedure_templates/" + filename in f and "arm-power" in f for f in findings), findings


def test_clause_classification_strength():
    assert cp.classify_step("With the rail off, fit the prop; then command the arm to full reach and hold.") == "arm-power"
    assert cp.classify_step("Bring the arm to the feed pose.") == "ambiguous"
    assert cp.classify_step("With the rail off, move the arm by hand to the marked position.") == "unpowered"
    assert cp.classify_step("Run the analysis script and record its output.") == "neutral"


@pytest.mark.parametrize("mutation", ["move", "delete"])
def test_generated_arm_step_requires_earlier_gate(tmp_path, mutation):
    root = _copy_lint_tree(tmp_path)
    p = root / "docs/gripper/test/procedures/TP-14-work-cell.md"
    text = p.read_text(encoding="utf-8")
    powered = next(line for line in text.splitlines() if line.startswith("9. Only after the feed pose"))
    if mutation == "move":
        text = text.replace(powered + "\n", "")
        text = text.replace("7. Turn the arm motor rail off.", powered + "\n7. Turn the arm motor rail off.")
    else:
        text = re.sub(r"^7\..*$", "", text, flags=re.M)
    p.write_text(text, encoding="utf-8")
    findings = cp.lint_procedures(root)
    assert any("missing: earlier gate step" in f for f in findings), findings


def _regenerate(root):
    subprocess.run([sys.executable, "docs/gripper/test/test_plan.py", "--root", str(root)],
                   cwd=root, check=True, stdout=subprocess.DEVNULL)


def test_rule_a_rejects_appended_unmeasured_powered_template_step(tmp_path):
    root = _copy_lint_tree(tmp_path)
    path = root / "docs/gripper/test/procedure_templates/TP-14-work-cell.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n12. Command the arm to an unmeasured powered pose.\n", encoding="utf-8")
    _regenerate(root)
    findings = cp.lint_procedures(root)
    assert any("TP-14-work-cell.md step 12 powered or commanded arm pose has no gate record" in f for f in findings), findings


def test_rule_a_rejects_numbered_step_with_gate_measurement_deleted(tmp_path):
    root = _copy_lint_tree(tmp_path)
    _regenerate(root)
    path = root / "docs/gripper/test/procedures/TP-14-work-cell.md"
    text = re.sub(r"^7\..*gate-record:tp14-feed.*$", "7. [gate deleted] Turn the arm motor rail off.", path.read_text(encoding="utf-8"), flags=re.M)
    path.write_text(text, encoding="utf-8")
    findings = cp.lint_procedures(root)
    assert any("step 9 pose feed pose gate tp14-feed missing: feed pose" in f for f in findings), findings


def test_rule_a_rejects_gate_after_powered_step(tmp_path):
    root = _copy_lint_tree(tmp_path)
    _regenerate(root)
    path = root / "docs/gripper/test/procedures/TP-14-work-cell.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    gate = next(line for line in lines if line.startswith("7.") and "gate-record:tp14-feed" in line)
    lines.remove(gate)
    powered_index = next(i for i, line in enumerate(lines) if line.startswith("9. Only after"))
    lines.insert(powered_index + 1, gate)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    findings = cp.lint_procedures(root)
    assert any("step 9 pose feed pose gate tp14-feed missing: earlier gate step" in f for f in findings), findings


def test_rule_a_rejects_emitted_gate_datum_change(tmp_path):
    root = _copy_lint_tree(tmp_path)
    _regenerate(root)
    path = root / "docs/gripper/test/procedures/TP-14-work-cell.md"
    path.write_text(path.read_text(encoding="utf-8").replace("shoulder_lift horn-screw centre", "shoulder_pan horn-screw centre", 1), encoding="utf-8")
    findings = cp.lint_procedures(root)
    assert any("gate tp14-feed missing: shoulder_lift horn-screw centre" in f for f in findings), findings


def test_rule_a_rejects_powered_step_where_no_gate_record_exists(tmp_path):
    root = _copy_lint_tree(tmp_path)
    path = root / "docs/gripper/test/procedure_templates/TP-05-stall-backoff.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n12. Command the arm to a powered test pose.\n", encoding="utf-8")
    _regenerate(root)
    findings = cp.lint_procedures(root)
    assert any("TP-05-stall-backoff.md step 12 powered or commanded arm pose has no gate record" in f for f in findings), findings


@pytest.mark.parametrize("filename,text", [
    ("TP-05-stall-backoff.md", "PASS when the back-off begins within 190 ms."),
    ("TP-03-close-time.md", "A comparison reference is 0.51 s."),
    ("TP-09-mass-envelope.md", "A comparison reference is 43000 g·mm."),
])
def test_hand_written_threshold_numbers_violate_rule_b(tmp_path, filename, text):
    findings = _append_procedure(_copy_lint_tree(tmp_path), filename, text)
    assert any("rule B" in f for f in findings), findings


def test_template_contradiction_and_duplicate_after_regeneration(tmp_path):
    root = _copy_lint_tree(tmp_path)
    findings = _append_template_and_regenerate(root, "TP-05-stall-backoff.md", "PASS when the back-off begins within 190 ms.")
    assert any("rule B contradiction: 190 ms; generated 0.2 s" in f for f in findings), findings
    root = _copy_lint_tree(tmp_path / "duplicate")
    findings = _append_template_and_regenerate(root, "TP-05-stall-backoff.md", "PASS when back-off begins within 200 ms.")
    assert any("rule B duplicate: 200 ms" in f for f in findings), findings


def test_unknown_template_placeholder_stops_generator(tmp_path):
    root = _copy_lint_tree(tmp_path)
    path = root / "docs/gripper/test/procedure_templates/TP-05-stall-backoff.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n{{unknown.key}}\n", encoding="utf-8")
    run = subprocess.run([sys.executable, "docs/gripper/test/test_plan.py"], cwd=root, encoding="utf-8", capture_output=True)
    assert run.returncode and "unknown procedure template placeholder: unknown.key" in run.stderr


def test_literal_ceiling_is_shrink_only_and_placeholder_passes(tmp_path):
    root = _copy_lint_tree(tmp_path)
    findings = _append_template_and_regenerate(root, "TP-05-stall-backoff.md", "PASS when current is at most 17 A.")
    assert any("literal count 35 exceeds ceiling 34" in f for f in findings), findings
    root = _copy_lint_tree(tmp_path / "placeholder")
    findings = _append_template_and_regenerate(root, "TP-05-stall-backoff.md", "PASS within {{tp05.backoff_limit}}.")
    assert not any("literal count" in f or "duplicate" in f for f in findings), findings


def test_gripper_command_rejected_by_none_scope(tmp_path):
    step = "12. Send `G 5` to close the gripper."
    findings = _append_procedure(_copy_lint_tree(tmp_path), "TP-09-mass-envelope.md", step)
    assert any("gripper-power step forbidden by none scope" in f and step in f for f in findings), findings


@pytest.mark.parametrize("step", [
    "12. With the rail off, move the arm by hand to the marked position.",
    "12. Run the analysis script and record its output.",
])
def test_unpowered_and_neutral_steps_are_accepted(tmp_path, step):
    findings = _append_procedure(_copy_lint_tree(tmp_path), "TP-14-work-cell.md", step)
    assert not any(step in f and ("arm-power" in f or "ambiguous" in f) for f in findings), findings


def test_checker_accepts_crlf_procedures(tmp_path):
    root = _copy_lint_tree(tmp_path)
    for p in (root / "docs/gripper/test/procedures").glob("TP-*.md"):
        p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert cp.lint_procedures(root) == []


@pytest.mark.parametrize("filename,old,new", [
    ("TP-14-work-cell.md", "9. Only after the feed pose", "6. Only after the feed pose"),
    ("TP-09-mass-envelope.md", "144.4 g", "144.5 g"),
    ("TP-05-stall-backoff.md", "gap over 40 ms", "gap over 41 ms"),
    ("TP-16-fault-detection.md", "FSR NORMAL", "FSR OPEN"),
])
def test_round5_mutations_are_suite_failures(tmp_path, filename, old, new):
    root = _copy_lint_tree(tmp_path)
    p = root / "docs/gripper/test/procedures" / filename
    assert old in p.read_text(encoding="utf-8")
    p.write_text(p.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
    assert cp.lint_procedures(root), (filename, old, new)


def _text_io_without_encoding(path):
    """(line, call) for each text-mode read_text, write_text or open call in path that names no encoding."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ("read_text", "write_text", "open"):
            name, mode_index = func.attr, 0
        elif isinstance(func, ast.Name) and func.id == "open":
            name, mode_index = "open", 1
        else:
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        if name != "open":
            found.append((node.lineno, name))
            continue
        mode = next((kw.value for kw in node.keywords if kw.arg == "mode"), None)
        if mode is None and len(node.args) > mode_index:
            mode = node.args[mode_index]
        if mode is None or not isinstance(mode, ast.Constant) or "b" not in str(mode.value):
            found.append((node.lineno, name))
    return found


def test_text_io_in_test_sources_names_its_encoding():
    offenders = [f"{path.name}:{line} {name}() without encoding=" for path in sorted(HERE.glob("*.py"))
                 for line, name in _text_io_without_encoding(path)]
    assert not offenders, "\n".join(offenders)
