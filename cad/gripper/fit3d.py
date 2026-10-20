#!/usr/bin/env python3
"""3D fit audit for the review page: clearances and interferences over the full jaw travel and the wrist roll.

fitcheck.py answers pass or fail at five jaw angles with boolean volumes. This script measures how close
things get, and where, so the page can draw each gap as a line with its value:

  1. jaw travel -11..+20 deg in 1 deg steps (plus the -7.4 deg firmware floor): BRep minimum distance and the
     two closest points between every moving part and every static part, and between side A and side B
     (gear pair and pad stack kept apart because they touch or overlap by design); intersection volume
     wherever the distance is zero;
  2. static parts against each other, fastener item by fastener item: intersection volume, classed as a
     press fit by design or as a modelling error;
  3. wrist roll 0..350 deg in 10 deg steps: true 3D minimum distance and closest points between the gripper
     and the stationary wrist link and servo 5 (fitcheck.py treats the stationary parts as a full ring, which
     is conservative);
  4. the margin of every value against its requirement.

Everything is in frame G (README), mm. Writes out/fit3d.json, which viewer_build.py embeds.

    uv run --with cadquery python cad/gripper/fit3d.py
"""
from __future__ import annotations

import json
import math
import os
import re
import argparse
import sys
import time
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepAdaptor import BRepAdaptor_Surface

HERE = Path(__file__).resolve().parent
SO = HERE.parent / "so101"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SO))
sys.path.insert(0, str(HERE / "viewer_src"))
import gripper_concept as gc  # noqa: E402
from fit3d_inputs import input_digest, parse_basis, kernel_versions, result_hash, validate_result  # noqa: E402

THETAS = sorted(set([float(t) for t in range(-11, 21)] + [-7.4]))
ROLLS = [float(r) for r in range(0, 360, 10)]
NEAR = 8.0  # pairs whose boxes are further apart than this are reported as "more than 8 mm"
STATIC = ["housing", "front_plate", "wrist_mount", "servo", "fasteners"]
MOV_A = ["knuckle_a", "finger_a", "nail_a", "fasteners_a", "horn"]
MOV_B = ["knuckle_b", "finger_b", "fsr_backing_b", "fsr_sensor_b", "fsr_puck_b", "fasteners_b"]
PAD_A, PAD_B = {"finger_a", "nail_a"}, {"finger_b", "fsr_backing_b", "fsr_sensor_b", "fsr_puck_b"}
# the servo horn turns with knuckle A on the servo shaft (pivot A); gripper_concept keeps it unposed because a disc
# looks the same at any angle, but its dog pins (fasteners_a) do turn, so it is posed with side A here.
SIDE = dict(gc.SIDE, horn="A")

_W = {}


def r3(v):
    return [round(float(x), 2) for x in v]


def bbox_gap(a, b):
    A, B = a.BoundingBox(), b.BoundingBox()
    dx = max(0.0, A.xmin - B.xmax, B.xmin - A.xmax)
    dy = max(0.0, A.ymin - B.ymax, B.ymin - A.ymax)
    dz = max(0.0, A.zmin - B.zmax, B.zmin - A.zmax)
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def dist(a, b):
    """(distance, point on a, point on b) by BRepExtrema."""
    d = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    d.Perform()
    if not d.IsDone() or d.NbSolution() < 1:
        return None
    p, q = d.PointOnShape1(1), d.PointOnShape2(1)
    return float(d.Value()), [p.X(), p.Y(), p.Z()], [q.X(), q.Y(), q.Z()]


def vol(s):
    try:
        return float(s.Volume())
    except Exception:
        return 0.0


def inter(a, b):
    try:
        return vol(a.intersect(b))
    except Exception:
        return 0.0


def pose(shape, side, G, theta):
    ang = -theta if side == "A" else theta
    px = -G.a / 2 if side == "A" else G.a / 2
    s = shape.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), ang) if ang else shape
    return s.translate(cq.Vector(px, 0, 0))


def world(parts, G, theta):
    # the horn is built at its world place, so it is moved back to pivot A, posed, and returned
    out = {}
    for n, s in parts.items():
        if n == "horn":
            out[n] = pose(s.translate(cq.Vector(G.a / 2, 0, 0)), "A", G, theta)
        elif n in SIDE:
            out[n] = pose(s, SIDE[n], G, theta)
        else:
            out[n] = s
    return out


def pair_row(a_name, a, b_name, b):
    g = bbox_gap(a, b)
    if g > NEAR:
        return {"a": a_name, "b": b_name, "d": None, "far": True}
    r = dist(a, b)
    if r is None:
        return {"a": a_name, "b": b_name, "d": None}
    d, p, q = r
    row = {"a": a_name, "b": b_name, "d": round(d, 3), "p": r3(p), "q": r3(q)}
    if d < 1e-4:
        row["v"] = round(inter(a, b), 3)
    return row


def _init():
    P = json.loads((HERE / "params.json").read_text(encoding="utf-8"))
    G, parts, info = gc.build(P)
    _W["P"], _W["G"], _W["parts"], _W["info"] = P, G, parts, info


def jaw_task(theta):
    if not _W:
        _init()
    G, parts = _W["G"], _W["parts"]
    W = world(parts, G, theta)
    rows = []
    for m in MOV_A + MOV_B:
        for s in STATIC:
            rows.append(pair_row(m, W[m], s, W[s]))
    for a in MOV_A:
        for b in MOV_B:
            rows.append(pair_row(a, W[a], b, W[b]))
    return theta, rows


def static_task(_):
    if not _W:
        _init()
    G, parts = _W["G"], _W["parts"]
    W = world(parts, G, 0.0)
    items = []
    for n in STATIC:
        if n == "fasteners":
            for (nm, _mat), c in zip(gc.FAST_ITEMS["fasteners"], gc.children(W[n])):
                items.append((nm, c))
        else:
            items.append((n, W[n]))
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            na, a = items[i]
            nb, b = items[j]
            if bbox_gap(a, b) > 0.05:
                continue
            v = inter(a, b)
            if v > 1e-3:
                bb = a.intersect(b).BoundingBox()
                row = {"a": na, "b": nb, "v": round(v, 3),
                       "at": r3([(bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2, (bb.zmin + bb.zmax) / 2])}
                if (na, nb) == ("housing", "servo"):
                    bore = gc.cyl_z(-G.a / 2, 0, _W["P"]["housing"]["boss_bore_ream"] / 2,
                                    G.zw0 - 0.01, G.zw1 + 0.01)
                    row["finished_v"] = round(inter(a.cut(bore), b), 3)
                out.append(row)
    return out


def _init_roll():
    _init()
    stat_I, I_to_G, _ctx = load_stationary()
    _W["stat"] = {n: I_to_G(s) for n, s in stat_I.items()}


def roll_task(args):
    """Stationary wrist parts in frame G turned by -psi about the roll axis (x 0, z 0, along Y), against the gripper at the jaw angle given."""
    psi, theta = args
    if not _W:
        _init()
    G, parts = _W["G"], _W["parts"]
    W = world(parts, G, theta)
    stat = _W["stat"]
    rows = []
    for sn, s in stat.items():
        sr = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -psi)
        best = None
        for gn, g in W.items():
            if bbox_gap(g, sr) > NEAR:
                continue
            r = dist(g, sr)
            if r and (best is None or r[0] < best["d"]):
                best = {"a": gn, "b": sn, "d": round(r[0], 3), "p": r3(r[1]), "q": r3(r[2])}
        if best:
            rows.append(best)
    return psi, theta, rows


def load_stationary():
    """Wrist_Roll_Pitch and the servo-5 body in frame G, by the same map as viewer_src/so101_mesh.py (so the page's context mesh lines up)."""
    import measure_interface as mi
    from OCP.gp import gp_Trsf, gp_Ax3, gp_Pnt, gp_Dir
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    asm = mi.read_assembly(SO / "SO101 Assembly.step")
    fol, origin, R, to_I, holes_I = mi.interface_frame(asm)
    ctx = json.loads((HERE / "viewer_src" / "so101_context.json").read_text(encoding="utf-8"))
    phi = math.radians(ctx["phi_deg"])
    YH = json.loads((HERE / "out" / "parts.json").read_text(encoding="utf-8"))["Y_H"]  # the CAD's horn face, not the context file's

    def to_I_shape(shape):
        ax = gp_Ax3(gp_Pnt(*map(float, origin)), gp_Dir(*map(float, R[2])), gp_Dir(*map(float, R[0])))
        t = gp_Trsf()
        t.SetTransformation(ax)
        return cq.Shape.cast(BRepBuilderAPI_Transform(shape.wrapped, t, True).Shape())

    def I_to_G(s):
        # so101_mesh.toG: turn by phi about Z_I, then (x, y, z) -> (x, -z, y), then lift by YH + 1
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), math.degrees(phi))
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 90)
        return s.translate(cq.Vector(0, YH + 1.0, 0))
    stat = {}
    for k in asm:
        if k.startswith("Wrist_Roll_Pitch"):
            stat["wrist_link"] = asm[k]
    stat["arm_servo"] = asm["ST3215 Servo v2:5"]
    out = {}
    BIG = 400.0
    for n, s in stat.items():
        sI = to_I_shape(s)
        if n == "arm_servo":  # its horn and spline roll with the gripper, so only the case below z_I -3.8 is stationary
            sI = sI.intersect(cq.Solid.makeBox(2 * BIG, 2 * BIG, BIG, cq.Vector(-BIG, -BIG, -3.8 - BIG)))
        out[n] = sI
    return out, I_to_G, ctx


def check_map(stat_I, I_to_G, ctx):
    """The frame map must reproduce the context mesh's bounding box to 0.1 mm."""
    sG = I_to_G(stat_I["wrist_link"])
    bb = sG.BoundingBox()
    ref = ctx["parts"]["wrist_roll_pitch"]["bbox"]
    got = [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax]
    return max(abs(a - b) for a, b in zip(got, ref)), got, ref


# ---------------------------------------------------------------- extras for the page: one detail record per finding
# Everything below reads the jaw, static and roll results above and adds what the page needs to show a fit, not just
# list it: a section cut through the two closest points, the faces near the other part coloured by distance, each
# overlap as its own solid, the gap at worst case under the stated tolerances, and the insertion path of the parts
# that cannot be fitted as drawn.
import base64  # noqa: E402
import re  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section  # noqa: E402
from OCP.gp import gp_Pln, gp_Pnt, gp_Dir  # noqa: E402
from OCP.TopExp import TopExp_Explorer  # noqa: E402
from OCP.TopAbs import TopAbs_EDGE  # noqa: E402
from OCP.TopoDS import TopoDS  # noqa: E402
from OCP.BRepAdaptor import BRepAdaptor_Curve  # noqa: E402
from OCP.GCPnts import GCPnts_QuasiUniformDeflection  # noqa: E402

ROOT = HERE.parent.parent
TIGHT = 0.5          # the page flags a running gap under this for review (unchanged from the previous page)
NEAR_T = 1.0         # faces closer than this to the other part are coloured by distance, mm
WIN = 6.0            # half-width of the section window kept around a finding, mm


def static_intent(row, declarations):
    key = row["a"] + "|" + row["b"]
    intent = declarations.get(key)
    if intent is None:
        return "error", "no declared interface intent", None
    area = math.pi / 4 * max(0.0, intent["pin_mm"] ** 2 - intent["hole_printed_mm"] ** 2)
    expected = area * intent["engagement_mm"]
    if abs(row["v"] - expected) > 0.01:
        return "error", f"measured overlap {row['v']} differs from declared {expected:.3f} mm³", intent
    finished_area = math.pi / 4 * max(0.0, intent["pin_mm"] ** 2 - intent["hole_finished_mm"] ** 2)
    finished = finished_area * intent["engagement_mm"]
    if row.get("finished_v", round(finished, 3)) > 0.01 and intent["intent"] != "self-tapping":
        return "error", "finished interface still overlaps", intent
    return "design", f"{intent['intent']}: {intent['feature']} ({intent['source']})", intent


def basis():
    """name -> {value, tag, source} from the tolerance stacks' own basis file (only the {value: ...} constants)."""
    # Optional fields between tag and source (`cad:`, `cad_derived:`, the CAD bindings the tolerance tests check) are skipped.
    return parse_basis((ROOT / "analysis/gripper/tolstack/stacks/basis.yaml").read_text(encoding="utf-8"))


def b64(arr, dtype):
    return base64.b64encode(np.asarray(arr, dtype=dtype).tobytes()).decode()


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def section_polys(shape, origin, m, u, v, win):
    """Cut a solid by the plane through origin with normal m; edges as 2D polylines in (u, v), mm, clipped to the window."""
    sec = BRepAlgoAPI_Section(shape.wrapped, gp_Pln(gp_Pnt(*map(float, origin)), gp_Dir(*map(float, m))), False)
    sec.Approximation(True)
    sec.Build()
    if not sec.IsDone():
        return []
    polys = []
    ex = TopExp_Explorer(sec.Shape(), TopAbs_EDGE)
    while ex.More():
        e = TopoDS.Edge_s(ex.Current())
        ad = BRepAdaptor_Curve(e)
        try:
            dfl = GCPnts_QuasiUniformDeflection(ad, 0.002)
            pts = [ad.Value(dfl.Parameter(i)) for i in range(1, dfl.NbPoints() + 1)] if dfl.IsDone() else []
        except Exception:
            pts = []
        cur = []
        P = np.array([[p.X(), p.Y(), p.Z()] for p in pts]) - origin if pts else np.zeros((0, 3))
        if len(P) > 1:  # a straight edge comes back as its two ends; fill it in so the part inside the window survives the clip
            seg = [P[:1]]
            for a0, a1 in zip(P[:-1], P[1:]):
                k = max(1, int(np.ceil(np.linalg.norm(a1 - a0) / 0.05)))
                seg.append(a0 + (a1 - a0) * (np.arange(1, k + 1) / k)[:, None])
            P = np.vstack(seg)
        for w in P:
            a, b = float(w @ u), float(w @ v)
            if abs(a) <= win and abs(b) <= win:
                cur.append([round(a, 4), round(b, 4)])
            elif cur:
                if len(cur) > 1:
                    polys.append(cur)
                cur = []
        if len(cur) > 1:
            polys.append(cur)
        ex.Next()
    return [rdp(c, 0.0005) for c in polys]


def rdp(pts, eps):
    """Drop points that lie on the line through their neighbours, within eps mm."""
    if len(pts) < 3:
        return pts
    P = np.array(pts)
    a, b = P[0], P[-1]
    d = b - a
    L = np.hypot(*d)
    dist = np.abs(d[0] * (P[:, 1] - a[1]) - d[1] * (P[:, 0] - a[0])) / L if L > 1e-12 else np.hypot(*(P - a).T)
    i = int(dist.argmax())
    if dist[i] <= eps:
        return [pts[0], pts[-1]]
    return rdp(pts[: i + 1], eps)[:-1] + rdp(pts[i:], eps)


def seg_dist(P, Q):
    """Smallest distance between two sets of 2D polylines."""
    best = 1e9
    A = [np.array(p) for p in P]
    B = [np.array(q) for q in Q]
    for a in A:
        for b in B:
            for s in (a, b):
                o = b if s is a else a
                if len(o) < 2:
                    continue
                p0, p1 = o[:-1], o[1:]
                d = p1 - p0
                L = np.maximum((d * d).sum(1), 1e-12)
                for x in s[:: max(1, len(s) // 400)]:
                    t = np.clip(((x - p0) * d).sum(1) / L, 0, 1)
                    c = p0 + d * t[:, None]
                    best = min(best, float(np.sqrt(((c - x) ** 2).sum(1)).min()))
    return best


def make_section(A, B, p, q, d3, extra=None, n_hint=None, normals=None):
    """Section through the two closest points. The in-plane u axis runs along the gap, so the inset reads it left to right.
    The plane normal is the first of Z, Y, X lying across the gap; it is nudged off any face it would lie in, and the
    nudge that reproduces the 3D gap in 2D is kept. Where the parts touch, the gap direction comes from n_hint."""
    p, q = np.asarray(p, float), np.asarray(q, float)
    mid = (p + q) / 2
    n = unit(q - p) if d3 > 1e-4 else (unit(n_hint) if n_hint is not None else None)
    best = None
    axes = [np.array([0, 0, 1.0]), np.array([0, 1.0, 0]), np.array([1.0, 0, 0])]
    cands = [ax for ax in axes if n is None or abs(ax @ n) <= 0.3]
    if n is not None:  # an oblique gap: planes that contain the gap and the principal axis it is least aligned with
        cands += [unit(np.cross(n, ax)) for ax in sorted(axes, key=lambda a: abs(a @ n))]
    if normals is not None:
        cands = [unit(x) for x in normals] + cands
    cands = [ax for ax in cands if np.linalg.norm(ax) > 0.5]  # a cross product with a parallel axis has no direction
    for ax in cands:
        m = ax
        u = unit(n - (n @ m) * m) if n is not None else (np.array([1.0, 0, 0]) if abs(m[0]) < 0.9 else np.array([0, 1.0, 0]))
        v = np.cross(m, u)
        for off in (0.15, -0.15, 0.4, -0.4, 0.0, 0.8, -0.8):
            o = mid + m * off
            pa, pb = section_polys(A, o, m, u, v, WIN), section_polys(B, o, m, u, v, WIN)
            if not pa or not pb:
                continue
            d2 = seg_dist(pa, pb)
            err = abs(d2 - d3)
            if best is None or err < best[0] - 1e-4:
                best = (err, o, m, u, v, pa, pb, d2)
            if err < max(0.01, 0.05 * d3):
                break
        if best and best[0] < max(0.01, 0.05 * d3):
            break
    if not best:
        return None
    err, o, m, u, v, pa, pb, d2 = best
    out = {"o": r3(o), "m": r3(m), "u": [round(float(x), 4) for x in u], "v": [round(float(x), 4) for x in v], "win": WIN,
           "a": pa, "b": pb, "d2": round(d2, 3), "p2": [round(float((p - o) @ u), 4), round(float((p - o) @ v), 4)],
           "q2": [round(float((q - o) @ u), 4), round(float((q - o) @ v), 4)]}
    if extra is not None:
        out["x"] = section_polys(extra, o, m, u, v, WIN)
    return out


def tri_mesh(shape, tol=0.02, ang=0.2):
    vs, ts = shape.tessellate(tol, ang)
    return np.array([[x.x, x.y, x.z] for x in vs], float), np.array(ts, np.int64).reshape(-1, 3)


def subdivide(V, T, h):
    """Split triangles across their longest edge until no edge is longer than h, so per-vertex colours can show a
    distance field. Vectorised: one split per level for every triangle still too long; shared vertices merged at the end."""
    P = V[T]
    done = []
    for _ in range(40):
        L = np.linalg.norm(P[:, [1, 2, 0]] - P, axis=2)  # edge i runs from vertex i to vertex i + 1
        ok = L.max(1) <= h
        done.append(P[ok])
        P, L = P[~ok], L[~ok]
        if not len(P):
            break
        i = L.argmax(1)
        Q = np.take_along_axis(P, ((np.arange(3)[None, :] + i[:, None]) % 3)[:, :, None], axis=1)  # longest edge first
        M = (Q[:, 0] + Q[:, 1]) / 2
        P = np.concatenate([np.stack([Q[:, 0], M, Q[:, 2]], 1), np.stack([M, Q[:, 1], Q[:, 2]], 1)])
    P = np.concatenate(done + [P])
    Vs, inv = np.unique(np.round(P.reshape(-1, 3), 5), axis=0, return_inverse=True)
    return Vs, inv.reshape(-1, 3).astype(np.int64)


def point_tri_dist(Pts, V, T):
    """Exact distance from each point to the nearest triangle (Ericson, closest point on triangle), chunked."""
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    AB, AC = B - A, C - A
    out = np.full(len(Pts), np.inf)
    step = max(1, int(2.0e5 // max(1, len(T))))
    for s in range(0, len(Pts), step):
        P = Pts[s:s + step][:, None, :]
        AP = P - A
        d1, d2 = (AB * AP).sum(-1), (AC * AP).sum(-1)
        BP = P - B
        d3, d4 = (AB * BP).sum(-1), (AC * BP).sum(-1)
        CP = P - C
        d5, d6 = (AB * CP).sum(-1), (AC * CP).sum(-1)
        va = d3 * d6 - d5 * d4
        vb = d5 * d2 - d1 * d6
        vc = d1 * d4 - d3 * d2
        den = np.where(np.abs(va + vb + vc) < 1e-18, 1e-18, va + vb + vc)
        v_ = vb / den
        w_ = vc / den
        X = A + AB * v_[..., None] + AC * w_[..., None]  # interior
        # edges and vertices
        cand = [A + AB * np.clip(d1 / np.maximum((AB * AB).sum(-1), 1e-18), 0, 1)[..., None],
                A + AC * np.clip(d2 / np.maximum((AC * AC).sum(-1), 1e-18), 0, 1)[..., None]]
        BC = C - B
        t = np.clip(((P - B) * BC).sum(-1) / np.maximum((BC * BC).sum(-1), 1e-18), 0, 1)
        cand.append(B + BC * t[..., None])
        inside = (va >= 0) & (vb >= 0) & (vc >= 0)
        dist = np.min([np.sqrt(((c - P) ** 2).sum(-1)) for c in cand], axis=0)
        di = np.sqrt(((X - P) ** 2).sum(-1))
        dist = np.where(inside, np.minimum(di, dist), dist)
        out[s:s + step] = dist.min(1)
    return out


def crop(shape, c, half):
    box = cq.Solid.makeBox(2 * half[0], 2 * half[1], 2 * half[2], cq.Vector(c[0] - half[0], c[1] - half[1], c[2] - half[2]))
    try:
        r = shape.intersect(box)
        return r if vol(r) > 1e-6 else None
    except Exception:
        return None


def near_patch(A, B, c, half, h=0.25):
    """Faces of A within NEAR_T of B, inside the box around c, as a mesh with a distance per vertex."""
    ca, cb = crop(A, c, half), crop(B, c, [x + NEAR_T for x in half])
    if ca is None or cb is None:
        return None
    Va, Ta = tri_mesh(ca)
    Vb, Tb = tri_mesh(cb)
    # keep only triangles of A that face the crop's real surface, not the cut faces of the box
    lo, hi = np.asarray(c) - np.asarray(half) + 1e-3, np.asarray(c) + np.asarray(half) - 1e-3
    cen = Va[Ta].mean(1)
    on_box = np.zeros(len(Ta), bool)
    for k in range(3):
        on_box |= (np.abs(Va[Ta][:, :, k] - lo[k]).max(1) < 2e-3) | (np.abs(Va[Ta][:, :, k] - hi[k]).max(1) < 2e-3)
    Ta = Ta[~on_box]
    if not len(Ta):
        return None
    # prefilter A triangles by a cheap vertex distance, then subdivide only what can be near
    dv = point_tri_dist(Va, Vb, Tb)
    keep = dv[Ta].min(1) < NEAR_T + 2 * h + np.max(np.linalg.norm(Va[Ta][:, [1, 2, 0]] - Va[Ta], axis=2), axis=1)
    Ta = Ta[keep]
    if not len(Ta):
        return None
    Vs, Ts = subdivide(Va, Ta, h)
    used = np.unique(Ts)
    dist = np.full(len(Vs), np.inf)
    dist[used] = point_tri_dist(Vs[used], Vb, Tb)
    Ts = Ts[dist[Ts].min(1) < NEAR_T]
    if not len(Ts):
        return None
    used = np.unique(Ts)
    remap = -np.ones(len(Vs), np.int64)
    remap[used] = np.arange(len(used))
    o = np.asarray(c, float)
    q = np.round((Vs[used] - o) / 0.001).astype(np.int64)
    if np.abs(q).max() > 32767:
        q = np.clip(q, -32767, 32767)
    dq = np.clip(np.round(dist[used] / NEAR_T * 255), 0, 255)
    rec = {"o": r3(o), "s": 0.001, "nv": int(len(used)), "nt": int(len(Ts)), "v": b64(q.ravel(), "<i2"), "d": b64(dq, "u1"), "dmin": round(float(dist[used].min()), 3)}
    rec.update(idx(remap[Ts]))
    return rec


def idx(T):
    """Triangle indices, 16-bit where they fit."""
    T = np.asarray(T)
    return {"t": b64(T.ravel(), "<u2"), "ti": 2} if T.max() < 65535 else {"t": b64(T.ravel(), "<u4"), "ti": 4}


def solid_mesh(shape, tol=0.02):
    V, T = tri_mesh(shape, tol, 0.25)
    if not len(T):
        return None
    o = V.mean(0)
    q = np.round((V - o) / 0.001).astype(np.int64)
    if np.abs(q).max() > 32767:  # larger than 65 mm: coarser grid
        q = np.round((V - o) / 0.01).astype(np.int64)
        rec = {"o": r3(o), "s": 0.01}
    else:
        rec = {"o": r3(o), "s": 0.001}
    rec.update(nv=int(len(V)), nt=int(len(T)), v=b64(q.ravel(), "<i2"))
    rec.update(idx(T))
    return rec


def items_of(W, name):
    return [(nm, c) for (nm, _m), c in zip(gc.FAST_ITEMS[name], gc.children(W[name]))]


def tol_record(key, d_nom, B, gc_params, axis_word, requirement=None):
    """Gap at worst case under the stated tolerances: the nominal less every stated contributor that can close it.
    Values come from the tolerance stacks' basis file and their results; a contributor nobody has stated is listed as
    missing, never assumed."""
    def c(name, factor, why):
        b = B[name]
        return {"name": name, "pm": round(abs(b["value"]) * factor, 4), "why": why, "tag": b["tag"], "src": "analysis/gripper/tolstack/stacks/basis.yaml"}
    req = {"min": B["keepout_min_clear"]["value"], "name": "keepout_min_clear", "why": B["keepout_min_clear"]["source"],
           "src": "analysis/gripper/tolstack/stacks/basis.yaml"}
    rec = {"nominal": d_nom, "req": req, "contrib": [], "missing": [], "stack": None}
    if key == "horn|housing":
        rec["contrib"] = [c("horn_height_tol", 1, "horn face height above the servo case"),
                          c("fdm_z_tol", 1, "printed axial position of the relieved housing face"),
                          c("horn_face_runout", 0.5, "half the stated axial face runout FIM")]
        rec["missing"] = ["delivered servo seating height and measured relief depth require a coupon and assembly check"]
        rec["features"] = "horn top annulus against the recessed underside of the housing mid plate"
    elif key == "horn|fasteners":
        # no servo flange-to-horn tolerance is stated in basis.yaml, so the horn face height above the flange is missing, not assumed
        rec["contrib"] = [c("fdm_z_tol", 1, "height of the printed seat frame the flange rests on")]
        rec["missing"] = ["servo flange-to-horn tolerance is not stated in basis.yaml", "how deep pivot pin A is pressed into the mid plate"]
        rec["features"] = "top face of the horn against the end of pivot pin A, along the pin axis"
        req = dict(req, min=B["axial_min_clear"]["value"], name="axial_min_clear", why=B["axial_min_clear"]["source"])
        rec["req"] = req
    elif key == "knuckle_a|knuckle_b":
        bm, bz = B["gear_m"]["value"], int(B["gear_z"]["value"])
        gm, gz = gc_params["gear"]["module"], gc_params["gear"]["teeth"]
        rec["missing"] = [f"the backlash stack T07 was run on the earlier gear basis (module {bm:g}, {bz} teeth), not the CAD gear (module {gm:g}, {gz} teeth), so its range does not apply"]
        rec["features"] = "tooth flanks of the two gear sectors"
    elif key == "roll":
        # no stack covers the r 14.6 wrist-plate band: T11-r15band146 is absent from summary.json (T11, T11-band2 and T11-stock12
        # are the r 11.6 hub band), so the roll gap has no worst case and says so
        rec["missing"] = ["no tolerance stack in summary.json covers the r 14.6 wrist-plate band (T11-r15band146 is absent)"]
        rec["features"] = "the gripper's wrist-plate band (radius 14.6) against the arm's wrist-link lip; both are round about the roll axis"
    else:
        rec["missing"] = ["no tolerance is stated for either face"]
    if requirement:
        rec["req"] = {"min": requirement["minimum_clearance_mm"], "name": requirement["source"],
                      "why": requirement["direction_or_feature"], "src": "cad/gripper/fit_requirements.json"}
    if rec["contrib"]:
        loss = rec.get("loss_from_stack") or sum(x["pm"] for x in rec["contrib"])
        rec["loss"] = round(loss, 4)
        rec["worst"] = round(d_nom - loss, 4)
    else:
        rec["loss"] = None
        rec["worst"] = None
    rec["axis"] = axis_word
    return rec


def build_items(W, P_, steps):
    """Deck screw insertion paths and the dog set screws in their horn slots."""
    out = []
    asm = {i["id"]: i for i in steps.get("fastener_items", [])}
    # only the parts already in place when the item goes in can block it (assembly/steps.json order); the wrist plate is
    # what the deck screws thread into, so it is not a blocker
    placed, order = set(), {}
    for st in steps.get("steps", []):
        placed |= set(st.get("parts") or [])
        for it in st.get("items") or []:
            order[it] = set(placed)
    deck = [(nm, c) for nm, c in items_of(W, "fasteners") if nm == "M3x6 deck screw"]
    finds = {f["text"]: f for f in steps.get("findings", [])}
    access = {t["item"]: t for t in steps.get("tool_access", [])}
    for k, (nm, c) in enumerate(deck):
        bb = c.BoundingBox()
        cen = np.array([(bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2, (bb.zmin + bb.zmax) / 2])
        aid = min((i for i in asm if i.startswith("deck_screw")), key=lambda i: np.linalg.norm(np.array(asm[i]["centroid"]) - cen), default=None)
        axis = np.array(asm[aid]["axis"] if aid else [0, 1.0, 0])  # direction the screw travels going in
        blockers = {n: W[n] for n in sorted(order.get(aid, {"housing"})) if n in W and n != "wrist_mount"}
        first, blk = None, None
        L = 30.0
        for s_ in np.arange(L, -0.01, -0.5):
            cs = c.translate(cq.Vector(*(-axis * s_)))
            hit = [(n, inter(cs, b)) for n, b in blockers.items() if bbox_gap(cs, b) < 1e-6]
            hit = [(n, v) for n, v in hit if v > 0.01]
            if hit:
                first, blk = float(s_), max(hit, key=lambda x: x[1])[0]
                break
        rec = {"id": aid or f"deck_screw_{k + 1}", "item": nm, "seat": r3(cen), "dir": r3(axis), "path_len": L, "in_place": sorted(blockers)}
        if first is not None:
            cs = c.translate(cq.Vector(*(-axis * max(first - 1.0, 0.0))))
            try:
                ci = cs.intersect(blockers[blk])
                rec["contact"] = solid_mesh(ci, 0.01)
            except Exception:
                ci, rec["contact"] = None, None
            rec.update(first_touch_mm=round(first, 1), blocker=blk, contact_v=round(inter(cs, blockers[blk]), 2), screw=solid_mesh(cs, 0.01))
            # the screw where it first touches, cut on the plane through its axis across the blocking direction; the shared
            # material is cut too, so the inset shows where they hit
            c0 = cen - axis * max(first - 1.0, 0.0)
            rec["section"] = make_section(cs, blockers[blk], c0, c0, 0.0, extra=ci, normals=[[0, 0, 1.0]])
            rec["touch_at"] = r3(c0)
        seated = inter(c, W["housing"])
        rec["seated_overlap"] = round(seated, 2)
        ta = access.get(rec["id"])
        if ta:
            rec["driver"] = {"free_mm": ta.get("clear_mm"), "need_mm": ta.get("need_mm"), "hit": ta.get("hit"), "src": "cad/gripper/assembly/steps.json tool_access"}
        f = next((f for t, f in finds.items() if t.lower().startswith(rec["id"].replace("_", " ").replace("deck screw", "deck screw"))), None)
        if f:
            rec["text"], rec["evidence"], rec["severity"] = f["text"], f["evidence"], f["severity"]
        rec["ok"] = first is None and seated < 0.01
        out.append(rec)
    dogs = [(nm, c) for nm, c in items_of(W, "fasteners_a") if nm.startswith("dog set screw")]
    if dogs:
        nm, c = dogs[0]
        bb = c.BoundingBox()
        horn_top = W["horn"].BoundingBox().zmax
        kb = _W["G"].z_k0  # the slot is cut up from knuckle A's back face (gripper_concept: z_k0 to z_k0 + dog_slot_depth)
        typ = next((i["type"] for i in asm.values() if i["id"].startswith("dog_screw")), "")
        mm = re.search(r"M(\d+)x(\d+)", typ)
        screw_len = float(mm.group(2)) if mm else None
        ht = P_["servo"]["horn_t"]
        depth = P_["knuckle"]["dog_slot_depth"]
        proud = screw_len - ht if screw_len else None
        rec = {"id": "dog_screw", "item": nm, "type": typ, "pin_len": round(bb.zmax - bb.zmin, 2), "pin_z": [round(bb.zmin, 2), round(bb.zmax, 2)],
               "horn_t": ht, "screw_len": screw_len, "proud": proud, "horn_top_z": round(horn_top, 2), "slot_z": [round(kb, 2), round(kb + depth, 2)],
               "slot_depth": depth, "xy": [round((bb.xmin + bb.xmax) / 2, 2), round((bb.ymin + bb.ymax) / 2, 2)], "r": round((bb.xmax - bb.xmin) / 2, 2)}
        if proud is not None:
            rec["top_z"] = round(horn_top + proud, 2)
            rec["engage"] = round(max(0.0, horn_top + proud - kb), 2)
            rec["engage_cad"] = round(bb.zmax - kb, 2)
        f = next((f for f in steps.get("findings", []) if "dog screw" in f["text"].lower() and f["severity"] == "blocker"), None)
        if f:
            rec["text"], rec["evidence"], rec["severity"] = f["text"], f["evidence"], f["severity"]
        rec["ok"] = proud is not None and rec.get("engage", 0) >= rec.get("engage_cad", 0) - 1e-6
        out.append(rec)
    return out


def roll_detail(res, detail, G, B, P_):
    rw = None
    for x in res.get("roll", []):
        for r in x["rows"]:
            if rw is None or r["d"] < rw[0]["d"]:
                rw = (r, x["psi"], x["theta"])
    if rw:
        r, psi, th = rw
        if "stat" not in _W:
            stat_I, I_to_G, _ctx = load_stationary()
            _W["stat"] = {n: I_to_G(s) for n, s in stat_I.items()}
        W = world(_W["parts"], G, th)
        S = _W["stat"][r["b"]].rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -psi)
        # cut on the meridian plane: it holds the roll axis and the gap, so the two round faces show as their profiles
        sec = make_section(W[r["a"]], S, r["p"], r["q"], r["d"], normals=[np.cross(np.array(r["q"]) - np.array(r["p"]), [0, 1.0, 0])])
        # both faces are round about the roll axis, so the near band is a whole ring: crop around the axis
        pr = np.hypot(r["p"][0], r["p"][2]) + 2
        cc = [0.0, (r["p"][1] + r["q"][1]) / 2, 0.0]
        half = [pr, 3.0, pr]
        rolls = [x for x in res["roll"] if x["theta"] == th]
        ds = [min(rr["d"] for rr in x["rows"]) for x in rolls]
        detail["roll"] = {"psi": psi, "theta": th, "a": r["a"], "b": r["b"], "p": r["p"], "q": r["q"], "d": r["d"], "const": (max(ds) - min(ds)) < 0.005,
                          "section": sec, "near": {"a": near_patch(W[r["a"]], S, cc, half, 0.35), "b": near_patch(S, W[r["a"]], cc, half, 0.35)},
                          "tol": tol_record("roll", r["d"], B, P_, "radial and axial")}


def static_overlap_details(res, W0):
    # every static overlap as its own solid, with its class in words
    items = []
    for nme in STATIC:
        items += [(nm, c) for nm, c in items_of(W0, nme)] if nme == "fasteners" else [(nme, W0[nme])]
    by = {}
    for nm, c in items:
        by.setdefault(nm, []).append(c)
    ovl = []
    declarations = json.loads((HERE / "fit_requirements.json").read_text(encoding="utf-8"))["interface_intents"]
    for k, o in enumerate(res["static_overlaps"]):
        A = W0[o["a"]] if o["a"] in W0 else None
        cand = by.get(o["b"], [])
        Bc = min(cand, key=lambda c: np.linalg.norm(np.array([(c.BoundingBox().xmin + c.BoundingBox().xmax) / 2, (c.BoundingBox().ymin + c.BoundingBox().ymax) / 2,
                                                                (c.BoundingBox().zmin + c.BoundingBox().zmax) / 2]) - np.array(o["at"])), default=None)
        classification, why, intent = static_intent(o, declarations)
        rec = {"id": f"ov{k + 1}", "a": o["a"], "b": o["b"], "v": o["v"], "at": o["at"],
               "cls": classification, "why": why}
        if intent is not None:
            rec["intent"] = intent
            rec["finished_v"] = o.get("finished_v", 0.0 if intent["intent"] != "self-tapping" else o["v"])
        if A is not None and Bc is not None:
            try:
                I = A.intersect(Bc)
                rec["mesh"] = solid_mesh(I, 0.01)
                bb = I.BoundingBox()
                rec["size"] = r3([bb.xlen, bb.ylen, bb.zlen])
                if rec["cls"] == "error":
                    c3 = np.array(o["at"])
                    rec["section"] = make_section(A, Bc, c3, c3, 0.0, extra=I)
            except Exception as e:
                rec["err"] = repr(e)[:120]
        ovl.append(rec)
    return ovl


def moving_overlap_details(res, ovl, G):
    # moving overlaps (the pads meet in the grip by design), each at its worst angle
    for t in res["jaw_pairs"]:
        if t["v_max"] < 1e-3:
            continue
        th = min((float(k) for k, v in t["v"].items() if v == t["v_max"]), default=t["theta_at_min"])
        W = world(_W["parts"], G, th)
        try:
            I = W[t["a"]].intersect(W[t["b"]])
            ovl.append({"id": f"ovm{len(ovl) + 1}", "a": t["a"], "b": t["b"], "v": t["v_max"], "theta": th, "cls": "design" if t["kind"] == "pad" else "error",
                        "why": "the pads meet in the grip below 0°" if t["kind"] == "pad" else "moving parts overlap", "mesh": solid_mesh(I, 0.03),
                        "at": r3([(I.BoundingBox().xmin + I.BoundingBox().xmax) / 2, (I.BoundingBox().ymin + I.BoundingBox().ymax) / 2, (I.BoundingBox().zmin + I.BoundingBox().zmax) / 2])})
        except Exception:
            pass


def extras(res):
    """Detail records for the findings, added to res in place."""
    t0 = time.time()
    if not _W:
        _init()
    P_, G = _W["P"], _W["G"]
    B = basis()
    steps = json.loads((HERE / "assembly/steps.json").read_text(encoding="utf-8")) if (HERE / "assembly/steps.json").exists() else {}
    detail = {}
    requirements = json.loads((HERE / "fit_requirements.json").read_text(encoding="utf-8"))["requirements"]
    # gaps between moving and fixed parts, and side A to side B, that the page lists or the brief names
    for t in res["jaw_pairs"]:
        key = t["a"] + "|" + t["b"]
        designed = t["kind"] in ("pad",) or key in (
            "fasteners_a|fasteners", "fasteners_b|fasteners", "horn|servo", "knuckle_a|fasteners", "knuckle_b|fasteners")
        beyond_detail_range = t["d_min"] is not None and t["d_min"] > 0.6 and t["v_max"] < 1e-3
        if designed or t["d_min"] is None or (beyond_detail_range and key not in requirements):
            continue
        ds = [x for x in t["d"].values() if x is not None]
        const = (max(ds) - min(ds)) < 0.005
        # the pose shown: the closest one at or above the firmware floor when the pair only touches below it
        th = t["theta_at_min"]
        W = world(_W["parts"], G, th)
        p, q = t["pts"][f"{th:g}"]
        d3 = t["d_min"]
        hint = None
        if d3 < 1e-4 and t["pts"].get("-7.4"):  # touching: take the gap direction from the firmware floor
            hp, hq = t["pts"]["-7.4"]
            hint = np.array(hq) - np.array(hp)
        sec = make_section(W[t["a"]], W[t["b"]], p, q, d3, n_hint=hint)
        mid = (np.array(p) + np.array(q)) / 2
        half = [4.0, 4.0, 4.0]
        na = near_patch(W[t["a"]], W[t["b"]], mid, half, 0.3)
        nb = near_patch(W[t["b"]], W[t["a"]], mid, half, 0.3)
        n = unit(np.array(q) - np.array(p)) if d3 > 1e-4 else (unit(hint) if hint is not None else None)
        axis_word = None if n is None else (
            "along the pin axis" if abs(n[2]) > 0.9 else "across the jaw" if abs(n[0]) > 0.9 else
            "along the finger" if abs(n[1]) > 0.9 else "oblique")
        detail[key] = {"theta": th, "const": const, "p": p, "q": q, "d": d3, "section": sec, "near": {"a": na, "b": nb},
                       "tol": tol_record(key, d3, B, P_, axis_word, requirements.get(key))}
        print("detail", key, round(time.time() - t0), "s", flush=True)
    roll_detail(res, detail, G, B, P_)
    W0 = world(_W["parts"], G, 0.0)
    ovl = static_overlap_details(res, W0)
    moving_overlap_details(res, ovl, G)
    print("overlaps", round(time.time() - t0), "s", flush=True)
    builds = build_items(W0, P_, steps)
    print("builds", round(time.time() - t0), "s", flush=True)
    res["detail"] = detail
    res["overlaps"] = ovl
    res["builds"] = builds
    res["near_threshold_mm"] = NEAR_T
    res["tight_mm"] = TIGHT
    res["extras_runtime_s"] = round(time.time() - t0, 1)


def resection(res):
    """Cut every detail section again from the saved closest points, the same way extras() does."""
    G = _W["G"]
    tabs = {t["a"] + "|" + t["b"]: t for t in res["jaw_pairs"]}
    out = {}
    for key, d in res.get("detail", {}).items():
        if key == "roll":
            if "stat" not in _W:
                stat_I, I_to_G, _ctx = load_stationary()
                _W["stat"] = {n: I_to_G(s) for n, s in stat_I.items()}
            W = world(_W["parts"], G, d["theta"])
            S = _W["stat"][d["b"]].rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -d["psi"])
            d["section"] = make_section(W[d["a"]], S, d["p"], d["q"], d["d"], normals=[np.cross(np.array(d["q"]) - np.array(d["p"]), [0, 1.0, 0])])
        else:
            t, (a, b) = tabs[key], key.split("|")
            W = world(_W["parts"], G, d["theta"])
            hint = None
            if d["d"] < 1e-4 and t["pts"].get("-7.4"):
                hp, hq = t["pts"]["-7.4"]
                hint = np.array(hq) - np.array(hp)
            d["section"] = make_section(W[a], W[b], d["p"], d["q"], d["d"], n_hint=hint)
        out[key] = None if not d["section"] else [d["section"]["d2"], sum(len(x) for x in d["section"]["a"] + d["section"]["b"])]
    return out


def write_result(res):
    record = dict(res)
    record["kernel"] = kernel_versions()
    record["input_digest_sha256"] = input_digest(HERE, record["kernel"])
    record.pop("runtime_s", None)
    record.pop("extras_runtime_s", None)
    record["result_sha256"] = result_hash(record)
    (HERE / "out" / "fit3d.json").write_text(
        json.dumps(record, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def feature_check(source, value, valid, requirements):
    """Grade an unrounded feature value; a margin inside the rounding resolution cannot be told met."""
    rule = requirements["feature_requirements"][source]
    allowance = requirements["sampling"]["rounding_allowance_mm"]
    margin = min(value - rule["minimum_mm"], rule["maximum_mm"] - value)
    status = ("fail" if not valid or margin < -allowance else
              "at risk" if margin <= allowance else "met")
    check = {"requirement_id": source, "measured_mm": round(value, 3), "margin_mm": round(margin, 4) + 0.0,
             "status": status, "feature": rule["feature"]}
    if "disposition" in rule:
        check["disposition"] = rule["disposition"]
    return check


def margin_text(margin):
    """A zero margin prints without a sign, so it cannot be read as a negative one."""
    return f"{round(margin, 4) + 0.0:.4f}"


def require_recorded_kernel():
    """The full audit must run on the kernel its committed record names; FIT3D_NEW_KERNEL=1 re-pins it."""
    if os.environ.get("FIT3D_NEW_KERNEL") == "1" or not (HERE / "out" / "fit3d.json").is_file():
        return
    recorded = json.loads((HERE / "out" / "fit3d.json").read_text(encoding="utf-8")).get("kernel")
    installed = kernel_versions()
    if recorded and installed != recorded:
        raise SystemExit(f"fit3d.json was measured on {recorded}; install that kernel, or set FIT3D_NEW_KERNEL=1 to re-pin on {installed}")


def governing_features(requirements, pairs=None):
    """Measure the B4 and B38 interfaces from the drawn hardware and stack, and T07 from the gear mesh gap."""
    if not _W:
        _init()
    P, G, parts = _W["P"], _W["G"], _W["parts"]
    static, side_a, side_b = gc.fasteners(P, G)
    pins = [solid for name, solid, _ in static if name.startswith("pin h8")]
    shims = [solid for name, solid, _ in static if name.startswith("shim ")]
    result = {}
    for side, hardware in (("a", side_a), ("b", side_b)):
        x = -G.a / 2 if side == "a" else G.a / 2
        bush = next(solid for name, solid, _ in hardware if name.startswith("bronze bush"))
        radii = [BRepAdaptor_Surface(face.wrapped).Cylinder().Radius()
                 for face in bush.Faces() if face.geomType() == "CYLINDER"]
        pin = min(pins, key=lambda solid: abs(solid.BoundingBox().center.x - x))
        clearance = 2 * min(radii) - pin.BoundingBox().xlen
        hub = parts[f"knuckle_{side}"].intersect(gc.cyl_z(0, 0, 9.0, -50, 50)).BoundingBox()
        side_shims = [s for s in shims if abs(s.BoundingBox().center.x - x) < 1.0]
        if len(side_shims) != 2:
            raise ValueError(f"B38: expected two drawn shims at pivot {side}")
        shim_od = min(s.BoundingBox().xlen for s in side_shims)
        bush_od = bush.BoundingBox().xlen
        play = G.z_fp0 - hub.zlen - sum(s.BoundingBox().zlen for s in side_shims)
        result[(side, "B4")] = feature_check("B4", clearance, True, requirements)
        result[(side, "B38")] = feature_check("B38", play, shim_od > bush_od + 0.5, requirements)
    if "T07" in requirements["feature_requirements"]:
        # circumferential backlash jt from the normal mesh gap d: jt = 2 d / cos(alpha), at the closest sampled pose
        mesh = (pairs or {}).get("knuckle_a|knuckle_b")
        theta = mesh["theta_at_min"] if mesh and mesh.get("theta_at_min") is not None else 0.0
        solids = world(parts, G, theta)
        found = dist(solids["knuckle_a"], solids["knuckle_b"])
        cos_alpha = math.cos(math.radians(P["gear"]["pressure_angle"]))
        check = feature_check("T07", 2 * found[0] / cos_alpha if found else -1.0, found is not None, requirements)
        check["mesh_gap_mm"] = round(found[0], 4) if found else None
        check["theta"] = theta
        result[("a", "T07")] = result[("b", "T07")] = check
    return result


NAMES_A_CHECK = r"\bchecked by\b|\banaly[sz]\w*|\b[TBRF]\d+[A-Z]?\b|governed|controlled"


def verdict_record(res):
    requirements = json.loads((HERE / "fit_requirements.json").read_text(encoding="utf-8"))
    reasons = []
    if res.get("roll_error"):
        reasons.append(f"roll audit failed: {res['roll_error']}")
    elif not res.get("roll"):
        reasons.append("roll audit has no measurements")
    pairs = {row["a"] + "|" + row["b"]: row for row in res["jaw_pairs"]}
    features = governing_features(requirements, pairs)
    at_risk = []
    for key, row in pairs.items():
        rule = requirements["requirements"].get(key)
        if rule is None:
            sources = requirements.get("governed_elsewhere", {}).get(key)
            if sources:
                side = "a" if "_a" in key else "b"
                checks = [features[(side, source)] for source in sources]
                row["status"] = "governed elsewhere"
                row["governing_checks"] = checks
                row["requirement_id"] = ", ".join(sources)
                for check in checks:
                    if check["status"] == "fail":
                        reasons.append(f"{key}: {check['requirement_id']} feature check failed")
                    elif check["status"] == "at risk":
                        at_risk.append(f"{key}: {check['requirement_id']} {check['measured_mm']:.3f} mm, "
                                       f"{margin_text(check['margin_mm'])} mm margin within the rounding resolution")
                continue
            row["status"] = "no requirement"
            row["no_requirement_reason"] = requirements.get("no_requirement", {}).get(key)
            if not row["no_requirement_reason"]:
                reasons.append(f"{key}: no declared reason for missing requirement")
            elif re.search(NAMES_A_CHECK, row["no_requirement_reason"], re.IGNORECASE):
                reasons.append(f"{key}: no-requirement reason names a governing feature")
            continue
        row["requirement_id"] = rule["source"]
        row["requirement_minimum_mm"] = rule["minimum_clearance_mm"]
        row["sampling_allowance_mm"] = requirements["sampling"]["allowance_mm"].get(key, 0.0)
        margin = row["d_min"] - rule["minimum_clearance_mm"] if row["d_min"] is not None else None
        row["status"] = ("fail" if margin is None or margin < 0 else
                         "at risk" if margin <= row["sampling_allowance_mm"] else "met")
    for key, rule in requirements["requirements"].items():
        if not res.get("detail", {}).get(key, {}).get("section"):
            reasons.append(f"{key}: required section evidence is missing")
        row = pairs.get(key)
        if row is None or row["d_min"] is None:
            reasons.append(f"{key}: no distance")
            continue
        margin = row["d_min"] - rule["minimum_clearance_mm"]
        allowance = requirements["sampling"]["allowance_mm"].get(key, 0.0)
        if margin < 0:
            reasons.append(f"{key}: requirement failed by {-margin:.3f} mm")
        elif margin <= allowance:
            reasons.append(f"{key}: {margin:.3f} mm margin within {allowance:.3f} mm sampling allowance")
    for row in res.get("overlaps", []):
        if row["cls"] == "error":
            reasons.append(f"{row['a']}|{row['b']}: {row['why']}")
    return {"pass": not reasons, "reasons": reasons, "at_risk": at_risk}


def subset_run(args):
    """Measure selected moving pairs without touching the committed audit."""
    if not args.output:
        raise SystemExit("--output outside cad/gripper/out is required for a subset")
    output = Path(args.output).resolve()
    if output.is_relative_to((HERE / "out").resolve()):
        raise SystemExit("subset output must be outside cad/gripper/out")
    if not args.pairs or not args.thetas:
        raise SystemExit("subset requires --pairs and --thetas")
    start, stop, step = (float(v) for v in args.thetas.split(":"))
    if step <= 0 or stop < start:
        raise SystemExit("--thetas must be start:stop:positive-step")
    names = [name.split("|") for name in args.pairs.split(",")]
    allowed = set(MOV_A + MOV_B + STATIC)
    if any(len(pair) != 2 or any(part not in allowed for part in pair) for pair in names):
        raise SystemExit("unknown subset pair")
    _init()
    samples = []
    for index in range(int(round((stop - start) / step)) + 1):
        theta = round(start + index * step, 8)
        if theta > stop + 1e-8:
            break
        solids = world(_W["parts"], _W["G"], theta)
        for a, b in names:
            samples.append({"theta": theta, **pair_row(a, solids[a], b, solids[b])})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(samples, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(output), "samples": len(samples), "minimum": {
        "|".join(pair): min((row["d"], row["theta"]) for row in samples
                            if row["a"] == pair[0] and row["b"] == pair[1] and row.get("d") is not None)
        for pair in names}}))
    return 0


def refresh_saved_result(args):
    if "--extras" in sys.argv:  # keep the jaw, static and roll results, compute the page's detail records again
        res = json.loads((HERE / "out" / "fit3d.json").read_text(encoding="utf-8"))
        validate_result(res, HERE)
        extras(res)
        res["verdict"] = verdict_record(res)
        write_result(res)
        print(json.dumps({"detail": sorted(res["detail"]), "overlaps": len(res["overlaps"]), "builds": [(b["id"], b.get("blocker"), b.get("first_touch_mm"), b.get("ok")) for b in res["builds"]],
                          "extras_runtime_s": res["extras_runtime_s"]}))
        return 0 if args.report_only or res["verdict"]["pass"] else 1
    if "--sections" in sys.argv:  # keep everything, cut the detail sections again
        res = json.loads((HERE / "out" / "fit3d.json").read_text(encoding="utf-8"))
        validate_result(res, HERE)
        n = resection(res)
        res["verdict"] = verdict_record(res)
        write_result(res)
        print(json.dumps(n))
        return 0 if args.report_only or res["verdict"]["pass"] else 1
    if "--roll-only" in sys.argv:  # keep the jaw results, measure the roll again
        res = json.loads((HERE / "out" / "fit3d.json").read_text(encoding="utf-8"))
        validate_result(res, HERE)
        stat_I, I_to_G, ctx = load_stationary()
        res["roll_frame_check_mm"] = round(check_map(stat_I, I_to_G, ctx)[0], 3)
        with ProcessPoolExecutor(4, mp_context=mp.get_context("spawn"), initializer=_init_roll) as ex:
            rows = list(ex.map(roll_task, [(psi, th) for th in (0.0, 20.0) for psi in ROLLS]))
        res["roll"] = [{"psi": psi, "theta": th, "rows": rr} for psi, th, rr in rows]
        res.pop("roll_error", None)
        res["complete"] = False
        write_result(res)
        print(json.dumps({"roll_min": min(r["d"] for x in res["roll"] for r in x["rows"]), "frame_check": res["roll_frame_check_mm"]}))
        return 0
    return None


def summarize_jaw(jaw):
    # per pair: closest approach over the travel, and the per-angle distance
    pairs = {}
    for th in THETAS:
        for r in jaw[th]:
            k = r["a"] + "|" + r["b"]
            pairs.setdefault(k, []).append((th, r))
    tab = []
    for k, lst in pairs.items():
        a, b = k.split("|")
        near = [(th, r) for th, r in lst if r.get("d") is not None]
        if not near:
            continue
        th_min, r_min = min(near, key=lambda x: (x[1]["d"], x[0]))
        kind = "pad" if (a in PAD_A and b in PAD_B) else ("gear" if (a, b) == ("knuckle_a", "knuckle_b") else "")
        tab.append({"a": a, "b": b, "kind": kind, "d_min": r_min["d"], "theta_at_min": th_min,
                    "v_max": max((r.get("v", 0.0) for _, r in near), default=0.0),
                    "d": {f"{th:g}": (r.get("d") if r.get("d") is not None else None) for th, r in lst},
                    "pts": {f"{th:g}": [r["p"], r["q"]] for th, r in lst if r.get("p")},
                    "v": {f"{th:g}": r["v"] for th, r in lst if r.get("v")}})
    tab.sort(key=lambda t: (t["d_min"], t["a"], t["b"]))
    return tab


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs")
    parser.add_argument("--thetas")
    parser.add_argument("--output")
    parser.add_argument("--report-only", action="store_true")
    args, _ = parser.parse_known_args()
    if args.pairs or args.thetas or args.output:
        return subset_run(args)
    t0 = time.time()
    require_recorded_kernel()
    _init()
    refreshed = refresh_saved_result(args)
    if refreshed is not None:
        return refreshed
    res = {"frame": "G (README), mm", "thetas": THETAS, "rolls": ROLLS,
           "parts": {"static": STATIC, "moving_A": MOV_A, "moving_B": MOV_B},
           "horn_note": "the servo horn turns with knuckle A on the servo shaft; gripper_concept leaves it unposed, which is invisible for a disc"}
    with ProcessPoolExecutor(4, mp_context=mp.get_context("spawn"), initializer=_init) as ex:
        jaw = dict(ex.map(jaw_task, THETAS))
        stat_rows = list(ex.map(static_task, [0]))[0]
    res["static_overlaps"] = stat_rows
    print("jaw + static", round(time.time() - t0), "s", flush=True)

    tab = summarize_jaw(jaw)
    res["jaw_pairs"] = tab
    res["complete"] = False
    write_result(res)  # kept if the roll phase is stopped

    # roll
    try:
        stat_I, I_to_G, ctx = load_stationary()
        err, got, ref = check_map(stat_I, I_to_G, ctx)
        res["roll_frame_check_mm"] = round(err, 3)
        with ProcessPoolExecutor(4, mp_context=mp.get_context("spawn"), initializer=_init_roll) as ex:
            rows = list(ex.map(roll_task, [(psi, th) for th in (0.0, 20.0) for psi in ROLLS]))
        res["roll"] = [{"psi": psi, "theta": th, "rows": rr} for psi, th, rr in rows]
    except Exception as e:  # the upstream assembly is optional; the page then shows the ring numbers only
        res["roll_error"] = repr(e)[:300]
    extras(res)
    res["runtime_s"] = round(time.time() - t0, 1)
    res["verdict"] = verdict_record(res)
    res["complete"] = True
    write_result(res)
    print(json.dumps({"pairs": [(t["a"], t["b"], t["d_min"], t["theta_at_min"], t["v_max"]) for t in tab[:25]],
                      "static": stat_rows, "roll_frame_check_mm": res.get("roll_frame_check_mm"), "roll_error": res.get("roll_error"),
                      "runtime_s": res["runtime_s"]}, indent=0))
    print("VERDICT", "PASS" if res["verdict"]["pass"] else "FAIL", "; ".join(res["verdict"]["reasons"]), flush=True)
    return 0 if args.report_only or res["verdict"]["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
