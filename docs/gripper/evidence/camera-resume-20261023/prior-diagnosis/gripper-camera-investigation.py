#!/usr/bin/env python3
import hashlib, json, os, pathlib, subprocess, tarfile, tempfile, time

ROOT=pathlib.Path('/workspace/product-design-system')
OUT=ROOT/'cases/gripper/evidence/camera-investigation-20261022'
PACK=ROOT/'cases/gripper/evidence/cloud-input-camera-investigation-20261022'
TARGETS={
 'baseline':'cases/gripper/evidence/cloud-input-camera-investigation-20261022/deployed-review.html',
 'candidate':'cases/gripper/evidence/cloud-input-ui-acceptance-20261022/public/review/index.html'}
EXPECTED={'baseline':'801ed08d2f8e360c216b8b93945db51c0ef462cca9d9a0ff8e3d3d593f1ad43d','candidate':'31ec87e55bf45187fdf755c226db24e9865197d7d36e0f3c802d59e5a9961d7b'}

def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def verify():
 m=json.loads((PACK/'manifest.json').read_text()); rows=[]
 for x in m['files']:
  p=PACK/x['path']; rows.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p),'ok':p.stat().st_size==x['bytes'] and sha(p)==x['sha256']})
 if not all(x['ok'] for x in rows): raise SystemExit('camera packet hash failure')
 for k,p in TARGETS.items():
  if sha(ROOT/p)!=EXPECTED[k]: raise SystemExit(f'{k} target hash failure')
 return rows

def extract_three(dst):
 tgz=ROOT/'cases/gripper/evidence/cloud-input-ui-dependency-20261022/three-0.186.1.tgz'
 if sha(tgz)!='8cd068708ea44f2c73c944b1cead2ba2f0d5c15c8fc194e5700f4e4f4a033fe7': raise SystemExit('three tgz hash failure')
 with tarfile.open(tgz,'r:gz') as t:
  for m in t.getmembers():
   q=pathlib.PurePosixPath(m.name)
   if q.is_absolute() or '..' in q.parts or m.issym() or m.islnk() or not (m.isfile() or m.isdir()): raise SystemExit('unsafe npm member')
  t.extractall(dst,filter='data')

def main():
 started=time.time(); OUT.mkdir(parents=True,exist_ok=True); checks=verify()
 with tempfile.TemporaryDirectory(prefix='gripper-three-') as td:
  extract_three(td)
  js=pathlib.Path(td)/'run.js'; js.write_text(JS)
  env=os.environ|{'ROOT':str(ROOT),'OUT':str(OUT),'THREE':str(pathlib.Path(td)/'package'),'CDN':str(ROOT/'cases/gripper/evidence/cloud-input-ui-dependency-20261022/cdn-three.module.min.js'),'TARGETS':json.dumps(TARGETS)}
  p=subprocess.run(['node',str(js)],env=env,text=True,capture_output=True,timeout=590)
  if p.returncode: print(p.stdout); print(p.stderr); raise SystemExit(p.returncode)
  browser=json.loads(p.stdout)
 result={'schema_version':1,'command':'python /tmp/gripper-camera-investigation.py','exit':0,'elapsed_seconds':round(time.time()-started,3),'input_checks':checks,'browser':browser,'rehash':{k:sha(ROOT/v) for k,v in TARGETS.items()}}
 (OUT/'measurements.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'exit':0,'elapsed_seconds':result['elapsed_seconds'],'captures':len(browser['captures']),'requests':len(browser['dependency_requests'])}))

JS=r'''
const {chromium}=require('/opt/pds-studio-seed/node_modules/playwright');
const fs=require('fs'), path=require('path'), crypto=require('crypto');
const root=process.env.ROOT,out=process.env.OUT,pkg=process.env.THREE,cdn=process.env.CDN,targets=JSON.parse(process.env.TARGETS);
const deps=[], captures=[]; const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
async function stable(page){await page.waitForFunction(()=>window.__v3ready===true&&typeof V3!=='undefined'&&V3.ready,{timeout:90000});await page.waitForTimeout(1800);}
async function state(page){return await page.evaluate(()=>{const r=V3.cv.getBoundingClientRect(), cam=[...V3.cam.position.toArray(),...V3.ctl.target.toArray()];let all=0,outside=0,behind=0,minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;const roots=[V3.grip,V3.arm].filter(Boolean);for(const root of roots)root.traverse(o=>{if(!o.isMesh||!o.visible||!o.geometry?.attributes?.position)return;for(let i=0;i<o.geometry.attributes.position.count;i++){const v=new THREE.Vector3().fromBufferAttribute(o.geometry.attributes.position,i).applyMatrix4(o.matrixWorld).project(V3.cam);all++;if(v.z < -1 || v.z > 1)behind++;if(v.x < -1||v.x>1||v.y < -1||v.y>1)outside++;minX=Math.min(minX,v.x);maxX=Math.max(maxX,v.x);minY=Math.min(minY,v.y);maxY=Math.max(maxY,v.y);}});return {url:location.href,hash:location.hash,viewport:{width:innerWidth,height:innerHeight},canvas:{x:r.x,y:r.y,width:r.width,height:r.height},camera:cam.map(x=>+x.toFixed(4)),aspect:+V3.cam.aspect.toFixed(6),theta:V3.theta,explode:+V3.explode.toFixed(4),vertices:{population:all,outside,behind,ndc:[minX,maxX,minY,maxY].map(x=>+x.toFixed(5)),margins_px:{left:+((minX+1)*r.width/2).toFixed(2),right:+((1-maxX)*r.width/2).toFixed(2),top:+((1-maxY)*r.height/2).toFixed(2),bottom:+((minY+1)*r.height/2).toFixed(2)}},exclusions:['ground plane','lights','labels','overlay helpers']};});}
async function shot(page,name){const p=path.join(out,name+'.png');await page.locator('canvas[role=\"img\"]').screenshot({path:p});const b=fs.readFileSync(p);const s=await state(page);s.file=name+'.png';s.png_bytes=b.length;s.png_sha256=hash(b);captures.push(s);return s;}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/root/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args:['--use-angle=swiftshader']});const context=await browser.newContext();await context.route('https://cdn.jsdelivr.net/npm/three@0.186.1/**',async route=>{const u=new URL(route.request().url()),rel=u.pathname.split('/three@0.186.1/')[1];let file;if(rel==='build/three.module.min.js')file=cdn;else {if(!rel||rel.includes('..'))return route.abort('blockedbyclient');file=path.join(pkg,rel);if(!file.startsWith(pkg+path.sep)||!fs.existsSync(file))return route.abort('failed');}const b=fs.readFileSync(file);deps.push({url:u.href,status:200,bytes:b.length,sha256:hash(b),source:rel==='build/three.module.min.js'?'cached-jsdelivr':'verified-npm'});await route.fulfill({status:200,contentType:'text/javascript; charset=utf-8',headers:{'access-control-allow-origin':'*'},body:b});});
for(const [label,rel] of Object.entries(targets)){for(const vp of [[390,844],[768,1024],[1440,1000]]){const page=await context.newPage();await page.setViewportSize({width:vp[0],height:vp[1]});const base='http://127.0.0.1:4193/'+rel;await page.goto(base+'#model');await stable(page);await shot(page,`${label}-model-assembled-${vp[0]}x${vp[1]}`);await page.locator('#jaw').evaluate(e=>{e.value='20';e.dispatchEvent(new Event('input',{bubbles:true}))});await page.locator('#explode').click();await page.waitForTimeout(2200);await shot(page,`${label}-model-exploded-${vp[0]}x${vp[1]}`);await page.close();}
 const page=await context.newPage();await page.setViewportSize({width:390,height:844});const fit='http://127.0.0.1:4193/'+rel+'#fit-f-pads~j=-10~r=0~c=111.0,20.2,158.6,0.0,-30.0,0.0~s=off';await page.goto(fit);await stable(page);await page.waitForTimeout(1200);const before=await shot(page,`${label}-fit-before-reload-390x844`);await page.reload();await stable(page);await page.waitForTimeout(1200);const after=await shot(page,`${label}-fit-after-reload-390x844`);captures.push({kind:'reload_comparison',target:label,camera_equal_0_1:before.camera.every((v,i)=>Math.abs(v-after.camera[i])<0.05),hash_equal:before.hash===after.hash,before:before.camera,after:after.camera});await page.close();}
await browser.close();process.stdout.write(JSON.stringify({captures,dependency_requests:deps}));})().catch(e=>{console.error(e);process.exit(1)});
'''

if __name__=='__main__': main()
