"""Project symbol and footprint library: the ESP32-DevKitC V4 on two 1x19 sockets.

Writes ecad/gripper/kicad/gripper.kicad_sym and gripper.pretty/ESP32-DevKitC-V4_Socket.kicad_mod.
Pin numbers 1-19 are header J2 (left, pin 1 = 3V3), 20-38 are header J3 (right, pin 20 = GND),
per the DevKitC V4 header table (see design.py DEVKITC for the source).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from sexp import Q, dump  # noqa: E402
import design  # noqa: E402

KDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def font(hide=False, justify=None):
    e = ['effects', ['font', ['size', 1.27, 1.27]]]
    if justify:
        e.append(['justify', justify])
    if hide:
        e.append(['hide', 'yes'])
    return e


def prop(name, val, x, y, hide=False, justify=None):
    return ['property', Q(name), Q(val), ['at', x, y, 0], font(hide, justify)]


def devkitc_symbol():
    left, right = design.DEVKITC['J2'], design.DEVKITC['J3']
    top = 9 * 2.54 + 2.54
    body = ['symbol', Q('ESP32-DevKitC-V4_0_1'),
            ['rectangle', ['start', -12.7, top], ['end', 12.7, -top],
             ['stroke', ['width', 0.254], ['type', 'default']], ['fill', ['type', 'background']]]]
    pins = ['symbol', Q('ESP32-DevKitC-V4_1_1')]
    for i, name in enumerate(left):
        y = 9 * 2.54 - i * 2.54
        etype = 'power_out' if name == '3V3' else ('power_in' if name == 'GND' else 'bidirectional')
        if name == '5V':
            etype = 'passive'   # fed through D7 or from USB inside the DevKitC
        pins.append(['pin', etype, 'line', ['at', -17.78, y, 0], ['length', 5.08],
                     ['name', Q(name), font()], ['number', Q(str(i + 1)), font()]])
    for i, name in enumerate(right):
        y = 9 * 2.54 - i * 2.54
        etype = 'power_in' if name == 'GND' else 'bidirectional'
        pins.append(['pin', etype, 'line', ['at', 17.78, y, 180], ['length', 5.08],
                     ['name', Q(name), font()], ['number', Q(str(i + 20)), font()]])
    return ['symbol', Q('ESP32-DevKitC-V4'),
            ['pin_names', ['offset', 1.016]], ['exclude_from_sim', 'no'],
            ['in_bom', 'yes'], ['on_board', 'yes'],
            prop('Reference', 'U', 0, top + 2.54),
            prop('Value', 'ESP32-DevKitC-V4', 0, -top - 2.54),
            prop('Footprint', 'gripper:ESP32-DevKitC-V4_Socket', 0, -top - 5.08, True),
            prop('Datasheet', design.DEVKITC['url'], 0, 0, True),
            prop('Description', 'Espressif ESP32-DevKitC V4 (ESP32-WROOM-32E) plugged into two 1x19 2.54 mm sockets', 0, 0, True),
            body, pins]


def write_symlib():
    lib = ['kicad_symbol_lib', ['version', 20251024], ['generator', Q('gripper_gen')],
           ['generator_version', Q('10.0')], devkitc_symbol()]
    with open(os.path.join(KDIR, 'gripper.kicad_sym'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(dump(lib) + '\n')


def devkitc_footprint():
    row = design.DEVKITC['row_pitch_mm']
    L, W = design.DEVKITC['board_l_mm'], design.DEVKITC['board_w_mm']
    pads = []
    for i in range(19):
        y = -9 * 2.54 + i * 2.54
        for num, x in ((i + 1, -row / 2), (i + 20, row / 2)):
            shape = 'rect' if num == 1 else 'circle'
            pads.append(['pad', Q(str(num)), 'thru_hole', shape, ['at', x, y], ['size', 1.7, 1.7],
                         ['drill', 1.0], ['layers', Q('*.Cu'), Q('*.Mask')]])
    hx, hy = W / 2, L / 2
    cy = 0.0
    lines = []
    for (a, b) in (((-hx, -hy), (hx, -hy)), ((hx, -hy), (hx, hy)), ((hx, hy), (-hx, hy)), ((-hx, hy), (-hx, -hy))):
        lines.append(['fp_line', ['start', a[0], a[1] + cy], ['end', b[0], b[1] + cy],
                      ['stroke', ['width', 0.12], ['type', 'solid']], ['layer', Q('F.SilkS')]])
        lines.append(['fp_line', ['start', a[0] * 1.02, (a[1] + cy) * 1.02], ['end', b[0] * 1.02, (b[1] + cy) * 1.02],
                      ['stroke', ['width', 0.05], ['type', 'solid']], ['layer', Q('F.CrtYd')]])
    fp = ['footprint', Q('ESP32-DevKitC-V4_Socket'), ['version', 20241229], ['generator', Q('gripper_gen')],
          ['layer', Q('F.Cu')],
          ['descr', Q('ESP32-DevKitC V4 on two 1x19 female sockets, rows %.2f mm apart; outline is the DevKitC board' % row)],
          ['attr', 'through_hole'],
          ['fp_text', 'reference', Q('REF**'), ['at', 0, -hy - 1.5], ['layer', Q('F.SilkS')], font()],
          ['fp_text', 'value', Q('ESP32-DevKitC-V4'), ['at', 0, hy + 1.5], ['layer', Q('F.Fab')], font()],
          ['fp_text', 'user', Q('USB'), ['at', 0, hy - 2.5], ['layer', Q('F.SilkS')], font()]]
    fp += lines + pads
    d = os.path.join(KDIR, 'gripper.pretty')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'ESP32-DevKitC-V4_Socket.kicad_mod'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(dump(fp) + '\n')


if __name__ == '__main__':
    write_symlib()
    devkitc_footprint()
    print('wrote gripper.kicad_sym and gripper.pretty')
