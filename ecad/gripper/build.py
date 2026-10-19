"""Regenerate the gripper electrical deliverable from design.py and sourcing.py.

One command from the repository root:

    python ecad/gripper/build.py            # everything (about 15 minutes; routing is the slow part)
    python ecad/gripper/build.py sch        # schematic, ERC, netlist check
    python ecad/gripper/build.py pcb        # place and route the board
    python ecad/gripper/build.py fab        # DRC, Gerbers, drill, position, PDFs, STEP, BOM, fabrication check
    python ecad/gripper/build.py calc       # calculations and simulations

Each step's stdout is captured to ecad/gripper/kicad/out/build_log_<stages>.txt and the pass/fail
summary to build_summary_<stages>.json (<stages> is "all" for the full run). The run stops at the first failing step and exits non-zero.
KiCad 10 is needed for the sch and pcb stages (kicad-cli and KiCad's bundled Python for pcbnew).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
KDIR = os.path.join(HERE, 'kicad')
OUT = os.path.join(KDIR, 'out')
FAB = os.path.join(KDIR, 'fab')
KICAD_BIN = os.environ.get('KICAD_BIN', os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'KiCad', '10.0', 'bin'))
CLI = os.path.join(KICAD_BIN, 'kicad-cli.exe')
KPY = os.path.join(KICAD_BIN, 'python.exe')
PY = sys.executable
SCH = os.path.join(KDIR, 'gripper.kicad_sch')
PCB = os.path.join(KDIR, 'gripper.kicad_pcb')


def gen(name):
    return os.path.join(KDIR, 'gen', name)


SCH_STEPS = [
    ('custom_lib', [PY, gen('custom_lib.py')]),
    ('lib_tables', [PY, gen('lib_tables.py')]),
    ('project', [PY, gen('gen_pro.py')]),
    ('schematic', [PY, gen('gen_sch.py')]),
    ('erc', [CLI, 'sch', 'erc', '--severity-all', '--exit-code-violations', '--format', 'report',
             '-o', os.path.join(OUT, 'erc.rpt'), SCH]),
    ('netlist', [CLI, 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                 '-o', os.path.join(OUT, 'gripper.net'), SCH]),
    ('netlist_check', [PY, gen('check_netlist.py')]),
    ('sch_pdf', [CLI, 'sch', 'export', 'pdf', '-o', os.path.join(OUT, 'gripper-schematic.pdf'), SCH]),
    ('sch_svg', [CLI, 'sch', 'export', 'svg', '--exclude-drawing-sheet', '-o', OUT, SCH]),
]

PCB_STEPS = [
    ('board', [KPY, gen('gen_pcb.py')]),
    ('project_rules', [PY, gen('gen_pro.py')]),
]

FAB_STEPS = [
    ('drc', [CLI, 'pcb', 'drc', '--severity-all', '--schematic-parity', '--refill-zones', '--save-board',
             '--format', 'report', '-o', os.path.join(OUT, 'drc.rpt'), PCB]),   # errors are counted by fab_check
    ('board_stats', [KPY, gen('board_stats.py')]),
    ('gerbers', [CLI, 'pcb', 'export', 'gerbers', '--layers',
                 'F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,F.Paste,B.Paste,Edge.Cuts',
                 '-o', os.path.join(FAB, 'gerber') + os.sep, PCB]),
    ('drill', [CLI, 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th',
               '--generate-map', '--map-format', 'pdf', '-o', os.path.join(FAB, 'gerber') + os.sep, PCB]),
    ('position', [CLI, 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '--exclude-dnp',
                  '-o', os.path.join(FAB, 'gripper-pos.csv'), PCB]),
    ('board_pdf', [CLI, 'pcb', 'export', 'pdf', '--layers', 'F.Cu,B.Cu,F.SilkS,F.Fab,Edge.Cuts',
                   '--mode-separate', '-o', os.path.join(OUT, 'board') + os.sep, PCB]),
    ('step', [CLI, 'pcb', 'export', 'step', '--force', '--subst-models', '-o', os.path.join(FAB, 'gripper.step'), PCB]),
    ('render_top', [CLI, 'pcb', 'render', '--side', 'top', '--width', '1600', '--height', '1300',
                    '-o', os.path.join(OUT, 'board-top.png'), PCB]),
    ('render_bottom', [CLI, 'pcb', 'render', '--side', 'bottom', '--width', '1600', '--height', '1300',
                       '-o', os.path.join(OUT, 'board-bottom.png'), PCB]),
    ('bom', [PY, gen('bom.py')]),
    ('fab_check', [PY, gen('check_fab.py')]),
]

CALC_STEPS = [
    ('calc', [PY, os.path.join(HERE, 'calc', 'run_all.py')]),
]


def main():
    want = sys.argv[1:] or ['sch', 'pcb', 'fab', 'calc']
    steps = []
    for stage, group in (('sch', SCH_STEPS), ('pcb', PCB_STEPS), ('fab', FAB_STEPS), ('calc', CALC_STEPS)):
        if stage in want:
            steps += group
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(FAB, 'gerber'), exist_ok=True)
    summary, log, failed = [], [], None
    for name, cmd in steps:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        text = (r.stdout or '') + (r.stderr or '')
        tail = [ln for ln in text.strip().splitlines() if ln.strip()][-1:] or ['']
        log.append('### %s (exit %d)\n%s' % (name, r.returncode, text.replace(ROOT + os.sep, '')))
        summary.append({'step': name, 'exit': r.returncode, 'last_line': tail[0].replace(ROOT + os.sep, '')})
        print('%-14s %s  %s' % (name, 'ok  ' if r.returncode == 0 else 'FAIL', summary[-1]['last_line']))
        if r.returncode != 0:
            failed = name
            break
    tag = 'all' if set(want) >= {'sch', 'pcb', 'fab', 'calc'} else '_'.join(want)
    with open(os.path.join(OUT, 'build_log_%s.txt' % tag), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(log).replace(ROOT.replace(os.sep, '/') + '/', '') + '\n')
    with open(os.path.join(OUT, 'build_summary_%s.json' % tag), 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'stages': want, 'failed': failed, 'steps': summary}, f, indent=2)
        f.write('\n')
    print('build: %s' % ('FAILED at ' + failed if failed else 'all %d steps ok' % len(steps)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
