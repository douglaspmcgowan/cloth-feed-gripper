"""Measure the routed board (run with KiCad's bundled Python).

Reads gripper.kicad_pcb as saved and writes out/board_stats.json: per net, copper length by layer and
width and the via count; board size; copper-layer count; hole counts; ground-plane coverage of the
bottom layer. These are the as-built numbers electrical.md quotes for the board.
"""
import json
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.abspath(os.path.join(HERE, '..'))
POWER = ['/VIN_RAW', '/VIN_F', '/VIN_P', '/SW', '/V_BUCK', '/SERVO_V']


def main():
    board = pcbnew.LoadBoard(os.path.join(KDIR, 'gripper.kicad_pcb'))
    nets = {}
    for t in board.GetTracks():
        name = t.GetNetname()
        n = nets.setdefault(name, {'top_mm': 0.0, 'bottom_mm': 0.0, 'vias': 0, 'by_width_mm': {}})
        if t.GetClass() == 'PCB_VIA':
            n['vias'] += 1
            continue
        length = pcbnew.ToMM(t.GetLength())
        n['top_mm' if t.GetLayer() == pcbnew.F_Cu else 'bottom_mm'] += length
        w = '%.2f' % pcbnew.ToMM(t.GetWidth())
        n['by_width_mm'][w] = n['by_width_mm'].get(w, 0.0) + length
    for n in nets.values():
        n['top_mm'] = round(n['top_mm'], 2)
        n['bottom_mm'] = round(n['bottom_mm'], 2)
        n['by_width_mm'] = {k: round(val, 2) for k, val in sorted(n['by_width_mm'].items())}
    w = h = 0.0
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:      # outline centre-line, not the drawn line's outer edge
            s, e = d.GetStart(), d.GetEnd()
            w = max(w, pcbnew.ToMM(abs(e.x - s.x)))
            h = max(h, pcbnew.ToMM(abs(e.y - s.y)))
    area = {}
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        layer = 'bottom' if z.GetLayer() == pcbnew.B_Cu else 'top'
        area[layer] = round(z.GetFilledArea() / 1e12, 1)     # nm2 -> mm2
    power = {k.lstrip('/'): nets.get(k, {}) for k in POWER}
    stats = {
        'board_w_mm': round(w, 2), 'board_h_mm': round(h, 2), 'board_area_mm2': round(w * h, 1),
        'copper_layers': board.GetCopperLayerCount(),
        'footprints': len(board.GetFootprints()),
        'track_segments': sum(1 for t in board.GetTracks() if t.GetClass() != 'PCB_VIA'),
        'vias': sum(n['vias'] for n in nets.values()),
        'bottom_track_mm': round(sum(n['bottom_mm'] for n in nets.values()), 1),
        'top_track_mm': round(sum(n['top_mm'] for n in nets.values()), 1),
        'ground_fill_mm2': area,
        'bottom_ground_coverage_pct': round(100.0 * area.get('bottom', 0.0) / (w * h), 1),
        'power_nets': power,
        'power_net_vias': sum(n.get('vias', 0) for n in power.values()),
        'power_neck_mm': round(sum(n.get('by_width_mm', {}).get('0.60', 0.0) for n in power.values()), 2),
        'power_wide_mm': round(sum(n.get('by_width_mm', {}).get('2.00', 0.0) for n in power.values()), 2),
        'ground_vias': nets.get('/GND', {}).get('vias', 0),
        'nets': {k.lstrip('/'): v for k, v in sorted(nets.items())},
    }
    with open(os.path.join(KDIR, 'out', 'board_stats.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(stats, f, indent=2, sort_keys=True)
        f.write('\n')
    print('board %.1f x %.1f mm, %d copper layers, %d footprints, %d track segments, %d vias' % (
        w, h, stats['copper_layers'], stats['footprints'], stats['track_segments'], stats['vias']))
    print('bottom ground coverage %.1f %%; bottom tracks %.1f mm; top tracks %.1f mm' % (
        stats['bottom_ground_coverage_pct'], stats['bottom_track_mm'], stats['top_track_mm']))
    print('power nets: %.1f mm at 2.0 mm, %.1f mm of 0.6 mm neck, %d vias' % (
        stats['power_wide_mm'], stats['power_neck_mm'], stats['power_net_vias']))
    for k, n in power.items():
        print('  %-8s %s vias %d' % (k, n.get('by_width_mm'), n.get('vias', 0)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
