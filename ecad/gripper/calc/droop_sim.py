"""Time-domain simulation of a servo stall step on the 6.58 V servo rail.

Run from the repository root:  python ecad/gripper/calc/droop_sim.py

Jargon.
  Averaged current-mode buck: the switching is replaced by its average. The inductor current follows a command
    iL_cmd = 17 A/V x (V_COMP - 0.6 V) - ripple/2 through a first-order lag of bandwidth fsw/6 [A]; the inductor voltage
    slews it no faster than (Vin - V_BUCK)/L up and V_BUCK/L down (the two real limits of a buck).
  Error amplifier: gm 350 uA/V, output limited to +/-30 uA [S], so COMP slews no faster than 30 uA over the compensation
    capacitance (the large-signal limit that a small-signal loop analysis misses).
  Stall step: the servo current goes from 0.15 A (moving, no load [A]) to its stall value in `rise` seconds. At stall the
    servo is a resistor R = V/I_stall (Fit A 1.80 ohm, Fit B 3.09 ohm; dyno.md), so the current falls a little as the rail sags.
  V_BUCK: ceramic output node. SERVO_V: after the 0.1 ohm shunt (the feedback node). Plug: the servo connector, after the
    cable, the 470 uF forearm capacitor and a 30 mohm lead.
Tags: [S] constants.py, [D] derived here, [A] assumed (stated).

Cross-check: one case is repeated in ngspice (KiCad 10 ngspice.dll through ctypes) when it loads; the result or the failure
record is printed at the end. See `ngspice_check()`.
"""
import math
import os

import numpy as np
from scipy.integrate import solve_ivp

import _common as cm
from _common import ELEC, FITS, v
from buck_design import cable_resistance, l_cable, R_LEAD, vset
from margin_inputs import recorded_cache
from formulas import capacitor_energy

def ilim_min():
    return v('tps_ilim_min')
def ilim_typ():
    return v('tps_ilim_typ')
def make_params(fit='A', rise=None, cb=None, wrist=True, fb_before_shunt=False, vin=None, esr_b=None, cer_factor=None,
                istall_scale=None):
    rise = v('droop_default_rise_s') if rise is None else rise
    vin = v('droop_default_vin_v') if vin is None else vin
    cb = ELEC['c_bulk_F'] if cb is None else cb
    if esr_b is None:
        esr_b = v('c12_esr') * (ELEC['c_bulk_F'] / cb) ** 0.5   # ESR falls with the square root of size [A]
    return dict(fit=fit, rise=rise, cb=cb, wrist=wrist, fb_before_shunt=fb_before_shunt, vin=vin, esr_b=esr_b,
                cer_factor=v('cer_derate_6v6') if cer_factor is None else cer_factor,
                r_mot=FITS[fit]['R'] if istall_scale is None else FITS[fit]['R'] / istall_scale)


def _aux(t, x, p):
    """Algebraic quantities from the states: SERVO_V, shunt current, servo current, plug voltage."""
    iL, vcer, vc5, vcomp, vb, icab, vw = x
    rs = ELEC['r_shunt_ohm']
    vs = (vcer / rs + vb / p['esr_b'] - icab) / (1 / rs + 1 / p['esr_b'])
    r = min(max((t - v('droop_step_time_s')) / p['rise'], 0),
            1)
    esr_w = v('c_wrist_esr')
    a = r / p['r_mot']
    b = v('droop_servo_idle_a') * (1 - r)
    rt = esr_w + R_LEAD
    vplug = (vw + esr_w * icab - rt * b) / (1 + rt * a)
    i = b + a * vplug
    return vs, (vcer - vs) / rs, i, vplug


def _rhs(t, x, p):
    iL, vcer, vc5, vcomp, vb, icab, vw = x
    rs = ELEC['r_shunt_ohm']
    vs, ish, i, vplug = _aux(t, x, p)
    esr_w = v('c_wrist_esr')
    cw = ELEC['c_wrist_F'] if p['wrist'] else v('droop_no_wrist_cap_f')
    vnode = vw + esr_w * (icab - i)
    d_vw = (icab - i) / cw
    d_icab = (vs - icab * cable_resistance() - vnode) / l_cable()
    d_vb = (vs - vb) / p['esr_b'] / p['cb']
    ccer = ELEC['c_out_ceramic_F'] * p['cer_factor']
    d_vcer = (iL - ish - v('droop_5v_load_a')) / ccer
    beta = ELEC['r_fb_bot_ohm'] / (ELEC['r_fb_top_ohm'] + ELEC['r_fb_bot_ohm'])
    vfb = (vcer if p['fb_before_shunt'] else vs) * beta
    iea = v('tps_ea_gm') * (v('tps_vref') - vfb)
    iea = max(-v('tps_ea_imax'), min(v('tps_ea_imax'), iea)) - vcomp / (v('tps_ea_gain') / v('tps_ea_gm'))
    r5, c5, c6 = ELEC['r_comp_ohm'], ELEC['c_comp_F'], ELEC['c_pole_F']
    d_vcomp = (iea - (vcomp - vc5) / r5) / c6
    d_vc5 = (vcomp - vc5) / r5 / c5
    vin = p['vin']
    vo = max(vcer, v('droop_voltage_floor_v'))
    fsw = v('droop_fsw_hz')
    di = (vin - vo) * vo / (vin * ELEC['l_buck_H'] * fsw)
    ipk = min(max(v('tps_ps_gm') * (vcomp - v('droop_comp_zero_v')), 0), ilim_typ())
    icmd = max(ipk - di / 2, 0)
    wi = 2 * math.pi * fsw / cm.NUMERICS['inner_loop_divisor']
    d_il = wi * (icmd - iL)
    up = (vin - iL * v('tps_rds_typ') - vo) / ELEC['l_buck_H']
    dn = -(vo + v('droop_diode_v')) / ELEC['l_buck_H']
    d_il = min(max(d_il, dn), up)
    if iL <= 0 and d_il < 0:
        d_il = 0
    return [d_il, d_vcer, d_vc5, d_vcomp, d_vb, d_icab, d_vw]


def _initial(p):
    vs = v('tps_vref') / (ELEC['r_fb_bot_ohm'] / (ELEC['r_fb_top_ohm'] + ELEC['r_fb_bot_ohm']))
    i = v('droop_servo_idle_a')
    vcer = vs + i * ELEC['r_shunt_ohm']
    if p['fb_before_shunt']:
        vcer = vs
        vs = vcer - i * ELEC['r_shunt_ohm']
    il = i + v('droop_5v_load_a')
    di = (p['vin'] - vcer) * vcer / (p['vin'] * ELEC['l_buck_H'] * v('droop_fsw_hz'))
    vcomp = v('droop_comp_zero_v') + (il + di / 2) / v('tps_ps_gm')
    return [il, vcer, vcomp, vcomp, vs, i, vs - i * cable_resistance()]


def simulate(p, t_end=None, keep=False):
    """Run one case. Returns the statistics dict (and the downsampled traces when keep)."""
    t_end = v('droop_end_time_s') if t_end is None else t_end
    t0 = v('droop_step_time_s')
    x0 = _initial(p)
    s1 = solve_ivp(_rhs, (0, t0), x0, args=(p,), method='LSODA',
                   rtol=cm.NUMERICS['solver_rtol'], atol=cm.NUMERICS['solver_atol'],
                   max_step=cm.NUMERICS['initial_max_step_s'])
    x1 = s1.y[:, -1]
    dense = cm.NUMERICS['dense_window_s']
    step = cm.NUMERICS['sample_step_s']
    dense_step = cm.NUMERICS['dense_sample_step_s']
    t_eval = np.unique(np.concatenate([
        np.arange(cm.NUMERICS['initial_sample_count']) * dense_step + t0,
        t0 + dense + np.arange(max(0, int((t_end - t0 - dense) / step))) * step,
    ]))
    t_eval = t_eval[t_eval < t_end]
    s2 = solve_ivp(_rhs, (t0, t_end), x1, args=(p,), method='LSODA', rtol=cm.NUMERICS['solver_rtol'],
                   atol=cm.NUMERICS['solver_atol'], max_step=cm.NUMERICS['loaded_max_step_s'], t_eval=t_eval)
    t, X = s2.t, s2.y
    aux = np.array([_aux(tt, X[:, k], p) for k, tt in enumerate(t)])
    vs, ish, i, vplug = aux.T
    vs0 = _aux(t0, x1, p)[0]
    vplug_end = vplug[-1]
    di = (p['vin'] - X[1]) * X[1] / (p['vin'] * ELEC['l_buck_H'] * v('droop_fsw_hz'))
    ipk = X[0] + di / 2
    bad = np.where(np.abs(vs - vs0) > v('droop_recovery_band_v'))[0]
    rec = (t[bad[-1]] - t0) if len(bad) else 0
    if len(bad) and bad[-1] == len(t) - 1:
        rec = math.inf
    badp = np.where(np.abs(vplug - vplug_end) > v('droop_recovery_band_v'))[0]
    recp = (t[badp[-1]] - t0) if len(badp) else 0
    # charge and energy the bulk capacitor delivers: integral of its current while it discharges
    ib = (vs - X[4]) / p['esr_b']
    q_bulk = -float(np.trapezoid(np.minimum(ib, 0), t))
    st = {
        'vbuck_min_V': float(X[1].min()), 'servo_v_min_V': float(vs.min()), 'plug_min_V': float(vplug.min()),
        'servo_v_pre_V': float(vs0), 'plug_final_V': float(vplug_end), 'servo_v_final_V': float(vs[-1]),
        'recovery_servo_v_s': float(rec), 'recovery_plug_s': float(recp),
        'ipeak_max_A': float(ipk.max()), 'iL_max_A': float(X[0].max()), 'ilim_min_A': ilim_min(),
        'i_servo_final_A': float(i[-1]), 'servo_v_max_V': float(vs.max()), 'vbuck_max_V': float(X[1].max()),
        'bulk_charge_C': q_bulk,
        'bulk_energy_J': capacitor_energy(p['cb'], float(vs0) ** 2 - float(vs.min()) ** 2),
        'vcomp_max_V': float(X[3].max()),
        'params': {k: p[k] for k in ('fit', 'rise', 'cb', 'wrist', 'fb_before_shunt', 'vin', 'esr_b', 'cer_factor')},
    }
    if keep:
        stride = cm.NUMERICS['trace_stride']
        st['trace'] = {'t_ms': (t - t0)[::stride] * 1e3, 'vbuck': X[1][::stride],
                       'servo_v': vs[::stride], 'plug': vplug[::stride],
                       'iL': X[0][::stride], 'i_servo': i[::stride]}
    return st


@recorded_cache
def run():
    r = {'cases': [], 'sweep': [], 'fb_before': []}
    fast = v('droop_fast_rise_s')
    default = v('droop_default_rise_s')
    for fit in ('A', 'B'):
        for rise in (default, fast):
            p = make_params(fit, rise)
            st = simulate(p, keep=fit == 'A' and rise in (default, fast))
            r['cases'].append(st)
    capacitors = (v('droop_sweep_cap_220_f'), v('droop_sweep_cap_470_f'),
                  v('droop_sweep_cap_1000_f'), v('droop_sweep_cap_2200_f'))
    for cb in capacitors:
        for wrist in (True, False):
            r['sweep'].append(simulate(make_params('A', fast, cb=cb, wrist=wrist)))
    for rise in (default, fast):
        r['fb_before'].append(simulate(make_params('A', rise, fb_before_shunt=True)))
    r['low_vin'] = simulate(make_params('A', fast, vin=v('droop_low_vin_v')))
    r['low_vin_B'] = simulate(make_params('B', fast, vin=v('droop_low_vin_v')))
    # zero-step reference: no droop expected
    p0 = make_params('A', default, cb=v('droop_sweep_cap_1000_f'))
    r['verdict'] = verdict(r)
    return r


def verdict(r):
    # power_budget imports this module at load time, so it is imported here, when both have loaded
    import power_budget
    by = {(round(s['params']['cb'] * 1e6), s['params']['wrist']): s for s in r['sweep']}
    s1000 = by[(1000, True)]
    s2200 = by[(2200, True)]
    s470 = by[(470, True)]
    floor = power_budget.ldo_min_input_V()
    ok = (s1000['plug_min_V'] >= v('servo_vmin')
          and s1000['vbuck_min_V'] >= floor)
    gain = s2200['plug_min_V'] - s1000['plug_min_V']
    return {'adequate': bool(ok), 'plug_min_1000_V': s1000['plug_min_V'], 'vbuck_min_1000_V': s1000['vbuck_min_V'],
            'plug_min_470_V': s470['plug_min_V'], 'plug_min_2200_V': s2200['plug_min_V'], 'gain_2200_over_1000_V': gain,
            'vbuck_floor_V': floor,
            'rule': 'plug >= 4.8 V (servo minimum [S]) and V_BUCK >= %.4f V (power_budget ldo_min_input_V: 5 V rail plus worst MCP1703A dropout [S]) in the worst stall step (Fit A, 10 us rise)' % floor}


# ----------------------------------------------------------------------------------------------------------------
def ngspice_check(r):
    """Attempt a cross-check through NGSPICE_LIBRARY or the platform loader path.

    Attempt 1: add the KiCad bin folder to the DLL search path, load ngspice.dll, ngSpice_Init with no-op callbacks,
               run a one-line RC netlist through ngSpice_Command to prove the engine works.
    Attempt 2 (only if 1 loads but the full circuit errors): rerun the netlist with simplified clipping.
    """
    import ctypes
    import ctypes.util
    import tempfile
    dll = os.environ.get('NGSPICE_LIBRARY') or ctypes.util.find_library('ngspice')
    rec = {'tool': 'ngspice', 'attempts': []}
    if not dll:
        rec['attempts'].append('library not found via NGSPICE_LIBRARY or PATH')
        rec['ran'] = False
        return rec
    try:
        if hasattr(os, 'add_dll_directory') and os.path.dirname(dll):
            os.add_dll_directory(os.path.dirname(dll))
        lib = ctypes.CDLL(dll)
        cb_t = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        st_t = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        ex_t = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
        sd_t = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p)
        bg_t = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
        log = []
        f1 = cb_t(lambda s, i, u: (log.append(s.decode(errors='replace')), False)[1])
        f2 = st_t(lambda s, i, u: False)
        f3 = ex_t(lambda a, b, c, d, e: False)
        f4 = sd_t(lambda a, b, c, d: False)
        f5 = sd_t(lambda a, b, c, d: False)
        f6 = bg_t(lambda a, b, c: False)
        keep = (f1, f2, f3, f4, f5, f6)
        lib.ngSpice_Init.restype = ctypes.c_int
        rc = lib.ngSpice_Init(f1, f2, f3, f4, f5, f6, None)
        rec['attempts'].append('attempt 1: ctypes load and ngSpice_Init returned %d' % rc)
    except Exception as e:  # noqa: BLE001
        rec['attempts'].append('attempt 1 failed: %s: %s' % (type(e).__name__, e))
        return rec
    tmp = tempfile.mkdtemp(prefix='gripper_ngspice_')
    out = os.path.join(tmp, 'v.txt').replace('\\', '/')
    p = make_params('A', v('droop_fast_rise_s'))
    cir = _netlist(p, out)
    cirf = os.path.join(tmp, 'droop.cir')
    with open(cirf, 'w', encoding='utf-8', newline='\n') as f:
        f.write(cir)
    try:
        lib.ngSpice_Command.argtypes = [ctypes.c_char_p]
        for cmd in ('source ' + cirf.replace('\\', '/'), 'run', 'wrdata ' + out + ' v(vs) v(vc) v(vp)'):
            rc = lib.ngSpice_Command(cmd.encode())
            rec['attempts'].append('attempt 2: %s -> %d' % (cmd.split()[0], rc))
        if os.path.exists(out):
            d = np.loadtxt(out)
            t, vs, vc, vp = d[:, 0], d[:, 1], d[:, 3], d[:, 5]
            m = t >= v('droop_step_time_s')
            rec['result'] = {'servo_v_min_V': float(vs[m].min()), 'vbuck_min_V': float(vc[m].min()), 'plug_min_V': float(vp[m].min()),
                             'python_servo_v_min_V': None, 'case': 'Fit A, 1000 uF, 10 us rise, 12 V'}
            base = [c for c in r['cases'] if c['params']['fit'] == 'A'
                    and abs(c['params']['rise'] - v('droop_fast_rise_s'))
                    < cm.NUMERICS['ngspice_match_atol_s']][0]
            rec['result']['python_servo_v_min_V'] = base['servo_v_min_V']
            rec['result']['python_vbuck_min_V'] = base['vbuck_min_V']
            rec['result']['python_plug_min_V'] = base['plug_min_V']
            rec['ran'] = True
        else:
            rec['ran'] = False
            rec['attempts'].append('no output file written; engine messages: ' + ' | '.join(log[-4:]))
    except Exception as e:  # noqa: BLE001
        rec['ran'] = False
        rec['attempts'].append('attempt 2 failed: %s: %s' % (type(e).__name__, e))
    return rec


def _netlist(p, out):
    """Behavioural ngspice netlist of the same averaged model (iL carried as a voltage on a 1 F capacitor)."""
    rs = ELEC['r_shunt_ohm']
    x0 = _initial(p)
    beta = ELEC['r_fb_bot_ohm'] / (ELEC['r_fb_top_ohm'] + ELEC['r_fb_bot_ohm'])
    ccer = ELEC['c_out_ceramic_F'] * p['cer_factor']
    r_mot = p['r_mot']
    vin = p['vin']
    L = ELEC['l_buck_H']
    return f"""gripper stall droop (averaged current-mode buck)
.param t0={v('droop_step_time_s')} rise={p['rise']}
Cil il 0 1 ic={x0[0]}
Bil 0 il I=min(max(2.0944e6*(max(min(max(17*(v(comp)-{v('droop_comp_zero_v')}),0),{ilim_typ()})-({vin}-v(vc))*v(vc)/({vin}*{L}*{v('droop_fsw_hz')})/2,0)-v(il)),-(v(vc)+{v('droop_diode_v')})/{L}),({vin}-v(il)*{v('tps_rds_typ')}-v(vc))/{L})
Ccer vc 0 {ccer} ic={x0[1]}
Bin 0 vc I=v(il)
Iload vc 0 {v('droop_5v_load_a')}
Rs vc vs {rs}
Rb vs nb {p['esr_b']}
Cb nb 0 {p['cb']} ic={x0[4]}
Rc vs nl {cable_resistance()}
Lc nl nw {l_cable()}
Rw nw nx {v('c_wrist_esr')}
Cw nx 0 {ELEC['c_wrist_F']} ic={x0[6]}
Rl nw vp {R_LEAD}
Bsrv vp 0 I={v('droop_servo_idle_a')}*(1-min(max((time-t0)/rise,0),1))+min(max((time-t0)/rise,0),1)*v(vp)/{r_mot}
Bea 0 comp I=min(max({v('tps_ea_gm')}*({v('tps_vref')}-{beta}*v(vs)),-{v('tps_ea_imax')}),{v('tps_ea_imax')})
R5 comp n5 {ELEC['r_comp_ohm']}
C5 n5 0 {ELEC['c_comp_F']} ic={x0[3]}
C6 comp 0 {ELEC['c_pole_F']} ic={x0[3]}
.ic v(il)={x0[0]} v(vc)={x0[1]} v(nb)={x0[4]} v(nx)={x0[6]} v(comp)={x0[3]} v(n5)={x0[3]}
.tran 1u {v('droop_end_time_s')} uic
.end
"""


def report(r):
    print('Servo stall step on the 6.58 V rail, averaged current-mode buck (Vin 12 V unless stated)')
    print('Step 0.15 A -> stall at t = %.0f ms; pre-step SERVO_V %.3f V' % (v('droop_step_time_s') * 1e3, r['cases'][0]['servo_v_pre_V']))
    rows = []
    for s in r['cases']:
        p = s['params']
        rows.append([p['fit'], '%.0f us' % (p['rise'] * 1e6)
                     if p['rise'] < v('droop_default_rise_s') else '%.0f ms' % (p['rise'] * 1e3),
                     '%.2f' % s['vbuck_min_V'], '%.2f' % s['servo_v_min_V'],
                     '%.2f' % s['plug_min_V'], '%.2f' % s['plug_final_V'], '%.2f' % (s['recovery_servo_v_s'] * 1e3), '%.2f' % (s['recovery_plug_s'] * 1e3),
                     '%.2f' % s['ipeak_max_A'], '%.2f' % s['i_servo_final_A']])
    print(cm.table(rows, ['fit', 'rise', 'V_BUCK min V', 'SERVO_V min V', 'plug min V', 'plug final V', 'SERVO_V recov ms (0.15 V)', 'plug recov ms',
                          'peak iL A (limit min 6.3)', 'stall A']))
    print('\nBulk capacitor sweep (Fit A, 10 us rise, Cwrist 470 uF unless "no"; bulk ESR 30 mohm x sqrt(1000 uF / C) [A])')
    rows = []
    for s in r['sweep']:
        p = s['params']
        rows.append(['%.0f' % (p['cb'] * 1e6), 'yes' if p['wrist'] else 'no', '%.3f' % p['esr_b'], '%.2f' % s['vbuck_min_V'], '%.2f' % s['servo_v_min_V'], '%.2f' % s['plug_min_V'],
                     '%.2f' % (s['recovery_servo_v_s'] * 1e3), '%.2f' % s['ipeak_max_A'], '%.0f' % (s['bulk_charge_C'] * 1e6)])
    print(cm.table(rows, ['Cbulk uF', 'Cwrist', 'ESR ohm', 'V_BUCK min V', 'SERVO_V min V', 'plug min V', 'recov ms', 'peak iL A', 'bulk charge uC']))
    print('\nFeedback taken before the shunt (at V_BUCK) for comparison, Fit A')
    print(cm.table([['%.0f us' % (s['params']['rise'] * 1e6)
                     if s['params']['rise'] < v('droop_default_rise_s') else '1 ms',
                     '%.2f' % s['vbuck_min_V'], '%.2f' % s['servo_v_min_V'],
                     '%.2f' % s['plug_min_V'], '%.2f' % (s['recovery_servo_v_s'] * 1e3), '%.2f' % s['servo_v_final_V']] for s in r['fb_before']],
                   ['rise', 'V_BUCK min V', 'SERVO_V min V', 'plug min V', 'recov ms', 'SERVO_V final V']))
    for k, lab in (('low_vin', 'Fit A'), ('low_vin_B', 'Fit B')):
        s = r[k]
        print('\nVin 10.8 V, %s, 10 us rise: V_BUCK min %.2f V, SERVO_V min %.2f V, plug min %.2f V, peak iL %.2f A' % (lab, s['vbuck_min_V'], s['servo_v_min_V'], s['plug_min_V'], s['ipeak_max_A']))
    vd = r['verdict']
    print('\nVerdict on 1000 uF: %s. Rule: %s.' % ('ADEQUATE' if vd['adequate'] else 'NOT ADEQUATE', vd['rule']))
    print('  plug minimum: 470 uF %.2f V, 1000 uF %.2f V, 2200 uF %.2f V (2200 gains %.2f V over 1000)' % (vd['plug_min_470_V'], vd['plug_min_1000_V'], vd['plug_min_2200_V'], vd['gain_2200_over_1000_V']))
    print('\nModel limits: averaged (no ripple), first-order inner loop, bulk ESR scaling, 100 mA 5 V load, servo lead 30 mohm: all [A].')


if __name__ == '__main__':
    report(run())
