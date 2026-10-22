# Gripper hype video

A 62-second motion graphics film of the ME102B cloth-feed gripper, built from the real CAD meshes, the real jaw kinematics and the firmware simulation. Shot list, on-screen numbers and their sources: `STORYBOARD.md`. Rev B.1 numbers (mass, servo, gear pair, force lines, floor) are read from the committed CAD and firmware files by `src/film_numbers.py`; run it to print them. Review: `REVIEW.md`. Licences: `CREDITS.md`.

Source correction 2026-10-22: S2 and S6 are configured as sharp engineering views; S7 distinguishes the R15 ≤ 8 N requirement from the 7.75 N firmware trip and conditional 10 N controller ceiling; S10 still reads its mass from canonical `fitcheck.json` (currently 153.9 g). Existing encoded deliverables have not been regenerated and remain pending native materialization and an independent whole-film review.

## Deliverables (`renders/`)

| File | What |
|---|---|
| `gripper_hype_1080p.mp4` | 1920 × 1080, 30 fps, H.264 + AAC |
| `gripper_hype_vertical.mp4` | 1080 × 1920 vertical cut, same timeline |
| `poster.png` | Poster frame (0:08.5, the title) |
| `teaser_10s.mp4` | 10 s teaser (0:04 to 0:14), 1280 × 720 |

## Re-render from source

One command, from the repository root:

```sh
PY=/path/to/python3.13 sh video/gripper/make_all.sh
```

Setup once: `python3.13 -m venv venv && venv/bin/pip install bpy==5.1.2 numpy pillow`, and ffmpeg on `PATH`. Nearly all the time is Cycles (see "3D render settings" below). Intermediate frames go to `video/gripper/build/` (git-ignored).

3D only, on Windows from Git Bash or PowerShell-launched `sh`, with the venv this film was rendered from:

```sh
PY=<gripper-film venv>/Scripts/python.exe sh video/gripper/src/render_3d.sh                     # GPU: OptiX, else CUDA, else CPU
GRIPPER_DEVICE=cpu PY=<gripper-film venv>/Scripts/python.exe sh video/gripper/src/render_3d.sh  # CPU only
SHOTS="S6 S9" SPP=128 sh video/gripper/src/render_3d.sh                                                        # some shots, other samples
```

Every frame logs the device that rendered it (`FRAME S2 12 3.10s 1920x1080 64spp high mblur pid 19220 on GPU OPTIX NVIDIA RTX A4500 Laptop GPU`). Rendering is resumable: a frame is written as `NNNN.part.png` and renamed when complete, and frames already on disk are skipped.

Production materialization must start with an empty native frame cache (or independently prove every required frame exists): S1 120, S2 150, S3 210, S4 180, S5 180, S6 180, S9 150 and S11 84, plus the separate 3413 × 1920 S10 plate. Do not use `compose.py`'s nearest-previous-frame preview fallback for a production encode. On the existing host pipeline, run `src/render_3d.sh` with Blender/bpy 5.1.2, OptiX, 1920 × 1080, 64 spp, high OIDN, motion blur and threshold 0.01; render the plate separately, then run the existing audio → graphics → compose → deliver chain. No CPU fallback is acceptance evidence for this correction.

| Step | Script | Output |
|---|---|---|
| Sound | `audio/make_audio.py` | `build/audio/mix.wav` |
| 2D shots S7, S8 | `graphics/make_graphics.py all` | `build/graphics/` |
| 3D shots | `src/render_3d.sh` → `src/shots3d.py <shot>` (scene in `src/scene3d.py`) | `build/frames3d/<shot>/`, plus `track.json` screen positions for the overlays |
| Type, overlays, both layouts, encode | `src/compose.py` | `build/*.mp4`, `review/frames/` (one frame every 2 s) |
| Deliverables | `src/deliver.py` | `renders/`, ffprobe lines |

Preview a shot fast: `python src/shots3d.py S5 --w 480 --h 270 --samples 2 --every 30 --out /tmp/prev`, then `FRAMES3D=/tmp/prev python src/compose.py --layout land` writes `build/animatic_land.mp4`.

## 3D render settings

Every 3D frame renders at native 1920 × 1080 and is used 1:1 by the compositor; nothing 3D is upscaled. The vertical cut takes a 1080 × 1080 square from each landscape frame at 1:1, and its S10 plate is its own 3413 × 1920 render of S2 frame 149 (`S10_plate`), so no 3D pixel is enlarged in either layout. `compose.py` refuses a 3D frame that is not 1920 × 1080 unless `FRAMES3D` points it at a preview.

Chosen: **64 samples, adaptive threshold 0.01, OpenImageDenoise high quality with the accurate prefilter (on the GPU), motion blur on (0.5-frame shutter centred on the frame), persistent data on**, on SYSTEMATICCHAOS's NVIDIA RTX A4500 Laptop GPU through OptiX. The earlier pass was 1280 × 720, 6 samples, fast denoiser, no motion blur, 4 CPU cores.

Measured 2026-10-11 with `src/bench3d.py` (warm frame times: the frame after a settings change is discarded, then the frame and the next one are timed and averaged), 1920 × 1080, three frames: a flat PETG face (S2 frame 60), the gear macro (S1 frame 90) and the cloth pinch (S6 frame 150). 100 % crops of every setting: `review/bench/bench_S1.png`, `bench_S2.png`, `bench_S6.png`; raw lines: `review/bench/bench.jsonl`; table: `python src/bench_sheet.py <benchdir> <outdir>`.

| Frame | Samples | Motion blur | s / frame | RMS difference from 256 spp, 8-bit levels |
|---|---|---|---|---|
| S1 90 | 32 / 64 / 128 / 256 | off | 14.9 / 71.1 / 68.4 / 12.3 | 0.65 / 0.53 / 0.42 / 0 |
| S1 90 | 32 / 64 / 128 / 256 | on | 2.2 / 3.9 / 7.1 / 13.1 | 0.68 / 0.54 / 0.42 / 0 |
| S2 60 | 32 / 64 / 128 / 256 | off | 4.7 / 20.1 / 11.6 / 21.4 | 1.39 / 1.06 / 0.73 / 0 |
| S2 60 | 32 / 64 / 128 / 256 | on | 1.8 / 3.1 / 7.0 / 9.9 | 1.38 / 1.06 / 0.73 / 0 |
| S6 150 | 32 / 64 / 128 / 256 | off | 9.6 / 12.8 / 41.3 / 50.0 | 2.06 / 1.32 / 0.82 / 0 |
| S6 150 | 32 / 64 / 128 | on | 17.6 / 14.9 / 28.2 | not measured: the 256 run was cut off |

The host was short of memory while this ran (other lanes; under 2.5 GB of 32 GB free, thousands of page faults a second), so the motion-blur-off column swings by up to 14× between two timings of the same frame; the motion-blur-on column, timed later in each run, is the steady one and is what the budget uses. Motion blur did not cost time on the GPU.

Budget, from the motion-blur-on times (S1's for S1, S2's for S2 to S5, S6's for the three tilted cloth shots S6, S9 and S11; 1,254 frames): 64 samples ≈ 120 × 3.9 + 720 × 3.1 + 414 × 14.9 ≈ 8,900 s ≈ 2.5 h; 128 samples ≈ 17,500 s ≈ 4.9 h. 64 samples is the highest setting that fits the 2.5-hour target. At 100 % the 64 and 256 crops differ by about one 8-bit level; flat PETG faces carry no denoiser blotching at 64 with the high-quality denoiser, where the 720p pass smeared them.

### Measured render

SYSTEMATICCHAOS, 2026-10-11, NVIDIA RTX A4500 Laptop GPU through OptiX, every frame at the chosen settings (frame times from the `FRAME` log lines; wall time per shot includes scene build and Blender start):

| Shot | Frames | Median s / frame | Wall time, min |
|---|---|---|---|
| S1 | 120 | 4.7 | 25.2 |
| S2 | 150 | 5.4 | 62.5 |
| S3 | 210 | 8.2 | 30.9 |
| S4 | 180 | 3.7 | 13.7 |
| S5 | 180 | 3.1 | 13.8 |
| S6 | 180 | 4.2 | 14.6 |
| S9 | 150 | 3.1 | 8.8 |
| S11 | 84 | 3.2 | 5.0 |
| S10 plate (3413 × 1920) | 1 | 23.7 | 0.5 |
| **All** | **1,255** | | **175 (2.9 h)** |

The steady frame time is the median: at the medians the whole 3D render takes about 1.6 h. The wall time ran over because the host was short of memory (other lanes): single frames stalled for up to 17 minutes in S2 and 7 minutes in S1, and S4's first attempt died with its console at frame 13 and resumed from there. On an idle machine budget about 1.6 h. The CPU path still works at the same settings but is not practical for the whole film: `GRIPPER_DEVICE=cpu` rendered S2 frames 60 and 61 in 192 s and 207 s on all 24 logical cores (with the compositor running alongside), about 70 h for 1,254 frames; on a machine without a GPU, lower `SPP` (the compositor requires 1920 × 1080 frames).

GPU proof: a production frame's log line, `FRAME S2 60 15.42s 1920x1080 64spp high mblur pid 39740 on GPU OPTIX NVIDIA RTX A4500 Laptop GPU`, and `nvidia-smi` during that render: `0   N/A  N/A  39740  C  ...s\Python\Python313\python.exe  N/A` (process type C, compute).

### Re-render 2026-10-16 (rev B.1 geometry)

SYSTEMATICCHAOS, `make_all.sh` from a clean `build/`, GPU OptiX (`DEVICE GPU OPTIX NVIDIA RTX A4500 Laptop GPU`), same settings as above; all 1,255 frames logged `on GPU OPTIX`. The host was again shared with other lanes (one headless Chrome took about 20 of 24 cores for a stretch; 3 to 7 GB of 32 GB free), so the times are contended ones. Wall time per shot is the sum of its frame times.

| Step | Frames | Median s / frame | Wall time, min |
|---|---|---|---|
| `audio/make_audio.py` | | | 40 (pure-Python per-sample filters on a busy CPU) |
| `graphics/make_graphics.py all` | | | about 7 |
| S2 | 150 | 17.1 | 63.5 |
| S1 | 120 | 10.0 | 28.4 |
| S3 | 210 | 7.2 | 29.8 |
| S4 | 180 | 9.0 | 31.1 |
| S5 | 180 | 7.9 | 26.9 |
| S6 | 180 | 8.7 | 28.7 |
| S9 | 150 | 6.2 | 17.9 |
| S11 | 84 | 5.3 | 8.9 |
| S10 plate (3413 × 1920) | 1 | 54.6 | 0.9 |
| **3D, all** | **1,255** | | **236 (3.9 h)** |
| **Whole `make_all.sh`** | | | **307 (10:21 to 15:28 PDT), exit 0** |

GPU use sat at 10 to 25 % through the 3D pass, so these frame times were bound by the contended host, not by samples; on an idle machine the 2026-10-11 medians (about 1.6 h of 3D) still apply.
