"""Cross-platform reproducibility tests for committed calculation evidence."""
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

HERE = Path(__file__).resolve().parent
RUN = HERE / 'run_all.py'
OUT = HERE / 'out'


def invoke(*args):
    env = os.environ.copy()
    env.pop('NGSPICE_LIBRARY', None)
    return subprocess.run([sys.executable, str(RUN), *map(str, args)], capture_output=True, text=True, env=env)


def copied_outputs(tmp_path):
    copied = tmp_path / 'out'
    shutil.copytree(OUT, copied)
    return copied


def change_charge(root, factor):
    path = root / 'droop_sim.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['sweep'][2]['bulk_charge_C'] *= factor
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    return path


def files(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_two_output_directories_are_byte_identical(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    env = os.environ.copy()
    env.pop('NGSPICE_LIBRARY', None)
    commands = ([sys.executable, str(RUN), '--output-dir', str(first)], [sys.executable, str(RUN), '--output-dir', str(second)])
    processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env) for command in commands]
    for process in processes:
        stdout, stderr = process.communicate()
        assert process.returncode == 0, stdout + stderr
    assert files(first) == files(second)
    assert not list(first.rglob('*.png'))
    assert not (first / 'ngspice_record.json').exists()


def test_check_is_read_only_and_matches_committed_outputs():
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in OUT.rglob('*') if p.is_file()}
    result = invoke('--check')
    assert result.returncode == 0, result.stdout + result.stderr
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in OUT.rglob('*') if p.is_file()}


def test_check_names_perturbed_key(tmp_path):
    copied = tmp_path / 'out'
    shutil.copytree(OUT, copied)
    path = copied / 'power_budget.json'
    value = json.loads(path.read_text(encoding='utf-8'))
    key = 'plug_cable.rating_V'
    value['plug_cable']['rating_V'] *= 1.000001
    path.write_text(json.dumps(value, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    result = invoke('--check', '--output-dir', copied)
    assert result.returncode == 1
    assert 'power_budget.json' in result.stdout and ('key ' + key) in result.stdout


def test_integrated_boundary_noise_passes_and_update_preserves_bytes(tmp_path):
    copied = copied_outputs(tmp_path)
    path = change_charge(copied, 1 + 1e-9)
    perturbed = path.read_bytes()
    result = invoke('--check', '--output-dir', copied)
    assert result.returncode == 0, result.stdout + result.stderr
    sys.path.insert(0, str(HERE))
    import run_all
    note = tmp_path / 'electrical.md'
    shutil.copyfile(HERE.parents[2] / 'docs/gripper/analysis/electrical.md', note)
    run_all.default_run(destination=copied, note=note)
    assert path.read_bytes() == perturbed


def test_integrated_large_change_fails_with_details_and_is_rewritten(tmp_path):
    copied = copied_outputs(tmp_path)
    sys.path.insert(0, str(HERE))
    import _common as cm
    original = json.loads((copied / 'droop_sim.json').read_text(encoding='utf-8'))['sweep'][2]['bulk_charge_C']
    factor = 1 + 10 * cm.tolerance('droop_sim.json', 'sweep[2].bulk_charge_C', original, original) / original
    path = change_charge(copied, factor)
    result = invoke('--check', '--output-dir', copied)
    assert result.returncode == 1
    assert all(term in result.stdout for term in ('sweep[2].bulk_charge_C', 'committed=', 'new=', 'tolerance='))
    import run_all
    note = tmp_path / 'electrical.md'
    shutil.copyfile(HERE.parents[2] / 'docs/gripper/analysis/electrical.md', note)
    run_all.default_run(destination=copied, note=note)
    assert json.loads(path.read_text(encoding='utf-8'))['sweep'][2]['bulk_charge_C'] == original


def test_exact_last_digit_change_fails(tmp_path):
    copied = copied_outputs(tmp_path)
    path = copied / 'droop_sim.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['sweep'][2]['params']['cb'] += 1e-10
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    result = invoke('--check', '--output-dir', copied)
    assert result.returncode == 1 and 'sweep[2].params.cb' in result.stdout


def test_all_json_floats_are_classified_and_unknown_key_is_named():
    sys.path.insert(0, str(HERE))
    import _common as cm
    for path in OUT.glob('*.json'):
        if path.name == 'ngspice_record.json':
            continue
        def walk(value, key=''):
            if isinstance(value, dict):
                for child, item in value.items():
                    walk(item, '%s.%s' % (key, child) if key else child)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, '%s[%d]' % (key, index))
            elif isinstance(value, float):
                assert cm.value_class(path.name, key) in ('exact', 'integrated')
        walk(json.loads(path.read_text(encoding='utf-8')))
    with pytest.raises(KeyError, match='new_solver_value'):
        cm.value_class('droop_sim.json', 'new_solver_value')


def test_tolerance_tracks_solver_rtol(monkeypatch):
    sys.path.insert(0, str(HERE))
    import _common as cm
    base = cm.tolerance('droop_sim.json', 'sweep[2].bulk_charge_C', 1.0, 1.0)
    monkeypatch.setitem(cm.NUMERICS, 'solver_rtol', cm.NUMERICS['solver_rtol'] * 10)
    assert cm.tolerance('droop_sim.json', 'sweep[2].bulk_charge_C', 1.0, 1.0) > base * 9


def test_note_unchanged_by_within_tolerance_perturbation(tmp_path):
    copied = copied_outputs(tmp_path)
    change_charge(copied, 1 + 1e-9)
    note = tmp_path / 'electrical.md'
    shutil.copyfile(HERE.parents[2] / 'docs/gripper/analysis/electrical.md', note)
    before = note.read_bytes()
    sys.path.insert(0, str(HERE))
    import run_all
    run_all.default_run(destination=copied, note=note)
    assert note.read_bytes() == before


def test_sub_rounding_perturbation_is_byte_identical(tmp_path):
    sys.path.insert(0, str(HERE))
    import _common as cm
    assert cm.stored_float(1.23456789012) == cm.stored_float(1.23456789012 * (1 + 1e-13))


def test_outputs_are_portable_and_lf_only():
    forbidden = (b'/tmp/', b'/home/', b'Users')
    for path, content in files(OUT).items():
        if path.suffix == '.png':
            continue
        assert b'\r' not in content, path
        assert not any(term in content for term in forbidden), path
        assert not re.search(rb'(?<![A-Za-z])[A-Za-z]:[\\/]', content), path
