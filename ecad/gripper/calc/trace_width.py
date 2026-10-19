"""External-layer 1 oz copper trace width for the board's currents, voltage drop, and via current.

Run from the repository root:  python ecad/gripper/calc/trace_width.py

Jargon.
  IPC-2221: the PCB design standard whose current-carrying curves are fitted by I = k * dT^b * A^c (I in A, dT in C
    temperature rise, A the copper cross-section in square mil). The constants are those of the public calculator page
    cited in constants.py; this file describes the relation in its own words and does not reproduce the standard.
  1 oz copper: 1.378 mil (35 um) thick. A mil is a thousandth of an inch (0.0254 mm).
  Via: a plated hole; its copper is a thin tube, area = pi x (hole diameter - plating) x plating thickness.
Tags: [S] constants.py, [D] derived here, [A] assumed.
"""
import json
import math
import os
import sys

import _common as cm
from _common import v

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'kicad', 'gen'))
import placement  # noqa: E402  (board widths: the calculation uses the widths the board is routed at)


def __getattr__(name):
    """Keep the historical HOLD_A API without binding a physical value at import time."""
    if name == 'HOLD_A':
        return v('trace_hold_current_a')
    raise AttributeError(name)


def currents():
    return (v('trace_supply_current_a'), cm.v_input("trace_demand_A"),
            v('trace_auxiliary_current_a'))


def thickness_m():
    return v('ipc_mil_per_oz') * v('trace_mm_per_mil') * 1e-3
CHOSEN_MM = placement.W_WIDE                           # width the servo rail and 12 V path are routed at
NECK_MM = placement.W_NECK                             # width where a power track necks down onto a pad
def stall_a():
    return cm.v_input("trace_demand_A")                                         # Fit A stall current [D: same]
STATS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'kicad', 'out', 'board_stats.json')


def rise_c(i_a, w_mm):
    """Steady-state rise of a long external 1 oz trace of this width at this current [D from the cited relation]."""
    area = w_mm / v('trace_mm_per_mil') * v('ipc_mil_per_oz')
    return (i_a / (v('ipc_k_ext') * area ** v('ipc_c'))) ** (1.0 / v('ipc_b'))


def area_mil2(i_a, rise):
    """Copper cross-section needed for a current and a rise (external layer) [D from the cited relation]."""
    return (i_a / (v('ipc_k_ext') * rise ** v('ipc_b'))) ** (1.0 / v('ipc_c'))


def width_mm(i_a, rise, oz=None):
    oz = 1.0 if oz is None else oz
    return area_mil2(i_a, rise) / (oz * v('ipc_mil_per_oz')) * v('trace_mm_per_mil')


def current_from_area(area, rise):
    return v('ipc_k_ext') * rise ** v('ipc_b') * area ** v('ipc_c')


def drop_mv_per_10mm(i_a, w_mm, rise=None):
    """Voltage drop across 10 mm of trace at the temperature the rise implies (copper tempco) [D]."""
    rise = v('trace_temperature_rises_c')[0] if rise is None else rise
    rho = v('cu_rho') * (1 + v('cu_tc') * (
        v('trace_ambient_temperature_c') + rise - v('trace_reference_temperature_c')))
    r = rho * (v('trace_reference_length_mm') * 1e-3) / (w_mm * 1e-3 * thickness_m())
    return i_a * r * 1e3, r * 1e3


def via_current(drill_mm, rise, plating_um=None):
    plating_um = v('trace_via_plating_um') if plating_um is None else plating_um
    t = plating_um * 1e-3
    area_mm2 = math.pi * (drill_mm - t) * t
    area = area_mm2 / (v('trace_mm_per_mil') ** 2)
    return {'area_mm2': area_mm2, 'area_mil2': area, 'current_A': current_from_area(area, rise)}


def run():
    r = {'widths': [], 'chosen_mm': CHOSEN_MM}
    for i in currents():
        for dt in v('trace_temperature_rises_c'):
            w = width_mm(i, dt)
            dm, rm = drop_mv_per_10mm(i, w, dt)
            dc, rc = drop_mv_per_10mm(i, CHOSEN_MM, dt)
            r['widths'].append({'current_A': i, 'rise_C': dt, 'width_mm': w, 'drop_mV_per_10mm': dm, 'r_mohm_per_10mm': rm,
                                'drop_mV_per_10mm_at_chosen': dc})
    drill = v('trace_via_drill_mm')
    r['vias'] = [{'drill_mm': drill, 'rise_C': dt, **via_current(drill, dt)}
                 for dt in v('trace_temperature_rises_c')]
    r['n_vias_for_5A_10C'] = math.ceil(v('trace_auxiliary_current_a') / r['vias'][0]['current_A'])
    r['n_vias_for_377A_10C'] = math.ceil(stall_a() / r['vias'][0]['current_A'])
    r['neck_mm'] = NECK_MM
    hold = v('trace_hold_current_a')
    reference_rise = v('trace_temperature_rises_c')[0]
    r['rise_C'] = {'wide_hold': rise_c(hold, CHOSEN_MM), 'wide_stall': rise_c(stall_a(), CHOSEN_MM),
                   'neck_hold': rise_c(hold, NECK_MM),
                   'neck_stall_long_trace_bound': rise_c(stall_a(), NECK_MM)}
    r['max_current_A_at_10C'] = {
        'wide': current_from_area(CHOSEN_MM / v('trace_mm_per_mil') * v('ipc_mil_per_oz'), reference_rise),
        'neck': current_from_area(NECK_MM / v('trace_mm_per_mil') * v('ipc_mil_per_oz'), reference_rise)}
    r['board'] = None
    if os.path.exists(STATS):
        with open(STATS, encoding='utf-8') as f:
            s = json.load(f)
        servo = [s['power_nets'][k] for k in ('V_BUCK', 'SERVO_V')]
        wide = sum(n['by_width_mm'].get('%.2f' % CHOSEN_MM, float()) for n in servo)
        neck = sum(n['by_width_mm'].get('%.2f' % NECK_MM, float()) for n in servo)
        rho = v('cu_rho') * (1 + v('cu_tc') * (
            v('trace_ambient_temperature_c') + reference_rise - v('trace_reference_temperature_c')))
        r_wide = rho * wide * 1e-3 / (CHOSEN_MM * 1e-3 * thickness_m())
        r_neck = rho * neck * 1e-3 / (NECK_MM * 1e-3 * thickness_m())
        r['board'] = {'power_wide_mm': s['power_wide_mm'], 'power_neck_mm': s['power_neck_mm'],
                      'power_net_vias': s['power_net_vias'], 'servo_path_wide_mm': wide, 'servo_path_neck_mm': neck,
                      'servo_path_copper_mohm_upper': (r_wide + r_neck) * 1e3,
                      'servo_path_drop_mV_at_stall_upper': (r_wide + r_neck) * stall_a() * 1e3,
                      'ground_vias': s['ground_vias'], 'bottom_ground_coverage_pct': s['bottom_ground_coverage_pct']}
    return r


def report(r):
    print('External 1 oz trace width (k %.3f, b %.2f, c %.3f from the cited calculator page; 1 oz = %.3f mil) [S]' % (v('ipc_k_ext'), v('ipc_b'), v('ipc_c'), v('ipc_mil_per_oz')))
    print(cm.table([[x['current_A'], x['rise_C'], '%.2f' % x['width_mm'], '%.2f' % x['r_mohm_per_10mm'], '%.1f' % x['drop_mV_per_10mm'], '%.1f' % x['drop_mV_per_10mm_at_chosen']] for x in r['widths']],
                   ['current A', 'rise C', 'min width mm', 'R per 10 mm mohm', 'drop mV / 10 mm at that width', 'drop mV / 10 mm at %.1f mm' % r['chosen_mm']]))
    print('Routed width of the servo rail and the 12 V path: %.1f mm (needs %.2f mm for 3.77 A at 10 C rise; carries %.2f A at 10 C).' % (
        r['chosen_mm'], width_mm(stall_a(), v('trace_temperature_rises_c')[0]),
        r['max_current_A_at_10C']['wide']))
    print('Rise at %.1f mm: %.1f C at the %.2f A hold current, %.1f C at the %.2f A stall current (steady state; the stall lasts 0.1 s before the trip).' % (
        r['chosen_mm'], r['rise_C']['wide_hold'], v('trace_hold_current_a'),
        r['rise_C']['wide_stall'], stall_a()))
    print('Necks onto pads are %.1f mm wide: %.1f C rise at hold as a long trace; %.0f C at stall is the long-trace bound, not reached by a neck a few mm long between wide copper [A].' % (
        r['neck_mm'], r['rise_C']['neck_hold'], r['rise_C']['neck_stall_long_trace_bound']))
    if r['board']:
        b = r['board']
        print('As routed (kicad/out/board_stats.json): power nets %.1f mm at %.1f mm, %.1f mm of neck, %d vias in any power net.' % (
            b['power_wide_mm'], r['chosen_mm'], b['power_neck_mm'], b['power_net_vias']))
        print('Servo path copper (V_BUCK + SERVO_V, every branch counted, so an upper bound): %.1f mm wide + %.1f mm neck = %.1f mohm, %.0f mV at stall.' % (
            b['servo_path_wide_mm'], b['servo_path_neck_mm'], b['servo_path_copper_mohm_upper'], b['servo_path_drop_mV_at_stall_upper']))
        print('Ground: %d vias to the bottom plane, which covers %.1f %% of the board.' % (b['ground_vias'], b['bottom_ground_coverage_pct']))
    print('\n0.4 mm drill via, %.0f um plating [A]: ' % v('trace_via_plating_um'))
    print(cm.table([[x['rise_C'], '%.4f' % x['area_mm2'], '%.1f' % x['area_mil2'], '%.2f' % x['current_A']] for x in r['vias']], ['rise C', 'barrel area mm2', 'area mil2', 'current A']))
    print('Vias in parallel for 3.77 A at 10 C: %d; for 5 A: %d (use at least 4 for each layer change in the servo path; the external-layer relation is applied to a barrel, a conservative use [A]).' % (
        r['n_vias_for_377A_10C'], r['n_vias_for_5A_10C']))


if __name__ == '__main__':
    report(run())
