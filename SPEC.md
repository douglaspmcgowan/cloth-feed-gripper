# Specification

What the site must do, as criteria observable by running it. Why it exists and for whom: `PRODUCT.md`. Look and behaviour: `DESIGN.md`.

Source of every requirement below: Douglas, 2026-10-10, "put the video in the website, make the website its own repo, put it on vercel, make it public", as refined in the dispatch brief of the same date. Each item names its proof. A box is ticked only against that proof.

## Site shape

- [x] `/` is a landing page and `/review/` is the design review app served as a standalone HTML document. Proof: `npm test` loads both; each has doctype, `lang`, charset and viewport.
- [x] The two pages read as one product: the landing page uses the review app's own palette and type tokens, light and dark. Proof: `npm test` compares the landing page's computed `--accent`, `--bg` and `--ink` with the review app's at both schemes.
- [x] A visitor in the review app reaches `/` in one click at any width without breaking the app's layout. Proof: `npm test` clicks the home link at 375, 768 and 1440 and checks no horizontal page scroll.

## Landing page

- [x] The film is the centre of the page: a muted looping 10 s teaser with a poster; reduced motion shows the poster only. Proof: `npm test` with `reducedMotion: reduce` finds no playing teaser.
- [x] One control plays the full 62 s film with native controls and sound; portrait phones get the vertical cut. Proof: `npm test` presses play and sees `readyState >= 2` and `currentTime` advance, at 375x812 and 1440x900.
- [x] No film downloads until asked. Proof: `npm test` records network requests before pressing play and finds no request for the full-length or vertical film.
- [x] A non-engineer can read what the gripper is in two or three sentences. Proof: reviewed in the real-browser jobs.
- [x] The page says honestly that the design is not built or measured, and every figure on it (requirement counts, mass, open decisions) is read by `scripts/sync.py` from the source at the pinned commit. Proof: `public/facts.json` carries the figures and `npm test` checks each rendered figure equals its `facts.json` value; the `typed-figure` rule of `check_public.py` hits every digit run in the landing page's static text, so a hand-typed figure fails unless a reviewed allowlist line with its count names it.
- [x] Four doors deep-link the review app by job: see the model, check the fits, follow the assembly, read what is still open. Proof: `npm test` clicks each and checks the named view is shown.
- [x] The page links the build log https://build-log-eight.vercel.app/log/gripper-2026-09-22/ and credits every third-party asset it serves. Proof: `npm test` finds the link; the credits list matches `public/provenance.json` and the review app's own external loads.

## Media

- [x] Three films in `public/media/` with the moov atom first, a compressed poster under 250 KB and a 1200x630 Open Graph image. Proof: `npm test` (`deploy.spec.mjs` and `landing.spec.mjs`) checks moov position, poster size and OG dimensions.

## Sync

- [x] One command, `python scripts/sync.py --ref <sha>`, copies the inputs from a `berkeley-ai-tutor` clone, writes the site files and `public/provenance.json` (source repository name, commit, sync date, and for each served file its public path, sha256 and size). Running it twice with the same ref changes nothing. Proof: second run, then `git status --short` is empty.
- [x] `public/provenance.json` lets a stranger verify the served bytes and reveals nothing else about the private source repository: no source-side path, hash or size, and no input that is read but not served. Proof: `npm test` (`deploy.spec.mjs`) rehashes every listed file and checks the key set; the `source-path` rule of `check_public.py` fails on any path `sync.py` reads that appears in a served file without a reviewed allowlist line. The review app's other evidence citations (relative file names in its Sources panels) are kept on purpose and are outside this rule.

## Privacy and serving

- [x] `vercel.json` sets `outputDirectory` to `public`, no framework, no build command, `cleanUrls`, long cache headers on `/media/*`. Proof: `npm test` reads it.
- [x] Nothing outside `public/` is served: `/AGENTS.md`, `/TASK.md`, `/.agents/INDEX.md` return not found. Proof: `npm test` against a server rooted at `public/`.
- [x] `scripts/check_public.py` scans everything in `public/`, including text inside the review app, for email addresses, phone numbers, street addresses, student or account identifiers, local paths, credential-shaped strings, names of people, handout-style phrases (a keyword rule that runs on every check) and paths read from the source repository, and exits non-zero on any hit not in the reviewed allowlist or any allowlist line whose expected count differs from the real count. Proof: `python scripts/check_public.py` exit code and a planted-hit self-test.
- [ ] No long passage of a course handout appears verbatim in a served file. Not yet shown: the shingle comparison exists (`python scripts/check_public.py --handout <file>`) but has not been run, because the handout text is in neither repository. Tick it after a run against the handout text exits 0.
- [x] After a deploy, `node scripts/check_live.mjs <base-url>` exits non-zero unless the landing page, `/review/`, `/facts.json`, the full film (HEAD) and a licence text return 200, the landing page carries its title, `/facts.json` parses with a requirement count, and each path in its hidden list (repository files outside `public/` and `public/`-prefixed copies) returns 404. Proof: run against the local server rooted at `public/`, then against the live address after each deploy.

## Quality

- [x] No console errors, no horizontal page scroll and no mojibake on either page at 1440x900, 768x1024 and 375x812, light and dark. Proof: `npm test`.
- [x] The review app's 3D canvas draws non-blank pixels. Proof: `npm test`.
- [x] A stranger on a phone can watch the film, learn the gripper is an unbuilt design and reach a specific fit finding. Proof: the three real-browser jobs recorded in the pull request.
