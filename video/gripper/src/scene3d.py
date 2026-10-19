"""Blender (bpy) scene for the gripper video: real STL meshes, real jaw kinematics, PBR materials.

Run through render.py, not directly. Geometry and kinematics come from the repository:
- meshes: cad/gripper/out/*.stl, frame G (mm), every part at theta = 0 [cad/gripper/gripper_concept.py line 8]
- pivots: A (driven, servo) at (-a/2, 0), B (idler) at (+a/2, 0), a = 28.5 mm [cad/gripper/out/parts.json "a"]
- pose: A rotates -theta about +Z_G, B rotates +theta [gripper_concept.py pose(), lines 574-578]
- theta: + opens, 0 = rigid pads 1 mm apart [firmware/gripper/config.h JAW_* block]
"""
import math
import os

import bpy
from mathutils import Euler, Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(ROOT, "cad", "gripper", "out")
A_HALF = 28.5 / 2.0  # mm, parts.json "a"

SIDE = {
    "knuckle_a": "A", "finger_a": "A", "nail_a": "A", "fasteners_a": "A",
    "knuckle_b": "B", "finger_b": "B", "fsr_backing_b": "B", "fsr_sensor_b": "B", "fsr_puck_b": "B",
    "fasteners_b": "B",
}
PARTS = ["housing", "front_plate", "wrist_mount", "servo", "horn", "fasteners",
         "knuckle_a", "finger_a", "nail_a", "fasteners_a",
         "knuckle_b", "finger_b", "fsr_backing_b", "fsr_sensor_b", "fsr_puck_b", "fasteners_b"]
MATERIAL_OF = {
    "housing": "petg", "front_plate": "petg", "wrist_mount": "petg",
    "knuckle_a": "pa6cf", "knuckle_b": "pa6cf",
    "finger_a": "tpu", "finger_b": "tpu",
    "nail_a": "pla", "fsr_backing_b": "pla", "fsr_puck_b": "pla",
    "fsr_sensor_b": "fsr", "servo": "servo", "horn": "alu",
    "fasteners": "steel", "fasteners_a": "steel", "fasteners_b": "steel",
}
# Exploded-view offsets in frame G (mm), along the real assembly axes (README "Z stack", wrist on top).
EXPLODE = {
    "front_plate": (0, 0, 34), "fasteners": (0, 0, 16), "wrist_mount": (0, 30, 0), "horn": (0, 0, -16),
    "servo": (0, 6, -46), "housing": (0, 0, -6),
    "knuckle_a": (-6, 0, 12), "knuckle_b": (6, 0, 12), "fasteners_a": (-6, 0, 24), "fasteners_b": (6, 0, 24),
    "finger_a": (-10, -26, 12), "finger_b": (10, -26, 12), "nail_a": (-18, -26, 12),
    "fsr_backing_b": (18, -26, 12), "fsr_sensor_b": (24, -26, 12), "fsr_puck_b": (28, -26, 12),
}


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, 1.0)


def _principled(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    return m, nt, bsdf


def _layer_lines(nt, bsdf, axis, pitch_mm, strength):
    """Printed layer lines: a fine sine band along one object axis, fed to a bump node."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 2 * math.pi / (pitch_mm * 0.001)
    nt.links.new(sep.outputs[axis], mul.inputs[0])
    sin = nt.nodes.new("ShaderNodeMath")
    sin.operation = "SINE"
    nt.links.new(mul.outputs[0], sin.inputs[0])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.00004
    nt.links.new(sin.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def make_materials():
    mats = {}
    m, nt, b = _principled("PETG")  # printed PETG, charcoal, satin
    b.inputs["Base Color"].default_value = srgb("#30353a")
    b.inputs["Roughness"].default_value = 0.38
    _layer_lines(nt, b, "Y", 0.2, 0.25)
    mats["petg"] = m
    m, nt, b = _principled("PA6-CF")  # carbon-fibre nylon: matte near-black with a faint fibre speckle
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9000.0
    noise.inputs["Detail"].default_value = 2.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = srgb("#141518")
    ramp.color_ramp.elements[1].color = srgb("#2a2c30")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[1].position = 0.75
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.62
    _layer_lines(nt, b, "Y", 0.15, 0.15)
    mats["pa6cf"] = m
    m, nt, b = _principled("TPU95A")  # the one accent: signal orange TPU
    b.inputs["Base Color"].default_value = srgb("#e4561f")
    b.inputs["Roughness"].default_value = 0.55
    _layer_lines(nt, b, "Y", 0.15, 0.2)
    mats["tpu"] = m
    m, nt, b = _principled("PLA")
    b.inputs["Base Color"].default_value = srgb("#e9e9e4")
    b.inputs["Roughness"].default_value = 0.42
    mats["pla"] = m
    m, nt, b = _principled("FSR402")
    b.inputs["Base Color"].default_value = srgb("#3b2f26")
    b.inputs["Roughness"].default_value = 0.3
    mats["fsr"] = m
    m, nt, b = _principled("ServoCase")
    b.inputs["Base Color"].default_value = srgb("#111214")
    b.inputs["Roughness"].default_value = 0.45
    mats["servo"] = m
    m, nt, b = _principled("Aluminium")
    b.inputs["Base Color"].default_value = srgb("#c8ccd1")
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.28
    mats["alu"] = m
    m, nt, b = _principled("Steel")
    b.inputs["Base Color"].default_value = srgb("#b9bcc0")
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.22
    mats["steel"] = m
    m, nt, b = _principled("Cyc")  # studio sweep, cool light grey
    b.inputs["Base Color"].default_value = srgb("#d9dde1")
    b.inputs["Roughness"].default_value = 0.9
    mats["cyc"] = m
    m, nt, b = _principled("Cotton")  # one ply of woven cotton, indigo
    tc = nt.nodes.new("ShaderNodeTexCoord")
    w1 = nt.nodes.new("ShaderNodeTexWave")
    w1.wave_type = "BANDS"
    w1.bands_direction = "X"
    w1.inputs["Scale"].default_value = 140.0
    w2 = nt.nodes.new("ShaderNodeTexWave")
    w2.wave_type = "BANDS"
    w2.bands_direction = "Y"
    w2.inputs["Scale"].default_value = 140.0
    for w in (w1, w2):
        nt.links.new(tc.outputs["UV"], w.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMath")
    mix.operation = "MAXIMUM"
    nt.links.new(w1.outputs["Fac"], mix.inputs[0])
    nt.links.new(w2.outputs["Fac"], mix.inputs[1])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = srgb("#1c2540")
    ramp.color_ramp.elements[1].color = srgb("#2f3d63")
    nt.links.new(mix.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    b.inputs["Sheen Weight"].default_value = 0.25
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.0001
    nt.links.new(mix.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    mats["cotton"] = m
    return mats


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_part(name):
    path = os.path.join(OUT, name + ".stl")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    bpy.ops.wm.stl_import(filepath=path)
    ob = bpy.context.selected_objects[0]
    ob.name = name
    return ob


class Rig:
    """root (G -> Blender: Y_G up = +Z_B, Z_G = -Y_B, so the front plate faces the -Y camera side)."""

    def __init__(self, mats):
        self.root = bpy.data.objects.new("G", None)
        bpy.context.scene.collection.objects.link(self.root)
        self.set_tilt(0.0)
        self.piv = {}
        for side, x in (("A", -A_HALF), ("B", A_HALF)):
            e = bpy.data.objects.new("pivot_" + side, None)
            bpy.context.scene.collection.objects.link(e)
            e.parent = self.root
            e.location = (x, 0, 0)
            self.piv[side] = e
        self.obj = {}
        self.base = {}
        for n in PARTS:
            ob = import_part(n)
            side = SIDE.get(n)
            if side:
                px = -A_HALF if side == "A" else A_HALF
                ob.data.transform(Matrix.Translation((-px, 0, 0)))
                ob.parent = self.piv[side]
            else:
                ob.parent = self.root
            ob.matrix_parent_inverse = Matrix.Identity(4)
            ob.location = (0, 0, 0)
            ob.data.materials.append(mats[MATERIAL_OF[n]])
            for p in ob.data.polygons:
                p.use_smooth = False
            ob.data.set_sharp_from_angle(angle=math.radians(35))
            for p in ob.data.polygons:
                p.use_smooth = True
            self.obj[n] = ob
            self.base[n] = Vector((0, 0, 0))

    def set_theta(self, theta_deg):
        self.piv["A"].rotation_euler = Euler((0, 0, math.radians(-theta_deg)))
        self.piv["B"].rotation_euler = Euler((0, 0, math.radians(theta_deg)))

    def set_explode(self, s):
        """s = 0 assembled, 1 fully exploded; a float or a {part: s} dict; offsets in frame G."""
        for n, ob in self.obj.items():
            off = Vector(EXPLODE.get(n, (0, 0, 0)))
            ob.location = off * (s.get(n, 0.0) if isinstance(s, dict) else s)

    def set_tilt(self, tilt_deg, origin_world=(0, 0, 0)):
        """Tilt the whole gripper about the gear axis (A side lower for + tilt), then place it."""
        self.tilt = tilt_deg
        self.root.matrix_world = (Matrix.Translation(Vector(origin_world)) @ Matrix.Rotation(math.radians(90), 4, "X")
                                  @ Matrix.Rotation(math.radians(tilt_deg), 4, "Z") @ Matrix.Diagonal((0.001, 0.001, 0.001, 1)))

    def g2w(self, p, side=None, theta=0.0, explode=0.0, part=None):
        """Frame G point (mm), optionally on finger side A/B at jaw angle theta -> world (m)."""
        v = Vector(p)
        if part:
            v = v + Vector(EXPLODE.get(part, (0, 0, 0))) * explode
        if side:
            px = -A_HALF if side == "A" else A_HALF
            ang = math.radians(-theta if side == "A" else theta)
            v = Matrix.Translation((px, 0, 0)) @ Matrix.Rotation(ang, 4, "Z") @ Matrix.Translation((-px, 0, 0)) @ v
        return self.root.matrix_world @ v

    def key(self, frame):
        for e in self.piv.values():
            e.keyframe_insert("rotation_euler", frame=frame)
        for ob in self.obj.values():
            ob.keyframe_insert("location", frame=frame)

    def g_to_world(self, x, y, z):
        """Frame G (mm) point -> Blender world (m), untilted rig at the origin."""
        return Vector((x * 0.001, -z * 0.001, y * 0.001))

    def hide(self, names, hidden=True):
        for n in names:
            self.obj[n].hide_render = hidden


def studio(mats, floor_z=-0.09):
    sc = bpy.context.scene
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = srgb("#dfe3e7")
    bg.inputs["Strength"].default_value = 0.35
    # cyc sweep: floor plane bent up into a back wall
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0.0, floor_z))
    cyc = bpy.context.object
    cyc.name = "cyc"
    cyc.scale = (3.0, 1.6, 1)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=40)
    bpy.ops.object.mode_set(mode="OBJECT")
    for v in cyc.data.vertices:
        y = v.co.y * 1.6
        if y > 0.15:
            d = y - 0.15
            r = 0.25
            if d < r * math.pi / 2:
                a = d / r
                v.co.y = (0.15 + r * math.sin(a)) / 1.6
                v.co.z = r * (1 - math.cos(a))
            else:
                v.co.y = (0.15 + r) / 1.6
                v.co.z = r + (d - r * math.pi / 2)
    cyc.data.materials.append(mats["cyc"])
    for p in cyc.data.polygons:
        p.use_smooth = True
    lights = {}

    def area(name, loc, size, energy, color="#ffffff", target=(0, 0, 0)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size
        ld.energy = energy
        ld.color = srgb(color)[:3]
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        d = Vector(target) - Vector(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        lights[name] = lo
        return lo

    area("key", (-0.32, -0.30, 0.34), (0.35, 0.25), 9.0, "#fff6ee")
    area("fill", (0.38, -0.22, 0.05), (0.40, 0.40), 2.5, "#eef4ff")
    area("rim", (0.10, 0.30, 0.28), (0.30, 0.08), 8.0, "#ffffff")
    area("top", (0.0, 0.0, 0.45), (0.25, 0.25), 3.0, "#ffffff")
    return cyc, lights


def camera(name="cam", lens=85.0):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = 4.0
    cd.clip_start = 0.005
    co = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(co)
    bpy.context.scene.camera = co
    return co


def look_at(cam, eye, target, roll_deg=0.0):
    cam.location = Vector(eye)
    d = Vector(target) - Vector(eye)
    q = d.to_track_quat("-Z", "Y")
    cam.rotation_euler = q.to_euler()
    if roll_deg:
        cam.rotation_euler.rotate_axis("Z", math.radians(roll_deg))
    cam.data.dof.focus_distance = d.length


def use_device(want=None):
    """Pick the Cycles device. want (or env GRIPPER_DEVICE): auto (default), gpu, optix, cuda, cpu.
    auto/gpu take OptiX, else CUDA, when such a device is present; anything else, or no GPU, renders on CPU.
    Returns a label naming the device that will render."""
    want = (want or os.environ.get("GRIPPER_DEVICE") or "auto").lower()
    sc = bpy.context.scene
    sc.cycles.device = "CPU"
    if want != "cpu":
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in {"optix": ["OPTIX"], "cuda": ["CUDA"]}.get(want, ["OPTIX", "CUDA"]):
            try:
                prefs.compute_device_type = kind
            except TypeError:  # backend not compiled in
                continue
            prefs.refresh_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if not gpus:
                continue
            for d in prefs.devices:
                d.use = d.type == kind
            sc.cycles.device = "GPU"
            return f"GPU {kind} " + ", ".join(d.name for d in gpus)
    return f"CPU ({os.cpu_count()} logical cores)"


def render_settings(w, h, samples, fps=30, device=None, denoise="fast", motion_blur=False, threshold=0.03):
    """denoise: fast (the original 720p pass) or high (OIDN high quality, accurate prefilter)."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    label = use_device(device)
    print("DEVICE", label, flush=True)
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = threshold
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.denoising_use_gpu = sc.cycles.device == "GPU"
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.denoising_prefilter = "ACCURATE" if denoise == "high" else "FAST"
    sc.cycles.denoising_quality = "HIGH" if denoise == "high" else "FAST"
    sc.cycles.transmission_bounces = 4
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.render.use_motion_blur = motion_blur  # measured: doubles the frame time on 4 CPU cores
    sc.render.motion_blur_shutter = 0.5
    sc.render.motion_blur_position = "CENTER"  # blur straddles the frame, so track.json points stay centred
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.render.film_transparent = False
    sc.render.use_persistent_data = os.environ.get("GRIPPER_PERSISTENT", "1") == "1"  # keep BVH and kernels between frames
    return label
