"""ina219_budget.py: error terms, saturation, chopped current limit cases."""
import math
import re
from pathlib import Path

import _common as cm
import constants as K
import ina219_budget as ib
from _common import FITS


def test_offset_term_by_hand():
    terms, vsh = ib.error_terms(1.8)
    assert math.isclose(vsh, 0.18, rel_tol=1e-12)                       # 1.8 A x 0.1 ohm
    a, f = terms['offset, PGA /8, 200 uV max [S]']
    assert math.isclose(a, 200e-6 / 0.1, rel_tol=1e-12)                 # 2 mA
    assert math.isclose(f, 0.0020 / 1.8, rel_tol=1e-9)


def test_worst_case_is_the_sum_and_rss_is_smaller():
    b = ib.budget()
    assert math.isclose(b['worst_A'], sum(a for a, _ in b['terms'].values()), rel_tol=1e-12)
    assert b['rss_A'] < b['worst_A']
    assert math.isclose(b['rss_A'], math.sqrt(sum(a * a for a, _ in b['terms'].values())), rel_tol=1e-12)
    # 3.0 A: worst-case sum 0.0638 A (2.13 %); range 2.9375 to 3.0652 A, width 0.1277 A
    lo, hi = b['true_trip_range_worst_A']
    assert lo < 3.0 < hi and hi - lo < 0.13


def test_saturation_by_hand():
    r = ib.run()
    assert math.isclose(r['shunt_fs_A'], 3.2, rel_tol=1e-12)           # 320 mV / 0.1 ohm
    assert r['saturation']['saturates'] is True                         # 3.77 A x 0.1 = 377 mV > 320 mV
    assert r['saturation']['fit_B_saturates'] is False
    # a saturated reading (3.2 A x (1 - 1 %) = 3.168 A) still exceeds the 3.0 A trip, so a stall trips
    assert math.isclose(3.2 * (1 - 0.01), 3.168, rel_tol=1e-12)
    assert 3.168 > 3.0
    assert r['saturation']['still_trips'] is True


def test_hold_torque_and_current_by_hand():
    # T = 2 F r_c / eta = 2 x 10 x 0.065 / 0.85 = 1.5294 N*m; Fit A K 0.861 -> 1.776 A
    assert math.isclose(cm.servo_torque(10.0), 1.5294, rel_tol=1e-3)
    assert math.isclose(cm.servo_current_ideal(10.0, 'A'), 1.776, rel_tol=2e-3)
    # the offset form reproduces the dyno.md hold point at the 0.758 N*m torque
    f = 0.758 * 0.85 / (2 * 0.065)
    assert math.isclose(cm.servo_current_at_force(f, 'A'), 1.35, rel_tol=1e-9)
    assert math.isclose(cm.servo_current_at_force(f, 'B'), 0.80, rel_tol=1e-9)


def test_chopped_current_limit_cases():
    # a window that is a whole number of chop periods reads the mean exactly
    lo, hi, mean = ib.chopped_error(1000.0, 0.5, w=4e-3)
    assert math.isclose(lo, 0.5, rel_tol=1e-9) and math.isclose(hi, 0.5, rel_tol=1e-9) and mean == 0.5
    # a window much shorter than the period reads the instantaneous value: 0 or 1
    lo, hi, _ = ib.chopped_error(10.0, 0.5, w=0.1e-3)
    assert lo == 0.0 and hi == 1.0
    # a window longer than the period: the spread shrinks as 1 / (periods)
    lo1, hi1, _ = ib.chopped_error(1000.0, 0.5, w=1.3e-3)
    lo2, hi2, _ = ib.chopped_error(1000.0, 0.5, w=17.02e-3)
    assert (hi2 - lo2) < (hi1 - lo1)


def test_recommended_configuration_register():
    r = ib.run()
    assert r['config']['default'] == '0x399F'
    new = int(r['config']['recommended'], 16)
    assert (new >> 3) & 0xF == 0xD                                      # SADC = 1101: 12-bit, 32 samples
    assert (new >> 11) & 3 == 3                                         # PGA stays /8
    assert new & 7 == 7                                                 # continuous mode kept
    n32 = [a for a in r['averaging'] if a['samples'] == 32][0]
    assert n32['fits_20ms'] and math.isclose(n32['time_ms'], 17.02, rel_tol=2e-3)
    assert math.isclose(r['delay']['max_s'], 0.1206, rel_tol=1e-3)


def test_hold_current_is_below_the_3_0_a_trip_at_10_n():
    # 3.0 A trip: Fit A hold at 10 N with offset is 2.246 A (below 3.0 A, so a legitimate grip does not stall)
    r = ib.run()
    assert r['hold'][10.0]['A']['with_offset_A'] < ib.TRIP_A
    assert r['hold'][10.0]['B']['with_offset_A'] < ib.TRIP_A


FW_DIR = Path(cm.REPO) / 'firmware/gripper'


def _config_value(name):
    m = re.search(r'^#define\s+' + name + r'\s+([0-9.]+)', (FW_DIR / 'config.h').read_text(encoding='utf-8'), re.M)
    assert m, name
    return float(m.group(1))


def test_force_ctrl_saturation_literals_match_constants():
    # force_ctrl.h INA219_SAT_READING_MIN_A = FS x (1 - gain error) - offset / shunt, literals duplicate constants.py
    text = (FW_DIR / 'force_ctrl.h').read_text(encoding='utf-8')
    m = re.search(r'#define\s+INA219_SAT_READING_MIN_A\s+\(INA219_FS_A \* \(1\.0 - ([0-9.eE+-]+)\) - ([0-9.eE+-]+) / INA219_SHUNT_OHM\)', text)
    assert m
    assert math.isclose(float(m.group(1)), K.val('ina_saturation_error_fraction'), rel_tol=1e-12)
    assert math.isclose(float(m.group(2)), K.val('ina_vos_pga8'), rel_tol=1e-12)
    fs = re.search(r'#define\s+INA219_FS_A\s+\(([0-9.]+) / INA219_SHUNT_OHM\)', text)
    assert fs and math.isclose(float(fs.group(1)), K.val('ina_fs_pga8'), rel_tol=1e-12)
    assert math.isclose(_config_value('INA219_SHUNT_OHM'), ib.rshunt(), rel_tol=1e-12)


def test_hold_trip_below_worst_saturated_reading():
    worst = K.val('ina_fs_pga8') / ib.rshunt() * (1 - K.val('ina_saturation_error_fraction')) - K.val('ina_vos_pga8') / ib.rshunt()
    assert math.isclose(worst, 3.166, abs_tol=1e-3)
    assert _config_value('STALL_CURRENT_HOLD_A') < worst
    assert _config_value('STALL_CURRENT_A') < worst


def test_force_caps_are_sizing_constant_then_r15():
    caps = K.val('ina_force_caps_n')
    assert caps == (_config_value('F_CAP_N'), K.val('harness_fsr_force_cap_n')) == (10.0, 8.0)
