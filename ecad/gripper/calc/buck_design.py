"""TPS54560B buck: frequency, ripple, set point, UVLO, duty limits, and the control loop.

Run from the repository root:  python ecad/gripper/calc/buck_design.py

Jargon.
  Peak-current-mode buck: the switch turns off when inductor current reaches a level set by the error amplifier
    (COMP pin); COMP volts x 17 A/V = peak current.
  Type-II compensator: R5 in series with C5 from COMP to ground (a zero), C6 from COMP to ground (a pole).
  Crossover: frequency where loop gain |T| = 1. Phase margin (PM) = 180 deg + phase of T there.
    Gain margin (GM) = -|T| in dB where the phase is -180 deg.
  Ridley sampling term He(s): the double pole at half the switching frequency of a current-mode loop [Ridley 1991].
  SERVO_V: the node after the 0.1 ohm shunt; the feedback divider R6/R7 reads it. V_BUCK is before the shunt.
Tags: [S] sourced (constants.py), [D] derived here, [A] assumed (stated).

Model of the loop gain T(s) = beta * gm_ea * Zcomp(s) * gm_ps / He(s) * (v_servo_v / i_L)(s), with
  v_servo_v / i_L = Zbuck * Zsrv / (Rs + Zsrv)
  Zbuck = Zceramic || (Rs + Zsrv)           ceramic at V_BUCK, shunt Rs, SERVO_V network Zsrv
  Zsrv  = Zbulk || (R_cable + s L_cable + (Zwrist || (R_lead + R_load)))
Feedback is taken at SERVO_V (after the shunt), so the shunt sits inside the loop.
The servo is a resistor at its operating point (small signal) [A].
"""
import itertools
import math

import numpy as np

import _common as cm
from formulas import amplitude_db, phase_margin, ridley_quality_factor
from _common import ELEC, v

def cable_resistance():
    return 2 * ELEC['cable_len_m'] * v('awg%d_ohm_m' % ELEC['cable_power_awg'])   # out and back, 20 AWG [D]
def l_cable():
    return v('cable_l_per_m') * ELEC['cable_len_m']                                # loop inductance [A]
def r_lead():
    return v('buck_servo_lead_resistance_ohm')                                                                      # servo lead + plug, 0.3 m of 22 AWG pair [A]

def __getattr__(name):
    if name == 'R_LEAD':
        return r_lead()
    raise AttributeError(name)
def vset():
    return ELEC['vref_V'] * (1 + ELEC['r_fb_top_ohm'] / ELEC['r_fb_bot_ohm'])


def fsw_from_rt(r_ohm):
    """Switching frequency in Hz from the RT resistor: fsw[kHz] = 92471 * RT[kohm]^-0.991 [S]."""
    return v('tps_rt_coeff') * (r_ohm / 1e3) ** v('tps_rt_exp') * 1e3


def duty(vo, vin):
    return vo / vin


def ripple_pp(vo, vin, l_h, fsw):
    """Inductor peak-to-peak ripple current, A (ideal buck) [D]."""
    return vo * (1 - vo / vin) / (l_h * fsw)


def uvlo(r_top, r_bot, ven=None, i1=None, ihys=None):
    """Input voltage at which the EN divider starts and stops the buck.

    EN rising: node = Vin*Rb/(Rt+Rb) + I1*(Rt||Rb) = Ven.  Once running, Ihys is added to the pull-up current.
    """
    ven = v('tps_en_thresh') if ven is None else ven
    i1 = v('tps_en_i1') if i1 is None else i1
    ihys = v('tps_en_ihys') if ihys is None else ihys
    rp = r_top * r_bot / (r_top + r_bot)
    k = (r_top + r_bot) / r_bot
    return (ven - i1 * rp) * k, (ven - (i1 + ihys) * rp) * k


def uvlo_range(r_top, r_bot):
    """Worst-case start (max) and stop (min) over the EN threshold and current ranges [S]."""
    starts, stops = [], []
    for ven in (v('tps_en_thresh_min'), v('tps_en_thresh_max')):
        for i1 in (v('tps_en_i1_min'), v('tps_en_i1_max')):
            for ih in (v('tps_en_ihys_min'), v('tps_en_ihys_max')):
                s, p = uvlo(r_top, r_bot, ven, i1, ih)
                starts.append(s)
                stops.append(p)
    return (min(starts), max(starts)), (min(stops), max(stops))


def setpoint(rt=None, rb=None, vref=None, tol_r=None):
    rt = ELEC['r_fb_top_ohm'] if rt is None else rt
    rb = ELEC['r_fb_bot_ohm'] if rb is None else rb
    vref = ELEC['vref_V'] if vref is None else vref
    return vref * (1 + rt / rb)


def setpoint_range():
    cm.margin_inputs.record_module("buck_design")
    tol = v('buck_feedback_resistor_tolerance')
    lo = v('tps_vref_min') * (1 + ELEC['r_fb_top_ohm'] * (1 - tol) / (ELEC['r_fb_bot_ohm'] * (1 + tol)))
    hi = v('tps_vref_max') * (1 + ELEC['r_fb_top_ohm'] * (1 + tol) / (ELEC['r_fb_bot_ohm'] * (1 - tol)))
    return lo, setpoint(), hi


def loop_T(f, iload=None, esr_b=None, cb=None, cer_factor=None, wrist=True, vin=None, r5=None, c5=None, c6=None,
           vo=None, r_cable=None, mc=None):
    """Complex loop gain at frequencies f (Hz)."""
    iload = v('buck_nominal_load_a') if iload is None else iload
    vin = v('buck_nominal_input_v') if vin is None else vin
    esr_b = v('c12_esr') if esr_b is None else esr_b
    cb = ELEC['c_bulk_F'] if cb is None else cb
    cer_factor = v('cer_derate_6v6') if cer_factor is None else cer_factor
    r5 = ELEC['r_comp_ohm'] if r5 is None else r5
    c5 = ELEC['c_comp_F'] if c5 is None else c5
    c6 = ELEC['c_pole_F'] if c6 is None else c6
    vo = vset() if vo is None else vo
    r_cable = cable_resistance() if r_cable is None else r_cable
    mc = v('mc_ridley') if mc is None else mc
    f = np.asarray(f, dtype=float)
    s = 2j * np.pi * f
    rs = ELEC['r_shunt_ohm']
    rload = max(vo / iload, v('buck_load_resistance_floor_ohm'))
    zb = esr_b + 1 / (s * cb)
    z_branch = r_lead() + rload
    if wrist:
        zw = v('c_wrist_esr') + 1 / (s * ELEC['c_wrist_F'])
        zend = zw * z_branch / (zw + z_branch)
    else:
        zend = z_branch + 0 * s
    zcab = r_cable + s * l_cable() + zend
    zsrv = zb * zcab / (zb + zcab)
    zcer = v('cer_esr') + 1 / (s * ELEC['c_out_ceramic_F'] * cer_factor)
    zrs = rs + zsrv
    zbuck = zcer * zrs / (zcer + zrs)
    plant = zbuck * zsrv / zrs
    beta = ELEC['r_fb_bot_ohm'] / (ELEC['r_fb_top_ohm'] + ELEC['r_fb_bot_ohm'])
    ro = v('tps_ea_gain') / v('tps_ea_gm')
    ycomp = 1 / ro + s * c6 + 1 / (r5 + 1 / (s * c5))
    zcomp = 1 / ycomp
    d = vo / vin
    wn = math.pi * fsw_from_rt(ELEC['r_rt_ohm'])
    qp = ridley_quality_factor(mc, d) / math.pi
    he = 1 + s / (wn * qp) + (s / wn) ** 2
    return beta * v('tps_ea_gm') * zcomp * v('tps_ps_gm') / he * plant


def margins(f, T):
    """(crossover Hz, PM deg, GM dB, fc list) for loop gain T over frequency f.

    Uses every |T| = 1 crossing: the reported crossover is the highest one and PM is the worst over all crossings.
    GM is taken at the first -180 deg crossing above the first crossover (inf if none below fsw/2).
    """
    mag = np.abs(T)
    ph = np.unwrap(np.angle(T))
    # shift so the low-frequency phase is the principal value of the plant (starts near 0 to -90)
    ph = ph - 2 * np.pi * np.round(ph[0] / (2 * np.pi))
    idx = np.where((mag[:-1] - 1) * (mag[1:] - 1) < 0)[0]
    if len(idx) == 0:
        return {'fc': float('nan'), 'pm': float('nan'), 'gm': math.inf, 'n_cross': 0}
    pms, fcs = [], []
    for i in idx:
        w = -math.log(mag[i]) / (math.log(mag[i + 1]) - math.log(mag[i]))
        fc = f[i] * (f[i + 1] / f[i]) ** w
        p = ph[i] + w * (ph[i + 1] - ph[i])
        pms.append(phase_margin(math.degrees(p)))
        fcs.append(fc)
    gm = math.inf
    pi_ = np.where((ph[:-1] + np.pi) * (ph[1:] + np.pi) < 0)[0]
    pi_ = [i for i in pi_ if f[i] > fcs[0]]
    gms = []
    for i in pi_:
        w = (-np.pi - ph[i]) / (ph[i + 1] - ph[i])
        m = mag[i] * (mag[i + 1] / mag[i]) ** w
        gms.append(-amplitude_db(math.log10(m)))
    if gms:
        gm = min(gms)
    return {'fc': max(fcs), 'pm': min(pms), 'gm': gm, 'n_cross': len(idx)}


def frequency_grid():
    return np.geomspace(cm.NUMERICS['buck_frequency_min_hz'],
                        cm.NUMERICS['buck_frequency_max_hz'],
                        cm.NUMERICS['buck_grid_points'])


def sweep_values():
    return {
        'iload_A': [v(name) for name in ('buck_load_min_a', 'buck_load_light_a',
                                         'buck_load_half_a', 'buck_nominal_load_a',
                                         'buck_load_two_a', 'buck_load_max_a')],
        'esr_b_ohm': [v(name) for name in ('buck_bulk_esr_min_ohm', 'c_wrist_esr',
                                           'buck_bulk_esr_max_ohm')],
        'cb_scale': [v('buck_bulk_scale_min'), None, v('buck_bulk_scale_max')],
        'cer_factor': [v('buck_ceramic_factor_min'), v('buck_ceramic_factor_mid'),
                       None],
        'vin_V': [v('buck_input_min_v'), v('buck_input_max_v')],
    }


def sweep(r5=None, c5=None, c6=None, wrist=True, grid=None, sw=None, keep=True):
    sw = sw or sweep_values()
    grid = frequency_grid() if grid is None else grid
    worst = {'pm': math.inf, 'gm': math.inf}
    rows = []
    for il, esr, cs, cf, vin in itertools.product(sw['iload_A'], sw['esr_b_ohm'], sw['cb_scale'], sw['cer_factor'], sw['vin_V']):
        cb = ELEC['c_bulk_F'] if cs is None else ELEC['c_bulk_F'] * cs
        ceramic = v('cer_derate_6v6') if cf is None else cf
        T = loop_T(grid, iload=il, esr_b=esr, cb=cb, cer_factor=ceramic,
                   vin=vin, r5=r5, c5=c5, c6=c6, wrist=wrist)
        m = margins(grid, T)
        m.update(iload=il, esr_b=esr, cb_scale=cb / ELEC['c_bulk_F'],
                 cer_factor=ceramic, vin=vin)
        if keep:
            rows.append(m)
        if m['pm'] < worst['pm'] or (math.isnan(m['pm'])):
            worst['pm'] = m['pm']
            worst['pm_case'] = m
        if m['gm'] < worst['gm']:
            worst['gm'] = m['gm']
            worst['gm_case'] = m
    return worst, rows


def phase_margin_min():
    return v('buck_phase_margin_min_deg')


def gain_margin_min():
    return v('buck_gain_margin_min_db')


def recommend():
    """Search R5, C5, C6 for values that pass PM >= 45 deg and GM >= 10 dB over a corner subset, maximising PM."""
    values = sweep_values()
    corners = {key: ([items[0], items[-1]] if len(items) > 2 else items)
               for key, items in values.items()}
    corners['iload_A'].insert(1, v('buck_nominal_load_a'))
    g = np.geomspace(cm.NUMERICS['buck_frequency_min_hz'],
                     cm.NUMERICS['buck_frequency_max_hz'],
                     cm.NUMERICS['buck_recommend_grid_points'])
    best = None
    for r5, c5, c6 in itertools.product(v('buck_candidate_r_ohm'),
                                         v('buck_candidate_c_f'),
                                         v('buck_candidate_pole_f')):
        w, _ = sweep(r5, c5, c6, grid=g, sw=corners, keep=False)
        if w['pm'] != w['pm']:
            continue
        ok = w['pm'] >= phase_margin_min() and w['gm'] >= gain_margin_min()
        score = (ok, min(w['pm'], v('buck_phase_score_cap_deg')), min(w['gm'], v('buck_gain_score_cap_db')))
        if best is None or score > best[0]:
            best = (score, r5, c5, c6, w['pm'], w['gm'])
    return {'r5_ohm': best[1], 'c5_F': best[2], 'c6_F': best[3], 'pm_deg': best[4], 'gm_dB': best[5], 'passes': bool(best[0][0])}


def run():
    r = {}
    r['fsw_Hz'] = fsw_from_rt(ELEC['r_rt_ohm'])
    r['setpoint_V'] = vset()
    r['setpoint_range_V'] = setpoint_range()
    st, sp = uvlo(ELEC['r_uvlo_top_ohm'], ELEC['r_uvlo_bot_ohm'])
    r['uvlo_start_V'], r['uvlo_stop_V'] = st, sp
    r['uvlo_start_range_V'], r['uvlo_stop_range_V'] = uvlo_range(ELEC['r_uvlo_top_ohm'], ELEC['r_uvlo_bot_ohm'])
    rip = []
    for vin in (v('buck_input_min_v'), v('buck_nominal_input_v'), v('buck_input_max_v')):
        d = duty(vset(), vin)
        dI = ripple_pp(vset(), vin, ELEC['l_buck_H'], r['fsw_Hz'])
        ton = d / r['fsw_Hz']
        rip.append({'vin_V': vin, 'duty': d, 'ripple_pp_A': dI, 'ton_s': ton,
                    'ton_over_min': ton / v('tps_ton_min'),
                    'imax_dc_for_ilim_min_A': v('tps_ilim_min') - dI / 2,
                    'fsw_max_by_ton_Hz': vset() / (vin * v('tps_ton_min'))})
    r['ripple'] = rip
    r['cable_R_ohm'] = cable_resistance()
    r['cable_L_H'] = l_cable()
    # nominal and worst corner
    grid = frequency_grid()
    T = loop_T(grid, iload=v('buck_nominal_load_a'))
    r['nominal'] = margins(grid, T)
    worst, rows = sweep()
    r['n_cases'] = len(rows)
    r['worst_pm'] = worst['pm']
    r['worst_pm_case'] = worst['pm_case']
    r['worst_gm'] = worst['gm']
    r['worst_gm_case'] = worst['gm_case']
    r['pass'] = bool(worst['pm'] >= phase_margin_min() and worst['gm'] >= gain_margin_min())
    fcs = [m['fc'] for m in rows if m['fc'] == m['fc']]
    r['fc_min_Hz'], r['fc_max_Hz'] = min(fcs), max(fcs)
    r['n_fail'] = sum(1 for m in rows if not (m['pm'] >= phase_margin_min() and m['gm'] >= gain_margin_min()))
    r['no_wrist_worst_pm'] = sweep(wrist=False, keep=False)[0]['pm']
    # which load/dimension drives the worst case, by load
    byload = {}
    for m in rows:
        d = byload.setdefault(m['iload'], {'pm': math.inf, 'gm': math.inf,
                                                   'fc_min': math.inf,
                                                   'fc_max': 0})
        d['pm'] = min(d['pm'], m['pm'])
        d['gm'] = min(d['gm'], m['gm'])
        if m['fc'] == m['fc']:
            d['fc_min'] = min(d['fc_min'], m['fc'])
            d['fc_max'] = max(d['fc_max'], m['fc'])
    r['by_load'] = byload
    r['recommendation'] = None if r['pass'] else recommend()
    if r['recommendation']:
        rc = r['recommendation']
        w2, _ = sweep(rc['r5_ohm'], rc['c5_F'], rc['c6_F'], keep=False)
        rc['full_sweep_pm_deg'], rc['full_sweep_gm_dB'] = w2['pm'], w2['gm']
    # figure data: Bode at nominal and worst corner
    wc = r['worst_pm_case']
    Tw = loop_T(grid, iload=wc['iload'], esr_b=wc['esr_b'], cb=ELEC['c_bulk_F'] * wc['cb_scale'], cer_factor=wc['cer_factor'], vin=wc['vin'])
    r['bode'] = {'f': grid[::cm.NUMERICS['buck_bode_stride']],
                 'nom_mag_dB': amplitude_db(np.log10(np.abs(T[::cm.NUMERICS['buck_bode_stride']]))),
                 'nom_ph_deg': np.degrees(np.unwrap(np.angle(T)))[::8],
                 'worst_mag_dB': amplitude_db(np.log10(np.abs(Tw[::cm.NUMERICS['buck_bode_stride']]))),
                 'worst_ph_deg': np.degrees(np.unwrap(np.angle(Tw)))[::8]}
    return r


def report(r):
    print('TPS54560B buck design (400 kHz, 10 uH, 2 x 47 uF, compensator R5/C5/C6 from design.py)')
    print('Tags: [S] constants.py, [D] derived, [A] assumed\n')
    print('Frequency and set point')
    print(cm.table([
        ['fsw from R4 = %.0f kohm [D, S equation]' % (ELEC['r_rt_ohm'] / 1e3), '%.1f kHz' % (r['fsw_Hz'] / 1e3)],
        ['set point 0.8 x (1 + R6/R7) [D]', '%.3f V' % r['setpoint_V']],
        ['set point range (Vref 0.792 to 0.808 V [S], R6/R7 0.1 %)', '%.3f to %.3f V' % (r['setpoint_range_V'][0], r['setpoint_range_V'][2])],
        ['UVLO start / stop nominal [D]', '%.2f V / %.2f V' % (r['uvlo_start_V'], r['uvlo_stop_V'])],
        ['UVLO start range (EN thresholds and currents [S])', '%.2f to %.2f V' % r['uvlo_start_range_V']],
        ['UVLO stop range', '%.2f to %.2f V' % r['uvlo_stop_range_V']],
        ['cable loop R (20 AWG, 1.2 m out and back) [D]', '%.1f mohm' % (r['cable_R_ohm'] * 1e3)],
        ['cable loop L [A]', '%.2f uH' % (r['cable_L_H'] * 1e6)],
    ], ['item', 'value']))
    print('\nInductor ripple, duty and minimum on-time')
    print(cm.table([[x['vin_V'], '%.3f' % x['duty'], '%.3f' % x['ripple_pp_A'], '%.2f' % (x['ton_s'] * 1e6), '%.1f' % x['ton_over_min'],
                     '%.2f' % x['imax_dc_for_ilim_min_A'], '%.2f' % (x['fsw_max_by_ton_Hz'] / 1e6)] for x in r['ripple']],
                   ['Vin V', 'duty', 'ripple A pk-pk', 'on-time us', 'on-time / 135 ns', 'max DC load A (6.3 A limit)', 'fsw max MHz by on-time']))
    print('\nLoop (peak-current-mode small-signal model, feedback at SERVO_V), %d cases' % r['n_cases'])
    n = r['nominal']
    print('nominal (1 A, ESR 0.03 ohm, 1000 uF, ceramic 60 %%, 12 V): crossover %.2f kHz, PM %.1f deg, GM %.1f dB' % (n['fc'] / 1e3, n['pm'], n['gm']))
    print('crossover over all cases: %.2f to %.2f kHz' % (r['fc_min_Hz'] / 1e3, r['fc_max_Hz'] / 1e3))
    wc = r['worst_pm_case']
    print('worst phase margin %.1f deg at load %.2f A, ESR %.2f ohm, Cbulk x%.1f, ceramic %.0f %%, Vin %.1f V (crossover %.2f kHz)' % (
        r['worst_pm'], wc['iload'], wc['esr_b'], wc['cb_scale'], wc['cer_factor'] * 100, wc['vin'], wc['fc'] / 1e3))
    gc = r['worst_gm_case']
    print('worst gain margin  %.1f dB at load %.2f A, ESR %.2f ohm, Cbulk x%.1f, ceramic %.0f %%, Vin %.1f V' % (
        r['worst_gm'], gc['iload'], gc['esr_b'], gc['cb_scale'], gc['cer_factor'] * 100, gc['vin']))
    print('cases failing PM >= 45 deg and GM >= 10 dB: %d of %d  ->  %s' % (r['n_fail'], r['n_cases'], 'PASS' if r['pass'] else 'FAIL'))
    print('worst PM with the 470 uF forearm capacitor absent: %.1f deg' % r['no_wrist_worst_pm'])
    print(cm.table([[k, '%.1f' % d['pm'], '%.1f' % d['gm'], '%.2f to %.2f' % (d['fc_min'] / 1e3, d['fc_max'] / 1e3)] for k, d in sorted(r['by_load'].items())],
                   ['load A', 'worst PM deg', 'worst GM dB', 'crossover kHz']))
    if r['recommendation']:
        rc = r['recommendation']
        print('\nRecommended compensator (search over R5, C5, C6): R5 %.1f kohm, C5 %.1f nF, C6 %.0f pF -> PM %.1f deg, GM %.1f dB on the corner subset; '
              'full sweep PM %.1f deg, GM %.1f dB; passes: %s' % (rc['r5_ohm'] / 1e3, rc['c5_F'] * 1e9, rc['c6_F'] * 1e12, rc['pm_deg'], rc['gm_dB'],
                                                              rc['full_sweep_pm_deg'], rc['full_sweep_gm_dB'], rc['passes']))
    print('\nNotes: He(s) uses mc = %.1f [A]; the servo is a resistor at its operating point [A]; the 5 V LDO load is a constant current [A].' % v('mc_ridley'))


if __name__ == '__main__':
    report(run())
