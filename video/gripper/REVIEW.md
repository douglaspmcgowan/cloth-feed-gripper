# Review

Frames: `review/frames/land_XXs.jpg` and `vert_XXs.jpg`, one every 2 s of the final cut (31 per layout), written by `src/compose.py --frames-out`. Two passes: mine on the first full render, then one independent read-only reviewer that saw the frames, the deliverables, `STORYBOARD.md` and every cited source cold. Fixes from both are in the final render.

## Numbers

*Rev B.1 update: the list below is the rev A review as it stood; the S10, S3, S5, S7 and S8 values it names changed in the re-cut, see "Rev B.1 re-cut, 2026-10-16" at the end.*

The reviewer opened every cited line and confirmed every on-screen number: 0.3 mm, 12 states, 695 of 695, 5 / 8 / 10 N, +20°, −7.4°, 65 mm, 28.5 mm, m 1.5 z 19 25°, 2.06 g, $12.99, 144.4 g, 2304 × 1296 and 5.5 px/mm. The force trace matches `fw_sim.json` series `1.05 FEA E56+D7` (0.5 N at 0.50 s, 5.03 N plateau). The jaw-angle readout in S5 is the angle actually rendered in that frame.

## Findings and what was done

| # | Finding | Source | Fix |
|---|---|---|---|
| 1 | Final card showed for about 1.5 s | mine | S11 card now lands at 0:59, title holds 2.5 s |
| 2 | S2 framing cut the fingertips (also the S10 plate) | mine | S2 re-rendered with the camera 40 mm further out |
| 3 | Vertical: S6 headline ran off the right edge; S9 edge line ran below the camera frame; empty band above the square | mine | S6 wraps to two lines; the edge overlay is clipped to the frame; the square moved up (y 330) |
| 4 | S7 opened on an empty chart | both | The cut now enters the graphic 1.1 s in, just before contact |
| 5 | 144.4 g in accent orange read as a boast while R10 fails (115 %) | reviewer | Caption is now "with cloth, over budget"; the accent moved to the gear pair |
| 6 | S2 title ran over the orange fingers (also the poster) | reviewer | Title set in the left column on two lines, clear of the model |
| 7 | S4 spec lines ran over gear geometry | reviewer | Stronger light scrim behind the bottom-left type block |
| 8 | Vertical S5 cut the fingertips | reviewer | S5 re-rendered from 90 mm further back |
| 9 | Vertical S10 plate off centre | reviewer | Crop re-centred |
| 10 | Vertical chart labels small | reviewer | Square-layout chart labels 34 → 42 px, ticks 30 → 36 px |
| 11 | S3 callouts pointed at parts already hidden by the front plate | reviewer | Callouts now show while the parts are apart (0:09.8 to 0:13.3) |
| 12 | S5 lever line stopped short of the pad | reviewer | Line now runs pivot to fingertip |
| 13 | S9 headline collided with the edge line and the servo | reviewer | Moved to the top left inside the camera frame, two lines |

## Checked and kept

- **List markers in the vertical S3 callouts.** Short orange bars mark a vertical list; `DESIGN.md` bans the bullet and middle dot as *inline dividers*, which this is not.
- **Tonal seam where the vertical square meets the page.** Softened with an 80 px fade; left as is.
- **Fade from black at 0:00 and to black at 1:02.** Intended.
- **S1 macro is soft.** Intended shallow focus; the gear teeth read.

## Render quality pass, 2026-10-11

Was in "Not done": every 3D frame was 1280 × 720, 6 samples, fast denoiser, no motion blur, upscaled in the compositor, so flat PETG faces carried denoiser smearing and the 3D sat soft beside native-resolution type. Now every 3D frame is a native 1920 × 1080 render at 64 samples with the high-quality denoiser and motion blur on the GPU (settings, measurements and frame times: `README.md` § "3D render settings"), used 1:1; the vertical cut's S10 plate is its own 3413 × 1920 render. The cut, storyboard, numbers, type, colours, geometry and sound are unchanged. Before / after at 100 % for the six moments: `review/compare/`.

| Check | Result |
|---|---|
| a. 0:02, 0:06, 0:12, 0:20, 0:34, 0:50 at 100 % | 3D sharper in every 3D moment: gear tooth edges, screw heads, fillets and the finger ribs resolve where the upscaled frames were soft and stair-stepped; the blotchy smear on the flat housing faces (0:06, 0:12) is gone. No fireflies, banding or framing change (an automated pass over all 1,254 frames found no isolated hot pixels and no brightness jumps). 0:34 is the 2D force chart (S7) and is unchanged by design. |
| b. Numbers | Every number listed under "Numbers" is drawn by the unchanged `compose.py` and graphics code and reads the same in `review/frames/`; the S5 readout is still the rendered angle from `track.json` (+15.3° at 0:24 in both passes). |
| c. Vertical, thirteen fixes | Unchanged: the vertical crop is the same 1080 square of the same camera, now taken 1:1 from the native frame; fingertips in frame in S2 and S5; S6 headline wraps; S9 edge line clipped to the camera frame; S10 plate centred. |
| d. Browser playback | From a local `http.server`, headless Chrome with audio unmuted: `playing` fired 3 ms after `play()`, 2.85 s played in 3 s, 1920 × 1080, 62 s, audio and video bytes decoded. The moov atom is at the front of all three films. |
| Sound | Same `mix.wav` (62.000 s, peak −1.20 dBFS, RMS −17.15 dBFS); the AAC track measures max −0.9 dB, mean −17.2 dB (the earlier film: −1.1 / −17.2). |

Findings from this pass:

| # | Finding | Source | Disposition |
|---|---|---|---|
| 14 | Moving flat faces (the front plate opening in S3, the housing in S2) show a faint directional streak at 100 %: motion blur resolved by the denoiser at 64 samples. It reads as motion, not smear, at viewing size. | mine | Kept; 128 samples would roughly double the render (README budget). |
| 15 | In S5 the fingers swing fast enough that their motion-blurred tips go translucent for a few frames. | mine | Kept: it is the real shutter on the real motion. |
| 16 | "65 mm lever to the pad" (landscape S5) runs into finger A's tip; the same in the 2026-10-10 film. | mine | Not changed: moving type is outside this pass (no typography changes). Recorded for a layout pass. |

An independent read-only reviewer that saw only `review/frames/`, `review/compare/`, the deliverables, `STORYBOARD.md` and the checklist above passed a, b and c, and d's file checks (browser playback is the author's check above): sharper 3D in every moment, no smearing, no regression; every number present and matching; all thirteen vertical fixes hold. Its notes, none a blocker or should-fix, all present in the 2026-10-10 film:

| # | Finding | Disposition |
|---|---|---|
| 17 | Vertical S9 headline is "Fixed Pi Camera 3" without "on the seam edge" (landscape has both lines). | Kept: the vertical layout's shorter two-line headline is deliberate in `compose.py` (`ov_S9`); type is outside this pass. |
| 18 | Vertical S9 "Pi Camera 3, 2304 × 1296" label sits a few pixels above the gripper's top rim; no overlap. | Kept; for a layout pass. |
| 19 | Landscape S4 "1:1 sector pair" sits over gear-arm geometry, legible on the scrim (fix #7). | Kept. |
| 20 | S7 footnote reads "Firmware simulation, not a bench test"; `STORYBOARD.md` says "Simulation, not a bench test". | Kept: wording is unchanged from the merged film; align the storyboard text in a later pass. |
| 21 | Its count of the vertical state grid at 0:44 came to 11 boxes. | Checked: the grid has 12 (Boot, Home, Calibrate, Idle, Approach, Touchdown, Retract, Fault, Close, Release, Feed, Hold; Fault is dashed). No change. |

## Not done, and why

- **Finger wrapping the cloth.** The Fin Ray deformation would be invented geometry (no deformed mesh in the repository), so the fingers stay rigid and the cloth is pinched at the contact angle −0.3° (`DESIGN-BASIS.md:96`). The 3D never shows the jaw past 0° in S5 because the rigid pads overlap there by design (`cad/gripper/README.md:48`).
- **Cloth realism.** The ply reads slightly thick and lavender under the studio light at this sample count.
- **Sound** was measured (62.000 s, peak −1.2 dBFS, RMS −17.2 dBFS) but not listened to by a person.

## Rev B.1 re-cut, 2026-10-16

A fresh review (C2, 2026-10-15) found the S10 card still showing rev A. Every on-screen number in `src/compose.py` and `graphics/make_graphics.py` was re-checked against `master` and the stale ones now read from the committed sources (`src/film_numbers.py`). Finding 5 above (144.4 g, 115 %) is a rev A row and stays as history.

| Where | Was | Now | Source |
|---|---|---|---|
| S10 mass | 144.4 g | 152.9 g (121.2 % of the R10 budget) | `cad/gripper/out/fitcheck.json` `mass.total_g_incl_cloth`, `budget_use` |
| S10 servo price | $12.99 (DS3218MG) | $27.00 (DS3230 MG) | `docs/gripper/research/actuators.csv:44` (A32) |
| S10 gear pair | 2.06 g (8 mm face) | 2.56 g (10.5 mm face) | `analysis/gripper/results/gears.json` `cad_rev_b` |
| S3 servo callout | DS3218MG servo | DS3230 MG servo | `cad/gripper/out/parts.json` `servo_model` |
| S5 firmware floor | −7.4° | −10.2° | `firmware/gripper/config.h:83` |
| S7 trip line | 8 N trip | 7.75 N trip | `firmware/gripper/config.h:157` |
| S8 subtitle | 695 of 695 host checks pass | Every host check passes | two sources disagree: `controls.md:63` 2123, a run on 2026-10-16 2124 |
| S7 trace plateau | 5.03 N | 6.2 N | `analysis/gripper/firmware_sim/results/fw_sim.json`, regenerated in `53fc0c6` |

Unchanged and re-checked: 0.3 mm, 12 states, +20°, 65 mm, 28.5 mm, m 1.5 z 19 25°, 5 N, 10 N, 2304 × 1296, 5.5 px/mm. The 3D shots were not re-rendered in this lane; see `RECUT-RETURN.md`.

## C2 independent review, 2026-10-16

**Verdict: NOT READY — 1 blocker, 2 minor findings.** This pass inspected 31 frames extracted every 2 s from the merged 1920 × 1080 film, 16 every 4 s from the vertical film, five teaser frames, and `poster.png`. The S10 rev B.1 values are present in both cuts; the gear-pair value was additionally checked at 0:55 in the vertical cut. Audio exists in all three MP4s and `volumedetect` found no digital clipping.

| Severity | Timecode and file | Evidence | Recommended fix |
|---|---|---|---|
| **Blocker** | S2 0:06–0:08 and S6 0:28–0:32, `renders/gripper_hype_1080p.mp4`; S2 also in `poster.png` and `teaser_10s.mp4` | At native 1080p, the typeset title is crisp while the housing fasteners and edges are soft. In S6 the nail-to-cloth contact becomes more blurred as it closes, obscuring the action named by its caption. Extracted frames: `f_005.png`, `f_016.png`, `f_017.png`. The poster shares the S2 softness, so changing only MP4 compression will not satisfy `INTENT.md` `intent-gripper-film`'s “3D is as sharp as the type” criterion. | Adjust camera focus/depth of field and motion blur in `src/shots3d.py::shot_S2` and `::shot_S6`; inspect native source frames at 100% before re-encoding all four deliverables. Keep the S6 contact plane in focus throughout the move. |
| Minor | S9 0:48, `renders/gripper_hype_vertical.mp4` | Extracted `vert/f_013.png` says “Fixed Pi Camera 3” but omits “on the seam edge,” which `STORYBOARD.md` S9 specifies and the landscape cut displays. | Add the missing purpose in `src/compose.py::ov_S9`'s vertical layout so the camera's role survives the shorter cut. |
| Minor | S7 0:36–0:40, both full films | The chart labels `10 N cap` (`land/f_019.png`), while R15's permitted cap is 8 N; firmware has a 7.75 N trip and a separate 10 N absolute ceiling (`firmware/gripper/config.h:157,159`; `docs/gripper/DESIGN-BASIS.md:91`). The numeric value matches `film_numbers.py`, but “cap” alone can be read as the permitted limit. | In `graphics/make_graphics.py`'s `REFS`, label 10 N as the absolute ceiling and show the 8 N R15 limit. This distinguishes the safety guard from the requirement. |

**Numbers checked.** `python video/gripper/src/film_numbers.py` printed 152.9 g, DS3230 MG, $27.00, 2.56 g, 5/7.75/10 N, −10.2°, and 65 mm; the displayed values match. The other visible values match the storyboard's sources: one 0.3 mm ply (`DESIGN-BASIS.md:140`), +20° (`config.h:82`), m 1.5 / z 19 / 25° / 28.5 mm (`gears.md:12`), 12 FSM states (`fsm.h:20-22`), Pi Camera 3 at 2304 × 1296 and planned 5.5 px/mm (`camera.md:14`). The S7 trace ends at 6.2 N; its source series `1.05 FEA E56+D7` ends at 6.2002 N.

**Verification.** Both frame extractions and the three `ffmpeg -af volumedetect -f null -` runs exited 0. Frame outputs: 31 landscape, 16 vertical. Full-film audio mean −17.2 dB, peak −0.9 dB; teaser mean −17.2 dB, peak −2.0 dB. `ffmpeg`'s final progress lines reported `frame=31 time=00:01:02.00` (landscape frames), `frame=16 time=00:01:04.00` (vertical frames), `frame=1860 time=00:01:02.00` (each full-film audio check), and `frame=300 time=00:00:10.00` (teaser audio check).

**Could not tell.** The uncommitted 3D source frames and `S5/track.json` were absent here, so the original Blender resolution and each live jaw-angle readout could not be independently checked against its rendered pose. `volumedetect` proves signal level, not subjective sound quality.
