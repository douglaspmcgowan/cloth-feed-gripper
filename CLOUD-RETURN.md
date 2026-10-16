tests passed: 169; tests failed: 0; tokens resolved: 7 of 7

## Commits and changed files

- `a2aab05` Document the source of every custom property and check them in a browser
  - `DESIGN.md`: token section gains a "Where each token is defined" table (seven rows), and one sentence pointing to it.
  - `tests/tokens.spec.mjs` (new): for `/` and `/review/`, every `var(--name` with no fallback in the served CSS and inline styles must have a computed value on some element or a declaration in the served HTML, stylesheets or scripts.
- No change to `public/landing.css`: all seven resolve, so no fix was needed.

Diff against `origin/main` (`8f33df9`) lists only owned paths: `DESIGN.md`, `tests/tokens.spec.mjs`, and this file.

## Proving commands

| Command | Result | Last line | Exit |
|---|---|---|---|
| `npm test` (full suite, 6 projects) | 169 passed, 0 failed, 65 skipped | `169 passed (6.2m)` | 0 |
| `npx playwright test tests/tokens.spec.mjs` | 18 passed | `18 passed (42.7s)` | 0 |
| Negative check: `--measure` removed from `landing.css` (desktop-1440-light only), then restored | 2 failed, as intended | `1 passed (8.0s)` / exit 1 | 1 |
| `npm run lint` | ok | `node --check scripts/check_live.mjs` | 0 |
| `npm run check:public` | ok | `check_public: scanned 16 files, 19 hits, 19 allowlisted, 0 open, 0 allowlist errors` | 0 |
| `git diff --check origin/main HEAD` | clean | (no output) | 0 |
| `git diff --stat origin/main HEAD` | 2 files, 94 insertions, 1 deletion | `2 files changed, 94 insertions(+), 1 deletion(-)` | 0 |

The 65 skips come from specs that already existed. This change adds no `skip`; I did not attribute the skips to individual specs.

## The seven tokens

Computed values were read in Chromium at 1440x900, 768x1024 and 375x812, light and dark.

| Token | Source | Computed value (observed) | Consumer |
|---|---|---|---|
| `--measure` | `public/landing.css:7`, `:root` | `66ch` on `/`, all six combinations | `landing.css:59, 349, 432` |
| `--wrap` | `public/landing.css:8`, `:root` | `1200px` on `/`, all six | `landing.css:74` |
| `--fs-d` | `public/landing.css:6`, `:root` | `clamp(40px, 5.2vw, 64px)` on `/`, all six | `landing.css:49` |
| `--sheet-h` | set on `.sheet`, `public/review/index.html:206` (generated file, not edited) | `calc(clamp(320px,calc(100vh - 300px),720px) + 48px)` at 1440; `calc(clamp(300px,62vh,560px) + 48px)` at 768 and 375 | `review/index.html:207` |
| `--zw` | set by the review script, `review/index.html:1013`, on `.sheet` when zoomed | empty at load; `150%` after one zoom-in | `review/index.html:209`, fallback `200%` |
| `--zh` | set by the review script, `review/index.html:1012`, when zoom starts | empty at load; `0px` after one zoom-in (see defects) | `review/index.html:208`, fallback `--stage-h` |
| `--sw` | set inline on `span.th.ph` by the template, `review/index.html:1568` | `#888888` for an unlisted part | `review/index.html:285` |

## Screenshots

Twelve PNGs (both pages at the three sizes and both schemes) are in the scratchpad, not committed: `landing-<size>-<scheme>.png` and `review-<size>-<scheme>.png`, for sizes `1440x900`, `768x1024`, `375x812` and schemes `light`, `dark`. No CSS changed, so no visual change is expected. The probe found no horizontal scroll (0 px) and no console errors on either page at any size.

## Skills

`craft` is absent in this container (not under `~/.agents/skills` or `~/.claude/skills`). I applied `DESIGN.md` inline.

## Specs checked

- SPEC.md: "The two pages read as one product: the landing page uses the review app's own palette and type tokens, light and dark": the landing page's page tokens are not in `tokens.css`; they are documented in `DESIGN.md`. Palette and type tokens come from `tokens.css` as before.
- SPEC.md: "No console errors, no horizontal page scroll and no mojibake on either page at 1440x900, 768x1024 and 375x812, light and dark": probe clean; the existing landing and review specs pass in the full suite.
- SPEC.md Sync section: `tokens.css` and `review/index.html` are not edited.
- DESIGN.md is the interface authority (its own line 3); the new table is in its token section.

## Assumptions

- The three landing tokens stay in `landing.css`; moving them into `tokens.css` needs a `sync.py` change, which is a separate decision and was not made here.
- The spec's source clause: a property set only by script (`--sw`, `--zw`, `--zh`) counts as resolved when the served code declares it. This is a declaration check, not a runtime read, for properties that exist only after a user action.
- `origin/main` was `8f33df9` when the branch was created; it had not moved.

## Defects met

- `--zh` after one zoom-in on a figure that is not shown reads `0px`. I triggered zoom with a script click on a hidden figure, so this is not reproduced through the visible UI. It is in the review app's script (`review/index.html:1012`), which is out of scope.
- `DESIGN.md` line 3 still says the tokens the site names are defined in `tokens.css`; that line is outside the token section, so I left it.

## Deferred

- Proposal: move `--measure`, `--wrap`, `--fs-d` into the generated `tokens.css` through `scripts/sync.py`. Not done.
- Visible-UI reproduction of the `--zh` observation.
