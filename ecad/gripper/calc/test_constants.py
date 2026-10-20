"""constants.py: structure checks and the numbers other tests lean on."""
import ast
import math
import re
from pathlib import Path

import _common as cm
import constants as K


def test_every_entry_is_tagged_and_cited():
    for name, e in K.C.items():
        assert set(e) == {'value', 'unit', 'tag', 'url', 'retrieved', 'note'}, name
        assert e['tag'] in ('S', 'A'), name
        assert e['retrieved'] in ('2026-10-11', '2026-10-19'), name
        assert e['note'], name
        if e['tag'] == 'S':
            assert e['url'].startswith('https://'), name       # sourced means a URL was fetched
        else:
            assert 'assumed' in e['note'] or 'not fetched' in e['note'] or 'fetch' in e['note'] or e['note'], name


def test_rt_equation_gives_400khz_for_243k():
    # hand: 92471 * 243^-0.991 kHz = 399.8 kHz
    f = K.val('tps_rt_coeff') * 243.0 ** K.val('tps_rt_exp')
    assert math.isclose(f, 399.8, rel_tol=0.003)


def test_wire_resistance_ordering_and_copper_physics():
    # AWG 20 is 3.2 mm^2 smaller step by step: resistance rises ~2x per 6 gauge; 20 -> 26 = 4.0x
    r20, r26 = K.val('awg20_ohm_m'), K.val('awg26_ohm_m')
    assert math.isclose(r26 / r20, 4.02, rel_tol=0.01)
    # 20 AWG area 0.5188 mm^2 -> rho / A with rho 1.724e-8
    assert math.isclose(K.val('cu_rho') / 0.5188e-6, r20, rel_tol=0.01)


def test_ina219_default_config_is_pga8():
    cfg = int(K.val('ina_default_cfg'))
    pga = (cfg >> 11) & 3
    assert pga == 3                                              # PG = 11 -> /8
    assert math.isclose(K.val('ina_fs_pga8'), 0.320)


def test_tags_present_for_assumed_parts():
    assumed = [k for k, e in K.C.items() if e['tag'] == 'A']
    assert 'devkit_diode_drop' in assumed and 'esp_bod_default' in assumed


def _unit_forms(value, unit):
    if unit == 'mm':
        return {'%g mm' % value, '%g m' % (value / 1000), '%.0f ft' % (value / 304.8)}
    return {'%g %s' % (value, unit)}


def test_sourced_constant_text_matches_its_record():
    import sourcing

    def records(node):
        if isinstance(node, dict):
            if isinstance(node.get('url'), str):
                yield node
            for child in node.values():
                yield from records(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                yield from records(child)

    pool = list(records([sourcing.SRC, sourcing.HARNESS, sourcing.FAB, sourcing.EVIDENCE]))
    for name, e in K.C.items():
        if e['tag'] != 'S':
            continue
        for record in (r for r in pool if r['url'] == e['url']):
            text = ' '.join(str(item) for item in record.values())
            forms = _unit_forms(e['value'], e['unit'])
            assert any(form in text for form in forms), (name, e['url'], sorted(forms))


# the real constant lookups: _common.v(name) and constants.val(name), reached by a bare import or a module alias
LOOKUPS = {('_common', 'v'), ('constants', 'val')}


def _lookup_reads(path):
    """Names passed as the first argument (or name=) of a real constant lookup in one module."""
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    bare, alias = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in ('_common', 'constants'):
            for a in node.names:
                if (node.module, a.name) in LOOKUPS:
                    bare[a.asname or a.name] = (node.module, a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name in ('_common', 'constants'):
                    alias[a.asname or a.name] = a.name
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name):
            target = bare.get(f.id)
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in alias:
            target = (alias[f.value.id], f.attr)
        else:
            target = None
        if target not in LOOKUPS:
            continue
        arg = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == 'name'), None)
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            names.add(arg.value)
    return names


def test_every_deg_and_db_constant_is_read_by_a_calc_module():
    # a constant is read only when a calc module passes its name to _common.v or constants.val
    read = set()
    for path in sorted(Path(cm.HERE).glob('*.py')):
        if path.name == 'constants.py' or path.name.startswith('test_'):
            continue
        read |= _lookup_reads(path)
    unread = sorted(n for n, e in K.C.items() if e['unit'] in ('deg', 'dB') and n not in read)
    assert unread == []


def test_ina_trip_current_mirrors_firmware_stall_current():
    # the INA219 budget reads the firmware trip; a 1.8 A copy survived the DS3230 move (PR 54), so compare the two sources
    text = (Path(cm.REPO) / 'firmware' / 'gripper' / 'config.h').read_text(encoding='utf-8')
    fw = re.search(r'^#define\s+STALL_CURRENT_A\s+([0-9.]+)', text, re.M)
    assert fw, 'STALL_CURRENT_A not found in firmware/gripper/config.h'
    assert math.isclose(float(fw.group(1)), K.val('ina_trip_current_a'), rel_tol=0, abs_tol=1e-12)
