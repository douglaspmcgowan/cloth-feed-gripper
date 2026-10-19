"""power_budget.py: hand calculations and limit cases."""
import math

import _common as cm
import buck_design as bd
import power_budget as pb
from _common import ELEC, v


def test_cable_resistance_by_hand():
    # 20 AWG 33.31 mohm/m x 1.2 m x 2 conductors = 79.9 mohm; 26 AWG 133.9 mohm/m -> 321.4 mohm
    assert math.isclose(bd.cable_resistance(), 0.0799, rel_tol=0.005)
    assert math.isclose(pb.r_cable_26(), 0.3214, rel_tol=0.005)


def test_zero_load_gives_zero_drop():
    # no current -> the servo terminals sit at the set point exactly
    assert pb.servo_current('A', 'idle', 6.584, 0.0) == v('servo_idle_a')
    vs = 6.584
    assert vs - 0.0 * bd.cable_resistance() == vs


def test_stall_is_a_resistive_divider():
    rw = bd.cable_resistance() + bd.R_LEAD
    i = pb.servo_current('A', 'stall', 6.584, rw)
    assert math.isclose(i, 6.584 / (1.80 + rw), rel_tol=1e-12)
    # plug voltage is the divider Rm / (Rm + Rw)
    assert math.isclose(6.584 - i * rw, 6.584 * 1.80 / (1.80 + rw), rel_tol=1e-12)
    # a bigger wire resistance (26 AWG) lowers the stall plug voltage
    i26 = pb.servo_current('A', 'stall', 6.584, pb.r_cable_26() + bd.R_LEAD)
    assert 6.584 - i26 * (pb.r_cable_26() + bd.R_LEAD) < 6.584 - i * rw


def test_input_power_energy_balance():
    pt = pb.input_point(12.0, 1.35)
    assert pt['pin_W'] > pt['pout_W']                              # losses are positive
    assert 0.85 < pt['eff'] < 0.99
    # hand: P_out = V_buck x (I_servo + I_5V) = (6.584 + 0.135) x (1.35 + 0.094) = 9.70 W
    assert math.isclose(pt['pout_W'], (6.584 + 0.135) * (1.35 + pb.i5_typ()), rel_tol=0.001)
    assert pt['iin_A'] * 12.0 > pt['pout_W']
    # higher input voltage -> lower input current
    assert pb.input_point(13.2, 1.35)['iin_A'] < pb.input_point(10.8, 1.35)['iin_A']


def test_regen_energy_balance():
    c = 1000e-6
    e = 0.020
    vend = math.sqrt(6.584 ** 2 + 2 * e / c)               # 1/2 C (V2^2 - V1^2) = E
    assert math.isclose(0.5 * c * (vend ** 2 - 6.584 ** 2), e, rel_tol=1e-12)
    # zero energy: no rise, infinite capacitance: no rise
    assert math.isclose(math.sqrt(6.584 ** 2 + 0.0), 6.584)
    assert math.sqrt(6.584 ** 2 + 2 * e / 1e9) - 6.584 < 1e-6


def test_fsr_reading_round_trip_and_rail_error():
    for f in (0.5, 5.0, 8.0):
        assert math.isclose(pb.fsr_reading(f), f, rel_tol=1e-9)    # exact 3300 mV rail, no ground offset: reads true
    assert pb.fsr_reading(5.0, vcc_mv=3333.0) > 5.0                 # high rail reads high
    assert pb.fsr_reading(5.0, vcc_mv=3267.0) < 5.0
    assert pb.fsr_reading(5.0, dvg_mv=100.0) > 5.0                  # positive ground offset reads high
    # hand: 1 % rail error changes the node by 1 % = 20.6 mV at 5 N; slope 0.0079 N/mV -> +0.16 N
    assert math.isclose(pb.fsr_reading(5.0, vcc_mv=3333.0) - 5.0, 0.165, abs_tol=0.01)


def test_run_end_to_end():
    r = pb.run()
    a = r['adapter']
    assert 2.0 < a['worst_input_A'] < 3.0                           # Fit A stall at 10.8 V
    assert a['rating_with_25pct_margin_A'] > a['worst_input_A']
    low = [x for x in r['plug'] if x['awg'] == 26 and x['fit'] == 'A' and x['scenario'] == 'hold'][0]
    ok20 = [x for x in r['plug'] if x['awg'] == 20 and x['fit'] == 'A' and x['scenario'] == 'hold'][0]
    assert ok20['in_band'] and not low['in_band']                   # 20 AWG holds the band at hold, 26 AWG does not
    chain = r['esp_board_power'][0]
    assert chain['margin_bod_V'] > 0.5
