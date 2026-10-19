/* three_setup.js -- lift-and-paste realism setup. three@0.186.1 (pinned), ES modules.
 *
 * <script type="importmap">
 * {"imports":{
 *   "three":"https://cdn.jsdelivr.net/npm/three@0.186.1/build/three.module.js",
 *   "three/addons/":"https://cdn.jsdelivr.net/npm/three@0.186.1/examples/jsm/"}}
 * </script>
 * <script type="module">
 *   import * as THREE from 'three';
 *   import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
 *   import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
 *   import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
 *   import {EffectComposer} from 'three/addons/postprocessing/EffectComposer.js';
 *   import {RenderPass} from 'three/addons/postprocessing/RenderPass.js';
 *   import {GTAOPass} from 'three/addons/postprocessing/GTAOPass.js';
 *   import {OutputPass} from 'three/addons/postprocessing/OutputPass.js';
 *   const addons = {RoomEnvironment, EffectComposer, RenderPass, GTAOPass, OutputPass};
 *   const R = setupRealism(THREE, addons, renderer, scene, camera, {container, model});
 *   // each frame:  R.render();   on resize: R.resize(w,h);   R.monitor(dtMs) auto-degrades
 */
function setupRealism(THREE, addons, renderer, scene, camera, opts = {}) {
  const small = matchMedia('(max-width: 600px)').matches;
  const mats = {};
  const P = (name, p) => (mats[name] = new THREE.MeshPhysicalMaterial(p));
  // Material table. null color = keep the GLB baseColor (per-part colour coding).
  P('petg',     {roughness: 0.38, metalness: 0, clearcoat: 0.25, clearcoatRoughness: 0.3, ior: 1.57, specularIntensity: 0.8});
  P('pa6cf',    {color: 0x2a2c30, roughness: 0.62, metalness: 0.05, sheen: 0.4, sheenRoughness: 0.5, sheenColor: new THREE.Color(0x6a6f78)});
  P('tpu',      {color: 0xe3721a, roughness: 0.55, metalness: 0, sheen: 1, sheenRoughness: 0.35, sheenColor: new THREE.Color(0xffb27a)});
  P('pla',      {roughness: 0.6, metalness: 0});
  P('servo',    {color: 0x141416, roughness: 0.48, metalness: 0, clearcoat: 0.1, clearcoatRoughness: 0.5});
  P('aluminium',{color: 0xc9ccd1, roughness: 0.38, metalness: 1, anisotropy: 0.3});
  P('steel',    {color: 0xb9bdc3, roughness: 0.35, metalness: 1});
  const byPrefix = [['housing','petg'],['front_plate','petg'],['wrist_mount','petg'],['knuckle','pa6cf'],['finger','tpu'],
    ['nail','pla'],['fsr','pla'],['servo','servo'],['horn','aluminium'],['fasteners','steel']];
  const keepColour = new Set(['petg', 'pla']);
  function applyMaterials(root) {
    root.traverse(o => {
      if (!o.isMesh) return;
      const hit = byPrefix.find(([p]) => o.name.startsWith(p));
      if (!hit) return;
      const src = o.material, key = hit[1];
      let m = mats[key];
      if (keepColour.has(key)) {           // one clone per source colour
        const k = key + ':' + src.color.getHexString();
        m = mats[k] || (mats[k] = Object.assign(m.clone(), {color: src.color.clone().multiplyScalar(key === 'petg' ? 0.72 : 1)}));
      }
      o.material = m; o.castShadow = o.receiveShadow = true;
    });
  }
  // Environment: procedural, no download.
  renderer.toneMapping = THREE.ACESFilmicToneMapping;   // or THREE.AgXToneMapping
  renderer.toneMappingExposure = 0.8;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.VSMShadowMap;   // PCFSoftShadowMap was removed in r18x; VSM is the soft option
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new addons.RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.7;
  pmrem.dispose();
  // Key light with soft shadow + shadow-catcher ground.
  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0005; key.shadow.normalBias = 0.2; key.shadow.radius = 6; key.shadow.blurSamples = 12;
  scene.add(key, key.target);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(1000, 1000), new THREE.ShadowMaterial({opacity: 0.28}));
  ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
  function fit(root) {      // call after model is added: sizes light frustum, places ground
    applyMaterials(root);
    const b = new THREE.Box3().setFromObject(root), c = b.getCenter(new THREE.Vector3()), s = b.getSize(new THREE.Vector3()).length();
    ground.position.set(c.x, b.min.y - 0.5, c.z);
    key.position.set(c.x + s * 0.6, b.max.y + s * 0.9, c.z + s * 0.5); key.target.position.copy(c);
    const sc = key.shadow.camera; sc.left = sc.bottom = -s * 0.65; sc.right = sc.top = s * 0.65; sc.near = 1; sc.far = s * 4; sc.updateProjectionMatrix();
    return {box: b, center: c, size: s};
  }
  // Post: AO composer (GTAO) + OutputPass (tone mapping + sRGB).
  const size = renderer.getSize(new THREE.Vector2());
  const composer = new addons.EffectComposer(renderer);
  composer.addPass(new addons.RenderPass(scene, camera));
  const gtao = new addons.GTAOPass(scene, camera, size.x, size.y);
  gtao.output = addons.GTAOPass.OUTPUT.Default;
  gtao.updateGtaoMaterial({radius: 10, distanceExponent: 1.5, thickness: 3, scale: 2.2, samples: 12, distanceFallOff: 1, screenSpaceRadius: false});
  gtao.updatePdMaterial({lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 12});
  composer.addPass(gtao);
  composer.addPass(new addons.OutputPass());
  // Quality: 0 = plain physical + env; 1 = + soft shadows; 2 = + AO.
  let level = small ? 0 : 2, aoOn = true, shadowOn = true;
  function setQuality(l) {
    level = l;
    renderer.shadowMap.enabled = l >= 1 && shadowOn;
    key.castShadow = ground.visible = renderer.shadowMap.enabled;
    scene.traverse(o => { if (o.material) o.material.needsUpdate = true; });
    gtao.enabled = l >= 2 && aoOn;
    renderer.setPixelRatio(l === 0 ? Math.min(devicePixelRatio, 1.5) : Math.min(devicePixelRatio, 2));
    return level;
  }
  const useComposer = () => level >= 2 && aoOn;
  function render() { useComposer() ? composer.render() : renderer.render(scene, camera); }
  function resize(w, h) { renderer.setSize(w, h, false); composer.setSize(w, h); }
  // Auto-degrade: 30-frame rolling mean > 40 ms (<25 fps) drops one level; call each frame with dt ms.
  const win = []; let cool = 0;
  function monitor(dt) {
    if (dt > 250) return;                              // ignore stalls (tab switch, load)
    win.push(dt); if (win.length > 30) win.shift();
    if (cool > 0) { cool--; return; }
    if (win.length === 30 && win.reduce((a, b) => a + b) / 30 > 40 && level > 0) { setQuality(level - 1); win.length = 0; cool = 60; }
  }
  setQuality(level);
  return {composer, setQuality, materials: mats, render, resize, monitor, fit, applyMaterials, key, ground, gtao,
          get level() { return level; }, set ao(v) { aoOn = v; setQuality(level); }, set shadows(v) { shadowOn = v; setQuality(level); }};
}
