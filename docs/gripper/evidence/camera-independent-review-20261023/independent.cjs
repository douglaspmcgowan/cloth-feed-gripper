const fs = require('fs'), path = require('path');
const {chromium} = require('C:/Users/dougl/Worktrees/product-design-system/pds-ux-linked-selection-20261022/studio/web/node_modules/@playwright/test/index.js');
const OUT=__dirname, URL='http://127.0.0.1:4200/cad/gripper/viewer.html';
const PREFIX='https://cdn.jsdelivr.net/npm/three@0.186.1/';
const DEP='C:/Users/dougl/Projects/product-design-system/gripper-ui-fixture/package';
const CACHED='C:/Users/dougl/Projects/product-design-system/gripper-ui-runtime/cdn-three.module.min.js';
const result={reviewer:'independent gpt-6.1-sol',screenshots:[],scenarios:[],console_errors:[],page_errors:[],requests_failed:[],cleanup:{},viewports:[]};
const save=(name,v)=>fs.writeFileSync(path.join(OUT,name+'.json'),JSON.stringify(v,null,2));
async function shot(p,name){const file=name+'.png';await p.screenshot({path:path.join(OUT,file)});result.screenshots.push(file);}
async function fixture(c){await c.route(PREFIX+'**',async route=>{const rel=route.request().url().slice(PREFIX.length);if(rel.includes('..'))throw Error('fixture traversal');const file=rel==='build/three.module.min.js'?CACHED:path.join(DEP,rel);await route.fulfill({status:200,body:fs.readFileSync(file),contentType:'text/javascript',headers:{'access-control-allow-origin':'*'}});});}
function listen(p,label){p.on('console',m=>{if(m.type()==='error')result.console_errors.push({label,text:m.text()});});p.on('pageerror',e=>result.page_errors.push({label,text:e.message}));p.on('requestfailed',r=>result.requests_failed.push({label,url:r.url(),failure:r.failure()}));}
async function ready(p){await p.waitForFunction(()=>typeof V3!=='undefined'&&V3.ready,null,{timeout:90000});await p.waitForTimeout(700);}
async function state(p){return p.evaluate(()=>({url:location.href,hash:location.hash,camera:[...V3.cam.position.toArray(),...V3.ctl.target.toArray()],host:V3.host.id,finding:document.querySelector('#fitPick').value,jaw:document.querySelector('#fitJaw').value,roll:document.querySelector('#fitRoll').value,section:{pressed:document.querySelector('#fitCutOn').getAttribute('aria-pressed'),mode:[...document.querySelectorAll('[data-cut][aria-pressed="true"]')].map(x=>x.dataset.cut),offset:document.querySelector('#fitCutPos').value},aspect:V3.cam.aspect,canvas:(()=>{const r=V3.renderer?V3.renderer.domElement.getBoundingClientRect():V3.host.querySelector('canvas').getBoundingClientRect();return {width:r.width,height:r.height};})()}));}
async function bounds(p){return p.evaluate(()=>{
    // Independent oracle: every position buffer, transformed through the complete world/camera matrices.
    // Record invisible descendants too, so disappearance cannot silently count as framing success.
    V3.scene.updateMatrixWorld(true);V3.cam.updateMatrixWorld(true);
    const canvas=V3.host.querySelector('canvas'),r=canvas.getBoundingClientRect(),all=[],visible=[];
    let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity,z0=Infinity,z1=-Infinity,n=0;
    V3.grip.traverse(mesh=>{if(!mesh.isMesh||!mesh.geometry?.attributes.position)return;
      const ancestry=[];for(let a=mesh;a;a=a.parent)ancestry.push({name:a.name,visible:a.visible});
      const row={name:mesh.name,positions:mesh.geometry.attributes.position.count,ancestry,shown:ancestry.every(a=>a.visible)};all.push(row);
      if(!row.shown)return;visible.push(mesh.name);
      const v=new THREE.Vector3(),buf=mesh.geometry.attributes.position;
      for(let i=0;i<buf.count;i++){v.fromBufferAttribute(buf,i).applyMatrix4(mesh.matrixWorld).project(V3.cam);n++;x0=Math.min(x0,v.x);x1=Math.max(x1,v.x);y0=Math.min(y0,v.y);y1=Math.max(y1,v.y);z0=Math.min(z0,v.z);z1=Math.max(z1,v.z);}
    });
    return {canvas:{x:r.x,y:r.y,width:r.width,height:r.height},all_meshes:all,visible_names:visible,vertex_population:n,part_keys:Object.keys(V3.parts),margins:{left:(x0+1)*r.width/2,right:(1-x1)*r.width/2,top:(1-y1)*r.height/2,bottom:(y0+1)*r.height/2},depth:[z0,z1],explode:V3.explode,camera:[...V3.cam.position.toArray(),...V3.ctl.target.toArray()]};
});}
async function orbit(p,selector){const b=await p.locator(selector).boundingBox();await p.mouse.move(b.x+b.width*.45,b.y+b.height*.48);await p.mouse.down();await p.mouse.move(b.x+b.width*.56,b.y+b.height*.54,{steps:12});await p.mouse.up();await p.waitForTimeout(1700);}
async function controls(p,id){return p.evaluate(id=>{const root=document.getElementById(id);return [...root.querySelectorAll('button,input,select,textarea,a[href],[role="button"]')].filter(e=>{if(!e.getClientRects().length)return false;for(let a=e;a;a=a.parentElement)if(a.hidden||getComputedStyle(a).display==='none'||getComputedStyle(a).visibility==='hidden')return false;return true;}).map(e=>({tag:e.tagName,id:e.id,text:(e.innerText||e.value||'').trim().slice(0,120),label:e.getAttribute('aria-label')}));},id);}
(async()=>{let browser;try{
  browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-angle=swiftshader']});
  for(const [width,height,theme] of [[390,844,'light'],[768,1024,'dark'],[1440,1000,'light']]){
    result.viewports.push({width,height,theme});const c=await browser.newContext({viewport:{width,height},colorScheme:theme});await fixture(c);const p=await c.newPage();listen(p,'model-'+width);
    await p.goto(URL+'#model');await ready(p);await p.locator('#model .v3d').scrollIntoViewIfNeeded();
    const seq=[];seq.push({pose:'assembled',bounds:await bounds(p)});await shot(p,`ind-model-${width}-assembled`);
    await p.locator('#jaw').fill('20');await p.locator('#explode').click();await p.waitForTimeout(160);seq.push({pose:'transition',bounds:await bounds(p)});
    await p.waitForFunction(()=>V3.explode>.998,null,{timeout:10000});seq.push({pose:'exploded',bounds:await bounds(p)});await shot(p,`ind-model-${width}-exploded`);
    await orbit(p,'#model canvas');seq.push({pose:'manual-orbit-exploded',bounds:await bounds(p)});await shot(p,`ind-model-${width}-orbit`);
    const jawBefore=await p.locator('#jaw').inputValue();await p.locator('#resetCam').click();await p.waitForTimeout(900);const jawAfter=await p.locator('#jaw').inputValue();
    result.scenarios.push({name:'framing-'+width,sequence:seq,reset_camera_only:{jawBefore,jawAfter,explode:await p.evaluate(()=>V3.explode)}});save('ind-framing-'+width,seq);await c.close();
  }
  const c=await browser.newContext({viewport:{width:390,height:844},permissions:['clipboard-read','clipboard-write']});await fixture(c);const p=await c.newPage();listen(p,'permalink');
  await p.goto(URL+'#fit');await ready(p);await p.locator('#fit3d').scrollIntoViewIfNeeded();
  const options=await p.locator('#fitPick option').evaluateAll(es=>es.map(e=>({value:e.value,text:e.textContent})));save('finding-options',options);
  await p.locator('#fitPick').selectOption('pads');await p.waitForTimeout(1500);await p.locator('#fitJaw').fill('7');await p.locator('#fitRoll').fill('40');await p.locator('#fitCutOn').click();await p.waitForTimeout(1000);
  await orbit(p,'#fit3d canvas');await shot(p,'ind-fit-selected-orbit');
  const before=await state(p);await p.locator('#fitLink').click();const copied=await p.evaluate(()=>navigator.clipboard.readText());const linked=await state(p);save('copied-permalink',{before,linked,copied});
  const cameraEncoded=new URL(copied).hash.match(/~c=([^~]+)/);if(!cameraEncoded)throw Error('Actual copied link has no camera');const expected=cameraEncoded[1].split(',').map(Number);const restorations=[];
  async function snap(label,page){await ready(page);await page.waitForTimeout(1200);const s=await state(page);s.label=label;s.expected=expected;s.deltas=s.camera.map((v,i)=>Math.abs(v-expected[i]));restorations.push(s);await page.locator('#fit3d').scrollIntoViewIfNeeded();await shot(page,'ind-fit-'+label);}
  const cold=await c.newPage();listen(cold,'cold');await cold.goto(copied);await snap('cold',cold);await cold.reload();await snap('warm',cold);
  await cold.goto(URL+'#model');await ready(cold);await cold.evaluate(hash=>{location.hash=hash},new URL(copied).hash);await snap('late-host',cold);
  const a=await state(cold);await cold.waitForTimeout(2500);const later=await state(cold);await cold.setViewportSize({width:420,height:844});await cold.waitForTimeout(900);const resized=await state(cold);
  result.scenarios.push({name:'real-copy-link',copied,expected,before,linked,restorations,later_readiness_deltas:later.camera.map((v,i)=>Math.abs(v-a.camera[i])),resize_deltas:resized.camera.map((v,i)=>Math.abs(v-later.camera[i])),resized});save('ind-permalink',result.scenarios[result.scenarios.length-1]);await c.close();
  const cc=await browser.newContext({viewport:{width:1440,height:1000}});await fixture(cc);const pp=await cc.newPage();listen(pp,'control-counts');const counted={};
  for(const id of ['model','fit','parts','assembly']){await pp.goto(URL+'#'+id);await ready(pp);counted[id]={controls:await controls(pp,id)};counted[id].total=counted[id].controls.length;}save('ind-control-counts',counted);result.control_counts=Object.fromEntries(Object.entries(counted).map(([k,v])=>[k,v.total]));await cc.close();
  // No interception for this context: report actual CDN outcome independently of fixture-based behavior.
  const nc=await browser.newContext({viewport:{width:390,height:844}});const np=await nc.newPage();listen(np,'actual-cdn');await np.goto(URL+'#model',{waitUntil:'domcontentloaded'});await np.waitForTimeout(13000);result.actual_cdn=await np.evaluate(()=>({ready:typeof V3!=='undefined'&&V3.ready,messages:[...document.querySelectorAll('.v3dmsg')].filter(e=>!e.hidden).map(e=>e.innerText)}));await shot(np,'actual-cdn');await nc.close();
}catch(e){result.error={message:e.message,stack:e.stack};process.exitCode=2;}finally{if(browser){await browser.close();result.cleanup.browser_closed=true;}save('independent-results',result);console.log(JSON.stringify({error:result.error||null,screenshots:result.screenshots.length,scenarios:result.scenarios.length,cleanup:result.cleanup}));}})();
