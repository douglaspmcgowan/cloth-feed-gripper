"""FSR front end: the divider, the fixed resistor for each force cap, resolution, and the anti-alias filter.

Run from the repository root:  python ecad/gripper/calc/fsr_frontend.py

Jargon.
  Divider: 3V3 - FSR - node - R15 - GND; the node voltage is 3300 mV x R15 / (R15 + R_fsr).
  Power-law fit: R_fsr = 6109 ohm x F^-0.8195 (firmware config.h FSR_FIT_R1N_OHM, FSR_FIT_EXP; fitted to the Adafruit 166 table).
  ADC span: the ESP32 ADC at 11 dB attenuation reads linearly from 150 to 2450 mV [S]; total error +/-60 mV after calibration [S].
  Anti-alias filter: R16 10 kohm and C17 100 nF; its source resistance includes the divider's Thevenin resistance R15 || R_fsr.
  EMA: the firmware's exponential moving average, alpha 0.10 at 1 kHz, tau = -1/(fs ln(1 - alpha)).
Tags: [S] sourced, [D] derived here, [A] assumed.
"""
import math

import _common as cm
from _common import ELEC, v
import formulas


def e96(lo, hi):
    """E96 values between lo and hi (3 significant figures of 10^(k/96); a few standard values differ in the last digit)."""
    out = []
    for k in range(96):
        for decade in range(2, 5):
            val = formulas.e96_value(k, decade, round)
            if lo <= val <= hi:
                out.append(val)
    return sorted(set(out))


def r_for_node(force, v_target_mv, vcc=None):
    """Fixed resistor that puts the node at v_target_mv for a force."""
    vcc = v('fsr_default_vcc_mv') if vcc is None else vcc
    rf = cm.fsr_r(force)
    return rf * v_target_mv / (vcc - v_target_mv)


def best_resistor(cap, v_top=None):
    """(exact ohm, largest E96 value that keeps node(cap) <= v_top)."""
    v_top = v('esp_adc_max_mv') if v_top is None else v_top
    exact = r_for_node(cap, v_top)
    std = [x for x in e96(v('fsr_e96_search_lo_ohm'), v('fsr_e96_search_hi_ohm'))
           if x <= exact + cm.NUMERICS['e96_select_tolerance_ohm']]
    return exact, (max(std) if std else float('nan'))


def n_per_mv(force, r_fixed):
    """Resolution: newtons per millivolt at a force (central difference) [D]."""
    h = force * cm.NUMERICS['fsr_resolution_step_fraction']
    dv = cm.node_mv(force + h, r_fixed) - cm.node_mv(force - h, r_fixed)
    return 2 * h / dv


def thevenin(force, r_fixed=None):
    r = ELEC['r_fsr_fixed_ohm'] if r_fixed is None else r_fixed
    rf = cm.fsr_r(force)
    return r * rf / (r + rf)


def filter_point(force, r_fixed=None):
    rth = thevenin(force, r_fixed) if force else 0.0
    rtot = ELEC['r_aa_ohm'] + rth
    c = ELEC['c_aa_F']
    fc = 1 / (2 * math.pi * rtot * c)
    return {'force_N': force, 'r_source_ohm': rth, 'fc_Hz': fc, 'tau_s': rtot * c,
            **{'atten_%dHz' % f: 1 / math.sqrt(1 + (f / fc) ** 2) for f in v('fsr_filter_gain_freqs_hz')}}


def run():
    r = {}
    r['fit'] = {'R1N_ohm': v('fsr_fit_r1n_ohm'), 'exp': v('fsr_fit_exponent')}
    forces = v('fsr_table_forces_n')
    adc_min, adc_max = v('esp_adc_min_mv'), v('esp_adc_max_mv')
    r['table'] = [{'force_N': f, 'r_fsr_ohm': cm.fsr_r(f), 'node_mV': cm.node_mv(f), 'in_span': adc_min <= cm.node_mv(f) <= adc_max,
                   'n_per_mV': n_per_mv(f, ELEC['r_fsr_fixed_ohm'])} for f in forces]
    cands = {}
    for cap in v('ina_force_caps_n'):
        exact, std = best_resistor(cap)
        exact_g, std_g = best_resistor(cap, adc_max - v('esp_adc_err_mv'))
        cands[cap] = {'r_exact_ohm': exact, 'r_e96_ohm': std, 'r_exact_guard_ohm': exact_g, 'r_e96_guard_ohm': std_g,
                      'node_at_cap_2k70_mV': cm.node_mv(cap), 'node_at_cap_e96_mV': cm.node_mv(cap, std),
                      'node_at_cap_e96_guard_mV': cm.node_mv(cap, std_g),
                      'node_at_02N_e96_mV': cm.node_mv(min(forces), std),
                      'n_per_mV_5N_e96': n_per_mv(v('fsr_resolution_force_n'), std),
                      'n_per_mV_cap_e96': n_per_mv(cap, std), 'n_per_mV_cap_2k70': n_per_mv(cap, ELEC['r_fsr_fixed_ohm']),
                      'keeps_2k70': cm.node_mv(cap) <= adc_max, 'over_2k70_mV': cm.node_mv(cap) - adc_max}
    r['caps'] = cands
    r['res'] = {'n_per_mV_5N_2k70': n_per_mv(v('fsr_resolution_force_n'), ELEC['r_fsr_fixed_ohm'])}
    fs = v('fsr_sample_rate_hz')
    r['filter'] = [filter_point(f) for f in (v('fsr_unloaded_force_n'),) + forces]
    r['ema_tau_s'] = -1.0 / (fs * math.log(1 - v('ema_alpha')))
    worst_tau = max(p['tau_s'] for p in r['filter'][1:])
    r['filter_delay_worst_s'] = worst_tau
    r['filter_delay_pct_of_budget'] = 100 * worst_tau / v('ctrl_lag_budget_s')
    cs = v('esp_adc_cs_pf') * 1e-12
    settle = formulas.half_lsb_settling_time(v('esp_adc_rsw_ohm'), cs, v('esp_adc_resolution_bits'), math.log)
    r['adc'] = {'cs_F': cs, 'charge_share_mV_at_2450': adc_max * cs / (cs + ELEC['c_aa_F']),
                'sample_tau_s': v('esp_adc_rsw_ohm') * cs, 'settle_12bit_s': settle,
                'reservoir_droop_mV_at_2450': adc_max * cs * fs * (ELEC['r_aa_ohm'] + max(p['r_source_ohm'] for p in r['filter']))}
    return r


def report(r):
    adc_min, adc_max = v('esp_adc_min_mv'), v('esp_adc_max_mv')
    r_fixed_kohm = ELEC['r_fsr_fixed_ohm'] / 1e3
    gain_freqs = v('fsr_filter_gain_freqs_hz')
    gain_keys = ['atten_%dHz' % frequency for frequency in gain_freqs]
    gain_headers = ['gain @%s' % ('%.0f kHz' % (frequency / 1e3) if frequency >= v('fsr_sample_rate_hz')
                                 else '%.0f Hz' % frequency) for frequency in gain_freqs]
    print('FSR front end: 3V3 - FSR - node - R15 - GND, R15 = %.0f ohm, R16 %.0f ohm, C17 %.0f nF' % (ELEC['r_fsr_fixed_ohm'], ELEC['r_aa_ohm'], ELEC['c_aa_F'] * 1e9))
    print('Fit [S: config.h]: R_fsr = %.0f ohm x F^-%.4f. ADC span %.0f to %.0f mV [S], total error +/-%.0f mV [S].\n' % (
        r['fit']['R1N_ohm'], r['fit']['exp'], adc_min, adc_max, v('esp_adc_err_mv')))
    print(cm.table([[x['force_N'], '%.0f' % x['r_fsr_ohm'], '%.1f' % x['node_mV'], 'yes' if x['in_span'] else 'NO (%+.1f mV)' % (x['node_mV'] - adc_max if x['node_mV'] > adc_max else x['node_mV'] - adc_min),
                     '%.4f' % x['n_per_mV']] for x in r['table']], ['force N', 'R_fsr ohm', 'node mV (R15 %.2fk)' % r_fixed_kohm,
                                                                    'inside %.0f-%.0f mV' % (adc_min, adc_max), 'resolution N/mV']))
    print('\nFixed resistor for each force cap (largest value with node(cap) <= %.0f mV; the guard column also leaves the %.0f mV ADC error)' % (
        adc_max, v('esp_adc_err_mv')))
    rows = []
    for cap, c in r['caps'].items():
        rows.append([cap, '%.0f' % c['r_exact_ohm'], '%.0f' % c['r_e96_ohm'], '%.0f' % c['r_e96_guard_ohm'], '%.1f' % c['node_at_cap_2k70_mV'], '%+.1f' % c['over_2k70_mV'],
                     '%.1f' % c['node_at_cap_e96_mV'], '%.1f' % c['node_at_02N_e96_mV'], '%.4f' % c['n_per_mV_5N_e96'], '%.4f' % c['n_per_mV_cap_e96'], '%.4f' % c['n_per_mV_cap_2k70'],
                     'yes' if c['keeps_2k70'] else 'no'])
    print(cm.table(rows, ['cap N', 'exact ohm', 'E96 ohm', 'E96 with guard', 'node@cap %.2fk mV' % r_fixed_kohm, 'vs %.0f mV' % adc_max,
                          'node@cap E96 mV', 'node@%.1fN E96 mV' % min(v('fsr_table_forces_n')),
                          'N/mV @%.0fN E96' % v('fsr_resolution_force_n'), 'N/mV @cap E96', 'N/mV @cap %.2fk' % r_fixed_kohm,
                          '%.2fk fits' % r_fixed_kohm]))
    print('Resolution at %.0f N with %.2fk: %.4f N/mV (%.2f mV per N)' % (
        v('fsr_resolution_force_n'), r_fixed_kohm, r['res']['n_per_mV_5N_2k70'], 1 / r['res']['n_per_mV_5N_2k70']))
    print('\nAnti-alias filter (R16 + R15 || R_fsr, C17); delay is the first-order time constant [D]')
    print(cm.table([[('open FSR (0 ohm)' if not x['force_N'] else x['force_N']), '%.0f' % x['r_source_ohm'], '%.1f' % x['fc_Hz']]
                    + ['%.3f' % x[key] for key in gain_keys] + ['%.2f' % (x['tau_s'] * 1e3)]
                    for x in r['filter']], ['force N', 'source ohm', 'corner Hz'] + gain_headers + ['delay ms']))
    print('EMA alpha %.2f at %.0f kHz: tau %.2f ms [D]. Worst filter delay %.2f ms = %.1f %% of the %.0f ms firmware lag budget [S: config.h].' % (
        v('ema_alpha'), v('fsr_sample_rate_hz') / 1e3, r['ema_tau_s'] * 1e3, r['filter_delay_worst_s'] * 1e3,
        r['filter_delay_pct_of_budget'], v('ctrl_lag_budget_s') * 1e3))
    a = r['adc']
    print('ADC sampling capacitor %.0f pF [A]: charge sharing with the %.0f nF reservoir %.2f mV at %.0f mV; reservoir droop between %.0f kHz samples %.2f mV (bound); '
          'sample-cap settling tau %.0f ns, %.0f-bit settling %.2f us [A: %.0f kohm switch].' % (
              a['cs_F'] * 1e12, ELEC['c_aa_F'] * 1e9, a['charge_share_mV_at_2450'], adc_max, v('fsr_sample_rate_hz') / 1e3,
              a['reservoir_droop_mV_at_2450'], a['sample_tau_s'] * 1e9, v('esp_adc_resolution_bits'), a['settle_12bit_s'] * 1e6,
              v('esp_adc_rsw_ohm') / 1e3))


if __name__ == '__main__':
    report(run())
