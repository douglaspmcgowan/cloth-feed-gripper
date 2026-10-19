"""Virtual actuator dyno + fatigue-to-failure for the cloth-feed gripper.

Lumped model: PWM servo (DC motor, quasi-static electrics, gearbox efficiency,
internal PD position loop with deadband and saturation) -> shaft / finger A ->
1:1 sector mesh (backlash, VDI 2736 tooth stiffness) -> finger B; Fin Ray tip
stiffness from fea_summary.json; cloth contact (stiff spring + Coulomb friction);
firmware force PI from firmware/gripper/config.h. Tests: torque-speed/efficiency,
stall + thermal RC, duty-cycle grip test, shock cases. Then rainflow (pylife) +
Miner damage for gear tooth root, TPU finger hot spot, knuckle arm root.

Run from the repo root (about 70 s):
  uv run --with numpy --with scipy --with matplotlib --with shapely --with pylife python analysis/gripper/dyno.py
Staleness check only (no simulation; exit 1 if any input changed since dyno.json was written):
  uv run --with numpy --with scipy --with matplotlib --with shapely --with pylife python analysis/gripper/dyno.py --check
Tags in the output JSON: [S] sourced, [D] derived, [A] assumed.
"""
import json
import math
import pathlib
import re
import time

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import hashlib  # noqa: E402
import sys  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
RES = ROOT / "analysis" / "gripper" / "results"
FIG = ROOT / "docs" / "gripper" / "figures"
T0 = time.time()
D2R = math.pi / 180.0

# Every file this script reads. Their hashes go into dyno.json; --check compares them with the files on disk, and a
# normal run refuses to write results if any of them changes while it runs (a parallel lane rewriting its outputs).
INPUT_FILES = ["cad/gripper/params.json", "analysis/gripper/results/fea_summary.json",
               "analysis/gripper/results/finger_beam.json", "firmware/gripper/config.h", "analysis/gripper/gears.py",
               "analysis/gripper/results/gears.json"]


def input_hashes():
    return {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest()[:16] for f in INPUT_FILES}


def stale_inputs(recorded):
    now = input_hashes()
    return {f: {"recorded": recorded.get(f), "on_disk": now[f]} for f in INPUT_FILES if recorded.get(f) != now[f]}


if "--check" in sys.argv:
    try:
        rec_h = json.loads((RES / "dyno.json").read_text(encoding="utf-8"))["inputs"]["input_file_sha256_16"]["value"]
    except (OSError, KeyError, ValueError) as exc:
        print("STALE: dyno.json has no input hashes (%s); re-run dyno.py" % exc)
        sys.exit(1)
    bad = stale_inputs(rec_h)
    if bad:
        print("STALE: dyno.json was computed from different inputs; re-run dyno.py")
        for f, v in bad.items():
            print("  %s recorded %s, on disk %s" % (f, v["recorded"], v["on_disk"]))
        sys.exit(1)
    print("FRESH: all %d input hashes match dyno.json" % len(INPUT_FILES))
    sys.exit(0)

HASH0 = input_hashes()
FIG.mkdir(parents=True, exist_ok=True)

params = json.loads((ROOT / "cad/gripper/params.json").read_text(encoding="utf-8"))
fea = json.loads((RES / "fea_summary.json").read_text(encoding="utf-8"))
beam = json.loads((RES / "finger_beam.json").read_text(encoding="utf-8"))
cfg_txt = (ROOT / "firmware/gripper/config.h").read_text(encoding="utf-8")
CFG = {m.group(1): float(m.group(2)) for m in re.finditer(r"#define\s+(\w+)\s+(-?[\d.]+)", cfg_txt)}
G = params["grip"]
DC = params["duty_cycle"]
AL = params["materials"]["allowables"]
# Gear lane (read-only): geometry, VDI 2736 / ISO 6336 root + flank stress incl. K_Hbeta (F_beta_y derived per face
# width by gears.fby), S-N curves with knockdowns. Importing gears.py runs only its module-level setup; main() is guarded.
sys.path.insert(0, str(ROOT / "analysis" / "gripper"))
import gears as GL  # noqa: E402

GJ = json.loads((RES / "gears.json").read_text(encoding="utf-8"))
GREC = GJ["recommendation"]
if (ROOT / "analysis/gripper/gears.py").stat().st_mtime > (RES / "gears.json").stat().st_mtime + 1:
    print("WARNING: gears.py is newer than gears.json; the gear lane's recommendation may be stale")

INPUTS = {}
INPUTS["input_file_sha256_16"] = {"value": HASH0, "tag": "D",
                                  "note": "sha256 (first 16 hex) of every input file at run start; dyno.py --check compares with disk"}


def inp(name, value, tag, note):
    INPUTS[name] = {"value": value, "tag": tag, "note": note}
    return value


# ---------------------------------------------------------------- servo datasheet
V = inp("V_rail", 6.8, "A", "torque_and_actuator.md 3.6: DS3218MG on a 6.8 V rail (reversible)")
T_S = inp("T_stall_Nm", 21.5 * 0.0980665, "S", "DS3218MG 21.5 kg*cm @ 6.8 V (Miuzei + SpeedyFPV, actuators.csv A17)")
W0 = inp("w_noload_rad_s", (60 * D2R) / 0.14, "S", "0.14 s/60 deg @ 6.8 V (actuators.csv A17)")
I_S_DS = inp("I_stall_datasheet_A", 2.2, "S", "Miuzei datasheet 2.2 A @ 6.8 V; Annimos says 1.8 A")
I_IDLE = inp("I_idle_A", 0.005, "S", "Miuzei idle 5 mA")
I_NL = inp("I_noload_A", 0.20, "A", "no-load running current; not published")
ETA_G = inp("eta_gearbox", 0.65, "A", "multi-stage metal spur servo gearbox efficiency")
N_G = inp("gear_ratio", 300.0, "A", "DS3218 ratio not published; DS3235 datasheet gives 373 [S]")
J_M = inp("J_rotor_kgm2", 0.6e-7, "A", "130-size DC motor rotor ~0.6 g*cm^2; +20 % for gear train")
J_REFL = J_M * N_G ** 2 * 1.2
DB = inp("deadband_deg", 3 * 0.09, "S", "3 us deadband (A17) x 0.09 deg/us (2000 us / 180 deg) [D]")
E_SAT = inp("servo_P_saturation_deg", 3.0, "A", "position error at which the servo drive reaches full duty")
ZETA_S = inp("servo_loop_zeta", 0.8, "A", "internal PD damping ratio")
US_PER_DEG = 2000.0 / 180.0


def fit_motor(mode, Vr=None, Ts=None, w0=None, Is=None):
    """Output-referred DC motor: V = R i + K w ; T_out = eta K (i - I_nl) moving, eta K V/R at stall."""
    Vr, Ts, w0, Is = (Vr or V), (Ts or T_S), (w0 or W0), (Is or I_S_DS)
    if mode == "A_mech":  # keep stall torque + no-load speed; stall current is inferred
        R = Vr ** 2 / (Ts * w0 / ETA_G + I_NL * Vr)
        K = (Vr - R * I_NL) / w0
    else:  # "B_elec": keep stall torque + datasheet stall current; no-load speed is inferred
        R = Vr / Is
        K = Ts * R / (ETA_G * Vr)
    return {"mode": mode, "V": Vr, "R_ohm": R, "K_out_NmA": K, "I_stall_A": Vr / R, "w0_rad_s": (Vr - R * I_NL) / K,
            "s_per_60deg": (60 * D2R) / ((Vr - R * I_NL) / K), "T_stall_Nm": ETA_G * K * Vr / R,
            "Kt_motor_mNm_per_A": 1000 * K / N_G}


MOT = {m: fit_motor(m) for m in ("A_mech", "B_elec")}
consistency = {
    "Ts_x_w0_W": T_S * W0, "V_x_Istall_W": V * I_S_DS,
    "eta_required_for_all_three": T_S * W0 / (V * I_S_DS) / (1 - I_NL * (V / I_S_DS) / V),
    "note": "An ideal DC motor with eta <= 1 needs T_stall*w0 <= eta*V*I_stall*(1 - I_nl*R/V). The datasheet triple "
            "violates it, so one of the three numbers is optimistic [D]. Fit A (baseline) keeps the two mechanical "
            "specs and infers the stall current; Fit B keeps the current and infers a slower no-load speed."}

INPUTS["model_assumptions"] = {"value": {
    "pwm_average_value": "motor current is the PWM average with continuous, ripple-free conduction (L/R >> PWM period); "
                         "L ignored. Bounding case i2_bound = |d| ((sgn(d) V - K w)/R)^2 (fully discontinuous) is carried "
                         "through the thermal run as test3_duty_cycle.thermal_30min_pwm_bound; M6/M7 scope the motor current",
    "reflected_rotor_inertia": "J_m N^2 is lumped on the output shaft, downstream of the gearbox efficiency, so rotor kinetic "
                               "energy reaches the teeth with no gearbox loss: jam and collision peaks are conservative",
    "knuckle_notch": "Kf 1.14 applied on top of the finger_beam Kt 1.5: notch counted twice, conservative"},
    "tag": "A", "note": "modelling assumptions that bias results; reversible"}

# ---------------------------------------------------------------- mechanism
RC = inp("r_c_m", G["r_c_design_mm"] / 1000, "D", "DESIGN-BASIS D3, 65 mm")
ETA_X = inp("eta_mesh_pivot", G["eta_mesh_pivot"], "A", "DESIGN-BASIS eta 0.85 (applied on each finger path)")
rec = fea["recommended"]["linear"]["tip"]
K_F = inp("k_finger_N_per_m", 1000 * rec["k_N_per_mm"], "D",
          "fea_summary.json recommended L45 finger, tip pad, E 67 (linear) = %.3f N/mm" % rec["k_N_per_mm"])
K_CLOTH = inp("k_cloth_N_per_m", 30e3, "A", "0.3 mm cotton ply under the pad, through-thickness, stiff spring")
C_CONT = inp("c_contact_Ns_per_m", 3.0, "A", "TPU hysteresis damping in contact")
T_CLOTH = inp("cloth_t_m", params["work_cell"]["cloth"]["thickness_mm"] / 1000, "A", "0.3 mm one ply")
G0 = inp("gap_at_theta0_m", 1.0e-3, "D", "DESIGN-BASIS R18: pads 1 mm apart at theta = 0")
MU = inp("mu_pad_cloth", G["mu_pad_cloth"], "A", "0.4, M2 measures")
TENS = inp("tension_N", G["tension_N"], "A", "2 N, M3 measures")
THETA_MIN = inp("theta_min_deg", G["theta_min_deg"], "D", "DESIGN-BASIS R18; config.h JAW_MIN_DEG -11 agrees")
THETA_OPEN = G["theta_open_max_deg"]

# Gear options, built from the gear lane's output (gears.json), never hardcoded: its three recommendations, the best PETG
# geometry of its sweep, the withdrawn previous pick, and its named geometries (DESIGN-BASIS / current CAD). Each is run in
# every material. The time-domain drivetrain is the gear lane's printed recommendation. [D gear lane]
JT_PRINT, JT_CNC = GJ["inputs"]["jt_print_mm"]["value"], GJ["inputs"]["jt_cnc_mm"]["value"]


def _parse_geo(txt, alpha=20, x=0.0):
    m_ = re.search(r"m([\d.]+)\s+z(\d+)(?:\s+a(\d+))?(?:\s+x([\d.]+))?\s+b(\d+)", txt)
    return dict(m=float(m_.group(1)), z=int(m_.group(2)), alpha=int(m_.group(3) or alpha), x=float(m_.group(4) or x),
                b=float(m_.group(5)))


def _key(o):
    return "m%gz%da%d%sb%g" % (o["m"], o["z"], o["alpha"], ("x%g" % o["x"]) if o["x"] else "", o["b"])


GEAR_OPTS = {}
for _tag, _lab in (("printed", "gears.json printed recommendation"), ("printed_robust", "gears.json robust printed alternative"),
                   ("cnc", "gears.json CNC recommendation")):
    _r = GREC[_tag]
    _o = dict(m=_r["m"], z=_r["z"], alpha=_r["alpha"], x=_r["x"], b=_r["b"], jt=_r["backlash"]["jt_design_mm"],
              named=_r["pair"], role=_tag, note="%s (%s, a_w %.2f)" % (_lab, _r["pair"], _r["a_w"]))
    GEAR_OPTS[_key(_o)] = _o
_pb = GJ["sweep"]["per_pair"]["PETG"]["best_margin_passing"]
if _pb:
    _o = _parse_geo(_pb[0]["geo"])
    _o.update(jt=JT_PRINT, named="PETG", role="petg_best", note="gears.json best PETG (margin %.2f, not recommended)" % _pb[0]["margin"])
    GEAR_OPTS.setdefault(_key(_o), _o)
_pp = GREC["sensitivity"].get("previous_pick_m1.25z19b10")
if _pp:
    _o = _parse_geo(_pp["geometry"])
    _o.update(jt=JT_PRINT, named=None, role="withdrawn", note="previous pick, withdrawn by gears.md (F_beta_y scaled to b)")
    GEAR_OPTS.setdefault(_key(_o), _o)
for _lab in GJ["named_geometries"]:
    _o = _parse_geo(_lab)  # gears.py main(): named geometries are alpha 20, x 0
    _o.update(jt=JT_PRINT, named=None, role="named", note="gears.json named geometry '%s'" % _lab)
    GEAR_OPTS.setdefault(_key(_o), _o)
GEAR_MATS = ("PLA", "PETG", "PA6-CF", "POM", "Al6061")
for _k, _o in GEAR_OPTS.items():
    _o["geo"] = GL.geometry(_o["m"], _o["z"], _o["alpha"], _o["x"], _o["jt"] if _o["named"] != "POM" else JT_CNC)
    _o["jt"] = _o["jt"] if _o["named"] != "POM" else JT_CNC
GEAR_BASE = [k for k, o in GEAR_OPTS.items() if o["role"] == "printed"][0]  # simulated drivetrain = gear lane printed pick
GEAR_ROBUST = [k for k, o in GEAR_OPTS.items() if o["role"] == "printed_robust"][0]
GEAR_CNC = [k for k, o in GEAR_OPTS.items() if o["role"] == "cnc"][0]
GB = GEAR_OPTS[GEAR_BASE]
GB_MAT = GB["named"]
R_P = GB["geo"]["r"] / 1000
X_F = inp("x_f_m", GB["geo"]["x_f"] / 1000, "D", "pad x offset from pivot = a_w/2 - gap/2 (gears.json printed pick %s, a_w %.2f)"
          % (GEAR_BASE, GB["geo"]["a_w"]))


def mesh_k(opt, mat):
    """VDI 2736 deformation relation lambda = 7.5 (Ft/b)(1/E1 + 1/E2), i.e. c_gamma = 1/(7.5 (2/E)) per mm of face
    [S via gears.md 2]; torsional k = c_gamma b r^2 (Ft and lambda at the reference circle)."""
    cg = 1 / (7.5 * 2 / GL.MAT[mat]["E"])  # N/mm^2
    return cg * opt["b"] * 1000 * (opt["geo"]["r"] / 1000) ** 2


K_MESH = inp("k_mesh_Nm_per_rad", mesh_k(GB, GB_MAT), "D", "VDI 2736 deformation relation, %s pair, %s" % (GB_MAT, GEAR_BASE))
JT = inp("backlash_jt_m", GB["jt"] / 1000, "S", "jt %.2f mm design backlash (gears.json recommendation.printed.backlash, tolerance_stacks.md T07)" % GB["jt"])
PHI_BL = JT / R_P
m_fing = fea["recommended"]["linear"]["mass_g"] / 1000
J_FING = m_fing * (0.025 + 0.0225) ** 2 + m_fing * 0.045 ** 2 / 12
J_KN = 0.003 * 0.015 ** 2 + 0.001 * R_P ** 2
J_B = inp("J_fingerB_kgm2", J_FING + J_KN, "D", "TPU finger %.2f g at 47.5 mm + 3 g knuckle + 1 g sector" % (1000 * m_fing))
J_A = inp("J_shaftA_kgm2", J_REFL + J_B + 0.003 * 0.008 ** 2, "D", "reflected rotor (J_m N^2 x 1.2) + finger A + horn")
C_MESH = 2 * 0.10 * math.sqrt(K_MESH * J_B)
C_PIV = 1e-4

# ---------------------------------------------------------------- firmware (config.h)
FW = {k: CFG[k] for k in ("CONTROL_PERIOD_MS", "SERVO_TAU_S", "CTRL_DELAY_S", "CTRL_TAU_CL_S", "CTRL_U_MIN_DEG",
                          "CTRL_RATE_LIMIT_DPS", "CTRL_I_DEADBAND_N", "F_TOUCH_N", "F_TARGET_DEFAULT_N",
                          "F_SOFT_LIMIT_N", "F_TRIP_N", "F_RAMP_NPS", "JAW_SPEED_FAST_DPS", "JAW_SPEED_NEAR_DPS",
                          "JAW_SLOW_ZONE_DEG", "JAW_PREGRASP_DEG", "FSR_EMA_ALPHA", "ADC_PERIOD_US",
                          "CTRL_SOFT_BACKOFF_DEG", "SERVO_DEG_AT_JAW0", "FINGER_K_MAX_N_PER_MM", "R_C_MM",
                          "STALL_CURRENT_A", "STALL_CURRENT_MS", "JAW_MIN_DEG", "THETA_C0_DEFAULT", "CAL_C0_MIN_DEG",
                          "CAL_C0_MAX_DEG")}
# SIMC gains exactly as the config.h comment specifies (force_ctrl.h not in the tree yet) [D]
FW["K_STIFF_N_PER_DEG"] = FW["FINGER_K_MAX_N_PER_MM"] * FW["R_C_MM"] * D2R
FW["KP_DEG_PER_N"] = FW["SERVO_TAU_S"] / (FW["K_STIFF_N_PER_DEG"] * (FW["CTRL_TAU_CL_S"] + FW["CTRL_DELAY_S"]))
FW["TI_S"] = min(FW["SERVO_TAU_S"], 4 * (FW["CTRL_TAU_CL_S"] + FW["CTRL_DELAY_S"]))
FW["KI_DEG_PER_NS"] = FW["KP_DEG_PER_N"] / FW["TI_S"]
# theta is + open and the pads are G0 apart at theta = 0 (R18), so they touch with no cloth at theta = -asin(G0/(2 r_c)).
# The firmware stores the COMMAND angle at which the FSR sees touch in CALIBRATE (R21); that is emulated below after the
# simulator is defined (it adds servo lag, deadband and backlash). The geometric value is kept as a sensitivity. [D]
THETA_C0_GEOM = -math.asin(G0 / (2 * RC)) / D2R
THETA_C0 = FW["THETA_C0_DEFAULT"] if "THETA_C0_DEFAULT" in FW else 0.0  # replaced by the CALIBRATE emulation
TAU_FSR = -(FW["ADC_PERIOD_US"] * 1e-6) / math.log(1 - FW["FSR_EMA_ALPHA"])
INPUTS["firmware"] = {"value": FW, "tag": "S", "note": "firmware/gripper/config.h (parsed); FSR EMA tau %.4f s [D]" % TAU_FSR}

# ---------------------------------------------------------------- thermal (two-node, maxon key information)
TH = {"Rth1_K_W": 8.0, "Rth2_K_W": 22.0, "tau_w_s": 12.0, "tau_h_s": 450.0, "alpha_Cu": 0.0039,
      "T_winding_max_C": 125.0, "T_case_limit_C": 60.0}
INPUTS["thermal"] = {"value": TH, "tag": "A", "note": "structure and alpha_Cu from maxon 'DC motor and EC motor Key "
                     "information' (Rth1 winding-housing, Rth2 housing-ambient, winding/motor time constants); values "
                     "assumed for a small motor inside a plastic servo case; M7 measures"}
T_AMB = 40.0  # DESIGN-BASIS 6 ambient max


def thermal_run(t, i_arr, R20, Tamb, Tw0=None, Th0=None, Rth2=None, scale_R=True):
    """Two-node RC. scale_R: copper loss i^2 R20 (1 + alpha (Tw - 20)) with i fixed by the torque demand (average-value
    model). scale_R False: loss i^2 R20 held constant, for the discontinuous-conduction bound, where the mean current is
    fixed by torque and P = |i_mean| (V - K w) does not depend on R(T)."""
    Rth1, Rth2 = TH["Rth1_K_W"], (Rth2 or TH["Rth2_K_W"])
    Cw, Ch = TH["tau_w_s"] / Rth1, TH["tau_h_s"] / Rth2
    Tw = Tamb if Tw0 is None else Tw0
    Th = Tamb if Th0 is None else Th0
    out = np.zeros((len(t), 3))
    for k in range(len(t)):
        dt = t[k] - t[k - 1] if k else 0.0
        P = i_arr[k] ** 2 * R20 * ((1 + TH["alpha_Cu"] * (Tw - 20)) if scale_R else 1.0)
        q1 = (Tw - Th) / Rth1
        Tw += dt * (P - q1) / Cw
        Th += dt * (q1 - (Th - Tamb) / Rth2) / Ch
        out[k] = (Tw, Th, P)
    return out


# ---------------------------------------------------------------- time-domain simulator
class Sim:
    def __init__(self, mot, J_A_=None, K_MESH_=None, gain=None, phi_bl=None, zeta=None):
        self.m = mot
        zeta = ZETA_S if zeta is None else zeta
        self.JA = J_A_ or J_A
        self.KM = K_MESH_ or K_MESH
        self.PB = PHI_BL if phi_bl is None else phi_bl
        self.CM = 2 * 0.10 * math.sqrt(self.KM * J_B)
        self.V = mot.get("V", V)
        a = ETA_G * mot["K_out_NmA"] * self.V / mot["R_ohm"]
        self.Kps = 1.0 / (E_SAT * D2R)
        wn = math.sqrt(a * self.Kps / self.JA)
        bemf = ETA_G * mot["K_out_NmA"] ** 2 / mot["R_ohm"]
        self.Kds = max(0.0, (2 * zeta * self.JA * wn - bemf) / a)

    def run(self, t_end, dt, script, y0=None, cloth=True, rec_every=10):
        """script(t, sim) -> dict(theta_cmd_deg, tension_N, obs) called at 50 Hz (firmware tick)."""
        m = self.m
        R, K, V = m["R_ohm"], m["K_out_NmA"], self.V
        cA, wA, cB, wB, fsr = y0 if y0 else (-THETA_OPEN * D2R, 0.0, -THETA_OPEN * D2R, 0.0, 0.0)
        tcl = T_CLOTH if cloth else 0.0
        keq = 1.0 / (2.0 / K_F + (1.0 / K_CLOTH if cloth else 0.0))
        tick = FW["CONTROL_PERIOD_MS"] / 1000.0
        next_tick = 0.0
        cmd = {"theta_cmd_deg": -cA / D2R, "tension_N": 0.0, "obs": None}
        a_fsr = dt / TAU_FSR
        n = int(round(t_end / dt))
        rows = []
        F = 0.0
        slip = False
        pen_prev = tcl - (G0 - RC * (math.sin(cA) + math.sin(cB)))
        for k in range(n):
            t = k * dt
            if t >= next_tick - 1e-12:
                self.F_meas = fsr
                self.state = (cA, wA, cB, wB, fsr)
                cmd = script(t, self)
                next_tick += tick
            # servo command, quantized to 1 us
            us = round((FW["SERVO_DEG_AT_JAW0"] + cmd["theta_cmd_deg"]) * US_PER_DEG)
            c_cmd = -(us / US_PER_DEG - FW["SERVO_DEG_AT_JAW0"]) * D2R
            e = c_cmd - cA
            hb = 0.5 * DB * D2R
            e_eff = 0.0 if abs(e) < hb else (e - hb if e > 0 else e + hb)
            d = self.Kps * e_eff - self.Kds * wA
            d = 1.0 if d > 1.0 else (-1.0 if d < -1.0 else d)
            i = (d * V - K * wA) / R
            Tm = K * (i - I_NL * math.tanh(wA / 0.05))
            # gearbox efficiency: eta when the motor drives, 1/eta when the load back-drives; blended over
            # |w| < 0.05 rad/s so the switch does not chatter at a hold (motoring convention at rest) [A]
            sg = math.tanh(wA / 0.05) * (1.0 if Tm >= 0 else -1.0)
            Tout = Tm * (ETA_G if sg >= 0 else ETA_G + (1.0 / ETA_G - ETA_G) * (-sg))
            # contact
            gap = G0 - RC * (math.sin(cA) + math.sin(cB))
            pen = tcl - gap
            if pen > 0:
                F = keq * pen + C_CONT * (pen - pen_prev) / dt
                F = F if F > 0 else 0.0
            else:
                F = 0.0
            pen_prev = pen
            # cloth friction carries the process tension (opening moment on each finger)
            ten = cmd["tension_N"]
            fcap = MU * F
            if ten > 0 and F > 0:
                f = ten / 2 if ten / 2 <= fcap else fcap
                slip = ten / 2 > fcap
            else:
                f = 0.0
                slip = ten > 0
            Mten = f * X_F
            # mesh with backlash
            dl = cA - cB
            hbl = 0.5 * self.PB
            if dl > hbl:
                Tmesh = self.KM * (dl - hbl) + self.CM * (wA - wB)
                Tmesh = Tmesh if Tmesh > 0 else 0.0
            elif dl < -hbl:
                Tmesh = self.KM * (dl + hbl) + self.CM * (wA - wB)
                Tmesh = Tmesh if Tmesh < 0 else 0.0
            else:
                Tmesh = 0.0
            # external obstacle on finger B (shock cases): obs(t, cB, wB) -> torque (closing +)
            Tobs = cmd["obs"](t, cB, wB) if cmd["obs"] else 0.0
            TA = Tout - Tmesh - (F * RC + Mten) / ETA_X - C_PIV * wA
            TB = ETA_X * Tmesh - F * RC - Mten - C_PIV * wB + Tobs
            wA += dt * TA / self.JA
            wB += dt * TB / J_B
            cA += dt * wA
            cB += dt * wB
            fsr += a_fsr * (F - fsr)
            if k % rec_every == 0:
                # i_bnd2: mean i^2 if conduction is fully discontinuous (L/R << PWM period): current (sgn(d) V - K w)/R
                # during the on-time fraction |d|, zero otherwise. Bounds the average-value model's i^2 from above. [A]
                i_on = ((V if d >= 0 else -V) - K * wA) / R
                rows.append((t, cmd["theta_cmd_deg"], -cA / D2R, -cB / D2R, F, fsr, Tout, Tmesh, i, d * i * V,
                             i * i * R, Tout * wA, ten, 1.0 if slip else 0.0, Tobs, d, abs(d) * i_on * i_on))
        self.state = (cA, wA, cB, wB, fsr)
        cols = ["t", "theta_cmd", "theta_A", "theta_B", "F", "F_fsr", "T_servo", "T_mesh", "i", "P_elec",
                "P_cu", "P_mech", "tension", "slip", "T_obs", "duty", "i2_bound"]
        a = np.array(rows)
        return {c: a[:, j] for j, c in enumerate(cols)}


class Firmware:
    """Grip sequence per config.h: fast pre-close, contact search, force PI with setpoint ramp, hold, release."""

    def __init__(self, t_close, t_release, t_feed0, t_feed1, F_sp=None, tension=TENS, tension_fn=None, obs=None, theta_c0=None):
        self.tc, self.tr, self.tf0, self.tf1 = t_close, t_release, t_feed0, t_feed1
        self.c0 = THETA_C0 if theta_c0 is None else theta_c0
        self.Fsp_target = F_sp if F_sp else FW["F_TARGET_DEFAULT_N"]
        self.tension = tension
        self.tension_fn = tension_fn
        self.obs = obs
        self.mode = "OPEN"
        self.cmd = THETA_OPEN
        self.I = 0.0
        self.Fsp = 0.0
        self.th_contact = None
        self.events = {}
        self.dt = FW["CONTROL_PERIOD_MS"] / 1000.0

    def __call__(self, t, sim):
        F = sim.F_meas
        dt = self.dt
        if t >= self.tr and self.mode != "RELEASE":
            self.mode = "RELEASE"
            self.events["release"] = t
        if self.mode == "OPEN" and t >= self.tc:
            self.mode = "FAST"
            self.events["close_start"] = t
        if self.mode == "FAST":
            self.cmd = max(self.c0 + FW["JAW_SLOW_ZONE_DEG"], self.cmd - FW["JAW_SPEED_FAST_DPS"] * dt)
            if self.cmd <= self.c0 + FW["JAW_SLOW_ZONE_DEG"]:
                self.mode = "SEARCH"
                self.events["search_start"] = t
        elif self.mode == "SEARCH":
            if F >= FW["F_TOUCH_N"]:
                self.mode = "FORCE"
                self.th_contact = self.cmd
                self.Fsp = F
                self.events["contact"] = t
            else:
                self.cmd = max(THETA_MIN, self.cmd - FW["JAW_SPEED_NEAR_DPS"] * dt)
        elif self.mode == "FORCE":
            self.Fsp = min(self.Fsp_target, self.Fsp + FW["F_RAMP_NPS"] * dt)
            err = self.Fsp - F
            u_prev = self.th_contact - self.cmd
            u_hi = self.th_contact - THETA_MIN
            if F > FW["F_TRIP_N"]:
                self.events.setdefault("trip", t)
            if F > FW["F_SOFT_LIMIT_N"]:
                u = u_prev - FW["CTRL_SOFT_BACKOFF_DEG"]
                self.I *= 0.5
            else:
                I_new = self.I + (FW["KI_DEG_PER_NS"] * err * dt if abs(err) > FW["CTRL_I_DEADBAND_N"] else 0.0)
                u_ff = self.Fsp / FW["K_STIFF_N_PER_DEG"]
                u = u_ff + FW["KP_DEG_PER_N"] * err + I_new
                if FW["CTRL_U_MIN_DEG"] <= u <= u_hi:
                    self.I = I_new  # conditional integration (anti-windup) [A]
                u = min(max(u, FW["CTRL_U_MIN_DEG"]), u_hi)
            du = FW["CTRL_RATE_LIMIT_DPS"] * dt
            u = min(max(u, u_prev - du), u_prev + du)
            self.cmd = self.th_contact - u
            if "at_target" not in self.events and abs(F - self.Fsp_target) < 0.3:
                self.events["at_target"] = t
        elif self.mode == "RELEASE":
            self.cmd = min(THETA_OPEN, self.cmd + FW["JAW_SPEED_FAST_DPS"] * dt)
        ten = 0.0
        if self.tf0 <= t < self.tf1 and self.mode == "FORCE":
            ten = self.tension_fn(t) if self.tension_fn else self.tension
        return {"theta_cmd_deg": self.cmd, "tension_N": ten, "obs": self.obs(t) if self.obs else None}


# ================================================================ CALIBRATE emulation (R21)
# Close with no cloth from the default theta_c0 (config.h THETA_C0_DEFAULT) until the FSR reads F_TOUCH, and store the
# command angle then, as the firmware does. Fit A and Fit B both, since servo lag differs; the baseline uses Fit A. [D]
def calibrate(mot):
    s_ = Sim(mot)
    fw_ = Firmware(0.05, 1e9, 1e9, 1e9, theta_c0=FW["THETA_C0_DEFAULT"])
    s_.run(1.0, 4e-5, fw_, cloth=False, rec_every=50)
    return fw_.th_contact


CAL = {}
for _key_m, _mot in MOT.items():
    CAL[_key_m] = calibrate(_mot)
THETA_C0 = CAL["A_mech"]
CAL_OK = FW["CAL_C0_MIN_DEG"] <= THETA_C0 <= FW["CAL_C0_MAX_DEG"]
INPUTS["theta_c0"] = {"value": {"calibrated_cmd_deg_A_mech": CAL["A_mech"], "calibrated_cmd_deg_B_elec": CAL["B_elec"],
                                "geometric_touch_deg": THETA_C0_GEOM, "in_config_window": CAL_OK},
                      "tag": "D", "note": "CALIBRATE emulation (R21): command angle at FSR >= F_TOUCH with no cloth; "
                      "geometric pad touch = -asin(G0/(2 r_c)); both negative because theta is + open"}


# ================================================================ TEST 1: torque-speed + efficiency map
def ts_curve(mot, d, T):
    i = T / (ETA_G * mot["K_out_NmA"]) + I_NL
    w = (d * V - mot["R_ohm"] * i) / mot["K_out_NmA"]
    eta = np.where((w > 0) & (i > 0), T * w / (d * V * i), np.nan)
    return w, i, eta


test1 = {}
for key, mot in MOT.items():
    T = np.linspace(0, mot["T_stall_Nm"], 60)
    w, i, eta = ts_curve(mot, 1.0, T)
    j = np.nanargmax(eta)
    P = T * w
    test1[key] = {"T_Nm": T[::6].round(4).tolist(), "w_rad_s": w[::6].round(4).tolist(), "I_A": i[::6].round(4).tolist(),
                  "eta_max": float(eta[j]), "T_at_eta_max": float(T[j]), "P_mech_max_W": float(np.nanmax(P)),
                  "T_at_Pmax": float(T[np.nanargmax(P)])}
T_HOLD_REQ = 0.792  # torque_and_actuator.md hold incl. tension term [D there]
for key, mot in MOT.items():
    i_h = T_HOLD_REQ / (ETA_G * mot["K_out_NmA"])
    test1[key]["hold_0p792Nm_current_A"] = i_h
    test1[key]["hold_0p792Nm_Pcu_W"] = i_h ** 2 * mot["R_ohm"]
    test1[key]["hold_fraction_of_stall"] = T_HOLD_REQ / mot["T_stall_Nm"]

fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
Tg = np.linspace(0.001, T_S, 200)
Wg = np.linspace(0.01, W0 * 1.05, 200)
TT, WW = np.meshgrid(Tg, Wg)
mA = MOT["A_mech"]
iG = TT / (ETA_G * mA["K_out_NmA"]) + I_NL
dG = (mA["R_ohm"] * iG + mA["K_out_NmA"] * WW) / V
effG = np.where(dG <= 1.0, TT * WW / (dG * V * iG), np.nan)
cs = ax[0].contourf(TT, WW * 60 / (2 * math.pi), effG * 100, levels=np.arange(0, 60, 5), cmap="viridis")
fig.colorbar(cs, ax=ax[0], label="efficiency, shaft power / rail power (%)")
for d in (0.25, 0.5, 0.75, 1.0):
    w, _, _ = ts_curve(mA, d, Tg)
    ax[0].plot(Tg[w > 0], w[w > 0] * 60 / (2 * math.pi), "w-", lw=1)
    ax[0].text(0.05, (d * V - mA["R_ohm"] * I_NL) / mA["K_out_NmA"] * 60 / (2 * math.pi), "duty %.2f" % d, color="w", fontsize=8)
mB = MOT["B_elec"]
w, _, _ = ts_curve(mB, 1.0, Tg)
ax[0].plot(Tg[w > 0], w[w > 0] * 60 / (2 * math.pi), "r--", lw=1.5, label="Fit B (datasheet 2.2 A), duty 1")
ax[0].axvline(T_HOLD_REQ, color="orange", ls=":", label="hold 0.792 N·m")
ax[0].plot([T_S], [0], "ro")
ax[0].plot([0], [W0 * 60 / (2 * math.pi)], "ro", label="datasheet points")
ax[0].set_xlabel("output torque (N·m)")
ax[0].set_ylabel("output speed (rpm)")
ax[0].set_title("DS3218MG @ 6.8 V, Fit A (baseline): torque-speed and efficiency")
ax[0].legend(fontsize=8, loc="upper right")
for key, mot, sty in (("A_mech", mA, "b-"), ("B_elec", mB, "r--")):
    w, i, eta = ts_curve(mot, 1.0, Tg)
    ax[1].plot(Tg, i, sty, label="current, " + key)
    ax[1].plot(Tg, np.clip(Tg * w, 0, None), sty, alpha=0.5, label="shaft power (W), " + key)
ax[1].axvline(T_HOLD_REQ, color="orange", ls=":")
ax[1].axhline(3.0, color="k", ls=":", label="3 A rail rating (R27)")
ax[1].set_xlabel("output torque (N·m)")
ax[1].set_ylabel("A  /  W")
ax[1].legend(fontsize=8)
ax[1].set_title("current and shaft power at full duty")
fig.tight_layout()
fig.savefig(FIG / "dyno_torque_speed.png", dpi=130)
plt.close(fig)

# ================================================================ TEST 2: stall + thermal
test2 = {}
t_st = np.arange(0, 120.0, 0.01)
fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
for key, mot, sty in (("A_mech", mA, "b"), ("B_elec", mB, "r")):
    for Tamb, ls in ((25.0, "--"), (T_AMB, "-")):
        # at stall with full duty the current is V / R(T): recompute with rising resistance
        Rth1, Rth2 = TH["Rth1_K_W"], TH["Rth2_K_W"]
        Cw, Ch = TH["tau_w_s"] / Rth1, TH["tau_h_s"] / Rth2
        Tw = Th = Tamb
        rows = []
        for k, t in enumerate(t_st):
            Rt = mot["R_ohm"] * (1 + TH["alpha_Cu"] * (Tw - 20)) / (1 + TH["alpha_Cu"] * (Tamb - 20))
            i = V / Rt
            P = V * i
            q1 = (Tw - Th) / Rth1
            if k:
                Tw += 0.01 * (P - q1) / Cw
                Th += 0.01 * (q1 - (Th - Tamb) / Rth2) / Ch
            rows.append((t, i, ETA_G * mot["K_out_NmA"] * i, Tw, Th))
        a = np.array(rows)
        hit = np.where(a[:, 3] >= TH["T_winding_max_C"])[0]
        t_lim = float(a[hit[0], 0]) if len(hit) else None
        k02 = int(0.2 / 0.01)
        k03 = int(0.3 / 0.01)
        test2["%s_amb%d" % (key, Tamb)] = {
            "I_stall_A": float(a[0, 1]), "T_stall_Nm": float(a[0, 2]), "P_stall_W": float(a[0, 1] * V),
            "dTw_at_0p2s_K": float(a[k02, 3] - Tamb), "dTw_at_0p3s_K": float(a[k03, 3] - Tamb),
            "t_to_winding_limit_s": t_lim, "T_case_at_60s_C": float(a[6000, 4]),
            "I_after_60s_A": float(a[6000, 1]), "rail_3A_exceeded": bool(a[0, 1] > 3.0)}
        ax[0].plot(a[:, 0], a[:, 3], sty + ls, label="winding %s, amb %d" % (key, Tamb))
        ax[0].plot(a[:, 0], a[:, 4], sty + ls, alpha=0.4)
        if Tamb == T_AMB:
            ax[1].plot(a[:, 0], a[:, 1], sty, label="current " + key)
            ax[1].plot(a[:, 0], a[:, 2], sty + ":", label="stall torque (N·m) " + key)
ax[0].axhline(TH["T_winding_max_C"], color="k", ls=":")
ax[0].axhline(TH["T_case_limit_C"], color="gray", ls=":")
ax[0].set_ylim(20, 200)
ax[0].set_xlabel("time blocked (s)")
ax[0].set_ylabel("°C (faint = motor housing / case proxy)")
ax[0].legend(fontsize=7)
ax[0].set_title("Locked-rotor stall, full duty, no protection")
ax[1].set_xlabel("time blocked (s)")
ax[1].legend(fontsize=8)
ax[1].set_title("Stall current and torque vs winding heating (amb 40 °C)")
fig.tight_layout()
fig.savefig(FIG / "dyno_stall.png", dpi=130)
plt.close(fig)

# ================================================================ TEST 3: duty cycle
ph = DC["phases_s"]
t_close = ph["approach_touchdown"]
t_feed0 = t_close + ph["close"] + ph["lift_move_to_needle"]
t_feed1 = t_feed0 + ph["feed_hold"]
t_rel = t_feed1
CYC = DC["cycle_s"]
DT = 4e-5
sim = Sim(mA)
duty_runs = {}
duty_sims = {}
for label, mot in (("A_mech", mA), ("B_elec", mB)):
    s = Sim(mot)
    fwc = Firmware(t_close, t_rel, t_feed0, t_feed1, theta_c0=CAL[label])
    r = s.run(CYC, DT, fwc, rec_every=25)
    duty_runs[label] = (r, fwc.events)
    duty_sims[label] = s
r, ev = duty_runs["A_mech"]
# close-time sensitivity to theta_c0 (Fit A, first 2 s only): geometric touch angle and the old (sign-wrong) +0.44 deg
close_sens = {}
for lab_, c0_ in (("calibrated_cmd", CAL["A_mech"]), ("geometric_touch", THETA_C0_GEOM), ("old_sign_error", -THETA_C0_GEOM)):
    s_ = Sim(mA)
    fw_ = Firmware(t_close, t_rel, t_feed0, t_feed1, theta_c0=c0_)
    s_.run(t_close + 1.5, DT, fw_, rec_every=50)
    e_ = fw_.events
    close_sens[lab_] = {"theta_c0_deg": c0_, "slow_zone_start_deg": c0_ + FW["JAW_SLOW_ZONE_DEG"],
                        "fast_s": e_.get("search_start", np.nan) - t_close,
                        "search_s": e_.get("contact", np.nan) - e_.get("search_start", np.nan),
                        "close_to_contact_s": e_.get("contact", np.nan) - t_close,
                        "close_to_5N_s": e_.get("at_target", np.nan) - t_close, "cmd_at_touch_deg": fw_.th_contact}
dtr = r["t"][1] - r["t"][0]


def cyc_metrics(r, ev):
    hold = (r["t"] > ev.get("at_target", t_close + 0.5) + 0.2) & (r["t"] < t_rel)
    feed = (r["t"] > t_feed0 + 0.2) & (r["t"] < t_feed1)
    E_el = float(np.sum(np.clip(r["P_elec"], 0, None)) * dtr + I_IDLE * V * CYC)
    return {
        "t_close_start": ev.get("close_start"), "t_contact": ev.get("contact"), "t_at_target": ev.get("at_target"),
        "close_to_contact_s": (ev.get("contact") or np.nan) - t_close,
        "close_to_5N_s": (ev.get("at_target") or np.nan) - t_close,
        "F_peak_N": float(r["F"].max()), "F_hold_mean_N": float(r["F"][hold].mean()),
        "F_feed_min_N": float(r["F"][feed].min()), "F_feed_mean_N": float(r["F"][feed].mean()),
        "theta_A_hold_deg": float(r["theta_A"][hold].mean()), "theta_cmd_hold_deg": float(r["theta_cmd"][hold].mean()),
        "T_servo_peak_Nm": float(r["T_servo"].max()), "T_servo_feed_mean_Nm": float(r["T_servo"][feed].mean()),
        "T_mesh_peak_Nm": float(r["T_mesh"].max()), "T_mesh_min_Nm": float(r["T_mesh"].min()),
        "T_mesh_feed_mean_Nm": float(r["T_mesh"][feed].mean()),
        "I_peak_A": float(r["i"].max()), "I_feed_mean_A": float(np.abs(r["i"][feed]).mean()),
        "I_rms_cycle_A": float(np.sqrt(np.mean(r["i"] ** 2))),
        "E_elec_J_per_cycle": E_el, "E_cu_J_per_cycle": float(np.sum(r["P_cu"]) * dtr),
        "E_mech_out_J_per_cycle": float(np.sum(np.clip(r["P_mech"], 0, None)) * dtr),
        "slip_fraction_of_feed": float(r["slip"][feed].mean()),
        "servo_hold_fraction_of_stall": float(r["T_servo"][feed].mean() / T_S)}


test3 = {k: cyc_metrics(*v) for k, v in duty_runs.items()}
test3["close_time_theta_c0_sensitivity_A_mech"] = close_sens
for k, (rr_, ev_) in duty_runs.items():
    test3[k]["t_search_start"] = ev_.get("search_start")
    test3[k]["search_s"] = (ev_.get("contact") or np.nan) - (ev_.get("search_start") or np.nan)
    test3[k]["theta_c0_calibrated_deg"] = CAL[k]

# thermal over 30 min of repeated cycles (current profile repeated), both fits, amb 40 and 25
test3["thermal_30min"] = {}
fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
test3["thermal_30min_pwm_bound"] = {}
for label, (rr, _) in duty_runs.items():
    tb = np.arange(0, CYC, 0.05)
    i2 = np.interp(tb, rr["t"], rr["i"] ** 2)
    i2b = np.interp(tb, rr["t"], rr["i2_bound"])
    ncy = int(1800 / CYC) + 1
    t30 = np.arange(0, ncy * CYC, 0.05)
    i30 = np.sqrt(np.tile(i2, ncy))[: len(t30)]
    i30b = np.sqrt(np.tile(i2b, ncy))[: len(t30)]
    for Tamb in (25.0, T_AMB):
        for rth2_mult in (0.5, 1.0, 1.5):
            out = thermal_run(t30, i30, MOT[label]["R_ohm"], Tamb, Rth2=TH["Rth2_K_W"] * rth2_mult)
            outb = thermal_run(t30, i30b, MOT[label]["R_ohm"], Tamb, Rth2=TH["Rth2_K_W"] * rth2_mult, scale_R=False)
            k30 = int(1800 / 0.05)
            key = "%s_amb%d_Rth2x%.1f" % (label, Tamb, rth2_mult)
            test3["thermal_30min"][key] = {"T_case_30min_C": float(out[k30, 1]), "T_winding_30min_C": float(out[k30, 0]),
                                           "mean_Pcu_W": float(out[:, 2].mean()),
                                           "R26_pass": bool(out[k30, 1] <= TH["T_case_limit_C"])}
            test3["thermal_30min_pwm_bound"][key] = {"T_case_30min_C": float(outb[k30, 1]),
                                                     "T_winding_30min_C": float(outb[k30, 0]),
                                                     "mean_Pcu_W": float(outb[:, 2].mean()),
                                                     "Pcu_ratio_to_average_model": float(outb[:, 2].mean() / out[:, 2].mean()),
                                                     "R26_pass": bool(outb[k30, 1] <= TH["T_case_limit_C"])}
            if rth2_mult == 1.0:
                ax[0].plot(t30 / 60, out[:, 1], ("b" if label == "A_mech" else "r") + ("-" if Tamb == T_AMB else "--"),
                           label="case proxy %s amb %d" % (label, Tamb))
                ax[0].plot(t30 / 60, out[:, 0], ("b" if label == "A_mech" else "r") + ("-" if Tamb == T_AMB else "--"),
                           alpha=0.3)
                if label == "A_mech" and Tamb == T_AMB:
                    th30 = (t30[::20], out[::20, 0], out[::20, 1])
                # per-cycle history: copper energy with R(T), rail energy, winding peak, case at cycle end
                spc = int(round(CYC / 0.05))
                pc = []
                for c in range(int(1800 // CYC)):
                    sl = slice(c * spc, (c + 1) * spc)
                    Ecu = float(out[sl, 2].sum() * 0.05)
                    pc.append({"cycle": c + 1, "E_cu_J": Ecu,
                               "E_rail_J": test3[label]["E_elec_J_per_cycle"] - test3[label]["E_cu_J_per_cycle"] + Ecu,
                               "T_winding_max_C": float(out[sl, 0].max()), "T_case_end_C": float(out[sl, 1][-1]),
                               "R_winding_ohm": MOT[label]["R_ohm"] * (1 + TH["alpha_Cu"] * (float(out[sl, 0].max()) - 20))})
                test3.setdefault("per_cycle_30min", {})["%s_amb%d" % (label, Tamb)] = pc
                test3.setdefault("per_cycle_30min_note", "Each row is one cycle of the 30-min thermal run: the "
                                 "cycle-1 current profile repeated with R(T) coupled into the copper loss. Peak current, "
                                 "servo and mesh torque are not recomputed per cycle (they are cycle-1 values, see "
                                 "test3_duty_cycle.<fit> and back_to_back_cycles_A_mech for time-domain cycles 1-3 and hot).")
ax[0].axhline(TH["T_case_limit_C"], color="k", ls=":", label="R26 case 60 °C")
ax[0].set_xlabel("minutes of the 35 s duty cycle")
ax[0].set_ylabel("°C (faint = winding)")
ax[0].legend(fontsize=7)
ax[0].set_title("30-minute thermal run (Rth2 = 22 K/W [A])")
ks = sorted(test3["thermal_30min"])
ax[1].barh(range(len(ks)), [test3["thermal_30min"][k]["T_case_30min_C"] for k in ks],
           color=["tab:green" if test3["thermal_30min"][k]["R26_pass"] else "tab:red" for k in ks])
ax[1].set_yticks(range(len(ks)))
ax[1].set_yticklabels(ks, fontsize=7)
ax[1].axvline(60, color="k", ls=":")
ax[1].set_xlabel("case proxy at 30 min (°C)")
ax[1].set_title("R26 sensitivity: fit, ambient, Rth2")
fig.tight_layout()
fig.savefig(FIG / "dyno_thermal_30min.png", dpi=130)
plt.close(fig)

# back-to-back time-domain cycles (Fit A): cycles 2 and 3 start from cycle 1's end state (cold winding), then
# one "hot" cycle with the winding resistance at the 30-min, 40 degC-ambient winding temperature [D]
s_bb = duty_sims["A_mech"]
bb = {"cycle_1": test3["A_mech"]}
bb_runs = {"cycle_1": duty_runs["A_mech"][0]}
for c in (2, 3):
    fwc = Firmware(t_close, t_rel, t_feed0, t_feed1, theta_c0=CAL["A_mech"])
    rr_ = s_bb.run(CYC, DT, fwc, y0=s_bb.state, rec_every=25)
    bb["cycle_%d" % c] = cyc_metrics(rr_, fwc.events)
    bb_runs["cycle_%d" % c] = rr_
Tw_hot = test3["thermal_30min"]["A_mech_amb40_Rth2x1.0"]["T_winding_30min_C"]
mA_hot = dict(mA)
mA_hot["R_ohm"] = mA["R_ohm"] * (1 + TH["alpha_Cu"] * (Tw_hot - 20))
mA_hot["T_stall_Nm"] = ETA_G * mA["K_out_NmA"] * V / mA_hot["R_ohm"]
s_hot = Sim(mA_hot)
fwc = Firmware(t_close, t_rel, t_feed0, t_feed1, theta_c0=CAL["A_mech"])
rr_ = s_hot.run(CYC, DT, fwc, y0=s_bb.state, rec_every=25)
bb["hot_after_30min"] = cyc_metrics(rr_, fwc.events)
bb["hot_after_30min"].update({"T_winding_C": Tw_hot, "R_ohm": mA_hot["R_ohm"], "T_stall_hot_Nm": mA_hot["T_stall_Nm"],
                              "hold_fraction_of_hot_stall": bb["hot_after_30min"]["T_servo_feed_mean_Nm"] / mA_hot["T_stall_Nm"]})
bb_runs["hot_after_30min"] = rr_
test3["back_to_back_cycles_A_mech"] = bb

fig, ax = plt.subplots(1, 3, figsize=(15, 4.3))
for key_, sty in (("A_mech_amb40", "b-"), ("A_mech_amb25", "b--"), ("B_elec_amb40", "r-"), ("B_elec_amb25", "r--")):
    pc = test3["per_cycle_30min"][key_]
    n_ = [p["cycle"] for p in pc]
    ax[0].plot(n_, [p["E_rail_J"] for p in pc], sty, label=key_)
    ax[1].plot(n_, [p["T_winding_max_C"] for p in pc], sty, label=key_)
    ax[1].plot(n_, [p["T_case_end_C"] for p in pc], sty, alpha=0.4)
ax[0].set_xlabel("cycle number")
ax[0].set_ylabel("rail energy per cycle (J)")
ax[0].set_title("Per-cycle energy, R(T) coupled (Rth2 22 K/W [A])")
ax[0].legend(fontsize=7)
ax[1].axhline(TH["T_case_limit_C"], color="k", ls=":")
ax[1].set_xlabel("cycle number")
ax[1].set_ylabel("°C: winding peak (dark), case at cycle end (faint)")
ax[1].set_title("Per-cycle temperatures")
labs = list(bb.keys())
xx = np.arange(len(labs))
ax[2].bar(xx - 0.2, [bb[k]["I_peak_A"] for k in labs], 0.2, label="peak motor current (A)")
ax[2].bar(xx, [bb[k]["T_mesh_peak_Nm"] * 5 for k in labs], 0.2, label="peak mesh torque x5 (N·m)")
ax[2].bar(xx + 0.2, [bb[k]["E_elec_J_per_cycle"] / 30 for k in labs], 0.2, label="rail energy / 30 (J)")
ax[2].set_xticks(xx)
ax[2].set_xticklabels(labs, fontsize=8)
ax[2].set_title("Time-domain cycles back to back (Fit A)")
ax[2].legend(fontsize=7)
fig.tight_layout()
fig.savefig(FIG / "dyno_per_cycle.png", dpi=120)
plt.close(fig)

fig, ax = plt.subplots(4, 2, figsize=(13, 10), sharex="col")
for col, (x0, x1) in enumerate(((0, CYC), (t_close - 0.1, t_close + 1.0))):
    msk = (r["t"] >= x0) & (r["t"] <= x1)
    t = r["t"][msk]
    ax[0, col].plot(t, r["theta_cmd"][msk], "k--", label="command")
    ax[0, col].plot(t, r["theta_A"][msk], "b", label="finger A")
    ax[0, col].plot(t, r["theta_B"][msk], "r", alpha=0.7, label="finger B")
    ax[0, col].set_ylabel("jaw angle (deg, + open)")
    ax[1, col].plot(t, r["F"][msk], "b", label="pad force")
    ax[1, col].plot(t, r["F_fsr"][msk], "g", alpha=0.7, label="FSR (filtered)")
    ax[1, col].plot(t, 2 * MU * r["F"][msk], "m:", label="friction capacity 2 mu F")
    ax[1, col].plot(t, r["tension"][msk], "k:", label="tension")
    ax[1, col].set_ylabel("N")
    ax[2, col].plot(t, r["T_servo"][msk], "b", label="servo output torque")
    ax[2, col].plot(t, r["T_mesh"][msk], "r", label="mesh (tooth) torque")
    ax[2, col].set_ylabel("N·m")
    ax[3, col].plot(t, r["i"][msk], "b", label="motor current")
    ax[3, col].plot(t, np.clip(r["P_elec"][msk], 0, None) / V, "c", alpha=0.6, label="rail current (PWM-averaged)")
    ax[3, col].set_ylabel("A")
    ax[3, col].set_xlabel("time (s)")
for a_ in ax[:, 0]:
    a_.legend(fontsize=7, loc="upper right")
ax[0, 0].set_title("One 35 s duty cycle (Fit A, 6.8 V)")
ax[0, 1].set_title("Close and force ramp (zoom)")
fig.tight_layout()
fig.savefig(FIG / "dyno_duty_cycle.png", dpi=120)
plt.close(fig)

# ================================================================ TEST 4: shock cases
test4 = {}
shock_series = {}
y_hold = None


def hold_then(extra_t, fw_kwargs, dt=1e-5, j=None, label=None, mot=mA):
    """Simulate close + 1.2 s settle, then the shock window. Returns recorded run and firmware."""
    s = Sim(mot, J_A_=j)
    tc = 0.05
    fwk = dict(t_close=tc, t_release=1e9, t_feed0=1.0, t_feed1=1e9)
    fwk.update(fw_kwargs)
    fwc = Firmware(**fwk)
    rr = s.run(1.3 + extra_t, dt, fwc, rec_every=10)
    return rr, fwc


# 4a cloth snag: tension 2 N -> 4 N (2x) with 5 ms rise at t = 1.4 s for 0.5 s
def snag_fn(t):
    if t < 1.4:
        return TENS
    if t < 1.405:
        return TENS * (1 + (t - 1.4) / 0.005)
    if t < 1.9:
        return 2 * TENS
    return TENS


rr, _ = hold_then(1.0, {"tension_fn": snag_fn})
w = rr["t"] > 1.35
test4["snag_2x_tension"] = {"T_mesh_peak_Nm": float(rr["T_mesh"][w].max()), "T_servo_peak_Nm": float(rr["T_servo"][w].max()),
                            "F_min_N": float(rr["F"][w].min()), "slip_fraction_during_snag": float(rr["slip"][(rr["t"] > 1.405) & (rr["t"] < 1.9)].mean()),
                            "friction_capacity_at_hold_N": float(2 * MU * rr["F"][(rr["t"] > 1.2) & (rr["t"] < 1.4)].mean())}
shock_series["snag"] = rr


# 4b arm collision on finger B's TPU tip (outer face, pushes B open) at 0.2 m/s for 10 mm then held
V_ARM = inp("v_arm_collision_m_s", 0.2, "A", "SO-101 TCP speed at impact")
D_INTR = inp("collision_intrusion_m", 0.010, "A", "arm keeps moving 10 mm before its own stop/stall")


M_ARM = inp("arm_effective_mass_kg", 0.3, "A", "SO-101 forearm + wrist + gripper effective mass at the TCP")
F_ARM = inp("arm_push_force_N", 20.0, "A", "STS3215 ~1.9 N*m stall (so101.md) over ~0.1 m wrist lever: force the arm can keep pushing")


T_RAMP = inp("arm_force_ramp_s", 0.05, "A", "arm position loop builds its push force over ~50 ms after contact")


def obs_tip(t0, r_hit, k_hit, t_push=0.3):
    """Arm carries the gripper into a fixed object: the object is modelled as a mass m_eff moving at V_ARM into
    finger B (opening direction), pushed by the saturated arm force F_ARM for t_push, then pulled back."""
    st = {"x": None, "v": V_ARM, "t": None, "y": 0.0}

    def mk(t):
        def f(tt, cB, wB):
            if tt < t0:
                return 0.0
            y = -(cB - c_ref[0]) * r_hit
            if st["t"] is None:
                st["t"], st["x"], st["y"] = tt, y, y
                return 0.0
            h = tt - st["t"]
            st["t"] = tt
            ydot = (y - st["y"]) / h if h > 0 else 0.0
            st["y"] = y
            pen = st["x"] - y
            Fc = k_hit * pen + 2 * 0.05 * math.sqrt(k_hit * M_ARM) * (st["v"] - ydot) if pen > 0 else 0.0
            Fc = Fc if Fc > 0 else 0.0
            Fd = F_ARM * min(1.0, (tt - t0) / T_RAMP) if tt < t0 + t_push else -F_ARM
            st["v"] += h * (Fd - Fc) / M_ARM
            st["x"] += h * st["v"]
            return -Fc * r_hit
        return f
    return mk


c_ref = [0.0]


def run_obs(label, r_hit, k_hit, j=None, t0=1.4):
    s = Sim(mA, J_A_=j)
    fwc = Firmware(t_close=0.05, t_release=1e9, t_feed0=1.0, t_feed1=1e9)
    # settle first to get the hold angle of B, then set the obstacle reference
    pre = s.run(1.2, 1e-5, fwc, rec_every=50)
    c_ref[0] = s.state[2]
    fwc.obs = obs_tip(t0 - 1.2, r_hit, k_hit)
    rr = s.run(1.0, 1e-5, lambda t, sm: fwc(t + 1.2, sm), y0=s.state, rec_every=10)
    rr["t"] = rr["t"] + 1.2
    return rr


k_tip_hit = 1.0 / (1.0 / K_F + 1.0 / 100e3)
rr = run_obs("tip", RC, k_tip_hit)
w = rr["t"] > 1.35
test4["collision_TPU_tip"] = {"T_mesh_peak_Nm": float(rr["T_mesh"][w].max()), "T_mesh_min_Nm": float(rr["T_mesh"][w].min()),
                              "T_servo_peak_Nm": float(np.abs(rr["T_servo"][w]).max()),
                              "obstacle_force_peak_N": float(np.abs(rr["T_obs"][w]).max() / RC),
                              "F_grip_min_N": float(rr["F"][w].min()), "F_grip_max_N": float(rr["F"][w].max()),
                              "I_peak_A": float(np.abs(rr["i"][w]).max())}
shock_series["collision_tip"] = rr

# 4c rigid hit on finger B's knuckle (PETG, r = 30 mm, 100 N/mm), J_refl sensitivity
test4["collision_rigid_knuckle"] = {}
for jl, jm in (("J_low_x0.35", 0.35), ("J_base", 1.0), ("J_high_x2.6", 2.6)):
    rr = run_obs("knuckle", 0.030, 100e3, j=J_REFL * jm + J_B)
    w = rr["t"] > 1.35
    test4["collision_rigid_knuckle"][jl] = {"J_A_kgm2": J_REFL * jm + J_B, "T_mesh_peak_Nm": float(rr["T_mesh"][w].max()),
                                           "obstacle_force_peak_N": float(np.abs(rr["T_obs"][w]).max() / 0.03),
                                           "I_peak_A": float(np.abs(rr["i"][w]).max())}
    if jl == "J_base":
        shock_series["collision_knuckle"] = rr


# 4d finger B jams on a rigid object during the fast pre-close (LC3 dynamic), both close speeds. The fast-close peak depends
# on where the impact falls relative to the 2.4 deg, 50 Hz command steps, so the jam angle is swept over one-and-a-half
# command steps (10-13.6 deg) and the servo-loop damping ZETA_S [A] over 0.5-1.0; the maximum is the design value. [D]
def jam_case(speed_dps, jm=1.0, km=None, pb=None, th_jam_deg=12.0, zeta=None, t_end=1.2):
    s = Sim(mA, J_A_=J_REFL * jm + J_B, K_MESH_=km, phi_bl=pb, zeta=zeta)
    th_jam = th_jam_deg * D2R  # B blocked th_jam open (knuckle on a seam or the table edge) [A]
    kj = 100e3 * 0.030 ** 2

    class FW2:
        def __init__(self):
            self.cmd = THETA_OPEN

        def __call__(self, t, sm):
            self.cmd = max(THETA_MIN, self.cmd - speed_dps * 0.02) if t > 0.02 else self.cmd

            def ob(tt, cB, wB):
                pen = cB - (-th_jam)
                return -(kj * pen + 2 * 0.1 * math.sqrt(kj * J_B) * wB) if pen > 0 else 0.0
            return {"theta_cmd_deg": self.cmd, "tension_N": 0.0, "obs": ob}
    rr = s.run(t_end, 1e-5, FW2(), cloth=True, rec_every=10)
    return rr


JAM_ANGLES = np.round(np.arange(10.0, 13.61, 0.3), 2)
JAM_ZETAS = (0.5, 0.8, 1.0)
test4["jam_fingerB"] = {}
test4["jam_sweep"] = {"angles_deg": JAM_ANGLES.tolist(), "zetas": list(JAM_ZETAS), "rows": {}}
for jl, jm in (("J_low_x0.35", 0.35), ("J_base", 1.0), ("J_high_x2.6", 2.6)):
    for zt in JAM_ZETAS:
        pk = [float(jam_case(FW["JAW_SPEED_FAST_DPS"], jm, th_jam_deg=float(a), zeta=zt, t_end=0.45)["T_mesh"].max())
              for a in JAM_ANGLES]
        test4["jam_sweep"]["rows"]["%s_zeta%.1f" % (jl, zt)] = pk
    allpk = [v for k, row in test4["jam_sweep"]["rows"].items() if k.startswith(jl) for v in row]
    base_row = test4["jam_sweep"]["rows"]["%s_zeta%.1f" % (jl, ZETA_S)]
    test4["jam_sweep"]["%s_max_Nm" % jl] = max(allpk)
    test4["jam_sweep"]["%s_min_Nm" % jl] = min(allpk)
    test4["jam_sweep"]["%s_max_at_zeta0.8_Nm" % jl] = max(base_row)
    test4["jam_sweep"]["%s_min_at_zeta0.8_Nm" % jl] = min(base_row)
for sp in (FW["JAW_SPEED_FAST_DPS"], FW["JAW_SPEED_NEAR_DPS"]):
    for jl, jm in (("J_low_x0.35", 0.35), ("J_base", 1.0), ("J_high_x2.6", 2.6)):
        rr = jam_case(sp, jm)
        row = {"T_mesh_peak_Nm_at_12deg": float(rr["T_mesh"].max()), "T_mesh_static_end_Nm": float(rr["T_mesh"][-200:].mean()),
               "I_peak_A": float(rr["i"].max()),
               "T_back_driven_lock_Nm": MOT["A_mech"]["T_stall_Nm"] / ETA_G ** 2}
        if sp == FW["JAW_SPEED_FAST_DPS"]:
            row["T_mesh_peak_Nm"] = test4["jam_sweep"]["%s_max_Nm" % jl]
            row["note"] = "T_mesh_peak_Nm = max over the jam-angle x zeta sweep (jam_sweep)"
        else:
            row["T_mesh_peak_Nm"] = row["T_mesh_peak_Nm_at_12deg"]
        test4["jam_fingerB"]["%ddps_%s" % (sp, jl)] = row
        if jl == "J_base" and sp == FW["JAW_SPEED_FAST_DPS"]:
            shock_series["jam"] = rr
# the mesh stiffness and backlash of the three gears.json recommendations change the fast-jam peak (angle swept, zeta 0.8) [D]
test4["jam_fingerB_by_gear"] = {}
for gk in (GEAR_BASE, GEAR_ROBUST, GEAR_CNC):
    o = GEAR_OPTS[gk]
    gm = o["named"]
    km, pb = mesh_k(o, gm), (o["jt"] / 1000) / (o["geo"]["r"] / 1000)
    pk = [float(jam_case(FW["JAW_SPEED_FAST_DPS"], 1.0, km=km, pb=pb, th_jam_deg=float(a), t_end=0.45)["T_mesh"].max())
          for a in JAM_ANGLES]
    test4["jam_fingerB_by_gear"]["%s_%s" % (gk, gm)] = {"k_mesh_Nm_rad": km, "backlash_deg": pb / D2R,
                                                         "T_mesh_peak_Nm": max(pk), "T_mesh_peak_min_Nm": min(pk)}
print("jam sweep done", round(time.time() - T0, 1), "s")

fig, ax = plt.subplots(2, 2, figsize=(12, 7))
for a_, (k, ttl) in zip(ax.flat, (("snag", "4a cloth snag, tension 2 -> 4 N"), ("collision_tip", "4b arm collision on TPU tip, 0.2 m/s"),
                                  ("collision_knuckle", "4c rigid hit on knuckle B, 0.2 m/s"), ("jam", "4d finger B jams during 120 °/s close"))):
    rr = shock_series[k]
    a_.plot(rr["t"], rr["T_mesh"], "r", label="mesh torque (N·m)")
    a_.plot(rr["t"], rr["T_servo"], "b", alpha=0.7, label="servo torque (N·m)")
    a_.plot(rr["t"], rr["F"] / 10, "g", alpha=0.7, label="pad force / 10 (N)")
    a_.axhline(MOT["A_mech"]["T_stall_Nm"], color="k", ls=":", label="servo stall (LC3)")
    a_.set_title(ttl, fontsize=10)
    a_.set_xlabel("time (s)")
    a_.legend(fontsize=7)
fig.tight_layout()
fig.savefig(FIG / "dyno_shock.png", dpi=120)
plt.close(fig)

# ================================================================ FATIGUE
from pylife.stress import rainflow as RF  # noqa: E402

N_LIFE = DC["N_design_cycles"]
SN = {}  # knuckle and TPU curves here; every gear curve is the gear lane's (GL.s_fat / GL.life / GL.sH_allow)
KF_COUPON = inp("Kf_coupon_to_notch", 1.14, "S", "printed PLA notch factor 1.12-1.16 (gears.md 2.1); applied to the coupon curves "
                 "at the knuckle arm root. The finger_beam stress already includes Kt 1.5, so the notch is counted twice: "
                 "conservative [A]")
SN["PLA"] = {"sf": 2 / 0.95 * 68.159, "b": -0.161, "cap": AL["PLA"]["tensile_xy"], "kf": KF_COUPON,
             "tag": "S Basquin sigma_a = 68.159 N^-0.161, R 0.05 (PMC12787623 via research/gears.md 2.1); sigma_max = 2 sigma_a/(1-R)"}
SN["PETG"] = {"sf": 30.6 / 1e5 ** -0.161, "b": -0.161, "cap": AL["PETG"]["tensile_xy"], "kf": KF_COUPON,
              "tag": "A PLA slope anchored at 30.6 MPa at 1e5 (DESIGN-BASIS 4)"}
tpu_pts = np.array([[3e3, 23.04], [1e5, 17.08], [3e5, 15.72], [1e6, 13.08]])
bt, at = np.polyfit(np.log10(tpu_pts[:, 0]), np.log10(tpu_pts[:, 1]), 1)
KD_TPU = inp("TPU_printed_knockdown", 0.5, "A", "printed weld lines / porosity vs moulded; 0.27 = Z/XY break ratio (6.4/23.7, Ultimaker TDS) as the pessimistic case")
SN["TPU95A"] = {"sf": 10 ** at * KD_TPU, "b": bt, "cap": AL["TPU95A"]["break_xy"], "kf": 1.0,
                "tag": "S TPU 80A HCF, R 0.1, 5 Hz (PMC9958809): 23.0@3e3, 17.1@1e5, 15.7@3e5, 13.1@1e6 MPa; D Basquin fit; x0.5 printed knockdown A"}
INF = 1e13  # the gear lane's life() ceiling


def N_basq(mat, s_eq, smax):
    c = SN[mat]
    if smax * c["kf"] >= c["cap"]:
        return 1.0
    if s_eq <= 0:
        return INF
    return min(INF, (s_eq * c["kf"] / c["sf"]) ** (1 / c["b"]))


def rainflow(sig):
    rec = RF.FullRecorder()
    det = RF.FourPointDetector(recorder=rec)
    det.process(np.asarray(sig, dtype=float))
    return np.asarray(rec.values_from), np.asarray(rec.values_to)


def miner(sig_one_cycle, Nfun, reps=3):
    """pylife FourPointDetector rainflow over `reps` repeated grips, Smith-Watson-Topper correction to the R = 0 basis
    of every curve used here (s_eq = sqrt(2 smax sa)), Palmgren-Miner sum, no endurance limit. Returns D per grip."""
    vf, vt = rainflow(np.tile(sig_one_cycle, reps))
    smax = np.maximum(vf, vt)
    sa = np.abs(vt - vf) / 2
    D = 0.0
    for mx, a_ in zip(smax, sa):
        if mx > 0 and a_ > 0:
            D += 1.0 / Nfun(math.sqrt(2 * mx * a_), mx)
    return D / reps, len(vf) / reps, float(smax.max() if len(smax) else 0.0)


def gear_fns(gk, mat):
    """Root (VDI 2736 tip load for polymers and POM, ISO 6336-3 method B for metals) and flank stress vs mesh torque,
    from gears.stresses (K_Hbeta from F_beta_y 0.03 mm, so root stress is not linear in torque)."""
    o = GEAR_OPTS[gk]
    Tg = np.concatenate([[0.0], np.geomspace(1e-4, 8.0, 240)])
    sF, sH = [0.0], [0.0]
    for T in Tg[1:]:
        st = GL.stresses(o["geo"], o["b"], float(T), mat, mat)
        sF.append(GL.sigma_root(st, mat))
        sH.append(st["sH"])
    sF, sH = np.array(sF), np.array(sH)
    return (lambda T: np.sign(T) * np.interp(np.abs(T), Tg, sF)), (lambda T: np.interp(np.abs(T), Tg, sH))


def gear_static(mat):
    return GL.MAT[mat]["S_static"] * GL.kd_static(mat)  # gear lane LC3 allowable (SF 1.0)


def life_root(mat):
    S = gear_static(mat)
    return lambda s_eq, smax: 1.0 if smax >= S else min(INF, GL.life(mat, s_eq))


def life_flank(mat):
    base = GL.sH_allow(mat)

    def f(s_eq, smax):
        if smax >= base:
            return 1.0
        if GL.sH_allow(mat, 1e13) >= s_eq:
            return INF
        lo, hi = 3.0, 13.0
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if GL.sH_allow(mat, 10 ** mid) > s_eq else (lo, mid)
        return 10 ** lo
    return f


rcyc = duty_runs["A_mech"][0]
T_mesh_cycle = rcyc["T_mesh"]
F_cycle = rcyc["F"]
sig_TPU_perN = fea["recommended"]["linear"]["tip"]["vm_max_per_N"]
sig_TPU_perN_p99 = fea["recommended"]["linear"]["tip"]["vm_p99_per_N"]
sig_KN_perN = beam["cases"]["design_L45"]["stresses_MPa"]["LC1_target_tip"]["pla"]["sigma_arm_top_Kt"] / G["F_target_N"]
INPUTS["stress_transfer"] = {"value": {"gear": "gears.stresses() per option and material (gear lane)",
                                       "TPU_hot_spot_MPa_per_N": sig_TPU_perN, "TPU_p99_MPa_per_N": sig_TPU_perN_p99,
                                       "knuckle_arm_root_MPa_per_N": sig_KN_perN},
                             "tag": "D", "note": "TPU from fea_summary.json recommended tip (max vM at a sharp rib corner = singular, and p99); "
                             "knuckle arm top from finger_beam.json design_L45 LC1 tip incl. Kt 1.5 [A]"}

# rare events over a 1e5-grip life [A counts], loads from the shock sims [D]; F_N = force at the tip pad
T_LC2 = (2 * 10.0 * RC + TENS * X_F) / ETA_X / 2 * 1.25
T_jam = test4["jam_fingerB"]["%ddps_J_base" % FW["JAW_SPEED_FAST_DPS"]]["T_mesh_peak_Nm"]
EV = {"cap_LC2": {"per_life": 1e3, "note": "DESIGN-BASIS LC2 <= 1e3 events; gear-lane LC2 torque incl. K_A 1.25", "T_mesh_Nm": T_LC2, "F_N": 10.0, "pad": True},
      "snag_2x": {"per_life": 1e3, "note": "1 per 100 grips [A]", "T_mesh_Nm": test4["snag_2x_tension"]["T_mesh_peak_Nm"], "F_N": 5.0, "pad": True},
      "stall_LC3": {"per_life": 100.0, "note": "gears.json n_LC3; quasi-static jam (20 deg/s search) = full stall through the mesh",
                    "T_mesh_Nm": T_S, "F_N": T_S * ETA_X / RC, "pad": False},
      "jam_120dps": {"per_life": 100.0, "note": "gears.json n_shock; finger B jams during the 120 deg/s pre-close", "T_mesh_Nm": T_jam,
                     "F_N": T_jam * ETA_X / RC, "pad": False},
      "collision_tip": {"per_life": 100.0, "note": "1 per 1000 grips [A]", "T_mesh_Nm": test4["collision_TPU_tip"]["T_mesh_peak_Nm"],
                        "F_N": test4["collision_TPU_tip"]["obstacle_force_peak_N"], "pad": False}}
INPUTS["rare_events"] = {"value": EV, "tag": "A", "note": "event counts over the 1e5-grip life (A); each is one 0 -> peak cycle; loads D from the shock sims. "
                         "F_N for stall/jam assumes finger B is blocked at its tip pad (A)"}

fat = {"gear": {}, "finger_TPU": {}, "knuckle": {}}
T_jam_hi = test4["jam_fingerB"]["%ddps_J_high_x2.6" % FW["JAW_SPEED_FAST_DPS"]]["T_mesh_peak_Nm"]
T_DS3235 = GJ["load_cases"]["LC3_backup_DS3235_Nm"]
for gk, o in GEAR_OPTS.items():
    for mat in GEAR_MATS:
        fF, fH = gear_fns(gk, mat)
        LR, LF = life_root(mat), life_flank(mat)
        Dr, ncount, smax_r = miner(fF(T_mesh_cycle), LR)
        Dh, _, smax_h = miner(fH(np.clip(T_mesh_cycle, 0, None)), LF)
        ev_r = {k: float(fF(e["T_mesh_Nm"])) for k, e in EV.items()}
        ev_h = {k: float(fH(max(e["T_mesh_Nm"], 0.0))) for k, e in EV.items()}
        Dr_ev = sum(EV[k]["per_life"] / LR(s, s) for k, s in ev_r.items()) / N_LIFE
        Dh_ev = sum(EV[k]["per_life"] / LF(s, s) for k, s in ev_h.items()) / N_LIFE
        S_r, S_h = gear_static(mat), GL.sH_allow(mat)
        worst_r, worst_h = max(ev_r.values()), max(ev_h.values())
        static_ok = bool(worst_r < S_r and worst_h < S_h)
        Nd = 1 / max(Dr, Dh, 1 / INF)
        Ne = 1 / max(Dr + Dr_ev, Dh + Dh_ev, 1 / INF)
        fat["gear"]["%s_%s" % (gk, mat)] = {
            "gear": gk, "material": mat, "gears_md_named_option": o["named"] == mat, "note": o["note"],
            "sigmaF_duty_peak_MPa": smax_r, "sigmaH_duty_peak_MPa": smax_h, "cycles_counted_per_grip": ncount,
            "D_root_per_grip": Dr, "D_flank_per_grip": Dh, "D_root_events_per_grip": Dr_ev, "D_flank_events_per_grip": Dh_ev,
            "grips_to_failure_duty_only": Nd, "hours_duty_only": Nd / DC["cycles_per_hour"],
            "grips_to_failure_with_events": Ne if static_ok else 1.0, "hours_with_events": (Ne if static_ok else 1.0) / DC["cycles_per_hour"],
            "governing_mode": ("static root" if worst_r >= S_r else "static flank" if worst_h >= S_h else
                               "root fatigue" if (Dr + Dr_ev) >= (Dh + Dh_ev) else "flank fatigue"),
            "sigmaF_event_MPa": ev_r, "sigmaH_event_MPa": ev_h, "root_static_allow_MPa": S_r, "flank_static_allow_MPa": S_h,
            "sigma_worst_event_MPa": worst_r, "worst_event_static_ok": static_ok,
            "root_SF_worst_event": S_r / worst_r, "flank_SF_worst_event": S_h / worst_h,
            "root_SF_jam_rotor_Jx2.6": S_r / float(fF(T_jam_hi)), "flank_SF_jam_rotor_Jx2.6": S_h / float(fH(T_jam_hi)),
            "root_SF_DS3235_stall": S_r / float(fF(T_DS3235)), "flank_SF_DS3235_stall": S_h / float(fH(T_DS3235)),
            "meets_1e5": bool(static_ok and Ne >= N_LIFE)}

# TPU finger. The linear FEA is valid only below the tip fold (fea_summary nonlinear.rec_tip last converged load, E 67,
# and its E 56 scaling). Any load above the fold is outside the linear model, and what carries it (backing, a D7 nail, the
# knuckle) is not modelled here [A]. Collisions: variant "capped" puts each tip collision at the nonlinear-FEA hot-spot
# stress at the fold (the most the TPU sees if something else takes the load above it) [A]; variant "linear, uncapped"
# applies the linear model to the full obstacle force (outside its validity). [D]
pad_ev = [e for e in EV.values() if e["pad"]]
nl_tip = fea.get("nonlinear", {}).get("rec_tip", {})
TPU_FOLD_N = float(nl_tip["last_converged_F_N"]) if nl_tip.get("last_converged_F_N") else None
_fold = nl_tip.get("at_last_converged", {}).get("cauchy_vm_and_green_lagrange_strain", {})
TPU_FOLD_SIG = {"hot_spot_max": _fold.get("vm_max"), "p99": _fold.get("vm_p99")}
TPU_FOLD_E56_N = nl_tip.get("scaled_to_E", {}).get("56", {}).get("last_converged_F_N")
for kd_label, kd in (("printed_x0.5", 1.0), ("pessimistic_x0.27", 0.27 / 0.5)):
    SN["TPU95A"]["sf"] = 10 ** at * KD_TPU * kd
    for which, per in (("hot_spot_max", sig_TPU_perN), ("p99", sig_TPU_perN_p99)):
        D, ncount, smax = miner(F_cycle * per, lambda s, m: N_basq("TPU95A", s, m))
        D_pad = sum(e["per_life"] / N_basq("TPU95A", e["F_N"] * per, e["F_N"] * per) for e in pad_ev) / N_LIFE
        ncol = EV["collision_tip"]["per_life"]
        s_cap = TPU_FOLD_SIG[which]
        s_lin = EV["collision_tip"]["F_N"] * per
        D_col_cap = ncol / N_basq("TPU95A", s_cap, s_cap) / N_LIFE
        D_col_lin = ncol / N_basq("TPU95A", s_lin, s_lin) / N_LIFE
        Nf, Nf_ev = 1 / D, 1 / (D + D_pad + D_col_cap)
        Nf_lin = 1 / (D + D_pad + D_col_lin)
        fat["finger_TPU"]["%s_%s" % (which, kd_label)] = {
            "sigma_duty_peak_MPa": smax, "D_per_grip": D, "D_pad_events_per_grip": D_pad,
            "D_collision_capped_per_grip": D_col_cap, "D_collision_linear_per_grip": D_col_lin,
            "grips_to_failure_duty_only": Nf, "grips_to_failure_with_events": Nf_ev, "hours_with_events": Nf_ev / DC["cycles_per_hour"],
            "grips_to_failure_collision_linear": Nf_lin, "meets_1e5": bool(Nf_ev >= N_LIFE),
            "strain_at_duty_peak_pct": 100 * float(F_cycle.max()) * fea["recommended"]["linear"]["tip"]["strain_max_per_N"],
            "collision_sigma_capped_at_fold_MPa": s_cap,
            "collision_sigma_linear_MPa": s_lin,
            "collision_N_linear": N_basq("TPU95A", s_lin, s_lin),
            "collision_strain_linear_pct": 100 * EV["collision_tip"]["F_N"] * fea["recommended"]["linear"]["tip"]["strain_max_per_N"],
            "validity": ("linear FEA valid below the tip fold, %.2f N at E 67 / %s N at E 56. Loads above it here: %s. "
                         "Those results assume the load above the fold is carried by structure not modelled here [A]"
                         % (TPU_FOLD_N, ("%.2f" % TPU_FOLD_E56_N) if TPU_FOLD_E56_N else "n/a",
                            ", ".join("%s %.1f N" % (k_, e_["F_N"]) for k_, e_ in list(EV.items()) + [("hold", {"F_N": G["F_target_N"]})]
                                      if e_["F_N"] > min(TPU_FOLD_N, TPU_FOLD_E56_N or TPU_FOLD_N) and (e_.get("pad", True) or k_ == "collision_tip"))
                            or "none"))}
SN["TPU95A"]["sf"] = 10 ** at * KD_TPU
for mat in ("PLA", "PETG"):
    D, ncount, smax = miner(F_cycle * sig_KN_perN, lambda s, m, mat=mat: N_basq(mat, s, m))
    ev_s = {k: e["F_N"] * sig_KN_perN for k, e in EV.items()}
    D_ev = sum(EV[k]["per_life"] / N_basq(mat, s, s) for k, s in ev_s.items()) / N_LIFE
    static_ok = bool(max(ev_s.values()) * SN[mat]["kf"] < SN[mat]["cap"])
    Nf = 1 / (D + D_ev) if static_ok else 1.0
    fat["knuckle"][mat] = {"sigma_duty_peak_MPa": smax, "D_per_grip": D, "D_rare_events_per_grip": D_ev,
                           "grips_to_failure_duty_only": 1 / D, "grips_to_failure_with_events": Nf, "hours_with_events": Nf / DC["cycles_per_hour"],
                           "sigma_event_MPa": ev_s, "static_ok": static_ok,
                           "SF_worst_event": SN[mat]["cap"] / (max(ev_s.values()) * SN[mat]["kf"])}

rank = []
for k, v in fat["gear"].items():
    rank.append(("gear " + k + (" *" if v["gears_md_named_option"] else ""), v["grips_to_failure_with_events"], v["worst_event_static_ok"], v["governing_mode"]))
for k, v in fat["finger_TPU"].items():
    rank.append(("finger TPU " + k, v["grips_to_failure_with_events"], True,
                 "fatigue; tip collisions capped at the fold stress (load above the fold carried elsewhere) [A]"))
    rank.append(("finger TPU " + k + " collision linear, uncapped", v["grips_to_failure_collision_linear"], True,
                 "fatigue; tip collisions at the linear-model stress (outside its validity)"))
for k, v in fat["knuckle"].items():
    rank.append(("knuckle arm root " + k, v["grips_to_failure_with_events"], v["static_ok"], "fatigue" if v["static_ok"] else "static"))
rank.sort(key=lambda x: x[1])
ranking = [{"component": a, "grips_to_failure": b, "hours": b / DC["cycles_per_hour"], "static_ok": c, "mode": d} for a, b, c, d in rank]
named = [x for x in ranking if x["component"].endswith("*") or not x["component"].startswith("gear ")]

# fatigue figure
fig, ax = plt.subplots(1, 3, figsize=(19, 6), gridspec_kw={"width_ratios": [1, 1, 0.8]})
Ns = np.logspace(3, 12, 80)
for mat in GEAR_MATS:
    ax[0].loglog(Ns, [GL.s_fat(mat, n) for n in Ns], color=GL.MAT[mat]["color"], label="gear root " + mat)
ax[0].loglog(Ns, np.minimum(SN["TPU95A"]["sf"] * Ns ** SN["TPU95A"]["b"], SN["TPU95A"]["cap"]), "k--", label="TPU hot spot (x0.5)")
ax[0].loglog(Ns, np.minimum(SN["PLA"]["sf"] * Ns ** SN["PLA"]["b"], SN["PLA"]["cap"]) / KF_COUPON, "k:", label="PLA knuckle (Kf 1.14)")
fF0, _ = gear_fns(GEAR_BASE, GB_MAT)
for lab, T_ in (("duty peak", T_mesh_cycle.max()), ("jam 120 °/s", T_jam), ("LC3 stall", T_S)):
    ax[0].axhline(float(fF0(T_)), ls=":", color="gray")
    ax[0].text({"duty peak": 1.3e3, "jam 120 °/s": 1e7, "LC3 stall": 1.3e3}[lab], float(fF0(T_)) * (0.9 if lab == "LC3 stall" else 1.04),
               lab + ", %s %s" % (GB_MAT, GEAR_BASE), fontsize=7)
ax[0].set_xlabel("cycles to failure")
ax[0].set_ylabel("allowable sigma_max, R = 0 (MPa), knockdowns applied")
ax[0].legend(fontsize=7, loc="lower left")
ax[0].set_title("S-N curves (gear lane + TPU + knuckle)")
vf, vt = rainflow(np.tile(fF0(T_mesh_cycle), 3))
ax[1].hist(np.abs(vt - vf), bins=40, log=True)
ax[1].set_xlabel("rainflow range, root stress, %s %s (MPa)" % (GB_MAT, GEAR_BASE))
ax[1].set_ylabel("count per 3 grips")
ax[1].set_title("Rainflow of the duty-cycle tooth-root stress")
top = named[:16]
ax[2].barh(range(len(top)), [max(1.0, x["grips_to_failure"]) for x in top],
           color=["tab:red" if (x["grips_to_failure"] < N_LIFE or not x["static_ok"]) else "tab:green" for x in top])
ax[2].set_xscale("log")
ax[2].axvline(N_LIFE, color="k", ls=":")
ax[2].set_yticks(range(len(top)))
ax[2].set_yticklabels([x["component"] for x in top], fontsize=7)
ax[2].invert_yaxis()
ax[2].set_xlabel("grips to failure, Miner incl. rare events")
ax[2].set_title("Weakest links (* = gears.json option)")
fig.tight_layout()
fig.savefig(FIG / "dyno_fatigue.png", dpi=120)
plt.close(fig)


# ================================================================ RAIL SENSITIVITY: 6.5 V and 6.35 V (torque_and_actuator.md)
# The torque note sets the rail to 6.5 +- 0.15 V (below the 6.8 V maximum rating) and checks the hold at the 6.35 V low end.
# The baseline above stays at 6.8 V: it is the gear lane's LC3 basis (2.108 N*m) and the upper bound for stall current.
# Torque and speed are interpolated linearly between the 5.0 V and 6.8 V datasheet points, taking the lower (Miuzei) 5 V
# torque 18 kg*cm [S actuators.csv A17]. No datasheet in actuators.csv gives a 5 V stall current: Miuzei gives 2.2 A and
# Annimos 1.8 A, both AT 6.8 V (A17 conflict note). So the stall current is scaled from 2.2 A @ 6.8 V with the winding
# resistance fixed, I = 2.2 x V/6.8 [D, ideal DC motor]; the Annimos 1.8 A is reported as a Fit B variant. [D from S]
def lerp(v5, v68, Vq):
    return v5 + (v68 - v5) * (Vq - 5.0) / 1.8


INPUTS["rail_sensitivity_stall_current"] = {"value": {"Miuzei_6p8V_A": 2.2, "Annimos_6p8V_A": 1.8, "scaling": "I = I_6.8 x V/6.8"},
                                            "tag": "D", "note": "actuators.csv A17 conflict note: both currents are at 6.8 V; "
                                            "no 5 V stall current is published, so no interpolation"}
rail65 = {}
for V_q, tagv in ((6.5, "6p5V"), (6.35, "6p35V")):
    inp("V_rail_sensitivity_" + tagv, V_q, "A", "torque_and_actuator.md: 6.5 +- 0.15 V adjustable buck (%s)" %
        ("nominal" if V_q == 6.5 else "low end, hold check"))
    Ts_q = lerp(18.0, 21.5, V_q) * 0.0980665
    w0_q = (60 * D2R) / lerp(0.16, 0.14, V_q)
    blk = {"inputs": {"T_stall_Nm": Ts_q, "s_per_60deg": lerp(0.16, 0.14, V_q), "I_stall_A_Miuzei_scaled": 2.2 * V_q / 6.8,
                      "I_stall_A_Annimos_scaled": 1.8 * V_q / 6.8,
                      "tag": "D: torque/speed interpolated between S points (Miuzei 18 / 21.5 kg*cm, 0.16 / 0.14 s at 5 / 6.8 V); "
                             "current scaled from S 6.8 V values with R fixed"}}
    for key, Is_q in (("A_mech", 2.2 * V_q / 6.8), ("B_elec", 2.2 * V_q / 6.8), ("B_elec_Annimos1p8A", 1.8 * V_q / 6.8)):
        mot_q = fit_motor(key if key != "B_elec_Annimos1p8A" else "B_elec", V_q, Ts_q, w0_q, Is_q)
        c0_q = calibrate(mot_q)
        s_q = Sim(mot_q)
        fw_q = Firmware(t_close, t_rel, t_feed0, t_feed1, theta_c0=c0_q)
        r_q = s_q.run(CYC, DT, fw_q, rec_every=25)
        m_q = cyc_metrics(r_q, fw_q.events)
        tb = np.arange(0, CYC, 0.05)
        ncy = int(1800 / CYC) + 1
        t30 = np.arange(0, ncy * CYC, 0.05)
        i30 = np.sqrt(np.tile(np.interp(tb, r_q["t"], r_q["i"] ** 2), ncy))[: len(t30)]
        th = {Ta: float(thermal_run(t30, i30, mot_q["R_ohm"], Ta)[int(1800 / 0.05), 1]) for Ta in (25.0, T_AMB)}
        blk[key] = {"fit": mot_q, "theta_c0_calibrated_deg": c0_q, "close_to_contact_s": m_q["close_to_contact_s"],
                    "close_to_5N_s": m_q["close_to_5N_s"], "F_hold_mean_N": m_q["F_hold_mean_N"],
                    "T_servo_feed_mean_Nm": m_q["T_servo_feed_mean_Nm"],
                    "hold_fraction_of_stall": m_q["T_servo_feed_mean_Nm"] / Ts_q,
                    "hold_fraction_of_stall_0p792Nm": 0.792 / Ts_q, "meets_40pct_rule": bool(m_q["T_servo_feed_mean_Nm"] / Ts_q <= 0.40),
                    "I_feed_mean_A": m_q["I_feed_mean_A"], "I_peak_A": m_q["I_peak_A"], "E_elec_J_per_cycle": m_q["E_elec_J_per_cycle"],
                    "T_case_30min_amb25_C": th[25.0], "T_case_30min_amb40_C": th[T_AMB], "T_mesh_peak_Nm": m_q["T_mesh_peak_Nm"]}
    blk["gear_LC3_Nm"] = Ts_q
    rail65[tagv] = blk
print("rail sensitivity done", round(time.time() - T0, 1), "s")


# ================================================================ viewer series + JSON
def ds(rr, keys, n=1500):
    idx = np.linspace(0, len(rr["t"]) - 1, min(n, len(rr["t"]))).astype(int)
    return {k: np.round(rr[k][idx], 4).tolist() for k in ["t"] + keys}


series = {"duty_cycle_A_mech": ds(rcyc, ["theta_cmd", "theta_A", "theta_B", "F", "F_fsr", "T_servo", "T_mesh", "i", "P_elec", "tension"], 1800),
          "close_zoom": ds({k: v[(rcyc["t"] > t_close - 0.1) & (rcyc["t"] < t_close + 1.0)] for k, v in rcyc.items()},
                           ["theta_cmd", "theta_A", "theta_B", "F", "F_fsr", "T_servo", "T_mesh", "i"], 600),
          "thermal_30min_A_amb40": {"t": np.round(th30[0], 1).tolist(), "T_winding": np.round(th30[1], 2).tolist(), "T_case": np.round(th30[2], 2).tolist()}}
for k, rr in shock_series.items():
    series["shock_" + k] = ds(rr, ["F", "T_servo", "T_mesh", "i", "theta_A", "theta_B"], 500)
series["hot_cycle_A_mech"] = ds(bb_runs["hot_after_30min"], ["theta_cmd", "theta_A", "F", "T_servo", "T_mesh", "i", "P_elec"], 700)
series["per_cycle_30min_A_amb40"] = {k: [round(p[k], 4) for p in test3["per_cycle_30min"]["A_mech_amb40"]]
                                     for k in ("cycle", "E_rail_J", "E_cu_J", "T_winding_max_C", "T_case_end_C")}
GEAR_EXPORT = {k: {kk: o[kk] for kk in ("m", "z", "alpha", "x", "b", "jt", "named", "role", "note")} | {
    "a_w_mm": o["geo"]["a_w"], "eps_alpha": o["geo"]["eps"], "tip_land_mm": o["geo"]["sa"], "x_f_mm": o["geo"]["x_f"]} for k, o in GEAR_OPTS.items()}
GEAR_SN = {m_: {"A": GL.MAT[m_].get("A", GL.MAT[m_].get("A_rev")), "b": GL.MAT[m_]["b"], "kd_fatigue": GL.kd_fat(m_),
                "static_allow_MPa": gear_static(m_), "flank_static_allow_MPa": GL.sH_allow(m_),
                "s_fat_1e5_MPa": GL.s_fat(m_, 1e5), "s_fat_1e7_MPa": GL.s_fat(m_, 1e7), "tag": GL.MAT[m_]["sn_tag"]} for m_ in GEAR_MATS}

out = {"_doc": "Virtual actuator dyno + fatigue for the cloth-feed gripper; script analysis/gripper/dyno.py. Tags: S sourced, D derived, A assumed.",
       "inputs": INPUTS,
       "motor_fit": {"consistency_check": consistency, "fits": MOT, "baseline": "A_mech",
                     "J_reflected_kgm2": J_REFL, "servo_PD": {"Kp_per_rad": sim.Kps, "Kd_s_per_rad": sim.Kds},
                     "mesh": {"k_Nm_per_rad": K_MESH, "backlash_rad": PHI_BL, "backlash_deg": PHI_BL / D2R, "J_B": J_B, "J_A": J_A}},
       "test1_torque_speed": test1, "test2_stall": test2, "test3_duty_cycle": test3, "test4_shock": test4,
       "rail_sensitivity": rail65,
       "fatigue": {"gear_options": GEAR_EXPORT, "gear_SN_from_gear_lane": GEAR_SN, "SN_curves_TPU_knuckle": SN,
                   "results": fat, "ranking_weakest_first": ranking, "ranking_named_options": named, "TPU_tip_fold_N": TPU_FOLD_N,
                   "life_target_grips": DC["N_design_cycles"], "cycles_per_hour": DC["cycles_per_hour"]},
       "series": series, "runtime_s": None}


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        o = float(o)
        return None if (math.isnan(o)) else (1e30 if math.isinf(o) else o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


_bad = stale_inputs(HASH0)
if _bad:
    print("REFUSED: input files changed during this run; results not written:", json.dumps(_bad))
    sys.exit(2)
out["runtime_s"] = time.time() - T0
ser = clean(out.pop("series"))
txt = json.dumps(clean(out), indent=1)
txt = txt[:-2] + ',\n "series": ' + json.dumps(ser, separators=(",", ":")) + "\n}\n"
with open(RES / "dyno.json", "w", newline="\n", encoding="utf-8") as fh:
    fh.write(txt)
print("dyno.json bytes", len(txt))
print(json.dumps(clean({"motor": MOT, "consistency": consistency, "test1": {k: {kk: vv for kk, vv in v.items() if not isinstance(vv, list)} for k, v in test1.items()},
                        "test2": test2, "test3": test3, "test4": test4, "ranking": ranking[:25],
                        "gear_all": {k: (v["grips_to_failure_with_events"], v["sigma_worst_event_MPa"], v["worst_event_static_ok"]) for k, v in fat["gear"].items()},
                        "tpu": fat["finger_TPU"], "knuckle": fat["knuckle"]}), indent=1))
print("runtime", time.time() - T0)
