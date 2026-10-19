"""Generate ecad/gripper/kicad/gripper.kicad_pcb (run with KiCad's bundled Python: it needs pcbnew).

Reads the netlist KiCad exported from the schematic (out/gripper.net), so footprints, pad nets and
symbol links are exactly what "Update PCB from Schematic" would produce. Places parts from
placement.py, routes with router.py, pours ground on both layers and writes out/route_report.json.
Deterministic: the same inputs give the same board.
"""
import json
import math
import os
import sys
import time

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..')))
from sexp import parse, find, find_all  # noqa: E402
import design  # noqa: E402
import placement as P  # noqa: E402
import router as RT  # noqa: E402

KDIR = os.path.abspath(os.path.join(HERE, '..'))
FPDIR = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), 'share', 'kicad', 'footprints')
OX, OY = P.ORIGIN
MM = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def read_netlist():
    with open(os.path.join(KDIR, 'out', 'gripper.net'), encoding='utf-8') as f:
        tree = parse(f.read())
    comps = {}
    for c in find_all(find(tree, 'components'), 'comp'):
        ref = str(find(c, 'ref')[1])
        fields = {}
        for fld in find_all(find(c, 'fields') or [], 'field'):
            fields[str(find(fld, 'name')[1])] = str(fld[2]) if len(fld) > 2 else ''
        comps[ref] = {'value': str(find(c, 'value')[1]), 'fp': str(find(c, 'footprint')[1]),
                      'uuid': str(find(c, 'tstamps')[1]), 'fields': fields}
    padnet = {}
    for net in find_all(find(tree, 'nets'), 'net'):
        name = str(find(net, 'name')[1])
        for node in find_all(net, 'node'):
            padnet[(str(find(node, 'ref')[1]), str(find(node, 'pin')[1]))] = name
    return comps, padnet


def load_fp(fp_id):
    lib, name = fp_id.split(':', 1)
    path = os.path.join(KDIR, 'gripper.pretty') if lib == 'gripper' else os.path.join(FPDIR, lib + '.pretty')
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit('footprint not found: ' + fp_id)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def pad_shape(pad):
    """Board-local conservative copper outline of a pad: circle, or its bounding rectangle."""
    pos = pad.GetPosition()
    x, y = pcbnew.ToMM(pos.x) - OX, pcbnew.ToMM(pos.y) - OY
    size = pad.GetSize()
    sx, sy = pcbnew.ToMM(size.x), pcbnew.ToMM(size.y)
    if pad.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
        return ('circle', x, y, sx / 2)
    rot = int(round(pad.GetOrientationDegrees())) % 180
    if rot == 90:
        sx, sy = sy, sx
    return ('rect', x, y, sx / 2, sy / 2)


def main():
    t0 = time.time()
    comps, padnet = read_netlist()
    dnp = {p['ref'] for p in design.PARTS if p.get('dnp')}
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    for attr, val in (('m_MinClearance', 0.2), ('m_TrackMinWidth', 0.2), ('m_ViasMinSize', 0.6),
                      ('m_ViasMinAnnularWidth', 0.13), ('m_MinThroughDrill', 0.2), ('m_HoleClearance', 0.25),
                      ('m_HoleToHoleMin', 0.5), ('m_CopperEdgeClearance', 0.3)):
        setattr(ds, attr, MM(val))
    ds.m_MinResolvedSpokes = 1
    nets = {}
    for name in sorted(set(padnet.values())):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    net_id = {name: i + 1 for i, name in enumerate(sorted(nets))}

    grid = RT.Grid(P.BOARD_W, P.BOARD_H)
    pins = {}       # net name -> [pin dict]
    fps = {}
    extra_id = len(net_id) + 1
    holes = {'plated': 0, 'unplated': 0}
    for ref in sorted(comps):
        c = comps[ref]
        if ref not in P.PLACE:
            raise SystemExit('no placement for ' + ref)
        x, y, rot, side = P.PLACE[ref]
        fp = load_fp(c['fp'])
        fp.SetReference(ref)
        fp.SetValue(c['value'])
        fp.SetPosition(V(x, y))
        fp.SetOrientationDegrees(rot)
        fp.SetPath(pcbnew.KIID_PATH('/' + c['uuid']))
        if ref in dnp:
            fp.SetDNP(True)
        for fname, fval in c['fields'].items():
            if fname in ('Footprint', 'Value', 'Reference'):
                continue
            fp.SetField(fname, fval)
        for fld in fp.GetFields():
            if fld.GetName() not in ('Reference', 'Value'):
                fld.SetVisible(False)
        board.Add(fp)
        fps[ref] = fp
        for pad in fp.Pads():
            num = pad.GetNumber()
            name = padnet.get((ref, num))
            on_f, on_b = pad.IsOnLayer(pcbnew.F_Cu), pad.IsOnLayer(pcbnew.B_Cu)
            drill = pcbnew.ToMM(pad.GetDrillSize().x)
            shape = pad_shape(pad)
            if name:
                pad.SetNet(nets[name])
                nid = net_id[name]
            else:
                nid = extra_id
                extra_id += 1
            if drill > 0:
                holes['unplated' if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else 'plated'] += 1
                grid.add_hole(shape[1], shape[2], drill / 2)
                if not (on_f or on_b):     # bare hole: keep copper off it
                    grid.add_copper((0, 1), nid, ('circle', shape[1], shape[2], drill / 2 + 0.3))
                    continue
            if not (on_f or on_b):
                continue
            layers = tuple(L for L, on in ((0, on_f), (1, on_b)) if on)
            grid.add_copper(layers, nid, shape)
            if drill == 0:
                grid.add_smd(shape)
            if name:
                pins.setdefault(name, []).append({'id': '%s.%s' % (ref, num), 'ref': ref, 'shape': shape,
                                                  'layers': layers, 'x': shape[1], 'y': shape[2], 'tht': drill > 0})
    grid.add_keepout((0, 1), *P.ANTENNA_KEEPOUT)

    def short(name):
        return name.lstrip('/')

    by_short = {short(n): n for n in nets}
    report = {'nets': {}, 'failed': [], 'narrowed': [], 'gnd_vias': 0, 'gnd_repairs': [], 'gnd_joined': []}

    def tree_add(tree, pin, shrink):
        for L in pin['layers']:
            for c in grid.cells_in(pin['shape'], shrink):
                tree[L * grid.n + c] = 1

    def connect(name, pin, tree, tree_pins, width, wide_mode):
        nid = net_id[name]
        own = [p['shape'] for p in pins[name]]
        if wide_mode:
            legal, wide, via_ok = grid.masks(nid, width, own, P.W_NECK, P.NECK_REACH)
            shrink = P.W_NECK / 2
        else:
            legal, wide, via_ok = grid.masks(nid, width)
            shrink = width / 2
        starts = [L * grid.n + c for L in pin['layers'] for c in grid.cells_in(pin['shape'], shrink)]
        anchor = min(tree_pins, key=lambda q: (q['x'] - pin['x']) ** 2 + (q['y'] - pin['y']) ** 2)
        path = grid.search(starts, tree, legal, via_ok, (anchor['x'], anchor['y']))
        if path is None and not wide_mode and width > P.W_SIGNAL:
            report['narrowed'].append('%s %s' % (short(name), pin['id']))
            return connect(name, pin, tree, tree_pins, P.W_SIGNAL, False)
        if path is None:
            report['failed'].append('%s %s' % (short(name), pin['id']))
            return False
        grid.commit(nid, path, width, wide, P.W_NECK if wide_mode else None)
        for node in path:
            tree[node] = 1
        tree_add(tree, pin, shrink)
        tree_pins.append(pin)
        return True

    def route_net(name, width, wide_ids=None, attached=()):
        todo = [p for p in pins[name] if p['id'] not in attached]
        if len(todo) < 2:
            return
        tree = bytearray(2 * grid.n)
        if wide_ids:
            first = [p for p in todo if p['id'] in wide_ids]
            second = [p for p in todo if p['id'] not in wide_ids]
        else:
            first, second = todo, []
        tree_pins = [first[0]]
        tree_add(tree, first[0], (P.W_NECK if wide_ids else width) / 2)
        for group, w, mode in ((first[1:], width, bool(wide_ids)), (second, P.W_SIGNAL, False)):
            rest = list(group)
            while rest:
                nxt = min(rest, key=lambda p: min((p['x'] - q['x']) ** 2 + (p['y'] - q['y']) ** 2 for q in tree_pins))
                rest.remove(nxt)
                connect(name, nxt, tree, tree_pins, w, mode)
        report['nets'][short(name)] = len(todo)

    # Kelvin taps first, so nothing else claims the gap beside the shunt.
    attached = {}
    for sname, pts, pin_id in P.KELVIN:
        for a, b in zip(pts, pts[1:]):
            grid.add_track(net_id[by_short[sname]], 0, a[0], a[1], b[0], b[1], P.W_SIGNAL)
        attached.setdefault(sname, []).append(pin_id)
    # U1 pin 7 (GND) straight onto the exposed pad under the package.
    u1 = fps['U1'].GetPosition()
    u1x, u1y = pcbnew.ToMM(u1.x) - OX, pcbnew.ToMM(u1.y) - OY
    gnd = by_short['GND']
    for p in pins[gnd]:
        if p['id'] == 'U1.7':
            grid.add_track(net_id[gnd], 0, p['x'], p['y'], u1x + 0.6, p['y'], 0.4)

    routed = set()
    for sname in ('VIN_P', 'SW', 'V_BUCK', 'SERVO_V', 'VIN_F', 'VIN_RAW'):
        route_net(by_short[sname], P.W_WIDE, P.WIDE_PINS[sname], attached.get(sname, ()))
        routed.add(sname)

    # Ground: surface-mount ground pads drop to the bottom plane through their own vias.
    def gnd_fanout(only_multi):
        nid = net_id[gnd]
        for p in pins[gnd]:
            if p['tht'] or p['id'] in ('U1.9', 'U1.7') or p.get('done'):
                continue
            count = P.GND_VIAS.get(p['id'], 1)
            if only_multi and count == 1:
                continue
            width = 0.5 if count > 1 else P.W_SIGNAL
            for _ in range(count):
                legal, _w, via_ok = grid.masks(nid, width)
                target = bytearray(grid.n) + bytearray(via_ok)
                starts = [c for c in grid.cells_in(p['shape'], width / 2)]
                path = grid.search(starts, target, legal, via_ok, None, via_cost=4.0, limit=400000)
                if path is None:
                    # no room for a via here: join the nearest ground pad or via on the top layer instead
                    target = bytearray(2 * grid.n)
                    for q in pins[gnd]:
                        if q is not p and (q.get('done') or q['tht']):
                            for L in q['layers']:
                                for c in grid.cells_in(q['shape'], width / 2):
                                    target[L * grid.n + c] = 1
                    path = grid.search(starts, target, legal, via_ok, None, limit=400000)
                    if path is not None:
                        report['gnd_joined'].append(p['id'])
                if path is None:
                    report['failed'].append('GND via %s' % p['id'])
                    break
                grid.commit(nid, path, width)
                report['gnd_vias'] += 1
            p['done'] = True

    gnd_fanout(True)

    def hpwl(name):
        xs = [p['x'] for p in pins[name]]
        ys = [p['y'] for p in pins[name]]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    order = [by_short[s] for s in P.FIRST_NETS + P.LOGIC_POWER_NETS]
    rest = [n for n in pins if short(n) not in routed and n not in order and n != gnd and len(pins[n]) > 1]
    order += sorted(rest, key=lambda n: (hpwl(n), n))
    for name in order:
        width = P.W_LOGIC_POWER if short(name) in P.LOGIC_POWER_NETS else P.W_SIGNAL
        t1 = time.time()
        route_net(name, width)
        if time.time() - t1 > 8:
            print('slow net %s: %.0f s' % (short(name), time.time() - t1))
    gnd_fanout(False)

    # Ground repair: bottom-layer tracks can cut the plane. Flood the copper the pour will make from a
    # seed pad; any ground pad or via left outside it gets its own track back to the flooded region.
    def gnd_repair():
        nid = net_id[gnd]
        seed = next(p for p in pins[gnd] if p['id'] == 'J1.2')
        nx, n = grid.nx, grid.n
        for _ in range(60):
            pour = ((grid.dist_other(1, nid) >= 0.45) & (~grid.hard[1]) & (grid.de >= 0.55)).tobytes()
            seen = bytearray(n)
            stack = [c for c in grid.cells_in(seed['shape'], 0.2) if pour[c]]
            for c in stack:
                seen[c] = 1
            while stack:
                c = stack.pop()
                cx = c % nx
                for nc in (c - nx, c + nx, c - 1 if cx else -1, c + 1 if cx < nx - 1 else -1):
                    if 0 <= nc < n and pour[nc] and not seen[nc]:
                        seen[nc] = 1
                        stack.append(nc)
            stranded = None
            for p in pins[gnd]:
                if p['tht'] and not any(seen[c] for c in grid.cells_in(p['shape'], 0.0)):
                    stranded = (p['id'], grid.cells_in(p['shape'], 0.2))
                    break
            if stranded is None:
                for vn, vx, vy in grid.vias:
                    c = int(round(vy / RT.G)) * nx + int(round(vx / RT.G))
                    if vn == nid and not seen[c]:
                        stranded = ('via %.2f,%.2f' % (vx, vy), [c])
                        break
            if stranded is None:
                return
            legal, _w, via_ok = grid.masks(nid, 0.3)
            target = bytearray(n) + seen
            starts = [L * n + c for L in (0, 1) for c in stranded[1]]
            path = grid.search(starts, target, legal, via_ok, None, bottom_cost=1.0, via_cost=10.0, limit=2000000)
            if path is None:
                report['failed'].append('GND repair %s' % stranded[0])
                return
            grid.commit(nid, path, 0.3)
            report['gnd_repairs'].append(stranded[0])

    t_routed = time.time() - t0
    gnd_repair()
    print('routing %.0f s, ground repair %.0f s, repairs %s' % (t_routed, time.time() - t0 - t_routed, report['gnd_repairs']))

    # Ground pads that carry the servo or input return current tie solidly into the pours.
    for p in pins[gnd]:
        if p['id'] in ('J1.2', 'J2.2', 'J3.1', 'J7.1', 'C1.2', 'C12.2'):
            for pad in fps[p['ref']].Pads():
                if pad.GetNumber() == p['id'].split('.')[1]:
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    # ---- write copper to the board
    id_net = {v: k for k, v in net_id.items()}
    for nid, L, x1, y1, x2, y2, w in grid.tracks:
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(x1, y1))
        t.SetEnd(V(x2, y2))
        t.SetWidth(MM(w))
        t.SetLayer(pcbnew.F_Cu if L == 0 else pcbnew.B_Cu)
        t.SetNet(nets[id_net[nid]])
        board.Add(t)
    for nid, x, y in grid.vias:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(V(x, y))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        try:
            v.SetWidth(pcbnew.F_Cu, MM(RT.VIA_D))
        except TypeError:
            v.SetWidth(MM(RT.VIA_D))
        v.SetDrill(MM(RT.VIA_DRILL))
        v.SetNet(nets[id_net[nid]])
        board.Add(v)

    # ---- outline, zones, rule area, silkscreen
    edge = pcbnew.PCB_SHAPE(board)
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(V(0, 0))
    edge.SetEnd(V(P.BOARD_W, P.BOARD_H))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(MM(0.1))
    board.Add(edge)

    def zone(layer, name):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(nets[gnd])
        z.SetZoneName(name)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((0, 0), (P.BOARD_W, 0), (P.BOARD_W, P.BOARD_H), (0, P.BOARD_H)):
            o.Append(MM(OX + x), MM(OY + y))
        z.SetLocalClearance(MM(0.3))
        z.SetMinThickness(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
        z.SetThermalReliefGap(MM(0.3))
        z.SetThermalReliefSpokeWidth(MM(0.5))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        board.Add(z)
        return z

    zone(pcbnew.B_Cu, 'GND bottom plane')
    zone(pcbnew.F_Cu, 'GND top fill')

    k = pcbnew.ZONE(board)
    k.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.B_Cu)
    k.SetLayerSet(ls)
    k.SetZoneName('antenna keep-out')
    k.SetDoNotAllowTracks(True)
    k.SetDoNotAllowVias(True)
    k.SetDoNotAllowZoneFills(True)
    k.SetDoNotAllowPads(False)
    k.SetDoNotAllowFootprints(False)
    x0, y0, x1, y1 = P.ANTENNA_KEEPOUT
    ko = k.Outline()
    ko.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ko.Append(MM(OX + x), MM(OY + y))
    board.Add(k)

    def silk(text, x, y, size, rot=0):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetPosition(V(x, y))
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(max(0.12, size * 0.15)))
        t.SetTextAngleDegrees(rot)
        board.Add(t)

    for text, x, y, size, rot in P.SILK:
        silk(text, x, y, size, rot)
    for ref, label in P.TP_LABEL.items():
        x, y = P.PLACE[ref][0], P.PLACE[ref][1]
        silk(label, x, y - 2.3, 0.8)

    # reference designators: small, beside the part
    for ref, fp in fps.items():
        x, y, rot, side = P.PLACE[ref]
        r = fp.Reference()
        r.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        r.SetTextThickness(MM(0.12))
        r.SetTextAngleDegrees(0)
        cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        hw = pcbnew.ToMM(cy.GetWidth()) / 2
        hh = pcbnew.ToMM(cy.GetHeight()) / 2
        cx = pcbnew.ToMM(cy.GetCenter().x) - OX
        cyy = pcbnew.ToMM(cy.GetCenter().y) - OY
        n = len(ref) * 0.35 + 0.3
        if ref.startswith('TP') or ref.startswith('H'):
            r.SetVisible(False)
            continue
        if side == 'N':
            r.SetLayer(pcbnew.F_Fab)
            r.SetPosition(V(cx, cyy))
            continue
        pos = {'T': (cx, cyy - hh - 0.6), 'T2': (cx - 2.0, cyy - hh - 0.6), 'B': (cx, cyy + hh + 0.6),
               'L': (cx - hw - n, cyy), 'R': (cx + hw + n, cyy)}[side]
        r.SetPosition(V(*pos))

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    out = os.path.join(KDIR, 'gripper.kicad_pcb')
    pcbnew.SaveBoard(out, board)

    report['tracks'] = len(grid.tracks)
    report['vias'] = len(grid.vias)
    report['track_length_mm'] = round(sum(math.hypot(t[4] - t[2], t[5] - t[3]) for t in grid.tracks), 1)
    report['bottom_track_length_mm'] = round(sum(math.hypot(t[4] - t[2], t[5] - t[3]) for t in grid.tracks if t[1] == 1), 1)
    report['wide_track_length_mm'] = round(sum(math.hypot(t[4] - t[2], t[5] - t[3]) for t in grid.tracks if t[6] == P.W_WIDE), 1)
    report['neck_track_length_mm'] = round(sum(math.hypot(t[4] - t[2], t[5] - t[3]) for t in grid.tracks if t[6] == P.W_NECK), 1)
    report['board_mm'] = [P.BOARD_W, P.BOARD_H]
    report['plated_pad_holes'] = holes['plated']
    report['unplated_holes'] = holes['unplated']
    report['widths_mm'] = {'signal': P.W_SIGNAL, 'logic_power': P.W_LOGIC_POWER, 'wide': P.W_WIDE, 'neck': P.W_NECK,
                           'via_pad': RT.VIA_D, 'via_drill': RT.VIA_DRILL, 'clearance': RT.CLR}
    report['longest_neck_mm'] = round(max([math.hypot(t[4] - t[2], t[5] - t[3]) for t in grid.tracks if t[6] == P.W_NECK] or [0]), 2)
    report['footprints'] = len(fps)
    with open(os.path.join(KDIR, 'out', 'route_report.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write('\n')
    print('footprints %d  tracks %d  vias %d  failed %d  (%.0f s)' % (
        len(fps), len(grid.tracks), len(grid.vias), len(report['failed']), time.time() - t0))
    for item in report['failed']:
        print('FAILED', item)
    return 1 if report['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
