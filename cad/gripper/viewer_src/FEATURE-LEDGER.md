# Gripper viewer feature ledger

Owner of `cad/gripper/viewer.html` continuity. Every view, figure, table, number, control and interaction in the 11-tab review is listed here with what happened to it in the app rework of 2026-10-09. Nothing is dropped without a row. Text is what gets cut; design evidence stays.

Request (Douglas, 2026-10-09): "in general look at the other design skills and turn the cloth griipper thing into a more effecitve app to view all the design things and cut out any unnecessary text. and then for detailed text be more intentional about the UI and how things are progressively disclosed."

## Capture

- Before: `python cad/gripper/viewer_src/viewer_build.py` at `origin/master` (ae0d09c), opened headless at 1440x900, every tab visited. 11 tabs, 65 controls plus 11 tab links, 26 tables, 18 chart figures, 2 canvases, 25 number tiles, about 12,500 words.
- After: `python cad/gripper/viewer_src/vw_test.py` visits every view, every figure tab and every disclosure level and prints the same counts. The totals are at the end of this file.
- A control keeps its element id wherever it survives, so the two captures compare by key.

## Information architecture

A reader of this page does four things: inspects the part, checks one number, sees whether an analysis passed, or finds what is still open. So the page is an app whose rail lists every design artefact with its status word, grouped as Design (3D model, Drawings, Fit check, Parts and BOM, Concepts), Analysis (Mass budget, Torque and actuator, Finger, Gears, Dyno, Tolerance stacks, Camera) and Build (Firmware and controls, Open items). The first screen is the 3D model, and the rail (the Views menu on a phone) reaches any artefact in one action. Each view shows one figure at a time through figure tabs, so a view fits one screen instead of scrolling like a report. Mass budget is split from torque because it has its own verdict (it fails), and the fit checks, drawings and BOM are split from the model because each is a thing a reader opens on purpose.

## Disclosure levels

The same four levels, in the same order, with the same controls, in every view.

| Level | What it holds | Control | Anchor |
|---|---|---|---|
| 1 Verdict | status word and one sentence | always shown under the view title | `#<view>` |
| 2 Figure and key numbers | one figure with its numbers and inputs beside it | figure tabs; Full screen on every figure | `#<view>-<figure>` |
| 3 Method and assumptions | how it was worked out, in short paragraphs and tables | the Method and assumptions button | `#<view>-method` |
| 4 Sources | repository paths of the documents, data and scripts | the Sources button | `#<view>-sources` |

Reading help for a figure sits behind its "i" button. On a desktop the "i" and Full screen buttons sit in the figure tab row. A table or chart wider than its card says "Scroll sideways, or open full screen" under it. Opening level 3 or 4 expands in place below the figure and does not move the page; the address bar updates so the open state can be linked. Tabs take arrow keys, every control is a native button, input or select, and Escape closes help and full screen.

## Rulings applied

| Ruling | Effect |
|---|---|
| No KPI tile strip unless the numbers are the point | all 25 tiles removed; each figure moved into its view's verdict sentence or the key numbers beside its figure |
| One-screen app rather than a long document | rail plus figure tabs; no view is a scroll of sections |
| Plain titles | tab numbers and compound titles removed |
| Helper text behind "i" buttons | every how-to-read note moved behind the figure's "i" |
| No internal codes shown to readers | requirement, measurement, load-case, concept, actuator, stack and criterion codes replaced by plain names; sourced/derived/assumed letter tags removed. Fit-audit requirement ids B4, B18, B19, B38 and F09 are allowed because they identify the graded checks beside their measured values. |
| Full-screen figures | every figure has Full screen |

## Ledger

Disposition is one of: kept, merged into X, cut (with the reason).

### Shell

| Key | Item | Disposition |
|---|---|---|
| shell.title | `<title>` Cloth-Feed Gripper Review | kept, unchanged |
| shell.h1 | page heading | kept as the rail name "Cloth-feed gripper" |
| shell.overline | "ME102B, SO-101 wrist, design review" label | cut: eyebrow labels are banned by the harness design rules |
| shell.meta | build date and branch sentence | cut: provenance is in level 4 of each view |
| shell.tags | sourced / derived / assumed legend and the per-number letter tags | cut: internal codes; "assumed" is written out where it changes a reading |
| shell.tabs | 11 numbered tabs | merged into the rail (14 views in 3 groups); numbers cut |
| shell.hash | `#<tab>` routing | kept; old tab hashes still resolve (`#overview`, `#actuators`, `#fea`, `#controls`) |
| shell.remember | last tab remembered in localStorage | kept |
| shell.footer | list of source files | merged into level 4 of each view |
| shell.theme | light and dark tokens, FEA redraw on theme change | kept |

### Overview (old tab 01)

| Key | Item | Disposition |
|---|---|---|
| ov.lede | paragraph describing the design | cut to the 3D model verdict sentence; the parts it named are the parts list |
| ov.kpis | 8 tiles: mass-moment, mass, hold margin, close time, tip stiffness, gear safety factor, stacks passing, camera | cut as tiles; merged into the verdict sentences of Mass budget, Torque and actuator, Finger, Gears, Tolerance stacks and Camera |
| ov.req | requirement status table, 27 rows, with counts | kept in Open items, Requirements; code column cut; a status filter added |
| ov.req.legend | four-status legend | merged into the Requirements "i" |
| ov.dec.hook | decision: firmware path blocked by a hook | cut: resolved (hook fixed, TASK.md 2026-10-07); firmware status is one line in Firmware and controls |
| ov.dec.gsi | decision: does the servo count as the DC motor | kept in Open items, Decisions |
| ov.dec.mass | decision: mass budget ruling | kept in Open items, Decisions |
| ov.dec.close | decision: close time disputed | kept in Open items, Decisions, restated from the controls analysis (contact at 0.50 to 0.51 s, 4.5 N at 0.60 to 0.70 s) |
| ov.dec.fold | decision: finger folds below the cap | kept in Open items, Decisions, restated as the squeeze cap with zero margin against a finger that folds at 8.4 to 8.9 N |
| ov.cad | CAD status table, 12 rows | merged into Fit check (checks and method) and Drawings; the "2D render not done" row is cut because the drawings now exist |

### 3D model (old tab 02)

| Key | Item | Disposition |
|---|---|---|
| model.lede | frame and pose paragraph | cut to the "i" and level 3 |
| #v3d | 3D canvas, orbit and zoom | kept, larger |
| #jaw | jaw angle slider and readout | kept |
| #explode | exploded view | kept |
| #ctxBtn | SO-101 wrist toggle | kept |
| #stockBtn | stock gripper ghost | kept |
| #resetCam | reset view | kept |
| #v3dhud | angle and mass readout on the canvas | kept |
| #v3dmsg | loading and failure messages | kept |
| model.note | overtravel and jaw sweep note | merged into the "i" and Fit check |
| #massKpis | 2 live tiles: mass and mass-moment of the parts shown | kept as one live sentence beside the parts list |
| #plist | 16 part checkboxes with colour and mass | kept |
| model.readout | how the live readout is computed | merged into level 3 |
| #fitTable | fit check table, 28 rows | merged into Fit check, Checks |

### Concepts (old tab 03)

| Key | Item | Disposition |
|---|---|---|
| con.lede | screening paragraph and decision | cut to the verdict sentence |
| #transChart | mass-moment against close time per transmission | kept; points labelled by name |
| #transTable | transmission table, 10 rows | kept; code column cut; footnote behind the "i" |
| con.spaces | other design spaces table, 6 rows | merged into the option chart (a materials row added) |
| #comboTable | concept combinations, 6 rows | kept |
| con.morph | morphological chart, 11 rows | kept; the number marks are replaced by a "Show concept" select that highlights that concept's options |
| #pughCase | weight case select | kept |
| #pughTable | scoring matrix with hover reasons | kept; each score is a button so the reason is reachable by keyboard and touch |
| con.note | close-time screen note | merged into the verdict and the "i" |

### Mass and torque (old tab 04)

| Key | Item | Disposition |
|---|---|---|
| mass.lede | back-calculation paragraph | cut to the two verdict sentences and level 3 |
| #chain | six-step live chain | merged into #sensOut, the live key numbers beside the sliders; the tiles repeated them |
| #sensCtrl | 9 sliders and reset | kept |
| mass.formula | formula line | merged into level 3 |
| #sensOut | 7 live results | kept as the key numbers beside the sliders, with the chain values added |
| mass.breakeven | break-even note | merged into the Torque and actuator verdict |
| #rcChart | hold torque against moment arm | kept |
| #tornado | sensitivity tornado | kept |
| #kitChart | allowable mass against centre-of-mass distance | kept in Mass budget |
| #kitTable | budget per arm kit | kept beside the payload figure |
| #rollTable | mass roll-up, estimate against CAD | kept in Mass budget, Roll-up |
| mass.measure | 6 bench measurements | merged into Open items, Bench checks |

### Actuators (old tab 05)

| Key | Item | Disposition |
|---|---|---|
| act.lede | trade paragraph | cut to the verdict and level 3 |
| #top3 | 3 cards: pick, backup, DC branch | kept as one three-column comparison in Torque and actuator, Shortlist |
| #actQ #actKind #actPass #actCount | filter, kind, passing only, count | kept |
| #actTable | 52-row trade table, 14 sortable columns | kept; code column cut; sort headers are buttons |
| act.note | how to read the table | merged into the "i" |
| act.measure | 2 bench measurements | merged into Open items, Bench checks |

### Finger FEA (old tab 06)

| Key | Item | Disposition |
|---|---|---|
| fea.lede | recommended finger paragraph | cut to the verdict and level 3 |
| #feaCase #feaF #feaE #feaField | load case, force, modulus, field | kept |
| #feaCanvas | deformed mesh with colour bar and info line | kept; the info line is now the key numbers beside the mesh |
| #kWin | stiffness against the window | kept |
| #sweepChart | 289-run sweep scatter | kept |
| #sweepKpis | 6 count tiles | cut as tiles; kept as key numbers beside the sweep |
| fea.fold | fold check table, 5 rows | kept |
| fea.measure | 3 bench measurements | merged into Open items, Bench checks |

### Gears (old tab 07)

| Key | Item | Disposition |
|---|---|---|
| gear.lede | load cases, sweep size, pick | cut to the verdict; loads are key numbers; sweep size is level 3 |
| #gearCards | 3 cards: printed pick, robust, CNC | merged with #gearCmp into one comparison table, Gears, Picks, shown at full height |
| #gearMap #gearMat | design-space map and material select | kept |
| #gearProf | tooth profile | kept |
| #gearMatTable | per-material table, 8 rows | kept |
| #gearCmp | printed against CNC, 11 rows | merged into Gears, Picks |
| gear.measure | 4 bench measurements | merged into Open items, Bench checks |

### Dyno and fatigue (old tab 08)

| Key | Item | Disposition |
|---|---|---|
| dyno.lede | two-fit paragraph | cut to the verdict and level 3 |
| #dynoKpis | 5 tiles | cut as tiles; each number sits beside its own figure |
| #tsChart | torque against speed | kept |
| #tiChart | current against torque | kept |
| #dutyChart #dutyWin | duty cycle, 4 panels, window select | kept |
| #thermChart | 30-minute thermal curve | kept |
| #thermTable | 12 thermal cases | kept; case names written out |
| #rankChart | grips to failure ranking | kept; note behind the "i" |
| #shockTable | shock events | kept; rebuilt as a table with units |
| dyno.measure | 4 bench measurements | merged into Open items, Bench checks |

### Tolerances (old tab 09)

| Key | Item | Disposition |
|---|---|---|
| tol.lede | method paragraph | cut to the verdict and level 3 |
| #tolKpis | 4 tiles | cut; the two pass counts are the verdict sentence |
| #tolShow #tolQ | show select and filter | kept |
| #tolTable | 71 results, sortable | kept; stack code replaced by the stack name and the variant in words |
| tol.note | verdict method note | merged into the "i" |
| tol.datum | datum scheme, 4 rows | merged into Drawings, Datums |
| tol.gdt | GD&T callouts, 12 rows | merged into Drawings, Callouts; the stack-code column is cut |
| tol.fixes | fixes table, 10 rows | kept; proof column reads the result from the data |
| tol.measure | coupon list, 5 items | merged into Open items, Bench checks |

### Controls (old tab 10)

| Key | Item | Disposition |
|---|---|---|
| ctl.lede | architecture paragraph | cut to the verdict and level 3 |
| ctl.blocked | "BLOCKED" box | cut: no longer true; the view status is the controls verdict, conditional |
| #fsmChart | state diagram | kept; redrawn so no edge crosses a label, with a one-column layout under 860 px |
| #fsmTable | 20 transitions | kept; now the firmware's own transition table with its timeouts |
| ctl.thresholds | thresholds table, 9 rows | kept; values read from the firmware configuration |
| ctl.pins | pins and host protocol, 8 rows | kept |
| ctl.measure | 3 bench checks | merged into Open items, Bench checks |

### Camera (old tab 11)

| Key | Item | Disposition |
|---|---|---|
| cam.lede | placement paragraph | cut to the verdict and level 3 |
| cam.options | 4 options table | kept |
| #camChart #camSel | 486 placements scatter and camera select | kept; the 264 placements that see none of the edge are one labelled point at the origin, counted in the key numbers |
| cam.mount | chosen mount paragraph | merged into level 3 |
| #camTop | top 10 placements | kept; the placement kind is written out and its parameters kept |
| cam.measure | 6 bench measurements | merged into Open items, Bench checks |

### Added

| Key | Item | Why |
|---|---|---|
| rail | grouped view list with a status word per view | reach any artefact in one action; see what passed |
| drawings | 5 part drawings from `cad/gripper/drawings/*.svg`, each with pinch, button and keyboard zoom, drag to pan, and its key dimensions as text beside it | the drawings exist in the repository and were not in the page; the sheets are read-only, so the text makes them usable on a phone |
| fit.section | fit-check section and isometric drawings | same |
| bom | BOM, fasteners and off-arm items from `cad/gripper/drawings/BOM.md` | same |
| con.sketches | 6 transmission sketches from `docs/gripper/figures/concept_*.svg` | same |
| cam.views | camera view and layout figures from `docs/gripper/figures/camera_*.png` | same |
| full | Full screen on every figure | standing ruling |
| info | "i" help on every figure | standing ruling |
| depth | Method and assumptions, Sources buttons | disclosure levels 3 and 4 |
| open.checks | every bench check in one list, grouped by view | "find what is still open" |
| fw.sim | step response, stiffness sweep, noise and slip, and sensor fault charts with their tables, drawn from `analysis/gripper/firmware_sim/results/fw_sim.json` | the controls analysis landed; live charts replace its PNG figures |
| fw.gates | proving commands and their results from `gates.json` | shows what the conditional verdict rests on |
| fw.decisions | Decisions needed block: close time, and squeeze cap margin, each with the recommended option | the two decisions the controls analysis leaves open |
| scrollcue | scroll cue under a table or chart wider or taller than its card, with the row count | a clipped table gave no sign it scrolled |
| con.scoresum | weighted totals and close-time result as text under the scores table | the last rows were cut off on a phone |
| chart.narrow | charts laid out narrower on a phone, with the legend as text below | labels shrank to about 6 px at 375 px wide |

## Totals

Ledger rows: 108. Kept 61, merged 27, cut 20. Added 16. Every cut is text, a tile strip, an internal code or a statement that is no longer true; no control, figure or table was cut.

| Count | Before (11 tabs, 1440x900) | After (`vw_test.py`, 1440x900) |
|---|---|---|
| Views | 11 tabs | 14 views |
| Figures reachable by tab | not applicable, one scroll per tab | 57, each with Full screen and an "i" note |
| Detail panels (levels 3 and 4) | 0 | 28 |
| Tables | 26 | 31 |
| Chart figures | 18 | 24 |
| Images (drawings, sketches, camera figures) | 0 | 16 |
| Number tiles | 25 | 0 |
| Controls (buttons, selects, inputs) | 65 plus 11 tab links | 329, of which most are score buttons, figure tabs, Full screen, "i", zoom and sort headers |
| Internal codes in reader-facing text | throughout | 0 outside the five fit-audit requirement ids allowed by the test |

Review fixes, 2026-10-09: the "Status by view" list under the model was removed because the rail already carries it; the torque chain tiles were merged into the key numbers; the open Method and assumptions button measures 6.31:1 in light and 7.79:1 in dark.

Second review fixes, 2026-10-09: the firmware review log and its process paragraph were cut from Method and assumptions, and the transitions table gives each event in plain words; the six concept sketches are embedded without their in-image titles, codes and numbers box, and their numbers are text under each sketch; the smallest chart label is 11.3 px or more at every tested width; no control, figure or table was cut.

## Rework 2, 2026-10-10: 3D fit check, one Parts view, assembly, links

Request (Douglas, 2026-10-09): "make the fitcheck something that iv interatively visualized in 3d. there are things to fix here. ... in general thigns should be more interlinked. like every part should cut to an image and or a 3d vieweer of that with a good way to view it. why isn't the per part view integrated withthe part bom with another way to view just the bom or partlist of both. ther are probablyother ways to consolidate and interconnect stuff. please do taht. and then if there are better 3d libraries that can make this seem evern more realistic, try taht too. also make assembly plans and a place to view each step in 3d motion. let's make this a full thing." Correction relayed 2026-10-10: "things to fix being the app ing eneral", so a whole-app first-reader pass is part of the work.

### Layout and disclosure plan

- One 3D engine and one WebGL context for the whole page. The canvas moves into the stage of whichever of the four 3D views is open (3D model, Fit check, Parts, Assembly), and each view sets a mode: arm context, fit overlays, one part isolated, or the assembly animation. Phones keep one context, and a lost context is restored once.
- Rail, Design group, in reading order: 3D model, Fit check, Parts, Assembly, Drawings, Concepts. Parts and BOM is merged into Parts; `#bom` and its figure anchors still resolve.
- Fit check, level 2: the 3D check (stage plus a list of checks to tick, each with its worst value over the travel and its live value), Findings (every failure or tight value with its number and a Show in 3D button), All checks (the old table), and the two old sheets. Levels 3 and 4 unchanged in form.
- Parts, level 2: Browse (part rows with thumbnails beside the selected part in 3D, its drawing sheet and an Appears in list) and List only (one sortable table, filters, totals). Every part has a bare anchor, `#housing`, `#knuckle-a` and so on.
- Assembly, level 2: Steps (3D stage with play, pause, previous, next, replay step and a scrub bar beside the numbered step list; the open step shows its parts, fasteners, tools, check and any finding) and Findings and tools.
- Selection: choosing a part anywhere (model tree, BOM row, drawing, fit finding, mass roll-up row, tolerance stack, assembly step) selects it everywhere; a selection bar in the rail, or along the bottom on a phone, names it and offers Open part.

### Ledger, rework 2

| Key | Item | Disposition |
|---|---|---|
| shell.rail | Design group | reordered: 3D model, Fit check, Parts, Assembly, Drawings, Concepts |
| shell.three | three.js 0.147 UMD scripts | replaced by three.js 0.186.1 ES modules through an import map, one pinned version; ambient occlusion loads only where it is used |
| #v3d, #jaw, #explode, #ctxBtn, #stockBtn, #resetCam, #v3dhud, #v3dmsg | 3D model controls | kept; the canvas is now shared with Fit check, Parts and Assembly |
| #lookBtn | Shadows and shading | added: physically based materials per material, room lighting, soft shadows and ambient occlusion, switched off on phones and slow machines |
| #plist | 16 part checkboxes | kept; each row's name selects the part everywhere and Open opens it in Parts |
| ctx.height | arm wrist context mesh | fixed: it was exported with the horn face at 49.75 mm, before the 2026-09-23 repackaging, so the arm sat 18.75 mm above the gripper; re-exported at 31.0 |
| fit.section, fit.isometric | the two fit sheets | kept as the Section sheet and Isometric sheet tabs |
| #fitTable | all checks table | kept as the All checks tab |
| #fitNums | fit key numbers | kept beside Findings, with the 3D gaps added |
| #fit-3d | 3D fit check | added: jaw slider over the full travel, wrist roll, sweep, section plane, a tick per check, gap lines with values, overlaps tinted |
| #fit-findings | findings table | added: every overlap and every gap under 0.5 mm, worst first, each with Show in 3D |
| #bom | Parts and BOM view | merged into Parts; `#bom`, `#bom-parts` and `#bom-fasteners` resolve to it |
| #bomTable, #fastTable | parts table and fasteners table | merged into one List only table with every fastener line, a filter, sorting and totals that equal the BOM |
| #offList | off-arm items | kept beside List only |
| #parts-browse | part rows | added: thumbnail drawn from the 3D model, quantity, material, mass, print settings; opens the part in 3D with others faded, alone or exploded, dimensions, section, its drawing sheet and an Appears in list |
| #assembly | Assembly view | added: 26 steps in 6 groups from `cad/gripper/assembly/steps.json`, animated along each insertion direction, with play, pause, previous, next, replay, scrub, per-step parts linked to Parts, and steps that jump under reduced motion |
| #selbar | selection | added: a part chosen anywhere is highlighted in every view, with Open part |
| verdict links | numbers in each verdict | added: each links to the figure it comes from |
| req.evidence | requirements | added an Evidence link per requirement; rows sorted fail, at risk, open, pass |
| open.deck, open.dogpin | two decisions | added from the assembly check |
| bench.link | Bench checks for this view | kept, now says how many |
| tables.cards | wide tables on a phone | the requirements table reads as label and value rows under 600 px |
| tabs.phone | figure tabs on a phone | one scrolling row instead of wrapping rows |
| here | current view name in the phone header | cut: the view title is directly below it |
| fw.decisions | Decisions needed block on Firmware and controls, with `#fwDecClose` and `#fwDecCap` | merged into Open items, Decisions; Firmware keeps one line linking to both |
| torque.sliders | slider labels | renamed: every label carries its unit or range; "Tension offset" is now "Pad position" |
| #sensOut | live results | regrouped under Needed at the pad and the servo, the build servo (named from `params.json`) the pick, DS3218MG as the rev A comparison, and DS3235 the alternative; the 10 N cap row now reads the 8 N cap (ruling 2026-10-12) |
| #tornado | sensitivity chart | relabelled in plain words; the servo limit label sits above the plot |
| #kWin | stiffness chart | in-chart labels moved to a key under it; the 0.88 and 1.63 limits stay |
| #tsChart | torque and speed | line labels shortened to Hold and Cap inside the plot; values in the key |
| #thermTable | thermal cases | Fit, Ambient and Resistance merged into Scenario; the result is the second column |
| #gearMap | design space | rows read "Module 1.5 mm"; cells focusable; `#gearMapRead` readout added |
| #rollTable | mass roll-up | two-row header so it fits a phone; rows select their parts |
| #pughSum | weighted totals | a ranked list, one concept per line |
| #actTable | all actuators | names split into a title and a spec line; fallback kind written out |
| #tolShow | tolerance filter | defaults to failing stacks; a status chip leads each stack name |
| table.full | short tables (pins, gates, cases, faults, camera options, kit, roll-up, gear materials, fold check) | no inner scroll box |
| open.horn | decision | added: the servo horn turns 0.2 mm from the housing wall |
| thumbs | part thumbnails | rendered from the page's own model by `make_thumbs.py` into `thumbs.json`, so they show without 3D graphics |
| fit.help | helper sentence above the checks | cut to "Tick a check to show it in 3D"; each check reads Worst and At this pose, and a zero gap says touches |
| asm.arrows | insertion arrows | added: each step draws an arrow along the direction its parts go in |
| asm.tools | tools list | deduplicated and sorted; "none" dropped |
| selbar.phone | selection bar on a phone | moved from a floating bar into the header, so it covers nothing |
| bom.tfoot | totals row | no longer sticky inside a scroll box; the list-only table shows every row |

### Totals, rework 2

Rows in this rework: 44. Kept 7, merged 3, cut 2 (the duplicate view name in the phone header and the long helper sentence in Fit check), changed in place 21, added 11. No control, figure or table was removed; the BOM tables and Firmware's decision block were merged, each with its new home named above. `vw_test.py` at 1440x900 counts 15 views, 61 figures, 30 detail panels, 32 tables, 24 charts and 457 controls.

## Rework 3, 2026-10-11: a fit you can see

Request (Douglas, 2026-10-10): "the 3d viewing of the fit check isn't good yet." The gaps that matter are 0.1 to 0.6 mm inside a 150 mm assembly, so the view now works one finding at a time: it flies to the finding, cuts the model through the two closest points, and draws that cut to scale beside the stage. Every number still comes from `out/fit3d.json` and the files it cites; `fit3d.py` now also writes, per finding, the section cut, the faces within 1 mm of the other part, each overlap as its own solid, the worst case under the stated tolerances, and the insertion path of the parts that cannot be fitted.

### Ledger, rework 3

| Key | Item | Disposition |
|---|---|---|
| #fit-3d | 3D check | changed: opens on the worst finding (a failure) at its worst pose, its two parts solid and the rest faded; Whole assembly returns to the old overview |
| #fitPick, #fitPrev, #fitNext, #fitCount, #fitAll | finding bar | added: a grouped picker (fails, at risk, tight, by design, clear), previous and next, "n of N", and Whole assembly; at 375 px the picker shows the finding title (its longest is 260 px, inside the box) and #fitPickRead under the bar names the full finding and its value, so the choice is readable without scrolling |
| .vtools | view presets | added: Front, Side, Top, Iso, Finding (frame it again) and Reset, on the stage; keys 1 to 4, F and 0 |
| #fitCard | finding card | added: value and verdict in words, when it happens, why, the faces involved, nominal, worst case and required, the tolerances used with their sources, and a link to the matching open decision |
| #fitSec | magnified section | added: the cut through the two closest points drawn to scale, the gap dimensioned with its value, the requirement as a band, the worst-case loss as a band, a scale bar, a key and zoom; a dog-pin elevation for the dog pin |
| #fitChartP | gap against motion | added: gap against jaw angle over the full travel (gap against roll for the wrist), with the requirement line, the worst-case line, the −7.4° firmware floor and the smallest point; drag or arrow keys move the jaw, and the jaw moves its cursor |
| #fitLegend | nearness and overlap key | added: the distance ramp for faces within 1 mm, and by design or not intended for overlaps, in words |
| overlap solids | interference bodies | changed: each overlap is its own solid from the boolean intersection, red when not intended and green by design, with its volume; the tinted spheres are cut |
| section | #fitCut select, #fitCutPos | changed: Section, X, Y, Z, Finding and Flip as one segmented control, capped cut faces coloured as the inset key, an offset slider in 0.1 mm and a drag handle on the plane; the select is cut |
| #fitReset | Reset view | merged into the Reset preset |
| #fitChecks | checks to tick | changed: each check keeps its worst value and gets Show, which opens its finding; the tick boxes and "At this pose" readouts are cut because one finding at a time replaces stacked overlays; the list moved beside the card |
| #fitList | findings list | added under the stage: every finding worst first, each opening its finding |
| #fitLink | Copy link | added: a link per finding that restores finding, jaw, roll, camera and cut (`#fit-f-<id>~j=..~r=..~c=..~s=..`); `go()` strips the part after "~" so every older anchor still resolves |
| build findings | deck screws 1 to 3, dog pin | added as fit findings: the insertion path as an arrow, the screw where it first hits, the blocker and the contact; the dog pin as an elevation against its slot |
| tolerance | worst case | added: worst case from `analysis/gripper/tolstack` and `stacks/basis.yaml`; where no tolerance is stated the card says "nominal only" and names what is missing; a gap that closes at worst case is "at risk" with the reason |
| #fitFind, #fitNums, #fitTable, sheets | Findings, All checks, Section sheet, Isometric sheet | kept; Findings rows are the same findings with Show in 3D |
| fgrid | layout | changed: the findings list fills the column under the stage, so the tall card, section and chart leave no empty block; on a phone the card follows the stage and the list comes last |
| open links | link from a finding to its decision | restored: the old findings rows linked the deck screw overlap and the roll gap to Open items; the card now links overlaps and deck screws, the dog pin, the horn clearance and the roll gap |
| overlaps-body | 12 overlaps in the body | changed after the fresh-eyes pass: graded "by design" with the count of by-design overlaps, because the one error is its own failing row above it and was being counted twice in "n findings fail"; the error solid is drawn through the parts in front of it, since it sits inside the housing and was invisible |
| fit headline | tightest gap | changed after the fresh-eyes pass: "the tightest gap between a moving part and the body", since the gear mesh (0.11 mm) and the fingers past the floor (0.00 mm) are smaller and the old "tightest moving gap" read as a contradiction |
| #fitChartW, chart key | worst point | changed after the fresh-eyes pass: a gap that does not change over the travel or the turn says so and draws no worst-point dot; the key names the shaded band past the firmware floor and the band below zero |
| #fitSec, build findings | contact in the section | changed after the fresh-eyes pass: the deck-screw section also cuts the material the screw shares with its blocker 1 mm past first touch (`fit3d.py`), so the inset shows where they hit; the 3D contact solid is drawn through the housing |
| #fit3d .hud | pose chip on a phone | changed after the fresh-eyes pass: under 560 px the chip sits under the view presets, clear of the key in the bottom corner |
| #fitCard, #fitSec, #fitChart | the 0.10 mm band | changed after the second cold pass: 0.10 mm is the roll gap's own requirement and reads "Required" there; for every other pair it is the running clearance the tolerance basis assumes for the wrist keep-out, so it reads "Running clearance" with "none is stated for this pair"; the gear mesh, a contact by design, carries no band at all |
| #fitCard | stack ids and raw notes | changed after the second cold pass: a tolerance stack is named by what it checks, not by its file id; ">=" and source tags in quoted notes are put in words; the roll card says the stack starts from 0.80 mm while the CAD measures 0.56 mm, so the stack's loss is taken off the measured gap |
| #fitCard | what "at risk" means | changed after the fresh reviewer's pass: the reviewer read "at risk", "Clear as drawn" and a negative worst case as a contradiction; the card now says "Clear as drawn, not clear at worst case", names a negative worst case as the parts going into each other, and says why it is at risk and not failing (the worst case takes every stated tolerance at its limit at once) |
| #fitCard, roll | answer first | changed after the fresh reviewer's pass: the roll card leads with what the gap does over a turn (it does not change, so no angle is tighter), then the tolerance; the stack's starting gap and the All checks figure move to a note under it, and "ring method" is replaced by what the All checks tab does |
| #fitAns | answer line above the stage | added after the fresh reviewer's pass: where the card sits under the stage (phone, tablet) the value, the verdict and one line of reason are repeated above the 3D view; hidden where the card is beside the stage |
| #fitLoc | locator | added after the fresh reviewer's pass: the whole uncut gripper drawn small in a corner of the same canvas (a second viewport of the one WebGL context), with a dot where the finding is, because a close view of a 0.2 mm gap could not be placed on the gripper; off for the whole assembly |
| frameFinding | framing on a portrait stage | changed after the fresh reviewer's pass: the camera stands back by 1/√aspect on a stage narrower than it is tall, and a gap is framed from 55 mm instead of 45 mm |
| overlaps-body, whole assembly | overlap label | changed after the fresh reviewer's pass: the label of the not-intended overlap stands off on a leader, since it sat on top of the small red solid and hid it |
| #fitCard, chart key | firmware floor | changed after the fresh reviewer's pass: said once in words, "the lowest angle the firmware drives the jaw to"; the deck-screw card points at "Assembly check notes" by name |

### Totals, rework 3

Rows in this rework: 32. Kept 1, merged 1, changed 18, added 11, restored 1. Cut: the stacked check tick boxes and their live readouts, the overlap spheres and the section select, each replaced by the row named above.

### Ledger, fit-check review

| Key | Item | Disposition |
|---|---|---|
| `fit_requirements.json` | governing clearances | added: B18 and B19 are the single source for limits, directions, sources and sampling allowances |
| fit statuses | requirement comparison | changed: fail below the limit, at risk within the sampling allowance, clear only above it; neutral statuses are "no requirement" (ungoverned pairs), "governed elsewhere" (a B4, B38 or T07 feature check governs the pair and is met) and the "Unverified arm clearance" group (R9 wrist-flex clearance needs an arm check); a governed pair whose feature check fails or is within the rounding resolution of a limit shows fail or at risk |
| fit headline | status counts | changed: reports fail, at risk and no-requirement counts from finding statuses |
| overlap findings | instance and case | changed: titles add left/right, front/rear and height; proper part-name case is preserved |
| document head | character encoding | added: UTF-8 declaration is the first fragment bytes |
| fit method | sampling uncertainty | changed: states jaw/roll increments, rounding and the adjacent-pose allowance method |
| static tests | browser-free contract | added: encoding, sources, statuses, allowances, titles, case, reproducibility and immutable audit hash |

### Ledger, rework 4 (fit check 3D audit, 2026-10-15)

Request (Douglas, 2026-10-10): "the 3d viewing of the fit check isn't good yet." Audit against the seven named capabilities found all seven already shipped in rework 3 and the fit-check review; none was rebuilt. Rows below record what was added or changed.

| Key | Item | Disposition |
|---|---|---|
| finding-first camera and isolation, magnified section inset, interference solids and distance colouring, capped section, gap against jaw angle, tolerance-aware gaps, view presets | `vw_test.py` JS_FIT8 groups 1 to 7 | kept; each capability has a group that fails if it regresses |
| section arrow | drag handle on the cut plane | kept; a real-mouse drag step now covers it in `vw_test.py` (`extra["fit section drag"]`) |
| forced WebGL context loss | restore step in `vw_test.py` | changed: waits for the page's own `V3.lost`, then asks for the restore until it is back; the loss wait is 15 s, not 3 s, since a late loss event under CPU load made the restore a no-op |
| `fit3d_inputs.py` digest | tolerance inputs | changed: hashes the `basis.yaml` constants `fit3d.py` reads and its one stack row, not the whole files; `fit3d.json` re-recorded |

## Review app on rev B.1 (2026-10-16)

Request: the consolidated review of `b33548d` found numbers and labels that did not follow the generated data. Rows changed or added in this pass.

| Key | Item | Disposition |
|---|---|---|
| torque card, `vw_5` Torque and actuator | hold margin and servo name | changed: the build servo's name and stall come from `D.params.servo.models[D.parts.servo_model]`, the hold fraction from `params.json`; the DS3218MG appears only as the labelled rev A comparison |
| Hold at least 5 N per pad, `vw_5` | risk text | changed: build servo numbers; the DS3218MG tension and friction limits kept, labelled rev A |
| Hold at most 40 % of stall, `vw_5` | risk text | changed: the build servo's stall at 6.5 V; the datasheet-difference sentence cut because it described the DS3218MG |
| breakTxt, `vw_5` decision | rev A break points | labelled rev A |
| #sensOut, `vw_7` | pick card and close-time cell | changed: the build servo row, the close limit of 0.75 s and the 8 N cap from the ruling of 2026-10-12 (`R19_CLOSE_S`, `R15_CAP_N`) |
| #tornado, #rcChart | servo limit line | changed: 40 % of the build servo's stall |
| #fitCount, `vw_11` | finding counter | changed: reads Finding n of N, so no count of pairs is shown; N is the number of findings, not the 40 jaw pairs |
| #fitChartP | gap against jaw angle, y ticks | changed: the tick format follows the tick step where the default labels would repeat |
| viewport meta, `vw_1` | page head | added: width=device-width, initial-scale=1 |
| section handle, `vw_11` | drag on the cut plane | changed: only a press within 18 px of the arrow head slides the section; a press anywhere else orbits |
| section handle, `vw_11` (2026-10-16, lane viewer-drag-load) | hit test | changed: a raycast against the arrow's head mesh decides the grab, not a screen-space radius; `vw_test.py` drags the head mesh centre (cut moves) and the canvas centre (camera orbits, cut unchanged) |
| forced context-loss restore under load | `vw_test.py --restore-only 10 --load` | added: one busy-loop process per CPU, fresh browser per run. Result: RESTORE 10/10 under load (4 busy loops), exit 0; no viewer change was needed |
| `fit3d.py` host facts | horn and roll tolerance rows | changed: no absent stack or constant is named; the horn-to-flange tolerance and the r 14.6 band are recorded as missing with their reason |
