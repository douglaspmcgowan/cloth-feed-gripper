"""trace_width.py: hand number and scaling laws."""
import math

import _common as cm
import trace_width as tw


def test_4a_10c_is_about_2mm():
    # hand: area = (4 / (0.048 x 10^0.44))^(1/0.725) = 110 mil^2; / 1.378 mil = 80 mil = 2.03 mm
    assert math.isclose(tw.width_mm(4.0, 10.0), 2.0, rel_tol=0.03)
    assert math.isclose(tw.area_mil2(4.0, 10.0), 110.2, rel_tol=0.01)


def test_width_scaling_laws():
    # area scales as I^(1/0.725): doubling the current multiplies the width by 2^1.379
    assert math.isclose(tw.width_mm(8.0, 10.0) / tw.width_mm(4.0, 10.0), 2 ** (1 / 0.725), rel_tol=1e-9)
    assert tw.width_mm(4.0, 20.0) < tw.width_mm(4.0, 10.0)             # a larger allowed rise needs less copper
    assert math.isclose(tw.width_mm(4.0, 10.0, oz=2.0), tw.width_mm(4.0, 10.0) / 2, rel_tol=1e-9)


def test_round_trip_current_from_area():
    a = tw.area_mil2(3.77, 10.0)
    assert math.isclose(tw.current_from_area(a, 10.0), 3.77, rel_tol=1e-9)


def test_drop_is_ohmic_and_zero_at_zero_current():
    d0, _ = tw.drop_mv_per_10mm(0.0, 3.0)
    assert d0 == 0.0
    d1, r1 = tw.drop_mv_per_10mm(2.0, 3.0)
    d2, r2 = tw.drop_mv_per_10mm(4.0, 3.0)
    assert math.isclose(d2 / d1, 2.0, rel_tol=1e-12) and math.isclose(r1, r2)
    # hand: copper 1.724e-8 x (1 + 0.00393 x 15) x 0.01 m / (3e-3 m x 35e-6 m) = 1.74 mohm... x1e3 -> 1.74 mohm
    assert math.isclose(r1, 1.724e-8 * (1 + 0.00393 * 15) * 0.01 / (3e-3 * 1.378 * 25.4e-6) * 1e3, rel_tol=1e-9)


def test_via_current_and_run():
    v10 = tw.via_current(0.4, 10.0)
    assert 1.0 < v10['current_A'] < 4.0
    assert tw.via_current(0.4, 20.0)['current_A'] > v10['current_A']
    r = tw.run()
    assert r['n_vias_for_5A_10C'] >= 2
    w = [x for x in r['widths'] if x['current_A'] == 3.77 and x['rise_C'] == 10.0][0]
    assert w['width_mm'] < r['chosen_mm']                               # the routed width covers the stall current at 10 C
    assert r['max_current_A_at_10C']['wide'] > tw.stall_a()
    assert tw.stall_a() > r['max_current_A_at_10C']['neck'] > tw.HOLD_A
    assert math.isclose(tw.rise_c(tw.stall_a(), tw.width_mm(tw.stall_a(), 10.0)), 10.0, rel_tol=1e-9)
