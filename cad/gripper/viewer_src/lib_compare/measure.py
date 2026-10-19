#!/usr/bin/env python3
"""Measure each prototype: CDN script bytes, first frame, median orbit frame. Run: python3 measure.py [name...]"""
import sys, json, pathlib
from playwright.sync_api import sync_playwright
here = pathlib.Path(__file__).resolve().parent
shots = here.parent / "shots"
pages = {"threejs": "three.html", "threejs_q0": "three.html?q=0", "threejs_q1": "three.html?q=1", "modelviewer": "modelviewer.html", "babylon": "babylon.html"}
want = sys.argv[1:] or ["threejs", "modelviewer", "babylon"]
ARGS = ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"]
out = json.loads((here / 'results.json').read_text(encoding="utf-8")) if (here / 'results.json').exists() else {}
with sync_playwright() as p:
    b = p.chromium.launch(args=ARGS)
    for name in want:
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        pg = ctx.new_page()
        cdp = ctx.new_cdp_session(pg); cdp.send("Network.enable")
        reqs, enc = {}, {}
        cdp.on("Network.requestWillBeSent", lambda e: reqs.__setitem__(e["requestId"], e["request"]["url"]))
        cdp.on("Network.loadingFinished", lambda e: enc.__setitem__(e["requestId"], e["encodedDataLength"]))
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("file://" + str(here / pages[name].split("?")[0]) + ("?" + pages[name].split("?")[1] if "?" in pages[name] else ""), wait_until="load")
        pg.wait_for_function("window.__firstFrame>0", timeout=120000)
        ff = pg.evaluate("window.__firstFrame")
        pg.wait_for_timeout(1500)
        bench = pg.evaluate("window.__orbit(" + __import__("os").environ.get("N","120") + ")")
        pg.wait_for_timeout(500)
        # screenshot at 960x600
        pg.set_viewport_size({"width": 960, "height": 600}); pg.wait_for_timeout(2500)
        shot = shots / f"lib_{name}.png"
        pg.screenshot(path=str(shot))
        cdn = {u: enc.get(i, 0) for i, u in reqs.items() if u.startswith("https://") and "cdn.jsdelivr" in u}
        out[name] = {"first_frame_ms": round(ff), "median_frame_ms": round(bench["median"], 1), "mean_frame_ms": round(bench["mean"], 1),
                     "script_kb_transferred": round(sum(cdn.values()) / 1024), "cdn_files": {u.split("/npm/")[1]: round(v / 1024, 1) for u, v in cdn.items()},
                     "shot_kb": round(shot.stat().st_size / 1024), "console": errs[:6]}
        print(name, json.dumps(out[name], indent=1), flush=True)
        ctx.close()
    b.close()
(here / "results.json").write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
