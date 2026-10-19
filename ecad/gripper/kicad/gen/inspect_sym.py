"""Print the pins of KiCad library symbols: python inspect_sym.py Lib:Name [Lib:Name ...]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import load_symbol, symbol_pins, find_all  # noqa: E402

SYMDIR = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'KiCad', '10.0', 'share', 'kicad', 'symbols')


def main(names):
    for full in names:
        lib, name = full.split(':', 1)
        try:
            sym = load_symbol(os.path.join(SYMDIR, lib + '.kicad_sym'), name)
        except KeyError:
            print(full, 'NOT FOUND')
            continue
        props = {p[1]: p[2] for p in find_all(sym, 'property')}
        print('==', full, '| fp:', props.get('Footprint', ''), '|', props.get('Description', '')[:90])
        for p in sorted(symbol_pins(sym), key=lambda t: (len(t[0]), t[0])):
            print('   ', p)


if __name__ == '__main__':
    main(sys.argv[1:])
