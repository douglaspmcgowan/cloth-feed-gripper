"""Compositor: 3D frames + 2D graphics + type -> ffmpeg, landscape 1920x1080 and vertical 1080x1920.

    python compose.py [--layout land|vert|both] [--only S5] [--frames-out DIR] [--no-encode]

Reads build/frames3d/<shot>/ (native 1920x1080 Cycles renders, used 1:1), build/graphics/<shot>/,
build/audio/mix.wav; writes build/gripper_hype_1080p.mp4 and build/gripper_hype_vertical.mp4.
Every on-screen number is cited in STORYBOARD.md.
"""
import argparse
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import film_numbers as FN  # noqa: E402  on-screen numbers read from the CAD and firmware sources

VID = os.path.dirname(HERE)
BUILD = os.path.join(VID, "build")
FRAMES3D = os.environ.get("FRAMES3D", os.path.join(BUILD, "frames3d"))  # override for animatic previews
FONT = os.path.join(VID, "assets", "fonts", "Archivo-Variable.ttf")
FPS = 30
INK = (21, 24, 27)
INK2 = (91, 97, 104)
ACC = (228, 86, 31)
BG = (223, 227, 231)

# shot, start (s), duration (s), source
TIMELINE = [("S1", 0, 4, "3d"), ("S2", 4, 5, "3d"), ("S3", 9, 7, "3d"), ("S4", 16, 6, "3d"), ("S5", 22, 6, "3d"),
            ("S6", 28, 6, "3d"), ("S7", 34, 7, "gfx"), ("S8", 41, 6, "gfx"), ("S9", 47, 5, "3d"),
            ("S10", 52, 5, "plate"), ("S11", 57, 5, "3d")]
TOTAL = 62

_fonts = {}


def font(size, weight=450, width=100):
    k = (size, weight, width)
    if k not in _fonts:
        f = ImageFont.truetype(FONT, size)
        f.set_variation_by_axes([weight, width])
        _fonts[k] = f
    return _fonts[k]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def appear(t, t_in, t_out=None, dur=0.45):
    """(alpha, dy) for an element entering at t_in and leaving at t_out."""
    a = ease((t - t_in) / dur)
    dy = (1 - a) * 18
    if t_out is not None:
        a *= 1 - ease_io((t - t_out) / 0.3)
    return a, dy


def text(d, xy, s, size, weight=450, color=INK, alpha=1.0, anchor="ls", width=100):
    if alpha <= 0.003:
        return
    d.text(xy, s, font=font(size, weight, width), fill=color + (int(255 * alpha),), anchor=anchor)


# ------------------------------------------------------------------ sources
_track = {}


def track(shot):
    if shot not in _track:
        p = os.path.join(FRAMES3D, shot, "track.json")
        _track[shot] = json.load(open(p)) if os.path.exists(p) else {}
    return _track[shot]


def frame3d(shot, f):
    p = os.path.join(FRAMES3D, shot, f"{f:04d}.png")
    if not os.path.exists(p):  # preview renders may be sparse: use the nearest earlier frame
        g = f
        while g > 0 and not os.path.exists(p):
            g -= 1
            p = os.path.join(FRAMES3D, shot, f"{g:04d}.png")
    im = Image.open(p).convert("RGB")
    if im.size != (1920, 1080):  # production frames are native 1080p; only a preview may be scaled
        if "FRAMES3D" not in os.environ:
            raise SystemExit(f"{p} is {im.size[0]}x{im.size[1]}, not 1920x1080: re-render with src/render_3d.sh")
        im = im.resize((1920, 1080), Image.LANCZOS)
    return im


def gfx(shot, f, layout):
    sub = "land" if layout == "land" else "sq"
    return Image.open(os.path.join(BUILD, "graphics", shot, sub, f"{f:04d}.png")).convert("RGB")


_plate = {}


PLATE_V = (3413, 1920)  # S2 frame 149 rendered at the vertical cut's scale (1920 * 1920 // 1080 wide)


def plate(layout="land"):
    """Blurred hero plate for S10. Vertical uses its own 3413 x 1920 render so no 3D pixel is enlarged."""
    if layout not in _plate:
        if layout == "land":
            im, r = frame3d("S2", 149), 22
        else:
            p = os.path.join(FRAMES3D, "S10_plate", "0149.png")
            r = 22 * 1920 / 1080  # the same blur relative to the frame as the landscape plate
            if os.path.exists(p):
                im = Image.open(p).convert("RGB")
            elif "FRAMES3D" in os.environ:  # previews: no tall plate rendered
                im = frame3d("S2", 149).resize(PLATE_V, Image.LANCZOS)
            else:
                raise SystemExit(f"missing {p}: render it with src/render_3d.sh")
            if im.size != PLATE_V:
                raise SystemExit(f"{p} is {im.size}, expected {PLATE_V}")
        im = im.filter(ImageFilter.GaussianBlur(r))
        _plate[layout] = Image.blend(im, Image.new("RGB", im.size, BG), 0.35)
    return _plate[layout]


def pt(shot, f, name, layout):
    tr = track(shot).get(str(f))
    if not tr:
        return None
    x, y = tr["pts"][name]
    if layout == "land":
        return (x * 1920, y * 1080)
    return (x * 1920 - 420, y * 1080 + VERT_Y0)


VERT_X0 = {}  # landscape x where a shot's vertical square starts (subject off centre)
VERT_Y0 = 330  # the centre 1080 square of a landscape frame sits at y 330..1410 in the vertical frame


# ------------------------------------------------------------------ per-shot overlays
class Lay:
    """Text blocks: landscape bottom-left; vertical above / below the square."""

    def __init__(self, layout):
        self.v = layout == "vert"

    def head(self, d, t, lines, t0, t_out=None, size=None, gap=None, first_acc=False, n_main=1):
        size = size or (84 if not self.v else 76)
        gap = gap or int(size * 1.15)
        x = 96 if not self.v else 72
        y = (1080 - 96 - gap * (len(lines) - 1)) if not self.v else 1560
        for i, s in enumerate(lines):
            sz = size if i < n_main else int(size * 0.62)
            a, dy = appear(t, t0 + i * 0.35 if isinstance(t0, (int, float)) else t0[i], t_out)
            col = ACC if (first_acc and i == 0) else (INK if i < n_main else INK2)
            text(d, (x, y + i * gap + dy), s, sz, 700 if i < n_main else 450, col, a)


def leader(d, p, q, a):
    if a <= 0:
        return
    d.line([p, q], fill=INK + (int(200 * a),), width=2)
    r = 6
    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=ACC + (int(255 * a),))


def ov_S1(d, t, f, L, layout):
    L.head(d, t, ["One ply of cotton.", "0.3 mm thick."], (0.5, 1.7), 3.6)


def ov_S2(d, t, f, L, layout):
    a, dy = appear(t, 0.9, None, 0.6)
    a2, dy2 = appear(t, 1.5, None)
    if layout == "land":  # left column, clear of the model (x 640..1260)
        text(d, (72, 480 + dy), "Cloth-feed", 96, 760, INK, a)
        text(d, (72, 584 + dy), "gripper", 96, 760, INK, a)
        text(d, (76, 656 + dy2), "ME102B, UC Berkeley", 40, 450, INK2, a2)
    else:
        text(d, (72, 1580 + dy), "Cloth-feed gripper", 104, 760, INK, a)
        text(d, (76, 1650 + dy2), "ME102B, UC Berkeley", 46, 450, INK2, a2)
    if t > 4.65:  # leave clean for the cut
        pass


CALLOUTS = [("servo", FN.servo_label(), (-240, 40), 0.8), ("housing", "PETG housing", (-260, -70), 1.4),
            ("knuckle_a", "PA6-CF sector gears", (-300, 40), 2.0), ("finger_b", "TPU 95A Fin Ray fingers", (190, 30), 2.6)]
CALLOUT_OUT = 4.3  # before the front plate closes over the gears (DELAY front_plate 4.1 + 0.3 in shots3d.py)


def ov_S3(d, t, f, L, layout):
    if layout == "land":
        for name, label, off, t0 in CALLOUTS:
            p = pt("S3", f, name, layout)
            if not p:
                continue
            a, _ = appear(t, t0, CALLOUT_OUT, 0.4)
            q = (p[0] + off[0], p[1] + off[1])
            leader(d, p, q, a)
            anchor = "rs" if off[0] < 0 else "ls"
            qx = q[0] - 10 if off[0] < 0 else q[0] + 10
            text(d, (qx, q[1] + 14), label, 40, 600, INK, a, anchor)
    else:
        for i, (name, label, off, t0) in enumerate(sorted(CALLOUTS, key=lambda c: c[3])):
            a, dy = appear(t, t0, 6.6)
            text(d, (72, 1540 + i * 70 + dy), label, 52, 600, INK, a)
            d.rectangle([40, 1540 + i * 70 - 22 + dy, 56, 1540 + i * 70 - 17 + dy], fill=ACC + (int(255 * a),))


def ov_S4(d, t, f, L, layout):
    L.head(d, t, ["1:1 sector pair", "m 1.5, z 19, 25°", "28.5 mm centres"], (0.5, 1.0, 1.4), 5.6)


def ov_S5(d, t, f, L, layout):
    tr = track("S5").get(str(f))
    if not tr:
        return
    th = tr["theta"]
    a0, _ = appear(t, 0.2, 5.6)
    # finger lines and swept arcs, pinned to the tracked pivots and tips
    for side in ("a", "b"):
        pv, tp = pt("S5", f, "pivot_" + side, layout), pt("S5", f, "tip_" + side, layout)
        tp0 = pt("S5", 0, "tip_" + side, layout)
        if not (pv and tp and tp0):
            continue
        r = math.dist(pv, tp) * 0.62
        ang = math.degrees(math.atan2(tp[1] - pv[1], tp[0] - pv[0]))
        ang0 = math.degrees(math.atan2(tp0[1] - pv[1], tp0[0] - pv[0]))
        lo, hi = min(ang, ang0), max(ang, ang0)
        d.line([pv, tp], fill=ACC + (int(220 * a0),), width=3)
        if hi - lo > 0.2:
            d.arc([pv[0] - r, pv[1] - r, pv[0] + r, pv[1] + r], lo, hi, fill=ACC + (int(255 * a0),), width=5)
        d.ellipse([pv[0] - 7, pv[1] - 7, pv[0] + 7, pv[1] + 7], fill=ACC + (int(255 * a0),))
    # live readout (the rendered jaw angle)
    sign = "+" if th > 0.05 else ("−" if th < -0.05 else "")
    x = 1500 if layout == "land" else 72
    y = 300 if layout == "land" else 170
    text(d, (x, y), "Jaw angle", 40, 450, INK2, a0)
    text(d, (x, y + 96), f"{sign}{abs(th):.1f}°", 104, 700, ACC, a0)
    L.head(d, t, [f"{FN.g(FN.lever_mm())} mm lever to the pad", f"Firmware floor {FN.jaw_floor_deg():g}°".replace("-", "−")], (1.0, 3.2), 5.6, size=64)


def ov_S6(d, t, f, L, layout):
    if layout == "land":
        L.head(d, t, ["Nail on finger A slides under the edge", "Force sensor behind finger B"], (0.6, 2.6), 5.6, size=60)
    else:
        L.head(d, t, ["Nail on finger A", "slides under the edge", "Force sensor behind finger B"], (0.6, 0.6, 2.6), 5.6, size=72, n_main=2)


def ov_S9(d, t, f, L, layout):
    a, _ = appear(t, 0.2, None, 0.4)
    if layout == "land":
        box = (60, 60, 1860, 1020)
    else:
        box = (36, VERT_Y0 + 36, 1044, VERT_Y0 + 1044)
    x0, y0, x1, y1 = box
    k = 60
    for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(cx, cy + sy * k), (cx, cy), (cx + sx * k, cy)], fill=INK + (int(230 * a),), width=4)
    text(d, (x0 + 24, y0 + 54), "Pi Camera 3, 2304 × 1296", 34, 500, INK, a)
    # detected seam edge: the cloth's free edge, drawn on progressively
    tr = track("S9").get(str(f))
    if tr and "edge" in tr["pts"]:
        pts = [(x * 1920, y * 1080) if layout == "land" else (x * 1920 - 420, y * 1080 + VERT_Y0) for x, y in tr["pts"]["edge"]]
        n = max(2, int(len(pts) * ease_io((t - 0.8) / 2.0)))
        if t > 0.8:
            if layout == "vert":  # keep the overlay inside the camera frame
                pts = [p for p in pts if VERT_Y0 + 40 < p[1] < VERT_Y0 + 1040]
                n = max(2, int(len(pts) * ease_io((t - 0.8) / 2.0)))
            if len(pts) >= 2:
                d.line(pts[:n], fill=ACC + (255,), width=6, joint="curve")
    if layout == "land":  # top left, inside the camera frame and clear of the cloth
        for i, (s_, t0) in enumerate((("Fixed Pi Camera 3", 1.2), ("on the seam edge", 1.2), ("Planned: 5.5 px/mm", 2.2))):
            a_, dy = appear(t, t0, 4.6)
            text(d, (96, 200 + i * 68 + dy), s_, 60 if i < 2 else 40, 700 if i < 2 else 450, INK if i < 2 else INK2, a_)
    else:
        L.head(d, t, ["Fixed Pi Camera 3", "Planned: 5.5 px/mm"], (1.2, 2.2), 4.6, size=68)


# rev B.1: mass fitcheck.json, price actuators.csv (servo in parts.json), pair mass gears.json cad_rev_b
NUMS = [(FN.total_mass_g(), "{:.1f} g", "with cloth, over budget"), (FN.servo_price_usd(), "${:.2f}", "servo"),
        (FN.gear_pair_g(), "{:.2f} g", "gear pair")]


def ov_S10(d, t, f, L, layout):
    for i, (v, fmt, label) in enumerate(NUMS):
        t0 = 0.15 + i * 1.0
        a, dy = appear(t, t0, 4.6, 0.5)
        val = v * ease_io((t - t0) / 0.8)
        s = fmt.format(val)
        if layout == "land":
            x, y = 96 + i * 600, 600
            text(d, (x, y + dy), s, 132, 760, ACC if i == 2 else INK, a)
            text(d, (x + 4, y + 70 + dy), label, 48, 450, INK2, a)
        else:
            x, y = 72, 640 + i * 380
            text(d, (x, y + dy), s, 150, 760, ACC if i == 2 else INK, a)
            text(d, (x + 4, y + 80 + dy), label, 54, 450, INK2, a)


def ov_S11(d, t, f, L, layout, base):
    L.head(d, t, ["Designed and simulated.", "Bench tests next."], (0.2, 0.8), 1.75, size=76)


def end_card(img, t, layout):
    """Fades a flat card over S11 from 1.95 s, then the title."""
    a = ease_io((t - 1.95) / 0.5)
    if a <= 0:
        return img
    img = Image.blend(img, Image.new("RGB", img.size, BG), 0.86 * a)
    d = ImageDraw.Draw(img, "RGBA")
    W, H = img.size
    a2, dy = appear(t, 2.25, None, 0.6)
    size = 132 if layout == "land" else 112
    text(d, (W / 2, H / 2 + dy), "Cloth-feed gripper", size, 760, INK, a2, "ms")
    a3, dy = appear(t, 2.6, None)
    text(d, (W / 2, H / 2 + 80 + dy), "ME102B, UC Berkeley", 50, 450, INK2, a3, "ms")
    bw = 120 * ease_io((t - 2.45) / 0.6)
    d.rectangle([W / 2 - bw / 2, H / 2 + 120, W / 2 + bw / 2, H / 2 + 126], fill=ACC + (int(255 * a2),))
    return img


OV = {"S1": ov_S1, "S2": ov_S2, "S3": ov_S3, "S4": ov_S4, "S5": ov_S5, "S6": ov_S6, "S9": ov_S9, "S10": ov_S10}


# ------------------------------------------------------------------ frame assembly
def base_for(shot, src, f, layout):
    if src == "gfx":
        g = gfx(shot, min(f + 33, 209) if shot == "S7" else f, layout)
        if layout == "land":
            return g
        canvas = Image.new("RGB", (1080, 1920), BG)
        canvas.paste(g, (0, VERT_Y0))
        return canvas
    im = plate(layout) if src == "plate" else frame3d(shot, f)
    if layout == "land":
        return im.copy()
    if src == "plate":
        return im.crop((1166, 0, 1166 + 1080, 1920))
    canvas = Image.new("RGB", (1080, 1920), BG)
    x0 = VERT_X0.get(shot, 420)
    sq = im.crop((x0, 0, x0 + 1080, 1080))
    canvas.paste(sq, (0, VERT_Y0))
    # soft fade of the square's top and bottom edges into the canvas
    fade = Image.new("L", (1080, 1080), 255)
    fd = ImageDraw.Draw(fade)
    for i in range(80):
        v = int(255 * i / 80)
        fd.line([(0, i), (1080, i)], fill=v)
        fd.line([(0, 1079 - i), (1080, 1079 - i)], fill=v)
    canvas.paste(Image.new("RGB", (1080, 1080), BG), (0, VERT_Y0), Image.eval(fade, lambda x: 255 - x))
    return canvas


_scrim = {}


def scrim():
    """Soft light wash behind the landscape bottom-left type block, so ink stays readable over the model."""
    if "s" not in _scrim:
        m = Image.new("L", (1920, 1080), 0)
        px = m.load()
        for y in range(640, 1080):
            vy = clamp((y - 640) / 300)
            for x in range(0, 1500, 2):
                v = int(205 * vy * clamp((1500 - x) / 700))
                px[x, y] = v
                px[x + 1, y] = v
        m = m.filter(ImageFilter.GaussianBlur(30))
        s = Image.new("RGBA", (1920, 1080), BG + (0,))
        s.putalpha(m)
        _scrim["s"] = s
    return _scrim["s"]


def render_frame(n, layout):
    t_abs = n / FPS
    for shot, start, dur, src in TIMELINE:
        if start <= t_abs < start + dur:
            break
    f = n - start * FPS
    t = f / FPS
    img = base_for(shot, src, f, layout)
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    L = Lay(layout)
    if shot == "S11":
        ov_S11(d, t, f, L, layout, img)
    elif shot in OV:
        OV[shot](d, t, f, L, layout)
    if layout == "land" and shot not in ("S7", "S8", "S10"):
        img = Image.alpha_composite(img.convert("RGBA"), scrim())
    img = Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")
    if shot == "S11":
        img = end_card(img, t, layout)
    # global fade in from black and out at the very end
    k = min(clamp(t_abs / 0.5), clamp((TOTAL - t_abs) / 0.7))
    if k < 1:
        img = Image.blend(Image.new("RGB", img.size, (0, 0, 0)), img, ease_io(k))
    return img


def encode(layout, frames_out=None, only=None, encode_video=True):
    size = (1920, 1080) if layout == "land" else (1080, 1920)
    out = os.path.join(BUILD, ("gripper_hype_1080p.mp4" if layout == "land" else "gripper_hype_vertical.mp4")
                       if "FRAMES3D" not in os.environ else f"animatic_{layout}.mp4")
    rng = range(TOTAL * FPS)
    if only:
        sh = [s for s in TIMELINE if s[0] == only][0]
        rng = range(sh[1] * FPS, (sh[1] + sh[2]) * FPS)
    proc = None
    if encode_video and not only:
        audio = os.path.join(BUILD, "audio", "mix.wav")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
               "-r", str(FPS), "-i", "-"]
        if os.path.exists(audio):
            cmd += ["-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p", "-profile:v", "high",
                "-movflags", "+faststart", out]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in rng:
        img = render_frame(n, layout)
        if frames_out and n % (FPS * 2) == 0:
            os.makedirs(frames_out, exist_ok=True)
            img.save(os.path.join(frames_out, f"{layout}_{n // FPS:02d}s.jpg"), quality=85)
        if proc:
            proc.stdin.write(img.tobytes())
    if proc:
        proc.stdin.close()
        proc.wait()
        print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default="both", choices=["land", "vert", "both"])
    ap.add_argument("--only")
    ap.add_argument("--frames-out")
    ap.add_argument("--no-encode", action="store_true")
    a = ap.parse_args()
    for lay in (["land", "vert"] if a.layout == "both" else [a.layout]):
        encode(lay, a.frames_out, a.only, not a.no_encode)


if __name__ == "__main__":
    main()
