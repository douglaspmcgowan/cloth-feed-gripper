import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import design  # noqa: E402
import sourcing  # noqa: E402
from calc import constants  # noqa: E402

FIELDS = ['mpn', 'mfr', 'supplier', 'spn', 'price_usd', 'price_qty', 'url', 'datasheet', 'retrieved', 'tag', 'notes']
FAB_KEYS = ['min_track_mm', 'min_space_mm', 'min_drill_mm', 'min_via_pad_mm', 'min_annular_ring_mm',
            'edge_copper_clearance_mm', 'min_silk_width_mm', 'thickness_std_mm', 'copper_oz',
            'max_size_cheapest_class_mm', 'price_5_boards_usd']
EVIDENCE_KEYS = ['servo_signal_level', 'servo_lead', 'devkitc_power', 'devkitc_dimensions', 'fsr_tail', 'flex_wire',
                 'jlc_assembly']


def test_every_design_src_key_is_sourced():
    keys = {p['src'] for p in design.PARTS if p.get('src')}
    assert keys - set(sourcing.SRC) == set()
    assert 'socket19' in sourcing.SRC


def test_entries_complete():
    for key, e in list(sourcing.SRC.items()) + [(h['item'], h) for h in sourcing.HARNESS]:
        for f in FIELDS:
            assert f in e, (key, f)
        for f in ('url', 'retrieved', 'mpn'):
            assert e[f], (key, f)
        assert e['price_usd'] > 0, key
        assert e['price_qty'] >= 1, key
        assert e['tag'] in ('S', 'A'), key
        if e['tag'] == 'A':
            assert e['notes'], key


def test_harness_items():
    assert len(sourcing.HARNESS) >= 12
    for h in sourcing.HARNESS:
        assert h['item'] and h['qty'] >= 1
        assert h['url'] or h['tag'] == 'A'


def test_fab():
    for k in FAB_KEYS:
        assert k in sourcing.FAB, k
        assert sourcing.FAB[k]['url'] and sourcing.FAB[k]['retrieved'], k


def test_evidence():
    for k in EVIDENCE_KEYS:
        e = sourcing.EVIDENCE[k]
        assert e['finding'] and e['retrieved']
        assert e['url'] or e['tag'] == 'A'
        assert e['tag'] in ('S', 'A')


def test_calculation_constant_sources():
    for key, constant in constants.C.items():
        if constant['tag'] != 'S':
            continue
        assert key in sourcing.CALC_CONSTANTS, key
        record = sourcing.CALC_CONSTANTS[key]
        assert record['tag'] == 'S', key
        assert all(record[field] for field in (
            'mpn', 'manufacturer', 'datasheet_url', 'datasheet_revision',
            'page', 'table', 'quote')), key
    for key, record in sourcing.CALC_CONSTANTS.items():
        assert key in constants.C, key
        assert record['tag'] == constants.C[key]['tag'], key
        if record['tag'] == 'A':
            assert record['reason'], key
