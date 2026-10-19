"""Shared helpers for the gripper controller calculations (ecad/gripper/calc/).

Evidence tags used in every printed table:
  [S] sourced: datasheet or vendor page, URL and retrieval date in constants.py
  [D] derived: computed by a script in this folder
  [A] assumed: a stated assumption, with the reason, in constants.py or the script

Importing this module puts ecad/gripper on sys.path so `import design` works from any directory.
"""
import json
import re
import math
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
GRIPPER = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(GRIPPER))
for _p in (GRIPPER, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import design  # noqa: E402  (data module, never edited here)
import constants as K  # noqa: E402
import margin_inputs  # noqa: E402

ELEC = margin_inputs.RecordingMapping(design.ELEC, "ELEC", {
    "r_shunt_ohm": "shunt_resistance_ohm", "c_bulk_F": "bulk_capacitance_F",
    "c_wrist_F": "wrist_capacitance_F", "c_out_ceramic_F": "ceramic_capacitance_F",
    "r_fsr_fixed_ohm": "r15_ohm", "l_buck_H": "inductance_H",
})
OUT = os.path.join(HERE, 'out')
FIG = os.path.join(OUT, 'figures')
NUMERICS = {
    'significant_figures': 7,
    'integrated_figures': 5,
    'solver_rtol': 1e-6,
    'solver_atol': 1e-9,
    'exact_tolerance': 0.0,
    'inner_loop_divisor': 6,
    'initial_max_step_s': 20e-6,
    'loaded_max_step_s': 2e-6,
    'dense_window_s': 0.5e-3,
    'dense_sample_step_s': 1e-6,
    'sample_step_s': 10e-6,
    'initial_sample_count': 500,
    'trace_stride': 4,
    'ngspice_match_atol_s': 1e-9,
    'buck_grid_points': 4000,
    'buck_recommend_grid_points': 1200,
    'buck_bode_stride': 8,
    'buck_frequency_min_hz': 1.0,
    'buck_frequency_max_hz': 200000.0,
    'e96_select_tolerance_ohm': 1e-9,
    'fsr_resolution_step_fraction': 1e-4,
}

NUMERICS_SENSITIVITY = {
    'significant_figures': {'class': 'presentation'},
    'integrated_figures': {'class': 'presentation'},
    'solver_rtol': {'class': 'method'},
    'solver_atol': {'class': 'method'},
    'exact_tolerance': {'class': 'presentation'},
    'inner_loop_divisor': {'class': 'method'},
    'initial_max_step_s': {'class': 'method'},
    'loaded_max_step_s': {'class': 'method'},
    'dense_window_s': {'class': 'method'},
    'dense_sample_step_s': {'class': 'method'},
    'sample_step_s': {'class': 'method'},
    'initial_sample_count': {'class': 'method'},
    'trace_stride': {'class': 'method'},
    'ngspice_match_atol_s': {'class': 'method'},
    'buck_grid_points': {'class': 'method'},
    'buck_recommend_grid_points': {'class': 'method'},
    'buck_bode_stride': {'class': 'method'},
    'buck_frequency_min_hz': {'class': 'method'},
    'buck_frequency_max_hz': {'class': 'method'},
    'e96_select_tolerance_ohm': {'class': 'method'},
    'fsr_resolution_step_fraction': {'class': 'method'},
}

# A number is integrated if an ODE/root/iteration produced it, or it is derived
# from such a number. Everything else is exact closed-form arithmetic. Patterns
# are checked before the per-file top-level schema below.
INTEGRATED_PATTERNS = {
    'droop_sim.json': (
        'cases[*].*', 'sweep[*].*', 'fb_before[*].*', 'low_vin.*', 'low_vin_B.*', 'verdict.*',
    ),
    'power_budget.json': ('esp_stall_vbuck_min', 'ldo_min_input_V', 'esp_board_power[*].*', 'bulk.stall_*', 'bulk.servo_v_dip_V', 'bulk.verdict.*'),
    'margins.json': ('rows[11].limit', 'rows[11].margin'),
}
EXACT_PATTERNS = {
    'droop_sim.json': ('cases[*].params.*', 'sweep[*].params.*', 'fb_before[*].params.*',
                       'low_vin.params.*', 'low_vin_B.params.*', 'cases[*].ilim_min_A', 'sweep[*].ilim_min_A',
                       'fb_before[*].ilim_min_A', 'low_vin.ilim_min_A', 'low_vin_B.ilim_min_A',
                       'cases[*].trace.t_ms[*]'),
}

# Top-level keys are the explicit schema. Adding a new stored key requires a
# declaration here; integrated patterns override exact descendants.
OUTPUT_SCHEMA = {
    name: frozenset(json.loads(Path(OUT, name).read_text(encoding='utf-8'))) for name in (
        'buck_design.json', 'constants.json', 'droop_sim.json', 'fault_limit.json',
        'fsr_frontend.json', 'harness.json',
        'ina219_budget.json', 'margins.json', 'open_requirements.json', 'pinmap_check.json',
        'power_budget.json', 'trace_width.json',
    )
}
OUTPUT_SCHEMA['margins.json'] = frozenset({'rows', 'faults', 'counts'})


def set_output_dir(path):
    """Set the destination used by every calculation artifact writer."""
    global OUT, FIG
    OUT = os.path.abspath(path)
    FIG = os.path.join(OUT, 'figures')

class FitsView:
    """Motor-fit view whose physical values are read at calculation time."""

    def __getitem__(self, fit):
        values = {
            'A': {'R': v('fit_a_resistance_ohm'), 'K': v('fit_a_torque_nm_per_a'),
                  'stall_A': margin_inputs.read('servo_stall_fit_A'), 'hold_A': v('fit_a_hold_a')},
            'B': {'R': v('fit_b_resistance_ohm'), 'K': v('fit_b_torque_nm_per_a'),
                  'stall_A': v('fit_b_stall_a'), 'hold_A': v('fit_b_hold_a')},
        }
        return values[fit]


FITS = FitsView()


def v_input(name):
    return margin_inputs.read(name)


def v(name):
    margin_inputs.record(name)
    return K.C[name]['value']


def servo_torque(force_n):
    """Servo output torque for a pad force: T = 2 F r_c / eta (DESIGN-BASIS, config.h)."""
    return 2.0 * force_n * v('gripper_pad_radius_m') / v('gripper_train_efficiency')


def servo_current_at_force(force_n, fit):
    """Servo current holding a pad force: T/K plus the offset implied by dyno.md's hold point [D].

    The dyno hold row gives current at 0.758 N*m; the part of it not explained by T/K is a constant
    (friction / no-load) offset, kept here. offset_A = hold_A - 0.758/K.
    """
    f = FITS[fit]
    off = f['hold_A'] - v('servo_hold_torque_nm') / f['K']
    return servo_torque(force_n) / f['K'] + off


def servo_current_ideal(force_n, fit):
    """Servo current from T/K alone (no offset) [D]."""
    return servo_torque(force_n) / FITS[fit]['K']


def fsr_r(force_n):
    """FSR resistance from the firmware power-law fit (config.h) [D]."""
    return v('fsr_fit_r1n_ohm') * force_n ** (-v('fsr_fit_exponent'))


def node_mv(force_n, r_fixed=None, vcc_mv=None):
    """Divider node voltage 3V3 - FSR - node - R_fixed - GND, in mV."""
    margin_inputs.record_module("fsr_frontend")
    r = ELEC['r_fsr_fixed_ohm'] if r_fixed is None else r_fixed
    vcc_mv = v('fsr_default_vcc_mv') if vcc_mv is None else vcc_mv
    return vcc_mv * r / (r + fsr_r(force_n))


def table(rows, headers, fmt=None):
    """Plain left-aligned text table; `fmt` maps column index -> format string."""
    fmt = fmt or {}
    cells = [[str(h) for h in headers]]
    for row in rows:
        cells.append([(fmt[i] % x if (i in fmt and isinstance(x, (int, float))) else str(x)) for i, x in enumerate(row)])
    w = [max(len(r[i]) for r in cells) for i in range(len(headers))]
    lines = []
    for k, r in enumerate(cells):
        lines.append('  '.join(c.ljust(w[i]) for i, c in enumerate(r)).rstrip())
        if k == 0:
            lines.append('  '.join('-' * w[i] for i in range(len(headers))))
    return '\n'.join(lines)


def jsonable(o):
    """Convert numpy scalars / arrays / complex to plain JSON types."""
    try:
        import numpy as np
    except ImportError:
        np = None
    if isinstance(o, dict):
        return {str(k): jsonable(x) for k, x in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(x) for x in o]
    if np is not None:
        if isinstance(o, np.ndarray):
            return jsonable(o.tolist())
        if isinstance(o, np.generic):
            return jsonable(o.item())
    if isinstance(o, complex):
        return {'re': o.real, 'im': o.imag}
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            return str(o)
        return float(format(o, '.%dg' % NUMERICS['significant_figures']))
    if isinstance(o, str):
        value = o.replace('\\', '/')
        repo = REPO.replace('\\', '/').rstrip('/') + '/'
        return value.replace(repo, '')
    return o


def value_class(filename, key):
    """Return exact/integrated for a declared numeric key; reject unknown roots."""
    root = key.split('.', 1)[0].split('[', 1)[0]
    if filename == 'numerics_sensitivity.json':
        return 'exact'
    if filename == 'constants.json' and root in K.C:
        return 'exact'
    if filename not in OUTPUT_SCHEMA or root not in OUTPUT_SCHEMA[filename]:
        raise KeyError('unclassified numeric key %s:%s' % (filename, key))
    normalized = re.sub(r'\[\d+\]', '[*]', key)
    exact = EXACT_PATTERNS.get(filename, ())
    if any(normalized == p or (p.endswith('.*') and normalized.startswith(p[:-1])) for p in exact):
        return 'exact'
    patterns = INTEGRATED_PATTERNS.get(filename, ())
    matched = any(normalized == p or (p.endswith('.*') and normalized.startswith(p[:-1])) for p in patterns)
    return 'integrated' if matched else 'exact'


def tolerance(filename, key, committed, generated):
    """Solver-derived tolerance: 100*LSODA rtol plus 100*atol."""
    if value_class(filename, key) != 'integrated':
        return NUMERICS['exact_tolerance']
    return 100 * NUMERICS['solver_atol'] + 100 * NUMERICS['solver_rtol'] * max(abs(committed), abs(generated))


def stored_float(value, value_kind='exact'):
    figures = NUMERICS['integrated_figures'] if value_kind == 'integrated' else NUMERICS['significant_figures']
    return float(format(value, '.%dg' % figures))


def classified_jsonable(filename, value, key=''):
    """Convert JSON data while applying the declared precision to each float."""
    if isinstance(value, dict):
        return {str(k): classified_jsonable(filename, v, '%s.%s' % (key, k) if key else str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [classified_jsonable(filename, v, '%s[%d]' % (key, i)) for i, v in enumerate(value)]
    converted = jsonable(value)
    if isinstance(converted, float):
        return stored_float(converted, value_class(filename, key))
    return converted


def classified_values(filename, value, key=''):
    """Round floats by class without changing containers used by reports."""
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None and isinstance(value, np.ndarray):
        return classified_values(filename, value.tolist(), key)
    if np is not None and isinstance(value, np.generic):
        return classified_values(filename, value.item(), key)
    if isinstance(value, dict):
        return {k: classified_values(filename, v, '%s.%s' % (key, k) if key else str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [classified_values(filename, v, '%s[%d]' % (key, i)) for i, v in enumerate(value)]
    if isinstance(value, tuple):
        return tuple(classified_values(filename, v, '%s[%d]' % (key, i)) for i, v in enumerate(value))
    if isinstance(value, float) and math.isfinite(value):
        return stored_float(value, value_class(filename, key))
    return value


def write_text(relative_path, text, encoding='utf-8'):
    """The sole writer for calculation evidence: UTF-8 with LF endings."""
    path = Path(OUT, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = text.replace('\r\n', '\n').replace('\r', '\n').encode(encoding)
    if not path.exists() or path.read_bytes() != content:
        path.write_bytes(content)


def write_json(name, res):
    filename = name + '.json'
    text = json.dumps(classified_jsonable(filename, res), indent=1, sort_keys=True, ensure_ascii=False) + '\n'
    write_text(name + '.json', text)
