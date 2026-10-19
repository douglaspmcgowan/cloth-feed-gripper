"""droop_sim.py: limit cases and the closed-form steady state."""
import math

import numpy as np

import _common as cm
import droop_sim as ds
from _common import ELEC
import buck_design as bd


def test_no_step_gives_no_droop():
    p = ds.make_params('A', rise=1e6)                 # the ramp never starts: servo stays at 0.15 A
    s = ds.simulate(p, t_end=6e-3)
    assert abs(s['servo_v_min_V'] - s['servo_v_pre_V']) < 2e-3
    assert abs(s['vbuck_min_V'] - s['vbuck_max_V']) < 5e-3
    assert math.isclose(s['servo_v_pre_V'], 6.584, abs_tol=0.01)       # hand: 0.8 x 8.23


def test_infinite_capacitance_gives_no_droop_at_servo_v():
    p = ds.make_params('A', rise=10e-6, cb=10.0, esr_b=1e-4)           # 10 F: dV = I t / C = 3.4 A x 12 ms / 10 F = 4 mV
    s = ds.simulate(p, t_end=6e-3)
    assert s['servo_v_pre_V'] - s['servo_v_min_V'] < 0.015


def test_steady_state_stall_matches_the_closed_form():
    p = ds.make_params('A', rise=100e-6)
    s = ds.simulate(p, t_end=15e-3)
    rm = 1.80
    rw = bd.cable_resistance() + bd.R_LEAD
    expect = 6.584 * rm / (rm + rw)                                    # plug = Vset Rm / (Rm + R_cable + R_lead)
    assert math.isclose(s['plug_final_V'], expect, abs_tol=0.03)
    assert math.isclose(s['i_servo_final_A'], expect / rm, rel_tol=0.02)
    # shunt sits inside the loop: SERVO_V returns to the set point
    assert math.isclose(s['servo_v_final_V'], 6.584, abs_tol=0.03)


def test_feedback_before_shunt_loses_the_shunt_drop():
    a = ds.simulate(ds.make_params('A', rise=100e-6), t_end=15e-3)
    b = ds.simulate(ds.make_params('A', rise=100e-6, fb_before_shunt=True), t_end=15e-3)
    # regulating V_BUCK instead: SERVO_V ends lower by about I_stall x 0.1 ohm (+ the 100 mA 5 V load)
    assert a['servo_v_final_V'] - b['servo_v_final_V'] > 0.25


def test_peak_current_stays_below_the_ic_limit_and_fit_b_is_lighter():
    a = ds.simulate(ds.make_params('A', rise=10e-6), t_end=8e-3)
    b = ds.simulate(ds.make_params('B', rise=10e-6), t_end=8e-3)
    assert a['ipeak_max_A'] < ds.ilim_min()
    assert b['ipeak_max_A'] < a['ipeak_max_A']
    assert b['plug_min_V'] > a['plug_min_V']


def test_ngspice_netlist_is_generated():
    net = ds._netlist(ds.make_params('A', rise=10e-6), 'x.txt')
    assert '.tran' in net and 'Bil' in net and 'Cb nb 0' in net


def test_droop_floor_is_the_power_budget_ldo_minimum_input(monkeypatch):
    import power_budget
    assert 'droop_vbuck_min_v' not in cm.K.C
    r = ds.run()
    assert r['verdict']['vbuck_floor_V'] == power_budget.ldo_min_input_V()
    monkeypatch.setattr(power_budget, 'ldo_min_input_V', lambda: 9.0)
    assert ds.verdict(r)['adequate'] is False
