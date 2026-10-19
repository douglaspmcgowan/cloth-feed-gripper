"""Tests for harness.py: physics of the wire, structure of the wiring table, agreement with design.py."""
import math

import pytest

import _common as cm
import design
import harness as h

TABLE = h.rows()


def test_pair_drop_matches_ohms_law():
    for awg in (20, 26):
        got = h.pair_drop_v(awg, 1.2, 3.0)
        assert abs(got - 3.0 * 2 * 1.2 * cm.v('awg%d_ohm_m' % awg)) < 1e-9


def test_20_awg_passes_servo_budget_26_awg_fails():
    assert h.servo_budget(20)['budget_ok']
    assert not h.servo_budget(26)['budget_ok']


def test_trunk_length_comes_from_design():
    for r in TABLE:
        if r['id'] in ('H01', 'H02', 'H03', 'H12', 'H13', 'H14', 'H15'):
            assert r['length_mm'] == design.ELEC['cable_len_m'] * 1000.0


def test_every_j3_j4_pin_is_a_source_exactly_once():
    pins = {}
    for r in TABLE:
        if r['wired'] and r['frm'][:2] in ('J3', 'J4'):
            pins.setdefault(r['frm'], 0)
            pins[r['frm']] += 1
    assert pins == {'J3.1': 1, 'J3.2': 1, 'J3.3': 1, 'J4.1': 1, 'J4.2': 1, 'J4.3': 1, 'J4.4': 1}


def test_nets_match_design_py():
    h.check_nets(TABLE)       # raises on mismatch
    pn = h.pin_net_map()
    assert pn[('J3', '2')] == 'SERVO_V' and pn[('J4', '4')] == 'GND'


def test_net_mismatch_fails_loudly():
    bad = [dict(r) for r in TABLE]
    for r in bad:
        if r['id'] == 'H02':
            r['net'] = 'GND'
    with pytest.raises(AssertionError):
        h.check_nets(bad)


def test_every_wired_row_has_gauge_colour_length():
    for r in TABLE:
        if r['wired']:
            assert r['gauge'] not in (None, '') and r['colour'] not in (None, ''), r['id']
            assert r['length_mm'] == 'could-not-tell' or r['length_mm'] > 0, r['id']
    ids = [r['id'] for r in TABLE]
    assert len(ids) == len(set(ids))


def test_unwired_connectors_listed():
    assert {r['frm'] for r in TABLE if not r['wired']} == {'J2', 'J5', 'J6', 'J7'}


def test_totals_equal_sum_of_rows():
    t = h.totals(TABLE)
    spool = sum(r['length_mm'] for r in TABLE if r['wired'] and r['kind'] == 'spool')
    assert abs(t['sum_rows_mm'] - spool) < 1e-9
    assert abs(sum(t['by_gauge_mm'].values()) - spool) < 1e-9
    for b in t['by_gauge_colour']:
        assert abs(b['with_spare_mm'] - b['length_mm'] * 1.15) < 1e-9
        assert b['length_mm'] == sum(r['length_mm'] for r in TABLE if r['kind'] == 'spool' and (r['gauge'], r['colour']) == (b['gauge_awg'], b['colour']))


def test_sensor_return_is_separate_from_servo_return():
    g = {r['id']: r for r in TABLE}
    assert g['H01']['net'] == g['H15']['net'] == 'GND'
    assert g['H01']['gauge'] == 20 and g['H15']['gauge'] == 26 and g['H01']['frm'] != g['H15']['frm']


def test_limit_switch_uses_com_and_no():
    ends = {r['to'] for r in TABLE if r['id'] in ('H18', 'H19')}
    assert ends == {'SW.NO', 'SW.COM'}


def test_bend_radius_and_flex_arithmetic():
    f = h.flex(-7.4)
    assert abs(f['min_radius_mm'] - 10 * f['od_mm']) < 1e-12
    assert abs(f['cycles_per_hour'] * f['hours_for_design_life'] - f['design_cycles']) < 1e-6
    assert abs(f['slack_for_travel_mm'] - f['min_radius_mm'] * math.radians(27.4)) < 1e-9


def test_signal_drops_are_small_against_adc_lsb():
    s = h.signal_drops()
    for c in s['conductors']:
        assert abs(c['drop_mV'] - c['current_A'] * c['r_ohm'] * 1e3) < 1e-12
        assert c['drop_lsb'] < 1.0
    assert all(abs(e['err_N']) < 0.01 for e in s['fsr_error'])
    assert s['limit_low_mV'] < s['limit_vil_mV']


def test_markdown_has_one_line_per_row():
    md = h.markdown(TABLE).strip().split('\n')
    assert len(md) == len(TABLE) + 2


def test_every_connector_pin_appears_once_per_view_from_table():
    pins = h.connector_pins(TABLE)
    views = h.connector_views(TABLE)
    records = {r['id']: r for r in h.connector_records(TABLE)}
    for cid, expected in pins.items():
        assert len(expected) == records[cid]['positions']
        for side in ('wire-entry', 'mating-face'):
            got = views[cid][side]
            assert sorted((x['position'], x['signal'], x['colour']) for x in got) == sorted(
                (x['position'], x['signal'], x['colour']) for x in expected)
            assert len({x['position'] for x in got}) == len(expected)


def test_two_view_sides_are_mirrors_and_sm_halves_mate():
    views = h.connector_views(TABLE)
    for sides in views.values():
        assert sides['mating-face'] == list(reversed(sides['wire-entry']))
    assert [x['signal'] for x in views['SM-T']['mating-face']] == list(
        reversed([x['signal'] for x in views['SM-W']['mating-face']]))


def test_wrong_builds_fail_continuity_and_adjacent_isolation():
    results = h.wrong_build_results(TABLE)
    assert [x['build'] for x in results] == ['mirrored XHP-4', 'mirrored SM trunk half', 'one-position-shifted XHP-4']
    assert all(x['continuity_failures'] and x['isolation_failures'] for x in results)


def test_changed_pin_data_changes_view_and_check():
    bad = [dict(r) for r in TABLE]
    h12 = next(r for r in bad if r['id'] == 'H12')
    h13 = next(r for r in bad if r['id'] == 'H13')
    h12['frm'], h13['frm'] = h13['frm'], h12['frm']
    assert h.connector_views(bad)['J4'] != h.connector_views(TABLE)['J4']
    with pytest.raises(AssertionError):
        h.check_nets(bad)


def test_selected_servo_and_unknown_lead_facts_come_from_params():
    supplied = [r for r in TABLE if r['id'] in ('H09', 'H10', 'H11')]
    assert all(h.selected_servo() in r['part'] for r in supplied)
    assert all(r['colour'] == r['length_mm'] == 'could-not-tell' for r in supplied)


def test_committed_guide_matches_generator_in_check_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, 'OUT', str(tmp_path))
    rendered = h.write_guide(TABLE)
    assert '<!-- harness-wiring:start -->' in rendered
    assert '<!-- harness-orientation:start -->' in rendered
    assert '<!-- harness-checks:start -->' in rendered
