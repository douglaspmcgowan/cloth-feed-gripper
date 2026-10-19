"""Tests for the thermal lane. Run: python3 -m pytest analysis/gripper/thermal -q

Each test would fail if the physics were wrong: hand-solved two-node network, the
single-node exponential, the copper-resistance runaway closed form, the Churchill-Chu
correlation against a hand calculation, and an energy balance on the gripper model.
"""
from __future__ import annotations

import math
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import network as nw  # noqa: E402

SCRIPT = Path(__file__).with_name("thermal.py")


def two_node(P=4.0, C1=2.0, C2=40.0, G12=0.1, G2a=0.08, Ta=25.0):
    net = nw.Network(["w", "c"], np.array([C1, C2]))
    net.links.append((0, 1, G12))
    net.bounds.append((1, Ta, G2a))
    return net, (lambda t, T: np.array([P, 0.0]))


def test_two_node_steady_hand_solution():
    # Hand: T_c = Ta + P/G2a = 25 + 4/0.08 = 75; T_w = T_c + P/G12 = 75 + 40 = 115
    net, pw = two_node()
    T, ok = net.steady(pw, np.array([25.0, 25.0]))
    assert ok
    assert T[1] == pytest.approx(75.0, abs=1e-6)
    assert T[0] == pytest.approx(115.0, abs=1e-6)


def test_two_node_transient_matches_closed_form():
    # Closed form: dT/dt = A (T - Ta) + b, solved by eigen-decomposition of A
    P, C1, C2, G12, G2a, Ta = 4.0, 2.0, 40.0, 0.1, 0.08, 25.0
    net, pw = two_node(P, C1, C2, G12, G2a, Ta)
    ts, Ts = net.transient(pw, np.array([Ta, Ta]), 1200.0, 0.05)
    A = np.array([[-G12 / C1, G12 / C1], [G12 / C2, -(G12 + G2a) / C2]])
    b = np.array([P / C1, 0.0])
    x_inf = -np.linalg.solve(A, b)
    lam, V = np.linalg.eig(A)
    c = np.linalg.solve(V, -x_inf)
    for t in (10.0, 100.0, 600.0, 1200.0):
        x = x_inf + (V @ (c * np.exp(lam * t))).real
        k = int(round(t / 0.05))
        assert Ts[k, 0] - Ta == pytest.approx(x[0], rel=1e-4)
        assert Ts[k, 1] - Ta == pytest.approx(x[1], rel=1e-4)


def test_single_node_time_constant():
    # T(tau) - Ta = P R (1 - e^-1)
    net = nw.Network(["c"], np.array([50.0]))
    net.bounds.append((0, 20.0, 0.1))
    ts, Ts = net.transient(lambda t, T: np.array([2.0]), np.array([20.0]), 500.0, 0.1)
    assert Ts[-1, 0] - 20.0 == pytest.approx(20.0 * (1 - math.exp(-1)), rel=1e-5)


def test_copper_runaway_closed_form():
    # P = I^2 R0 (1 + a (T - 20)); one node to ambient Ta through R.
    # Steady: T - Ta = I^2 R0 (1 + a (Ta - 20)) R / (1 - I^2 R0 a R)
    I2R0, a, R, Ta = 2.0, 0.0039, 30.0, 25.0
    net = nw.Network(["w"], np.array([1.0]))
    net.bounds.append((0, Ta, 1.0 / R))
    T, ok = net.steady(lambda t, T: np.array([I2R0 * (1 + a * (T[0] - 20.0))]), np.array([Ta]))
    gain = nw.runaway_factor(I2R0 * a, R)
    assert gain < 1
    assert ok
    assert T[0] - Ta == pytest.approx(I2R0 * (1 + a * (Ta - 20)) * R / (1 - gain), rel=1e-8)


def test_churchill_chu_hand_value_and_limit():
    # Hand calculation at Ra 1e6, Pr 0.71: Nu = 16.56; Ra -> 0 gives 0.825^2
    assert nw.nu_vertical_churchill_chu(1e6, 0.71) == pytest.approx(16.56, abs=0.05)
    assert nw.nu_vertical_churchill_chu(0.0, 0.71) == pytest.approx(0.825 ** 2, rel=1e-12)


def test_small_plate_h_is_physical():
    # A 20 mm tall vertical plate 35 K above ambient: textbook range 5-15 W/m^2K convection,
    # radiation near 6-7 W/m^2K at eps 0.9.
    f = nw.Face("p", 0.02 * 0.04, "vertical", 0.02, eps=0.9)
    assert 6.0 < f.h_conv(60.0, 25.0) < 14.0
    assert 6.0 < f.h_rad(60.0, 25.0) < 7.5
    # convection grows with temperature difference (Nu ~ Ra^(1/4) in this range)
    assert f.h_conv(80.0, 25.0) > f.h_conv(40.0, 25.0)


def test_air_properties_hit_table_rows():
    p = nw.air(300.0 - 273.15)
    assert p["k"] == pytest.approx(0.02624)
    assert p["nu"] == pytest.approx(1.568e-5)


def test_gripper_model_energy_balance_and_ordering():
    import thermal as th
    m = th.build_model(th.Scenario())
    res = th.solve_steady(m)
    assert res["converged"]
    T = res["T"]
    # Heat in = heat out to every boundary
    P = m["power_avg"](0.0, T)
    out = sum(m["net"]._g(Gb, T) * (T[i] - Tb) for i, Tb, Gb in m["net"].bounds)
    assert out == pytest.approx(float(np.sum(P)), rel=1e-6)
    # Temperatures fall along the heat path: winding > case > housing wall > ambient
    n = m["net"]
    assert T[n.idx("winding")] > T[n.idx("case")] > T[n.idx("housing")] > m["sc"].T_amb
    assert T[n.idx("case")] > T[n.idx("finger_root")] > m["sc"].T_amb


def test_zero_power_stays_at_ambient():
    import thermal as th
    m = th.build_model(th.Scenario(force_N=0.0, idle_W=0.0, T_arm_offset_K=0.0, I_close_frac_stall=0.0))
    res = th.solve_steady(m)
    assert np.allclose(res["T"], m["sc"].T_amb, atol=1e-6)


# ---- physics checks on the gripper model (values hand-computed from T = 2 F r_c / eta and I = T / (K eta_g)) ----
def test_hold_torque_at_5N():
    import thermal as th
    assert th.hold_torque(5.0) == pytest.approx(0.792, abs=5e-4)
    assert th.hold_torque(6.0) == pytest.approx(0.944, abs=1e-3)


@pytest.mark.parametrize("fit,F,I", [("A_mech", 5.0, 1.690), ("B_elec", 5.0, 1.609),
                                     ("A_mech", 6.0, 2.015), ("B_elec", 6.0, 1.920)])
def test_hold_current_both_fits(fit, F, I):
    import thermal as th
    assert th.currents(th.Scenario(fit=fit, force_N=F))["I_hold_A"] == pytest.approx(I, abs=2e-3)


def test_backoff_heat_scales_with_factor_squared():
    import thermal as th
    base = th.Scenario()
    for f in (0.4225, 0.6, 0.8):
        sc = th.Scenario(hold_current_factor=f)
        p1 = th.heat_sources(base, 100.0)["P_hold_winding_W"]
        p2 = th.heat_sources(sc, 100.0)["P_hold_winding_W"]
        assert p2 / p1 == pytest.approx(f * f, rel=1e-9)
    # the discontinuous-conduction bound is linear in current, not quadratic
    pw = th.Scenario(conduction="pwm")
    r = th.heat_sources(replace_sc(pw, hold_current_factor=0.5), 100.0)["P_hold_winding_W"] / th.heat_sources(pw, 100.0)["P_hold_winding_W"]
    assert r == pytest.approx(0.5, rel=1e-9)


def replace_sc(sc, **kw):
    from dataclasses import replace
    return replace(sc, **kw)


def test_case_rises_with_ambient_one_for_one():
    import thermal as th
    for fit in ("A_mech", "B_elec"):
        lo = th.summary(th.Scenario(fit=fit, T_amb=25.0))["T_C"]["case"]
        hi = th.summary(th.Scenario(fit=fit, T_amb=40.0))["T_C"]["case"]
        assert hi - lo == pytest.approx(15.0, abs=0.3)  # film properties and R(T) bend it slightly


def test_case_temperature_rises_with_force():
    import thermal as th
    prev = -1.0
    for F in (2.0, 3.0, 4.0, 5.0, 6.0, 7.0):
        s = th.summary(th.Scenario(fit="B_elec", force_N=F))
        assert s["converged"]
        assert s["T_C"]["case"] > prev
        prev = s["T_C"]["case"]


def test_verdict_class_as_drawn():
    import thermal as th
    a = th.summary(th.Scenario(fit="A_mech"))
    b = th.summary(th.Scenario(fit="B_elec"))
    assert a["T_C"]["case"] > b["T_C"]["case"] > 60.0
    assert th.verdict_class(-1.0, -1.0, 1.0) == "safe with a limit"
    assert th.verdict_class(-1.0, -1.0, -1.0) == "not safe"
    assert th.verdict_class(1.0, 1.0, 1.0) == "safe"


def test_sha16_ignores_line_endings(tmp_path):
    import thermal as th
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_bytes(b"x\ny\n")
    b.write_bytes(b"x\r\ny\r\n")
    assert th.sha16(a) == th.sha16(b)


def test_ds3230_inputs_are_owned_sources():
    import thermal as th
    assert th.SV["model"] == "DSServo DS3230 MG"
    assert th.SV["mass_g"] == 60
    assert th.SV["body_y"] == 40.0 and th.SV["body_x"] == 20.1 and th.SV["overall_h"] == 40.5
    assert th.motor_fit("B_elec", 6.5)["I_stall_A"] == pytest.approx(3.8)
    assert th.motor_fit("A_mech", 6.5)["I_stall_A"] == pytest.approx(3.99)


def test_master_force_and_close_requirements_are_live_inputs():
    import thermal as th
    assert th.CONFIG["F_SET_MAX_N"] == pytest.approx(6.5)
    assert th.R19_CLOSE_S == pytest.approx(0.75)
    assert th.Scenario().t_close == pytest.approx(th.R19_CLOSE_S)


def test_t1_numbers_and_revision_b_exposure():
    import thermal as th
    assert th.SV["stall_torque_kgcm"]["6.5V"] * 0.0980665 == pytest.approx(2.877, abs=1e-3)
    assert th.hold_torque(5) == pytest.approx(0.792, abs=5e-4)
    assert th.hold_torque(6) == pytest.approx(0.944, abs=1e-3)
    assert th.GEO["z_out"] * 1000 == pytest.approx(25.5)


def test_generated_note_table_equals_json():
    import re
    import thermal as th
    result = json.loads((th.OUT_DIR / "thermal.json").read_text(encoding="utf-8"))
    note = th.P_NOTE.read_text(encoding="utf-8")
    block = note.split("<!-- THERMAL-R26:BEGIN -->", 1)[1].split("<!-- THERMAL-R26:END -->", 1)[0]
    rows = []
    for line in block.splitlines():
        if not line.startswith("|") or "---" in line or "Reading" in line:
            continue
        c = [x.strip() for x in line.strip("|").split("|")]
        rows.append({"reading": c[0], "conduction": c[1], "backoff": c[2], "ambient_C": int(c[3]),
                     "case_30min_C": float(c[4]), "case_steady_C": float(c[5]), "R26": c[6]})
    expected = [{k: row[k] for k in rows[0]} for row in result["r26_verdict_table"]]
    for row in expected:
        row["case_steady_C"] = round(row["case_steady_C"], 1)
    assert rows == expected


def test_check_passes_without_writing():
    import thermal as th
    paths = [th.OUT_DIR / "thermal.json", th.OUT_DIR / "thermal_stdout.txt", th.P_NOTE,
             th.FIG_DIR / "thermal_sensitivity.png", th.FIG_DIR / "thermal_transient_1h.png"]
    before = {path: path.read_bytes() for path in paths}
    run = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert {path: path.read_bytes() for path in paths} == before


def test_default_writes_lf_text_and_no_png(tmp_path):
    import thermal as th
    out = tmp_path / "results"
    note = tmp_path / "thermal.md"
    note.write_bytes(th.P_NOTE.read_bytes())
    run = subprocess.run([sys.executable, str(SCRIPT), "--output-dir", str(out), "--note", str(note)],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert not list(tmp_path.rglob("*.png"))
    for path in (out / "thermal.json", out / "thermal_stdout.txt", note):
        assert b"\r" not in path.read_bytes()


def test_check_reports_changed_numeric_key(tmp_path):
    import thermal as th
    out = tmp_path / "results"
    out.mkdir()
    result = json.loads((th.OUT_DIR / "thermal.json").read_text(encoding="utf-8"))
    result["verdict"]["fitA_case_C"] += 1
    (out / "thermal.json").write_text(json.dumps(result), encoding="utf-8", newline="\n")
    note = tmp_path / "thermal.md"
    note.write_bytes(th.P_NOTE.read_bytes())
    run = subprocess.run([sys.executable, str(SCRIPT), "--check", "--output-dir", str(out),
                          "--note", str(note)], capture_output=True, text=True)
    assert run.returncode != 0
    assert "verdict.fitA_case_C" in run.stdout


@pytest.mark.parametrize("ambient,conduction,duration", [
    (25.0, "avg", 1800.0), (40.0, "avg", 1800.0),
    (25.0, "pwm", 1800.0), (40.0, "pwm", 1800.0),
    (25.0, "avg", None), (40.0, "avg", None),
    (25.0, "pwm", None), (40.0, "pwm", None),
])
def test_each_acceptance_limit_hits_r26_and_one_percent_fails(ambient, conduction, duration):
    import thermal as th
    sc = th.Scenario(fit="A_mech", T_amb=ambient, conduction=conduction)
    solved = th.acceptance_limit(sc, duration)
    at_limit, _ = th.case_temperature_at(replace_sc(sc, hold_current_factor=solved["hold_current_factor"]), duration)
    over, _ = th.case_temperature_at(replace_sc(sc, hold_current_factor=solved["hold_current_factor"] * 1.01), duration)
    assert at_limit == pytest.approx(60.0, abs=0.05)
    assert over > 60.0


def test_acceptance_limit_falls_with_ambient_and_lower_r26_limit():
    import thermal as th
    base = th.Scenario(fit="A_mech", conduction="avg")
    at25 = th.acceptance_limit(replace_sc(base, T_amb=25.0), None)
    at40 = th.acceptance_limit(replace_sc(base, T_amb=40.0), None)
    at59 = th.acceptance_limit(replace_sc(base, T_amb=25.0), None, case_limit_C=59.0)
    assert at40["rail_limit_A"] < at25["rail_limit_A"]
    assert at59["rail_limit_A"] < at25["rail_limit_A"]


def test_verdict_flips_when_backoff_factor_is_raised():
    import thermal as th
    result = json.loads((th.OUT_DIR / "thermal.json").read_text(encoding="utf-8"))
    rows = result["acceptance"]["rows"]
    assert all(r["predicted_rail_A_backoff"] <= r["rail_limit_A"] for r in rows if r["conduction"] == "continuous")
    raised = 0.8
    hot = th.acceptance_limit(th.Scenario(fit="A_mech", conduction="avg", T_amb=40.0), None)
    _, winding = th.case_temperature_at(th.Scenario(fit="A_mech", conduction="avg", T_amb=40.0,
                                                      hold_current_factor=raised), None)
    predicted = th.heat_sources(th.Scenario(fit="A_mech", conduction="avg", T_amb=40.0,
                                             hold_current_factor=raised), winding)["I_rail_hold_A"]
    assert predicted > hot["rail_limit_A"]


def test_raised_backoff_changes_table_and_stale_note_fails_check(tmp_path):
    import copy
    import thermal as th
    committed = json.loads((th.OUT_DIR / "thermal.json").read_text(encoding="utf-8"))
    changed = copy.deepcopy(committed)
    hot = next(r for r in changed["acceptance"]["rows"]
               if r["ambient_C"] == 40 and r["conduction"] == "continuous" and r["duration"] == "steady")
    hot["predicted_rail_A_backoff"] = hot["rail_limit_A"] + 0.001
    changed_table = th.render_acceptance_table(changed["acceptance"]["rows"])
    assert "do not operate" in changed_table
    assert changed_table != th.render_acceptance_table(committed["acceptance"]["rows"])
    note_text = th.P_NOTE.read_text(encoding="utf-8")
    changed["_generated_note_table"] = note_text[note_text.index("<!-- THERMAL-R26:BEGIN -->"):note_text.index("<!-- THERMAL-R26:END -->") + len("<!-- THERMAL-R26:END -->")]
    changed["_generated_acceptance_table"] = changed_table
    changed["_generated_washer_block"] = note_text[note_text.index("<!-- THERMAL-WASHER:BEGIN -->"):note_text.index("<!-- THERMAL-WASHER:END -->") + len("<!-- THERMAL-WASHER:END -->")]
    out = tmp_path / "results"
    out.mkdir()
    serializable = {k: v for k, v in changed.items() if not k.startswith("_generated")}
    (out / "thermal.json").write_text(json.dumps(serializable), encoding="utf-8", newline="\n")
    note = tmp_path / "thermal.md"
    note.write_bytes(th.P_NOTE.read_bytes())
    problems = th.check_outputs(changed, out, note)
    assert "note.THERMAL-ACCEPT: generated table differs" in problems


def test_generated_acceptance_block_equals_results_file():
    import thermal as th
    result = json.loads((th.OUT_DIR / "thermal.json").read_text(encoding="utf-8"))
    note = th.P_NOTE.read_text(encoding="utf-8")
    block = note[note.index("<!-- THERMAL-ACCEPT:BEGIN -->"):note.index("<!-- THERMAL-ACCEPT:END -->") + len("<!-- THERMAL-ACCEPT:END -->")]
    assert block == th.render_acceptance_table(result["acceptance"]["rows"])


def test_minimum_washer_protrusion_rises_with_preload():
    import thermal as th
    assert th.washer_minimum_protrusion_mm(500) > th.washer_minimum_protrusion_mm(250) > 0
