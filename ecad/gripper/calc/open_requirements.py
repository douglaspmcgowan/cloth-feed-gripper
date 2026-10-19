"""The two open requirements as parameters: R15 pad-force cap {10, 8} N and R19 close time {0.5, 0.75} s.

Run from the repository root:  python ecad/gripper/calc/open_requirements.py

Jargon.
  R15, R19 here are DESIGN-BASIS requirement ids (pad-force cap; full-close time), not the board resistors R15 (2.70 kohm FSR
    resistor) and R19 (10 kohm button pull-up). The board resistor is always written "board R15".
  Fit A / Fit B: servo electrical fits of docs/gripper/analysis/dyno.md.
  Duty cycle: DESIGN-BASIS section 7: approach and touchdown 4.0 s, close R19, lift and move 5.0 s, feed hold 20.0 s,
    release 0.5 s, return 5.0 s.
Neither requirement is settled here. Every number below is given for both values.
Tags: [S] sourced, [D] derived here, [A] assumed.
"""
import itertools

import _common as cm
from _common import ELEC, FITS, v
import fsr_frontend as ff
import ina219_budget as ib
import power_budget as pb

CAPS = (10.0, 8.0)
CLOSES = (0.5, 0.75)
I_MOVE = 0.15       # servo moving or parked with no load [A]
SETPOINT_N = 5.0    # grip setpoint during the hold phases (config.h F_TARGET_DEFAULT_N)


def mean_current(fit, close_s):
    """Mean servo-rail current over the section 7 cycle; close phase drawn at the 5 N hold current, release at their mean [A]."""
    hold = cm.servo_current_at_force(SETPOINT_N, fit)
    # the dyno.md hold point is 5 N + 2 N tension -> use the table value for the feed hold, the 5 N formula for the close
    hold_tab = FITS[fit]['hold_A']
    phases = [('approach + touchdown', 4.0, I_MOVE), ('close', close_s, hold), ('lift and move', 5.0, hold_tab), ('feed hold', 20.0, hold_tab),
              ('release', 0.5, 0.5 * (hold_tab + I_MOVE)), ('return', 5.0, I_MOVE)]
    t = sum(p[1] for p in phases)
    q = sum(p[1] * p[2] for p in phases)
    return q / t, t


def run():
    r = {'combos': []}
    for cap, close in itertools.product(CAPS, CLOSES):
        c = {'cap_N': cap, 'close_s': close}
        for fit in ('A', 'B'):
            i_off = cm.servo_current_at_force(cap, fit)
            i_ideal = cm.servo_current_ideal(cap, fit)
            mean_i, cycle = mean_current(fit, close)
            pt = pb.input_point(12.0, mean_i)
            c[fit] = {'i_cap_A': i_off, 'i_cap_ideal_A': i_ideal, 'margin_trip_A': ib.TRIP_A - i_off, 'margin_trip_ideal_A': ib.TRIP_A - i_ideal,
                      'shunt_W': i_off ** 2 * ELEC['r_shunt_ohm'], 'mean_servo_A': mean_i, 'cycle_s': cycle, 'mean_12V_input_mA': pt['iin_A'] * 1e3,
                      'min_trip_A': i_off / (1 - ib.budget()['worst_pct'] / 100.0) * 1.05}
        c['node_cap_mV'] = cm.node_mv(cap)
        c['node_cap_vs_span_mV'] = cm.node_mv(cap) - 2450.0
        exact, e96 = ff.best_resistor(cap)
        c['r15_best_e96_ohm'] = e96
        c['r15_exact_ohm'] = exact
        c['node_cap_best_mV'] = cm.node_mv(cap, e96)
        c['changes'] = changes(cap, close, c)
        r['combos'].append(c)
    # each row of the board does not depend on the other requirement
    r['independent'] = {'close_time_changes_board': False, 'cap_changes_board': True}
    return r


def changes(cap, close, c):
    ch = []
    if cap == 10.0:
        ch.append('board R15: 2.70k -> 2.61k or 2.67k (node at 10 N is %.1f mV, %+.1f mV over the 2450 mV edge; harmless but the cap is the strict case)' % (c['node_cap_mV'], c['node_cap_vs_span_mV']))
    else:
        ch.append('board R15: 2.70k -> 3.16k (E96) puts 8 N at %.0f mV instead of %.0f mV; 2.70k still works with %.0f mV of spare span' % (
            cm.node_mv(8.0, 3160.0), c['node_cap_mV'], -c['node_cap_vs_span_mV']))
    ch.append('firmware (not board): STALL_CURRENT_A %.1f A; Fit A holding current at %.0f N is %.2f A with offset, %.2f A ideal; the trip must stay above the holding current (minimum %.2f A) or the stall test moves to a differential measurement' % (
        v('ina_trip_current_a'), cap, c['A']['i_cap_A'], c['A']['i_cap_ideal_A'], c['A']['min_trip_A']))
    ch.append('F1, adapter, RS1, buck, bulk C12, trace width: none (set by the %.2f A Fit A stall, not by the cap or the close time)' % pb.FITS['A']['stall_A'])
    if close == 0.75:
        ch.append('close time 0.75 s: none on the board (cycle %.2f s instead of 35.00 s; mean current changes under 0.5 %%)' % c['A']['cycle_s'])
    else:
        ch.append('close time 0.5 s: none on the board')
    return ch


def report(r):
    print('Open requirements as parameters: pad-force cap R15 in {10, 8} N, full-close time R19 in {0.5, 0.75} s (neither is settled here)')
    cols = ['R15 %g N / R19 %g s' % (c['cap_N'], c['close_s']) for c in r['combos']]
    rows = []

    def row(label, f):
        rows.append([label] + [f(c) for c in r['combos']])
    row('servo current at the cap, Fit A (T/K + offset) A', lambda c: '%.3f' % c['A']['i_cap_A'])
    row('servo current at the cap, Fit B A', lambda c: '%.3f' % c['B']['i_cap_A'])
    row('  same, T/K only: Fit A / Fit B A', lambda c: '%.3f / %.3f' % (c['A']['i_cap_ideal_A'], c['B']['i_cap_ideal_A']))
    row('margin to the firmware trip, Fit A / Fit B A', lambda c: '%+.3f / %+.3f' % (c['A']['margin_trip_A'], c['B']['margin_trip_A']))
    row('  same, T/K only: Fit A / Fit B A', lambda c: '%+.3f / %+.3f' % (c['A']['margin_trip_ideal_A'], c['B']['margin_trip_ideal_A']))
    row('FSR node at the cap, board R15 2.70k mV', lambda c: '%.1f (%+.1f vs 2450)' % (c['node_cap_mV'], c['node_cap_vs_span_mV']))
    row('FSR node at the cap, best E96 R15 mV', lambda c: '%.0f ohm -> %.1f' % (c['r15_best_e96_ohm'], c['node_cap_best_mV']))
    row('shunt dissipation at the cap, Fit A / Fit B W', lambda c: '%.2f / %.2f' % (c['A']['shunt_W'], c['B']['shunt_W']))
    row('cycle time s', lambda c: '%.2f' % c['A']['cycle_s'])
    row('mean servo-rail current over the cycle, Fit A / Fit B A', lambda c: '%.3f / %.3f' % (c['A']['mean_servo_A'], c['B']['mean_servo_A']))
    row('mean current from the 12 V adapter, Fit A / Fit B mA', lambda c: '%.0f / %.0f' % (c['A']['mean_12V_input_mA'], c['B']['mean_12V_input_mA']))
    print(cm.table(rows, ['quantity'] + cols))
    print('\nMean current assumes: close phase at the 5 N hold current, hold phases at the dyno.md hold current, parked/moving 0.15 A, release the mean of the two [A].')
    print('\nBoard values that change for each combination:')
    for c in r['combos']:
        print('  R15 %g N / R19 %g s:' % (c['cap_N'], c['close_s']))
        for x in c['changes']:
            print('    - ' + x)
    print('\nSummary: the close time (R19) changes no board value. The force cap (R15) changes board R15 only, and only at the margin. '
          'The firmware trip (STALL_CURRENT_A) is compared with the Fit A holding current at each cap (see ina219_budget.py).')


if __name__ == '__main__':
    report(run())
