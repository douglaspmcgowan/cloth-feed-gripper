19 151 0 10
(files removed; tests passed; tests failed; references fixed)

## Commits
- 72da7f5 Remove agent harness files from main
- this commit: CLOUD-RETURN.md

Base: origin/main at c75719f (unchanged at start). No history rewrite, no force push.

## Removed (19; each path is in the harness install commit deec888 --stat)
.agents/DISPATCH-CHECKLIST.md, .agents/INDEX.md, .agents/feedback/FEEDBACK-LOG.md, .agents/harness-provenance.json, .agents/skill-pathways.json, .claude/settings.json, .codex/hooks.json, .cursor/rules/00-project-contract.mdc, AGENTS.md, CLAUDE.md, TASK.md, LOG.md, BACKBURNER.md, MEMORY.md, skills-manifest.json, secret-manifest.json, secret-manifest.md, data-manifest.yaml, .env.example

- data-manifest.yaml and .env.example: `git grep` for PROJECT_DATA_ROOT and data-manifest finds no product file that reads them. Only removed harness files, PRODUCT.md, and the `/.env.example` not-served probe in scripts/check_live.mjs reference them.

## Kept, with reason
- DESIGN.md, PRODUCT.md: product documents, kept per brief. Both came from deec888 but are product files.
- SPEC.md, README.md, .gitattributes, .gitleaks.toml, .gitignore, .github/, docs/, public/, scripts/, tests/, package.json, package-lock.json, playwright.config.mjs, site.config.json, vercel.json: product files; not in the removal list.

## Reference fixes (10 lines, all in PRODUCT.md)
- Line 25 sentence no longer names TASK.md or .agents/INDEX.md; now names DESIGN.md and SPEC.md.
- Core-documents table rows for AGENTS.md, CLAUDE.md, .cursor, TASK/LOG/BACKBURNER, MEMORY.md, .agents/INDEX.md, skills-manifest.json, data-manifest.yaml, secret-manifest.json replaced with README.md, SPEC.md, DESIGN.md, PRODUCT.md.
- .gitignore: project-owned section appended after the managed block (managed text unchanged). It ignores the removed root files, `/.agents/`, `/.codex/`, `/.cursor/`, `/.claude/settings.json`, `/.claude/settings.local.json`, and `/.env.example`.
- Kept on purpose: `scripts/check_live.mjs:28-39` and `tests/deploy.spec.mjs:13` probe the removed paths and assert they are NOT served. Those probes pass.
- No change to SPEC.md: no criterion names a removed file as present.
- No change to README.md, docs/ or any public/ file: no contributor-facing text pointed at AGENTS.md.

## Proving commands (last line; exit code)
1. `npm ci`: last line `npm notice To update run: npm install -g npm@12.2.0`; exit 0
2. `npm run lint`: no errors printed, last echoed line is the `node --check scripts/check_live.mjs` chain; exit 0
3. `npm run check:public:selftest`: `self-test: passed`; exit 0
4. `npm run check:public`: `check_public: scanned 16 files, 19 hits, 19 allowlisted, 0 open, 0 allowlist errors`; exit 0
5. `npx playwright install --with-deps chromium`: `Chrome Headless Shell 156.0.8078.4 ... downloaded`; exit 0
6. `npm test`: `151 passed (5.0m)` with `65 skipped` above it, 0 failed; exit 0
7. `git ls-tree -r --name-only HEAD | grep -c -E '^(AGENTS\.md|CLAUDE\.md|\.agents/|\.claude/|\.codex/|\.cursor/)'`: `0` (grep exit 1 = no match)
8. `git diff --quiet origin/main HEAD -- public`: exit 0
9. `git diff --stat origin/main HEAD`: `21 files changed, 24 insertions(+), 2529 deletions(-)` (before this return file)
10. `git diff --check origin/main HEAD`: no output; exit 0

## Specs checked
- SPEC.md "Privacy and serving": nothing outside `public/` is served. `tests/deploy.spec.mjs:13` probes /AGENTS.md, /TASK.md, /.agents/INDEX.md and /.agents/AGENTS.md; all four show "is not served" and pass. `check_public` 0 open.
- SPEC.md "Quality": `npm test` green, 151 passed, 0 failed.

## Assumptions
- `.gitignore` ignores `.claude/settings*.json` only, not all of `.claude/`. The managed block says `.claude/` is a product configuration directory.
- `.gitleaks.toml` allowlist patterns for `.agents/` and `.claude/worktrees/` remain. They match no existing file and are harmless.
- `DESIGN.md`'s harness-managed block points at `~/.agents/`, a user-home harness path, not a repository file. Left as is.
- No fresh-eyes subagent review was run.

## Defects met (harness)
- The managed `.gitignore` block says `.claude/` is product state, which conflicts with a harness-level ignore of harness files under it. Resolved with file-level rules.
- The harness install writes a managed block into `DESIGN.md`, a product file the brief keeps. It refers to user-home harness paths, not repository paths.
