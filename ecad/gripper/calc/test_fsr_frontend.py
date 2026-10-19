"""fsr_frontend.py: divider, filter corner and resolution against hand numbers."""
import math

import _common as cm
import fsr_frontend as ff
from _common import ELEC


def test_divider_at_equal_resistances_is_half_the_supply():
    r = cm.fsr_r(3.0)
    assert math.isclose(cm.node_mv(3.0, r_fixed=r), 1650.0, rel_tol=1e-12)
    assert math.isclose(cm.node_mv(3.0, r_fixed=r, vcc_mv=3000.0), 1500.0, rel_tol=1e-12)


def test_hand_node_voltages():
    assert math.isclose(cm.node_mv(0.5), 661.0, rel_tol=0.03)         # hand: about 661 mV at 0.5 N
    assert math.isclose(cm.node_mv(10.0), 2457.0, rel_tol=0.03)       # hand: about 2457 mV at 10 N
    # power-law fit by hand: 6109 x 0.5^-0.8195 = 10781 ohm; 3300 x 2700 / (2700 + 10781) = 660.9
    assert math.isclose(cm.fsr_r(0.5), 10781.0, rel_tol=0.001)


def test_filter_corner_with_zero_source_is_159_hz():
    p = ff.filter_point(0.0)
    assert math.isclose(p['fc_Hz'], 159.0, rel_tol=0.01)               # 1 / (2 pi x 10k x 100n) = 159.15 Hz
    assert math.isclose(p['fc_Hz'], 1 / (2 * math.pi * 10e3 * 100e-9), rel_tol=1e-12)
    # at the corner the gain is -3 dB
    assert math.isclose(1 / math.sqrt(1 + (p['fc_Hz'] / p['fc_Hz']) ** 2), 0.70711, rel_tol=1e-4)
    # a real source resistance lowers the corner
    assert ff.filter_point(5.0)['fc_Hz'] < p['fc_Hz']
    gains = [p['atten_%dHz' % frequency] for frequency in cm.v('fsr_filter_gain_freqs_hz')]
    assert all(lower < upper for lower, upper in zip(reversed(gains), reversed(gains[:-1])))


def test_best_resistor_puts_the_cap_at_the_edge():
    for cap in (10.0, 8.0):
        exact, std = ff.best_resistor(cap)
        assert math.isclose(cm.node_mv(cap, exact), 2450.0, rel_tol=1e-9)
        assert cm.node_mv(cap, std) <= 2450.0 + 1e-9
        assert std <= exact < std * 1.06                                # the next E96 step is about 2.4 % above
    assert ff.best_resistor(8.0)[0] > ff.best_resistor(10.0)[0]


def test_resolution_rises_with_force_and_is_the_derivative():
    r = ELEC['r_fsr_fixed_ohm']
    assert ff.n_per_mv(10.0, r) > ff.n_per_mv(5.0, r) > ff.n_per_mv(0.5, r)       # the curve flattens at high force
    h = 1e-3
    d = (cm.node_mv(5.0 + h) - cm.node_mv(5.0 - h)) / (2 * h)          # mV per N
    assert math.isclose(ff.n_per_mv(5.0, r), 1 / d, rel_tol=1e-3)


def test_ema_tau_and_delay_budget():
    r = ff.run()
    assert math.isclose(r['ema_tau_s'], 9.49e-3, rel_tol=0.01)          # -1/(1 kHz x ln 0.9)
    assert r['filter_delay_pct_of_budget'] < 3.0                        # the RC adds about 1 ms against 76 ms
    assert r['adc']['charge_share_mV_at_2450'] < 1.0                    # 20 pF into 100 nF: 0.49 mV
