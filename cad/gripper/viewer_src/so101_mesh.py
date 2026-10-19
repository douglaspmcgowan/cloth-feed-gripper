"""Tessellate SO-101 context parts, transform to gripper frame G, write compact binary + json."""
import sys, json, math, struct, time
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
sys.path.insert(0, str(REPO / "cad/so101"))
import measure_interface as mi
t0 = time.time()
parts = mi.read_assembly(REPO / "cad/so101/SO101 Assembly.step")
print("read", time.time() - t0, list(parts.keys()), flush=True)
fol, origin, R, to_I, holes_I = mi.interface_frame(parts)
print("holes_I", holes_I)
YH = json.loads((REPO / "cad/gripper/out/parts.json").read_text(encoding="utf-8"))["Y_H"]
ang = [math.atan2(h[1], h[0]) for h in holes_I]
phi = math.radians(45) - ang[0]
names = {}
for k in parts:
    if k.startswith("Wrist_Roll_Pitch"): names["wrist_roll_pitch"] = k
    if k.startswith("Moving_Jaw"): names["stock_moving_jaw"] = k
    if k.startswith("Wrist_Roll_Follower"): names["stock_follower"] = k
    if k.startswith("Motor_holder_SO101_Wrist"): names["motor4_holder"] = k
names["motor5_sts3215"] = "ST3215 Servo v2:5"
names["motor6_sts3215"] = "ST3215 Servo v2:6"
def toG(pI, phi):
    c, s = math.cos(phi), math.sin(phi)
    x = c * pI[:, 0] - s * pI[:, 1]
    z = s * pI[:, 0] + c * pI[:, 1]
    y = YH + 1.0 - pI[:, 2]
    return np.stack([x, y, z], 1)
# choose 90-deg multiple making stock follower widest along X
fp = to_I(mi.sample_points(fol, 1.0))
best = None
for k in range(4):
    g = toG(fp, phi + k * math.pi / 2)
    w = np.ptp(g[:, 0]) - np.ptp(g[:, 2])
    if best is None or w > best[0]: best = (w, k)
phi += best[1] * math.pi / 2
print("phi deg", math.degrees(phi))
out = {}
blob = bytearray()
for key, n in names.items():
    if n not in parts: print("missing", n); continue
    tol = 0.35 if key != "motor4_holder" else 0.5
    verts, tris = parts[n].tessellate(tol, 0.5)
    V = np.array([v.toTuple() for v in verts])
    T = np.array(tris, dtype=np.uint32).reshape(-1, 3)
    G = toG(to_I(V), phi)
    q = np.round(G / 0.02).astype(np.int32)
    assert np.abs(q).max() < 32767, key
    off = len(blob)
    blob += q.astype(np.int16).tobytes()
    while len(blob) % 4: blob += b"\0"
    ioff = len(blob)
    blob += T.astype(np.uint32).tobytes()
    out[key] = dict(nv=len(V), nt=len(T), voff=off, ioff=ioff,
                    bbox=[round(float(v), 2) for v in (*G.min(0), *G.max(0))])
    print(key, len(V), len(T), time.time() - t0, flush=True)
(OUT / "so101_context.bin").write_bytes(bytes(blob))
(OUT / "so101_context.json").write_text(
    json.dumps(dict(parts=out, scale=0.02, phi_deg=math.degrees(phi), YH=YH,
                    holes_G=toG(np.array(holes_I), phi).round(2).tolist()), indent=1),
    encoding="utf-8", newline="\n")
print("done", len(blob), time.time() - t0)
