"""Tests for the actuation trade model. Run from the repository root:
    python -m pytest analysis/gripper/actuation -q
Each test fails if the physics or a reference number were wrong."""
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import actuation_trade as T  # noqa: E402
import extras as X  # noqa: E402
import model as M  # noqa: E402

PT = M.PT
PT_ACT = {e["id"]: e for e in PT["runs"]["r40_design"]["actuators"]}


@pytest.fixture(scope="module")
def cfgs():
    configs, screened = M.build_configs()
    return {c["cfg"]: c for c in configs}, screened


def test_hold_torque_matches_payload_torque():
    # (2 F r_c + T x_f) / eta with F 5 N, r_c 65 mm, T 2 N, x_f 11.5 mm, eta 0.85
    assert M.t_req(5.0, 0.85) == pytest.approx(PT["grip"]["T_hold_Nm"], abs=1e-3)
    assert M.t_req(5.0, 1.0) == pytest.approx((2 * 5 * 65 + 2 * 11.5) / 1000, rel=1e-9)  # eta = 1 hand calc
    assert M.t_req(10.0, 0.85, tension=2.0) == pytest.approx(PT["grip"]["T_peak_Nm"], abs=1e-3)


@pytest.mark.parametrize("pid", ["A17", "A19", "A20"])
def test_hold_margin_and_lc3_match_payload_torque(cfgs, pid):
    """At payload_torque.py's design rail (6.5 +/- 0.15 V) the 40 % hold margin and LC3 mesh torque must equal its
    r40_design results for the same rows."""
    by, _ = cfgs
    c = dict(by[f"{pid}@1:1"])
    ref = PT_ACT[pid]
    vm = M.fnum(c["row"]["voltage_max_V"])
    c["V_rail"] = 6.5 if vm >= 6.65 else None
    if c["V_rail"] is None:  # payload_torque clamps the rail at the part's maximum
        c["V_rail"] = vm + M.V["V_rail_tol"]
        assert T.static(c)["hold_margin"] == pytest.approx(ref["hold_margin"], abs=2e-3)
        return
    s = T.static(c)
    assert s["hold_margin"] == pytest.approx(ref["hold_margin"], abs=2e-3)
    assert s["T_mesh_LC3_Nm"] == pytest.approx(ref["T_mesh_LC3_Nm"], abs=2e-3)


def test_reference_numbers_A17(cfgs):
    by, _ = cfgs
    s = T.static(by["A17@1:1"])
    assert s["hold_margin"] == pytest.approx(1.034, abs=1e-3)
    assert s["T_mesh_LC3_Nm"] == pytest.approx(2.09, abs=0.01)
    assert s["arm_util_C001_7p4V"] == pytest.approx(PT_ACT["A17"]["arm_util_C001_7p4V"], abs=2e-3)


def test_ratio_scales_hold_margin_by_N_eta(cfgs):
    by, _ = cfgs
    h1 = T.static(by["A17@1:1"])["hold_margin"]
    h2 = T.static(by["A17@2:1"])["hold_margin"]
    assert h2 / h1 == pytest.approx(2 * M.V["stage_eta"], rel=2e-3)
    assert T.static(by["A17@2:1"])["w0_jaw_dps"] == pytest.approx(T.static(by["A17@1:1"])["w0_jaw_dps"] / 2, rel=1e-3)


def test_hold_current_against_dyno_fits(cfgs):
    """dyno.md: at the 0.758 N*m hold the motor draws 0.80 A (Fit B, 2.2 A stall) and 1.35 A (Fit A, 3.77 A stall)
    with a 2.068 N*m stall. The linear zero-speed relation I = I_stall T / T_stall gives 0.81 / 1.38 A; dyno's
    motor model also carries no-load friction current and ripple, so agreement is held to 3 %."""
    Ts = M.CFG["SERVO_STALL_NM"]
    assert 2.2 * 0.758 / Ts == pytest.approx(0.80, rel=0.03)
    assert 3.77 * 0.758 / Ts == pytest.approx(1.35, rel=0.03)
    by, _ = cfgs
    # model at 6.5 V and the 0.792 N*m requirement: listed 2.2 A at 6.8 V scaled to 6.5 V, times 0.792 / 2.068, + 5 mA
    s = T.static(by["A17@1:1"])
    assert s["I_hold_A"] == pytest.approx(2.2 * 6.5 / 6.8 * 0.792 / 2.068 + 0.005, rel=0.01)


def test_fit_a_stall_current_relation(cfgs):
    """The rail-sizing current T_s w0 / (V 0.62) must reproduce dyno.md Fit A (3.77 A) for A17 at 6.5 V."""
    by, _ = cfgs
    c = by["A17@1:1"]
    assert M.stall_current_sizing(c, 6.5) == pytest.approx(3.77, rel=0.03)


def test_gear_safety_factor_fit():
    assert float(M.gear_sf(2.108)) == pytest.approx(1.61, abs=0.005)
    assert float(M.gear_sf(3.306)) == pytest.approx(1.12, abs=0.005)
    assert float(M.gear_sf(2.69)) == pytest.approx(1.33, abs=0.02)  # dyno jam shock SF
    assert M.gear_allow(1.0) == pytest.approx(3.81, abs=0.02)


def test_temperature_derating():
    assert float(M.derate_T(25.0)) == pytest.approx(1.0)
    hot = float(M.derate_T(125.0))
    assert hot == pytest.approx((1 - 0.2) / (1 + 0.393), rel=1e-3)


def test_sim_reproduces_firmware_sim():
    """The vectorised mirror against the compiled-firmware simulation (fw_sim.json, A17 1:1)."""
    fw = json.loads(M.FW_JSON.read_text(encoding="utf-8"))
    labs = {"R12 min": "0.88 R12 min", "FEA E56": "1.05 FEA E56+D7", "FEA E67": "1.24 FEA E67+D7", "R12 max": "1.63 R12 max"}
    jobs = []
    for kl, k in T.K_CASES.items():
        d = T.ref_lanes(k)
        d.update({kk: np.full(20, vv) for kk, vv in M.fw_profile().items()})
        jobs.append((kl, d))
    for kl, d, res in T.run_batch(jobs, ms=1500):
        ref = fw["cases"][labs[kl]]
        assert res["c0"].mean() == pytest.approx(ref["c0_deg"], abs=0.05)
        assert np.nanmean(res["t_contact"]) == pytest.approx(ref["t_contact_s"], abs=0.03)
        assert np.nanmean(res["t_45"]) == pytest.approx(ref["t_F90_s"], abs=0.03)
        assert res["F_peak"].mean() == pytest.approx(ref["F_max_N"], abs=0.3)
        assert res["F_final"].mean() == pytest.approx(ref["F_hold_mean_N"], abs=0.1)


def test_stall_limited_force():
    """A drive whose stall is below the hold need stalls at F = (T eta 1000 - T_ten x_f) / (2 r_c)."""
    d = T.ref_lanes(2 * 0.523)
    d["T_stall_motor"] = np.full(20, 0.5)
    d["tension"] = np.full(20, M.V["tension_N"])
    d.update({kk: np.full(20, vv) for kk, vv in M.fw_profile().items()})
    res = T.run_batch([("x", d)], ms=2000)[0][2]
    F_stall = (0.5 * 0.85 * 1000 - M.V["tension_N"] * M.V["x_f_mm"]) / (2 * M.R_C)
    assert res["F_final"].mean() == pytest.approx(F_stall, abs=0.15)
    assert res["F_final"].mean() < 4.0


def test_speed_limited_drive_closes_at_its_own_speed():
    """Limit case: a drive slower than the 20 deg/s slow-zone command (25 deg/s jaw speed against 120 deg/s
    commanded) never catches the command, so the jaw touches at travel / speed = (20 deg open + 0.31 deg ply) / 25
    = 0.81 s. Contact is declared later by the pulse pipeline (command tick 20 ms, pulse sampled 10 ms later, applied
    10 ms after that: 40 ms) and the force EMA reaching 0.5 N (about 30 ms): at most 0.08 s after touch."""
    d1, d2 = T.ref_lanes(1.0), T.ref_lanes(1.0)
    d2["w0_motor"] = np.full(20, 25.0)
    for d in (d1, d2):
        d.update({kk: np.full(20, vv) for kk, vv in M.fw_profile().items()})
    (_, _, r1), (_, _, r2) = T.run_batch([("a", d1), ("b", d2)], ms=1500)
    t_touch = (M.CFG["JAW_OPEN_DEG"] - M.TH_TOUCH_PLY) / 25.0
    assert t_touch < np.nanmean(r2["t_contact"]) < t_touch + 0.08
    assert np.nanmean(r2["t_contact"]) > np.nanmean(r1["t_contact"]) + 0.25


def test_cap8_stiffness_floor():
    f = T.cap8_floor()
    u8 = (8.0 - 0.5 - 0.5) / M.K_STIFF   # cap - F_CAP_MARGIN_N - F_TOUCH_N, as force_ctrl.h CTRL_U_MAX_DEG
    assert f["cap 8 N"]["U_MAX_deg"] == pytest.approx(u8, abs=1e-3)
    assert f["cap 8 N"]["k_tip_min_N_per_mm"] == pytest.approx(4.5 / u8 / (65 * math.pi / 180), abs=1e-3)
    assert f["cap 8 N"]["F_reachable_at_R12_min_N"] < 5.0 < f["cap 10 N"]["F_reachable_at_R12_min_N"]


def test_ranking_is_byte_stable_on_near_ties():
    """A sub-precision score gap ties at the written precision, then candidate key orders the pair."""
    w = {"a": 1.0, "b": 1.0}
    cfgs = [{"cfg": "B@1:1", "utilities": {"p": {"a": 0.5, "b": 0.5}}},
            {"cfg": "A@1:1", "utilities": {"p": {"a": 0.5004, "b": 0.5}}}]
    sc = T.scores(cfgs, w, "p")
    assert sc["A@1:1"] == sc["B@1:1"] == 0.5
    assert T.top(sc, sc) == "A@1:1" and T.top(reversed(list(sc)), sc) == "A@1:1"
    assert T.top([], sc) is None


def test_check_mode_reports_differing_keys_without_writing(tmp_path):
    original_json = b'{"ranking": [{"cfg": "A@1:1", "score": 0.5}]}'
    original_stdout = b"original\n"
    (tmp_path / "actuation_trade.json").write_bytes(original_json)
    (tmp_path / "actuation_trade_stdout.txt").write_bytes(original_stdout)
    differences = T.result_differences(b'{"ranking": [{"cfg": "A@1:1", "score": 0.501}]}', b"updated\n", tmp_path)
    assert differences == ["actuation_trade.json: $.ranking[0].score", "actuation_trade_stdout.txt: bytes differ"]
    assert (tmp_path / "actuation_trade.json").read_bytes() == original_json
    assert (tmp_path / "actuation_trade_stdout.txt").read_bytes() == original_stdout


def test_check_mode_matches_committed_result():
    result = subprocess.run([sys.executable, str(HERE / "actuation_trade.py"), "--check"], cwd=M.ROOT,
                            capture_output=True, text=True, timeout=1200)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    assert result.stdout.rstrip().endswith("actuation trade: results current")


def test_seeded_sampling_is_deterministic(cfgs):
    by, _ = cfgs
    c = by["A17@1:1"]
    a = T.lanes(c, 50, rng=np.random.default_rng(7))
    b = T.lanes(c, 50, rng=np.random.default_rng(7))
    for k in a:
        assert np.array_equal(a[k], b[k])


def test_vendor_claim_derate(cfgs):
    """A vendor-listing row's sampled stall torque averages 0.925 x (mean of U(0.85, 1.0)) the same row taken as a
    datasheet, with the same seed."""
    by, _ = cfgs
    c = by["A33@1:1"]
    assert c["evidence"] == "vendor claim"
    a = T.lanes(c, 4000, rng=np.random.default_rng(3))
    b = T.lanes(dict(c, evidence="datasheet"), 4000, rng=np.random.default_rng(3))
    assert (a["T_stall_cold"] / b["T_stall_cold"]).mean() == pytest.approx(0.925, abs=0.01)
    assert by["A34@1:1"]["evidence"] == "vendor claim"  # SG variant, gear ratio 342: the A19 datasheet (373) is not it
    assert by["A19@1:1"]["evidence"] == "datasheet"


def test_tie_rule_prefers_evidence():
    ranking = {"proposed": [{"cfg": "X@1:1", "score": 0.650, "eligible": True},
                            {"cfg": "Y@1:1", "score": 0.640, "eligible": True},
                            {"cfg": "Z@1:1", "score": 0.600, "eligible": True}]}
    ev = {"X@1:1": "vendor claim", "Y@1:1": "corroborated", "Z@1:1": "datasheet"}
    assert T.tie_pick(ranking["proposed"], ev, {k: 0.4 for k in ev}) == "Y@1:1"  # Z is outside the 0.02 band
    ev["Y@1:1"] = "vendor claim"
    assert T.tie_pick(ranking["proposed"], ev, {k: 0.4 for k in ev}) == "X@1:1"


def test_screen_keeps_r7_r8(cfgs):
    by, screened = cfgs
    ids = {s["id"] for s in screened}
    assert {"A21", "A22", "A23"} <= ids          # continuous rotation (R7)
    assert "L01" in ids                          # over $50 (R8)
    assert all(c["price_total"] <= 50 + M.V["dc_price_extra"] + 2 for c in by.values())


def test_note_section0_matches_json():
    """Section 0 of actuation_trade.md quotes the JSON's decision rows: a rerun that moves any of these numbers fails
    here until the note is rewritten."""
    data = json.loads((T.RES / "actuation_trade.json").read_text(encoding="utf-8"))
    note = (M.ROOT / "docs/gripper/analysis/actuation_trade.md").read_text(encoding="utf-8")
    sec0 = note.split("## 0. Answer")[1].split("## 1. What was compared")[0]
    head = note.split("## 0. Answer")[0]
    rows = data["decision"]["rows"]
    rec = data["recommendation"]
    assert rec["winner_proposed"] in ("A39@1:1", "A32@1:1") and rows["wait_for_backordered"]["cfg"] == "A32@1:1"
    assert data["decision"]["recommended"] == "wait_for_backordered"
    assert "Recommendation: wait for the backordered DSServo DS3230" in head
    for role, r in rows.items():
        assert f"${r['price_total_usd']:.2f}" in sec0
        assert f"{r['hold_margin']:.2f} / {r['hold_margin_p05']:.2f}" in sec0
        assert f"{r['P_R16_fw_cap10']:.2f} / {r['P_R16_fw_cap8']:.2f}" in sec0
        assert f"{r['hold_margin_hold6N_p50']:.2f} / {r['P_R16_hold6N']:.2f}" in sec0
        assert f"{r['F_peak_max_fw_cap10_N']:.2f} N" in sec0
        assert f"{r['t_close_p50_fw_cap8_s']:.3f} s" in sec0
        assert f"{r['arm']['util']:.3f} ± {r['arm']['u']:.3f}" in sec0
        assert f"{r['arm']['status']}" in sec0 or r["arm"]["status"] == "pass"
        # Since the firmware's squeeze-cap margin (F_CAP_MARGIN_N) the 8 N cap stops some soft fingers before 4.5 N:
        # P(R19 at 0.75 s) is just under 1 there, and the note quotes it.
        assert 0.98 <= r["P_R19_0.75s_fw_cap8"] <= 1.0 and f"{r['P_R19_0.75s_fw_cap8']:.3f} / " in sec0
        assert r["P_R15_fw_cap10"] == 1.0
    assert rows["order_today"]["arm"]["status"] == "marginal" and "marginal" in sec0
    assert f"**{rows['wait_for_backordered']['bench_floor_Nm_at_servo']:.2f} N·m**" in sec0 or \
        f"≥ {rows['wait_for_backordered']['bench_floor_Nm_at_servo']:.2f} N·m" in sec0
    w = rows["wait_for_backordered"]
    assert f"{w['I_hold_A_nominal']:.2f} / **{w['I_hold_p50_fw_cap8_A']:.2f}** / {w['I_hold_p95_fw_cap8_A']:.2f} A" in sec0
    assert "**45.1 %**" in sec0 and data["firmware_study"]["R14_true_force_met_share_present_servo"] == 0.451
    assert "Neither fixes the 45 % hold result by itself" in sec0
    assert "P(R19) with 4.5 N and an ideal sensor, 0.5 s / 0.75 s, 10 N cap (8 N cap at 0.75 s) | 0.00 / 1.00" in sec0
    assert "49.3 %" in sec0 and "recommendation and the purchase gate did not change" in sec0
    gt = data["gear_width_table"]["cases"]["A32@1:1"]
    assert f"{gt['min_width_mm_for_target']:.1f} mm" in sec0
    th = data["thermal_scaling_estimate"]["estimates"]
    k = "Fit B | pwm | no back-off | 25 C"
    assert f"{th['A32@1:1'][k]['case_C']:.1f} against {th['A17@1:1'][k]['case_C']:.1f} °C" in sec0
    assert "C:\\Users" not in note and "AppData" not in note
    assert "P(R14" not in sec0.replace("P(R14", "P(R14", 0) or "closed-loop true force" in sec0


# ------------------------------------------------------------------ review follow-up tests
def _by(cfgs):
    return cfgs[0]


def test_bench_floor_hand_calc(cfgs):
    by = _by(cfgs)
    hand = (2 * 5 * 65 + 2 * 11.5) / 1000 / 0.85 / 0.40          # 0.792 N*m / 0.40 = 1.979 N*m, 1:1
    assert X.bench_stall_floor(by["A32@1:1"]) == pytest.approx(hand, rel=1e-9)
    assert hand == pytest.approx(1.98, abs=0.005)
    assert X.bench_stall_floor(by["A17@1.5:1"]) == pytest.approx(hand / (1.5 * M.V["stage_eta"]), rel=1e-9)
    # a lower link efficiency raises the floor by the ratio of efficiencies on the 5 N term
    assert X.bench_stall_floor(by["A32@1:1"], 0.70) == pytest.approx((2 * 5 * 65 + 2 * 11.5) / 1000 / 0.70 / 0.40)
    # at that floor the model's hold margin at the rail low end is 1.0 for a unit exactly on the floor
    c = dict(by["A32@1:1"])
    assert T.hold_cap(c, X.bench_stall_floor(c) / 1.0) == pytest.approx(M.t_req(5.0, 0.85), rel=1e-9)


def test_thermal_estimate_reproduces_present_servo(cfgs):
    """For the present servo the scaling estimate must give back thermal.json's own numbers (ratio 1)."""
    by = _by(cfgs)
    th = json.loads(X.THERMAL_JSON.read_text(encoding="utf-8"))
    est = X.thermal_estimate(by["A17@1:1"])
    for fit, key in X.FITS.items():
        for cond in X.COND:
            for amb in (25, 40):
                m = th["step4b_mitigated_matrix"][f"{key}|{cond}|amb{amb}|backoff_none"]
                e = est[f"{fit} | {cond} | no back-off | {amb} C"]
                assert e["power_ratio_vs_present"] == pytest.approx(1.0, abs=0.01)
                assert e["case_C"] == pytest.approx(m["case_C"], abs=0.5)
                assert e["mount_C"] == pytest.approx(m["mount_C"], abs=0.5)
                mb = th["step4b_mitigated_matrix"][f"{key}|{cond}|amb{amb}|backoff_0.4225"]
                tol = 1.5 if cond == "avg" else 5.0                # scaling error, stated in the note
                assert est[f"{fit} | {cond} | back-off F1 | {amb} C"]["case_C"] == pytest.approx(mb["case_C"], abs=tol)


def test_thermal_estimate_orders_by_hold_heat(cfgs):
    by = _by(cfgs)
    ref = X.thermal_reference()
    # discontinuous conduction: heat ~ V I_stall f, so a stronger servo with a bigger stall current runs hotter in Fit B
    assert X.hold_power_ratio(by["A32@1:1"], "Fit B", "pwm", ref) > 1.0
    # continuous conduction: heat ~ V I_stall f^2, so the lower hold fraction wins
    assert X.hold_power_ratio(by["A32@1:1"], "Fit B", "avg", ref) < 1.0
    hand = (6.5 * M.stall_current(by["A32@1:1"], 6.5)[0] * (0.7647 / (float(X._stall_nom(by["A32@1:1"])))) ** 2) / \
           (6.5 * ref[("Fit B", "avg")]["I_stall_A"] * (0.7647 / M.CFG["SERVO_STALL_NM"]) ** 2)
    assert X.hold_power_ratio(by["A32@1:1"], "Fit B", "avg", ref) == pytest.approx(hand, rel=1e-9)


def test_gear_width_table_matches_gears_py(cfgs):
    configs, _ = M.build_configs()
    tab = X.gear_width_table(configs)["cases"]
    # SF falls with torque and rises with face width
    for case in tab.values():
        sf = [case["by_width"][str(b)]["SF_jam"] for b in X.WIDTHS]
        assert sf == sorted(sf)
    # the 8 mm jam-shock SF of A32 agrees with the study's two-point fit within the rounding of the note (1.02)
    assert tab["A32@1:1"]["by_width"]["8"]["SF_jam"] == pytest.approx(float(M.gear_sf(tab["A32@1:1"]["T_jam_Nm"])), abs=0.04)
    assert tab["A32@1:1"]["beyond_3p306_fit_point"] and tab["A19@1:1"]["beyond_3p306_fit_point"]
    # the stated width reaches the target and 0.5 mm less does not
    sys_path = str(M.ROOT / "analysis/gripper")
    import sys
    sys.path.insert(0, sys_path)
    import gears as G
    g = G.geometry(1.5, 19, 25, 0.0, G.V["jt_print_mm"])
    for cfg, case in tab.items():
        b = case["min_width_mm_for_target"]
        e = G.evaluate(g, b, "PA6-CF", T3=case["T_mesh_LC3_Nm"], Tsh=case["T_jam_Nm"])
        assert min(e["SF"]["F_LC3"], e["SF"]["F_shock"]) >= X.TARGET_SF - 0.002
        if b > 8:
            e = G.evaluate(g, b - 0.5, "PA6-CF", T3=case["T_mesh_LC3_Nm"], Tsh=case["T_jam_Nm"])
            assert min(e["SF"]["F_LC3"], e["SF"]["F_shock"]) < X.TARGET_SF


def test_arm_gate_marginal_band(cfgs):
    by = _by(cfgs)
    g32, g15, g11 = (X.arm_gate(by[k]) for k in ("A32@1:1", "A17@1.5:1", "A17@1:1"))
    assert g32["status"] == "pass" and g11["status"] == "pass"
    assert g15["status"] == "marginal" and g15["util"] > 1.0 > g15["util"] - g15["u"]
    assert g32["mass_at_util_1_g"] == pytest.approx((1 - M.ARM_A) / M.ARM_B, abs=0.05)
    # util is the fitted line at the stated mass
    assert g15["util"] == pytest.approx(M.ARM_A + M.ARM_B * g15["mass_g"], abs=1e-3)


def test_ideal_actuator_bounds_the_close_time():
    """R19: with zero lag and 5000 deg/s the 4.5 N event still falls after 0.5 s on the shipped profile, and first
    contact moves earlier by under 0.06 s; the claim therefore holds for 'F >= 4.5 N' and not for 'contact'."""
    T.PROFILE_PARAMS["fast"] = {"v_fast": 240.0, "slow_zone": 4.0, "a_dec": 1000.0}
    case = T.ideal_actuator_case()["cases"]
    ideal, ship = case["ideal actuator | fw profile"], case["shipped servo | fw profile"]
    assert ideal["FEA E56"]["t_45_s"] > 0.5
    assert 0.0 < ship["FEA E56"]["t_contact_s"] - ideal["FEA E56"]["t_contact_s"] < 0.06
    assert ideal["FEA E56"]["t_contact_s"] < 0.5 < ship["FEA E56"]["t_contact_s"]


def test_oat_has_low_stall_rows_and_scales_hold_margin(cfgs):
    by = _by(cfgs)
    c = by["A32@1:1"]
    jobs = []
    for name in ("base", "stall -20 %", "stall -30 %"):
        d = T.lanes(c, 20, nominal=T.OAT[name])
        d.update(T.fw_lanes(c, "fw", 10.0, 20))
        jobs.append(((name,), d))
    res = {k[0]: (d, rr) for k, d, rr in T.run_batch(jobs)}
    hm = {k: float(np.mean(T.hold_cap(dict(c, eta_stage=1.0), d["T_stall_cold"]) * d["eta_stage"] / M.t_req(5.0, d["eta_link"])))
          for k, (d, _) in res.items()}
    assert hm["stall -20 %"] == pytest.approx(0.8 * hm["base"], rel=5e-3)  # rail sag moves it slightly
    assert hm["stall -30 %"] == pytest.approx(0.7 * hm["base"], rel=5e-3)
    assert hm["stall -20 %"] == pytest.approx(1.15, abs=0.03) and hm["stall -30 %"] == pytest.approx(1.01, abs=0.03)


def test_hold_6N_margin_hand_calc(cfgs):
    by = _by(cfgs)
    c = by["A32@1:1"]
    base = T.static(c)["hold_margin"]
    six = M.t_req(T.HOLD_BIAS_SETPOINT_N, 0.85)
    assert T.HOLD_BIAS_SETPOINT_N == 6.0
    assert base * M.t_req(5.0, 0.85) / six == pytest.approx(1.20, abs=0.02)


def test_result_file_definitions_and_no_old_r14_keys():
    data = json.loads((T.RES / "actuation_trade.json").read_text(encoding="utf-8"))
    assert "P_R16_sim_force" in data["definitions"] and "R14_true_force_closed_loop" in data["definitions"]
    assert data["firmware_study"]["R14_true_force_met_share_present_servo"] == 0.451
    text = json.dumps(data)
    assert "P_R14" not in text
    c = next(c for c in data["configs"] if c["cfg"] == "A32@1:1")
    assert "P_sim_force_fw_cap10" in c["mc"] and "P_R16_fw_cap10" in c["mc"] and "P_R16_hold6N" in c["mc"]
    assert "C:\\Users" not in text
