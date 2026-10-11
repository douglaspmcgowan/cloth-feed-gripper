# Cloth-feed gripper site

Public site for the cloth-feed gripper, a UC Berkeley ME102B design that has not been built. It has a landing page, the film, and the interactive design review app. Everything is static and served from `public/`.

## What is in `public/`

| Path | Source |
|---|---|
| `index.html`, `landing.css`, `landing.js`, `favicon.svg` | hand-written, no framework or build |
| `review/index.html` | the review app, wrapped in a document head and a Home link; generated |
| `media/` | teaser, full film, vertical cut, posters and the social image; generated |
| `licenses/` | licence texts for the third-party assets; generated |
| `facts.json`, `tokens.css`, `provenance.json` | figures, design tokens and file hashes read from the source; generated |

`scripts/sync.py` writes every generated file from the source repository at one commit. `provenance.json` records the source repository name, that commit, the sync date, and each served file's public path, sha256 and size; it says nothing about the source repository's layout. The landing page shows no figure that is not read from `facts.json`.

## Commands

```powershell
npm ci
npx playwright install chromium

python scripts/sync.py --ref 996dce6      # refresh generated files; running it twice changes nothing
python scripts/check_public.py            # scan public/ for private content
npm run serve                             # http://127.0.0.1:4173/
npm test                                  # Playwright, 3 sizes x light and dark
npm run lint
```

`sync.py` takes `--source <path to a clone>` to use a local checkout, and otherwise makes its own shallow clone with `gh`.

## Checks

- `scripts/check_public.py` looks for emails, phones, addresses, student IDs, local paths, credential shapes, names of people, handout-style phrases and paths from the source repository (read from `scripts/sync.py`'s own input table), in every file including the text inside the review app, and for any digit typed into the landing page's text. A hit passes only with a reviewed line in `scripts/public-allowlist.txt` that also states how many times it occurs; a different count fails. `--self-test` plants one hit per rule. A shingle comparison against a course handout runs only with `--handout <file>` and has not been run.
- `npm test` covers console errors, sideways scroll, broken text, the hero poster, film playback, the 3D canvas, each landing door, the Home link, and that nothing outside `public/` is served.

## Deploying

`vercel.json` sets `public` as the output directory with no framework and no build command. Deploying is a separate step that needs the owner's say-so.

After a deploy, run the guard against the live address:

```powershell
npm run check:live -- https://cloth-feed-gripper.vercel.app
```

It prints one line per path and ends with `check_live: N ok, M failed`. It exits non-zero unless the landing page, `/review/`, `/facts.json`, the full film (HEAD) and a licence text return 200, and every repository file outside `public/` (`/AGENTS.md`, `/TASK.md`, `/README.md`, `/SPEC.md`, `/package.json`, `/vercel.json`, `/.agents/INDEX.md`, `/scripts/sync.py`, `/tests/deploy.spec.mjs`, `/.gitignore`, `/site.config.json`) returns 404.

## Runtime dependencies

The review app loads three.js from jsDelivr, and both pages load Public Sans from Google Fonts. Without a network the 3D views do not draw.

## Credits

See the credits section of the landing page: SO-ARM100 geometry (Apache-2.0), Archivo and Public Sans (OFL), three.js (MIT).
