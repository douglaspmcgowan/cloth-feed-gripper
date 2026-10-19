"""Generate ecad/gripper/kicad/gripper.kicad_sch from design.py.

Every connected pin gets a 2.54 mm wire stub and a local net label at its end; every pin left out of
a part's pin map gets a no-connect flag. Symbols are embedded from the KiCad 10 standard libraries
and the project library gripper.kicad_sym. UUIDs are uuid5 of the reference, so output is stable.
"""
import math
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..')))
from sexp import Q, dump, load_symbol, symbol_pins, find_all  # noqa: E402
import design  # noqa: E402
import sourcing  # noqa: E402

KDIR = os.path.abspath(os.path.join(HERE, '..'))
SYMDIR = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'KiCad', '10.0', 'share', 'kicad', 'symbols')
NS = uuid.UUID('6f1c1d2e-5a2b-4c1e-9d6a-2f6b0e7a9c11')
ROOT = str(uuid.uuid5(NS, 'root'))
STUB = 2.54


def uid(*parts):
    return str(uuid.uuid5(NS, '/'.join(str(p) for p in parts)))


def lib_path(lib):
    if lib == 'gripper':
        return os.path.join(KDIR, 'gripper.kicad_sym')
    return os.path.join(SYMDIR, lib + '.kicad_sym')


_cache = {}


def libsym(lib_id):
    if lib_id not in _cache:
        lib, name = lib_id.split(':', 1)
        _cache[lib_id] = load_symbol(lib_path(lib), name)
    return _cache[lib_id]


def r2(v):
    return round(v * 100) / 100.0


def pin_world(part, pin):
    """Pin tip and outward unit vector in schematic coordinates (y down)."""
    num, name, px, py, ang, ln, et = pin
    X, Y = part['at']
    rot = part.get('rot', 0)
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    # symbol frame (y up) rotated CCW by rot, then flipped to y down
    sx, sy = px * c - py * s, px * s + py * c
    tip = (r2(X + sx), r2(Y - sy))
    a = math.radians(ang + rot + 180.0)
    out = (round(math.cos(a)), -round(math.sin(a)))
    return tip, out


def font(size=1.27, hide=False, justify=None):
    e = ['effects', ['font', ['size', size, size]]]
    if justify:
        e.append(['justify'] + justify.split())
    if hide:
        e.append(['hide', 'yes'])
    return e


def placed_symbol(part, units_pins):
    ref = part['ref']
    X, Y = part['at']
    rot = part.get('rot', 0)
    src = sourcing.SRC.get(part.get('src') or '', {})
    props = [('Reference', ref, (X + part.get('ref_dx', 2.54), Y - part.get('ref_dy', 1.27)), False),
             ('Value', part['value'], (X + part.get('ref_dx', 2.54), Y + part.get('ref_dy', 1.27)), False),
             ('Footprint', part['fp'], (X, Y + 5.08), True),
             ('Datasheet', src.get('datasheet', ''), (X, Y + 7.62), True),
             ('Description', part.get('desc', ''), (X, Y + 10.16), True)]
    if src:
        fields = {'MPN': src['mpn'], 'Manufacturer': src['mfr'], 'Supplier': src['supplier'],
                  'Supplier PN': src['spn'], 'Unit price USD': '%.4f' % src['price_usd']}
        if src['supplier'] == 'LCSC':
            fields['LCSC Part #'] = src['spn']
        for k, v in fields.items():
            props.append((k, str(v), (X, Y + 12.7), True))
    out = ['symbol', ['lib_id', Q(part['sym'])], ['at', X, Y, rot], ['unit', 1],
           ['exclude_from_sim', 'no'], ['in_bom', 'no' if part.get('virtual') or part.get('bom') is False else 'yes'],
           ['on_board', 'no' if part.get('virtual') else 'yes'],
           ['dnp', 'yes' if part.get('dnp') else 'no'], ['uuid', Q(uid(ref))]]
    for name, val, (x, y), hide in props:
        justify = 'left' if name in ('Reference', 'Value') else None
        out.append(['property', Q(name), Q(val), ['at', r2(x), r2(y), 0], font(hide=hide, justify=justify)])
    for num in units_pins:
        out.append(['pin', Q(num), ['uuid', Q(uid(ref, 'pin', num))]])
    out.append(['instances', ['project', Q('gripper'),
                              ['path', Q('/' + ROOT), ['reference', Q(ref)], ['unit', 1]]]])
    return out


def build():
    used = {}
    items = []
    netpins = {}
    for part in design.PARTS:
        sym = libsym(part['sym'])
        used[part['sym']] = sym
        pins = symbol_pins(sym)
        pinmap = part.get('pins', {})
        unknown = set(pinmap) - {p[0] for p in pins}
        if unknown:
            raise SystemExit('%s: pins %s not in symbol %s' % (part['ref'], sorted(unknown), part['sym']))
        names = {p[0]: p[1] for p in pins}
        for num, want in design.EXPECT.get(part['ref'], {}).items():
            if want.lower() not in names[num].lower():
                raise SystemExit('%s pin %s: symbol %s names it "%s", design expects "%s"'
                                 % (part['ref'], num, part['sym'], names[num], want))
        # group stacked pins by tip position
        groups = {}
        for p in pins:
            tip, out = pin_world(part, p)
            groups.setdefault(tip, []).append((p, out))
        for tip, members in groups.items():
            nets = {pinmap[m[0][0]] for m in members if m[0][0] in pinmap}
            if len(nets) > 1:
                raise SystemExit('%s: stacked pins at %s on nets %s' % (part['ref'], tip, nets))
            out = members[0][1]
            if not nets:
                items.append(['no_connect', ['at', tip[0], tip[1]], ['uuid', Q(uid(part['ref'], 'nc', tip))]])
                continue
            net = nets.pop()
            for m in members:
                netpins.setdefault(net, []).append('%s.%s' % (part['ref'], m[0][0]))
            end = (r2(tip[0] + out[0] * STUB), r2(tip[1] + out[1] * STUB))
            items.append(['wire', ['pts', ['xy', tip[0], tip[1]], ['xy', end[0], end[1]]],
                          ['stroke', ['width', 0], ['type', 'default']], ['uuid', Q(uid(part['ref'], 'w', tip))]])
            ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[out]
            just = 'left bottom' if ang in (0, 90) else 'right bottom'
            items.append(['label', Q(net), ['at', end[0], end[1], ang], font(justify=just),
                          ['uuid', Q(uid(part['ref'], 'l', tip))]])
        items.append(placed_symbol(part, [p[0] for p in pins]))
    for t in design.TEXTS:
        items.append(['text', Q(t['text']), ['exclude_from_sim', 'no'], ['at', t['at'][0], t['at'][1], 0],
                      font(size=t.get('size', 1.27), justify='left bottom'), ['uuid', Q(uid('text', t['text'][:40]))]])
    lib_symbols = ['lib_symbols']
    for lib_id in sorted(used):
        s = [list(x) if isinstance(x, list) else x for x in used[lib_id]]
        s[1] = Q(lib_id)
        lib_symbols.append(s)
    sch = ['kicad_sch', ['version', 20260101], ['generator', Q('eeschema')], ['generator_version', Q('10.0')],
           ['uuid', Q(ROOT)], ['paper', Q(design.SHEET['paper'])],
           ['title_block', ['title', Q(design.SHEET['title'])], ['date', Q(design.SHEET['date'])],
            ['rev', Q(design.SHEET['rev'])], ['company', Q(design.SHEET['company'])],
            ['comment', 1, Q(design.SHEET['comment'])]],
           lib_symbols] + items + [['sheet_instances', ['path', Q('/'), ['page', Q('1')]]],
                                   ['embedded_fonts', 'no']]
    with open(os.path.join(KDIR, 'gripper.kicad_sch'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(dump(sch) + '\n')
    single = sorted(n for n, p in netpins.items() if len(p) < 2)
    print('parts', len(design.PARTS), 'nets', len(netpins), 'single-pin nets', single)
    return netpins


if __name__ == '__main__':
    build()
