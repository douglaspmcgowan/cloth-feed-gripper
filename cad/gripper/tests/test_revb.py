"""Revision B: tests named by their cad/gripper/CHANGELOG.md row ids (test_B<n>_...), measured on the built solids.

    python3 -m pytest cad/gripper/tests -q

Builds the model once (gripper_concept.build, about 20 s). Frame G, mm (cad/gripper/README.md).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
CAD = HERE.parent
ROOT = CAD.parent.parent
sys.path.insert(0, str(CAD))

cq = pytest.importorskip("cadquery")
import gripper_concept as gc  # noqa: E402

PRINTED = ["housing", "front_plate", "wrist_mount", "knuckle_a", "knuckle_b", "finger_a", "finger_b", "nail_a",
           "fsr_backing_b", "fsr_puck_b"]
MOVING = ["knuckle_a", "finger_a", "nail_a", "fasteners_a", "knuckle_b", "finger_b", "fsr_backing_b", "fsr_sensor_b",
          "fsr_puck_b", "fasteners_b"]
STATIC = ["housing", "front_plate", "wrist_mount", "servo", "fasteners"]  # as fitcheck.py; the horn turns with knuckle A


@pytest.fixture(scope="session")
def model():
    raw = json.loads((CAD / "params.json").read_text(encoding="utf-8"))
    P = gc.resolve(raw)
    G, parts, info = gc.build(raw)
    st, sa, sb = gc.fasteners(P, G)
    return dict(raw=raw, P=P, G=G, parts=parts, info=info, W0=gc.world(parts, G, 0.0),
                items={"static": st, "A": sa, "B": sb})


# ------------------------------------------------------------------ measuring helpers
def cylinders(shape):
    """(radius, centre point of the axis segment, axis direction, axial length) for every cylindrical face."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    out = []
    for f in shape.Faces():
        if f.geomType() != "CYLINDER":
            continue
        c = BRepAdaptor_Surface(f.wrapped).Cylinder()
        ax = c.Axis()
        d = ax.Direction()
        loc = ax.Location()
        bb = f.BoundingBox()
        dv = (d.X(), d.Y(), d.Z())
        ext = {0: (bb.xmin, bb.xmax), 1: (bb.ymin, bb.ymax), 2: (bb.zmin, bb.zmax)}[max(range(3), key=lambda i: abs(dv[i]))]
        out.append((c.Radius(), (loc.X(), loc.Y(), loc.Z()), dv, ext))
    return out


def has_bore(shape, d, at, axis, tol=0.005, pos_tol=0.02):
    """True when the solid has a cylindrical face of diameter d whose axis passes through the 2D point at (in the plane normal to axis)."""
    i, j = [k for k in range(3) if k != axis]
    for r, p, dv, _ in cylinders(shape):
        if abs(2 * r - d) > tol or abs(abs(dv[axis]) - 1) > 1e-6:
            continue
        if abs(p[i] - at[0]) < pos_tol and abs(p[j] - at[1]) < pos_tol:
            return True
    return False


def bore_extent(shape, d, at, axis, tol=0.005, pos_tol=0.02):
    i, j = [k for k in range(3) if k != axis]
    ex = [e for r, p, dv, e in cylinders(shape) if abs(2 * r - d) <= tol and abs(abs(dv[axis]) - 1) < 1e-6
          and abs(p[i] - at[0]) < pos_tol and abs(p[j] - at[1]) < pos_tol]
    return (min(e[0] for e in ex), max(e[1] for e in ex)) if ex else None


def gap_along(shape, axis, lo, hi, fixed):
    """Empty interval of the solid along a probe line (thin box) between lo and hi; returns (start, end) of the widest gap."""
    t = 0.05
    c = [0.0, 0.0, 0.0]
    k = 0
    for ax in range(3):
        if ax != axis:
            c[ax] = fixed[k]
            k += 1
    b = [None] * 3
    for ax in range(3):
        b[ax] = (lo, hi) if ax == axis else (c[ax] - t, c[ax] + t)
    probe = gc.box(b[0][0], b[0][1], b[1][0], b[1][1], b[2][0], b[2][1])
    pieces = sorted(((s.BoundingBox().xmin, s.BoundingBox().xmax) if axis == 0 else (s.BoundingBox().ymin, s.BoundingBox().ymax)
                     if axis == 1 else (s.BoundingBox().zmin, s.BoundingBox().zmax)) for s in shape.intersect(probe).Solids())
    best = (0.0, None)
    for (a0, a1), (b0, b1) in zip(pieces, pieces[1:]):
        if b0 - a1 > best[0]:
            best = (b0 - a1, (a1, b0))
    return best[1]


def intervals_z(shapes, x, y, z0, z1, t=0.02):
    """Merged material intervals of the shapes along the line (x, y, z) for z in [z0, z1]."""
    probe = gc.box(x - t, x + t, y - t, y + t, z0, z1)
    iv = []
    for sh in shapes:
        for so in sh.intersect(probe).Solids():
            bb = so.BoundingBox()
            iv.append((bb.zmin, bb.zmax))
    iv.sort()
    out = []
    for a, b in iv:
        if out and a <= out[-1][1] + 1e-6:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def gaps_total(iv):
    return sum(b0 - a1 for (_, a1), (b0, _) in zip(iv, iv[1:]))


def pad_face_x(shape, y, z, toward_plus, t=0.02):
    """x of the solid's face toward +X (toward_plus) or -X, on the line (., y, z)."""
    sec = shape.intersect(gc.box(-200, 200, y - t, y + t, z - t, z + t))
    bb = sec.BoundingBox()
    return bb.xmax if toward_plus else bb.xmin


def item(model, name_start, group="static"):
    return [s for n, s, _ in model["items"][group] if n.startswith(name_start)]


# ------------------------------------------------------------------ general
def test_revision_and_parts(model):
    assert model["raw"]["revision"] == "B"
    assert set(model["parts"]) == set(PRINTED) | {"fsr_sensor_b", "servo", "horn", "fasteners", "fasteners_a", "fasteners_b"}
    assert len(model["parts"]) == 16
    assert not model["info"]["warnings"]


@pytest.mark.parametrize("name", PRINTED)
def test_printed_part_single_valid_solid(model, name):
    s = model["parts"][name]
    assert s.isValid()
    assert len(s.Solids()) == 1
    assert s.Volume() > 0


def test_fastener_item_count(model):
    n = {g: len(v) for g, v in model["items"].items()}
    # static: 2 pins, 4 shims, 4 horn screws, 4 deck screws, 4 inserts, 2 locating pins, 4 x (ear screw, sleeve, washer, nut), 3 plate screws
    assert n == {"static": 2 + 4 + 4 + 4 + 4 + 2 + 16 + 3, "A": 2 + 2, "B": 2}


# ------------------------------------------------------------------ B1-B3 servo boss bore, dog slots 3.4, pocket width + 0.40 (B23 horn on the boss)
def test_B1_B23_boss_bore_in_web(model):
    G, h = model["G"], model["P"]["housing"]
    hs = model["parts"]["housing"]
    assert has_bore(hs, h["boss_bore_cad"], (-G.a / 2, 0.0), axis=2)
    z0, z1 = bore_extent(hs, h["boss_bore_cad"], (-G.a / 2, 0.0), axis=2)
    assert z0 == pytest.approx(G.zw0, abs=0.01) and z1 == pytest.approx(G.zw1, abs=0.01)
    assert G.zw0 > G.z_ct and G.zw1 < G.z_horn0  # web between the case top and the horn
    assert G.z_horn0 - G.z_ct == pytest.approx(model["P"]["servo"]["boss_h"], abs=1e-6)  # horn on the boss top


def test_B2_dog_slot_width(model):
    G = model["G"]
    gap = gap_along(model["parts"]["knuckle_a"], 0, -4.0, 4.0, (7.0, G.z_k0 + 1.0))
    assert gap is not None and gap[1] - gap[0] == pytest.approx(3.4, abs=0.01)


def test_B3_cradle_pocket_width(model):
    G, s = model["G"], model["P"]["servo"]
    gap = gap_along(model["parts"]["housing"], 1, -15.0, 15.0, (-4.0, G.zs0 + 1.0))
    w = gap[1] - gap[0]
    assert w == pytest.approx(20.5, abs=0.01)
    assert w == pytest.approx(s["body_x"] + 0.40, abs=0.01)


# ------------------------------------------------------------------ B4 bush bore 6, h8 pins 3 x 16, bush 3 x 6 x 10; B20 blind front holes
@pytest.mark.parametrize("name,side", [("knuckle_a", "A"), ("knuckle_b", "B")])
def test_B4_knuckle_bush_bore(model, name, side):
    k = model["P"]["knuckle"]
    kn = model["parts"][name]
    bush = item(model, "bronze bush", side)[0]
    od = bush.BoundingBox().xlen
    assert od == pytest.approx(6.0, abs=1e-3)                          # 3 x 6 x 10 bush, measured
    # the printed bore is 0.2 under the bush OD (reamed to it), on the pivot axis, through the hub
    assert has_bore(kn, od - 0.2, (0.0, 0.0), axis=2)
    z0, z1 = bore_extent(kn, od - 0.2, (0.0, 0.0), axis=2)
    hub = kn.intersect(gc.cyl_z(0, 0, 9.0, -50, 50)).BoundingBox()
    assert (z0, z1) == (pytest.approx(hub.zmin, abs=0.01), pytest.approx(hub.zmax, abs=0.01))
    bb = bush.BoundingBox()
    # bush 10.0 inside the 10.5 hub: below both faces, so the shims bear on the hub (B38)
    assert bb.zmin - hub.zmin == pytest.approx(0.25, abs=1e-3) and hub.zmax - bb.zmax == pytest.approx(0.25, abs=1e-3)


def test_B4_B20_pins_and_bushes(model):
    G, W = model["G"], model["W0"]
    hs, fp = model["parts"]["housing"], model["parts"]["front_plate"]
    pins = item(model, "pin h8 3x16")
    assert len(pins) == 2
    for p in pins:
        bb = p.BoundingBox()
        x = bb.center.x
        assert bb.xlen == pytest.approx(3.0, abs=1e-3) and bb.zlen == pytest.approx(16.0, abs=1e-3)
        h0, h1 = bore_extent(hs, 2.9, (x, 0.0), axis=2)               # pin hole through the mid plate
        f0, f1 = bore_extent(fp, 2.9, (x, 0.0), axis=2)               # blind hole in the front plate
        assert bb.zmin - h0 == pytest.approx(0.5, abs=0.01)            # 0.5 under the mid-plate back face
        assert bb.zmax == pytest.approx(f1, abs=0.01)                  # bottoms in the blind hole
        assert f1 < fp.BoundingBox().zmax - 0.99                       # blind: 1.0 front skin, pin captured (B20)
        assert f1 - f0 == pytest.approx(1.5, abs=0.01)
    for side, kn in (("A", "knuckle_a"), ("B", "knuckle_b")):
        bush = gc.pose(item(model, "bronze bush 3x6x10", side)[0], side, G, 0.0).BoundingBox()
        assert bush.zlen == pytest.approx(10.0, abs=1e-3)
        pin = min(pins, key=lambda p: abs(p.BoundingBox().center.x - bush.center.x)).BoundingBox()
        assert pin.zmin < bush.zmin and pin.zmax > bush.zmax          # the pin runs the whole bush


# ------------------------------------------------------------------ B5 toe-in 0.44 deg, B6 r_c, 1 mm closed gap
def pad_face_angle(shape, x_near):
    best = None
    for f in shape.Faces():
        if f.geomType() != "PLANE":
            continue
        n = f.normalAt()
        if abs(n.z) > 1e-6 or abs(n.x) < 0.99:
            continue
        c = f.Center()
        if abs(c.x - x_near) < 1.5 and (best is None or f.Area() > best[0]):
            best = (f.Area(), math.degrees(math.atan2(n.y, n.x)) if n.x > 0 else math.degrees(math.atan2(-n.y, -n.x)))
    return best[1]


@pytest.mark.parametrize("name,side,y_span", [
    ("finger_a", "A", (-30.0, -60.0)), ("nail_a", "A", (-59.5, -68.5)),
    ("finger_b", "B", (-30.0, -60.0)), ("fsr_backing_b", "B", (-52.0, -68.5)),
    ("fsr_sensor_b", "B", (-55.0, -62.0)), ("fsr_puck_b", "B", (-64.0, -67.0))])
def test_B5_toe_in_signed(model, name, side, y_span):
    """Signed toe-in on each pad-face part, in its own pivot frame: the face toward the jaw centre (+X for A, -X for B)
    is nearer the centre at the root end than at the tip end, by tan(0.44 deg) per mm. Toe-out fails."""
    G, parts = model["G"], model["parts"]
    shp = parts[name]
    bb = shp.BoundingBox()
    y_hi, y_lo = min(y_span[0], bb.ymax - 0.3), max(y_span[1], bb.ymin + 0.3)
    toward_plus = side == "A"
    z = G.zc if name != "fsr_puck_b" else bb.center.z
    x_hi, x_lo = pad_face_x(shp, y_hi, z, toward_plus), pad_face_x(shp, y_lo, z, toward_plus)
    inward = (x_hi - x_lo) if toward_plus else (x_lo - x_hi)          # root end nearer the centre: > 0
    slope = math.degrees(math.atan2(inward, y_hi - y_lo))
    assert slope == pytest.approx(0.44, abs=0.01), (name, slope)          # CHANGELOG B5: toe-in, not toe-out


def test_B5_toe_in_finger_and_nail(model):
    G, parts = model["G"], model["parts"]
    assert abs(pad_face_angle(parts["finger_a"], G.xf)) == pytest.approx(0.44, abs=0.005)
    assert abs(pad_face_angle(parts["nail_a"], G.xf + 1.0)) == pytest.approx(0.44, abs=0.005)
    # A-local: the root end of the pad face is nearer the jaw centre (+X) than the tip end
    bb = parts["finger_a"].BoundingBox()
    assert bb.xmax == pytest.approx(G.xf + (G.y_root - G.yp) * math.tan(math.radians(0.44)), abs=0.01)


def test_B6_closed_gap_and_r_c(model):
    W, G = model["W0"], model["G"]
    # rigid faces 1.0 apart at theta 0 at the pad-contact height (R18 / R21 definition kept; the toe-in hinges there)
    gap = gap_along(W["nail_a"].fuse(W["fsr_puck_b"]), 0, -6.0, 6.0, (G.yp, G.zc))
    assert gap[1] - gap[0] == pytest.approx(1.0, abs=0.005)
    # R17 and test plan row 1: r_c <= 64.95 measured from the built nail face (normal line through the contact point)
    nail = model["parts"]["nail_a"]
    face = max((f for f in nail.Faces() if f.geomType() == "PLANE" and abs(f.normalAt().x) > 0.99 and f.Center().x > G.xf + 0.5),
               key=lambda f: f.Area())
    n = face.normalAt()
    p = face.Center()
    yp = G.yp
    px = p.x + (yp - p.y) * (-n.y / n.x) if abs(n.x) > 0 else p.x
    r_c = abs(px * n.y - yp * n.x)  # distance from the pivot (A-local origin) to the normal line through (px, yp)
    assert r_c <= 64.95
    assert r_c == pytest.approx(G.r_c_face["A"], abs=0.01)


# ------------------------------------------------------------------ B7 deck locating pins
def test_B7_deck_locating_pins(model):
    h, w = model["P"]["housing"], model["P"]["wrist_mount"]
    for x, z in h["deck_pegs"]:
        assert has_bore(model["parts"]["housing"], h["deck_peg_hole_cad"], (x, z), axis=1)
        assert has_bore(model["parts"]["wrist_mount"], w["peg_hole_cad"], (x, z), axis=1)
    pins = item(model, "locating pin h8 3x6")
    assert len(pins) == 2
    assert {(round(p.Center().x, 1), round(p.Center().z, 1)) for p in pins} == {(round(x, 1), round(z, 1)) for x, z in h["deck_pegs"]}


# ------------------------------------------------------------------ B8 recess 19.56, B9 mount holes 3.7
def test_B8_B9_wrist_recess_and_holes(model):
    wm = model["parts"]["wrist_mount"]
    assert has_bore(wm, 19.56, (0.0, 0.0), axis=1)
    r = 7.0
    for i in range(4):
        t = math.pi / 4 + i * math.pi / 2
        assert has_bore(wm, 3.7, (r * math.cos(t), r * math.sin(t)), axis=1)
    assert not any(abs(2 * c[0] - 3.6) < 0.005 for c in cylinders(wm))


# ------------------------------------------------------------------ B10 horn screw length is a parameter with the measured-depth rule
def test_B10_horn_screw_length_parameter(model):
    G = model["G"]
    w, wi = model["P"]["wrist_mount"], model["P"]["wrist_interface"]
    L = w["horn_screw_len"]
    screws = item(model, f"M3x{L:g} horn screw")
    assert len(screws) == 4
    wm = model["parts"]["wrist_mount"]
    depth = wi["horn_hole_depth"]
    for sc in screws:
        bb = sc.BoundingBox()
        x, z = bb.center.x, bb.center.z
        _, cb_top = bore_extent(wm, w["counterbore_d"], (x, z), axis=1)   # counterbore floor = under-head face
        shank = sc.intersect(gc.cyl_y(x, z, 1.6, cb_top, cb_top + 50)).BoundingBox()
        assert shank.ymin == pytest.approx(cb_top, abs=1e-3) and shank.ylen == pytest.approx(L, abs=1e-3)
        past_H = shank.ymax - G.Y_H                                      # thread into the arm's horn
        assert depth - past_H >= 0.2 - 1e-6                              # tip clearance at the rule's minimum depth
        assert past_H >= 1.5                                             # engagement
    assert "measure" in w["horn_screw_rule"] and "3.75" in w["horn_screw_rule"]


# ------------------------------------------------------------------ B11 compression limiters, washer, frame +1.5 per end
def test_B11_limiter_seats_and_frame(model):
    G, P = model["G"], model["P"]
    hs = model["parts"]["housing"]
    for x, y in gc.ear_holes(P, G):
        assert has_bore(hs, 5.0, (x, y), axis=2)
        z0, z1 = bore_extent(hs, 5.0, (x, y), axis=2)
        assert z1 - z0 == pytest.approx(P["housing"]["wall"], abs=0.01)
    sl = item(model, "limiter sleeve")
    assert len(sl) == 4
    for s in sl:
        bb = s.BoundingBox()
        assert bb.xlen == pytest.approx(5.0, abs=1e-3) and bb.zlen == pytest.approx(2.55, abs=1e-3)
        assert has_bore(s, 3.2, (bb.center.x, bb.center.y), axis=2)
    assert len(item(model, "washer M3")) == 4 and len(item(model, "nut M3")) == 4
    # K3: sleeve, washer and nut stacked touching on each ear screw, the sleeve seated on the seat-hole floor (= ear)
    for x, y in gc.ear_holes(P, G):
        near = lambda name: min(item(model, name), key=lambda s: math.hypot(s.Center().x - x, s.Center().y - y)).BoundingBox()
        sv, wa, nu, sc = near("limiter sleeve"), near("washer M3"), near("nut M3"), near("M3x10 ear screw")
        seat0, _ = bore_extent(hs, 5.0, (x, y), axis=2)
        assert has_bore(model["W0"]["servo"], P["servo"]["ear_hole_d"], (x, y), axis=2)
        assert sv.zmin == pytest.approx(seat0, abs=1e-3) and sv.zmin == pytest.approx(G.z_ear1, abs=1e-3)
        assert wa.zmin == pytest.approx(sv.zmax, abs=1e-3) and nu.zmin == pytest.approx(wa.zmax, abs=1e-3)
        assert sc.zmax > nu.zmax                                         # thread passes through the nut
        for b in (sv, wa, nu):
            assert (b.center.x, b.center.y) == (pytest.approx(x, abs=1e-3), pytest.approx(y, abs=1e-3))
    # frame slab at the seat level spans the ears + 1 + 1.5 per end
    sl_ = hs.intersect(gc.box(-60, 60, -12, -11, G.zs0 + 0.5, G.zs0 + 1.0))
    bb = sl_.BoundingBox()
    assert bb.xmin == pytest.approx(G.ear_x0 - 2.5, abs=0.01) and bb.xmax == pytest.approx(G.ear_x1 + 2.5, abs=0.01)
    # 2.5 mm of PETG beyond each outer seat hole (thermal C1)
    xs = sorted(x for x, _ in gc.ear_holes(P, G))
    assert (xs[0] - 2.5) - bb.xmin == pytest.approx(2.5, abs=0.01)
    # washers, nuts and sleeves clear the housing
    for s in item(model, "washer M3") + item(model, "nut M3"):
        assert s.intersect(model["W0"]["housing"]).Volume() < 1e-6


# ------------------------------------------------------------------ B12 servo body open to the air behind the seat
def test_B12_servo_open_behind_seat(model):
    G, W = model["G"], model["W0"]
    t = 1.0
    shell = gc.box(G.sx0 - t, G.sx1 + t, G.ys0 - t, G.ys1 + t, G.z_cb, G.z_ear0).cut(
        gc.box(G.sx0, G.sx1, G.ys0, G.ys1, G.z_cb - 1, G.z_ear0 + 1))
    for n in ("housing", "front_plate", "wrist_mount", "fasteners"):
        assert W[n].intersect(shell).Volume() < 1e-6, n
    exposed = G.z_ear0 - G.z_cb
    assert exposed == pytest.approx(25.5, abs=0.01)  # the whole case behind the seat; see CHANGELOG B8 for the 28 mm figure


# ------------------------------------------------------------------ B13 thermocouple hole
def test_B13_thermocouple_hole(model):
    G, P = model["G"], model["P"]
    tx, ty = gc.tc_hole_xy(P, G)
    hs = model["parts"]["housing"]
    assert has_bore(hs, 1.0, (tx, ty), axis=2)
    z0, z1 = bore_extent(hs, 1.0, (tx, ty), axis=2)
    assert z1 == pytest.approx(G.zs1, abs=0.01)           # opens on the frame front face
    assert z0 == pytest.approx(G.zs0 + 0.5, abs=0.01)     # stops 0.5 short of the ear


# ------------------------------------------------------------------ B14 gear face width 10.5 and the Z stack that follows
def test_B14_face_width_and_stack(model):
    G, parts = model["G"], model["parts"]
    for n in ("knuckle_a", "knuckle_b"):
        hub = parts[n].intersect(gc.cyl_z(0, 0, 9.0, -50, 50))
        assert hub.BoundingBox().zlen == pytest.approx(10.5, abs=1e-3)
    fp = parts["front_plate"].BoundingBox()
    assert fp.zmin == pytest.approx(G.z_k1 + 1.0, abs=1e-3)   # shim 0.85 + 0.15 end play room
    for x, y in model["P"]["housing"]["standoffs"]:
        z = bore_extent(parts["housing"], 6.0, (x, y), axis=2)
        assert z[1] == pytest.approx(fp.zmin, abs=0.01)
    gj = json.loads((ROOT / "analysis/gripper/results/gears.json").read_text(encoding="utf-8"))
    assert gj["cad_rev_b"]["face_width_drawn"] == 10.5
    row = gj["cad_rev_b"]["rows"]["DSServo DS3230 MG"]["by_face_width"]["b10.5"]
    assert row["pass_"] and row["SF_shock"] >= 1.0


# ------------------------------------------------------------------ B15 servo is a named parameter set; both rows build
@pytest.mark.parametrize("row", ["DSServo DS3218MG", "DSServo DS3230 MG"])
def test_B15_servo_model_rows(model, row):
    """Each named row builds its own servo envelope and gear face, measured on the solids."""
    import copy
    raw = copy.deepcopy(model["raw"])
    raw["servo"]["model"] = row
    P = gc.resolve(raw)
    G = gc.derive(P)
    r = raw["servo"]["models"][row]
    sv, _ = gc.servo_parts(P, G)
    below_ears = sv.intersect(gc.box(-100, 100, -100, 100, G.z_cb - 1, G.z_ear0)).BoundingBox()
    slice_x = sv.intersect(gc.box(G.sx1 - 1.0, G.sx1 - 0.5, -100, 100, -100, 100)).BoundingBox()
    assert below_ears.xlen == pytest.approx(r["body_y"], abs=1e-3) and below_ears.ylen == pytest.approx(r["body_x"], abs=1e-3)
    assert slice_x.zlen == pytest.approx(r["body_z"], abs=1e-3)
    kn = gc.knuckle(P, G, "A", [], {})
    assert kn.intersect(gc.cyl_z(0, 0, 9.0, -50, 50)).BoundingBox().zlen == pytest.approx(r["gear_face_width"], abs=1e-3)
    if row == model["raw"]["servo"]["model"]:
        assert model["parts"]["servo"].BoundingBox().ylen == pytest.approx(r["body_x"], abs=1e-3)


def test_B15_present_servo_builds(model):
    import copy
    raw = copy.deepcopy(model["raw"])
    raw["servo"]["model"] = "DSServo DS3218MG"
    P = gc.resolve(raw)
    G = gc.derive(P)
    assert P["gear"]["face_width"] == 8.0
    hs = gc.housing(P, G, [])
    assert hs.isValid() and len(hs.Solids()) == 1
    gc.BOUGHT_G["servo"] = float(model["P"]["servo"]["mass_g"])


# ------------------------------------------------------------------ B16-B19 fit3d findings
def test_B16_deck_screw_driver_access(model):
    G, W = model["G"], model["W0"]
    for x, z in model["P"]["housing"]["deck_screws"]:
        drv = gc.cyl_y(x, z, 3.0, G.yd0 - 2.4 - 40.0, G.yd0 - 2.4)  # Ø6 driver, 40 mm below the head
        for n in ("housing", "front_plate", "servo", "fasteners", "wrist_mount"):
            assert W[n].intersect(drv).Volume() < 1e-6, (x, z, n)


def test_B16_deck_screw_heads_clear(model):
    W = model["W0"]
    for s in item(model, "M3x6 deck screw"):
        assert s.intersect(W["housing"]).Volume() < 1e-6


def test_B18_horn_running_clearance(model):
    W = model["W0"]
    requirements = json.loads((CAD / "fit_requirements.json").read_text(encoding="utf-8"))["requirements"]
    assert W["horn"].distance(W["housing"]) >= requirements["horn|housing"]["minimum_clearance_mm"]


def test_B42_horn_seat_and_web(model):
    G, h, s = model["G"], model["P"]["housing"], model["P"]["servo"]
    assert G.pl == pytest.approx(2.5)
    assert s["horn_counterbore_d"] / 2 > h["horn_face_seat_radius"]
    assert s["horn_counterbore_depth"] >= h["horn_face_relief_depth"]
    assert h["horn_face_seat_radius"] - model["P"]["knuckle"]["pin_hole_cad"] / 2 >= 1.4
    assert G.zw1 - G.zw0 == pytest.approx(1.6)
    assert G.zw0 - G.z_ct == pytest.approx(h["boss_web_gap"])
    assert G.zw0 > G.z_ct


def test_B17_dog_set_screw_engages_slot(model):
    """Each dog sits inside its knuckle slot radially and axially (A-local frame), measured on the knuckle solid."""
    G = model["G"]
    kn = model["parts"]["knuckle_a"]
    horn = model["parts"]["horn"].BoundingBox()                          # z extent; the dogs are in the A pivot frame
    dogs = item(model, "dog set screw M3x10", "A")
    assert len(dogs) == 2
    for s in dogs:
        bb = s.BoundingBox()
        yc = bb.center.y
        sgn = 1.0 if yc > 0 else -1.0
        assert bb.zmin == pytest.approx(horn.zmin, abs=1e-3)              # tail flush with the horn's back face
        assert s.intersect(kn).Volume() < 1e-6                            # in the slot, not in the knuckle
        # radial: slot walls along the dog's radius, at mid engagement depth
        zm = (G.z_k0 + bb.zmax) / 2
        r0, r1 = gap_along(kn, 1, sgn * 2.0 if sgn > 0 else -12.0, 12.0 if sgn > 0 else -2.0, (0.0, zm))
        lo, hi = sorted((abs(r0), abs(r1)))
        assert lo + 0.2 <= abs(yc) - 1.5 and abs(yc) + 1.5 <= hi - 0.2    # >= 0.2 radial float each way
        # axial: slot floor from the knuckle solid; >= 2.5 engaged, >= 0.3 short of the floor
        iv = intervals_z([kn], 0.0, yc, G.z_k0 - 1, G.z_k1 + 1)
        floor = iv[0][0]
        assert bb.zmax - G.z_k0 >= 2.5 and floor - bb.zmax >= 0.3 - 1e-6


def test_B19_finger_to_other_knuckle(model):
    parts, G = model["parts"], model["G"]
    requirements = json.loads((CAD / "fit_requirements.json").read_text(encoding="utf-8"))["requirements"]
    for th in (-11.0, -10.0):
        W = gc.world(parts, G, th)
        for a, b in (("finger_a", "knuckle_b"), ("knuckle_a", "finger_b")):
            assert W[a].distance(W[b]) >= requirements[f"{a}|{b}"]["minimum_clearance_mm"]


def test_B43_root_wall(model):
    k, f = model["P"]["knuckle"], model["P"]["finger"]
    side_wall = (f["base_width"] - k["root_relief"] - k["peg_pitch"] - k["peg_d"]) / 2
    assert side_wall == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------------------------ B41 fit3d pairs that B16-B19 did not name, re-measured on rev B
@pytest.mark.parametrize("theta", [-11.0, -10.0, 0.0, 20.0])
def test_B41_fit3d_near_pairs(model, theta):
    """fit3d.json (d74372c) near pairs at its 0.5 mm 'tight' line: fasteners_a|finger_b and finger_a|fasteners_b
    (0.562), horn|fasteners (0.5), knuckle_a|knuckle_b (0.113, the gear mesh: overlap only, tested under R18)."""
    W = gc.world(model["parts"], model["G"], theta)
    assert W["fasteners_a"].distance(W["finger_b"]) >= 0.5
    assert W["finger_a"].distance(W["fasteners_b"]) >= 0.5
    assert W["horn"].distance(W["fasteners"]) >= 0.5


# ------------------------------------------------------------------ B38 knuckle end play, measured along the pin axis
@pytest.mark.parametrize("side", ["A", "B"])
def test_B38_end_play_measured(model, side):
    """Between the mid-plate front face and the front-plate back face, along a line through the shim annulus outside
    the bush (r 3.25), the free axial room is the end play; it must equal params end_play. A shim that only reaches
    the bush end (OD 6) leaves 2.0 mm here and fails."""
    G, P, W = model["G"], model["P"], model["W0"]
    k = P["knuckle"]
    xp = -G.a / 2 if side == "A" else G.a / 2
    kn = W["knuckle_a" if side == "A" else "knuckle_b"]
    shims = [s for s in item(model, "shim") if abs(s.BoundingBox().center.x - xp) < 1.0]
    assert len(shims) == 2
    od = shims[0].BoundingBox().xlen
    assert od > k["sleeve_od"] + 0.5                                       # bears on the hub face, beyond the Ø6 bore
    r = (k["sleeve_od"] / 2 + od / 2) / 2
    iv = intervals_z([W["housing"], W["front_plate"], kn] + shims, xp + r, 0.0, -G.pl - 0.01, G.z_fp1 + 0.01)
    assert len(iv) == 5                                                    # plate, shim, hub, shim, plate
    play = gaps_total(iv)
    assert play == pytest.approx(k["end_play"], abs=1e-3) and play == pytest.approx(G.end_play, abs=1e-3)
    # inside the bush radius the bush ends stand back from the shims (they do not set the end play)
    bush = gc.pose(item(model, "bronze bush", side)[0], side, G, 0.0)
    ivb = intervals_z(shims + [bush], xp + 2.25, 0.0, -0.01, G.z_fp0 + 0.01)
    assert gaps_total(ivb) == pytest.approx(play / 2 + 2 * 0.25, abs=1e-3)  # shim-to-hub room + 0.25 recess per end


# ------------------------------------------------------------------ B39 end wall beside the washer / nut notches
@pytest.mark.parametrize("layer", ["washer", "nut"])
def test_B39_nut_notch_wall(model, layer):
    G, P = model["G"], model["P"]
    h = P["housing"]
    hs = model["parts"]["housing"]
    z = G.zs1 + (0.4 if layer == "washer" else h["nut_notch_washer_h"] + 1.0)
    walls = []
    for x, y in gc.ear_holes(P, G):
        lo, hi = (x - 6, x) if x > 0 else (x, x + 6)
        sec = hs.intersect(gc.box(lo, hi, y - 0.02, y + 0.02, z - 0.02, z + 0.02)).Solids()
        piece = min(sec, key=lambda s: abs(s.BoundingBox().center.x - x))
        walls.append(piece.BoundingBox().xlen)
    wmin = min(walls)
    assert wmin == pytest.approx(G.wall_notch[0 if layer == "washer" else 1], abs=0.01)
    assert wmin >= (0.75 if layer == "washer" else 1.05)
    # washer and nut still turn in their layers
    assert h["nut_notch_r"] >= h["washer"]["od"] / 2 + 0.2
    assert h["nut_notch_r_nut"] >= h["nut"]["ac"] / 2 + 0.2
    assert h["nut_notch_washer_h"] >= h["limiter"]["len"] - h["wall"] + h["washer"]["t"] + 0.2


# ------------------------------------------------------------------ B40 dog coupling at stall: the README states what dog_check.py prints
def test_B40_dog_check_matches_readme(model):
    import dog_check
    out = dog_check.main()
    one = out["rows"]["M3 set screw 45H (as drawn), 1 dog"]
    assert one["SF_bending"] < 1.0 and one["SF_horn"] < 1.0                # fails at stall on one dog: stated, not hidden
    txt = (CAD / "README.md").read_text(encoding="utf-8")
    head = txt[:txt.index("## What changed")]
    assert f"{one['bending_MPa']:,} MPa" in head and f"{one['horn_bearing_MPa']} MPa" in head
    assert f"{out['one_dog_T_allow_Nm']:.2f} N·m" in head
    # the interim limit (0.5 x stall, torque taken proportional to current) stays under what one dog carries, above the hold
    assert out["T_servo_LC1_Nm"] < 0.5 * out["T_stall_6p5V_Nm"] < out["one_dog_T_allow_Nm"]
    assert "0.5 × the stall current" in head


# ------------------------------------------------------------------ review findings 3, 4: params and drawing text follow the solid
def test_params_and_sheet_text_follow_geometry(model):
    G, P = model["G"], model["P"]
    assert P["grip"]["r_c_current_cad_mm"] == pytest.approx(min(G.r_c_face.values()), abs=0.02)
    assert "3 x 8" not in json.dumps(model["raw"])                        # deck locating pins are h8 3 x 6
    assert f"{P['housing']['boss_web_t']:g} mm web" in model["raw"]["_provenance"]["housing.boss_web"]
    svg = (CAD / "drawings/housing.svg").read_text(encoding="utf-8")
    horn = model["W0"]["horn"].BoundingBox()
    yy, zm = 0.5, (horn.zmin + horn.zmax) / 2                            # just above the slide-in channel
    sec = model["parts"]["housing"].intersect(gc.box(-G.a / 2 - 20, -G.a / 2, yy - 0.01, yy + 0.01, zm - 0.01, zm + 0.01))
    x_wall = max(so.BoundingBox().xmax for so in sec.Solids())            # relief face in the A end wall
    radial = math.hypot(x_wall + G.a / 2, yy) - horn.ylen / 2             # measured relief radius - horn radius
    assert f"horn runs {radial:.1f} clear radially" in svg


# ------------------------------------------------------------------ B24 the README's mass and mass moment are fitcheck.py's
def test_B24_mass_moment_matches_fitcheck():
    import re
    fc = json.loads((CAD / "out/fitcheck.json").read_text(encoding="utf-8"))["mass"]
    txt = (CAD / "README.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*R10 fails: ([0-9.]+) g .*?, ([0-9,]+) g·mm", txt)
    assert m, "README R10 line"
    assert float(m.group(1)) == pytest.approx(fc["total_g_incl_cloth"], abs=0.05)
    assert int(m.group(2).replace(",", "")) == round(fc["mass_moment_gmm"])


# ------------------------------------------------------------------ jaw range R18: no interference between moving and static parts
@pytest.mark.parametrize("theta", [-11.0, -7.4, 0.0, 10.0, 20.0])
def test_R18_jaw_range_no_interference(model, theta):
    W = gc.world(model["parts"], model["G"], theta)
    bad = {}
    for mv in MOVING:
        for stn in STATIC:
            v = W[mv].intersect(W[stn]).Volume()
            if v > 1e-3:
                bad[f"{mv}|{stn}"] = round(v, 3)
    assert not bad
    assert W["knuckle_a"].intersect(W["knuckle_b"]).Volume() < 1e-3  # gear mesh, no overlap
    # the horn (a disc on the servo shaft) against everything except the dog set screws threaded into it
    for n in [m for m in MOVING if m != "fasteners_a"] + ["housing", "front_plate", "wrist_mount", "fasteners"]:
        assert W["horn"].intersect(W[n]).Volume() < 1e-3, n


# ------------------------------------------------------------------ params.json equals rev_b.yaml wherever both state a value
def test_params_equal_rev_b_yaml(model):
    yaml = pytest.importorskip("yaml")
    rb = yaml.safe_load((ROOT / "analysis/gripper/tolstack/stacks/rev_b.yaml").read_text(encoding="utf-8"))["rev_b"]["set"]
    P = model["P"]
    s, k, h, w, wi, f = P["servo"], P["knuckle"], P["housing"], P["wrist_mount"], P["wrist_interface"], P["finger"]
    assert k["dog_slot_w"] == rb["dog_slot_w"]
    assert s["body_x"] + 2 * h["cradle_pocket_clear"] == pytest.approx(rb["cradle_pocket_w"], abs=1e-9)
    assert w["recess_d_cad"] == rb["recess_d_cad"] == wi["pilot_recess_d_cad_fdm"]
    assert w["clearance_hole_cad"] == rb["hole_cad_d"] == wi["clearance_hole_d_cad_fdm"]
    assert wi["horn_hole_depth"] == rb["horn_hole_depth"]
    assert rb["pin_d_min"] == "=pin_h8_min" and "h8" in k["pin_spec"]
    assert "0.020" in k["pin_spec"] and rb["pin_clear"] == pytest.approx(0.020)
    # closed_gap 0.0 in the stack = faces parallel at first contact = toe-in contact_gap / (2 r_c)
    assert rb["closed_gap"] == 0.0
    assert f["toe_in_deg"] == pytest.approx(round(math.degrees(f["contact_gap"] / (2 * 65.0)), 2), abs=1e-9)
