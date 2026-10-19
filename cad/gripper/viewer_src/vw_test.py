"""Browser check for the built viewer.html.

Loads the page inside the same skeleton the Artifact host adds, then at three sizes visits every view,
every figure tab, the "i" note, full screen and both detail levels, and follows deep links.
Exit code 0 only when there are no failures, no console errors and no horizontal overflow.

    python vw_test.py [--shots DIR]
    python vw_test.py --restore-only 10 --load   # forced context-loss restore N times under CPU load

The B4 finding check in JS_FIT8 reads its expected value and status from the page's own embedded audit data.
Drift between that data and the audit itself (out/fit3d.json plus fit_requirements.json) is caught by
cad/gripper/tests/test_viewer_static.py:247-259 (test_embedded_pair_counts_match_audit_and_requirements).
"""
import asyncio, json, os, sys
from pathlib import Path
from playwright.async_api import async_playwright

SP = Path(__file__).parent
SRC = SP.parent / "viewer.html"
SHOTS = Path(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else None
SIZES = [(1440, 900, "light"), (768, 1024, "dark"), (375, 812, "dark")]
if "--only" in sys.argv:  # one size, for a quick look: --only 375
    SIZES = [s for s in SIZES if str(s[0]) == sys.argv[sys.argv.index("--only") + 1]]
EXPECT_VIEWS = ["model", "fit", "parts", "assembly", "drawings", "concepts", "mass", "torque", "finger", "gears", "dyno",
                "tolerances", "camera", "firmware", "open"]
LINKS = [("#finger-fold", "finger", "finger-fold"), ("#mass-method", "mass", "mass-method"),
         ("#open-torque", "open", "open-torque"), ("#fea", "finger", None), ("#controls", "firmware", None),
         ("#tolerances-sources", "tolerances", "tolerances-sources"), ("#nonsense", "model", None),
         ("#bom", "parts", None), ("#knuckle-b", "parts", None), ("#fit-findings", "fit", "fit-findings"), ("#assembly-findings", "assembly", "assembly-findings")]

JS_OVER = "document.documentElement.scrollWidth - window.innerWidth"
# every visible select: the selected label must fit inside the box (24 px kept for the arrow)
JS_CLIP = """() => { const c = document.createElement('canvas').getContext('2d'), out = [];
  for (const s of document.querySelectorAll('select')) {
    if (!s.offsetParent || s.selectedIndex < 0) continue;
    const cs = getComputedStyle(s), t = s.options[s.selectedIndex].text;
    c.font = cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
    const avail = s.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - 24, tw = c.measureText(t).width;
    if (tw > avail + 0.5) out.push(`${s.id || s.getAttribute('aria-label')} "${t}" ${Math.round(tw)}px > ${Math.round(avail)}px`);
  } return out; }"""
JS_FIG = """id=>{const f=document.getElementById(id);if(!f||f.hidden)return {ok:false,why:'hidden'};
  const r=f.getBoundingClientRect();if(r.width<50||r.height<50)return {ok:false,why:'no size'};
  const body=[...f.querySelectorAll('svg,table,img,canvas,dl,ul,ol,p')].filter(e=>{const b=e.getBoundingClientRect();return b.width>20&&b.height>8;});
  if(!body.length)return {ok:false,why:'empty'};
  const emptyT=[...f.querySelectorAll('table')].filter(t=>!t.querySelector('tbody tr'));if(emptyT.length)return {ok:false,why:'empty table '+emptyT[0].id};
  const emptyC=[...f.querySelectorAll('.chart')].filter(c=>!c.closest('[hidden]')&&!c.querySelector('svg'));if(emptyC.length)return {ok:false,why:'empty chart '+emptyC[0].id};
  const emptyD=[...f.querySelectorAll('dl.kv')].filter(c=>!c.children.length);if(emptyD.length)return {ok:false,why:'empty numbers '+emptyD[0].id};
  const bad=[...f.querySelectorAll('img')].filter(i=>!(i.complete&&i.naturalWidth>0));if(bad.length)return {ok:false,why:'image '+(bad[0].dataset.img||'')};
  const emptyL=[...f.querySelectorAll('ul[data-notes]')].filter(u=>!u.children.length);if(emptyL.length)return {ok:false,why:'no key dimensions '+emptyL[0].dataset.notes};
  const noZoom=[...f.querySelectorAll('.sheet')].filter(s=>!(s.nextElementSibling&&s.nextElementSibling.querySelector('button[data-z="in"]')));if(noZoom.length)return {ok:false,why:'sheet without zoom controls'};
  const noCue=[...f.querySelectorAll('.tw,.chart.wide')].filter(e=>e.offsetParent&&e.scrollWidth>e.clientWidth+2&&!(e.nextElementSibling&&e.nextElementSibling.classList.contains('scrollcue')&&!e.nextElementSibling.hidden));
  if(noCue.length)return {ok:false,why:'sideways scroll without a cue '+(noCue[0].id||noCue[0].querySelector('table,svg')?.id||'')};
  const cut=[...f.querySelectorAll('.tw.full')].filter(e=>e.scrollHeight>e.clientHeight+1);if(cut.length)return {ok:false,why:'full table is cut off'};
  const txt=f.innerText;if(/undefined|NaN|\\[object/.test(txt))return {ok:false,why:'bad text: '+(txt.match(/.{0,30}(undefined|NaN|\\[object).{0,20}/)||[''])[0]};
  return {ok:true};}"""

# state diagram: no edge may pass through a label, nothing may leave the frame, and it must not scroll sideways
JS_FSM = """()=>{const box=document.getElementById('fsmChart'),svg=box.querySelector('svg'),out=[];
  if(box.scrollWidth>box.clientWidth+1)out.push('scrolls sideways');
  const fr=svg.getBoundingClientRect();
  const texts=[...svg.querySelectorAll('text')].map(t=>({t:t.textContent,r:t.getBoundingClientRect()}));
  texts.forEach(({t,r})=>{if(r.left<fr.left-1||r.right>fr.right+1||r.top<fr.top-1||r.bottom>fr.bottom+1)out.push('label outside the frame: '+t);});
  svg.querySelectorAll('path[marker-end]').forEach(p=>{const m=p.getScreenCTM(),L=p.getTotalLength();
    for(let d=0;d<=L;d+=2){const q=p.getPointAtLength(d),x=q.x*m.a+q.y*m.c+m.e,y=q.x*m.b+q.y*m.d+m.f;
      if(x<fr.left-1||x>fr.right+1||y<fr.top-1||y>fr.bottom+1){out.push('edge outside the frame');break;}
      const hit=texts.find(({r})=>x>r.left+1&&x<r.right-1&&y>r.top+2&&y<r.bottom-2);if(hit){out.push('edge crosses label: '+hit.t);break;}}});
  const fs=parseFloat(getComputedStyle(svg.querySelector('text')).fontSize)*fr.width/svg.viewBox.baseVal.width;
  return {problems:[...new Set(out)],mode:box.classList.contains('tall')?'tall':'wide',label_px:Math.round(fs*10)/10};}"""
JS_CONTRAST = """sel=>{const e=document.querySelector(sel),cs=getComputedStyle(e);
  const lum=c=>{const v=c.match(/[\\d.]+/g).slice(0,3).map(x=>{x=x/255;return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4);});return 0.2126*v[0]+0.7152*v[1]+0.0722*v[2];};
  const a=lum(cs.color),b=lum(cs.backgroundColor);return {color:cs.color,background:cs.backgroundColor,ratio:Math.round((Math.max(a,b)+0.05)/(Math.min(a,b)+0.05)*100)/100};}"""

# smallest rendered chart label in a figure, in screen pixels
JS_TEXT = """id=>{let min=99,where='';document.getElementById(id).querySelectorAll('.chart svg text').forEach(t=>{
  if(!t.textContent.trim()||!t.getClientRects().length)return;const m=t.getScreenCTM();if(!m)return;
  const px=parseFloat(getComputedStyle(t).fontSize)*Math.hypot(m.a,m.b);if(px<min){min=px;where=(t.closest('.chart').id||'chart')+': '+t.textContent.trim().slice(0,24);}});
  return {min:Math.round(min*10)/10,where};}"""
# every row of the scores table can be brought on screen, and nothing inside its box is cut off
JS_ROWS = """()=>{const t=document.getElementById('pughTable'),box=t.closest('.tw'),out=[];
  if(box.scrollHeight>box.clientHeight+1)out.push('box cuts '+(box.scrollHeight-box.clientHeight)+' px');
  const rows=[...t.querySelectorAll('tr')];rows.forEach(r=>{r.scrollIntoView({block:'center'});const a=r.getBoundingClientRect(),b=box.getBoundingClientRect();
    if(a.height<8||a.top<b.top-1||a.bottom>b.bottom+1||a.top<0||a.bottom>window.innerHeight)out.push('row not visible: '+r.cells[0].textContent.trim().slice(0,30));});
  const sum=[...document.querySelectorAll('#pughSum li')].map(l=>l.innerText);
  if(sum.length!==2||!/Weighted total/.test(sum[0])||!/0\\.5 s/.test(sum[1]))out.push('totals are not given as text under the table');
  return {rows:rows.length,problems:out};}"""
JS_NUM = """()=>{const out=[],cells=document.querySelectorAll('main td.n, main td.sc');cells.forEach(c=>{const cs=getComputedStyle(c);
  if(/mono|courier|consolas/i.test(cs.fontFamily)||!/Public Sans/.test(cs.fontFamily)||!/tabular-nums/.test(cs.fontVariantNumeric))out.push(cs.fontFamily.slice(0,30)+' / '+cs.fontVariantNumeric);});
  return {cells:cells.length,bad:[...new Set(out)]};}"""
JS_VCUE = """()=>{const box=document.getElementById('fsmTable').closest('.tw'),cue=box.nextElementSibling;
  return {scrolls:box.scrollHeight>box.clientHeight+2,cue:!!cue&&cue.classList.contains('scrollcue')&&!cue.hidden?cue.innerText:''};}"""
# draw one frame and count the canvas pixels the model covers (the canvas clears to transparent)
JS_DRAWN = """()=>{const r=V3.renderer,gl=r.getContext();if(gl.isContextLost())return {px:0,hud:'',running:V3.running,lost:true};
  V3.dirty=true;V3.loop();const w=gl.drawingBufferWidth,h=gl.drawingBufferHeight,buf=new Uint8Array(w*h*4);gl.readPixels(0,0,w,h,gl.RGBA,gl.UNSIGNED_BYTE,buf);
  let n=0;for(let i=3;i<buf.length;i+=4)if(buf[i]>0)n++;return {px:n,hud:document.getElementById('v3dhud').textContent,running:V3.running};}"""
JS_LOSE = """()=>new Promise(res=>{const cv=V3.renderer.domElement,gl=V3.renderer.getContext(),ext=gl.getExtension('WEBGL_lose_context');
  if(!ext)return res({lost:false,why:'no WEBGL_lose_context'});window.__lose=ext;
  if(gl.isContextLost())return res({lost:true,already:true});
  cv.addEventListener('webglcontextlost',e=>res({lost:gl.isContextLost(),prevented:e.defaultPrevented}),{once:true});ext.loseContext();
  setTimeout(()=>res({lost:gl.isContextLost(),timeout:true}),15000);})"""
JS_WORDS = """()=>{const out=[],fw=document.getElementById('firmware').textContent,tb=document.getElementById('fsmTable').textContent;
  ['section 0','open item','g++','should-fix','Independent review','CONCEPT','Review issues'].forEach(s=>{if(fw.includes(s))out.push('firmware: '+s);});
  ['ARM_AT_POSE','START','G <N>','"A"'].forEach(s=>{if(tb.includes(s))out.push('transitions: '+s);});
  const noI=[...document.querySelectorAll('.view > .fig')].filter(f=>!f.querySelector('.ibtn')).map(f=>f.id);if(noI.length)out.push('figures without an i note: '+noI.join(' '));
  if(/Option [1-5]\\b/.test(document.getElementById('concepts').textContent))out.push('generic option headers');
  return out;}"""

# smallest text anywhere in the page that is on screen, in screen pixels (svg text scaled by its transform)
JS_MINTEXT = r"""()=>{let min=99,where='';const walk=document.createTreeWalker(document.querySelector('.app'),NodeFilter.SHOW_TEXT);
  while(walk.nextNode()){const n=walk.currentNode;if(!n.textContent.trim())continue;const e=n.parentElement;if(!e||!e.getClientRects().length)continue;
    const r=e.getBoundingClientRect();if(r.width<1||r.height<1)continue;let st=getComputedStyle(e);if(st.visibility==='hidden'||st.opacity==='0')continue;
    let px=parseFloat(st.fontSize);if(e instanceof SVGElement){const m=e.getScreenCTM();if(m)px*=Math.hypot(m.a,m.b);}
    if(px<min){min=px;where=(e.closest('[id]')||{}).id+': '+n.textContent.trim().slice(0,24);}}
  return {min:Math.round(min*10)/10,where};}"""
JS_FIT = r"""()=>{const out=[],chk=[...document.querySelectorAll('#fitChecks .chk')];if(chk.length<8)out.push('checks '+chk.length);
  const vals=chk.map(c=>c.querySelector('small').textContent);if(!vals.some(v=>/\d\.\d+ mm/.test(v)))out.push('no computed gap in the checks: '+vals.join(' | '));
  if(!/nothing within/.test(vals[0])&&!D.fit3d)out.push('no fit3d data');if(!D.fit3d||!D.fit3d.pairs.length)out.push('fit3d has no pairs');
  const lb=[...document.querySelectorAll('#fit3d .lb')].filter(l=>!l.hidden&&/mm/.test(l.textContent));if(!lb.length)out.push('no gap label drawn in 3D');
  if(V3.mode!=='fit')out.push('mode '+V3.mode);if(!V3.overlay.children.length)out.push('nothing drawn');
  return {problems:out,checks:vals,labels:lb.slice(0,4).map(l=>l.textContent),findings:document.querySelectorAll('#fitFind tbody tr').length};}"""
# fit check, rework 3: one assertion group per change, each fails if that behaviour regresses
JS_FIT8 = r"""async()=>{const out=[],P=[],tick=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
  const own=k=>{let m;V3.parts[k].node.traverse(o=>{if(!m&&o.isMesh&&!o.userData.stencil)m=o.material;});return m===V3.parts[k].mat;};
  const cam=()=>V3.cam.position.toArray().concat(V3.ctl.target.toArray()).map(v=>Math.round(v*10)/10).join();
  const ov=()=>{const r={std:0,col:0,arrow:0};V3.overlay.traverse(o=>{if(o.isMesh&&o.material.vertexColors)r.col++;else if(o.isMesh&&o.material.isMeshStandardMaterial)r.std++;if(o.type==='ArrowHelper')r.arrow++;});return r;};
  const F=id=>FF.find(f=>f.id===id);
  /* what the card says: the visible text plus the tolerance list inside its closed details (the source file paths under it are not prose) */
  const said=()=>{const c=document.getElementById('fitCard');return c.innerText+' '+[...c.querySelectorAll('details li')].map(l=>l.textContent).join(' ');};
  /* 1 finding first: opens on the worst; choosing one sets its pose, its two parts solid, the rest faded, and moves the camera */
  if(!FF.length||FS.cur!==FF[0]&&!location.hash.includes(FF[0].id))out.push('1: did not open on the worst finding');
  if(FF[0]&&FF.some(f=>f.st==='fail')&&FF[0].st!=='fail')out.push('1: first finding is not the worst status');
  const notes=FF.filter(f=>f.st==='integration');
  if(!notes.length||notes.some(f=>f.title!=='Unverified arm clearance'))
    out.push('1: arm clearance note missing or mislabeled');
  if(notes.some(f=>FF.slice(FF.indexOf(f)+1).some(next=>next.st!=='integration')))
    out.push('1: arm clearance note sorted before audit findings');
  if(!document.querySelector('#fitPick optgroup[label="Unverified arm clearance"]'))
    out.push('1: arm clearance integration group missing');
  if(!document.querySelector('#fitList .integration-heading h3'))
    out.push('1: arm clearance list heading missing');
  /* the expected state comes from the audit (fit3d.json via the page data), not a literal; page-vs-audit drift is caught by tests/test_viewer_static.py:247-259 */
  const governed=F('fasteners-a-fasteners'),gc=governed&&governed.pair.governing_checks.find(c=>c.requirement_id==='B4');
  const gst=gc&&({'met':'pass','at risk':'risk'})[gc.status];
  if(!gc||governed.st!==gst||!governed.val.includes('B4 '+fmt(gc.measured_mm,3)+' mm '+gc.status)||
     !governed.why.includes(fmt(gc.measured_mm,3)+' mm, '+gc.status+', margin '+fmt(gc.margin_mm,4)+' mm')||(gc.status==='at risk'&&!/at risk|feature at risk/.test(governed.word)))
    out.push('1: B4 feature value and status missing from fit finding');
  const hh=F('horn-housing');if(!hh)out.push('1: no horn-housing finding');else{
    wholeView(false);await tick();const c0=cam(),s0=V3.fitSolid;selectFinding('horn-housing',{instant:true});await tick();
    const solid=Object.keys(V3.parts).filter(own).sort().join();
    if(cam()===c0)out.push('1: camera did not move');if(V3.theta!==hh.th||FST.th!==hh.th)out.push('1: jaw not at the worst pose '+V3.theta);
    if(solid!==[...hh.solid].sort().join())out.push('1: solid parts '+solid);if(s0)out.push('1: whole assembly kept a solid set');
    /* 2 the inset's dimension equals the finding's value, and the cut plane is drawn in 3D */
    const dt=(document.querySelector('#fitSec .dimt')||{}).textContent;if(dt!==fmt(hh.det.d,2)+' mm'||!document.querySelector('#fitCard .fv b').textContent.startsWith(fmt(hh.det.d,2)))out.push('2: inset dimension '+dt);
    if(!document.querySelector('#fitSec .sb')||!document.querySelector('#fitSec .skey'))out.push('2: inset has no scale bar or key');
    let frame=0;V3.overlay.traverse(o=>{if(o.isMesh&&o.geometry.type==='PlaneGeometry')frame++;});if(!frame)out.push('2: cut plane not shown in 3D');
    /* 3 nearness as colour, with a legend */
    if(!ov().col)out.push('3: no distance-coloured faces');if(document.getElementById('fitLegend').hidden||!/touching/.test(document.getElementById('fitLegend').textContent))out.push('3: no nearness legend');
    /* 4 section: capped, flips, snaps to an axis, slides */
    const capped=Object.values(FS.caps).filter(c=>c.cap.visible).length;if(!FS.cut.on||V3.clip!==FS.plane||capped<2)out.push('4: section not on and capped ('+capped+')');
    const n0=FS.plane.normal.clone(),k0=FS.plane.constant;document.getElementById('fitFlip').click();await tick();if(FS.plane.normal.dot(n0)>-0.99)out.push('4: flip did not reverse the cut');
    document.querySelector('#fit-3d [data-cut="x"]').click();await tick();if(Math.abs(Math.abs(FS.plane.normal.x)-1)>1e-6)out.push('4: X did not snap the cut');
    const k1=FS.plane.constant,r=document.getElementById('fitCutPos');r.value=3;r.dispatchEvent(new Event('input'));await tick();if(Math.abs(Math.abs(FS.plane.constant-k1)-3)>1e-6)out.push('4: offset did not slide the cut');
    const hs=hh.det.section;if(!hs)out.push('2: no section cut for horn-housing');
    document.querySelector('#fit-3d [data-cut="f"]').click();await tick();if(hs&&FS.plane.normal.distanceTo(vec(hs.m))>1e-6&&FS.plane.normal.distanceTo(vec(hs.m).negate())>1e-6)out.push('4: Finding did not snap to its plane');
    /* 5 the chart cursor follows the jaw, and scrubbing the chart moves the jaw */
    const j=document.getElementById('fitJaw');j.value=5;j.dispatchEvent(new Event('input'));await tick();
    if(![...document.querySelectorAll('#fitChart svg text')].some(t=>t.textContent==='5°'))out.push('5: chart cursor did not follow the jaw');
    const sv=document.querySelector('#fitChart svg'),bb=sv.getBoundingClientRect();
    sv.dispatchEvent(new PointerEvent('pointerdown',{clientX:bb.left+bb.width*0.9,clientY:bb.top+bb.height/2,pointerId:1,button:0,pointerType:'mouse',bubbles:true}));sv.dispatchEvent(new PointerEvent('pointerup',{pointerId:1,bubbles:true}));await tick();
    if(FST.th<=5||+j.value!==FST.th||V3.theta!==FST.th)out.push('5: scrubbing the chart did not move the jaw '+FST.th);
    if(!/Smallest/.test((document.getElementById('fitChartW')||{}).textContent||''))out.push('5: no worst point stated');
    /* a gap that does not change over the travel says so, and carries no worst-point dot */
    const flat=hh.pair.d.filter(v=>v!=null),isFlat=Math.max(...flat)-Math.min(...flat)<0.01;
    if(isFlat&&(!/the same over the whole travel/.test(document.getElementById('fitChartW').textContent)||document.querySelector('#fitChart svg circle')))out.push('5: a flat gap is charted with a worst point');
    /* 6 tolerance: nominal and worst case, at risk with the reason */
    const t=hh.tol,card=document.getElementById('fitCard').innerText;
    if(t.worst==null||!card.includes(fmt(t.worst,2)+' mm')||!/Worst case/.test(card))
      out.push('6: worst case not shown');
    const g=F('knuckle-a-knuckle-b');if(g){selectFinding(g.id,{instant:true});await tick();if(!/nominal only|Not stated/.test(document.getElementById('fitCard').innerText))out.push('6: a gap with no stated tolerance does not say so');
      /* gear teeth in mesh are not held to a running clearance, and no stack id shows on the card, open or closed */
      if(g.tol.req||document.querySelector('#fitSec .req')||/Running clearance|Required/.test(document.getElementById('fitCard').innerText))out.push('6: the gear mesh is held to a clearance nobody stated');
      if(/\bT\d{1,3}[A-Z]?\b/.test(said()))out.push('6: a stack id is visible on the gear card');}
    /* the explicit B18 value, its id and the measured gap travel together */
    selectFinding('horn-housing',{instant:true});
    await tick();
    const hornCard=document.getElementById('fitCard').innerText;
    if(!/Requirement B18/.test(hornCard)||!hornCard.includes(fmt(hh.req.minimum_clearance_mm,2)+' mm'))
      out.push('6: B18 requirement is missing');
    if(!hornCard.includes(fmt(hh.allowance,4)+' mm between-sample allowance'))
      out.push('6: B18 sampling allowance is rounded incorrectly');
    /* at risk says both halves in words: clear as drawn, not clear at worst case, and a negative worst case is named as an overlap */
    {const ct=document.getElementById('fitCard').innerText;if(hh.st==='risk'&&(!/Clear as drawn, not clear at worst case/.test(ct)||/leaving −/.test(ct)||(hh.tol.worst<0&&!/into each other/.test(ct))||!/at risk, not failing/.test(ct)))out.push('6: the at-risk card does not say what at risk means');}
    /* 1 where the card sits under the stage, the answer is repeated in one line above it; beside the stage it is not */
    {const an=document.getElementById('fitAns'),st3=document.getElementById('fit3d').getBoundingClientRect(),stacked=document.getElementById('fitCard').getBoundingClientRect().top>st3.bottom-1,ar=an.getBoundingClientRect();
      if(stacked!==(ar.height>0))out.push('1: answer line '+(stacked?'missing above a stacked stage':'shown beside the card'));
      if(stacked&&(ar.bottom>st3.top+1||!an.textContent.startsWith(hh.val)||!an.textContent.includes(hh.word)))out.push('1: answer line is not above the stage with the value and verdict');}
    /* 7 the locator: the whole gripper drawn small in the same canvas, on for a located finding and off for the whole assembly */
    {const lo=document.getElementById('fitLoc');FS.locDrawn=0;V3.dirty=true;V3.loop();if(lo.hidden||!FS.locDrawn)out.push('7: no locator picture for a located finding');
      if(lo.querySelector('canvas')||document.querySelectorAll('#fit3d canvas').length!==1)out.push('7: the locator is not drawn in the one shared canvas');
      wholeView(false);V3.dirty=true;V3.loop();if(!lo.hidden)out.push('7: locator left on for the whole assembly');selectFinding('horn-housing',{instant:true});await tick();}
    /* 7 a portrait stage frames the finding from further back, so the gripper is not cropped to a blob */
    {const a=V3.cam.aspect,dd=V3.cam.position.distanceTo(V3.ctl.target),want=55/Math.sqrt(Math.min(1,Math.max(0.36,a)));if(Math.abs(dd-want)>0.6)out.push('7: finding framed at '+dd.toFixed(1)+' mm, expected '+want.toFixed(1)+' for aspect '+a.toFixed(2));}}
  /* 7 getting around: next, presets, deep link */
  selectFinding(FF[0].id,{instant:true});await tick();document.dispatchEvent(new KeyboardEvent('keydown',{key:']',bubbles:true}));await tick();if(FS.cur!==FF[1])out.push('7: ] did not go to the next finding');
  preset('top');V3.anim&&V3.anim(1e9);V3.anim&&V3.anim(2e9);await tick();const d=V3.cam.position.clone().sub(V3.ctl.target).normalize();if(d.y<0.99)out.push('7: Top preset '+d.toArray().map(v=>v.toFixed(2)));
  location.hash='#fit-f-roll-wrist~j=20~r=90';await new Promise(r=>setTimeout(r,300));await tick();if(!FS.cur||FS.cur.id!=='roll-wrist'||FST.th!==20||FST.roll!==90)out.push('7: deep link did not restore finding and pose');
  {const ct=said(),req=F('roll-wrist').tol.req;if(/\bT\d{1,3}[A-Z]?\b|>=/.test(ct)||!new RegExp(req&&/ spec$/.test(req.name||'')?'Required':'Running clearance').test(ct))out.push('6: the roll card shows a stack id, a raw comparison, or incorrect clearance basis');
    /* the roll card answers what the gap does over a turn before it talks about tolerance */
    const wy=(document.querySelector('#fitCard .why')||{}).textContent||'';if(F('roll-wrist').det.const&&!/^Turning the wrist does not change this gap/.test(wy))out.push('5: the roll card does not lead with what the gap does over a turn');}
  if(!/^#fit-f-roll-wrist~/.test(linkHash().replace(/^/,'#')))out.push('7: link does not name the finding');
  /* 3 overlaps as solids, classed in words */
  const oe=FF.find(f=>f.kind==='overlap'),errors=OVL.filter(o=>o.cls==='error');
  if(errors.length&&!oe)out.push('3: unintended overlap has no finding');
  if(oe){
    selectFinding(oe.id,{instant:true});
    await tick();
    if(!ov().std||!/error|not intended/.test(document.getElementById('fitCard').innerText))
      out.push('3: overlap not drawn as a solid with its class');
  }
  const ob=F('overlaps-body');if(ob){selectFinding(ob.id,{instant:true});await tick();const n=OVL.filter(o=>o.theta===undefined&&o.mesh).length;if(ov().std<n)out.push('3: overlap solids '+ov().std+' of '+n);
    /* the not-intended overlap is buried in the housing, so it is drawn through the parts in front of it */
    let xr=0;
    V3.overlay.traverse(o=>{
      if(o.isMesh&&o.material.isMeshStandardMaterial&&o.material.depthTest===false&&o.material.color.getHex()===0xd62b1f)xr++;
    });
    if(errors.length&&!xr)out.push('3: the error overlap can be hidden inside the body');
    /* its label stands off on a leader, so the label does not cover the small red solid it names */
    let ld=0;
    V3.overlay.traverse(o=>{if(o.userData.leader)ld++;});
    if(errors.length&&!ld)out.push('3: the error overlap label sits on the overlap');
    /* the summary row is not a second failure for the same overlap */
    if(ob.st==='fail')out.push('3: the overlap summary counts the error twice');}
  /* 8 buildability: revision B gives every deck screw a clear insertion path */
  const deck=BLD.filter(b=>b.id.startsWith('deck_screw_'));if(deck.length!==4)out.push('8: expected four deck screw paths, got '+deck.length);
  if(deck.some(b=>!b.ok))out.push('8: a revision B deck screw path is blocked');
  const dp=BLD.find(b=>b.id==='dog_screw');if(!dp)out.push('8: no revision B dog set screw audit');else if(!dp.ok)out.push('8: dog set screw engagement does not match the CAD');
  return {problems:out,findings:FF.length};}"""
JS_BOMTOT = r"""()=>{const sel=document.getElementById('bomShow'),out={};for(const o of [...sel.options]){sel.value=o.value;sel.dispatchEvent(new Event('change'));
    const rows=[...document.querySelectorAll('#bomTable tbody tr')];const num=(t)=>parseFloat(t.replace(/[^\d.\-]/g,''));
    const g=rows.reduce((a,r)=>a+num(r.cells[5].textContent),0),u=rows.reduce((a,r)=>a+num(r.cells[6].textContent),0);
    out[o.value]={rows:rows.length,g:num(document.getElementById('bomG').textContent),u:num(document.getElementById('bomUsd').textContent),sumg:Math.round(g*10)/10,sumu:Math.round(u*100)/100};}
  sel.value='all';sel.dispatchEvent(new Event('change'));out.bom={g:D.bom.total.g,u:D.bom.total.usd};return out;}"""
JS_HOSTS = r"""(html)=>0"""


async def force_loss_restore(pg):
    """Force a WebGL context loss and ask for the restore; returns (drawn-before, loss result, restored)."""
    # a loss forced before the canvas has drawn, or before the extension exists, proves nothing: wait for both
    before = await pg.evaluate(JS_DRAWN)
    for _ in range(240):
        if before["px"] > 0:
            break
        await pg.wait_for_timeout(500)
        before = await pg.evaluate(JS_DRAWN)
    has_ext = False
    for _ in range(40):
        has_ext = await pg.evaluate("!!V3.renderer.getContext().getExtension('WEBGL_lose_context')")
        if has_ext:
            break
        await pg.wait_for_timeout(500)
    if before["px"] <= 0 or not has_ext:
        return before, {"lost": False, "could_not_tell": True,
                        "why": "canvas never drew" if before["px"] <= 0 else "no WEBGL_lose_context"}, False
    lost = await pg.evaluate(JS_LOSE)
    # restoreContext() only acts on a context the page has already seen lost, and under CPU load the loss event
    # and the restore each arrive late: wait for the page's own V3.lost, then ask again until it is back.
    restored = False
    try:
        await pg.wait_for_function("V3.lost&&V3.renderer.getContext().isContextLost()", timeout=15000)
        for _ in range(4):
            await pg.evaluate("window.__lose&&window.__lose.restoreContext()")
            try:
                await pg.wait_for_function("!V3.renderer.getContext().isContextLost()&&!V3.lost", timeout=10000)
                restored = True
                break
            except Exception:
                continue
    except Exception:
        pass
    return before, lost, restored


async def restore_only(pw, n, load):
    """--restore-only N [--load]: N forced loss/restore runs on the model view, optionally under CPU load (one busy loop per CPU)."""
    import multiprocessing as mp
    procs = [mp.Process(target=_spin, daemon=True) for _ in range(os.cpu_count() or 1)] if load else []
    for p in procs:
        p.start()
    ok = cnt = 0
    if procs:
        await asyncio.sleep(2)
        live = sum(1 for p in procs if p.is_alive() and p.exitcode is None)
        print(f"busy-loop children alive: {live} of {len(procs)}", flush=True)
        if live != len(procs):
            for p in procs:
                p.terminate()
            print(f"RESTORE could-not-tell: only {live} of {len(procs)} busy loops started")
            return False
    try:
        for i in range(n):
            b = await pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])
            pg = await b.new_page(viewport={"width": 1440, "height": 900})
            await pg.goto(SRC.as_uri(), wait_until="load", timeout=120000)
            await pg.wait_for_function("V3&&V3.ready", timeout=600000)
            await pg.wait_for_timeout(400)
            before, lost, restored = await force_loss_restore(pg)
            if lost.get("could_not_tell"):
                cnt += 1
                print(f"restore run {i + 1}: could-not-tell ({lost['why']}) px {before['px']}", flush=True)
                await b.close()
                continue
            await pg.wait_for_timeout(600)
            after = await pg.evaluate(JS_DRAWN)
            good = bool(restored and lost.get("lost") and after["px"] >= 2000 and after["px"] >= before["px"] * 0.8 and after["running"])
            ok += good
            print(f"restore run {i + 1}: {'pass' if good else 'FAIL'} lost={lost} px {before['px']}->{after['px']} running={after['running']}", flush=True)
            await b.close()
    finally:
        for p in procs:
            p.terminate()
    print(f"RESTORE {ok}/{n} {'under load' if load else 'no load'} ({len(procs)} busy loops){f', {cnt} could-not-tell' if cnt else ''}")
    return ok == n


def _spin():
    while True:
        pass


async def run(pw, wrap, w, hgt, scheme):
    name = f"{w}x{hgt} {scheme}"
    fails, errors, over, extra = [], [], [], {}
    b = await pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])
    pg = await b.new_page(viewport={"width": w, "height": hgt}, color_scheme=scheme)
    pg.on("console", lambda m: errors.append(m.type + ": " + m.text[:300]) if m.type in ("error", "warning") and "GL Driver Message" not in m.text and "CONTEXT_LOST_WEBGL" not in m.text else None)  # software-GL notices; a lost context is the browser's own warning, and the forced-loss check below proves the page recovers from it
    pg.on("pageerror", lambda e: errors.append("pageerror: " + str(e)[:300]))
    pg.on("requestfailed", lambda r: errors.append("request failed: " + r.url[:120]))

    async def check_over(where):
        d = await pg.evaluate(JS_OVER)
        if d > 0:
            over.append(f"{where} +{d}px")

    async def shot(tag):
        if SHOTS:
            SHOTS.mkdir(parents=True, exist_ok=True)
            await pg.screenshot(path=str(SHOTS / f"{tag}_{w}_{scheme}.png"), full_page=True)

    await pg.goto(wrap.as_uri(), wait_until="load", timeout=120000)
    await pg.evaluate("location.hash='#fit-findings'")
    await pg.wait_for_function("document.querySelectorAll('#fitFind tbody tr').length>0", timeout=600000)
    fit_rows = await pg.evaluate("[...document.querySelectorAll('#fitFind tbody tr')].map(r=>r.innerText.trim())")
    fit_text = "\n".join(fit_rows)
    required = await pg.evaluate("""() => F3.pairs.filter(p =>
      p.requirement_id && p.status !== 'governed elsewhere').map(p => ({
      title: (FF.find(f => f.id === (p.a+'-'+p.b).replaceAll('_','-'))||{}).title,
      status: p.status, id: p.requirement_id, required: fmt(p.required_mm,2)+' mm',
      measured: fmt(p.dmin,2)+' mm'}))""")
    for item in required:
        if not any(all(str(item[key]) in row for key in ("title", "status", "id", "required", "measured"))
                   for row in fit_rows):
            fails.append("required pair row disagrees with audit: " + str(item))
    pair_counts = await pg.evaluate("""() => ({stored:F3.pair_status_counts,
      recomputed:Object.fromEntries(['fail','at risk','met','governed elsewhere','no requirement'].map(s =>
        [s,F3.pairs.filter(p => {
          /* headline_status in viewer_build.py: a governed pair counts by its feature checks */
          const cs = (p.governing_checks||[]).map(c => c.status);
          const h = p.status !== 'governed elsewhere' ? p.status
            : (!cs.length || cs.some(c => c !== 'met' && c !== 'at risk')) ? 'fail'
            : cs.includes('at risk') ? 'at risk' : p.status;
          return h === s;}).length]))})""")
    if pair_counts["stored"] != pair_counts["recomputed"]:
        fails.append("fit headline pair counts disagree with rows")
    group_errors = await pg.evaluate("""() => FCK.filter(c => c.pairs && c.sum.w).filter(c => {
      const row = document.querySelector('#fitChecks [data-c="'+c.id+'"]');
      return !row || !row.textContent.includes(c.sum.w.status);
    }).map(c => c.id)""")
    if group_errors:
        fails.append("fit group status disagrees with its named pair: " + ", ".join(group_errors))
    await pg.evaluate("location.hash='#model'")
    visible = await pg.evaluate("document.body.innerText")
    if any(x in visible for x in ("Â°", "Â³", "âˆ’", "ï¿½", "�")):
        fails.append("visible text contains a character-decoding artifact")
    if len(fit_rows) != len(set(fit_rows)):
        fails.append("two finding rows have identical text")
    try:
        await pg.wait_for_function("!document.getElementById('v3dmsg')||document.getElementById('v3dmsg').hidden", timeout=60000)
        model3d = True
    except Exception:
        model3d = False
        fails.append("3D model did not finish loading: " + await pg.evaluate("(document.getElementById('v3dmsg')||{}).textContent||''"))
    views = await pg.evaluate("[...document.querySelectorAll('.view')].map(v=>v.id)")
    if views != EXPECT_VIEWS:
        fails.append(f"views {views}")
    if await pg.evaluate("document.querySelector('.view:not([hidden])').id") != "model":
        fails.append("first screen is not the model")
    nav = await pg.evaluate("[...document.querySelectorAll('#rail a.nav')].map(a=>a.getAttribute('href').slice(1))")
    if nav != EXPECT_VIEWS:
        fails.append(f"rail {nav}")
    counts = {"views": len(views), "figures": 0, "info notes": 0, "details": 0}
    for v in views:
        await pg.evaluate(f"location.hash='#{v}'")
        await pg.wait_for_timeout(350)
        if await pg.evaluate("[...document.querySelectorAll('.view:not([hidden])')].map(v=>v.id).join()") != v:
            fails.append(f"{v}: view not shown")
            continue
        if not await pg.evaluate(f"!!document.querySelector('#{v} > .vh h1') && document.querySelector('#{v} .verdict').innerText.trim().length>20"):
            fails.append(f"{v}: no title or verdict")
        if await pg.evaluate(f"!!document.querySelector('#{v} .err')"):
            fails.append(f"{v}: render error shown")
        figs = await pg.evaluate(f"[...document.querySelectorAll('#{v} > .fig')].map(f=>f.id)")
        for i, f in enumerate(figs):
            counts["figures"] += 1
            if len(figs) > 1:
                await pg.click(f"#tab-{f}")
                await pg.wait_for_timeout(150)
                if await pg.evaluate("location.hash") != "#" + f:
                    fails.append(f"{f}: tab did not set the anchor")
            r = await pg.evaluate(JS_FIG, f)
            if not r["ok"]:
                fails.append(f"{f}: {r['why']}")
            await check_over(f)
            tx = await pg.evaluate(JS_TEXT, f)
            if tx["min"] < extra.get("smallest chart label px", {"min": 99})["min"]:
                extra["smallest chart label px"] = tx
            if tx["min"] < 10.9:
                fails.append(f"{f}: chart label {tx['min']} px ({tx['where']})")
            if f == "concepts-scores":
                rows = await pg.evaluate(JS_ROWS)
                extra["scores rows"] = rows["rows"]
                fails.extend("scores table: " + p for p in rows["problems"])
                await pg.evaluate("window.scrollTo(0,0)")
            if f == "firmware-transitions":
                vc = await pg.evaluate(JS_VCUE)
                extra["transitions scroll cue"] = vc["cue"]
                if vc["scrolls"] and "rows" not in vc["cue"]:
                    fails.append("transitions table scrolls down without a cue")
            await shot(v if i == 0 else f)
            if f == "firmware-states":
                fsm = await pg.evaluate(JS_FSM)
                extra["state diagram"] = fsm
                fails.extend("state diagram: " + p for p in fsm["problems"])
                if fsm["mode"] != ("tall" if w <= 900 else "wide") or fsm["label_px"] < 11:
                    fails.append(f"state diagram: {fsm['mode']} layout, labels {fsm['label_px']} px")
            if f == "drawings-housing":
                await pg.click(f"#{f} button[data-z='in']")
                z = await pg.evaluate(f"(()=>{{const s=document.querySelector('#{f} .sheet');return [s.classList.contains('zoomed'),s.scrollWidth>s.clientWidth+20,document.querySelector('#{f} .zlevel').textContent];}})()")
                if z != [True, True, "150 %"]:
                    fails.append(f"sheet zoom in: {z}")
                await shot("drawings_zoomed")
                await pg.click(f"#{f} button[data-z='fit']")
                if await pg.evaluate(f"document.querySelector('#{f} .sheet').classList.contains('zoomed')"):
                    fails.append("sheet did not return to fit")
            if await pg.evaluate(f"!!document.querySelector('#{f} .ibtn')"):
                counts["info notes"] += 1
                await pg.click(f"#{f} .ibtn")
                if await pg.evaluate(f"document.querySelector('#{f} .pop').hidden"):
                    fails.append(f"{f}: note did not open")
                await check_over(f + " note")
                await pg.keyboard.press("Escape")
                if not await pg.evaluate(f"document.querySelector('#{f} .pop').hidden"):
                    fails.append(f"{f}: Escape did not close the note")
            await pg.click(f"#{f} .fullb")
            await pg.wait_for_timeout(120)
            if not await pg.evaluate(f"document.getElementById('{f}').classList.contains('is-full')"):
                fails.append(f"{f}: full screen did not open")
            await check_over(f + " full screen")
            if i == 0 and v in ("model", "drawings", "torque"):
                await shot(v + "_full")
            await pg.keyboard.press("Escape")
            if await pg.evaluate(f"document.getElementById('{f}').classList.contains('is-full')"):
                fails.append(f"{f}: Escape did not leave full screen")
        dets = await pg.evaluate(f"[...document.querySelectorAll('#{v} > .detail')].map(d=>d.id)")
        if sorted(dets) != sorted([v + "-method", v + "-sources"]) and v != "open":
            fails.append(f"{v}: detail levels {dets}")
        for d in dets:
            counts["details"] += 1
            sel = f".depth button[aria-controls='{d}']"
            await pg.click(sel)
            if await pg.evaluate(f"document.getElementById('{d}').hidden") or await pg.evaluate("location.hash") != "#" + d:
                fails.append(f"{d}: did not open")
            if await pg.evaluate(f"document.getElementById('{d}').innerText.trim().length") < 40:
                fails.append(f"{d}: empty")
            await check_over(d)
            if d.endswith("-method") and v in ("mass", "firmware"):
                await pg.mouse.move(2, 2)
                await pg.wait_for_timeout(600)  # let the button's colour transition settle before measuring
                c = await pg.evaluate(JS_CONTRAST, sel)
                extra[f"open method button contrast, {v}"] = c
                if c["ratio"] < 4.5:
                    fails.append(f"{d}: open button contrast {c['ratio']}")
                await shot(v + "_method")
            await pg.click(sel)
            if not await pg.evaluate(f"document.getElementById('{d}').hidden"):
                fails.append(f"{d}: did not close")
    # keyboard: arrow keys move between figure tabs
    await pg.evaluate("location.hash='#mass'")
    await pg.wait_for_timeout(200)
    await pg.focus("#tab-mass-payload")
    await pg.keyboard.press("ArrowRight")
    if await pg.evaluate("document.getElementById('mass-rollup').hidden"):
        fails.append("arrow key did not change the figure tab")
    # place is kept when leaving a view and coming back
    await pg.evaluate("location.hash='#bom'")
    await pg.wait_for_timeout(200)
    await pg.evaluate("location.hash='#mass'")
    await pg.wait_for_timeout(200)
    if await pg.evaluate("document.getElementById('mass-rollup').hidden"):
        fails.append("figure choice was lost after leaving the view")
    # deep links
    for href, view, target in LINKS:
        await pg.evaluate(f"location.hash='{href}'")
        await pg.wait_for_timeout(300)
        cur = await pg.evaluate("document.querySelector('.view:not([hidden])').id")
        ok = cur == view
        if ok and target:
            ok = await pg.evaluate(f"(()=>{{const e=document.getElementById('{target}');return !!e&&!e.hidden&&e.getBoundingClientRect().height>0;}})()")
        if not ok:
            fails.append(f"link {href} did not reach {target or view}")
    # narrow screens: the menu opens and reaches a view
    if w <= 900:
        await pg.evaluate("location.hash='#model'")
        await pg.click("#menuBtn")
        await shot("menu")
        if not await pg.evaluate("document.getElementById('rail').classList.contains('open')"):
            fails.append("menu did not open")
        await pg.click("#rail a.nav[href='#gears']")
        await pg.wait_for_timeout(250)
        if await pg.evaluate("document.querySelector('.view:not([hidden])').id") != "gears" or await pg.evaluate("document.getElementById('rail').classList.contains('open')"):
            fails.append("menu link did not open its view and close the menu")
    counts.update(await pg.evaluate("""({tables:document.querySelectorAll('main table').length,charts:document.querySelectorAll('main .chart > svg').length,
      controls:document.querySelectorAll('main button,main select,main input').length,images:document.querySelectorAll('main img').length,
      codes:(document.querySelector('main').innerText.match(/\\b(?:R|D|A|T|DB|FM)-?\\d{1,3}\\b/g)||[]).slice(0,12)})"""))
    if counts["codes"]:
        fails.append(f"internal codes visible: {counts['codes']}")
    if await pg.evaluate("!!document.getElementById('statusList')||!!document.querySelector('.chain')"):
        fails.append("a removed block is back (status list or torque chain)")
    # 3D model: force the graphics context away and back, then the model must draw again
    if model3d:
        await pg.evaluate("location.hash='#model'")
        await pg.wait_for_timeout(400)
        before, lost, restored = await force_loss_restore(pg)
        await pg.wait_for_timeout(600)
        after = await pg.evaluate(JS_DRAWN)
        extra["3d after a forced context loss"] = {"lost": lost, "drawn pixels before": before["px"], "after": after["px"], "hud": after["hud"], "loop running": after["running"]}
        if not lost.get("lost") or after["px"] < 2000 or after["px"] < before["px"] * 0.8 or "jaw" not in after["hud"] or not after["running"]:
            fails.append(f"3D model did not redraw after a forced context loss: {lost} {before} {after}")
    # fit check in 3D: loads, shows the computed gaps
    await pg.evaluate("location.hash='#fit-3d'")
    try:
        await pg.wait_for_function("V3.ready&&V3.mode==='fit'", timeout=600000)
    except Exception:
        pass
    await pg.evaluate("selectFinding('horn-housing',{instant:true})")
    await pg.wait_for_timeout(500)
    fr = await pg.evaluate(JS_FIT)
    extra["fit check 3D"] = {k: fr[k] for k in ("checks", "labels", "findings")}
    fails.extend("fit check: " + p for p in fr["problems"])
    await pg.fill("#fitJaw", "-11") if False else await pg.evaluate("(()=>{const r=document.getElementById('fitJaw');r.value=-11;r.dispatchEvent(new Event('input'));})()")
    await pg.wait_for_timeout(300)
    await shot("fit3d_jaw-11")
    await check_over("fit 3D")
    if model3d:
        try:
            await pg.evaluate("selectFinding(FF[0].id,{instant:true})")
            f8 = await pg.evaluate(JS_FIT8)
        except Exception as e:  # a script error in the checks is a failure, not a crash
            f8 = {"problems": ["the eight checks threw: " + str(e).splitlines()[0]]}
        extra["fit check, eight changes"] = f8
        fails.extend("fit check: " + p for p in f8["problems"])
        await check_over("fit 3D after the eight checks")
        # capability 4, drag: the section arrow's head mesh is grabbed with a real mouse and slides the cut along its normal
        try:
            await pg.evaluate("""async()=>{selectFinding('horn-housing',{instant:true});if(!FS.cut.on)toggleCut();
              document.getElementById('fitCutPos').value=0;document.getElementById('fitCutPos').dispatchEvent(new Event('input'));
              document.getElementById('v3d').scrollIntoView({block:'center'});
              await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));}""")
            await pg.wait_for_timeout(300)
            hd = await pg.evaluate("""()=>{const r=V3.cv.getBoundingClientRect(),a=FS.cutO.clone(),n=FS.plane.normal,L=Math.max(4,V3.cam.position.distanceTo(FS.cutO)*0.12);
              const head=a.clone().addScaledVector(n,L-Math.min(4,L*0.25)/2).project(V3.cam),o=a.clone().project(V3.cam),tip=a.clone().add(n).project(V3.cam);
              return {x:r.left+(head.x+1)/2*r.width,y:r.top+(1-head.y)/2*r.height,dx:(tip.x-o.x)*r.width/2,dy:-(tip.y-o.y)*r.height/2,off:FS.cut.off};}""")
            ln = (hd["dx"] ** 2 + hd["dy"] ** 2) ** 0.5 or 1
            await pg.mouse.move(hd["x"], hd["y"])
            await pg.mouse.down()
            await pg.mouse.move(hd["x"] + hd["dx"] / ln * 40, hd["y"] + hd["dy"] / ln * 40, steps=6)
            await pg.mouse.up()
            off = await pg.evaluate("FS.cut.off")
            if abs(off - hd["off"]) < 0.05:
                fails.append(f"fit check: dragging the section arrow did not move the cut ({hd['off']} to {off})")
            extra["fit section drag"] = {"offset before": hd["off"], "after": off}
        except Exception as e:
            fails.append("fit check: section drag step threw: " + str(e).splitlines()[0])
        # a drag from the canvas centre, away from the arrow's head, orbits: the cut stays put and the camera moves
        try:
            cen = await pg.evaluate("""()=>{const r=V3.cv.getBoundingClientRect(),a=FS.cutO.clone(),n=FS.plane.normal,L=Math.max(4,V3.cam.position.distanceTo(FS.cutO)*0.12);
              const head=a.clone().addScaledVector(n,L).project(V3.cam);
              return {x:r.left+r.width/2,y:r.top+r.height/2,gap:Math.hypot(r.left+(head.x+1)/2*r.width-(r.left+r.width/2),r.top+(1-head.y)/2*r.height-(r.top+r.height/2)),off:FS.cut.off,cam:V3.cam.position.toArray()};}""")
            if cen["gap"] <= 18:
                fails.append(f"fit check: the arrow head sits at the canvas centre, so the orbit step proves nothing ({cen['gap']:.0f} px)")
            await pg.mouse.move(cen["x"], cen["y"])
            await pg.mouse.down()
            await pg.mouse.move(cen["x"] + 60, cen["y"] + 30, steps=6)
            await pg.mouse.up()
            off = await pg.evaluate("FS.cut.off")
            cam = await pg.evaluate("V3.cam.position.toArray()")
            extra["fit canvas-centre drag"] = {"offset before": cen["off"], "after": off, "camera moved": cam != cen["cam"]}
            if abs(off - cen["off"]) > 1e-9:
                fails.append(f"fit check: a drag from the canvas centre moved the section ({cen['off']} to {off})")
            if cam == cen["cam"]:
                fails.append("fit check: a drag from the canvas centre did not orbit the camera")
        except Exception as e:
            fails.append("fit check: canvas-centre drag step threw: " + str(e).splitlines()[0])
    # every BOM row opens its part
    await pg.evaluate("location.hash='#parts-browse'")
    await pg.wait_for_timeout(600)
    keys = await pg.evaluate("[...document.querySelectorAll('#partsList .prow2')].map(b=>b.dataset.k)")
    opened = 0
    for k in keys:
        await pg.click(f"#partsList .prow2[data-k='{k}']")
        await pg.wait_for_timeout(120)
        r = await pg.evaluate(f"""(()=>{{const b=document.querySelector('#partsList .prow2[data-k="{k}"]');const r=D.bomx.find(x=>rowKey(x)==='{k}');
          return {{cur:PARTS_CUR,current:b.getAttribute('aria-current'),title:document.querySelector('#partInfo h2').textContent,mode:V3.mode,sel:V3.sel,part:r.part,
            items:V3.selItems?V3.selItems.size:0,qty:r.qty,kind:r.kind,vis:V3.ready?Object.values(V3.parts).filter(p=>p.node.visible).length:-1}}}})()""")
        ok = r["cur"] == k and r["current"] == "true" and r["title"] and (not model3d or (r["mode"] == "part" and (r["sel"] or not r["part"]))) and (r["kind"] != "fastener" or not model3d or r["items"] == r["qty"])
        if ok:
            opened += 1
        else:
            fails.append(f"part row {k} did not open: {r}")
    extra["BOM rows that open their part"] = f"{opened} of {len(keys)}"
    if not keys:
        fails.append("no part rows")
    await shot("parts_open")
    if model3d:
        th = await pg.evaluate("Object.keys(THUMB).length")
        extra["part thumbnails drawn from the 3D model"] = th
        if th < 16:
            fails.append(f"thumbnails: {th}")
    await pg.click("#ptabDraw") if await pg.evaluate("!document.getElementById('ptabDraw').disabled") else None
    # list only: totals equal the BOM
    await pg.click("#tab-parts-list")
    await pg.wait_for_timeout(200)
    tot = await pg.evaluate(JS_BOMTOT)
    extra["list-only totals"] = {k: v for k, v in tot.items() if k in ("all", "bom")}
    if abs(tot["all"]["g"] - tot["bom"]["g"]) > 0.051 or abs(tot["all"]["u"] - tot["bom"]["u"]) > 0.005:
        fails.append(f"list-only totals {tot['all']} differ from the BOM {tot['bom']}")
    for k, v in tot.items():
        if k != "bom" and (abs(v["g"] - v["sumg"]) > 0.11 or abs(v["u"] - v["sumu"]) > 0.011):
            fails.append(f"list-only {k}: total {v} is not the sum of its rows")
    await shot("parts_list")
    # one selection, highlighted everywhere: from each place a part can be chosen
    ORIG = [("model tree", "#model", "#plist .prow[data-part='knuckle_a'] .nm", "knuckle_a"),
            ("BOM row", "#parts-list", "#bomTable tbody tr[data-part='housing'] td:nth-child(2)", "housing"),
            ("drawing", "#drawings-wrist-mount", "#drawings-wrist-mount a[data-part='wrist_mount']", "wrist_mount"),
            ("fit check", "#fit-findings", "#fitFind tbody tr[data-part] td:first-child", None),
            ("mass budget row", "#mass-rollup", "#rollTable tbody tr[data-part^='servo'] td:first-child", "servo"),
            ("tolerance stack", "#tolerances-stacks", "#tolTable tbody tr[data-part^='finger_a'] td:nth-child(2)", "finger_a"),
            ("assembly step", "#assembly-steps", "#asmSteps button.step[data-part^='front_plate']", "front_plate")]
    xh = {}
    for oname, href, sel, want in ORIG:
        await pg.evaluate(f"location.hash='{href}'")
        await pg.wait_for_timeout(500)
        if not await pg.evaluate(f"!!document.querySelector(\"{sel}\")"):
            if oname == "fit check" and await pg.evaluate("!document.querySelector('#fitFind tbody tr[data-part]')"):
                xh[oname] = "no findings to select"
                continue
            fails.append(f"cross-highlight: no {oname} origin ({sel})")
            continue
        if want is None:
            want = await pg.evaluate(f"document.querySelector(\"{sel}\").closest('[data-part]').dataset.part.split(' ')[0]")
        await pg.click(sel)
        await pg.wait_for_timeout(400)
        r = await pg.evaluate(f"""(()=>{{const k='{want}';const lit=[...document.querySelectorAll('.selp')].map(e=>(e.closest('.view')||{{}}).id).filter(Boolean);
          return {{sel:V3.sel,bar:!document.getElementById('selbar').hidden,name:document.getElementById('selName').textContent,open:document.getElementById('selOpen').getAttribute('href'),
            views:[...new Set(lit)],emissive:V3.ready&&V3.parts[k]?V3.parts[k].mat.emissiveIntensity:null}}}})()""")
        xh[oname] = r["views"]
        if r["sel"] != want or not r["bar"] or not r["name"] or len(r["views"]) < 2:
            fails.append(f"cross-highlight from {oname}: {r}")
    extra["cross-highlight, views lit"] = xh
    # assembly: play every step, end in the assembled pose
    if model3d:
        await pg.evaluate("location.hash='#assembly-steps'")
        await pg.wait_for_timeout(600)
        await pg.evaluate("V3.asmSeen=new Set();AS.t=0")
        await pg.click("#asmPlay")
        # drive the page's own play loop with a fast clock, 250 ms per tick, instead of waiting on software-rendered frames
        await pg.evaluate("(()=>{let t=AS.last,n=0;while(AS.playing&&V3.anim&&n<5000){t+=250;V3.anim(t);n++;}return n;})()")
        a = await pg.evaluate("""(()=>{const offs=Object.values(V3.offset||{}).flat().filter(v=>Math.abs(v)>1e-6).length;
          const items=Object.values(V3.items).flat().filter(o=>!o.visible||(o.userData.p0&&o.position.distanceTo(o.userData.p0)>1e-6)).length;
          return {steps:ASM.steps.length,seen:V3.asmSeen?V3.asmSeen.size:0,done:!!(V3.asmState&&V3.asmState.done),moved:offs,itemsOff:items,hidden:V3.asmHide?V3.asmHide.size:-1,theta:V3.theta};})()""")
        extra["assembly played"] = a
        if a["seen"] != a["steps"] or not a["done"] or a["moved"] or a["itemsOff"] or a["hidden"] or a["theta"] != 0:
            fails.append(f"assembly did not play every step into the assembled pose: {a}")
        await shot("assembly_end")
        # reduced motion: a step jumps into place
        await pg.emulate_media(reduced_motion="reduce")
        await pg.click("#asmSteps button.step[data-i='9']")
        await pg.wait_for_timeout(150)
        jump = await pg.evaluate("({t:AS.t,end:9*STEP_T()+AS.dur,offs:Object.values(V3.offset||{}).flat().filter(v=>Math.abs(v)>1e-6).length})")
        if abs(jump["t"] - jump["end"]) > 1 or jump["offs"]:
            fails.append(f"reduced motion: step did not jump into place {jump}")
        await pg.emulate_media(reduced_motion="no-preference")
    # no text under 11 px on any view
    small = {"min": 99}
    for v in EXPECT_VIEWS:
        await pg.evaluate(f"location.hash='#{v}'")
        await pg.wait_for_timeout(250)
        t = await pg.evaluate(JS_MINTEXT)
        if t["min"] < small["min"]:
            small = t
        await check_over(v + " again")
    extra["smallest text px"] = small
    if small["min"] < 11:
        fails.append(f"text under 11 px: {small}")
    fails.extend(await pg.evaluate(JS_WORDS))
    num = await pg.evaluate(JS_NUM)
    extra["numeric cells in the sans face with tabular figures"] = num["cells"]
    if num["bad"] or not num["cells"]:
        fails.append(f"numeric cells: {num['bad']}")
    # selects: no selected label is cut off, and the finding picker names its choice in full under the bar
    # the fit view, with the longest finding label picked: the label the reader sees must fit, and the reading must name it
    await pg.evaluate("location.hash='#fit-3d'")
    await pg.wait_for_timeout(1200)
    await pg.evaluate("selectFinding([...FF].sort((a,b)=>(b.title+b.val).length-(a.title+a.val).length)[0].id,{instant:true})")
    await pg.wait_for_timeout(300)
    rd = await pg.evaluate("(()=>{const r=document.getElementById('fitPickRead'),s=document.getElementById('fitPick');return r&&s?{read:r.textContent,pick:s.options[s.selectedIndex]?.text||'',shown:r.offsetParent!==null,fits:r.scrollWidth<=r.clientWidth+1}:null})()")
    if not rd or not rd["shown"] or not rd["fits"] or not rd["pick"] or rd["pick"] not in rd["read"]:
        fails.append(f"finding picker does not name its choice: {rd}")
    for x in await pg.evaluate(JS_CLIP):
        fails.append(f"select label clipped in fit: {x}")
    for vid in await pg.evaluate("[...document.querySelectorAll('section.view')].map(s => s.id).filter(v => v !== 'fit')"):
        await pg.evaluate(f"location.hash='#{vid}'")
        await pg.wait_for_timeout(300)
        for x in await pg.evaluate(JS_CLIP):
            fails.append(f"select label clipped in {vid}: {x}")
    hud = await pg.evaluate("(document.getElementById('v3dhud')||{}).textContent||''")
    await b.close()
    return {"size": name, "3d": model3d, "hud": hud, "counts": counts, "checks": extra, "console": errors, "overflow": over, "fails": fails}


async def main():
    bad = 0
    html = SRC.read_text(encoding="utf-8")
    import re
    mb = len(html.encode("utf-8")) / 1e6
    urls = re.findall(r'<script[^>]+src="([^"]+)"', html) + re.findall(r'"(https?://[^"]+)"', (re.search(r'<script type="importmap">(.*?)</script>', html, re.S) or [None, ""])[1] if re.search(r'<script type="importmap">', html) else "")
    okhost = re.compile(r"^https://(cdnjs\.cloudflare\.com/|cdn\.jsdelivr\.net/npm/|unpkg\.com/)[^/@]+@\d+\.\d+\.\d+/")
    badurl = [u for u in urls if not okhost.match(u)]
    tags = [t for t in ("<!doctype", "<html", "<head", "<body") if re.search(t + r"[\s>]", html.lower())]
    print(json.dumps({"file MB": round(mb, 2), "script URLs": urls, "bad script URLs": badurl, "document tags": tags}))
    bad += (mb >= 14) + len(badurl) + len(tags) + (0 if urls else 1)
    async with async_playwright() as pw:
        if "--restore-only" in sys.argv:
            sys.exit(0 if await restore_only(pw, int(sys.argv[sys.argv.index("--restore-only") + 1]), "--load" in sys.argv) else 1)
        for w, hgt, sc in SIZES:
            r = await run(pw, SRC, w, hgt, sc)
            bad += len(r["console"]) + len(r["overflow"]) + len(r["fails"]) + (0 if r["3d"] else 1)
            print(json.dumps(r, ensure_ascii=True))
    print("RESULT", "pass" if not bad else f"{bad} problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":  # Windows spawns children that re-import this module; they must not start the test again
    asyncio.run(main())
