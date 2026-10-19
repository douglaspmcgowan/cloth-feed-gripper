"""Render-settings benchmark: one frame of one shot at several sample counts, with and without motion blur.

    python bench3d.py S2 60 [--w 1920 --h 1080] [--samples 32 64 128 256] [--denoise high] [--out DIR]

Builds the scene once. For each setting it renders the frame before as a warm-up (changing settings drops
Cycles' persistent data, so the first frame after a change rebuilds the BVH and reloads kernels), then times
the frame itself and the frame after, which is what a frame costs inside a shot render.
Writes DIR/<shot>_<frame>_<spp>[_mb].png and appends one JSON line per setting to DIR/bench.jsonl.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import bpy  # noqa: E402

import scene3d as S  # noqa: E402
import shots3d as T  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shot")
    ap.add_argument("frame", type=int)
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--samples", type=int, nargs="+", default=[32, 64, 128, 256])
    ap.add_argument("--mblur", default="both", choices=["off", "on", "both"])
    ap.add_argument("--denoise", default="high")
    ap.add_argument("--threshold", type=float, default=0.01)
    ap.add_argument("--device")
    ap.add_argument("--out", default=os.path.join(S.ROOT, "video", "gripper", "build", "bench"))
    a = ap.parse_args([x for x in sys.argv[1:] if x != "--"])
    os.makedirs(a.out, exist_ok=True)
    args = T.parse([a.shot, "--w", str(a.w), "--h", str(a.h), "--samples", "8", "--frame", str(a.frame),
                    "--out", a.out, "--name", f"track_{a.shot}"] + (["--device", a.device] if a.device else []))
    sc, _, _, dev = T.prepare(args)
    sc.render.filepath = os.path.join(a.out, "warmup.png")
    sc.frame_set(a.frame - 1)
    bpy.ops.render.render(write_still=True)
    for mb in {"off": [False], "on": [True], "both": [False, True]}[a.mblur]:
        for spp in a.samples:
            dev = S.render_settings(a.w, a.h, spp, device=a.device, denoise=a.denoise, motion_blur=mb,
                                    threshold=a.threshold)
            sc.render.filepath = os.path.join(a.out, "warmup.png")
            sc.frame_set(a.frame - 1)
            bpy.ops.render.render(write_still=True)
            name = f"{a.shot}_{a.frame:04d}_{spp}{'_mb' if mb else ''}.png"
            times = []
            for f, fn in ((a.frame, name), (a.frame + 1, "next.png")):
                sc.frame_set(f)
                sc.render.filepath = os.path.join(a.out, fn)
                t0 = time.perf_counter()
                bpy.ops.render.render(write_still=True)
                times.append(time.perf_counter() - t0)
            rec = dict(shot=a.shot, frame=a.frame, w=a.w, h=a.h, spp=spp, mblur=mb, denoise=a.denoise,
                       threshold=a.threshold, seconds=round(sum(times) / len(times), 2),
                       runs=[round(t, 2) for t in times], device=dev, pid=os.getpid(), file=name)
            print("BENCH", json.dumps(rec), flush=True)
            with open(os.path.join(a.out, "bench.jsonl"), "a") as fh:
                fh.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
