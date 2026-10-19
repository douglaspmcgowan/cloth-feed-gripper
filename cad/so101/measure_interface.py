"""Measure the SO-101 wrist-roll -> gripper interface and arm payload inputs.

Run from the repository root:
    uv run --with cadquery python cad/so101/measure_interface.py

Inputs (all in cad/so101/, from TheRobotStudio/SO-ARM100, see SOURCE.md):
    Wrist_Roll_Follower_SO101.step   stock gripper body (fixed jaw + motor-6 cradle)
    Moving_Jaw_SO101.step            stock moving jaw
    Wrist_Roll_Pitch_SO101.step      wrist link that holds motor 5 (wrist roll)
    Motor_holder_SO101_Wrist.step    forearm-end motor-4 holder
    SO101 Assembly.step              full follower assembly (servos, screws)
    so101_old_calib.urdf             zero pose = arm fully extended horizontally

Output: prints a JSON report to stdout (pass --json PATH to also save it).

Interface frame ("I"): origin = centre of the 4-screw horn pattern on the horn
mating plane; +Z = wrist-roll axis pointing away from motor 5 (into the
gripper); +X = along one side of the square screw pattern. Units mm.
"""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TopAbs import TopAbs_REVERSED

HERE = Path(__file__).resolve().parent
PLA = 1.24  # g/cm^3, same value as cad/gripper/params.json (assumed)
G = 9.81


# ---------------------------------------------------------------- geometry helpers
def cylinders(shape: cq.Shape):
    """Every cylindrical face: diameter, unit axis, a point on the axis, hole/boss."""
    out = []
    for f in shape.Faces():
        a = BRepAdaptor_Surface(f.wrapped)
        if a.GetType() != GeomAbs_Cylinder:
            continue
        c = a.Cylinder()
        ax = c.Axis()
        d = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
        p0 = np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()])
        u = 0.5 * (a.FirstUParameter() + a.LastUParameter())
        v = 0.5 * (a.FirstVParameter() + a.LastVParameter())
        pt = a.Value(u, v)
        pt = np.array([pt.X(), pt.Y(), pt.Z()])
        radial = pt - p0 - np.dot(pt - p0, d) * d
        radial /= np.linalg.norm(radial) + 1e-12
        # outward surface normal of a cylinder param is +radial; reversed face flips it
        n = -radial if f.wrapped.Orientation() == TopAbs_REVERSED else radial
        kind = "hole" if np.dot(n, radial) < 0 else "boss"
        span = math.degrees(a.LastUParameter() - a.FirstUParameter())
        verts = np.array([v.toTuple() for v in f.Vertices()]) if f.Vertices() else pt[None]
        out.append(dict(d=2 * c.Radius(), axis=d, p0=p0, kind=kind, span=span,
                        pts=verts, pt=pt, area=f.Area()))
    return out


def volume_mm3(shape: cq.Shape) -> float:
    total = 0.0
    for s in shape.Solids():
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(s.wrapped, g)
        total += g.Mass()
    return total


def sample_points(shape: cq.Shape, tol=0.3) -> np.ndarray:
    verts, _ = shape.tessellate(tol, 0.3)
    return np.array([v.toTuple() for v in verts])


# ---------------------------------------------------------------- assembly reader
def read_assembly(path: Path):
    doc = TDocStd_Document(TCollection_ExtendedString("so101"))
    r = STEPCAFControl_Reader()
    r.SetNameMode(True)
    r.ReadFile(str(path))
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def name(lab):
        n = TDataStd_Name()
        return n.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), n) else "?"

    free = TDF_LabelSequence()
    st.GetFreeShapes(free)
    root = free.Value(1)
    ref = root
    kids = TDF_LabelSequence()
    st.GetComponents_s(ref, kids)
    parts = {}
    for i in range(1, kids.Length() + 1):
        k = kids.Value(i)
        parts[name(k)] = cq.Shape.cast(st.GetShape_s(k))  # located (world) shape
    return parts


# ---------------------------------------------------------------- 1. stock gripper part
def follower_features():
    shp = cq.importers.importStep(str(HERE / "Wrist_Roll_Follower_SO101.step")).val()
    bb = shp.BoundingBox()
    cyl = cylinders(shp)
    # the part file's own frame: z = 0 is the horn mating face, +z toward the jaw tip
    near = [c for c in cyl if abs(abs(c["axis"][2]) - 1) < 1e-3 and np.hypot(*c["p0"][:2]) < 16
            and c["pts"][:, 2].min() < 12]
    rows = []
    for c in near:
        rows.append(dict(d=round(c["d"], 2), x=round(c["p0"][0], 2), y=round(c["p0"][1], 2),
                         z0=round(c["pts"][:, 2].min(), 2), z1=round(c["pts"][:, 2].max(), 2),
                         kind=c["kind"], span_deg=round(c["span"])))
    rows.sort(key=lambda r: (r["d"], r["x"], r["y"], r["z0"]))
    m3 = [r for r in rows if abs(r["d"] - 3.2) < 0.05]
    cx = float(np.mean([r["x"] for r in m3])) if m3 else float("nan")
    cy = float(np.mean([r["y"] for r in m3])) if m3 else float("nan")
    # planar faces facing -z at the bottom (mating) -> contact footprint
    mating = []
    for f in shp.Faces():
        a = BRepAdaptor_Surface(f.wrapped)
        if a.GetType() != GeomAbs_Plane:
            continue
        fb = f.BoundingBox()
        if fb.zmax < 1.5 and abs(fb.zmax - fb.zmin) < 1e-3:
            mating.append(dict(z=round(fb.zmin, 2), area=round(f.Area(), 1),
                               x=(round(fb.xmin, 1), round(fb.xmax, 1)),
                               y=(round(fb.ymin, 1), round(fb.ymax, 1))))
    # motor-6 cradle M2 holes and M3 hex-nut (camera) holes, axis along part Y
    side = [c for c in cyl if abs(abs(c["axis"][1]) - 1) < 1e-3 and c["d"] < 4.5]
    side_rows = sorted({(round(c["d"], 2), round(c["p0"][0], 2), round(c["p0"][2], 2), c["kind"])
                        for c in side})
    return dict(bbox=[round(v, 2) for v in (bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax)],
                volume_cm3=round(volume_mm3(shp) / 1000, 2),
                horn_face_features=rows, m3_pattern_center=(round(cx, 2), round(cy, 2)),
                mating_planes=mating, side_holes=side_rows)


# ---------------------------------------------------------------- 2. assembly interface frame
def interface_frame(parts):
    fol = next(v for k, v in parts.items() if k.startswith("Wrist_Roll_Follower"))
    cyl = cylinders(fol)
    m3 = [c for c in cyl if abs(c["d"] - 3.2) < 0.05]
    # group by axis direction; the horn pattern is 4 parallel holes forming a square
    best = None
    for c in m3:
        grp = [o for o in m3 if abs(abs(np.dot(o["axis"], c["axis"])) - 1) < 1e-4]
        if len(grp) >= 4:
            best = grp
            break
    ax = best[0]["axis"] / np.linalg.norm(best[0]["axis"])
    # unique hole axes (a hole may be split into several faces)
    cents = []
    for o in best:
        p = o["p0"] - np.dot(o["p0"], ax) * ax
        if not any(np.linalg.norm(p - q) < 0.5 for q in cents):
            cents.append(p)
    cents = np.array(cents)
    ctr_perp = cents.mean(axis=0)
    fol_pts = sample_points(fol)
    # +Z points from motor 5 toward the gripper: the follower body lies on +Z side
    s = fol_pts @ ax
    servo5 = parts["ST3215 Servo v2:5"]
    s5 = sample_points(servo5) @ ax
    if np.median(s5) > np.median(s):
        ax = -ax
        s = -s
    z0 = s.min()  # mating plane = lowest follower point along the axis
    origin = ctr_perp + z0 * ax
    ex = cents[1] - cents[0]
    ex -= np.dot(ex, ax) * ax
    ex /= np.linalg.norm(ex)
    ey = np.cross(ax, ex)
    R = np.vstack([ex, ey, ax])  # world -> I rows

    def to_I(p):
        return (np.atleast_2d(p) - origin) @ R.T

    return fol, origin, R, to_I, to_I(cents + z0 * ax)


def envelope(pts_I, zlo, zhi):
    m = (pts_I[:, 2] >= zlo) & (pts_I[:, 2] <= zhi)
    if not m.any():
        return None
    p = pts_I[m]
    r = np.hypot(p[:, 0], p[:, 1])
    return dict(n=int(m.sum()), r_min=round(float(r.min()), 2), r_max=round(float(r.max()), 2),
                x=(round(float(p[:, 0].min()), 1), round(float(p[:, 0].max()), 1)),
                y=(round(float(p[:, 1].min()), 1), round(float(p[:, 1].max()), 1)),
                z=(round(float(p[:, 2].min()), 1), round(float(p[:, 2].max()), 1)))


def assembly_report(parts):
    fol, origin, R, to_I, holes_I = interface_frame(parts)
    out = {"horn_screw_holes_I": [[round(v, 2) for v in h] for h in holes_I]}
    names = {
        "motor5_ST3215": "ST3215 Servo v2:5",
        "motor6_ST3215": "ST3215 Servo v2:6",
    }
    for k, v in parts.items():
        if k.startswith("Wrist_Roll_Pitch"):
            names["wrist_roll_pitch"] = k
        if k.startswith("Moving_Jaw"):
            names["moving_jaw"] = k
        if k.startswith("Wrist_Roll_Follower"):
            names["follower"] = k
        if k.startswith("Motor_holder_SO101_Wrist"):
            names["motor4_holder"] = k
    pts = {key: to_I(sample_points(parts[n])) for key, n in names.items()}
    env = {}
    for key, p in pts.items():
        env[key] = dict(all=envelope(p, -1e9, 1e9))
    # stationary side (does NOT roll with the gripper): wrist_roll_pitch + motor 5
    for key in ("wrist_roll_pitch", "motor5_ST3215"):
        env[key]["beyond_mating_plane"] = envelope(pts[key], -0.01, 1e9)
        env[key]["band_-5_0"] = envelope(pts[key], -5, 0)
        env[key]["band_-15_-5"] = envelope(pts[key], -15, -5)
        env[key]["band_-30_-15"] = envelope(pts[key], -30, -15)
    out["envelopes_I"] = env
    # stock rolling gripper (follower + motor 6 + moving jaw) envelope by axial band:
    # a proven-clear envelope for wrist roll and wrist flex motion
    stock = np.vstack([pts["follower"], pts["motor6_ST3215"], pts["moving_jaw"]])
    out["stock_gripper_bands_I"] = {f"{a}..{b}": envelope(stock, a, b)
                                    for a, b in ((0, 6), (6, 12), (12, 25), (25, 40), (40, 60), (60, 80), (80, 110))}
    # horn: off-axis holes on the motor-5 model within 3 mm of the mating plane
    hh = []
    for c in cylinders(parts["ST3215 Servo v2:5"]):
        a = c["axis"] @ R.T
        if abs(abs(a[2]) - 1) > 1e-3:
            continue
        pI = to_I(c["p0"])[0]
        rr = float(np.hypot(pI[0], pI[1]))
        zs = to_I(c["pts"])[:, 2]
        if 2 < rr < 12 and zs.max() > -4:
            hh.append((round(c["d"], 2), c["kind"], round(float(pI[0]), 2), round(float(pI[1]), 2),
                       round(float(zs.min()), 2), round(float(zs.max()), 2)))
    out["motor5_offaxis_cylinders_I"] = sorted(set(hh))
    # planar faces of motor 5 perpendicular to the roll axis (horn top, case top)
    pl = []
    for f in parts["ST3215 Servo v2:5"].Faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() != GeomAbs_Plane:
            continue
        nrm = ad.Plane().Axis().Direction()
        nI = np.array([nrm.X(), nrm.Y(), nrm.Z()]) @ R.T
        if abs(abs(nI[2]) - 1) > 1e-3:
            continue
        vz = to_I(np.array([v.toTuple() for v in f.Vertices()]))
        if vz[:, 2].max() > -8 and f.Area() > 5:
            pl.append((round(float(vz[:, 2].mean()), 2), round(f.Area(), 1),
                       round(float(np.hypot(vz[:, 0], vz[:, 1]).max()), 1)))
    out["motor5_planes_I(z,area,rmax)"] = sorted(set(pl))
    # horn: motor-5 cylinders coaxial with the roll axis near the mating plane
    s5 = parts["ST3215 Servo v2:5"]
    horn = []
    for c in cylinders(s5):
        a = c["axis"] @ R.T
        if abs(abs(a[2]) - 1) > 1e-3:
            continue
        pI = to_I(c["p0"])[0]
        if np.hypot(pI[0], pI[1]) > 1.0:
            continue
        zs = to_I(c["pts"])[:, 2]
        horn.append((round(c["d"], 2), c["kind"], round(float(zs.min()), 2), round(float(zs.max()), 2)))
    out["motor5_coaxial_cylinders_I"] = sorted(set(horn))
    # screws: M3x6 pan heads whose centre lies within 12 mm of the axis and near the plane
    scr = []
    for k, v in parts.items():
        if "M3 x 6" in k or "1-42" in k or "0-48" in k:
            c = to_I(np.array(v.Center().toTuple()))[0]
            if abs(c[2]) < 15 and np.hypot(c[0], c[1]) < 30:
                scr.append((k.split(" v1:")[0][:40] + " #" + k.split(":")[-1],
                            [round(float(x), 2) for x in c]))
    out["screws_near_interface_I"] = scr
    # motor 6 (stock gripper servo) axis in I: from its coaxial horn cylinders
    s6c = [c for c in cylinders(parts["ST3215 Servo v2:6"]) if abs(c["d"] - 5.9) < 0.6 or abs(c["d"] - 20) < 3]
    if s6c:
        a6 = (s6c[0]["axis"] @ R.T)
        out["motor6_axis_dir_I"] = [round(float(x), 3) for x in a6]
    out["roll_clearance_I"] = roll_clearance(pts)
    return out


def roll_clearance(pts):
    """Keep-out for a part that rolls with the horn: stationary material (wrist link
    and motor-5 case, horn excluded) per 1 mm axial band. A rolling body inside
    r < r_min of a band clears the stationary side through any roll angle."""
    s5 = pts["motor5_ST3215"]
    r5 = np.hypot(s5[:, 0], s5[:, 1])
    horn = (r5 < 10.0) & (s5[:, 2] > -3.7)  # horn disk + screw rotate with the gripper
    stat = np.vstack([pts["wrist_roll_pitch"], s5[~horn]])
    rows = {}
    for z in np.arange(-6.0, 8.0, 1.0):
        m = (stat[:, 2] >= z) & (stat[:, 2] < z + 1)
        if not m.any():
            rows[f"{z:+.0f}..{z + 1:+.0f}"] = None
            continue
        p = stat[m]
        r = np.hypot(p[:, 0], p[:, 1])
        ang = np.degrees(np.arctan2(p[:, 1], p[:, 0]))
        near = ang[r < r.min() + 3]
        rows[f"{z:+.0f}..{z + 1:+.0f}"] = dict(r_min=round(float(r.min()), 2),
                                             ang_deg_near_rmin=(round(float(near.min())), round(float(near.max()))))
    return rows


# ---------------------------------------------------------------- 3. part masses
def part_masses():
    res = {}
    for fn in ("Wrist_Roll_Follower_SO101.step", "Moving_Jaw_SO101.step",
               "Wrist_Roll_Pitch_SO101.step", "Motor_holder_SO101_Wrist.step"):
        shp = cq.importers.importStep(str(HERE / fn)).val()
        v = volume_mm3(shp) / 1000.0
        res[fn] = dict(volume_cm3=round(v, 2), solid_PLA_g=round(v * PLA, 1))
    return res


# ---------------------------------------------------------------- 4. URDF statics
def rpy_to_R(r, p, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


def urdf_statics(path: Path, q=None):
    root = ET.parse(path).getroot()
    links = {}
    for l in root.findall("link"):
        i = l.find("inertial")
        if i is None:
            continue
        o = i.find("origin")
        links[l.get("name")] = dict(m=float(i.find("mass").get("value")),
                                    com=np.array([float(x) for x in o.get("xyz").split()]))
    joints = {}
    for j in root.findall("joint"):
        o = j.find("origin")
        ax = j.find("axis")
        joints[j.get("name")] = dict(parent=j.find("parent").get("link"), child=j.find("child").get("link"),
                                     xyz=np.array([float(x) for x in o.get("xyz").split()]),
                                     rpy=[float(x) for x in o.get("rpy").split()],
                                     axis=np.array([float(x) for x in ax.get("xyz").split()]) if ax is not None else np.zeros(3),
                                     type=j.get("type"))
    q = q or {}
    children = {j["child"] for j in joints.values()}
    root_link = next(j["parent"] for j in joints.values() if j["parent"] not in children)
    T = {root_link: np.eye(4)}
    jworld = {}
    changed = True
    while changed:
        changed = False
        for n, j in joints.items():
            if j["parent"] in T and j["child"] not in T:
                A = np.eye(4)
                A[:3, :3] = rpy_to_R(*j["rpy"])
                A[:3, 3] = j["xyz"]
                Tj = T[j["parent"]] @ A
                Rq = np.eye(4)
                if j["type"] == "revolute" and n in q:
                    k = j["axis"] / np.linalg.norm(j["axis"])
                    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
                    Rq[:3, :3] = np.eye(3) + math.sin(q[n]) * K + (1 - math.cos(q[n])) * K @ K
                T[j["child"]] = Tj @ Rq
                jworld[n] = (Tj[:3, 3].copy(), Tj[:3, :3] @ j["axis"])
                changed = True
    com_w = {n: (T[n] @ np.append(l["com"], 1))[:3] for n, l in links.items() if n in T}
    return links, joints, T, jworld, com_w


KGCM = 0.0980665  # N*m per kg*cm
# servo torque ratings, kg*cm (see docs/gripper/research/so101.md for sources)
SERVO = {
    "C001_6V_README": dict(stall=16.5),         # SO-ARM100 README: 16.5 kg*cm at 6 V (kit runs on 5 V)
    "C001_7.4V": dict(stall=19.5, rated=5.0),   # vendor listing (openelab), 7.4 V
    "C018_12V": dict(stall=30.0, rated=10.0),   # Feetech datasheet ST-3215-C018
}
# gripper_frame (TCP) offset in the gripper link, from so101_new_calib.urdf
TCP_IN_GRIPPER = np.array([-0.0079, -0.000218121, -0.0981274])


def payload_report():
    links, joints, T, jw, com = urdf_statics(HERE / "so101_old_calib.urdf")
    order = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
    pos = {n: jw[n][0] for n in order}
    child = {n: joints[n]["child"] for n in order}
    tcp = (T[child["wrist_roll"]] @ np.append(TCP_IN_GRIPPER, 1))[:3]
    seg = {}
    seq = order[1:5]
    for a, b in zip(seq, seq[1:]):
        d = pos[b] - pos[a]
        seg[f"{a}->{b}"] = dict(total=round(float(np.linalg.norm(d)) * 1000, 2),
                                horizontal=round(float(np.hypot(d[0], d[1])) * 1000, 2),
                                vertical=round(float(d[2]) * 1000, 2))
    d = tcp - pos["wrist_roll"]
    seg["wrist_roll(flange)->TCP"] = dict(total=round(float(np.linalg.norm(d)) * 1000, 2))
    g = np.array([0, 0, -G])
    chain = [child[n] for n in ("shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")]
    distal = {"shoulder_lift": chain, "elbow_flex": chain[1:], "wrist_flex": chain[2:]}
    roll_dir = jw["wrist_roll"][1] / np.linalg.norm(jw["wrist_roll"][1])
    if np.dot(tcp - pos["wrist_roll"], roll_dir) < 0:
        roll_dir = -roll_dir  # point from motor 5 toward the TCP
    PAYLOAD_OFFSET = 0.040  # m beyond the flange along the roll axis (assumed gripper COM)
    p_pay = pos["wrist_roll"] + PAYLOAD_OFFSET * roll_dir
    tau = {}
    for jn, ls in distal.items():
        p, a = jw[jn]
        a = a / np.linalg.norm(a)
        t = lambda l: float(np.dot(np.cross(com[l] - p, links[l]["m"] * g), a))
        t_arm = sum(t(l) for l in ls[:-2])
        t_grip = sum(t(l) for l in ls[-2:])
        lev = lambda q: abs(float(np.dot(np.cross(q - p, g / G), a)))  # horizontal lever about joint axis
        row = dict(arm_only_Nm=round(abs(t_arm), 4), stock_gripper_Nm=round(abs(t_grip), 4),
                   lever_to_flange_mm=round(lev(pos["wrist_roll"]) * 1000, 1),
                   lever_to_payload_point_mm=round(lev(p_pay) * 1000, 1),
                   axis_world=[round(float(x), 3) for x in a])
        for key, sv in SERVO.items():
            for lim in ("rated", "stall"):
                if lim not in sv:
                    continue
                avail = sv[lim] * KGCM - abs(t_arm)
                row[f"max_gripper_g_{key}_{lim}"] = round(max(avail, 0) / (G * lev(p_pay)) * 1000, 0)
        tau[jn] = row
    masses = {n: round(l["m"] * 1000, 1) for n, l in links.items()}
    zpose = {n: [round(float(x) * 1000, 1) for x in pos[n]] for n in order}
    gl = links[child["wrist_roll"]]
    return dict(segment_lengths_mm=seg, link_masses_g=masses, joint_positions_zero_pose_mm=zpose,
                tcp_zero_pose_mm=[round(float(x) * 1000, 1) for x in tcp], static_torque_zero_pose=tau,
                gripper_link_com_in_link_mm=[round(float(x) * 1000, 2) for x in gl["com"]],
                servo_ratings_kgcm=SERVO, roll_axis_world=[round(float(x), 4) for x in roll_dir],
                payload_point_offset_mm=PAYLOAD_OFFSET * 1000)


def main():
    rep = {}
    rep["follower_part"] = follower_features()
    rep["part_masses"] = part_masses()
    parts = read_assembly(HERE / "SO101 Assembly.step")
    rep["assembly"] = assembly_report(parts)
    rep["payload"] = payload_report()
    txt = json.dumps(rep, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    import sys
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
