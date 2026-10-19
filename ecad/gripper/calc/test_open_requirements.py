"""open_requirements.py: the four combinations."""
import math

import _common as cm
import open_requirements as orq


def test_four_combinations_and_cycle_time():
    r = orq.run()
    assert len(r['combos']) == 4
    cyc = {(c['cap_N'], c['close_s']): c['A']['cycle_s'] for c in r['combos']}
    assert math.isclose(cyc[(10.0, 0.5)], 35.0)                         # DESIGN-BASIS section 7: 35 s cycle
    assert math.isclose(cyc[(10.0, 0.75)], 35.25)


def test_cap_current_by_hand_and_independent_of_close_time():
    r = orq.run()
    for c in r['combos']:
        assert math.isclose(c['A']['i_cap_ideal_A'], 2 * c['cap_N'] * 0.065 / 0.85 / 0.861, rel_tol=1e-9)
        assert math.isclose(c['A']['margin_trip_ideal_A'], 3.0 - c['A']['i_cap_ideal_A'], rel_tol=1e-9)  # 3.0 A trip; 10 N: 1.2237 A
        assert math.isclose(c['A']['shunt_W'], c['A']['i_cap_A'] ** 2 * 0.1, rel_tol=1e-9)
    a = {(c['cap_N'], c['close_s']): c for c in r['combos']}
    assert math.isclose(a[(10.0, 0.5)]['A']['i_cap_A'], a[(10.0, 0.75)]['A']['i_cap_A'])
    assert a[(10.0, 0.5)]['A']['i_cap_A'] > a[(8.0, 0.5)]['A']['i_cap_A']


def test_mean_current_is_a_weighted_average():
    m, t = orq.mean_current('A', 0.5)
    assert 0.15 < m < 1.35 and math.isclose(t, 35.0)
    # all-parked limit would be 0.15 A; a longer close at the hold current raises the mean
    assert orq.mean_current('A', 0.75)[0] > m
    assert orq.mean_current('B', 0.5)[0] < m


def test_node_at_cap_and_close_time_changes_no_board_value():
    r = orq.run()
    for c in r['combos']:
        assert math.isclose(c['node_cap_mV'], cm.node_mv(c['cap_N']))
        board = [x for x in c['changes'] if x.startswith('board R15')]
        assert len(board) == 1
        assert any('none on the board' in x for x in c['changes'] if x.startswith('close time'))
    assert r['independent']['close_time_changes_board'] is False
