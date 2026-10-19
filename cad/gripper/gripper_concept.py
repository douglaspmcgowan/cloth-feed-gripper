#!/usr/bin/env python3
"""CAD rebuild for the ME102B cloth-feed gripper (DS3218MG, PA6-CF m1.5 z19 sector pair, 45 mm Fin Ray).

Reads params.json (+ gear_profile.dxf) and writes to out/: STEP + STL per part, assembly.step,
parts.json (mass, COM, bbox per part) and out/web/*.glb for a viewer; to drawings/: SVG sheets and BOM.md.

Frame G (README): X = jaw closing axis, Y = up (wrist on top, tips at -Y), Z = out of the gear plane.
Pivot A (servo side) at (-a/2, 0), pivot B at (+a/2, 0). Per-part files are at theta = 0.
The wrist-roll axis is the line x = 0, z = 0; horn face H is at y = Y_H (reported).

    uv run --with cadquery python cad/gripper/gripper_concept.py [--angle DEG] [--no-drawings]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import cadquery as cq

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- 2D helpers
def area(p):
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p))) / 2


def clean(p):
    o = []
    for q in p:
        if not o or math.hypot(q[0] - o[-1][0], q[1] - o[-1][1]) > 1e-4:
            o.append(q)
    if len(o) > 2 and math.hypot(o[0][0] - o[-1][0], o[0][1] - o[-1][1]) < 1e-4:
        o.pop()
    return o


def clip_half(poly, nx, ny, c):
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        fa, fb = nx * a[0] + ny * a[1] - c, nx * b[0] + ny * b[1] - c
        if fa >= 0:
            out.append(a)
        if (fa >= 0) != (fb >= 0):
            t = fa / (fa - fb)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def inset(poly, d):
    r = poly
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        nx, ny = -(q[1] - p[1]) / L, (q[0] - p[0]) / L
        r = clip_half(r, nx, ny, nx * p[0] + ny * p[1] + d)
        if len(r) < 3:
            return []
    return r


def rdp(pts, eps):
    """Ramer-Douglas-Peucker on an open polyline (iterative)."""
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        ax, ay = pts[i]
        bx, by = pts[j]
        L = math.hypot(bx - ax, by - ay) or 1e-12
        dmax, k = -1.0, -1
        for m in range(i + 1, j):
            d = abs((bx - ax) * (ay - pts[m][1]) - (ax - pts[m][0]) * (by - ay)) / L
            if d > dmax:
                dmax, k = d, m
        if dmax > eps:
            keep[k] = True
            stack += [(i, k), (k, j)]
    return [p for p, f in zip(pts, keep) if f]


def read_dxf_polylines(path):
    """R12 DXF POLYLINE/VERTEX reader -> {layer: [(x, y), ...]}."""
    ln = [s.strip() for s in Path(path).read_text(encoding="utf-8").split("\n")]
    out, cur, mode, vx = {}, None, None, 0.0
    for c, v in zip(ln[0::2], ln[1::2]):
        if c == "0":
            if v == "POLYLINE":
                mode, cur = "P", []
            elif v == "VERTEX":
                mode = "V"
            else:
                mode = None
        elif mode == "P" and c == "8":
            out[v] = cur
        elif mode == "V" and c == "10":
            vx = float(v)
        elif mode == "V" and c == "20":
            cur.append((vx, float(v)))
    return out


# ---------------------------------------------------------------- solid helpers
def box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def cyl_z(x, y, r, z0, z1):
    return cq.Solid.makeCylinder(r, z1 - z0, cq.Vector(x, y, z0), cq.Vector(0, 0, 1))


def cyl_y(x, z, r, y0, y1):
    return cq.Solid.makeCylinder(r, y1 - y0, cq.Vector(x, y0, z), cq.Vector(0, 1, 0))


def cyl_x(y, z, r, x0, x1):
    return cq.Solid.makeCylinder(r, x1 - x0, cq.Vector(x0, y, z), cq.Vector(1, 0, 0))


def prism(pts, z0, z1):
    return cq.Workplane("XY", origin=(0, 0, z0)).polyline(pts).close().extrude(z1 - z0).val()


def fuse(*shapes):
    s = shapes[0].fuse(*shapes[1:]).clean() if len(shapes) > 1 else shapes[0]
    return s


def cut(body, tools):
    return body.cut(*tools).clean() if tools else body


def single(shape, name, warn):
    sol = shape.Solids()
    if len(sol) != 1:
        warn.append(f"{name}: {len(sol)} solids")
        return cq.Compound.makeCompound(sol) if len(sol) > 1 else shape
    return sol[0]


# ---------------------------------------------------------------- derived layout
def resolve(P):
    """Copy servo.models[servo.model] over the servo block and set gear.face_width from it (rev B, CHANGELOG B11).
    Idempotent; returns a new dict, so callers may pass the raw params.json."""
    import copy
    Q = copy.deepcopy(P)
    s = Q["servo"]
    models = s.get("models")
    if models:
        row = models[s["model"]]
        for k, v in row.items():
            if k.startswith("_") or k == "measure_on_delivered_part":
                continue
            s[k] = copy.deepcopy(v)
        if "gear_face_width" in row:
            Q["gear"]["face_width"] = row["gear_face_width"]
    return Q


def x_face(G, y):
    """A-local x of the toed-in pad face at height y (hinge at the pad-contact point (xf, yp), CHANGELOG B4)."""
    return G.xf + (y - G.yp) * math.tan(G.toe)


def derive(P):
    s, g, k, f, h, w = P["servo"], P["gear"], P["knuckle"], P["finger"], P["housing"], P["wrist_mount"]
    a = g["center_distance"]
    m = g["module"]
    ra = m * g["teeth"] / 2 + m * (1 + g.get("profile_shift", 0.0))
    pl, b = h["plate"], g["face_width"]
    z_k0 = k["shim_t"] + k["end_play"] / 2 + 0.0  # knuckle back face (mid-plate front face = 0)
    z_k0 = round(1.0, 3)
    z_fp0 = z_k0 + b + h["front_gap"]
    zc = z_k0 + b / 2
    nail = P["nail"]["thickness"]
    fsr = P["fsr"]
    b_stack = fsr["backing_under"] + fsr["pocket_depth"] - fsr["pocket_depth"] + fsr["thickness"] + fsr["puck_t"]
    closed_gap = f["contact_gap"] + nail + b_stack
    xf = a / 2 - closed_gap / 2
    R0 = k["root_offset"]
    y_root = -R0 - k["root_thickness"]          # bottom of root web = top of TPU tab
    y0 = y_root - k["root_tab"]                 # clamp line (finger root line)
    long_x = s.get("long_axis", "Y") == "X"
    L_long, L_w = s["body_y"], s["body_x"]  # case length (long axis) and width
    if long_x:  # long axis along X: shaft 10 from the outboard (-X) end, body runs toward pivot B
        sx0, sx1 = -a / 2 - s["shaft_from_bottom"], -a / 2 - s["shaft_from_bottom"] + L_long
        ys0, ys1 = -L_w / 2, L_w / 2
    else:       # long axis along Y (2026-09-22 layout): shaft 10 from the finger-side end
        sx0, sx1 = -a / 2 - L_w / 2, -a / 2 + L_w / 2
        ys0, ys1 = -s["shaft_from_bottom"], L_long - s["shaft_from_bottom"]
    z_horn1 = -pl - 0.5
    z_horn0 = z_horn1 - s["horn_t"]
    z_ct = z_horn0 - s["horn_gap"]              # servo case top
    z_cb = z_ct - s["body_z"]
    z_ear1 = z_ct - s["ear_from_top"]
    z_ear0 = z_ear1 - s["ear_t"]
    if long_x:
        ear_x0, ear_x1 = (sx0 + sx1) / 2 - s["ear_span"] / 2, (sx0 + sx1) / 2 + s["ear_span"] / 2
        ear_y0, ear_y1 = ys0, ys1
    else:
        ear_x0, ear_x1 = sx0, sx1
        ear_y0 = (ys0 + ys1) / 2 - s["ear_span"] / 2
        ear_y1 = (ys0 + ys1) / 2 + s["ear_span"] / 2
    yd0 = max(ear_y1 + h["deck_clear_above_servo"], h.get("deck_y_min", 0.0))
    yd1 = yd0 + h["deck_t"]
    Y_H = yd1 + w["arm_t"] + w["band_to_H"]
    toe = math.radians(f.get("toe_in_deg", 0.0))
    yp = y0 - (f["length"] - f.get("contact_from_tip", P["grip"]["pad_centroid_from_tip_mm"]))
    # pad-normal moment arm about the pivot for each rigid contact face (A: nail face, B: puck face), toed in [D]
    r_c_face = {side: -yp * math.cos(toe) - (xf + off) * math.sin(toe)
                for side, off in (("A", nail), ("B", b_stack))}
    G = SimpleNamespace(a=a, ra=ra, pl=pl, b=b, z_k0=z_k0, z_k1=z_k0 + b, z_fp0=z_fp0, z_fp1=z_fp0 + pl,
                           zc=zc, xf=xf, closed_gap=closed_gap, R0=R0, y_root=y_root, y0=y0,
                           sx0=sx0, sx1=sx1, ys0=ys0, ys1=ys1, z_ct=z_ct, z_cb=z_cb, z_horn0=z_horn0,
                           z_horn1=z_horn1, z_ear0=z_ear0, z_ear1=z_ear1, ear_y0=ear_y0, ear_y1=ear_y1,
                           ear_x0=ear_x0, ear_x1=ear_x1, long_x=long_x,
                           yd0=yd0, yd1=yd1, Y_H=Y_H, Rp=h["plate_radius"], X=a / 2 + h["plate_radius"],
                           r_c=-y0 + (f["length"] - P["grip"]["pad_centroid_from_tip_mm"]),
                           b_stack=b_stack, toe=toe, yp=yp, r_c_face=r_c_face,
                           zs0=z_ear1, zs1=z_ear1 + h["wall"],
                           zw0=z_ct + h.get("boss_web_gap", 0.3), zw1=z_ct + h.get("boss_web_gap", 0.3) + h.get("boss_web_t", 1.8))
    # end play: plate gap (mid-plate front face z 0 to the front-plate back face) - hub - one shim per face (CHANGELOG B38)
    G.end_play = z_fp0 - b - 2 * k["shim_t"]
    # end-wall PETG left beside the washer / nut notch at the nearer ear screw (long-X layout; CHANGELOG B39)
    if long_x and h.get("nut_notch_r"):
        c, wl = h["cradle_pocket_clear"], h["wall"]
        xe = sorted({x for x, _ in ear_holes(P, G)})
        inner = (sx0 - c, sx1 + c)  # end-wall faces toward the servo case
        G.wall_notch = tuple(min(inner[0] - (xe[0] + r), (xe[-1] - r) - inner[1])
                             for r in (h["nut_notch_r"], h.get("nut_notch_r_nut", h["nut_notch_r"])))
    else:
        G.wall_notch = (float("nan"), float("nan"))
    return G


# ---------------------------------------------------------------- housing (PETG): deck + mid plate + cradle + standoffs
def plate_outline(G, y_top):
    """Pivot circles (radius Rp) + rectangle up to y_top; no hull line between the pivots, so the
    finger root blocks clear the plates during overtravel."""
    X, a, Rp = G.X, G.a, G.Rp
    yi = -math.sqrt(max(Rp ** 2 - (a / 2) ** 2, 0.0))
    ai = math.atan2(yi, a / 2)
    mA = (math.pi + (2 * math.pi + ai)) / 2
    mB = ((math.pi - ai) + 2 * math.pi) / 2
    return (cq.Workplane("XY").moveTo(-X, y_top).lineTo(-X, 0)
            .threePointArc((-a / 2 + Rp * math.cos(mA), Rp * math.sin(mA)), (0, yi))
            .threePointArc((a / 2 + Rp * math.cos(mB), Rp * math.sin(mB)), (X, 0))
            .lineTo(X, y_top).close())


def ear_holes(P, G):
    """Servo ear-screw centres (x, y) in frame G."""
    s = P["servo"]
    xc, yc = (G.sx0 + G.sx1) / 2, (G.ys0 + G.ys1) / 2
    pl, pw = s["ear_hole_pitch_y"] / 2, s["ear_hole_pitch_x"] / 2  # along / across the long axis
    if G.long_x:
        return [(xc + dl, yc + dw) for dl in (-pl, pl) for dw in (-pw, pw)]
    return [(xc + dw, yc + dl) for dl in (-pl, pl) for dw in (-pw, pw)]


def housing(P, G, warn):
    h, s, k = P["housing"], P["servo"], P["knuckle"]
    w, pl = h["wall"], G.pl
    a = G.a
    bodies = []
    # mid plate z in [-pl, 0], up to the deck
    mid = plate_outline(G, G.yd0).extrude(pl).val().translate(cq.Vector(0, 0, -pl))
    zz = (-pl - 1, 1)
    holes = [cyl_z(x, 0, k["pin_hole_cad"] / 2, *zz) for x in (-a / 2, a / 2)]
    # dog-pin arc slots around pivot A: pin-centre path for theta in [theta_min - 5, open + 5], with
    # round ends of radius ws/2 centred on the path at both end angles, so the pin's own angular
    # half-width asin(r_pin / r_dog) = 12.4 deg stays inside the slot (fitcheck jaw sweep 2026-09-23)
    tmin, tmax = P["motion"]["theta_min"] - 5, P["motion"]["open_angle_max"] + 5
    rs, ws = s["dog_r"], s["dog_d"] + 1.5
    for base in (90.0, 270.0):
        a0, a1 = math.radians(base - tmax), math.radians(base - tmin)
        ro, ri = rs + ws / 2, rs - ws / 2
        n = 16
        pts = [(-a / 2 + ro * math.cos(a0 + (a1 - a0) * i / n), ro * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
        pts += [(-a / 2 + ri * math.cos(a1 - (a1 - a0) * i / n), ri * math.sin(a1 - (a1 - a0) * i / n)) for i in range(n + 1)]
        holes.append(prism(pts, *zz))
        for t in (a0, a1):
            holes.append(cyl_z(-a / 2 + rs * math.cos(t), rs * math.sin(t), ws / 2, *zz))
    for (x, y) in h["standoffs"]:
        holes.append(cyl_z(x, y, h["clearance_hole_cad"] / 2 - 0.4, *zz))
    if h["lightened"] and G.yd0 - 4 > 25.0:  # the long-Y layout only; the long-X deck is too low
        holes.append(box(G.sx0 + 3, G.sx1 - 3, 14.0, G.yd0 - 4, *zz))
        holes.append(box(4.0, G.X - 4, 22.0, G.yd0 - 4, *zz))
    # B.1 annular underside recess preserves the full central pivot-pin seat.
    if h.get("horn_face_relief_depth"):
        depth = h["horn_face_relief_depth"]
        outer = cyl_z(-a / 2, 0, s["horn_d"] / 2 + h["horn_face_relief_radial"], -pl - 0.01, -pl + depth)
        seat = cyl_z(-a / 2, 0, h["horn_face_seat_radius"], -pl - 0.02, -pl + depth + 0.01)
        holes.append(outer.cut(seat))
    bodies.append(cut(mid, holes))
    # standoffs z in [0, z_fp0] with M3 pilot (self-tap into PETG, 2.5)
    for (x, y) in h["standoffs"]:
        bodies.append(cut(cyl_z(x, y, h["standoff_d"] / 2, 0, G.z_fp0), [cyl_z(x, y, 1.25, -1, G.z_fp0 + 1)]))
    # cradle: seat frame on the spline side of the ears + two end walls to the mid plate
    c = h["cradle_pocket_clear"]
    zs0, zs1 = G.zs0, G.zs1
    ext = h.get("frame_end_ext", 0.0)  # rev B C1: frame 1.5 longer per end keeps 2.5 mm of PETG round the Ø5 seat hole
    if G.long_x:
        frame = box(G.ear_x0 - 1 - ext, G.ear_x1 + 1 + ext, G.ys0 - w, G.yd0, zs0, zs1)
    else:
        frame = box(G.sx0 - w, G.sx1 + w, G.ear_y0 - 1 - ext, G.yd0, zs0, zs1)
    fh = [box(G.sx0 - c, G.sx1 + c, G.ys0 - c, G.ys1 + c, zs0 - 1, zs1 + 1)]
    seat_d = h.get("ear_seat_hole", h["clearance_hole_cad"])  # rev B C1: limiter sleeve seat
    for x, y in ear_holes(P, G):
        fh.append(cyl_z(x, y, seat_d / 2, zs0 - 1, zs1 + 1))
    if h["lightened"] and G.long_x:  # two windows in the seat frame above the case
        fh.append(box(G.sx0 + 3, G.sx1 - 3, G.ys1 + c + 2.5, G.yd0 - 2.5, zs0 - 1, zs1 + 1))
    if h.get("tc_hole_d"):  # rev B C3: thermocouple hole under the A-end ear, front face to 0.5 short of the ear
        tx, ty = tc_hole_xy(P, G)
        fh.append(cyl_z(tx, ty, h["tc_hole_d"] / 2, zs0 + h["tc_hole_short_of_ear"], zs1 + 1))
    bodies.append(cut(frame, fh))
    walls = []
    if G.long_x:  # end walls at both ends of the case, frame to mid plate
        for x0 in (G.sx0 - c - w, G.sx1 + c):
            walls.append(box(x0, x0 + w, G.ys0 + 2.0, G.yd0, zs1, -pl))
    else:
        for x0 in (G.sx0 - w, G.sx1):
            walls.append(box(x0, x0 + w, G.ys0 + 2.0, G.yd0, zs1, -pl))
    wt = []
    if h.get("nut_notch_r"):  # rev B: room for washer + nut on each ear screw (fit3d had no nut; the washer hit the walls)
        # B39: washer layer R3.75 (washer R3.5), nut layer R3.45 (nut corners R3.18), so the end wall keeps 0.80 / 1.10 mm
        hw = h.get("nut_notch_washer_h", h["nut_notch_h"])
        for x, y in ear_holes(P, G):
            wt.append(cyl_z(x, y, h["nut_notch_r"], zs1 - 0.01, zs1 + hw))
            if hw < h["nut_notch_h"]:
                wt.append(cyl_z(x, y, h.get("nut_notch_r_nut", h["nut_notch_r"]), zs1 + hw - 0.01, zs1 + h["nut_notch_h"]))
    if h.get("horn_relief") and G.long_x:  # rev B: horn slide-in channel and running gap in the A end wall (fit3d 0.20 mm)
        rr = P["servo"]["horn_d"] / 2 + h["horn_relief"]
        wt.append(cyl_z(-G.a / 2, 0, rr, G.zw1, -pl))
        wt.append(box(-G.a / 2 - rr, -G.a / 2 + rr, G.ys0 - 5, 0, G.zw1, -pl))
    walls = [cut(wl, wt) for wl in walls]
    bodies += walls
    if h.get("boss_web_t"):  # rev B row 1: Ø9 servo-boss bore in a web of the housing print at the case top
        web = box(G.sx0 - c, G.sx1 + c, -h["boss_web_half_y"], h["boss_web_half_y"], G.zw0, G.zw1)
        bodies.append(cut(web, [cyl_z(-G.a / 2, 0, h["boss_bore_cad"] / 2, G.zw0 - 1, G.zw1 + 1)]))
    # deck y in [yd0, yd1]
    dz0, dz1 = h["deck_z"]
    X = h["deck_half_x"]
    deck = box(-X, X, G.yd0, G.yd1, dz0, dz1)
    if h.get("deck_r_max"):  # rev B: corners clipped to the stock rolling envelope (fitcheck band z_I 6-12, stock r 37.6)
        deck = deck.intersect(cyl_y(0, 0, h["deck_r_max"], G.yd0 - 1, G.yd1 + 1))
    dh = [cyl_y(x, z, h["clearance_hole_cad"] / 2, G.yd0 - 1, G.yd1 + 1) for x, z in h["deck_screws"]]
    for x, z in h.get("deck_pegs", []):  # rev B row 5: reamed Ø3 locating-pin holes
        dh.append(cyl_y(x, z, h["deck_peg_hole_cad"] / 2, G.yd0 - 1, G.yd1 + 1))
    if h["lightened"]:
        dh.append(box(-X + 7, -X + 12, G.yd0 - 1, G.yd1 + 1, -9, 2))
        dh.append(box(X - 12, X - 7, G.yd0 - 1, G.yd1 + 1, -9, 2))
        dh.append(box(-16, 16, G.yd0 - 1, G.yd1 + 1, 3.0, 9.0))
    bodies.append(cut(deck, dh))
    return single(fuse(*bodies), "housing", warn)


def tc_hole_xy(P, G):
    """Thermocouple hole: under the A-end ear, midway between its two screw seats."""
    pts = [p for p in ear_holes(P, G) if p[0] < G.sx0]
    return (pts[0][0], sum(p[1] for p in pts) / len(pts))


def front_plate(P, G, warn):
    h, k, cp = P["housing"], P["knuckle"], P["camera_pad"]
    a, pl = G.a, G.pl
    z0, z1 = G.z_fp0, G.z_fp1
    body = plate_outline(G, G.yd0 - 0.2).extrude(pl).val().translate(cq.Vector(0, 0, z0))
    cx, cy = cp["centre_rel_pivot"]
    sx, sy = cp["size"]
    pad = box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z1, z1 + cp["boss_h"])
    body = fuse(body, pad)
    zz = (z0 - 1, z1 + cp["boss_h"] + 1)
    zpin = z0 + k["pin_front_blind"] if k.get("pin_front_blind") else z1 + 1  # rev B row 10: blind, pin captured
    holes = [cyl_z(x, 0, k["pin_hole_cad"] / 2, z0 - 1, zpin) for x in (-a / 2, a / 2)]
    holes += [cyl_z(x, y, h["clearance_hole_cad"] / 2, *zz) for x, y in h["standoffs"]]
    ztop = z1 + cp["boss_h"]
    for dy in (-cp["bolt_pitch"] / 2, cp["bolt_pitch"] / 2):
        holes.append(cyl_z(cx, cy + dy, cp["bore_d"] / 2, ztop - cp["bore_depth"], ztop + 1))
    tx, ty, tz = cp["tab_slot"]
    holes.append(box(cx - tx / 2, cx + tx / 2, cy + sy / 2 - ty - 0.5, cy + sy / 2 - 0.5, ztop - tz, ztop + 1))
    if h["lightened"]:
        if G.yd0 > 30:
            holes += [cyl_z(0, 11, 4.5, z0 - 1, z1 + 1), box(-G.X + 4, -9.0, 20.0, G.yd0 - 5, z0 - 1, z1 + 1)]
        else:
            holes += [cyl_z(0, 8.0, 3.0, z0 - 1, z1 + 1)]
        holes.append(cyl_z(0, -11, 3.5, z0 - 1, z1 + 1))
    return single(cut(body, holes), "front_plate", warn)


# ---------------------------------------------------------------- wrist mount plate (PETG) on the SO-101 roll horn
def wrist_mount(P, G, warn):
    w, h = P["wrist_mount"], P["housing"]
    YH = G.Y_H
    y_rim = YH + w["rim_below_H"]
    hub_lo = cyl_y(0, 0, w["hub_r_low"], YH - w["hub_low_to_H"], y_rim)
    band = cyl_y(0, 0, w["hub_r_band"], YH - w["band_to_H"], YH - w["hub_low_to_H"] + 0.001)
    ya0, ya1 = G.yd1, YH - w["band_to_H"] + 0.001
    parts = [hub_lo, band, cyl_y(0, 0, w["hub_r_band"], ya0, ya1)]
    for x, z in h["deck_screws"]:
        L = math.hypot(x, z)
        ux, uz = x / L, z / L
        wv = w["arm_w"] / 2
        pts = [(-uz * wv, ux * wv), (x - uz * wv, z + ux * wv), (x + uz * wv, z - ux * wv), (uz * wv, -ux * wv)]
        arm = cq.Workplane("XZ", origin=(0, ya1, 0)).polyline([(p[0], p[1]) for p in pts]).close().extrude(ya1 - ya0).val()
        parts += [arm, cyl_y(x, z, w["boss_d"] / 2, ya0, ya1)]
    body = fuse(*parts)
    holes = [cyl_y(0, 0, w["recess_d_cad"] / 2, YH, y_rim + 1),
             cyl_y(0, 0, w["centre_hole_d"] / 2, ya0 - 1, y_rim + 1)]
    ch = w["recess_chamfer"]
    holes.append(cq.Solid.makeCone(w["recess_d_cad"] / 2, w["recess_d_cad"] / 2 + ch + 0.01, ch + 0.01,
                                   cq.Vector(0, y_rim - ch, 0), cq.Vector(0, 1, 0)))
    r = w["bolt_circle_d"] / 2
    for i in range(w["bolt_count"]):
        t = math.pi / 4 + i * 2 * math.pi / w["bolt_count"]
        x, z = r * math.cos(t), r * math.sin(t)
        holes.append(cyl_y(x, z, w["clearance_hole_cad"] / 2, YH - w["clamp_t"] - 0.01, y_rim + 1))
        holes.append(cyl_y(x, z, w["counterbore_d"] / 2, ya0 - 1, YH - w["clamp_t"]))
    for x, z in h["deck_screws"]:
        holes.append(cyl_y(x, z, h["insert_bore"] / 2, ya0 - 0.01, ya0 + h["insert_depth"]))
    for x, z in h.get("deck_pegs", []):  # rev B row 5: locating-pin holes in the spider underside
        holes.append(cyl_y(x, z, w["peg_hole_cad"] / 2, ya0 - 0.01, ya0 + w["peg_hole_depth"]))
    return single(cut(body, holes), "wrist_mount", warn)


# ---------------------------------------------------------------- knuckles (PA6-CF) in their own pivot frame
def sector_solid(P, G, side):
    poly = read_dxf_polylines(HERE / P["gear"]["profile_dxf"])["GEAR_" + side]
    dx = G.a / 2 if side == "A" else -G.a / 2
    pts = [(x + dx, y) for x, y in poly]
    if math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-6:
        pts = pts[:-1]
    j = max(range(len(pts)), key=lambda i: math.hypot(pts[i][0] - pts[0][0], pts[i][1] - pts[0][1]))
    pts = rdp(pts[:j + 1], 0.002)[:-1] + rdp(pts[j:] + [pts[0]], 0.002)[:-1]
    return prism(pts, G.z_k0, G.z_k1), len(poly), len(pts)


def finger_frame_local(P, G, side):
    """Arm + root block (U: web + 2 cheeks) in A-local coordinates (B mirrors it)."""
    k, f = P["knuckle"], P["finger"]
    wA = k["arm_top_width"]
    rh = k["hub_r"]
    hh = math.sqrt(rh ** 2 - wA ** 2 / 4)
    W, D = f["base_width"], f["depth"]
    xr = G.xf - k["root_relief"]
    arm = prism([(-wA / 2, -hh + 0.5), (G.xf - W, -G.R0 - 0.5), (xr, -G.R0 - 0.5), (wA / 2, -hh + 0.5)], G.z_k0, G.z_k1)
    zc, cz = G.zc, k["root_cheek"]
    web = box(G.xf - W, xr, G.y_root, -G.R0, zc - D / 2 - cz, zc + D / 2 + cz)
    cheeks = [box(G.xf - W, xr, G.y0, G.y_root + 0.01, zc - D / 2 - cz, zc - D / 2),
              box(G.xf - W, xr, G.y0, G.y_root + 0.01, zc + D / 2, zc + D / 2 + cz)]
    return arm, web, cheeks


def root_holes(P, G, x_sign=1.0):
    k, f = P["knuckle"], P["finger"]
    xc = G.xf - f["base_width"] + (f["base_width"] - k["root_relief"]) / 2
    yh = (G.y0 + G.y_root) / 2
    zc, D, cz = G.zc, f["depth"], k["root_cheek"]
    z0, z1 = zc - D / 2 - cz - 1, zc + D / 2 + cz + 1
    out = []
    for dx in (-k["peg_pitch"] / 2, k["peg_pitch"] / 2):
        out.append(cq.Solid.makeCylinder(k["peg_d"] / 2, z1 - z0, cq.Vector(x_sign * (xc + dx), yh, z0), cq.Vector(0, 0, 1)))
    out.append(cq.Solid.makeCylinder(k["root_screw_d"] / 2, z1 - z0, cq.Vector(x_sign * xc, yh, z0), cq.Vector(0, 0, 1)))
    return out


def knuckle(P, G, side, warn, info):
    k, s = P["knuckle"], P["servo"]
    sec, n_raw, n_used = sector_solid(P, G, side)
    info[f"sector_{side}_vertices"] = [n_raw, n_used]
    hub = cyl_z(0, 0, k["hub_r"], G.z_k0, G.z_k1)
    arm, web, cheeks = finger_frame_local(P, G, side)
    parts = [arm, web] + cheeks
    if side == "B":
        parts = [p.mirror("YZ") for p in parts]
    body = fuse(hub, sec, *parts)
    holes = [cyl_z(0, 0, k.get("sleeve_bore_cad", k["sleeve_od"]) / 2, G.z_k0 - 1, G.z_k1 + 1)]
    holes += root_holes(P, G, 1.0 if side == "A" else -1.0)
    if side == "A":  # dog slots (radial float) on the back face, at +/-90 deg
        for base in (90.0, 270.0):
            t = math.radians(base)
            r0, r1, hw = k["dog_slot_r0"], k["dog_slot_r1"], k["dog_slot_w"] / 2
            ux, uy, vx, vy = math.cos(t), math.sin(t), -math.sin(t), math.cos(t)
            pts = [(ux * r0 + vx * hw, uy * r0 + vy * hw), (ux * r1 + vx * hw, uy * r1 + vy * hw),
                   (ux * r1 - vx * hw, uy * r1 - vy * hw), (ux * r0 - vx * hw, uy * r0 - vy * hw)]
            holes.append(prism(pts, G.z_k0 - 1, G.z_k0 + k["dog_slot_depth"]))
    return single(cut(body, holes), f"knuckle_{side.lower()}", warn)


# ---------------------------------------------------------------- Fin Ray finger (TPU 95A), A-local
def finger_profile(P, G):
    f = P["finger"]
    Lf, W, t, tw = f["length"], f["base_width"], f["rib_thickness"], f.get("tip_width", 0.0)
    xf, y0 = G.xf, G.y0
    xr0, xt = x_face(G, y0), x_face(G, y0 - Lf)  # rev B: pad face toed in about the contact point
    outer = [(xr0, y0), (xf - W, y0), (xf - tw, y0 - Lf), (xt, y0 - Lf)] if tw > 0 else [(xr0, y0), (xf - W, y0), (xt, y0 - Lf)]
    if area(outer) < 0:
        outer.reverse()
    inner = inset(outer, f["wall"])
    cells = []
    if len(inner) >= 3:
        be = math.radians(f["rib_angle"])
        nx, ny, N = math.sin(be), math.cos(be), int(f["ribs"])
        cs = [nx * xf + ny * (y0 - i * Lf / (N + 1)) for i in range(1, N + 1)]
        for kk in range(N + 1):
            poly = inner
            if kk >= 1:
                poly = clip_half(poly, -nx, -ny, -(cs[kk - 1] - t / 2))
            if kk < N and len(poly) >= 3:
                poly = clip_half(poly, nx, ny, cs[kk] + t / 2)
            cells.append(poly)
    cells = [c for c in (clean(c) for c in cells) if len(c) >= 3 and abs(area(c)) > 1.2]
    return outer, cells


def finger(P, G, side, warn):
    f, k = P["finger"], P["knuckle"]
    D = f["depth"]
    z0, z1 = G.zc - D / 2, G.zc + D / 2
    outer, cells = finger_profile(P, G)
    body = prism(outer, z0, z1)
    yb = G.y0 - 0.01
    tab = prism([(G.xf - f["base_width"], yb), (x_face(G, yb), yb), (x_face(G, G.y_root), G.y_root),
                 (G.xf - f["base_width"], G.y_root)], z0, z1)
    body = cut(fuse(body, tab), [prism(c, z0 - 1, z1 + 1) for c in cells])
    body = cut(body, root_holes(P, G, 1.0))
    if side == "B":
        body = body.mirror("YZ")
    return single(body, f"finger_{side.lower()}", warn)


def toe(shape, G):
    """Rotate an A-local pad-face part with the toed-in face: about Z through the contact point (xf, yp)."""
    if not G.toe:
        return shape
    return shape.rotate(cq.Vector(G.xf, G.yp, 0), cq.Vector(G.xf, G.yp, 1), -math.degrees(G.toe))


def nail_a(P, G, warn):
    n, f = P["nail"], P["finger"]
    y1, y0 = G.y0 - (f["length"] - n["length"]), G.y0 - f["length"]
    return toe(box(G.xf, G.xf + n["thickness"], y0, y1, G.zc - n["depth"] / 2, G.zc + n["depth"] / 2), G)


def fsr_parts_b(P, G, warn):
    """Backing with FSR pocket, FSR disc envelope and puck, built A-local then mirrored."""
    s, f = P["fsr"], P["finger"]
    ytip = G.y0 - f["length"]
    D = f["depth"]
    t_b = s["backing_under"] + s["pocket_depth"]
    back = box(G.xf, G.xf + t_b, ytip, ytip + s["backing_length"], G.zc - D / 2, G.zc + D / 2)
    yc = ytip + s["centre_from_tip"]
    xp = G.xf + s["backing_under"]
    pocket = cyl_x(yc, G.zc, s["head_d"] / 2 + 0.15, xp, xp + 2)
    tail = box(xp, xp + 2, yc, ytip + s["backing_length"] + 1, G.zc - s["tail_w"] / 2 - 0.15, G.zc + s["tail_w"] / 2 + 0.15)
    back = cut(back, [pocket, tail])
    sensor = cyl_x(yc, G.zc, s["head_d"] / 2, xp, xp + s["thickness"])
    xs = xp + s["thickness"]
    puck = cyl_x(ytip + s["puck_from_tip"], G.zc, s["puck_d"] / 2, xs, xs + s["puck_t"])
    back, sensor, puck = toe(back, G), toe(sensor, G), toe(puck, G)
    return (single(back.mirror("YZ"), "fsr_backing_b", warn), sensor.mirror("YZ"), puck.mirror("YZ"))


# ---------------------------------------------------------------- bought parts and fasteners (envelopes)
def servo_parts(P, G):
    s = P["servo"]
    a = G.a
    body = box(G.sx0, G.sx1, G.ys0, G.ys1, G.z_cb, G.z_ct)
    ears = box(G.ear_x0, G.ear_x1, G.ear_y0, G.ear_y1, G.z_ear0, G.z_ear1)
    ear_bores = [cyl_z(x, y, s["ear_hole_d"] / 2, G.z_ear0 - 1, G.z_ear1 + 1)
                 for x, y in ear_holes(P, G)]
    ears = cut(ears, ear_bores)
    boss = cyl_z(-a / 2, 0, s["boss_d"] / 2, G.z_ct, G.z_horn0)
    servo = fuse(body, ears, boss)
    horn = cyl_z(-a / 2, 0, s["horn_d"] / 2, G.z_horn0, G.z_horn1)
    if s.get("horn_counterbore_d"):
        recess = cyl_z(-a / 2, 0, s["horn_counterbore_d"] / 2,
                       G.z_horn1 - s["horn_counterbore_depth"], G.z_horn1 + 0.01)
        horn = horn.cut(recess)
    return servo, horn


def fasteners(P, G):
    """Returns (static list, side-A list, side-B list) of (name, solid, material)."""
    k, s, h, w = P["knuckle"], P["servo"], P["housing"], P["wrist_mount"]
    a = G.a
    st, sa, sb = [], [], []
    rev_b = "pin_len" in k
    if rev_b:  # ISO 2338 h8 3 x 16: 0.5 below the mid-plate back face to the bottom of the 1.5 blind hole in the front plate
        zp0 = -G.pl + k["pin_back_recess"]
        zp1 = zp0 + k["pin_len"]
        pin_name = f"pin h8 3x{k['pin_len']:g}"
    else:
        zp0, zp1, pin_name = -G.pl, G.z_fp1, "pin 3m6x15"
    for x in (-a / 2, a / 2):
        st.append((pin_name, cyl_z(x, 0, k["pin_d"] / 2, zp0, zp1), "steel"))
    sl_name = f"bronze bush 3x{k['sleeve_od']:g}x{k['sleeve_len']:g}" if rev_b else "bronze sleeve 3x5x7.7"
    for side, lst in (("A", sa), ("B", sb)):
        L = k["sleeve_len"]
        zc = (G.z_k0 + G.z_k1) / 2
        lst.append((sl_name, cut(cyl_z(0, 0, k["sleeve_od"] / 2, zc - L / 2, zc + L / 2),
                                 [cyl_z(0, 0, k["sleeve_id"] / 2 + 0.01, zc - L, zc + L)]), "bronze"))
        lst.append(("pegs + M2 screw", fuse(*root_holes(P, G, 1.0 if side == "A" else -1.0)), "steel"))
    # shims bear on the PA6-CF hub faces (OD 7 > the Ø6 bush bore; the 10.0 bush sits 0.25 below each face of the 10.5 hub),
    # drawn centred in their 1.0 room: end play = (z_fp0 - 0) - hub - 2 shim_t (CHANGELOG B38)
    sh_name = f"shim {k['shim_id']:g}x{k['shim_od']:g}x{k['shim_t']:g}"
    for x in (-a / 2, a / 2):
        for z0 in (0.0 + 0.075, G.z_k1 + 0.075):
            st.append((sh_name, cut(cyl_z(x, 0, k["shim_od"] / 2, z0, z0 + k["shim_t"]),
                                    [cyl_z(x, 0, k["shim_id"] / 2, z0 - 1, z0 + 2)]), "steel"))
    for yy in (-s["dog_r"], s["dog_r"]):
        if rev_b:  # M3x10 set screw threaded into the horn from the front; its tail is flush with the horn's back face
            L = s["dog_pin_len"]
            sa.append((f"dog set screw M3x{L:g}", cyl_z(0, yy, s["dog_d"] / 2, G.z_horn0, G.z_horn0 + L), "steel"))
        else:
            sa.append(("dog pin M3", cyl_z(0, yy, s["dog_d"] / 2, G.z_horn1, G.z_k0 + k["dog_slot_depth"] - 0.3), "steel"))
    r = w["bolt_circle_d"] / 2
    Lh = w.get("horn_screw_len", 6.0)
    for i in range(4):
        t = math.pi / 4 + i * math.pi / 2
        x, z = r * math.cos(t), r * math.sin(t)
        y_head = G.Y_H - w["clamp_t"]
        st.append((f"M3x{Lh:g} horn screw", fuse(cyl_y(x, z, 1.5, y_head, y_head + Lh), cyl_y(x, z, 2.75, y_head - 2.4, y_head)), "steel"))
    for x, z in h["deck_screws"]:
        st.append(("M3x6 deck screw", fuse(cyl_y(x, z, 1.5, G.yd0, G.yd0 + 6), cyl_y(x, z, 2.75, G.yd0 - 2.4, G.yd0)), "steel"))
        st.append(("M3 heat-set insert", cut(cyl_y(x, z, 2.1, G.yd1, G.yd1 + h["insert_depth"]), [cyl_y(x, z, 1.5, G.yd1 - 1, G.yd1 + 5)]), "brass"))
    for x, z in h.get("deck_pegs", []):  # h8 3 x 6: 3.5 in the spider, 2.5 in the deck (0.5 short of its underside)
        y1 = G.yd1 + w["peg_hole_depth"]
        st.append(("locating pin h8 3x6", cyl_y(x, z, 1.5, y1 - 6.0, y1), "steel"))
    for x, y in ear_holes(P, G):
        if rev_b:  # head under the metal ear; limiter sleeve in the seat; washer + nut on the frame front face (thermal C1)
            li, wa, nu = h["limiter"], h["washer"], h["nut"]
            st.append(("M3x10 ear screw", fuse(cyl_z(x, y, 1.5, G.z_ear0, G.z_ear0 + 10.0), cyl_z(x, y, 2.8, G.z_ear0 - 1.8, G.z_ear0)), "steel"))
            st.append(("limiter sleeve 5x3.2x2.55", cut(cyl_z(x, y, li["od"] / 2, G.zs0, G.zs0 + li["len"]),
                                                        [cyl_z(x, y, li["id"] / 2, G.zs0 - 1, G.zs0 + li["len"] + 1)]), "brass"))
            zw = G.zs0 + li["len"]
            st.append(("washer M3 7x3.2x0.5", cut(cyl_z(x, y, wa["od"] / 2, zw, zw + wa["t"]),
                                                  [cyl_z(x, y, wa["id"] / 2, zw - 1, zw + 2)]), "steel"))
            zn = zw + wa["t"]
            hexn = cq.Workplane("XY", origin=(x, y, zn)).polygon(6, nu["ac"]).extrude(nu["h"]).val()
            st.append(("nut M3", cut(hexn, [cyl_z(x, y, 1.5, zn - 1, zn + nu["h"] + 1)]), "steel"))
        else:
            st.append(("M3x10 ear screw + nut", cyl_z(x, y, 1.5, G.z_ear0, G.z_ear1 + h["wall"] + 2.4), "steel"))
    for x, y in h["standoffs"]:
        if rev_b:  # shank 16 under the head (BOM length; RISK F45), pan head 2.4 on the front face
            st.append(("M3x16 plate screw", fuse(cyl_z(x, y, 1.5, G.z_fp1 - 16, G.z_fp1), cyl_z(x, y, 2.8, G.z_fp1, G.z_fp1 + 1.8)), "steel"))
        else:
            st.append(("M3x16 plate screw", cyl_z(x, y, 1.5, G.z_fp1 - 16 + 2.4, G.z_fp1 + 2.4), "steel"))
    return st, sa, sb


# ---------------------------------------------------------------- assembly bookkeeping
SIDE = {"knuckle_a": "A", "finger_a": "A", "nail_a": "A",
        "knuckle_b": "B", "finger_b": "B", "fsr_backing_b": "B", "fsr_sensor_b": "B", "fsr_puck_b": "B",
        "fasteners_a": "A", "fasteners_b": "B"}
MATERIAL = {"housing": "PETG", "front_plate": "PETG", "wrist_mount": "PETG", "knuckle_a": "PA6CF", "knuckle_b": "PA6CF",
            "finger_a": "TPU", "finger_b": "TPU", "nail_a": "PLA", "fsr_backing_b": "PLA", "fsr_puck_b": "PLA",
            "fsr_sensor_b": "bought", "servo": "bought", "horn": "bought Al", "fasteners": "steel",
            "fasteners_a": "steel", "fasteners_b": "steel"}
FILL = {"housing": "print_fill", "front_plate": "print_fill"}
COLOR = {"housing": (0.78, 0.80, 0.83), "front_plate": (0.70, 0.74, 0.80), "wrist_mount": (0.55, 0.58, 0.64),
         "knuckle_a": (0.20, 0.20, 0.22), "knuckle_b": (0.20, 0.20, 0.22),
         "finger_a": (0.20, 0.62, 0.72), "finger_b": (0.20, 0.62, 0.72), "nail_a": (0.95, 0.85, 0.30),
         "fsr_backing_b": (0.95, 0.85, 0.30), "fsr_sensor_b": (0.10, 0.10, 0.10), "fsr_puck_b": (0.95, 0.40, 0.25),
         "servo": (0.10, 0.12, 0.35), "horn": (0.75, 0.75, 0.78), "fasteners": (0.60, 0.60, 0.62),
         "fasteners_a": (0.60, 0.60, 0.62), "fasteners_b": (0.60, 0.60, 0.62)}
# Catalogue mass per fastener item, g [A: typical ISO 7045 / ISO 4762 / ISO 2338 steel values]. Items not listed
# use envelope volume x the item's density (steel 7.85, brass 8.5, bronze 8.8) [D].
CATALOG_G = {"M3x6 horn screw": 0.45, "M3x6 deck screw": 0.45, "M3x10 ear screw + nut": 0.62 + 0.26,
             "M3x16 plate screw": 0.95, "dog pin M3": 0.80, "pegs + M2 screw": 2 * 0.59 + 0.55 + 0.10,
             "M3x10 ear screw": 0.62, "nut M3": 0.26, "dog set screw M3x10": 0.43}
FAST_ITEMS = {}  # part name -> [(item name, material)] in compound child order (filled by build)


def build(P):
    """Returns (G, local parts dict, info). Side A/B parts are in their own pivot frames (pivot at origin)."""
    P = resolve(P)
    BOUGHT_G["servo"] = float(P["servo"]["mass_g"])
    G = derive(P)
    warn, info = [], {}
    servo, horn = servo_parts(P, G)
    fsr_back, fsr_sensor, fsr_puck = fsr_parts_b(P, G, warn)
    st, fa, fb = fasteners(P, G)
    parts = {
        "housing": housing(P, G, warn),
        "front_plate": front_plate(P, G, warn),
        "wrist_mount": wrist_mount(P, G, warn),
        "knuckle_a": knuckle(P, G, "A", warn, info),
        "knuckle_b": knuckle(P, G, "B", warn, info),
        "finger_a": finger(P, G, "A", warn),
        "finger_b": finger(P, G, "B", warn),
        "nail_a": nail_a(P, G, warn),
        "fsr_backing_b": fsr_back, "fsr_sensor_b": fsr_sensor, "fsr_puck_b": fsr_puck,
        "servo": servo, "horn": horn,
        "fasteners": cq.Compound.makeCompound([s for _, s, _ in st]),
        "fasteners_a": cq.Compound.makeCompound([s for _, s, _ in fa]),
        "fasteners_b": cq.Compound.makeCompound([s for _, s, _ in fb]),
    }
    info["fastener_items"] = {"static": [n for n, _, _ in st], "A": [n for n, _, _ in fa], "B": [n for n, _, _ in fb]}
    for key, lst in (("fasteners", st), ("fasteners_a", fa), ("fasteners_b", fb)):
        FAST_ITEMS[key] = [(n, mat) for n, _, mat in lst]
    info["warnings"] = warn
    info["servo_model"] = P["servo"]["model"]
    info["face_width"] = P["gear"]["face_width"]
    return G, parts, info


def pose(shape, side, G, theta):
    ang = -theta if side == "A" else theta
    px = -G.a / 2 if side == "A" else G.a / 2
    s = shape.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), ang) if ang else shape
    return s.translate(cq.Vector(px, 0, 0))


def world(parts, G, theta):
    return {n: (pose(s, SIDE[n], G, theta) if n in SIDE else s) for n, s in parts.items()}


BOUGHT_G = {"servo": 58.0, "fsr_sensor_b": 0.6}  # S servo (actuators.csv); FSR 402 A
BOUGHT_RHO = {"horn": "Al"}  # horn = modelled 20 x 3 disc envelope x aluminium density [D] (was 5 g [A])


def children(shape):
    from OCP.TopoDS import TopoDS_Iterator
    it, out = TopoDS_Iterator(shape.wrapped), []
    while it.More():
        out.append(cq.Shape.cast(it.Value()))
        it.Next()
    return out


def fastener_mass(P, name, s):
    """Mass and COM of a fastener compound, item by item (CATALOG_G, else volume x density)."""
    mt = P["materials"]
    kids = children(s)
    items = FAST_ITEMS.get(name, [])
    m_tot, mx, rows = 0.0, cq.Vector(0, 0, 0), []
    for i, k in enumerate(kids):
        nm, mat = items[i] if i < len(items) else ("?", "steel")
        V = k.Volume()
        g = CATALOG_G.get(nm, V / 1000.0 * mt[mat])
        c = cq.Shape.centerOfMass(k) if V > 0 else k.Center()
        m_tot += g
        mx = mx + c * g
        rows.append((nm, round(g, 3), "A catalogue" if nm in CATALOG_G else f"D {mat}"))
    return m_tot, (mx * (1.0 / m_tot) if m_tot else s.Center()), rows


def mass_props(P, parts_w, G):
    mt = P["materials"]
    rows = {}
    for n, s in parts_w.items():
        V = s.Volume()
        c = cq.Shape.centerOfMass(s) if V > 0 else s.Center()
        mat = MATERIAL[n]
        if n in FAST_ITEMS:
            g, c, _ = fastener_mass(P, n, s)
        elif n in BOUGHT_G:
            g = BOUGHT_G[n]
            if n == "servo":
                c = s.Center()
        elif n in BOUGHT_RHO:
            g = V / 1000.0 * mt[BOUGHT_RHO[n]]
        else:
            rho = {"PETG": mt["PETG"], "PA6CF": mt["PA6CF"], "TPU": mt["TPU"], "PLA": mt["PLA"], "steel": mt["steel"]}[mat]
            fill = mt["print_fill"] if n in FILL else 1.0
            g = V / 1000.0 * rho * fill
        bb = s.BoundingBox()
        rows[n] = dict(material=mat, volume_cm3=round(V / 1000, 3), mass_g=round(g, 2),
                       com_G=[round(c.x, 2), round(c.y, 2), round(c.z, 2)],
                       u_past_H=round(G.Y_H - c.y, 2),
                       bbox_G=[round(v, 2) for v in (bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax)])
    return rows


STEP_STAMP = re.compile(r"(FILE_NAME\('[^']*',)'[^']*'")
STEP_COUNTER = re.compile(r"(Open CASCADE STEP translator \d+\.\d+) \d+")


def normalise_step(path):
    """STEP writers stamp the export time and a per-process translator counter; fix both so a rebuild is byte-stable."""
    t = Path(path).read_text(encoding="utf-8", errors="surrogateescape")
    t = STEP_COUNTER.sub(r"\1", STEP_STAMP.sub(r"\1'1970-01-01T00:00:00'", t, count=1))
    Path(path).write_text(t, encoding="utf-8", errors="surrogateescape", newline="\n")


def export(parts_w, parts_posed, out, theta, web=True):
    out.mkdir(parents=True, exist_ok=True)
    for n, s in parts_w.items():
        cq.exporters.export(s, str(out / f"{n}.step"))
        normalise_step(out / f"{n}.step")
        cq.exporters.export(s, str(out / f"{n}.stl"), tolerance=0.02, angularTolerance=0.1)
    assy = cq.Assembly(name=f"gripper_theta_{theta:g}")
    for n, s in parts_posed.items():
        assy.add(s, name=n, color=cq.Color(*COLOR[n]))
    assy.export(str(out / "assembly.step")) if hasattr(assy, "export") else assy.save(str(out / "assembly.step"))
    normalise_step(out / "assembly.step")
    sizes = {}
    if web:
        wd = out / "web"
        wd.mkdir(exist_ok=True)
        for old in wd.glob("*"):
            old.unlink()
        for tag, th in (("closed", 0.0),):
            wa = cq.Assembly(name=f"gripper_{tag}")
            for n, s in parts_posed.items() if tag == "closed" else world_cache["open"].items():
                wa.add(s, name=n, color=cq.Color(*COLOR[n]))
            p = wd / f"gripper_{tag}.glb"
            try:
                wa.export(str(p), "GLTF", tolerance=0.12, angularTolerance=0.5)
            except TypeError:
                wa.save(str(p), "GLTF", tolerance=0.12, angularTolerance=0.5)
            sizes[p.name] = p.stat().st_size
    return sizes


world_cache = {}


# ---------------------------------------------------------------- drawings (SVG sheets) and BOM
VIEWS = [("front (+Z)", (0, 0, 1)), ("top (+Y)", (0, 1, 0)), ("side (+X)", (1, 0, 0)), ("iso", (1, 0.8, 1.2))]


def svg_view(shape, d, w=360, h=300):
    opts = {"width": w, "height": h, "marginLeft": 10, "marginTop": 10, "showAxes": False,
            "projectionDir": d, "strokeWidth": 0.25, "strokeColor": (20, 20, 20),
            "hiddenColor": (160, 160, 160), "showHidden": True}
    s = cq.occ_impl.exporters.svg.getSVG(shape, opts)
    s = re.sub(r"<\?xml[^>]*\?>", "", s)
    return s


def drawing_sheet(path, title, shape, notes, rows=(), revision="B"):
    """Four projections, then a 'check after printing' table. rows: (feature, CAD / print, finish and callout, check, rev_b).
    A row changed in revision B carries a revision triangle with the letter B."""
    W = 760
    H_views = 668
    row_h = 13
    H = H_views + 24 + row_h * (len(rows) + 1) + 14 + 12 * (len(notes) + 2)
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="monospace">',
            f'<rect x="0" y="0" width="{W}" height="{H}" fill="white" stroke="black"/>',
            f'<text x="10" y="18" font-size="14" font-weight="bold">{esc(title)}</text>',
            f'<text x="{W - 10}" y="18" font-size="11" text-anchor="end">rev {revision}  |  mm  |  frame G (cad/gripper/README.md)</text>']
    for i, (lab, d) in enumerate(VIEWS):
        x, y = 10 + (i % 2) * 375, 28 + (i // 2) * 320
        inner = svg_view(shape, d)
        inner = inner.replace("<svg", f'<svg x="{x}" y="{y + 12}"', 1)
        body.append(f'<text x="{x}" y="{y + 10}" font-size="11">{lab}</text>')
        body.append(inner)
    y = H_views + 18
    cols = [(10, "Feature"), (190, "CAD (prints)"), (330, "Finish / callout"), (560, "Check after printing")]
    body.append(f'<text x="10" y="{y}" font-size="11" font-weight="bold">Check after printing (triangle B = changed in revision B, cad/gripper/CHANGELOG.md)</text>')
    y += row_h + 2
    for x, t in cols:
        body.append(f'<text x="{x + 14}" y="{y}" font-size="9.5" font-weight="bold">{t}</text>')
    body.append(f'<line x1="10" y1="{y + 3}" x2="{W - 10}" y2="{y + 3}" stroke="black" stroke-width="0.5"/>')
    for r in rows:
        y += row_h
        feat, cad, fin, chk, rb = r
        if rb:
            body.append(f'<polygon points="12,{y} 22,{y} 17,{y - 9}" fill="none" stroke="black" stroke-width="0.8"/>'
                        f'<text x="15" y="{y - 1}" font-size="6">B</text>')
        for (x, _), t in zip(cols, (feat, cad, fin, chk)):
            body.append(f'<text x="{x + 14}" y="{y}" font-size="9">{esc(str(t))}</text>')
    bb = shape.BoundingBox()
    lines = [f"envelope X {bb.xlen:.2f} x Y {bb.ylen:.2f} x Z {bb.zlen:.2f} mm (frame G, theta 0)"] + list(notes)
    y += 18
    for t in lines:
        body.append(f'<text x="10" y="{y}" font-size="9.5">{esc(t)}</text>')
        y += 12
    body.append("</svg>")
    Path(path).write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def sheet_rows(P, G):
    """Per printed part: the dimensions a student checks on the print, with the tolerance-note callouts."""
    s, k, f, h, w, g, n, fs = P["servo"], P["knuckle"], P["finger"], P["housing"], P["wrist_mount"], P["gear"], P["nail"], P["fsr"]
    a = G.a
    sd = h["standoffs"]
    ds = h["deck_screws"]
    pk = h.get("deck_pegs", [])
    c = h["cradle_pocket_clear"]
    pocket_w = s["body_x"] + 2 * c
    pocket_l = s["body_y"] + 2 * c
    tx, ty = tc_hole_xy(P, G)
    eh = ear_holes(P, G)
    ex = sorted({round(p[0], 2) for p in eh})
    R = {}
    R["housing"] = [
        ("Datum D: mid-plate front face", "z 0", "flat 0.1 [A]", "straight edge + feeler", False),
        ("Pin A / pin B holes", f"Ø{k['pin_hole_cad']} at x ∓{a/2:.2f}, y 0", "line-ream Ø3.0 H7 with front plate; pos ±0.10, perp Ø0.10 | D", "3.0 pin gauge enters both plates", True),
        ("Servo-boss bore (web)", f"Ø{h['boss_bore_cad']} at pin A, web z {G.zw0:.1f}..{G.zw1:.1f}", f"REAM Ø{h['boss_bore_ream']} H7; pos to pin A ±0.10", "Ø9 gauge / the servo boss drops in", True),
        ("Cradle pocket", f"{pocket_l:.1f} (X) x {pocket_w:.2f} (Y)", f"= measured case width {s['body_x']} + 0.40 (row 3)", "servo drops in by hand, no force", True),
        ("Ear seat holes (4)", f"Ø{h['ear_seat_hole']} at x {ex[0]} / {ex[1]}, y ±{s['ear_hole_pitch_x']/2:g}", "slip for Ø5.0 sleeve (Ø4.9 if pressed: coupon)", "sleeve slides in", True),
        ("Seat frame length", f"x {G.ear_x0 - 1 - h['frame_end_ext']:.1f}..{G.ear_x1 + 1 + h['frame_end_ext']:.1f}", "2.5 mm PETG round each seat hole (C1)", "caliper", True),
        ("Thermocouple hole", f"Ø{h['tc_hole_d']} at ({tx:.1f}, {ty:.1f}), {h['wall'] - h['tc_hole_short_of_ear']:.1f} deep", "from frame front face, stops 0.5 short of the ear (C3)", "1.0 drill bit as depth gauge", True),
        ("Nut notches in end walls (4)", f"R{h['nut_notch_r']} x {h['nut_notch_washer_h']} + R{h['nut_notch_r_nut']} to {h['nut_notch_h']}", f"washer + nut room; wall {G.wall_notch[0]:.2f} / {G.wall_notch[1]:.2f} left", "nut turns by hand", True),
        ("Horn relief, A end wall", f"R{s['horn_d']/2 + h['horn_relief']:.1f} + slide channel", f"horn runs {h['horn_relief']:.1f} clear radially (R{s['horn_d']/2 + h['horn_relief']:.1f} on a Ø{s['horn_d']:g} horn)", "horn slides in from below", True),
        ("Dog arc slots (2)", f"R{s['dog_r']} ± {(s['dog_d'] + 1.5)/2:g}, -16..+25 deg", "set screw passes", "M3 set screw passes freely", False),
        ("Deck screw holes (4)", f"Ø{h['clearance_hole_cad']} at {', '.join(f'({x:g}, {z:g})' for x, z in ds)}", "driver reaches each from below", "40 mm driver fits straight", True),
        ("Deck peg holes (2)", f"Ø{h['deck_peg_hole_cad']} at {', '.join(f'({x:g}, {z:g})' for x, z in pk)}", "REAM Ø3.0 H7 (slip for h8 pin)", "3.0 pin slides in", True),
        ("Standoffs (3)", f"Ø{h['standoff_d']} x {G.z_fp0:g} at {', '.join(f'({x:g}, {y:g})' for x, y in sd)}", "M3 pilot Ø2.5; tops coplanar 0.05", "caliper height", True),
        ("Deck", f"x ±{h['deck_half_x']}, y {G.yd0:g}..{G.yd1:g}", "", "caliper", True),
    ]
    R["front_plate"] = [
        ("Pin holes (2), blind", f"Ø{k['pin_hole_cad']} x {k['pin_front_blind']} deep at x ∓{a/2:.2f}", "ream with the housing; pin captured (row 10)", "1.0 front skin left", True),
        ("Standoff screw holes (3)", f"Ø{h['clearance_hole_cad']} at {', '.join(f'({x:g}, {y:g})' for x, y in sd)}", "", "M3 passes", True),
        ("Plate thickness", f"{G.pl} (z {G.z_fp0:g}..{G.z_fp1:g})", "", "caliper", True),
        ("Camera pad bores (2)", f"Ø{P['camera_pad']['bore_d']} x {P['camera_pad']['bore_depth']}, {P['camera_pad']['bolt_pitch']} apart", "M3 heat-set inserts", "insert flush", False),
    ]
    R["wrist_mount"] = [
        ("Datum A: recess floor", "at horn face H", "flat 0.2 [A]", "seat on a flat plate, no rock", False),
        ("Pilot recess (datum B)", f"Ø{w['recess_d_cad']} x {w['recess_depth']}, {w['recess_chamfer']}x45 chamfer", "prints ~19.4; size from coupon item 2", "slides over the real horn by hand", True),
        ("Horn screw holes (4)", f"Ø{w['clearance_hole_cad']} on Ø{w['bolt_circle_d']} BC", "pos Ø0.2 (M) | A | B (M) | (row 7)", "M3 passes all four at once", True),
        ("Counterbores (4)", f"Ø{w['counterbore_d']}", "", "pan head drops in", False),
        ("Hub", f"Ø{2*w['hub_r_low']} to H+1, Ø{2*w['hub_r_band']} to H+{w['band_to_H']}", "keep-out R9", "caliper", False),
        ("Insert bores (4)", f"Ø{h['insert_bore']} x {h['insert_depth']} at {', '.join(f'({x:g}, {z:g})' for x, z in ds)}", "M3 heat-set inserts", "insert flush", True),
        ("Locating-pin holes (2)", f"Ø{w['peg_hole_cad']} x {w['peg_hole_depth']} at {', '.join(f'({x:g}, {z:g})' for x, z in pk)}", "REAM Ø3.0; h8 3x6 pin bonded", "pin stands 2.5 proud", True),
    ]
    kA = [
        ("Gear sector", f"m {g['module']} z {g['teeth']} a {g['pressure_angle']} x {g['profile_shift']}", "profile = gear_profile.dxf; jt 0.25", "mesh by hand, no bind", False),
        ("Face width (hub thickness)", f"{G.b:g}", "par 0.1 | D", "caliper", True),
        ("Bush bore", f"Ø{k['sleeve_bore_cad']}", f"REAM Ø{k['sleeve_od']} H7, press 3x{k['sleeve_od']:g}x{k['sleeve_len']:g} bush", "pin-gauge the pressed bore; grade pins", True),
        ("Root U-block pegs", f"2x Ø{k['peg_d']} {k['peg_pitch']} apart + Ø{k['root_screw_d']} M2", f"root relief {k['root_relief']} on pad side", "Ø2 dowel passes", True),
    ]
    R["knuckle_a"] = kA + [("Dog slots (2)", f"{k['dog_slot_w']} wide, r {k['dog_slot_r0']}..{k['dog_slot_r1']}, {k['dog_slot_depth']} deep, ±90 deg",
                            "lash about ±1.5 deg (row 1)", "set screw slides, no bind", True)]
    R["knuckle_b"] = kA
    fr = [
        ("Fin Ray body", f"L {f['length']}, W {f['base_width']}, depth {f['depth']}", f"wall {f['wall']}, {f['ribs']} ribs x {f['rib_thickness']} at {f['rib_angle']} deg", "caliper", False),
        ("Pad face toe-in", f"{f['toe_in_deg']} deg about the contact point {f.get('contact_from_tip', 5)} above the tip",
         f"root end {40 * math.tan(G.toe):.2f} nearer the jaw centre (row 4)", "faces parallel at first touch", True),
        ("Root tab peg holes", f"2x Ø{k['peg_d']} {k['peg_pitch']} apart + Ø{k['root_screw_d']}", "", "Ø2 dowel passes", True),
    ]
    R["finger_a"] = fr
    R["finger_b"] = fr
    R["nail_a"] = [("Nail", f"{n['thickness']} x {n['length']} x {n['depth']}", "bond flat on the toed-in pad face at the tip", "flush with tip edge", True)]
    R["fsr_backing_b"] = [("Backing", f"{fs['backing_under'] + fs['pocket_depth']} x {fs['backing_length']} x {f['depth']}", "bond flat on the toed-in pad face", "", True),
                          ("FSR pocket", f"Ø{fs['head_d'] + 0.3:.2f} x {fs['pocket_depth']}, tail {fs['tail_w'] + 0.3:.1f}", "FSR 402 head drops in", "", False)]
    R["fsr_puck_b"] = [("Puck", f"Ø{fs['puck_d']} x {fs['puck_t']}", f"{fs['puck_from_tip']} above the tip, inside the active area", "", False)]
    return R


def drawings(P, G, parts_w, mp, dd):
    dd.mkdir(parents=True, exist_ok=True)
    g, h, s = P["gear"], P["housing"], P["servo"]
    rows = sheet_rows(P, G)
    sheets = {
        "housing": ("Housing (PETG, 60 % gyroid) - deck, mid plate, boss web, cradle, standoffs", [
            "Print mid plate down (datum D on the bed); supports under the deck and the boss web.",
            f"Servo {s['model']} located by its Ø{s['boss_d']} output boss in the reamed web bore (T14B-boss34); the pocket only has to let it drop in (T14-boss).",
            "Proposed callouts (tolerance_stacks.md, Datum frame and GD&T): pin holes pos Ø0.2 | A | B | C |, perp Ø0.10 | D |; coaxial ±0.03 (line-ream)."]),
        "front_plate": ("Front plate (PETG, 60 %) - pin caps, standoff screws, camera pad", [
            "Print face down. Ream the blind pin holes together with the housing in one pass (prep step)."]),
        "wrist_mount": ("Wrist mount plate (PETG, 100 %) - SO-101 wrist-roll horn interface (frame I)", [
            "Print recess face up (datum A flat, no supports). H at y = %.2f in frame G; roll axis x 0, z 0." % G.Y_H,
            f"Horn screws: length by the measured horn hole depth (wrist_mount.horn_screw_rule): M3x6 needs ≥ 3.75 mm."]),
        "knuckle_a": ("Knuckle A (PA6-CF, 100 %) - driven, integral gear sector (6 teeth), dog slots", [
            "Print hub flat on the bed, hardened nozzle, dried filament; anneal per the filament sheet."]),
        "knuckle_b": ("Knuckle B (PA6-CF, 100 %) - idler, integral gear sector (7 teeth)", [
            "Mirror of knuckle A without dog slots. Firmware angle limits only: no hard stop may load the mesh."]),
        "finger_a": ("Finger A (TPU 95A, printed flat, 100 %) - Fin Ray, carries the PLA nail", [
            "Print flat (rib plane in X-Y; TPU Z strength 6.4 MPa). Finger B is the mirror image."]),
        "finger_b": ("Finger B (TPU 95A, printed flat, 100 %) - Fin Ray, carries the FSR backing", [
            "Mirror of finger A."]),
        "nail_a": ("Nail A (PLA, 100 %)", ["Print flat; bond with CA, jaw open 20 deg."]),
        "fsr_backing_b": ("FSR backing B (PLA, 100 %)", ["Print pocket up; bond with CA, jaw open 20 deg."]),
        "fsr_puck_b": ("FSR puck B (PLA, 100 %)", ["Print flat; one drop of CA on the FSR active area."]),
    }
    for nm, (title, notes) in sheets.items():
        drawing_sheet(dd / f"{nm}.svg", title, parts_w[nm], notes, rows.get(nm, ()), P.get("revision", "A"))
    return list(sheets)


PRINT_ROWS = [
    # part, qty, material, infill, orientation, post-processing
    ("housing", 1, "PETG", "60 % gyroid, 0.2 mm layers, 4 walls", "mid plate (datum D) on the bed; supports under deck and boss web",
     "ream pin holes 3.0 H7 (with front plate), boss bore 9.0 H7 (1.6 mm web on supports: clear support, light feed, tear-out risk), deck peg holes 3.0 H7; check Ø1 thermocouple hole"),
    ("front_plate", 1, "PETG", "60 % gyroid", "front face on the bed", "ream blind pin holes 3.0 H7 with the housing; 2 heat-set inserts in the camera pad (optional)"),
    ("wrist_mount", 1, "PETG", "100 %", "recess face up", "ream peg holes 3.0; press 4 M3 heat-set inserts (iron)"),
    ("knuckle_a", 1, "PA6-CF", "100 %", "hub face on the bed; hardened nozzle, dried, annealed", "ream bore 6.0 H7, press bush 3x6x10; pin-gauge the pressed bore"),
    ("knuckle_b", 1, "PA6-CF", "100 %", "hub face on the bed", "ream bore 6.0 H7, press bush 3x6x10; pin-gauge the pressed bore"),
    ("finger_a", 1, "TPU 95A", "100 %", "flat (rib plane on the bed)", "clear the Ø2 peg holes with a 2.0 drill by hand"),
    ("finger_b", 1, "TPU 95A", "100 %", "flat (rib plane on the bed)", "as finger A"),
    ("nail_a", 1, "PLA", "100 %", "flat", "bond (CA) on finger A pad"),
    ("fsr_backing_b", 1, "PLA", "100 %", "pocket up", "bond (CA) on finger B pad"),
    ("fsr_puck_b", 1, "PLA", "100 %", "flat", "bond (CA) on the FSR active area"),
]


def bought_rows(P):
    """(item, qty, specification, supplier class, unit USD [A unless tagged], note)"""
    k, h, w, s = P["knuckle"], P["housing"], P["wrist_mount"], P["servo"]
    Lh = w.get("horn_screw_len", 6.0)
    return [
        ("Servo", 1, f"{s['model']} ({s['id']}), 25T spline, {s['rail_V']} V rail", "hobby RC vendor (aifitlab listing)", s["price_usd"], "S price; dimensions [A]: measure on the delivered part (README)"),
        ("Horn", 1, "25T aluminium disc horn Ø20 x 3 with a counterbored centre (screw head flush or below the face), two M3 holes drilled and tapped at r 7, ±90 deg", "hobby RC vendor", 3.00, "A; the head may stand at most 0.4 above the horn face (0.5 gap to the mid plate)"),
        ("Horn centre screw", 1, "M3x6 ISO 7380 button head, 2.0 mm hex", "hardware (McMaster/Misumi class)", 0.10, "replaces the Phillips screw; driven through the Ø3 pin A bore"),
        ("Dog set screws", 2, f"M3x{s['dog_pin_len']:g} ISO 4026 socket set screw, flat point, 45H", "hardware", 0.10, "thread-locker 243"),
        ("Knuckle pins", 2, f"{k['pin_spec']}", "precision pins (Misumi/McMaster class)", 0.40, "buy 10 to grade; retaining compound 638 in the mid plate"),
        ("Knuckle bushes", 2, f"sintered bronze plain bush 3 x {k['sleeve_od']:g} x {k['sleeve_len']:g} (oil-impregnated)", "bearing supplier (Oilite class)", 0.60, "no 3 x 5 found [A]; buy 5 for the coupon"),
        ("Shims", 4, f"shim washer {k['shim_id']:g} x {k['shim_od']:g}, 0.05 mm step assortment (0.1-1.0) [A]", "hardware (RC shim class)", 0.10,
         f"one stack per knuckle face, {k['shim_t']:g} nominal; bears on the hub face (OD > the Ø{k['sleeve_od']:g} bush); picked at assembly to {k['end_play']:g} ± 0.05 end play"),
        ("Deck locating pins", 2, "ISO 2338 h8 3 x 6", "precision pins", 0.30, "bonded in the spider, slip in the deck (row 5)"),
        ("Horn screws", 4, f"M3x{Lh:g} pan head ISO 7045", "hardware", 0.05, f"length per measured horn hole depth: M3x{Lh:g} needs ≥ 3.75 mm"),
        ("Deck screws", 4, "M3x6 pan head ISO 7045", "hardware", 0.05, ""),
        ("Heat-set inserts", 4, f"M3 brass heat-set insert, bore {h['insert_bore']} x {h['insert_depth']}", "hardware", 0.15, "spider"),
        ("Camera-pad inserts (optional)", 2, "M3 brass heat-set insert 4.2 x 4.5", "hardware", 0.15, "only for the wrist UVC option"),
        ("Servo tester or controller", 1, "servo tester, or the ESP32 controller on the 6.5 V rail", "hobby RC / course kit", 0.00, "steps 11 and 29-31 drive the jaw"),
        ("Ear screws", 4, "M3x10 pan head ISO 7045", "hardware", 0.05, "head under the servo ear"),
        ("Compression limiters", 4, f"{h['limiter']['spec']}", "metal tube stock (K&S class)", 0.10, "thermal C1"),
        ("Washers", 4, f"{h['washer']['spec']}", "hardware", 0.02, "mandatory under each nut"),
        ("Nuts", 4, "M3 hex nut ISO 4032", "hardware", 0.02, "on the frame front face, in the notch"),
        ("Front plate screws", 3, "M3x16 pan head, self-tapping into the Ø2.5 standoff pilots", "hardware", 0.06, "stop at first snug"),
        ("Finger pegs", 4, "dowel pin 2 x 24 (= root block width; the 26 mm CAD solid is the hole tool, 1 mm proud each side)", "hardware", 0.20, "RISK F48"),
        ("Finger root bolts", 2, "M2x30 + nut (24 block + 1.6 nut + thread)", "hardware", 0.08, "RISK F48; was M2x25, too short"),
        ("FSR", 1, "Interlink FSR 402 (Adafruit 166)", "Adafruit", 7.95, "S"),
        ("Thermocouple", 1, "type-K bead, Ø ≤ 1.0 (test only)", "test equipment", 0.00, "thermal.md 6; not on the arm"),
        ("Consumables", 1, "retaining compound 638, thread-locker 243, CA glue", "hardware", 0.00, "shared"),
    ]


TOOLS = ["M3 tap and 2.5 mm drill (horn dog holes)", "7 mm spanner or pliers", "tweezers", "flat block", "depth gauge (horn hole depth)", "torque-limited screwdriver (plate screws, RISK F45)", "3.0 mm H7 hand reamer", "6.0 mm H7 hand reamer", "9.0 mm H7 hand reamer", "3 mm pin gauges (0.002 step) or a 0-25 micrometer",
         "feeler gauges 0.05-0.5", "2.0 mm and 1.5 mm hex keys", "Phillips #1", "soldering iron with insert tip", "arbor press or vice",
         "caliper with depth rod", "1.0 mm drill (thermocouple hole check)"]


def write_bom(P, mp, dd):
    price = {"PETG": 25, "PA6-CF": 60, "TPU 95A": 35, "PLA": 20}
    L = ["# Gripper bill of materials (revision %s)" % P.get("revision", "A"), "",
         "Generated by `cad/gripper/gripper_concept.py` from `params.json`. Mass [D] = CAD volume x density x fill; filament cost [A] = mass x $/kg; "
         "bought parts [A] unit prices unless tagged S. Revision B changes are listed in `cad/gripper/CHANGELOG.md`.", "",
         "## Printed parts", "",
         "| Part | Qty | Material | Infill | Orientation | Post-processing | Mass g | Filament USD |", "|---|---:|---|---|---|---|---:|---:|"]
    tot_g, tot_c = 0.0, 0.0
    for n, q, mat, fill, orient, post in PRINT_ROWS:
        g = mp[n]["mass_g"]
        c = g / 1000 * price.get(mat, 30) / (P["materials"]["print_fill"] if n in FILL else 1.0)
        tot_g += g * q
        tot_c += c * q
        L.append(f"| {n} | {q} | {mat} | {fill} | {orient} | {post} | {g:.1f} [D] | {c:.2f} |")
    L += ["", "## Bought parts", "", "| Item | Qty | Specification | Supplier class | Unit USD | Note |", "|---|---:|---|---|---:|---|"]
    bc = 0.0
    for it, q, spec, sup, u, note in bought_rows(P):
        bc += q * u
        L.append(f"| {it} | {q} | {spec} | {sup} | {u:.2f} | {note} |")
    fg = mp["fasteners"]["mass_g"] + mp["fasteners_a"]["mass_g"] + mp["fasteners_b"]["mass_g"]
    other = mp["servo"]["mass_g"] + mp["horn"]["mass_g"] + mp["fsr_sensor_b"]["mass_g"]
    tot_g += fg + other
    pg = sum(mp[n]['mass_g'] for n, *_ in PRINT_ROWS)
    L += ["", "## Mass and cost", "",
          "| Item | Qty | Material | Source | Mass g | USD | Basis |", "|---|---:|---|---|---:|---:|---|",
          f"| printed parts | {len(PRINT_ROWS)} | PETG / PA6-CF / TPU / PLA | printed | {pg:.1f} | {tot_c:.2f} | D mass; A filament price |",
          f"| servo | 1 | - | bought | {mp['servo']['mass_g']:.1f} | {P['servo']['price_usd']:.2f} | S listing |",
          f"| horn | 1 | Al | bought | {mp['horn']['mass_g']:.1f} | 3.00 | D envelope x density |",
          f"| FSR | 1 | - | bought | {mp['fsr_sensor_b']['mass_g']:.1f} | 7.95 | A |",
          f"| fasteners, pins, bushes, sleeves, other bought items | 1 set | steel / bronze / brass | bought | {fg:.1f} | {bc - P['servo']['price_usd'] - 3.00 - 7.95:.2f} | D per item |",
          f"| **total on the arm (no cloth, no wiring)** | | | | **{tot_g:.1f}** | **{tot_c + bc:.2f}** | |", "",
          f"Unrounded {tot_g:.2f} g; `fitcheck.py` adds 13.5 g cloth and 5.0 g wiring ({tot_g + 18.5:.2f} g) for R10.", "",
          f"- Printed parts {sum(mp[n]['mass_g'] for n, *_ in PRINT_ROWS):.1f} g; servo {mp['servo']['mass_g']:.1f} g [S listing]; horn {mp['horn']['mass_g']:.1f} g [D]; "
          f"FSR {mp['fsr_sensor_b']['mass_g']:.1f} g [A]; fasteners, pins, bushes, sleeves {fg:.1f} g [D per item, `out/parts.json` fastener_masses_g].",
          f"- **Total on the arm (no cloth, no wiring): {tot_g:.1f} g**; filament {tot_c:.2f} USD + bought {bc:.2f} USD = **{tot_c + bc:.2f} USD**.",
          "", "## Tools for post-processing and assembly", ""] + [f"- {t}" for t in TOOLS]
    L += ["", "## Measure before you buy or assemble", "",
          "- Horn hole depth on the arm (DB M15): pick the horn screw length by `wrist_mount.horn_screw_rule` (M3x6 needs ≥ 3.75 mm; 3.5-3.7 marginal; shallower: drill and re-tap).",
          "- Servo case width in 3 places on 3 units: pocket = largest + 0.40 (set `servo.body_x`); boss diameter; ear pattern (servo `measure_on_delivered_part`).",
          "- Pressed bush bores (pin gauge) and each pin (micrometer): pair them for 0.000-0.020 clearance.",
          "- Shim stack at each pin with feeler gauges for 0.3 ± 0.05 end play.",
          "", "Off-arm (not in the mass): primary camera Pi Camera 3 on a table post (camera.md 6), ESP32 DevKitC, INA219, 6.5 V buck, 1000 uF cap."]
    (dd / "BOM.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    return round(tot_g, 1), round(tot_c + bc, 2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--params", type=Path, default=HERE / "params.json")
    ap.add_argument("--angle", type=float, default=0.0, help="assembly jaw angle, deg (0 = closed, + = open)")
    ap.add_argument("--out", type=Path, default=HERE / "out")
    ap.add_argument("--drawings", type=Path, default=HERE / "drawings")
    ap.add_argument("--no-drawings", action="store_true")
    args = ap.parse_args(argv)
    P = resolve(json.loads(args.params.read_text(encoding="utf-8")))
    G, parts, info = build(P)
    bad = [n for n, s in parts.items() if not s.isValid()]
    pw = world(parts, G, 0.0)
    world_cache["open"] = world(parts, G, 20.0)
    sizes = export(pw, world(parts, G, args.angle), args.out, args.angle)
    mp = mass_props(P, pw, G)
    mp_faces = {}
    info["fastener_masses_g"] = {n: fastener_mass(P, n, pw[n])[2] for n in FAST_ITEMS}
    for n, s in pw.items():  # face count per exported part: with volume and bbox, the check for files that are not byte-stable
        mp_faces[n] = len(s.Faces())
    summary = {"revision": P.get("revision", "A"), "frame": "G (README)", "Y_H": round(G.Y_H, 3), "a": G.a, "xf": round(G.xf, 3), "y0": round(G.y0, 3),
               "toe_in_deg": P["finger"].get("toe_in_deg", 0.0), "r_c_contact_face": {k: round(v, 3) for k, v in G.r_c_face.items()},
               "z_stack": {"case": [round(G.z_cb, 3), round(G.z_ct, 3)], "boss_web": [round(G.zw0, 3), round(G.zw1, 3)],
                           "horn": [round(G.z_horn0, 3), round(G.z_horn1, 3)], "mid_plate": [-G.pl, 0.0], "knuckles": [G.z_k0, G.z_k1],
                           "front_plate": [G.z_fp0, G.z_fp1], "seat_frame": [round(G.zs0, 3), round(G.zs1, 3)]},
               "face_count": mp_faces,
               "r_c_nominal": round(G.r_c, 2), "end_play": round(G.end_play, 3), "closed_gap_tpu": round(G.closed_gap, 3), "zc": G.zc,
               "pivot_to_H": round(G.Y_H, 2), "tip_u_past_H": round(G.Y_H - (G.y0 - P["finger"]["length"]), 2),
               "parts": mp, "web_sizes_bytes": sizes, "web_total_bytes": sum(sizes.values()),
               "invalid": bad, **info}
    (args.out / "parts.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
    if not args.no_drawings:
        drawings(P, G, pw, mp, args.drawings)
        summary["bom_total"] = write_bom(P, mp, args.drawings)
    print(f"{'part':<16}{'mat':<8}{'cm3':>8}{'g':>8}{'u past H':>10}")
    for n, r in mp.items():
        print(f"{n:<16}{r['material']:<8}{r['volume_cm3']:>8.2f}{r['mass_g']:>8.1f}{r['u_past_H']:>10.1f}")
    print(f"total {sum(r['mass_g'] for r in mp.values()):.1f} g; H at y = {G.Y_H:.2f}; r_c (contact face) A {G.r_c_face['A']:.2f} / B {G.r_c_face['B']:.2f} "
          f"(nominal {G.r_c:.1f}); end play {G.end_play:.2f}; web {summary['web_total_bytes']/1e6:.2f} MB")
    if info["warnings"]:
        print("warnings: " + "; ".join(info["warnings"]), file=sys.stderr)
    if bad:
        print(f"invalid solids: {bad}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
