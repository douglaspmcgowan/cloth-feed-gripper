"""Write the project sym-lib-table and fp-lib-table from design.py.

Every standard library a part uses is listed against KiCad's own install variables
(${KICAD10_SYMBOL_DIR}, ${KICAD10_FOOTPRINT_DIR}), so the project resolves its libraries on a
machine whose global library tables were never set up (a headless kicad-cli run, a fresh install).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..')))
import design  # noqa: E402

KDIR = os.path.abspath(os.path.join(HERE, '..'))


def row(name, uri, descr):
    return '  (lib (name "%s")(type "KiCad")(uri "%s")(options "")(descr "%s"))' % (name, uri, descr)


def write():
    syms = sorted({p['sym'].split(':', 1)[0] for p in design.PARTS} - {'gripper'})
    fps = sorted({p['fp'].split(':', 1)[0] for p in design.PARTS if p.get('fp')} - {'gripper'})
    lines = ['(sym_lib_table', '  (version 7)',
             row('gripper', '${KIPRJMOD}/gripper.kicad_sym', 'ESP32-DevKitC V4 on sockets')]
    lines += [row(n, '${KICAD10_SYMBOL_DIR}/%s.kicad_sym' % n, 'KiCad 10 standard library') for n in syms]
    lines.append(')')
    with open(os.path.join(KDIR, 'sym-lib-table'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    lines = ['(fp_lib_table', '  (version 7)',
             row('gripper', '${KIPRJMOD}/gripper.pretty', 'ESP32-DevKitC V4 socket footprint')]
    lines += [row(n, '${KICAD10_FOOTPRINT_DIR}/%s.pretty' % n, 'KiCad 10 standard library') for n in fps]
    lines.append(')')
    with open(os.path.join(KDIR, 'fp-lib-table'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print('sym libs', syms)
    print('fp libs', fps)


if __name__ == '__main__':
    write()
