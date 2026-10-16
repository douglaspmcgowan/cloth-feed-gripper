Tests passed: 141; tests failed: 12 (must be 0; all 12 are video playback in `tests/landing.spec.mjs`, see below); items closed: 4 of 4 (a to d).

# Cloud return: cfg-pr4-deferred-cloud

Branch `agent/cfg-pr4-deferred-cloud`, cut from `origin/main` at `8f33df9`. That head had not moved when the lane started.

## Commits

- `86a018b` Remove harness remnants from .gitignore and ignore .venv/: `.gitignore`
- `17db675` Replace harness paths in the not-served checks with neutral repository files: `SPEC.md`, `scripts/check_live.mjs`, `tests/deploy.spec.mjs`
- `7382053` Fill PRODUCT.md's important paths, data flow, integrations and ownership from the tree: `PRODUCT.md`
- Final commit: adds this file, `CLOUD-RETURN.md`, only

`git diff --stat origin/main HEAD` on `7382053`:

```
 .gitignore             | 169 +------------------------------------------------
 PRODUCT.md             |  40 ++++++++++--
 SPEC.md                |   2 +-
 scripts/check_live.mjs |  11 ++--
 tests/deploy.spec.mjs  |  15 ++++-
 5 files changed, 59 insertions(+), 178 deletions(-)
```

All five are owned paths. The final commit adds `CLOUD-RETURN.md`, also owned. `DESIGN.md`, `public/**`, `public/landing.css`, `tests/tokens.spec.mjs` and other scripts and tests are untouched.

## Items

- **(a) `.gitignore`.** Removed the managed block (markers included) and the agent-harness rules after it: `.agents/**`, `.worktrees/`, `.agents-hold`, `.claude/state/`, `taskstate/`, `error.log`, `.impeccable/`, the root agent-file rules, `.codex/`, `.cursor/`, `.claude/settings*.json`. Kept `.sync/`, `__pycache__/`, `node_modules/`, `test-results/`, `playwright-report/`. Added `.venv/`.
- **(b) `SPEC.md:35`.** The not-found proof now names `/README.md`, `/SPEC.md`, `/package.json`, `/scripts/sync.py`. The test it cites (`npm test`, server rooted at `public/`) is unchanged in step.
- **(c) Probes.** `scripts/check_live.mjs` hidden list: 21 to 22 paths. Removed the five harness paths (`AGENTS.md`, `CLAUDE.md`, `TASK.md`, `LOG.md`, `.agents/INDEX.md`); added `PRODUCT.md`, `DESIGN.md`, `playwright.config.mjs`, `scripts/serve.mjs`, `.gitleaks.toml`, `.git/HEAD`. `tests/deploy.spec.mjs` not-served list: 10 to 12 paths, same replacement plus `.git/HEAD` and `.gitignore`; the `/../` traversal probe now targets `/../README.md`.
- **(d) `PRODUCT.md`.** Filled the important-paths table, data flow, integrations and ownership and concurrency from `README.md`, `scripts/sync.py`, `vercel.json`, `site.config.json`, `scripts/serve.mjs`, `scripts/extract_facts.mjs`, `public/tokens.css` and `.github/workflows/gitleaks.yml`. Entries with no source in the repository say "none" or "none recorded". No placeholder remains.

## Verification

Environment: Linux container, Node 22.22.0, Playwright 1.64.0 from the lockfile. The host's Windows-specific checks still need a run on the host.

1. `npm ci` — last line: `npm notice To update run: npm install -g npm@12.2.0`; exit 0.
2. `npm test` as configured in `playwright.config.mjs` — 132 failed, 21 passed, 75 skipped; every failure was `browserType.launch: Executable doesn't exist at /opt/pw-browsers/chromium_headless_shell-1248/...`. Playwright 1.64 expects revision 1248; the container has revision 1194. Last line: `test exit 1`. Superseded by the run below.
3. Full suite via a scratch wrapper outside the repo (`import` of the repo's own config, unchanged, plus `launchOptions.executablePath` pointing at the preinstalled `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, and an absolute `webServer` command) — `141 passed`, `12 failed`, `75 skipped`, wall time 21.0m. Last line: `test exit 1`. Result by test:
   - 12 failures, all `tests/landing.spec.mjs:66` ("the teaser loops muted without a click") and `:76` ("the play control plays the full film with sound…"), at each of the six projects that run them (desktop-1440, tablet-768, phone-375, light and dark where applicable). Error: `page.waitForFunction: Test timeout of 150000ms exceeded`, waiting for `readyState >= 2` on the film.
   - Cause, probed: `canPlayType('video/mp4; codecs="avc1.42E01E"')` in the preinstalled browser returns an empty string, so this Chromium build cannot decode H.264. The films are H.264 MP4. This is an environment limit of the container, not a site defect; the host's Playwright Chromium must be used for these tests.
   - 75 skipped are the existing `test.skip` guard in `tests/deploy.spec.mjs` (its viewport-independent tests skip on every project except `desktop-1440-light`). No skip was added.
   - Not run in the container: the three real-browser jobs in `scripts/jobs.mjs` (not part of `npm test`).
4. `npm run lint` — no output (the script's last command is `node --check`, which prints nothing on success); exit 0.
5. `npm run check:public` — last line: `check_public: scanned 16 files, 19 hits, 19 allowlisted, 0 open, 0 allowlist errors`; exit 0.
6. `npm run check:public:selftest` — last line: `self-test: passed`; exit 0.
7. `node scripts/check_live.mjs http://127.0.0.1:4173` against `npm run serve` (`scripts/serve.mjs`, default port 4173) — last line: `check_live: 27 ok, 0 failed`; exit 0. Local checks cover the five served paths (200, the title and `facts.json` content) and all 22 hidden paths (404). Needs the deployed site: the Vercel headers and `cleanUrls` redirects, the live `Cache-Control` on `/media/*`, and the film sizes served by the CDN.
8. `git grep -n -i -E "agents|harness|claude|codex|worktree" -- .gitignore SPEC.md PRODUCT.md scripts/check_live.mjs tests/deploy.spec.mjs` — one hit, `PRODUCT.md:94: - **Worktree constraints.** None recorded.` It is the word "worktree" in the ownership section's field name, with "None recorded" as its content. No other hits; exit 0.
9. `git diff --check origin/main HEAD` on `7382053` — no output; exit 0.
10. `git diff --stat origin/main HEAD` — the five owned paths listed above.

## Specs checked

- `SPEC.md` "Privacy and serving": nothing outside `public/` is served (the probe lists in `check_live.mjs` and `deploy.spec.mjs` still check it, with same-or-more paths); `check_live.mjs <base-url>` exit codes unchanged; the `check_public.py` scan is unchanged.
- `SPEC.md` "Sync": `PRODUCT.md`'s data-flow section matches the one-command, pinned-ref behaviour in `scripts/sync.py`; no sync code was changed.
- `PRODUCT.md` "Problem", "Users and jobs", "Non-goals": the new paths, data flow and integrations describe the shipped site and add no scope.
- `DESIGN.md`: not touched.

## Assumptions

- The lane's "no co-author trailer" and "no session id" rules override the attribution reminder's trailer lines; commits carry no trailer.
- The commit author is the container's configured git identity (`Claude <noreply@anthropic.com>`), which I did not set. It is a generic noreply address, not a person's address.
- `.env` and OS-file ignore rules did not exist in this file, so none were removed. The item asked to keep such rules where present; none were added, since they were not among the four items.
- `Current product evidence` in `PRODUCT.md` still reads as template instruction text (`Keep product intent and the system record here…`). It was not one of the four items, so it was left as is.
- The Playwright wrapper was run from outside the repo and is not committed; the repo config is unchanged.
- The host's `npm test` must be rerun in its own Chromium for the 12 video tests. Those are the only expected differences.

## Defects and deferred items (reported, not fixed)

- `SPEC.md:5` names a person in the requirement's source line. Existing text, not changed; the owner should decide whether attribution by name stays in a public repository.
- `README.md` "Deploying" describes the hidden list as "contract, task and spec files". Not an owned path; it now lists the new probes differently from the code. Stale wording to fix in a README lane.
- `.gitignore` has no `.env` or OS-file (`.DS_Store`, `Thumbs.db`) rules. Not added: outside the four items.
- Preinstalled Chromium 1194 cannot play H.264. The container cannot prove the video tests; the host must.
- Playwright 1.64 expects Chromium revision 1248; the container has 1194. The operator instruction not to run `playwright install` was followed, so the wrapper above was used.
- One foreground `sleep 2` was used before starting the check against the local server. No effect on the results.
- Binary media under `public/` and `docs/screens/` was not inspected for harness strings (unchanged from the prior return).
