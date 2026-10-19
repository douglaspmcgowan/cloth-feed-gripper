"""Wiring harness of the gripper controller: the one cable from the board to the wrist, as data, with the checks that decide it.

Run from the repository root:  python ecad/gripper/calc/harness.py
Writes out/harness.json, out/harness.txt (stdout capture), out/harness_wiring.csv, out/harness_wiring.md.

Jargon.
  Trunk: the sleeved cable from the board (J3, J4) to the wrist, ELEC['cable_len_m'] long.
  Pigtail: the 100 mm cut-off stub of the 3-pin servo extension lead that carries the male plug (X1) into the servo's own lead.
  Splice: a soldered joint covered with heat-shrink, where the trunk wire meets the pigtail wire (SPL-*).
  SM pair: the 4-position latching wire-to-wire connector at the wrist that lets the gripper detach.
  Clincher: Amphenol 2-position connector that grips the FSR tail; the tail is never soldered.
  COM / NO / NC: common, normally-open and normally-closed contacts of the D2F-01L microswitch.
  Dynamic bend radius: the tightest curve a wire may follow while it moves, here 10 x outer diameter.
Tags: [S] sourced (constants.py, sourcing.py or a repo document), [D] derived here, [A] assumed (stated here).
"""
import contextlib
import csv
import collections
import io
import json
import math
import os
import re
import sys

import _common as cm
import formulas
from _common import ELEC, FITS, v
import design
import sourcing
import power_budget as pb

bd = pb.bd

def cable_mm():
    return ELEC['cable_len_m'] * 1000.0          # board to wrist [A, measure at assembly]


def adc_lsb_mv():
    """12-bit ESP32 ADC step at the divider supply [D]."""
    return formulas.adc_step(v('fsr_default_vcc_mv'), v('esp_adc_resolution_bits'))


# colour of each 26 AWG signal conductor (five Adafruit spools in sourcing.HARNESS)
COLOUR = {'PWM': 'orange', '3V3': 'red', 'FSR': 'white', 'LIM': 'green', 'SGND': 'gray'}


def selected_servo():
    with open(os.path.join(cm.REPO, 'cad', 'gripper', 'params.json'), encoding='utf-8') as f:
        return json.load(f)['servo']['model']


def awg_ohm_m(awg):
    return v('awg%d_ohm_m' % awg)


def pair_drop_v(awg, length_m, current_a):
    """Voltage lost in a supply-and-return pair of equal wires [D]: I x 2 x L x ohm/m."""
    return current_a * 2.0 * length_m * awg_ohm_m(awg)


def r_wire_ohm(awg, length_mm):
    return awg_ohm_m(awg) * length_mm / 1000.0


# ---------------------------------------------------------------------------------------------
# The wiring table. kind: spool = cut from a bought spool, assembly = cut from a bought lead,
# component = a component's own lead, supplied = part of another item, bought = a bought cable.
# net is the design.py net of the board-side pin when `frm` is a board connector.
# ---------------------------------------------------------------------------------------------
def _row(id_, frm, to, net, awg, colour, length_mm, part, notes, kind, wired=True):
    return dict(id=id_, frm=frm, to=to, net=net, gauge=awg, colour=colour, length_mm=length_mm, part=part, notes=notes, kind=kind, wired=wired)


def rows():
    t = cable_mm()
    tr = 'Trunk, in the braided sleeve'
    xh = 'J4 JST XH B4B-XH-A, housing XHP-4 with SXH-001T-P0.6 crimp contact'
    sm = 'JST SM 4-position pair SMP-04V-BC / SMR-04V-B, wrist end'
    ph = 'J3 Phoenix MKDS 1,5/3-5.08 screw terminal'
    servo = selected_servo()
    pwr, pig, sig = v('harness_awg_power'), v('harness_awg_pigtail'), v('harness_awg_signal')
    pigtail_mm, fsr_run_mm, lim_run_mm = v('harness_pigtail_mm'), v('harness_fsr_run_mm'), v('harness_limit_run_mm')
    cap_lead_mm, adapter_mm, usb_mm = v('harness_cap_lead_mm'), v('harness_adapter_cord_mm'), v('harness_usb_cable_mm')
    unwired_mm = v('harness_unwired_length_mm')
    return [
        _row('H01', 'J3.1', 'SPL-GND', 'GND', pwr, 'black', t, ph + ', pin 1',
             tr + '. Servo return. Splice at the forearm end with H04 and the capacitor lead H08.', 'spool'),
        _row('H02', 'J3.2', 'SPL-V', 'SERVO_V', pwr, 'red', t, ph + ', pin 2',
             tr + '. Servo V+, 6.58 V nominal. Splice with H05 and the capacitor lead H07.', 'spool'),
        _row('H03', 'J3.3', 'SPL-PWM', 'SERVO_PWM', sig, COLOUR['PWM'], t, ph + ', pin 3',
             tr + '. 5 V logic, 50 Hz. Fold the strands back on themselves so the screw clamps more copper.', 'spool'),
        _row('H04', 'SPL-GND', 'X1.1', None, pig, 'black', pigtail_mm, 'Servo extension lead 972, male plug X1, pin 1',
             'Pigtail. Gauge is not stated by the seller [A]. Cut the female end off the lead.', 'assembly'),
        _row('H05', 'SPL-V', 'X1.2', None, pig, 'red', pigtail_mm, 'Servo extension lead 972, male plug X1, pin 2', 'Pigtail [A gauge].', 'assembly'),
        _row('H06', 'SPL-PWM', 'X1.3', None, pig, 'white', pigtail_mm, 'Servo extension lead 972, male plug X1, pin 3', 'Pigtail [A gauge]; white is the signal wire of this lead.', 'assembly'),
        _row('H07', 'SPL-V', 'C_WRIST.+', None, 'cap lead', 'red', cap_lead_mm, 'EEU-FR1C471 470 uF 16 V, + lead (longer lead)',
             'Soldered across the splice. Polarised: wrong way round it fails. Capacitance is design.ELEC c_wrist_F.', 'component'),
        _row('H08', 'SPL-GND', 'C_WRIST.-', None, 'cap lead', 'black', cap_lead_mm, 'EEU-FR1C471 470 uF 16 V, - lead (stripe side)', 'Soldered across the splice.', 'component'),
        _row('H09', 'X1.1', 'SERVO.GND', None, 'could-not-tell', 'could-not-tell', 'could-not-tell', servo + ' lead, 3-pin plug', 'Supplied with the selected servo; lead gauge, colour, and length are not recorded. Not built. Team must confirm on delivered servo.', 'supplied'),
        _row('H10', 'X1.2', 'SERVO.V+', None, 'could-not-tell', 'could-not-tell', 'could-not-tell', servo + ' lead, 3-pin plug', 'Supplied with the selected servo; lead gauge, colour, and length are not recorded. Team must confirm on delivered servo.', 'supplied'),
        _row('H11', 'X1.3', 'SERVO.SIG', None, 'could-not-tell', 'could-not-tell', 'could-not-tell', servo + ' lead, 3-pin plug', 'Supplied with the selected servo; lead gauge, colour, and length are not recorded. Team must confirm on delivered servo.', 'supplied'),
        _row('H12', 'J4.1', 'SM.1', '+3V3', sig, COLOUR['3V3'], t, xh + ', pin 1', tr + '. 3.3 V to the FSR, about 0.9 mA at 10 N.', 'spool'),
        _row('H13', 'J4.2', 'SM.2', 'FSR_SIG', sig, COLOUR['FSR'], t, xh + ', pin 2', tr + '. FSR node; carries the same 0.9 mA as H12 because R15 is on the board.', 'spool'),
        _row('H14', 'J4.3', 'SM.3', 'LIM_SIG', sig, COLOUR['LIM'], t, xh + ', pin 3', tr + '. Pulled up by R17 4.7 k; switch closing pulls it to GND.', 'spool'),
        _row('H15', 'J4.4', 'SM.4', 'GND', sig, COLOUR['SGND'], t, xh + ', pin 4', tr + '. Sensor return, separate from the servo return H01. Carries only the 0.7 mA limit current.', 'spool'),
        _row('H16', 'SM.1', 'FSR.1', None, sig, COLOUR['3V3'], fsr_run_mm, sm + ', contact 1; to Clincher position 1',
             'Along finger B. Clincher end: crimp or solder to the Clincher contact per Amphenol, never to the FSR tail. Length includes the service loop [A].', 'spool'),
        _row('H17', 'SM.2', 'FSR.2', None, sig, COLOUR['FSR'], fsr_run_mm, sm + ', contact 2; to Clincher position 2', 'Same route as H16. FSR leg polarity does not matter.', 'spool'),
        _row('H18', 'SM.3', 'SW.NO', None, sig, COLOUR['LIM'], lim_run_mm, sm + ', contact 3; to D2F-01L NO terminal', 'Normally-open contact: closes to COM when the lever is pressed at jaw open.', 'spool'),
        _row('H19', 'SM.4', 'SW.COM', None, sig, COLOUR['SGND'], lim_run_mm, sm + ', contact 4; to D2F-01L COM terminal', 'Common contact, to the sensor return.', 'spool'),
        _row('A01', 'ADAPTER.TIP', 'J1.1', 'VIN_RAW', 'supplied cord', 'supplied', adapter_mm, 'J1 barrel jack 5.5 x 2.1 mm, centre positive; Pololu WPA-1774',
             '12 V in. J2 is the screw-terminal alternative; use one input only.', 'bought'),
        _row('A02', 'ADAPTER.SLEEVE', 'J1.2', 'GND', 'supplied cord', 'supplied', adapter_mm, 'J1 barrel jack sleeve', 'Return of the adapter cord (same cord as A01).', 'bought'),
        _row('U01', 'HOST.USB-A', 'U5.USB', None, 'supplied cable', 'supplied', usb_mm, 'Adafruit 592 USB A to micro-B on the DevKitC', 'Firmware load and serial. Not part of the wrist cable.', 'bought'),
        _row('N01', 'J2', '-', 'VIN_RAW', '-', '-', unwired_mm, 'J2 screw terminal 2-way', 'Not wired: alternative 12 V input, use J1 or J2, not both.', 'none', wired=False),
        _row('N02', 'J5', '-', 'FB_IN', '-', '-', unwired_mm, 'J5 1x3 header', 'Not wired: optional servo position feedback, unfitted (FB_ENABLED 0).', 'none', wired=False),
        _row('N03', 'J6', '-', 'DRV_AIN1', '-', '-', unwired_mm, 'J6 1x8 header', 'Not wired: DC-gearmotor branch expansion, unused in the servo build.', 'none', wired=False),
        _row('N04', 'J7', '-', 'SERVO_PWM', '-', '-', unwired_mm, 'J7 1x3 header', 'Not wired: bench servo header, bench use only.', 'none', wired=False),
    ]


def pin_net_map():
    return {(p['ref'], pin): net for p in design.PARTS for pin, net in p['pins'].items()}


def check_nets(table):
    """Fail loudly if a row's board-side pin has a different net in design.py."""
    pn = pin_net_map()
    for r in table:
        m = re.match(r'^(J\d+)\.(\d+)$', r['frm'])
        if not m or not r['wired'] or r['net'] is None:
            continue
        got = pn.get((m[1], m[2]))
        if got != r['net']:
            raise AssertionError('harness row %s: %s is net %r in design.py, row says %r' % (r['id'], r['frm'], got, r['net']))
    # every pin of J3 and J4 must appear exactly once as a source
    for ref in ('J3', 'J4'):
        pins = sorted(p for (rf, p) in pn if rf == ref)
        srcs = sorted(r['frm'].split('.')[1] for r in table if r['wired'] and r['frm'].startswith(ref + '.'))
        if pins != srcs:
            raise AssertionError('%s pins %s are not each wired once: harness has %s' % (ref, pins, srcs))
    # the not-wired rows must name nets that exist on that connector
    for r in table:
        if not r['wired'] and r['net']:
            ref = r['frm']
            if r['net'] not in set(n for (rf, _), n in pn.items() if rf == ref):
                raise AssertionError('not-wired row %s: %s has no net %s' % (r['id'], ref, r['net']))


def jaw_min_deg():
    with open(os.path.join(cm.REPO, 'firmware', 'gripper', 'config.h'), encoding='utf-8') as f:
        m = re.search(r'#define\s+JAW_MIN_DEG\s+(-?[0-9.]+)', f.read())
    return float(m[1])


def servo_budget(awg_trunk):
    """Plug voltage and drop for a trunk power pair of `awg_trunk`, at hold and stall, using power_budget's currents [D]."""
    r_trunk = 2.0 * r_wire_ohm(awg_trunk, cable_mm())
    r_pig = 2.0 * r_wire_ohm(v('harness_awg_pigtail'), v('harness_pigtail_mm'))
    # Stop the calculated path at X1: the selected servo's lead facts are not recorded.
    r_lead = v('harness_servo_lead_ohm')
    band, rating, v_min = v('harness_plug_band_v'), v('harness_plug_rating_v'), v('harness_servo_v_min')
    r_total = r_trunk + r_pig
    lo, nom, hi = bd.setpoint_range()
    out = []
    for fit in ('A', 'B'):
        for sc in ('hold', 'stall'):
            vals = {}
            for lab, vs in (('low', lo), ('nom', nom), ('high', hi)):
                vals[lab] = vs - pb.servo_current(fit, sc, vs, r_total) * r_total
            i = pb.servo_current(fit, sc, nom, r_total)
            out.append({'awg': awg_trunk, 'fit': fit, 'scenario': sc, 'i_A': i, 'trunk_pair_drop_V': i * r_trunk, 'total_drop_V': i * r_total,
                        'plug_low_V': vals['low'], 'plug_nom_V': vals['nom'], 'plug_high_V': vals['high'],
                        'in_band': vals['low'] >= band[0] and vals['high'] <= band[1], 'below_rating': vals['high'] <= rating,
                        'nom_in_band': band[0] <= vals['nom'] <= band[1], 'above_servo_min': vals['low'] >= v_min})
    holds = [c for c in out if c['scenario'] == 'hold']
    # budget: at hold the nominal plug voltage is inside the calibration band; in every case the plug stays between 4.8 V and 6.8 V
    budget_ok = all(c['nom_in_band'] for c in holds) and all(c['above_servo_min'] and c['below_rating'] for c in out)
    a_hold = [c for c in holds if c['fit'] == 'A'][0]
    return {'awg': awg_trunk, 'budget_ok': budget_ok,
            'corner_margin_mV': (a_hold['plug_low_V'] - band[0]) * 1e3,
            'r_max_corner_ohm': (lo - band[0]) / FITS['A']['hold_A'], 'r_trunk_pair_ohm': r_trunk, 'r_pigtail_pair_ohm': r_pig, 'r_servo_lead_pair_ohm': r_lead, 'r_total_ohm': r_total, 'cases': out}


def signal_drops():
    """Resistance and worst-case drop of each 26 AWG conductor at its current [D]."""
    vcc_mv = v('fsr_default_vcc_mv')
    awg = v('harness_awg_signal')
    i_fsr = vcc_mv / (cm.fsr_r(v('harness_fsr_force_cap_n')) + ELEC['r_fsr_fixed_ohm']) * 1e-3     # A, at the R15 cap
    i_lim = vcc_mv / 1e3 / ELEC['r_lim_pullup_ohm']                                   # A, switch closed
    spec = [('H03', 'SERVO_PWM', i_pwm_a()), ('H12', '+3V3', i_fsr), ('H13', 'FSR_SIG', i_fsr), ('H14', 'LIM_SIG', i_lim), ('H15', 'GND (sensor)', i_lim)]
    res = []
    for hid, sig, i in spec:
        r = r_wire_ohm(awg, cable_mm())
        res.append({'id': hid, 'signal': sig, 'current_A': i, 'r_ohm': r, 'drop_mV': i * r * 1e3, 'drop_lsb': i * r * 1e3 / adc_lsb_mv()})
    # FSR reading error from the two series wires, at 5 N and 8 N
    extra = 2.0 * r_wire_ohm(awg, cable_mm())
    err = []
    for f in v('harness_fsr_error_forces_n'):
        mv = vcc_mv * ELEC['r_fsr_fixed_ohm'] / (ELEC['r_fsr_fixed_ohm'] + cm.fsr_r(f) + extra)
        err.append({'force_N': f, 'read_N': pb.fsr_force_from_mv(mv), 'err_N': pb.fsr_force_from_mv(mv) - f, 'extra_r_ohm': extra})
    # limit switch low level
    lim_low_mv = i_lim * 2.0 * r_wire_ohm(awg, cable_mm()) * 1e3
    return {'conductors': res, 'fsr_error': err, 'limit_low_mV': lim_low_mv, 'limit_vil_mV': v('harness_vil_fraction') * vcc_mv, 'i_fsr_mA': i_fsr * 1e3, 'i_lim_mA': i_lim * 1e3}


def i_pwm_a():
    return v('harness_pwm_current_a')


def totals(table):
    spare = v('harness_spare_fraction')
    by = collections.defaultdict(float)
    for r in table:
        if r['wired'] and r['kind'] == 'spool':
            by[(r['gauge'], r['colour'])] += r['length_mm']
    buy = []
    for (g, c), mm in sorted(by.items()):
        buy.append({'gauge_awg': g, 'colour': c, 'length_mm': mm, 'with_spare_mm': mm * (1 + spare), 'spare_pct': 100 * spare})
    per_gauge = collections.defaultdict(float)
    for b in buy:
        per_gauge[b['gauge_awg']] += b['length_mm']
    return {'by_gauge_colour': buy, 'by_gauge_mm': {str(k): x for k, x in per_gauge.items()},
            'by_gauge_with_spare_mm': {str(k): x * (1 + spare) for k, x in per_gauge.items()},
            'sum_rows_mm': sum(b['length_mm'] for b in buy)}


def flex(jmin):
    od, jaw_max, cycle_s = v('harness_od_26awg_mm'), v('harness_jaw_max_deg'), v('harness_cycle_s')
    life, semester = v('harness_design_life_cycles'), v('harness_semester_fraction')
    r_min = v('harness_bend_factor') * od
    r_abs = v('harness_bend_factor_abs') * od
    travel = jaw_max - jmin
    cph = 3600.0 / cycle_s
    hours = life / cph
    return {'od_mm': od, 'min_radius_mm': r_min, 'abs_min_radius_mm': r_abs, 'min_loop_diameter_mm': 2 * r_min,
            'jaw_travel_deg': travel, 'jaw_min_deg': jmin, 'jaw_max_deg': jaw_max,
            'slack_for_travel_mm': r_min * math.radians(travel),
            'cycles_per_hour': cph, 'design_cycles': life, 'hours_for_design_life': hours,
            'cycles_per_semester': life * semester, 'hours_per_semester': hours * semester,
            'inspect_every_cycles': life * semester,
            'basis': 'one open-close of the jaw bends the lead across the finger-B knuckle once; %.0f cycles = %.1f cycles/h x %.0f h (%.0f s cycle) [A, DESIGN-BASIS section 7]' % (
                life, cph, hours, cycle_s)}


def markdown(table):
    head = ['id', 'from', 'to', 'signal', 'gauge AWG', 'colour', 'length mm', 'connector and pin', 'notes']
    lines = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join(['---'] * len(head)) + '|']
    for r in table:
        length = '%g' % r['length_mm'] if isinstance(r['length_mm'], (int, float)) else r['length_mm']
        lines.append('| ' + ' | '.join(str(x).replace('|', '/') for x in (r['id'], r['frm'], r['to'], r['net'] or '', r['gauge'], r['colour'], length, r['part'], r['notes'])) + ' |')
    return '\n'.join(lines) + '\n'


def write_tables(table):
    out = io.StringIO(newline='')
    w = csv.writer(out, lineterminator='\n')
    w.writerow(['id', 'from', 'to', 'signal', 'gauge_awg', 'colour', 'length_mm', 'connector_and_pin', 'notes'])
    for r in table:
        length = '%g' % r['length_mm'] if isinstance(r['length_mm'], (int, float)) else r['length_mm']
        w.writerow([r['id'], r['frm'], r['to'], r['net'] or '', r['gauge'], r['colour'], length, r['part'], r['notes']])
    cm.write_text('harness_wiring.csv', out.getvalue(), encoding='utf-8')
    cm.write_text('harness_wiring.md', markdown(table), encoding='utf-8')


def connector_records(table):
    """Assembly connector metadata. Pin payload always comes from wiring rows."""
    cavities = {'J3': '123', 'J4': '1234', 'SM-T': '1234', 'SM-W': '1234', 'X1': '123', 'FSR': '12', 'SW': '12'}
    ct = ('could-not-tell: identify position 1 from the moulded mark on the part in hand and the '
          'manufacturer drawing named here; do not infer it from the latch, key, or wire colours')
    return [
        dict(id='J3', part='Phoenix MKDS 1,5/3-5.08', positions=len(cavities['J3']), half='board screw terminal; builder inserts stripped trunk wires',
             feature=ct, source='KiCad footprint pad 1 and design.py J3 pin list; Phoenix MKDS 1,5/3-5.08 drawing must locate the physical cavity'),
        dict(id='J4', part='JST B4B-XH-A / XHP-4', positions=len(cavities['J4']), half='builder populates the XHP-4 cable housing',
             feature=ct, source='KiCad footprint pad 1 and design.py J4 pin list; JST XHP-4 drawing must locate the housing cavity'),
        dict(id='SM-T', part='JST SMP-04V-BC', positions=len(cavities['SM-T']), half='trunk half at the wrist; builder populates this plug',
             feature=ct, source='sourcing.py identifies SMP-04V-BC; JST SM connector drawing must locate the cavity'),
        dict(id='SM-W', part='JST SMR-04V-B', positions=len(cavities['SM-W']), half='wrist pigtail half; builder populates this receptacle',
             feature=ct, source='sourcing.py identifies SMR-04V-B; JST SM connector drawing must locate the cavity', reverse_base=True),
        dict(id='X1', part='Adafruit 972 male servo-extension plug', positions=len(cavities['X1']), half='builder retains and splices the male-plug pigtail',
             feature=ct, source='sourcing.py identifies lead 972; its product/manufacturer drawing must locate the cavity'),
        dict(id='FSR', part='Amphenol 65801-002LF Clincher', positions=len(cavities['FSR']), half='builder terminates the female Clincher onto H16/H17',
             feature=ct, source='sourcing.py identifies 65801-002LF; Amphenol 65801 drawing must locate position 1'),
        dict(id='SW', part='Omron D2F-01L', positions=len(cavities['SW']), half='builder solders the NO and COM terminals',
             feature='terminal mould marks NO and COM; position 1 in this note means NO', source='design.py pin list (LIM_SIG to NO, GND to COM); D2F-01L terminal names are moulded on the case'),
    ]


def connector_pins(table):
    byid = {r['id']: r for r in table}
    specs = {
        'J3': [('H01', 'frm'), ('H02', 'frm'), ('H03', 'frm')],
        'J4': [('H12', 'frm'), ('H13', 'frm'), ('H14', 'frm'), ('H15', 'frm')],
        'SM-T': [('H12', 'to'), ('H13', 'to'), ('H14', 'to'), ('H15', 'to')],
        'SM-W': [('H16', 'frm'), ('H17', 'frm'), ('H18', 'frm'), ('H19', 'frm')],
        'X1': [('H04', 'to'), ('H05', 'to'), ('H06', 'to')],
        'FSR': [('H16', 'to'), ('H17', 'to')],
        'SW': [('H18', 'to'), ('H19', 'to')],
    }
    nets = {'H01': 'GND', 'H02': 'SERVO_V', 'H03': 'SERVO_PWM', 'H04': 'GND', 'H05': 'SERVO_V', 'H06': 'SERVO_PWM',
            'H12': '+3V3', 'H13': 'FSR_SIG', 'H14': 'LIM_SIG', 'H15': 'GND', 'H16': '+3V3', 'H17': 'FSR_SIG',
            'H18': 'LIM_SIG', 'H19': 'GND'}
    out = {}
    for cid, items in specs.items():
        out[cid] = [dict(position=i + 1, contact=byid[rid][end], signal=nets[rid], colour=byid[rid]['colour'], row=rid)
                    for i, (rid, end) in enumerate(items)]
    return out


def connector_views(table):
    pins = connector_pins(table)
    records = {r['id']: r for r in connector_records(table)}
    views = {}
    for cid, ps in pins.items():
        wire = list(reversed(ps)) if records[cid].get('reverse_base') else list(ps)
        views[cid] = {'wire-entry': wire, 'mating-face': list(reversed(wire))}
    return views


def _pin(text):
    """Split 'J3.1' into ('J3', 1)."""
    name, position = text.split('.')
    return name, int(position)


def continuity_rows(table):
    p = connector_pins(table)
    routes = [
        ('GND servo', 'J3.1', 'X1.1', 'under 1 ohm'),
        ('SERVO_V', 'J3.2', 'X1.2', 'under 1 ohm'),
        ('SERVO_PWM', 'J3.3', 'X1.3', 'under 1 ohm'),
        ('+3V3', 'J4.1', 'FSR.1', 'under 1 ohm'),
        ('FSR_SIG', 'J4.2', 'FSR.2', 'under 1 ohm'),
        ('LIM_SIG', 'J4.3', 'SW.1', 'under 1 ohm'),
        ('GND sensor', 'J4.4', 'SW.2', 'under 1 ohm'),
        ('FSR element', 'FSR.1', 'FSR.2', 'not a short: open unloaded, finite resistance when pressed'),
    ]
    routes = [(signal, *_pin(start), *_pin(end), expected) for signal, start, end, expected in routes]
    continuity = [dict(signal=s, start='%s.%d' % (a, ap), end='%s.%d' % (b, bp), expected=e) for s, a, ap, b, bp, e in routes]
    isolation = []
    route_lookup = {(a, ap): (b, bp) for _, a, ap, b, bp, _ in routes[:-1]}
    route_lookup.update({(b, bp): (a, ap) for _, a, ap, b, bp, _ in routes[:-1]})
    for pos in range(1, 5):
        route_lookup[('SM-T', pos)] = ('SM-W', pos)
        route_lookup[('SM-W', pos)] = ('SM-T', pos)
    for cid, ps in p.items():
        for pos in range(1, len(ps)):
            for probe, neighbor in ((pos, pos + 1), (pos + 1, pos)):
                remote = route_lookup.get((cid, neighbor))
                if remote:
                    isolation.append(dict(connector=cid, adjacent='%d-%d' % (pos, pos + 1), start='%s.%d' % (cid, probe),
                                          end='%s.%d' % remote, expected='open'))
    return continuity, isolation


def single_swap_rows(table):
    """Enumerate all 21 swaps of the seven board conductors and what the written test detects."""
    conductors = [('J3.1', 'GND servo'), ('J3.2', 'SERVO_V'), ('J3.3', 'SERVO_PWM'),
                  ('J4.1', '+3V3'), ('J4.2', 'FSR_SIG'), ('J4.3', 'LIM_SIG'), ('J4.4', 'GND sensor')]
    out = []
    for index, (left, left_name) in enumerate(conductors):
        for right, right_name in conductors[index + 1:]:
            ground_pair = {left, right} == {'J3.1', 'J4.4'}
            out.append({'first': left, 'second': right, 'signals': left_name + ' / ' + right_name,
                        'detected': not ground_pair,
                        'physical_check': 'trace conductor end to end; confirm colour and gauge' if ground_pair else 'continuity procedure'})
    return out


def wrong_build_results(table):
    """Return the diagnostic rows failed by three physical mis-populations."""
    pins = connector_pins(table)
    count = len(pins['J4'])
    mirrored = {pin: count + 1 - pin for pin in range(1, count + 1)}
    shifted = {pin: pin % count + 1 for pin in range(1, count + 1)}
    cases = [('mirrored XHP-4', 'J4', mirrored),
             ('mirrored SM trunk half', 'SM-T', mirrored),
             ('one-position-shifted XHP-4', 'J4', shifted)]
    by_id = {r['id']: r for r in table}
    far = {x['position']: by_id[x['row']]['to'] for x in pins['SM-W']}
    results = []
    for name, cid, perm in cases:
        probe_cid = 'J4' if cid == 'SM-T' else cid
        signals = {x['position']: x['signal'] for x in pins[cid]}
        cont = ['%s.%d to %s' % (probe_cid, pin, far[pin]) for pin in perm if signals[perm[pin]] != signals[pin]]
        iso = []
        for pin, actual in perm.items():
            if abs(pin - actual) == 1 and signals[pin] != signals[actual]:
                iso.append('%s.%d to adjacent remote %s (expected open)' % (probe_cid, pin, far[actual]))
        assert cont and iso, '%s must fail continuity and adjacent isolation' % name
        results.append(dict(build=name, continuity_failures=cont, isolation_failures=iso))
    return results


def _view_block(record, sides):
    lines = ['### %s — %s' % (record['id'], record['part']), '', record['half'] + '.',
             'Position-1 reference: ' + record['feature'] + '.', 'Source: ' + record['source'] + '.']
    for key, label in (('wire-entry', 'viewed from the wire-entry side'), ('mating-face', 'viewed from the mating face')):
        lines += ['', label + ':', '```text', 'reference: ' + record['feature']]
        lines.append(' | '.join('[%d %s %s]' % (x['position'], x['signal'], x['colour']) for x in sides[key]))
        lines.append('```')
    return '\n'.join(lines)


def generated_guide(table):
    views = connector_views(table)
    orient = ['<!-- harness-orientation:start -->', '## Connector orientation views', '',
              'Numbers, signals, and colours below are generated from the wiring rows. Opposite sides are mirrored.']
    for rec in connector_records(table):
        orient += ['', _view_block(rec, views[rec['id']])]
    orient += ['', '### Team must confirm', '',
               '- J3: locate cavity 1 using the Phoenix MKDS 1,5/3-5.08 manufacturer drawing and the part in hand.',
               '- J4/XHP-4: locate cavity 1 using the JST XHP-4 drawing and moulded mark.',
               '- Both SM halves: locate cavity 1 independently using the JST SM drawings and moulded marks; do not transfer a latch-side rule between halves.',
               '- X1: locate contact 1 on the Adafruit 972 male plug from its drawing or continuity to its labelled conductors.',
               '- Clincher: locate position 1 using the Amphenol 65801 drawing and moulded mark.',
               '- Selected DSServo DS3230 MG lead gauge, length, colours, contact order, and mating orientation on the delivered servo.',
               '<!-- harness-orientation:end -->']
    cont, isolation = continuity_rows(table)
    checks = ['<!-- harness-checks:start -->', '## Continuity and isolation before first power', '',
              'Disconnect all power; unplug the servo and ESP32 module; mate the SM pair. Use a low-ohms meter.', '',
              '### End-to-end by signal', '', '| signal | from | to | expected |', '|---|---|---|---|']
    checks += ['| %s | %s | %s | %s |' % (x['signal'], x['start'], x['end'], x['expected']) for x in cont]
    checks += ['', '### Adjacent-position isolation', '',
               'Each probe below crosses to the far contact belonging to the adjacent position; this makes a swapped wire read continuity instead of open.', '',
               '| connector | adjacent positions | from | unintended far contact | expected |', '|---|---|---|---|---|']
    checks += ['| %s | %s | %s | %s | %s |' % (x['connector'], x['adjacent'], x['start'], x['end'], x['expected']) for x in isolation]
    checks += ['', '### Required wrong-build challenge', '', '| wrong build | continuity rows that fail | isolation rows that fail |', '|---|---|---|']
    for x in wrong_build_results(table):
        checks.append('| %s | %s | %s |' % (x['build'], '; '.join(x['continuity_failures']), '; '.join(x['isolation_failures'])))
    swaps = single_swap_rows(table)
    checks += ['', '### Every single conductor swap', '', '| first | second | signals | detected | physical check |', '|---|---|---|---|---|']
    checks += ['| %s | %s | %s | %s | %s |' % (x['first'], x['second'], x['signals'], 'yes' if x['detected'] else 'NO', x['physical_check']) for x in swaps]
    checks += ['', 'The procedure detects 20 of 21 swaps. J3.1 servo ground exchanged with J4.4 sensor ground is electrically invisible; trace each conductor and confirm its colour and gauge.',
               '<!-- harness-checks:end -->']
    return '\n'.join(orient) + '\n', '\n'.join(checks) + '\n'


def write_guide(table):
    path = os.path.join(cm.REPO, 'ecad', 'gripper', 'HARNESS.md')
    with open(path, encoding='utf-8') as f:
        text = f.read()
    orientation, checks = generated_guide(table)
    wiring = '<!-- harness-wiring:start -->\n' + markdown(table) + '<!-- harness-wiring:end -->\n'
    if '<!-- harness-wiring:start -->' in text:
        text = re.sub(r'<!-- harness-wiring:start -->.*?<!-- harness-wiring:end -->\n', wiring, text, flags=re.S)
    else:
        text = re.sub(r'(Lead-in names:.*?\n\n).*?(?=### Limit switch)', r'\1' + wiring + '\n', text, flags=re.S)
    if '<!-- harness-orientation:start -->' in text:
        text = re.sub(r'<!-- harness-orientation:start -->.*?<!-- harness-orientation:end -->\n', orientation, text, flags=re.S)
    else:
        text = text.replace('## Assembly order', orientation + '\n## Assembly order')
    if '<!-- harness-checks:start -->' in text:
        text = re.sub(r'<!-- harness-checks:start -->.*?<!-- harness-checks:end -->\n?', checks, text, flags=re.S)
    else:
        text = re.sub(r'## Continuity checks before first power-on.*\Z', checks, text, flags=re.S)
    if cm.OUT != os.path.join(cm.HERE, 'out'):
        if text != open(path, encoding='utf-8').read():
            raise AssertionError('ecad/gripper/HARNESS.md is stale; run harness.py')
        return text
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    return text


def run():
    table = rows()
    check_nets(table)
    jmin = jaw_min_deg()
    sb20, sb26 = servo_budget(v('harness_awg_power')), servo_budget(v('harness_awg_signal'))
    sig = signal_drops()
    tot = totals(table)
    fl = flex(jmin)
    write_tables(table)
    write_guide(table)
    return {'table': table, 'parts': [{'item': h['item'], 'qty': h['qty'], 'mpn': h['mpn']} for h in sourcing.HARNESS],
            'servo_20awg': sb20, 'servo_26awg': sb26, 'signal': sig, 'totals': tot, 'flex': fl,
            'buck_design_assumed_r_lead_ohm': bd.R_LEAD,
            'limit_switch': {'contact': 'COM + NO; physical terminal order could-not-tell without a quoted manufacturer drawing', 'physical_order': 'could-not-tell',
                             'firmware': 'config.h PIN_LIMIT_OPEN: switch to GND with INPUT_PULLUP; events.h EV_LIMIT_HIT: switch closed; fsm.cpp limitClosed',
                             'fail_safe': 'a broken wire reads as not at the open limit, never as at the limit',
                             'contact_load_mA': sig['i_lim_mA']},
            'assumptions': ['trunk length %.0f mm' % cable_mm(), 'pigtail %.0f mm %d AWG' % (v('harness_pigtail_mm'), v('harness_awg_pigtail')),
                            'FSR run %.0f mm' % v('harness_fsr_run_mm'), 'limit run %.0f mm' % v('harness_limit_run_mm'),
                            'PWM wire current %.0f mA' % (v('harness_pwm_current_a') * 1e3),
                            'design life %.0f grips' % v('harness_design_life_cycles')]}


def report(r):
    band, rating, v_min = v('harness_plug_band_v'), v('harness_plug_rating_v'), v('harness_servo_v_min')
    spare = v('harness_spare_fraction')
    pigtail_mm = v('harness_pigtail_mm')
    adc_step_mv = adc_lsb_mv()
    print('Harness of the gripper controller: board to wrist')
    print('Tags: [S] sourced, [D] derived here, [A] assumed')
    print('Trunk length %.0f mm [A, measure at assembly]; 20 AWG %.5f ohm/m, 26 AWG %.4f ohm/m, 22 AWG %.5f ohm/m [S constants.py]' % (
        cable_mm(), awg_ohm_m(v('harness_awg_power')), awg_ohm_m(v('harness_awg_signal')),
        awg_ohm_m(v('harness_awg_pigtail'))))
    print('\n(a) Wiring table (also out/harness_wiring.md and out/harness_wiring.csv)')
    print(cm.table([[x['id'], x['frm'], x['to'], x['net'] or '', x['gauge'], x['colour'],
                     '%g' % x['length_mm'] if isinstance(x['length_mm'], (int, float)) else x['length_mm']] for x in r['table']],
                   ['id', 'from', 'to', 'net', 'AWG', 'colour', 'length mm']))
    print('\n(b) Servo power pair: resistance and drop (power_budget.py currents; setpoint low/nom/high %.3f/%.3f/%.3f V; plug band %.2f to %.2f V, rating %.1f V)' % (
        tuple(bd.setpoint_range()) + band + (rating,)))
    for key in ('servo_20awg', 'servo_26awg'):
        s = r[key]
        print('%d AWG trunk to X1: pair %.1f mohm [D] + pigtail pair %.1f mohm [D, A gauge] = %.1f mohm loop (buck_design.py assumed lead %.0f mohm)' % (
            s['awg'], s['r_trunk_pair_ohm'] * 1e3, s['r_pigtail_pair_ohm'] * 1e3, s['r_total_ohm'] * 1e3, r['buck_design_assumed_r_lead_ohm'] * 1e3))
        print(cm.table([[c['fit'], c['scenario'], '%.2f' % c['i_A'], '%.3f' % c['trunk_pair_drop_V'], '%.3f' % c['total_drop_V'],
                         '%.3f' % c['plug_low_V'], '%.3f' % c['plug_nom_V'], '%.3f' % c['plug_high_V'], 'yes' if c['nom_in_band'] else 'NO', 'yes' if c['in_band'] else 'NO', 'yes' if c['below_rating'] else 'NO']
                        for c in s['cases']],
                       ['fit', 'case', 'servo A', 'trunk drop V', 'total drop V', 'plug low V', 'plug nom V', 'plug high V', 'nom in band', 'corners in band', '<= %.1f V' % rating]))
    print('Budget = nominal plug voltage at hold inside %.2f to %.2f V, and every case between %.1f and %.1f V (the band is a hold-torque calibration band; stall is judged against %.1f V only) [D].' % (
        band + (v_min, rating, v_min)))
    print('20 AWG power pair %s the budget; a 26 AWG pair %s [D].' % ('MEETS' if r['servo_20awg']['budget_ok'] else 'MISSES', 'MEETS' if r['servo_26awg']['budget_ok'] else 'MISSES'))
    s20 = r['servo_20awg']
    print('Corner finding: at the low set point and Fit A hold the plug is %+.0f mV against the %.2f V band edge; the loop would have to be at most %.0f mohm (is %.1f) [D]. '
          'The pigtail is %.1f mohm of it; the unknown selected-servo lead is excluded.' % (s20['corner_margin_mV'], band[0], s20['r_max_corner_ohm'] * 1e3, s20['r_total_ohm'] * 1e3,
                                                                                           s20['r_pigtail_pair_ohm'] * 1e3))
    sg = r['signal']
    print('\n(c) Signal conductors, 26 AWG, %.0f mm each (one conductor, worst case)' % cable_mm())
    print(cm.table([[c['id'], c['signal'], '%.2f' % (c['current_A'] * 1e3), '%.1f' % (c['r_ohm'] * 1e3), '%.4f' % c['drop_mV'], '%.4f' % c['drop_lsb']] for c in sg['conductors']],
                   ['id', 'signal', 'current mA', 'resistance mohm', 'drop mV', 'drop in ADC LSBs (%.3f mV)' % adc_step_mv]))
    print('FSR current %.2f mA at the %.0f N cap [D]; PWM wire current %.1f mA [A]; limit current %.2f mA [D].' % (sg['i_fsr_mA'], v('harness_fsr_force_cap_n'), v('harness_pwm_current_a') * 1e3, sg['i_lim_mA']))
    print('FSR force error from the two series wires (%.0f mohm added) [D]:' % (sg['fsr_error'][0]['extra_r_ohm'] * 1e3))
    print(cm.table([['%.0f' % e['force_N'], '%.3f' % e['read_N'], '%+.4f' % e['err_N']] for e in sg['fsr_error']], ['true force N', 'reads N', 'error N']))
    print('Limit switch closed: LIM_SIG sits %.3f mV above the sensor GND at the board [D]; ESP32 input-low threshold %.0f mV [A].' % (sg['limit_low_mV'], sg['limit_vil_mV']))
    print('Limit switch contact: COM + NO. Firmware wants the pin pulled to GND when the jaw is open (config.h PIN_LIMIT_OPEN, events.h EV_LIMIT_HIT); '
          'NO closes only when the lever is pressed, so a cut wire reads as not at the limit. Contact load %.2f mA at %.1f V [D]; check against the D2F-01L datasheet minimum load [A, not read].' % (
              r['limit_switch']['contact_load_mA'], v('power_3v3_rail_v')))
    t = r['totals']
    print('\n(d) Wire to buy (cut from spool, %d %% spare added)' % (spare * 100))
    print(cm.table([[b['gauge_awg'], b['colour'], '%g' % b['length_mm'], '%.0f' % b['with_spare_mm']] for b in t['by_gauge_colour']], ['AWG', 'colour', 'cut length mm', 'buy mm (with spare)']))
    for g in sorted(t['by_gauge_mm']):
        print('Total %s AWG: %.0f mm cut, %.0f mm with spare [D].' % (g, t['by_gauge_mm'][g], t['by_gauge_with_spare_mm'][g]))
    print('Spools: 26 AWG 2 m spool per colour (sourcing.HARNESS), five colours; 20 AWG red and black %.0f mm each with spare. Bought leads: servo extension lead (cut to %.0f mm pigtail), braided sleeve %.0f mm with spare.' % (
        cable_mm() * (1 + spare), pigtail_mm, cable_mm() * (1 + spare)))
    f = r['flex']
    print('\n(e) Flex')
    print('26 AWG silicone OD %.1f mm [S]; minimum dynamic bend radius %.0f x OD = %.1f mm (absolute minimum %.0f x = %.1f mm) [S, D]; a service loop needs a diameter of at least %.0f mm.' % (
        f['od_mm'], v('harness_bend_factor'), f['min_radius_mm'], v('harness_bend_factor_abs'), f['abs_min_radius_mm'], f['min_loop_diameter_mm']))
    print('Jaw travel %.1f deg (%.1f to %+.1f deg, config.h JAW_MIN_DEG and DESIGN-BASIS R18); slack the lead must absorb at that radius: %.1f mm [D].' % (
        f['jaw_travel_deg'], f['jaw_min_deg'], f['jaw_max_deg'], f['slack_for_travel_mm']))
    print('Flex cycles to survive [A]: %.0f = %.1f cycles/h x %.0f h; basis: %s.' % (f['design_cycles'], f['cycles_per_hour'], f['hours_for_design_life'], f['basis']))
    print('One semester is about %.0f cycles (%.0f h) [A]; inspect every %.0f cycles.' % (f['cycles_per_semester'], f['hours_per_semester'], f['inspect_every_cycles']))


def main():
    res = run()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        report(res)
    text = buf.getvalue()
    sys.stdout.write(text)
    cm.write_text('harness.txt', text, encoding='utf-8')
    cm.write_json('harness', res)
    print('wrote harness.json, harness.txt, harness_wiring.csv, harness_wiring.md in ecad/gripper/calc/out')


if __name__ == '__main__':
    main()
