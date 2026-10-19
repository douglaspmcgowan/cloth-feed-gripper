"""Render one thumbnail per part and per fastener line from the built viewer.html and save them to thumbs.json,
which viewer_build.py embeds. Run after a CAD change, then rebuild:

    python viewer_build.py && python make_thumbs.py && python viewer_build.py
"""
import asyncio, json, tempfile
from pathlib import Path
from playwright.async_api import async_playwright

SP = Path(__file__).parent
SRC = SP.parent / "viewer.html"


async def main():
    tmp = Path(tempfile.mkdtemp(prefix="thumbs_")) / "t.html"
    tmp.write_text("<!" + "doctype html><html><head><meta charset='utf-8'><style>[hidden]{display:none!important}</style></head><body>"
                   + SRC.read_text(encoding="utf-8") + "</body></html>", encoding="utf-8", newline="\n")
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])
        pg = await b.new_page(viewport={"width": 1200, "height": 900}, color_scheme="light")
        await pg.goto(tmp.as_uri())
        await pg.wait_for_function("typeof V3!=='undefined'&&V3.ready", timeout=300000)
        await pg.evaluate("window.__forceThumbs=true;for(const k in THUMB)delete THUMB[k];location.hash='#parts'")
        await pg.wait_for_function("V3.thumbsDone", timeout=900000)
        th = await pg.evaluate("THUMB")
        await b.close()
    (SP / "thumbs.json").write_text(json.dumps(th, sort_keys=True, indent=0), encoding="utf-8", newline="\n")
    print(len(th), "thumbnails,", sum(len(v) for v in th.values()) // 1024, "KB")


asyncio.run(main())
