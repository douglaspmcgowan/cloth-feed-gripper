#!/usr/bin/env python3
"""Assembly plan for the ME102B cloth-feed gripper (revision B).

Reads the CAD exports (cad/gripper/out/*.stl, out/parts.json, out/web/gripper_closed.glb, params.json),
identifies every fastener item, orders the build, checks every insertion path against the parts already
installed (sampled every 0.5 mm, boolean overlap on the STL meshes), casts a driver ray from every screw head,
and writes
  cad/gripper/assembly/steps.json         (deterministic: sorted keys, rounded numbers)
  cad/gripper/assembly/ASSEMBLY.md        (student document, generated from the same data)

Frame G, mm: X jaw closing axis, Y up to the wrist, Z out of the gear plane. Run:  python3 assembly_plan.py
"""
import itertools
import json
import math
import re
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
CAD = HERE.parent
OUT = CAD / "out"

SAMPLE_MM = 0.5          # insertion path sampling
COLLIDE_MM3 = 0.5        # overlap above the as-modelled baseline that counts as a collision
DRIVER_MM = 40.0         # free driver length wanted along a screw axis
DRIVER_RING_R = 2.5      # driver shaft radius used for the ray ring
INSERT_IRON_MM = 25.0    # free length wanted for the soldering iron tip
CAP_MM = 300.0

PART_KEYS = ["housing", "front_plate", "wrist_mount", "knuckle_a", "knuckle_b", "finger_a", "finger_b",
             "nail_a", "fsr_backing_b", "fsr_sensor_b", "fsr_puck_b", "servo", "horn"]
GROUPS = ["fasteners", "fasteners_a", "fasteners_b"]
SIDE_PART = {"knuckle_a": "A", "finger_a": "A", "nail_a": "A",
             "knuckle_b": "B", "finger_b": "B", "fsr_backing_b": "B", "fsr_sensor_b": "B", "fsr_puck_b": "B"}

# BOM fastener line labels (cad/gripper/drawings/BOM.md) used as the item type
T_PIN = "ISO 2338 h8 3 x 16"
T_SHIM = "shim washer 3.2 x 7 x 0.85"
T_HORN = "M3x6 ISO 7045 pan head (horn)"
T_DECK = "M3x6 ISO 7045 pan head (deck)"
T_INS = "M3 brass heat-set insert 4.2 x 3.5"
T_LOC = "ISO 2338 h8 3 x 6 locating pin"
T_EAR = "M3x10 ISO 7045 pan head (servo ear)"
T_LIM = "compression limiter 5.0 x 3.2 x 2.55"
T_WASH = "M3 ISO 7089 washer 7 x 3.2 x 0.5"
T_NUT = "M3 ISO 4032 nut"
T_PLATE = "M3x16 pan head (front plate)"
T_BUSH = "sintered bronze plain bush 3 x 6 x 10"
T_PEG = "dowel pin 2 x 24 (finger pegs)"
T_M2 = "M2x30 + nut (finger root)"
T_DOG = "M3x10 ISO 4026 socket set screw (dog)"
CAD_TO_TYPE = {"pin h8 3x16": (T_PIN, "pin"), "shim 3.2x7x0.85": (T_SHIM, "shim"),
               "M3x6 horn screw": (T_HORN, "horn_screw"), "M3x6 deck screw": (T_DECK, "deck_screw"),
               "M3 heat-set insert": (T_INS, "insert"), "locating pin h8 3x6": (T_LOC, "locpin"),
               "M3x10 ear screw": (T_EAR, "ear_screw"), "limiter sleeve 5x3.2x2.55": (T_LIM, "limiter"),
               "washer M3 7x3.2x0.5": (T_WASH, "washer"), "nut M3": (T_NUT, "nut"),
               "M3x16 plate screw": (T_PLATE, "plate_screw"), "bronze bush 3x6x10": (T_BUSH, "bush"),
               "dog set screw M3x10": (T_DOG, "dog_screw")}
# direction each fastener travels as it goes in (frame G)
INSERT_DIR = {"pin": (0, 0, -1), "shim": (0, 0, -1), "horn_screw": (0, 1, 0), "deck_screw": (0, 1, 0),
              "insert": (0, 1, 0), "locpin": (0, 1, 0), "ear_screw": (0, 0, 1), "limiter": (0, 0, -1),
              "washer": (0, 0, -1), "nut": (0, 0, -1), "plate_screw": (0, 0, -1), "bush": (0, 0, -1),
              "peg": (0, 0, 1), "m2": (0, 0, 1), "dog_screw": (0, 0, -1)}
SCREW_KINDS = {"horn_screw", "deck_screw", "ear_screw", "plate_screw", "m2", "dog_screw"}


# ------------------------------------------------------------------ small helpers
def rnd(x, n=2):
    if isinstance(x, (list, tuple, np.ndarray)):
        return [rnd(v, n) for v in x]
    if isinstance(x, (np.floating, float)):
        v = round(float(x), n)
        return 0.0 if v == 0 else v
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def to_manifold(t):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices, dtype=np.float32),
                               tri_verts=np.asarray(t.faces, dtype=np.uint32)))


def rot_about(pivot_x, ang_deg):
    a = math.radians(ang_deg)
    c, s = math.cos(a), math.sin(a)
    R = np.eye(4)
    R[0, 0], R[0, 1], R[1, 0], R[1, 1] = c, -s, s, c
    T1, T2 = np.eye(4), np.eye(4)
    T1[0, 3], T2[0, 3] = pivot_x, -pivot_x
    return T1 @ R @ T2


def pose_matrix(side, theta, a):
    """Jaw pose as in gripper_concept.pose: A rotates -theta about pivot A, B +theta about pivot B."""
    if not theta or side is None:
        return np.eye(4)
    return rot_about(-a / 2, -theta) if side == "A" else rot_about(a / 2, theta)


def rotate_dir(d, side, theta, a):
    M = pose_matrix(side, theta, a)
    v = M[:3, :3] @ np.asarray(d, float)
    return unit(v)


# ------------------------------------------------------------------ load CAD
def load_cad():
    P = json.loads((CAD / "params.json").read_text(encoding="utf-8"))
    PJ = json.loads((OUT / "parts.json").read_text(encoding="utf-8"))
    meshes = {k: trimesh.load(OUT / f"{k}.stl") for k in PART_KEYS}
    comps = {g: trimesh.load(OUT / f"{g}.stl").split(only_watertight=False) for g in GROUPS}
    glb = trimesh.load(OUT / "web" / "gripper_closed.glb")
    return P, PJ, meshes, comps, glb


def identify_items(PJ, comps, glb):
    """Group the GLB solids of each fastener into items. The GLB nodes are faces; each belongs to the STL solid
    whose bounds contain it. Items follow the compound order recorded in parts.json."""
    fi = PJ["fastener_items"]
    order = {"fasteners": fi["static"], "fasteners_a": fi["A"], "fasteners_b": fi["B"]}
    items = []
    counters = {}
    for g in GROUPS:
        nodes = {}
        for name, geom in glb.geometry.items():
            m = re.fullmatch(re.escape(g) + r"(?:_(\d+))?", name)
            if m:
                nodes[name] = (int(m.group(1) or 0), geom.bounds)
        cs = comps[g]
        cb = [c.bounds for c in cs]
        assign = {i: [] for i in range(len(cs))}
        for name, (idx, b) in sorted(nodes.items(), key=lambda kv: kv[1][0]):
            best = None
            for i, bb in enumerate(cb):
                if (b[0] >= bb[0] - 0.06).all() and (b[1] <= bb[1] + 0.06).all():
                    vol = float(np.prod(bb[1] - bb[0] + 1e-3))
                    if best is None or vol < best[0]:
                        best = (vol, i)
            if best is None:
                raise RuntimeError(f"GLB node {name} fits no {g} solid")
            assign[best[1]].append((idx, name))
        seq = sorted(range(len(cs)), key=lambda i: min(ix for ix, _ in assign[i]))
        pos = 0
        for cad_name in order[g]:
            if cad_name == "pegs + M2 screw":
                trio = [seq[pos], seq[pos + 1], seq[pos + 2]]
                pos += 3
                parts = []
                for ci in trio:
                    w = float(cs[ci].extents[0])
                    parts.append((T_PEG, "peg", ci) if abs(w - 2.0) < 0.05 else (T_M2, "m2", ci))
                use = parts
            else:
                typ, kind = CAD_TO_TYPE[cad_name]
                use = [(typ, kind, seq[pos])]
                pos += 1
            for typ, kind, ci in use:
                counters[kind] = counters.get(kind, 0) + 1
                items.append({"type": typ, "kind": kind, "group": g, "comp": ci,
                              "nodes": [n for _, n in sorted(assign[ci])], "mesh": cs[ci]})
    return items


def name_items(items):
    """Stable ids. Pins, shims, bushes, pegs and M2 bolts carry their side; the rest are numbered."""
    count = {}
    for it in items:
        c = it["mesh"].bounds.mean(0)
        kind = it["kind"]
        side = "a" if c[0] < 0 else "b"
        if kind == "pin":
            iid = f"pin_{side}"
        elif kind == "shim":
            iid = f"shim_{side}_{'back' if c[2] < 5 else 'front'}"
        elif kind == "bush":
            iid = f"bush_{side}"
        elif kind in ("peg", "m2"):
            n = count.get((kind, side), 0) + 1
            count[(kind, side)] = n
            iid = f"m2_{side}" if kind == "m2" else f"peg_{side}_{n}"
        else:
            n = count.get(kind, 0) + 1
            count[kind] = n
            iid = f"{kind}_{n}"
        it["id"] = iid
        it["side"] = "A" if it["group"] == "fasteners_a" else "B" if it["group"] == "fasteners_b" else None
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids)), ids
    return items


def item_record(it):
    m = it["mesh"]
    v = m.volume if m.volume > 1e-6 else None
    cen = m.center_mass if v else m.bounds.mean(0)
    ax = unit(INSERT_DIR[it["kind"]])
    return {"id": it["id"], "type": it["type"], "group": it["group"], "nodes": it["nodes"],
            "centroid": rnd(cen), "axis": rnd(ax, 3),
            "bbox": rnd(m.bounds.reshape(-1).tolist()),
            "driver_axis": rnd(-ax, 3) if it["kind"] in SCREW_KINDS or it["kind"] == "insert" else None}


# ------------------------------------------------------------------ plan data (the build order)
SUBS = [
    ("prep", "Prepare the printed parts", None),
    ("wrist", "Wrist plate on the arm", [0, -60, 0]),
    ("housing", "Servo and housing", [0, -60, 0]),
    ("mount", "Housing onto the wrist plate", None),
    ("gears", "Pins, knuckles and front plate", None),
    ("fingers", "Fingers and pads", None),
]

TORQUE_NOTE = "Torques are assumed starting values, not measured; stop at the first sign of a stripped thread."


def build_steps(it, a, P):
    """Return the ordered step list (revision B). Moves reference part keys or item ids."""
    def by_kind(k):
        return [i["id"] for i in it if i["kind"] == k]

    def mv(what, d, dist, rot=None):
        m = {"what": what, "dir": d, "dist": dist}
        if rot is not None:
            m["rot_deg"] = rot
        return m

    UP, ZP, ZN = [0, 1, 0], [0, 0, 1], [0, 0, -1]
    hs, ds, ins, loc = by_kind("horn_screw"), by_kind("deck_screw"), by_kind("insert"), by_kind("locpin")
    es, ps, lim = by_kind("ear_screw"), by_kind("plate_screw"), by_kind("limiter")
    wsh, nts, dogs = by_kind("washer"), by_kind("nut"), by_kind("dog_screw")
    cx = {i["id"]: float(i["mesh"].bounds.mean(0)[0]) for i in it}

    def side_in(i):  # washers and nuts slide in sideways from outboard, at their seated height, into the end-wall notch
        return [1, 0, 0] if cx[i] < 0 else [-1, 0, 0]

    th = 20.0
    dA = rotate_dir((-1, 0, 0), "A", th, a)   # nail A travels toward its pad face (-X at theta 0)
    dB = rotate_dir((1, 0, 0), "B", th, a)    # B pad stack travels toward finger B (+X at theta 0)
    S = []

    def step(sid, sub, title, parts, items, moves, fasteners, tools, check, note=None, theta=0.0, bench=False):
        d = {"id": sid, "sub": sub, "title": title, "parts": parts, "items": items, "moves": moves,
             "fasteners": fasteners, "tools": tools, "check": check, "theta_deg": theta}
        if note:
            d["note"] = note
        if bench:
            d["bench"] = True
        S.append(d)

    # ---- prep (bench)
    step("s1", "prep", "Clamp the housing and front plate together and line-ream the pin holes", ["housing", "front_plate"], [], [],
         "3 x M3x16 plate screws, snug, to clamp the front plate to the housing; take them out again after reaming",
         ["3.0 mm H7 hand reamer", "3.0 mm pin gauge"],
         "Ream 3.0 H7 from the mid-plate back face through into the 1.5 mm blind holes in the front plate. A 3.0 pin gauge goes in to the bottom of both holes. Mark the pair.",
         "Reaming the two parts together keeps the two pins parallel. The housing and front plate stay a matched pair.", bench=True)
    step("s2", "prep", "Ream the boss-web bore 9.0 H7", ["housing"], [], [],
         "none", ["9.0 mm H7 hand reamer"],
         "Ream from behind through the cradle pocket. The servo output boss drops into the bore by hand.",
         "Test with the servo boss now, while the housing is still empty. The web is only 1.6 mm thick, spans about 40 mm "
         "and prints on supports: clear the support from both faces first, then turn the reamer slowly with light feed "
         "and back it out turning forward; a reamer that grabs tears the web out. Print a spare housing if the web cracks.", bench=True)
    step("s3", "prep", "Ream the four peg holes 3.0 H7", ["housing", "wrist_mount"], [], [],
         "none", ["3.0 mm H7 hand reamer", "3.0 mm pin gauge"],
         "Two deck peg holes in the housing and two spider peg holes in the wrist plate, each takes the 3.0 pin gauge.", bench=True)
    step("s4", "prep", "Ream both knuckle bores 6.0 H7 and press in the bushes", ["knuckle_a", "knuckle_b"], ["bush_a", "bush_b"],
         [mv("bush_a", ZN, 10), mv("bush_b", ZN, 10)],
         "2 x sintered bronze plain bush 3 x 6 x 10, pressed in with the arbor press until neither end stands proud of a hub face "
         "(centred: 0.25 mm below each face of the 10.5 mm hub)",
         ["6.0 mm H7 hand reamer", "arbor press", "3.0 mm pin gauge", "0-25 mm micrometer"],
         "Pin-gauge each pressed bore, then measure the two ISO 2338 h8 3 x 16 pins with the micrometer and pair each pin with a bore for 0.000-0.020 mm clearance.",
         "Pairing the pins to the bores is done once here, so mark which pin goes to which knuckle. The shims bear on the "
         "hub faces, so a bush end standing proud would set the end play instead: check both faces with a straight edge.", bench=True)
    step("s5", "prep", "Tap the two dog holes in the horn", [], [], [],
         "none; skip if the horn already has them", ["M3 tap", "2.5 mm drill"],
         "Two M3 holes at r 7 mm, plus and minus 90 degrees from the horn arm line; an M3 screw runs in by hand.",
         "Drill and tap by hand, square to the horn face.", bench=True)
    # ---- wrist
    step("s6", "wrist", "Heat-set four inserts into the wrist plate", ["wrist_mount"], ins,
         [mv(i, UP, 8) for i in ins],
         "4 x M3 brass heat-set insert 4.2 x 3.5, pressed in from the underside of the spider",
         ["soldering iron with an M3 insert tip, set to about 220 C", "flat block"],
         "Each insert sits flush with the underside of the plate and square to it. Let the plastic cool before screwing into it.",
         "PETG melts around 220 C, so keep the iron on each insert only as long as it takes to push it flush.", bench=True)
    step("s7", "wrist", "Bond the two locating pins into the spider holes", [], loc,
         [mv(i, UP, 8) for i in loc],
         "2 x ISO 2338 h8 3 x 6 locating pin, retaining compound 638, 2.5 mm standing proud",
         ["retaining compound 638", "depth gauge"],
         "Both pins stand 2.5 mm proud of the spider underside and square to it. Leave the compound to cure.",
         "Bond them before the wrist plate goes on the arm. The deck holes take the pins later with a sliding fit.", bench=True)
    step("s8", "wrist", "Measure the horn hole depth, then seat the wrist plate on the horn", ["wrist_mount"], ins + loc,
         [mv("wrist_mount", UP, 60)] + [mv(i, UP, 60) for i in ins + loc],
         "none until the next step",
         ["caliper with depth rod"],
         "Measure the horn hole depth (DB M15) and pick the screw length with wrist_mount.horn_screw_rule: M3x6 needs 3.75 mm or more, 3.5 to 3.7 is marginal, less means drill and re-tap. The four counterbores line up with the four horn holes.",
         "The horn belongs to the SO-101 arm and is not in the bill of materials.")
    step("s9", "wrist", "Fit the four horn screws", [], hs, [mv(i, UP, 10, 720) for i in hs],
         "4 x M3x6 ISO 7045 pan head into the SO-101 aluminium horn (length per the measured depth), about 0.6 N m (assumed)",
         ["PH1 screwdriver", "torque screwdriver"],
         "All four heads seat in the counterbores and the plate does not rock. Stop if a screw bottoms before the plate clamps.",
         "This is the only time the horn screws are easy to reach. " + TORQUE_NOTE)
    # ---- housing (bench)
    step("s10", "housing", "Press four limiter sleeves into the seat holes", ["housing"], lim,
         [mv(i, ZN, 3) for i in lim],
         "4 x compression limiter 5.0 x 3.2 x 2.55, from the frame front face",
         ["flat block"],
         "Each sleeve sits flush in its seat hole, 2.55 mm long.",
         "The sleeves take the clamp load of the ear screws so the printed seat does not creep.", bench=True)
    step("s11", "housing", "Power the servo to the jaw-0 pulse", [], [], [],
         "none", ["servo and controller"],
         "The servo is on the jaw-0 pulse (the CAD closed pose) and stays powered until the horn is on.",
         "The horn goes on in the next step at this angle, so the dog slots land at jaw angle 0.", bench=True)
    step("s12", "housing", "Slide the horn in from below under the arc slots", ["horn"], [],
         [mv("horn", UP, 40)],
         "1 x M3x6 ISO 7380 button head centre screw, loose in the horn for now",
         ["none"],
         "The horn sits between the boss web and the mid plate and its two tapped holes are under the two arc slots.",
         "Slide the horn from below, +Y, with the centre screw already in it.", bench=True)
    step("s13", "housing", "Slide the servo in from behind and drive the centre screw", ["servo"], [],
         [mv("servo", ZP, 60)],
         "the M3x6 ISO 7380 centre screw, driven through the pin A bore",
         ["2.0 mm hex key"],
         "The boss is in the web bore and the spline is in the horn. The hex key goes through the pin A bore into the centre screw while you hold the servo up.",
         "Pin A is not in yet. It goes in at step 16 because the hex key uses its bore.", bench=True)
    step("s14", "housing", "Fit the four ear screws with washers and nuts", [], es + wsh + nts,
         [mv(i, ZP, 10, 720) for i in es] + [mv(i, side_in(i), 12) for i in wsh + nts],
         "4 x M3x10 ISO 7045 from the ear side, washer + nut on the frame front face in the end-wall notches, about 0.4 N m (assumed)",
         ["PH1 screwdriver", "7 mm spanner or pliers"],
         "The ears are pulled flat against the sleeves and the servo does not move when pushed by hand.",
         "Slide each washer and nut in sideways from the outboard end into its notch (they cannot come straight down past the end wall), then hold the nut while its screw turns. " + TORQUE_NOTE, bench=True)
    step("s15", "housing", "Fit the two dog set screws through the arc slots", [], dogs,
         [mv(i, ZN, 20, 720) for i in dogs],
         "2 x M3x10 ISO 4026 socket set screw, thread-locker 243, from the front through the mid-plate arc slots into the horn",
         ["1.5 mm hex key", "thread-locker 243"],
         "Each screw top stands 4.0 mm in front of the mid-plate front face.",
         "They carry the drive to knuckle A. Do not over-tighten into the aluminium. They are not strong enough to carry a "
         "full stall on one dog (README, Dog coupling): keep the interim limit there until the coupling is fixed.", bench=True)
    step("s16", "housing", "Press the two h8 pins in from the front", ["housing"], ["pin_a", "pin_b"],
         [mv("pin_a", ZN, 20), mv("pin_b", ZN, 20)],
         "2 x ISO 2338 h8 3 x 16, retaining compound 638, pressed in until 0.5 mm short of the mid-plate back face",
         ["arbor press", "retaining compound 638"],
         "Both pins stand 14.0 mm proud of datum D and square to the mid plate.",
         "Pin A goes in only after step 13, because the hex key uses its bore. Use each pin with the bore it was paired with. "
         "Service: pin A is bonded and its back end faces the horn, so it can only be driven out backwards after the servo "
         "and the horn come off (steps 13 and 12 in reverse); pin B can be driven out backwards at any time.", bench=True)
    # ---- mount
    step("s17", "mount", "Lift the housing up onto the wrist plate", ["housing"], [],
         [mv("housing", UP, 60), mv("horn", UP, 60), mv("servo", UP, 60)] +
         [mv(i, UP, 60) for i in es + wsh + nts + lim + dogs + ["pin_a", "pin_b"]],
         "none until the next step", ["none"],
         "The locating pins go into the deck holes, the deck lies flat against the underside of the wrist plate and the four deck holes sit over the inserts.",
         "The servo, horn and all the fasteners fitted so far come up with the housing.")
    step("s18", "mount", "Fit the four deck screws", [], ds, [mv(i, UP, 10, 720) for i in ds],
         "4 x M3x6 ISO 7045 pan head up through the deck into the heat-set inserts, about 0.5 N m (assumed)",
         ["PH1 screwdriver", "torque screwdriver"],
         "The deck is tight against the wrist plate with no gap at any of the four screws.",
         "DECKNOTE " + TORQUE_NOTE)
    # ---- gears
    step("s19", "gears", "Slip the two back shims onto the pins", [], ["shim_a_back", "shim_b_back"],
         [mv("shim_a_back", ZN, 10), mv("shim_b_back", ZN, 10)],
         "2 x shim washer 3.2 x 7 x 0.85, one per pin, against the mid plate; it bears on the knuckle hub face, not on the bush",
         ["tweezers"],
         "Each shim spins freely on its pin.")
    step("s20", "gears", "Fit knuckle A with its bush onto pin A", ["knuckle_a"], [],
         [mv("knuckle_a", ZN, 20), mv("bush_a", ZN, 20)],
         "none; the bush was pressed in at step 4",
         ["none"],
         "The knuckle turns smoothly on the pin and the two dog slots sit on the two set screws at jaw angle 0.",
         "Hold the knuckle at jaw angle 0 so the dog slots line up with the set screws.")
    step("s21", "gears", "Fit knuckle B with its bush onto pin B", ["knuckle_b"], [],
         [mv("knuckle_b", ZN, 20), mv("bush_b", ZN, 20)],
         "none; the bush was pressed in at step 4",
         ["none"],
         "The two gear sectors mesh with no visible gap at jaw angle 0 and both knuckles still turn on their pins.",
         "Drop knuckle B straight down while the gears are at jaw angle 0 so the teeth find each other.")
    step("s22", "gears", "Pick and slip on the two front shims", [], ["shim_a_front", "shim_b_front"],
         [mv("shim_a_front", ZN, 10), mv("shim_b_front", ZN, 10)],
         "2 x shim washer 3.2 x 7, one per pin, picked from the 0.05 mm step assortment (0.85 nominal: plate gap 12.5 - hub 10.5 - 2 x 0.85 = 0.3)",
         ["feeler gauges 0.05-0.5", "tweezers"],
         "End play of each knuckle is 0.3 mm plus or minus 0.05 mm, measured with the feeler gauges.",
         "Change the shim thickness until each pin is in range.")
    step("s23", "gears", "Press the front plate onto the pins and standoffs", ["front_plate"], [],
         [mv("front_plate", ZN, 20)],
         "none until the next step; the pin ends go 1.5 mm into the blind holes", ["none"],
         "The plate sits on all three standoffs and the knuckles still turn freely.",
         "Use the matched front plate from step 1. Do not tilt it; start both pins together.")
    step("s24", "gears", "Fit the three front plate screws", [], ps, [mv(i, ZN, 10, 720) for i in ps],
         "3 x M3x16, self-tapping into the 2.5 mm pilot in each standoff, about 0.3 N m (assumed)",
         ["PH1 screwdriver", "torque screwdriver"],
         "The plate is tight on the standoffs and the gears still turn by hand through the servo.",
         "These cut their own thread in PETG, so stop at first snug. " + TORQUE_NOTE)
    # ---- fingers
    step("s25", "fingers", "Slide finger A up into the root block of knuckle A", ["finger_a"], [],
         [mv("finger_a", UP, 30)], "none until the next step", ["none"],
         "The root tab sits between the two cheeks against the web and its peg holes line up with the cheek holes.")
    step("s26", "fingers", "Pin finger A with two dowels and an M2 bolt", [], ["peg_a_1", "peg_a_2", "m2_a"],
         [mv("peg_a_1", ZP, 12), mv("peg_a_2", ZP, 12), mv("m2_a", ZP, 12, 720)],
         "2 x dowel pin 2 x 24 (6 mm apart), 1 x M2x30 with nut, about 0.2 N m (assumed)",
         ["1.5 mm hex key", "tweezers"],
         "The finger cannot slide out of the block and the bolt is snug without crushing the cheeks.",
         "The CAD shows only a plain shank, so head and nut sides are assumed: head on the back, nut on the front end. " + TORQUE_NOTE)
    step("s27", "fingers", "Slide finger B up into the root block of knuckle B", ["finger_b"], [],
         [mv("finger_b", UP, 30)], "none until the next step", ["none"],
         "The root tab sits between the two cheeks against the web and its peg holes line up with the cheek holes.")
    step("s28", "fingers", "Pin finger B with two dowels and an M2 bolt", [], ["peg_b_1", "peg_b_2", "m2_b"],
         [mv("peg_b_1", ZP, 12), mv("peg_b_2", ZP, 12), mv("m2_b", ZP, 12, 720)],
         "2 x dowel pin 2 x 24 (6 mm apart), 1 x M2x30 with nut, about 0.2 N m (assumed)",
         ["1.5 mm hex key", "tweezers"],
         "The finger cannot slide out of the block.", "Same as finger A. " + TORQUE_NOTE)
    step("s29", "fingers", "Open the jaw 20 degrees and bond the FSR backing and the FSR on finger B",
         ["fsr_backing_b", "fsr_sensor_b"], [],
         [mv("fsr_backing_b", rnd(dB, 4), 10), mv("fsr_sensor_b", rnd(dB, 4), 10)],
         "cyanoacrylate glue, thin film on the pad face; a dot of glue at the sensor head only",
         ["cyanoacrylate glue", "servo and controller", "tweezers"],
         "The backing sits flat on the pad with its pocket facing the jaw centre, tight to the tip edge. The FSR head lies flat in the pocket and the tail leaves through the tail slot without a sharp bend.",
         "The jaw must be open at 20 degrees for steps 29 to 31: with the jaw closed the pad gap is only 4.45 mm and the stack on one finger blocks the other. Drive the jaw with the servo; never turn it by hand.",
         theta=th)
    step("s30", "fingers", "Bond the puck onto the FSR active area", ["fsr_puck_b"], [],
         [mv("fsr_puck_b", rnd(dB, 4), 8)],
         "cyanoacrylate glue, one small drop", ["cyanoacrylate glue", "tweezers"],
         "The puck is centred inside the printed circle of the active area and does not touch the backing edge.",
         theta=th)
    step("s31", "fingers", "Bond the nail onto the pad of finger A", ["nail_a"], [],
         [mv("nail_a", rnd(dA, 4), 10)],
         "cyanoacrylate glue, thin film", ["cyanoacrylate glue"],
         "The nail sits flat on the pad face at the tip edge and faces the puck.",
         theta=th)
    step("s32", "fingers", "Close the jaw, check the gap and travel, then calibrate the pinch point", [], [], [],
         "none", ["servo and controller", "feeler gauge or paper strip"],
         "At jaw angle 0 the rigid faces are 1.0 mm apart at the contact height. Run the jaw from -11 to +20 degrees and check that nothing rubs. Then do the one-time pinch-point TCP calibration (tolerance row 5).",
         "Jaw angle 0 is the CAD closed pose. Every part is now back at its CAD position.")
    return S


# ------------------------------------------------------------------ geometry engine
class Engine:
    def __init__(self, P, meshes, items):
        self.a = P["gear"]["center_distance"]
        self.base = {}      # name -> trimesh at theta 0
        self.side = {}
        self.kind = {}
        for k in PART_KEYS:
            self.base[k] = meshes[k]
            self.side[k] = SIDE_PART.get(k)
            self.kind[k] = "part"
        for i in items:
            self.base[i["id"]] = i["mesh"]
            self.side[i["id"]] = i["side"]
            self.kind[i["id"]] = "item"
        # CAD pose(): dog pins (fasteners_a) turn with knuckle A; the horn does not
        self.cache = {}

    def mesh(self, name, theta):
        key = (name, theta)
        if key not in self.cache:
            t = self.base[name]
            M = pose_matrix(self.side[name], theta, self.a)
            self.cache[key] = t.copy().apply_transform(M) if theta else t
        return self.cache[key]

    def manifold(self, name, theta):
        key = ("M", name, theta)
        if key not in self.cache:
            self.cache[key] = to_manifold(self.mesh(name, theta))
        return self.cache[key]

    def overlap(self, n1, n2, theta, shift=None):
        """overlap volume mm3 of n1 (translated by shift) and n2."""
        b1 = self.mesh(n1, theta).bounds.copy()
        b2 = self.mesh(n2, theta).bounds
        if shift is not None:
            b1 += shift
        if (b1[1] < b2[0] - 1e-6).any() or (b2[1] < b1[0] - 1e-6).any():
            return 0.0
        m1 = self.manifold(n1, theta)
        if shift is not None:
            m1 = m1.translate(tuple(float(x) for x in shift))
        return float((m1 ^ self.manifold(n2, theta)).volume())


def overlap_bounds(eng, n1, n2, theta, shift):
    m1 = eng.manifold(n1, theta).translate(tuple(float(x) for x in shift))
    r = (m1 ^ eng.manifold(n2, theta)).to_mesh()
    v = np.asarray(r.vert_properties)[:, :3]
    return v.min(0), v.max(0)


def ray_clear(origins, d, meshes, cap=CAP_MM):
    d = np.asarray(d, float)
    best = np.full(len(origins), np.inf)
    hit_by = [None] * len(origins)
    for name, mesh in meshes:
        tri = mesh.triangles
        v0 = tri[:, 0]
        e1 = tri[:, 1] - v0
        e2 = tri[:, 2] - v0
        p = np.cross(d, e2)
        det = (e1 * p).sum(1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        for i, o in enumerate(origins):
            s = o - v0
            u = (s * p).sum(1) * inv
            q = np.cross(s, e1)
            v = (q * d).sum(1) * inv
            t = (e2 * q).sum(1) * inv
            h = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6)
            if h.any():
                tm = float(t[h].min())
                if tm < best[i]:
                    best[i], hit_by[i] = tm, name
    return best, hit_by


def ring_origins(c, d, r, n=8):
    d = unit(d)
    helper = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 1.0, 0])
    u = unit(np.cross(d, helper))
    w = np.cross(d, u)
    pts = [c]
    for k in range(n):
        t = 2 * math.pi * k / n
        pts.append(c + r * (math.cos(t) * u + math.sin(t) * w))
    return pts


# ------------------------------------------------------------------ run the plan
def run(P, meshes, items):
    a = P["gear"]["center_distance"]
    eng = Engine(P, meshes, items)
    steps = build_steps(items, a, P)
    item_by_id = {i["id"]: i for i in items}
    world, bench = {}, {s[0]: {} for s in SUBS}
    findings, tool_access, sweep_log, path_hits = [], [], [], []
    placed_step = {}

    def ctx_for(st):
        return bench[st["sub"]] if st.get("bench") else world

    for st in steps:
        theta = st["theta_deg"]
        ctx = ctx_for(st)
        installed = dict(ctx)
        movers = {}
        for m in st["moves"]:
            movers[m["what"]] = m
        # carried members come out of the bench into the world after this step
        carried = [n for n in movers if any(n in b_ for b_ in bench.values()) and not st.get("bench")]
        new_names = list(st["parts"]) + list(st["items"])
        for n in new_names:
            assert n in eng.base, n
        # every name that moves must be new in this step or be carried
        for n in movers:
            assert n in new_names or n in carried, (st["id"], n)
        stat = {n: True for n in installed if n not in movers}
        for n in new_names:
            if n not in movers:
                stat[n] = True
        # sweep each mover
        for n, m in sorted(movers.items()):
            d = np.asarray(m["dir"], float)
            dist = float(m["dist"])
            base_ov = {o: eng.overlap(n, o, theta) for o in stat}
            first = {}
            for k in range(int(round(dist / SAMPLE_MM)), 0, -1):
                dd = k * SAMPLE_MM
                shift = -d * dd
                for o in sorted(stat):
                    v = eng.overlap(n, o, theta, shift)
                    if v > base_ov[o] + COLLIDE_MM3:
                        rec = first.setdefault(o, {"d": dd, "vol": v, "shift": shift})
                        rec["vol"] = max(rec["vol"], v)
            for o, rec in sorted(first.items()):
                lo, hi = overlap_bounds(eng, n, o, theta, rec["shift"])
                path_hits.append({"step": st["id"], "what": n, "other": o, "d": rec["d"], "vol": rec["vol"],
                                  "lo": lo, "hi": hi, "dir": d})
            sweep_log.append({"step": st["id"], "what": n, "samples": int(round(dist / SAMPLE_MM)),
                              "collisions": sorted(first)})
        # driver ray for screws and inserts placed in this step
        for iid in [i_ for i_ in st["items"] if i_ not in carried]:
            it = item_by_id[iid]
            if it["kind"] not in SCREW_KINDS and it["kind"] != "insert":
                continue
            ax = unit(INSERT_DIR[it["kind"]])
            V = eng.mesh(iid, theta).vertices
            proj = V @ ax
            head = V[proj <= proj.min() + 0.02].mean(0)
            origin = head - ax * 0.05
            drv = -ax
            ctx_meshes = [(o, eng.mesh(o, theta)) for o in sorted(stat)]
            tool_rec = {"item": iid, "step": st["id"], "axis": rnd(drv, 3)}
            d_, by = ray_clear(ring_origins(origin, drv, DRIVER_RING_R), drv, ctx_meshes)
            clear = float(min(d_.min(), CAP_MM))
            hitn = by[int(np.argmin(d_))]
            need = INSERT_IRON_MM if it["kind"] == "insert" else DRIVER_MM
            tool_rec.update({"clear_mm": rnd(clear, 1), "hit": hitn if clear < CAP_MM else None,
                             "ok": bool(clear >= need), "need_mm": need})
            tool_access.append(tool_rec)
        # commit the step
        for n in new_names:
            if n not in carried:
                if st["moves"]:  # a bench operation with no moves (ream, tap, measure) places nothing
                    ctx[n] = True
                placed_step.setdefault(n, st["id"])
        if carried:
            for n in carried:
                world[n] = True
                for b_ in bench.values():
                    b_.pop(n, None)
        # bench members that were not listed as moving but belong to the join (none expected)
        if not st.get("bench"):
            left = [n for n in list(bench[st["sub"]])] if st["sub"] != "prep" else []
            assert not left, (st["id"], left)
    return eng, steps, findings, tool_access, sweep_log, placed_step, path_hits


def final_service_access(eng, items, tool_access):
    """Driver clearance with the whole gripper built (service access)."""
    allm = [(n, eng.mesh(n, 0.0)) for n in sorted(eng.base)]
    item_by_id = {i["id"]: i for i in items}
    for rec in tool_access:
        it = item_by_id[rec["item"]]
        ax = unit(INSERT_DIR[it["kind"]])
        V = eng.mesh(rec["item"], 0.0).vertices
        proj = V @ ax
        head = V[proj <= proj.min() + 0.02].mean(0)
        origin = head - ax * 0.05
        drv = -ax
        use = [(n, m) for n, m in allm if n != rec["item"]]
        d_, by = ray_clear(ring_origins(origin, drv, DRIVER_RING_R), drv, use)
        rec["clear_final_mm"] = rnd(min(float(d_.min()), CAP_MM), 1)
        rec["hit_final"] = by[int(np.argmin(d_))] if float(d_.min()) < CAP_MM else None
        # how many of the 9 rays are blocked inside the first 40 mm (partly open access)
        rec["rays_open_final"] = int(sum(1 for x in d_ if x >= DRIVER_MM))


def asmodelled_overlaps(eng):
    """Pairwise overlap volume at the CAD closed pose (jaw angle 0)."""
    names = sorted(eng.base)
    out = []
    for n1, n2 in itertools.combinations(names, 2):
        v = eng.overlap(n1, n2, 0.0)
        if v > 0.3:
            out.append((n1, n2, v))
    return out


def pad_check_closed(eng, steps):
    """Would the nail reach finger A with the jaw closed and the B stack in place? (justifies the open jaw)"""
    st = next(s for s in steps if s["id"] == "s31")
    installed = ["housing", "front_plate", "wrist_mount", "knuckle_a", "knuckle_b", "finger_a", "finger_b",
                 "fsr_backing_b", "fsr_sensor_b", "fsr_puck_b"]
    d = np.array([-1.0, 0, 0])
    hits = {}
    for k in range(int(round(10 / SAMPLE_MM)), 0, -1):
        dd = k * SAMPLE_MM
        for o in installed:
            if eng.overlap("nail_a", o, 0.0, -d * dd) > COLLIDE_MM3:
                hits[o] = max(hits.get(o, 0), dd)
    return hits


def jaw_gap_open(eng, theta=20.0):
    """Distance between the nail face and the puck face at theta (mid-height of the pads)."""
    nail = eng.mesh("nail_a", theta)
    puck = eng.mesh("fsr_puck_b", theta)
    return nail, puck


# ------------------------------------------------------------------ assemble the output
def order_of(step_id):
    return int(step_id[1:])


def main():
    P, PJ, meshes, comps, glb = load_cad()
    items = name_items(identify_items(PJ, comps, glb))
    assert len(items) == 49, len(items)
    eng, steps, findings, tool_access, sweep_log, placed_step, path_hits = run(P, meshes, items)
    final_service_access(eng, items, tool_access)
    ov = asmodelled_overlaps(eng)
    closed_hit = pad_check_closed(eng, steps)

    # ---- static facts used by the findings
    s, k = P["servo"], P["knuckle"]
    by_id = {i["id"]: i for i in items}
    mid_back_z = -P["housing"]["plate"]
    tmin = P["motion"]["theta_min"] - 5
    tmax = P["motion"]["open_angle_max"] + 5
    step_deg = 360.0 / 25.0
    pin_len = float(by_id["pin_a"]["mesh"].extents[2])
    pin_top = float(by_id["pin_a"]["mesh"].bounds[1][2])
    pin_bot = float(by_id["pin_a"]["mesh"].bounds[0][2])
    dog_top = float(by_id["dog_screw_1"]["mesh"].bounds[1][2])
    locpin = by_id["locpin_1"]["mesh"]
    peg_len = float(by_id["peg_a_1"]["mesh"].extents[2])
    plate_len = float(by_id["plate_screw_1"]["mesh"].extents[2])

    # ---- per-item fit problems: final-pose overlap, insertion path hits, short driver (merged into one finding)
    issues = {}
    INTENDED = {  # (item kind, other part) pairs that overlap on purpose: press, thread or bond fits
        ("pin", "housing"), ("pin", "front_plate"), ("pin", "knuckle_a"), ("pin", "knuckle_b"),
        ("plate_screw", "housing"), ("ear_screw", "servo"), ("bush", "knuckle_a"), ("bush", "knuckle_b"),
        ("locpin", "wrist_mount"), ("locpin", "housing"), ("dog_screw", "horn"), ("limiter", "housing"),
        ("insert", "wrist_mount"), ("horn_screw", "horn"), ("horn_screw", "wrist_mount"),
        ("deck_screw", "wrist_mount"), ("deck_screw", "housing"), ("nut", "housing"),
        ("ear_screw", "housing"), ("washer", "housing"), ("m2", "finger_a"), ("m2", "finger_b"),
        ("peg", "finger_a"), ("peg", "finger_b"), ("peg", "knuckle_a"), ("peg", "knuckle_b"),
        ("m2", "knuckle_a"), ("m2", "knuckle_b")}
    for n1, n2, v in sorted(ov, key=lambda x: (x[0], x[1])):
        i1 = by_id.get(n1) or by_id.get(n2)
        other = n2 if n1 in by_id else n1
        if i1 is None and {n1, n2} == {"housing", "servo"}:
            findings.append({"step": "s13", "severity": "note",
                             "text": "The servo boss and the boss-web bore touch in the CAD.",
                             "evidence": f"{v:.1f} mm3 overlap: nominal 9.0 mm boss in the 9.0 mm bore, which is reamed H7 at step 2"})
            continue
        if i1 is None:
            findings.append({"step": "all", "severity": "blocker", "text": f"{n1} and {n2} overlap in the CAD.",
                             "evidence": f"{v:.1f} mm3"})
            continue
        if other in by_id:
            continue  # item against item: reported through its parent part
        if (i1["kind"], other) in INTENDED:
            continue
        issues.setdefault(i1["id"], {})["overlap"] = (other, v)
    for h in path_hits:
        if h["what"] in by_id:
            issues.setdefault(h["what"], {}).setdefault("path", []).append(h)
        else:
            findings.append({"step": h["step"], "severity": "blocker",
                             "text": f"{NAMES.get(h['what'], h['what'])} collides with {h['other'].replace('_', ' ')} on its way in.",
                             "evidence": f"first contact {h['d']:.1f} mm before the seat, overlap up to {h['vol']:.1f} mm3"})
    for r in tool_access:
        if not r["ok"]:
            issues.setdefault(r["item"], {})["driver"] = r
    for iid, iss in sorted(issues.items(), key=lambda kv: (order_of(placed_step[kv[0]]), kv[0])):
        it = by_id[iid]
        c = it["mesh"].bounds.mean(0)
        bits = []
        if "path" in iss:
            h = max(iss["path"], key=lambda q: q["d"])
            bits.append(f"on the way in it first touches the {h['other'].replace('_', ' ')} {h['d']:.1f} mm before the seat "
                        f"(overlap up to {max(q['vol'] for q in iss['path']):.1f} mm3 at x {h['lo'][0]:.1f} to {h['hi'][0]:.1f}, "
                        f"y {h['lo'][1]:.1f} to {h['hi'][1]:.1f}, z {h['lo'][2]:.1f} to {h['hi'][2]:.1f})")
        if "overlap" in iss:
            bits.append(f"seated, it overlaps the {iss['overlap'][0].replace('_', ' ')} by {iss['overlap'][1]:.1f} mm3")
        if "driver" in iss:
            d_ = iss["driver"]
            bits.append(f"the tool has {d_['clear_mm']} mm of free length against {d_['need_mm']:.0f} mm wanted (blocked by the {str(d_['hit']).replace('_', ' ')})")
        findings.append({"step": placed_step[iid], "severity": "blocker",
                         "text": f"{iid.replace('_', ' ').capitalize()} at x {c[0]:.1f}, y {c[1]:.1f}, z {c[2]:.1f} cannot be fitted as drawn.",
                         "evidence": "; ".join(bits)})
    plate_ov = [v for n1, n2, v in ov if (n1 in by_id and by_id[n1]['kind'] == 'plate_screw') or (n2 in by_id and by_id[n2]['kind'] == 'plate_screw')]
    ear_ov = [v for n1, n2, v in ov if (n1 in by_id and by_id[n1]['kind'] == 'ear_screw') or (n2 in by_id and by_id[n2]['kind'] == 'ear_screw')]

    findings.append({"step": "s16", "severity": "note",
                     "text": "Pin A can only go in after the servo is fitted and the horn centre screw is driven, because the 2.0 mm hex key uses the pin A bore.",
                     "evidence": f"pin {pin_len:.1f} mm long, z {pin_bot:.1f} to {pin_top:.1f}, bottom {pin_bot - mid_back_z:.1f} mm from the mid-plate back face z {mid_back_z}; pressed in from the front with retaining compound, with {k['pin_front_blind']:g} mm in the front-plate blind hole"})
    findings.append({"step": "s24", "severity": "note",
                     "text": "The front plate screws cut their own thread in a 2.5 mm pilot; stop at first snug (torque-limited driver, RISK F45).",
                     "evidence": (f"thread-forming overlap {min(plate_ov):.1f} mm3 per screw; " if plate_ov else "") + f"CAD length {plate_len:.1f} mm including a 1.8 mm head, so {plate_len-1.8:.1f} mm of shank against 16 mm listed"})
    if ear_ov:
        findings.append({"step": "s14", "severity": "note",
                         "text": "The servo model has no ear holes, so the ear screws overlap the servo ears in the CAD.",
                         "evidence": f"{min(ear_ov):.1f} mm3 overlap per screw (solid ears); the washer and nut sit on the frame front face in the end-wall notches"})
    findings.append({"step": "s12", "severity": "note",
                     "text": "The horn centre screw (M3x6 ISO 7380) is not in the CAD, so its path is not swept; its head must sit in the horn's counterbored centre, at most 0.4 mm proud, because the mid plate is 0.5 mm above the horn face.",
                     "evidence": f"it is driven with a 2.0 mm hex key through the pin A bore at step 13; the bore is {k['pin_d']:g} mm and pin A is not yet fitted"})
    findings.append({"step": "s15", "severity": "note",
                     "text": "The dog set screws are screwed in from the front through the mid-plate arc slots, before the gears go on.",
                     "evidence": f"set screw tops at z {dog_top:.1f}; the knuckle A dog slots ({k['dog_slot_w']} mm wide) take them at jaw angle 0"})
    findings.append({"step": "s7", "severity": "note",
                     "text": "The locating pins go into the spider holes from below (travel +Y), not along -Y.",
                     "evidence": f"the spider holes are blind and open on the underside, so a -Y path would run through solid plate; the pin is {float(locpin.extents[1]):.1f} mm long and stands 2.5 mm proud"})
    findings.append({"step": "s13", "severity": "risk",
                     "text": "The 25-tooth spline moves the horn in coarse steps, so the dog slots will not land exactly at the screw angle without driving the servo.",
                     "evidence": (f"spline step {step_deg:.1f} deg (up to {step_deg/2:.1f} deg off); the dog arc slots reach {tmin:.0f} to +{tmax:.0f} deg "
                                  f"against a jaw range of {P['motion']['theta_min']:.0f} to +{P['motion']['open_angle_max']:.0f} deg, a margin of only "
                                  f"{P['motion']['theta_min'] - tmin:.0f} deg at the closing end")})
    findings.append({"step": "s8", "severity": "risk",
                     "text": "The horn screw length is not confirmed against the real horn hole depth.",
                     "evidence": "the SO-101 horn is not modelled; measure the hole depth (DB M15) and apply wrist_mount.horn_screw_rule: M3x6 needs 3.75 mm or more, 3.5 to 3.7 is marginal, less means re-tap"})
    findings.append({"step": "s26", "severity": "note",
                     "text": "The finger pegs in the CAD are the hole tool, 1 mm longer each side than the 2 x 24 dowel the BOM lists (block width 24).",
                     "evidence": f"CAD peg {peg_len:.1f} mm long across both cheeks; a 2 x 24 dowel sits flush with both cheek faces; the M2x30 bolt covers 24 mm of block plus a 1.6 mm nut (RISK F48)"})
    findings.append({"step": "s6", "severity": "note",
                     "text": "The insert bore in the CAD equals the insert diameter, so the model shows no melt-in interference.",
                     "evidence": f"bore {P['housing']['insert_bore']} mm = insert outer diameter 4.2 mm, depth {P['housing']['insert_depth']} mm; printed holes run about 0.25 mm small, so test an insert in a coupon"})
    findings.append({"step": "s23", "severity": "note",
                     "text": "The front plate camera pad has two insert bores for the optional wrist camera.",
                     "evidence": "2 x 4.2 mm bore, 4.5 mm deep, 8.1 mm apart; BOM line 'Camera-pad inserts (optional)'. Leave them empty unless the wrist camera is built"})
    findings.append({"step": "s1", "severity": "note",
                     "text": "The housing and front plate are a matched pair.",
                     "evidence": "pin holes are line-reamed together; replacing either plate means reaming again"})
    if closed_hit:
        findings.append({"step": "s31", "severity": "risk",
                         "text": "The nail and the FSR stack can only be bonded with the jaw open; the jaw must be driven by the servo.",
                         "evidence": f"with the jaw closed the nail path along -X runs into {', '.join(sorted(NAMES[h] for h in closed_hit))}; the closed gap between the finger pads is {PJ['closed_gap_tpu']} mm and already holds the nail, the FSR stack and a 1.0 mm running gap"})
    # ---- tool access findings
    horn_blocked = [r for r in tool_access if r["item"].startswith("horn_screw") and r["clear_final_mm"] < DRIVER_MM]
    if horn_blocked:
        open_ids = [r["item"] for r in tool_access if r["item"].startswith("horn_screw") and r["clear_final_mm"] >= DRIVER_MM]
        findings.append({"step": "s9", "severity": "risk",
                         "text": f"{'All 4' if len(horn_blocked) == 4 else str(len(horn_blocked)) + ' of the 4'} horn screws are trapped behind the deck once the housing is on, so removing the gripper from the arm means taking the housing off the wrist plate first.",
                         "evidence": f"driver clear {'/'.join(str(v) for v in sorted({r['clear_final_mm'] for r in horn_blocked}))} mm against {DRIVER_MM:.0f} mm wanted, first hit {sorted({r['hit_final'] for r in horn_blocked})[0].replace('_', ' ')}"
                                     + (f"; reachable: {', '.join(open_ids)}" if open_ids else "")})
    other_blocked = [r for r in tool_access if (not r["item"].startswith(("horn_screw", "insert"))) and r["clear_final_mm"] < DRIVER_MM
                     and r["ok"]]
    for r in other_blocked:
        findings.append({"step": r["step"], "severity": "risk",
                         "text": f"{r['item'].replace('_', ' ')} is hard to reach for service once the gripper is built.",
                         "evidence": f"clear {r['clear_final_mm']} mm along {r['axis']} (hit {r['hit_final']})"})

    # ---- fill the dynamic note of the deck screw step
    bad_deck = sorted(i for i in issues if i.startswith("deck_screw"))
    for st_ in steps:
        if st_["id"] == "s18":
            txt = ("As drawn, " + ", ".join(b_.replace("_", " ") for b_ in bad_deck) + " cannot be fitted straight from below; see the findings. "
                   if bad_deck else "All four deck screws have at least 40 mm of free driver length from below. ")
            st_["note"] = st_["note"].replace("DECKNOTE ", txt)

    # ---- final pose check
    placed = set(placed_step)
    expect = set(PART_KEYS) | {i["id"] for i in items}
    final_ok = placed == expect
    assert final_ok, (sorted(expect - placed), sorted(placed - expect))
    moved_last = {}
    for st in steps:
        for m in st["moves"]:
            moved_last[m["what"]] = st["id"]

    # ---- serialise
    order = {st["id"]: n for n, st in enumerate(steps)}
    findings.sort(key=lambda f: (order.get(f["step"], 99), {"blocker": 0, "risk": 1, "note": 2}[f["severity"]], f["text"]))
    tool_access.sort(key=lambda r: (order[r["step"]], r["item"]))
    out_subs = []
    for sid, name, off in SUBS:
        d = {"id": sid, "name": name, "steps": [s["id"] for s in steps if s["sub"] == sid]}
        if off:
            d["bench_offset"] = off
        out_subs.append(d)
    out_steps = []
    bench_names = {n_ for st in steps if st.get("bench") for n_ in st["parts"] + st["items"]}
    joins = {st["id"] for st in steps if not st.get("bench") and any(m["what"] in bench_names for m in st["moves"])}
    for st in steps:
        d = dict(st)
        if st["id"] in joins:
            d["join"] = True
        d["moves"] = [{**m, "dir": rnd(list(m["dir"]), 4), "dist": rnd(m["dist"], 1)} for m in st["moves"]]
        d["theta_deg"] = rnd(st["theta_deg"], 1)
        out_steps.append(d)
    plan = {
        "frame": "G, mm",
        "note": "Steps run in order. A step with bench true builds a sub-assembly displaced by the sub-assembly bench_offset; the first later step that moves those parts by dir x dist joins them into the gripper. moves also lists parts and items carried in a join. theta_deg poses the jaw for the whole step (finger A turns -theta about pivot A, finger B +theta about pivot B). Every move ends at the CAD position, so after the last step each part is at its CAD pose. Torques are assumed.",
        "subassemblies": out_subs,
        "steps": out_steps,
        "fastener_items": [item_record(i) for i in items],
        "findings": findings,
        "sweeps": [{"step": x["step"], "what": x["what"], "samples": x["samples"], "collisions": x["collisions"]} for x in sweep_log],
        "tool_access": [{k_: v for k_, v in r.items()} for r in tool_access],
        "summary": {
            "sweep_step_mm": SAMPLE_MM, "collision_mm3": COLLIDE_MM3, "driver_need_mm": DRIVER_MM,
            "final_pose_equals_cad": bool(final_ok),
            "parts_placed": sorted(placed & set(PART_KEYS)), "items_placed": len(placed & {i['id'] for i in items}),
            "sweeps_run": len(sweep_log), "sweeps_with_collisions": sum(1 for s_ in sweep_log if s_["collisions"]),
        },
    }
    plan = json.loads(json.dumps(plan, default=lambda o: rnd(o)))
    (HERE / "steps.json").write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (HERE / "ASSEMBLY.md").write_text(write_md(plan, P), encoding="utf-8", newline="\n")
    print(f"steps {len(steps)}  items {len(items)}  findings {len(findings)}  sweeps {len(sweep_log)}")


# ------------------------------------------------------------------ markdown
NAMES = {"housing": "housing", "front_plate": "front plate", "wrist_mount": "wrist plate", "knuckle_a": "knuckle A",
         "knuckle_b": "knuckle B", "finger_a": "finger A", "finger_b": "finger B", "nail_a": "nail",
         "fsr_backing_b": "FSR backing", "fsr_sensor_b": "FSR 402 sensor", "fsr_puck_b": "FSR puck",
         "servo": "servo", "horn": "servo horn"}


def write_md(plan, P):
    steps = plan["steps"]
    num = {s["id"]: n + 1 for n, s in enumerate(steps)}
    L = []
    w = L.append
    nblock = sum(1 for f in plan["findings"] if f["severity"] == "blocker")
    w("# Cloth-feed gripper assembly (revision B)\n")
    w(f"**Answer: build it in {len(steps)} steps, in the order below.** "
      + ("Every insertion path and every screw driver path checks clear in the CAD." if not nblock else
         f"{nblock} fastener(s) fail a CAD check, in step(s) "
         + ", ".join(str(num[x]) for x in sorted({f['step'] for f in plan['findings'] if f['severity'] == 'blocker' and f['step'] in num}, key=order_of))
         + "; see the blockers under Findings.")
      + " Do the reaming and pressing on the bench first (steps 1 to 5), then the wrist plate, the servo and housing, the mount, the gears and the fingers.\n")
    w("This guide follows the revision B CAD in cad/gripper and the bought parts in cad/gripper/drawings/BOM.md. "
      "The data behind it is in cad/gripper/assembly/steps.json. "
      "Every torque below is an assumed starting value, not a measured one.\n")
    w("Directions use the CAD frame: X is the jaw closing direction, Y points up to the wrist and Z comes out of the gear plane. "
      "Jaw angle 0 is the closed pose; positive angles open the jaw.\n")
    w("## How the build goes\n")
    w("The wrist plate goes on the SO-101 roll horn first, and the housing comes up onto it afterwards. "
      "Reaming and pressing are done on the bench so the arm never takes a hammer blow. "
      f"Steps {num['s29']} to {num['s31']} need the servo powered to hold the jaw open.\n")
    for sub in plan["subassemblies"]:
        rng = [num[i] for i in sub["steps"]]
        label = f"step {rng[0]}" if len(rng) == 1 else f"steps {rng[0]} to {rng[-1]}"
        extra = " Built on the bench, then joined." if sub.get("bench_offset") else ""
        w(f"- {sub['name']} ({label}).{extra}")
    w("")
    w("## Tools and consumables\n")
    tools = []
    for s in steps:
        for t in s["tools"]:
            if t != "none" and t not in tools:
                tools.append(t)
    for t in sorted(tools):
        w(f"- {t}")
    w("")
    w("## Steps\n")
    subname = {s["id"]: s["name"] for s in plan["subassemblies"]}
    cur = None
    for s in steps:
        if s["sub"] != cur:
            cur = s["sub"]
            w(f"### {subname[cur]}\n")
        n = num[s["id"]]
        w(f"**Step {n}. {s['title']}**\n")
        pk = [NAMES[p] for p in s["parts"]]
        its = [i for i in s["items"]]
        if s.get("bench"):
            w("- Where: on the bench, away from the arm.")
        if s.get("join"):
            w("- Where: this joins the bench sub-assembly to the gripper on the arm.")
        if pk:
            w(f"- Parts: {', '.join(pk)}.")
        if its:
            w(f"- Fastener items: {', '.join(i.replace('_', ' ') for i in its)}.")
        w(f"- Fasteners: {s['fasteners']}.")
        w(f"- Tools: {', '.join(s['tools'])}.")
        if s.get("theta_deg"):
            w(f"- Jaw angle: {s['theta_deg']:g} degrees open.")
        w(f"- Check: {s['check']}")
        if s.get("note"):
            w(f"- Note: {s['note']}")
        w("")
    w("## Findings\n")
    w("Numbers come from the CAD meshes: every insertion path is sampled every 0.5 mm against the parts already installed, "
      "and a driver ray is cast from every screw head outward. A free driver length of about 40 mm is wanted for a screw.\n")
    for sev in ("blocker", "risk", "note"):
        group = [f for f in plan["findings"] if f["severity"] == sev]
        if not group:
            continue
        w(f"### {sev.capitalize()}s\n" if sev != "note" else "### Notes\n")
        for f in group:
            ref = f"Step {num[f['step']]}" if f["step"] in num else "Whole build"
            ev = f["evidence"][0].upper() + f["evidence"][1:]
            w(f"- {ref}. {f['text']} {ev}.")
        w("")
    w("## Driver access\n")
    w("The heat-set inserts are left out: the iron tip has 300 mm or more of free length on the bench.\n")
    w("| Fastener | Driver direction | Free length when fitted, mm | Free length when built, mm | Enough |")
    w("|---|---|---:|---:|---|")
    for r in plan["tool_access"]:
        if r["item"].startswith("insert"):
            continue
        ax = r["axis"]
        axn = ("+" if sum(ax) > 0 else "-") + "XYZ"[[abs(v) > 0.5 for v in ax].index(True)]
        fmt = lambda v: "300 or more" if v >= 300 else f"{v:g}"
        w(f"| {r['item'].replace('_', ' ')} | {axn} | {fmt(r['clear_mm'])} | {fmt(r['clear_final_mm'])} | {'yes' if r['ok'] else 'no'} |")
    w("")
    w("## What this plan does not settle\n")
    w("- Torques, thread-locker and the shim and pin press forces are assumed, not measured.")
    w("- The SO-101 horn is not modelled, so its hole depth and the horn screw engagement are untested.")
    w("- The horn centre screw and the nuts on the M2 bolts are not in the CAD.")
    w("- Servo wiring, the FSR tail route and the nut on each M2 bolt are not in the CAD.")
    w("- Gear mesh timing is checked only at jaw angle 0, where the CAD says the sectors clear.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
