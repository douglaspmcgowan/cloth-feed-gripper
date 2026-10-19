"""Checks for linear.py against hand calculations and the plant laws.
Run from the repository root:  python -m pytest analysis/gripper/controls -q"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import linear as LN  # noqa: E402
import plant as P  # noqa: E402


def test_margins_of_a_delayed_integrator_match_hand_calc():
    # L = K/(j w) e^{-j w d}: crossover at w = K, PM = 90 - K d (rad -> deg); phase -180 at w = pi/(2 d),
    # GM = 1/|L| there = pi / (2 K d).
    K, d = 5.0, 0.03
    w = np.logspace(-1, 3, 200000)
    L = K / (1j * w) * np.exp(-1j * w * d)
    m = LN.margins(L, w)
    assert m["wc_rad_s"] == pytest.approx(K, rel=1e-3)
    assert m["pm_deg"] == pytest.approx(90.0 - math.degrees(K * d), abs=0.05)
    assert m["gm_db"] == pytest.approx(20 * math.log10(math.pi / (2 * K * d)), abs=0.02)


def test_contact_stiffness_matches_the_plant_numerically():
    p = P.nominal()
    pl = P.Plant(p)
    pl.cloth = True
    f0 = 5.0
    # closure s at f0, then dF/dtheta by a finite difference on the plant's own solver.
    ff = p["f_fold_n"]
    n = p["plies"]
    s0 = (P.finger_defl(f0, pl.kA, ff) + P.finger_defl(f0, pl.kB, ff)
          + P.cloth_comp(f0, p["k_ply_n_per_mm"] / n, p["phi_compact"] * n * p["ply_mm"]))
    ds = 1e-4
    dF = pl.force_from_closure(s0 + ds) - pl.force_from_closure(s0 - ds)
    k_num = dF / (2 * ds) * (2 * p["r_c_mm"] * math.pi / 180.0)
    assert LN.k_contact(p, f0) == pytest.approx(k_num, rel=2e-3)


def test_droop_reduces_gain_as_hand_calc():
    p = P.nominal()
    k_servo = p["tstall_nm_at_6v5"] / p["droop_deg_at_stall"]
    c_d = 2 * 0.065 / p["eta"] / k_servo
    assert LN.droop_factor(p, 1.0) == pytest.approx(1 / (1 + c_d))


def test_shipped_gains_have_margin_at_every_operating_point():
    for name, p, f0 in LN.operating_points():
        a = LN.analyse(p, f0, True)["worst frame phase"]
        assert a["pm_deg"] >= 45.0, name
        assert a["gm_db"] >= 6.0, name
        assert a["Ms"] <= 2.0, name
