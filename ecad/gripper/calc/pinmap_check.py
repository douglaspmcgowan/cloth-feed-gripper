"""Pin map check: firmware config.h against design.GPIO_NETS, the DevKitC socket pins, ESP32 pin rules, and the KiCad netlist.

Run from the repository root:  python ecad/gripper/calc/pinmap_check.py

Jargon.
  GPIO: ESP32 general-purpose pin number. Socket pin: the 1-to-38 position on the DevKitC header (J2 left 1-19, J3 right 20-38).
  ADC1 / ADC2: the two ESP32 analog converters; ADC2 cannot be used while Wi-Fi runs, so analog inputs go on ADC1 (GPIO 32-39).
  Input-only: GPIO 34, 35, 36, 39 have no output driver and no internal pull-up or pull-down.
  Strapping pins: GPIO 0, 2, 5, 12, 15 are read at reset to choose boot mode and flash voltage; a circuit must not pull them
    the wrong way while the chip resets (GPIO 0 low = download mode; GPIO 12 high = 1.8 V flash, which kills the WROOM-32 boot;
    GPIO 2 must be low or floating to enter download mode; GPIO 5 and 15 set boot log and timing).
  Netlist: ecad/gripper/kicad/out/gripper.net, a KiCad s-expression export that the tactician generates later.
Tags: [S] pin rules from the ESP32 datasheet pin-description tables and the ESP-IDF ADC documentation, [D] derived here.
"""
import os
import re

import _common as cm
import design

CONFIG_H = os.path.join(cm.REPO, 'firmware', 'gripper', 'config.h')
NETLIST = os.path.join(cm.GRIPPER, 'kicad', 'out', 'gripper.net')
ADC1 = {32, 33, 34, 35, 36, 37, 38, 39}
INPUT_ONLY = {34, 35, 36, 37, 38, 39}
STRAPPING = {0: 'low = download mode (boot)', 2: 'low or floating for download mode', 5: 'boot log / SDIO timing', 12: 'high = 1.8 V flash (bad)', 15: 'boot log silencing'}
FLASH = set(range(6, 12))
ANALOG_MACROS = {'PIN_FSR_ADC', 'PIN_SERVO_FB_ADC'}
ANALOG_NETS = {'FSR_ADC', 'FB_ADC'}


def parse_config(path=CONFIG_H):
    """{macro: gpio} for every `#define PIN_... <integer>` line in config.h."""
    out = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'\s*#define\s+(PIN_[A-Z0-9_]+)\s+(\d+)\b', line)
            if m:
                out[m.group(1)] = int(m.group(2))
    return out


def parse_sexp(text):
    """Tiny s-expression reader: returns nested lists of strings."""
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+', text)
    pos = 0

    def rd():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == '(':
            lst = []
            while toks[pos] != ')':
                lst.append(rd())
            pos += 1
            return lst
        return t[1:-1] if t.startswith('"') else t
    return rd()


def netlist_pins(path=NETLIST):
    """{(ref, pin): net} from a KiCad netlist file."""
    with open(path, encoding='utf-8') as f:
        tree = parse_sexp(f.read())
    out = {}

    def walk(n):
        if isinstance(n, list):
            if n and n[0] == 'net':
                name = None
                nodes = []
                for c in n[1:]:
                    if isinstance(c, list) and c and c[0] == 'name':
                        name = c[1]
                    if isinstance(c, list) and c and c[0] == 'node':
                        d = {x[0]: x[1] for x in c[1:] if isinstance(x, list) and len(x) > 1}
                        nodes.append((d.get('ref'), d.get('pin')))
                for nd in nodes:
                    out[nd] = name
            else:
                for c in n:
                    walk(c)
    walk(tree)
    return out


def net_matches(have, want):
    """KiCad prefixes sheet-level net names with '/'. Accept either form."""
    return have is not None and have.lstrip('/') == want


def run():
    r = {'config': parse_config()}
    gn = design.GPIO_NETS
    rows = []
    # line by line: every PIN_ define must be in GPIO_NETS with the same GPIO, and vice versa
    by_macro = {m: g for g, (_, m) in gn.items()}
    for macro, gpio in r['config'].items():
        want = by_macro.get(macro)
        rows.append({'macro': macro, 'config_gpio': gpio, 'design_gpio': want, 'match': want == gpio,
                     'net': gn.get(gpio, (None,))[0], 'socket_pin': design.devkit_pin_number(gpio) if ('IO%d' % gpio) in (design.DEVKITC['J2'] + design.DEVKITC['J3']) else None})
    for gpio, (net, macro) in gn.items():
        if macro not in r['config']:
            rows.append({'macro': macro, 'config_gpio': None, 'design_gpio': gpio, 'match': False, 'net': net, 'socket_pin': design.devkit_pin_number(gpio)})
    r['lines'] = rows
    # socket pin is what design.part U5 carries
    u5 = [p for p in design.PARTS if p['ref'] == 'U5'][0]
    sock = []
    for gpio, (net, macro) in gn.items():
        pn = design.devkit_pin_number(gpio)
        sock.append({'gpio': gpio, 'net': net, 'socket_pin': pn, 'header': 'J2' if pn <= 19 else 'J3', 'design_net_on_pin': u5['pins'].get(str(pn)), 'ok': u5['pins'].get(str(pn)) == net})
    r['socket'] = sock
    # ESP32 rules
    rules = []
    for gpio, (net, macro) in gn.items():
        notes = []
        ok = True
        if net in ANALOG_NETS or macro in ANALOG_MACROS:
            if gpio not in ADC1:
                ok = False
                notes.append('analog input NOT on ADC1')
            else:
                notes.append('ADC1')
        if gpio in INPUT_ONLY:
            notes.append('input-only, no pull-up (external network provides the bias)')
            if net not in ANALOG_NETS and macro not in ('PIN_FSR_ADC', 'PIN_SERVO_FB_ADC'):
                ok = False
                notes.append('used as digital with no external pull')
        if gpio in FLASH:
            ok = False
            notes.append('flash pin')
        if gpio in STRAPPING:
            pulls = [(p['ref'], p['pins']) for p in design.PARTS if p['sym'] in ('Device:R',) and net in p['pins'].values()]
            to3v3 = any('+3V3' in pins.values() for _, pins in pulls)
            togd = any('GND' in pins.values() for _, pins in pulls)
            notes.append('strapping (%s); resistors on net: %s' % (STRAPPING[gpio], ', '.join(ref for ref, _ in pulls) or 'none'))
            if gpio == 12 and to3v3:
                ok = False
                notes.append('pulled HIGH at reset: selects 1.8 V flash')
            if gpio == 0 and togd:
                ok = False
                notes.append('pulled LOW at reset: download mode')
            if gpio == 2:
                # LED through 330 ohm to GND: a low or floating level at reset; allowed
                notes.append('LED + 330 ohm to GND only: low at reset, allowed (download mode needs low or floating)')
                if to3v3:
                    ok = False
                    notes.append('pull-up present')
        rules.append({'gpio': gpio, 'net': net, 'ok': ok, 'notes': '; '.join(notes) if notes else 'plain digital I/O'})
    r['rules'] = rules
    # strapping pins that are not used must not be connected by the circuit either
    used = set(gn)
    r['strapping_unused'] = sorted(STRAPPING.keys() - used)
    # netlist
    if os.path.exists(NETLIST):
        pins = netlist_pins()
        nl = []
        for s in sock:
            have = pins.get(('U5', str(s['socket_pin'])))
            nl.append({'gpio': s['gpio'], 'socket_pin': s['socket_pin'], 'expected': s['net'], 'netlist': have, 'ok': net_matches(have, s['net'])})
        r['netlist'] = {'present': True, 'path': os.path.relpath(NETLIST, cm.REPO).replace('\\', '/'), 'rows': nl, 'ok': all(x['ok'] for x in nl)}
    else:
        r['netlist'] = {'present': False, 'path': os.path.relpath(NETLIST, cm.REPO).replace('\\', '/'), 'rows': [], 'ok': None}
    r['ok'] = all(x['match'] for x in rows) and all(x['ok'] for x in sock) and all(x['ok'] for x in rules) and (r['netlist']['ok'] in (True, None))
    return r


def report(r):
    print('Pin map check: firmware/gripper/config.h against ecad/gripper/design.py GPIO_NETS')
    print(cm.table([[x['macro'], x['config_gpio'], x['design_gpio'], x['net'], x['socket_pin'], 'ok' if x['match'] else 'MISMATCH'] for x in r['lines']],
                   ['config.h macro', 'config.h GPIO', 'design GPIO', 'net', 'DevKitC socket pin', 'line check']))
    print('\nSocket pin on the DevKitC header and the net design.PARTS places on it')
    print(cm.table([[x['gpio'], x['net'], x['header'], x['socket_pin'], x['design_net_on_pin'], 'ok' if x['ok'] else 'MISMATCH'] for x in r['socket']],
                   ['GPIO', 'expected net', 'header', 'socket pin', 'net on U5 pin', 'check']))
    print('\nESP32 pin rules [S]: analog on ADC1 (32-39), 34-39 input-only without pull-ups, strapping pins 0, 2, 5, 12, 15, flash pins 6-11')
    print(cm.table([[x['gpio'], x['net'], 'ok' if x['ok'] else 'FAIL', x['notes']] for x in r['rules']], ['GPIO', 'net', 'result', 'notes']))
    print('Strapping pins 0, 5, 12, 15 are unused by the circuit: %s' % (', '.join(str(s) for s in r['strapping_unused'] if s != 2) or 'none'))
    nl = r['netlist']
    if nl['present']:
        print('\nNetlist %s: %s' % (nl['path'], 'every GPIO socket pin is on the expected net' if nl['ok'] else 'MISMATCHES'))
        print(cm.table([[x['gpio'], x['socket_pin'], x['expected'], x['netlist'], 'ok' if x['ok'] else 'MISMATCH'] for x in nl['rows']], ['GPIO', 'socket pin', 'expected net', 'netlist net', 'check']))
    else:
        print('\nNetlist %s is absent: the netlist part of the check was skipped (the tactician generates it later); rerun this script then.' % nl['path'])
    print('\nOverall: %s' % ('PASS' if r['ok'] else 'FAIL'))


if __name__ == '__main__':
    report(run())
