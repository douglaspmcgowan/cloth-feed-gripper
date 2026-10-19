"""Regenerate every number and figure of the gripper controller calculations.

Run from the repository root: python ecad/gripper/calc/run_all.py

Runs each script in order, writes out/<name>.json (results) and out/<name>.txt (what the script prints), then the figures under
out/figures/. Exit status 0 only if every script ran. Deterministic: no random numbers are used anywhere.
"""
import argparse
import contextlib
import importlib
import io
import os
import sys
import time
import traceback
import tempfile
import json
import shutil
import gc
import subprocess
from pathlib import Path

import _common as cm
import release_artifacts
import margin_inputs

ORDER = ['constants', 'power_budget', 'buck_design', 'fsr_frontend', 'ina219_budget', 'trace_width',
         'droop_sim', 'open_requirements', 'fault_limit', 'margins', 'pinmap_check', 'harness']
REFERENCE = None
NUMERIC_DIFFERENCES = []
KEPT_VALUES = []


def _clear_calculation_caches():
    for module_name in ORDER:
        module = sys.modules.get(module_name)
        if not module:
            continue
        for value in vars(module).values():
            clear = getattr(value, 'cache_clear', None)
            if clear:
                clear()


def _sensitivity_value(value, factor):
    if isinstance(value, tuple):
        return tuple(_sensitivity_value(item, factor) for item in value)
    changed = value * factor
    return max(1, round(changed)) if isinstance(value, int) else changed


def _first_stored_difference(left, right, key=''):
    if type(left) is not type(right):
        return key or '<root>'
    if isinstance(left, dict):
        if set(left) != set(right):
            return key or '<root>'
        for child in sorted(left):
            found = _first_stored_difference(
                left[child], right[child], '%s.%s' % (key, child) if key else child)
            if found:
                return found
    elif isinstance(left, list):
        if len(left) != len(right):
            return key + '.length'
        for index, (a, b) in enumerate(zip(left, right)):
            found = _first_stored_difference(a, b, '%s[%d]' % (key, index))
            if found:
                return found
    elif left != right:
        return key or '<root>'
    return None


def _module_result(name):
    _clear_calculation_caches()
    module = importlib.import_module(name)
    with margin_inputs.recording():
        return cm.classified_jsonable(name + '.json', module.run())


def _isolated_module_result(name, entry=None, value=None):
    with tempfile.TemporaryDirectory() as temporary_directory:
        output = Path(temporary_directory, 'result.json')
        command = [sys.executable, __file__, '--sensitivity-worker', name,
                   '--sensitivity-output', str(output)]
        if entry is not None:
            command.extend(('--sensitivity-setting', entry,
                            '--sensitivity-value', json.dumps(value)))
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError(completed.stderr or completed.stdout)
        return json.loads(output.read_text(encoding='utf-8'))


def _isolated_difference(name, entry, value):
    command = [sys.executable, __file__, '--sensitivity-compare', name,
               '--sensitivity-setting', entry, '--sensitivity-value', json.dumps(value)]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr or completed.stdout)
    return completed.stdout.strip() or None


def numerics_sensitivity(entries=None, write_table=False):
    """Measure convergence against the scalar quantities used by margin rows."""
    import numerics_sensitivity as ns
    try:
        table, failures = ns.measure(entries)
    except (ValueError, RuntimeError) as error:
        print('numerics sensitivity FAIL: %s' % error)
        return 1
    target = Path(cm.HERE, 'out/numerics_sensitivity.json')
    if write_table and not entries:
        ns.write_table(table, target)
    for entry, details in table['entries'].items():
        worst = max((run['worst']['fraction_of_margin'] for run in details['runs']), default=0)
        print('%s method: worst fraction %.9g' % (entry, worst))
    if failures:
        entry, factor, item = failures[0]
        print('numerics sensitivity FAIL: %s %sx row %s measured fraction %.9g' %
              (entry, factor, item['row'], item['fraction_of_margin']))
        return 1
    if not write_table and target.exists():
        committed = json.loads(target.read_text(encoding='utf-8'))
        for entry in table['entries']:
            difference = ns.comparison_difference(
                committed.get('entries', {}).get(entry), table['entries'].get(entry), entry)
            if difference:
                print('numerics sensitivity FAIL: %s' % difference)
                return 1
    print('numerics sensitivity: %d method entries passed' % len(table['entries']))
    return 0


def reconcile(filename, committed, generated, key=''):
    """Keep tolerably equal integrated values; exact values remain byte-strict."""
    if type(committed) is not type(generated):
        return generated
    if isinstance(generated, dict):
        if set(committed) != set(generated):
            return generated
        return {k: reconcile(filename, committed[k], generated[k], '%s.%s' % (key, k) if key else k) for k in generated}
    if isinstance(generated, list):
        if len(committed) != len(generated):
            return generated
        return [reconcile(filename, a, b, '%s[%d]' % (key, i)) for i, (a, b) in enumerate(zip(committed, generated))]
    if isinstance(generated, float) and cm.value_class(filename, key) == 'integrated':
        limit = cm.tolerance(filename, key, committed, generated)
        if abs(committed - generated) <= limit:
            if committed != generated:
                KEPT_VALUES.append((filename, key, abs(committed - generated) / max(abs(generated), 1e-30)))
            return committed
        NUMERIC_DIFFERENCES.append((filename, key, committed, generated, limit))
    return generated


def run_one(name, results):
    mod = importlib.import_module(name)
    buf = io.StringIO()
    t0 = time.time()
    with contextlib.redirect_stdout(buf):
        with margin_inputs.recording() as observed:
            raw = mod.run()
            if name == 'margins':
                raw = _add_numerical_sensitivity(raw)
        margin_inputs.MODULE_READS[name] = {
            item for item in observed if not item.startswith('module:')
        }
        if name == 'fault_limit':
            cm.OUTPUT_SCHEMA['fault_limit.json'] = frozenset(raw)
        res = cm.classified_values(name + '.json', raw)
        wanted = Path(REFERENCE, name + '.json') if REFERENCE else None
        if wanted and wanted.exists():
            res = reconcile(name + '.json', json.loads(wanted.read_text(encoding='utf-8')), res)
        mod.report(res)
    text = buf.getvalue()
    cm.write_text(name + '.txt', text, encoding='utf-8')
    cm.write_json(name, res)
    results[name] = res
    print('%-18s ok  %5.1f s  %d lines' % (name, time.time() - t0, text.count('\n')))


def _add_numerical_sensitivity(result):
    """Attach measured row evidence when a current convergence table exists."""
    import numerics_sensitivity as ns
    path = Path(cm.HERE, 'out/numerics_sensitivity.json')
    if path.exists():
        table = json.loads(path.read_text(encoding='utf-8'))
        values = ns.row_sensitivities(table, [row['id'] for row in result['rows']])
    else:
        values = {row['id']: {'fraction_of_margin': 0.0, 'cause': ''}
                  for row in result['rows']}
    for row in result['rows']:
        row['numerical_sensitivity'] = values[row['id']]
    return result


def figures(res):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    import fsr_frontend as ff
    os.makedirs(cm.FIG, exist_ok=True)
    made = []

    # 1. FSR node voltage against force
    fig, ax = plt.subplots(figsize=(7, 4.2))
    f = np.logspace(np.log10(0.1), np.log10(12), 200)
    for r_fixed, lab in ((2700.0, 'R15 2.70 k (design)'), (2610.0, '2.61 k (10 N cap, E96)'), (3160.0, '3.16 k (8 N cap, E96)')):
        ax.plot(f, [cm.node_mv(x, r_fixed) for x in f], label=lab)
    ax.axhspan(150, 2450, color='0.9', label='ADC span 150 to 2450 mV')
    ax.axvline(8, color='k', ls=':', lw=0.8)
    ax.axvline(10, color='k', ls=':', lw=0.8)
    ax.set_xscale('log')
    ax.set_xlabel('pad force (N)')
    ax.set_ylabel('FSR node voltage (mV)')
    ax.set_title('FSR node voltage against force (3.3 V supply, firmware power-law fit)')
    ax.legend(fontsize=8)
    ax.grid(True, which='both', alpha=0.3)
    p = os.path.join(cm.FIG, 'fsr_node_vs_force.png')
    fig.tight_layout()
    fig.savefig(p, dpi=110)
    plt.close(fig)
    made.append(p)

    # 2. filter magnitude response
    fig, ax = plt.subplots(figsize=(7, 4.2))
    fr = np.logspace(0, 3.4, 300)
    for force in (0.0, 0.5, 5.0, 10.0):
        pt = ff.filter_point(force)
        ax.plot(fr, 20 * np.log10(1 / np.sqrt(1 + (fr / pt['fc_Hz']) ** 2)), label=('open FSR' if not force else '%g N' % force) + ' (fc %.0f Hz)' % pt['fc_Hz'])
    ax.axvline(500, color='k', ls=':', lw=0.8)
    ax.set_xscale('log')
    ax.set_xlabel('frequency (Hz)')
    ax.set_ylabel('gain (dB)')
    ax.set_title('Anti-alias filter R16 + (R15 || FSR), C17; dotted line = 500 Hz Nyquist')
    ax.legend(fontsize=8)
    ax.grid(True, which='both', alpha=0.3)
    p = os.path.join(cm.FIG, 'filter_response.png')
    fig.tight_layout()
    fig.savefig(p, dpi=110)
    plt.close(fig)
    made.append(p)

    # 3. Bode
    b = res['buck_design']['bode']
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
    for lab, m, ph in (('nominal (1 A, 12 V)', b['nom_mag_dB'], b['nom_ph_deg']), ('worst phase-margin corner', b['worst_mag_dB'], b['worst_ph_deg'])):
        a1.semilogx(b['f'], m, label=lab)
        a2.semilogx(b['f'], ph, label=lab)
    a1.axhline(0, color='k', lw=0.8)
    a2.axhline(-135, color='r', ls=':', lw=0.8, label='45 deg phase margin')
    a2.axhline(-180, color='k', lw=0.8)
    a1.set_ylabel('loop gain (dB)')
    a2.set_ylabel('phase (deg)')
    a2.set_xlabel('frequency (Hz)')
    a1.set_title('Loop gain T(s): compensator R5 27.4 k, C5 22 nF, C6 470 pF, feedback at SERVO_V')
    a1.legend(fontsize=8)
    a2.legend(fontsize=8)
    a1.grid(True, which='both', alpha=0.3)
    a2.grid(True, which='both', alpha=0.3)
    p = os.path.join(cm.FIG, 'loop_bode.png')
    fig.tight_layout()
    fig.savefig(p, dpi=110)
    plt.close(fig)
    made.append(p)

    # 4. stall-droop transient
    ds = res['droop_sim']
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
    for s, ls in ((ds['cases'][0], '-'), (ds['cases'][1], '--')):
        t = s['trace']
        lab = '%s rise' % ('1 ms' if s['params']['rise'] > 5e-4 else '10 us')
        a1.plot(t['t_ms'], t['vbuck'], ls, color='C0', label='V_BUCK, ' + lab)
        a1.plot(t['t_ms'], t['servo_v'], ls, color='C1', label='SERVO_V, ' + lab)
        a1.plot(t['t_ms'], t['plug'], ls, color='C2', label='servo plug, ' + lab)
        a2.plot(t['t_ms'], t['iL'], ls, color='C3', label='inductor current, ' + lab)
        a2.plot(t['t_ms'], t['i_servo'], ls, color='C4', label='servo current, ' + lab)
    a2.axhline(6.3, color='r', ls=':', lw=0.8, label='current limit, min 6.3 A')
    a1.set_xlim(-0.2, 3)
    a1.set_ylabel('volts')
    a2.set_ylabel('amps')
    a2.set_xlabel('time after the stall step (ms)')
    a1.set_title('Fit A stall step, 1000 uF bulk + 470 uF forearm capacitor, 12 V in')
    a1.legend(fontsize=7)
    a2.legend(fontsize=7)
    a1.grid(True, alpha=0.3)
    a2.grid(True, alpha=0.3)
    p = os.path.join(cm.FIG, 'droop_transient.png')
    fig.tight_layout()
    fig.savefig(p, dpi=110)
    plt.close(fig)
    made.append(p)

    # 5. droop against bulk capacitance
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for wrist, ls in ((True, '-'), (False, '--')):
        rows = [s for s in ds['sweep'] if s['params']['wrist'] == wrist]
        c = [s['params']['cb'] * 1e6 for s in rows]
        ax.plot(c, [s['plug_min_V'] for s in rows], 'o' + ls, color='C2', label='servo plug minimum, %s 470 uF forearm' % ('with' if wrist else 'without'))
        ax.plot(c, [s['servo_v_min_V'] for s in rows], 's' + ls, color='C1', label='SERVO_V minimum, %s forearm' % ('with' if wrist else 'without'))
    ax.axhline(4.8, color='r', ls=':', lw=0.8, label='servo minimum 4.8 V')
    ax.set_xscale('log')
    ax.set_xlabel('bulk capacitance C12 (uF)')
    ax.set_ylabel('minimum voltage in a Fit A, 10 us stall step (V)')
    ax.set_title('Stall droop against bulk capacitance')
    ax.legend(fontsize=7)
    ax.grid(True, which='both', alpha=0.3)
    p = os.path.join(cm.FIG, 'droop_vs_cbulk.png')
    fig.tight_layout()
    fig.savefig(p, dpi=110)
    plt.close(fig)
    made.append(p)
    return made


def generate(make_figures=False, make_ngspice=False, note_path=None):
    results = {}
    failed = []
    for name in ORDER:
        try:
            run_one(name, results)
        except Exception:  # noqa: BLE001
            failed.append(name)
            print('%-18s FAILED' % name)
            traceback.print_exc()
    if not failed and make_figures:
        try:
            for p in figures(results):
                print('figure  ' + os.path.relpath(p, cm.REPO))
        except Exception:  # noqa: BLE001
            failed.append('figures')
            traceback.print_exc()
    if not failed and make_ngspice:
        import droop_sim
        cm.write_json('ngspice_record', droop_sim.ngspice_check(results['droop_sim']))
    if not failed:
        import margins
        note = note_path or Path(cm.REPO, 'docs/gripper/analysis/electrical.md')
        rendered = margins.render_note(note.read_text(encoding='utf-8'), results['margins'])
        cm.write_text('__electrical.md', rendered, encoding='utf-8')
    print('done: %d scripts, %d failed %s' % (len(ORDER), len(failed), failed))
    return 1 if failed else 0


def ordering_surface_paths():
    gripper = Path(cm.REPO, 'ecad/gripper')
    documents = (Path(cm.REPO, 'docs/gripper/analysis/electrical.md'), gripper / 'HARNESS.md',
                 gripper / 'kicad/fab/README.md')
    return documents + release_artifacts.required_status_paths(gripper)


def render_order_surface(path, block):
    import margins
    if path.name == 'README.md' and not path.exists():
        files = sorted(x.name for x in path.parent.iterdir() if x.is_file() and x.name != 'README.md')
        text = '# Fabrication release — gripper controller rev A\n\n<!-- ORDER-STATUS:BEGIN -->\nplaceholder\n<!-- ORDER-STATUS:END -->\n\n'
        text += 'Generated fabrication files for revision A:\n\n' + ''.join('- `%s`\n' % name for name in files)
    elif path.name.endswith('ORDER-STATUS.md') and not path.exists():
        text = '# Ordering gate\n\n<!-- ORDER-STATUS:BEGIN -->\nplaceholder\n<!-- ORDER-STATUS:END -->\n'
    else:
        text = path.read_text(encoding='utf-8')
    return margins.replace_block(text, 'ORDER-STATUS', block)


def update_order_surfaces(result, check=False):
    import margins
    block = margins.order_block(result)
    gripper = Path(cm.REPO, 'ecad/gripper')
    if check:
        release_artifacts.validate_statuses(gripper, block)
    for path in ordering_surface_paths():
        rendered = render_order_surface(path, block)
        if check:
            relative = path.relative_to(cm.REPO)
            if not path.exists():
                raise AssertionError('%s ordering block is missing' % relative)
            if path.read_text(encoding='utf-8') != rendered:
                raise AssertionError('%s ordering block is stale or not identical' % relative)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding='utf-8', newline='\n')


def first_difference(expected, actual, prefix=''):
    """Return the first differing JSON key/index, or None."""
    if type(expected) is not type(actual):
        return prefix or '<root>'
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            here = '%s.%s' % (prefix, key) if prefix else key
            if key not in expected or key not in actual:
                return here
            found = first_difference(expected[key], actual[key], here)
            if found:
                return found
    elif isinstance(expected, list):
        for index, (left, right) in enumerate(zip(expected, actual)):
            found = first_difference(left, right, '%s[%d]' % (prefix, index))
            if found:
                return found
        if len(expected) != len(actual):
            return '%s[%d]' % (prefix, min(len(expected), len(actual)))
    elif expected != actual:
        return prefix or '<root>'
    return None


def semantic_difference(filename, committed, generated, key=''):
    """Return details for the first structural, exact, or out-of-tolerance difference."""
    generated = cm.classified_jsonable(filename, generated, key)
    if type(committed) is not type(generated):
        return (key or '<root>', committed, generated, 0.0)
    if isinstance(committed, dict):
        if set(committed) != set(generated):
            missing = sorted(set(committed) ^ set(generated))[0]
            return ('%s.%s' % (key, missing) if key else missing, None, None, 0.0)
        for child in sorted(committed):
            here = '%s.%s' % (key, child) if key else child
            found = semantic_difference(filename, committed[child], generated[child], here)
            if found:
                return found
    elif isinstance(committed, list):
        if len(committed) != len(generated):
            return ('%s[%d]' % (key, min(len(committed), len(generated))), None, None, 0.0)
        for index, (left, right) in enumerate(zip(committed, generated)):
            found = semantic_difference(filename, left, right, '%s[%d]' % (key, index))
            if found:
                return found
    elif committed != generated:
        limit = cm.tolerance(filename, key, committed, generated) if isinstance(committed, float) else 0.0
        if not limit or abs(committed - generated) > limit:
            return (key or '<root>', committed, generated, limit)
    return None


def check_outputs(reference=None):
    global REFERENCE
    committed = Path(reference) if reference else Path(cm.HERE, 'out')
    import numerics_sensitivity as ns
    sensitivity_path = committed / 'numerics_sensitivity.json'
    if not sensitivity_path.exists():
        print('DIFF numerics_sensitivity.json: missing committed file')
        return 1
    sensitivity = json.loads(sensitivity_path.read_text(encoding='utf-8'))
    try:
        ns.validate_table(sensitivity)
    except ValueError as error:
        print('DIFF numerics_sensitivity.json: %s' % error)
        return 1
    constants_source = Path(cm.HERE, 'constants.py').read_text(encoding='utf-8')
    forbidden_constants = ('buck_nominal_scale', 'buck_frequency_log_start_decade')
    if any(name in constants_source for name in forbidden_constants):
        print('DIFF constants.py: false buck method constant restored')
        return 1
    REFERENCE = committed
    NUMERIC_DIFFERENCES.clear()
    KEPT_VALUES.clear()
    with tempfile.TemporaryDirectory(prefix='gripper_calc_check_') as tmp:
        cm.set_output_dir(tmp)
        if generate():
            return 1
        import margins
        note = Path(cm.REPO, 'docs/gripper/analysis/electrical.md')
        rendered_note = Path(tmp, '__electrical.md').read_text(encoding='utf-8')
        if rendered_note != note.read_text(encoding='utf-8'):
            print('DIFF docs/gripper/analysis/electrical.md: generated blocks stale')
            return 1
        for made in sorted(Path(tmp).rglob('*')):
            if not made.is_file():
                continue
            relative = made.relative_to(tmp)
            if str(relative) == '__electrical.md':
                continue
            wanted = committed / relative
            if not wanted.exists():
                print('DIFF %s: missing committed file' % relative)
                return 1
            left, right = wanted.read_bytes(), made.read_bytes()
            if left != right:
                if made.suffix == '.json':
                    detail = semantic_difference(str(relative), json.loads(left), json.loads(right))
                    if not detail:
                        continue
                    key = detail[0]
                    if detail[3]:
                        print('DIFF %s: key %s committed=%r new=%r difference=%r tolerance=%r' %
                              (relative, key, detail[1], detail[2], abs(detail[1] - detail[2]), detail[3]))
                    else:
                        print('DIFF %s: key %s' % (relative, key))
                else:
                    lines_left, lines_right = left.splitlines(), right.splitlines()
                    line = next((i + 1 for i, pair in enumerate(zip(lines_left, lines_right)) if pair[0] != pair[1]), min(len(lines_left), len(lines_right)) + 1)
                    print('DIFF %s: line %d' % (relative, line))
                return 1
        update_order_surfaces(json.loads(Path(tmp, 'margins.json').read_text(encoding='utf-8')), check=True)
    largest = max((x[2] for x in KEPT_VALUES), default=0.0)
    print('kept solver values: %d; largest relative difference %.3g' % (len(KEPT_VALUES), largest))
    print('check: all generated outputs match')
    return 0


def default_run(make_figures=False, make_ngspice=False, destination=None, note=None):
    """Generate aside, preserving committed integrated values within tolerance."""
    global REFERENCE
    destination = Path(destination) if destination else Path(cm.HERE, 'out')
    REFERENCE = destination
    NUMERIC_DIFFERENCES.clear()
    KEPT_VALUES.clear()
    with tempfile.TemporaryDirectory(prefix='gripper_calc_run_') as tmp:
        cm.set_output_dir(tmp)
        status = generate(make_figures, make_ngspice)
        if status:
            return status
        note_output = Path(tmp, '__electrical.md')
        for made in Path(tmp).rglob('*'):
            if made.is_file() and made != note_output:
                relative = made.relative_to(tmp)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if made.suffix == '.json' and target.exists():
                    old = json.loads(target.read_text(encoding='utf-8'))
                    new = json.loads(made.read_text(encoding='utf-8'))
                    if semantic_difference(str(relative), old, new) is None:
                        continue
                if not target.exists() or target.read_bytes() != made.read_bytes():
                    shutil.copyfile(made, target)
        note = Path(note) if note else Path(cm.REPO, 'docs/gripper/analysis/electrical.md')
        if note.read_bytes() != note_output.read_bytes():
            shutil.copyfile(note_output, note)
        update_order_surfaces(json.loads(Path(tmp, 'margins.json').read_text(encoding='utf-8')))
    largest = max((x[2] for x in KEPT_VALUES), default=0.0)
    print('kept solver values: %d; largest relative difference %.3g' % (len(KEPT_VALUES), largest))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--figures', action='store_true')
    parser.add_argument('--ngspice', action='store_true')
    parser.add_argument('--numerics-sensitivity', action='store_true')
    parser.add_argument('--numerics-entry', action='append')
    parser.add_argument('--write-numerics-table', action='store_true')
    parser.add_argument('--sensitivity-worker')
    parser.add_argument('--sensitivity-compare')
    parser.add_argument('--sensitivity-output')
    parser.add_argument('--sensitivity-setting')
    parser.add_argument('--sensitivity-value')
    parser.add_argument('--decision-worker')
    args = parser.parse_args()
    if args.decision_worker:
        if args.sensitivity_setting:
            cm.NUMERICS[args.sensitivity_setting] = json.loads(args.sensitivity_value)
        _clear_calculation_caches()
        import margins
        result = margins.run()
        rows = [{key: row[key] for key in ('id', 'demand', 'limit', 'margin', 'status')}
                for row in result['rows']]
        Path(args.decision_worker).write_text(
            json.dumps(rows), encoding='utf-8', newline='\n')
        return 0
    if args.sensitivity_compare:
        baseline = _module_result(args.sensitivity_compare)
        cm.NUMERICS[args.sensitivity_setting] = json.loads(args.sensitivity_value)
        changed = _module_result(args.sensitivity_compare)
        difference = _first_stored_difference(baseline, changed)
        if difference:
            print(difference)
        return 0
    if args.sensitivity_worker:
        if args.sensitivity_setting:
            cm.NUMERICS[args.sensitivity_setting] = json.loads(args.sensitivity_value)
        result = _module_result(args.sensitivity_worker)
        Path(args.sensitivity_output).write_text(
            json.dumps(result), encoding='utf-8', newline='\n')
        return 0
    if args.numerics_sensitivity:
        return numerics_sensitivity(args.numerics_entry, args.write_numerics_table)
    if args.check:
        return check_outputs(args.output_dir)
    if args.output_dir:
        cm.set_output_dir(args.output_dir)
        return generate(args.figures, args.ngspice)
    return default_run(args.figures, args.ngspice)


if __name__ == '__main__':
    sys.exit(main())
