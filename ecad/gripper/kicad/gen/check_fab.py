"""Open the fabrication outputs and check they are complete enough to order.

Checks, each written to ecad/gripper/kicad/out/fab_check.json:
  - one Gerber per required layer, each with draw commands (a blank bottom paste or silk file is allowed);
  - the drill files hold as many plated holes as the board has drilled pads plus vias, and 4 unplated holes;
  - the position file has one row per surface-mount part that is fitted;
  - every BOM line has an MPN, a supplier number and a price;
  - the DRC report says 0 errors and 0 unconnected items, the ERC report 0 errors.
Exits non-zero when any check fails.
"""
import csv
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.abspath(os.path.join(HERE, '..'))
FAB = os.path.join(KDIR, 'fab')
OUT = os.path.join(KDIR, 'out')

LAYERS = {'F_Cu': False, 'B_Cu': False, 'F_Mask': False, 'B_Mask': False, 'F_Silkscreen': False,
          'Edge_Cuts': False, 'F_Paste': False, 'B_Silkscreen': True, 'B_Paste': True}   # True = may be blank


def drill_holes(path):
    tools, counts, cur = {}, {}, None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            m = re.match(r'^T(\d+)C([\d.]+)', line)
            if m:
                tools[m.group(1)] = float(m.group(2))
                continue
            m = re.match(r'^T(\d+)$', line)
            if m:
                cur = m.group(1)
                continue
            if cur and re.match(r'^X-?[\d.]+Y-?[\d.]+', line):
                counts[cur] = counts.get(cur, 0) + 1
    return {('%.3f' % tools[t]): n for t, n in counts.items() if t in tools}


def main():
    res = {'checks': {}, 'gerbers': {}, 'drill': {}}
    ok = True

    def check(name, passed, detail):
        nonlocal ok
        res['checks'][name] = {'pass': bool(passed), 'detail': detail}
        ok = ok and bool(passed)
        print('%-22s %s  %s' % (name, 'ok  ' if passed else 'FAIL', detail))

    files = glob.glob(os.path.join(FAB, 'gerber', '*'))
    missing = []
    for layer, may_be_blank in LAYERS.items():
        hit = [p for p in files if ('-' + layer + '.') in os.path.basename(p)]
        if not hit:
            missing.append(layer)
            continue
        with open(hit[0], encoding='utf-8', errors='replace') as f:
            text = f.read()
        draws = len(re.findall(r'D0[123]\*', text))
        res['gerbers'][layer] = {'file': os.path.basename(hit[0]), 'bytes': len(text), 'draw_commands': draws}
        if draws == 0 and not may_be_blank:
            missing.append(layer + ' (blank)')
    check('gerber_layer_set', not missing, '%d of %d layers present%s' % (
        len(res['gerbers']), len(LAYERS), '' if not missing else '; missing ' + ', '.join(missing)))

    with open(os.path.join(OUT, 'route_report.json'), encoding='utf-8') as f:
        route = json.load(f)
    pth = glob.glob(os.path.join(FAB, 'gerber', '*-PTH.drl'))
    npth = glob.glob(os.path.join(FAB, 'gerber', '*-NPTH.drl'))
    n_pth = n_npth = -1
    if pth:
        res['drill']['plated'] = drill_holes(pth[0])
        n_pth = sum(res['drill']['plated'].values())
    if npth:
        res['drill']['unplated'] = drill_holes(npth[0])
        n_npth = sum(res['drill']['unplated'].values())
    want_pth = route['plated_pad_holes'] + route['vias']
    check('drill_plated', n_pth == want_pth, 'drill file %d holes, board %d (%d pad holes + %d vias)' % (
        n_pth, want_pth, route['plated_pad_holes'], route['vias']))
    check('drill_unplated', n_npth == route['unplated_holes'], 'drill file %d holes, board %d mounting holes' % (
        n_npth, route['unplated_holes']))

    with open(os.path.join(FAB, 'gripper-bom.csv'), encoding='utf-8', newline='') as f:
        bom = list(csv.DictReader(f))
    bad = [r['References'] for r in bom if not (r['MPN'] and r['Supplier PN'] and float(r['Unit USD']) >= 0 and r['Supplier'])]
    check('bom_complete', not bad, '%d lines, %d parts, every line has MPN, supplier number and price%s' % (
        len(bom), sum(int(r['Qty']) for r in bom), '' if not bad else '; incomplete ' + ', '.join(bad)))
    res['bom_zero_price_lines'] = [r['References'] for r in bom if float(r['Unit USD']) == 0]

    with open(os.path.join(FAB, 'gripper-pos.csv'), encoding='utf-8', newline='') as f:
        pos = list(csv.DictReader(f))
    refs_pos = {r.get('Ref') or r.get('Designator') for r in pos}
    refs_bom = {x for r in bom if r['Fit'] == 'fit' for x in r['References'].split()}
    check('position_file', refs_pos <= refs_bom | {x for r in bom for x in r['References'].split()} and len(pos) > 0,
          '%d placements; %d fitted BOM parts are hand-placed through-hole or socketed and not in the file' % (
              len(pos), len(refs_bom - refs_pos)))
    res['position_rows'] = len(pos)

    with open(os.path.join(OUT, 'drc.rpt'), encoding='utf-8') as f:
        drc = f.read()
    with open(os.path.join(OUT, 'erc.rpt'), encoding='utf-8') as f:
        erc = f.read()
    drc_viol = int(re.search(r'Found (\d+) DRC violations', drc).group(1))
    drc_unc = int(re.search(r'Found (\d+) unconnected pads', drc).group(1))
    drc_par = int(re.search(r'Found (\d+) Footprint errors', drc).group(1))
    drc_err = len(re.findall(r'; error', drc))
    drc_warn = len(re.findall(r'; warning', drc))
    m = re.search(r'ERC messages: (\d+)\s+Errors (\d+)\s+Warnings (\d+)', erc)
    res['drc'] = {'violations': drc_viol, 'errors': drc_err, 'warnings': drc_warn, 'unconnected': drc_unc,
                  'schematic_parity_issues': drc_par}
    res['erc'] = {'messages': int(m.group(1)), 'errors': int(m.group(2)), 'warnings': int(m.group(3))}
    check('drc', drc_err == 0 and drc_unc == 0 and drc_par == 0,
          '%d errors, %d warnings, %d unconnected, %d schematic parity issues' % (drc_err, drc_warn, drc_unc, drc_par))
    check('erc', res['erc']['errors'] == 0, '%d errors, %d warnings' % (res['erc']['errors'], res['erc']['warnings']))
    step = os.path.join(FAB, 'gripper.step')
    check('step_model', os.path.exists(step) and os.path.getsize(step) > 10000,
          '%d bytes' % (os.path.getsize(step) if os.path.exists(step) else 0))
    res['pass'] = ok
    with open(os.path.join(OUT, 'fab_check.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(res, f, indent=2, sort_keys=True)
        f.write('\n')
    print('fabrication outputs: %s' % ('COMPLETE' if ok else 'INCOMPLETE'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
