#!/usr/bin/env python3
"""Build standalone prototype pages with the GLB embedded as base64. Run: python3 make.py"""
import base64, pathlib
here = pathlib.Path(__file__).resolve().parent
glb = here.parent.parent / "out" / "web" / "gripper_closed.glb"
b64 = base64.b64encode(glb.read_bytes()).decode()
THREE_V, MV_V, BAB_V = "0.186.1", "4.3.1", "9.28.0"
CDN = "https://cdn.jsdelivr.net/npm"
setup = (here / "three_setup.js").read_text(encoding="utf-8")
setup_fn = setup[setup.index("function setupRealism"):]

CSS = """:root{--bg:#eef0f3;--fg:#1c2026}@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15181d;--fg:#e8eaed}}
:root[data-theme=dark]{--bg:#15181d;--fg:#e8eaed}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:13px system-ui,sans-serif}
#v{position:fixed;inset:0;width:100%;height:100%;display:block}
#hud{position:fixed;left:16px;top:12px;opacity:.7}"""

BENCH = """
window.__bench = (n, step) => new Promise(res => { const t=[]; let last=performance.now(), i=0;
  (function f(now){ t.push(now-last); last=now; step(i); if(++i<n+1) requestAnimationFrame(f); else { t.shift(); t.sort((a,b)=>a-b); res({median:t[t.length>>1], mean:t.reduce((a,b)=>a+b)/t.length}); } })(performance.now()); });
"""

three = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gripper three.js proto</title><style>{CSS}</style>
<script type="importmap">{{"imports":{{"three":"{CDN}/three@{THREE_V}/build/three.module.js","three/addons/":"{CDN}/three@{THREE_V}/examples/jsm/"}}}}</script>
</head><body><canvas id="v"></canvas><div id="hud">three.js {THREE_V} | 1/2/3 quality</div>
<script type="module">
import * as THREE from 'three';
import {{GLTFLoader}} from 'three/addons/loaders/GLTFLoader.js';
import {{OrbitControls}} from 'three/addons/controls/OrbitControls.js';
import {{RoomEnvironment}} from 'three/addons/environments/RoomEnvironment.js';
import {{EffectComposer}} from 'three/addons/postprocessing/EffectComposer.js';
import {{RenderPass}} from 'three/addons/postprocessing/RenderPass.js';
import {{GTAOPass}} from 'three/addons/postprocessing/GTAOPass.js';
import {{OutputPass}} from 'three/addons/postprocessing/OutputPass.js';
{setup_fn}
const addons = {{RoomEnvironment, EffectComposer, RenderPass, GTAOPass, OutputPass}};
const canvas = document.getElementById('v');
const renderer = new THREE.WebGLRenderer({{canvas, antialias: true}});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
const scene = new THREE.Scene();
scene.background = new THREE.Color(dark ? 0x15181d : 0xeef0f3);
const q = new URLSearchParams(location.search).get('q');
const camera = new THREE.PerspectiveCamera(30, 1, 1, 3000);
const R = setupRealism(THREE, addons, renderer, scene, camera);
if (q !== null) R.setQuality(+q);
const controls = new OrbitControls(camera, canvas); controls.enableDamping = false;
function size() {{ const w = innerWidth, h = innerHeight; camera.aspect = w / h; camera.updateProjectionMatrix(); R.resize(w, h); }}
addEventListener('resize', size); size();
const b64 = "{b64}";
const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0)).buffer;
new GLTFLoader().parse(bin, '', gltf => {{
  scene.add(gltf.scene);
  const f = R.fit(gltf.scene);
  controls.target.copy(f.center);
  camera.position.copy(f.center).add(new THREE.Vector3(0.9, 0.55, 1.0).normalize().multiplyScalar(f.size * 1.5));
  controls.update();
  window.__R = R; window.__scene = scene; window.__camera = camera; window.__controls = controls;
  let prev = performance.now();
  (function loop(now) {{ requestAnimationFrame(loop); R.monitor(now - prev); prev = now; controls.update(); R.render();
    if (!window.__firstFrame) window.__firstFrame = performance.now(); }})(prev);
}});
addEventListener('keydown', e => {{ if ('123'.includes(e.key)) R.setQuality(+e.key - 1); }});
{BENCH}
window.__orbit = (n) => window.__bench(n, i => {{ controls.autoRotate = false; const o = camera.position.clone().sub(controls.target); o.applyAxisAngle(new THREE.Vector3(0,1,0), 0.03); camera.position.copy(controls.target).add(o); camera.lookAt(controls.target); }});
</script></body></html>"""
(here / "three.html").write_text(three, encoding="utf-8", newline="\n")

mv = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gripper model-viewer proto</title><style>{CSS} model-viewer{{position:fixed;inset:0;width:100%;height:100%;--poster-color:transparent;background:var(--bg)}}</style>
<script type="module" src="{CDN}/@google/model-viewer@{MV_V}/dist/model-viewer.min.js"></script>
</head><body><model-viewer id="m" camera-controls environment-image="neutral" shadow-intensity="1" shadow-softness="0.8" tone-mapping="aces" exposure="1" camera-orbit="40deg 70deg auto" interaction-prompt="none"></model-viewer>
<div id="hud">model-viewer {MV_V}</div>
<script>
const m = document.getElementById('m');
m.src = URL.createObjectURL(new Blob([Uint8Array.from(atob("{b64}"), c => c.charCodeAt(0))], {{type: 'model/gltf-binary'}}));
m.addEventListener('load', () => requestAnimationFrame(() => requestAnimationFrame(() => {{ window.__firstFrame = performance.now(); }})));
{BENCH}
window.__orbit = (n) => window.__bench(n, i => {{ m.cameraOrbit = (40 + i * 1.7) + 'deg 70deg auto'; m.jumpCameraToGoal && m.jumpCameraToGoal(); }});
</script></body></html>"""
(here / "modelviewer.html").write_text(mv, encoding="utf-8", newline="\n")

bab = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gripper Babylon proto</title><style>{CSS}</style>
<script src="{CDN}/babylonjs@{BAB_V}/babylon.js"></script>
<script src="{CDN}/babylonjs-loaders@{BAB_V}/babylonjs.loaders.min.js"></script>
<script src="{CDN}/babylonjs-materials@{BAB_V}/babylonjs.materials.min.js"></script>
</head><body><canvas id="v"></canvas><div id="hud">Babylon.js {BAB_V}</div>
<script>
const canvas = document.getElementById('v');
const engine = new BABYLON.Engine(canvas, true, {{preserveDrawingBuffer: false}});
const scene = new BABYLON.Scene(engine);
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
scene.clearColor = dark ? new BABYLON.Color4(0.082, 0.094, 0.114, 1) : new BABYLON.Color4(0.933, 0.941, 0.953, 1);
const cam = new BABYLON.ArcRotateCamera('c', 0.9, 1.2, 250, BABYLON.Vector3.Zero(), scene); cam.attachControl(canvas, true); cam.minZ = 1; cam.fov = 0.52;
const hemi = new BABYLON.HemisphericLight('h', new BABYLON.Vector3(0.2, 1, 0.3), scene); hemi.intensity = 0.8; hemi.groundColor = new BABYLON.Color3(0.35,0.35,0.4);
const dl = new BABYLON.DirectionalLight('d', new BABYLON.Vector3(-0.5, -1, -0.6), scene); dl.intensity = 2.2;
// No env texture: Babylon's createDefaultEnvironment/.env files load from assets.babylonjs.com, not an allowed host.
const bin = Uint8Array.from(atob("{b64}"), c => c.charCodeAt(0));
const url = URL.createObjectURL(new Blob([bin], {{type: 'model/gltf-binary'}}));
BABYLON.SceneLoader.ImportMesh('', '', url, scene, meshes => {{
  const ext = scene.getWorldExtends(); const c = ext.min.add(ext.max).scale(0.5); const sz = ext.max.subtract(ext.min).length();
  cam.target = c; cam.radius = sz * 2.2; dl.position = c.add(new BABYLON.Vector3(sz, sz * 1.5, sz));
  const sg = new BABYLON.ShadowGenerator(2048, dl); sg.useBlurExponentialShadowMap = true; sg.blurKernel = 24; sg.bias = 0.0005;
  const col = {{knuckle:[0.16,0.17,0.19,0.62,0],finger:[0.89,0.45,0.1,0.55,0],servo:[0.08,0.08,0.09,0.48,0],horn:[0.79,0.8,0.82,0.38,1],fasteners:[0.73,0.74,0.77,0.35,1]}};
  meshes.forEach(m => {{ if (!m.getTotalVertices || !m.getTotalVertices()) return; sg.addShadowCaster(m); m.receiveShadows = true;
    const k = Object.keys(col).find(p => m.name.startsWith(p) || (m.parent && m.parent.name.startsWith(p)));
    if (k && m.material) {{ const [r,g,b,ro,me] = col[k]; m.material.albedoColor = new BABYLON.Color3(r,g,b); m.material.roughness = ro; m.material.metallic = me; }} }});
  const gr = BABYLON.MeshBuilder.CreateGround('g', {{width: 1000, height: 1000}}, scene); gr.position = new BABYLON.Vector3(c.x, ext.min.y - 0.5, c.z);
  const gm = new BABYLON.ShadowOnlyMaterial('gm', scene); gm.activeLight = dl; gm.alpha = 0.3; gr.material = gm; gr.receiveShadows = true;
  scene.imageProcessingConfiguration.toneMappingEnabled = true; scene.imageProcessingConfiguration.toneMappingType = BABYLON.ImageProcessingConfiguration.TONEMAPPING_ACES;
  const pipe = new BABYLON.SSAO2RenderingPipeline('ssao', scene, {{ssaoRatio: 0.5, blurRatio: 1}}, [cam]); pipe.radius = 6; pipe.totalStrength = 1; pipe.expensiveBlur = false;
  engine.runRenderLoop(() => {{ scene.render(); if (!window.__firstFrame) window.__firstFrame = performance.now(); }});
}}, null, (s, m, e) => console.error('babylon load fail', m, e), '.glb');
addEventListener('resize', () => engine.resize());
{BENCH}
window.__orbit = (n) => window.__bench(n, i => {{ cam.alpha += 0.03; }});
</script></body></html>"""
(here / "babylon.html").write_text(bab, encoding="utf-8", newline="\n")
print("ok", [p.name for p in here.glob("*.html")])
