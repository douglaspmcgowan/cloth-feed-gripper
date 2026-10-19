#!/usr/bin/env python3
"""Fit check of the rebuilt gripper on the SO-101 wrist-roll horn.

Places the new gripper (gripper_concept.build) in interface frame I (research/so101.md: origin = horn
pattern centre on the stock rim plane, +Z = roll axis into the gripper, horn face H at z = +1), loads the
stock Wrist_Roll_Follower + Moving_Jaw (the parts it replaces) and the stationary wrist link + servo 5
from the upstream assembly, and checks:
  1. keep-out bands (params wrist_interface and tolerance_stacks.md fix 5) on the rolling gripper;
  2. roll clearance: per z band, gripper r_max vs stationary r_min (full 320 deg roll treated as a ring);
  3. jaw sweep theta -11..+20: boolean intersection volumes between every moving part (knuckles, fingers,
     nail, FSR stack, fasteners_a / fasteners_b incl. the dog pins) and every static part, A vs B;
  4. mass, COM and the R10 mass-moment against DESIGN-BASIS (43,720 g mm; stock 33,380);
  5. wrist flex (R9): gripper and stock gripper rotated about the wrist-flex axis (61.55 from H) over
     +/-95 deg at 4 roll angles, boolean volume against the forearm (Under_arm, wrist motor holder, servo 4).
Every r_max / r_min is BRep-exact to 0.02 mm (slab boolean + ring-volume bisection), not tessellation
vertices: a cylinder face has vertices only on its end edges, so vertex sampling misses it in a narrow band.
Writes out/fitcheck.json and drawings/fitcheck.svg.

    uv run --with cadquery python cad/gripper/fitcheck.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import cadquery as cq

HERE = Path(__file__).resolve().parent
SO = HERE.parent / "so101"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SO))
import gripper_concept as gc  # noqa: E402
import measure_interface as mi  # noqa: E402


def G_to_I(shape, G):
    """Frame G -> I: (x, y, z) -> (x, z, -y), then H (y = Y_H) to z_I = +1."""
    s = shape.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), -90)
    return s.translate(cq.Vector(0, 0, G.Y_H + 1.0))


def world_to_I(shape, origin, R):
    from OCP.gp import gp_Trsf, gp_Ax3, gp_Pnt, gp_Dir
    ax = gp_Ax3(gp_Pnt(*origin), gp_Dir(*R[2]), gp_Dir(*R[0]))
    t = gp_Trsf()
    t.SetTransformation(ax)
    return cq.Shape.cast(shape.transformShape(t).wrapped) if False else shape._apply_transform(t)


def pts_of(shape, tol=0.4):
    return mi.sample_points(shape, tol=tol)


def to_I_shape(shape, origin, R):
    """World shape -> frame I (BRep), the same map as measure_interface.to_I for points."""
    from OCP.gp import gp_Trsf, gp_Ax3, gp_Pnt, gp_Dir
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    ax = gp_Ax3(gp_Pnt(*map(float, origin)), gp_Dir(*map(float, R[2])), gp_Dir(*map(float, R[0])))
    t = gp_Trsf()
    t.SetTransformation(ax)
    return cq.Shape.cast(BRepBuilderAPI_Transform(shape.wrapped, t, True).Shape())


BIG = 400.0
PHIS = [-95, -70, -45, -20, 0, 20, 45, 70, 95]


EPS_Z = 0.01  # band ends inset 0.01 mm so faces lying on a band edge (and 0.001 mm fuse overlaps) do not count


def slab(shape, z0, z1):
    z0, z1 = z0 + EPS_Z, z1 - EPS_Z
    return shape.intersect(cq.Solid.makeBox(2 * BIG, 2 * BIG, z1 - z0, cq.Vector(-BIG, -BIG, z0)))


def ring_out(r, z0, z1):
    return cq.Solid.makeCylinder(BIG, z1 - z0 + 2, cq.Vector(0, 0, z0 - 1)).cut(
        cq.Solid.makeCylinder(r, z1 - z0 + 2, cq.Vector(0, 0, z0 - 1)))


def vol(s):
    try:
        return s.Volume()
    except Exception:
        return 0.0


def brep_r(shape, z0, z1, which="max", tol=0.02):
    """BRep r_max (or r_min) about the Z axis of the material in z0 < z < z1; None if there is none."""
    sl = slab(shape, z0, z1)
    if vol(sl) < 1e-4:
        return None
    vs = np.array([v.toTuple() for v in sl.Vertices()]) if sl.Vertices() else np.zeros((1, 3))
    rv = np.hypot(vs[:, 0], vs[:, 1])
    bb = sl.BoundingBox()
    if which == "max":  # volume outside radius R > 0  <=>  R < r_max
        lo, hi = float(rv.max()) - 1e-3, float(np.hypot(max(abs(bb.xmin), abs(bb.xmax)), max(abs(bb.ymin), abs(bb.ymax)))) + 0.05
        while hi - lo > tol:
            mid = 0.5 * (lo + hi)
            if vol(sl.intersect(ring_out(mid, z0, z1))) > 1e-5:
                lo = mid
            else:
                hi = mid
        return hi
    lo, hi = 0.0, float(rv.min()) + 1e-3  # r_min: volume inside radius R > 0  <=>  R > r_min
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if vol(sl.intersect(cq.Solid.makeCylinder(mid, z1 - z0 + 2, cq.Vector(0, 0, z0 - 1)))) > 1e-5:
            hi = mid
        else:
            lo = mid
    return lo


def bands(p, edges):
    r = np.hypot(p[:, 0], p[:, 1])
    out = []
    for a, b in edges:
        m = (p[:, 2] >= a + 0.01) & (p[:, 2] <= b - 0.01)
        out.append(None if not m.any() else (float(r[m].min()), float(r[m].max())))
    return out


def main():
    t0 = time.time()
    P = json.loads((HERE / "params.json").read_text(encoding="utf-8"))
    wi = P["wrist_interface"]
    G, parts, info = gc.build(P)
    res = {"frame": "I (research/so101.md)", "H_z_I": 1.0, "Y_H_in_G": round(G.Y_H, 3)}

    # ---- stock and stationary parts from the upstream assembly
    asm = mi.read_assembly(SO / "SO101 Assembly.step")
    fol, origin, R, to_I, holes_I = mi.interface_frame(asm)
    res["horn_holes_I"] = [[round(float(v), 2) for v in h] for h in holes_I]
    stat_names = [k for k in asm if k.startswith("Wrist_Roll_Pitch")] + ["ST3215 Servo v2:5"]
    stock_names = [k for k in asm if k.startswith("Wrist_Roll_Follower") or k.startswith("Moving_Jaw")] + ["ST3215 Servo v2:6"]
    # stationary material in frame I (BRep); the servo-5 horn and spline roll with the gripper, so
    # servo 5 is cut at its case top (z_I -3.8)
    stat_I = [to_I_shape(asm[n], origin, R) for n in stat_names]
    stat_I[-1] = stat_I[-1].intersect(cq.Solid.makeBox(2 * BIG, 2 * BIG, BIG, cq.Vector(-BIG, -BIG, -3.8 - BIG)))
    stat_comp = cq.Compound.makeCompound(stat_I)
    stock_comp = cq.Compound.makeCompound([to_I_shape(asm[n], origin, R) for n in stock_names])
    fol_bb = to_I_shape(fol, origin, R).BoundingBox()
    res["frame_check_follower_z_I"] = [round(fol_bb.zmin, 2), round(fol_bb.zmax, 2)]

    # ---- new gripper in I at theta 0 and at the sweep angles
    rolling = {n: G_to_I(s, G) for n, s in gc.world(parts, G, 0.0).items()}
    comp = cq.Compound.makeCompound(list(rolling.values()))
    res["r_method"] = ("BRep: slab boolean (band ends inset 0.01 mm) + ring-volume bisection, tol 0.02 mm "
                       "(upper bound for r_max, lower bound for r_min); replaces tessellation-vertex sampling")

    # 1. keep-out bands (z measured from H)
    ko = []
    for band in wi["keepout"]:
        a, b = 1.0 + band["z_from_H_min"], 1.0 + band["z_from_H_max"]
        rmax = brep_r(comp, a, b) or 0.0
        # brep_r is an upper bound within its 0.02 mm bisection tolerance; the exact test is the volume outside (below)
        ko.append(dict(z_from_H=[band["z_from_H_min"], band["z_from_H_max"]], r_max_allowed=band["r_max"],
                       r_max_new=round(rmax, 2), ok=rmax <= band["r_max"] + 0.02))
    tol_fix = []
    for zl, zh, rmx in ((-1.0, 1.0, 11.6), (1.0, 5.0, 14.6)):
        rmax = brep_r(comp, 1 + zl, 1 + zh) or 0.0
        tol_fix.append(dict(z_from_H=[zl, zh], r_max_fix5=rmx, r_max_new=round(rmax, 2), ok=rmax <= rmx + 0.05))
    for row in ko + tol_fix:
        zl, zh = row["z_from_H"]
        rr = row.get("r_max_allowed", row.get("r_max_fix5"))
        ring = cq.Solid.makeCylinder(200, zh - zl - 0.02, cq.Vector(0, 0, 1 + zl + 0.01)).cut(
            cq.Solid.makeCylinder(rr, zh - zl - 0.02, cq.Vector(0, 0, 1 + zl + 0.01)))
        v = comp.intersect(ring).Volume()
        row["brep_volume_outside_mm3"] = round(v, 4)
        row["ok"] = bool(row["ok"] and v < 1e-3)
    res["keepout_params"] = ko
    res["keepout_tolerance_fix5"] = tol_fix

    # 2. roll clearance by z band (stationary material treated as a full ring), so101.md bands
    edges = [(-4.0, -3.0), (-3.0, -2.0), (-2.0, -1.0), (-1.0, 0.0), (0.0, 1.0), (1.0, 2.0), (2.0, 5.3), (5.3, 12.0)]
    roll = []
    for a, b in edges:
        g_, s_ = brep_r(comp, a, b, "max"), brep_r(stat_comp, a, b, "min")
        roll.append(dict(z_I=[a, b], gripper_r_max=None if g_ is None else round(g_, 2),
                         stationary_r_min=None if s_ is None else round(s_, 2),
                         radial_gap=None if (g_ is None or s_ is None) else round(s_ - g_, 2)))
    res["roll_ring_clearance"] = roll
    res["roll_min_radial_gap_mm"] = min((r["radial_gap"] for r in roll if r["radial_gap"] is not None), default=None)

    # stock envelope comparison (R9), BRep r_max per band for both grippers
    env_edges = [(0, 6), (6, 12), (12, 25), (25, 40), (40, 60), (60, 80), (80, 125)]
    env = []
    for e in env_edges:
        n_, s_ = brep_r(comp, *e, tol=0.1), brep_r(stock_comp, *e, tol=0.1)
        env.append(dict(z_I=list(e), new_r_max=None if n_ is None else round(n_, 1),
                        stock_r_max=None if s_ is None else round(s_, 1),
                        inside=(n_ is None) or (s_ is not None and n_ <= s_ + 0.5)))
    res["envelope_vs_stock"] = env
    res["envelope_inside_stock_all_bands"] = all(e["inside"] for e in env)

    # 3. jaw sweep: boolean intersections (new parts only; frame G is enough)
    # rev B: the horn turns with knuckle A (the dog set screws are threaded into it), so it is not a static part; it is
    # checked on its own below against everything except those set screws
    static = ["housing", "front_plate", "wrist_mount", "servo", "fasteners"]
    moving_A = ["knuckle_a", "finger_a", "nail_a", "fasteners_a"]
    moving_B = ["knuckle_b", "finger_b", "fsr_backing_b", "fsr_sensor_b", "fsr_puck_b", "fasteners_b"]
    res["jaw_sweep_parts"] = {"static": static, "moving_A": moving_A, "moving_B": moving_B}
    sweep = []
    for th in (-11.0, -7.4, 0.0, 10.0, 20.0):
        W = gc.world(parts, G, th)
        row = {"theta_deg": th, "clash_mm3": {}}
        for mv in moving_A + moving_B:
            for st in static:
                v = W[mv].intersect(W[st]).Volume()
                if v > 1e-3:
                    row["clash_mm3"][f"{mv}|{st}"] = round(v, 3)
        for other in [m for m in moving_A + moving_B if m != "fasteners_a"] + static:
            if other == "servo":
                continue  # the horn sits on the servo spline
            v = W["horn"].intersect(W[other]).Volume()
            if v > 1e-3:
                row["clash_mm3"][f"horn|{other}"] = round(v, 3)
        v = W["knuckle_a"].intersect(W["knuckle_b"]).Volume()
        row["gear_mesh_overlap_mm3"] = round(v, 4)
        pa = W["nail_a"].fuse(W["finger_a"])
        pb = W["fsr_puck_b"].fuse(W["finger_b"]).fuse(W["fsr_backing_b"])
        row["pad_interference_mm3"] = round(pa.intersect(pb).Volume(), 3)
        row["pad_min_dist_mm"] = round(W["nail_a"].distance(W["fsr_puck_b"]), 3) if row["pad_interference_mm3"] < 1e-3 else 0.0
        row["knuckle_a_to_front_plate_mm"] = round(W["knuckle_a"].distance(W["front_plate"]), 3)
        row["knuckle_a_to_housing_mm"] = round(W["knuckle_a"].distance(W["housing"]), 3)
        sweep.append(row)
    res["jaw_sweep"] = sweep
    res["jaw_sweep_static_clash_free"] = all(not r["clash_mm3"] for r in sweep)

    # 4. mass, COM, mass-moment (R10)
    mp = gc.mass_props(P, gc.world(parts, G, 0.0), G)
    items = [(n, r["mass_g"], r["u_past_H"]) for n, r in mp.items()]
    pad_u = G.Y_H - (G.y0 - (P["finger"]["length"] - P["grip"]["pad_centroid_from_tip_mm"]))
    items += [("cloth at the pad [D DB]", P["work_cell"]["cloth"]["mass_g"], pad_u), ("FSR + servo wiring [A DB]", 5.0, 40.0)]
    lever = P["payload_scenarios"]["lever_shoulder_lift_to_H_mm"]
    M = sum(m for _, m, _ in items)
    com = sum(m * u for _, m, u in items) / M
    mom = sum(m * (lever + u) for _, m, u in items)
    budget = 43720.0
    cam = P["camera_pad"]
    res["mass"] = dict(items=[dict(name=n, g=round(m, 2), u_past_H=round(u, 1)) for n, m, u in items],
                       total_g_incl_cloth=round(M, 1), com_u_past_H=round(com, 1),
                       mass_moment_gmm=round(mom), budget_gmm=budget, budget_use=round(mom / budget, 3),
                       stock_loading_gmm=33380.0, design_basis_estimate_gmm=40507.0,
                       revision=P.get("revision", "A"), rev_a_cad_gmm=50131.0,
                       rev_a_note="rev A as built (fitcheck.py on master 899265a, 144.4 g incl. cloth and wiring); DESIGN-BASIS 40,507 is the pre-CAD estimate (115.8 g)",
                       with_wrist_uvc_16g_at_u30_gmm=round(mom + 16.25 * (lever + 30.0)),
                       ok=mom <= budget)
    # 5. wrist flex (R9): rotate about the flex axis (parallel to Y_I through x 0, z_I 1 - 61.55) against the forearm
    fa_names = [k for k in asm if k.startswith("Under_arm") or k.startswith("Motor_holder_SO101_Wrist")] + ["ST3215 Servo v2:4"]
    forearm = [to_I_shape(asm[n], origin, R) for n in fa_names]
    z_ax = 1.0 - wi["wrist_flex_axis_to_H_mm"]
    open_I = cq.Compound.makeCompound([G_to_I(s, G) for s in gc.world(parts, G, P["motion"]["open_angle_max"]).values()])
    # the stock gripper rolls with its own jaw closed, as in the upstream assembly
    flex_rows = []
    for tag, body in (("new_open", open_I), ("stock", stock_comp)):
        for psi in (0.0, 90.0, 180.0, 270.0):
            b_psi = body.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), psi)
            for phi in PHIS:
                b = b_psi.rotate(cq.Vector(0, 0, z_ax), cq.Vector(0, 1, z_ax), float(phi))
                bb = b.BoundingBox()
                v = 0.0
                for f in forearm:
                    fb = f.BoundingBox()
                    if bb.xmin > fb.xmax or fb.xmin > bb.xmax or bb.ymin > fb.ymax or fb.ymin > bb.ymax or bb.zmin > fb.zmax or fb.zmin > bb.zmax:
                        continue
                    v += vol(b.intersect(f))
                flex_rows.append((tag, psi, phi, v))
    flex = {}
    for tag in ("new_open", "stock"):
        for psi in (0.0, 90.0, 180.0, 270.0):
            rows = [(ph, v) for t, ps, ph, v in flex_rows if t == tag and ps == psi]
            ok = [ph for ph, v in rows if v < 1e-3]
            bad = [ph for ph, v in rows if v >= 1e-3]
            flex[f"{tag}@roll{psi:g}"] = dict(clear_phi_deg=[min(ok), max(ok)] if ok else None,
                                             clash_phi_deg=bad, max_clash_mm3=round(max((v for _, v in rows), default=0.0), 2))
    new_bad = {k: set(v["clash_phi_deg"]) for k, v in flex.items() if k.startswith("new")}
    stock_bad = {k.replace("new_open", "stock"): set(v["clash_phi_deg"]) for k, v in flex.items() if k.startswith("new")}
    worse = sorted({ph for k in new_bad for ph in new_bad[k] - set(flex[k.replace("new_open", "stock")]["clash_phi_deg"])})
    res["wrist_flex"] = dict(axis="parallel to Y_I through (x 0, z_I %.2f)" % z_ax, forearm_parts=fa_names,
                             phi_deg=PHIS, roll_angles_deg=[0, 90, 180, 270],
                             new_gripper_pose="jaw open +20 deg", per_case=flex,
                             phi_where_new_clashes_and_stock_does_not=worse,
                             ok_vs_stock=not worse,
                             limits="bounding-box prefilter + boolean volume at the listed angles only; forearm = Under_arm, "
                                    "wrist motor holder and servo-4 body (servo-4 horn and Wrist_Roll_Pitch move with flex)")
    del stock_bad
    runtime_s = round(time.time() - t0, 1)  # printed only: the committed file holds no durations (rev B)
    (HERE / "out" / "fitcheck.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8", newline="\n")

    # render: side view (looking along +Y_I) of the new gripper + stationary wrist, CadQuery SVG
    dd = HERE / "drawings"
    dd.mkdir(exist_ok=True)
    comp_new = cq.Compound.makeCompound(list(rolling.values()))
    for lab, d, fn in (("fitcheck (new gripper in frame I, theta 0)", (0, -1, 0), "fitcheck.svg"),
                       ("fitcheck iso", (1, -1, 0.6), "fitcheck_iso.svg")):
        svg = cq.occ_impl.exporters.svg.getSVG(comp_new, {"width": 700, "height": 600, "projectionDir": d,
                                                          "showHidden": False, "strokeWidth": 0.3})
        (dd / fn).write_text(svg, encoding="utf-8", newline="\n")
    print(json.dumps({k: res[k] for k in ("keepout_params", "keepout_tolerance_fix5", "roll_ring_clearance",
                                          "roll_min_radial_gap_mm", "envelope_vs_stock", "jaw_sweep_static_clash_free")}, indent=1))
    print("runtime_s", runtime_s)
    print(json.dumps(res["wrist_flex"], indent=1))
    print(json.dumps([{"th": r["theta_deg"], "clash": r["clash_mm3"]} for r in res["jaw_sweep"]]))
    print(json.dumps(res["mass"]["total_g_incl_cloth"]), res["mass"]["mass_moment_gmm"], res["mass"]["budget_use"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
