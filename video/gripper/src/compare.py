"""Before / after crops at 100 % for the six review moments, into review/compare/.

    python compare.py BEFORE_DIR

BEFORE_DIR holds {land,vert}_XXs.png stills pulled with ffmpeg from the previous films (the 1280 x 720,
6-sample pass, upscaled). The after side is pulled the same way from renders/, so both are what a viewer
of the MP4 sees. Each output is one PNG per moment and layout: before on the left, after on the right.
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

VID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
B = sys.argv[1]
A = os.path.join(VID, "build", "after")
O = os.path.join(VID, "review", "compare")
FONT = ImageFont.truetype(os.path.join(VID, "assets", "fonts", "Archivo-Variable.ttf"), 26)
os.makedirs(A, exist_ok=True)
os.makedirs(O, exist_ok=True)
# 720 x 540 crop on the 3D subject of each landscape moment (x, y of the top-left corner)
BOX = {2: (720, 300), 6: (760, 160), 12: (700, 260), 20: (600, 300), 34: (900, 200), 50: (800, 300)}
CW, CH = 720, 540
for t, (x0, y0) in BOX.items():
    for lay, film in (("land", "gripper_hype_1080p.mp4"), ("vert", "gripper_hype_vertical.mp4")):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", os.path.join(VID, "renders", film),
                        "-frames:v", "1", os.path.join(A, f"{lay}_{t:02d}s.png")], check=True)
    for lay, box in (("land", (x0, y0, x0 + CW, y0 + CH)), ("vert", (180, 600, 180 + CW, 600 + CH))):
        pair = Image.new("RGB", (CW * 2 + 16, CH + 44), (245, 246, 247))
        d = ImageDraw.Draw(pair)
        for i, (src, label) in enumerate(((B, "before: 1280 x 720, 6 spp, upscaled"), (A, "after: native 1920 x 1080, 64 spp"))):
            im = Image.open(os.path.join(src, f"{lay}_{t:02d}s.png")).convert("RGB").crop(box)
            pair.paste(im, (i * (CW + 16), 44))
            d.text((i * (CW + 16) + 8, 8), f"0:{t:02d} {lay}, {label}", font=FONT, fill=(21, 24, 27))
        pair.save(os.path.join(O, f"{lay}_{t:02d}s.png"), optimize=True)
        print("wrote", os.path.join(O, f"{lay}_{t:02d}s.png"))
