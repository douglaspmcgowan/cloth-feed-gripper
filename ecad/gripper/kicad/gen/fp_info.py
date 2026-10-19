"""Print pad and courtyard geometry of every footprint design.py uses (run with KiCad's Python).

A layout aid: the placement table in placement.py was written from this listing.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..')))
import design  # noqa: E402

KDIR = os.path.abspath(os.path.join(HERE, '..'))
FPDIR = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), 'share', 'kicad', 'footprints')


def load(fp_id):
    lib, name = fp_id.split(':', 1)
    path = os.path.join(KDIR, 'gripper.pretty') if lib == 'gripper' else os.path.join(FPDIR, lib + '.pretty')
    return pcbnew.FootprintLoad(path, name)


def mm(v):
    return round(pcbnew.ToMM(v), 3)


def main():
    seen = {}
    for p in design.PARTS:
        if p.get('fp'):
            seen.setdefault(p['fp'], []).append(p['ref'])
    for fp_id, refs in seen.items():
        fp = load(fp_id)
        cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        print('%s  refs=%s' % (fp_id, ','.join(refs)))
        print('  courtyard x %s..%s y %s..%s' % (mm(cy.GetLeft()), mm(cy.GetRight()), mm(cy.GetTop()), mm(cy.GetBottom())))
        pads = list(fp.Pads())
        if len(pads) > 12:
            pads = pads[:3] + pads[-2:]
        for pad in pads:
            pos, size = pad.GetPosition(), pad.GetSize()
            print('  pad %-3s at %7.3f %7.3f size %5.2f x %5.2f drill %4.2f %s' % (
                pad.GetNumber(), mm(pos.x), mm(pos.y), mm(size.x), mm(size.y), mm(pad.GetDrillSize().x),
                'tht' if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else 'smd'))


if __name__ == '__main__':
    main()
