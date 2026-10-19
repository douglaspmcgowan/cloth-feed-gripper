"""Camera placement study for the cloth-feed gripper (CV itself out of scope).

Evaluates wrist (eye-in-hand), fixed overhead and fixed side placements for the candidate cameras in
docs/gripper/research/cloth_and_camera.md: FOV coverage of the cloth edge and fingertips at approach and feed,
px/mm at the seam line, occlusion (ray casting against a simplified gripper from params.json, the SO-101 link
meshes via MuJoCo mj_ray, and a boxed sewing machine), depth of field, motion blur, and arm-payload impact.

Inputs : cad/gripper/params.json, cad/so101/Simulation/SO101/so101_old_calib.xml (+ STL assets),
         cad/so101/SO-ARM101_camera_wrist_mount.step (measured once; values copied into STOCK_MOUNT below).
Outputs: analysis/gripper/results/camera.json, analysis/gripper/results/camera_stdout.txt,
         docs/gripper/figures/camera_top.png, camera_side.png, camera_views.png
Run    : uv run --with mujoco --with numpy --with scipy --with matplotlib python analysis/gripper/camera.py
Frame  : MuJoCo world of so101_old_calib.xml (arm base on the table, z up, arm reaches along -y at pan 0).
Tags   : S sourced, D derived, A assumed.
"""
import io, json, math, sys
from pathlib import Path
import numpy as np
import mujoco
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
P = json.loads((ROOT / "cad/gripper/params.json").read_text())
MJCF = ROOT / "cad/so101/Simulation/SO101/so101_old_calib.xml"
OUT = ROOT / "analysis/gripper/results/camera.json"
LOG = ROOT / "analysis/gripper/results/camera_stdout.txt"
FIG = ROOT / "docs/gripper/figures"
_buf = io.StringIO()


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s); _buf.write(s + "\n")


WC, GR, PS = P["work_cell"], P["grip"], P["payload_scenarios"]
# ------------------------------------------------------------------ inputs (value, tag, note)
INPUT = {
    "bed_z_mm": (WC["bed_height_above_table_mm"], "A", "params.json work_cell"),
    "feed_speed_mm_s": (WC["feed_speed_mm_s"], "A/D", "params.json work_cell (240 st/min x 2.5 mm)"),
    "arm_speed_mm_s": (100.0, "A", "cloth_and_camera.md 3.2 arm speed while imaging"),
    "exposure_ms": (10.0, "A", "cloth_and_camera.md 3.2; indoor, no extra light"),
    "exposure_lit_ms": (2.0, "A", "with a 5-10 W LED work light on the bed"),
    "seam_allowance_mm": (15.9, "A", "5/8 in seam-guide line right of the needle (common domestic default)"),
    "presser_foot_front_mm": (12.0, "A", "foot toe ahead of the needle"),
    "release_before_foot_mm": (WC["release_before_presser_foot_mm"], "A", "params.json work_cell"),
    "needle_reach_mm": (325.0, "A", "needle at 325 mm from the pan axis along the tension line (R24: reach <= 300 at the gripper)"),
    "feed_travel_mm": (150.0, "A", "gripper travel along the feed while holding (duty cycle 20 s x 10 mm/s = 200 mm; trimmed to 150 mm so IK holds 45 deg tilt inside the reach window; longer seams re-grip)"),
    "tilt_deg": (45.0, "A", "gripper within 45 deg of straight down (params.json work_cell.gripper_tilt_max_deg); nail finger lower"),
    "pad_above_bed_mm": (4.0, "A", "cloth lifted 4 mm into the pinch so the tip clears the bed"),
    "approach_backoff_mm": (15.0, "A", "approach pose: jaw open +20 deg, 15 mm back along the finger axis"),
    "px_per_mm_req": (5.0, "A", "edge located to +-0.5 mm with >= 2.5 px per 0.5 mm band (brief)"),
    "px_per_mm_min": (3.0, "A", "cloth_and_camera.md +-1 mm target"),
    "coc_px": (2.0, "A", "circle of confusion = 2 output pixels"),
    "critical_len_mm": (40.0, "A", "edge segment just ahead of the presser foot = next 4 s of seam at 10 mm/s"),
    "cable_g_per_m": (18.0, "A", "thin USB 2.0 cable (28/28 AWG) ~ 15-20 g/m"),
    "cable_carried_m": (0.20, "A", "cable length whose weight hangs on the gripper before the first tie-down on the lower arm"),
    "petg_density": (1.25, "S", "params.json materials.allowables.PETG"),
    "mount_fill": (0.55, "A", "40 % infill + walls, effective solid fraction (upstream README prints the adapter at 40 %)"),
    "shoulder_lever_H_mm": (PS["lever_shoulder_lift_to_H_mm"], "D", "params.json payload_scenarios"),
    "mass_moment_now_gmm": (PS["new_gripper_estimate"]["mass_moment_gmm"], "D", "params.json payload_scenarios (DESIGN-BASIS R10)"),
    "mass_moment_budget_gmm": (PS["scenarios"]["C001_7p4V"]["mass_moment_budget_gmm"], "D", "C001 7.4 V design point"),
}
V = {k: v[0] for k, v in INPUT.items()}

# Measured from cad/so101/SO-ARM101_camera_wrist_mount.step with cadquery (face/cylinder dump, this lane, 2026-09-22)
STOCK_MOUNT = {"flange_holes": "2x dia 3.3 (M3 clearance), centres 8.1 mm apart, dia 5.4 x 2 counterbores, 4 mm flange",
               "flange_face_mm": [35.0, 21.0], "camera_holes": "4x dia 2.0 (M2) on a 27.0 mm square",
               "camera_plate_tilt_deg": 24.8, "volume_cm3": 10.85, "tag": "D (STEP measurement)"}

# ------------------------------------------------------------------ cameras
# diag FOV, aspect, output px (w,h), full-sensor width px, pixel pitch um, f-number, focal mm (None = derive), mass g, price.
# Cameras with a sourced focal length and sourced H/V FOV (Pi Camera 3, 3 Wide): fx = f / effective pitch [D from S], and the
# frame is the intersection of the pinhole pixel frame and the sourced H/V FOV.  The others have only a diagonal FOV:
# HFOV/VFOV from the diagonal and aspect, f from the sensor width [D].
# body: board extent along c (image vertical) and along n (image horizontal) in mm, lens centre distance from the board edge
# that faces the housing (-n), depth behind the lens front (board + lens stack), camera hole pattern.
RPI_DOC = "https://www.raspberrypi.com/documentation/accessories/camera.html"
RPI_CM2_DWG = "https://datasheets.raspberrypi.com/camera/camera-module-2-mechanical-drawing.pdf"
PI_BODY = dict(board_c=25.0, board_n=23.862, lens_from_low_edge=9.462,
               holes="4x dia 2.2 (M2) on 21.0 x 12.5 mm centres, 2.0 mm in from the edges, board 25 x 23.86 mm",
               body_tag="S Camera Module 2 mechanical drawing (%s); RPi docs: CM3 board and holes identical to CM2 (%s)" % (RPI_CM2_DWG, RPI_DOC))
CAMS = {
    "PiCam3": dict(diag=75, ar=(16, 9), out=(2304, 1296), fps=56, sensor_w=4608, pitch=1.4, N=1.8, f=4.74, mass=4.0, usd=25.0,
                   hfov_src=66.0, vfov_src=41.0, depth=11.5, **PI_BODY,
                   af=True, shutter="rolling", tag="S %s (H 66 x V 41 deg, 75 diag, f 4.74 mm, F1.8, 1.4 um, 4608 x 2592, 25 x 24 x 11.5 mm, 4 g); 2304x1296p56 binned mode" % RPI_DOC),
    "PiCam3_wide": dict(diag=120, ar=(16, 9), out=(2304, 1296), fps=56, sensor_w=4608, pitch=1.4, N=2.2, f=2.75, mass=4.0, usd=35.0,
                        hfov_src=102.0, vfov_src=67.0, depth=12.4, **PI_BODY,
                        af=True, shutter="rolling", tag="S %s (H 102 x V 67 deg, 120 diag, f 2.75 mm, F2.2, 25 x 24 x 12.4 mm, 4 g)" % RPI_DOC),
    "ESP32CAM_OV2640": dict(diag=66, ar=(4, 3), out=(1600, 1200), fps=15, sensor_w=1600, pitch=2.2, N=2.0, f=None, mass=8.0, usd=7.0,
                            board_c=40.5, board_n=27.0, lens_from_low_edge=13.5, depth=10.0, holes="no mounting holes; clip or 2x M2 printed clamp",
                            body_tag="S 40.5 x 27 x 4.5 mm board (Handsontec); lens position and depth A",
                            af=False, shutter="rolling", tag="S makeradvisor/handsontec (66 deg, UXGA 15 fps, 8 g); pitch/F A"),
    "UVC32_1080p": dict(diag=90, ar=(16, 9), out=(1920, 1080), fps=30, sensor_w=1920, pitch=3.0, N=2.0, f=None, mass=10.0, usd=25.0,
                        board_c=32.0, board_n=32.0, lens_from_low_edge=16.0, depth=15.0,
                        holes="4x M2 on a 27.0 mm square (D, measured from the upstream 32x32 wrist-mount STEP)",
                        body_tag="S 32 x 32 board (SO-101 README); lens centred and 15 mm depth A",
                        af=False, shutter="rolling", tag="S SO-101 README (32x32 board, >= 720p30, manual focus); FOV/res/pitch/mass A (listing not retrievable)"),
    "OV9281_GS": dict(diag=70, ar=(16, 10), out=(1280, 800), fps=120, sensor_w=1280, pitch=3.0, N=2.0, f=None, mass=5.0, usd=25.99,
                      board_c=38.0, board_n=38.0, lens_from_low_edge=19.0, depth=20.0, holes="per module; not specified here",
                      body_tag="A 38 x 38 UVC-class board, lens centred (not verified)",
                      af=False, shutter="global", tag="S arducam.com OV9281 (1 MP mono global shutter, $25.99); lens FOV/F/mass A"),
    "C270": dict(diag=55, ar=(16, 9), out=(1280, 720), fps=30, sensor_w=1280, pitch=2.8, N=2.4, f=None, mass=75.0, usd=29.99,
                 board_c=72.0, board_n=31.0, lens_from_low_edge=15.5, depth=28.0, holes="clip housing", body_tag="A housing envelope",
                 af=False, shutter="rolling", tag="S logitech.com/Tom's Guide (720p30, 55 deg, 75 g); pitch/F A"),
}
for c in CAMS.values():
    a, b = c["ar"]
    c["pitch_eff_um"] = c["pitch"] * c["sensor_w"] / c["out"][0]
    w2, h2 = c["out"][0] / 2, c["out"][1] / 2
    if c.get("hfov_src"):  # sourced f and H/V FOV
        c["fx"] = c["f"] / (c["pitch_eff_um"] * 1e-3)
        c["tan_h"] = min(w2 / c["fx"], math.tan(math.radians(c["hfov_src"] / 2)))
        c["tan_v"] = min(h2 / c["fx"], math.tan(math.radians(c["vfov_src"] / 2)))
        c["fov_tag"] = "S (H/V FOV sourced); fx = f / effective pitch [D]; frame = pixel frame clipped to the sourced FOV"
    else:  # diagonal only
        k = a / math.hypot(a, b)
        hf = 2 * math.degrees(math.atan(math.tan(math.radians(c["diag"] / 2)) * k))
        c["fx"] = w2 / math.tan(math.radians(hf / 2))
        c["f"] = (c["sensor_w"] * c["pitch"] * 1e-3 / 2) / math.tan(math.radians(hf / 2))
        c["tan_h"], c["tan_v"] = w2 / c["fx"], h2 / c["fx"]
        c["fov_tag"] = "D from the diagonal FOV and aspect (pinhole); f from the sensor width"
    c["hfov"] = 2 * math.degrees(math.atan(c["tan_h"]))
    c["vfov"] = 2 * math.degrees(math.atan(c["tan_v"]))

# ------------------------------------------------------------------ geometry helpers (all mm internally)
def box(lo, hi):
    return np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], float)


def poly(verts):
    v = np.asarray(verts, float)
    h = ConvexHull(v)
    return {"v": v, "eq": h.equations}  # n.x + d <= 0 inside


def ray_hits(p0, p1, solids, tmax=1.0):
    """True if the segment p0->p1 (t in (1e-6, tmax)) enters any convex solid (Cyrus-Beck)."""
    dv = p1 - p0
    for s in solids:
        n, d = s["eq"][:, :3], s["eq"][:, 3]
        num = -(n @ p0 + d)
        den = n @ dv
        t0, t1, ok = 1e-6, tmax, True
        for a, b in zip(num, den):
            if abs(b) < 1e-12:
                if a < 0:
                    ok = False; break
            elif b < 0:
                t0 = max(t0, a / b)
            else:
                t1 = min(t1, a / b)
            if t0 > t1:
                ok = False; break
        if ok:
            return True
    return False


# ------------------------------------------------------------------ sewing machine (A, reference Singer 4423 envelope [S])
# local machine frame: a = operator's right (toward the tower), b = along the feed from the needle, z up from the table
MACH_LOCAL = {
    "base_bed": ((-90, -80, 0), (304, 79, V["bed_z_mm"])),
    "upper_arm": ((-60, -45, 220), (304, 45, 305)),
    "head": ((-70, -50, 165), (40, 50, 305)),
    "tower": ((159, -60, V["bed_z_mm"]), (304, 60, 305)),
    "needle_presser_bar": ((-6, -4, V["bed_z_mm"] + 7), (6, 8, 165)),
    "presser_foot": ((-8, -V["presser_foot_front_mm"], V["bed_z_mm"] + 0.3), (10, 14, V["bed_z_mm"] + 6)),
}

# ------------------------------------------------------------------ arm model
m = mujoco.MjModel.from_xml_path(str(MJCF))
d = mujoco.MjData(m)
JN = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
jid = {n: m.joint(n).id for n in JN}
qadr = {n: m.jnt_qposadr[jid[n]] for n in JN}
bg = m.body("gripper").id
for g in range(m.ngeom):  # the new gripper replaces the stock wrist-roll follower + jaw: drop them from ray casts
    if m.geom_bodyid[g] in (bg, m.body("moving_jaw_so101_v1").id):
        m.geom_group[g] = 5
GEOMGROUP = np.array([0, 0, 1, 0, 0, 0], np.uint8)  # visual meshes of base..wrist only
mujoco.mj_forward(m, d)
PAN = d.xanchor[jid["shoulder_pan"]].copy() * 1000
FEED = np.array([0.0, -1.0, 0.0])            # cloth moves away from the arm along -y
RIGHT = np.array([-1.0, 0.0, 0.0])           # operator's right when facing the feed (= FEED x z)
NEEDLE = np.array([PAN[0], PAN[1] - V["needle_reach_mm"], V["bed_z_mm"]])


def mach_to_world(a, b, z):
    return np.array([NEEDLE[0] + a * RIGHT[0] + b * FEED[0], NEEDLE[1] + a * RIGHT[1] + b * FEED[1], z])


MACH = {}
for k, (lo, hi) in MACH_LOCAL.items():
    MACH[k] = poly(np.array([mach_to_world(*c) for c in box(lo, hi)]))

# ------------------------------------------------------------------ simplified gripper, local (c, u, n) mm
# c = jaw closing axis (finger B side +), u = roll axis toward the tips (= -z of the MuJoCo gripper body),
# n = gear-axis / finger-depth direction (front plate +, servo body -). DS3218MG 40 x 20 x 40.5 [S], m1.5 z20 a = 30 [D],
# H->pivot 40.7 [D], root 25 + finger 45 [D], pad x_f 14.5 [D], depth 20 at zc = 4 [D], housing half-width 34 [D].
A_HALF, U_PIV, U_ROOT, U_TIP = 15.0, 40.7, 65.7, 110.7
PAD_U = U_TIP - GR["pad_centroid_from_tip_mm"]
N_LO, N_HI = -6.0, 14.0


def gripper_solids_local(theta_deg):
    sol = {"deck_hub": box((-34, 0, -45.5), (34, 5, 10.5)),
           "servo_cradle": box((-27.5, 5, -45.5), (-2.5, 53, -2.5)),
           "plates_gears": box((-34, 5, -2.5), (34, 58, 10.5))}
    for side, sgn in (("A", -1), ("B", 1)):
        piv = np.array([sgn * A_HALF, U_PIV])
        knuck = [(sgn * 18, 50), (sgn * 0.5, 50), (sgn * 18, U_ROOT), (sgn * 0.5, U_ROOT)]
        fin = [(sgn * 0.5, U_ROOT), (sgn * 16.5, U_ROOT), (sgn * 0.5, U_TIP)]
        ang = math.radians(theta_deg) * (1 if sgn > 0 else -1)   # opening swings each tip outward
        R = np.array([[math.cos(ang), math.sin(ang)], [-math.sin(ang), math.cos(ang)]])
        for nm, pts in (("knuckle", knuck), ("finger", fin)):
            q = [piv + R @ (np.array(p) - piv) for p in pts]
            sol[f"{nm}_{side}"] = np.array([[x, y, n] for x, y in q for n in (N_LO, N_HI)])
    return sol


def tip_local(theta_deg, side):
    sgn = -1 if side == "A" else 1
    piv = np.array([sgn * A_HALF, U_PIV])
    ang = math.radians(theta_deg) * (1 if sgn > 0 else -1)
    R = np.array([[math.cos(ang), math.sin(ang)], [-math.sin(ang), math.cos(ang)]])
    x, y = piv + R @ (np.array([sgn * 0.5, U_TIP + 2.0]) - piv)  # 2 mm past the apex: visible iff the tip is seen
    return np.array([x, y, 4.0])


# check the sign convention: +20 deg must open the tips outward
assert abs(tip_local(20, "A")[0]) > 5 and abs(tip_local(20, "B")[0]) > 5


def set_q(q):
    d.qpos[:] = 0
    for n, v in zip(JN, q):
        d.qpos[qadr[n]] = v
    mujoco.mj_kinematics(m, d)


def grip_frame():
    """World origin (mm) and unit axes c, u, n of the local gripper frame for the current pose."""
    Rb = d.xmat[bg].reshape(3, 3).copy()   # copy: a view of d.xmat would change under later kinematics calls
    o = d.xpos[bg] * 1000
    u = -Rb[:, 2]
    c = Rb[:, 0]
    n = np.cross(u, c)
    n *= NSIGN
    return o, c, u, n


NSIGN = 1.0


def L2W(pts, fr):
    o, c, u, n = fr
    pts = np.atleast_2d(pts)
    return o + pts[:, :1] * c + pts[:, 1:2] * u + pts[:, 2:3] * n


def ik(target_pad, tilt_deg, q0):
    t = math.radians(tilt_deg)
    u_des = np.array([0, -math.sin(t), -math.cos(t)])
    c_des = np.array([0, -math.cos(t), math.sin(t)])  # finger B forward-up, nail finger A back-down
    lo = [m.jnt_range[jid[n]][0] for n in JN]; hi = [m.jnt_range[jid[n]][1] for n in JN]

    def res(q):
        set_q(q)
        o, c, u, n = grip_frame()
        p = o + PAD_U * u
        return np.concatenate([(p - target_pad), 60 * (u - u_des), 60 * (c - c_des)])

    r = least_squares(res, q0, bounds=(lo, hi), xtol=1e-10, ftol=1e-10)
    set_q(r.x)
    o, c, u, n = grip_frame()
    p = o + PAD_U * u
    return r.x, float(np.linalg.norm(p - target_pad)), float(math.degrees(math.acos(np.clip(-u[2], -1, 1))))


# ------------------------------------------------------------------ poses along the feed trajectory
pad_z = V["bed_z_mm"] + V["pad_above_bed_mm"]
edge_x = NEEDLE[0] + V["seam_allowance_mm"] * RIGHT[0]
b_release = -V["presser_foot_front_mm"] - V["release_before_foot_mm"] - GR["pad_centroid_from_tip_mm"]
b_start = b_release - V["feed_travel_mm"]
q0 = np.array([0.0, -1.2, 1.2, 0.9, 0.0])
POSES = []
# grid seed for the first IK
best = None
for sl in np.linspace(-3.0, 0.1, 14):
    for el in np.linspace(-0.1, 3.0, 14):
        for wf in np.linspace(-1.6, 1.6, 9):
            for rl in (-1.57, 0.0, 1.57):
                qq = np.array([0, sl, el, wf, rl])
                set_q(qq)
                o, c, u, n = grip_frame()
                tgt = mach_to_world(0, b_start, pad_z)
                e = np.linalg.norm(o + PAD_U * u - tgt) + 40 * np.linalg.norm(u - np.array([0, -.707, -.707])) + 40 * np.linalg.norm(c - np.array([0, -.707, .707]))
                if best is None or e < best[0]:
                    best = (e, qq)
q_prev = best[1]
samples = [("approach", b_start, 20.0, V["approach_backoff_mm"])]
for i, b in enumerate(np.linspace(b_start, b_release, 7)):
    samples.append((f"feed{i}", b, 0.0, 0.0))
for name, b, th, back in samples:
    tgt = mach_to_world(0, b, pad_z)
    q, err, tilt = ik(tgt, V["tilt_deg"], q_prev)
    if back:
        o, c, u, n = grip_frame()
        q, err2, tilt = ik(tgt - back * u, V["tilt_deg"], q)
    q_prev = q
    POSES.append({"name": name, "b": float(b), "theta": th, "q": q.tolist(), "ik_err_mm": err, "tilt_deg": tilt})
# decide handedness so +n (front plate) faces the seam edge (operator's right); a mirror of the CAD, reversible
set_q(np.array(POSES[1]["q"])); _, c_, u_, n_ = grip_frame()
NSIGN = 1.0 if n_ @ RIGHT > 0 else -1.0

# ------------------------------------------------------------------ targets
def targets(pose):
    set_q(np.array(pose["q"])); fr = grip_frame()
    tipA, tipB = L2W(tip_local(pose["theta"], "A"), fr)[0], L2W(tip_local(pose["theta"], "B"), fr)[0]
    b_tip = pose["b"] + GR["pad_centroid_from_tip_mm"]
    if pose["name"] == "approach":
        bs = np.linspace(pose["b"] - 20, pose["b"] + 40, 13)
    else:
        bs = np.linspace(b_tip + 5, -V["presser_foot_front_mm"], 24)
    edge = np.array([mach_to_world(V["seam_allowance_mm"], b, V["bed_z_mm"] + 0.3) for b in bs])
    crit = bs >= -V["presser_foot_front_mm"] - V["critical_len_mm"] - 1e-9
    foot = mach_to_world(0, -V["presser_foot_front_mm"] - 1, V["bed_z_mm"] + 3)
    return {"edge": edge, "edge_b": bs, "crit": crit, "tips": np.array([tipA, tipB]), "foot": foot, "fr": fr}


# ------------------------------------------------------------------ placements
def look(pos, aim, up_hint):
    z = aim - pos; z /= np.linalg.norm(z)
    x = np.cross(z, up_hint);
    if np.linalg.norm(x) < 1e-6:
        x = np.cross(z, np.array([1.0, 0, 0]))
    x /= np.linalg.norm(x); y = np.cross(z, x)
    return np.array([x, y, z])  # rows: cam x (right), y (down), z (optical axis)


WRIST = []
# front-plate (+n) lens heights: n = 24 (first pass; the board clashes with its own flange), 28.5 (Pi Camera 3 board + 1.5 mm
# plate rim clears the flange top at n = 16.5 by ~1 mm, lens 9.46 mm from the low edge), 35 (32 x 32 UVC clears it)
EDGE_N = (24.0, 28.5, 35.0)
FAMILIES = [("top", "", lambda u: (40, u, 4), lambda ua: (0, ua, 4)),
            ("servo", "", lambda u: (-15, u, -52), lambda ua: (0, ua, 4)),
            ("bottom", "", lambda u: (-40, u, 4), lambda ua: (0, ua, 4))]
for nn in EDGE_N:
    FAMILIES.insert(0, ("edge", f"_n{nn:g}".replace(".", "p"), (lambda nn: lambda u: (0, u, nn))(nn), lambda ua: (0, ua, 14)))
for side, tag_, pos_f, aim_f in FAMILIES:
    for u0 in (10.0, 30.0):
        for ua in (125.0, 160.0):
            p, a = np.array(pos_f(u0), float), np.array(aim_f(ua), float)
            v = a - p
            tilt = math.degrees(math.acos(v[1] / np.linalg.norm(v)))
            WRIST.append({"id": f"W_{side}{tag_}_u{int(u0)}_aim{int(ua)}", "kind": "wrist", "p_loc": p, "aim_loc": a, "tilt_from_roll_axis_deg": tilt})

FIXED = []
crit_mid = mach_to_world(V["seam_allowance_mm"], -V["presser_foot_front_mm"] - 60, V["bed_z_mm"])
path_mid = mach_to_world(V["seam_allowance_mm"], (b_start + -V["presser_foot_front_mm"]) / 2, V["bed_z_mm"])
for hz in (250.0, 350.0, 500.0):
    for off in (0.0, 60.0, 120.0):
        for aim_nm, aim in (("crit", crit_mid), ("path", path_mid)):
            pos = mach_to_world(V["seam_allowance_mm"] + off, float((aim - NEEDLE) @ FEED), V["bed_z_mm"] + hz)
            FIXED.append({"id": f"O_h{int(hz)}_r{int(off)}_{aim_nm}", "kind": "overhead", "pos": pos, "aim": aim, "up": RIGHT})
for hz in (200.0, 225.0, 250.0, 275.0, 300.0):   # local refinement around O_h250_r120_path
    for off in (90.0, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0):
        if hz == 250.0 and off == 120.0:
            continue
        pos = mach_to_world(V["seam_allowance_mm"] + off, float((path_mid - NEEDLE) @ FEED), V["bed_z_mm"] + hz)
        FIXED.append({"id": f"O_h{int(hz)}_r{int(off)}_path", "kind": "overhead", "pos": pos, "aim": path_mid, "up": RIGHT, "fine": True})
foot_aim = mach_to_world(V["seam_allowance_mm"], -V["presser_foot_front_mm"] - 20, V["bed_z_mm"])
for a_, b_, hz, nm in ((110, -40, 40, "throat_low"), (110, -40, 80, "throat_high"), (140, -90, 60, "throat_front"),
                       (-130, -40, 50, "left_low"), (60, -160, 70, "front_right")):
    FIXED.append({"id": f"S_{nm}", "kind": "side", "pos": mach_to_world(a_, b_, V["bed_z_mm"] + hz), "aim": foot_aim, "up": np.array([0, 0, 1.0])})

# ------------------------------------------------------------------ evaluation
def cam_pose(pl, tg):
    if pl["kind"] == "wrist":
        fr = tg["fr"]
        pos = L2W(pl["p_loc"], fr)[0]; aim = L2W(pl["aim_loc"], fr)[0]
        return pos, look(pos, aim, fr[1])  # image up = +c (finger B, world-up side)
    return pl["pos"], look(pl["pos"], pl["aim"], pl["up"])


def project(R, pos, pts, cam):
    pc = (np.atleast_2d(pts) - pos) @ R.T
    z = pc[:, 2]
    uu = cam["fx"] * pc[:, 0] / np.maximum(z, 1e-9) + cam["out"][0] / 2
    vv = cam["fx"] * pc[:, 1] / np.maximum(z, 1e-9) + cam["out"][1] / 2
    zz = np.maximum(z, 1e-9)
    inside = (z > 5) & (np.abs(pc[:, 0] / zz) <= cam["tan_h"]) & (np.abs(pc[:, 1] / zz) <= cam["tan_v"])
    return np.stack([uu, vv], 1), z, inside


def occluded(pos, pt, solids):
    dist = np.linalg.norm(pt - pos)
    tmax = max(0.0, 1 - 1.5 / dist)
    hits = []
    if ray_hits(pos, pt, solids[:len(MACH)], tmax):
        hits.append("machine")
    if ray_hits(pos, pt, solids[len(MACH):], tmax):
        hits.append("gripper")
    gid = np.array([-1], np.int32)
    r = mujoco.mj_ray(m, d, pos / 1000, (pt - pos) / 1000, GEOMGROUP, 1, -1, gid)
    if 0 <= r < tmax:
        hits.append("arm")
    return "+".join(hits) if hits else None


def to_mach(p):
    q = np.atleast_2d(p) - NEEDLE
    return np.stack([q @ RIGHT, q @ FEED, q[:, 2] + NEEDLE[2]], 1)


def head_ray_clear(pos, pts, ns=120):
    """Smallest distance (mm) from the sight lines pos -> pts to the machine head box (machine-local AABB)."""
    lo, hi = np.array(MACH_LOCAL["head"][0], float), np.array(MACH_LOCAL["head"][1], float)
    best = np.inf
    for pt in np.atleast_2d(pts):
        seg = to_mach(pos[None] + np.linspace(0, 1, ns)[:, None] * (pt - pos)[None])
        dd = np.linalg.norm(np.maximum(0, np.maximum(lo - seg, seg - hi)), axis=1)
        best = min(best, float(dd.min()))
    return best


def solids_for(pose, tg, exclude_self=False):
    sol = [MACH[k] for k in MACH]
    for k, v in gripper_solids_local(pose["theta"]).items():
        sol.append(poly(L2W(v, tg["fr"])))
    return sol


def evaluate(pl):
    rows = []
    geo = []
    for pose in POSES:
        tg = targets(pose)
        set_q(np.array(pose["q"]))
        pos, R = cam_pose(pl, tg)
        sol = solids_for(pose, tg)
        # fingertip targets: 2 mm past each apex, on the finger face that looks toward the camera
        o_, c_, u_, n_ = tg["fr"]
        nt = N_HI + 0.5 if float((pos - o_) @ n_) > 4 else N_LO - 0.5
        tg["tips"] = np.array([L2W(tip_local(pose["theta"], sd) * np.array([1, 1, 0]) + np.array([0, 0, nt]), tg["fr"])[0] for sd in ("A", "B")])
        # the camera must not sit inside a solid (e.g. machine) -- reject
        inside_solid = any(np.all(s["eq"][:, :3] @ pos + s["eq"][:, 3] < 0) for s in sol)
        pts = np.vstack([tg["edge"], tg["tips"], tg["foot"][None]])
        occ = [occluded(pos, p, sol) for p in pts]
        if pl["kind"] != "wrist" and pose["name"] != "approach":
            pose_head = head_ray_clear(pos, tg["edge"][tg["crit"]])
        else:
            pose_head = np.nan
        tg["head_clear"] = pose_head
        geo.append((pose, tg, pos, R, pts, occ, inside_solid))
    for cname, cam in CAMS.items():
        per = []
        for pose, tg, pos, R, pts, occ, inside_solid in geo:
            uv, z, ins = project(R, pos, pts, cam)
            ne = len(tg["edge"])
            vis = ins & np.array([o is None for o in occ]) & (not inside_solid)
            # px/mm across the edge (direction RIGHT, in the bed plane)
            p2, _, _ = project(R, pos, tg["edge"] + RIGHT, cam)
            ppm = np.linalg.norm(p2 - uv[:ne], axis=1)
            ev, cr = vis[:ne], tg["crit"]
            ppm_vis = ppm[ev]
            ppm_crit = ppm[ev & cr]
            # DoF set: the targets that must be sharp in this state (critical edge + tips at feed; edge + tips at approach)
            need = vis.copy()
            if pose["name"] != "approach":
                need[:ne] &= cr
            need[-1] = False
            zs = z[need] if need.any() else np.array([np.nan])
            zall = z[vis] if vis.any() else np.array([np.nan])
            # depth of field at the best focus for the visible targets
            f, N, c = cam["f"], cam["N"], V["coc_px"] * cam["pitch_eff_um"] * 1e-3
            Hf = f * f / (N * c) + f
            dn, df = float(np.nanmin(zs)), float(np.nanmax(zs))
            if cam["af"] or True:
                s = 2 * dn * df / (dn + df) if np.isfinite(dn) else np.nan
            near = s * (Hf - f) / (Hf + s - 2 * f) if np.isfinite(s) else np.nan
            far = s * (Hf - f) / (Hf - s) if (np.isfinite(s) and s < Hf) else float("inf")
            dof_ok = bool(np.isfinite(dn) and near <= dn * 1.0001 and far >= df * 0.9999)
            sa = 2 * np.nanmin(zall) * np.nanmax(zall) / (np.nanmin(zall) + np.nanmax(zall)) if vis.any() else np.nan
            dof_all_ok = bool(vis.any() and sa * (Hf - f) / (Hf + sa - 2 * f) <= np.nanmin(zall) * 1.0001 and (sa >= Hf or sa * (Hf - f) / (Hf - sa) >= np.nanmax(zall) * 0.9999))
            per.append({"pose": pose["name"], "edge_in_fov": float(ins[:ne].mean()), "edge_visible": float(ev.mean()),
                        "crit_visible": float(ev[cr].mean()) if cr.any() else None,
                        "tips_visible": int(vis[ne:ne + 2].sum()), "foot_visible": bool(vis[-1]),
                        "occluders": sorted({x for o, i in zip(occ, ins) if o and i for x in o.split("+")}),
                        "ppm_crit_min": float(ppm_crit.min()) if ppm_crit.size else 0.0,
                        "ppm_vis_min": float(ppm_vis.min()) if ppm_vis.size else 0.0,
                        "ppm_vis_max": float(ppm_vis.max()) if ppm_vis.size else 0.0,
                        "range_mm": [dn, df], "focus_mm": s, "dof_mm": [near, far], "dof_ok": dof_ok, "hyperfocal_mm": Hf,
                        "dof_all_visible_ok": dof_all_ok,
                        "cam_inside_solid": inside_solid, "head_ray_clear_mm": tg["head_clear"]})
        # motion blur
        blur = {}
        t_exp = V["exposure_ms"] / 1000
        feed_rows = [r for r in per if r["pose"].startswith("feed")]
        if pl["kind"] == "wrist":
            # relative motion of the fixed foot point between successive feed poses, scaled to the feed speed
            vpx = []
            for (p0, tg0, pos0, R0, *_), (p1, tg1, pos1, R1, *_) in zip(geo[1:-1], geo[2:]):
                a0, z0, i0 = project(R0, pos0, tg0["foot"][None], cam); a1, z1, i1 = project(R1, pos1, tg1["foot"][None], cam)
                db = abs(p1["b"] - p0["b"])
                vpx.append(float(np.linalg.norm(a1 - a0)) / db * V["feed_speed_mm_s"])
            blur["feed_px"] = max(vpx) * t_exp
            blur["approach_px"] = max(r["ppm_vis_max"] for r in per) * V["arm_speed_mm_s"] * t_exp
        else:
            blur["feed_px"] = max((r["ppm_vis_max"] for r in feed_rows), default=0) * V["feed_speed_mm_s"] * t_exp
            blur["approach_px"] = max((r["ppm_vis_max"] for r in per), default=0) * V["arm_speed_mm_s"] * t_exp
        blur["approach_px_lit"] = blur["approach_px"] * V["exposure_lit_ms"] / V["exposure_ms"]
        rows.append((cname, per, blur))
    return rows, geo


def summarise(pl, cname, per, blur):
    app = per[0]; feed = [r for r in per if r["pose"].startswith("feed")]
    crit = [r["crit_visible"] for r in feed if r["crit_visible"] is not None]
    s = {"placement": pl["id"], "kind": pl["kind"], "camera": cname,
         "approach_edge_visible": app["edge_visible"], "approach_tips_visible": app["tips_visible"],
         "feed_edge_visible_mean": float(np.mean([r["edge_visible"] for r in feed])),
         "feed_crit_visible_min": float(min(crit)) if crit else 0.0,
         "feed_tips_visible_min": int(min(r["tips_visible"] for r in feed)),
         "feed_foot_visible_frac": float(np.mean([r["foot_visible"] for r in feed])),
         "ppm_crit_min": float(min(r["ppm_crit_min"] for r in feed)),
         "ppm_approach_min": app["ppm_vis_min"],
         "dof_ok_all": bool(all(r["dof_ok"] or r["edge_visible"] == 0 for r in per)),
         "dof_everything_sharp_all_poses": bool(all(r["dof_all_visible_ok"] for r in per)),
         "blur_feed_px": blur["feed_px"], "blur_approach_px": blur["approach_px"], "blur_approach_px_lit": blur["approach_px_lit"],
         "occluders": sorted({o for r in per for o in r["occluders"]}),
         "cam_inside_solid": any(r["cam_inside_solid"] for r in per),
         "head_ray_clear_mm": float(np.nanmin([r["head_ray_clear_mm"] for r in feed])) if pl["kind"] != "wrist" else None}
    s["pass_feed"] = bool(s["feed_crit_visible_min"] >= 0.9 and s["ppm_crit_min"] >= V["px_per_mm_req"] and s["dof_ok_all"]
                          and s["blur_feed_px"] <= 1.0 and not s["cam_inside_solid"])
    s["pass_approach"] = bool(s["approach_edge_visible"] >= 0.8 and s["approach_tips_visible"] == 2 and s["ppm_approach_min"] >= V["px_per_mm_min"])
    s["score"] = (2 * s["pass_feed"] + s["pass_approach"] + s["feed_crit_visible_min"] + 0.5 * s["feed_edge_visible_mean"]
                  + 0.25 * s["feed_foot_visible_frac"] + 0.25 * s["feed_tips_visible_min"] / 2 + 0.1 * min(s["ppm_crit_min"] / V["px_per_mm_req"], 2)
                  - (0.3 if pl["kind"] == "wrist" else 0) - 5 * s["cam_inside_solid"])
    return s


say("poses:")
for p in POSES:
    say(f"  {p['name']:9s} b={p['b']:7.1f} theta={p['theta']:5.1f} ik_err={p['ik_err_mm']:.2f} mm tilt={p['tilt_deg']:.1f} q={np.round(p['q'], 3).tolist()}")
say("handedness: +n (front plate) faces the seam edge, NSIGN =", NSIGN)

ALL, GEO = [], {}
for pl in WRIST + FIXED:
    rows, geo = evaluate(pl)
    GEO[pl["id"]] = (pl, geo)
    for cname, per, blur in rows:
        s = summarise(pl, cname, per, blur)
        s["per_pose"] = per
        ALL.append(s)

# ------------------------------------------------------------------ wrist pad on the +n front plate (numbers the CAD uses)
# Front plate n in [b + 2, b + 2 + plate] = [8.0, 10.5] (b = 6, plate 2.5), gear faces at n <= 7.0 (README z stack) [D].
# Plate outline = hull of R 22.5 circles at the pivots (c = +-15, u = 40.7) -> straight top edge at u = 18.2 [D];
# lightening holes dia 9 at (c 0, u 29.7) and dia 7 at (c 0, u 51.7) (README "(0, +-11)" about the pivot line) [D].
PAD = {"c0": 11.0, "u0": 27.0, "size_c": 12.0, "size_u": 17.0, "boss_h": 3.0, "plate_top_n": 10.5, "plate_t": 2.5,
       "gear_face_n": 7.0, "flange_t": 3.0, "bolt_pitch": 8.1, "insert_len_max": 4.0, "insert_bore_d": 4.2,
       "bore_depth": 4.5, "screw_len": 6.0}
PAD["flange_top_n"] = PAD["plate_top_n"] + PAD["boss_h"] + PAD["flange_t"]
PAD["bolts_cu"] = [(PAD["c0"], PAD["u0"] - PAD["bolt_pitch"] / 2), (PAD["c0"], PAD["u0"] + PAD["bolt_pitch"] / 2)]
_stack = PAD["boss_h"] + PAD["plate_t"]
PAD_CHECK = {
    "boss_plus_plate_mm": _stack,
    "bore_floor_left_mm": _stack - PAD["bore_depth"],
    "bore_floor_to_gear_face_mm": _stack - PAD["bore_depth"] + (PAD["plate_top_n"] - PAD["plate_t"] - PAD["gear_face_n"]),
    "screw_engagement_mm": PAD["screw_len"] - PAD["flange_t"],
    "screw_tip_above_bore_floor_mm": PAD["bore_depth"] - (PAD["screw_len"] - PAD["flange_t"]),
    "bolt_web_to_dia9_hole_mm": min(math.hypot(c - 0, u - 29.7) for c, u in PAD["bolts_cu"]) - 4.5 - PAD["insert_bore_d"] / 2,
    "bolt_web_to_plate_top_edge_mm": min(u for _, u in PAD["bolts_cu"]) - PAD["insert_bore_d"] / 2 - 18.2,
    "bolt_to_pitch_point_mm": min(math.hypot(c, u - U_PIV) for c, u in PAD["bolts_cu"]),
    "pad_edge_to_dia9_hole_mm": (PAD["c0"] - PAD["size_c"] / 2) - 4.5,
}
PAD_CHECK["ok"] = bool(PAD_CHECK["bore_floor_left_mm"] >= 0.8 and PAD_CHECK["screw_engagement_mm"] <= PAD["insert_len_max"] - 0.5
                       and PAD_CHECK["screw_tip_above_bore_floor_mm"] >= 0.5 and PAD_CHECK["bolt_web_to_dia9_hole_mm"] >= 2.0
                       and PAD_CHECK["bolt_web_to_plate_top_edge_mm"] >= 2.0 and PAD_CHECK["pad_edge_to_dia9_hole_mm"] >= 0.0)
assert PAD_CHECK["ok"], PAD_CHECK
PAD_SOLID = box((PAD["c0"] - PAD["size_c"] / 2, PAD["u0"] - PAD["size_u"] / 2, PAD["plate_top_n"]),
                (PAD["c0"] + PAD["size_c"] / 2, PAD["u0"] + PAD["size_u"] / 2, PAD["flange_top_n"]))
PLATE_MARGIN, PLATE_T = 1.5, 2.5   # [A] printed camera plate: board + 1.5 mm rim, 2.5 mm thick, behind the board


def cam_axes_local(pl):
    a = pl["aim_loc"] - pl["p_loc"]; a = a / np.linalg.norm(a)
    ec = np.array([1.0, 0, 0]) - a[0] * a; ec /= np.linalg.norm(ec)
    en = np.cross(a, ec)
    if en[2] < 0:
        en = -en
    return a, ec, en


def cam_envelope_local(pl, cname):
    """Board + lens stack + printed plate as a box in the gripper frame; the lens-to-low-edge side faces -n (the housing)."""
    cam = CAMS[cname]
    a, ec, en = cam_axes_local(pl)
    hc = cam["board_c"] / 2 + PLATE_MARGIN
    n_lo, n_hi = -(cam["lens_from_low_edge"] + PLATE_MARGIN), cam["board_n"] - cam["lens_from_low_edge"] + PLATE_MARGIN
    t_lo = -(cam["depth"] + PLATE_T)
    return np.array([pl["p_loc"] + cc * ec + nn * en + tt * a for cc in (-hc, hc) for nn in (n_lo, n_hi) for tt in (t_lo, 0.0)])


def box_surface_pts(corners, step=1.5):
    """Grid points on the faces of the (parallelepiped) box given by the 8 corners of cam_envelope_local."""
    o = corners[0]; e1, e2, e3 = corners[4] - o, corners[2] - o, corners[1] - o
    out = []
    for (p_, q_, r_) in ((e1, e2, e3), (e1, e3, e2), (e2, e3, e1)):
        n1 = max(2, int(np.linalg.norm(p_) / step) + 1); n2 = max(2, int(np.linalg.norm(q_) / step) + 1)
        s1, s2 = np.meshgrid(np.linspace(0, 1, n1), np.linspace(0, 1, n2))
        base = o + s1.reshape(-1, 1) * p_ + s2.reshape(-1, 1) * q_
        out += [base, base + r_]
    return np.vstack(out)


def gap_lb(pts_a, hull_b, pts_b, hull_a):
    """Lower bound on the gap between two convex bodies (negative = overlap): max plane distance, both directions."""
    da = np.max(pts_a @ hull_b["eq"][:, :3].T + hull_b["eq"][:, 3], axis=1).min()
    db = np.max(pts_b @ hull_a["eq"][:, :3].T + hull_a["eq"][:, 3], axis=1).min()
    return float(min(da, db))


HOUSING_KEYS = ("deck_hub", "servo_cradle", "plates_gears")
SELF_REQ_HOUSING, SELF_REQ_FINGER = 1.0, 8.0   # [A] 1 mm to its own housing/pad stack, 8 mm to the finger sweep
INPUT["wrist_self_clear_housing_mm"] = (SELF_REQ_HOUSING, "A", "camera board + plate envelope to housing solids and pad/flange stack")
INPUT["wrist_self_clear_fingers_mm"] = (SELF_REQ_FINGER, "A", "camera envelope to the finger/knuckle sweep, theta_min .. +20 deg")


def wrist_self_clearance(pl, cname):
    env = cam_envelope_local(pl, cname)
    hull = poly(env); sp = box_surface_pts(env)
    g_h = {}
    for k in HOUSING_KEYS:
        v = gripper_solids_local(0.0)[k]
        g_h[k] = gap_lb(sp, poly(v), v, hull)
    g_h["pad_flange_stack"] = gap_lb(sp, poly(PAD_SOLID), PAD_SOLID, hull)
    g_f = np.inf
    for th in np.linspace(GR["theta_min_deg"], GR["theta_open_max_deg"], 7):
        for k, v in gripper_solids_local(th).items():
            if k.startswith(("knuckle", "finger")):
                g_f = min(g_f, gap_lb(sp, poly(v), v, hull))
    return {"gap_to_housing_mm": min(g_h.values()), "gap_by_solid_mm": g_h, "gap_to_finger_sweep_mm": float(g_f),
            "envelope_low_n_mm": float(env[:, 2].min())}


# ------------------------------------------------------------------ mass impact (wrist only)
def wrist_mass(pl, cname):
    cam = CAMS[cname]
    # bracket: flange = pad footprint x 3; riser 12 x 3 from the flange top to the plate's low edge; camera plate = board + rim
    env = cam_envelope_local(pl, cname)
    u_lo, u_hi = PAD["u0"] - PAD["size_u"] / 2, PAD["u0"] + PAD["size_u"] / 2
    riser = (max(5.0, float(env[:, 2].min()) - PAD["flange_top_n"] + 3.0)
             + max(0.0, u_lo - float(env[:, 1].max())) + max(0.0, float(env[:, 1].min()) - u_hi))   # rise in n + reach along u
    vol = (PAD["size_c"] * PAD["size_u"] * PAD["flange_t"] + (cam["board_c"] + 2 * PLATE_MARGIN) * (cam["board_n"] + 2 * PLATE_MARGIN) * PLATE_T
           + riser * 12 * 3) / 1000
    mount_g = vol * V["petg_density"] * V["mount_fill"]
    if cname in ("PiCam3", "PiCam3_wide", "OV9281_GS"):
        cable_g, cable = 3.0, "CSI ribbon, carried part [A]; the Pi stays off the arm"
    else:
        cable_g, cable = V["cable_g_per_m"] * V["cable_carried_m"], "USB cable, carried part [A]"
    tot = cam["mass"] + mount_g + cable_g
    u = pl["p_loc"][1]
    dm = tot * (V["shoulder_lever_H_mm"] + u)
    use = (V["mass_moment_now_gmm"] + dm) / V["mass_moment_budget_gmm"]
    return {"camera_g": cam["mass"], "camera_mass_tag": "S" if cname.startswith("PiCam3") else "A", "mount_g": mount_g, "cable_g": cable_g,
            "cable": cable, "total_g": tot, "u_mm": u, "mass_moment_added_gmm": dm, "budget_use_C001_7p4V": use}


for s in ALL:
    if s["kind"] == "wrist":
        pl = next(p for p in WRIST if p["id"] == s["placement"])
        s["mass"] = wrist_mass(pl, s["camera"])
        s["score"] -= 0.5 * max(0.0, s["mass"]["budget_use_C001_7p4V"] - 1.0) * 10
    else:
        s["mass"] = {"total_g": 0.0, "budget_use_C001_7p4V": V["mass_moment_now_gmm"] / V["mass_moment_budget_gmm"]}

ALL.sort(key=lambda s: -s["score"])
say("\ntop 12 placement x camera (score):")
for s in ALL[:12]:
    say(f"  {s['score']:.2f} {s['placement']:24s} {s['camera']:16s} feed_pass={s['pass_feed']} app_pass={s['pass_approach']} "
        f"crit_vis={s['feed_crit_visible_min']:.2f} edge_vis={s['feed_edge_visible_mean']:.2f} ppm_crit={s['ppm_crit_min']:.1f} "
        f"tips={s['feed_tips_visible_min']} dof={s['dof_ok_all']} blur={s['blur_feed_px']:.2f} occ={s['occluders']}")


def best_of(kind):
    c = [s for s in ALL if s["kind"] == kind]
    return c[0] if c else None


BEST = {k: best_of(k) for k in ("wrist", "overhead", "side")}
say("\nbest per kind:")
for k, s in BEST.items():
    say(f"  {k:8s} {s['placement']} {s['camera']} score {s['score']:.2f} pass_feed {s['pass_feed']} pass_approach {s['pass_approach']}")

# ------------------------------------------------------------------ physical clearance of the camera hardware
# Fixed cameras: the lens body (sphere r = CAM_R) plus its support (overhead: vertical post from the lens to the table;
# side: stalk from the lens down to the bed) must clear the SO-101 link meshes and the gripper solids at every sampled
# pose by >= CLEAR_REQ, and the support must not pass through a machine box.  Wrist cameras (per camera): the board +
# plate envelope must clear its own housing / pad stack and the finger sweep (wrist_self_clearance), stay >= CLEAR_REQ
# above the bed and outside the machine boxes at every pose.
CAM_R, CLEAR_REQ = 20.0, 25.0   # [A] 32 x 32 board + lens barrel half-diagonal ~ 20 mm; 25 mm running clearance
INPUT["camera_body_radius_mm"] = (CAM_R, "A", "fixed cameras: 32 x 32 board + lens barrel half-diagonal")
INPUT["clearance_req_mm"] = (CLEAR_REQ, "A", "running clearance to arm links, gripper and bed")


def world_obstacles(pose):
    set_q(np.array(pose["q"])); mujoco.mj_forward(m, d)
    pts = []
    for g in range(m.ngeom):
        if m.geom_group[g] != 2 or m.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH:
            continue
        mid = m.geom_dataid[g]
        vv = m.mesh_vert[m.mesh_vertadr[mid]: m.mesh_vertadr[mid] + m.mesh_vertnum[mid]][::3]
        pts.append((d.geom_xpos[g] + vv @ d.geom_xmat[g].reshape(3, 3).T) * 1000)
    fr = grip_frame()
    for v in gripper_solids_local(pose["theta"]).values():
        pts.append(L2W(v, fr))
    return np.vstack(pts)


OBST = [world_obstacles(p) for p in POSES]


def seg_dist(P_, a, b):
    ab = b - a; t = np.clip(((P_ - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
    return np.linalg.norm(P_ - (a + t[:, None] * ab), axis=1)


def inside_machine(pt):
    return [k for k, s_ in MACH.items() if np.all(s_["eq"][:, :3] @ pt + s_["eq"][:, 3] < -1e-6)]


def fixed_clearance(pl):
    pos = pl["pos"]
    foot = np.array([pos[0], pos[1], 0.0 if pl["kind"] == "overhead" else V["bed_z_mm"]])
    dmin = min(float(seg_dist(O, pos, foot).min()) for O in OBST) - CAM_R
    hits = sorted({k for t in np.linspace(0, 1, 60) for k in inside_machine(pos + t * (foot - pos))})
    return {"support": "vertical post lens->table" if pl["kind"] == "overhead" else "stalk lens->bed",
            "support_foot_world_mm": foot, "min_clearance_to_arm_gripper_mm": dmin,
            "support_passes_through_machine": hits, "clear_ok": bool(dmin >= CLEAR_REQ and not hits)}


SELF_REQ_ARM = 3.0   # [A] camera envelope to the SO-101 link meshes: at the 8 task poses and over a +-150 deg roll sweep at mid-feed
INPUT["wrist_clear_arm_links_mm"] = (SELF_REQ_ARM, "A", "wrist camera envelope to SO-101 link meshes: task poses + roll sweep -150..150 deg at mid-feed; "
                                     "the folded approach pose's roll sweep is reported, not gated")
ARM_GEOMS = [g for g in range(m.ngeom) if m.geom_group[g] == 2 and m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH]
ROLL_Q, ROLL_APP = [], []
for pose in POSES:
    ROLL_Q.append(np.array(pose["q"]))
for rr in np.radians(np.arange(-150, 151, 15)):
    q_ = np.array(POSES[len(POSES) // 2]["q"]); q_[4] = rr; ROLL_Q.append(q_)
    q_ = np.array(POSES[0]["q"]); q_[4] = rr; ROLL_APP.append((float(np.degrees(rr)), q_))


def arm_pts_for(q_):
    set_q(q_); mujoco.mj_forward(m, d)
    vv = []
    for g in ARM_GEOMS:
        mid = m.geom_dataid[g]
        mv = m.mesh_vert[m.mesh_vertadr[mid]: m.mesh_vertadr[mid] + m.mesh_vertnum[mid]]
        vv.append((d.geom_xpos[g] + mv @ d.geom_xmat[g].reshape(3, 3).T) * 1000)
    return np.vstack(vv), grip_frame()


ARM_PTS = []   # (arm link vertices world, gripper frame) per configuration
for q_ in ROLL_Q:
    set_q(q_); mujoco.mj_forward(m, d)
    vv = []
    for g in ARM_GEOMS:
        mid = m.geom_dataid[g]
        mv = m.mesh_vert[m.mesh_vertadr[mid]: m.mesh_vertadr[mid] + m.mesh_vertnum[mid]]
        vv.append((d.geom_xpos[g] + mv @ d.geom_xmat[g].reshape(3, 3).T) * 1000)
    ARM_PTS.append((np.vstack(vv), grip_frame()))


def arm_gap(env_local, pts=None):
    best = np.inf
    for P_, fr in (ARM_PTS if pts is None else pts):
        w = L2W(env_local, fr)
        near = P_[np.linalg.norm(P_ - w.mean(0), axis=1) < 120]
        if len(near):
            h = poly(w)
            best = min(best, float(np.max(near @ h["eq"][:, :3].T + h["eq"][:, 3], axis=1).min()))
    return best


def wrist_clearance(pl, cname):
    env = cam_envelope_local(pl, cname)
    zmin, mach = 1e9, set()
    for pose in POSES:
        tg = targets(pose)
        w = L2W(env, tg["fr"])
        zmin = min(zmin, float(w[:, 2].min() - V["bed_z_mm"]))
        for pt in w:
            mach |= set(inside_machine(pt))
    sc = wrist_self_clearance(pl, cname)
    g_arm = arm_gap(env)
    ok = bool(zmin >= CLEAR_REQ and not mach and sc["gap_to_housing_mm"] >= SELF_REQ_HOUSING and sc["gap_to_finger_sweep_mm"] >= SELF_REQ_FINGER
              and g_arm >= SELF_REQ_ARM)
    return {"min_body_height_above_bed_mm": zmin, "lens_inside_machine": sorted(mach), **sc,
            "gap_to_so101_links_over_roll_mm": g_arm, "clear_ok": ok}


CLR_F = {pl["id"]: fixed_clearance(pl) for pl in FIXED}
CLR_W = {(pl["id"], cn): wrist_clearance(pl, cn) for pl in WRIST for cn in CAMS}
for s in ALL:
    s["clearance"] = CLR_F[s["placement"]] if s["kind"] != "wrist" else CLR_W[(s["placement"], s["camera"])]
say("\nclearance, fixed (body + support to arm/gripper over all poses):")
for pid, c in CLR_F.items():
    say(f"  {pid:24s} {c['min_clearance_to_arm_gripper_mm']:7.1f} mm  ok={c['clear_ok']} {c['support_passes_through_machine']}")
say("clearance, wrist edge face (envelope above bed / gap to own housing+pad / gap to finger sweep):")
for (pid, cn), c in CLR_W.items():
    if "_edge_" in pid and cn in ("PiCam3", "PiCam3_wide", "UVC32_1080p"):
        say(f"  {pid:26s} {cn:12s} bed {c['min_body_height_above_bed_mm']:6.1f}  housing {c['gap_to_housing_mm']:6.1f}  "
            f"fingers {c['gap_to_finger_sweep_mm']:6.1f}  arm {c['gap_to_so101_links_over_roll_mm']:6.1f}  ok={c['clear_ok']}")

# ------------------------------------------------------------------ torque-lane metric at its governing (worst) pose
# payload_torque.py arm_util(): max over shoulder_lift/elbow/wrist_flex poses of max_j |tau_j| / (hold_frac_arm * stall),
# gripper bodies massless, hardware as point masses d_mm past the gripper origin.  Items and seed pose are read from
# payload_torque.json rollup_design_point_A17; the no-camera and 10 g-at-20 mm values are reproduced as a check.
from scipy.optimize import minimize
TQ = json.loads((ROOT / "analysis/gripper/results/payload_torque.json").read_text())["rollup_design_point_A17"]
KIT = "C001_7p4V"
m2 = mujoco.MjModel.from_xml_path(str(MJCF)); d2 = mujoco.MjData(m2)
for bname in ("gripper", "moving_jaw_so101_v1"):
    m2.body_mass[m2.body(bname).id] = 1e-9
mujoco.mj_setConst(m2, d2)
TQ_J = ["shoulder_lift", "elbow_flex", "wrist_flex"]
TQ_DOF = [int(m2.jnt_dofadr[m2.joint(n).id]) for n in TQ_J]
TQ_QADR = [int(m2.jnt_qposadr[m2.joint(n).id]) for n in TQ_J]
TQ_BND = [tuple(float(v) for v in m2.jnt_range[m2.joint(n).id]) for n in TQ_J]
TQ_ALLOW = PS["hold_fraction_arm"] * PS["scenarios"][KIT]["stall_Nm"]
bg2 = m2.body("gripper").id


def tq_util(x, items):
    d2.qpos[:] = 0; d2.qvel[:] = 0
    for a_, v_ in zip(TQ_QADR, x):
        d2.qpos[a_] = v_
    mujoco.mj_forward(m2, d2)
    t = np.array([d2.qfrc_bias[k] for k in TQ_DOF])
    R_ = d2.xmat[bg2].reshape(3, 3)
    for _, g_, dd in items:
        p_ = d2.xpos[bg2] + R_ @ np.array([0, 0, -dd / 1000])
        jp = np.zeros((3, m2.nv)); mujoco.mj_jac(m2, d2, jp, None, p_, bg2)
        t += g_ / 1000 * 9.80665 * jp[2, TQ_DOF]
    return float(np.max(np.abs(t))) / TQ_ALLOW


_TQC = {}


def tq_worst(items):
    key = tuple((round(g_, 3), round(dd, 3)) for _, g_, dd in items)
    if key in _TQC:
        return _TQC[key]
    best = (-1.0, None)
    for x0 in (np.array(TQ["no_camera"]["worst_pose"][KIT]), np.zeros(3)):
        simplex = np.vstack([x0] + [np.clip(x0 + 0.15 * np.eye(3)[i] * (1 if x0[i] + 0.15 <= TQ_BND[i][1] else -1), TQ_BND[i][0], TQ_BND[i][1]) for i in range(3)])
        r_ = minimize(lambda x: -tq_util(x, items), x0, method="Nelder-Mead", bounds=TQ_BND,
                      options={"xatol": 1e-5, "fatol": 1e-8, "maxiter": 800, "initial_simplex": simplex})
        for v_, x_ in ((-r_.fun, r_.x), (tq_util(x0, items), x0)):
            if v_ > best[0]:
                best = (float(v_), np.array(x_, float))
    _TQC[key] = best
    return best


TQ_ITEMS0 = [(it["name"], it["g"], it["d_mm"]) for it in TQ["no_camera"]["items"]]
u0_, x0_ = tq_worst(TQ_ITEMS0)
u10_, x10_ = tq_worst(TQ_ITEMS0 + [("camera", 10.0, 20.0)])
TQ_CHECK = {"no_camera_util_this_script": u0_, "no_camera_util_torque_lane": TQ["no_camera"]["util"][KIT],
            "camera10g_at_20mm_util_this_script": u10_, "camera10g_at_20mm_util_torque_lane": TQ["with_camera"]["util"][KIT],
            "worst_pose_no_camera_sl_el_wf_rad": x0_, "zero_pose_reference_torque_lane": TQ["no_camera"]["util_zero_pose_reference"][KIT]}
assert abs(u0_ - TQ_CHECK["no_camera_util_torque_lane"]) < 0.003 and abs(u10_ - TQ_CHECK["camera10g_at_20mm_util_torque_lane"]) < 0.003, TQ_CHECK
say(f"\ntorque-lane worst-pose util reproduced: no camera {u0_:.4f} (lane {TQ_CHECK['no_camera_util_torque_lane']}), "
    f"10 g @ 20 mm {u10_:.4f} (lane {TQ_CHECK['camera10g_at_20mm_util_torque_lane']})")
for s in ALL:
    if s["kind"] == "wrist" and s["mass"]["total_g"] <= 20:
        uu_, xx_ = tq_worst(TQ_ITEMS0 + [("camera", s["mass"]["total_g"], s["mass"]["u_mm"])])
        s["mass"]["util_worst_pose_torque_lane"] = uu_
        s["mass"]["worst_pose_sl_el_wf_rad"] = xx_
    elif s["kind"] != "wrist":
        s["mass"]["util_worst_pose_torque_lane"] = u0_

# ------------------------------------------------------------------ selection
# primary = the passing, clear fixed candidate with the most sight-line clearance past the (assumed) head box, among
# those with >= 5 % px/mm margin; backup = best passing candidate of the other fixed family; wrist = pick-view ranking.
fixed_pass = [s for s in ALL if s["kind"] != "wrist" and s["pass_feed"] and s["clearance"]["clear_ok"]]
robust = [s for s in fixed_pass if s["kind"] == "overhead" and s["ppm_crit_min"] >= 1.05 * V["px_per_mm_req"]]
if robust:
    primary = max(robust, key=lambda s: (round(s["head_ray_clear_mm"], 1), s["score"]))
else:
    primary = fixed_pass[0] if fixed_pass else [s for s in ALL if s["kind"] != "wrist"][0]
other = [s for s in ALL if s["kind"] not in ("wrist", primary["kind"]) and s["pass_feed"] and s["clearance"]["clear_ok"]]
backup_fixed = other[0] if other else [s for s in ALL if s["kind"] not in ("wrist", primary["kind"])][0]
backup_alts = [s for s in other if s["camera"] != backup_fixed["camera"]]
say("\nfixed candidates that pass feed and clearance (placement camera ppm head_clear):")
for s in fixed_pass:
    say(f"  {s['placement']:22s} {s['camera']:16s} ppm {s['ppm_crit_min']:.2f} head_clear {s['head_ray_clear_mm']:.1f} mm")
# ------------------------------------------------------------------ CSI ribbon run for the wrist option
set_q(np.array(POSES[len(POSES) // 2]["q"])); mujoco.mj_forward(m, d)
anch = {n: d.xanchor[jid[n]] * 1000 for n in JN}
lens_w = L2W(next(p for p in WRIST if p["id"] == "W_edge_n28p5_u30_aim125")["p_loc"], grip_frame())[0]
legs = {"lens_to_wrist_roll": np.linalg.norm(lens_w - anch["wrist_roll"]),
        "wrist_roll_to_wrist_flex": np.linalg.norm(anch["wrist_roll"] - anch["wrist_flex"]),
        "wrist_flex_to_elbow": np.linalg.norm(anch["wrist_flex"] - anch["elbow_flex"]),
        "elbow_to_shoulder_lift": np.linalg.norm(anch["elbow_flex"] - anch["shoulder_lift"]),
        "shoulder_lift_to_pan": np.linalg.norm(anch["shoulder_lift"] - anch["shoulder_pan"]),
        "pan_to_table": float(anch["shoulder_pan"][2])}
loops = {"wrist_roll_service_loop": 80.0, "wrist_flex": 40.0, "elbow": 40.0, "shoulder_lift": 40.0, "pan": 40.0, "table_run_to_pi": 150.0}
csi_len = float(sum(legs.values()) + sum(loops.values()))
CSI = {"legs_mm_D": {k: float(v) for k, v in legs.items()}, "allowances_mm_A": loops, "total_mm": csi_len,
       "official_lengths_mm_S": [200, 300, 500], "official_source": "https://www.raspberrypi.com/products/camera-cable/",
       "fits_official_500": bool(csi_len <= 500.0),
       "roll_twist": "a flat-flex ribbon through +-150 deg wrist roll in a 60-80 mm loop is not assessed and is not a rated use [A]; "
                     "the USB 32 x 32 UVC (round cable) avoids both the length and the twist problem"}
say(f"CSI run lens -> Pi on the table ~ {csi_len:.0f} mm (official cables 200/300/500 mm)")

wr = [s for s in ALL if s["kind"] == "wrist" and s["mass"]["total_g"] <= 20 and s["clearance"]["clear_ok"]]
for s in wr:  # the wrist camera's job is the pick: rank on approach first, then feed coverage, then mass
    s["wrist_score"] = (s["pass_approach"] + s["approach_edge_visible"] + 0.5 * s["approach_tips_visible"] + 0.1 * min(s["ppm_approach_min"] / 5, 2)
                        + 0.5 * s["feed_crit_visible_min"] + 0.25 * s["feed_edge_visible_mean"] + 0.2 * min(s["ppm_crit_min"] / 5, 1)
                        - 2 * max(0.0, s["mass"]["budget_use_C001_7p4V"] - 1.0))
wr.sort(key=lambda s: -s["wrist_score"])
CSI_CAMS = ("PiCam3", "PiCam3_wide", "OV9281_GS")
WIRED_USB = ("UVC32_1080p", "C270")
# the wrist video link must reach the host by wire: CSI only if a standard cable reaches, else USB. The ESP32-CAM (Wi-Fi
# stream, power-only wires through the roll) is reported separately: Wi-Fi latency and drop-outs are not assessed [A].
wr_ok = [s for s in wr if (s["camera"] in CSI_CAMS and CSI["fits_official_500"]) or s["camera"] in WIRED_USB]
backup = wr_ok[0]
wr_wifi = [s for s in wr if s["camera"] == "ESP32CAM_OV2640"]
wrist_wifi = wr_wifi[0] if wr_wifi else None
wr_csi = [s for s in wr if s["camera"] in CSI_CAMS]
wrist_csi_best = wr_csi[0] if wr_csi and wr_csi[0] is not backup else None
wr_usb = [s for s in wr_ok if s["camera"] == "UVC32_1080p"]
wrist_usb = wr_usb[0] if wr_usb else None
say("\nPRIMARY:", primary["placement"], primary["camera"], " BACKUP (fixed):", backup_fixed["placement"], backup_fixed["camera"],
    " WRIST OPTION (reserved pad):", backup["placement"], backup["camera"],
    " (optical best, CSI:", wrist_csi_best["placement"] if wrist_csi_best else None, wrist_csi_best["camera"] if wrist_csi_best else None, ")")
for s in wr[:8]:
    say(f"  wrist {s['wrist_score']:.2f} {s['placement']} {s['camera']} app_edge {s['approach_edge_visible']:.2f} tips {s['approach_tips_visible']} "
        f"ppm_app {s['ppm_approach_min']:.1f} crit {s['feed_crit_visible_min']:.2f} ppm_crit {s['ppm_crit_min']:.1f} blur_app {s['blur_approach_px']:.1f} "
        f"use {s['mass']['budget_use_C001_7p4V']:.3f} util_worst {s['mass']['util_worst_pose_torque_lane']:.3f}")

# ------------------------------------------------------------------ primary robustness to the real head (M-C1 thresholds)
ppl = next(p for p in FIXED if p["id"] == primary["placement"])


def crit_min_with_head(pl_, cname, lo, hi):
    global MACH
    keep = MACH
    MACH = dict(keep); MACH["head"] = poly(np.array([mach_to_world(*c) for c in box(lo, hi)]))
    try:
        rows, _ = evaluate(pl_)
    finally:
        MACH = keep
    per = next(p for cn, p, _ in rows if cn == cname)
    return min(r["crit_visible"] for r in per if r["pose"].startswith("feed"))


h_lo0, h_hi0 = MACH_LOCAL["head"]


def head_thresholds(pl_, cname):
    su, sr = [], []
    for hu in np.arange(65.0, 29.0, -2.0):   # head underside height above the bed, right face at nominal a = 40
        su.append((float(hu), crit_min_with_head(pl_, cname, (h_lo0[0], h_lo0[1], V["bed_z_mm"] + hu), h_hi0)))
        if su[-1][1] < 0.9:
            break
    for ar in np.arange(40.0, 91.0, 2.0):    # head right face a, underside at nominal 65 mm
        sr.append((float(ar), crit_min_with_head(pl_, cname, h_lo0, (ar, h_hi0[1], h_hi0[2]))))
        if sr[-1][1] < 0.9:
            break
    tu = next((su[i - 1][0] for i, (_, v) in enumerate(su) if v < 0.9 and i > 0), su[-1][0])
    tr = next((sr[i - 1][0] for i, (_, v) in enumerate(sr) if v < 0.9 and i > 0), sr[-1][0])
    return {"placement": pl_["id"], "camera": cname,
            "nominal_head_underside_above_bed_mm": h_lo0[2] - V["bed_z_mm"], "nominal_head_right_face_a_mm": h_hi0[0],
            "pass_if_underside_above_bed_mm_at_least": tu, "pass_if_right_face_a_mm_at_most": tr,
            "margin_underside_mm": (h_lo0[2] - V["bed_z_mm"]) - tu, "margin_right_face_mm": tr - h_hi0[0],
            "sweep_underside_mm_vs_crit_visible": su, "sweep_right_face_mm_vs_crit_visible": sr,
            "rule": "critical edge >= 90 % visible at every feed pose; 2 mm steps; the other head faces at nominal"}


HEAD_M = head_thresholds(ppl, primary["camera"])
HEAD_M["sight_line_clearance_to_head_box_mm"] = primary["head_ray_clear_mm"]
first_pass = next(s_ for s_ in ALL if s_["placement"] == "O_h250_r120_path" and s_["camera"] == "PiCam3")
HEAD_M_FIRST = head_thresholds(next(p for p in FIXED if p["id"] == "O_h250_r120_path"), "PiCam3")
HEAD_M_FIRST["sight_line_clearance_to_head_box_mm"] = first_pass["head_ray_clear_mm"]
thr_under, thr_right = HEAD_M["pass_if_underside_above_bed_mm_at_least"], HEAD_M["pass_if_right_face_a_mm_at_most"]
say("first-pass O_h250_r120 head thresholds: underside >= %.0f, right face <= %.0f" % (
    HEAD_M_FIRST["pass_if_underside_above_bed_mm_at_least"], HEAD_M_FIRST["pass_if_right_face_a_mm_at_most"]))
say(f"\nprimary head thresholds: underside >= {thr_under:.0f} mm above bed (nominal 65), right face <= a {thr_right:.0f} mm (nominal 40)")

# ------------------------------------------------------------------ mount proposal
bpl = next(p for p in WRIST if p["id"] == backup["placement"])
pos_mach = ppl["pos"] - NEEDLE
axis = ppl["aim"] - ppl["pos"]; axis /= np.linalg.norm(axis)


def cam_plate(cname):
    c = CAMS[cname]
    return {"camera": cname, "board_mm": [c["board_c"], c["board_n"]], "holes": c["holes"], "tag": c["body_tag"],
            "lens_from_housing_side_edge_mm": c["lens_from_low_edge"],
            "plate_mm": [c["board_c"] + 2 * PLATE_MARGIN, c["board_n"] + 2 * PLATE_MARGIN, PLATE_T]}


def wrist_block(s):
    pl_ = next(p for p in WRIST if p["id"] == s["placement"])
    a_, ec_, en_ = cam_axes_local(pl_)
    env_ = cam_envelope_local(pl_, s["camera"])
    app_sweep = [(deg, arm_gap(env_, [arm_pts_for(q_)])) for deg, q_ in ROLL_APP]
    bad = [deg for deg, g_ in app_sweep if g_ < SELF_REQ_ARM]
    return {
        "placement": s["placement"], "camera": s["camera"],
        "lens_centre_local_mm": {"c": float(pl_["p_loc"][0]), "u": float(pl_["p_loc"][1]), "n": float(pl_["p_loc"][2])},
        "aim_point_local_mm": {"c": float(pl_["aim_loc"][0]), "u": float(pl_["aim_loc"][1]), "n": float(pl_["aim_loc"][2])},
        "optical_axis_tilt_from_roll_axis_deg": float(pl_["tilt_from_roll_axis_deg"]),
        "plate_to_flange_angle_deg": float(90.0 - pl_["tilt_from_roll_axis_deg"]),
        "plate_orientation": "camera plate stands %.1f deg to the flange; its normal (the optical axis) is %.1f deg from +u toward -n; "
                             "board edge nearest the lens faces -n (toward the housing; the FFC/USB exits there)" % (
                                 90.0 - pl_["tilt_from_roll_axis_deg"], pl_["tilt_from_roll_axis_deg"]),
        "camera_plate": cam_plate(s["camera"]),
        "approach_ppm_min": s["ppm_approach_min"], "feed_ppm_crit_min": s["ppm_crit_min"],
        "mass_g_total_on_arm": float(s["mass"]["total_g"]), "mass_breakdown": s["mass"],
        "budget_use_C001_7p4V": float(s["mass"]["budget_use_C001_7p4V"]),
        "util_worst_pose_torque_lane": float(s["mass"]["util_worst_pose_torque_lane"]),
        "clearance": s["clearance"],
        "approach_pose_roll_sweep_gap_mm": app_sweep,
        "approach_pose_roll_keepout_deg": [min(bad), max(bad)] if bad else None,
    }


MOUNT = {
    "_doc": "Numbers the CAD rebuild uses. Gripper local frame: c = jaw closing axis (+ toward finger B, the upper/idler finger), "
            "u = roll axis from the gripper-body origin toward the tips, n = gear-axis direction (+ = front-plate side, which faces "
            "the seam edge; servo body on -n). Machine frame: origin at the needle point on the bed, a = operator's right (toward the tower), "
            "b = along the feed, z = up from the bed.",
    "primary_fixed": {
        "placement": primary["placement"], "camera": primary["camera"],
        "position_machine_mm": {"a_right": float(pos_mach @ RIGHT), "b_feed": float(pos_mach @ FEED), "z_above_bed": float(pos_mach[2])},
        "optical_axis_depression_deg": float(math.degrees(math.asin(-axis[2]))),
        "optical_axis_yaw_from_feed_deg": float(math.degrees(math.atan2(axis @ RIGHT, axis @ FEED))),
        "aim_point_machine_mm": {"a_right": float((ppl["aim"] - NEEDLE) @ RIGHT), "b_feed": float((ppl["aim"] - NEEDLE) @ FEED), "z_above_bed": float(ppl["aim"][2] - NEEDLE[2])},
        "image_long_axis": "along the feed (b)" if ppl["kind"] == "overhead" else "horizontal",
        "camera_plate": cam_plate(primary["camera"]),
        "hardware": "desk clamp + 1/4-20 ball head on a 12-15 mm rod or 2020 extrusion post, fixed to the table (not the machine: needle vibration); "
                    "printed camera plate 28 x 26.9 x 2.5 mm with 4x M2 on 21.0 x 12.5 mm centres (Pi Camera 3 board 25 x 23.86, holes dia 2.2) "
                    "and a 1/4-20 insert on its back; lock the pose with thread-locker, then run one homography to the bed",
        "calibration": "intrinsics (checkerboard) + planar homography to the bed plane, re-done if the clamp moves",
        "head_thresholds_M_C1": HEAD_M,
        "clearance": primary["clearance"],
    },
    "backup_fixed": {
        "placement": backup_fixed["placement"], "camera": backup_fixed["camera"],
        "position_machine_mm": dict(zip(("a_right", "b_feed", "z_above_bed"), [float(x) for x in (
            (next(p for p in FIXED if p["id"] == backup_fixed["placement"])["pos"] - NEEDLE) @ np.array([RIGHT, FEED, [0, 0, 1.0]]).T)])),
        "aim_point_machine_mm": {"a_right": V["seam_allowance_mm"], "b_feed": -V["presser_foot_front_mm"] - 20, "z_above_bed": 0.0},
        "hardware": "small bracket on a printed foot clipped to the bed front-right, inside the throat under the machine arm; "
                    "keep clear of the presser-foot lever and the hand wheel side",
        "note": "UVC 32 x 32 here rests on assumed specs (1080p, 90 deg, 3 um; a 720p module drops to about 3.9 px/mm); "
                "the OV9281 (global shutter, sourced 1280 x 800) passes on a sourced resolution with an assumed lens",
        "alternatives_same_mount": [{"camera": s["camera"], "ppm_crit_min": s["ppm_crit_min"], "feed_crit_visible_min": s["feed_crit_visible_min"],
                                     "blur_feed_px": s["blur_feed_px"], "shutter": CAMS[s["camera"]]["shutter"]}
                                    for s in backup_alts if s["placement"] == backup_fixed["placement"]],
        "clearance": backup_fixed["clearance"],
    },
    "wrist_option": {
        **wrist_block(backup),
        "pad_on_housing": {
            "face": "+n front plate",
            "pad_centre_local_mm": {"c": PAD["c0"], "u": PAD["u0"]}, "pad_size_mm_c_u": [PAD["size_c"], PAD["size_u"]],
            "pad_boss_height_mm": PAD["boss_h"],
            "bolt_pattern": "2x M3 at %.1f mm along u (upstream Hex-Nut adapter spacing, D9) at (c, u) = %s" % (PAD["bolt_pitch"], PAD["bolts_cu"]),
            "fastening": "blind bore dia %.1f x %.1f deep from the boss top for a short M3 heat-set insert <= %.1f mm long; M3 x %.0f screws "
                         "through the %.0f mm flange (%.0f mm engagement). No inside hex-nut trap: the inside face of the front plate is 1 mm "
                         "above the gear faces" % (PAD["insert_bore_d"], PAD["bore_depth"], PAD["insert_len_max"], PAD["screw_len"],
                                                   PAD["flange_t"], PAD["screw_len"] - PAD["flange_t"]),
            "placement_reason": "off the gear pitch point (c 0, u 40.7) and clear of the dia 9 lightening hole at (c 0, u 29.7)",
            "checks": PAD_CHECK,
            "deviation_from_D9": "D9 names hex-nut points; this uses heat-set inserts because a nut trap needs the inside face (gear zone). "
                                 "Spacing kept at the upstream 8.1 mm. Reversible [A]",
            "upstream_pattern_for_reference": STOCK_MOUNT},
        "bracket": {"flange_mm": [PAD["size_c"], PAD["size_u"], PAD["flange_t"]], "flange_top_n_mm": PAD["flange_top_n"],
                    "riser": "12 x 3 mm web from the flange up +n to the camera plate's low edge",
                    "material": "PETG, 40 % infill, print flange flat", "mass_g": float(backup["mass"]["mount_g"])},
        "cable": "Pi Camera: CSI ribbon ~%.0f mm lens -> Pi on the table vs official 200/300/500 mm [S]; ribbon twist through +-150 deg "
                 "roll not assessed. If the wrist camera must survive wrist roll, fit the 32 x 32 UVC instead (USB, see usb_alternative)" % csi_len,
        "csi_run": CSI,
        "usb_alternative": wrist_block(wrist_usb) if wrist_usb else None,
        "optical_best_csi": wrist_block(wrist_csi_best) if wrist_csi_best else None,
        "wifi_alternative": wrist_block(wrist_wifi) if wrist_wifi else None,
        "keepout": "camera envelope >= %.0f mm from the finger sweep (theta %.0f..%.0f deg) and >= %.0f mm from its own housing and pad stack"
                   % (SELF_REQ_FINGER, GR["theta_min_deg"], GR["theta_open_max_deg"], SELF_REQ_HOUSING),
    },
}

# ------------------------------------------------------------------ figures
def frustum_lines(pos, R, cam, L):
    out = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        ray = R.T @ np.array([sx * cam["tan_h"], sy * cam["tan_v"], 1.0])
        ray /= np.linalg.norm(ray)
        tz = (V["bed_z_mm"] - pos[2]) / ray[2] if ray[2] < -1e-6 else L
        out.append(pos + ray * min(tz, L))
    return np.array(out)


def draw(ax, i, j, pose_idx, plist, colors, title):
    pose = POSES[pose_idx]
    set_q(np.array(pose["q"])); mujoco.mj_kinematics(m, d); mujoco.mj_forward(m, d)
    for g in range(m.ngeom):
        if m.geom_group[g] != 2 or m.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH:
            continue
        mid = m.geom_dataid[g]
        vv = m.mesh_vert[m.mesh_vertadr[mid]: m.mesh_vertadr[mid] + m.mesh_vertnum[mid]][::15]
        w = (d.geom_xpos[g] + vv @ d.geom_xmat[g].reshape(3, 3).T) * 1000
        ax.scatter(w[:, i], w[:, j], s=0.3, c="0.55", lw=0)
    for k, s in MACH.items():
        v = s["v"][:, [i, j]]
        hh = ConvexHull(v); ax.fill(v[hh.vertices, 0], v[hh.vertices, 1], color="#c9b79c" if k != "presser_foot" else "#8a6d3b", alpha=0.35, lw=0.6, ec="#7a6a50")
    tg = targets(pose)
    for k, v in gripper_solids_local(pose["theta"]).items():
        w = L2W(v, tg["fr"])[:, [i, j]]
        hh = ConvexHull(w); ax.fill(w[hh.vertices, 0], w[hh.vertices, 1], color="#4c78a8" if "finger" not in k else "#f58518", alpha=0.6, lw=0.4, ec="k")
    ed = np.array([mach_to_world(V["seam_allowance_mm"], b, V["bed_z_mm"]) for b in (b_start - 40, -V["presser_foot_front_mm"])])
    ax.plot(ed[:, i], ed[:, j], "r-", lw=1.5, label="cloth seam edge")
    for (pl, cn), col in zip(plist, colors):
        s = next(x for x in ALL if x["placement"] == pl["id"] and x["camera"] == cn)
        cam = CAMS[cn]
        pos, R = cam_pose(pl, tg)
        fl = frustum_lines(pos, R, cam, 700)
        for q in fl:
            ax.plot([pos[i], q[i]], [pos[j], q[j]], color=col, lw=0.9)
        ax.plot(np.r_[fl[:, i], fl[0, i]], np.r_[fl[:, j], fl[0, j]], color=col, lw=0.9, ls="--")
        ax.plot(pos[i], pos[j], "o", color=col, ms=5, label=f"{pl['id']} ({s['camera']})")
    ax.set_aspect("equal"); ax.set_title(title, fontsize=9); ax.grid(alpha=0.3)


plist = [(ppl, primary["camera"]), (bpl, backup["camera"]),
         (next(p for p in FIXED if p["id"] == backup_fixed["placement"]), backup_fixed["camera"])]
cols = ["#2ca02c", "#d62728", "#9467bd"]
FIG.mkdir(parents=True, exist_ok=True)
for fname, (i, j, xl, yl) in {"camera_top.png": (0, 1, "x (mm, world)", "y (mm, world; feed = -y)"),
                              "camera_side.png": (1, 2, "y (mm, world; feed = -y)", "z (mm above table)")}.items():
    fig, axs = plt.subplots(1, 2, figsize=(14, 6.5))
    for ax, pidx, tl in ((axs[0], 0, "approach (jaw open +20 deg)"), (axs[1], len(POSES) - 1, "feed, at release (20 mm before the foot)")):
        draw(ax, i, j, pidx, plist, cols, tl)
        ax.set_xlabel(xl); ax.set_ylabel(yl)
        if j == 2:
            ax.set_ylim(-10, 700); ax.set_xlim(-600, 50)
        else:
            ax.set_xlim(-250, 350); ax.set_ylim(-520, 50)
    axs[1].legend(fontsize=7, loc="lower left")
    fig.suptitle("Camera frustums (to the bed plane): primary fixed (green), wrist option (red), backup fixed (purple). "
                 "Grey = SO-101 link meshes, blue/orange = simplified gripper, tan = sewing machine", fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / fname, dpi=130); plt.close(fig)

# simulated image views
fig, axs = plt.subplots(len(plist), 2, figsize=(11, 3.4 * len(plist)))
for r_, (pl, cn) in enumerate(plist):
    s = next(x for x in ALL if x["placement"] == pl["id"] and x["camera"] == cn); cam = CAMS[cn]
    for c_, pidx in enumerate((0, len(POSES) - 1)):
        ax = axs[r_, c_]; pose, tg, pos, R, pts, occ, _ = GEO[pl["id"]][1][pidx]
        uv, z, ins = project(R, pos, pts, cam)
        ne = len(tg["edge"])
        for k in range(len(pts)):
            if not ins[k]:
                continue
            col = "g" if occ[k] is None else ("m" if "arm" in occ[k] else ("b" if "machine" in occ[k] else "k"))
            mk = "o" if k < ne else ("^" if k < ne + 2 else "s")
            ax.plot(uv[k, 0], uv[k, 1], mk, color=col, ms=4)
        for k, v in gripper_solids_local(pose["theta"]).items():
            w = L2W(v, tg["fr"]); a, zz, _ = project(R, pos, w, cam)
            if (zz > 5).all():
                hh = ConvexHull(a); ax.fill(a[hh.vertices, 0], a[hh.vertices, 1], color="#f58518" if "finger" in k else "#4c78a8", alpha=0.35)
        ax.set_xlim(cam["out"][0] / 2 - cam["fx"] * cam["tan_h"], cam["out"][0] / 2 + cam["fx"] * cam["tan_h"])
        ax.set_ylim(cam["out"][1] / 2 + cam["fx"] * cam["tan_v"], cam["out"][1] / 2 - cam["fx"] * cam["tan_v"]); ax.set_aspect("equal")
        ax.set_title(f"{pl['id']} / {s['camera']} / {pose['name']}", fontsize=8)
fig.suptitle("Simulated images (px). o edge, ^ fingertips, s foot toe; green = visible, black = hidden by gripper, "
             "blue = by machine, magenta = by arm. Shaded: gripper (blue) and fingers (orange)", fontsize=8)
fig.tight_layout(); fig.savefig(FIG / "camera_views.png", dpi=110); plt.close(fig)

# ------------------------------------------------------------------ write results
def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 3)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


cams_out = {k: {kk: vv for kk, vv in v.items()} for k, v in CAMS.items()}
res = {
    "_doc": "analysis/gripper/camera.py output. Tags: S sourced, D derived (this script), A assumed. Frame: MuJoCo world of so101_old_calib.xml (mm).",
    "inputs": {k: {"value": v[0], "tag": v[1], "note": v[2]} for k, v in INPUT.items()},
    "cameras": cams_out,
    "work_cell_frame": {"needle_world_mm": NEEDLE, "feed_dir": FEED, "right_dir": RIGHT, "edge_offset_right_mm": V["seam_allowance_mm"],
                        "machine_boxes_local_mm": MACH_LOCAL, "tag": "A (Singer 4423 envelope S; internal layout A)"},
    "gripper_model": {"frame": "c closing, u roll axis to tips, n gear axis", "U_pivot": U_PIV, "U_root": U_ROOT, "U_tip": U_TIP, "pad_u": PAD_U,
                      "n_range_fingers": [N_LO, N_HI], "handedness_nsign": NSIGN, "tag": "D from params.json + DESIGN-BASIS (DS3218MG, m1.5 z20, L 45)"},
    "poses": POSES,
    "requirement": {"px_per_mm": V["px_per_mm_req"], "px_per_mm_relaxed": V["px_per_mm_min"], "crit_len_mm": V["critical_len_mm"],
                    "pass_feed_rule": "critical edge >= 90 % visible at every feed pose, px/mm >= req there, DoF covers all visible targets, feed blur <= 1 px",
                    "pass_approach_rule": ">= 80 % of edge near the grip visible, both fingertips visible, px/mm >= relaxed"},
    "best_per_kind": {k: {kk: vv for kk, vv in s.items() if kk != "per_pose"} for k, s in BEST.items()},
    "primary": primary, "backup_fixed": backup_fixed, "wrist_option": backup,
    "ranking_top20": [{kk: vv for kk, vv in s.items() if kk != "per_pose"} for s in ALL[:20]],
    "all": [{kk: vv for kk, vv in s.items() if kk != "per_pose"} for s in ALL],
    "mount": MOUNT,
    "torque_lane_check": TQ_CHECK,
    "primary_head_thresholds": HEAD_M,
    "first_pass_primary_head_thresholds": HEAD_M_FIRST,
    "wrist_pad_checks": PAD_CHECK,
    "csi_run": CSI,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", newline="\n", encoding="utf-8") as fh:
    json.dump(clean(res), fh, indent=1)
say("wrote", OUT.relative_to(ROOT))
with open(LOG, "w", newline="\n", encoding="utf-8") as fh:
    fh.write(_buf.getvalue())
