"""3D shots for the gripper video. Usage (Blender as a Python module):

    python shots3d.py S2 [--w 1280 --h 720 --samples 6] [--every N] [--out DIR]

Writes DIR/S2/0000.png ... and DIR/S2/track.json (screen positions of named points per frame,
used by the compositor to pin labels and overlays to the geometry).
"""
import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import scene3d as S  # noqa: E402

FPS = 30
CLOTH_X = -0.725      # cloth mid-plane between nail face (x -1.22) and puck face (x -0.23), parts.json bbox_G
THETA_CONTACT = -0.3  # contact with one 0.3 mm ply, DESIGN-BASIS.md:96 ("contact at -0.3 deg with a 0.3 mm ply")


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return 4 * x * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a, b, s):
    return a + (b - a) * s


def seg(t, t0, t1):
    return ease((t - t0) / (t1 - t0))


def orbit(target, az_deg, el_deg, dist):
    """Camera position around a world target; az 0 = in front (-Y), + = toward +X."""
    az, el = math.radians(az_deg), math.radians(el_deg)
    return Vector(target) + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist


# ---------------------------------------------------------------- cloth (tilted, pinched one ply)
def build_cloth(rig, mats, tilt, width=120.0, flat=170.0, R=9.0):
    """One 0.3 mm ply pinched between the pads at theta = -0.3 deg, running down the pad plane, bending onto
    the bed. Built in frame G so it rides the tilted rig. Returns (object, bed z world, edge polyline in G)."""
    t = math.radians(tilt)
    ca, sa = math.cos(t), math.sin(t)

    def to_g(xp, yp):  # world-aligned jaw-plane 2D (mm) -> G 2D
        return (ca * xp + sa * yp, -sa * xp + ca * yp)

    def to_p(xg, yg):
        return (ca * xg - sa * yg, sa * xg + ca * yg)

    # lowest point of the gripper in the jaw plane (y'), from the posed meshes
    low = 1e9
    for n, ob in rig.obj.items():
        side = S.SIDE.get(n)
        for v in list(ob.data.vertices)[::3]:
            co = v.co.copy()
            if side:
                px = -S.A_HALF if side == "A" else S.A_HALF
                co = Matrix.Rotation(math.radians(-THETA_CONTACT if side == "A" else THETA_CONTACT), 4, "Z") @ co
                co.x += px
            low = min(low, to_p(co.x, co.y)[1])
    bed = low - 0.6
    # profile in the jaw plane: pinch segment along -Y_G from the edge, arc, flat on the bed
    prof = []
    y_edge = -58.0
    ln = 0.0
    while True:  # extend the pad-plane segment until the arc lands on the bed
        x0, y0 = to_p(CLOTH_X, y_edge - 12.0 - ln)
        a0 = math.radians(tilt - 90.0)
        cx, cy = x0 - R * math.sin(a0), y0 + R * math.cos(a0)
        if cy - R <= bed + 0.15 or ln > 200:
            break
        ln += 0.5
    n1 = 14
    for i in range(n1 + 1):
        prof.append(to_p(CLOTH_X, y_edge - (12.0 + ln) * i / n1))
    for i in range(1, 13):
        a = a0 + (0 - a0) * i / 12
        prof.append((cx + R * math.sin(a), cy - R * math.cos(a)))
    lastx, lasty = prof[-1]
    for i in range(1, 30):
        x = lastx + flat * i / 29
        prof.append((x, lasty + 0.25 * math.sin(x * 0.11) * clamp(i / 6)))
    bed = lasty - 0.15
    # arc length for UVs
    s_acc = [0.0]
    for i in range(1, len(prof)):
        s_acc.append(s_acc[-1] + math.dist(prof[i], prof[i - 1]))
    nw = 24
    verts, uvs, faces = [], [], []
    for j, (xp, yp) in enumerate(prof):
        xg, yg = to_g(xp, yp)
        for k in range(nw + 1):
            z = 5.0 - width / 2 + width * k / nw
            # soft waves away from the pads: the free cloth outside the pad depth (z -5..15) drapes slightly
            outside = max(0.0, abs(z - 5.0) - 12.0)
            wob = 0.0 if j <= n1 else 0.6 * math.sin(z * 0.09 + j * 0.4) * clamp(outside / 30)
            verts.append((xg + wob * sa, yg - wob * ca * 0.2, z))
            uvs.append((s_acc[j] / 120.0, (z + 60) / 120.0))
    for j in range(len(prof) - 1):
        for k in range(nw):
            a = j * (nw + 1) + k
            faces.append((a, a + 1, a + nw + 2, a + nw + 1))
    me = bpy.data.meshes.new("cloth")
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name="UV")
    for poly in me.polygons:
        for li in poly.loop_indices:
            uvl.data[li].uv = uvs[me.loops[li].vertex_index]
    me.materials.append(mats["cotton"])
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("cloth", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = rig.root
    ob.matrix_parent_inverse = Matrix.Identity(4)
    sol = ob.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = 0.3
    sol.offset = 0.0
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    edge = [to_g(*p) + (5.0 + width / 2,) for p in prof]
    return ob, bed, edge


# ---------------------------------------------------------------- shot definitions
# Each shot: frames, setup(ctx) once, state(ctx, t) -> dict with theta, explode, eye, target, lens, fstop, focus
def shot_S1():
    def setup(c):
        c["rig"].hide(["front_plate", "fasteners"])

    def state(c, t):
        th = lerp(20.0, 0.0, seg(t, 0.2, 3.4))
        tgt = c["rig"].g2w((0, 2, 9))
        eye = orbit(tgt, lerp(-38, -12, seg(t, 0, 4)), lerp(26, 14, seg(t, 0, 4)), lerp(0.13, 0.105, seg(t, 0, 4)))
        focus = c["rig"].g2w((lerp(-10, 0, seg(t, 0.2, 2.6)), lerp(6, 0, seg(t, 0.2, 2.6)), 9))
        return dict(theta=th, eye=eye, target=tgt, lens=100, fstop=4.0, focus=focus)
    return 120, setup, state


def shot_S2():
    def state(c, t):
        th = lerp(0.0, 20.0, seg(t, 0.8, 3.6))
        tgt = c["rig"].g2w((0, -20, 0))
        eye = orbit(tgt, lerp(-42, -18, seg(t, 0, 5)), lerp(20, 14, seg(t, 0, 5)), lerp(0.42, 0.38, seg(t, 0, 5)))
        # Engineering overview: keep the complete mechanism readable throughout the orbit.
        return dict(theta=th, eye=eye, target=tgt, lens=60, fstop=5.6, focus=tgt, use_dof=False)
    return 150, None, state


DELAY = {"servo": 0.0, "housing": 0.35, "horn": 0.7, "knuckle_a": 1.2, "knuckle_b": 1.2, "fasteners_a": 1.7,
         "fasteners_b": 1.7, "finger_a": 2.2, "finger_b": 2.2, "nail_a": 2.6, "fsr_backing_b": 2.6,
         "fsr_sensor_b": 2.75, "fsr_puck_b": 2.9, "wrist_mount": 3.2, "fasteners": 3.7, "front_plate": 4.1}


def shot_S3():
    def state(c, t):
        ex = {n: 1.0 - seg(t, d + 0.3, d + 1.7) for n, d in DELAY.items()}
        tgt = c["rig"].g2w((0, -18, 0))
        eye = orbit(tgt, lerp(-58, -26, seg(t, 0, 7)), lerp(24, 16, seg(t, 0, 7)), lerp(0.50, 0.38, seg(t, 0, 7)))
        return dict(theta=10.0, explode=ex, eye=eye, target=tgt, lens=55, fstop=8, focus=tgt)
    return 210, None, state


def shot_S4():
    def setup(c):
        c["rig"].hide(["front_plate"])

    def state(c, t):
        th = lerp(20.0, 0.0, seg(t, 0.4, 2.4)) if t < 3.0 else lerp(0.0, 20.0, seg(t, 3.4, 5.4))
        tgt = c["rig"].g2w((0, -3, 9))
        eye = orbit(tgt, lerp(-10, -4, seg(t, 0, 6)), lerp(9, 5, seg(t, 0, 6)), lerp(0.19, 0.145, seg(t, 0, 6)))
        return dict(theta=th, eye=eye, target=tgt, lens=85, fstop=7.1, focus=tgt)
    return 180, setup, state


def shot_S5():
    def state(c, t):
        th = lerp(20.0, 0.0, seg(t, 0.6, 4.2))
        tgt = c["rig"].g2w((0, -20, 5))
        eye = orbit(tgt, 0.0, 1.5, lerp(0.42, 0.40, seg(t, 0, 6)))
        return dict(theta=th, eye=eye, target=tgt, lens=70, fstop=11, focus=tgt)
    return 180, None, state


TILT = 30.0


def _tilted_setup(c):
    rig = c["rig"]
    rig.set_tilt(TILT, (0, 0, 0.0))
    cl, bed, edge = build_cloth(rig, c["mats"], TILT)
    # place the rig so the bed sits on the studio floor
    floor = c["floor_z"]
    off = floor - bed * 0.001
    rig.set_tilt(TILT, (0, 0, off))
    c["edge"] = edge


def shot_S6():
    def setup(c):
        _tilted_setup(c)

    def state(c, t):
        th = lerp(6.0, THETA_CONTACT, seg(t, 0.8, 3.8))
        tgt = c["rig"].g2w((CLOTH_X, -64, 5))
        eye = orbit(tgt, lerp(-34, -18, seg(t, 0, 6)), lerp(16, 10, seg(t, 0, 6)), lerp(0.17, 0.15, seg(t, 0, 6)))
        # Engineering comparison: both contact faces and the cloth edge must stay readable.
        return dict(theta=th, eye=eye, target=tgt, lens=100, fstop=6.3, focus=tgt, use_dof=False)
    return 180, setup, state


def shot_S9():
    def setup(c):
        _tilted_setup(c)

    def state(c, t):
        tgt = c["rig"].g2w((CLOTH_X, -60, 20))
        # fixed camera, oblique 53 deg down (camera.md:14); a slow push stands in for the reveal
        eye = orbit(tgt, 62.0, 53.0, lerp(0.36, 0.32, seg(t, 0, 5)))
        return dict(theta=THETA_CONTACT, eye=eye, target=tgt, lens=28, fstop=11, focus=tgt)
    return 150, setup, state


def shot_S11():
    def setup(c):
        _tilted_setup(c)

    def state(c, t):
        tgt = c["rig"].g2w((0, -40, 5))
        eye = orbit(tgt, lerp(-30, -22, seg(t, 0, 5)), lerp(18, 15, seg(t, 0, 5)), lerp(0.40, 0.36, seg(t, 0, 5)))
        return dict(theta=THETA_CONTACT, eye=eye, target=tgt, lens=55, fstop=6.3, focus=c["rig"].g2w((CLOTH_X, -60, 5)))
    return 84, setup, state  # the end card covers S11 from 2.45 s; compose.py holds the last frame under it


SHOTS = {"S1": shot_S1, "S2": shot_S2, "S3": shot_S3, "S4": shot_S4, "S5": shot_S5, "S6": shot_S6,
         "S9": shot_S9, "S11": shot_S11}

# points tracked to screen for the compositor: name -> (side, G point, part for explode)
TRACK = {
    "pivot_a": (None, (-S.A_HALF, 0, 12.5), None), "pivot_b": (None, (S.A_HALF, 0, 12.5), None),
    "tip_a": ("A", (-8, -70, 5), "finger_a"), "tip_b": ("B", (8, -70, 5), "finger_b"),
    "mesh": (None, (0, 0, 9), None), "pinch": ("A", (CLOTH_X, -64, 5), None),
    "housing": (None, (-24, 10, 12.5), "housing"), "knuckle_a": ("A", (-14, -14, 9), "knuckle_a"),
    "finger_b": ("B", (10, -45, 15), "finger_b"), "servo": (None, (-28, 0, -30), "servo"),
    "nail": ("A", (-1.7, -66, 15), "nail_a"), "fsr": ("B", (1.5, -60, 15), "fsr_backing_b"),
}


def parse(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("shot")
    ap.add_argument("--w", type=int, default=1280)
    ap.add_argument("--h", type=int, default=720)
    ap.add_argument("--samples", type=int, default=6)
    ap.add_argument("--denoise", default="fast", choices=["fast", "high"])
    ap.add_argument("--mblur", action="store_true", help="Cycles motion blur, 0.5 frame shutter")
    ap.add_argument("--threshold", type=float, default=0.03, help="adaptive sampling noise threshold")
    ap.add_argument("--device", help="auto (default; env GRIPPER_DEVICE), gpu, optix, cuda or cpu")
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--frame", type=int, action="append", help="render only these frames (repeatable)")
    ap.add_argument("--reverse", action="store_true", help="render last frame first (split a shot across two workers)")
    ap.add_argument("--force", action="store_true", help="re-render frames that already exist")
    ap.add_argument("--out", default=os.path.join(S.ROOT, "video", "gripper", "build", "frames3d"))
    ap.add_argument("--name", help="output folder name (default: the shot)")
    return ap.parse_args([x for x in argv if x != "--"])


def prepare(a):
    """Build the shot's scene, keyframe every frame, write track.json. Returns (scene, frames, out dir, device)."""
    nfr, setup, state = SHOTS[a.shot]()
    S.reset()
    mats = S.make_materials()
    rig = S.Rig(mats)
    floor_z = {"S3": -0.125}.get(a.shot, -0.085)
    S.studio(mats, floor_z=floor_z)
    cam = S.camera()
    c = {"rig": rig, "mats": mats, "floor_z": floor_z}
    if setup:
        setup(c)
    dev = S.render_settings(a.w, a.h, a.samples, device=a.device, denoise=a.denoise, motion_blur=a.mblur,
                            threshold=a.threshold)
    sc = bpy.context.scene
    frames = a.frame or list(range(0, nfr, a.every))
    sc.frame_start, sc.frame_end = 0, nfr - 1
    track = {}
    focus_empty = bpy.data.objects.new("focus", None)
    sc.collection.objects.link(focus_empty)
    cam.data.dof.focus_object = focus_empty
    for f in range(nfr):
        st = state(c, f / FPS)
        th = st["theta"]
        ex = st.get("explode", 0.0)
        rig.set_theta(th)
        rig.set_explode(ex)
        rig.key(f)
        S.look_at(cam, st["eye"], st["target"])
        cam.data.lens = st["lens"]
        cam.data.dof.use_dof = st.get("use_dof", True)
        cam.data.dof.aperture_fstop = st["fstop"]
        focus_empty.location = st["focus"]
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.keyframe_insert("lens", frame=f)
        cam.data.dof.keyframe_insert("use_dof", frame=f)
        focus_empty.keyframe_insert("location", frame=f)
        bpy.context.view_layer.update()
        pts = {}
        for name, (side, p, part) in TRACK.items():
            e = ex.get(part, 0.0) if isinstance(ex, dict) else ex
            w = rig.g2w(p, side=side, theta=th, explode=e, part=part)
            v = world_to_camera_view(sc, cam, w)
            pts[name] = [round(v.x, 4), round(1 - v.y, 4)]
        if "edge" in c:
            pts["edge"] = [[round(q, 4) for q in (lambda v: (v.x, 1 - v.y))(world_to_camera_view(sc, cam, rig.root.matrix_world @ Vector(e)))]
                           for e in c["edge"]]
        track[f] = dict(theta=round(th, 3), pts=pts)
    for fc in [o.animation_data.action for o in list(bpy.data.objects) + [cam.data] if o.animation_data and o.animation_data.action]:
        try:
            for cu in fc.fcurves:
                for kp in cu.keyframe_points:
                    kp.interpolation = "LINEAR"
        except AttributeError:
            pass
    od = os.path.join(a.out, a.name or a.shot)
    os.makedirs(od, exist_ok=True)
    with open(os.path.join(od, "track.json"), "w") as fh:
        json.dump(track, fh)
    return sc, frames, od, dev


def main():
    a = parse(sys.argv[1:])
    sc, frames, od, dev = prepare(a)
    for f in (frames[::-1] if a.reverse else frames):
        final = os.path.join(od, f"{f:04d}.png")
        if os.path.exists(final) and not a.force:  # resumable; two workers can split a shot
            continue
        sc.render.filepath = os.path.join(od, f"{f:04d}.part.png")  # renamed when complete, so a cut-off
        sc.frame_set(f)                                             # render never counts as written
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        os.replace(sc.render.filepath, final)
        print(f"FRAME {a.shot} {f} {time.perf_counter() - t0:.2f}s {a.w}x{a.h} {a.samples}spp "
              f"{a.denoise}{' mblur' if a.mblur else ''} pid {os.getpid()} on {dev}", flush=True)


if __name__ == "__main__":
    main()
