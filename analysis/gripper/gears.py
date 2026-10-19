"""Gear profile, fatigue and wear for the 1:1 spur sector pair: 3D printed vs CNC.

Rates the finger-A / finger-B sector pair at the design-basis load cases with
  * VDI 2736-2 structure for thermoplastics (tip-load root stress YFa*YSa*Yeps, flank
    Hertz, tooth deformation lambda, Archard-type local wear, root temperature), and
  * ISO 6336-3 Method B (YF, YS at the outer point of single-pair contact) plus
    ISO 6336-2 Hertz for metals,
over a design-space sweep (module, teeth, face width, pressure angle, profile shift,
materials), then writes the recommended involute sector profile (rack-generated, with the
trochoidal root fillet) as SVG and DXF for the CAD rebuild.

Inputs   cad/gripper/params.json (grip, materials, duty_cycle), docs/gripper/DESIGN-BASIS.md,
         docs/gripper/research/actuators.csv values quoted in INPUT below (tagged S/D/A)
Outputs  analysis/gripper/results/gears.json and gears_stdout.txt by default.
         --figures also writes docs/gripper/figures/gear_*.png; PNG bytes are
         deterministic on one machine, but font/library differences may affect other machines.
         --check writes nothing and compares all results with the committed JSON.
         cad/gripper/gear_profile.svg and gear_profile.dxf are refreshed by normal runs.
Run from the repository root (about 35 s):
    python analysis/gripper/gears.py
    python analysis/gripper/gears.py --figures
    python analysis/gripper/gears.py --check

Tests may point at a copied parameter file with the GRIPPER_PARAMS environment
variable and at copied thermal results with GRIPPER_THERMAL_RESULTS.

Determinism: numeric results use RESULT_SIGNIFICANT_FIGURES (10) significant
figures; profile coordinates use COORDINATE_DECIMALS (5) decimal places in mm
(0.00001 mm, far below manufacturing relevance). All text outputs are UTF-8/LF.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.integrate import solve_ivp  # noqa: E402
from scipy.optimize import brentq, minimize_scalar  # noqa: E402
from shapely import affinity  # noqa: E402
from shapely.geometry import Point, Polygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PARAMS_PATH = Path(os.environ.get("GRIPPER_PARAMS", ROOT / "cad/gripper/params.json"))
THERMAL_PATH = Path(os.environ.get("GRIPPER_THERMAL_RESULTS", ROOT / "analysis/gripper/thermal/results/thermal.json"))
P = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
OUT_DEFAULT = ROOT / "analysis/gripper/results/gears.json"
STDOUT_DEFAULT = ROOT / "analysis/gripper/results/gears_stdout.txt"
OUT = OUT_DEFAULT
FIG = ROOT / "docs/gripper/figures"
SVG = ROOT / "cad/gripper/gear_profile.svg"
DXF = ROOT / "cad/gripper/gear_profile.dxf"
NOTE = ROOT / "docs/gripper/analysis/gears.md"
WRITE_OUTPUT = True
WRITE_FIGURES = False
WRITE_PROFILE = True
RESULT_SIGNIFICANT_FIGURES = 10
COORDINATE_DECIMALS = 5
GR, AL, DC = P["grip"], P["materials"]["allowables"], P["duty_cycle"]
KGCM = 9.80665 / 100.0


def round_result_tree(value):
    """Return a result tree with every finite floating-point leaf rounded."""
    if isinstance(value, dict):
        return {key: round_result_tree(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        rounded = [round_result_tree(item) for item in value]
        return tuple(rounded) if isinstance(value, tuple) else rounded
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if not math.isfinite(number) or number == 0.0:
            return number
        places = RESULT_SIGNIFICANT_FIGURES - 1 - math.floor(math.log10(abs(number)))
        return round(number, places)
    return bool(value) if isinstance(value, np.bool_) else value


def write_utf8_text(path, content):
    """Write UTF-8 text with LF endings on every platform."""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    path.write_text(normalized, encoding="utf-8", newline="\n")


def stable_json(value, **kwargs):
    return json.dumps(round_result_tree(value), **kwargs)


def output_print(*values, **kwargs):
    print(*(round_result_tree(value) for value in values), **kwargs)

# ---------------------------------------------------------------- inputs (value, tag, note)
INPUT = {
    "F_target_N": (GR["F_target_N"], "A", "params.json grip (DESIGN-BASIS LC1)"),
    "F_cap_N": (GR["F_cap_N"], "A", "params.json grip (LC2)"),
    "tension_N": (GR["tension_N"], "A", "params.json grip (LC4 process tension, adds T*x_f to the servo, torque_and_actuator.md 2.3)"),
    "r_c_mm": (GR["r_c_design_mm"], "D", "params.json grip.r_c_design_mm (DESIGN-BASIS D3)"),
    "eta": (GR["eta_mesh_pivot"], "A", "params.json grip.eta_mesh_pivot"),
    "closed_gap_mm": (P["finger"]["closed_gap"], "S", "params.json finger.closed_gap; x_f = a/2 - gap/2 (cad/gripper/README.md)"),
    "KA_LC2": (P["materials"]["safety_factors"]["KA_LC2"], "A", "params.json materials.safety_factors"),
    "SF_LC1": (1.5, "A", "DESIGN-BASIS section 4 (fatigue at 1e5 / 1.5)"),
    "SF_LC2": (1.5, "A", "DESIGN-BASIS section 4"),
    "SF_LC3": (1.0, "A", "DESIGN-BASIS section 4"),
    "SF_shock": (1.0, "A", "rare event, no fracture (same rule as LC3)"),
    "SH_min": (1.0, "A", "flank: slow, wear-limited polymer contact; metals static"),
    "N_design": (P["materials"]["safety_factors"]["N_design_cycles"], "A", "DESIGN-BASIS R25"),
    "n_LC2": (1.0e3, "A", "DESIGN-BASIS LC2 occurrence"),
    "n_LC3": (1.0e2, "A", "stall events over life (R20 back-off <= 0.2 s each)"),
    "n_shock": (1.0e2, "A", "unplanned snags at full closing speed over life"),
    # servo (primary DS3218MG at 6.8 V, torque_and_actuator.md 3.6)
    "stall_kgcm_6p8V": (21.5, "S", "DS3218MG 21.5 kg*cm at 6.8 V, both datasheets (actuators.csv A17)"),
    "speed_s60_6p8V": (0.14, "S", "DS3218MG 0.14 s/60 deg at 6.8 V (actuators.csv A17)"),
    "backup_stall_pts_kgcm": ({6.0: 32.0, 7.4: 35.0}, "S", "DS3235 datasheet 32 kg*cm at 6 V, 35 at 7.4 V (actuators.csv A19)"),
    "backup_speed_pts_s60": ({5.0: 0.13, 7.4: 0.11}, "S", "DS3235 0.13 s/60 at 5 V, 0.11 at 7.4 V (actuators.csv A19)"),
    "backup_ratio": (373.0, "S", "DS3235 gear ratio 373 (datasheet, actuators.csv A19)"),
    "rail_V": (6.8, "A", "brief: DS3218MG on a 6.8 V rail; torque_and_actuator.md now uses a 6.5 +-0.15 V rail (LC3 at 6.65 V: 2.09 / 3.28 N*m), so 6.8 V is ~1 % conservative"),
    "servo_ratio": (300.0, "A", "DS3218MG gear ratio not published; DS3235 is 373 [S actuators.csv A19]"),
    "J_rotor_kgm2": ([2e-8, 5e-8, 1e-7], "A", "small iron-core DC motor rotor 0.2-1.0 g*cm^2; 5e-8 used for design"),
    "k_finger_max_N_mm": (GR["k_tip_max_N_per_mm"], "D", "params.json grip.k_tip_max (stiffest finger gives the hardest snag)"),
    "k_rigid_Nm_rad": (50.0, "A", "servo gear train + horn + knuckle torsional stiffness if a knuckle hits a rigid stop"),
    # duty/kinematics for wear
    "theta_squeeze_deg": (4.4, "D", "DESIGN-BASIS section 3: 5 N at k = 1.0 N/mm, r_c 65"),
    "theta_hold_deg": (-4.7, "D", "DESIGN-BASIS section 3: contact at -0.3 deg (0.3 mm ply) plus 4.4 deg squeeze; squeeze scales 1/k over params k_tip 0.88-1.63"),
    "theta_stroke_deg": (31.0, "D", "DESIGN-BASIS R18: theta in [-11, +20]"),
    "restep_per_grip": (3, "A", "FSR re-steps of one deadband (0.27 deg) at full hold load per grip (DESIGN-BASIS section 8)"),
    "unloaded_frac": (0.05, "A", "mesh load while closing/opening in free air, fraction of hold"),
    "omega_squeeze_rad_s": (60 * math.pi / 180, "A", "squeeze at 60 deg/s (torque_and_actuator.md 2.6)"),
    "mu_mesh": (0.3, "A", "dry polymer pair, 0.25-0.45 back-calculated from VDI temperatures (gears.md 4)"),
    "k_theta_root": (2100.0, "S", "VDI 2736 default root-temperature coefficient for POM/PA (Pogacnik & Tavcar, gears.md 5)"),
    "T_ambient_C": (P["work_cell"]["ambient_max_C"], "A", "params.json work_cell.ambient_max_C"),
    # geometry rules
    "rack_20": ({"hfP": 1.25, "rhofP": 0.38}, "S", "ISO 53 basic rack profile A (haP 1, cP 0.25 m, rhofP 0.38 m)"),
    "rack_25": ({"hfP": 1.25, "rhofP": 0.30}, "A", "25 deg rack, hfP 1.25 m, near-full-round tip 0.30 m (full round is 0.318 m)"),
    "eps_min": (1.2, "A", "minimum transverse contact ratio"),
    "sa_min_m": (0.25, "A", "minimum tip land, fraction of module"),
    "sa_min_print_mm": (0.45, "A", "FDM: tip land >= ~1 extrusion width at a 0.4 mm nozzle"),
    "sa_min_cnc_mm": (0.20, "A", "CNC hobbing / wire-EDM tip land"),
    "jt_print_mm": (0.25, "S", "design backlash jt0 (tolerance_stacks.md T07; Sovol 0.2-0.4 for FDM gears)"),
    "jt_cnc_mm": (0.08, "A", "fine-pitch machined pair"),
    "da_print_mm": (0.10, "A", "centre-distance scatter, printed housing, bushed (tolerance_stacks.md T06 window)"),
    "da_cnc_mm": (0.03, "A", "centre-distance scatter, machined housing"),
    "dA_ip_b6_mm": (0.050, "D", "in-plane axis tilt: T16-bushed MC 99.73 % band of the across-face centre-distance change at b = 6 (analysis/gripper/tolstack/results/T16-bushed.md); every term scales with b (b/10 hole terms, c*b/L cocking)"),
    "dA_op_b6_mm": (0.050, "A", "out-of-plane axis tilt at b = 6: the same hole-position (line-reamed +-0.03) and bore-clearance terms act isotropically, so equal to the in-plane value"),
    "Fby_combine": ("RSS", "A", "F_beta_y = (b/6)*sqrt((dA_ip sin aw)^2 + (dA_op cos aw)^2): in-plane tilt moves the flank along the line of action by x sin(aw), out-of-plane by x cos(aw) [D geometry]; independent directions -> RSS. WC (linear sum) is a sensitivity row. JGMA 1102 / ISO/TR 10064-3 allow half as much out-of-plane as in-plane deviation because it loads the flank harder [S kggear.co.jp 6.3]"),
    "Fby_cnc_b6_mm": (0.01, "A", "machined housing / reamed pins, at b = 6, scaled x b/6"),
    "rim_below_root_mm": (3.0, "A", "rim under the teeth for the sector-mass comparison"),
    "margin_rec": (1.5, "A", "recommendation rule: every SF >= 1.5 x its required value (covers unmeasured print knockdowns, F_beta_y, KHb)"),
    "a_max_mm": (34.0, "A", "compactness: centre distance limit (40 x 20 mm servo; DESIGN-BASIS R9)"),
    "wear_limit_m": (0.10, "A", "wear depth limit 0.1*m (gears.md 7)"),
    "lambda_limit_m": (0.07, "S", "VDI 2736 deformation guide 0.07*m (gears.md 5)"),
}
V = {k: v[0] for k, v in INPUT.items()}

def interp_pts(pts, v):
    xs = sorted(pts)
    return float(np.interp(v, xs, [pts[k] for k in xs], left=None, right=None)) if xs[0] <= v <= xs[-1] else         pts[xs[-2]] + (pts[xs[-1]] - pts[xs[-2]]) * (v - xs[-2]) / (xs[-1] - xs[-2])


T_STALL = V["stall_kgcm_6p8V"] * KGCM          # 2.108 N*m through the mesh (LC3)
W0 = (math.pi / 3) / V["speed_s60_6p8V"]         # no-load output speed rad/s
STALL_BACKUP_KGCM = interp_pts(V["backup_stall_pts_kgcm"], V["rail_V"])   # 33.71 kg*cm at 6.8 V [D]
T_STALL_BACKUP = STALL_BACKUP_KGCM * KGCM                                  # 3.306 N*m
W0_BACKUP = (math.pi / 3) / interp_pts(V["backup_speed_pts_s60"], V["rail_V"])


def fby(b, alpha_w_deg, route="printed", combine=None):
    """Effective flank misalignment F_beta_y (mm) for face width b: T16-bushed stack scaled x b/6."""
    combine = combine or V["Fby_combine"]
    if route == "CNC_housing":
        return V["Fby_cnc_b6_mm"] * b / 6
    aw = math.radians(alpha_w_deg)
    ip, op = V["dA_ip_b6_mm"] * math.sin(aw), V["dA_op_b6_mm"] * math.cos(aw)
    f = math.hypot(ip, op) if combine == "RSS" else ip + op
    return f * b / 6

# ---------------------------------------------------------------- materials
# S-N: sigma_max(N) = A * N**b at R ~ 0 (pulsating, one flank). kd_* are knockdowns.
# kw: Archard dimensional wear coefficient, mm^3/(N*m), (greased, dry) for the self-mated pair.
MAT = {
    "PLA": dict(route="printed", rho=1.24, E=AL["PLA"]["E_xy"], nu=0.35, S_static=AL["PLA"]["tensile_xy"], sy=AL["PLA"]["tensile_xy"],
                sn="coupon", A=68.159 * 2 / 0.95, b=-0.161,
                sn_tag="S Basquin sigma_a = 68.159 N^-0.161, R 0.05 smooth YZ coupons (gears.md 2.1) -> sigma_max = 2 sigma_a/(1-R)",
                kd_temp=0.80, kd_orient=0.90, kd_notch=1 / 1.14, moist=1.0,
                kw=(1e-4, 5e-4), kw_tag="S weak: printed PETG pin-on-disc 1e-4 wet / 5e-4 dry (gears.md 4); PLA assumed equal [A]",
                cost_kg=25.0, color="#c44e52"),
    "PETG": dict(route="printed", rho=AL["PETG"]["density"], E=AL["PETG"]["E_xy"], nu=0.35, S_static=AL["PETG"]["tensile_xy"], sy=AL["PETG"]["tensile_xy"],
                 sn="coupon", A=30.6 * 1e5 ** 0.161, b=-0.161,
                 sn_tag="A: 30.6 MPa at 1e5 (0.60 x UTS, PLA ratio, DESIGN-BASIS 4), PLA Basquin slope",
                 kd_temp=0.90, kd_orient=0.90, kd_notch=1 / 1.14, moist=1.0,
                 kw=(1e-4, 5e-4), kw_tag="S weak: printed PETG pin-on-disc 1e-4 wet / 5e-4 dry (gears.md 4)",
                 cost_kg=25.0, color="#dd8452"),
    "PA6-CF": dict(route="printed", rho=AL["PA6-CF"]["density"], E=AL["PA6-CF"]["E_xy"], nu=0.35, S_static=AL["PA6-CF"]["tensile_xy"], sy=AL["PA6-CF"]["tensile_xy"],
                   sn="onyx", A=None, b=None,
                   sn_tag="D from S: gear-level fit to Hribersek 2024 printed Onyx m1 z20 b6 (1.1 N*m 6.27e6 sd 1.36e6; 1.3 N*m 2.05e6 sd 0.53e6), 90 % survival",
                   kd_temp=0.95, kd_orient=1.0, kd_notch=1.0, moist=0.85,
                   kw=None, kw_tag="D: back-calculated from Onyx flank wear 0.186 mm after 4.86e6 cycles at 1.1 N*m vs steel, x2 self-mated [A]; l_Fl = contact-path length [A], 2.75x the involute-arc value",
                   cost_kg=80.0, color="#55a868"),
    "POM": dict(route="CNC", rho=AL["POM"]["density"], E=AL["POM"]["E"], nu=0.35, S_static=AL["POM"]["tensile"], sy=AL["POM"]["tensile"],
                sn="pogacnik", A=None, b=None,
                sn_tag="D from S: gear-level lower bound = PA6 root-fatigue lives in the POM/PA6 m1 z20 b6 tests (0.42 N*m 5.4e6, 0.59 N*m 1.6e6, 0.82 N*m 0.30e6, 90 % survival); POM outlived PA6 in that pairing",
                kd_temp=0.90, kd_orient=1.0, kd_notch=1.0, moist=1.0,
                kw=(3.4e-6, 1.0e-5), kw_tag="A: POM/POM greased taken as the POM/steel dry value 3.4e-6 [S VDI 2736 via Muratovic 2024] (no greased POM/POM k_w found; grease assumed to offset self-mating); POM/POM dry x3 [A] (POM/POM wore most, Pogacnik)",
                cost_kg=None, color="#4c72b0"),
    "Al6061": dict(route="CNC", rho=AL["Al6061-T6"]["density"], E=AL["Al6061-T6"]["E"], nu=0.33, S_static=AL["Al6061-T6"]["yield"], sy=AL["Al6061-T6"]["yield"],
                   sn="metal", Su=AL["Al6061-T6"]["UTS"], Se=97.0, Ne=5e8,
                   sn_tag="S 97 MPa at 5e8 R.R. Moore (gears.md 2.2); 0.9 Su at 1e3 [A]; Goodman to R = 0",
                   kd_temp=1.0, kd_orient=1.0, kd_notch=0.9, moist=1.0,
                   kw=(1e-5, 1e-3), kw_tag="A: Archard K 1e-5 greased / 1e-3 dry (galling) over H ~ 1 GPa",
                   cost_kg=None, color="#8172b3"),
    "Brass": dict(route="CNC", rho=8.2, E=100000.0, nu=0.31, S_static=140.0, sy=140.0,
                  sn="metal", Su=360.0, Se=0.35 * 360.0, Ne=1e8,
                  sn_tag="S C36000 H02: rho 8.2, E 100 GPa, nu 0.31, UTS 360, yield 140 MPa (makeitfrom.com); fatigue 0.35 Su at 1e8 [A]; Goodman to R = 0",
                  kd_temp=1.0, kd_orient=1.0, kd_notch=0.9, moist=1.0,
                  kw=(1e-5, 1e-3), kw_tag="A: as Al (brass/brass greased)",
                  cost_kg=None, color="#937860"),
}
PAIRS = {  # name: (gear A material, gear B material)
    "PLA": ("PLA", "PLA"), "PETG": ("PETG", "PETG"), "PA6-CF": ("PA6-CF", "PA6-CF"),
    "PETG/PA6-CF": ("PETG", "PA6-CF"),
    "POM": ("POM", "POM"), "Al6061": ("Al6061", "Al6061"), "Brass": ("Brass", "Brass"), "Al6061/Brass": ("Al6061", "Brass"),
}
KW_PAIR = {"PETG/PA6-CF": None, "Al6061/Brass": (5e-6, 3e-4)}  # dissimilar pairs [A]: PETG/PA6-CF uses the PA6-CF value

COST = {  # per pair of sectors, USD and lead time [A]
    "printed": ("$0.05-0.20 filament per pair (<= 3 g); PA6-CF needs a hardened nozzle (~$20 once)", "same day (0.5-1 h print)"),
    "CNC": ("$60-200 per pair from an online CNC service at qty 2 (small-part minimums dominate); 2D laser/waterjet from plate $15-40 but +-0.1 mm", "5-15 business days incl. shipping"),
}


def inv(a):
    return math.tan(a) - a


def inv_inverse(v):
    a = (3 * v) ** (1 / 3)
    for _ in range(50):
        a -= (math.tan(a) - a - v) / (math.tan(a) ** 2)
    return a


# ---------------------------------------------------------------- geometry
def geometry(m, z, alpha_deg, x, jt):
    al = math.radians(alpha_deg)
    rack = V["rack_20"] if alpha_deg == 20 else V["rack_25"]
    hfP, rho = rack["hfP"], rack["rhofP"]
    r = m * z / 2
    rb = r * math.cos(al)
    inv_aw = inv(al) + 2 * x * math.tan(al) / z          # x1 = x2 = x, z1 = z2 = z
    aw = inv_inverse(inv_aw)
    a_w = m * z * math.cos(al) / math.cos(aw)
    y = (a_w - m * z) / m
    k = 2 * x - y                                        # tip shortening
    ra = r + m * (1 + x - k)
    rf = r - m * (hfP - x)
    rw = a_w / 2
    L_a = math.sqrt(ra ** 2 - rb ** 2)
    pb = math.pi * m * math.cos(al)
    eps = (2 * L_a - a_w * math.sin(aw)) / pb
    # thickness allowance for backlash: jt at the working circle ~ 2 * ds/2 * rw/r
    ds = jt / 2 * (r / rw)
    s = m * (math.pi / 2 + 2 * x * math.tan(al)) - ds
    aa = math.acos(rb / ra)
    sa = 2 * ra * (s / (2 * r) + inv(al) - inv(aa))
    h_lin = hfP - rho * (1 - math.sin(al))               # depth of the straight rack flank below datum (in m)
    undercut = (h_lin - x) > z * math.sin(al) ** 2 / 2
    rFf = math.sqrt(rb ** 2 + max(r * math.sin(al) - (h_lin - x) * m / math.sin(al), 0) ** 2)  # form circle
    rA = math.sqrt(rb ** 2 + (a_w * math.sin(aw) - L_a) ** 2)                               # start of active profile
    # sector: jaw range + contact-path angle + one pitch each side
    path_deg = math.degrees(eps * pb / rb)
    pitch_deg = 360 / z
    sector = V["theta_stroke_deg"] + path_deg + 2 * pitch_deg
    n_teeth = math.ceil(sector / pitch_deg)
    return dict(m=m, z=z, alpha=alpha_deg, x=x, hfP=hfP, rhofP=rho, r=r, rb=rb, ra=ra, rf=rf, rw=rw, a_w=a_w, alpha_w=math.degrees(aw),
                eps=eps, pb=pb, L_a=L_a, s=s, sa=sa, ds=ds, undercut=undercut, rFf=rFf, rA=rA, interference=rA < rFf - 1e-6,
                sector_deg=n_teeth * pitch_deg, n_teeth=n_teeth, x_f=a_w / 2 - V["closed_gap_mm"] / 2)


def root_factors(g, load="C"):
    """ISO 6336-3 YF, YS for a spur gear generated by a rack (spr = 0), per m.
    load 'B': outer point of single-pair contact (Method B); 'C': tip (Method C / VDI 2736)."""
    z, x, al = g["z"], g["x"], math.radians(g["alpha"])
    hfP, rho = g["hfP"], g["rhofP"]
    E = math.pi / 4 - hfP * math.tan(al) - (1 - math.sin(al)) * rho / math.cos(al)
    G = rho - hfP + x
    H = 2 / z * (math.pi / 2 - E) - math.pi / 3
    th = math.pi / 6
    for _ in range(100):
        th = 2 * G / z * math.tan(th) - H
    sFn = z * math.sin(math.pi / 3 - th) + math.sqrt(3) * (G / math.cos(th) - rho)
    rhoF = rho + 2 * G ** 2 / (math.cos(th) * (z * math.cos(th) ** 2 - 2 * G))
    m = g["m"]
    dbn = z * math.cos(al)
    if load == "B":
        den = 2 * math.sqrt((g["L_a"] / m - math.pi * math.cos(al) * (g["eps"] - 1)) ** 2 + (g["rb"] / m) ** 2)
    else:
        den = 2 * g["ra"] / m
    a_en = math.acos(dbn / den)
    g_e = (0.5 * math.pi + 2 * math.tan(al) * x) / z + inv(al) - inv(a_en)
    a_Fen = a_en - g_e
    hFe = 0.5 * ((math.cos(g_e) - math.sin(g_e) * math.tan(a_Fen)) * den - z * math.cos(math.pi / 3 - th) - G / math.cos(th) + rho)
    YF = 6 * hFe * math.cos(a_Fen) / (sFn ** 2 * math.cos(al))
    L = sFn / hFe
    qs = sFn / (2 * rhoF)
    domain = {"sFn": sFn, "hFe": hFe, "rhoF": rhoF, "L": L, "qs": qs}
    for quantity, value in domain.items():
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"root-factor domain requires {quantity} > 0; got {value!r}")
    YS = (1.2 + 0.13 * L) * qs ** (1 / (1.21 + 2.3 / L))
    return YF, YS, dict(sFn=sFn, rhoF=rhoF, hFe=hFe, qs=qs)


def z_E(E1, n1, E2, n2):
    return math.sqrt(1 / (math.pi * ((1 - n1 ** 2) / E1 + (1 - n2 ** 2) / E2)))


def stresses(g, b, T_Nm, mA, mB, KA=1.0, Fby=None):
    """Root (VDI tip-load and ISO-B) and flank stress, KHb from misalignment, VDI deformation."""
    MA, MB = MAT[mA], MAT[mB]
    Fby = fby(b, g["alpha_w"]) if Fby is None else Fby
    m, z = g["m"], g["z"]
    d = 2 * g["r"]
    Ft = 2000 * T_Nm / d                                   # N at the reference circle
    c_g = 1 / (7.5 * (1 / MA["E"] + 1 / MB["E"]))          # mesh stiffness per unit face (VDI lambda relation), N/mm^2
    Fm_b = Ft * KA / b
    q = c_g * Fby / (2 * Fm_b)
    KHb = 1 + q if q <= 1 else math.sqrt(2 * c_g * Fby / Fm_b)
    h = g["ra"] - g["rf"]
    NF = (b / h) ** 2 / (1 + b / h + (b / h) ** 2)
    KFb = KHb ** NF
    YFa, YSa, _ = root_factors(g, "C")
    YF, YS, _ = root_factors(g, "B")
    Yeps = 0.25 + 0.75 / g["eps"]
    sF_vdi = Ft / (b * m) * YFa * YSa * Yeps * KA * KFb
    sF_iso = Ft / (b * m) * YF * YS * KA * KFb
    al, aw = math.radians(g["alpha"]), math.radians(g["alpha_w"])
    ZH = math.sqrt(2 * math.cos(aw) / (math.cos(al) ** 2 * math.sin(aw)))
    Zeps = math.sqrt((4 - g["eps"]) / 3)
    ra_rb = g["ra"] / g["rb"]
    M1 = math.tan(aw) / math.sqrt((math.sqrt(ra_rb ** 2 - 1) - 2 * math.pi / z) * (math.sqrt(ra_rb ** 2 - 1) - (g["eps"] - 1) * 2 * math.pi / z))
    ZB = max(1.0, M1)
    ZE = z_E(MA["E"], MA["nu"], MB["E"], MB["nu"])
    sH = ZE * ZH * Zeps * ZB * math.sqrt(Ft / (b * d) * 2) * math.sqrt(KA * KHb)
    lam = 7.5 * (Ft * KA / b) * (1 / MA["E"] + 1 / MB["E"])
    Fn = Ft / math.cos(aw)
    return dict(Ft=Ft, Fn=Fn, KHb=KHb, KFb=KFb, YFa=YFa, YSa=YSa, Yeps=Yeps, YF=YF, YS=YS, sF_vdi=sF_vdi, sF_iso=sF_iso,
                ZH=ZH, Zeps=Zeps, ZB=ZB, ZE=ZE, sH=sH, lam=lam, c_gamma=c_g)


def sigma_root(st, mat):
    return st["sF_vdi"] if MAT[mat]["route"] != "CNC" or mat == "POM" else st["sF_iso"]


# ---------------------------------------------------------------- S-N curves
def fit_basquin(Ts, Ns, geo_kwargs):
    g = geometry(**geo_kwargs)
    s = [stresses(g, 6.0, T, "POM", "POM", Fby=0.0)["sF_vdi"] for T in Ts]
    bb, lnA = np.polyfit(np.log(Ns), np.log(s), 1)
    return float(np.exp(lnA)), float(bb), s


TEST_GEO = dict(m=1.0, z=20, alpha_deg=20, x=0.0, jt=0.0)
# Onyx: 90 % survival = mean - 1.28 sd
onyx_N = [6.27e6 - 1.28 * 1.36e6, 2.05e6 - 1.28 * 0.53e6]
A_onyx, b_onyx, s_onyx = fit_basquin([1.1, 1.3], onyx_N, TEST_GEO)
MAT["PA6-CF"].update(A=A_onyx, b=b_onyx)
pog_T, pog_N = [0.42, 0.59, 0.82], [5.4e6, 1.6e6, 0.30e6]
A_pog, b_pog, s_pog = fit_basquin(pog_T, pog_N, TEST_GEO)
MAT["POM"].update(A=A_pog, b=b_pog)
for nm in ("Al6061", "Brass"):
    M = MAT[nm]
    S1, S2 = 0.9 * M["Su"], M["Se"]
    bb = math.log(S2 / S1) / math.log(M["Ne"] / 1e3)
    M.update(A_rev=S1 / 1e3 ** bb, b=bb)


def kd_fat(mat):
    M = MAT[mat]
    return M["kd_temp"] * M["kd_orient"] * M["kd_notch"] * M["moist"]


def kd_static(mat):
    M = MAT[mat]
    return M["kd_temp"] * M["kd_orient"] * M["moist"]


def s_fat(mat, N):
    """Pulsating (R ~ 0) sigma_max allowable at N cycles incl. knockdowns."""
    M = MAT[mat]
    N = max(N, 1e3)
    if M["sn"] == "metal":
        Sa = M["A_rev"] * N ** M["b"]
        Sa = max(Sa, M["Se"]) if N > M["Ne"] else Sa
        s = 2 * Sa * M["Su"] / (Sa + M["Su"])                # Goodman, R = 0: sigma_max
        s = min(s, M["sy"])
    else:
        s = M["A"] * N ** M["b"]
        s = min(s, M["S_static"])
    return s * kd_fat(mat)


def life(mat, sigma):
    """Cycles to failure at sigma_max (inverse of s_fat)."""
    M = MAT[mat]
    kd = kd_fat(mat)
    if sigma >= s_fat(mat, 1e3):
        return 1e3 * (s_fat(mat, 1e3) / sigma) ** 8
    lo, hi = 3.0, 13.0
    if s_fat(mat, 10 ** hi) >= sigma:
        return 1e13
    for _ in range(60):
        mid = (lo + hi) / 2
        if s_fat(mat, 10 ** mid) > sigma:
            lo = mid
        else:
            hi = mid
    _ = (M, kd)
    return 10 ** lo


def sH_allow(mat, N=None):
    """Flank allowable: Hertz subsurface-yield onset p0 = 1.67 sigma_y (Tresca, line contact) [D], scaled by the
    root fatigue ratio for N cycles [A]."""
    base = 1.67 * MAT[mat]["sy"] * kd_static(mat)
    if N is None:
        return base
    return base * s_fat(mat, N) / s_fat(mat, 1e3)


# ---------------------------------------------------------------- load cases
def load_cases(g):
    xf = g["x_f"] / 1000
    rc = V["r_c_mm"] / 1000
    T1 = (2 * V["F_target_N"] * rc + V["tension_N"] * xf) / V["eta"] / 2
    T2 = (2 * V["F_cap_N"] * rc + V["tension_N"] * xf) / V["eta"] / 2 * V["KA_LC2"]
    return {"LC1": T1, "LC2": T2, "LC3": T_STALL}


def shock(Ts=None, w0=None, ratio=None):
    """Finger B snagged while the jaw closes at full speed: J th'' = Tm(w) - k th, Tm = Ts(1 - w/w0) clipped."""
    Ts = T_STALL if Ts is None else Ts
    w0 = W0 if w0 is None else w0
    ratio = V["servo_ratio"] if ratio is None else ratio
    res = {}
    rc = V["r_c_mm"]
    k_f = V["k_finger_max_N_mm"] * rc ** 2 / 1000         # N*m/rad
    for case, k in (("finger_snag", k_f), ("rigid_knuckle_stop", V["k_rigid_Nm_rad"])):
        rows = []
        for Jr in V["J_rotor_kgm2"]:
            J = Jr * ratio ** 2

            def f(t, y, J=J, k=k, Ts=Ts):
                th, w = y
                Tm = float(np.clip(Ts * (1 - w / w0), -Ts, Ts))
                return [w, (Tm - k * th) / J]
            sol = solve_ivp(f, (0, 0.6), [0.0, w0], max_step=2e-4)
            Tsp = k * sol.y[0]
            rows.append(dict(J_rotor=Jr, J_out=J, T_peak=float(Tsp.max()), factor=float(Tsp.max() / Ts),
                             t=sol.t[::10].tolist(), T=Tsp[::10].tolist()))
        res[case] = dict(k_Nm_rad=k, rows=rows)
    return res


SHOCK = shock()
T_SHOCK = [r for r in SHOCK["finger_snag"]["rows"] if r["J_rotor"] == 5e-8][0]["T_peak"]
SHOCK_BACKUP = shock(T_STALL_BACKUP, W0_BACKUP, V["backup_ratio"])
T_SHOCK_BACKUP = [r for r in SHOCK_BACKUP["finger_snag"]["rows"] if r["J_rotor"] == 5e-8][0]["T_peak"]


# ---------------------------------------------------------------- wear, temperature
def wear(g, b, T_hold, kw, phased):
    """Local Archard wear depth (mm) after N_design grips: W = sum (Fn/b) zeta kw (VDI 2736 local form)."""
    aw = math.radians(g["alpha_w"])
    rho_p = g["rb"] * math.tan(aw)                     # radius of curvature at the pitch point
    gA = g["a_w"] * math.sin(aw) - g["L_a"]            # base-tangent distance of start of active profile
    g_root = rho_p - gA                                # |g| at the flank's root end (approach side)
    kmm = kw / 1000                                    # mm^3/(N*mm)
    Fn_b = 2000 * T_hold / (2 * g["rb"]) / b           # normal load per face width, N/mm (Fn = T/rb)
    dg = g["rb"] * math.radians(V["theta_squeeze_deg"])
    N = V["N_design"]
    zeta = lambda gg: abs(2 * gg / (rho_p + gg))       # gg signed from pitch point, negative toward this flank's root
    if not phased:                                     # loaded arc ends at the root end of the active flank
        z_max = zeta(-g_root)
        per = (2 + V["restep_per_grip"] + 2 * V["unloaded_frac"]) * Fn_b * z_max
    else:                                              # hold contact phased at the pitch point; ramp over dg
        s = np.linspace(0, 1, 201)
        gg = -dg * (1 - s)
        per = float(np.max(2 * s * Fn_b * np.array([zeta(v) for v in gg])))
        per += V["restep_per_grip"] * Fn_b * zeta(-g["rb"] * math.radians(0.27))
        per += 2 * V["unloaded_frac"] * Fn_b * zeta(-g_root)
    return per * N * kmm


def kw_onyx():
    """Back-calculate kw from Hribersek 2024: 0.186 mm mean flank wear after 4.86e6 cycles at 1.1 N*m, m1 z20 b6,
    via VDI 2736 mean wear W = T 2 pi N (1+u) HV kw / (b z l_Fl), u = 1 [A: steel mate z20]."""
    g = geometry(**TEST_GEO)
    aw = math.radians(g["alpha_w"])
    ga = g["L_a"] - g["rb"] * math.tan(aw)
    e1 = e2 = ga / g["pb"]
    HV = math.pi * 2 / g["z"] * (1 - g["eps"] + e1 ** 2 + e2 ** 2)
    # l_Fl [A]: VDI 2736-2's exact definition could not be checked (paywalled). Three candidate lengths of the active flank:
    rho_a, rho_A = math.sqrt(g["ra"] ** 2 - g["rb"] ** 2), math.sqrt(max(g["rA"] ** 2 - g["rb"] ** 2, 0))
    l_path = rho_a - rho_A                             # contact-path length g_alpha on the line of action (4.60 mm)
    l_arc = (rho_a ** 2 - rho_A ** 2) / (2 * g["rb"])  # involute arc length rA -> ra (1.67 mm): physical flank length
    l_rad = g["ra"] - g["rA"]                          # radial flank height (1.54 mm)
    lFl = l_path                                       # design: path length, the largest -> kw 2.75x the arc-length value (conservative)
    Tn = 1100.0
    kmm = 0.186 * 6 * g["z"] * lFl / (Tn * 2 * math.pi * 4.86e6 * 2 * HV)
    return kmm * 1000, dict(HV=HV, l_Fl_used=lFl, l_Fl_basis="contact-path length [A, conservative]", l_path=l_path, l_arc=l_arc,
                            l_radial=l_rad, kw_if_arc=kmm * 1000 * l_arc / lFl, factor_path_over_arc=lFl / l_arc)


KW_ONYX, KW_ONYX_INFO = kw_onyx()
MAT["PA6-CF"]["kw"] = (2 * KW_ONYX, 2 * KW_ONYX)
KW_PAIR["PETG/PA6-CF"] = (KW_ONYX * 2, KW_ONYX * 2)


def temperature(g, b, T_hold):
    aw = math.radians(g["alpha_w"])
    ga = g["L_a"] - g["rb"] * math.tan(aw)
    e1 = e2 = ga / g["pb"]
    HV = math.pi * 2 / g["z"] * (1 - g["eps"] + e1 ** 2 + e2 ** 2)
    Pkw = T_hold * V["omega_squeeze_rad_s"] / 1000
    v = V["omega_squeeze_rad_s"] * g["r"] / 1000
    t_sq = 2 * math.radians(V["theta_squeeze_deg"]) / V["omega_squeeze_rad_s"]
    ED = t_sq / DC["cycle_s"]
    dT_cont = Pkw * V["mu_mesh"] * HV * 136 * V["k_theta_root"] / (b * g["z"] * (v * g["m"]) ** 0.75)
    return dict(HV=HV, P_W=Pkw * 1000, ED=ED, dT_continuous_C=dT_cont, dT_duty_C=dT_cont * ED ** 0.64)


# ---------------------------------------------------------------- evaluate one option
def sector_mass(g, b, rho):
    r_in = max(g["rf"] - V["rim_below_root_mm"], 1.0)
    frac = g["sector_deg"] / 360
    A = frac * math.pi * (g["rf"] ** 2 - r_in ** 2) + frac * math.pi * (g["ra"] ** 2 - g["rf"] ** 2) * 0.5
    return A * b * rho / 1000


def evaluate(g, b, pair, Fby=None, T3=None, Tsh=None):
    """Fby: None -> derived per b (fby(), printed housing); a number -> fixed F_beta_y; 'CNC_housing' or 'WC' -> fby() variant."""
    mA, mB = PAIRS[pair]
    route = "printed" if MAT[mA]["route"] == "printed" else "CNC"
    if Fby is None:
        Fby = fby(b, g["alpha_w"])
    elif Fby == "CNC_housing":
        Fby = fby(b, g["alpha_w"], "CNC_housing")
    elif Fby == "WC":
        Fby = fby(b, g["alpha_w"], combine="WC")
    LC = load_cases(g)
    if T3 is not None:
        LC["LC3"] = T3
    LC["shock"] = T_SHOCK if Tsh is None else Tsh
    out = dict(pair=pair, route=route, m=g["m"], z=g["z"], b=b, alpha=g["alpha"], x=g["x"], a_w=round(g["a_w"], 3),
               eps=round(g["eps"], 3), sa=round(g["sa"], 3), undercut=g["undercut"], interference=g["interference"], Fby_mm=round(Fby, 4))
    st = {k: stresses(g, b, T, mA, mB, KA=1.0, Fby=Fby) for k, T in LC.items()}
    sf = {}
    worst = {}
    for mat in {mA, mB}:
        s1 = sigma_root(st["LC1"], mat)
        sf.setdefault("F_LC1", []).append(s_fat(mat, V["N_design"]) / s1)
        sS = MAT[mat]["S_static"] * kd_static(mat)
        for k in ("LC2", "LC3", "shock"):
            sf.setdefault("F_" + k, []).append(sS / sigma_root(st[k], mat))
        sf.setdefault("H_LC1", []).append(sH_allow(mat, V["N_design"]) / st["LC1"]["sH"])
        sf.setdefault("H_LC3", []).append(sH_allow(mat) / st["LC3"]["sH"])
        Nf = life(mat, s1)
        D = V["N_design"] / Nf + sum(V[n] / life(mat, sigma_root(st[k], mat)) for k, n in (("LC2", "n_LC2"), ("LC3", "n_LC3"), ("shock", "n_shock")))
        worst.setdefault("N_f_LC1", []).append(Nf)
        worst.setdefault("miner_D", []).append(D)
    for k in sf:
        sf[k] = min(sf[k])
    out["SF"] = {k: round(v, 3) for k, v in sf.items()}
    out["N_f_LC1"] = min(worst["N_f_LC1"])
    out["miner_D"] = max(worst["miner_D"])
    out["sigmaF_MPa"] = {k: round(max(sigma_root(st[k], mA), sigma_root(st[k], mB)), 2) for k in st}
    out["sigmaH_MPa"] = {k: round(st[k]["sH"], 2) for k in st}
    out["KHb_LC1"] = round(st["LC1"]["KHb"], 3)
    out["lambda_LC1_mm"] = round(st["LC1"]["lam"], 4)
    out["lambda_limit_mm"] = round(V["lambda_limit_m"] * g["m"], 4)
    kw = KW_PAIR.get(pair) or MAT[mA]["kw"]
    out["wear_mm"] = {"greased_worst": wear(g, b, LC["LC1"], kw[0], False), "greased_phased": wear(g, b, LC["LC1"], kw[0], True),
                      "dry_worst": wear(g, b, LC["LC1"], kw[1], False)}
    out["wear_mm"]["greased_worst_end_KHb"] = out["wear_mm"]["greased_worst"] * st["LC1"]["KHb"]   # loaded face end, before running-in
    out["wear_mm"] = {k: round(v, 5) for k, v in out["wear_mm"].items()}
    out["wear_limit_mm"] = round(V["wear_limit_m"] * g["m"], 4)
    out["mass_pair_g"] = round(sector_mass(g, b, MAT[mA]["rho"]) + sector_mass(g, b, MAT[mB]["rho"]), 3)
    jt = V["jt_print_mm"] if route == "printed" else V["jt_cnc_mm"]
    da = V["da_print_mm"] if route == "printed" else V["da_cnc_mm"]
    dj = 2 * da * math.tan(math.radians(g["alpha_w"]))
    out["backlash"] = dict(jt_design_mm=jt, jt_range_mm=[round(max(jt - dj, 0), 3), round(jt + dj, 3)],
                           deg=round(math.degrees(jt / g["rw"]), 3), tip_pad_lag_mm=round(jt * V["r_c_mm"] / g["rw"], 3),
                           wear_growth_mm=round(2 * out["wear_mm"]["greased_worst"] / math.cos(math.radians(g["alpha_w"])), 4))
    sa_min = max(V["sa_min_m"] * g["m"], V["sa_min_print_mm"] if route == "printed" else V["sa_min_cnc_mm"])
    req = dict(F_LC1=V["SF_LC1"], F_LC2=V["SF_LC2"], F_LC3=V["SF_LC3"], F_shock=V["SF_shock"], H_LC1=V["SH_min"], H_LC3=V["SH_min"])
    checks = {k: sf[k] >= req[k] for k in req}
    checks.update(eps=g["eps"] >= V["eps_min"], undercut=not g["undercut"], interference=not g["interference"], tip_land=g["sa"] >= sa_min,
                  deformation=st["LC1"]["lam"] <= V["lambda_limit_m"] * g["m"], wear=out["wear_mm"]["greased_worst"] <= out["wear_limit_mm"],
                  miner=out["miner_D"] <= 1.0, compact=g["a_w"] <= V["a_max_mm"])
    out["checks"] = checks
    out["pass"] = all(checks.values())
    out["margin_min"] = round(min(sf[k] / req[k] for k in req), 3)
    out["envelope_score"] = round(g["a_w"] + b, 3)
    return out


# ---------------------------------------------------------------- sweep
MODS = [0.8, 1.0, 1.25, 1.5]
ZS = list(range(18, 29))
BS = [4, 5, 6, 7, 8, 9, 10]
ALS = [20, 25]
XS = [0.0, 0.25, 0.5]


def run_sweep():
    rows = []
    geos = {}
    for m in MODS:
        for z in ZS:
            for al in ALS:
                for x in XS:
                    for route, jt in (("printed", V["jt_print_mm"]), ("CNC", V["jt_cnc_mm"])):
                        geos[(m, z, al, x, route)] = geometry(m, z, al, x, jt)
    for pair, (mA, _) in PAIRS.items():
        route = "printed" if MAT[mA]["route"] == "printed" else "CNC"
        for (m, z, al, x, r), g in geos.items():
            if r != route:
                continue
            for b in BS:
                rows.append(evaluate(g, b, pair))
    return rows, geos


def pick(rows, pair):
    ok = [r for r in rows if r["pair"] == pair and r["pass"] and r["margin_min"] >= V["margin_rec"]]
    ok.sort(key=lambda r: (round(r["envelope_score"]), -r["margin_min"], r["mass_pair_g"]))
    return ok


# ---------------------------------------------------------------- profile generator (rack generation, shapely)
def rack_tooth(g, dsh):
    """Cutter tooth that forms one tooth space; frame (u along the rolling line, v outward), v = 0 at the rolling line."""
    m, al = g["m"], math.radians(g["alpha"])
    hfP, rho = g["hfP"] * m, g["rhofP"] * m
    xm = g["x"] * m
    half0 = math.pi * m / 4 + dsh / 2                   # cutter tooth half-width at the datum line (v = xm)
    v_tip = xm - hfP
    vc = v_tip + rho
    uc = half0 - (hfP - rho) * math.tan(al) - rho / math.cos(al)
    v_top = xm + 2.0 * m
    pts = []
    u_top = half0 + (v_top - xm) * math.tan(al)
    pts.append((-u_top, v_top))
    # left fillet: from flank tangent (angle pi + al) down to tip (angle 3pi/2)
    for t in np.linspace(math.pi + al, 1.5 * math.pi, 24):
        pts.append((-uc + rho * math.cos(t), vc + rho * math.sin(t)))
    for t in np.linspace(1.5 * math.pi, 2 * math.pi - al, 24):
        pts.append((uc + rho * math.cos(t), vc + rho * math.sin(t)))
    pts.append((u_top, v_top))
    return Polygon(pts)


def gear_polygon(g, sector_center_deg, tooth_on_center, r_in, n_side_extra=0):
    r = g["r"]
    cut = rack_tooth(g, g["ds"])  # cutter widened by ds = the gear's tooth thinning at the reference circle
    pitch = 2 * math.pi / g["z"]
    phis = np.arange(-2.6 * pitch, 2.6 * pitch + 1e-12, math.radians(0.2))
    cuts = []
    for ph in phis:
        c = affinity.translate(cut, xoff=r * ph, yoff=r)
        c = affinity.rotate(c, ph, origin=(0, 0), use_radians=True)
        cuts.append(c)
    space = unary_union(cuts)                           # one tooth space centred on +Y
    space = affinity.rotate(space, -90, origin=(0, 0))  # centred on +X
    blank = Point(0, 0).buffer(g["ra"], 2048)
    half = g["sector_deg"] / 2
    spaces = []
    k_max = int(math.ceil(half / math.degrees(pitch))) + 2
    off = 0.0 if not tooth_on_center else math.degrees(pitch) / 2
    for k in range(-k_max, k_max + 1):
        spaces.append(affinity.rotate(space, k * math.degrees(pitch) + off, origin=(0, 0)))
    teeth = blank.difference(unary_union(spaces))
    # sector wedge ending at tooth-space centres
    pd = math.degrees(pitch)
    h = math.ceil(half / pd) * pd if not tooth_on_center else (math.ceil((half - pd / 2) / pd) + 0.5) * pd
    R = g["ra"] * 1.5
    ang = np.radians(np.linspace(-h, h, 200))
    wedge = Polygon([(0, 0)] + [(R * math.cos(a), R * math.sin(a)) for a in ang])
    band = teeth.intersection(wedge).difference(Point(0, 0).buffer(r_in, 1024))
    band = affinity.rotate(band, sector_center_deg, origin=(0, 0))
    return band, dict(half_angle_deg=h, teeth=int(round(2 * h / math.degrees(pitch))))


def check_profile(g, poly_A):
    """Tooth thickness on the reference circle and root radius, measured on the generated polygon (gear A at origin)."""
    ang = np.radians(np.linspace(-40, 40, 40001))
    r = g["r"]
    inside = np.array([poly_A.contains(Point(r * math.cos(a), r * math.sin(a))) for a in ang[::10]])
    a_s = ang[::10]
    # find the tooth centred at +half pitch (A has a space on +X)
    runs, start = [], None
    for i, v in enumerate(inside):
        if v and start is None:
            start = i
        if (not v) and start is not None:
            runs.append((a_s[start], a_s[i - 1]))
            start = None
    widths = [(b - a) * r for a, b in runs]
    s_meas = float(np.median(widths)) if widths else float("nan")
    # root radius: min distance from origin to boundary within the teeth band
    ext = np.array(poly_A.exterior.coords)
    rr = np.hypot(ext[:, 0], ext[:, 1])
    band = rr[(rr > g["rf"] - 0.2 * g["m"]) & (rr < g["ra"] + 1e-6)]
    return dict(s_ref_measured_mm=round(s_meas, 4), s_ref_analytic_mm=round(g["s"], 4), rf_measured_mm=round(float(band.min()), 4),
                rf_analytic_mm=round(g["rf"], 4), ra_measured_mm=round(float(rr.max()), 4), ra_analytic_mm=round(g["ra"], 4))


def write_svg_dxf(polys, g, meta):
    xs, ys = [], []
    for _, p in polys:
        c = np.array(p.exterior.coords)
        xs += c[:, 0].tolist()
        ys += c[:, 1].tolist()
    pad = 3
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    W, H = x1 - x0, y1 - y0
    q = COORDINATE_DECIMALS
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.{q}f}mm" height="{H:.{q}f}mm" viewBox="{x0:.{q}f} {-y1:.{q}f} {W:.{q}f} {H:.{q}f}">',
             f'<!-- {meta} ; units mm ; y flipped (SVG y down) -->', '<g transform="scale(1,-1)" fill="none" stroke-width="0.05">']
    col = {"GEAR_A": "#000000", "GEAR_B": "#1f4e9a"}
    for name, p in polys:
        for ring in [p.exterior] + list(p.interiors):
            c = np.array(ring.coords)
            d = "M " + " L ".join(f"{u:.{q}f},{v:.{q}f}" for u, v in c) + " Z"
            lines.append(f'<path id="{name}" d="{d}" stroke="{col[name]}"/>')
    for cx in (-g["a_w"] / 2, g["a_w"] / 2):
        lines.append(f'<circle cx="{cx:.{q}f}" cy="0" r="{g["rw"]:.{q}f}" stroke="#999999" stroke-dasharray="0.5,0.3"/>')
        lines.append(f'<path d="M {cx - 1:.{q}f},0 L {cx + 1:.{q}f},0 M {cx:.{q}f},-1 L {cx:.{q}f},1" stroke="#999999"/>')
    lines += ["</g>", "</svg>"]
    write_utf8_text(SVG, "\n".join(lines) + "\n")
    # DXF R12, ENTITIES only (closed POLYLINEs per layer, CIRCLE for working pitch circles, LINE centre marks)
    d = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for name, p in polys:
        for ring in [p.exterior] + list(p.interiors):
            c = np.array(ring.coords)[:-1]
            d += ["0", "POLYLINE", "8", name, "66", "1", "10", "0.0", "20", "0.0", "30", "0.0", "70", "1"]
            for u, v in c:
                d += ["0", "VERTEX", "8", name, "10", f"{u:.{q}f}", "20", f"{v:.{q}f}", "30", "0.0"]
            d += ["0", "SEQEND", "8", name]
    for cx in (-g["a_w"] / 2, g["a_w"] / 2):
        d += ["0", "CIRCLE", "8", "PITCH_WORKING", "10", f"{cx:.{q}f}", "20", "0.0", "30", "0.0", "40", f"{g['rw']:.{q}f}"]
        d += ["0", "LINE", "8", "CENTRE", "10", f"{cx - 1:.{q}f}", "20", "0.0", "30", "0.0", "11", f"{cx + 1:.{q}f}", "21", "0.0", "31", "0.0"]
        d += ["0", "LINE", "8", "CENTRE", "10", f"{cx:.{q}f}", "20", "-1.0", "30", "0.0", "11", f"{cx:.{q}f}", "21", "1.0", "31", "0.0"]
    d += ["0", "ENDSEC", "0", "EOF"]
    write_utf8_text(DXF, "\n".join(d) + "\n")


def contact_offset(g, theta_deg):
    """Loaded-contact offset from the pitch point along the line of action (mm) at jaw angle theta (closing negative),
    for the DXF phase (theta 0: A has a tooth space centred on the line of centres). A's loaded flank crosses the working
    circle e_w/(2 rw) from the centre line; rotating A by theta moves that flank rb*theta along the line of action."""
    al, aw = math.radians(g["alpha"]), math.radians(g["alpha_w"])
    s_w = 2 * g["rw"] * (g["s"] / (2 * g["r"]) + inv(al) - inv(aw))
    e_w = 2 * math.pi * g["rw"] / g["z"] - s_w
    phi0 = e_w / (2 * g["rw"])
    return g["rb"] * (phi0 + math.radians(theta_deg)), -math.degrees(phi0)


def phasing_info(g):
    kd, kmin, kmax = GR.get("k_tip_default_N_per_mm", 1.0), GR["k_tip_min_N_per_mm"], GR["k_tip_max_N_per_mm"]
    th0 = V["theta_hold_deg"] + V["theta_squeeze_deg"]            # contact angle (-0.3 deg, 0.3 mm ply)
    rows = {}
    for lab, k in (("k_default", kd), ("k_min", kmin), ("k_max", kmax)):
        th = th0 - V["theta_squeeze_deg"] * kd / k
        off, th_pitch = contact_offset(g, th)
        rho_p = g["rb"] * math.tan(math.radians(g["alpha_w"]))
        rows[lab] = dict(k_N_mm=k, theta_hold_deg=round(th, 3), offset_from_pitch_mm=round(off, 4),
                         specific_sliding_zeta=round(abs(2 * off / (rho_p + off)), 4))
    _, th_pitch = contact_offset(g, 0.0)
    rho_p = g["rb"] * math.tan(math.radians(g["alpha_w"]))
    g_root = rho_p - (g["a_w"] * math.sin(math.radians(g["alpha_w"])) - g["L_a"])
    return dict(zeta_root_end_worst=round(abs(2 * g_root / (rho_p - g_root)), 4), theta_contact_at_pitch_deg=round(th_pitch, 3), rule="offset along the line of action = rb * (theta_hold - theta_pitch) in rad; "
                "re-phase by rotating both sectors' tooth pattern by (theta_hold_new - theta_hold) about their pivots",
                rb_mm=round(g["rb"], 4), mm_per_deg=round(g["rb"] * math.pi / 180, 4), cases=rows)


def _thermal_case_temperatures():
    data = json.loads(THERMAL_PATH.read_text(encoding="utf-8"))
    key = "r26_verdict_table"
    if key not in data:
        raise KeyError(f"thermal results missing key: {key}")
    found = {}
    for row in data[key]:
        if row.get("ambient_C") == 40 and row.get("reading") == "high" and row.get("conduction") == "continuous":
            found[row.get("backoff")] = row.get("case_steady_C")
    for state in ("on", "off"):
        if state not in found or found[state] is None:
            raise KeyError(f"thermal results missing key: {key}[ambient_C=40,reading=high,conduction=continuous,backoff={state}].case_steady_C")
    return {"ambient_no_servo_heating": 40.0, "with_backoff_steady": found["on"], "without_backoff_steady": found["off"]}


def _verdict(value, required):
    ratio = value / required
    return "meets rule" if ratio >= V["margin_rec"] else ("passes below rule" if ratio >= 1 else "fails")


def as_drawn_analysis():
    """Evaluate only the revision-B product selected and dimensioned by params.json."""
    gc, servo = P["gear"], P["servo"]
    selected = servo["model"]
    model = servo["models"][selected]
    Ts = model["stall_torque_kgcm"]["6.5V"] * KGCM
    w0 = math.radians(328.0) if selected == "DSServo DS3230 MG" else W0
    Tsh = [r for r in shock(Ts, w0)["finger_snag"]["rows"] if r["J_rotor"] == 5e-8][0]["T_peak"]

    def geo_for_shift(x):
        # Equal positive shifts enlarge a_w. Reduce module to retain the housing's fixed centre distance.
        unit = geometry(1.0, gc["teeth"], gc["pressure_angle"], x, gc["backlash_jt"])
        return geometry(gc["center_distance"] / unit["a_w"], gc["teeth"], gc["pressure_angle"], x, gc["backlash_jt"])

    g = geo_for_shift(gc["profile_shift"])
    b = gc["face_width"]
    drawn_fby = fby(b, g["alpha_w"])
    e = evaluate(g, b, "PA6-CF", T3=Ts, Tsh=Tsh)
    torques = load_cases(g) | {"LC3": Ts, "shock": Tsh}
    required = dict(F_LC1=V["SF_LC1"], F_LC2=V["SF_LC2"], F_LC3=V["SF_LC3"], F_shock=V["SF_shock"], H_LC1=V["SH_min"], H_LC3=V["SH_min"])
    checks = {}
    for name, req in required.items():
        checks[name] = dict(value=e["SF"][name], required=req, ratio_to_1p5_rule=e["SF"][name] / req / V["margin_rec"], verdict=_verdict(e["SF"][name], req))
    wear_sf = e["wear_limit_mm"] / e["wear_mm"]["greased_worst"]
    fatigue_sf = 1 / e["miner_D"]
    checks["wear"] = dict(value=wear_sf, required=1.0, ratio_to_1p5_rule=wear_sf / V["margin_rec"], verdict=_verdict(wear_sf, 1.0))
    checks["fatigue_Miner"] = dict(value=fatigue_sf, required=1.0, ratio_to_1p5_rule=fatigue_sf / V["margin_rec"], verdict=_verdict(fatigue_sf, 1.0))

    def factor(width, shift=gc["profile_shift"]):
        # A CAD-only width/shift change does not change the existing housing's
        # absolute pivot-axis error; retain its as-drawn F_beta_y.
        try:
            ee = evaluate(geo_for_shift(shift), width, "PA6-CF", Fby=drawn_fby, T3=Ts, Tsh=Tsh)
        except ValueError as error:
            if "root-factor domain" not in str(error):
                raise
            return -math.inf
        return min(ee["SF"][k] / required[k] for k in required)

    target = V["margin_rec"]
    b_solution = b if factor(b) >= target else brentq(lambda width: factor(width) - target, b, 40.0)
    x_solution = gc["profile_shift"] if factor(b) >= target else None
    previous_x, previous_f = gc["profile_shift"], factor(b) - target
    for x_candidate in np.linspace(gc["profile_shift"] + 0.001, 3.0, 3000):
        candidate_f = factor(b, x_candidate) - target
        if previous_f < 0 <= candidate_f:
            x_solution = brentq(lambda x: factor(b, x) - target, previous_x, x_candidate)
            break
        previous_x, previous_f = x_candidate, candidate_f
    x_opt = minimize_scalar(lambda x: -factor(b, x), bounds=(-0.35, 3.0), method="bounded")

    # Smallest pair mass when both dimensions may change; bounded deterministic scalar solve.
    def solved_width(x):
        if factor(b, x) >= target:
            return b
        return brentq(lambda width: factor(width, x) - target, b, 40.0)
    opt = minimize_scalar(lambda x: sector_mass(geo_for_shift(x), solved_width(x), MAT["PA6-CF"]["rho"]) * 2,
                          bounds=(-0.35, max(1.0, x_solution or 1.0)), method="bounded", options={"xatol": 1e-10})
    bx, bb = float(opt.x), solved_width(float(opt.x))

    def solution(width, shift):
        gg = geo_for_shift(shift)
        return dict(face_width_mm=width, added_face_mm=width - b, profile_shift=shift, module=gg["m"], center_distance_mm=gg["a_w"],
                    mass_pair_g=sector_mass(gg, width, MAT["PA6-CF"]["rho"]) * 2, factor=factor(width, shift),
                    housing_room="could-not-tell", missing_field="housing.available_gear_face_width_mm")
    profile_solution = (solution(b, x_solution) if x_solution is not None else
                        dict(status="no solution in valid shift range", best_profile_shift=float(x_opt.x), best_factor=-float(x_opt.fun),
                             reason="At fixed 28.5 mm centre distance, compensating module reduction offsets the shift benefit."))
    solutions = {"face_width_only": solution(b_solution, gc["profile_shift"]), "profile_shift_only": profile_solution, "both": solution(bb, bx)}

    raw_sf = e["SF"]["F_LC3"] / MAT["PA6-CF"]["kd_temp"]
    temps = {}
    for label, temp_c in _thermal_case_temperatures().items():
        known = math.isclose(temp_c, V["T_ambient_C"], abs_tol=1e-9)
        temps[label] = dict(temperature_C=temp_c, knockdown=MAT["PA6-CF"]["kd_temp"] if known else "could-not-tell",
                           stall_safety_factor=e["SF"]["F_LC3"] if known else "could-not-tell",
                           break_even_knockdown_SF_1p0=1 / raw_sf, break_even_knockdown_SF_1p5=target / raw_sf,
                           verdict=_verdict(e["SF"]["F_LC3"], 1.0) if known else "could-not-tell")
    stall_at_15 = Ts * e["SF"]["F_LC3"] / target
    stall_at_10 = Ts * e["SF"]["F_LC3"]
    overall = min(checks.values(), key=lambda row: row["ratio_to_1p5_rule"])
    return dict(servo_model=selected, geometry=dict(module=gc["module"], teeth=gc["teeth"], pressure_angle_deg=gc["pressure_angle"],
                profile_shift=gc["profile_shift"], center_distance_mm=gc["center_distance"], face_width_mm=b),
                mesh_torque_Nm={"hold_5N": torques["LC1"], "cap": torques["LC2"], "stall_6p5V": Ts, "snag_shock": Tsh},
                checks=checks, overall=dict(verdict=overall["verdict"], governing_check=next(k for k, v in checks.items() if v is overall)),
                smallest_change=solutions,
                stall_break_even=dict(SF_1p5_Nm=stall_at_15, SF_1p5_fraction_of_servo_stall=stall_at_15 / Ts,
                                      SF_1p0_Nm=stall_at_10, SF_1p0_fraction_of_servo_stall=stall_at_10 / Ts),
                temperature=temps,
                trade_study_8mm=dict(script_SF_LC3=evaluate(g, 8.0, "PA6-CF", T3=Ts, Tsh=Tsh)["SF"]["F_LC3"],
                                     script_SF_shock=evaluate(g, 8.0, "PA6-CF", T3=Ts, Tsh=Tsh)["SF"]["F_shock"],
                                     note="Trade study 1.24/1.02 differs: 8 mm face, its face-load factor and load definitions differ from this script."))


def render_as_drawn_block(data):
    g, t = data["geometry"], data["mesh_torque_Nm"]
    rows = ["<!-- GEARS-AS-DRAWN:BEGIN -->", "### Revision B as drawn (generated)", "", "| Item | Generated result |", "|---|---|"]
    rows.append(f"| Product | {data['servo_model']}; m {g['module']:g}, z {g['teeth']}, α {g['pressure_angle_deg']:g}°, x {g['profile_shift']:g}, a {g['center_distance_mm']:g} mm, b {g['face_width_mm']:g} mm |")
    rows.append(f"| Mesh torque: hold / cap / stall / snag | {t['hold_5N']:.3f} / {t['cap']:.3f} / {t['stall_6p5V']:.3f} / {t['snag_shock']:.3f} N·m |")
    for name in ("F_LC1", "F_LC2", "F_LC3", "F_shock", "H_LC1", "H_LC3", "wear", "fatigue_Miner"):
        row = data["checks"][name]
        rows.append(f"| {name} | SF {row['value']:.3f}; required {row['required']:.3f}; rule ratio {row['ratio_to_1p5_rule']:.3f}; **{row['verdict']}** |")
    rows.append(f"| Overall | **{data['overall']['verdict']}**; governed by {data['overall']['governing_check']} |")
    rows.extend(["", "<!-- GEARS-AS-DRAWN:END -->"])
    return "\n".join(rows)


def render_downstream_block(data):
    """Render build requests from the as-drawn result."""
    g = data["geometry"]
    wider = data["smallest_change"]["face_width_only"]["face_width_mm"]
    geometry = (
        f"Build the drawn {data['servo_model']} pair: m {g['module']:g}, z {g['teeth']}, "
        f"α {g['pressure_angle_deg']:g}°, x {g['profile_shift']:g}, a {g['center_distance_mm']:g} mm, "
        f"b {g['face_width_mm']:g} mm"
    )
    rows = ["<!-- GEARS-DOWNSTREAM:BEGIN -->", "### Revision B downstream requests (generated)", ""]
    rows.extend(["| Where | Request |", "|---|---|", f"| `params.json` gear and CAD | {geometry} |"])
    rows.append(
        f"| Housing-width decision | First record available housing width (absent from `params.json`), then choose either "
        f"the drawn b {g['face_width_mm']:g} mm at stall root SF {data['checks']['F_LC3']['value']:.3f} with a recorded "
        f"acceptance reason, or widen to b {wider:.3f} mm for the 1.5 rule |"
    )
    rows.append("| Firmware | Keep stall back-off ≤ 0.2 s; do not put a hard stop through the mesh |")
    rows.extend(["", "<!-- GEARS-DOWNSTREAM:END -->"])
    return "\n".join(rows)


def update_note_block(block, begin, end, check=False):
    text = NOTE.read_text(encoding="utf-8")
    if begin in text and end in text:
        current = text[text.index(begin):text.index(end) + len(end)]
        updated = text.replace(current, block)
    else:
        raise ValueError(f"note is missing generated block markers {begin} and {end}")
    if check:
        return updated == text
    write_utf8_text(NOTE, updated)
    return True


# ---------------------------------------------------------------- main
def run_analysis():
    if WRITE_FIGURES:
        FIG.mkdir(parents=True, exist_ok=True)
    val = {}
    # validation 1: ISO root factors vs gears.md table (YF*YS 3.51 z14, 3.15 z18, 2.88 z24, 2.73 z30, 2.64 z36 at x 0, rhofP 0.38)
    ref = {14: 3.51, 18: 3.15, 24: 2.88, 30: 2.73, 36: 2.64}
    lewis = {20: 0.322, 24: 0.337, 30: 0.359}
    v1 = {}
    for z, yy in ref.items():
        g = geometry(1.0, z, 20, 0.0, 0.0)
        YF, YS, _ = root_factors(g, "B")
        YFa, YSa, _ = root_factors(g, "C")
        v1[z] = dict(YF_YS_B=round(YF * YS, 3), gears_md=yy, YFa=round(YFa, 3), YSa=round(YSa, 3), eps=round(g["eps"], 3),
                     inv_lewis=round(1 / lewis[z], 3) if z in lewis else None)
    for z in lewis:
        g = geometry(1.0, z, 20, 0.0, 0.0)
        YFa, YSa, _ = root_factors(g, "C")
        v1.setdefault(z, {})
        v1[z].update(YFa=round(YFa, 3), YSa=round(YSa, 3), inv_lewis=round(1 / lewis[z], 3), YFa_x_lewisY=round(YFa * lewis[z], 3))
    val["root_factors"] = v1
    val["S_N_anchors"] = dict(onyx_sigma_vdi_MPa=[round(s, 2) for s in s_onyx], onyx_N90=onyx_N, onyx_fit=dict(A=A_onyx, b=b_onyx),
                              pogacnik_sigma_vdi_MPa=[round(s, 2) for s in s_pog], pogacnik_N=pog_N, pogacnik_fit=dict(A=A_pog, b=b_pog),
                              POM_gear_level_at_1e6_MPa=round(A_pog * 1e6 ** b_pog, 2), POM_coupon_flex_fatigue_1e6_MPa=32.0,
                              PLA_sigma_max_1e5_MPa=round(MAT["PLA"]["A"] * 1e5 ** MAT["PLA"]["b"], 2))
    val["kw_onyx_mm3_Nm"] = dict(value=KW_ONYX, **KW_ONYX_INFO)

    rows, geos = run_sweep()
    summary = {}
    for pair in PAIRS:
        ok = pick(rows, pair)
        allp = [r for r in rows if r["pair"] == pair]
        passing = sorted([r for r in allp if r["pass"]], key=lambda r: -r["margin_min"])
        fails = {}
        for r in allp:
            for k, v in r["checks"].items():
                fails[k] = fails.get(k, 0) + (not v)
        summary[pair] = dict(n_eval=len(allp), n_pass=sum(r["pass"] for r in allp), n_pass_margin=len(ok), best=ok[:12],
                             best_margin_passing=[dict(geo=f"m{r['m']} z{r['z']} a{r['alpha']} x{r['x']} b{r['b']}", a_w=r["a_w"], margin=r["margin_min"],
                                                       wear_frac=round(r["wear_mm"]["greased_worst"] / r["wear_limit_mm"], 3)) for r in passing[:3]],
                             best_margin_any=max(r["margin_min"] for r in allp), fail_counts=fails)
    # recommendations
    rec_print = None
    for pair in ("PETG", "PA6-CF", "PLA", "PETG/PA6-CF"):
        if summary[pair]["best"]:
            c = summary[pair]["best"][0]
            if rec_print is None or (round(c["envelope_score"]), -c["margin_min"]) < (round(rec_print["envelope_score"]), -rec_print["margin_min"]):
                rec_print = c
    rec_cnc = None
    for pair in ("POM", "Al6061", "Brass", "Al6061/Brass"):
        if summary[pair]["best"]:
            c = summary[pair]["best"][0]
            if rec_cnc is None or (round(c["envelope_score"]), c["mass_pair_g"]) < (round(rec_cnc["envelope_score"]), rec_cnc["mass_pair_g"]):
                rec_cnc = c
    robust = [r for r in rows if r["pair"] == rec_print["pair"] and r["pass"] and r["a_w"] <= 30.0]
    rec_print_robust = max(robust, key=lambda r: (r["margin_min"] - 0.01 * r["envelope_score"])) if robust else None
    # the PETG-preferred printed option (same-day, no hardened nozzle) and baselines at named geometries
    named = {}
    for label, (m, z, al, x, b) in {"baseline m1 z24 b6": (1.0, 24, 20, 0.0, 6), "DB m1.5 z20 b6": (1.5, 20, 20, 0.0, 6),
                                     "DB m1.25 z24 b6": (1.25, 24, 20, 0.0, 6)}.items():
        named[label] = {}
        for pair in PAIRS:
            route = "printed" if MAT[PAIRS[pair][0]]["route"] == "printed" else "CNC"
            g = geometry(m, z, al, x, V["jt_print_mm"] if route == "printed" else V["jt_cnc_mm"])
            e = evaluate(g, b, pair)
            named[label][pair] = dict(pass_=e["pass"], SF=e["SF"], failed=[k for k, v in e["checks"].items() if not v],
                                      sigmaF=e["sigmaF_MPa"], sigmaH=e["sigmaH_MPa"], N_f_LC1=e["N_f_LC1"], wear=e["wear_mm"])
    # backup servo (DS3235) sensitivity and CNC-housing sensitivity on the recommendations
    sens = {}
    prev_pick = dict(pair="PA6-CF", m=1.25, z=19, alpha=25, x=0.0, b=10)   # the pick under the old fixed F_beta_y 0.03 mm
    for tag, rec in (("printed", rec_print), ("CNC", rec_cnc), ("printed_robust", rec_print_robust), ("previous_pick_m1.25z19b10", prev_pick)):
        if rec is None:
            continue
        rt = "printed" if MAT[PAIRS[rec["pair"]][0]]["route"] == "printed" else "CNC"
        g = geometry(rec["m"], rec["z"], rec["alpha"], rec["x"], V["jt_print_mm"] if rt == "printed" else V["jt_cnc_mm"])
        row = {}
        e = evaluate(g, rec["b"], rec["pair"], T3=T_STALL_BACKUP, Tsh=T_SHOCK_BACKUP)
        row["DS3235_backup"] = dict(T_LC3=round(T_STALL_BACKUP, 4), T_shock=round(T_SHOCK_BACKUP, 4), SF_LC3=e["SF"]["F_LC3"], SF_shock=e["SF"]["F_shock"],
                                    margin=e["margin_min"], pass_=e["pass"], failed=[k for k, v in e["checks"].items() if not v])
        for lab, F in (("Fby_derived_RSS", None), ("Fby_derived_WC", "WC"), ("Fby_0.03", 0.03), ("Fby_0.05", 0.05), ("Fby_0.08", 0.08),
                       ("CNC_housing", "CNC_housing")):
            e = evaluate(g, rec["b"], rec["pair"], Fby=F)
            row[lab] = dict(Fby_mm=e["Fby_mm"], KHb_LC1=e["KHb_LC1"], SF_LC3=e["SF"]["F_LC3"], SF_shock=e["SF"]["F_shock"], margin=e["margin_min"],
                            pass_=e["pass"], wear_worst_mm=e["wear_mm"]["greased_worst"], wear_worst_end_mm=e["wear_mm"]["greased_worst_end_KHb"])
        sens[tag] = dict(geometry=f"{rec['pair']} m{rec['m']} z{rec['z']} a{rec['alpha']} x{rec['x']} b{rec['b']} a_w {g['a_w']:.2f}", rows=row)
    # the same recommendations checked against the DESIGN-BASIS section 4 allowables (LC1 / LC2 / LC3, no knockdown) and DB LC3 torque
    db_check = {}
    for tag, rec in (("printed", rec_print), ("CNC", rec_cnc)):
        mat = PAIRS[rec["pair"]][0]
        key = {"PA6-CF": "PA6-CF", "POM": "POM"}.get(mat)
        if key is None or "allow_LC1" not in AL.get(key, {}):
            continue
        A_ = AL[key]
        sg = rec["sigmaF_MPa"]
        db_check[tag] = dict(DB_allow_LC1_LC2_LC3=[A_["allow_LC1"], A_["allow_LC2"], A_["allow_LC3"]],
                             lane_allow_LC1=round(s_fat(mat, V["N_design"]) / V["SF_LC1"], 2), lane_allow_LC3=round(MAT[mat]["S_static"] * kd_static(mat), 2),
                             SF_vs_DB=dict(LC1=round(A_["allow_LC1"] / sg["LC1"], 3), LC2=round(A_["allow_LC2"] / sg["LC2"], 3),
                                           LC3=round(A_["allow_LC3"] / sg["LC3"], 3)),
                             LC3_DB_torque_Nm=2.00, SF_LC3_lane_at_DB_torque=round(rec["SF"]["F_LC3"] * T_STALL / 2.00, 3))
    # temperature for recommendations
    temp = {}
    for tag, rec in (("printed", rec_print), ("CNC", rec_cnc)):
        g = geometry(rec["m"], rec["z"], rec["alpha"], rec["x"], 0.0)
        temp[tag] = {k: round(v, 5) for k, v in temperature(g, rec["b"], load_cases(g)["LC1"]).items()}

    # profile for the printed recommendation (primary CAD geometry)
    gP = geometry(rec_print["m"], rec_print["z"], rec_print["alpha"], rec_print["x"], V["jt_print_mm"])
    r_in = gP["rf"] - V["rim_below_root_mm"]
    polyA0, infoA = gear_polygon(gP, 0.0, False, r_in)
    chk = check_profile(gP, polyA0)
    polyA = affinity.translate(polyA0, xoff=-gP["a_w"] / 2)
    polyB0, infoB = gear_polygon(gP, 180.0, True, r_in)
    polyB = affinity.translate(polyB0, xoff=gP["a_w"] / 2)
    overlap = polyA.intersection(polyB).area
    meta = (f"1:1 sector pair, m {gP['m']} z {gP['z']} alpha {gP['alpha']} x {gP['x']} b {rec_print['b']} a_w {gP['a_w']:.3f} "
            f"jt {V['jt_print_mm']} rack hfP {gP['hfP']}m rhofP {gP['rhofP']}m; A pivot (-a/2,0) space on +X, B pivot (+a/2,0) tooth on -X")
    if WRITE_PROFILE:
        write_svg_dxf([("GEAR_A", polyA), ("GEAR_B", polyB)], gP, meta)
    prof = dict(file_svg="cad/gripper/gear_profile.svg", file_dxf="cad/gripper/gear_profile.dxf", meta=meta, check=chk,
                sector_A=infoA, sector_B=infoB, overlap_area_mm2=round(overlap, 5), area_A_mm2=round(polyA0.area, 3),
                mass_pair_exact_g=round((polyA0.area + polyB0.area) * rec_print["b"] * MAT[PAIRS[rec_print["pair"]][0]]["rho"] / 1000, 3),
                r_in_mm=round(r_in, 3), rFf_mm=round(gP["rFf"], 4), rA_mm=round(gP["rA"], 4), phasing=phasing_info(gP))

    # ------------------------------------------------ figures
    figs = [ROOT / "docs/gripper/figures" / name for name in (
        "gear_design_space.png", "gear_safety_factors.png", "gear_sn.png",
        "gear_shock.png", "gear_wear.png", "gear_profile.png",
    )]
    # The map is result data; calculate it even when rendering is disabled.
    pairs_plot = ["PLA", "PETG", "PA6-CF", "POM", "Al6061", "Brass"]
    bmin_maps = {}
    for pair in pairs_plot:
        M = np.full((len(MODS), len(ZS)), np.nan)
        for i, m in enumerate(MODS):
            for j, z in enumerate(ZS):
                candidates = [r["b"] for r in rows if r["pair"] == pair and r["m"] == m and r["z"] == z and r["pass"]]
                if candidates:
                    M[i, j] = min(candidates)
        bmin_maps[pair] = [[None if np.isnan(value) else float(value) for value in row] for row in M]

    # Plot construction is intentionally skipped unless --figures is requested.
    if WRITE_FIGURES:
        fig, axs = plt.subplots(2, 3, figsize=(13, 7), constrained_layout=True)
        bmin_maps = {}
        for ax, pair in zip(axs.flat, pairs_plot):
            M = np.full((len(MODS), len(ZS)), np.nan)
            for i, m in enumerate(MODS):
                for j, z in enumerate(ZS):
                    c = [r["b"] for r in rows if r["pair"] == pair and r["m"] == m and r["z"] == z and r["pass"]]
                    if c:
                        M[i, j] = min(c)
            bmin_maps[pair] = [[None if np.isnan(value) else float(value) for value in row] for row in M]
            im = ax.imshow(M, origin="lower", aspect="auto", cmap="viridis_r", vmin=4, vmax=10)
            for i in range(len(MODS)):
                for j in range(len(ZS)):
                    ax.text(j, i, "x" if np.isnan(M[i, j]) else f"{int(M[i, j])}", ha="center", va="center", fontsize=7,
                            color="#888888" if np.isnan(M[i, j]) else "white")
            ax.set_xticks(range(len(ZS)), ZS, fontsize=7)
            ax.set_yticks(range(len(MODS)), MODS)
            ax.set_title(f"{pair}: min face width b (mm) that passes", fontsize=9)
            ax.set_xlabel("teeth z")
            ax.set_ylabel("module m")
        fig.colorbar(im, ax=axs, shrink=0.6, label="b_min (mm); x = no b <= 10 passes")
        fig.suptitle("Design space: every check (LC1 fatigue, LC2, LC3 stall 2.11 N*m, snag shock, flank, lambda, wear, geometry, a <= 34), best alpha / x", fontsize=10)
        p = FIG / "gear_design_space.png"
        if WRITE_FIGURES:
            fig.savefig(p, dpi=130, metadata={"Software": "berkeley-ai-tutor"})
        plt.close(fig)

        # 2 safety factors of the recommendations and baselines
        cands = [("printed rec", rec_print), ("CNC rec", rec_cnc)]
        for pair in ("PETG", "PA6-CF", "POM", "Al6061"):
            if summary[pair]["best"]:
                cands.append((f"{pair} best", summary[pair]["best"][0]))
        keys = ["F_LC1", "F_LC2", "F_LC3", "F_shock", "H_LC1", "H_LC3"]
        req = [V["SF_LC1"], V["SF_LC2"], V["SF_LC3"], V["SF_shock"], V["SH_min"], V["SH_min"]]
        fig, ax = plt.subplots(figsize=(11, 4.5), constrained_layout=True)
        w = 0.8 / len(cands)
        for i, (lab, c) in enumerate(cands):
            vals = [c["SF"][k] / r for k, r in zip(keys, req)]
            ax.bar(np.arange(len(keys)) + i * w, vals, w, label=f"{lab}: {c['pair']} m{c['m']} z{c['z']} b{c['b']} a{c['alpha']} x{c['x']}")
        ax.axhline(1.0, color="k", lw=1)
        ax.set_xticks(np.arange(len(keys)) + w * (len(cands) - 1) / 2, [f"{k}\n(req {r})" for k, r in zip(keys, req)])
        ax.set_ylabel("SF / required SF")
        ax.set_yscale("log")
        ax.legend(fontsize=7)
        ax.set_title("Safety factor over the required value (>= 1 passes)")
        p = FIG / "gear_safety_factors.png"
        if WRITE_FIGURES:
            fig.savefig(p, dpi=130, metadata={"Software": "berkeley-ai-tutor"})
        plt.close(fig)

        # 3 S-N curves with LC1 stress of the printed recommendation geometry
        fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
        Ns = np.logspace(3, 9, 200)
        gR = geometry(rec_print["m"], rec_print["z"], rec_print["alpha"], rec_print["x"], 0.0)
        for mat in MAT:
            ax.loglog(Ns, [s_fat(mat, n) for n in Ns], color=MAT[mat]["color"], label=f"{mat} (knockdown {kd_fat(mat):.2f})")
            s1 = sigma_root(stresses(gR, rec_print["b"], load_cases(gR)["LC1"], mat, mat), mat)
            ax.plot([V["N_design"]], [s1], "o", color=MAT[mat]["color"])
        ax.axvline(V["N_design"], color="k", ls=":", lw=1)
        ax.set_xlabel("cycles N")
        ax.set_ylabel("allowable root sigma_max, R ~ 0 (MPa)")
        ax.set_title(f"S-N used (after knockdowns); dots: LC1 root stress at m{gR['m']} z{gR['z']} b{rec_print['b']}")
        ax.legend(fontsize=7)
        p = FIG / "gear_sn.png"
        if WRITE_FIGURES:
            fig.savefig(p, dpi=130, metadata={"Software": "berkeley-ai-tutor"})
        plt.close(fig)

        # 4 shock
        fig, ax = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
        for i, case in enumerate(("finger_snag", "rigid_knuckle_stop")):
            for r in SHOCK[case]["rows"]:
                ax[i].plot(np.array(r["t"]) * 1000, r["T"], label=f"J_rotor {r['J_rotor'] * 1e7:.1f} g*cm^2: peak {r['T_peak']:.2f} N*m ({r['factor']:.2f}x stall)")
            ax[i].axhline(T_STALL, color="k", ls=":", lw=1)
            ax[i].set_title(case.replace("_", " ") + f", k = {SHOCK[case]['k_Nm_rad']:.1f} N*m/rad")
            ax[i].set_xlabel("time (ms)")
            ax[i].set_ylabel("mesh torque (N*m)")
            ax[i].legend(fontsize=7)
            ax[i].set_xlim(0, 400 if i == 0 else 60)
        p = FIG / "gear_shock.png"
        if WRITE_FIGURES:
            fig.savefig(p, dpi=130, metadata={"Software": "berkeley-ai-tutor"})
        plt.close(fig)

        # 5 wear per pair at the recommended printed geometry
        fig, ax = plt.subplots(figsize=(9, 4), constrained_layout=True)
        labs, wg, wp, wd = [], [], [], []
        for pair in PAIRS:
            mA = PAIRS[pair][0]
            g = geometry(rec_print["m"], rec_print["z"], rec_print["alpha"], rec_print["x"], 0.0)
            kw = KW_PAIR.get(pair) or MAT[mA]["kw"]
            T1 = load_cases(g)["LC1"]
            labs.append(pair)
            wd.append(wear(g, rec_print["b"], T1, kw[1], False))
            wg.append(wear(g, rec_print["b"], T1, kw[0], False))
            wp.append(wear(g, rec_print["b"], T1, kw[0], True))
        xx = np.arange(len(labs))
        ax.bar(xx - 0.27, wd, 0.27, label="dry, worst phasing")
        ax.bar(xx, wg, 0.27, label="greased, worst phasing")
        ax.bar(xx + 0.27, wp, 0.27, label="greased, hold phased at pitch point")
        ax.axhline(V["wear_limit_m"] * rec_print["m"], color="k", ls=":", lw=1, label="limit 0.1 m")
        ax.set_yscale("log")
        ax.set_xticks(xx, labs, fontsize=8)
        ax.set_ylabel("flank wear depth after 1e5 grips (mm)")
        ax.set_title(f"Archard wear, m{rec_print['m']} z{rec_print['z']} b{rec_print['b']}, LC1 hold")
        ax.legend(fontsize=7)
        p = FIG / "gear_wear.png"
        if WRITE_FIGURES:
            fig.savefig(p, dpi=130, metadata={"Software": "berkeley-ai-tutor"})
        plt.close(fig)

        # 6 profile render
        fig, ax = plt.subplots(1, 2, figsize=(12, 5.5), constrained_layout=True)
        for a_ in ax:
            for pol, colr in ((polyA, "#333333"), (polyB, "#1f4e9a")):
                c = np.array(pol.exterior.coords)
                a_.fill(c[:, 0], c[:, 1], color=colr, alpha=0.25)
                a_.plot(c[:, 0], c[:, 1], color=colr, lw=0.6)
            for cx in (-gP["a_w"] / 2, gP["a_w"] / 2):
                t = np.linspace(0, 2 * np.pi, 400)
                a_.plot(cx + gP["rw"] * np.cos(t), gP["rw"] * np.sin(t), "k:", lw=0.5)
                a_.plot(cx + gP["rb"] * np.cos(t), gP["rb"] * np.sin(t), color="#aaaaaa", lw=0.4)
            a_.set_aspect("equal")
        ax[0].set_title(meta[:95], fontsize=8)
        ax[1].set_xlim(-2.5 * gP["m"], 2.5 * gP["m"])
        ax[1].set_ylim(-2.5 * gP["m"], 2.5 * gP["m"])
        ax[1].set_title("mesh at the pitch point (dotted: working pitch circles; grey: base circles)", fontsize=8)
        p = FIG / "gear_profile.png"
        if WRITE_FIGURES:
            fig.savefig(p, dpi=150, metadata={"Software": "berkeley-ai-tutor"})
        plt.close(fig)

    # CAD rev B check (actuation_trade.md 8 C1): the drawn pair (params.json gear) at the drawn face width, for each servo in
    # params.json servo.models at its own 6.5 V stall and snag shock; the sweep above is unchanged
    gc_ = P["gear"]
    models = P["servo"].get("models", {})
    gR = geometry(gc_["module"], gc_["teeth"], gc_["pressure_angle"], gc_["profile_shift"], gc_["backlash_jt"])
    no_load = {"DSServo DS3218MG": (W0, "D from speed_s60_6p8V"), "DSServo DS3230 MG": (math.radians(328.0), "S 328 deg/s listing (actuation_trade.md 8 T1)")}
    rev_b = dict(geometry=f"PA6-CF m{gc_['module']} z{gc_['teeth']} a{gc_['pressure_angle']} x{gc_['profile_shift']} a_w {gR['a_w']:.3f}",
                 face_width_drawn=gc_["face_width"], selected_servo=P["servo"]["model"], ratio_assumed=V["servo_ratio"], rows={})
    for name, row in models.items():
        Ts = row["stall_torque_kgcm"]["6.5V"] * KGCM
        w0, w0_src = no_load.get(name, (W0, "A DS3218MG value"))
        Tsh = [r for r in shock(Ts, w0)["finger_snag"]["rows"] if r["J_rotor"] == 5e-8][0]["T_peak"]
        per_b = {}
        for b_ in sorted({8.0, float(row.get("gear_face_width", gc_["face_width"])), float(gc_["face_width"])}):
            e = evaluate(gR, b_, "PA6-CF", T3=Ts, Tsh=Tsh)
            per_b[f"b{b_:g}"] = dict(SF_LC3=e["SF"]["F_LC3"], SF_shock=e["SF"]["F_shock"], margin=e["margin_min"], pass_=e["pass"],
                                    failed=[k for k, v in e["checks"].items() if not v], sigmaF_MPa=e["sigmaF_MPa"],
                                    mass_pair_g=e.get("mass_pair_g"))
        rev_b["rows"][name] = dict(T_LC3_6p5V_Nm=round(Ts, 4), T_shock_Nm=round(Tsh, 4), no_load_rad_s=round(w0, 3), no_load_src=w0_src,
                                   face_width_for_this_servo=row.get("gear_face_width"), by_face_width=per_b)
    as_drawn = as_drawn_analysis()
    out = dict(
        as_drawn=as_drawn,
        cad_rev_b=rev_b,
        inputs={k: dict(value=v[0], tag=v[1], note=v[2]) for k, v in INPUT.items()},
        materials={k: {kk: vv for kk, vv in M.items() if kk not in ("color",)} | dict(kd_fatigue=round(kd_fat(k), 4), kd_static=round(kd_static(k), 4),
                                                                                   s_fat_1e5=round(s_fat(k, 1e5), 3), s_static_design=round(M["S_static"] * kd_static(k), 3))
                   for k, M in MAT.items()},
        load_cases=dict(note="mesh torque, N*m; LC1/LC2 per option from x_f; values below at the printed recommendation",
                        at_rec_print={k: round(v, 4) for k, v in load_cases(gP).items()} | {"shock": round(T_SHOCK, 4)},
                        LC3_stall_Nm=round(T_STALL, 4), LC3_backup_DS3235_Nm=round(T_STALL_BACKUP, 4), backup_stall_kgcm=round(STALL_BACKUP_KGCM, 3),
                        shock_backup_Nm=round(T_SHOCK_BACKUP, 4), servo_no_load_rad_s=round(W0, 3), backup_no_load_rad_s=round(W0_BACKUP, 3)),
        shock={k: dict(k_Nm_rad=v["k_Nm_rad"], rows=[{kk: vv for kk, vv in r.items() if kk not in ("t", "T")} for r in v["rows"]]) for k, v in SHOCK.items()},
        shock_backup_DS3235={k: dict(k_Nm_rad=v["k_Nm_rad"], rows=[{kk: vv for kk, vv in r.items() if kk not in ("t", "T")} for r in v["rows"]])
                             for k, v in SHOCK_BACKUP.items()},
        validation=val,
        sweep=dict(modules=MODS, teeth=ZS, face=BS, alpha=ALS, x=XS, n_rows=len(rows), per_pair=summary, bmin_maps=bmin_maps),
        named_geometries=named,
        recommendation=dict(printed=rec_print, printed_robust=rec_print_robust, cnc=rec_cnc, sensitivity=sens, design_basis_check=db_check, temperature=temp, cost_lead=COST),
        profile=prof,
        figures=[f.relative_to(ROOT).as_posix() for f in figs],
    )
    out = round_result_tree(out)
    if WRITE_OUTPUT:
        write_utf8_text(OUT, stable_json(out, indent=1, sort_keys=True) + "\n")
        if OUT == OUT_DEFAULT:
            update_note_block(
                render_as_drawn_block(out["as_drawn"]),
                "<!-- GEARS-AS-DRAWN:BEGIN -->",
                "<!-- GEARS-AS-DRAWN:END -->",
            )
            update_note_block(
                render_downstream_block(out["as_drawn"]),
                "<!-- GEARS-DOWNSTREAM:BEGIN -->",
                "<!-- GEARS-DOWNSTREAM:END -->",
            )
    # console summary
    output_print("validation root factors:", stable_json(val["root_factors"]))
    output_print("S-N anchors:", stable_json(val["S_N_anchors"]))
    output_print("kw onyx:", val["kw_onyx_mm3_Nm"])
    output_print("shock:", {k: [(r["J_rotor"], round(r["T_peak"], 3), round(r["factor"], 3)) for r in v["rows"]] for k, v in SHOCK.items()})
    for pair in PAIRS:
        s = summary[pair]
        b0 = s["best"][0] if s["best"] else None
        output_print(pair, s["n_pass"], "/", s["n_eval"], "best:", None if not b0 else (b0["m"], b0["z"], b0["b"], b0["alpha"], b0["x"], b0["a_w"], b0["SF"], b0["mass_pair_g"], b0["wear_mm"]))
    output_print("REC printed:", stable_json(rec_print))
    output_print("REC cnc:", stable_json(rec_cnc))
    output_print("REC printed robust:", stable_json(rec_print_robust))
    output_print("named:", stable_json({k: {p: (v["pass_"], v["failed"]) for p, v in d.items()} for k, d in named.items()}))
    output_print("sens:", sens, "temp:", temp)
    output_print("profile:", stable_json(prof))
    output_print("CAD rev B:", stable_json(rev_b, sort_keys=True))
    output_print("AS DRAWN:", stable_json(as_drawn, sort_keys=True))
    return out


def compare_results(expected, actual, path=""):
    """Return deterministic leaf differences between two result trees."""
    differences = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        expected = {str(key): value for key, value in expected.items()}
        actual = {str(key): value for key, value in actual.items()}
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}" if path else key
            if key not in expected:
                differences.append(f"{child}: unexpected")
            elif key not in actual:
                differences.append(f"{child}: missing")
            else:
                differences.extend(compare_results(expected[key], actual[key], child))
    elif isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
        if len(expected) != len(actual):
            differences.append(f"{path}: length {len(actual)} != {len(expected)}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            differences.extend(compare_results(left, right, f"{path}[{index}]"))
    elif isinstance(expected, bool) or isinstance(actual, bool):
        if expected != actual:
            differences.append(f"{path}: {actual!r} != {expected!r}")
    elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if isinstance(expected, int) and isinstance(actual, int):
            equal = expected == actual
        else:
            equal = (math.isnan(float(expected)) and math.isnan(float(actual))) or math.isclose(
                float(expected), float(actual), rel_tol=1e-9, abs_tol=0.0
            )
        if not equal:
            differences.append(f"{path}: {actual!r} != {expected!r}")
    elif expected != actual:
        differences.append(f"{path}: {actual!r} != {expected!r}")
    return differences


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figures", action="store_true", help="write PNG figures")
    parser.add_argument("--check", action="store_true", help="compare calculations with committed JSON without writing")
    parser.add_argument("--out-dir", type=Path, help="write JSON and stdout capture under this directory")
    args = parser.parse_args(argv)
    if args.check and (args.figures or args.out_dir):
        parser.error("--check cannot be combined with --figures or --out-dir")

    global OUT, FIG, SVG, DXF, WRITE_OUTPUT, WRITE_FIGURES, WRITE_PROFILE
    WRITE_OUTPUT = not args.check
    WRITE_FIGURES = args.figures
    WRITE_PROFILE = not args.check
    stdout_path = STDOUT_DEFAULT
    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        OUT = args.out_dir / "gears.json"
        stdout_path = args.out_dir / "gears_stdout.txt"
        FIG = args.out_dir / "figures"
        SVG = args.out_dir / "gear_profile.svg"
        DXF = args.out_dir / "gear_profile.dxf"

    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        actual = run_analysis()
    report = capture.getvalue().replace("\r\n", "\n")
    if args.check:
        expected = json.loads(OUT_DEFAULT.read_text(encoding="utf-8"))
        differences = compare_results(expected, actual)
        if not update_note_block(
            render_as_drawn_block(actual["as_drawn"]),
            "<!-- GEARS-AS-DRAWN:BEGIN -->",
            "<!-- GEARS-AS-DRAWN:END -->",
            check=True,
        ):
            differences.append("docs/gripper/analysis/gears.md: stale GEARS-AS-DRAWN block")
        if not update_note_block(
            render_downstream_block(actual["as_drawn"]),
            "<!-- GEARS-DOWNSTREAM:BEGIN -->",
            "<!-- GEARS-DOWNSTREAM:END -->",
            check=True,
        ):
            differences.append("docs/gripper/analysis/gears.md: stale GEARS-DOWNSTREAM block")
        for difference in differences:
            print(difference)
        return 1 if differences else 0
    write_utf8_text(stdout_path, report)
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
