"""Deliverables from the composed masters: renders/ (MP4s, poster, teaser) and ffprobe lines."""
import json
import os
import shutil
import subprocess

import compose as C

R = os.path.join(C.VID, "renders")
os.makedirs(R, exist_ok=True)
for name in ("gripper_hype_1080p.mp4", "gripper_hype_vertical.mp4"):
    shutil.copy(os.path.join(C.BUILD, name), os.path.join(R, name))
# poster: the title moment of S2 (0:08.5), no fades
C.render_frame(int(8.5 * C.FPS), "land").save(os.path.join(R, "poster.png"), optimize=True)
# 10 s teaser: title and exploded view (0:04 to 0:14), 720p, under 8 MB
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "4", "-t", "10", "-i", os.path.join(R, "gripper_hype_1080p.mp4"),
                "-vf", "scale=1280:720:flags=lanczos,fade=t=in:st=0:d=0.3,fade=t=out:st=9.5:d=0.5",
                "-af", "afade=t=in:st=0:d=0.3,afade=t=out:st=9.3:d=0.7", "-c:v", "libx264", "-preset", "slow",
                "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                os.path.join(R, "teaser_10s.mp4")], check=True)
for f in sorted(os.listdir(R)):
    p = os.path.join(R, f)
    if f.endswith(".mp4"):
        o = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                       "format=duration,size:stream=codec_name,width,height,r_frame_rate",
                                       "-of", "json", p], capture_output=True, text=True).stdout)
        v = [s for s in o["streams"] if "width" in s][0]
        a = [s["codec_name"] for s in o["streams"] if "width" not in s]
        print(f"{f}: {float(o['format']['duration']):.2f} s, {v['width']}x{v['height']}, {v['codec_name']} "
              f"{v['r_frame_rate']} fps, audio {a or 'none'}, {int(o['format']['size']) / 1e6:.2f} MB")
    else:
        print(f"{f}: {os.path.getsize(p) / 1e6:.2f} MB")
