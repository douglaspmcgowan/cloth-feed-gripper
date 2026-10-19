"""Bench evidence: 100 % crops of each bench3d.py render side by side, one sheet per shot, plus a markdown table.

    python bench_sheet.py BENCHDIR OUTDIR

Crops are 480 x 270 on the subject: flat PETG face (S2), gear teeth (S1), the pinch (S6, from track.json).
The last column of the table is the RMS difference from the 256-sample render of the same setting.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

B, O = sys.argv[1], sys.argv[2]
os.makedirs(O, exist_ok=True)
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts", "Archivo-Variable.ttf")
CROP = {"S2": (900, 330), "S1": (760, 420), "S6": (740, 420)}
CW, CH = 480, 270
recs = list({(r["shot"], r["spp"], r["mblur"]): r  # a re-run of a setting replaces the earlier line
             for r in (json.loads(ln) for ln in open(os.path.join(B, "bench.jsonl")))}.values())


def crop(r):
    x0, y0 = CROP.get(r["shot"], (720, 405))
    return Image.open(os.path.join(B, r["file"])).convert("RGB").crop((x0, y0, x0 + CW, y0 + CH))


for shot in sorted({r["shot"] for r in recs}):
    rs = [r for r in recs if r["shot"] == shot]
    spps = sorted({r["spp"] for r in rs})
    sheet = Image.new("RGB", (CW * len(spps), (CH + 40) * 2), (240, 240, 240))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 22)
    for r in rs:
        col, row = spps.index(r["spp"]), int(r["mblur"])
        sheet.paste(crop(r), (col * CW, row * (CH + 40) + 40))
        d.text((col * CW + 8, row * (CH + 40) + 8), f"{r['spp']} spp{' + motion blur' if r['mblur'] else ''}  {r['seconds']} s",
               font=f, fill=(20, 20, 20))
    sheet.save(os.path.join(O, f"bench_{shot}.png"), optimize=True)
    print("wrote", os.path.join(O, f"bench_{shot}.png"))

print("| Frame | Samples | Motion blur | s / frame | RMS difference from 256 spp (8-bit levels) |")
print("|---|---|---|---|---|")
for r in sorted(recs, key=lambda r: (r["shot"], r["mblur"], r["spp"])):
    ref = [q for q in recs if q["shot"] == r["shot"] and q["mblur"] == r["mblur"] and q["spp"] == 256]
    a = np.asarray(crop(r), float)
    rms = float(np.sqrt(((a - np.asarray(crop(ref[-1]), float)) ** 2).mean())) if ref else float("nan")
    print(f"| {r['shot']} {r['frame']} | {r['spp']} | {'on' if r['mblur'] else 'off'} | {r['seconds']} | {rms:.2f} |")
