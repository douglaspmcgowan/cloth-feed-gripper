# Task

## Intent

<!-- Prose: why this project exists and what good looks like. Durable across requests. -->

## Specs

<!-- Testable statements of what must be true when the request is met, one checkbox each. -->
<!-- Closure is graded against these, not against an empty queue. Tick one only against the same -->
<!-- observable proof a task would have had to produce. There is no separate requirements list. -->

## Goal

Public site for the cloth-feed gripper: `/` landing page with the film, `/review/` the design review app, built and proved locally, pull request `agent/site-v1` against `main`. No deploy, no merge (Douglas, 2026-10-10: "put the video in the website, make the website its own repo, put it on vercel, make it public").

## Active


## Queue

<!-- Add required work extracted from the request here. -->

## Blocked

<!-- Record externally blocked work here. -->

## Needs decision

<!-- Record items requiring a user decision here. -->

## Completed
- [x] 1 `scripts/sync.py` + `scripts/extract_facts.mjs`: copy inputs at 996dce6, write `public/review/index.html`, `public/media/*`, `public/provenance.json`, `public/facts.json`
- [x] 2 `public/index.html` landing page (hero teaser, full film, what it is, where it stands, doors, build log, credits, light and dark)
- [x] 3 `vercel.json` and `scripts/check_public.py` with reviewed allowlist
- [x] 4 Playwright tests: `npm test` 145 passed, 65 skipped (viewport-independent deploy checks run once), exit 0, 3 sizes x light and dark
- [x] 5 `AGENTS.md` project section, `README.md`, `SPEC.md` (all boxes ticked against their proof), screenshots in `docs/screens/`
- [x] 6 Real-browser jobs at 375 and 1440 (`node scripts/jobs.mjs`): film played to its end unmuted (62 s); 2 failing requirements read from the landing page; servo-horn finding reached and Home returns to `/`; no console errors
- [x] 7 Proving commands run, `origin/main` merged (already up to date), branch pushed, PR https://github.com/douglaspmcgowan/cloth-feed-gripper/pull/1 open. `VerifyProject` fails on the whole-file AGENTS.md hash; queued to agent-harness as `verifyproject-hashes-project-owned-agents-md`.

<!-- Keep only current completion evidence here; durable history belongs in LOG.md. -->

## Verification

- Next: record the exact command or observable proof when work begins.

<!--
Markers use a space for queued work, a tilde for active work, x for complete,
an exclamation mark for blocked work, and a question mark for decisions.
Required delegated work may be nested under its parent with agent provenance.
Optional discoveries belong in BACKBURNER.md.
Parallel mode applies to three or more independent, file-disjoint items.
-->
