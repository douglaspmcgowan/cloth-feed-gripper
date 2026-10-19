"""pytest for the force-loop simulation: the compiled firmware matches its config, and the key numbers
controls.md quotes hold. Run from the repository root:  python -m pytest analysis/gripper/firmware_sim -q"""
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402
import fwconfig  # noqa: E402
import sim  # noqa: E402

CFG = fwconfig.load()
DER = fwconfig.derived(CFG)


@pytest.fixture(scope="module")
def lib():
    return build.load()


@pytest.fixture(scope="module")
def out():
    return sim.run_all()


def test_compiled_gains_match_config_formulas(lib):
    assert lib.sim_k_stiff() == pytest.approx(DER["K_STIFF_N_PER_DEG"], rel=1e-5)
    assert lib.sim_kp() == pytest.approx(DER["CTRL_KP_DEG_PER_N"], rel=1e-5)
    assert lib.sim_ti() == pytest.approx(DER["CTRL_TI_S"], rel=1e-5)
    assert lib.sim_u_max() == pytest.approx(DER["CTRL_U_MAX_DEG"], rel=1e-5)
    assert lib.sim_lag_comp() == pytest.approx(DER["CTRL_LAG_COMP_DEG"], rel=1e-5)


def test_gain_values():
    # SIMC on the stiffest R12 finger: K = 1.63 N/mm * 65 mm * pi/180 = 1.849 N/deg.
    assert DER["K_STIFF_N_PER_DEG"] == pytest.approx(1.849, abs=1e-3)
    assert DER["CTRL_KP_DEG_PER_N"] == pytest.approx(0.040 / (1.849 * 0.090), abs=1e-3)
    assert DER["CTRL_TI_S"] == pytest.approx(0.040)
    # Squeeze cap: (10 - 0.5 margin - 0.5) / 1.849 = 4.87 deg past the touch reference (9.5 N basis, 2026-10-11).
    assert DER["CTRL_U_MAX_DEG"] == pytest.approx(4.867, abs=1e-3)


def test_position_floor_is_relative_to_the_calibrated_contact():
    # Round 2 (controls.md 6.4, tolerance_stacks.md T09F-relfloor): the force loop's floor is relative to theta_c0, so
    # the contact-angle spread no longer moves it. R15 8 N (2026-10-16, T09F-relfloor8): 4.9 deg, was 6.2 (10 N). The
    # absolute backstop stays at round 2's -10.2 (CAL_C0_MIN_DEG - 6.2): at or below the floor of the lowest calibrated
    # contact (-8.9), so it never cuts a calibrated grip, and inside DB R18's -11.
    assert CFG["JAW_FLOOR_BELOW_C0_DEG"] == pytest.approx(4.9)
    assert CFG["JAW_MIN_DEG"] == pytest.approx(-10.2)
    assert CFG["JAW_MIN_DEG"] <= CFG["CAL_C0_MIN_DEG"] - CFG["JAW_FLOOR_BELOW_C0_DEG"]
    assert CFG["JAW_MIN_DEG"] >= -11.0
    assert CFG["JAW_OPEN_DEG"] == pytest.approx(20.0)


def test_fsr_model_round_trip(lib):
    for f in (0.3, 0.5, 1, 3, 5, 8, 10):
        assert lib.sim_fsr_force_from_mv(lib.sim_fsr_mv_from_force(f)) == pytest.approx(f, rel=1e-3)
    # 10 N stays inside the ESP32 11 dB recommended range (2450 mV).
    assert lib.sim_fsr_mv_from_force(10.0) <= CFG["ADC_V_LINEAR_MAX_MV"] + 10


@pytest.mark.parametrize("label", [c[0] for c in sim.K_CASES])
def test_step_response_across_stiffness_window(out, label):
    m = out["cases"][label]
    # This is the W2b-1 linear plant (no softening, no droop); analysis/gripper/controls has the honest one.
    assert m["final_state"] == "HOLD"
    assert m["faults"] == []
    assert m["F_max_N"] < CFG["F_SOFT_LIMIT_N"]      # below the 7.5 N soft limit and the 8 N trip
    assert m["F_max_N"] <= CFG["F_CAP_N"]            # R15
    hi = 5.0 + CFG["F_HOLD_BIAS_N"] + CFG["CTRL_I_DB_HI_N"] + 0.05
    assert 5.0 <= m["F_hold_mean_N"] <= hi           # R14 hold >= 5 N (the soft finger stops at the cap, ~5.2 N)
    assert m["t_contact_s"] <= 0.75                  # R19 full close <= 0.75 s (ruling 2026-10-12; contact is 0.58-0.59 s)
    assert m["t_F90_s"] <= 0.75                      # 4.5 N within the ruled 0.75 s close (was 0.70, R19 open item O1)
    assert m["v_jaw_at_touch_plus_3_dps"] <= 21.5    # R19 last 3 deg at <= 20 deg/s (modelled jaw, not command)
    assert m["v_jaw_at_touch_plus_2_dps"] <= 20.5


def test_calibration_lands_on_the_half_newton_angle(out):
    for lab, k, _ in sim.K_CASES:
        m = out["cases"][lab]
        half_n = sim.TH_TOUCH_NOCLOTH - math.degrees(0.5 / (k * sim.R_C))
        assert CFG["CAL_C0_MIN_DEG"] <= m["c0_deg"] <= CFG["CAL_C0_MAX_DEG"]
        assert abs(m["c0_deg"] - half_n) <= 0.2, (lab, m["c0_deg"], half_n)


def test_sensor_noise(out):
    for n in out["noise"]:
        assert n["states"] == ["HOLD"]
        assert n["faults"] == []
        assert n["F_max_N"] < CFG["F_SOFT_LIMIT_N"]
        assert n["F_hold_min_N"] >= 5.0


def test_sensor_faults_never_exceed_the_cap(out):
    for key, v in out["sensor_faults"].items():
        if key.startswith("early_contact"):
            continue
        assert v["F_max_N"] <= CFG["F_CAP_N"] + 0.05, key


def test_early_contact_limits(out):
    # Contact 6-10 deg above the no-cloth touch (a fold or object, 13-23 mm, O9) on the linear plant with the stiffest R12
    # finger (the bound: no softening, no droop, no fold). R15 is 8 N (ruling 2026-10-12): with the 12 deg / 45 deg/s mid
    # zone every peak stays <= 8 N (controls.md 4.4). 6 and 10 deg hold; 8 deg peaks just above the 7.75 N trip and faults.
    f = out["sensor_faults"]
    peak = {d: f[f"early_contact_{d}deg@1.63"]["F_max_N"] for d in ("6", "8", "10")}
    assert max(peak.values()) <= 8.0
    assert peak["6"] < CFG["F_TRIP_N"]
    for d in ("6", "10"):
        assert f[f"early_contact_{d}deg@1.63"]["final_state"] == "HOLD"
    assert f["early_contact_8deg@1.63"]["final_state"] == "FAULT"


def test_setpoint_steps_and_slip(out):
    s = out["steps"]
    assert s["final_state"] == "HOLD"
    assert s["F_at_3_mean"] == pytest.approx(3.0 + CFG["F_HOLD_BIAS_N"], abs=0.15)
    # G 7 with k 1.0 stops at the squeeze cap: 0.5 + 1.134 N/deg * 4.87 deg = 6.0 N, never 7.
    assert 5.7 <= s["F_at_7_mean"] <= 6.1
    assert s["F_recovered_mean"] >= 5.0


def test_sweep_inside_window(out):
    for r in out["sweep_k"]:
        if 0.88 <= r["k"] <= 1.63:
            assert r["final_state"] == "HOLD"
            assert r["F_max_N"] < CFG["F_SOFT_LIMIT_N"]
