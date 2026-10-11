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

`scripts/sync.py` writes every generated file from the source repository at one commit, and `provenance.json` records that commit and the hash of each file. The landing page shows no figure that is not read from `facts.json`.

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

- `scripts/check_public.py` looks for emails, phones, addresses, student IDs, local paths, credential shapes, names of people and handout text, in every file including the text inside the review app. A hit passes only with a reviewed line in `scripts/public-allowlist.txt`. `--self-test` plants one hit per rule.
- `npm test` covers console errors, sideways scroll, broken text, the hero poster, film playback, the 3D canvas, each landing door, the Home link, and that nothing outside `public/` is served.

## Deploying

`vercel.json` sets `public` as the output directory with no framework and no build command. Deploying is a separate step that needs the owner's say-so.

## Runtime dependencies

The review app loads three.js from jsDelivr, and both pages load Public Sans from Google Fonts. Without a network the 3D views do not draw.

## Credits

See the credits section of the landing page: SO-ARM100 geometry (Apache-2.0), Archivo and Public Sans (OFL), three.js (MIT).
