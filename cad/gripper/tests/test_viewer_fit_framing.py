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
(async()=>{const launch={headless:true,args:['--use-angle=swiftshader']};if(cfg.browserPath)launch.executablePath=cfg.browserPath;if(cfg.browserChannel)launch.channel=cfg.browserChannel;const browser=await chromium.launch(launch);let results=[],cameraFailures=[];
 const record=(name,ok,details)=>{const row={name,passed:!!ok,...details};results.push(row);if(!ok)cameraFailures.push(row);};
 async function gripperFrame(page){return page.evaluate(()=>{const cv=document.querySelector('#model canvas'),r=cv.getBoundingClientRect(),T=window.THREE;
  V3.grip.updateMatrixWorld(true);V3.cam.updateMatrixWorld(true);const q=new T.Vector3();let count=0,meshes=0,outsideXY=0,outsideDepth=0,minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
  const shown=o=>{for(let p=o;p;p=p.parent)if(!p.visible)return false;return true;};
  V3.grip.traverse(o=>{if(!o.isMesh||!o.geometry||!o.geometry.attributes.position||!shown(o))return;meshes++;const a=o.geometry.attributes.position;
   for(let i=0;i<a.count;i++){q.fromBufferAttribute(a,i).applyMatrix4(o.matrixWorld).project(V3.cam);count++;minX=Math.min(minX,q.x);maxX=Math.max(maxX,q.x);minY=Math.min(minY,q.y);maxY=Math.max(maxY,q.y);
    if(q.x < -1||q.x > 1||q.y < -1||q.y > 1)outsideXY++;if(q.z < -1||q.z > 1)outsideDepth++;}});
  return {theme:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light',canvas:{x:r.x,y:r.y,width:r.width,height:r.height},meshes,vertices:count,outsideXY,outsideDepth,ndc:[minX,maxX,minY,maxY],margins_px:{left:(minX+1)*r.width/2,right:(1-maxX)*r.width/2,top:(1-maxY)*r.height/2,bottom:(minY+1)*r.height/2}};});}
 async function fitState(page){return page.evaluate(()=>({hash:location.hash,host:V3.host&&V3.host.id,camera:[...V3.cam.position.toArray(),...V3.ctl.target.toArray()],finding:FS.cur&&FS.cur.id,theta:FST.th,roll:FST.roll,cut:{on:FS.cut.on,mode:FS.cut.mode,flip:FS.cut.flip,off:FS.cut.off}}));}
 const expectedCamera=[111,20.2,158.6,0,-30,0],permalink='#fit-f-pads~j=-10~r=0~c=111.0,20.2,158.6,0.0,-30.0,0.0~s=off';
 async function cameraRegressions(){
  for(const [w,h] of [[390,844],[768,1024],[1440,1000]]){const c=await browser.newContext({viewport:{width:w,height:h},colorScheme:w===768?'dark':'light'}),p=await c.newPage();await p.goto(cfg.url+'#model',{waitUntil:'domcontentloaded'});await ready(p);await p.waitForFunction(()=>V3.host===document.querySelector('#model .v3d'));
   const out=path.join(cfg.out,`model-${w}x${h}`);fs.mkdirSync(out,{recursive:true});
   const assembled=await gripperFrame(p);await p.screenshot({path:path.join(out,'assembled.png')});fs.writeFileSync(path.join(out,'assembled.json'),JSON.stringify(assembled,null,2));
   const goodMargins=b=>Object.values(b.margins_px).every(v=>Number.isFinite(v)&&v>=8);record(`assembled gripper margins ${w}x${h}`,goodMargins(assembled),{bounds:assembled,required_margin_px:8});
   await p.locator('#jaw').evaluate(e=>{e.value='20';e.dispatchEvent(new Event('input',{bubbles:true}));});await p.locator('#explode').click();
   await p.evaluate(()=>{V3.explode=0.5;V3.explodeTarget=0.5;applyPose();V3.dirty=true;});await p.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
   const middle=await gripperFrame(p);await p.screenshot({path:path.join(out,'exploded-midpoint.png')});fs.writeFileSync(path.join(out,'exploded-midpoint.json'),JSON.stringify(middle,null,2));
   record(`exploded midpoint gripper margins ${w}x${h}`,goodMargins(middle),{bounds:middle,required_margin_px:8,explode:await p.evaluate(()=>V3.explode)});await p.evaluate(()=>{V3.explodeTarget=1;V3.dirty=true;});
   await p.waitForFunction(()=>Math.abs(V3.explode-V3.explodeTarget)<0.002,null,{timeout:15000});const exploded=await gripperFrame(p);await p.screenshot({path:path.join(out,'exploded.png')});fs.writeFileSync(path.join(out,'exploded.json'),JSON.stringify(exploded,null,2));
   record(`exploded endpoint gripper margins ${w}x${h}`,goodMargins(exploded),{bounds:exploded,required_margin_px:8,explode:await p.evaluate(()=>V3.explode)});await c.close();}
  const c=await browser.newContext({viewport:{width:390,height:844},colorScheme:'light'}),p=await c.newPage();
  const settle=async label=>{await p.waitForFunction(()=>typeof V3!=='undefined'&&V3.ready&&CUR==='fit'&&V3.host===document.querySelector('#fit3d'),null,{timeout:120000});await p.waitForTimeout(250);const s=await fitState(p);fs.writeFileSync(path.join(cfg.out,`fit-${label}.json`),JSON.stringify(s,null,2));await p.screenshot({path:path.join(cfg.out,`fit-${label}.png`)});const delta=s.camera.map((v,i)=>Math.abs(v-expectedCamera[i]));record(`explicit fit camera ${label}`,delta.every(v=>v<=0.1),{camera:s.camera,expected:expectedCamera,delta,hash:s.hash,host:s.host});record(`fit permalink retained ${label}`,s.hash===permalink,{actual:s.hash,expected:permalink});
   const stateOK=s.finding==='pads'&&s.theta===-10&&s.roll===0&&!s.cut.on&&s.cut.mode==='f'&&!s.cut.flip&&s.cut.off===0;record(`fit state retained ${label}`,stateOK,{finding:s.finding,theta:s.theta,roll:s.roll,cut:s.cut});return s;};
  await p.goto(cfg.url+permalink,{waitUntil:'domcontentloaded'});await ready(p);await settle('cold');
  await p.reload({waitUntil:'domcontentloaded'});await ready(p);await settle('warm');
  await p.goto(cfg.url+'#model',{waitUntil:'domcontentloaded'});await ready(p);await p.evaluate(h=>{location.hash=h;},permalink);await settle('late-host-attach');
  const before=await fitState(p);const box=await p.locator('#fit3d canvas').boundingBox();await p.mouse.move(box.x+box.width*.55,box.y+box.height*.55);await p.mouse.down();await p.mouse.move(box.x+box.width*.67,box.y+box.height*.62,{steps:5});await p.mouse.up();await p.evaluate(()=>{V3.ctl.enableDamping=false;V3.ctl.update();});
  const orbited=await fitState(p),orbitDelta=orbited.camera.map((v,i)=>Math.abs(v-before.camera[i]));
  record('manual orbit remains interactive',orbitDelta.some(v=>v>0.1),{before:before.camera,after:orbited.camera,delta:orbitDelta});
  await p.setViewportSize({width:420,height:844});await p.waitForFunction(()=>{const r=document.querySelector('#fit3d canvas').getBoundingClientRect();return Math.abs(V3.cam.aspect-r.width/r.height)<0.001;},null,{timeout:5000});const resized=await fitState(p),resizeDelta=resized.camera.map((v,i)=>Math.abs(v-orbited.camera[i]));record('resize preserves manual camera',resizeDelta.every(v=>v<=0.1),{before:orbited.camera,after:resized.camera,delta:resizeDelta});await c.close();
  const counts={};for(const id of ['model','fit','parts','assembly']){const c2=await browser.newContext({viewport:{width:1440,height:1000}}),p2=await c2.newPage();await p2.goto(cfg.url+'#'+id,{waitUntil:'domcontentloaded'});await ready(p2);await p2.waitForFunction(v=>{const e=document.getElementById(v);return e&&!e.hidden;},id);counts[id]=await p2.evaluate(v=>{const root=document.getElementById(v),sel='button,input,select,textarea,a[href],[role="button"]';const vis=e=>{for(let n=e;n&&n!==root.parentElement;n=n.parentElement){if(n.hidden||getComputedStyle(n).display==='none'||getComputedStyle(n).visibility==='hidden')return false;}return e.getClientRects().length>0;};const rows=[...root.querySelectorAll(sel)].filter(vis).map(e=>({tag:e.tagName.toLowerCase(),id:e.id||null,role:e.getAttribute('role'),label:e.getAttribute('aria-label'),text:(e.innerText||e.value||'').trim().replace(/\s+/g,' ').slice(0,80)}));return {total:rows.length,byTag:rows.reduce((a,x)=>(a[x.tag]=(a[x.tag]||0)+1,a),{}),controls:rows};},id);await c2.close();}
  fs.writeFileSync(path.join(cfg.out,'control-counts.json'),JSON.stringify(counts,null,2));results.push({name:'rendered control counts',passed:true,counts});
 }
 if(!cfg.cameraOnly){
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
 }
 await cameraRegressions();const cameraResult={passed:cameraFailures.length===0,failures:cameraFailures,results};fs.writeFileSync(path.join(cfg.out,'camera-assertions.json'),JSON.stringify(cameraResult,null,2));fs.writeFileSync(path.join(cfg.out,'assertions.json'),JSON.stringify(cameraResult,null,2));await browser.close();process.stdout.write(JSON.stringify({passed:cameraResult.passed,failures:cameraFailures.length,results:results.length}));if(cameraFailures.length)process.exitCode=2;
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
    ap.add_argument("--camera-only", action="store_true",
                    help="run only the new actual-browser gripper framing and camera permalink regressions")
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
              "browserChannel": args.browser_channel, "cameraOnly": args.camera_only}
    with tempfile.TemporaryDirectory(prefix="viewer-fit-") as td:
        script, conf = Path(td) / "run.js", Path(td) / "config.json"
        script.write_text(NODE, encoding="utf-8")
        conf.write_text(json.dumps(config), encoding="utf-8")
        subprocess.run(["node", str(script), str(conf)], check=True, timeout=600)


if __name__ == "__main__":
    main()
