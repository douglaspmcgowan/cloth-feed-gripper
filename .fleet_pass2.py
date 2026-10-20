"""Local lane proof runner; logs each command and its exit and last line."""
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
phase = sys.argv[1]
temp = Path('C:/Users/dougl/AppData/Local/Temp/pw/pt-dog-b40-3')
temp.mkdir(parents=True, exist_ok=True)
environment = dict(os.environ, TEMP=str(temp), TMP=str(temp))
uv = ['uv', '--cache-dir', 'C:/Users/dougl/AppData/Local/Temp/uv-dog-b40', 'run']
checks = [
    ('dog_check', uv + ['--python', '3.12', '--no-project', '--with', 'cadquery', '--with', 'numpy', '--with', 'scipy', '--with', 'matplotlib', 'python', 'cad/gripper/dog_check.py'], 1200),
    ('cad_pytest', uv + ['--python', '3.12', '--no-project', '--with', 'cadquery', '--with', 'pytest', '--with', 'pygments', '--with', 'pyyaml', '--with', 'playwright', '--with', 'shapely', 'python', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--basetemp', str(temp / f'{phase}-cad'), 'cad/gripper'], 1800),
    ('tolstack_pytest', uv + ['--python', '3.12', '--no-project', '--with-requirements', 'requirements-dev.txt', 'python', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--basetemp', str(temp / f'{phase}-tolstack'), 'analysis/gripper/tolstack'], 1800),
    ('actuation_pytest', uv + ['--python', '3.12', '--no-project', '--with-requirements', 'requirements-dev.txt', 'python', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--basetemp', str(temp / f'{phase}-actuation'), 'analysis/gripper/actuation'], 1200),
    ('pin', uv + ['--no-project', '--with', 'numpy', 'python', 'analysis/gripper/actuation/pin_rev_a.py', '--check'], 1200),
    ('tolstack_check', uv + ['--no-project', '--with', 'pyyaml', '--with', 'numpy', 'python', 'analysis/gripper/tolstack/tolstack.py', '--check'], 1200),
    ('ecad', uv + ['--no-project', '--with', 'numpy', '--with', 'scipy', 'python', 'ecad/gripper/calc/run_all.py', '--check'], 1200),
    ('gears', uv + ['--no-project', '--with', 'numpy', '--with', 'scipy', '--with', 'matplotlib', '--with', 'shapely', 'python', 'analysis/gripper/gears.py', '--check'], 1200),
    ('thermal', uv + ['--no-project', '--with', 'numpy', '--with', 'scipy', 'python', 'analysis/gripper/thermal/thermal.py', '--check'], 1200),
    ('test_plan', uv + ['--no-project', '--with', 'numpy', '--with', 'scipy', '--with', 'pyyaml', 'python', 'docs/gripper/test/test_plan.py', '--check'], 1200),
    ('dyno', uv + ['--no-project', '--with', 'numpy', '--with', 'scipy', '--with', 'matplotlib', '--with', 'shapely', '--with', 'pylife', '--with', 'packaging', 'python', 'analysis/gripper/dyno.py', '--check'], 1200),
    ('finger_beam', uv + ['--no-project', '--with', 'numpy', '--with', 'scipy', '--with', 'matplotlib', 'python', 'analysis/gripper/finger_beam.py', '--check'], 1200),
    ('lint', ['npm.cmd', 'run', 'lint'], 1200),
    ('public', ['npm.cmd', 'run', 'check:public'], 1200),
    ('sync', ['python', '-m', 'unittest', 'tests/test_sync.py'], 1200),
]
if phase == 'corrected':
    checks = [entry for entry in checks if entry[0] in {'cad_pytest', 'tolstack_pytest', 'actuation_pytest'}]
results = {}
for name, command, timeout in checks:
    print(f'RUN {name}', flush=True)
    try:
        with (root / f'.fleet_pass2_{phase}_{name}.log').open('w', encoding='utf-8', errors='replace') as log:
            proc = subprocess.run(command, cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        lines = (root / f'.fleet_pass2_{phase}_{name}.log').read_text(encoding='utf-8', errors='replace').strip().splitlines()
        results[name] = {'exit': proc.returncode, 'last': lines[-1] if lines else ''}
    except subprocess.TimeoutExpired:
        results[name] = {'exit': 'timeout', 'last': f'timed out after {timeout}s'}
    print(f"{name}: {results[name]['exit']} {results[name]['last']}", flush=True)
    (root / f'.fleet_pass2_{phase}.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
