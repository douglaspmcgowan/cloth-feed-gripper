# Specification

What the site must do, as criteria observable by running it. Why it exists and for whom: `PRODUCT.md`. Look and behaviour: `DESIGN.md`.

Source of every requirement below: Douglas, 2026-10-10, "put the video in the website, make the website its own repo, put it on vercel, make it public", as refined in the dispatch brief of the same date. Each item names its proof. A box is ticked only against that proof.

## Site shape

- [ ] `/` is a landing page and `/review/` is the design review app served as a standalone HTML document. Proof: `npm test` loads both; each has doctype, `lang`, charset and viewport.
- [ ] The two pages read as one product: the landing page uses the review app's own palette and type tokens, light and dark. Proof: `npm test` compares the landing page's computed `--accent`, `--bg` and `--ink` with the review app's at both schemes.
- [ ] A visitor in the review app reaches `/` in one click at any width without breaking the app's layout. Proof: `npm test` clicks the home link at 375, 768 and 1440 and checks no horizontal page scroll.

## Landing page

- [ ] The film is the centre of the page: a muted looping 10 s teaser with a poster; reduced motion shows the poster only. Proof: `npm test` with `reducedMotion: reduce` finds no playing teaser.
- [ ] One control plays the full 62 s film with native controls and sound; portrait phones get the vertical cut. Proof: `npm test` presses play and sees `readyState >= 2` and `currentTime` advance, at 375x812 and 1440x900.
- [ ] No film downloads until asked. Proof: `npm test` records network requests before pressing play and finds no request for the full-length or vertical film.
- [ ] A non-engineer can read what the gripper is in two or three sentences. Proof: reviewed in the real-browser jobs.
- [ ] The page says honestly that the design is not built or measured, and every figure on it (requirement counts, mass, open decisions) is read by `scripts/sync.py` from the source at the pinned commit. Proof: `public/facts.json` carries the figures and `npm test` checks each rendered figure equals its `facts.json` value; `check_public.py` finds no hand-typed figure.
- [ ] Four doors deep-link the review app by job: see the model, check the fits, follow the assembly, read what is still open. Proof: `npm test` clicks each and checks the named view is shown.
- [ ] The page links the build log https://build-log-eight.vercel.app/log/gripper-2026-09-22/ and credits every third-party asset it serves. Proof: `npm test` finds the link; the credits list matches `public/provenance.json` and the review app's own external loads.

## Media

- [ ] Three films in `public/media/` with the moov atom first, a compressed poster under 250 KB and a 1200x630 Open Graph image. Proof: `scripts/check_public.py` checks moov position, poster size and OG dimensions.

## Sync

- [ ] One command, `python scripts/sync.py --ref <sha>`, copies the inputs from a `berkeley-ai-tutor` clone, writes the site files and `public/provenance.json` (repository, commit, date, sha256 and size of every copied file). Running it twice with the same ref changes nothing. Proof: second run, then `git status --short` is empty.

## Privacy and serving

- [ ] `vercel.json` sets `outputDirectory` to `public`, no framework, no build command, `cleanUrls`, long cache headers on `/media/*`. Proof: `npm test` reads it.
- [ ] Nothing outside `public/` is served: `/AGENTS.md`, `/TASK.md`, `/.agents/INDEX.md` return not found. Proof: `npm test` against a server rooted at `public/`.
- [ ] `scripts/check_public.py` scans everything in `public/`, including text inside the review app, for email addresses, phone numbers, street addresses, student or account identifiers, local paths, credential-shaped strings, names of people and long verbatim passages, and exits non-zero on any hit not in the reviewed allowlist. Proof: `python scripts/check_public.py` exit code and a planted-hit self-test.

## Quality

- [ ] No console errors, no horizontal page scroll and no mojibake on either page at 1440x900, 768x1024 and 375x812, light and dark. Proof: `npm test`.
- [ ] The review app's 3D canvas draws non-blank pixels. Proof: `npm test`.
- [ ] A stranger on a phone can watch the film, learn the gripper is an unbuilt design and reach a specific fit finding. Proof: the three real-browser jobs recorded in the pull request.
