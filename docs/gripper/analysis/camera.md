# Camera placement (for later CV)

Lane W2, 2026-09-22 (review fixes applied the same day). This note picks where a camera goes. It does not do the CV. The design basis is `docs/gripper/DESIGN-BASIS.md`, and it wins where the two disagree.

- **Script:** `analysis/gripper/camera.py`. Inputs: `cad/gripper/params.json`, `cad/so101/Simulation/SO101/so101_old_calib.xml` (link meshes and kinematics), `analysis/gripper/results/payload_torque.json` (torque lane's item list and worst pose), and the camera list in `docs/gripper/research/cloth_and_camera.md` §3.3. The upstream hex-nut adapter `cad/so101/SO-ARM101_camera_wrist_mount.step` was measured once with cadquery, and the values are copied into `STOCK_MOUNT`.
- **Outputs:** `analysis/gripper/results/camera.json` (every placement and camera, each pose, plus the **`mount`** block), `analysis/gripper/results/camera_stdout.txt`, and the figures `docs/gripper/figures/camera_top.png`, `camera_side.png` and `camera_views.png`.
- **Re-run** (about 70 s): `uv run --with mujoco --with numpy --with scipy --with matplotlib python analysis/gripper/camera.py`
- **Tags:** [S] sourced, [D] derived by the script, [A] assumed. Every input carries its tag in `camera.json` → `inputs` and `cameras`.

## 0. Answer

| Item | Result |
|---|---|
| **Primary** | **Fixed, raised oblique view, Raspberry Pi Camera Module 3 (standard lens), 2304 × 1296 mode.** Lens **200 mm above the bed, 166 mm right of the needle (toward the tower), 100 mm in front of the needle**, looking left and down at 53°. Every feed pose sees 100 % of the critical edge (the last 40 mm before the foot) at **5.5 px/mm** (requirement 5) and the foot toe. Both fingertips at approach; one of two at the last two feed poses. Feed blur 0.56 px. DoF 218–270 mm covers the approach targets (228–256 mm); at feed, DoF 226–282 mm covers the 250–252 mm targets. **0 g** on the arm [D] |
| **Backup (fixed)** | **Side view in the throat, Pi Camera 3 Wide**: 110 mm right, 40 mm in front of the needle, 80 mm above the bed, aimed 20 mm ahead of the foot. 100 % critical edge at 5.2 px/mm, foot toe at every feed pose, no pick view. Same mount also passes with the **OV9281 global shutter (5.7 px/mm)**, whose pass does not rest on the unverified UVC specs [D] |
| **Wrist option** (the pad D9 reserves) | **32 × 32 UVC (USB) on the +n front plate, lens at u = 30, n = 35**, plate 80.8° to the flange. Approach: whole edge and both tips at ≥ 9.0 px/mm. At feed the critical edge is out of frame until 75 mm into the feed, so **pick only**. 16.3 g → 105 % of the mass-moment budget, **103.4 %** in the torque lane's worst-pose definition (97.7 % without) [D] |
| Rejected | Straight overhead at every height: the head hides the critical edge (0 % visible). Every wrist mount on the top, servo or bottom face: fingers or housing hide the edge. Wrist lens at u = 10: it hits the SO-101 wrist link during roll. Pi Camera 3 Wide on the wrist: best optics (5.1 px/mm at feed, 8.8 g), but its CSI run is ~906 mm against 500 mm for the longest official cable (§6). C270: 75 g, fixed mounts only [D] |
| Mount numbers for CAD | `camera.json` → `mount` (section 6) |

D9 said "fixed overhead is primary". That still holds in spirit: a fixed, off-arm camera is primary. But *straight* overhead fails. The camera has to be offset toward the tower and look obliquely under the machine arm, past the head.

## 1. Method

**Work cell** [A unless tagged]. The frame is the MuJoCo world of `so101_old_calib.xml` (arm base on the table, z up). The arm base stands on the cloth tension line (R24). The needle sits 325 mm from the pan axis along that line, on a 100 mm bed (`params.json` `work_cell`). The cloth feeds away from the arm (−y). The seam edge lies 15.9 mm (5/8 in) right of the needle. The machine is boxed from the Singer 4423 envelope, 394 × 159 × 305 mm [S]: base/bed, tower 159 mm right of the needle [S], horizontal arm with a 120 mm throat, head 65 mm above the bed with its right face 40 mm right of the needle, presser bar, and a presser foot whose toe is 12 mm ahead of the needle. The internal layout is [A]. Box coordinates are in `camera.json` → `work_cell_frame`.

**Gripper** [D from `params.json` + DESIGN-BASIS]. Convex solids in the gripper frame: c is the jaw axis (+ = finger B, the upper idler finger), u is the roll axis toward the tips, n is the gear axis (+ = front plate, facing the seam edge; servo body on −n). Solids: deck/hub 68 mm wide; DS3218MG cradle; plates and m1.5 z20 gears (pivots ±15 mm at u = 40.7; front plate n 8.0–10.5, gear faces ≤ 7.0); knuckles; 45 mm Fin Ray fingers, 20 mm deep, tips at u = 110.7; and the wrist pad/flange stack (§6). Opening θ = +20° rotates each finger about its pivot. The handedness (front plate toward the edge) is a reversible mirror choice.

**Poses.** Least-squares IK puts the pad centroid 4 mm above the bed on the seam line, gripper tilted 45° from vertical, nail finger A lower [A]. One approach pose (jaw open, backed off 15 mm) and 7 feed poses over 150 mm, ending 20 mm before the foot. Tilt is 45.0° at 6 of 8 poses; at the start (reach 108 mm) shoulder_lift hits its limit (41–42° tilt, 2.4 mm error). The first 30 mm of the 200 mm duty-cycle feed are not reachable at 45°, so longer seams re-grip [D].

**Targets.** 24 seam-edge points from 5 mm past the fingertips to the foot toe; the critical subset is the last 40 mm (4 s at 10 mm/s) [A]. Both fingertips (2 mm past each apex, on the face toward the camera) and the foot toe. At approach: 13 edge points around the grip plus the tips.

**Tests** for every placement × camera × pose:
- **FOV and projection.** Pi Camera 3 and 3 Wide have a sourced focal length and H/V FOV [S]: fx = f / effective pitch (2.8 µm in the 2 × 2 binned mode) [D], and the frame is the pinhole pixel frame clipped to the sourced H/V FOV. The other cameras have only a diagonal FOV: H/V from the diagonal and aspect ratio [D].
- **Occlusion:** rays from the lens to each target against the gripper and machine solids (Cyrus-Beck) and the SO-101 link meshes (`mujoco.mj_ray`, visual group). The stock wrist-roll follower and jaw are excluded, because the new housing replaces them.
- **Pixel density:** image distance of 1 mm across the edge, in the bed plane.
- **Depth of field:** CoC = 2 output pixels; focus at the harmonic mean of the nearest and farthest targets that must be sharp.
- **Blur:** fixed cameras: px/mm × 10 mm/s × 10 ms. Wrist: image motion of the fixed foot point between feed poses, scaled to 10 mm/s. Approach: 100 mm/s arm speed [A].
- **Head margin (fixed):** smallest distance from the critical-edge sight lines to the head box; for the chosen pose, a sweep of the head underside height and right-face position until the critical edge drops below 90 %.
- **Mass:** camera + PETG bracket + carried cable, times (309.1 + u) mm, added to the R10 mass-moment (40,507 of 43,720 g·mm, C001 at 7.4 V) [D]. Also the **torque lane's governing metric**: the worst pose over shoulder_lift / elbow / wrist_flex of max |τ| / (0.5 × stall), with the lane's item list from `payload_torque.json` → `rollup_design_point_A17` plus the camera as a point mass at its u. The script reproduces the lane's 0.9769 (no camera) and 1.011 (10 g at 20 mm) before using it [D].
- **Clearance:** fixed: camera body (sphere r = 20 mm [A]) plus its post or stalk must clear the SO-101 links and gripper by ≥ 25 mm at every pose and not pass through the machine. Wrist, per camera: the board + lens + 1.5 mm printed-plate envelope must stay ≥ 25 mm above the bed, outside the machine, ≥ 1 mm from its own housing and pad/flange stack, ≥ 8 mm from the finger sweep (θ −11° to +20°), and ≥ 3 mm from the SO-101 link meshes at the 8 task poses and over a ±150° roll sweep at mid-feed [A]. A failing placement cannot be chosen.

**Pass rules.** Feed: critical edge ≥ 90 % visible at every feed pose, ≥ 5 px/mm there, DoF covering the critical edge and the tips, blur ≤ 1 px. Approach: ≥ 80 % of the edge near the grip visible, both tips visible, ≥ 3 px/mm.

**Candidates:** 24 wrist mounts (front plate at lens n = 24 / 28.5 / 35, top, servo-back and bottom faces × u = 10 or 30 × two aim points); 52 overhead (coarse grid: heights 250 / 350 / 500 × offsets 0 / 60 / 120 × two aim points; fine grid: heights 200–300 in 25 mm steps × offsets 90–150 in 10 mm steps); 5 side views. Each with 6 cameras: 486 combinations.

**Selection.** Primary: among overhead candidates that pass the feed, clear the arm and keep ≥ 5 % px/mm margin, the one with the largest head sight-line clearance. Backup: the best passing candidate of the other fixed family. Wrist: ranked on the pick view, then feed coverage, then mass; the video link must reach the host by wire (CSI only if a standard cable reaches; else USB).

## 2. Cameras

| Camera | HFOV × VFOV used (°) | Output px | f (mm) | fx (px) | F | Eff. pitch (µm) | Mass (g) | Tag |
|---|---|---|---|---|---|---|---|---|
| Pi Camera 3 | 66.0 × 41.0 (sourced FOV clips the pixel frame) | 2304 × 1296 @ 56 fps | 4.74 [S] | 1693 [D] | 1.8 [S] | 2.8 | 4 [S] | [S] raspberrypi.com camera docs (66 × 41°, f, F, 1.4 µm, 4 g) |
| Pi Camera 3 Wide | 99.1 × 66.8 (pixel frame at fx; sourced 102 × 67) | 2304 × 1296 | 2.75 [S] | 982 [D] | 2.2 [S] | 2.8 | 4 [S] | [S] same page (102 × 67°) |
| ESP32-CAM OV2640 | 54.9 × 42.6 [D] | 1600 × 1200 @ 15 fps | 3.39 [D] | 1540 [D] | 2.0 [A] | 2.2 [A] | 8 | [S] cloth_and_camera.md (66° diag) |
| 32 × 32 UVC | 82.1 × 52.2 [D] | 1920 × 1080 @ 30 [A] | 3.30 [D] | 1101 [D] | 2.0 [A] | 3.0 [A] | 10 [A] | [S] README ≥ 720p30, manual focus; the rest [A] |
| OV9281 global shutter | 61.4 × 40.7 [D] | 1280 × 800 @ 120 | 3.23 [D] | 1078 [D] | 2.0 [A] | 3.0 | 5 [A] | [S] Arducam, $25.99; lens [A] |
| Logitech C270 | 48.8 × 28.6 [D] | 1280 × 720 @ 30 | 3.95 [D] | 1411 [D] | 2.4 [A] | 2.8 [A] | 75 | [S] |

Source for both Pi cameras: https://www.raspberrypi.com/documentation/accessories/camera.html (H/V FOV, focal length, F-stop, pixel size, 25 × 24 × 11.5 / 12.4 mm, 4 g; "board dimensions and mounting-hole positions … identical to Camera Module 2"). Board and holes: Camera Module 2 mechanical drawing, https://datasheets.raspberrypi.com/camera/camera-module-2-mechanical-drawing.pdf (board 25 × 23.86 mm, 4 × Ø2.2 on 21 × 12.5 mm, 2 mm from the edges, lens 9.46 mm from the connector edge).

## 3. Results

### 3.1 Best per placement family [D]

| Placement / camera | Critical edge visible (worst feed pose) | Edge visible (mean) | px/mm, critical (worst) | Tips (feed / approach) | Feed blur (px) | Approach blur (px), 10 / 2 ms | DoF | Mass on arm |
|---|---|---|---|---|---|---|---|---|
| **O_h200_r150 / Pi Camera 3** | 100 % | 100 % | **5.5** | 1 / 2 | 0.56 | 5.7 / 1.1 | pass | 0 g |
| O_h250_r120 / Pi Camera 3 (first-pass primary) | 100 % | 100 % | 5.5 | 2 / 2 | 0.56 | 5.6 / 1.1 | pass | 0 g |
| O_h200_r120 / Pi Camera 3 | 100 % | 100 % | 6.3 | 1 / 2 | 0.64 | — | pass | 0 g |
| O_h200_r150 / other cameras | 100 % | 100 % | ESP32 5.0 (fails by 0.01), C270 4.6, UVC 3.6, OV9281 3.5, Wide 3.2 | — | < 0.6 | — | pass | 0 g |
| **S_throat_high / Pi Camera 3 Wide** | 100 % | 99 % | **5.2** | 0 / 0 | 0.89 | no pick view | pass | 0 g |
| S_throat_high / OV9281, UVC, ESP32, C270 | 100 % | — | 5.7 / 5.8 / 8.1 / 7.4 | 0 / 0 | 0.69 / 0.84 / 0.95 / 0.84 | — | pass | 0 g |
| **W_edge_n35_u30 / 32 × 32 UVC** | 0 % (feed start) → 100 % from 75 mm | 89 % | — | 1 / 2 | 0.62 | 13.1 / 2.6 | fails | 16.3 g |
| W_edge_n28.5_u30 / Pi Camera 3 Wide | 100 % | 100 % | 5.1 | 1 / 2 | 0.54 | 12.0 / 2.4 | fails (tips + foot) | 8.8 g (CSI run too long) |
| Straight overhead (r = 0 or 60), any height; r = 120 at 350 or 500 mm | 0 % (head occludes) | — | — | — | — | — | — | 0 g |
| W_top / W_servo / W_bottom, any | 0 % | 0–62 % | — | 0–1 | — | — | — | 10–17 g |

Full table: `camera.json` → `all` (486 rows, each with its `clearance`); per-pose detail under `primary`, `backup_fixed` and `wrist_option`.

### 3.2 Physical clearance [D]

| Placement | Check | Result |
|---|---|---|
| **O_h200_r150_path (primary)** | Body + post to arm/gripper, all 8 poses | **120.8 mm** (pass). The post foot is 19.5 mm in front of the bed's front face (b = −99.5 vs −80 [A]) |
| O_h*_r0_* and O_h*_r*_crit | same | The r0 bodies hit the arm or gripper, and every `crit` post stands inside the machine bed. All fail |
| **S_throat_high (backup)** | Body + stalk | **76.2 mm** (pass) |
| **W_edge_n35_u30 / UVC (wrist)** | Above bed / own housing and pad / finger sweep / SO-101 links over roll | 43.2 / **1.2** / 15.5 / 4.6 mm (pass) |
| W_edge_n24_u30_* (first-pass mount) | Own housing and flange | −2.9 (Pi) to −6.8 mm (UVC): the board passes through the flange. Fails |
| W_edge_n28.5_* / UVC | Own housing and flange | −4.3 to +0.6 mm (needs ≥ 1). Fails; the UVC needs n = 35 |
| W_edge_*_u10_* | SO-101 wrist link over ±150° roll | −6 to −9 mm: the camera plate sweeps into the wrist link. Fails |

At the folded approach pose, rolling the wrist into −135° … −45° drives any front-plate camera into the shoulder / upper arm. The task poses never do this, but firmware should block that roll band while the arm is folded (`approach_pose_roll_keepout_deg`).

### 3.3 What limits each family

- **Straight overhead.** A ray from above the seam line to the edge 12–52 mm ahead of the foot passes through the head box. Moving the camera 120–150 mm toward the tower and lowering it to 200 mm brings the ray under the machine arm, past the head. The first-pass pose (250 mm, 120 mm) passed with thin margin: its sight lines cleared the head box by 6.4 mm, and it fails if the head underside is below 51 mm or its right face is past 46 mm. The chosen pose clears by 19.6 mm (thresholds in §7).
- **Resolution.** Only the Pi Camera 3 at 2304 × 1296 clears 5 px/mm with margin from 200–250 mm (5.5–6.3). At 1080p the same view gives about 4.6. The 500 mm overhead of `cloth_and_camera.md` §3.2 gives about 2.9 px/mm: enough for ±1 mm, not ±0.5 mm.
- **Wrist.** The standard lens is too narrow: the foot is 150–195 mm ahead at the start of the feed. The Pi Camera 3 Wide sees everything at ≥ 5.1 px/mm, but one fixed focus cannot keep both the fingertips (~85 mm) and the foot (~160 mm) sharp; its autofocus could refocus per state. The 82° UVC does not see all of the critical edge until 75 mm into the feed. The top, servo-side and bottom faces put fingers, housing or the cloth pinch between lens and edge.
- **Blur.** At feed every fixed placement is < 1 px at 10 ms. During the approach (100 mm/s) every camera blurs 5–21 px at 10 ms, so either image with the arm stopped or light the bed and expose ≤ 2 ms (1.1–4 px). All candidates except the OV9281 are rolling shutter, which also skews moving edges. The OV9281 passes the feed at S_throat_high (5.7 px/mm, 0.69 px blur); it fails 5 px/mm in every overhead placement.
- **Mass.** A wrist camera costs 8.8 g (Pi Camera 3 Wide + CSI ribbon) to 16.3 g (32 × 32 UVC + USB). In the torque lane's worst-pose definition that is 100.8–103.4 % of the C001 7.4 V hold allowance (97.7 % without a camera); in the R10 mass-moment it is 99.5–105.3 %. The C270 would be 84 g, 157 %. Over 100 % only near full horizontal extension, which the torque note's operating rule already forbids. Every fixed placement costs 0 g.

## 4. Decision

1. **Primary: fixed oblique Pi Camera 3**, standard lens, 2304 × 1296, autofocus locked after calibration. Needs a Raspberry Pi (Zero 2 W or 4/5) off the arm. Why: it passes feed and approach, has the most head margin of the passing poses, and adds 0 g.
2. **Backup: side throat camera, Pi Camera 3 Wide** (all optical specs sourced), same Pi. It passes the feed on its own and is the fallback if M-C1 shows the real head blocks the primary or bed glare kills the oblique view. Alternatives on the same bracket: **OV9281** global shutter (5.7 px/mm, sourced resolution, lens [A]); 32 × 32 UVC (5.8, all specs [A]); ESP32-CAM at UXGA (8.1, 15 fps).
3. **Wrist: keep only the reserved pad** (D9). Fit the 32 × 32 UVC there only if CV must find the cloth edge for the pick. Do not use it for the seam at feed. A Pi Camera 3 Wide would be lighter and sharper, but only if the Pi rides the arm or a > 900 mm CSI run is proven, and its ribbon survives the roll.

## 5. Assumptions and sensitivities

| Assumption | Value | Effect if wrong |
|---|---|---|
| Machine head | Underside 65 mm above the bed, right face 40 mm right of the needle, front face 50 mm ahead; arm underside 120 mm [A] | Primary still passes down to a 33 mm underside or out to a 64 mm right face (§7). Re-run with measured boxes (M-C1) |
| Seam edge | 15.9 mm right of the needle [A] | A narrower allowance moves the edge under the foot shank; px/mm barely changes |
| Needle reach / feed travel | 325 mm / 150 mm [A] | Shifts the wrist results; fixed cameras are almost unaffected |
| Gripper tilt | 45°, nail finger lower [A] | Changes wrist occlusion; the front-plate face stays best by symmetry |
| Requirement | 5 px/mm for ±0.5 mm [A] | At 3 px/mm, straight 500 mm overhead would also pass if it were not occluded |
| Pi Camera 3 Wide projection | Pinhole at fx = f / pitch; real lens has some barrel distortion [A] | px/mm near the frame edge is a few % lower than modelled; backup margin is 4 % |
| UVC module specs | 1080p, 90° diagonal, 3 µm, 10 g, lens centred, 15 mm deep [A] | Measure (M-C3); a 720p module drops the throat view to about 3.9 px/mm |
| Wrist pad fastening | Short M3 heat-set inserts ≤ 4 mm, not hex nuts [A] | Reversible deviation from D9 (§6) |
| Exposure / speeds | 10 ms; 10 mm/s feed; 100 mm/s arm [A] | Blur scales linearly |

## 6. Mount (`camera.json` → `mount`)

**Primary fixed** (machine frame: origin at the needle point on the bed, a = right, b = along the feed, z = up):
- Lens at a = +165.9, b = −99.5, z = +200 mm. Optical axis 53.1° below horizontal, yawed −90° from the feed (looking left at the seam). Aim point a = +15.9, b = −99.5, on the bed. Image long axis along the feed.
- Camera plate 28 × 26.9 × 2.5 mm, **4× M2 on 21.0 × 12.5 mm centres** (board 25 × 23.86 mm, holes Ø2.2, 2 mm from the edges) [S], with a 1/4-20 insert on the back.
- Hardware: clamp to the table (not the machine: needle vibration); 12–15 mm rod or 2020 post; 1/4-20 ball head. Lock the pose, then calibrate once: checkerboard intrinsics plus a planar homography to the bed.
- Clearance 120.8 mm to arm and gripper at every pose [D]. The post stands 19.5 mm in front of the bed's front face [A]; if the real bed sticks out further, move the post upstream and reach over with a short boom. Keep the lens where it is.

**Backup fixed:** lens at a = +110, b = −40, z = +80 mm, aimed at a = +15.9, b = −32, on the bed. Same Pi plate (or the OV9281 / UVC plate). The bracket sits on a printed foot clipped to the bed front-right, inside the throat. Clearance 76.2 mm [D].

**Wrist pad** (gripper frame c / u / n; +n = front-plate face, toward the seam edge):
- Pad 12 (c) × 17 (u) mm, 3 mm boss, on the +n front plate, centred at c = +11, u = 27: off the gear pitch point (c 0, u 40.7; 14.6 mm away) and clear of the Ø9 lightening hole at (c 0, u 29.7).
- **2× M3 at 8.1 mm along u** (the upstream Hex-Nut adapter spacing, D9), at (c, u) = (11, 22.95) and (11, 31.05).
- **Fastening:** blind Ø4.2 × 4.5 mm bores from the boss top for short M3 heat-set inserts ≤ 4 mm long; **M3 × 6** screws through the 3 mm flange (3 mm engagement, tip 1.5 mm above the bore floor). Boss + plate is 5.5 mm, so 1.0 mm of front plate stays under each bore, 2.0 mm from the gear faces. Webs: 4.5 mm to the Ø9 hole, 2.65 mm to the plate's top edge. No inside nut trap: the inside face is 1 mm above the gears.
- **Deviation from D9 [A, reversible]:** D9 names hex-nut points; this uses heat-set inserts, because a nut trap needs the inside face, which is the gear zone. Spacing unchanged.
- **Bracket:** flange 12 × 17 × 3 mm (top at n = 16.5); a 12 × 3 mm riser up +n to the camera plate. PETG, 40 % infill, flange printed flat.
- **Camera plate for the 32 × 32 UVC (chosen):** 35 × 35 × 2.5 mm, **4× M2 on a 27.0 mm square** [D, upstream STEP]; lens centre at c 0, u 30, **n 35** (board low edge at 17.7, ≥ 1.2 mm above the flange). Aim (c 0, u 160, n 14): the optical axis is 9.2° from +u toward −n, so the plate stands **80.8° to the flange**. Bracket 2.65 g.
- **Camera plate for a Pi Camera 3 / 3 Wide (if used):** 28 × 26.9 × 2.5 mm, **4× M2 on 21.0 × 12.5 mm** on the 25 × 23.86 board [S], the 9.46 mm lens-to-edge side toward −n (the FFC exits there); lens at n ≥ 28.5, plate 81.3° to the flange. Bracket 1.8 g.
- **Cable.** UVC: USB routed along −n past the servo, tied to the wrist-roll follower with a 60–80 mm service loop; limit roll to ±150°. Pi camera: the CSI run from the lens to a Pi on the table is ~906 mm (links 516 mm [D] + service loops and table run 390 mm [A]) against official Raspberry Pi camera cables of 200 / 300 / 500 mm [S] (https://www.raspberrypi.com/products/camera-cable/). Flat-flex twist through ±150° roll is not assessed. So a wrist Pi camera needs the Pi on the arm, which adds mass, or a proven extender; the UVC avoids both.
- **Mass on the arm (UVC):** 16.3 g (camera 10 [A], bracket 2.65, carried USB 3.6 [A]) → 105.3 % of the mass-moment budget, **103.4 %** torque-lane worst-pose use (97.7 % without it). Pi Camera 3 Wide: 8.8 g → 99.5 % / 100.8 %. Both exceed 100 % only near full horizontal extension, which the operating rule forbids.
- **Keep-outs:** envelope ≥ 8 mm from the finger sweep (15.5 mm now) and ≥ 1 mm from its own housing and pad (1.2 mm now); no lens at u = 10 (the wrist link); block roll −135° … −45° while the arm is folded at approach.

## 7. Team must measure

| # | Quantity | Default now | Pass/fail for the primary | How |
|---|---|---|---|---|
| M-C1 | Head underside height above the bed, head right face from the needle, foot toe position | 65 / 40 / 12 mm [A] | **Pass if the underside is ≥ 33 mm above the bed and the right face is ≤ 64 mm right of the needle** (each with the other at its default). The first-pass pose would need ≥ 51 mm and ≤ 46 mm | Ruler from the needle; if outside, update `MACH_LOCAL` and re-run |
| M-C2 | Seam guide used for the demo | 15.9 mm | — | Throat-plate marking |
| M-C3 | UVC module resolution, FOV, mass, lens position | 1080p, 90°, 10 g, centred | Wrist and UVC-backup numbers depend on it | Datasheet or listing; checkerboard at 100 mm; scale |
| M-C4 | Edge contrast and bed glare at the primary angle | Not modelled | — | Photograph the demo fabric from the primary pose, with and without an LED bar |
| M-C5 | Exposure needed with the work light | 2 ms [A] | — | Pi Camera 3 manual exposure at the chosen gain |
| M-C6 | Arm speed while imaging during approach | 100 mm/s [A] | — | LeRobot trajectory log |
