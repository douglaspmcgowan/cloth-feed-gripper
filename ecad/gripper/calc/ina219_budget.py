"""INA219 current-reading error budget at the 3.0 A stall trip, saturation, trip against hold, detection delay, chopped current.

Run from the repository root:  python ecad/gripper/calc/ina219_budget.py

Jargon.
  Trip: the firmware's STALL_CURRENT_A = 3.0 A, which must persist for STALL_CURRENT_MS = 100 ms, read every 20 ms.
  PGA /8: the INA219 power-on default (the firmware never writes the configuration register): shunt full scale +/-320 mV.
  Offset: shunt-voltage error at zero input, RTI (referred to input), in microvolts; here as amperes through 0.1 ohm.
  Worst case: all terms add. RSS: root of the sum of squares (the terms are independent).
  Chopped current: a servo's motor drive switches on and off; the INA219 integrates the shunt voltage over its conversion
    time (532 us at 12 bits), so a short conversion can land on the on-part or the off-part of a chop cycle.
Tags: [S] constants.py, [D] derived here, [A] assumed.
"""
import math

import _common as cm
from _common import ELEC, FITS, v
from formulas import half_interval


def __getattr__(name):
    """Keep the historical TRIP_A API without binding a physical value at import time."""
    if name == 'TRIP_A':
        return v('ina_trip_current_a')
    raise AttributeError(name)


def rshunt():
    return ELEC['r_shunt_ohm']


def error_terms(i_a=None):
    """Each error source at current i_a as (amperes, fraction of reading). All values are +/- limits."""
    i_a = v('ina_trip_current_a') if i_a is None else i_a
    vsh = i_a * rshunt()
    t = {}
    t['offset, PGA /8, 200 uV max [S]'] = v('ina_vos_pga8') / rshunt()
    t['gain error, 0.5 % max incl. offset at 25 C [S]'] = v('ina_meas_err_max') * i_a
    t['gain temperature drift, 1 m%/C over 40 C [S]'] = (
        v('ina_gain_tc') * v('ina_gain_temperature_span_c') * i_a)
    t['shunt tolerance 1 % [A]'] = v('rs1_tol') * i_a
    t['shunt TCR 100 ppm/C over 45 C rise [A]'] = (
        v('rs1_tcr') * v('ina_shunt_temperature_rise_c') * i_a)
    # filter resistors: R8, R9 10 ohm with 1 % mismatch, and bias-current mismatch assumed 100 % of the 20 uA
    t['filter R8/R9: 20 uA bias mismatch x 10 ohm [S, A]'] = v('ina_ibias') * ELEC['r_ina_filter_ohm'] / rshunt()
    t['filter R8/R9: gain loss R/320 kohm input impedance [S]'] = (
        ELEC['r_ina_filter_ohm'] / v('ina_input_impedance_ohm') * i_a)
    t['quantisation, +/-0.5 LSB = 5 uV [S]'] = half_interval(v('ina_lsb')) / rshunt()
    return {k: (a, a / i_a) for k, a in t.items()}, vsh


def budget(i_a=None):
    i_a = v('ina_trip_current_a') if i_a is None else i_a
    terms, vsh = error_terms(i_a)
    wc = sum(a for a, _ in terms.values())
    rss = math.sqrt(sum(a * a for a, _ in terms.values()))
    return {'terms': terms, 'worst_A': wc, 'worst_pct': 100 * wc / i_a, 'rss_A': rss, 'rss_pct': 100 * rss / i_a,
            'true_trip_range_worst_A': (i_a / (1 + wc / i_a), i_a / (1 - wc / i_a)),
            'true_trip_range_rss_A': (i_a - rss, i_a + rss), 'shunt_mV': vsh * 1e3}


def hold_currents(cap):
    out = {}
    for fit in ('A', 'B'):
        out[fit] = {'torque_Nm': cm.servo_torque(cap), 'ideal_A': cm.servo_current_ideal(cap, fit),
                    'with_offset_A': cm.servo_current_at_force(cap, fit)}
    return out


def chopped_error(f_chop, duty, ip=None, w=None):
    """Reading range for a conversion window w over a chopped current (ip when on, 0 when off) [D].

    Returns (min reading, max reading, mean) in units of ip. When w is a whole number of chop periods all three agree.
    """
    ip = 1.0 if ip is None else ip
    w = v('ina_conv_12bit') if w is None else w
    tc = 1.0 / f_chop
    on = duty * tc
    off = tc - on
    if w >= tc:
        n = math.floor(w / tc)
        rem = w - n * tc
        base = n * on
        lo = base + max(0.0, rem - off)
        hi = base + min(on, rem)
    else:
        lo = max(0.0, w - off)
        hi = min(on, w)
    return lo / w * ip, hi / w * ip, duty * ip


def run():
    r = {'budget': budget()}
    r['shunt_fs_A'] = v('ina_fs_pga8') / rshunt()
    r['saturation'] = {'fit_A_stall_A': FITS['A']['stall_A'], 'fit_A_shunt_mV': FITS['A']['stall_A'] * rshunt() * 1e3, 'fs_mV': v('ina_fs_pga8') * 1e3,
                       'saturates': FITS['A']['stall_A'] * rshunt() > v('ina_fs_pga8'), 'reading_when_saturated_A': r['shunt_fs_A'],
                       'still_trips': (r['shunt_fs_A'] * (1 - v('ina_saturation_error_fraction'))
                                       > v('ina_trip_current_a')),
                       'fit_B_stall_A': FITS['B']['stall_A'], 'fit_B_saturates': FITS['B']['stall_A'] * rshunt() > v('ina_fs_pga8')}
    rng = r['budget']['true_trip_range_worst_A']
    r['hold'] = {}
    for cap in v('ina_force_caps_n'):
        hc = hold_currents(cap)
        r['hold'][cap] = {fit: {
                                **hc[fit],
                                'margin_ideal_A': v('ina_trip_current_a') - hc[fit]['ideal_A'],
                                'margin_offset_A': v('ina_trip_current_a') - hc[fit]['with_offset_A'],
                                'margin_offset_vs_worst_low_A': rng[0] - hc[fit]['with_offset_A'],
                                'margin_ideal_vs_worst_low_A': rng[0] - hc[fit]['ideal_A']} for fit in ('A', 'B')}
    window_s = v('ina_trip_window_s')
    period_s = v('ina_control_period_s')
    n_samples = round(window_s / period_s)
    r['delay'] = {'window_s': window_s, 'period_s': period_s, 'samples_needed': n_samples,
                  'min_s': window_s, 'max_s': window_s + period_s + v('ina_conv_12bit_max'),
                  'r20_limit_s': v('ina_detection_limit_s'),
                  'left_for_backoff_s': (v('ina_detection_limit_s')
                                         - (window_s + period_s + v('ina_conv_12bit_max')))}
    ch = []
    for fc in v('ina_chop_frequencies_hz'):
        for d in (v('ina_chop_duty'),):
            lo, hi, mean = chopped_error(fc, d)
            ch.append({'f_chop_Hz': fc, 'duty': d, 'lo': lo, 'hi': hi, 'mean': mean, 'err_pct_worst': 100 * max(abs(lo - mean), abs(hi - mean)) / mean})
    r['chop'] = ch
    # averaging: SADC settings 0x8..0xF: 12-bit averaged 2,4,8,16,32,64,128 samples (532 us each)
    avg = []
    for code, n in v('ina_average_codes_samples'):
        t = n * v('ina_conv_12bit')
        e = [chopped_error(f, v('ina_chop_duty'), w=t)
             for f in v('ina_chop_frequencies_hz')[:2]]
        duty = v('ina_chop_duty')
        avg.append({'sadc_bits': code, 'samples': n, 'time_ms': t * 1e3,
                    'fits_20ms': t <= v('ina_average_fit_limit_s'),
                    'worst_err_pct_300Hz': 100 * max(abs(e[0][0] - duty), abs(e[0][1] - duty)) / duty,
                    'worst_err_pct_1kHz': 100 * max(abs(e[1][0] - duty), abs(e[1][1] - duty)) / duty})
    r['averaging'] = avg
    cfg = v('ina_default_cfg')
    shift = int(v('ina_sadc_shift'))
    new = ((int(cfg) & ~(int(v('ina_sadc_mask')) << shift))
           | (int(v('ina_recommended_sadc_code')) << shift))
    r['config'] = {'default': '0x%04X' % int(cfg), 'recommended': '0x%04X' % new, 'sadc_bits': '1101 (12-bit, 32 samples, 17.02 ms)',
                   'note': 'write to register 0x00 once at boot; keeps PGA /8 and 12-bit bus ADC'}
    return r


def report(r):
    b = r['budget']
    print('INA219 current reading at the %.1f A trip '
          '(shunt %.0f mV across %.2f ohm, PGA /8 default, full scale %.0f mV = %.2f A)' % (
              v('ina_trip_current_a'), b['shunt_mV'], rshunt(),
              v('ina_fs_pga8') * 1e3, r['shunt_fs_A']))
    print(cm.table([[k, '%.4f' % a, '%.3f' % (100 * f)] for k, (a, f) in b['terms'].items()] +
                   [['WORST CASE (sum)', '%.4f' % b['worst_A'], '%.2f' % b['worst_pct']], ['ROOT-SUM-SQUARE', '%.4f' % b['rss_A'], '%.2f' % b['rss_pct']]],
                   ['error source (+/-)', 'amperes', 'percent of reading']))
    lo, hi = b['true_trip_range_worst_A']
    print('The true current when the reading first reaches %.1f A lies in %.3f to %.3f A (worst case) and %.3f to %.3f A (RSS).' % (v('ina_trip_current_a'), lo, hi, *b['true_trip_range_rss_A']))
    s = r['saturation']
    print('\nSaturation: Fit A stall %.2f A -> %.0f mV across the shunt against %.0f mV full scale: %s. A saturated reading is %.2f A, %s the %.1f A trip. Fit B stall %.2f A: %s.' % (
        s['fit_A_stall_A'], s['fit_A_shunt_mV'], s['fs_mV'], 'SATURATES' if s['saturates'] else 'does not saturate', s['reading_when_saturated_A'], 'above' if s['still_trips'] else 'NOT above', v('ina_trip_current_a'),
        s['fit_B_stall_A'], 'saturates' if s['fit_B_saturates'] else 'does not saturate'))
    print('\nTrip against holding current at the force cap (torque = 2 F r_c / eta, r_c 65 mm, eta 0.85; current = T/K, and T/K + offset implied by the dyno.md hold point [D])')
    rows = []
    for cap, d in r['hold'].items():
        for fit, x in d.items():
            rows.append([cap, fit, '%.3f' % x['torque_Nm'], '%.3f' % x['ideal_A'], '%.3f' % x['with_offset_A'], '%+.3f' % x['margin_ideal_A'], '%+.3f' % x['margin_offset_A'],
                         '%+.3f' % x['margin_ideal_vs_worst_low_A'], '%+.3f' % x['margin_offset_vs_worst_low_A']])
    print(cm.table(rows, ['cap N', 'fit', 'torque N*m', 'I = T/K A', 'I = T/K + offset A', 'trip margin A (T/K)', 'trip margin A (+offset)', 'margin at low end of trip range (T/K)', '... (+offset)']))
    print('A negative margin means the servo current at the cap is above the trip: STALL would be raised by a legitimate grip at the cap.')
    d = r['delay']
    print('\nDetection delay: current must stay above %.1f A for %.0f ms, sampled every %.0f ms (%d samples): %.0f ms at best, up to %.1f ms with one sample period and one conversion (586 us max). '
          'R20 allows 200 ms to detect and back off: %.1f ms remain for the back-off.' % (v('ina_trip_current_a'), d['window_s'] * 1e3, d['period_s'] * 1e3, d['samples_needed'], d['min_s'] * 1e3, d['max_s'] * 1e3, d['left_for_backoff_s'] * 1e3))
    print('\nChopped motor current (50 % duty, amplitude 1) read once per 20 ms with a 532 us conversion, no averaging; the mean is 0.5')
    print(cm.table([[x['f_chop_Hz'], '%.3f' % x['lo'], '%.3f' % x['hi'], '%.1f' % x['err_pct_worst']] for x in r['chop']], ['chop Hz [A]', 'reading min', 'reading max', 'worst error % of mean']))
    print('\nAveraging setting (SADC bits; time to produce one result)')
    print(cm.table([['0x%X' % x['sadc_bits'], x['samples'], '%.2f' % x['time_ms'], 'yes' if x['fits_20ms'] else 'no', '%.1f' % x['worst_err_pct_300Hz'], '%.1f' % x['worst_err_pct_1kHz']] for x in r['averaging']],
                   ['SADC', 'samples', 'time ms', 'fits 20 ms', 'chop error % @300 Hz', 'chop error % @1 kHz']))
    c = r['config']
    print('Recommendation: write configuration register 0x00 = %s at boot (default %s) -> shunt ADC %s. The result then averages over 17 ms, nearly the whole 20 ms control period, so a chopped current is read as its mean; '
          'one result is ready per control tick. Chop frequency of the DS3218MG drive is not published [A: 300 Hz to 20 kHz tried].' % (c['recommended'], c['default'], c['sadc_bits']))


if __name__ == '__main__':
    report(run())
