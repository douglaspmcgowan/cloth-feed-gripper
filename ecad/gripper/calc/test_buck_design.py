"""buck_design.py against the tactician's hand numbers and known limits."""
import math

import numpy as np

import _common as cm
import buck_design as bd
from _common import ELEC


def test_frequency_from_rt():
    assert math.isclose(bd.fsw_from_rt(243e3), 400e3, rel_tol=0.03)       # hand: about 400 kHz (399.8)


def test_inductor_ripple_at_12v():
    # hand: Vo (1 - Vo/Vin) / (L fsw) = 6.584 x 0.4513 / (10u x 400k) = 0.743 A
    assert math.isclose(bd.ripple_pp(6.584, 12.0, 10e-6, 400e3), 0.74, rel_tol=0.03)
    assert bd.ripple_pp(5.0, 5.0, 10e-6, 400e3) == 0.0                    # no step-down, no ripple


def test_setpoint():
    assert math.isclose(bd.setpoint(), 0.8 * (1 + (71.5 + 0.768) / 10.0), rel_tol=1e-12)
    assert math.isclose(bd.setpoint(), 6.5814, abs_tol=5e-4)
    lo, nom, hi = bd.setpoint_range()
    assert lo < nom < hi and math.isclose(nom, 6.5814, abs_tol=5e-4)


def test_uvlo():
    st, sp = bd.uvlo(ELEC['r_uvlo_top_ohm'], ELEC['r_uvlo_bot_ohm'])
    assert math.isclose(st, 9.0, rel_tol=0.03) and math.isclose(sp, 8.0, rel_tol=0.03)
    # no EN current and a 1:1 divider -> twice the threshold
    s0, _ = bd.uvlo(10e3, 10e3, ven=1.2, i1=0.0, ihys=0.0)
    assert math.isclose(s0, 2.4)


def test_margins_of_a_pure_integrator():
    # T = wc / s: crossover at wc/2pi, phase -90 deg -> PM 90 deg, no -180 crossing
    f = np.logspace(0, 5, 3000)
    wc = 2 * math.pi * 1000.0
    T = wc / (2j * np.pi * f)
    m = bd.margins(f, T)
    assert math.isclose(m['fc'], 1000.0, rel_tol=0.01)
    assert math.isclose(m['pm'], 90.0, abs_tol=0.5)
    assert m['gm'] == float('inf')


def test_margins_of_integrator_with_delay_like_poles():
    # T = wc / (s (1 + s/wp)^2) has a -180 crossing at w = wp; GM = -|T| there
    f = np.logspace(0, 6, 6000)
    s = 2j * np.pi * f
    wc, wp = 2 * math.pi * 1000.0, 2 * math.pi * 10000.0
    T = wc / (s * (1 + s / wp) ** 2)
    m = bd.margins(f, T)
    # |T| at w = wp is wc / (wp x |1 + j|^2) = wc / (2 wp) = 0.05 -> GM = 26.0 dB
    assert math.isclose(m['gm'], -20 * math.log10(wc / (2 * wp)), rel_tol=0.01)


def test_loop_gain_falls_with_frequency_and_ceramic_only_limit():
    f = np.array([10.0, 1e3, 1e5])
    T = bd.loop_T(f, iload=1.0)
    assert abs(T[0]) > abs(T[1]) > abs(T[2])
    # with every output capacitor vanishing, the output impedance rises: gain at 1 kHz must rise
    big = bd.loop_T(np.array([1e3]), cb=1e-6, cer_factor=0.01, wrist=False)
    assert abs(big[0]) > abs(T[1])


def test_design_passes_and_is_reported():
    r = bd.run()
    assert r['n_cases'] == 324
    assert r['pass'] is True and r['worst_pm'] >= 45.0 and r['worst_gm'] >= 10.0
    for x in r['ripple']:
        assert x['ton_over_min'] > 5                                       # on-time far above the 135 ns minimum
        assert x['imax_dc_for_ilim_min_A'] > 4.0                            # peak current limit leaves room for 3.8 A stall
