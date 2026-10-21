# Professor demo lane

## Scope and intake

Source: fleet-route-ca0d60b247f240d2a2508df46c234639.md; local lane on SYSTEMATICCHAOS, branch agent/cfg-w5-demo. User explicitly requests a PR, overriding the brief's commit-only delivery. No Work Scope enrolment, reconciliation, repair, or generated task views are used as evidence.

- [x] Read craft, impeccable, design-review, slides, PRODUCT.md, DESIGN.md, SPEC.md and README.md.
- [x] Baseline both pages at 1440, 768 and 375, light and dark; screenshots inspected.
- [x] Remake landing hierarchy, purposeful motion and accessible five-step tour.
- [x] Capture captioned 60–90 second walkthrough; encode H.264 faststart under 15 MB with small poster.
- [x] Add behavioral regression tests and observable specification criteria.
- [ ] Inspect final renders, exercise primary flow and run all proving commands.
- [ ] Update branch, commit, push and open PR.

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
- The reviewer’s additional time-boxed suite completed 127 assertions but exited 1 during plugin teardown at its 180-second ceiling. No assertion failed. The primary full suite separately exited 0 with 220 passed and 80 viewport-independent skips before the fit correction; a final full run covers the correction.
- The live catalogue reported legacy PRODUCT.md schema drift. It was not repaired: product-record migration is outside this lane's owned paths and scope.

## Specs checked:

Every criterion in SPEC.md; PRODUCT.md; DESIGN.md. The existing handout comparison criterion remains unverified because the source handout is absent. It will not be ticked by this work.
