# Cloth-feed gripper: motion graphics storyboard

**Pitch.** A 62-second product film for a gripper that pinches one ply of cotton and feeds it to a sewing machine, built from the real CAD, the real jaw kinematics and the real firmware simulation, and honest that it has not been built yet.

**Audience.** ME102B course staff and classmates (do they see a working mechatronic design?), and a portfolio viewer (is this person's engineering careful and good-looking?).

**Rules held.** Every number on screen is cited below by file and line. Anything unproven is labelled as planned or simulated: the gripper is designed, simulated and host-tested, not built or bench-tested; R10 (mass) fails at 121.2 % of budget on rev B.1 (`cad/gripper/README.md:65`, `cad/gripper/out/fitcheck.json` `mass.budget_use`) and R19 (5 N within 0.75 s) is met in 50.8 % of simulated grips (`docs/gripper/analysis/controls.md:25`), so the film claims neither "light" nor "fast". Rev B.1 re-cut 2026-10-16: the numbers below are read from the committed sources by `src/film_numbers.py` (rev A values 144.4 g, $12.99 and 2.06 g are retired). Sentence case; no eyebrow labels; no middle dots; no monospace; no machine slogans.

## Toolchain

| Stage | Tool | Why |
|---|---|---|
| 3D | Blender 5.1.2 as the `bpy` Python module (PyPI), Cycles path tracer on the GPU (OptiX, else CUDA), OpenImageDenoise | Imports the 16 real STL parts from `cad/gripper/out/` with physically based materials, area lights and motion blur. S1 and the S10 plate retain deliberate depth of field; the engineering views S2 and S6 disable it so the mechanism and contact remain readable. |
| 3D resolution | Native 1920 × 1080, 64 samples, high-quality denoise, motion blur; used 1:1, nothing 3D upscaled | Chosen by measurement on SYSTEMATICCHAOS's RTX A4500 Laptop GPU: `README.md` § *3D render settings*. The first pass (1280 × 720, 6 samples, Lanczos upscale, 4 CPU cores) read soft |
| 2D graphics and type | Python, Pillow, numpy, drawn at 2× and downsampled | Reproducible, no browser; the force trace reads `analysis/gripper/firmware_sim/results/fw_sim.json` directly |
| Type | Archivo (variable, SIL OFL 1.1, Google Fonts) | A sans grotesque with real weight and width axes; Inter is banned as a default by `DESIGN.md:18` and `:50` |
| Sound | Procedural synthesis in numpy (no samples) | No licence to track; see `CREDITS.md` |
| Encode | ffmpeg, libx264, yuv420p, AAC | Standard |

**Look.** Light cool-grey studio sweep (`#d9dde1`), charcoal PETG, near-black PA6-CF with fibre speckle, steel and aluminium fasteners, black servo case. One accent: the signal-orange TPU fingers (`#e4561f`), reused for every highlight in the graphics. The cloth is indigo woven cotton.

**Vertical cut (1080 × 1920).** The centre 1080 × 1080 square of every landscape frame, with the type re-set above and below it. Every 3D shot keeps its subject inside that centre square.

## Shot list (30 fps, cuts on the 120 BPM beat grid)

| # | Time | Dur | On screen | Motion | On-screen text | Number sources |
|---|---|---|---|---|---|---|
| S1 | 0:00–0:04 | 4 s | Macro of the two PA6-CF sector gears, shallow focus | Camera slides along the pitch circle while the jaw closes from +20° to 0°; focus racks from tooth tips to the mesh | "One ply of cotton." then "0.3 mm thick." | 0.3 mm, one ply: `docs/gripper/DESIGN-BASIS.md:140` |
| S2 | 0:04–0:09 | 5 s | Hero three-quarter view of the whole gripper on the sweep | Slow orbit, 24°; jaw opens to +20° | "Cloth-feed gripper" (left column, clear of the model) / "ME102B, UC Berkeley" | ME102B: `cad/gripper/README.md:3` |
| S3 | 0:09–0:16 | 7 s | Exploded view assembling itself along the real Z stack | Parts start exploded, settle into place one group at a time (front plate last); orbit continues | Callouts: "PETG housing", "PA6-CF sector gears", "TPU 95A Fin Ray fingers", "DS3230 MG servo" | materials: `cad/gripper/README.md:29`, `:32`, `:33`; servo: `cad/gripper/out/parts.json` `servo_model`, `firmware/gripper/config.h:61` |
| S4 | 0:16–0:22 | 6 s | Front view through the gear plane, front plate hidden, gears meshing | Jaw closes +20° → 0° → opens; camera pushes in | "1:1 sector pair" / "m 1.5, z 19, 25°" / "28.5 mm centres" | `docs/gripper/analysis/gears.md:12` |
| S5 | 0:22–0:28 | 6 s | Straight-on view, both fingers, an angle arc at each pivot | Jaw sweeps +20° → 0°; a live readout tracks θ | Live "Jaw angle +20.0°" … "0.0°"; "65 mm lever to the pad"; "Firmware floor −10.2°" (the render stops at 0°: below it the rigid pads overlap by design, `cad/gripper/README.md:48`) | +20°: `firmware/gripper/config.h:82`; floor −10.2°: `config.h:83` (`JAW_MIN_DEG`); 65 mm: `config.h:111` |
| S6 | 0:28–0:34 | 6 s | Macro on the fingertips closing on one ply of indigo cotton | Pads close from +6° to contact, cloth pinched; slow dolly | "Nail on A slides under the edge" / "Force sensor behind B" | `docs/gripper/DESIGN-BASIS.md:20` (D7) |
| S7 | 0:34–0:41 | 7 s | 2D: grip force against time drawn from the firmware simulation; dashed references at 5, 7.75, 8 and 10 N | Trace draws on, a dot rides its head, then separated leaders label the close trip and requirement lines | "Grip force, simulated" / "5 N hold" / "7.75 N trip" / "8 N requirement (R15)" / "10 N conditional controller ceiling" / "Firmware simulation, not a bench test" | trace: `analysis/gripper/firmware_sim/results/fw_sim.json` series `1.05 FEA E56+D7`; hold / trip / conditional ceiling: `firmware/gripper/config.h` (`F_TARGET_DEFAULT_N`, `F_TRIP_N`, `F_CAP_N`); requirement: current `docs/gripper/DESIGN-BASIS.md` R15 owner-ruling row, parsed fail-closed by `src/film_numbers.py` |
| S8 | 0:41–0:47 | 6 s | 2D: the 12 firmware states; the grip cycle lights up IDLE → APPROACH → TOUCHDOWN → CLOSE → HOLD → FEED → RELEASE → RETRACT → IDLE | One transition every 0.5 s from 0:41.5, FAULT shown dimmed | "12 states, event driven" / "Every host check passes" | state count: `firmware/gripper/fsm.h:20-23` (`ST_BOOT` to `ST_FAULT`); no count is shown because two sources disagree (`docs/gripper/analysis/controls.md:63` says 2123 / 2123, `firmware/gripper/test/run_host_tests.py` on 2026-10-16 printed `PASS 2124 / 2124 checks`) |
| S9 | 0:47–0:52 | 5 s | 3D: the view from the fixed camera, oblique, onto the gripper holding the cloth edge; a frame and edge line overlaid | Slow push; the detected edge line draws along the cloth | "Pi Camera 3, 2304 × 1296" (frame label) / "Fixed Pi Camera 3 on the seam edge" / "Planned: 5.5 px/mm" | `docs/gripper/analysis/camera.md:14` |
| S10 | 0:52–0:57 | 5 s | Kinetic type over a deliberately blurred hero plate | Numbers count up and land one per beat | "153.9 g with cloth, over budget" / "$27.00 servo" / "2.56 g gear pair" (accent on the gear pair, not the mass) | 153.9 g and "over budget": canonical `cad/gripper/out/fitcheck.json` `mass.total_g_incl_cloth`, read at compose time by `src/film_numbers.py`; $27.00: `docs/gripper/research/actuators.csv` row matching the `parts.json` servo; 2.56 g: `analysis/gripper/results/gears.json` `cad_rev_b` row selected by servo and CAD face width |
| S11 | 0:57–1:02 | 5 s | Hero view, jaw closed on the cloth; end card from 0:59 | Slow push; a flat card fades over it at 0:59 and the title lands | "Designed and simulated." / "Bench tests next." then "Cloth-feed gripper" / "ME102B, UC Berkeley" | status: `cad/gripper/README.md:65`, `docs/gripper/analysis/controls.md:25` |

**Kinematics.** Every jaw pose uses the CAD's own rule: pivots at x = ∓14.25 mm (`cad/gripper/out/parts.json` `a` = 28.5), finger A turns −θ, finger B +θ about the gear axis (`cad/gripper/gripper_concept.py:574-578`), θ = 0 means the rigid pads are 1 mm apart, + opens (`firmware/gripper/config.h:77`). Jaw closing profiles in S1, S4, S5 and S6 are eased for the film; the speed is not a claim.

**Sound sync points.** Beat 0.5 s. Downbeat hits at 0:04 (title), 0:16, 0:34; gear clicks in S4; a soft servo whir under S5; a tick on each S8 transition (0:41.5 to 0:45.0); a resolving hit at 0:57.

**Materialization acceptance gate (2026-10-22).** The corrected source semantics and source-graphic proof do not accept checked-in encodes. Acceptance of replacement films requires an executed receipt for all 1,254 regular native frames plus the separate S10 plate, the canonical audio → graphics → compose → deliver chain, full H.264/AAC decode, frame-count and poster checks, and a fresh independent whole-film review with exact artifact hashes. Historical reviews describe only their dated bytes; current generation status and hashes belong in the actual executed receipts associated with this source PR. No native-render, encoded-film, hardware or bench acceptance is claimed here.
