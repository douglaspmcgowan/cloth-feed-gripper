# Cloth handling, camera placement, ME102B requirement map

Lane research for the cloth-feed gripper (`cad/gripper/`). Dated 2026-09-22. Every number is tagged **[S]** sourced (URL), **[D]** derived (math shown), or **[A]** assumed (to test).

## 1. Headline findings

1. **Pinch between two flat pads is the right grasp.** The grasp-centred cloth-manipulation review finds that simple parallel pinch grippers cover most published cloth tasks ([Borràs, Alenyà, Torras, arXiv 1906.08202](https://arxiv.org/abs/1906.08202)). Our 1-DOF geared jaw is a pinch gripper; keep it.
2. **Wrong-layer-count is the dominant failure.** Singulating the right number of layers needed tactile feedback (ReSkin) to beat vision-only baselines over 180 physical trials ([Tirumala et al., "Learning to Singulate Layers of Cloth using Tactile Feedback", arXiv 2207.11196](https://arxiv.org/abs/2207.11196)). Design for one ply from a flat single sheet, not from a stack.
3. **Required normal (pinch) force is small: target ~5 N [D], cap ~10 N [A].** Servo torque is not the limit; controlling force is.
4. **`closed_gap = 1.0 mm` in `params.json` will not pinch one ply.** A single cotton ply is ~0.2–0.5 mm [A]. At θ = 0 the pads sit 1 mm apart, so cloth falls through unless the servo over-drives past closed. Fix: set `closed_gap` to 0 and command a small over-travel so the TPU pads preload, or add a ~1 mm compliant pad insert. **Flag for the CAD lane.**
5. **Camera: fixed overhead (eye-to-hand) for edge alignment at the needle, plus an optional wrist camera for the pick.** A wrist-only camera is occluded by the fingers and cloth exactly at the needle and blurs during motion.
6. **PWM conflict to note.** The arm's STS3215 is a TTL serial-bus servo, not PWM ([Feetech](https://www.feetechrc.com/2020-05-13_56655.html); [Seeed](https://www.seeedstudio.com/STS3215-19kg-cm-7-4V-Serial-Servo-p-6338.html)). Douglas's ruling says the gripper actuator is PWM. So the gripper actuator is **not** an STS3215; the current CAD (`params.json` `servo.model = "Feetech STS3215"`) must be re-enveloped for the chosen PWM actuator. Owned by the actuator lane; recorded here because it changes the requirement map (section 4).

## 2. Cloth grasping and feeding literature

### 2.1 Grasping principles for fabric

| Principle | Notes | Source |
|---|---|---|
| Clamping / pinching | Most common; effective on flexible fabrics; our choice | [Koustoumpardis & Aspragathos review](https://www.researchgate.net/publication/256645552_A_Review_of_Gripping_Devices_for_Fabric_Handling) |
| Pins / microneedles | Top-ply-only pickup from a stack; lamprey-inspired soft microneedle gripper: **1.12 N** max holding force, 0.32 s actuation, picked air-permeable fabric a commercial vacuum pad could not [S] | ["Delicate Fabric Handling Using a Soft Robotic Gripper With Embedded Microneedles", IEEE 9123593](https://ieeexplore.ieee.org/document/9123593/) |
| Vacuum | Industry's usual single-ply-from-stack answer; likely weak on porous knits [A] | [Borràs et al.](https://arxiv.org/abs/1906.08202) |
| Electroadhesion | Fingertip-size (2 cm²) pad lifts top ply; high voltage; out of scope for ME102B | [HKRITA](https://www.hkrita.com/en/our-innovation-tech/projects/compact-electro-adhesion-gripper-fabric-handling) |
| Rollers | 6-DoF arm with a roller end-effector (active fabric rollers + passive press-roller) coordinates roller velocity to stretch and align plies during straight-line sewing | [Jin et al., arXiv 2607.29464](https://arxiv.org/abs/2607.29464) |

Takeaway: the 1.12 N microneedle holding force [S] shows how little force a sewing-feed hold needs. Robotic sewing research treats **fabric tension control** as the critical variable, with the machine's feed doing the pulling ([Springer IJIRA robot sewing](https://link.springer.com/article/10.1007/s41315-024-00326-1); [Kosmopoulos et al.](https://www.sciencedirect.com/science/article/abs/pii/S0736584513000574)). The gripper **guides and tensions**; it should not fight the feed dogs.

### 2.2 Single-ply vs multi-ply

- Tactile layer-count classification with ±2 mm height search was needed to reliably get 1 vs 2 layers from 3–5 mm thick towels [S] ([arXiv 2207.11196](https://arxiv.org/abs/2207.11196)). Vision alone did worse there.
- Pressing on the pile to open a gap, then clamping one layer, is one published strategy; industry uses vacuum instead [S] ([Borràs et al.](https://arxiv.org/abs/1906.08202)).
- A "very thin finger to slide under flat clothes" plus a touch sensor on the other finger is a proven cloth-gripper pattern [S] ([Borràs et al.](https://arxiv.org/abs/1906.08202)).
- Getting under an edge that "can easily twist in on itself" is the edge-grasp problem; a successful grasp for sliding needs one layer [S] ([Sunil et al., arXiv 2212.05108](https://arxiv.org/abs/2212.05108)).

**Recommendation [A]:** demo with one flat ply lying on the table, edge near the needle. Pick strategy: lower until the lower finger's tip touches the table (FSR or current spike), close. Give the lower finger a thin, stiff PLA "nail" (0.8–1.2 mm) at the tip so it slides under the edge. Put the TPU compliance behind it.

### 2.3 Pinch-force budget [D]

Pinch with two pads puts friction on both faces of the cloth: F_hold = 2 μ N.

| Quantity | Value | Tag |
|---|---|---|
| Cloth: 300 × 300 mm, 150 g/m² cotton | 13.5 g → 0.13 N weight | [A] areal density; [D] weight |
| Table drag while sliding, μ_table 0.3 | 0.04 N | [A]/[D] |
| Guide/tension force held against feed or presser drag | 2 N | [A], measure with a luggage scale |
| Pad–cloth μ, TPU 95A on cotton | 0.4 (range 0.3–0.6) | [A]; fabric-fabric μ ≈ 0.28–0.30 for cotton [S] ([cotton/polyester friction study](https://www.researchgate.net/publication/281064584_Roughness_and_frictional_properties_of_cotton_and_polyester_woven_fabrics); [Kawabata denim study](https://www.tandfonline.com/doi/abs/10.1080/15440478.2022.2069187)); printed TPU vs steel: TPU 82A gyroid μ peaks ≈ 1.06 at 50 % infill [S] ([Future Transp. 5(4):184](https://doi.org/10.3390/futuretransp5040184)); TPU 95A lowest mean μ 0.50 ± 0.01 [S] ([Technologies 14(9):536](https://www.mdpi.com/2227-7080/14/9/536)); elastomer gripper pads 0.48–1.22 on metals, ASTM D1894, vendor recommends 10× SF [S] ([PFA gripper pads](https://www.pfa-inc.com/modular-end-of-arm-automation/gripper-pads/)). Counterfaces are metal, not cloth, so 0.4 stays conservative [A] |
| Safety factor | 2 | [A] |
| **Required normal force N = SF·F / (2μ)** | **2·2 / (2·0.4) = 5 N** | [D] |
| Worst case μ = 0.3 | 6.7 N | [D] |

- No published TPU-on-textile μ was found; measure it with an incline test (pad on a tilted board covered with the demo fabric; μ = tan θ_slip) [A].
- Pad texture [A]: shallow cross-hatch ribs (0.3–0.5 mm) or a cast silicone skin (e.g. Shore 20–30A) should raise μ over smooth TPU 95A; knurled/pebbled elastomer pads beat smooth ones in the PFA data above [S], and softer infill raised printed-TPU μ [S] (Future Transp. above). Avoid sharp teeth: they snag knits and can pull threads.
- Cap force near 10 N [A]: enough margin, low enough not to crush the Fin Ray lattice flat and lose its compliance.

### 2.4 Fin Ray / compliant fingers on textiles

- Fin Ray fingers conform, carry more payload than pneumatic soft grippers, and have shown stable force feedback on soft fabric blocks [S] ([3D-printed Fin Ray with force feedback, PMC8538355](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8538355/); [MDPI Appl. Sci. 15(5):2576](https://www.mdpi.com/2076-3417/15/5/2576)).
- **Caveat for thin cloth [A]:** Fin Ray wraps *around* bulky objects. A 0.3 mm ply gives almost no wrap, and a soft tip can peel open under load, so contact runs from the tip back. Keep the tip region stiffer (thicker wall or PLA insert) and let the Fin Ray lattice give compliance behind the tip. That keeps the pinch at the tip, where the cloth is.
- Longer line contact transmits torque to cloth better than point pinch [S] ([Borràs et al.](https://arxiv.org/abs/1906.08202)). Pad depth 20 mm (`finger.depth`) is fine; keep the tip pads flat and parallel at closure.

### 2.5 Failure modes to design against

| Failure | Cause | Mitigation |
|---|---|---|
| Two plies grabbed | Edge folded or stacked | Single flat ply demo; nail finger; later tactile/vision check ([2207.11196](https://arxiv.org/abs/2207.11196)) |
| Miss (zero plies) | Pads not reaching table; `closed_gap` 1 mm | Touch-down detect; gap 0 plus preload (finding 4) |
| Slip during lift or feed | Low μ, low force | 5 N target, textured pads ([2207.11196](https://arxiv.org/abs/2207.11196) Fig. 5) |
| Snag or tear | Sharp texture, needle strike | Rounded ribs; release before the gripper reaches presser-foot zone (≥ 20 mm, [A]) |
| Wrinkle / bunching at feed | Gripper speed ≠ feed speed | Hold light tension, follow feed; roller research does velocity sync ([2607.29464](https://arxiv.org/abs/2607.29464)) |
| Edge twisted | Cloth edge curls | Approach flat, slide under ([2212.05108](https://arxiv.org/abs/2212.05108)) |

## 3. Camera placement

### 3.1 Options

| Placement | Pros | Cons | Fit |
|---|---|---|---|
| **Eye-in-hand (on gripper)** | Close view of the pick edge; no hand-eye extrinsic drift once mounted; SO-101 repo already ships wrist-cam mounts ([SO-ARM100 Optional/](https://github.com/TheRobotStudio/SO-ARM100/tree/eecbe3e0a9ebb23e25ad7b2759b03884c6660903/Optional)) | Fingers and cloth occlude the target at closure; motion blur; adds mass at the wrist; cable must cross the wrist roll | Pick phase |
| On arm (forearm/elbow) | Less occlusion than wrist; lower moment on wrist | Pose changes with every joint → needs forward kinematics per frame | Weak |
| **Fixed eye-to-hand, overhead** | Static, one-time calibration; sees cloth edge vs needle line; no cable through the arm; arm can be still while imaging | Arm and gripper occlude from above; sewing machine head blocks the needle view from straight above | **Primary** for edge alignment |
| Fixed side / oblique | Sees the gap under the presser foot; sees ply count on edge | Narrow useful view; lighting glare on machine bed | Optional second |

**Recommendation [A]:** fixed overhead camera, offset to look past the machine head at the bed in front of the presser foot. Now, reserve a wrist-camera boss in the gripper housing (SO-101's 32 × 32 UVC pattern, 4 × M2 [S] ([Wrist_Cam_Mount_32x32_UVC_Module README](https://github.com/TheRobotStudio/SO-ARM100/blob/eecbe3e0a9ebb23e25ad7b2759b03884c6660903/Optional/Wrist_Cam_Mount_32x32_UVC_Module/README.md))). Leave the camera off until CV starts, to save mass.

### 3.2 FOV / working-distance math [D]

Horizontal FOV from a diagonal spec for a 16:9 sensor: tan(H/2) = tan(D/2) · 16/√(16²+9²) = 0.872 · tan(D/2).
Footprint width W = 2 d tan(H/2). Resolution r = W / pixels.

Example: Pi Camera Module 3 standard, D = 75° [S] → tan(H/2) = 0.872 × 0.767 = 0.669, H ≈ 67° [D].

| Setup | d | W | px across | mm/px | Tag |
|---|---|---|---|---|---|
| Wrist cam | 100 mm | 134 mm | 1920 | 0.070 | [D] |
| Overhead | 500 mm | 669 mm | 1920 | 0.35 | [D] |
| Overhead, OV2640 SVGA, 66° diag (4:3, tan H/2 = 0.8·0.650 = 0.52) | 500 mm | 520 mm | 800 | 0.65 | [D] |

Target edge accuracy ±1 mm [A] (seam allowances are typically several mm). Overhead at 0.35 mm/px gives ~3 px per mm: enough for edge detection.

**Motion blur [D]:** blur_px = v · t_exp / (mm/px). Arm at 100 mm/s [A], 10 ms exposure [A] → 1 mm of motion = 14 px on the wrist cam, 3 px overhead. Rolling-shutter modules skew too. Mitigation: image with the arm stopped (a state-machine state), bright light for short exposure, or a global-shutter OV9281 ([Arducam](https://www.arducam.com/arducam-120fps-global-shutter-usb-camera-board-1mp-720p-ov9281-uvc-webcam-module-with-low-distortion-m12-lens-without-microphones-for-computer-laptop-android-device-and-raspberry-pi.html)).

**Calibration [A]:** overhead = one intrinsic calibration (checkerboard) + one homography to the machine bed plane (cloth is flat, so a planar homography is enough). Wrist = intrinsics + hand-eye calibration against SO-101 forward kinematics.

**Cable routing [A]:** wrist USB crosses the continuous wrist-roll joint; limit roll to ±180° and add a service loop, or use ESP32-CAM Wi-Fi to avoid the cable (it still needs power).

### 3.3 Candidate cameras (prices 2026-09-22)

| Camera | Price | Mass | Optics / rate | Interface | Tag / source |
|---|---|---|---|---|---|
| Raspberry Pi Camera Module 3 (std / wide) | from $25 | ~4 g board [A] | IMX708 12 MP, 75° / 120° diag, PDAF autofocus, 1080p50; 25 × 24 × 11.5 mm | CSI → needs Pi (Zero 2 W or 4/5) | [S] [raspberrypi.com](https://www.raspberrypi.com/products/camera-module-3/) |
| ESP32-CAM (AI-Thinker, OV2640) | ~$7 (eBay/Amazon range $6–15) | 6.8–8 g | 2 MP, 66° lens; UXGA 15 fps / SVGA 30 fps / VGA 60 fps; 40.5 × 27 × 4.5 mm; 180 mA @ 5 V | Wi-Fi stream; Arduino IDE | [S] [Maker Advisor](https://makeradvisor.com/esp32-cam-ov2640-camera/), [Handsontec datasheet](https://www.handsontec.com/dataspecs/module/ESP32-CAM.pdf), [OV2640 FOV](https://mikroelectron.com/product/ov2640-camera-module-esp32-cam-2mp-21mm-lens-66-wide-angle-dvp-24pin), [fps](https://blog.arducam.com/ov2640/) |
| 32 × 32 mm UVC module (SO-101 wrist mount; README links an innomaker module) | ~$20–30 [A] | ~10 g [A] | ≥ 720p30 required; README recommends running 640 × 480 @ 30 fps; manual-focus lens; 4 × M2 | USB UVC | [S] specs [SO-101 README](https://github.com/TheRobotStudio/SO-ARM100/blob/eecbe3e0a9ebb23e25ad7b2759b03884c6660903/Optional/Wrist_Cam_Mount_32x32_UVC_Module/README.md), [linked listing](https://www.amazon.com/innomaker-Computer-Raspberry-Support-Windows/dp/B0CNCSFQC1/); [A] price/mass |
| OV5640 5 MP AF USB module | ~$20–35 [A] | ~10 g [A] | 2592 × 1944, 60–65° | USB UVC | [S] listing [Amazon B08SBJRVSG](https://www.amazon.com/25921944P-Security-Monitoring-Industrial-Equipment/dp/B08SBJRVSG) |
| Arducam OV9281 global-shutter (CSI) | $25.99 | few g [A] | 1 MP mono, global shutter | CSI | [S] [Arducam](https://www.arducam.com/arducam-ov9281-mipi-1mp-monochrome-global-shutter-camera-module-raspberry-pi.html) |
| Logitech C270 | $29.99 | 75 g with housing | 720p30, 55° diag (older units 60°) | USB | [S] [logitech.com](https://www.logitech.com/en-us/shop/p/c270-hd-webcam); mass/FOV [S] [Tom's Guide](https://www.tomsguide.com/reviews/logitech-c270-hd-webcam) |

**Pick [A]:** overhead = Logitech C270 or a 32 × 32 UVC module on a clamp arm (mass irrelevant off-arm; UVC works with any laptop CV). Wrist (later) = 32 × 32 UVC module on the SO-101 mount pattern. ESP32-CAM is the choice if the team wants the camera on the same Arduino IDE toolchain; its 0.65 mm/px overhead at SVGA is marginal, so mount it nearer (d ≈ 300 mm → 0.39 mm/px [D]).

## 4. ME102B requirement map

| Requirement | How this gripper meets it | Tag |
|---|---|---|
| ≥ 1 moving transmission DOF | Jaw DOF: actuator → finger A gear sector → 1:1 mesh → finger B. The gear pair is the transmission. If the actuator is a bare DC gearmotor, its gearbox (plus an optional worm or pinion stage) also counts | design |
| ≥ 1 DC motor | **Option A (recommended [A]):** DC gearmotor with encoder (N20 class) driving finger A through PWM on an H-bridge (e.g. TB6612). That is a DC motor, PWM-controlled, and needs student-written position/force control, which reads better for the course. **Option B:** PWM hobby servo for the jaw (a servo contains a DC motor but hides it; check with course staff whether it counts) plus a separate small DC motor task (e.g. a cloth feed roller) | [A]; confirm with staff |
| PWM control (team ruling) | Both options are PWM. The arm's STS3215 serial bus stays for the arm only (finding 6) | ruling 2026-09-22 |
| ≥ 1 analog input | **FSR on one pad** (Ø½" area, 0.3–10 N, >20 MΩ unloaded, ~10 % unit-to-unit, $3.95 [S] [Adafruit 166](https://www.adafruit.com/product/166)) → grip-force threshold, touch-down detection, slip detection. The 10 N ceiling matches the 5–10 N budget [D]. Backup: potentiometer on the finger-B pivot for jaw angle, or motor-current sense resistor | [S]/[D] |
| ≥ 1 digital button input | START / STOP button; TEACH button to record a pick pose; limit switch at jaw fully-open for homing (switch = digital input and a clean event) | design |
| Microcontroller | Arduino-IDE board: ESP32 DevKit or Arduino Uno/Nano. ESP32 gives more PWM channels and Wi-Fi to talk to the arm/CV laptop | [A] |
| State machine | `HOME → IDLE → APPROACH → TOUCHDOWN → CLOSE → HOLD → FEED → RELEASE → RETRACT → IDLE`, plus `FAULT` (slip, over-force, timeout) | design |
| Event-driven programming | Events: button press (interrupt, debounced), FSR crosses touch threshold, FSR reaches grip setpoint, FSR drops (slip), limit switch hit, serial "arm at pose"/"feed done" message, timeout timer. Loop dispatches events to the current state; no blocking `delay()` | design |
| Computer vision (later) | Overhead camera finds cloth edge and needle line; wrist boss reserved now (section 3) | [A] |

Grip-force control loop [A]: in CLOSE, ramp PWM duty until FSR ≥ 5 N, then hold duty (DC motor) or hold that position (servo). FSR < 3 N during HOLD/FEED raises a SLIP event. That closes the loop the hobby servo cannot give by itself.

## 5. Assumptions (all to verify)

- Demo fabric is one flat ply of woven cotton, ~150 g/m², ~0.3 mm thick, ≤ 300 × 300 mm.
- Pad–cotton μ = 0.4 (0.3–0.6) for TPU 95A; measure by incline test.
- Guide/tension force held ≤ 2 N; measure against your sewing machine.
- Safety factor 2; force cap 10 N.
- Arm speed while imaging 100 mm/s, exposure 10 ms.
- Edge accuracy target ±1 mm.
- Pi Camera 3 board mass ~4 g; 32 × 32 UVC and OV5640 module mass ~10 g and price $20–35 (listing pages did not render).
- Release the cloth ≥ 20 mm before the presser foot.
- The PFA pad μ (0.48–1.22) and printed-TPU μ (0.50–1.06) are against metal; cloth μ may differ either way.
- Verified 2026-09-22 (retry pass): arXiv 2607.29464 and 2207.11196 titles/content, IEEE 9123593 1.12 N, SO-101 wrist-cam README, Adafruit 166, Pi Camera 3, C270. Earlier draft mis-cited 5(4):184 as a TPU 60A-vs-95A study; corrected.

## 6. Not found

- No open-access friction coefficient for TPU or silicone against cotton, denim or polyester. [Impact of cloth material characteristics on finger-gripper force (ResearchGate 387528462)](https://www.researchgate.net/publication/387528462_Impact_of_material_characteristics_of_cloth_on_the_gripping_force_and_performance_of_finger_grippers) measures silicone-finger vs textile μ by sled test but returned 403. [Han et al. 2021](https://onlinelibrary.wiley.com/doi/full/10.1002/pen.25717) and [Tribology Letters 2021](https://link.springer.com/article/10.1007/s11249-021-01502-1) measure related pairs but were paywalled; silicone surrogate skin had the highest μ vs cotton in the latter (abstract only).
- No published presser-foot force in newtons ([Wikipedia: Presser foot](https://en.wikipedia.org/wiki/Presser_foot) describes the mechanism only).
