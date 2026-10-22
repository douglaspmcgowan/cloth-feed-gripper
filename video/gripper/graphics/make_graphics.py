#!/usr/bin/env python
"""Render S7 (force loop) and S8 (state machine) motion-graphics PNG sequences.

Usage: make_graphics.py [all|S7|S8] [--layout land|sq] [--frames N] [--only-frame I]
Output: video/gripper/build/graphics/<shot>/<layout>/NNNN.png (30 fps)
"""
import argparse, json, math, os, sys
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import film_numbers as FN  # noqa: E402  force lines read from firmware/gripper/config.h
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FONT = os.path.join(HERE, "..", "assets", "fonts", "Archivo-Variable.ttf")
SIM = os.path.join(ROOT, "analysis/gripper/firmware_sim/results/fw_sim.json")
OUT = os.path.join(ROOT, "video/gripper/build/graphics")
FPS = 30
SS = 2  # supersample

BG, BG2 = (0xdf, 0xe3, 0xe7), (0xd3, 0xd8, 0xdd)
INK, SEC, LIGHT, ACC = (0x15, 0x18, 0x1b), (0x5b, 0x61, 0x68), (0xaa, 0xb1, 0xb8), (0xe4, 0x56, 0x1f)
FILL = (0xe9, 0xec, 0xef)
WHITE = (255, 255, 255)

# Firmware values and the separately authoritative R15 requirement (all read, not typed).
_hold, _trip, _requirement, _cap = FN.force_semantics()
REFS = [(_hold, f"{FN.g(_hold)} N hold"),
        (_trip, f"{FN.g(_trip)} N trip"),
        (_requirement, f"{FN.g(_requirement)} N requirement (R15)"),
        (_cap, f"{FN.g(_cap)} N conditional controller ceiling")]
T0, T1 = 0.3, 1.2          # S7 simulated-time window (s)
YMAX = 11.0

LAYOUTS = {"land": (1920, 1080), "sq": (1080, 1080)}


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, a, b): return clamp((t - a) / (b - a)) if b > a else float(t >= a)
def ease_io(x): x = clamp(x); return 4*x**3 if x < .5 else 1 - (-2*x + 2)**3 / 2
def ease_out(x): x = clamp(x); return 1.0 if x >= 1 else 1 - 2**(-10*x)
def mix(c1, c2, k): return tuple(int(round(a + (b - a)*k)) for a, b in zip(c1, c2))


@lru_cache(maxsize=None)
def font(weight, size):
    f = ImageFont.truetype(FONT, int(round(size*SS)))
    f.set_variation_by_axes([weight, 100])
    return f


_vig = {}
def background(w, h):
    k = (w, h)
    if k not in _vig:
        W, H = w*SS, h*SS
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((x - W/2)/(W/2))**2 + ((y - H/2)/(H/2))**2) / math.sqrt(2)
        r = np.clip(r, 0, 1)**2
        arr = np.zeros((H, W, 4), np.uint8)
        for i in range(3):
            arr[..., i] = (BG[i] + (BG2[i] - BG[i])*r).round().astype(np.uint8)
        arr[..., 3] = 255
        _vig[k] = Image.fromarray(arr, "RGBA")
    return _vig[k].copy()


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = background(w, h)
        self.d = ImageDraw.Draw(self.img, "RGBA")

    def px(self, v): return v*SS

    def text(self, xy, s, weight, size, color, a=1.0, dy=0.0, anchor="la"):
        if a <= 0.004: return
        self.d.text((xy[0]*SS, (xy[1] + dy)*SS), s, font=font(weight, size),
                    fill=color + (int(255*clamp(a)),), anchor=anchor)

    def line(self, pts, color, width, a=1.0):
        if a <= 0.004 or len(pts) < 2: return
        self.d.line([(x*SS, y*SS) for x, y in pts], fill=color + (int(255*clamp(a)),),
                    width=max(1, int(round(width*SS))), joint="curve")

    def dashed(self, x0, x1, y, color, width, a, dash=22, gap=14):
        x = x0
        while x < x1:
            self.line([(x, y), (min(x + dash, x1), y)], color, width, a)
            x += dash + gap

    def rrect(self, box, r, fill=None, outline=None, width=3, a=1.0, dy=0.0, dashed=False):
        if a <= 0.004: return
        x0, y0, x1, y1 = [v*SS for v in box]
        y0 += dy*SS; y1 += dy*SS
        al = int(255*clamp(a))
        self.d.rounded_rectangle((x0, y0, x1, y1), r*SS,
                                 fill=(fill + (al,)) if fill else None)
        if outline:
            oc = outline + (al,)
            if not dashed:
                self.d.rounded_rectangle((x0, y0, x1, y1), r*SS, outline=oc, width=int(width*SS))
            else:
                self._dashed_rrect(x0, y0, x1, y1, r*SS, oc, width*SS)

    def _dashed_rrect(self, x0, y0, x1, y1, r, col, w):
        # approximate with straight dashed edges + corner arcs
        dash, gap = 18*SS, 12*SS
        def seg(ax, ay, bx, by):
            L = math.hypot(bx-ax, by-ay); n = 0.0
            while n < L:
                m = min(n + dash, L)
                self.d.line([(ax+(bx-ax)*n/L, ay+(by-ay)*n/L), (ax+(bx-ax)*m/L, ay+(by-ay)*m/L)], fill=col, width=int(w))
                n += dash + gap
        seg(x0+r, y0, x1-r, y0); seg(x0+r, y1, x1-r, y1)
        seg(x0, y0+r, x0, y1-r); seg(x1, y0+r, x1, y1-r)
        for (cx, cy, st) in ((x0+r, y0+r, 180), (x1-r, y0+r, 270), (x1-r, y1-r, 0), (x0+r, y1-r, 90)):
            self.d.arc((cx-r, cy-r, cx+r, cy+r), st, st+90, fill=col, width=int(w))

    def glow(self, cx, cy, r, color, strength=1.0):
        R = int(r*SS*3)
        size = R*2
        m = Image.new("L", (size, size), 0)
        ImageDraw.Draw(m).ellipse((R - r*SS, R - r*SS, R + r*SS, R + r*SS), fill=int(255*clamp(strength)))
        m = m.filter(ImageFilter.GaussianBlur(r*SS*0.9))
        layer = Image.new("RGBA", (size, size), color + (0,))
        layer.putalpha(m)
        self.img.alpha_composite(layer, (int(cx*SS - R), int(cy*SS - R)))

    def dot(self, cx, cy, r, color, a=1.0):
        if a <= 0.004: return
        self.d.ellipse(((cx-r)*SS, (cy-r)*SS, (cx+r)*SS, (cy+r)*SS), fill=color + (int(255*clamp(a)),))

    def restore_background(self, box):
        """Clear chart strokes behind an annotation without adding a visible panel."""
        scaled = tuple(int(round(v*SS)) for v in box)
        clean = background(self.w, self.h)
        self.img.paste(clean.crop(scaled), scaled)

    def finish(self):
        return self.img.convert("RGB").resize((self.w, self.h), Image.LANCZOS)


def enter(t, start, dur=0.4):
    """fade + 12 px slide: returns (alpha, dy)"""
    e = ease_io(prog(t, start, start + dur))
    return e, 12*(1 - e)


# ------------------------------------------------------------------ S7
_sim = {}
def sim():
    if not _sim:
        s = json.load(open(SIM))["series"]["1.05 FEA E56+D7"]
        _sim["t"] = np.array(s["t"]); _sim["F"] = np.array(s["F"])
    return _sim["t"], _sim["F"]


def s7_geom(layout):
    if layout == "land":
        return dict(M=96, hs=72, ro=64, px0=190, px1=1824, py0=250, py1=860, lab=34, ax=30,
                    ytit=(96, 200), xtit=(190, 950), foot=(1824, 950), foota="ra", xtita="la", head_y=84)
    return dict(M=80, hs=60, ro=56, px0=150, px1=1000, py0=250, py1=800, lab=42, ax=36,
                ytit=(80, 196), xtit=(575, 868), foot=(80, 966), foota="la", xtita="ma", head_y=72)


def s7_reference_layout(layout):
    """Reference label positions and measured boxes; close 7.75/8 N labels are separated."""
    g = s7_geom(layout)
    px1, py0, py1 = g["px1"], g["py0"], g["py1"]
    y = lambda force: py1 - force/YMAX*(py1 - py0)
    offsets = (0, 30, -30, 0)
    entries = []
    for (force, label), offset in zip(REFS, offsets):
        label_y = y(force) + offset
        baseline = label_y - 14
        box = font(700, g["lab"]).getbbox(label, anchor="rd")
        bounds = (px1 - 8 + box[0]/SS, baseline + box[1]/SS,
                  px1 - 8 + box[2]/SS, baseline + box[3]/SS)
        entries.append(dict(force=force, label=label, line_y=y(force), label_y=label_y,
                            bounds=bounds,
                            clearance=(bounds[0] - 10, bounds[1] - 8,
                                       px1 + 2, bounds[3] + 28)))
    return entries


def s7_frame(layout, i):
    w, h = LAYOUTS[layout]; g = s7_geom(layout); c = Canvas(w, h)
    t = i / FPS
    tt, FF = sim()
    px0, px1, py0, py1 = g["px0"], g["px1"], g["py0"], g["py1"]
    X = lambda ts: px0 + (ts - T0)/(T1 - T0)*(px1 - px0)
    Y = lambda f: py1 - f/YMAX*(py1 - py0)

    a, dy = enter(t, 0.0, 0.45)
    c.text((g["M"], g["head_y"]), "Grip force, simulated", 700, g["hs"], INK, a, dy)

    # axes (0 - 1.0 s)
    for k, f in enumerate(range(0, 11, 2)):
        a, dy = enter(t, 0.1 + 0.04*k, 0.4)
        c.line([(px0, Y(f) + dy), (px1, Y(f) + dy)], LIGHT, 2, a*(0.55 if f else 1.0))
        c.text((px0 - 16, Y(f)), str(f), 450, g["ax"], SEC, a, dy, "rm")
    a, dy = enter(t, 0.15, 0.4)
    c.text(g["ytit"], "Force (N)", 450, g["ax"], SEC, a, dy)
    nt = int(round((T1 - T0)*10))
    for k in range(nt + 1):
        ts = T0 + k*0.1
        a, dy = enter(t, 0.15 + 0.03*k, 0.4)
        c.line([(X(ts), py1), (X(ts), py1 + 10 + dy)], SEC, 2, a)
        c.text((X(ts), py1 + 14), f"{ts:.1f}", 450, g["ax"], SEC, a, dy, "ma")
    a, dy = enter(t, 0.5, 0.4)
    c.text(g["xtit"], "Simulated time, seconds", 450, g["ax"], SEC, a, dy, g["xtita"])
    c.line([(px0, py1), (px1, py1)], SEC, 3, enter(t, 0.1, 0.4)[0])
    c.line([(px0, py0), (px0, py1)], SEC, 3, enter(t, 0.1, 0.4)[0])

    # reference lines
    ref_layout = s7_reference_layout(layout)
    for k, ref in enumerate(ref_layout):
        f = ref["force"]
        p = ease_out(prog(t, 0.3 + 0.1*k, 1.0))
        c.dashed(px0, px0 + (px1 - px0)*p, Y(f), SEC, 3, 0.9)

    # trace: sim time follows shot time linearly, 1.0 - 5.0 s
    p = prog(t, 1.0, 5.0)
    ts = T0 + p*(T1 - T0)
    m = (tt >= T0) & (tt <= ts)
    xs = list(tt[m]); fs = list(FF[m])
    Fh = float(np.interp(ts, tt, FF))
    if p > 0:
        xs.append(ts); fs.append(Fh)
        pts = [(X(x), Y(f)) for x, f in zip(xs, fs)]
        if len(pts) == 1: pts = [pts[0], pts[0]]
        c.line(pts, ACC, 6, 1.0)
    # reference labels pop in as trace nears: 5 N when F > 2.5, then 8 N and 10 N follow
    t5 = None
    above = np.where(FF >= 2.5)[0]
    t5 = 1.0 + (float(tt[above[0]]) - T0)/(T1 - T0)*4.0
    for k, ref in enumerate(ref_layout):
        f, lab = ref["force"], ref["label"]
        ts0 = t5 + 0.45*k
        e = ease_out(prog(t, ts0, ts0 + 0.35))
        pop = 1 + 0.12*math.sin(math.pi*clamp((t - ts0)/0.35))*(1 if t > ts0 else 0)
        if e > 0:
            ly = ref["label_y"] - 14 + 10*(1 - e)
            label_size = g["lab"]*pop
            box = font(700, label_size).getbbox(lab, anchor="rd")
            clear = (px1 - 8 + box[0]/SS - 10, ly + box[1]/SS - 8,
                     px1 + 2, ly + box[3]/SS + 28)
            c.line([(clear[0] - 42, Y(f)), (clear[0] - 22, ly), (clear[0] - 8, ly)], SEC, 2, e)
            c.restore_background(clear)
            c.text((px1 - 8, ly), lab, 700, label_size, INK, e, 0, "rd")
    # head dot and readout
    if p > 0:
        breathe = 0.5 + 0.5*math.sin(2*math.pi*(t - 5.0)/2.0 - math.pi/2) if t > 5.0 else 1.0
        settle = ease_io(prog(t, 5.0, 5.8))
        gs = 0.75 - 0.2*settle*(1 - breathe)
        gr = 20 + 6*breathe*settle
        hx, hy = X(ts), Y(Fh)
        c.glow(hx, hy, gr, ACC, gs)
        c.dot(hx, hy, 15, BG)
        c.dot(hx, hy, 11, ACC)
    ra = enter(t, 0.8, 0.4)
    c.text((g["px1"] if layout == "land" else 1000, g["head_y"] + (4 if layout == "land" else 2)),
           f"{Fh if p > 0 else 0.0:.1f} N", 700, g["ro"], ACC, ra[0], ra[1], "ra")
    a, dy = enter(t, 0.6, 0.4)
    c.text(g["foot"], "Firmware simulation, not a bench test", 450, 30, SEC, a, dy, g["foota"])
    return c.finish()


# ------------------------------------------------------------------ S8
def s8_layout(layout):
    """returns node boxes (cx, cy, w, h), arrows [(src, dst, points)], text sizes"""
    if layout == "land":
        W, H, M = 1920, 1080, 96
        nw, nh = 300, 96
        cols = [M + nw/2 + k*(W - 2*M - nw)/3 for k in range(4)]
        ylead, y1, y2 = 400, 620, 840
        P = {"Boot": (cols[0], ylead), "Home": (cols[1], ylead), "Calibrate": (cols[2], ylead),
             "Fault": (cols[3], ylead),
             "Idle": (cols[0], y1), "Approach": (cols[1], y1), "Touchdown": (cols[2], y1), "Close": (cols[3], y1),
             "Hold": (cols[3], y2), "Feed": (cols[2], y2), "Release": (cols[1], y2), "Retract": (cols[0], y2)}
        sz = dict(hs=72, sub=44, node=38, hy=84, sy=186, M=M)
    else:
        W, H, M = 1080, 1080, 80
        nw, nh = 250, 88
        cols = [M + nw/2 + k*(W - 2*M - nw)/2 for k in range(3)]
        ylead, r0, r1, r2 = 360, 560, 730, 900
        P = {"Boot": (cols[0], ylead), "Home": (cols[1], ylead), "Calibrate": (cols[2], ylead),
             "Idle": (cols[0], r0), "Approach": (cols[1], r0), "Touchdown": (cols[2], r0),
             "Close": (cols[2], r1), "Hold": (cols[2], r2), "Feed": (cols[1], r2),
             "Release": (cols[0], r2), "Retract": (cols[0], r1), "Fault": (cols[1], r1)}
        sz = dict(hs=60, sub=40, node=36, hy=72, sy=156, M=M)
    pad = 14
    def edge(a, b):
        (x0, y0), (x1, y1) = P[a], P[b]
        if abs(y0 - y1) < 1:
            s = 1 if x1 > x0 else -1
            return [(x0 + s*(nw/2 + pad), y0), (x1 - s*(nw/2 + pad), y1)]
        s = 1 if y1 > y0 else -1
        return [(x0, y0 + s*(nh/2 + pad)), (x1, y1 - s*(nh/2 + pad))]
    A = {}
    for a, b in (("Boot", "Home"), ("Home", "Calibrate")):
        A[(a, b)] = edge(a, b)
    # Calibrate -> Idle elbow through the gap
    cx, cy = P["Calibrate"]; ix, iy = P["Idle"]
    ymid = (cy + nh/2 + iy - nh/2)/2
    A[("Calibrate", "Idle")] = [(cx, cy + nh/2 + pad), (cx, ymid), (ix, ymid), (ix, iy - nh/2 - pad)]
    ring = ["Idle", "Approach", "Touchdown", "Close", "Hold", "Feed", "Release", "Retract", "Idle"]
    for a, b in zip(ring[:-1], ring[1:]):
        A[(a, b)] = edge(a, b)
    return W, H, nw, nh, P, A, ring, sz


def path_len(pts): return sum(math.hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(pts[:-1], pts[1:]))


def path_part(pts, p):
    """sub-polyline from start up to fraction p; returns (points, head_direction)"""
    L = path_len(pts)*clamp(p); out = [pts[0]]; acc = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        sl = math.hypot(b[0]-a[0], b[1]-a[1])
        if acc + sl >= L:
            k = (L - acc)/sl if sl else 0
            out.append((a[0] + (b[0]-a[0])*k, a[1] + (b[1]-a[1])*k)); return out
        out.append(b); acc += sl
    return out


def head(c, pts, color, a, size=13):
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    ang = math.atan2(y1 - y0, x1 - x0)
    tri = [(x1, y1), (x1 - size*1.8*math.cos(ang) + size*math.sin(ang), y1 - size*1.8*math.sin(ang) - size*math.cos(ang)),
           (x1 - size*1.8*math.cos(ang) - size*math.sin(ang), y1 - size*1.8*math.sin(ang) + size*math.cos(ang))]
    c.d.polygon([(x*SS, y*SS) for x, y in tri], fill=color + (int(255*clamp(a)),))


def s8_frame(layout, i):
    W, H, nw, nh, P, A, ring, sz = s8_layout(layout)
    c = Canvas(W, H); t = i / FPS
    R = 22
    a, dy = enter(t, 0.0, 0.4)
    c.text((sz["M"], sz["hy"]), "12 states, event driven", 700, sz["hs"], INK, a, dy)
    a, dy = enter(t, 0.12, 0.4)
    c.text((sz["M"], sz["sy"]), "Every host check passes", 450, sz["sub"], SEC, a, dy)

    names = list(P)
    # lit schedule: node -> list of (start, end) active windows; visited start
    act = {n: [] for n in names}      # (t_on, t_off or None)
    flash = {"Boot": 0.10, "Home": 0.16, "Calibrate": 0.22}
    for n, s in flash.items(): act[n].append((s, s + 0.2))
    act["Idle"].append((0.34, 0.5))
    for k in range(8):
        T = 0.5 + 0.5*k
        nxt = ring[k + 1]
        act[nxt].append((T, T + 0.5 if k < 7 else None))
        if k < 7: pass
    # Idle stays lit until Approach at 0.5 handled by (0.34,0.5) window above
    # arrows: schedule start times
    arrow_t = {("Boot", "Home"): flash["Home"] - 0.04, ("Home", "Calibrate"): flash["Calibrate"] - 0.04,
               ("Calibrate", "Idle"): 0.30}
    for k in range(8): arrow_t[(ring[k], ring[k + 1])] = 0.5 + 0.5*k
    ring_arrow = set(arrow_t)

    # nodes + arrows fade in (staggered, done by ~0.4)
    order = {n: j for j, n in enumerate(["Boot", "Home", "Calibrate", "Idle", "Approach", "Touchdown", "Close",
                                          "Hold", "Feed", "Release", "Retract", "Fault"])}
    # arrows (grey base, accent progress)
    for key, pts in A.items():
        a0, dy = enter(t, 0.04 + 0.02*order[key[0]], 0.3)
        pp = [(x, y + dy) for x, y in pts]
        c.line(pp, LIGHT, 3, a0)
        head(c, pp, LIGHT, a0)
        T = arrow_t[key]; dur = 0.3 if T >= 0.5 else 0.12
        p = ease_io(prog(t, T, T + dur))
        if p > 0:
            seg = path_part(pp, p)
            recent = t < T + 0.5
            c.line(seg, ACC, 6 if recent else 3, 1.0)
            if p >= 0.98: head(c, pp, ACC, 1.0, 14)
            # pulse travelling along the lit arrow
            q = prog(t, T, T + dur)
            if 0 < q < 1:
                L = path_len(pp)*ease_io(q); acc = 0; px_ = pp[0]
                for aa, bb in zip(pp[:-1], pp[1:]):
                    sl = math.hypot(bb[0]-aa[0], bb[1]-aa[1])
                    if acc + sl >= L:
                        k2 = (L - acc)/sl; px_ = (aa[0] + (bb[0]-aa[0])*k2, aa[1] + (bb[1]-aa[1])*k2); break
                    acc += sl
                c.glow(px_[0], px_[1], 11, ACC, 0.9)
                c.dot(px_[0], px_[1], 9, ACC)

    for n in names:
        cx, cy = P[n]; box = (cx - nw/2, cy - nh/2, cx + nw/2, cy + nh/2)
        a0, dy = enter(t, 0.0 + 0.025*order[n], 0.3)
        if n == "Fault":
            c.rrect(box, R, fill=None, outline=LIGHT, width=3, a=a0*0.65, dy=dy, dashed=True)
            c.text((cx, cy), n, 600, sz["node"], LIGHT, a0*0.85, dy, "mm")
            continue
        # lit amount: smooth over 0.2 s at start, and out at end
        lit = 0.0; visited = 0.0
        for (s, e) in act[n]:
            on = ease_io(prog(t, s, s + 0.2))
            off = ease_io(prog(t, e, e + 0.2)) if e is not None else 0.0
            lit = max(lit, on*(1 - off))
            visited = max(visited, on)
        vis_only = clamp(visited - lit)
        fill = mix(FILL, ACC, lit)
        outline = mix(LIGHT, ACC, max(lit, visited))
        tcol = mix(SEC, WHITE, lit) if lit > vis_only else mix(SEC, INK, vis_only)
        if lit > 0.5: tcol = mix(SEC, WHITE, lit)
        c.rrect(box, R, fill=fill, outline=outline, width=3, a=a0, dy=dy)
        c.text((cx, cy), n, 700 if (lit > .5 or visited > .5) else 600, sz["node"], tcol, a0, dy, "mm")
    return c.finish()


# ------------------------------------------------------------------ driver
SHOTS = {"S7": (210, s7_frame), "S8": (180, s8_frame)}


def job(args):
    shot, layout, i = args
    d = os.path.join(OUT, shot, layout); os.makedirs(d, exist_ok=True)
    SHOTS[shot][1](layout, i).save(os.path.join(d, f"{i:04d}.png"), optimize=False, compress_level=3)
    return i


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shot", nargs="?", default="all", choices=["all", "S7", "S8"])
    ap.add_argument("--layout", choices=["land", "sq"])
    ap.add_argument("--frames", help="comma list of frame indices (default: all)")
    ap.add_argument("--only-frame", type=int, help="render one frame")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    a = ap.parse_args()
    shots = ["S7", "S8"] if a.shot == "all" else [a.shot]
    layouts = [a.layout] if a.layout else ["land", "sq"]
    work = []
    for s in shots:
        n = SHOTS[s][0]
        if a.only_frame is not None and a.frames:
            ap.error("--only-frame and --frames are mutually exclusive")
        idx = [a.only_frame] if a.only_frame is not None else ([int(x) for x in a.frames.split(",")] if a.frames else range(n))
        for l in layouts:
            work += [(s, l, i) for i in idx]
    with Pool(a.jobs) as p:
        for k, _ in enumerate(p.imap_unordered(job, work, chunksize=4)):
            if k % 100 == 0: print(f"{k}/{len(work)}", flush=True)
    print("done", len(work))


if __name__ == "__main__":
    main()
