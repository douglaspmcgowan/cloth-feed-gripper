"""Bill of materials for the gripper controller board and its harness.

Reads design.py (what is on the board) and sourcing.py (what to buy, from whom, at what price).
Writes, under ecad/gripper/kicad/fab/:
  gripper-bom.csv          one line per distinct part, with MPN, supplier number and price
  gripper-bom-jlcpcb.csv   the same parts in JLCPCB's assembly upload columns (LCSC-stocked lines only)
  gripper-harness-bom.csv  cable, connectors, adapter and off-board parts
and ecad/gripper/kicad/out/bom.json with the totals electrical.md quotes.
Evidence column: S = price and part number read from the supplier page on the retrieval date,
A = assumed (see the note on that line in sourcing.py).
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..')))
import design  # noqa: E402
import sourcing  # noqa: E402

KDIR = os.path.abspath(os.path.join(HERE, '..'))
FAB = os.path.join(KDIR, 'fab')
OUT = os.path.join(KDIR, 'out')
STRIP_KEYS = ('hdr3', 'hdr8')                                  # sourcing keys that are the same break-away strip
# (sourcing key, reference label, value text, packs): bought for the board, not a schematic symbol
ACCESSORIES = [('socket19', 'U5-SOCKETS', 'two 1x19 female 2.54 mm sockets for the DevKitC (one 2-pack)', 1)]


def ref_key(ref):
    head = ref.rstrip('0123456789')
    return (head, int(ref[len(head):] or 0))


def main():
    os.makedirs(FAB, exist_ok=True)
    groups = {}
    missing = []
    for p in design.bom_parts():
        src = sourcing.SRC.get(p.get('src') or '')
        if src is None:
            missing.append(p['ref'])
            continue
        key = (p['src'], p['value'], p['fp'], bool(p.get('dnp')))
        groups.setdefault(key, []).append(p['ref'])
    rows = []
    strip_refs = []                      # pin headers cut from one 36-pin strip: one purchase line, not one per header
    for (skey, value, fp, dnp), refs in groups.items():
        if skey in STRIP_KEYS and not dnp:
            strip_refs += refs
            continue
        src = sourcing.SRC[skey]
        refs = sorted(refs, key=ref_key)
        rows.append({'refs': refs, 'qty': len(refs), 'parts': len(refs), 'value': value,
                     'footprint': fp.split(':', 1)[1], 'dnp': dnp,
                     'mfr': src['mfr'], 'mpn': src['mpn'], 'supplier': src['supplier'], 'spn': src['spn'],
                     'unit': src['price_usd'], 'ext': round(src['price_usd'] * len(refs), 4), 'tag': src['tag'],
                     'url': src['url'], 'retrieved': src['retrieved'], 'key': skey})
    if strip_refs:
        src = sourcing.SRC[STRIP_KEYS[0]]
        refs = sorted(strip_refs, key=ref_key)
        rows.append({'refs': refs, 'qty': 1, 'parts': len(refs), 'value': 'pin headers cut from one 36-pin strip',
                     'footprint': 'PinHeader_1xNN_P2.54mm_Vertical', 'dnp': False,
                     'mfr': src['mfr'], 'mpn': src['mpn'], 'supplier': src['supplier'], 'spn': src['spn'],
                     'unit': src['price_usd'], 'ext': round(src['price_usd'], 4), 'tag': src['tag'],
                     'url': src['url'], 'retrieved': src['retrieved'], 'key': STRIP_KEYS[0]})
    rows.sort(key=lambda r: ref_key(r['refs'][0]))
    for skey, label, value, qty in ACCESSORIES:
        src = sourcing.SRC[skey]
        rows.append({'refs': [label], 'qty': qty, 'parts': 0, 'value': value,
                     'footprint': 'soldered in the U5 footprint', 'dnp': False,
                     'mfr': src['mfr'], 'mpn': src['mpn'], 'supplier': src['supplier'], 'spn': src['spn'],
                     'unit': src['price_usd'], 'ext': round(src['price_usd'] * qty, 4), 'tag': src['tag'],
                     'url': src['url'], 'retrieved': src['retrieved'], 'key': skey})

    with open(os.path.join(FAB, 'gripper-bom.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['Item', 'Qty', 'References', 'Value', 'Footprint', 'Fit', 'Manufacturer', 'MPN', 'Supplier',
                    'Supplier PN', 'Unit USD', 'Ext USD', 'Evidence', 'Retrieved', 'Supplier URL'])
        for i, r in enumerate(rows, 1):
            w.writerow([i, r['qty'], ' '.join(r['refs']), r['value'], r['footprint'], 'DNP' if r['dnp'] else 'fit',
                        r['mfr'], r['mpn'], r['supplier'], r['spn'], '%.4f' % r['unit'], '%.4f' % r['ext'], r['tag'],
                        r['retrieved'], r['url']])
    with open(os.path.join(FAB, 'gripper-bom-jlcpcb.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for r in rows:
            if r['supplier'] == 'LCSC' and not r['dnp']:
                w.writerow([r['value'], ','.join(r['refs']), r['footprint'], r['spn']])
    harness_total = 0.0
    with open(os.path.join(FAB, 'gripper-harness-bom.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['Item', 'Qty', 'Manufacturer', 'MPN', 'Supplier', 'Supplier PN', 'Unit USD', 'Ext USD', 'Evidence',
                    'Retrieved', 'Supplier URL'])
        for h in sourcing.HARNESS:
            ext = round(h['price_usd'] * h['qty'], 4)
            harness_total += ext
            w.writerow([h['item'], h['qty'], h['mfr'], h['mpn'], h['supplier'], h['spn'], '%.2f' % h['price_usd'],
                        '%.2f' % ext, h['tag'], h['retrieved'], h['url']])

    fitted = round(sum(r['ext'] for r in rows if not r['dnp']), 2)
    dnp_value = round(sum(r['ext'] for r in rows if r['dnp']), 2)
    assumed = round(sum(r['ext'] for r in rows if not r['dnp'] and r['tag'] == 'A'), 2)
    pcb = sourcing.FAB['price_5_boards_usd']['value']
    result = {
        'bom_lines': len(rows),
        'placed_parts': sum(r['parts'] for r in rows if not r['dnp']),
        'dnp_parts': sum(r['parts'] for r in rows if r['dnp']),
        'parts_without_source': missing,
        'lines_without_mpn': [' '.join(r['refs']) for r in rows if not r['mpn']],
        'assumed_price_lines': [' '.join(r['refs']) for r in rows if r['tag'] == 'A'],
        'board_parts_usd': fitted,
        'board_parts_assumed_usd': assumed,
        'dnp_parts_usd': dnp_value,
        'harness_usd': round(harness_total, 2),
        'harness_assumed_lines': [h['item'] for h in sourcing.HARNESS if h['tag'] == 'A'],
        'pcb_5_boards_usd_assumed': pcb,
        'pcb_5_boards_tag': sourcing.FAB['price_5_boards_usd']['tag'],
        'total_one_gripper_usd': round(fitted + harness_total + pcb, 2),
        'note': 'One set of parts, five bare boards, shipping and tax excluded. The servo and the FSR are in the '
                'mechanical BOM (cad/gripper/drawings/BOM.md) and are not counted here.',
    }
    with open(os.path.join(OUT, 'bom.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print('BOM lines %d, placed parts %d, DNP %d' % (result['bom_lines'], result['placed_parts'], result['dnp_parts']))
    print('board parts $%.2f (of which assumed-price lines $%.2f), harness $%.2f, 5 bare boards $%.2f [%s]' % (
        fitted, assumed, result['harness_usd'], pcb, result['pcb_5_boards_tag']))
    print('total for one gripper $%.2f' % result['total_one_gripper_usd'])
    if missing or result['lines_without_mpn']:
        print('INCOMPLETE: no source for %s; no MPN for %s' % (missing, result['lines_without_mpn']))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
