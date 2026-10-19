"""Payload -> mass budget -> finger torque -> actuator, then the PWM actuator trade study.

Works backwards from the SO-101 arm (what mass the arm can carry) to the grip (what torque
the fingers need) to the actuator (which PWM part delivers it).

Inputs
    cad/gripper/params.json                      grip, payload_scenarios, work_cell, duty_cycle, mcu
    cad/so101/so101_old_calib.urdf               hand calc (numpy forward kinematics, sum m*g x r)
    cad/so101/Simulation/SO101/so101_old_calib.xml   MuJoCo cross-check (qfrc_bias, mj_jac, mj_inverse)
    docs/gripper/research/actuators.csv          market scan; this script appends rows/columns once
                                                 (EXTRA_ROWS / EXTRA_COLS below; never edits a value)
    INPUT table below                            every value tagged S sourced / D derived / A assumed
Outputs
    analysis/gripper/results/payload_torque.json
    docs/gripper/figures/payload_*.png, docs/gripper/figures/actuator_*.png

Run from the repository root (about 20 s):
    uv run --with mujoco --with numpy --with scipy --with matplotlib python analysis/gripper/payload_torque.py
"""
from __future__ import annotations

import csv
import io
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mujoco  # noqa: E402
import numpy as np  # noqa: E402
from scipy.optimize import minimize  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PARAMS = ROOT / "cad/gripper/params.json"
ACT_CSV = ROOT / "docs/gripper/research/actuators.csv"
URDF = ROOT / "cad/so101/so101_old_calib.urdf"
MJCF = ROOT / "cad/so101/Simulation/SO101/so101_old_calib.xml"
OUT = ROOT / "analysis/gripper/results/payload_torque.json"
FIG = ROOT / "docs/gripper/figures"

G = 9.80665
KGCM = G / 100.0  # 1 kg*cm in N*m
P = json.loads(PARAMS.read_text(encoding="utf-8"))
GR, PS, WC, DC = P["grip"], P["payload_scenarios"], P["work_cell"], P["duty_cycle"]
SELECTION_BASIS_LABEL = "selection basis 0.5 s (R19 at selection; superseded 2026-10-12)"

# ------------------------------------------------------------------ inputs (value, tag, note)
INPUT = {
    # grip (params.json grip block, DESIGN-BASIS LC1/LC2)
    "tension_N": (GR["tension_N"], "A", "params.json grip.tension_N (M3 measures)"),
    "mu": (GR["mu_pad_cloth"], "A", "params.json grip.mu_pad_cloth (M2 measures)"),
    "mu_nail_low": (0.25, "A", "PLA nail on cotton, lower bound for the asymmetric-finger case (D7); fabric-fabric 0.28-0.30 [S cloth_and_camera.md 2.3]"),
    "SF_slip": (GR["SF_slip"], "A", "params.json grip.SF_slip"),
    "F_cap_N": (GR["F_cap_N"], "A", "params.json grip.F_cap_N"),
    "eta": (GR["eta_mesh_pivot"], "A", "params.json grip.eta_mesh_pivot (M18 measures)"),
    "r_c_mm": (GR["r_c_design_mm"], "D", "params.json grip.r_c_design_mm (DESIGN-BASIS D3)"),
    "r_c_cad_mm": (GR["r_c_current_cad_mm"], "D", "params.json grip.r_c_current_cad_mm"),
    "pad_from_tip_mm": (GR["pad_centroid_from_tip_mm"], "A", "params.json grip.pad_centroid_from_tip_mm"),
    "root_mm": (P["knuckle"]["root_offset"] + P["knuckle"]["root_thickness"], "D", "params.json knuckle.root_offset + root_thickness"),
    "closed_gap_mm": (P["finger"]["closed_gap"], "S", "params.json finger.closed_gap"),
    "x_f_mm": (P["gear"]["module"] * P["gear"]["teeth"] / 2 - P["finger"]["closed_gap"] / 2, "D", "pad x offset from pivot = m z/2 - gap/2 (m1 z24); 14.5 mm for m1.5 z20"),
    "cloth_t_mm": (WC["cloth"]["thickness_mm"], "A", "params.json work_cell.cloth.thickness_mm"),
    "k_tip_N_mm": (GR["k_tip_default_N_per_mm"], "A", "params.json grip.k_tip_default_N_per_mm (FEA lane refines)"),
    "k_sweep_N_mm": ([0.42, 0.76, 0.88, 1.0, 1.63], "A", "0.42/0.76 = preliminary FEA-lane tip values (analysis/gripper/results/fea_stdout.txt, other lane); 0.88/1.63 = DESIGN-BASIS window"),
    "theta_open_deg": (GR["theta_open_max_deg"], "D", "params.json grip.theta_open_max_deg"),
    "theta_min_deg": (GR["theta_min_deg"], "D", "params.json grip.theta_min_deg"),
    "hold_frac": (GR["hold_fraction_of_stall"], "A", "40 % case: hold <= 40 % of stall (R16), applied to EVERY actuator driven by a brushed DC motor (servos and gearmotors alike)"),
    "hold_frac_25": (0.25, "S", "25 % case: Pololu 'a general recommendation for brushed DC motor operation is 25% or less of the stall current', https://www.pololu.com/category/60/micro-metal-gearmotors; applied to EVERY brushed-DC-driven actuator (hobby servos contain brushed or coreless brushed DC motors)"),
    "close_time_s": (GR["close_time_selection_basis_s"], "A", SELECTION_BASIS_LABEL),
    "close_time_requirement_s": (GR["close_time_max_s"], "D", "ruled R19 requirement: full close within 0.75 s (Douglas, 2026-10-12)"),
    "near_contact_deg": (3.0, "A", "R19: last 3 deg before contact"),
    "near_contact_speed": (GR["near_contact_speed_deg_s"], "A", "R19 deg/s"),
    "overtravel_speed_max": (60.0, "A", "deg/s ceiling while the FSR loop ramps force (firmware steps)"),
    "k_trap": (1.3, "A", "trapezoid-profile time factor on the free-travel segment"),
    "V_servo": (P["mcu"]["power"]["servo_rail_V"], "A", "params.json mcu.power.servo_rail_V (the 6.0 V baseline trade)"),
    "V_rail_design": (6.5, "A", "proposed servo rail: trimmed adjustable buck set to 6.5 V, below the 6.8 V maximum rating of DS3218MG/DS3225 [S actuators.csv voltage_max_V]"),
    "V_rail_tol": (0.15, "A", "set-point + load-regulation tolerance of the buck (6.35-6.65 V); verify by measurement at stall (R27 scope test)"),
    "V_rated_max_A17": (6.8, "S", "DS3218MG voltage_max_V (actuators.csv A17; Miuzei datasheet 1-3 'Operating Voltage Range 4.8-6.8V')"),
    # arm / payload
    "hold_frac_arm": (PS["hold_fraction_arm"], "A", "params.json payload_scenarios.hold_fraction_arm"),
    "dyn_accel_g": (0.5, "A", "DESIGN-BASIS LC5 vertical acceleration in g"),
    "dyn_limit_frac": (0.8, "A", "dynamic peak <= 80 % of arm stall (LC5)"),
    "bed_height_m": (WC["bed_height_above_table_mm"] / 1000, "A", "params.json work_cell"),
    "reach_max_m": (WC["feed_pose_reach_max_mm"] / 1000, "A", "params.json work_cell.feed_pose_reach_max_mm"),
    "tilt_max_deg": (WC["gripper_tilt_max_deg"], "A", "params.json work_cell.gripper_tilt_max_deg"),
    "swing_rad": (0.5, "A", "shoulder_lift swing for the dynamic check (min-jerk, ends at full extension)"),
    # gripper mass items (d = mm past the gripper-body origin along the roll axis, as design_basis.py)
    "H_to_pivot_mm": (40.7, "D", "design_basis.py: servo body_y - shaft_from_bottom + wall + mount_t"),
    "housing_g": (18.7, "D", "gripper_concept.py mass table (PLA, 60 % fill), via design_basis.py"),
    "housing_d": (25.0, "A", "design_basis.py"),
    "knuckles_g": (6.0, "D", "gripper_concept.py mass table"),
    "fingers_g_per_mm": (8.8 / 60.0, "D", "gripper_concept.py 8.8 g at L = 60, scaled with L"),
    "servo_d": (29.0, "D", "servo COM, design_basis.py concept layout"),
    "fasteners_g": (8.0, "A", "horn, pins, fasteners (README estimate)"),
    "fasteners_d": (20.0, "A", ""),
    "wiring_g": (5.0, "A", "FSR + backing + wires"),
    "wiring_d": (40.0, "A", ""),
    "cloth_g": (WC["cloth"]["mass_g"], "D", "params.json work_cell.cloth.mass_g"),
    "camera_g": (10.0, "A", "32x32 UVC wrist module (DESIGN-BASIS D9)"),
    "camera_d": (20.0, "A", ""),
    "stage_gear_fill": (0.6, "A", "printed extra reduction stage, lightened gear, PETG 1.25 g/cm3"),
    "stage_eta": (0.9, "A", "efficiency of one printed spur stage"),
    "stage_pinion_z": (12, "A", "pinion teeth, module 0.8, face 5 mm"),
    "envelope_max_mm": ([45.0, 25.0, 45.0], "A", "hand-sized BODY envelope, mounting ears excluded: longest side <= 45, then 25 x 45 (standard servo body is the ceiling)"),
    "flange_max_mm": (56.0, "A", "ear-to-ear span the housing's servo bay accepts (standard 40 x 20 servo ears are 54.5 mm [S Miuzei DS3218 and DS3235 drawings]); checked where flange_span_mm is published"),
    "lewis_sigma_per_Nm": ({"m1.0_z24": 41.2, "m1.5_z20": 23.0}, "D", "MPa per N*m of mesh torque, b = 6 mm (design_basis.py Lewis table, DESIGN-BASIS section 2)"),
    "lc3_allow_MPa": ({"PETG": 51.0, "PA6-CF": 102.0}, "S", "X-Y tensile / 1.0 (params.json materials.allowables allow_LC3)"),
    "hbridge_note": ("DRV8833-class driver sits with the MCU, 0 g on the gripper", "A", ""),
    "kit_stall_tags": ({"C001_5V": "A: 1.618 N*m is the STS3215 6 V rating; at 5 V the stall is somewhat less (DESIGN-BASIS section 5), "
                                   "so every C001 5 V payload number here is OPTIMISTIC",
                        "C001_7p4V": "S so101.md via params.json", "C018_12V": "S so101.md via params.json"}, "S/A",
                       "tag of params.json payload_scenarios.*.stall_Nm per kit"),
    "vendor_hold_rule": ({"M01": 0.25, "M02": 0.25, "M03": 0.25, "M04": 0.25}, "S",
                         "part-specific published continuous rule: Pololu micro metal gearmotors 'a general recommendation for brushed DC "
                         "motor operation is 25% or less of the stall current' https://www.pololu.com/category/60/micro-metal-gearmotors. "
                         "The recommendation never applies a hold rule looser than the part's own vendor publishes"),
}
V = {k: v[0] for k, v in INPUT.items()}
V_LO = round(V["V_rail_design"] - V["V_rail_tol"], 3)  # D: low end of the rail band: hold margin, speed, break-even
V_HI = round(V["V_rail_design"] + V["V_rail_tol"], 3)  # D: high end of the band: LC3 mesh torque and the rating check

KITS = {k: s["stall_Nm"] for k, s in PS["scenarios"].items()}  # S so101.md via params.json
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]


def r(x, n=3):
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [r(v, n) for v in x]
    return float(round(float(x), n))


# ------------------------------------------------------------------ actuators.csv extension
EXTRA_COLS = ["output_interface", "horn_included", "mount_pattern", "stock_checked", "interface_source",
              "torque_mid_kgcm", "torque_mid_at_V", "flange_span_mm", "ear_hole_pattern_mm"]
MIUZEI = "https://images-na.ssl-images-amazon.com/images/I/81Lbgu+nG6L.pdf"
DS3235 = "https://hajim.rochester.edu/me/sites/kelley/me240/DS3235-270_datasheet.pdf"
IFACE = {  # id -> {lane-appended column: value}; datasheet / vendor text or drawing only, blank where not published.
    # The script owns these appended columns and sets them to these values; original columns are never changed.
    "A17": {"output_interface": "25T spline, 5.9 mm", "horn_included": "1x aluminum arm + 4x plastic arms",
            "mount_pattern": "standard-size flange servo, body 40.0x20.5x40.5 mm; 4 ear holes on a 49.5 x 10 mm pattern, 54.5 mm across the ears (Miuzei drawing)",
            "stock_checked": "in stock, 14 units (SpeedyFPV, 2026-09-22)",
            "interface_source": "S https://speedyfpv.com/products/ds3218mg-digital-servo-high-speed-high-torque-metal-gear-waterproof-20kg-torque-180-degrees-w-accessories ; drawing " + MIUZEI,
            "flange_span_mm": "54.5", "ear_hole_pattern_mm": "49.5 x 10"},
    "A18": {"output_interface": "25T spline", "horn_included": "2x 25T adjustable metal arm",
            "mount_pattern": "standard-size flange servo, body 40x20x40.5 mm; ear-hole spacing not published",
            "stock_checked": "unavailable (MakerFocus, 2026-09-22)", "interface_source": "S https://www.makerfocus.com/products/digital-servo-25kg"},
    "A19": {"output_interface": "25T spline", "horn_included": "optional arm (datasheet section 8)",
            "mount_pattern": "standard-size flange servo, body 40x20x38.5 mm (datasheet); 4 ear holes on a 49.5 x 10 mm pattern, 54.5 mm across the ears (datasheet section 1 drawing)",
            "stock_checked": "sold out (RCDrone, row notes)", "interface_source": "S " + DS3235 + " sections 1, 3, 4 and 7",
            "torque_mid_kgcm": "32", "torque_mid_at_V": "6.0", "flange_span_mm": "54.5", "ear_hole_pattern_mm": "49.5 x 10"},
    "A20": {"output_interface": "25T (stated as 'Metal Teeth:25T' for the PDI-6221MG-360 variant; '25T Arm' option in the listing title; not stated for the 180 variant)",
            "horn_included": "25T arm offered as a listing option; inclusion not stated",
            "mount_pattern": "standard-size flange servo, body 40.5x20.2x38 mm; mounting pattern not published",
            "stock_checked": "sold out (RCDrone, 2026-09-22)",
            "interface_source": "S https://rcdrone.top/products/jx-20kg-servo-pdi-6221mg (JX site http://www.jx-servo.com/en/Product/STANDARD/SD/555.html not retrievable: certificate error)"},
    "M02": {"output_interface": "3 mm D-shaft, 9 mm long ('9 mm long, 3 mm diameter D-shaped gearbox output shaft'); specs page: output shaft adds 10 mm to the 32 mm length",
            "horn_included": "none (hub or printed coupler needed)",
            "mount_pattern": "no mounting holes on the gearmotor; Pololu micro metal gearmotor bracket pair #989 ($2.95, #2-56 x 7/16 in screws + nuts, captures the 10x12 mm gearbox); hole spacing not in the public text",
            "stock_checked": "listed $32.45, status 'Active and Preferred' (Pololu, 2026-09-22); page weight 11 g",
            "interface_source": "S https://www.pololu.com/product/5200 ; https://www.pololu.com/product/5200/specs ; bracket https://www.pololu.com/product/989"},
    "M01": {"output_interface": "3 mm D-shaft (same micro metal gearmotor gearbox family as M02)", "horn_included": "none",
            "mount_pattern": "no mounting holes; Pololu bracket pair #989", "stock_checked": "listed $32.45 (Pololu, 2026-09-22)",
            "interface_source": "S https://www.pololu.com/product/5193/specs ; bracket https://www.pololu.com/product/989 (shaft form by family, A)"},
    "M04": {"output_interface": "3 mm D-shaft (same micro metal gearmotor gearbox family as M02)", "horn_included": "none",
            "mount_pattern": "no mounting holes; Pololu bracket pair #989", "stock_checked": "listed $29.95 (Pololu, 2026-09-22)",
            "interface_source": "S https://www.pololu.com/product/5173 ; bracket https://www.pololu.com/product/989 (shaft form by family, A)"},
    "A13": {"stock_checked": "listed $35.77, inventory not shown (Pololu, 2026-09-22)", "interface_source": "S https://www.pololu.com/product/3443"},
    "W01": {"output_interface": "3 mm shaft, 8 mm long, right-angle worm output", "horn_included": "none",
            "mount_pattern": "N20 motor + worm gearbox; overall dimensions only in the page's outline image (not in the text)",
            "stock_checked": "listed $12.50 (NFP, 2026-09-22)", "interface_source": "S https://nfpshop.com/product/12mm-metal-gear-motor-model-nfp-n20-gm1218s"},
    "W02": {"output_interface": "3 mm shaft, 8 mm long, right-angle worm output", "horn_included": "none",
            "mount_pattern": "N20 motor + worm gearbox + encoder; overall dimensions only in the page's outline image",
            "stock_checked": "listed $16.50 (NFP, 2026-09-22)", "interface_source": "S https://nfpshop.com/product/12mm-metal-gear-motor-model-nfp-n20-gm1218s"},
    "L01": {"output_interface": "20 mm stroke rod, 3 mm rod-eye hole", "horn_included": "n/a (linear)",
            "mount_pattern": "2 mounting brackets + M3 hardware included; body 36.5 x 21.5 x 15 mm retracted (datasheet drawing)",
            "stock_checked": "in stock (SparkFun, 2026-09-22)", "interface_source": "S https://www.actuonix.com/assets/images/datasheets/ActuonixPQ12Datasheet.pdf"},
}
FILL_BLANK = {  # original columns: filled only where the cell is empty (never overwrites); published dimensions
    "M02": {"dim_L_mm": "32", "dim_W_mm": "12", "dim_H_mm": "10"},   # S https://www.pololu.com/product/5200/specs '10 x 12 x 32 mm'
    "L01": {"dim_L_mm": "36.5", "dim_W_mm": "21.5", "dim_H_mm": "15"},  # S PQ12 datasheet drawing (retracted body; rod extends 20 mm)
}
NFP = "https://nfpshop.com/product/12mm-metal-gear-motor-model-nfp-n20-gm1218s"
EXTRA_ROWS = [  # dicts keyed by the original header; unlisted columns blank
    {"id": "W01", "model": "NFP-WG1218S-N20 6V 1030:1 worm gearmotor (B45 type)", "category": "DC worm gearmotor", "vendor": "NFP Shop",
     "price_usd": "12.50", "price_date": "2026-09-22", "vendor_url": NFP, "datasheet_url": NFP, "voltage_max_V": "6.0",
     "torque_high_kgcm": "3.0", "torque_high_at_V": "6.0", "no_load_speed_rpm": "22", "weight_g": "13", "gear_material": "metal (worm)",
     "travel_deg": "continuous", "feedback": "none", "no_load_current_mA": "80", "stall_current_A": "0.65",
     "provenance": "sourced (NFP 6 V B45 table): stall <=3 kgcm, rated 1.2 kgcm at 15 rpm, 22 rpm no load, <=0.65 A stall, ~13 g",
     "notes": "worm gearbox self-locks (vendor); needs an H-bridge; stall figure is an upper bound; 603:1 variant 2 kgcm / 37 rpm"},
    {"id": "W02", "model": "NFP-WG1218S-N20-EN-SD 6V 1030:1 worm gearmotor + encoder", "category": "DC worm gearmotor + encoder", "vendor": "NFP Shop",
     "price_usd": "16.50", "price_date": "2026-09-22", "vendor_url": NFP, "datasheet_url": NFP, "voltage_max_V": "6.0",
     "torque_high_kgcm": "3.0", "torque_high_at_V": "6.0", "no_load_speed_rpm": "22", "weight_g": "13", "gear_material": "metal (worm)",
     "travel_deg": "continuous", "feedback": "encoder (counts not retrieved)", "no_load_current_mA": "80", "stall_current_A": "0.65",
     "provenance": "price sourced (NFP page); gearbox specs assumed equal to W01",
     "notes": "self-locking worm + encoder; needs an H-bridge"},
    {"id": "L01", "model": "Actuonix PQ12-100-6-R micro linear servo (RC PWM input)", "category": "micro linear actuator (RC PWM)", "vendor": "SparkFun",
     "price_usd": "149.95", "price_date": "2026-09-22", "vendor_url": "https://www.sparkfun.com/products/18591",
     "datasheet_url": "https://www.actuonix.com/assets/images/datasheets/ActuonixPQ12Datasheet.pdf", "voltage_min_V": "6.0", "voltage_max_V": "6.0",
     "weight_g": "21", "travel_deg": "20 mm stroke", "feedback": "internal pot (closed loop inside)", "stall_current_A": "0.55",
     "provenance": "sourced: SparkFun price; PQ12 datasheet 40 N at 6 mm/s peak power, 50 N max, back-drive 35 N, 10 mm/s no load, 20 % max duty, 21 g (R)",
     "notes": "over $50; linear stroke needs a crank to drive knuckle A; 1.0-2.0 ms pulses; 63:1 variant 30 N at 8 mm/s"},
]
LINEAR = {"L01": {"F_peak_N": 40.0, "F_max_N": 50.0, "F_backdrive_N": 35.0, "v_noload_mm_s": 10.0, "v_peak_mm_s": 6.0,
                  "stroke_mm": 20.0, "tag": "S PQ12 datasheet"}}


def extend_csv():
    """Append EXTRA_COLS and EXTRA_ROWS once. Original cells are never changed (FILL_BLANK only fills empty cells);
    the lane-appended columns are owned by this script and set to IFACE. A second run changes nothing."""
    text = ACT_CSV.read_text(encoding="utf-8")
    rows = list(csv.reader(text.splitlines()))
    head, body = rows[0], rows[1:]
    for c in EXTRA_COLS:
        if c not in head:
            head.append(c)
    ids = {row[0] for row in body}
    for er in EXTRA_ROWS:
        if er["id"] not in ids:
            body.append([er.get(c, "") for c in head])
    for row in body:
        row += [""] * (len(head) - len(row))
        if row[0] in IFACE:
            for c in EXTRA_COLS:
                row[head.index(c)] = IFACE[row[0]].get(c, "")
        for c, v in FILL_BLANK.get(row[0], {}).items():
            j = head.index(c)
            if not row[j]:
                row[j] = v
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(head)
    w.writerows(body)
    changed = buf.getvalue() != text
    if changed:
        with ACT_CSV.open("w", encoding="utf-8", newline="") as fh:
            fh.write(buf.getvalue())
    return changed


# ------------------------------------------------------------------ gripper mass model
def mass_items(servo_g, finger_L, extra=()):
    rc = finger_L + V["root_mm"] - V["pad_from_tip_mm"]
    it = [("housing", V["housing_g"], V["housing_d"], "D"),
          ("knuckles", V["knuckles_g"], V["H_to_pivot_mm"], "D"),
          ("fingers TPU", V["fingers_g_per_mm"] * finger_L, V["H_to_pivot_mm"] + V["root_mm"] + finger_L / 3, "D"),
          ("actuator", servo_g, V["servo_d"], "S mass"),
          ("horn, pins, fasteners", V["fasteners_g"], V["fasteners_d"], "A"),
          ("FSR + wiring", V["wiring_g"], V["wiring_d"], "A"),
          ("cloth at pad", V["cloth_g"], V["H_to_pivot_mm"] + rc, "D")]
    return it + list(extra)


FINGER_L = V["r_c_mm"] - V["root_mm"] + V["pad_from_tip_mm"]  # 45 mm


# ------------------------------------------------------------------ 1a. URDF hand calc
def rpy_R(rpy):
    rr, pp, yy = rpy
    cx, sx, cy, sy, cz, sz = math.cos(rr), math.sin(rr), math.cos(pp), math.sin(pp), math.cos(yy), math.sin(yy)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def axis_R(ax, q):
    ax = np.asarray(ax, float) / np.linalg.norm(ax)
    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * K @ K


def urdf_load():
    t = ET.parse(URDF).getroot()
    links = {}
    for L in t.findall("link"):
        ine = L.find("inertial")
        if ine is None:
            continue
        o = ine.find("origin")
        links[L.get("name")] = (float(ine.find("mass").get("value")), np.array([float(x) for x in o.get("xyz").split()]))
    joints = []
    for J in t.findall("joint"):
        o = J.find("origin")
        joints.append({"name": J.get("name"), "parent": J.find("parent").get("link"), "child": J.find("child").get("link"),
                       "xyz": np.array([float(x) for x in o.get("xyz").split()]),
                       "rpy": [float(x) for x in o.get("rpy").split()],
                       "axis": [float(x) for x in J.find("axis").get("xyz").split()]})
    return links, joints


def urdf_gravity(links, joints, q, drop=(), points=()):
    """Required holding torque per joint = axis . sum (c - o) x (m g z_hat); points = [(link, m, xyz_local)]."""
    T = {"base": (np.eye(3), np.zeros(3))}
    jw = {}
    pending = list(joints)
    while pending:
        for j in list(pending):
            if j["parent"] in T:
                Rp, pp = T[j["parent"]]
                Rj = Rp @ rpy_R(j["rpy"])
                oj = pp + Rp @ j["xyz"]
                jw[j["name"]] = (oj, Rj @ np.asarray(j["axis"], float), j["child"])
                T[j["child"]] = (Rj @ axis_R(j["axis"], q.get(j["name"], 0.0)), oj)
                pending.remove(j)
    masses = [(ln, m, T[ln][1] + T[ln][0] @ c) for ln, (m, c) in links.items() if ln not in drop]
    masses += [(ln, m, T[ln][1] + T[ln][0] @ np.asarray(x)) for ln, m, x in points]
    child = {j["parent"]: [] for j in joints}
    for j in joints:
        child.setdefault(j["parent"], []).append(j["child"])

    def subtree(ln):
        out = {ln}
        for c in child.get(ln, []):
            out |= subtree(c)
        return out
    tau = {}
    for name, (oj, aw, ch) in jw.items():
        sub = subtree(ch)
        tq = sum(np.cross(p - oj, np.array([0, 0, m * G])) for ln, m, p in masses if ln in sub)
        tau[name] = float(aw @ tq) if not isinstance(tq, int) else 0.0
    return tau, T


# ------------------------------------------------------------------ 1b. MuJoCo helpers
class Arm:
    def __init__(self):
        self.m = mujoco.MjModel.from_xml_path(str(MJCF))
        self.d = mujoco.MjData(self.m)
        self.jid = {self.m.joint(i).name: i for i in range(self.m.njnt)}
        self.dof = {n: int(self.m.jnt_dofadr[self.jid[n]]) for n in JOINTS}
        self.bg = self.m.body("gripper").id
        self.bj = self.m.body("moving_jaw_so101_v1").id
        self.m0 = (self.m.body_mass[self.bg], self.m.body_mass[self.bj])

    def arm_only(self):
        self.m.body_mass[self.bg] = 1e-9
        self.m.body_mass[self.bj] = 1e-9
        mujoco.mj_setConst(self.m, self.d)

    def stock(self):
        self.m.body_mass[self.bg], self.m.body_mass[self.bj] = self.m0
        self.m.body_ipos[self.bg] = mujoco.MjModel.from_xml_path(str(MJCF)).body_ipos[self.bg]
        mujoco.mj_setConst(self.m, self.d)

    def lump(self, items):
        m = sum(x[1] for x in items) / 1000
        dd = sum(x[1] * x[2] for x in items) / sum(x[1] for x in items) / 1000
        self.m.body_mass[self.bg] = m
        self.m.body_ipos[self.bg] = [0, 0, -dd]
        self.m.body_inertia[self.bg] = [1e-6, 1e-6, 1e-6]
        self.m.body_mass[self.bj] = 1e-9
        mujoco.mj_setConst(self.m, self.d)
        return m, dd

    def pose(self, q):
        self.d.qpos[:] = 0
        for n, v in q.items():
            self.d.qpos[self.m.jnt_qposadr[self.jid[n]]] = v
        self.d.qvel[:] = 0
        mujoco.mj_forward(self.m, self.d)

    def bias(self):
        return np.array([self.d.qfrc_bias[self.dof[n]] for n in JOINTS])

    def point(self, d_mm):
        R = self.d.xmat[self.bg].reshape(3, 3)
        return self.d.xpos[self.bg] + R @ np.array([0, 0, -d_mm / 1000])

    def jac(self, p):
        jp = np.zeros((3, self.m.nv))
        mujoco.mj_jac(self.m, self.d, jp, None, p, self.bg)
        return np.array([jp[:, self.dof[n]] for n in JOINTS]).T  # 3 x 5

    def grav_point(self, m_g, d_mm):
        """Required holding torque for a point mass m_g at d_mm past the gripper origin."""
        return m_g / 1000 * G * self.jac(self.point(d_mm))[2]

    def force_at(self, F, d_mm):
        """Required actuator torque to resist an external force F (world, N) at d_mm (tension on the cloth)."""
        return -(self.jac(self.point(d_mm)).T @ F)

    def bounds(self):
        return [tuple(float(v) for v in self.m.jnt_range[self.jid[n]]) for n in POSE_J]

    def force_applyFT(self, F, d_mm):
        q = np.zeros(self.m.nv)
        mujoco.mj_applyFT(self.m, self.d, np.asarray(F, float), np.zeros(3), self.point(d_mm), self.bg, q)
        return -np.array([q[self.dof[n]] for n in JOINTS])


POSE_J = ["shoulder_lift", "elbow_flex", "wrist_flex"]
SEEDS = [np.zeros(3)]  # grid-sweep and optimised worst poses; payload() fills this before any budget check


def tau_loads(A, x, its):
    """Required holding torque (shoulder_lift, elbow, wrist_flex) at pose x for the arm (gripper bodies massless)
    plus point loads its = [(name, g, d_mm, ...)]. A must be in the arm_only state."""
    A.pose(dict(zip(POSE_J, x)))
    t = A.bias()[1:4].copy()
    for it in its:
        t += A.grav_point(it[1], it[2])[1:4]
    return t


def maximize(A, f, seeds=None):
    """Bounded Nelder-Mead from every seed (0.15 rad initial simplex); returns (max f, pose). The maximum over the
    joint ranges, not a grid sample, so it can only equal or exceed the grid value it is seeded from."""
    best = (-math.inf, None)
    bnd = A.bounds()
    for x0 in (seeds if seeds is not None else SEEDS):
        x0 = np.clip(np.asarray(x0, float), [b[0] for b in bnd], [b[1] for b in bnd])
        simplex = np.vstack([x0] + [np.clip(x0 + 0.15 * np.eye(3)[i] * (1 if x0[i] + 0.15 <= bnd[i][1] else -1),
                                            bnd[i][0], bnd[i][1]) for i in range(3)])
        res = minimize(lambda x: -f(x), x0, method="Nelder-Mead", bounds=bnd,
                       options={"xatol": 1e-5, "fatol": 1e-8, "maxiter": 800, "initial_simplex": simplex})
        for v, x in ((-res.fun, res.x), (f(x0), x0)):
            if v > best[0]:
                best = (float(v), np.array(x, float))
    return best


_UTIL_CACHE = {}


def arm_util(A, its, kit="C001_7p4V"):
    """Worst-case shoulder_lift/elbow/wrist hold utilisation over the whole joint range (max over pose of
    max_j |tau_j| / (hold_frac_arm * stall)). Returns (util, pose)."""
    key = (kit, tuple((round(it[1], 3), round(it[2], 3)) for it in its))
    if key not in _UTIL_CACHE:
        A.arm_only()
        allow = V["hold_frac_arm"] * KITS[kit]
        _UTIL_CACHE[key] = maximize(A, lambda x: float(np.max(np.abs(tau_loads(A, x, its)))) / allow)
    return _UTIL_CACHE[key]


def m_max(tau0, c, allow):
    """Largest m >= 0 with |tau0 + m c| <= allow on every joint (per unit of c)."""
    best = math.inf
    for t0, cc, a in zip(tau0, c, allow):
        if abs(t0) > a:
            return 0.0
        if abs(cc) < 1e-12:
            continue
        best = min(best, ((a - t0) / cc) if cc > 0 else ((-a - t0) / cc))
    return max(0.0, best)


def allow_mass(A, fixed, d_mm, allow, f=1.0):
    """Allowable hardware mass (g) at d_mm past the gripper origin: the minimum over the whole shoulder_lift /
    elbow / wrist_flex range of the largest m with |f (tau_arm + tau_fixed + m c)| <= allow on every joint.
    Optimised (bounded Nelder-Mead from every grid seed), not read at the zero pose. A must be arm_only."""
    def g(x):
        t = tau_loads(A, x, fixed)
        c = A.grav_point(1000.0, d_mm)[1:4]
        return min(10.0, m_max(f * t, f * c, allow))
    v, x = maximize(A, lambda x: -g(x))
    return -1000 * v, x


def payload():
    links, joints = urdf_load()
    tcp_d = V["H_to_pivot_mm"] + V["r_c_mm"]  # pad centroid, where the cloth and the tension act
    A = Arm()
    out = {"tcp_d_mm": tcp_d}
    # --- cross-check stock and arm-only at the zero (horizontal) pose
    A.stock(); A.pose({})
    mj_stock = A.bias()
    A.arm_only(); A.pose({})
    mj_arm = A.bias()
    u_stock, _ = urdf_gravity(links, joints, {})
    u_arm, _ = urdf_gravity(links, joints, {}, drop=("gripper", "jaw"))
    items = mass_items(58.0, FINGER_L)
    pts = [("gripper", g / 1000, [0, 0, -d / 1000]) for _, g, d, _ in items]
    u_new, _ = urdf_gravity(links, joints, {}, drop=("gripper", "jaw"), points=pts)
    mj_new = mj_arm + sum(A.grav_point(g, d) for _, g, d, _ in items)
    A.lump(items); A.pose({})
    mj_new_lumped = A.bias()
    A.arm_only(); A.pose({})
    xcheck = {}
    for i, n in enumerate(JOINTS[1:4], start=1):
        xcheck[n] = {"urdf_hand_stock": r(u_stock[n]), "mujoco_stock": r(mj_stock[i]),
                     "urdf_hand_arm_only": r(u_arm[n]), "mujoco_arm_only": r(mj_arm[i]),
                     "urdf_hand_new_DS3218": r(u_new[n]), "mujoco_new_jacobian": r(mj_new[i]), "mujoco_new_lumped": r(mj_new_lumped[i])}
    out["crosscheck_zero_pose_Nm"] = xcheck
    lever_H = float(np.linalg.norm((A.point(0) - A.d.xanchor[A.jid["shoulder_lift"]])[:2]) * 1000)
    out["lever_shoulder_lift_to_gripper_origin_mm"] = r(lever_H, 1)
    # --- tension at the TCP, full extension, six directions (MuJoCo applyFT vs Jacobian hand calc)
    dirs = {"+x": [1, 0, 0], "-x": [-1, 0, 0], "+y": [0, 1, 0], "-y": [0, -1, 0], "+z": [0, 0, 1], "-z": [0, 0, -1]}
    ten = {}
    for k, v in dirs.items():
        F = V["tension_N"] * np.array(v, float)
        t1, t2 = A.force_applyFT(F, tcp_d), A.force_at(F, tcp_d)
        ten[k] = {n: r(t1[i]) for i, n in enumerate(JOINTS) if n != "shoulder_pan"} | {"jac_check_shoulder_lift": r(t2[1])}
    out["tension_full_ext_Nm_by_direction"] = ten
    # --- worst-case pose sweep (lumped new gripper, no camera and with camera)
    rng = lambda n, k: np.linspace(A.m.jnt_range[A.jid[n]][0], A.m.jnt_range[A.jid[n]][1], k)
    worst = {}
    for case, its in (("new_no_camera", items), ("new_with_camera", items + [("camera", V["camera_g"], V["camera_d"], "A")])):
        A.lump(its)
        best = {n: (0.0, None) for n in JOINTS[1:4]}
        for sl in rng("shoulder_lift", 36):
            for el in rng("elbow_flex", 36):
                for wf in rng("wrist_flex", 13):
                    A.pose({"shoulder_lift": sl, "elbow_flex": el, "wrist_flex": wf})
                    b = A.bias()
                    for i, n in enumerate(JOINTS[1:4], start=1):
                        if abs(b[i]) > best[n][0]:
                            best[n] = (abs(b[i]), [r(sl), r(el), r(wf)])
        A.pose({})
        z = A.bias()
        worst[case] = {n: {"max_abs_Nm": r(best[n][0]), "pose_sl_el_wf_rad": best[n][1], "zero_pose_Nm": r(abs(z[i]))}
                       for i, n in enumerate(JOINTS[1:4], start=1)}
    # optimiser seeds: the zero pose and every grid argmax; then refine each joint maximum (point masses on the
    # gripper body, identical to the lumped body, see crosscheck)
    SEEDS[:] = [np.zeros(3)] + [np.array(v[n]["pose_sl_el_wf_rad"], float) for v in worst.values() for n in v]
    A.arm_only()
    for case, its in (("new_no_camera", items), ("new_with_camera", items + [("camera", V["camera_g"], V["camera_d"], "A")])):
        for j, n in enumerate(JOINTS[1:4]):
            v, x = maximize(A, lambda x: abs(float(tau_loads(A, x, its)[j])))
            worst[case][n]["optimised_max_abs_Nm"] = r(v, 4)
            worst[case][n]["optimised_pose_sl_el_wf_rad"] = r(x, 3)
    out["worst_pose_sweep"] = worst
    # --- allowable hardware mass vs COM offset at the WORST pose (static hold and dynamic), zero pose for reference
    fixed_nc = [("cloth", V["cloth_g"], tcp_d), ("wiring", V["wiring_g"], V["wiring_d"])]
    fixed_c = fixed_nc + [("camera", V["camera_g"], V["camera_d"])]
    d_grid = np.arange(10, 81, 5.0)
    allow_tab = {}
    A.pose({})
    tau_arm = A.bias()[1:4]
    f_dyn = 1 + V["dyn_accel_g"]
    for kit, Ts in KITS.items():
        allow_tab[kit] = {}
        for cam, fx in (("no_camera", fixed_nc), ("with_camera", fixed_c)):
            st, dy, st0, poses = [], [], [], []
            for dd in d_grid:
                ms, xs = allow_mass(A, fx, dd, [V["hold_frac_arm"] * Ts] * 3)
                md, _ = allow_mass(A, fx, dd, [V["dyn_limit_frac"] * Ts] * 3, f_dyn)
                st.append(ms); dy.append(md); poses.append(r(xs, 3))
                A.pose({})
                tf = sum(A.grav_point(g, d) for _, g, d in fx)[1:4]
                st0.append(1000 * m_max(tau_arm + tf, A.grav_point(1000.0, dd)[1:4], [V["hold_frac_arm"] * Ts] * 3))
            allow_tab[kit][cam] = {"static_hold_g": r(st, 1), "dynamic_g": r(dy, 1),
                                   "governing_g": r(np.minimum(st, dy), 1), "static_worst_pose_sl_el_wf_rad": poses,
                                   "static_hold_zero_pose_g_reference": r(st0, 1)}
    out["allowable_hardware_mass_worst_pose"] = {"d_mm": d_grid.tolist(), "kits": allow_tab,
                                                 "note": "hardware = everything except cloth, camera and FSR wiring (fixed items at their own d); "
                                                         "each value is the minimum over the joint ranges (optimised), the zero-pose value is kept for reference only"}
    # --- feed poses: fingertip at bed height, tension 2 N horizontal in the worst of four directions
    tip_d = tcp_d + V["pad_from_tip_mm"]
    tilt = math.radians(V["tilt_max_deg"])
    feed = []
    for sl in rng("shoulder_lift", 81):
        for el in rng("elbow_flex", 81):
            for wf in rng("wrist_flex", 41):
                A.d.qpos[:] = 0
                A.d.qpos[A.m.jnt_qposadr[A.jid["shoulder_lift"]]] = sl
                A.d.qpos[A.m.jnt_qposadr[A.jid["elbow_flex"]]] = el
                A.d.qpos[A.m.jnt_qposadr[A.jid["wrist_flex"]]] = wf
                mujoco.mj_kinematics(A.m, A.d)
                v = -A.d.xmat[A.bg].reshape(3, 3)[:, 2]
                if -v[2] < math.cos(tilt):
                    continue
                tip = A.d.xpos[A.bg] + v * tip_d / 1000
                if abs(tip[2] - (V["bed_height_m"] + 0.005)) > 0.008 or A.d.xpos[A.bg][2] < tip[2]:
                    continue
                pan = A.d.xanchor[A.jid["shoulder_pan"]]
                rad = (tip - pan)[:2]
                reach = float(np.linalg.norm(rad))
                feed.append((reach, sl, el, wf, rad / max(reach, 1e-9)))
    per_bin = {}
    for reach, sl, el, wf, u in feed:
        A.pose({"shoulder_lift": sl, "elbow_flex": el, "wrist_flex": wf})
        ta = A.bias()[1:4]
        tf = sum(A.grav_point(g, d) for _, g, d in fixed_nc)[1:4]
        c40 = A.grav_point(1000.0, 40.0)[1:4]
        hdirs = [np.array([u[0], u[1], 0]), -np.array([u[0], u[1], 0]), np.array([-u[1], u[0], 0]), -np.array([-u[1], u[0], 0])]
        tts = [A.force_at(V["tension_N"] * h, tcp_d)[1:4] for h in hdirs]
        b = int(reach * 100)
        for kit, Ts in KITS.items():
            al = [V["hold_frac_arm"] * Ts] * 3
            mm = min(m_max(ta + tf + tt, c40, al) for tt in tts) * 1000
            key = (kit, b)
            if mm > per_bin.get(key, (-1,))[0]:
                per_bin[key] = (mm, [r(sl), r(el), r(wf)], r(max(abs(x) for tt in tts for x in tt[:1])))
    feed_tab = {kit: {f"{b / 100:.2f}": {"m_hw_max_g_at_d40": r(per_bin[(kit, b)][0], 1), "pose": per_bin[(kit, b)][1],
                                          "tension_sl_Nm_worst": per_bin[(kit, b)][2]}
                      for b in sorted({bb for (kk, bb) in per_bin if kk == kit})} for kit in KITS}
    ten_max = {}
    for kit, tab in feed_tab.items():
        inside = {b: v for b, v in tab.items() if float(b) <= V["reach_max_m"] + 1e-9}
        mx = max(v["tension_sl_Nm_worst"] for v in inside.values())
        ten_max[kit] = {"max_Nm": mx, "bins_m": [b for b, v in inside.items() if v["tension_sl_Nm_worst"] == mx]}
    out["feed_pose"] = {"n_poses": len(feed), "reach_range_m": [r(min(f[0] for f in feed)), r(max(f[0] for f in feed))],
                        "best_config_per_10mm_bin": feed_tab, "tension_sl_max_in_work_cell": ten_max}
    # --- dynamic check: min-jerk shoulder_lift swing ending at full extension (mj_inverse)
    A.lump(items)
    dyn = {}
    arm_dof = (A.m.dof_armature.copy(), A.m.dof_damping.copy(), A.m.dof_frictionloss.copy())
    for model_kind in ("rigid_body", "with_model_armature_damping"):
        if model_kind == "rigid_body":
            A.m.dof_armature[:] = 0; A.m.dof_damping[:] = 0; A.m.dof_frictionloss[:] = 0
        else:
            A.m.dof_armature[:], A.m.dof_damping[:], A.m.dof_frictionloss[:] = arm_dof
        rows = {}
        for Tm in (0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0):
            pk = 0.0
            for s, sgn in [(x, sg) for x in np.linspace(0, 1, 201) for sg in (1, -1)]:
                qd = V["swing_rad"] * (10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5)
                vd = V["swing_rad"] / Tm * (30 * s ** 2 - 60 * s ** 3 + 30 * s ** 4)
                ad = V["swing_rad"] / Tm ** 2 * (60 * s - 180 * s ** 2 + 120 * s ** 3)
                A.d.qpos[:] = 0; A.d.qvel[:] = 0; A.d.qacc[:] = 0
                # sgn +1: swing up from -swing to 0 (ends at full extension); -1: from 0 down to -swing (starts there)
                A.d.qpos[A.m.jnt_qposadr[A.jid["shoulder_lift"]]] = (-V["swing_rad"] + qd) if sgn > 0 else -qd
                A.d.qvel[A.dof["shoulder_lift"]] = vd * sgn
                A.d.qacc[A.dof["shoulder_lift"]] = ad * sgn
                mujoco.mj_inverse(A.m, A.d)
                pk = max(pk, abs(A.d.qfrc_inverse[A.dof["shoulder_lift"]]))
            rows[str(Tm)] = r(pk)
        dyn[model_kind] = rows
    A.m.dof_armature[:], A.m.dof_damping[:], A.m.dof_frictionloss[:] = arm_dof
    A.pose({})
    g_end = abs(A.bias()[1])
    dyn["static_at_end_Nm"] = r(g_end)
    dyn["min_swing_time_s_for_80pct_stall"] = {
        kit: {mk: next((float(t) for t, v in dyn[mk].items() if v <= V["dyn_limit_frac"] * Ts), None) for mk in ("rigid_body", "with_model_armature_damping")}
        for kit, Ts in KITS.items()}
    out["dynamic_swing"] = dyn
    out["_tau_arm_zero"] = r(tau_arm)
    return out, A


# ------------------------------------------------------------------ 2. finger force and torque
def F_req(mu_a, mu_b, T, SF, th_deg=0.0):
    th = math.radians(th_deg)
    den = (mu_a + mu_b) * math.cos(th) - 2 * math.sin(th)
    return math.inf if den <= 0 else SF * T / den


def T_servo(F, rc_mm, T_ten, x_f, eta):
    return (2 * F * rc_mm + T_ten * x_f) / 1000 / eta  # N*m


def grip():
    rc, xf = V["r_c_mm"], V["x_f_mm"]
    F_t = F_req(V["mu"], V["mu"], V["tension_N"], V["SF_slip"])
    th_c = math.degrees(math.asin((V["cloth_t_mm"] - V["closed_gap_mm"]) / (2 * rc)))
    out = {"F_target_N": r(F_t), "F_cap_N": V["F_cap_N"], "theta_contact_deg": r(th_c, 2),
           "F_target_asym_nail_N": r(F_req(V["mu_nail_low"], V["mu"], V["tension_N"], V["SF_slip"])),
           "ejection_limit_deg": r(math.degrees(math.atan(V["mu"])), 1)}
    Th = T_servo(F_t, rc, V["tension_N"], xf, V["eta"])
    Tp = T_servo(V["F_cap_N"], rc, V["tension_N"], xf, V["eta"])
    Th0 = 2 * F_t * rc / 1000 / V["eta"]
    out.update({"T_hold_Nm": r(Th), "T_hold_kgcm": r(Th / KGCM, 2), "T_hold_no_tension_term_Nm": r(Th0),
                "tension_term_Nm": r(Th - Th0), "T_peak_Nm": r(Tp), "T_peak_kgcm": r(Tp / KGCM, 2),
                "stall_needed_kgcm": r(Th / KGCM / V["hold_frac"], 2)})
    # lever vs finger length and contact position
    Ls = np.arange(30, 71, 5.0)
    out["lever_vs_L"] = {"L_mm": Ls.tolist(), "r_c_mm": r(Ls + V["root_mm"] - V["pad_from_tip_mm"], 1),
                         "T_hold_kgcm": r([T_servo(F_t, L + V["root_mm"] - V["pad_from_tip_mm"], V["tension_N"], xf, V["eta"]) / KGCM for L in Ls], 2),
                         "contact_at_tip_vs_10mm_up_mm": [r(V["root_mm"] + FINGER_L), r(V["root_mm"] + FINGER_L - 10)]}
    # jaw angle: required force (ejection) and torque vs pad angle at contact
    ths = [0, 1, 2, 5, 10, 15]
    out["jaw_angle"] = {"theta_deg": ths, "F_req_N": [r(F_req(V["mu"], V["mu"], V["tension_N"], V["SF_slip"], t)) for t in ths],
                        "T_hold_kgcm": [r(T_servo(F_req(V["mu"], V["mu"], V["tension_N"], V["SF_slip"], t), rc, V["tension_N"], xf, V["eta"]) / KGCM, 2) for t in ths],
                        "theta_c_for_plies": {str(n): r(math.degrees(math.asin(max(-1, (n * V["cloth_t_mm"] - V["closed_gap_mm"]) / (2 * rc)))), 2) for n in (1, 2, 4, 10)}}
    # preload / overtravel vs stiffness
    ov = []
    for k in V["k_sweep_N_mm"]:
        d_t, d_c = F_t / k, V["F_cap_N"] / k
        th_t, th_cap = math.degrees(d_t / rc), math.degrees(d_c / rc)
        F_at_min = k * rc * math.radians(th_c - V["theta_min_deg"])
        ov.append({"k_N_mm": k, "overtravel_target_mm": r(d_t, 2), "overtravel_target_deg": r(th_t, 2),
                   "theta_hold_deg": r(th_c - th_t, 2), "overtravel_cap_deg": r(th_cap, 2),
                   "F_at_theta_min_N": r(F_at_min, 2), "hold_reachable_before_theta_min": th_c - th_t >= V["theta_min_deg"],
                   "force_per_deg_N": r(k * rc * math.pi / 180, 3)})
    out["overtravel"] = ov
    # speed requirement
    free = V["theta_open_deg"] - th_c - V["near_contact_deg"]
    th_over = math.degrees(F_t / V["k_tip_N_mm"] / rc)
    t_near = V["near_contact_deg"] / V["near_contact_speed"]
    t_over = th_over / V["overtravel_speed_max"]
    t_free = V["close_time_s"] - t_near - t_over
    w_req = V["k_trap"] * free / t_free
    out["speed"] = {"free_travel_deg": r(free, 2), "t_near_s": r(t_near), "t_over_s_at_ramp_ceiling": r(t_over),
                    "t_free_budget_s": r(t_free), "no_load_speed_required_deg_s": r(w_req, 1),
                    "equiv_s_per_60deg": r(60 / w_req, 3)}
    # sensitivity (tornado) on T_hold
    base = dict(mu_a=V["mu"], mu_b=V["mu"], T=V["tension_N"], SF=V["SF_slip"], rc=rc, eta=V["eta"], th=0.0, xf=xf)

    def Tfun(p):
        return T_servo(F_req(p["mu_a"], p["mu_b"], p["T"], p["SF"], p["th"]), p["rc"], p["T"], p["xf"], p["eta"]) / KGCM
    ranges = {"mu both pads 0.3-0.6": ({"mu_a": .6, "mu_b": .6}, {"mu_a": .3, "mu_b": .3}),
              "nail mu 0.4-0.25 (finger A)": ({"mu_a": .4}, {"mu_a": V["mu_nail_low"]}),
              "tension 1-3 N": ({"T": 1.0}, {"T": 3.0}),
              "slip SF 1.5-2.5": ({"SF": 1.5}, {"SF": 2.5}),
              "r_c 55-80 mm": ({"rc": 55.0}, {"rc": 80.0}),
              "eta 0.95-0.70": ({"eta": .95}, {"eta": .70}),
              "pad angle 0-5 deg": ({"th": 0.0}, {"th": 5.0}),
              "pad offset x_f 11.5-14.5 mm": ({"xf": 11.5}, {"xf": 14.5})}
    tor = {}
    for k, (lo, hi) in ranges.items():
        tor[k] = [r(Tfun(base | lo), 2), r(Tfun(base | hi), 2)]
    out["tornado_T_hold_kgcm"] = {"base": r(Tfun(base), 2), "ranges": tor}
    # T_hold vs r_c for mu set (plot data)
    rcs = np.arange(40, 91, 2.0)
    out["T_hold_vs_rc"] = {"r_c_mm": rcs.tolist(), **{f"mu_{m}": r([T_servo(F_req(m, m, V["tension_N"], V["SF_slip"]), x, V["tension_N"], xf, V["eta"]) / KGCM for x in rcs], 2) for m in (0.3, 0.4, 0.5, 0.6)}}
    return out


# ------------------------------------------------------------------ 3. actuator trade study
def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def stall_at(row, v):
    """Stall torque (kg*cm) at rail voltage v: piecewise-linear over every published (V, torque) point
    (low, optional mid, high); below the lowest point scaled by v / V; above the highest point held flat."""
    pts = sorted({(fnum(row.get(vk)), fnum(row.get(tk))) for tk, vk in (("torque_low_kgcm", "torque_low_at_V"),
                                                                      ("torque_mid_kgcm", "torque_mid_at_V"),
                                                                      ("torque_high_kgcm", "torque_high_at_V"))
                  if fnum(row.get(vk)) and fnum(row.get(tk))})
    if not pts:
        return None
    if v <= pts[0][0]:
        return pts[0][1] * min(1.0, v / pts[0][0])
    if v >= pts[-1][0]:
        return pts[-1][1]
    return float(np.interp(v, [p[0] for p in pts], [p[1] for p in pts]))


def speed_s60(row, v):
    a, b = fnum(row["speed_low_s_per_60deg"]), fnum(row["speed_high_s_per_60deg"])
    vl, vh = fnum(row["voltage_min_V"]) or 4.8, fnum(row["voltage_max_V"]) or 6.0
    if a and b:
        return a + (b - a) * (min(max(v, vl), vh) - vl) / max(vh - vl, 1e-9)
    return a or b


GEARBOX_LIMIT = {"M01": 2.0, "M02": 2.5, "M03": 2.5, "M04": 2.0}  # kg*cm, S Pololu category page (actuators.csv notes)
SPEC_CONF = {  # 0..1 [A], reason in the doc
    "A17": 0.5, "A18": 0.4, "A19": 0.8, "A20": 0.4, "A13": 0.9, "A16": 0.3,
    "M01": 0.9, "M02": 0.9, "M03": 0.9, "M04": 0.5, "W01": 0.5, "W02": 0.4, "L01": 0.9}


def close_time(w0_deg_s, T_hold, T_stall, th_c, th_over):
    """Close from theta_open to theta_hold: free travel at no-load speed (trapezoid factor), last 3 deg at the
    near-contact ceiling, overtravel at the loaded speed (mean torque T_hold/2) capped by the ramp ceiling."""
    if not w0_deg_s:
        return None
    free = V["theta_open_deg"] - th_c - V["near_contact_deg"]
    t = V["k_trap"] * free / w0_deg_s
    t += V["near_contact_deg"] / min(V["near_contact_speed"], w0_deg_s)
    w_ld = w0_deg_s * max(0.0, 1 - 0.5 * T_hold / T_stall) if T_stall else w0_deg_s
    return t + (th_over / min(w_ld, V["overtravel_speed_max"]) if w_ld > 0 else math.inf)


def stage_mass(N):
    """Printed spur stage (pinion + gear, m0.8, b 5 mm, PETG, lightened)."""
    dp = 0.8 * V["stage_pinion_z"]
    dg = dp * N
    return 1.25e-3 * V["stage_gear_fill"] * 5 * math.pi / 4 * (dp ** 2 + dg ** 2)


def actuators(gr, A, V_rail, V_hi, hold_frac):
    """Hard filter over every csv row, then the gearmotor/worm + printed-stage fallback branch.
    V_rail: rail voltage for hold capacity and speed (low end of the band); V_hi: high end (LC3, rating check);
    hold_frac: the hold rule applied to EVERY brushed-DC-driven actuator (servos and gearmotors alike)."""
    rows = list(csv.DictReader(ACT_CSV.open(encoding="utf-8")))
    Th_req = gr["T_hold_Nm"]
    Tp_req = gr["T_peak_Nm"]
    th_c = gr["theta_contact_deg"]
    th_over = math.degrees(gr["F_target_N"] / V["k_tip_N_mm"] / V["r_c_mm"])
    t_lim = V["close_time_s"]

    def mass_ok(its, kit="C001_7p4V"):
        util, _ = arm_util(A, its, kit)  # worst pose over the joint ranges, not the zero pose
        return util <= 1.0, util
    res = []
    for row in rows:
        rid, cat = row["id"], row["category"]
        e = {"id": rid, "model": row["model"], "category": cat, "price": fnum(row["price_usd"]), "mass_g": fnum(row["weight_g"]),
             "feedback": row["feedback"], "fail": []}
        dims = [fnum(row[k]) for k in ("dim_L_mm", "dim_W_mm", "dim_H_mm")]
        stock = (row.get("stock_checked") or "") + " " + row["notes"]
        e["stock"] = 0.0 if any(s in stock.lower() for s in ("sold out", "out of stock", "unavailable")) else (1.0 if "in stock" in stock.lower() else 0.5)
        if rid.startswith("A"):
            kind = "continuous" if "continuous" in cat else "servo"
        elif rid.startswith("W"):
            kind = "worm"
        elif rid.startswith("L"):
            kind = "linear"
        else:
            kind = "gearmotor"
        e["kind"] = kind
        if kind == "continuous":
            e["fail"].append("no position control (continuous rotation)")
        if e["price"] is None or e["price"] > 50:
            e["fail"].append("price > $50")
        T3 = None
        if kind in ("servo", "continuous"):
            vm = fnum(row["voltage_max_V"]) or 6.0
            if V_hi > vm + 1e-9:
                e["fail"].append(f"rail {V_hi:g} V > rated max {vm:g} V")
            Ts = stall_at(row, min(V_rail, vm))
            Ts_hi = stall_at(row, min(V_hi, vm))
            s60 = speed_s60(row, min(V_rail, vm))
            w0 = 60 / s60 if s60 else (fnum(row["no_load_speed_rpm"]) or 0) * 6 or None
            cap = hold_frac * Ts * KGCM if Ts else None
            e.update({"stall_kgcm": r(Ts, 2), "stall_kgcm_at_V_hi": r(Ts_hi, 2), "hold_capacity_Nm": r(cap), "voltage_max_V": vm})
            Tst = Ts * KGCM if Ts else None
            T3 = Ts_hi * KGCM if Ts_hi else None
        elif kind == "gearmotor":
            Ts = fnum(row["torque_high_kgcm"])
            lim = GEARBOX_LIMIT.get(rid)
            cap_k = (min(hold_frac * Ts, lim) if lim else hold_frac * Ts) if Ts else None
            cap = cap_k * KGCM if cap_k else None
            hv = min(hold_frac, V["vendor_hold_rule"].get(rid, 1.0))
            cap_vk = (min(hv * Ts, lim) if lim else hv * Ts) if Ts else None
            e["hold_capacity_vendor_rule_Nm"] = r(cap_vk * KGCM) if cap_vk else None
            w0 = (fnum(row["no_load_speed_rpm"]) or 0) * 6 or None
            e.update({"stall_kgcm": Ts, "gearbox_limit_kgcm": lim, "hold_capacity_Nm": r(cap), "drive_V": 6.0})
            Tst = T3 = Ts * KGCM if Ts else None
        elif kind == "worm":
            Ts = fnum(row["torque_high_kgcm"])
            cap = Ts * KGCM  # self-locking: holds at the gearbox rating with no current [A]
            w0 = (fnum(row["no_load_speed_rpm"]) or 0) * 6
            e.update({"stall_kgcm": Ts, "hold_capacity_Nm": r(cap), "self_locking": True})
            Tst = T3 = Ts * KGCM
        else:  # linear, via a crank on knuckle A spanning the full jaw range
            lin = LINEAR[rid]
            span = math.radians(V["theta_open_deg"] - V["theta_min_deg"])
            arm = lin["stroke_mm"] / span
            cap = lin["F_backdrive_N"] * arm / 1000  # passive hold (no duty limit)
            Tst = T3 = lin["F_peak_N"] * arm / 1000
            w0 = math.degrees(lin["v_noload_mm_s"] / arm)
            e.update({"crank_arm_mm": r(arm, 1), "hold_capacity_Nm": r(cap), "drive_torque_Nm": r(Tst)})
        if cap is None:
            e["fail"].append("no torque data")
        elif cap < Th_req:
            e["fail"].append(f"hold capacity {cap:.3f} < {Th_req:.3f} N*m")
        e["hold_margin"] = r(cap / Th_req) if cap else None
        cv = e.get("hold_capacity_vendor_rule_Nm", cap)
        e["hold_margin_vendor_rule"] = r(cv / Th_req) if cv else None
        e["r_c_max_mm"] = r((cap * 1000 * V["eta"] - V["tension_N"] * V["x_f_mm"]) / (2 * gr["F_target_N"]), 1) if cap else None
        tc = close_time(w0, Th_req, Tst, th_c, th_over) if (w0 and Tst and Tst > Th_req) else None
        e["close_time_s"] = r(tc)
        e["no_load_deg_s"] = r(w0, 1)
        if tc is None:
            if cap and cap >= Th_req:
                e["fail"].append("no speed data")
        elif tc > t_lim:
            e["fail"].append(f"close {tc:.2f} s > {t_lim} s {SELECTION_BASIS_LABEL}")
        if e["mass_g"] is not None:
            ok, util = mass_ok(mass_items(e["mass_g"], FINGER_L))
            e["arm_util_C001_7p4V"] = r(util)
            if not ok:
                e["fail"].append(f"arm budget {util:.0%} of C001 7.4 V hold (worst pose)")
        else:
            e["fail"].append("no mass data")
        if all(dims):
            dd = sorted(dims, reverse=True)
            lim = sorted(V["envelope_max_mm"], reverse=True)
            if dd[0] > lim[0] or dd[1] > lim[1] or dd[2] > lim[2]:
                e["fail"].append(f"envelope {dd[0]:.0f}x{dd[1]:.0f}x{dd[2]:.0f} mm")
            e["volume_cm3"] = r(dims[0] * dims[1] * dims[2] / 1000, 1)
            e["envelope_note"] = "body only; mounting ears checked separately where flange_span_mm is published"
        else:
            e["envelope_note"] = "dimensions not published in text: not checked"
        fl = fnum(row.get("flange_span_mm"))
        if fl:
            e["flange_span_mm"] = fl
            if fl > V["flange_max_mm"]:
                e["fail"].append(f"ear span {fl:g} mm > {V['flange_max_mm']:g} mm")
        e["peak_can_exceed_cap"] = bool(Tst and Tst > Tp_req)
        e["T_mesh_LC3_Nm"] = r(T3) if T3 else None
        e["pass"] = not e["fail"]
        res.append(e)
    # --- fallback branch: DC gearmotor or worm + printed spur stage N (hold rule, then cap, then speed); motors driven
    # through the H-bridge at their 6 V rating [A]
    fb = []
    for e in res:
        if e["kind"] not in ("gearmotor", "worm") or e["price"] is None or e["price"] > 50 or not e.get("hold_capacity_Nm") \
                or e["mass_g"] is None:
            continue
        row = next(x for x in rows if x["id"] == e["id"])
        cap = e["hold_capacity_Nm"]
        lim = (e.get("gearbox_limit_kgcm") or e["stall_kgcm"]) * KGCM
        for tag in ("hold", "hold_and_carry_cap"):
            for n_st in (1, 2):
                eta = V["stage_eta"] ** n_st
                N_hold = Th_req / (cap * eta)
                N_cap = Tp_req / (lim * eta)
                N = max(1.0, math.ceil((N_hold if tag == "hold" else max(N_hold, N_cap)) * 4) / 4)
                if N ** (1 / n_st) * 0.8 * V["stage_pinion_z"] <= 45.0:
                    break
            w0 = (fnum(row["no_load_speed_rpm"]) or 0) * 6 / N
            Tst = min(e["stall_kgcm"], e.get("gearbox_limit_kgcm") or 1e9) * KGCM * N * eta
            tc = close_time(w0, Th_req, e["stall_kgcm"] * KGCM * N * eta, th_c, th_over)
            cid = e["id"] + f"+{N:g}:1"
            dup = next((x for x in fb if x["id"] == cid), None)
            if dup:  # both sizings give the same ratio: one configuration, both tags
                dup["sizing"] += "+" + tag
                continue
            ms = e["mass_g"] + n_st * stage_mass(N ** (1 / n_st))
            hm = cap * N * eta / Th_req
            hm_v = (e.get("hold_capacity_vendor_rule_Nm") or cap) * N * eta / Th_req
            ok_m, util = mass_ok(mass_items(ms, FINGER_L))
            f = [] if tc <= t_lim else [f"close {tc:.2f} s > {t_lim} s {SELECTION_BASIS_LABEL}"]
            if hm < 1 - 1e-9:
                f.append(f"hold margin {hm:.2f}")
            if N ** (1 / n_st) * 0.8 * V["stage_pinion_z"] > 45.0:
                f.append("stage gear > 45 mm")
            if not ok_m:
                f.append(f"arm budget {util:.0%}")
            fb.append({"id": cid, "base": e["id"], "hold_margin_vendor_rule": r(hm_v), "model": e["model"] + f" + printed {N:g}:1 spur ({n_st} stage)", "sizing": tag,
                       "N": N, "stages": n_st, "stage_gear_d_mm": r(N ** (1 / n_st) * 0.8 * V["stage_pinion_z"], 1),
                       "N_required_hold": r(N_hold, 2), "N_required_carry_cap": r(N_cap, 2),
                       "mass_g": r(ms, 1), "stage_mass_g": r(ms - e["mass_g"], 1), "price": r(e["price"] + 5.0, 2), "price_note": "+$5 H-bridge [A]",
                       "close_time_s": r(tc), "output_no_load_deg_s": r(w0, 1), "hold_margin": r(hm), "T_mesh_LC3_Nm": r(Tst),
                       "arm_util_C001_7p4V": r(util), "feedback": e["feedback"], "stock": e["stock"], "kind": "fallback",
                       "self_locking": e["kind"] == "worm", "fail": f, "pass": not f,
                       "volume_cm3": None})
    return res, fb


CRIT = {  # weight, description
    "torque_margin": (0.20, "hold capacity / required, 1.0 -> 0, >= 1.6 -> 1"),
    "overload": (0.05, "LC3 torque the drive can push through the mesh, 4 N*m -> 0, <= 1.5 N*m -> 1 (gear lane burden)"),
    "mass": (0.20, "actuator + stage mass, 80 g -> 0, 10 g -> 1"),
    "availability": (0.15, "in stock 1, listed 0.5, sold out 0"),
    "cost": (0.10, "$50 -> 0, <= $10 -> 1"),
    "spec_confidence": (0.10, "datasheet with currents, consistent sources"),
    "sensing": (0.05, "pot or encoder feedback = extra analog input and stall detection"),
    "course_dc_motor": (0.05, "certainty it meets the DC-motor rule (servo 0.5 pending GSI, bare DC motor 1)"),
    "simplicity": (0.05, "parts count (servo 1, gearmotor + driver + printed stage 0.3)"),
    "speed_margin": (0.05, f"1 - close_time / {GR['close_time_selection_basis_s']} s; {SELECTION_BASIS_LABEL}"),
}
W0 = {k: v[0] for k, v in CRIT.items()}


def utilities(c):
    fbk = c.get("feedback") or ""
    fb = 0.0 if fbk in ("", "none") else 1.0
    kind = c["kind"]
    return {"torque_margin": float(np.clip((c["hold_margin"] - 1) / 0.6, 0, 1)),
            "mass": float(np.clip((80 - c["mass_g"]) / 70, 0, 1)),
            "overload": float(np.clip((4.0 - c["T_mesh_LC3_Nm"]) / 2.5, 0, 1)),
            "availability": c["stock"],
            "cost": float(np.clip((50 - c["price"]) / 40, 0, 1)),
            "spec_confidence": SPEC_CONF.get(c.get("base", c["id"]), 0.5),
            "sensing": fb,
            "course_dc_motor": 0.5 if kind == "servo" else 1.0,
            "simplicity": 1.0 if kind == "servo" else 0.3,
            "speed_margin": float(np.clip(1 - c["close_time_s"] / V["close_time_s"], 0, 1))}


def score(cands, w):
    ws = np.array([w[k] for k in CRIT])
    ws = ws / ws.sum()
    return {c["id"]: float(np.dot(ws, [c["u"][k] for k in CRIT])) for c in cands}


def vendor_ok(c):
    """True when the configuration also holds under its own vendor's published hold rule (never looser than INPUT)."""
    return (c.get("hold_margin_vendor_rule") or 0) >= 1 - 1e-9


def trade(res, fb, vendor_consistent=False):
    """Weighted scoring over configurations that pass every hard constraint. vendor_consistent=True keeps only those
    that also hold under their vendor's published hold rule (the pool the recommendation draws from)."""
    cands = [c for c in res if c["pass"]] + [c for c in fb if c["pass"]]
    if vendor_consistent:
        cands = [c for c in cands if vendor_ok(c)]
    near = [c for c in res if not c["pass"] and c["kind"] == "servo" and c.get("hold_margin") and c["hold_margin"] >= 0.75
            and len(c["fail"]) == 1 and c["fail"][0].startswith("hold")]
    for c in cands:
        c["u"] = utilities(c)
    base = score(cands, W0)
    rank = sorted(base, key=lambda k: -base[k])
    sens = {}
    for k in CRIT:
        for f in (0.5, 1.5):
            w = dict(W0)
            w[k] *= f
            s = score(cands, w)
            sens[f"{k} x{f}"] = sorted(s, key=lambda i: -s[i])
    rng = np.random.default_rng(102)
    wins = {c["id"]: 0 for c in cands}
    top3 = {c["id"]: 0 for c in cands}
    NMC = 4000
    for _ in range(NMC if cands else 0):
        w = {k: W0[k] * rng.uniform(0.5, 1.5) for k in CRIT}
        s = score(cands, w)
        order = sorted(s, key=lambda i: -s[i])
        wins[order[0]] += 1
        for i in order[:3]:
            top3[i] += 1
    return {"vendor_consistent_only": vendor_consistent,
            "weights": {k: {"w": v[0], "rule": v[1]} for k, v in CRIT.items()},
            "candidates": [{"id": c["id"], "model": c["model"], "u": {k: r(v, 3) for k, v in c["u"].items()}, "score": r(base[c["id"]], 3),
                            "vendor_rule_ok": vendor_ok(c), "hold_margin": c["hold_margin"],
                            "hold_margin_vendor_rule": c.get("hold_margin_vendor_rule")} for c in cands],
            "rank": rank, "one_at_a_time": sens,
            "top_stable_fraction": r(sum(1 for v in sens.values() if v[0] == rank[0]) / len(sens), 3) if rank else None,
            "monte_carlo_n": NMC, "p_rank1": {k: r(v / NMC, 3) for k, v in wins.items()},
            "p_top3": {k: r(v / NMC, 3) for k, v in top3.items()},
            "near_miss_servos": [{"id": c["id"], "model": c["model"], "hold_margin": c["hold_margin"], "r_c_max_mm": c["r_c_max_mm"]} for c in near]}


DC_RULE = ("best base-weight score among DC gearmotor/worm + printed-stage configurations that pass every selection-time "
           "hard constraint AND hold under their vendor's published rule; if none, best score among those (vendor-consistent) "
           "whose ONLY failure is the selection basis 0.5 s (R19 at selection; superseded 2026-10-12) with close <= 0.6 s "
           "(the historical near-miss rule; current R19 requirement is 0.75 s)")


def dc_pick(fb):
    for c in fb:
        c["u"] = utilities(c)
        c["score"] = r(score([c], W0)[c["id"]], 3)
    ok = [c for c in fb if c["pass"] and vendor_ok(c)]
    near = [c for c in fb if vendor_ok(c) and len(c["fail"]) == 1 and c["fail"][0].startswith("close") and c["close_time_s"] <= 0.6]
    pool = ok or near
    best = max(pool, key=lambda c: c["score"]) if pool else None
    excluded = [c["id"] for c in fb if c["pass"] and not vendor_ok(c)]
    return {"rule": DC_RULE, "pick": best["id"] if best else None, "passes_R19": bool(ok),
            "requires_R19_0p6s": bool(best) and not ok,
            "passing_but_exceed_vendor_rule": excluded,
            "pool": [{"id": c["id"], "score": c["score"], "close_time_s": c["close_time_s"], "mass_g": c["mass_g"],
                      "hold_margin": c["hold_margin"], "hold_margin_vendor_rule": c["hold_margin_vendor_rule"], "fail": c["fail"]}
                     for c in sorted(pool, key=lambda c: -c["score"])]}


REC_RULE = ("primary and backup = params.json ruled_selection, held by Douglas's 2026-10-12 ruling; "
            "computed_rank = the full trade_vendor_consistent rank on the superseded 0.5 s selection basis; "
            "computed_top = its first entry; DC branch = dc_pick rule")


def recommend(res, fb, tr_vc):
    allc = {c["id"]: c for c in res + fb}
    pool = tr_vc["rank"]
    selection = P["ruled_selection"]
    primary = selection["primary_actuator"]["id"]
    backup = selection["backup_actuator"]["id"]
    computed_top = pool[0] if pool else None
    dc = dc_pick(fb)
    return {"rule": REC_RULE, "primary": primary, "primary_in_stock": allc[primary]["stock"] >= 1.0,
            "backup": backup, "computed_rank": list(pool), "computed_top": computed_top,
            "note": f"The refreshed catalogue ranks {computed_top} above ruled pick {primary}; Douglas's 2026-10-12 ruling holds {primary} primary and {backup} backup.",
            "selection_source": selection["primary_actuator"]["source"], "dc_branch": dc["pick"], "dc": dc}


def rollup(A, servo_g, name):
    out = {"actuator_part": name}
    for cam in (False, True):
        its = mass_items(servo_g, FINGER_L, [("camera", V["camera_g"], V["camera_d"], "A")] if cam else [])
        A.arm_only(); A.pose({})
        tau0 = A.bias()[1:4] + sum(A.grav_point(g, d) for _, g, d, _ in its)[1:4]
        m = sum(x[1] for x in its)
        com = sum(x[1] * x[2] for x in its) / m
        util = {}
        for k in KITS:
            u, x = arm_util(A, its, k)
            util[k] = {"util": r(u, 4), "pose_sl_el_wf_rad": r(x, 3)}
        out["with_camera" if cam else "no_camera"] = {
            "items": [{"name": n, "g": r(g, 1), "d_mm": r(d, 1), "tag": t} for n, g, d, t in its],
            "mass_g": r(m, 1), "com_mm": r(com, 1),
            "util": {k: v["util"] for k, v in util.items()}, "worst_pose": {k: v["pose_sl_el_wf_rad"] for k, v in util.items()},
            "util_zero_pose_reference": {k: r(float(np.max(np.abs(tau0) / (V["hold_frac_arm"] * Ts))), 4) for k, Ts in KITS.items()}}
    hw = [x for x in mass_items(servo_g, FINGER_L) if x[0] not in ("cloth at pad", "FSR + wiring")]
    hw_g = sum(x[1] for x in hw)
    hw_d = sum(x[1] * x[2] for x in hw) / hw_g
    out["hardware_g"] = r(hw_g, 1)
    out["hardware_com_mm"] = r(hw_d, 1)
    tcp_d = V["H_to_pivot_mm"] + V["r_c_mm"]
    fixed_nc = [("cloth", V["cloth_g"], tcp_d), ("wiring", V["wiring_g"], V["wiring_d"])]
    fixed_c = fixed_nc + [("camera", V["camera_g"], V["camera_d"])]
    A.arm_only()
    allow = {}
    for k, Ts in KITS.items():
        a_nc, _ = allow_mass(A, fixed_nc, hw_d, [V["hold_frac_arm"] * Ts] * 3)
        a_c, _ = allow_mass(A, fixed_c, hw_d, [V["hold_frac_arm"] * Ts] * 3)
        allow[k] = {"allowable_hw_g_no_camera": r(a_nc, 1), "margin_g_no_camera": r(a_nc - hw_g, 1),
                    "allowable_hw_g_with_camera": r(a_c, 1), "margin_g_with_camera": r(a_c - hw_g, 1)}
    out["allowable_at_hardware_com_worst_pose"] = allow
    return out


# ------------------------------------------------------------------ figures
C = ["#2b6cb0", "#dd6b20", "#2f855a", "#9b2c2c", "#6b46c1", "#718096"]


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=.25)


def figures(pay, gr, run, roll, rail_label):
    res, tr = run["actuators"], run["trade"]
    FIG.mkdir(parents=True, exist_ok=True)
    # payload_allowable_mass.png (worst pose)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
    tab = pay["allowable_hardware_mass_worst_pose"]
    d = tab["d_mm"]
    for ax, cam in zip(axs, ("no_camera", "with_camera")):
        for i, (kit, v) in enumerate(tab["kits"].items()):
            kl = kit + (" [A: 6 V rating, optimistic]" if kit == "C001_5V" else "")
            ax.plot(d, v[cam]["static_hold_g"], color=C[i], lw=2, label=f"{kl} static hold (50 % stall)")
            ax.plot(d, v[cam]["dynamic_g"], color=C[i], lw=1.2, ls="--", label=f"{kl} dynamic (1.5 g, 80 % stall)")
        hw, hd = roll["hardware_g"], roll["hardware_com_mm"]
        ax.scatter([hd], [hw], color="k", zorder=5)
        ax.annotate(f"current estimate\n{hw:.0f} g at {hd:.0f} mm", (hd, hw), textcoords="offset points", xytext=(8, 8), fontsize=8)
        ax.set_title(f"Worst pose over the joint ranges, {cam.replace('_', ' ')}", fontsize=10)
        ax.set_xlabel("hardware COM past gripper origin d (mm)")
        style(ax)
        ax.set_ylim(0, 320)
    axs[0].set_ylabel("allowable gripper hardware mass (g)\n(net of cloth 13.5 g, wiring 5 g, camera)")
    h, lab = axs[0].get_legend_handles_labels()
    fig.legend(h, lab, fontsize=7, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("SO-101 payload: allowable gripper mass vs COM offset (MuJoCo so101_old_calib, optimised worst pose)", fontsize=11)
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    fig.savefig(FIG / "payload_allowable_mass.png", dpi=150)
    plt.close(fig)
    # payload_feed_reach.png
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, (kit, t) in enumerate(pay["feed_pose"]["best_config_per_10mm_bin"].items()):
        xs = [float(k) + 0.005 for k in t]
        ax.plot(xs, [v["m_hw_max_g_at_d40"] for v in t.values()], "o-", color=C[i], ms=3, label=kit)
    ax.axvline(V["reach_max_m"], color="k", ls=":", lw=1)
    ax.text(V["reach_max_m"] + .003, 20, "work-cell reach limit", fontsize=8)
    hw = roll["hardware_g"]
    ax.axhline(hw, color="k", lw=1)
    ax.text(0.11, hw + 5, f"current hardware estimate {hw:.0f} g", fontsize=8)
    ax.set_xlabel("fingertip reach from shoulder_pan axis (m)")
    ax.set_ylabel("allowable hardware mass at d = 40 mm (g)")
    ax.set_title("Feed poses: tip at bed height, 2 N tension (worst horizontal direction), best arm configuration", fontsize=9)
    ax.set_ylim(0, 600)
    style(ax); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(FIG / "payload_feed_reach.png", dpi=150); plt.close(fig)
    # actuator_torque_vs_lever.png
    fig, ax = plt.subplots(figsize=(9, 4.5))
    tv = gr["T_hold_vs_rc"]
    for i, m in enumerate((0.3, 0.4, 0.5, 0.6)):
        ax.plot(tv["r_c_mm"], tv[f"mu_{m}"], color=C[i], lw=2 if m == 0.4 else 1.2, label=f"required hold, mu = {m}")
    for e in res:
        if e["id"] in ("A13", "A16", "A17", "A18", "A19", "A20") and e.get("hold_capacity_Nm"):
            y = e["hold_capacity_Nm"] / KGCM
            ax.axhline(y, color="#555", lw=.8, ls="--")
            ax.text(41, y + .15, f"{e['id']} {e['model'].split('(')[0][:22]} 40 % stall", fontsize=7)
    ax.axvline(V["r_c_mm"], color="k", lw=1); ax.axvline(V["r_c_cad_mm"], color="k", lw=.8, ls=":")
    ax.text(V["r_c_mm"] + .5, 1, "design 65", fontsize=8); ax.text(V["r_c_cad_mm"] + .5, 1, "CAD 80", fontsize=8)
    ax.set_xlabel("perpendicular lever r_c (mm)"); ax.set_ylabel("servo torque (kg*cm)")
    ax.set_title(f"Hold torque required (2 N tension, SF 2, eta 0.85) vs servo 40 %-of-stall at {rail_label}", fontsize=9)
    style(ax); ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1.01, 0.5)); ax.set_ylim(0, 16)
    fig.tight_layout(); fig.savefig(FIG / "actuator_torque_vs_lever.png", dpi=150); plt.close(fig)
    # actuator_torque_tornado.png
    tor = gr["tornado_T_hold_kgcm"]
    items = sorted(tor["ranges"].items(), key=lambda kv: abs(kv[1][1] - kv[1][0]))
    fig, ax = plt.subplots(figsize=(7.5, 4))
    for i, (k, (lo, hi)) in enumerate(items):
        ax.barh(i, lo - tor["base"], left=tor["base"], color=C[0], alpha=.8)
        ax.barh(i, hi - tor["base"], left=tor["base"], color=C[1], alpha=.8)
        ax.text(max(lo, hi) + .1, i, f"{lo:.1f} / {hi:.1f}", va="center", fontsize=7)
    ax.set_yticks(range(len(items))); ax.set_yticklabels([k for k, _ in items], fontsize=8)
    ax.axvline(tor["base"], color="k", lw=1)
    ax.set_xlabel("required servo hold torque (kg*cm); base %.2f" % tor["base"])
    ax.set_title("Sensitivity of hold torque (first value / second value of each range)", fontsize=9)
    style(ax); fig.tight_layout(); fig.savefig(FIG / "actuator_torque_tornado.png", dpi=150); plt.close(fig)
    # actuator_scores.png
    cand = {c["id"]: c for c in tr["candidates"]}
    ids = tr["rank"]
    fig, ax = plt.subplots(figsize=(10, 1.2 + 0.45 * len(ids)))
    left = np.zeros(len(ids))
    wsum = sum(v[0] for v in CRIT.values())
    for j, (k, (w, _)) in enumerate(CRIT.items()):
        vals = np.array([cand[i]["u"][k] * w / wsum for i in ids])
        ax.barh(range(len(ids)), vals, left=left, color=plt.cm.tab10(j), label=k)
        left += vals
    for y, i in enumerate(ids):
        ax.text(left[y] + .005, y, f"{cand[i]['score']:.3f}", va="center", fontsize=7)
    ax.set_yticks(range(len(ids)))
    ax.set_yticklabels([f"{'* ' if not cand[i]['vendor_rule_ok'] else ''}{i}  {cand[i]['model'][:40]}" for i in ids], fontsize=7)
    ax.invert_yaxis(); ax.set_xlabel("weighted score (0-1)   * = holds only above its vendor's published 25 % rule (excluded from the recommendation)",
                                     fontsize=7)
    ax.legend(fontsize=6, loc="center left", bbox_to_anchor=(1.01, 0.5)); style(ax)
    ax.set_title(f"Configurations passing every hard constraint, rail {rail_label}, 40 % hold rule on every brushed-DC drive", fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / "actuator_scores.png", dpi=150); plt.close(fig)
    # actuator_weight_sensitivity.png (rank heatmap)
    cases = list(tr["one_at_a_time"])
    M = np.array([[tr["one_at_a_time"][c].index(i) + 1 for c in cases] for i in ids])
    fig, ax = plt.subplots(figsize=(10, 0.8 + 0.4 * len(ids)))
    im = ax.imshow(M, cmap="viridis_r", aspect="auto", vmin=1, vmax=len(ids))
    for a in range(M.shape[0]):
        for b in range(M.shape[1]):
            ax.text(b, a, M[a, b], ha="center", va="center", fontsize=6, color="w" if M[a, b] < len(ids) / 2 else "k")
    ax.set_xticks(range(len(cases))); ax.set_xticklabels(cases, rotation=70, fontsize=6)
    ax.set_yticks(range(len(ids))); ax.set_yticklabels(ids, fontsize=7)
    ax.set_title(f"Rank under each weight x0.5 / x1.5 (1 = best), {rail_label}", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=.02)
    fig.tight_layout(); fig.savefig(FIG / "actuator_weight_sensitivity.png", dpi=150); plt.close(fig)


def figure_rollup(rolls, rail_label):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    names = list(rolls)
    for j, n in enumerate(names):
        its = rolls[n]["no_camera"]["items"]
        bottom = 0
        for k, it in enumerate(its):
            ax.bar(j, it["g"], bottom=bottom, color=plt.cm.tab10(k), label=it["name"] if j == 0 else None)
            bottom += it["g"]
        u = rolls[n]["no_camera"]["util"]["C001_7p4V"]
        ax.text(j, bottom + 2, f"{bottom:.0f} g\n{u:.1%} of C001 7.4 V", ha="center", fontsize=7)
    ax.set_xticks(range(len(names))); ax.set_xticklabels([f"{n}\n{rolls[n]['actuator_part']}" for n in names], fontsize=7)
    ax.set_ylabel("gripper mass incl. cloth (g)"); style(ax)
    ax.legend(fontsize=6, loc="center left", bbox_to_anchor=(1.01, 0.5)); ax.set_ylim(0, 180)
    ax.set_title(f"Mass roll-up: primary, backup, DC branch (rail {rail_label}, no camera); label = worst-pose arm hold use", fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / "actuator_mass_rollup.png", dpi=150); plt.close(fig)


# ------------------------------------------------------------------ main
RUNS = {  # key -> (rail for hold/speed, rail for LC3/rating, hold rule applied to every brushed-DC actuator)
    "r40_6p0V": (V["V_servo"], V["V_servo"], V["hold_frac"]),
    "r40_design": (V_LO, V_HI, V["hold_frac"]),
    "r25_6p0V": (V["V_servo"], V["V_servo"], V["hold_frac_25"]),
    "r25_design": (V_LO, V_HI, V["hold_frac_25"]),
}


def main():
    csv_changed = extend_csv()
    pay, A = payload()
    gr = grip()
    runs = {}
    for key, (vl, vh, hf) in RUNS.items():
        res, fb = actuators(gr, A, vl, vh, hf)
        tr = trade(res, fb)
        tr_vc = trade(res, fb, vendor_consistent=True)
        runs[key] = {"V_rail_hold": vl, "V_rail_LC3": vh, "hold_frac": hf, "actuators": res, "fallback_branch": fb,
                     "trade": tr, "trade_vendor_consistent": tr_vc, "recommendation": recommend(res, fb, tr_vc)}
    D = runs["r40_design"]
    rows = {x["id"]: x for x in csv.DictReader(ACT_CSV.open(encoding="utf-8"))}
    # DS3218MG datasheet conflict: SpeedyFPV 19 kgcm @ 5 V vs Miuzei 18 kgcm @ 5 V; both 21.5 @ 6.8 V [S]
    a17 = dict(rows["A17"])
    a17m = dict(a17, torque_low_kgcm="18")
    conflict = {}
    for lab, v in (("6p0V", V["V_servo"]), ("low_end", V_LO), ("nominal", V["V_rail_design"]), ("high_end", V_HI)):
        for src, row in (("speedyfpv", a17), ("miuzei", a17m)):
            Ts = stall_at(row, v)
            conflict[f"{src}_{lab}"] = {"V": v, "stall_kgcm": r(Ts, 3),
                                        **{f"hold_margin_{int(hf * 100)}pct": r(hf * Ts * KGCM / gr["T_hold_Nm"], 4)
                                           for hf in (V["hold_frac"], V["hold_frac_25"])}}
    gear_lc3 = {}
    for key in ("r40_6p0V", "r40_design", "r25_design"):
        for e in [x for x in runs[key]["actuators"] if x["pass"]] + runs[key]["fallback_branch"]:
            T3 = e.get("T_mesh_LC3_Nm")
            if T3:
                gear_lc3[f"{e['id']}@{key}"] = {g: {"sigma_MPa": r(k * T3, 1), **{m: k * T3 <= a for m, a in V["lc3_allow_MPa"].items()}}
                                                for g, k in V["lewis_sigma_per_Nm"].items()} | {"T_LC3_Nm": T3}
    # break-even tension and friction for each passing servo at the LOW end of the design rail (hold capacity = T_servo(F_req))
    thresholds = {}
    k_T = T_servo(F_req(V["mu"], V["mu"], 1.0, V["SF_slip"]), V["r_c_mm"], 1.0, V["x_f_mm"], V["eta"])  # N*m per N of tension
    for key in ("r40_design", "r25_design"):
        for e in [x for x in runs[key]["actuators"] if x["pass"] and x["kind"] == "servo"]:
            cap = e["hold_capacity_Nm"]
            mu_min = V["SF_slip"] * V["tension_N"] * 2 * V["r_c_mm"] / (2 * (cap * 1000 * V["eta"] - V["tension_N"] * V["x_f_mm"]))
            thresholds[f"{e['id']}@{key}"] = {"V": V_LO, "tension_max_N": r(cap / k_T, 2), "mu_min": r(mu_min, 3)}
    rail_label = f"{V_LO:g} V (low end of {V['V_rail_design']:g} +/- {V['V_rail_tol']:g} V)"
    roll = rollup(A, 58.0, "DS3218MG (A17)")
    rolls = {}
    rec = D["recommendation"]
    selected_R19_check = {}
    for role in ("primary", "backup"):
        selected = next(c for c in D["actuators"] + D["fallback_branch"] if c["id"] == rec[role])
        selected_R19_check[role] = {"actuator": rec[role], "close_time_s": selected["close_time_s"],
                                    "limit_s": GR["close_time_max_s"],
                                    "passes": selected["close_time_s"] <= GR["close_time_max_s"]}
    for cid in dict.fromkeys(x for x in (rec["primary"], rec["backup"], rec["dc_branch"]) if x):
        c = next(x for x in D["actuators"] + D["fallback_branch"] if x["id"] == cid)
        rolls[cid] = rollup(A, c["mass_g"], c["model"].split("(")[0].strip()[:24])
    figures(pay, gr, D, roll, rail_label)
    figure_rollup(rolls, rail_label)
    out = {"inputs": {k: {"value": v[0], "tag": v[1], "note": v[2]} for k, v in INPUT.items()},
           "rail_band_V": {"low": V_LO, "nominal": V["V_rail_design"], "high": V_HI, "tag": "A (reversible)"},
           "csv_extended_this_run": csv_changed, "finger_length_mm": FINGER_L,
           "payload": pay, "grip": gr, "runs": runs, "datasheet_conflict_A17": conflict,
           "recommendation": D["recommendation"], "selected_actuator_R19_check": selected_R19_check,
           "recommendation_25pct_rule": runs["r25_design"]["recommendation"],
           "gear_LC3_check": gear_lc3, "breakeven_design_rail_low_end": thresholds,
           "rollup_design_point_A17": roll, "rollup_top3": rolls}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)), encoding="utf-8")
    brief = {"xcheck": pay["crosscheck_zero_pose_Nm"], "lever": pay["lever_shoulder_lift_to_gripper_origin_mm"],
             "worst": pay["worst_pose_sweep"],
             "allow": {k: {c: {dd: (v[c]["static_hold_g"][i], v[c]["dynamic_g"][i], v[c]["static_hold_zero_pose_g_reference"][i])
                               for i, dd in enumerate(pay["allowable_hardware_mass_worst_pose"]["d_mm"]) if dd in (20, 30, 40, 50)} for c in v}
                       for k, v in pay["allowable_hardware_mass_worst_pose"]["kits"].items()},
             "feed_tension_max": pay["feed_pose"]["tension_sl_max_in_work_cell"],
             "grip": {k: v for k, v in gr.items() if k in ("F_target_N", "T_hold_Nm", "T_hold_kgcm", "T_peak_Nm", "stall_needed_kgcm", "speed")},
             "runs": {key: {"pass": [(e["id"], e["hold_margin"], e["r_c_max_mm"], e["close_time_s"], e["arm_util_C001_7p4V"], e["T_mesh_LC3_Nm"])
                                     for e in run["actuators"] if e["pass"]],
                            "fails_servo_std": {e["id"]: e["fail"] for e in run["actuators"] if e["id"] in ("A13", "A16", "A17", "A18", "A19", "A20")},
                            "gearmotor_direct": {e["id"]: (e["hold_capacity_Nm"], e["fail"]) for e in run["actuators"] if e["kind"] in ("gearmotor", "worm", "linear")},
                            "fallback": [(f["id"], f["sizing"], f["N"], f["stage_gear_d_mm"], f["mass_g"], f["hold_margin"], f["hold_margin_vendor_rule"], f["close_time_s"],
                                          f["T_mesh_LC3_Nm"], f["arm_util_C001_7p4V"], f["fail"]) for f in run["fallback_branch"]],
                            "rank": run["trade"]["rank"], "scores": {c["id"]: c["score"] for c in run["trade"]["candidates"]},
                            "rank_vendor_consistent": run["trade_vendor_consistent"]["rank"],
                            "p1_vendor_consistent": run["trade_vendor_consistent"]["p_rank1"],
                            "stable_vendor_consistent": run["trade_vendor_consistent"]["top_stable_fraction"],
                            "one_at_a_time_first_vc": {k: (v[0] if v else None) for k, v in run["trade_vendor_consistent"]["one_at_a_time"].items()},
                            "p1": run["trade"]["p_rank1"], "p3": run["trade"]["p_top3"], "stable": run["trade"]["top_stable_fraction"],
                            "one_at_a_time_first": {k: (v[0] if v else None) for k, v in run["trade"]["one_at_a_time"].items()},
                            "reco": {k: v for k, v in run["recommendation"].items() if k != "dc"},
                            "dc_pool": run["recommendation"]["dc"]["pool"]}
                      for key, run in runs.items()},
             "conflict": conflict, "breakeven": thresholds,
             "gear_lc3": {k: v for k, v in gear_lc3.items() if k.split("@")[0] in ("A17", "A18", "A19", "A20") or "+" in k and k.endswith("design")},
             "roll_A17": {c: {"mass": roll[c]["mass_g"], "util": roll[c]["util"], "util0": roll[c]["util_zero_pose_reference"], "pose": roll[c]["worst_pose"]}
                          for c in ("no_camera", "with_camera")} | {"hw": (roll["hardware_g"], roll["hardware_com_mm"]),
                                                                   "allow": roll["allowable_at_hardware_com_worst_pose"]},
             "rolls": {k: (v["actuator_part"], v["no_camera"]["mass_g"], v["no_camera"]["util"], v["with_camera"]["util"]) for k, v in rolls.items()},
             "csv_changed": csv_changed}
    print(json.dumps(brief, indent=1, default=str))
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
