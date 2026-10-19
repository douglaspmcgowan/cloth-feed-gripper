"""Write ecad/gripper/kicad/gripper.kicad_pro: board constraints and net classes.

Constraints are the fabricator's published minimums (sourcing.FAB) widened to the values this
board is drawn to; KiCad fills every key left out with its default when it opens the project.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..')))
import design  # noqa: E402

KDIR = os.path.abspath(os.path.join(HERE, '..'))

# Drawn-to rules, mm. Each is at or above the fabricator minimum in sourcing.FAB.
RULES = {
    'min_clearance': 0.2,
    'min_track_width': 0.2,
    'min_via_diameter': 0.6,
    'min_via_annular_width': 0.13,
    'min_through_hole_diameter': 0.2,   # U1 thermal vias under the exposed pad are 0.2 mm
    'min_hole_clearance': 0.25,
    'min_hole_to_hole': 0.5,
    'min_copper_edge_clearance': 0.3,
    'min_silk_clearance': 0.0,
    'min_text_height': 0.8,
    'min_text_thickness': 0.12,
    'min_microvia_diameter': 0.2,
    'min_microvia_drill': 0.1,
    'min_connection': 0.0,
    'min_resolved_spokes': 1,
    'solder_mask_to_copper_clearance': 0.0,
    'use_height_for_length_calcs': True,
}

POWER_NETS = ['VIN_RAW', 'VIN_F', 'VIN_P', 'SW', 'V_BUCK', 'SERVO_V', 'GND']


def netclass(name, track, clearance, via_d, via_drill, priority):
    return {'name': name, 'priority': priority, 'clearance': clearance, 'track_width': track,
            'via_diameter': via_d, 'via_drill': via_drill, 'microvia_diameter': 0.3, 'microvia_drill': 0.1,
            'diff_pair_width': 0.2, 'diff_pair_gap': 0.25, 'diff_pair_via_gap': 0.25,
            'bus_width': 12, 'wire_width': 6, 'line_style': 0,
            'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)'}


def write():
    pro = {
        'board': {'design_settings': {'rules': RULES,
                                      'track_widths': [0.0, 0.25, 0.5, 1.0, 3.0],
                                      'via_dimensions': [{'diameter': 0.0, 'drill': 0.0},
                                                         {'diameter': 0.8, 'drill': 0.4}]}},
        'meta': {'filename': 'gripper.kicad_pro', 'version': 3},
        'net_settings': {
            'classes': [netclass('Default', 0.25, 0.2, 0.8, 0.4, 2147483647),
                        netclass('Power', 1.0, 0.25, 0.8, 0.4, 0)],
            'meta': {'version': 4},
            'net_colors': None,
            'netclass_assignments': None,
            'netclass_patterns': [{'netclass': 'Power', 'pattern': n} for n in POWER_NETS],
        },
        'schematic': {'legacy_lib_dir': '', 'legacy_lib_list': []},
        'sheets': [],
        'text_variables': {'DESIGN_DATE': design.SHEET['date']},
    }
    path = os.path.join(KDIR, 'gripper.kicad_pro')
    if os.path.exists(path):
        # KiCad rewrites the project file when it saves the board; keep what it wrote and
        # re-apply the constraints and net classes this design is drawn to.
        with open(path, encoding='utf-8') as f:
            have = json.load(f)
        have.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rules', {}).update(RULES)
        for key in ('track_widths', 'via_dimensions'):
            have['board']['design_settings'][key] = pro['board']['design_settings'][key]
        have.setdefault('net_settings', {}).update(pro['net_settings'])
        have['text_variables'] = pro['text_variables']
        have.setdefault('meta', pro['meta'])
        pro = have
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(pro, f, indent=2, sort_keys=True)
        f.write('\n')
    print('wrote gripper.kicad_pro')


if __name__ == '__main__':
    write()
