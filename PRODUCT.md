# Product

## Problem

The cloth-feed gripper is a design that has been simulated but not built or measured, with a film and an interactive design review that show where it stands, but they sit in a private repository where nobody else can see them.

## Users and jobs

Anyone with a link, mostly on a phone: watch the film, learn what the gripper is and that it is not built, and reach one specific fit finding in the 3D review.

## Outcomes

A stranger can do those three things in a few minutes with no broken text or layout and no private content exposed.

## Scope

A static landing page, the film, and the design review app, served from `public/`, with every figure read from the source at a recorded commit.

## Non-goals

No framework, build step, backend or analytics. No hand-typed figures. Not a place to publish course handouts or personal details.

## Current product evidence

Keep product intent and the system record here. Put interface rules in `DESIGN.md` and the testable criteria in `SPEC.md`.

## System record

### Core documents

| File | Owns |
|---|---|
| `README.md` | Entry point for a visitor or contributor |
| `SPEC.md` | Testable criteria the project must meet |
| `DESIGN.md` | Interface rules and the stack-selection record |
| `PRODUCT.md` | Product intent and the system record |

### Architecture

| Component | Purpose | Entry point | Owner |
|---|---|---|---|
| Landing page | Film, plain-language summary, honest status, doors into the review | `public/index.html` | project |
| Review app | The design's 3D model, fits, assembly and open items | `public/review/index.html` (generated) | `scripts/sync.py` |
| Sync | Copies inputs from the source at one commit, writes figures, tokens and provenance | `scripts/sync.py` | project |
| Public-content check | Blocks publishing private content | `scripts/check_public.py` | project |

### Important paths

| Path | Purpose | Generated | Committed |
|---|---|---|---|
| `public/index.html`, `public/landing.css`, `public/landing.js`, `public/favicon.svg` | Landing page: markup, styles, script, icon; hand-written, no build | no | yes |
| `public/review/index.html` | Design review app, wrapped in a document head and a Home link | yes (`scripts/sync.py`) | yes |
| `public/media/*` | The three films, the posters and the Open Graph image | yes (`scripts/sync.py`) | yes |
| `public/licenses/*` | Licence texts for the third-party assets the credits name | yes (`scripts/sync.py`) | yes |
| `public/facts.json` | Every figure the landing page shows | yes (`scripts/sync.py`) | yes |
| `public/tokens.css` | Design tokens copied from the review app's `:root` blocks | yes (`scripts/sync.py`) | yes |
| `public/provenance.json` | Source commit, sync date, and the sha256 and size of each served file | yes (`scripts/sync.py`) | yes |
| `scripts/sync.py` | Writes every generated file from the source at one commit | no | yes |
| `scripts/extract_facts.mjs` | Runs the review app's own figure code in a bare `node:vm` context and prints JSON for `sync.py` | no | yes |
| `scripts/check_public.py`, `scripts/public-allowlist.txt` | Privacy scan of `public/` and its reviewed allowlist | no | yes |
| `scripts/serve.mjs` | Local static server rooted at `public/` | no | yes |
| `scripts/check_live.mjs` | Post-deploy guard against a base URL | no | yes |
| `scripts/screens.mjs`, `scripts/jobs.mjs` | Screenshots, and the three real-browser jobs | no | yes |
| `docs/screens/*.png` | Screenshots written by `scripts/screens.mjs` and `scripts/jobs.mjs` | yes | yes |
| `tests/` | Playwright specs and their helper | no | yes |
| `vercel.json`, `site.config.json` | Deployment shape (output directory, headers) and the public site URL | no | yes |
| `package.json`, `playwright.config.mjs`, `.gitleaks.toml`, `.github/workflows/gitleaks.yml` | Dependencies, test configuration, secret scan configuration and CI | no | yes |
| `SPEC.md`, `PRODUCT.md`, `DESIGN.md`, `README.md` | Core documents | no | yes |
| `.sync/state.json` | Full sync record, source-side paths included; never served | yes (`scripts/sync.py`) | no |
| `node_modules/`, `test-results/`, `playwright-report/` | Installed dependencies and test output | yes | no |

### Data flow

1. **Input.** `scripts/sync.py --ref <sha>` reads files at that commit of the private source repository `berkeley-ai-tutor`, with `git show`. It reads from a clone given by `--source`, or else from a temporary clone it makes with `gh`. The files it reads are listed in its input table: the review app, the films, the poster, the licence texts and a few read-only files for checks and credits.
2. **Transform.** `sync.py` wraps the review app in a document head with a Home link. It prepares the films and posters with `ffmpeg`, runs `scripts/extract_facts.mjs` to read the figures out of the review app, and copies the review app's `:root` token blocks.
3. **Stores.** It writes the generated files under `public/`, only where their bytes differ, and writes `.sync/state.json`, which is git-ignored and never served.
4. **Trust boundary.** The private source is read only at sync time, and nothing is fetched from it while the site is served. `scripts/check_public.py` scans `public/` for private content. `provenance.json` holds hashes and byte counts and nothing about the source layout.
5. **Output.** `public/` is served by Vercel under `vercel.json`, or by `scripts/serve.mjs` locally. Visitors' browsers then load the three.js module and the Public Sans font from third parties (see Integrations).

### Integrations

| System | Direction | Credential name | Failure behavior |
|---|---|---|---|
| `berkeley-ai-tutor` (GitHub, private source repository) | in, at sync time only | none in the repository; the `gh` login of the machine that runs `sync.py`, used only when `--source` is not given | `sync.py` exits with an error naming the failure (`could not clone`, `ref ... not found`, or `missing at the pinned commit`) |
| Vercel (hosts `public/`) | out | none in the repository; the Vercel project is linked outside it | `npm run check:live -- <base-url>` exits 1 and names each failed path |
| GitHub Actions, `gitleaks` workflow (`.github/workflows/gitleaks.yml`) | in (reads this repository on push and pull request) | none; the job uses the default token with `contents: read` | the job fails on a checksum mismatch in the pinned download or on any finding in the history scan |
| jsDelivr (three.js 0.186.1, loaded by the review app in the visitor's browser) | in, at view time | none | the 3D views do not draw without a network |
| Google Fonts (Public Sans, loaded by both pages in the visitor's browser) | in, at view time | none | the text uses the fallback stack in `public/tokens.css` (`Segoe UI`, `system-ui`, then the generic sans-serif) |

### Ownership and concurrency

- **Owners.** Every component in the architecture table is owned by the project.
- **Shared mutable resources.** `scripts/sync.py` rewrites files under `public/` in place and takes no lock, so run one sync at a time per clone. `.sync/state.json` belongs to each clone.
- **Worktree constraints.** None recorded.
- **Ports.** `scripts/serve.mjs` listens on 4173 by default; its first argument or the `PORT` variable changes that. `scripts/screens.mjs` and `scripts/jobs.mjs` start their own server on a free port.
- **Test databases.** None; the test suite is static.
- **Deployment target.** Vercel, at the `siteUrl` in `site.config.json`. Deploying needs the owner's say-so, per `README.md`.

Update this record when a component boundary, data flow, owner, integration, core document, or important path changes.
