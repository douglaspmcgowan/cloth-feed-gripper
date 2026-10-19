"""Physics checks for plant.py against hand calculations and limit cases.
Run from the repository root:  python -m pytest analysis/gripper/controls -q"""
import math
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plant as P  # noqa: E402


def test_every_param_is_tagged_with_a_range():
    for k, (nom, lo, hi, tag, why) in P.PARAMS.items():
        assert tag in ("S", "D", "A"), k
        assert lo <= nom <= hi, k
        assert why, k


def test_finger_law_linear_at_small_load_and_bounded_by_fold():
    k, ff = 1.1, 8.88
    assert P.finger_force(0.01, k, ff) == pytest.approx(k * 0.01, rel=1e-4)      # tangent stiffness k at zero load
    assert P.finger_force(100.0, k, ff) < ff                                       # never past the fold load
    # Secant stiffness at 5 N is lower than k by atanh(x)/x, x = 5/8.88 (hand calc: 1.135 -> 12 % softer).
    d5 = P.finger_defl(5.0, k, ff)
    x = 5.0 / ff
    assert 5.0 / d5 == pytest.approx(k * x / math.atanh(x), rel=1e-6)
    assert P.finger_force(d5, k, ff) == pytest.approx(5.0, rel=1e-6)


def test_series_closure_matches_hand_calc():
    pl = P.Plant()
    pl.cloth = False
    # Bare pads: closure s splits over two equal fingers; small load is linear: F = k s / 2.
    assert pl.force_from_closure(0.1) == pytest.approx(1.10 * 0.05, rel=2e-3)
    pl.cloth = True
    p = pl.p
    f = pl.force_from_closure(1.0)
    k_c, c_max = p["k_ply_n_per_mm"], p["phi_compact"] * p["ply_mm"]
    s = P.finger_defl(f, pl.kA, p["f_fold_n"]) * 2 + P.cloth_comp(f, k_c, c_max)
    assert s == pytest.approx(1.0, rel=1e-6)
    # Cloth in series makes the stack softer than bare fingers at the same closure.
    pl.cloth = False
    assert f < pl.force_from_closure(1.0)


def test_touch_angle_one_ply():
    pl = P.Plant()
    pl.cloth = True
    # gap = 1 + 2 r_c theta_rad = 0.3 mm -> theta = -0.7 / 130 rad = -0.3085 deg (TA 2.1 quotes -0.31).
    assert pl.touch_theta() == pytest.approx(math.degrees(-0.7 / 130.0), abs=1e-9)


def test_voltage_scaling_hits_datasheet_points():
    assert P.speed_scale(6.5) == pytest.approx(1.0)
    assert P.speed_scale(6.8) == pytest.approx((0.20 - 0.02 * 1.5 / 1.8) / 0.18)
    assert P.torque_scale(5.0) * 2.876 == pytest.approx(26.0 * 0.0981, rel=2e-3)


def test_unloaded_servo_runs_at_rated_speed_and_settles_in_deadband():
    p = P.nominal()
    p["tau_s"] = 0.010   # fast loop, so the 15 deg move reaches the speed limit (15 / 0.04 = 375 > 327 deg/s)
    pl = P.Plant(p)
    us0 = 1500 + int(round(5.0 * P.US_PER_DEG))   # +5 deg: the bare pads touch near -0.4
    th, ts = [], []
    for t in range(1, 1001):
        pl.step(t, us0)
        th.append(pl.thA)
    v = max((th[i - 1] - th[i]) / 0.001 for i in range(1, len(th)))
    v_moving = p["v_set"] - p["r_src_ohm"] * (p["i_idle_a"] + 0.3 * (p["istall_a"] - p["i_idle_a"]))
    w0 = p["w0_dps_at_6v5"] * P.speed_scale(v_moving)
    assert v == pytest.approx(w0, rel=0.02)                       # rate-limited by the no-load speed
    target = (us0 - 1500) / P.US_PER_DEG
    assert abs(th[-1] - target) <= pl.db / 2 + 1e-6               # inside the deadband


def test_blocked_servo_draws_stall_current_and_sags_the_rail():
    p = P.nominal()
    pl = P.Plant(p)
    pl.blocked_at = 10.0
    for t in range(1, 1500):
        pl.step(t, 1500 + int(round(-10 * P.US_PER_DEG)))         # command 10 deg past the obstruction
    assert pl.T == pytest.approx(pl.p["tstall_nm_at_6v5"] * P.torque_scale(pl.V), rel=1e-3)
    assert pl.I == pytest.approx(p["istall_a"], rel=1e-6)
    assert pl.V == pytest.approx(p["v_set"] - p["r_src_ohm"] * p["istall_a"], rel=1e-3)


def test_fsr_reads_offset_unloaded_and_divider_at_load():
    p = P.nominal()
    p["noise_mv"] = 0.0
    pl = P.Plant(p)
    assert pl.adc_mv() == pytest.approx(p["zero_mv"], abs=0.5)
    pl.F = 5.0
    pl.F_prev = 5.0
    r = P.FSR_R1N * 5.0 ** (-P.FSR_EXP)
    assert pl.adc_mv() == pytest.approx(3300 * 2700 / (r + 2700) + p["zero_mv"], abs=1.0)
    pl.fsr_open = True
    assert pl.adc_mv() == 0.0
    pl.fsr_open, pl.fsr_short = False, True
    assert pl.adc_mv() == p["adc_sat_mv"]


def test_fsr_creep_follows_log_time():
    p = P.nominal()
    pl = P.Plant(p)
    pl.F = pl.F_prev = 5.0
    pl.t_loaded = 99.999
    f = pl.fsr_reading_force()   # t_loaded -> 100 s: log10(101) = 2.004 decades
    assert f == pytest.approx(5.0 * (1 + p["drift_per_dec"] * math.log10(101.0)), rel=1e-4)


def test_sampling_is_deterministic():
    a = P.sample(random.Random(7))
    b = P.sample(random.Random(7))
    assert a == b
