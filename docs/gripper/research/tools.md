# Open-source tools survey — cloth-feed gripper

Date 2026-09-22. Machine: Windows 11, uv 0.12.2, Python 3.12.10. Tags: **[S]** sourced (URL), **[D]** derived (computed here), **[A]** assumed. License and activity from the GitHub API on 2026-09-22 [S]. Every tool is free. No prices apply.

## Summary

- **W2 analysis runs entirely through `uv` on this machine.** The chain is CadQuery STEP -> gmsh mesh -> scikit-fem solve -> pyLife fatigue. It was tested end to end on `cad/gripper/out/finger_a.step`, and re-run on 2026-09-22 with identical results (versions, 2.80 mm/N, 2638.8 mm³, SO101 6 actuators) [D].
- **CalculiX / FreeCAD FEM is the GUI cross-check.** It is not on PyPI and is not installed here.
- **No open-source VDI 2736 plastic-gear calculator was found.** Hand-code VDI 2736 / Lewis in Python and use `python-gearbox` (ISO 6336, steel-oriented) only as a cross-check.
- **Conflict: the ruling says "stick with PWM", but `params.json` still names the Feetech STS3215, which is a serial-bus servo.** The PWM-servo libraries below assume a PWM hobby servo. See `actuators.md`.

## Tool table

| Category | Tool | License [S] | What it solves for us | Install / test result on this machine [D] | Recommendation |
|---|---|---|---|---|---|
| FEA | [scikit-fem](https://github.com/kinnala/scikit-fem) 12.0.2 | BSD-3-Clause | Linear-elastic FEA of the TPU finger, the knuckle arm, and the housing in pure Python | **Works.** `uv run --with scikit-fem --with gmsh --with meshio`. 2D cantilever test solved. Full STEP -> tet -> solve on `finger_a.step` in 19 s (4035 nodes, 12196 tets) | **Primary FEA** |
| FEA meshing | [gmsh](https://github.com/gmsh/gmsh) 4.15.2 (PyPI wheel) | GPL-2.0+ ([gmsh.info](https://gmsh.info/)) | Imports STEP through OpenCASCADE and makes tet meshes | **Works.** Imported `finger_a.step` directly | **Primary mesher** |
| FEA I/O | [meshio](https://github.com/nschloe/meshio) 5.3.5 | MIT | Moves `.msh` files into scikit-fem, ParaView and CalculiX `.inp` | **Works** | Use |
| FEA | [CalculiX](https://github.com/Dhondtguido/CalculiX) via [FreeCAD FEM](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/FEM_Install.md) | GPL-2.0 / LGPL-2.1 | GUI FEA with a nonlinear/contact solver. The FreeCAD Windows build bundles `ccx.exe` ([FEM_Install](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/FEM_Install.md)) | **Not tested.** Not on PyPI. `ccx` and FreeCAD are absent from PATH and Program Files | Install FreeCAD for one cross-check of the finger's large deflection |
| FEA | [SfePy](https://github.com/sfepy/sfepy) | BSD-3-Clause | A scikit-fem alternative with a hyperelastic model | **Fails.** A source build fails on Windows under both Python 3.12 and 3.11 (no wheel) | Skip on Windows |
| FEA | [FEniCSx / dolfinx](https://github.com/FEniCS/dolfinx) | LGPL-3.0 | High-end FEA | **Fails.** `fenics-dolfinx` is not on PyPI. It needs conda, WSL or Docker | Skip; overkill |
| Gear geometry | [cq_gears](https://github.com/meadiode/cq_gears) | Apache-2.0 | Involute spur-gear solids in CadQuery (the same toolchain as `gripper_concept.py`) | **Works from git only.** `uv run --with "cq_gears @ git+https://github.com/meadiode/cq_gears.git" --with cadquery`. Not on PyPI. The m1, z24, b6, bore-3 gear builds at 2638.8 mm³ | **Use** to replace the hand-rolled involute in `gripper_concept.py` |
| Gear geometry | [freecad.gears](https://github.com/looooo/freecad.gears) | GPL-3.0 | FreeCAD Gear workbench: involute spur with profile shift, undercut, fillets ([wiki](https://wiki.freecad.org/Gear_Workbench)) | Not tested (needs FreeCAD; Addon Manager install) | GUI alternative to cq_gears if the team works in FreeCAD |
| Gear rating | [python-gearbox](https://github.com/efirvida/python-gearbox) 0.1.2a0 | LGPL-2.1 | ISO 6336 / AGMA 2101 bending and pitting classes (`gearbox.standards.iso.Bending`, `Pitting`) | **Imports.** Emits a SyntaxWarning (`is 0`). Last push 2020-05-09. The material model is steel | Cross-check only |
| Gear rating | VDI 2736 (plastic gears) | standard, not open | Root and flank stress limits for plastic gears. For POM/PA6, the starting-load root stress is about 15–20 MPa ([PMC10537784](https://pmc.ncbi.nlm.nih.gov/articles/PMC10537784)) [S] | No open-source calculator found | **Hand-code** the Lewis + VDI 2736 root-stress check in Python. `viewer.html` already has Lewis |
| Fatigue | [pyLife](https://github.com/boschresearch/pylife) 2.3.1 | Apache-2.0 | Wöhler (S-N) curves, Miner damage, rainflow counting | **Works.** Test: k=8, SD=20 MPa at 1e6 [A] gives 167,772 cycles at 25 MPa, which matches the hand calculation 1e6·(20/25)^8 [D] | **Use** for gear-tooth and snap-fit fatigue |
| Tolerance stack-up | [EasyStackup](https://github.com/robertdosa/EasyStackup) | MIT | 1D worst-case / RSS / Monte Carlo desktop app | Not tested (desktop app, 0 stars) | Optional |
| Tolerance stack-up | [tol-stack](https://github.com/slightlynybbled/tol-stack) | no license detected | Python Monte Carlo stack-up | **Fails.** Not on PyPI. Last push 2022 | Skip |
| Tolerance stack-up | numpy Monte Carlo (about 20 lines) | BSD (numpy) | Gear center distance, backlash, and jaw-gap stack | numpy works (already a dependency above) | **Use.** A spreadsheet or a numpy script is enough for 1D chains |
| Gripper design | [SO-ARM101-6DoF Compliant_Gripper](https://github.com/EmbodiedAI-Group/SO-ARM101-6DoF/blob/main/Optional/Compliant_Gripper/README.md) | Apache-2.0 | A TPU Fin Ray-style SO-101 jaw from the June 2025 LeRobot hackathon | Not downloaded (not a github.com/TheRobotStudio source) | **Reference** for rib layout and SO-101 mounting |
| Gripper design | [roboninecom SO-ARM100-101 Parallel Gripper](https://github.com/roboninecom/SO-ARM100-101-Parallel-Gripper) | CC-BY-4.0 | A parallel gripper driven by an STS3215 on the SO-101 | Not downloaded | Reference for the wrist interface |
| Gripper design | [SO-ARM100 stock SO-101 gripper](https://github.com/TheRobotStudio/SO-ARM100/tree/eecbe3e0a9ebb23e25ad7b2759b03884c6660903) | Apache-2.0 | The stock wrist and jaw geometry, and the wrist-roll horn pattern that `README.md` says is not modeled | **Downloaded** (sparse clone of `Simulation/SO101`) | **Use** to measure the wrist mount |
| Gripper design | [XLeRobot](https://github.com/Vector-Wangel/XLeRobot) fin-ray gripper | Apache-2.0 | SO-101-compatible Fin Ray TPU jaws; already swapped into an SO-101 sim model ([PickNik PR #929](https://github.com/PickNikRobotics/moveit_pro_example_ws/pull/929)) | Not downloaded | **Reference** finger geometry (PR lists finger 67.2 x 24.2 x 24.1 mm [S]) |
| Gripper index | [lerobotdepot](https://github.com/maximilienroberti/lerobotdepot) | MIT | Community list of LeRobot-compatible grippers and parts | Not needed | Browse before designing new parts |
| Gripper design | Open-source Fin Ray gripper for multi-robot manipulation ([article](https://www.opensourceforu.com/2026/09/open-source-fin-ray-gripper-enables-multi-robot-manipulation/)) | CC-BY-4.0 [S] | TPU fingers with a 45° strut angle chosen by FEA, PLA geared arms. The same architecture as ours [S] | Article gives no repo link; likely [vekkax/Fin-ray-Soft-Gripper](https://github.com/vekkax/Fin-ray-Soft-Gripper) (no license file per GitHub API) [A] | Cite the 45° strut result. Our `rib_angle` is 10° |
| Cloth robotics | [airo-mono](https://github.com/airo-ugent/airo-mono) | MIT | Camera calibration, grasp execution, and cloth-lifting utilities (backbone of the ICRA 2024 Cloth Competition) | Not tested | Reference for the later computer-vision work |
| Cloth robotics | [cloth-competition](https://github.com/Victorlouisdg/cloth-competition) + [dataset](https://zenodo.org/records/14621179) | MIT | Grasp-pose selection for cloth, 679 demonstrations [S] | Not tested | Reference for the later computer-vision work |
| Cloth robotics | [SoftGym](https://github.com/Xingyu-Lin/softgym) | BSD-3-Clause | Cloth-manipulation benchmark environments | Not tested. Last push 2022-11-14 | Skip (stale) |
| Arm simulation | [MuJoCo](https://github.com/google-deepmind/mujoco) 3.14.0 | Apache-2.0 | Physics simulation of the SO-101 plus the gripper | **Works.** `uv run --with mujoco` | **Use** |
| Arm simulation | [SO101 MJCF/URDF](https://github.com/TheRobotStudio/SO-ARM100/tree/eecbe3e0a9ebb23e25ad7b2759b03884c6660903/Simulation/SO101) | Apache-2.0 | The official SO-101 model | **Works.** `scene.xml` loads and steps: nq 6, nu 6, actuators shoulder_pan…gripper, bodies include `gripper` and `moving_jaw_so101_v1` | **Use.** Swap `moving_jaw` for our gripper to check wrist payload and reach. Now vendored in `cad/so101/Simulation/SO101/` (see `cad/so101/SOURCE.md`) |
| Arm control | [LeRobot](https://github.com/huggingface/lerobot) 0.4.4 | Apache-2.0 | SO-101 teleop and recording ([docs](https://huggingface.co/docs/lerobot/so101)) | **Works** in 102 s. `from lerobot.robots.so_follower import SO101Follower` imports. The docs' `so101_follower` path does not exist in 0.4.4 | Use for arm teleop and data collection |
| MCU servo | [ESP32Servo](https://github.com/madhephaestus/ESP32Servo) | no SPDX detected by the API | Arduino Servo API on ESP32 LEDC/MCPWM for a **PWM** servo ([Arduino docs](https://docs.arduino.cc/libraries/esp32servo/)) | Not tested (`arduino-cli` absent) | **Use** if ESP32. Use the stock `Servo.h` on AVR |
| MCU state machine | [Automaton](https://github.com/tinkerspy/Automaton) | MIT | A reactive, event-driven FSM framework with debouncing, timers and an event queue. Matches the course's state-machine and event-driven requirement | Not tested | **Use.** Alternatives: [SimpleFSM](https://github.com/LennartHennigs/SimpleFSM) (MIT), [arduino-fsm](https://github.com/jonblack/arduino-fsm) (MIT) |
| MCU button | [Button2](https://github.com/LennartHennigs/Button2) | MIT | Debounced click, double-click and long-press callbacks (the digital button requirement) | Not tested | **Use.** Alternative: [OneButton](https://github.com/mathertel/OneButton) |

## FEA smoke results (tool checks, not design results)

| Test | Result | Tag |
|---|---|---|
| 2D cantilever, 10×1, E = 3500 MPa, ν = 0.35, 1 N tip load, 80 P1 triangles | scikit-fem gives 0.69 mm. Euler beam theory gives PL³/(3EI) = 1.14 mm | [D] |
| Conclusion | Coarse **P1 elements lock** and read about 40% too stiff. Use P2 (`ElementTetP2`) or a finer mesh for bending | [D] |
| `finger_a.step`, TPU E = 26 MPa, ν = 0.45 [A], root clamped (top 0.5 mm), 1 N lateral load on the bottom 2 mm, P1, 1.5 mm mesh | Tip compliance 2.80 mm/N. This is linear small-strain and **stiff-biased** (P1 locking at ν = 0.45). Treat it as a lower bound on deflection | [D] |

## Recommended W2 analysis toolchain

1. **Geometry:** `gripper_concept.py` (CadQuery) -> STEP. Replace the tooth generator with `cq_gears` from git.
2. **Mesh:** gmsh (PyPI wheel) imports the STEP directly and meshes it with tetrahedra. Size the mesh so the 0.9 mm ribs get at least 2 elements through their thickness [A].
3. **Solve:** scikit-fem with P2 tetrahedra. Run the TPU finger, the PLA knuckle arm, and the gear-tooth root. The Fin Ray finger's large deflection needs one nonlinear cross-check in FreeCAD + CalculiX (install FreeCAD; `ccx` is bundled).
4. **Gear check:** a Python Lewis + VDI 2736 root-stress script sized to PLA, cross-checked against `python-gearbox` ISO 6336 bending. For comparison, the POM/PA6 starting-load root stress is 15–20 MPa [S]. PLA allowables still have to be sourced.
5. **Fatigue:** pyLife Wöhler curve plus Miner damage on the gear root stress over the cloth-feed duty cycle [A: cycles per shift to be set].
6. **Tolerances:** a numpy Monte Carlo on center distance -> backlash and on the closed jaw gap (`closed_gap` = 1.0 mm).
7. **System:** MuJoCo plus the official SO101 MJCF for wrist payload and reach. LeRobot 0.4.4 for teleop.
8. **Firmware:** Arduino IDE with ESP32Servo (PWM), Automaton (FSM) and Button2 (digital input). The analog input is `analogRead` (a potentiometer or FSR).

Reproduce any install: `uv run --with <pkg> python -c "import <mod>"`. The FEA smoke script used `uv run --with scikit-fem --with gmsh --with meshio python step_fem.py <path-to-finger_a.step>`.

## Assumptions

- TPU 95A: E ≈ 26 MPa, ν = 0.45. PLA: E = 3500 MPa, ν = 0.35. Used only for the tool smoke tests [A]. Design values are now sourced: Ultimaker TPU 95A TDS gives E = 67 (XY) / 56 (Z) MPa [S]; see `docs/gripper/DESIGN-BASIS.md`.
- The pyLife curve parameters (k = 8, SD = 20 MPa at 1e6) are placeholders, not PLA data [A].
- "Works" means the package installs and a minimal real computation runs on this machine. It does not mean the results are validated.
