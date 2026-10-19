#!/usr/bin/env python3
"""Procedural soundtrack for the 62 s gripper film. numpy + stdlib only. Deterministic."""
import json, os, wave
import numpy as np

SR = 48000
DUR = 62.0
N = int(SR * DUR)
BEAT, BAR = 0.5, 2.0
rng = np.random.default_rng(20261010)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "build", "audio"))

music_dry = np.zeros((2, N)); music_wet = np.zeros((2, N)); sfx = np.zeros((2, N))
events = []

def log(kind, t, **kw):
    events.append(dict(type=kind, t=round(float(t), 4), **kw))

def add(buf, x, t, pan=0.0, gain=1.0):
    i = int(round(t * SR))
    if i >= N or i + len(x) <= 0: return
    a = max(0, -i); b = min(len(x), N - i)
    ang = (pan + 1) * np.pi / 4
    buf[0, i + a:i + b] += x[a:b] * gain * np.cos(ang)
    buf[1, i + a:i + b] += x[a:b] * gain * np.sin(ang)

def tt(d): return np.arange(int(d * SR)) / SR
def midi(m): return 440.0 * 2 ** ((np.asarray(m, float) - 69) / 12)

def fade(x, a=0.005, r=0.01):
    x = x.copy(); na = min(len(x) // 2, int(a * SR)); nr = min(len(x) // 2, int(r * SR))
    if na: x[:na] *= np.linspace(0, 1, na)
    if nr: x[-nr:] *= np.linspace(1, 0, nr)
    return x

def lp1(x, fc):
    """one-pole lowpass; fc scalar or array (Hz)."""
    fc = np.broadcast_to(np.asarray(fc, float), x.shape)
    a = 1 - np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)):
        s += a[i] * (x[i] - s); y[i] = s
    return y

def hp1(x, fc): return x - lp1(x, fc)

def biquad_bp(x, f0, q):
    w = 2 * np.pi * f0 / SR; al = np.sin(w) / (2 * q)
    b0, b2 = al, -al; a0 = 1 + al; a1 = -2 * np.cos(w); a2 = 1 - al
    b0 /= a0; b2 /= a0; a1 /= a0; a2 /= a0
    y = np.zeros_like(x); x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        v = b0 * x[i] + b2 * x2 - a1 * y1 - a2 * y2
        x2 = x1; x1 = x[i]; y2 = y1; y1 = v; y[i] = v
    return y

def reverb(x, seed_off, rt=2.6):
    """Schroeder: 4 combs + 2 allpass, block-vectorised."""
    combs = [1557, 1617, 1491, 1422]; aps = [225, 556]
    y = np.zeros_like(x)
    for d in combs:
        d += seed_off
        g = 10 ** (-3 * d / SR / rt)
        c = x.copy()
        for s in range(d, len(x), d):
            e = min(s + d, len(x))
            c[s:e] += g * c[s - d:e - d]
        # damp the comb output
        y += c * 0.25
    y = lp1(y[::1], 5000.0) if len(y) < 0 else y
    for d in aps:
        d += seed_off // 2; g = 0.5
        o = np.zeros_like(y)
        for s in range(0, len(y), d):
            e = min(s + d, len(y))
            xd = y[s - d:e - d] if s >= d else np.zeros(e - s)
            od = o[s - d:e - d] if s >= d else np.zeros(e - s)
            o[s:e] = -g * y[s:e] + xd + g * od
        y = o
    return y

# ---------------------------------------------------------------- timbres
def pluck(f, d=0.5, bright=1.0, rngv=None):
    t = tt(d); y = np.zeros_like(t)
    for h in range(1, 12):
        if f * h > 9000: break
        dec = 6.0 + 9.0 * h / max(bright, 0.2)
        y += (1.0 / h) * np.exp(-dec * t) * np.sin(2 * np.pi * f * h * t + 0.3 * h)
    y *= (1 - np.exp(-t * 900))
    return fade(y * 0.6, 0.002, 0.03)

def pad_note(f, d, fc):
    t = tt(d); y = np.zeros_like(t)
    lfo = 1 + 0.003 * np.sin(2 * np.pi * 0.2 * t)
    for det in (-0.07, 0.0, 0.07):
        fd = f * 2 ** (det / 12)
        for h in range(1, 40):
            if fd * h > 12000: break
            w = 1.0 / (h * (1 + (fd * h / fc) ** 2))
            y += w * np.sin(2 * np.pi * fd * h * t * lfo + h * 1.7 + det * 40)
    return y / 3

def kick(g=1.0):
    t = tt(0.32)
    f = 46 + 90 * np.exp(-t * 30)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t * 9) + 0.12 * np.sin(2 * ph * 1.0) * np.exp(-t * 40)
    return fade(y * g, 0.001, 0.02)

def sub(f, d):
    t = tt(d); y = np.sin(2 * np.pi * f * t) + 0.15 * np.sin(4 * np.pi * f * t)
    e = np.minimum(1, t / 0.02) * np.exp(-t * 2.2)
    return fade(y * e, 0.01, 0.06)

def hat(open_=False):
    d = 0.18 if open_ else 0.05
    t = tt(d); n = rng.standard_normal(len(t))
    n = hp1(hp1(n, 6000.0), 6000.0)
    return fade(n * np.exp(-t * (18 if open_ else 80)), 0.0005, 0.005)

def clap(g=1.0):
    t = tt(0.22); n = rng.standard_normal(len(t))
    n = biquad_bp(n, 1500.0, 0.8)
    e = np.exp(-t * 22) + 0.6 * np.exp(-((t - 0.012) ** 2) * 8e4)
    return fade(n * e * 1.2 * g, 0.001, 0.02)

def whoosh(d=0.4, rise=True):
    t = tt(d); n = rng.standard_normal(len(t))
    u = t / d
    fc = 300 * (14 ** (u if rise else 1 - u))
    y = lp1(n, fc) * 1.0
    y = hp1(y, 200.0)
    env = np.sin(np.pi * np.minimum(1, u)) ** 1.5
    # peak toward end (leading into cut)
    env = np.minimum(1, u * 1.2) ** 2 * (1 - np.exp(-(1 - u) * 60) * 0.0)
    env *= np.minimum(1, (1 - u) / 0.08 + 0.0)
    return fade(y * env, 0.01, 0.02)

def riser(d, f0=300, f1=9000):
    t = tt(d); n = rng.standard_normal(len(t)); u = t / d
    y = lp1(n, f0 * (f1 / f0) ** u)
    y = hp1(y, 250.0) * (u ** 2.0)
    tone = np.sin(2 * np.pi * np.cumsum(220 * 4 ** u) / SR) * u ** 2 * 0.0
    return fade(y + tone, 0.05, 0.02)

# ---------------------------------------------------------------- music
CH = [  # (bass midi, chord midis) per bar, 4-bar loop: Am9 Fmaj7 Cadd9 G6
    (33, [57, 60, 64, 67, 71]),
    (29, [53, 57, 60, 64, 67]),
    (36, [55, 60, 64, 67, 62]),
    (31, [55, 59, 62, 64, 67]),
]

def section_level(t):
    """energy 0..4"""
    if t < 4: return 0
    if t < 16: return 1
    if t < 34: return 2
    if t < 47: return 3
    if t < 52: return 0.5
    if t < 57: return 2.5
    return 0

def bar_chord(b): return CH[b % 4]

nbars = int(DUR / BAR)
for b in range(nbars + 1):
    t0 = b * BAR
    if t0 >= 57.0 and t0 != 56.0:
        chord = (33, [57, 60, 64, 67, 71])
    else:
        chord = bar_chord(b)
    lvl = section_level(t0 + 0.01)
    fc = {0: 700, 0.5: 600, 1: 900, 2: 1500, 2.5: 1400, 3: 2200}[lvl] if t0 < 57 else 900
    if t0 < 16 and t0 >= 4: fc = 900
    # pad (only up to the resolving hit; final pad handled below)
    if t0 < 57.0:
        dur = BAR + 0.8
        g = 0.20 if lvl in (0, 0.5) else 0.16
        for m in chord[1][:4]:
            x = pad_note(float(midi(m - 12 if m > 64 else m)), dur, fc)
            x = x * np.minimum(1, tt(dur) / 0.6) * np.minimum(1, (dur - tt(dur)) / 0.8)
            pan = ((m * 7) % 11 - 5) / 8
            add(music_dry, x, t0 - 0.0, pan, g * 0.5)
            add(music_wet, x, t0, pan, g * 0.9)

# arpeggio
arp_pat = [0, 2, 4, 3, 1, 3, 4, 2]
t = 0.0; k = 0
while t < 57.0 - 1e-6:
    lvl = section_level(t); b = int(t // BAR)
    chord = bar_chord(b)
    step = round((t % BAR) / 0.25)
    play = True
    if lvl == 0: play = (step % 2 == 0)           # intro: half density
    if 47 <= t < 52: play = step in (0, 3, 6)
    if 52 <= t < 57: play = True
    if t >= 56.5: play = False
    if play:
        m = chord[1][arp_pat[step % 8] % 5] + (12 if lvl >= 2 else 0)
        br = {0: 0.5, 0.5: 0.5, 1: 0.8, 2: 1.3, 2.5: 1.3, 3: 1.8}[lvl]
        if t < 4: br = 0.35 + 0.5 * (t / 4)  # filtered pluck opening
        ga = 0.20 if lvl != 3 else 0.22
        x = pluck(float(midi(m)), 0.55, br)
        pan = -0.5 if step % 2 == 0 else 0.5
        add(music_dry, x, t, pan, ga)
        add(music_wet, x, t, pan, ga * 0.7)
        add(music_dry, x, t + 0.375, -pan, ga * 0.38)   # dotted-eighth echo
        add(music_wet, x, t + 0.375, -pan, ga * 0.3)
        k += 1
    t += 0.25

# drums / bass
def groove(t0, t1, kick_on=True, density=1, clap_on=False, bass=True, hat16=False):
    t = t0
    while t < t1 - 1e-6:
        step = round(((t - t0) / 0.25))
        pos = round((t % BAR) / 0.25)
        if kick_on and pos % 2 == 0 and (pos % 4 == 0 or density >= 2 and pos in (6,)):
            add(music_dry, kick(), t, 0, 0.62 if pos % 4 == 0 else 0.35)
            log("kick", t)
        if pos % 4 == 2 and not hat16:
            add(music_dry, hat(), t, 0.3, 0.07)
        if hat16 and pos % 2 == 1:
            add(music_dry, hat(), t, 0.3, 0.05)
        if hat16 and pos % 4 == 2:
            add(music_dry, hat(True), t, -0.3, 0.05)
        if clap_on and pos in (4, 12):
            add(music_dry, clap(), t, 0, 0.12); add(music_wet, clap(), t, 0, 0.08)
        if bass and pos in (0, 5, 10) and t < 57:
            b = int(t // BAR); m = bar_chord(b)[0]
            add(music_dry, sub(float(midi(m)), 0.5 if pos == 0 else 0.3), t, 0, 0.30)
        t += 0.25

groove(4.0, 16.0)
groove(16.0, 34.0, density=2, hat16=True)
groove(34.0, 47.0, density=2, clap_on=True, hat16=True)
# light 47-52: soft hat + bass only
groove(47.0, 52.0, kick_on=False, bass=True)
# build 52-57: kick eighths with rising feel
for tk in np.arange(52.0, 57.0, 0.5):
    u = (tk - 52) / 5
    add(music_dry, kick(), tk, 0, 0.30 + 0.35 * u); log("kick", tk)
for tk in np.arange(52.0, 57.0, 0.25):
    u = (tk - 52) / 5
    add(music_dry, hat(), tk, 0.3, 0.03 + 0.05 * u)
for tk in np.arange(55.0, 57.0, 0.125):
    add(music_dry, clap(0.5), tk, 0, 0.02 + 0.05 * (tk - 55) / 2)
for b in (52, 54, 56):
    m = bar_chord(b // 2)[0]
for tk in (52.0, 54.0, 56.0):
    m = bar_chord(int(tk // BAR))[0]
    add(music_dry, sub(float(midi(m)), 1.6), tk, 0, 0.28)

# risers and hits
add(music_dry, riser(2.0), 2.0, 0, 0.26); log("riser", 2.0, end=4.0)
add(music_dry, riser(5.0, 250, 8000), 52.0, 0, 0.24); log("riser", 52.0, end=57.0)

def big_hit(t0, root, chord_m, g=1.0, tail=3.0):
    t = tt(tail)
    s = np.sin(2 * np.pi * np.cumsum(root * (1 + 0.5 * np.exp(-t * 25))) / SR) * np.exp(-t * 1.6)
    n = lp1(rng.standard_normal(len(t)), 2500.0) * np.exp(-t * 14) * 0.5
    add(music_dry, fade(s * 0.9 + n, 0.001, 0.2), t0, 0, 0.55 * g)
    for m in chord_m:
        x = pad_note(float(midi(m)), tail, 1800.0) * np.exp(-tt(tail) * 1.1)
        x = fade(x, 0.004, 0.3)
        add(music_dry, x, t0, 0, 0.14 * g); add(music_wet, x, t0, 0, 0.22 * g)
    add(music_dry, kick(1.0), t0, 0, 0.6 * g)

big_hit(4.0, 55.0, [45, 57, 60, 64, 69], 1.0, 3.5); log("hit", 4.0, note="title downbeat")
big_hit(57.0, 55.0, [45, 57, 64, 69, 72], 0.9, 5.0); log("hit", 57.0, note="resolve")
# resolving pad to silence
dur = 5.0
for m in [45, 57, 60, 64, 69]:
    x = pad_note(float(midi(m)), dur, 1000.0)
    x *= np.minimum(1, tt(dur) / 0.5) * np.exp(-tt(dur) * 0.55)
    pan = ((m * 7) % 11 - 5) / 8
    add(music_dry, x, 57.0, pan, 0.10); add(music_wet, x, 57.0, pan, 0.2)

# ---------------------------------------------------------------- sound design
def gear_click():
    t = tt(0.04); n = rng.standard_normal(len(t))
    n = hp1(lp1(n, 5000.0), 800.0) * np.exp(-t * 300)
    ring = np.sin(2 * np.pi * 1900 * t) * np.exp(-t * 220) * 0.5
    thump = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 150) * 0.5
    return fade(n * 0.8 + ring + thump, 0.0005, 0.008)

for lo, hi in ((16.5, 18.5), (19.5, 21.5)):
    for tc in np.arange(lo, hi - 1e-6, 0.25):
        add(sfx, gear_click(), tc, 0.1 * ((int(tc * 4) % 2) * 2 - 1), 0.30)
        log("gear_click", tc)

# servo whir 22.5-27.0 (pitch follows motion)
d = 4.5; t = tt(d); u = t / d
motion = 0.5 - 0.5 * np.cos(2 * np.pi * (u * 2.0))      # two move-and-return strokes
fq = 300 + 300 * motion
ph = np.cumsum(fq) / SR
saw = 2 * (ph % 1.0) - 1
w = biquad_bp(saw, 450.0, 0.7)
w = lp1(w, 1800.0)
amp = (0.55 + 0.45 * motion)
w = fade(w * amp, 0.25, 0.3)
add(sfx, w, 22.5, 0, 0.055); log("servo_whir", 22.5, end=27.0, hz="300-600")

def ui_tick():
    t = tt(0.05)
    y = np.sin(2 * np.pi * 2600 * t) * np.exp(-t * 130) + 0.3 * np.sin(2 * np.pi * 5200 * t) * np.exp(-t * 220)
    return fade(y, 0.0005, 0.01)
for tc in np.arange(41.5, 45.01, 0.5):
    add(sfx, ui_tick(), tc, 0.0, 0.10); log("ui_tick", tc)

def thud():
    t = tt(0.3); f = 55 + 70 * np.exp(-t * 25)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)
    n = lp1(rng.standard_normal(len(t)), 900.0) * np.exp(-t * 60) * 0.25
    return fade(y + n, 0.001, 0.05)
add(sfx, thud(), 31.0, 0, 0.5); log("pinch_thud", 31.0)

for tc in (9.0, 22.0, 28.0, 41.0, 47.0, 52.0):
    add(sfx, whoosh(0.4), tc - 0.4, 0, 0.16); log("whoosh", tc - 0.4, end=tc, cut=tc)

# ---------------------------------------------------------------- mix
wetL = reverb(music_wet[0], 0); wetR = reverb(music_wet[1], 37)
music = music_dry + 0.55 * np.stack([wetL, wetR])
mix = music * 1.0 + sfx * 1.0

# dc removal + gentle low cut
for c in range(2):
    mix[c] = hp1(mix[c], 25.0)

# master fades
f_in = int(0.01 * SR); mix[:, :f_in] *= np.linspace(0, 1, f_in)
f_out = int(1.5 * SR); mix[:, -f_out:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, f_out)))
mix[:, -1] = 0.0

def rms_db(x): return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
TARGET_RMS, CEIL = -16.0, 10 ** (-1.2 / 20)

def soft(x, th=0.55):
    a = np.abs(x); o = np.sign(x) * np.where(a <= th, a, th + (1 - th) * np.tanh((a - th) / (1 - th)))
    return o

g = 10 ** (TARGET_RMS / 20) / np.sqrt(np.mean(mix ** 2))
for _ in range(12):
    y = soft(mix * g) * 1.0
    r = rms_db(y)
    if abs(r - TARGET_RMS) < 0.05: break
    g *= 10 ** ((TARGET_RMS - r) / 20)
y = y / max(1.0, np.max(np.abs(y)) / CEIL)
y[:, -1] = 0.0
y = y - np.mean(y, axis=1, keepdims=True) * 0  # DC handled by high-pass

pcm = np.round(np.clip(y, -1, 1) * 32767).astype("<i2")
os.makedirs(OUT, exist_ok=True)
with wave.open(os.path.join(OUT, "mix.wav"), "wb") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes(pcm.T.copy().tobytes())
events.sort(key=lambda e: e["t"])
with open(os.path.join(OUT, "sync.json"), "w") as f:
    json.dump(dict(sample_rate=SR, duration_s=DUR, bpm=120, events=events), f, indent=1)

# ---------------------------------------------------------------- verify
with wave.open(os.path.join(OUT, "mix.wav"), "rb") as wf:
    nf, ch, sr, sw = wf.getnframes(), wf.getnchannels(), wf.getframerate(), wf.getsampwidth()
    d = np.frombuffer(wf.readframes(nf), "<i2").reshape(-1, ch) / 32768.0
print(f"frames={nf} duration={nf / sr:.3f}s sr={sr} channels={ch} bits={sw * 8}")
print(f"peak={20 * np.log10(np.max(np.abs(d))):.2f} dBFS  rms={rms_db(d):.2f} dBFS  dc={np.mean(d, axis=0)}")
print(f"last-1.5s rms={rms_db(d[-int(1.5 * sr):]):.1f} dBFS  last sample={d[-1]}  events={len(events)}")
