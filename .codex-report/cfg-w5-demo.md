# Professor demo lane

## Scope and intake

Source: fleet-route-ca0d60b247f240d2a2508df46c234639.md; local lane on SYSTEMATICCHAOS, branch agent/cfg-w5-demo. User explicitly requests a PR, overriding the brief's commit-only delivery. No Work Scope enrolment, reconciliation, repair, or generated task views are used as evidence.

- [x] Read craft, impeccable, design-review, slides, PRODUCT.md, DESIGN.md, SPEC.md and README.md.
- [x] Baseline both pages at 1440, 768 and 375, light and dark; screenshots inspected.
- [x] Remake landing hierarchy, purposeful motion and accessible five-step tour.
- [x] Capture captioned 60–90 second walkthrough; encode H.264 faststart under 15 MB with small poster.
- [x] Add behavioral regression tests and observable specification criteria.
- [x] Inspect final renders, exercise primary flow and run all proving commands.
- [x] Update branch, commit, push and open PR: https://github.com/douglaspmcgowan/cloth-feed-gripper/pull/20 .

## Findings before

Live screenshots: Temp/cfg-w5-demo/before/{landing,review}-{light,dark}-{1440,768,375}.png, plus landing full-page captures.

- Major, landing below film: identical two-column bands flatten the distinction between explanation, evidence and navigation; a first-time reviewer must decide their own reading order. Fix: distinct mechanism sequence, guided review and evidence regions.
- Major, #inside: four useful destinations exist, but no tutorial explains the question to ask in each view. Fix: an optional inline guide with explicit stop links, backward navigation and a close action.
- Minor, #film-actions: two equally weighted tonal actions obscure the primary film action. Fix: give play the primary tier, preserve the direct review link.
- Preserve: actual film imagery, honest unbuilt statement, facts.json figures, working deep links, responsive wrapping and light/dark token parity.
- Review app is usable and renders real model geometry in all six captures; no changes to generated review files are needed.

## Design plan and skill sweep

Stage: built but unpolished. Mode: Read, supported by the film. Audience: a professor opening a design record on desktop or phone. Preserve the established Public Sans and blue-gray system; this is a layout and onboarding extension, not a new visual identity. The four destinations stay a bounded navigation list; nine or ninety evidence items belong in the review app rather than becoming more landing-page doors.

Ordered checks: baseline/detector → critique/audit → layout/clarify/onboard → adapt/harden → optimize/animate → rendered review/primary flow → document/test/delivery. The output and proof of each step are recorded below.

| Capability | Decision and target-specific reason | Proof |
|---|---|---|
| craft, impeccable, design-review | Run: requested governing design route | Baseline and final screenshots, report |
| critique, audit | Run: diagnose hierarchy, responsive and keyboard behavior | Findings before/after, browser tests |
| layout, typeset, clarify, distill | Run: restructure landing, keep one type family and shorten repetitive prose | Final screenshots and visible strings |
| onboard, animate | Run: optional guided route and sequence motion | Tour/reduced-motion tests |
| adapt, harden, optimize, polish | Run: mobile, focus, media failure and lazy loading | Browser tests and network assertions |
| document, spec | Run: record shipped rules and criteria | DESIGN.md and SPEC.md |
| ui-feature-ledger | Skip formal ledger creation: FEATURES.md is outside lane ownership; preserve the existing controls through their live regression checks | Existing regression suite; no claim of a new ledger |
| shape, init, stack, hue, colorize, extract | Skip: established static stack and shared palette are pinned; no new system or product discovery |
| bolder, quieter, delight, overdrive, live | Skip: evidence called for hierarchy and teaching, not stronger ornament, variants or effects |
| visualize, image-artist, imagegen-frontend-web, brandkit | Skip: real film and screen recording are the required assets; no synthetic product imagery |
| slides, frontend-slides, html-slides | Skip: this deliverable is a website and screen recording, not a deck |
| voice, tune | Skip: preserve factual engineering prose; no personal-voice rewrite requested |
| compare-options, grill-me, brainstorming | Skip: audience, scope, navigation and visual system are settled by brief; no questions requested |
| present | Skip a separate first-viewer study: the requested independent design review covers clarity; no separate naive-viewer rubric is claimed | Independent review answers and bounded limitations below |
| user | Run the bounded independent matrix: identify status, use guide, reach fit evidence, return Home, play/close walkthrough | Six live primary-flow combinations |
| probe | Skip a formal test-effectiveness campaign and unowned root ledger; focused failure detection belongs to this feature's regression work | Red/green tour and clipping regressions; no mutation score claimed |
| hone, spar, tech-debt-audit | Skip: no measured performance incident, adversarial campaign or architecture audit in this bounded lane |
| review | Run final diff and behavior review within owned paths | Checks and PR |

Prior art: W3C APG disclosure pattern (https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/) supports a native button with aria-expanded and aria-controls for an optional inline guide. Playwright's video documentation (https://playwright.dev/docs/videos) requires closing the recording context to save the capture. These inform the guide and recorder rather than introducing a new dependency.

## Defects met

- CUA createBrowserTab timed out after 32.7 s and reset the kernel, without returning a tab. Headless Playwright is the brief's required route and remains available.
- Statusboard heartbeat write under .agents was denied; the tool wrote its declared fallback at taskstate/agent-status/cfg-w5-demo.json. This fallback is not used as task evidence.
- Add-ProjectIntake filing was attempted immediately: the sandbox identity did not resolve agent-harness; an explicit harness path was then refused because the harness cannot file intake against itself. No harness state was repaired.
- Get-Volume was denied; Python shutil.disk_usage read 16.35 GB free, above the 11 GB stop threshold.
- Linked-worktree merge metadata was denied in sandbox; scoped elevated Git execution succeeded, Already up to date.
- Host browser installation is not visible to sandboxed Chromium launch; scoped host execution captures successfully. No source workaround.
- The sanctioned absolute PowerShell fleet-review invocation was rejected by `checkVisiblePowershell` when its inline brief contained command recipes. The complete refusal was filed with report-hook-misfire.js (Recorded); the same router accepted a file brief.
- The reviewer’s additional time-boxed suite completed 127 assertions but exited 1 during plugin teardown at its 180-second ceiling. No assertion failed. The primary full suite separately exited 0 with 220 passed and 80 viewport-independent skips before the fit correction, then 232 passed and 80 skips after the correction.
- The live catalogue reported legacy PRODUCT.md schema drift. It was not repaired: product-record migration is outside this lane's owned paths and scope.

## Specs checked:

Every criterion in SPEC.md; PRODUCT.md; DESIGN.md. The existing handout comparison criterion remains unverified because the source handout is absent. It will not be ticked by this work.

## Findings after

| Before | Shipped result | Executed evidence |
|---|---|---|
| Repeated bands flattened the story | Task and film lead; mechanism sequence, guided route, optional recording, evidence and remaining work each have a distinct place | Six final landing captures inspected, light/dark at 1440/768/375 |
| No first-visit tutorial | Optional five-step inline guide with previous/next/finish/close, Escape, focus return and current-door state | Tour browser matrix; keyboard flow; direct links into all four views |
| Equal-weight film actions | Play has primary emphasis; ordinary design-review access remains | Existing native film playback/back tests and screenshots |
| Small phone captions in the first finishing pass | Caption type has a phone-readable floor; native fullscreen remains available for review detail | Final phone playback captures, read by builder and independent reviewer |
| Independent P2: guided fit view opened unrelated initial table rows | Guided link now reveals and highlights the existing horn-clearance cell through a native text fragment; explicit Find/table-scroll recovery and ordinary fit door remain | Clipping regression failed before fix, then passed; six final fit captures; independent focused and fallback checks passed |

Independent reviewer: gpt-6.1-sol at xhigh, routed through Invoke-FleetRoute.ps1 on the host. Initial verdict: looks good, clear and useful, with one P2 fit-handoff exception. Follow-up verdict: **Resolved in the verified Chromium flow**; no remaining material gap keeps that finding open. Original findings and follow-up are preserved at `C:/Users/dougl/AppData/Local/Temp/cfg-w5-demo/independent-review/findings.md` and `verdict.md`. This was one independent reviewer and a continued verdict pass, not two early-design readers or a human comprehension study.

The independent reviewer drove the app, inspected all six final fit captures and the corresponding tour/landing/player captures, and separately executed the phone/desktop clipping and simulated unsupported-feature tests (2 passed each, exit 0). Automatic targeting is verified in Chromium. A separate unsupported engine was not tested; the ordinary route and manual Find fallback were tested by feature absence. Native text matching depends on the existing label remaining stable; the regression detects its disappearance or failure to reveal it. Phone users still scroll the findings table horizontally for the remaining columns, as the guide states.

## Files changed

- `public/index.html`, `public/landing.css`, `public/landing.js`: story order, optional guide, sequence/state motion, lazy captioned player, error recovery and responsive composition.
- `public/media/review-walkthrough.mp4`, `public/media/review-walkthrough.vtt`, `public/media/review-walkthrough-poster.jpg`: new authored walkthrough assets only.
- `tests/tour.spec.mjs`: guide boundaries, focus, all four deep links, nested-scroll target, fallback, reduced motion, media budgets/playback/deferred requests, media failure and facts failure.
- `tests/capture-walkthrough.mjs`, `tests/capture-demo.mjs`, `tests/run-demo-check.mjs`: reproducible recording, screenshots/primary-flow capture and isolated test-port helper.
- `DESIGN.md`, `SPEC.md`: shipped interaction rules, browser limitation, new criteria and their proof.
- `.codex-report/cfg-w5-demo.md`: this scoped delivery report.

No generated review, facts, tokens, provenance or licence file was changed. Original films were not re-encoded. No privacy allowlist line was added or changed. No CAD, analysis, electronics, firmware or gripper-documentation file was edited. Runtime hook/status artifacts already present under untracked `.agents/`, `.agents-hold` and `taskstate/` are not part of the change.

## Explainer

- Path: `public/media/review-walkthrough.mp4`.
- Actual exported duration from ffprobe: **82.300 seconds**; size: **973,045 bytes**.
- H.264, yuv420p, faststart; embedded default text subtitles and a lazily attached English VTT track for browser controls; no audio.
- Poster: `public/media/review-walkthrough-poster.jpg`, **122,932 bytes**.
- Recording uses Playwright recordVideo over the real tour and all four review views, then the installed ffmpeg. It was refreshed after the fit correction. The source capture timeline is under `C:/Users/dougl/AppData/Local/Temp/cfg-w5-demo/recording-final/capture.json`.

## Screenshot paths

All captures live under `C:/Users/dougl/AppData/Local/Temp/cfg-w5-demo/`.

- `before/landing-{light,dark}-{1440,768,375}.png` and `-full.png`; `before/review-{light,dark}-{1440,768,375}.png`.
- `after/`: first finish pass, including tour and native-caption playback states.
- `independent-review/`: independent captures, original findings, settled baseline fit views, and final verdict.
- `final/landing-{light,dark}-{1440,768,375}.png` and `-full.png`.
- `final/tour-{light,dark}-{1440,768,375}.png`.
- `final/review-fit-{light,dark}-{1440,768,375}.png`: corrected, highlighted named finding.
- `final/explainer-{light,dark}-{1440,768,375}.png`.
- `final/flow.json`: six successful guide → named fit finding → Home → walkthrough → close flows; zero console errors and zero document overflow in all six.

Builder inspected the baseline landing and review renders, the first finish pass, phone captions, all six final fit handoffs and representative final landing/tour/player states. The independent reviewer inspected the full final set. Browser contexts close in the capture scripts' finally blocks.

## Verification notes

- Red/green guide proof: the initial guide test failed because `#start-tour` did not exist. After implementation, the added suite returned 49 passed, 5 viewport-independent skips, exit 0.
- Red/green spatial proof: the named cell existed in the old fit table but failed the nested clipping assertion. After native targeting, the phone and desktop focused run returned 2 passed, exit 0; independent confirmation and fallback checks also passed.
- The manual Impeccable detector returned `[]`, exit 0, with no unscanned targets; rendered review supplied the separate visual judgement.
- `node --check public/landing.js` and `git diff --check origin/main...HEAD` both returned exit 0, no output.
- No deployment was performed. The unbuilt design status and the existing unverified handout comparison remain explicit.

## Proving commands

Executed in this lane. The last full run below used the final implementation checkpoint `bd2246a`; the following receipt commit changes only this report and the evidenced specification checkbox. The required proving commands are repeated after that receipt commit before final delivery.

| Command | Exit | Last nonempty output line |
|---|---:|---|
| `npm run lint` | 0 | `> python -m py_compile scripts/sync.py scripts/check_public.py && node --check scripts/extract_facts.mjs && node --check scripts/serve.mjs && node --check scripts/screens.mjs && node --check scripts/check_live.mjs` |
| `npm run check:public` | 0 | `check_public: scanned 19 files, 18 hits, 18 allowlisted, 0 open, 0 allowlist errors` |
| `npm run check:public:selftest` | 0 | `self-test: passed` |
| `npm test` (isolated PW_PORT 45134) | 0 | `232 passed (4.7m)`; preceding summary: `80 skipped` |
| `git diff --check` | 0 | No output |

The skips are deliberate duplicate viewport-independent deployment/media checks, not skipped tour or responsive-flow coverage. Each new spatial and fallback scenario ran at all three widths, both themes. Extra syntax and branch-diff whitespace checks also returned exit 0. Screenshot and recording commands returned exit 0; all six final primary flows have empty error arrays and equal document/client widths.

## Delivery

- Branch: `agent/cfg-w5-demo`; PR: https://github.com/douglaspmcgowan/cloth-feed-gripper/pull/20 .
- `origin/main` was fetched and merged before opening the PR; the merge returned `Already up to date.` The repository's actual default branch is `main`.
- Checkpoints: `446db64` baseline/plan; `5393474` implementation and walkthrough; `bd2246a` reviewed fit correction and refreshed recording. The final receipt commit SHA and its post-commit verifier results are returned in the delivery message and visible on the PR.
- All tracked source changes stay inside the lane's owned paths. Work Scope was not enrolled, reconciled or repaired; stale generated task views were not used as evidence.
- Remaining verification limit: the pre-existing course-handout comparison is still unchecked because no handout text was supplied. Cross-engine automatic text-fragment behavior and physical hardware performance are not claimed.
