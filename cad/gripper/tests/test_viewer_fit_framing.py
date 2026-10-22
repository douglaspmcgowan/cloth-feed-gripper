#!/usr/bin/env python3
"""Actual Chromium regression for fit framing and Three.js loading recovery.

Usage: python cad/gripper/tests/test_viewer_fit_framing.py --url URL --dependency-dir DIR --output DIR
DIR is the extracted three@0.186.1 package, or its parent containing package/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

NODE = r'''
const fs=require('fs'),path=require('path');
const cfg=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const {chromium}=require(cfg.playwright);
const PREFIX='https://cdn.jsdelivr.net/npm/three@0.186.1/';
const dep=fs.existsSync(path.join(cfg.dep,'build'))?cfg.dep:path.join(cfg.dep,'package');
const cached=cfg.cached;
function fixture(context,{block=false,delay=0}={}){return context.route(PREFIX+'**',async route=>{
  if(block)return route.abort('failed');
  const rel=route.request().url().slice(PREFIX.length);if(rel.includes('..'))throw Error('fixture escape');
  const file=rel==='build/three.module.min.js'?cached:path.join(dep,rel);
  if(!file.startsWith(dep+path.sep)&&file!==cached)throw Error('fixture escape');
  const body=fs.readFileSync(file);if(delay&&rel==='build/three.module.min.js')await new Promise(r=>setTimeout(r,delay));
  await route.fulfill({status:200,body,contentType:'text/javascript; charset=utf-8',headers:{'access-control-allow-origin':'*'}});
});}
function assert(ok,msg){if(!ok)throw Error(msg)}
async function ready(page){await page.waitForFunction(()=>typeof V3!=="undefined"&&V3.ready,null,{timeout:120000});await page.waitForTimeout(700)}
async function findingState(page,kind){return page.evaluate(kind=>{
 const f=kind==='overlap'?(FF.find(x=>x.kind==='overlap')||FF.find(x=>x.kind==='padov')||FF.find(x=>x.kind==='overlaps')):(FF.find(x=>x.kind==='gap'&&x.pair&&x.pair.a==='fasteners_b'&&x.pair.b==='fasteners')||FF.find(x=>x.kind===kind));selectFinding(f.id,{instant:true,hash:false});drawFit();placeLabels();
 const stage=document.querySelector('#fit3d').getBoundingClientRect(),labels=[...document.querySelectorAll('#fit3d .lb:not([hidden])')].map(e=>({text:e.textContent,r:(()=>{const x=e.getBoundingClientRect();return {left:x.left,top:x.top,right:x.right,bottom:x.bottom,width:x.width,height:x.height}})()}));
 const loc=document.querySelector('#fitLoc').getBoundingClientRect(),cv=document.querySelector('#fit3d canvas').getBoundingClientRect();
 // Oracle comes directly from unchanged fit fields: pair.p at det.theta, or overlap at/size; never findingFramePoints().
 const raw=kind==='gap'?(()=>{const i=F3.th.reduce((best,v,j)=>Math.abs(v-f.det.theta)<Math.abs(F3.th[best]-f.det.theta)?j:best,0),pq=f.pair.p[i];return pq;})():(()=>{const o=f.ov||f.err||(f.ovs&&f.ovs[0]),at=o.at,size=o.size||[0,0,0],pts=[];for(const x of [-1,1])for(const y of [-1,1])for(const z of [-1,1])pts.push(at.map((v,i)=>v+x*(i===0?size[i]/2:0)+y*(i===1?size[i]/2:0)+z*(i===2?size[i]/2:0)));return pts;})();
 const pts=raw.map(a=>{const q=new THREE.Vector3(...a).project(V3.cam);return{x:(q.x+1)/2*stage.width+stage.left,y:(1-q.y)/2*stage.height+stage.top,z:q.z,source:a}});
 return {id:f.id,title:f.title,kind,stage:{left:stage.left,top:stage.top,right:stage.right,bottom:stage.bottom,width:stage.width,height:stage.height},labels,pts,locator:{left:loc.left,top:loc.top,width:loc.width,height:loc.height,hidden:document.querySelector('#fitLoc').hidden},canvas:{width:cv.width,height:cv.height},scrollWidth:document.documentElement.scrollWidth,innerWidth,ready:V3.ready,parts:Object.keys(V3.parts).length,locDrawn:FS.locDrawn||0};
 },kind)}
(async()=>{const launch={headless:true,args:['--use-angle=swiftshader']};if(cfg.browserPath)launch.executablePath=cfg.browserPath;if(cfg.browserChannel)launch.channel=cfg.browserChannel;const browser=await chromium.launch(launch);let results=[];
 for(const [w,h] of [[390,844],[768,1024],[1440,1000]])for(const kind of ['gap','overlap']){
  const c=await browser.newContext({viewport:{width:w,height:h},colorScheme:'dark'});await fixture(c);const p=await c.newPage();await p.goto(cfg.url+'#fit',{waitUntil:'domcontentloaded'});await ready(p);await p.locator('#fit3d').scrollIntoViewIfNeeded();await p.waitForTimeout(150);const s=await findingState(p,kind);
  assert(s.ready&&s.parts>10&&s.canvas.width>300&&s.canvas.height>250,`${w} ${kind}: real geometry not rendered`);assert(s.scrollWidth<=s.innerWidth,`${w} ${kind}: horizontal overflow`);assert(!s.locator.hidden&&s.locator.width>40&&s.locDrawn>0,`${w} ${kind}: locator not visible`);
  assert(s.pts.every(q=>q.z<1&&q.x>=s.stage.left+2&&q.x<=s.stage.right-2&&q.y>=s.stage.top+2&&q.y<=s.stage.bottom-2),`${w} ${kind}: independent comparison point/overlap bound clipped`);
  const relevant=s.labels.filter(x=>kind==='gap'?x.text.toLowerCase().includes('fastener')||x.text.includes('mm'):x.text.toLowerCase().includes('overlap')||x.text.includes('by design'));
  assert(relevant.length>=2-(kind==='overlap'),`${w} ${kind}: relevant labels missing`);assert(relevant.every(x=>x.r.left>=s.stage.left&&x.r.right<=s.stage.right&&x.r.top>=s.stage.top&&x.r.bottom<=s.stage.bottom),`${w} ${kind}: label clipped`);
  await p.screenshot({path:path.join(cfg.out,`finding-${kind}-${w}x${h}.png`)});fs.writeFileSync(path.join(cfg.out,`finding-${kind}-${w}x${h}.json`),JSON.stringify(s,null,2));results.push(s);await c.close();
 }
 // Negative dependency path: immediate, distinct still-loading, terminal, Parts usable, and keyboard Reload navigation.
 {const c=await browser.newContext({viewport:{width:390,height:844}});await fixture(c,{block:true});const p=await c.newPage();await p.goto(cfg.url+'#model',{waitUntil:'domcontentloaded'});
  const snap=async name=>{const state=await p.evaluate(()=>({text:document.querySelector('#v3dmsg span').textContent,stage:document.querySelector('#v3dmsg').dataset.state,reload:!document.querySelector('#v3dmsg .v3dreload').hidden,parts:!!document.querySelector('#parts:not([hidden])')}));await p.screenshot({path:path.join(cfg.out,`dependency-${name}-390.png`)});fs.writeFileSync(path.join(cfg.out,`dependency-${name}.json`),JSON.stringify(state,null,2));return state};
  const initial=await snap('initial');assert(initial.text.startsWith('Loading')&&initial.reload,'initial loading/reload missing');await p.waitForTimeout(3000);const still=await snap('still');assert(still.text.startsWith('Still loading')&&still.stage==='loading','distinct still-loading missing');await p.evaluate(()=>location.hash='parts');await p.waitForTimeout(200);assert(await p.locator('#parts').isVisible(),'Parts unusable during failure');await p.waitForTimeout(7500);await p.evaluate(()=>location.hash='model');const terminal=await snap('terminal');assert(terminal.text.startsWith('The 3D library did not load')&&terminal.stage==='failed','terminal failure missing');
  const reload=p.locator('#v3dmsg .v3dreload').first();await reload.focus();assert(await reload.evaluate(e=>e===document.activeElement),'Reload not keyboard focusable');await Promise.all([p.waitForNavigation({waitUntil:'domcontentloaded'}),reload.press('Enter')]);await c.close();}
 // Slow dependency reaches still-loading, then recovers without stale loading/error.
 {const c=await browser.newContext({viewport:{width:390,height:844}});await fixture(c,{delay:4000});const p=await c.newPage();const nav=p.goto(cfg.url+'#model',{waitUntil:'domcontentloaded'});await p.waitForSelector('#v3dmsg');await p.waitForTimeout(2800);assert((await p.locator('#v3dmsg span').first().textContent()).startsWith('Still loading'),'slow module skipped still-loading');await nav;await ready(p);assert(await p.locator('.v3dmsg:not([hidden])').count()===0,'loading/error remained after recovery');results.push({slowRecovery:true});await c.close();}
 fs.writeFileSync(path.join(cfg.out,'assertions.json'),JSON.stringify({passed:true,results},null,2));await browser.close();
})().catch(e=>{console.error(e.stack||e);process.exit(2)});
'''

EXPECTED_CACHED_SHA256 = "3bc833fceb6577bd1a380388f832ae61cd6e2f78ad02b0bf0d5adf5a4a9334fe"
REQUIRED_FIXTURE_FILES = (
    "build/three.core.js",
    "examples/jsm/controls/OrbitControls.js",
    "examples/jsm/loaders/GLTFLoader.js",
    "examples/jsm/environments/RoomEnvironment.js",
    "examples/jsm/utils/BufferGeometryUtils.js",
)


def fail(message):
    raise SystemExit(f"configuration error: {message}")


def resolve_playwright(repo, supplied):
    target = supplied or "@playwright/test"
    probe = r"""
const {createRequire}=require('module'),path=require('path');
const r=createRequire(path.join(process.argv[1],'package.json'));
const choices=JSON.parse(process.argv[2]);
for(const choice of choices){try{process.stdout.write(r.resolve(choice));process.exit(0)}catch(e){}}
process.stderr.write(`could not resolve ${choices.join(' or ')} from ${process.argv[1]}`);process.exit(2);
"""
    choices = [target] if supplied else ["@playwright/test", "playwright"]
    done = subprocess.run(
        ["node", "-e", probe, str(repo), json.dumps(choices)],
        text=True, capture_output=True,
    )
    if done.returncode:
        flag = "--playwright-module PATH" if not supplied else "a valid --playwright-module"
        fail(f"{done.stderr.strip()}; install the repository's declared Playwright dependency or supply {flag}")
    return done.stdout


def main():
    ap = argparse.ArgumentParser(
        description="Run the gripper viewer's real-browser fit/loading regression.",
        epilog=("Normal CFG: python cad/gripper/tests/test_viewer_fit_framing.py --url "
                "http://127.0.0.1:4193/cad/gripper/viewer.html --dependency-dir <three-package> "
                "--output <evidence-dir> (place the exact cached module at <three-package>/cdn-three.module.min.js). "
                "Explicit cloud/Windows runtime: add --playwright-module "
                "<installed-module> and either --browser-path <browser-executable> or "
                "--browser-channel <installed-channel>; add --cached-module <exact-minified-module> "
                "when it is outside the product checkout."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--url", required=True, help="served viewer URL")
    ap.add_argument("--dependency-dir", required=True, type=Path,
                    help="extracted three@0.186.1 package or its parent containing package/")
    ap.add_argument("--output", required=True, type=Path, help="directory for screenshots and JSON receipts")
    ap.add_argument("--playwright-module", help="installed @playwright/test or playwright module name/path")
    browsers = ap.add_mutually_exclusive_group()
    browsers.add_argument("--browser-path", type=Path, help="explicit installed browser executable")
    browsers.add_argument("--browser-channel", help="Playwright installed browser channel, for example chrome")
    ap.add_argument("--cached-module", type=Path,
                    help="exact cached jsDelivr three.module.min.js (SHA-256 is verified)")
    args = ap.parse_args()

    if not args.url.startswith(("http://", "https://")):
        fail("--url must be an http:// or https:// URL")
    dep_arg = args.dependency_dir.expanduser().resolve()
    dep = dep_arg if (dep_arg / "build").is_dir() else dep_arg / "package"
    if not dep.is_dir():
        fail(f"--dependency-dir does not contain an extracted three package: {dep_arg}")
    missing = [name for name in REQUIRED_FIXTURE_FILES if not (dep / name).is_file()]
    if missing:
        fail(f"three@0.186.1 fixture is incomplete; missing {', '.join(missing)}")
    if args.browser_path:
        browser_path = args.browser_path.expanduser().resolve()
        if not browser_path.is_file():
            fail(f"--browser-path is not a file: {browser_path}")
    else:
        browser_path = None

    repo = Path(__file__).resolve().parents[3]
    cached = (args.cached_module.expanduser().resolve() if args.cached_module else
              dep_arg / "cdn-three.module.min.js")
    if not cached.is_file():
        fail(f"cached minified module not found at {cached}; supply --cached-module <exact-minified-module>")
    digest = hashlib.sha256(cached.read_bytes()).hexdigest()
    if digest != EXPECTED_CACHED_SHA256:
        fail(f"--cached-module SHA-256 is {digest}, expected {EXPECTED_CACHED_SHA256}")
    playwright = resolve_playwright(repo, args.playwright_module)

    args.output.mkdir(parents=True, exist_ok=True)
    config = {"url": args.url, "dep": str(dep), "out": str(args.output.resolve()),
              "cached": str(cached), "playwright": playwright,
              "browserPath": str(browser_path) if browser_path else None,
              "browserChannel": args.browser_channel}
    with tempfile.TemporaryDirectory(prefix="viewer-fit-") as td:
        script, conf = Path(td) / "run.js", Path(td) / "config.json"
        script.write_text(NODE, encoding="utf-8")
        conf.write_text(json.dumps(config), encoding="utf-8")
        subprocess.run(["node", str(script), str(conf)], check=True, timeout=600)


if __name__ == "__main__":
    main()
