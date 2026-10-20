"""Power budget of the gripper controller board: loads, input current, rail voltage at the servo, dissipation,
the ESP32 supply chain, the FSR reading error from the 3.3 V rail and ground, and the bulk capacitor.

Run from the repository root:  python ecad/gripper/calc/power_budget.py

Jargon.
  Fit A / Fit B: the two electrical fits of the DS3218MG servo in docs/gripper/analysis/dyno.md (Fit A R 1.80 ohm,
    stall 3.77 A; Fit B R 3.09 ohm, stall 2.2 A, both at 6.8 V). At stall the servo is a resistor R; at hold it draws
    a fixed current (A 1.35 A, B 0.80 A). Idle is the 5 mA datasheet figure.
  Set point: the SERVO_V regulation voltage, 6.584 V nominal; Vref tolerance and 0.1 % resistors give 6.507 to 6.662 V.
  Plug: the servo terminals after the 1.2 m cable and a 30 mohm lead (R_cable + R_lead are printed).
  BOD: ESP32 brown-out detector. Regen: energy returned to the rail when the servo is driven backwards by the load.
Tags: [S] constants.py, [D] derived here, [A] assumed (stated in constants.py or here).
"""
import math

import _common as cm
from formulas import capacitor_energy, round_up_half, switching_transition_loss
from _common import ELEC, FITS, v
import buck_design as bd
import droop_sim

def rs():
    return ELEC['r_shunt_ohm']
def r_in():
    return v('f1_r1max') + v('q1_rds')        # F1 worst case + Q1 [S]
def r_cable_26():
    return 2 * ELEC['cable_len_m'] * v('awg26_ohm_m')
def i_5v():
    return {   # current on the +5V rail (MCP1703A output, through D7 to the DevKitC 5V pin) [A/S]
    'esp32 board, no Wi-Fi': v('esp_i_active_nowifi') + v('devkit_overhead_a') + v('power_external_3v3_load_a') + v('ibus_5v_idle'),
    'esp32 board, Wi-Fi receive': v('esp_i_wifi_rx') + v('devkit_overhead_a') + v('power_external_3v3_load_a') + v('ibus_5v_idle'),
    'esp32 board, Wi-Fi transmit peak': v('esp_i_wifi_tx_peak') + v('devkit_overhead_a') + v('power_external_3v3_load_a') + v('ibus_5v_idle'),
}
def i5_typ():
    return i_5v()['esp32 board, no Wi-Fi']
def i3v3_ext():
    return v('power_external_3v3_load_a')
def idle_a():
    return v('servo_idle_a')


def servo_current(fit, scenario, vset, r_wire):
    """Servo current for a scenario: idle 5 mA, hold (fixed per fit), stall (resistor R through the wire)."""
    f = FITS[fit]
    if scenario == 'idle':
        return idle_a()
    if scenario == 'hold':
        return f['hold_A']
    return vset / (f['R'] + r_wire)


def buck_losses(vin, i_l, vo):
    """Losses of U1, D2, L1 at inductor current i_l (W) [D]; dict by part."""
    d = vo / vin
    p_hs = i_l ** 2 * v('tps_rds_typ') * d
    p_sw = switching_transition_loss(
        vin, i_l, v('power_switch_transition_time_s'), bd.fsw_from_rt(ELEC['r_rt_ohm']))
    p_q = vin * v('tps_iq')
    p_d2 = v('d2_vf') * i_l * (1 - d)
    p_l1 = i_l ** 2 * v('l1_dcr')
    return {'U1_cond': p_hs, 'U1_switch': p_sw, 'U1_iq': p_q, 'D2': p_d2, 'L1': p_l1}


def input_point(vin_adapter, i_servo, i5=i5_typ(), vset=None):
    """Solve the input current at a given adapter voltage by fixed-point iteration. Returns dict."""
    vset = bd.vset() if vset is None else vset
    vo = vset + rs() * i_servo
    p_out = vo * (i_servo + i5)
    iin = p_out / vin_adapter / v('power_starting_efficiency')
    for _ in range(40):
        vu = vin_adapter - iin * r_in()
        loss = buck_losses(vu, i_servo + i5, vo)
        p_in = p_out + sum(loss.values())
        iin = p_in / vu
    vu = vin_adapter - iin * r_in()
    return {'iin_A': iin, 'pin_W': iin * vin_adapter, 'pout_W': p_out, 'eff': p_out / p_in, 'vu_V': vu, 'loss': loss,
            'p_f1_W': iin ** 2 * v('f1_r1max'), 'p_q1_W': iin ** 2 * v('q1_rds'), 'v_buck_V': vo}


def vd7(i):
    return v('d7_vf_100ma') + v('d7_vf_slope') * math.log10(max(i, v('power_log_current_floor_a')) / v('power_diode_reference_current_a'))


def ldo_dropout(i5):
    """MCP1703A dropout at load i5 (worst case): proportional to load up to its rated current, then capped."""
    return v('mcp_dropout_max') * min(i5 / v('mcp_iout_max'), v('power_ldo_dropout_scale_cap'))


def ldo_min_input_V():
    """Lowest +5 V rail input that keeps the MCP1703A in regulation in every ESP32 load case (worst dropout).
    Reads constants only, so droop_sim.py can use it without running this module."""
    return v('power_five_volt_rail_v') + max(ldo_dropout(i5) for i5 in i_5v().values())


def ldo_ams(i3, worst=True):
    d = v('ams_dropout_max') if worst else v('ams_dropout_typ')
    base = 1 / v('power_ldo_full_load_dropout_ratio') * d
    return base + (d - base) * max(0, (i3 - v('power_ldo_light_load_a'))) / v('power_ldo_load_span_a')


def fsr_force_from_mv(mv):
    r = ELEC['r_fsr_fixed_ohm'] * (v('fsr_default_vcc_mv') / mv - 1)
    return (r / v('fsr_fit_r1n_ohm')) ** (-1 / v('fsr_fit_exponent'))


def fsr_reading(force, vcc_mv=None, dvg_mv=None):
    """Force the firmware would report when the real rail is vcc_mv and the ADC ground is dvg_mv away [D]."""
    vcc_mv = v('fsr_default_vcc_mv') if vcc_mv is None else vcc_mv
    dvg_mv = 0 if dvg_mv is None else dvg_mv
    mv = cm.node_mv(force, vcc_mv=vcc_mv) + dvg_mv
    return fsr_force_from_mv(mv)


def run():
    r = {}
    ds = droop_sim.run()
    r_cable = bd.cable_resistance()
    r_wire = r_cable + bd.R_LEAD
    lo, nom, hi = bd.setpoint_range()
    # (a) load table
    r['loads'] = [
        ['DS3218MG servo, Fit A', '4.8 to 6.8', '%.3f idle / %.2f hold' % (idle_a(), FITS['A']['hold_A']), '%.2f at 6.8 V' % FITS['A']['stall_A'], '%.2f' % FITS['A']['stall_A']],
        ['DS3218MG servo, Fit B', '4.8 to 6.8', '%.3f idle / %.2f hold' % (idle_a(), FITS['B']['hold_A']), '%.2f at 6.8 V' % FITS['B']['stall_A'], '%.2f' % FITS['B']['stall_A']],
        ['ESP32 + DevKitC on +5V, no Wi-Fi', '4.5 to 5.5', '%.3f' % i_5v()['esp32 board, no Wi-Fi'], '%.3f (Wi-Fi TX peak)' % i_5v()['esp32 board, Wi-Fi transmit peak'], '-'],
        ['74AHCT1G125 + R12 on +5V', '4.5 to 5.5', '0.001', '0.001', '-'],
        ['INA219, LED, FSR divider, pull-ups on +3V3', '3.0 to 3.6', '%.3f' % i3v3_ext(), '%.3f' % i3v3_ext(), '-'],
        ['TPS54560B quiescent', '4.5 to 60', '%.4f' % v('tps_iq'), '%.4f' % v('tps_iq'), '-'],
    ]
    # (b) input power
    rows = []
    worst = {'iin': 0}
    for vin in (v('buck_input_min_v'), v('buck_nominal_input_v'), v('buck_input_max_v')):
        for fit in ('A', 'B'):
            for sc in ('idle', 'hold', 'stall'):
                i = servo_current(fit, sc, hi if sc == 'stall' else nom, r_wire)
                pt = input_point(vin, i)
                rows.append({'vin': vin, 'fit': fit, 'scenario': sc, 'i_servo': i, **{k: pt[k] for k in ('iin_A', 'pin_W', 'pout_W', 'eff')},
                             'f1_margin_A': v('f1_hold') - pt['iin_A']})
                if pt['iin_A'] > worst['iin']:
                    worst = {'iin': pt['iin_A'], 'vin': vin, 'fit': fit, 'sc': sc, 'pin': pt['pin_W']}
    r['input'] = rows
    r['worst_input'] = worst
    nom12 = [x for x in rows if x['vin'] == v('buck_nominal_input_v') and x['scenario'] == 'stall' and x['fit'] == 'A'][0]
    r['adapter'] = {'worst_input_A': worst['iin'], 'worst_input_W': worst['pin'], 'nominal_12V_stall_A_A': nom12['iin_A'],
                    'rating_with_25pct_margin_A': v('power_rating_margin_factor') * worst['iin'], 'rating_W_at_12V': v('power_rating_margin_factor') * worst['iin'] * v('buck_nominal_input_v'),
                    'sustained_hold_A': max(x['iin_A'] for x in rows if x['scenario'] == 'hold'),
                    'recommended': '12 V, %.1f A (%.0f W) minimum for a sustained Fit A stall; 12 V 2 A would carry hold and any Fit B case' % (
                        round_up_half(v('power_rating_margin_factor') * worst['iin'], math.ceil),
                        v('buck_nominal_input_v') * round_up_half(
                            v('power_rating_margin_factor') * worst['iin'], math.ceil))}
    r['adapter']['hold_rating_A'] = v('power_rating_margin_factor') * r['adapter']['sustained_hold_A']
    # (c) servo plug voltage
    pv = []
    for awg, rc in zip(v('wire_gauges_awg'), (r_cable, r_cable_26())):
        rw = rc + bd.R_LEAD
        for fit in ('A', 'B'):
            for sc in ('idle', 'hold', 'stall'):
                vals = {}
                for lab, vs in (('low', lo), ('nom', nom), ('high', hi)):
                    i = servo_current(fit, sc, vs, rw)
                    vals[lab] = vs - i * rw
                i_nom = servo_current(fit, sc, nom, rw)
                pv.append({'awg': awg, 'R_cable_ohm': rc, 'fit': fit, 'scenario': sc, 'i_A': i_nom, **vals,
                           'in_band': vals['low'] >= v('harness_plug_band_v')[0] and vals['high'] <= v('harness_plug_band_v')[1], 'below_rating': vals['high'] <= v('servo_vmax')})
    r['plug'] = pv
    r['plug_cable'] = {'R_cable_20_ohm': r_cable, 'R_cable_26_ohm': r_cable_26(), 'R_lead_ohm': bd.R_LEAD, 'band': v('harness_plug_band_v'), 'rating_V': v('servo_vmax')}
    # (d) dissipation at 12 V and 13.2 V
    dis = []
    for vin in (v('buck_nominal_input_v'), v('buck_input_max_v')):
        for fit in ('A', 'B'):
            for sc in ('hold', 'stall'):
                i = servo_current(fit, sc, hi, r_wire)
                pt = input_point(vin, i, vset=hi)
                il = i + i5_typ()
                u3 = (pt['v_buck_V'] - v('power_five_volt_rail_v')) * i5_typ()
                dis.append({'vin': vin, 'fit': fit, 'scenario': sc, 'i_A': i, 'RS1_W': i ** 2 * rs(), 'RS1_pct_rating': 100 * i ** 2 * rs() / v('rs1_rating'),
                            'D2_W': pt['loss']['D2'], 'Q1_W': pt['p_q1_W'], 'F1_W': pt['p_f1_W'],
                            'U1_cond_W': pt['loss']['U1_cond'], 'U1_switch_W': pt['loss']['U1_switch'],
                            'U1_total_W': pt['loss']['U1_cond'] + pt['loss']['U1_switch'] + pt['loss']['U1_iq'],
                            'U1_rise_K': (pt['loss']['U1_cond'] + pt['loss']['U1_switch'] + pt['loss']['U1_iq']) * v('tps_rth_ja'),
                            'L1_W': pt['loss']['L1'], 'U3_W': u3, 'U3_rise_K': u3 * v('mcp_rth_sot223')})
    r['dissipation'] = dis
    # (e) ESP32 supply chain
    chain = []
    low_vbuck = min(ds['low_vin']['vbuck_min_V'], ds['low_vin_B']['vbuck_min_V'])
    for lab, i5 in i_5v().items():
        i3 = i5 - v('devkit_overhead_a') * 0 - v('ibus_5v_idle')
        # LDO output: tolerance low, or dropout-limited
        vdo = ldo_dropout(i5)
        v5_tol = v('power_five_volt_rail_v') * (1 - v('mcp_vout_tol'))
        v5 = min(v5_tol, low_vbuck - vdo)
        vd = vd7(i5)
        v5pin = v5 - vd
        vdo_a = ldo_ams(i3)
        v33_reg = v('power_3v3_rail_v') * (1 - v('ams_vout_tol'))
        v33 = min(v33_reg, v5pin - vdo_a)
        chain.append({'case': lab, 'v_buck_min_V': low_vbuck, 'i5_A': i5, 'ldo_dropout_V': vdo, 'v5_V': v5, 'd7_V': vd, 'v5pin_V': v5pin,
                      'ams_dropout_V': vdo_a, 'ams_headroom_V': v5pin - vdo_a - v33_reg, 'v33_V': v33, 'bod_V': v('esp_bod_default'),
                      'margin_bod_V': v33 - v('esp_bod_default'), 'margin_min_supply_V': v33 - v('esp_vdd_min_flash'),
                      'ldo_over_rating': i5 > v('mcp_iout_max')})
    r['esp_board_power'] = chain
    usb = []
    for vusb in (v('power_usb_min_v'), v('power_five_volt_rail_v'), v('power_usb_max_v')):
        i5 = i_5v()['esp32 board, no Wi-Fi']
        v5pin = vusb - v('devkit_diode_drop')
        vdo_a = ldo_ams(i5 - v('ibus_5v_idle'))
        v33 = min(v('power_3v3_rail_v') * (1 - v('ams_vout_tol')), v5pin - vdo_a)
        usb.append({'v_usb_V': vusb, 'v5pin_V': v5pin, 'ams_dropout_V': vdo_a, 'ams_headroom_V': v5pin - vdo_a - v('power_3v3_rail_v') * (1 - v('ams_vout_tol')),
                    'v33_V': v33, 'margin_bod_V': v33 - v('esp_bod_default')})
    r['esp_usb'] = usb
    r['esp_stall_vbuck_min'] = low_vbuck
    r['ldo_min_input_V'] = ldo_min_input_V()
    # (f) FSR reading error from rail and ground
    errs = []
    gnd = {'shared 20 AWG return, Fit A stall': v('power_fit_a_stall_current_a') * v('power_ground_wire_length_m') * v('awg20_ohm_m') * 1e3,
           'shared 20 AWG return, Fit A hold': FITS['A']['hold_A'] * v('power_ground_wire_length_m') * v('awg20_ohm_m') * 1e3,
           'separate 26 AWG FSR return (0.9 mA) + 5 mohm board plane at 3.45 A [A]': v('power_fsr_return_current_a') * v('power_ground_wire_length_m') * v('awg26_ohm_m') * 1e3 + v('power_fit_a_stall_current_a') * v('power_board_plane_resistance_ohm') * 1e3,
           }
    for force in (v('power_fsr_force_low_n'), v('power_fsr_force_high_n')):
        for lab, vcc in (('3V3 -1 %', v('power_3v3_minus_1pct_mv')), ('3V3 +1 %', v('power_3v3_plus_1pct_mv')), ('3V3 -3 %', v('power_3v3_minus_3pct_mv')), ('3V3 = 3.267 V (AMS1117 low, board power)', v('power_3v3_minus_1pct_mv'))):
            errs.append({'force_N': force, 'cause': lab, 'read_N': fsr_reading(force, vcc_mv=vcc), 'err_N': fsr_reading(force, vcc_mv=vcc) - force})
        for lab, dv in gnd.items():
            errs.append({'force_N': force, 'cause': 'ground offset %.1f mV: %s' % (dv, lab), 'read_N': fsr_reading(force, dvg_mv=dv),
                         'err_N': fsr_reading(force, dvg_mv=dv) - force})
    r['fsr_errors'] = errs
    r['ground_mv'] = gnd
    # (g) bulk capacitor
    base = [c for c in ds['cases'] if c['params']['fit'] == 'A' and abs(c['params']['rise'] - v('droop_fast_rise_s')) < cm.NUMERICS['ngspice_match_atol_s']][0]
    c_tot = ELEC['c_bulk_F'] + ELEC['c_wrist_F'] + ELEC['c_out_ceramic_F'] * v('cer_derate_6v6')
    regen = []
    for e_mj in (v('power_regen_min_mj'), v('power_regen_low_mj'), v('power_regen_basis_mj'), v('power_regen_high_mj'), v('power_regen_rotor_mj')):
        e = e_mj * 1e-3
        vend = math.sqrt(nom ** 2 + 2 * e / c_tot)
        regen.append({'energy_mJ': e_mj, 'v_peak_V': vend, 'rise_V': vend - nom, 'c_needed_for_6v8_uF': 2 * e / (v('servo_vmax') ** 2 - nom ** 2) * 1e6})
    r['bulk'] = {'stall_charge_uC': base['bulk_charge_C'] * 1e6, 'stall_energy_mJ': base['bulk_energy_J'] * 1e3, 'servo_v_dip_V': base['servo_v_pre_V'] - base['servo_v_min_V'],
                 'verdict': ds['verdict'], 'c_total_uF': c_tot * 1e6, 'regen': regen,
                 'regen_basis': 'assumed energy returned by a back-driven servo: 20 mJ = half of stall torque 2.1 N*m x 1 deg backlash (0.0175 rad) [A]; 174 mJ = whole reflected rotor kinetic energy 0.5 x 6.5e-3 kg*m2 x (7.31 rad/s)^2 [D from dyno.md]; '
                               'nothing in the board sinks energy (non-synchronous buck, diode D2), so the rail rises by the capacitors alone',
                 'e_max_to_6v8_mJ': capacitor_energy(
                     c_tot, v('servo_vmax') ** 2 - nom ** 2) * 1e3}
    return r


def report(r):
    print('Power budget of the gripper controller board')
    print('Tags: [S] constants.py, [D] derived here, [A] assumed')
    print('Wiring: R_cable (20 AWG, 1.2 m out and back) = %.1f mohm, 26 AWG = %.1f mohm, servo lead %.0f mohm [D, A]' % (
        r['plug_cable']['R_cable_20_ohm'] * 1e3, r['plug_cable']['R_cable_26_ohm'] * 1e3, r['plug_cable']['R_lead_ohm'] * 1e3))
    print('\n(a) Load table (A; stall is at 6.8 V for the servo, as in dyno.md)')
    print(cm.table(r['loads'], ['load', 'V range', 'typ A (idle / hold)', 'peak A', 'stall A']))
    print('\n(b) Input current and power at the adapter (U1 losses, F1 %.0f mohm worst, Q1 %.0f mohm worst, 10 ns switching transitions [A])' % (v('f1_r1max') * 1e3, v('q1_rds') * 1e3))
    print(cm.table([[x['vin'], x['fit'], x['scenario'], '%.3f' % x['i_servo'], '%.2f' % x['pout_W'], '%.2f' % x['pin_W'], '%.2f' % x['iin_A'], '%.0f %%' % (100 * x['eff']),
                     '%+.2f' % x['f1_margin_A']] for x in r['input']],
                   ['Vin V', 'fit', 'case', 'servo A', 'buck out W', 'input W', 'input A', 'efficiency', 'F1 margin A (2.6 hold)']))
    a = r['adapter']
    print('Worst input: %.2f A (%.1f W) at %.1f V, Fit %s %s. Adapter rating with 25 %% margin: %.2f A (%.0f W at 12 V). Sustained hold needs %.2f A with margin.' % (
        a['worst_input_A'], a['worst_input_W'], r['worst_input']['vin'], r['worst_input']['fit'], r['worst_input']['sc'], a['rating_with_25pct_margin_A'], a['rating_W_at_12V'], a['hold_rating_A']))
    print('Recommended: %s' % a['recommended'])
    print('F1 (hold 2.6 A at 23 C [S]) trips only above 5.0 A or after seconds above 2.6 A; a negative margin above means a stall longer than a few seconds can open F1.')
    print('\n(c) Voltage at the servo terminals (set point low / nom / high = %.3f / %.3f / %.3f V; band 6.35 to 6.65 V, rating 6.8 V)' % tuple(bd.setpoint_range()))
    print(cm.table([[x['awg'], x['fit'], x['scenario'], '%.2f' % x['i_A'], '%.3f' % x['low'], '%.3f' % x['nom'], '%.3f' % x['high'], 'yes' if x['in_band'] else 'NO',
                     'yes' if x['below_rating'] else 'NO'] for x in r['plug']],
                   ['AWG', 'fit', 'case', 'servo A', 'plug low V', 'plug nom V', 'plug high V', 'inside 6.35-6.65', '<= 6.8 V']))
    print('\n(d) Dissipation (set point high, ESP32 100 mA load on +5V)')
    print(cm.table([[x['vin'], x['fit'], x['scenario'], '%.2f' % x['i_A'], '%.2f (%.0f %%)' % (x['RS1_W'], x['RS1_pct_rating']), '%.2f' % x['D2_W'], '%.3f' % x['Q1_W'], '%.3f' % x['F1_W'],
                     '%.2f + %.2f' % (x['U1_cond_W'], x['U1_switch_W']), '%.0f' % x['U1_rise_K'], '%.3f' % x['L1_W'], '%.2f' % x['U3_W'], '%.0f' % x['U3_rise_K']] for x in r['dissipation']],
                   ['Vin V', 'fit', 'case', 'servo A', 'RS1 W (of 2 W)', 'D2 W', 'Q1 W', 'F1 W', 'U1 cond + switch W', 'U1 rise K (42 K/W)', 'L1 W', 'U3 W', 'U3 rise K (%.1f K/W)' % v('mcp_rth_sot223')]))
    print('\n(e) ESP32 supply chain with V_BUCK at its lowest in a stall (droop_sim.py, Vin 10.8 V): %.2f V' % r['esp_stall_vbuck_min'])
    print(cm.table([[x['case'], '%.3f' % x['i5_A'], '%.2f' % x['v5_V'], '%.2f' % x['d7_V'], '%.2f' % x['v5pin_V'], '%.2f' % x['ams_dropout_V'], '%+.2f' % x['ams_headroom_V'],
                     '%.3f' % x['v33_V'], '%+.2f' % x['margin_bod_V'], 'yes' if x['ldo_over_rating'] else 'no'] for x in r['esp_board_power']],
                   ['board power case', '+5V A', '+5V V (LDO -%.0f %%)' % (100 * v('mcp_vout_tol')), 'D7 drop V', 'DevKit 5V pin V', 'AMS1117 dropout V (max)', 'headroom to 3.267 V reg', '3V3 V', 'margin to BOD 2.43 V', '+5V load > 250 mA']))
    print('USB power (D7 reverse-biased, DevKitC diode drop %.2f V [A]):' % v('devkit_diode_drop'))
    print(cm.table([['%.2f' % x['v_usb_V'], '%.2f' % x['v5pin_V'], '%.2f' % x['ams_dropout_V'], '%+.2f' % x['ams_headroom_V'], '%.3f' % x['v33_V'], '%+.2f' % x['margin_bod_V']] for x in r['esp_usb']],
                   ['USB V', 'DevKit 5V pin V', 'AMS1117 dropout V (max)', 'headroom to 3.267 V reg', '3V3 V', 'margin to BOD 2.43 V']))
    print('\n(f) FSR force reading error: the ESP32 ADC is absolute, the firmware assumes 3300 mV')
    print(cm.table([[x['force_N'], x['cause'], '%.3f' % x['read_N'], '%+.3f' % x['err_N']] for x in r['fsr_errors']], ['true force N', 'cause', 'reads N', 'error N']))
    b = r['bulk']
    print('\n(g) Bulk capacitor (C12 %d uF + forearm %d uF + ceramic %.0f uF = %.0f uF total on the rail)' % (ELEC['c_bulk_F'] * 1e6, ELEC['c_wrist_F'] * 1e6, ELEC['c_out_ceramic_F'] * v('cer_derate_6v6') * 1e6, b['c_total_uF']))
    print('Stall step (Fit A, 10 us rise): the bulk capacitor delivers %.0f uC and %.2f mJ; SERVO_V dips %.2f V before the loop catches up (droop_sim.py).' % (b['stall_charge_uC'], b['stall_energy_mJ'], b['servo_v_dip_V']))
    vd = b['verdict']
    print('Verdict on 1000 uF for the stall step: %s (plug minimum 470 uF %.2f V, 1000 uF %.2f V, 2200 uF %.2f V).' % ('ADEQUATE' if vd['adequate'] else 'NOT ADEQUATE', vd['plug_min_470_V'], vd['plug_min_1000_V'], vd['plug_min_2200_V']))
    print('Regen onto the rail. Basis: %s.' % b['regen_basis'])
    print(cm.table([['%.0f' % x['energy_mJ'], '%.2f' % x['v_peak_V'], '%+.2f' % x['rise_V'], '%.0f' % x['c_needed_for_6v8_uF']] for x in b['regen']],
                   ['energy mJ', 'rail peak V', 'rise V', 'capacitance to stay <= 6.8 V uF']))
    print('Energy the present capacitance absorbs before the rail reaches 6.8 V: %.1f mJ. Any larger regen needs a clamp or a sink; capacitance alone is not the answer.' % b['e_max_to_6v8_mJ'])


if __name__ == '__main__':
    report(run())
