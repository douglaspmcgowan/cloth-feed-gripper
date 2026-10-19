"""Compare the netlist KiCad exported from gripper.kicad_sch with design.nets().

Run after `kicad-cli sch export netlist`. Exits non-zero on any difference, so a schematic that
KiCad reads differently from the design table cannot pass silently. Writes out/netlist_check.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..')))
from sexp import parse, find, find_all  # noqa: E402
import design  # noqa: E402

KDIR = os.path.abspath(os.path.join(HERE, '..'))


def kicad_nets(path):
    with open(path, encoding='utf-8') as f:
        tree = parse(f.read())
    out = {}
    for net in find_all(find(tree, 'nets'), 'net'):
        name = str(find(net, 'name')[1]).lstrip('/')
        nodes = []
        for node in find_all(net, 'node'):
            ref = str(find(node, 'ref')[1])
            if ref.startswith('#'):
                continue
            nodes.append((ref, str(find(node, 'pin')[1])))
        if nodes:
            out[name] = sorted(nodes)
    return out


def main():
    got = kicad_nets(os.path.join(KDIR, 'out', 'gripper.net'))
    want = design.nets()
    # stacked pins the design leaves implicit (same net, same position) are added by KiCad
    diffs = []
    for name in sorted(set(got) | set(want)):
        g, w = set(got.get(name, [])), set(want.get(name, []))
        if name.startswith('unconnected-'):
            continue
        if g != w:
            diffs.append({'net': name, 'only_kicad': sorted(g - w), 'only_design': sorted(w - g)})
    unconnected = sorted(n for n in got if n.startswith('unconnected-'))
    result = {'nets_design': len(want), 'nets_kicad': len([n for n in got if not n.startswith('unconnected-')]),
              'pins_design': sum(len(v) for v in want.values()),
              'pins_kicad': sum(len(v) for k, v in got.items() if not k.startswith('unconnected-')),
              'unconnected_pins': len(unconnected), 'differences': diffs}
    with open(os.path.join(KDIR, 'out', 'netlist_check.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'differences'}, sort_keys=True))
    for d in diffs:
        print('DIFF', d)
    return 1 if diffs else 0


if __name__ == '__main__':
    sys.exit(main())
