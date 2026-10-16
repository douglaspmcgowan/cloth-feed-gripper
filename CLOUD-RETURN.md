12 allowlist entries removed; 0 kept; 0 harness-home pointers left in DESIGN.md

# Cloud return: cfg-hygiene follow-ups

Branch `agent/cfg-hygiene-followups-cloud`, cut from `origin/main` at `75f9fc2`. That head had not moved when the lane started.

## Commits

- `db57f51` Remove harness pointers from the gitleaks config and DESIGN.md: `.gitleaks.toml`, `DESIGN.md`
- Final commit: adds this file, `CLOUD-RETURN.md`, only

`git diff --stat origin/main HEAD` on `db57f51`: `.gitleaks.toml` 87 lines changed, `DESIGN.md` 145 lines changed, 2 files, all owned paths. The final commit adds `CLOUD-RETURN.md`, which is also owned.

## Proofs

Each row gives the command, the last line of its output, and the exit code.

1. `git grep -n -E "\.agents|~/|[A-Za-z]:\\\\" -- .gitleaks.toml DESIGN.md` — no output (no hit). Exit 1, git grep's no-match code.
2. `npm run lint` — last line is the echoed `py_compile` command of the lint script; no error output. Exit 0.
3. `python3 scripts/check_public.py` — `check_public: scanned 16 files, 19 hits, 19 allowlisted, 0 open, 0 allowlist errors`. Exit 0.
4. `python3 scripts/check_public.py --self-test` — `self-test: passed`. Exit 0.
5. `gitleaks detect --no-banner --redact --config .gitleaks.toml` — `no leaks found`. Exit 0. Gitleaks 8.30.1, the release version CI pins, installed from its release page and checked against its published sha256.
6. `gitleaks git --redact --no-banner --log-opts="--all" --config .gitleaks.toml .` — the same form CI runs, scanning all five commits — `no leaks found`. Exit 0.
7. `git diff --check origin/main HEAD` — no output. Exit 0.
8. `git merge-base --is-ancestor origin/main HEAD` — no output. Exit 0.
9. `git diff --stat origin/main HEAD` — `.gitleaks.toml` and `DESIGN.md` only (on `db57f51`). Exit 0.

## Specs checked

- Item 1, `.gitleaks.toml`: `SPEC.md` "Privacy and serving" (nothing outside `public/` is served; the privacy scan runs over `public/` only). The gitleaks rules are unchanged: `useDefault = true` is kept and no rule is loosened or deleted. Only path allowlists for absent paths were removed.
- Item 2, `DESIGN.md`: `SPEC.md` names this file as the look-and-behaviour authority; `PRODUCT.md` places interface rules here. The rules, tokens and stack record are self-contained. Nothing under `public/` changed.
- Item 3: no other owned or unowned file changed.
- The return and PR body contain no local path, email address, account or student id, machine name, session or run id, or private-repository path.

## Choices

- **Allowlist.** Removed all 11 path patterns from the first block and the freshness block (12 entries). Kept none. `.venv/` and `site-packages/`: removed, because the site has no Python packages (the Python tooling uses only the standard library) and no vendored source, so no virtualenv is a legitimate part of it. `freshness_baseline.json` is neither tracked nor generated here (`scripts/sync.py` does not write it), so the freshness rule went too. History was checked first: no commit reachable from any ref contains a file matching a removed pattern, so the history scan in CI stays clean. Gitleaks confirms it (proof 6).
- **Comment in `.gitleaks.toml`.** Rewritten for this repository. It explains why there is no path allowlist, describes the `.gitleaksignore` fingerprint method, and notes that CI scans the full history.
- **DESIGN.md.** Removed the shared-rules pointer block and its markers, the leaf routing list, and the design-libraries section. The rules those pointers summarized were kept where they change what gets built here: the anti-default rules, the banned names with the word-boundary note, the mobile and touch rules, and the typography rules. The remaining pointers' leaves (animation, icons, slides, dashboards, mission-control studies, the workflow template, the production and design-space notes) cover nothing this site builds, so they went.
- **Mobile rules.** The only source for these was the pointer summaries, since the linked leaves are not in this repository. Each rule is one stated by a summary: no bottom tab bar on a responsive site, inputs at least 16px, touch targets at least 24 CSS px (the WCAG 2.2 minimum; the stricter platform figures were not adopted), `svh`/`dvh`, and `viewport-fit=cover` with `env(safe-area-inset-*)`. Both HTML pages already declare `viewport-fit=cover`.
- **Stack selection.** Not recorded. The selection was never made in this repository, and a template number would be invented. The entry states the stack the repository shows and marks the six answers and the template as not recorded.
- **Filled placeholders.** The empty typography, tokens, interaction and exceptions sections now hold values taken from `public/tokens.css` and `SPEC.md`. Monospace is recorded as none.
- **Attribution.** The commits carry no co-author trailer. A trailer needs an email address, and the lane forbids one in a commit, PR body or return; it also forbids a session id and a model identifier, which the attribution reminder's trailer lines would add. The PR body ends with the Claude Code generation footer, which names neither.
- **PR template.** None found under `.github/`, so the body is this file.

## Assumptions

- The reviewer's specs (`SPEC.md`, `PRODUCT.md`) were read as the authority. The "Privacy and serving" rule constrains the change because it is the only spec naming the scanned tree.
- The owner's 2026-10-12 ruling was read as already carried out in PR 3 and not reopened: no history rewrite, and no file removed beyond the items named here.
- The lane owns `.gitleaks.toml`, `DESIGN.md` and this file only, so nothing else was changed.

## Defects and deferred items (reported, not fixed)

- `.gitignore`: the managed block (its markers name a harness template source) and its agent-harness ignore rules (the harness directory rule, the root agent-file rules, `.worktrees/`, and the rest) are harness remnants. Deferred, outside this lane's owned paths.
- `.gitignore`: no ignore rule for a Python virtualenv (`.venv/`), so a local one would show as untracked and a `git add -A` could commit it. Deferred.
- `SPEC.md:35` names root agent-file paths and a harness index path as a not-found check. Deferred, not owned.
- `scripts/check_live.mjs:28-36` and `tests/deploy.spec.mjs:13` probe harness paths as hidden-file checks. Harmless as negative probes, but they name removed paths. Deferred, not owned.
- `PRODUCT.md`: the "Important paths" table still holds template placeholders (`<path>`, `<purpose>`) and the data-flow and integrations sections are unfilled. Deferred, not owned.
- Binary media under `public/` and `docs/screens/` matched loose text searches for harness strings; these are byte matches, not references, and were not inspected further.
- Nothing in the owned paths failed. No stop condition was hit: removing the allowlist entries produced no gitleaks finding.
- Environment: `npm ci` ran on Node 22. The Python checks ran on the container's Python 3; the owner's Windows host uses Python 3.12 and `core.autocrlf=true`. The owned files are LF in the repository; `git diff --check` is clean, so no line-ending issue is expected.
