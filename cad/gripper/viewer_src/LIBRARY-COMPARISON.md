# 3D library comparison for the gripper review page

Model: `out/web/gripper_closed.glb` (2.2 MB, 16 named parts). Prototypes in `lib_compare/` (`make.py` builds them, `measure.py` measures, `results.json` holds raw numbers). 1440x900, headless Chromium with **software WebGL (SwiftShader)**, so absolute frame times are pessimistic; use the ratios. Script KB is transferred (compressed) bytes from cdn.jsdelivr.net.

| Library | Version | Script KB | First frame ms | Median frame ms (120-frame orbit) | PBR | Env | Shadows | AO | Clipping / section | Per-part animation | Per-part picking |
|---|---|---|---|---|---|---|---|---|---|---|---|
| three.js, full (shadows + GTAO) | 0.186.1 | 481 | 2600 | 5950 (6.5x model-viewer) | MeshPhysical, clearcoat, sheen, anisotropy | RoomEnvironment PMREM, no download | VSM soft + ShadowMaterial catcher | GTAOPass | yes, `clippingPlanes` + caps | full | Raycaster |
| three.js, shadows only | 0.186.1 | 480 | 2250 | 2550 (2.8x) | same | same | same | off | yes | full | yes |
| three.js, env + physical only (phone mode) | 0.186.1 | 480 | 3070 | 1450 (1.6x) | same | same | off | off | yes | full | yes |
| model-viewer | 4.3.1 | 283 | 7600 | 917 (1.0x) | glTF PBR (+ some extensions) | built-in `neutral` | soft contact shadow | none | no | no (only variants, material colour/roughness edits, animations baked in GLB) | `positionAndNormalFromPoint` / `materialFromPoint` (material, not node) |
| Babylon.js | 9.28.0 | 1894 | 1960 | 1950 (2.1x, SSAO2 on, no env) | PBRMaterial | none offline (default env fetches from assets.babylonjs.com, not an allowed host) | blur ESM + ShadowOnlyMaterial | SSAO2 | yes (clipPlane) | full | scene.pick |

Notes: model-viewer first frame includes its own scene setup and a 2.2 MB blob decode; its ratio vs three.js "first frame" is noisy (7.6 to 14.9 s across runs under contention). three.js first frame was 2.2 to 3.1 s across quality levels, near the 3 s target even on software GL; real GPUs will be far faster. Babylon only parses its 8.6 MB script quickly because of cache-less local file load and V8 caching in headless; expect more on a phone.

## Look achieved (shots/)
- `shots/lib_threejs.png`: physical materials per node name (PETG clearcoat, PA6-CF dark sheen, TPU orange sheen, steel/aluminium metal), procedural room environment, ACES tone mapping, soft VSM shadow on a shadow-catcher, GTAO. Honest verdict: a clear step up from MeshStandard plus simple lights (metal fasteners and horn read as metal, TPU reads as satin), but the GTAO contribution is subtle on this model and large flat PETG faces remain plain. Further gains need texture work (layer-line normal map, noise roughness) rather than a different library.
- `shots/lib_modelviewer.png`: good default look in zero code (neutral env, contact shadow), but uses the GLB's own flat colours; materials can only be edited through its `model.materials` API.
- `shots/lib_babylon.png`: dark and flat because no environment texture is available offline under the host rules; would need a procedural environment built by hand.

## What the page needs
| Need | three.js | model-viewer | Babylon |
|---|---|---|---|
| Per-part picking by node name | Raycaster, `object.name` | only material under pointer | yes |
| Section planes | `renderer.clippingPlanes` / `material.clippingPlanes`, stencil caps | no | yes |
| Animate individual parts (assembly explode, jaw rotation) | set `object.position/rotation` directly | no node transform API; would require baked glTF animations and a timeline scrub | yes |
| Measurement lines / annotations | Line2, CSS2D/sprites in same scene | hotspots only (HTML anchored to surface points) | yes |
| Light/dark theming, custom UI | full control | CSS vars, limited | full |

## Recommendation
Stay on three.js 0.186.1 as ES modules via an inline importmap, because per-part picking, section planes, per-part animation and measurement lines are first-class there and model-viewer cannot do the middle three; Babylon matches the features but costs about 4x the script weight. Lift `lib_compare/three_setup.js` (`setupRealism`) into the page, default to quality 2 on desktop, level 0 under 600 px and auto-degrade on slow frames (built in).
