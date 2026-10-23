<!-- agent-harness:universal-design:v1:start -->
## Universal interface rules

The authority is `~/.agents/DESIGN.md`, and it is fuller than this. What follows is
carried here rather than only linked because a cloud or container session has no
`~/.agents` to reach — so the rules that actually change what gets built have to survive
in the repository itself.

### Anti-default discipline

Quoted verbatim from the authority rather than paraphrased, because this is the section an
agent most needs and a paraphrase is a second copy that drifts.

The model's house style is recognizable, and reaching for it reads as machine-made. Never
default to: purple-blue gradients, a centered hero over a dark mesh background, three equal
feature cards, ubiquitous glassmorphism, or Inter with slate everywhere. The
beige-brass-espresso "premium consumer" palette is the same tell; rotate off it.

- Lock one accent color page-wide, and one gray family per project.
- Lock one corner-radius system per page. Mix radii only under a rule you can state.
- Keep one theme per page. Sections do not invert light and dark mid-scroll except as a single deliberate composition device.
- A section layout family appears at most once per page. At most two consecutive image-text zigzag splits.
- **No eyebrow labels and no kicker titles on any page, deck, or artifact.** An eyebrow or kicker is the small uppercase or letter-spaced label above a heading; the heading carries its own weight, so delete the label. Ruled 2026-09-30.
- **Never use the middle dot `·` (U+00B7, `&middot;`) or the bullet `•` as an inline divider.** Separate inline items with a semicolon, `|`, a comma, or a line break. The em-dash stays banned as a divider. Ruled 2026-09-30.
- Where a brief reads as an established design system, use that system's official package rather than approximating it. One system per project.
- The brief wins. Honor a pinned aesthetic even when it is not the choice you would make; redirecting a clear brief toward your own taste is failure, not judgment.

### Names that appear here only to be forbidden

The rules above and below name specific typefaces in order to ban them. A project that
scans its own source for banned font names will find those names *here* and report this
file as the violation — measured on `base-flight-finder`, 2026-08-07, whose typography
policy test failed against text whose whole purpose is to forbid the thing it names.

**If you write such a scan, exclude the region between the two `agent-harness:universal-design`
marker comments.** That region is generated and is replaced wholesale on every sync, so
nothing a project owns ever lives inside it. The names are also declared machine-readably
on the next line, so a scanner can subtract them without parsing prose. `Test-DesignBlockScanSafety.ps1`
fails the build if any of them appears outside the markers, which is what makes the
exclusion sufficient rather than merely conventional.

**Match on word boundaries, not substrings.** `Inter` is a prefix of interaction,
interface, internal and interval, so a bare substring scan reports a violation on ordinary
English. That is a second, independent cause of the same false positive, and it lives on
your side of the line rather than in this block — the check above hit it on its own first
run, against the heading "Interaction and accessibility" a few sections down.

<!-- agent-harness:design-prohibited-names: IBM Plex Mono, Inter, Fraunces, Instrument Serif -->

### Everything else

- Never use IBM Plex Mono.
- **Never set anything in a monospace typeface unless it is code.** Not numbers, not labels, not reference tags, not captions, not credits, not timestamps. Monospace outside a code block is a costume that says "technical" and reads as machine output. Numerals that need to line up get `font-variant-numeric: tabular-nums` on the normal face instead.
- **Never use the middle dot as a separator.** No `·`, and no bullet character standing in for it. Separate with an en dash, a slash, a comma, or plain whitespace with a rule. The middle dot reads as machine-assembled metadata everywhere it appears, which is why it is out on every surface, not just decks.
- **Never write a line that is only "The" plus a noun.** "The transfer function", "The result", "The problem" — a bare definite noun phrase standing alone is the most common shape in machine-written copy and carries no more information than the noun alone. A title may open with "The"; a label, a bullet or a caption may not be one.
- **Never title anything as a noun followed by a rhythmic tag.** "The argument, rung by rung", "The story, piece by piece", "Design, from the ground up". The tag adds cadence, not meaning, and it is the tell that a title was composed rather than named. Title the thing by what it is.
- **A reference shown to a reader must be identifiable without the source document.** A bare bracket number or a bare superscript means nothing to someone who does not have the bibliography open, which on a slide or a poster is everyone. Name the author and year, and put the numbering in a source line if the numbering itself matters.
- Default to a sans display face. Use serif only with an articulated reason; `Fraunces` and `Instrument Serif` are banned as defaults specifically because they are the common machine-made choice.
- Hero discipline: the hero fits the first viewport, the headline runs at most two lines, subtext stays under roughly twenty words, and no more than four text elements sit inside it. Trust marks and logo walls go below the hero, never in it.
- A grid has exactly as many cells as there is content for. Reshape the grid rather than pasting in a blank tile.
- Every animation names what it communicates — hierarchy, sequence, feedback, or state change. An animation that names nothing gets cut.
- Reread every visible string before shipping. Never invent a precise-sounding number.
- Use a proportional body face for prose, navigation, labels, dates, names, and human-readable metadata.
- Reserve monospace for code and commands only, and set it in a code block. Identifiers, timestamps and numeric columns take the proportional face.
- Define explicit body and display roles, and a monospace role only where the surface actually renders code. Use tabular numerals on the proportional face for aligned quantities.
- Establish hierarchy through size, weight, spacing, and placement before decoration.
- **Use all-caps titles, labels, and headings very, very sparingly, only when absolutely necessary.** Uppercase letters and `text-transform: uppercase` both count; the default is sentence case. Ruled 2026-09-30.
- Give each screen a clear primary action or reading path. Use spacing and alignment to show relationships.
- Reuse existing tokens and components before adding variants.
- Cover relevant default, hover, focus, active, disabled, loading, empty, error, and success states.
- Use semantic structure and native controls, visible keyboard focus, logical tab order, accessible names, sufficient contrast, and non-color state cues.
- Support narrow, medium, and wide layouts, zoom, text resizing, touch targets, and reduced motion.
- A design skill's silence on accessibility is not an exemption. Seven of the sixteen design-adjacent skill packages carry no accessibility content at all, so the two bullets above are the floor whichever skill is driving.
- A visual world is chosen, not accumulated. Template packs, style presets, and named aesthetics contradict each other by construction — `retro-windows` bans every rounded corner where `capsule` requires a 9999px radius. Commit to one, take its taste entire, and treat the others as unread. The rules here apply to all of them.
- Inspect the existing design system, screenshots, and implementation before proposing a new rule or component.
- Verify browser-visible work with browser or end-to-end tests across responsive, keyboard, loading, empty, and error behavior.

### Design libraries

Concrete things to reach for — animation packages and working skeletons, icon kits, typeface pools, design-system install commands and canonical documentation. Read the leaf you need; each one loads on its own.

- **Index** `~/.agents/design/LIBRARIES.md`
- **Precedence and routing** `~/.agents/design/precedence.md` — which source wins when the universal rules, `impeccable` and a pinned brief disagree, and whether this project's design detector hook is actually wired
- **Stack templates** `~/.agents/design/STACK-TEMPLATES.md` — seven app-kind templates naming an occupant for all 22 stack slots, and the per-slot deviation rules. The selection itself belongs to `~/.agents/skills/stack/SKILL.md`: six observable questions, the scaffold, and `architecture.md`'s import direction. Enter there before choosing a framework, styling method, primitive layer or component source, and read the result in this file's `## Stack selection`; `solo-review` stack mode measures a real repository against it
- **Motion** `~/.agents/design/animation/` — `libraries.md`, `sticky-stack.md`, `horizontal-pan.md`, `scroll-reveal.md`, `liquid-glass.md` (frosted glass), `forbidden.md`
- **Icons** `~/.agents/design/icons/libraries.md`
- **Type** `~/.agents/design/type/families.md`
- **Design systems** `~/.agents/design/systems/install.md` and `sources.md`
- **Design languages** `~/.agents/design/languages/registry.md` — read it before committing a visual world or generating a new design language, and register the world committed for this project there in the same work unit
- **Surface craft** `~/.agents/design/craft/` — `high-end.md` (surface construction), `from-reference.md` (building faithfully from a reference image), `from-code.md` (reading a design system out of a live product's own CSS), `device-mockups.md`
- **Fundamentals** `~/.agents/design/fundamentals.md` — the arithmetic under a decision: palette construction (60-30-10, one accent, warm neutrals, the colourblind-safe sets and the grayscale test), type-scale ratios with a worked scale and measure, and grid selection. Read it when the palette or scale is not already decided
- **Slides and posters** `~/.agents/design/slides-and-posters.md` — the only leaf addressing a non-web medium: deck frameworks, PowerPoint craft, HTML deck frameworks, and the academic poster including A0 sizing and the ≥24pt body floor
- **Pre-ship matrix** `~/.agents/design/preflight.md` — the mechanical finish check for landing, marketing and portfolio surfaces; not dashboards, not product UI
- **Dashboards and data-dense product UI** `~/.agents/design/dashboards.md` — the full system for the surface this tree used to leave uncovered: the three dashboard kinds and why building one while thinking of another causes most of the mistakes, information architecture and the three reading distances, density targets set against marketing spacing, typography and colour for data (sequential, diverging, categorical and semantic scales), chart selection ordered by the Cleveland-McGill perceptual ranking, chart and table craft, the six states every data region has, filters and URL state, interaction, real-time cadence, renderer choice by point count, the charting-library table, the anti-patterns, and a §18 pre-ship matrix that is the entry above's equivalent for this medium. This line used to say the tree did not own dashboards and pointed at the `/design-review` rubric, which critiques a running app rather than generating one; that gap closed on 2026-08-09
- **Mobile, touch and responsive** `~/.agents/design/mobile.md` — the medium, not a surface type: the three kinds of mobile thing and why a responsive site should not get a bottom tab bar, the viewport and its moving parts (`svh`/`lvh`/`dvh`, `viewport-fit=cover`, `env(safe-area-inset-*)` with the `max()` fallback that is the part people omit), the three touch-target floors — WCAG 2.2's 24px, Material's 48dp, Apple's 44pt — and which to design to, thumb reach and what it decides, mobile type including the 16px threshold below which iOS zooms a focused input, breakpoints and container queries, navigation patterns, forms with `inputmode`/`autocomplete`/`enterkeyhint` and the keyboard that covers your action bar, the gestures the OS has already reserved, the states that do not exist without a pointer, scrolling, the motion budget on a mid-tier device, images, offline, touch accessibility, the anti-patterns, a §18 pre-ship matrix, and §19 on the four checks emulation cannot answer. It does not restate `impeccable`'s `reference/adapt.md`, which owns converting an existing surface between contexts
- **Production readiness** `~/.agents/design/ADVISOR-PRODUCTION-READY.md` — what still stands between the design-space explorer and the Work Scope graph and real use
- **Design-space explorer** `~/.agents/design/design-space-explorer/README.md` — the reusable two-axis combination explorer, its intent, specification, design rules, and inspection record
- **Design-space manifests** `~/.agents/design/design-spaces/README.md` — the reusable schema for design-space axes, entries, palettes, templates, and generated-axis sources
- **Mission-control design studies** `~/.agents/design/mission-control/AESTHETIC-OPTIONS.md` and `REPRESENTATIONS.md` — visual-world and information-representation options for that surface
- **Full-scope checklist** `~/.agents/design/fullscope-checklist.md` — what a full-scope build must cover, group by group, before the `fullscope` skill calls it done
- **Workflow design template** `~/.agents/design/workflow-design-template.md` — the reusable four-phase `Workflow` script for a design build, with its prompt pattern
- **Harness map** `~/.agents/design/harness-map/DESIGN.md` — the sources of the harness's own map page (`harness-graph.html`, generated by `tools/Build-HarnessGraph.ps1`) and that sub-app's recorded stack selection and import direction

The full universal rules are `~/.agents/DESIGN.md`. Where a library entry and a rule disagree, the rule wins.

**This list is enumerated because it has to be.** A cloud or container session has no `~/.agents` to walk, so this block is the only routing it gets — which also means a leaf missing here is a leaf that session cannot reach at all. `craft/` and `preflight.md` were absent until 2026-08-07 and every project copy inherited the gap. `Test-DesignLibraryIndex.ps1` now fails the build when this list falls behind the tree.
<!-- agent-harness:universal-design:v1:end -->

# Project design rules

This file is the interface authority for the site: the landing page and the design review app, both served from `public/`. Every rule that changes what gets built here is written out below. The tokens it names are defined in `public/tokens.css`, and the look and behaviour the tests check are in `SPEC.md`.

## Interface rules

### Anti-default discipline

The model's house style is recognizable, and reaching for it reads as machine-made. Never default to: purple-blue gradients, a centered hero over a dark mesh background, three equal feature cards, ubiquitous glassmorphism, or Inter with slate everywhere. The beige-brass-espresso "premium consumer" palette is the same tell; rotate off it.

- Lock one accent color page-wide, and one gray family per project.
- Lock one corner-radius system per page. Mix radii only under a rule you can state.
- Keep one theme per page. Sections do not invert light and dark mid-scroll except as a single deliberate composition device.
- A section layout family appears at most once per page. At most two consecutive image-text zigzag splits.
- **No eyebrow labels and no kicker titles on any page, deck, or artifact.** An eyebrow or kicker is the small uppercase or letter-spaced label above a heading; the heading carries its own weight, so delete the label. Ruled 2026-09-30.
- **Never use the middle dot (U+00B7, `&middot;`) or the bullet character as an inline divider.** Separate inline items with a semicolon, `|`, a comma, or a line break. The em-dash stays banned as a divider. Ruled 2026-09-30.
- Where a brief reads as an established design system, use that system's official package rather than approximating it. One system per project.
- The brief wins. Honor a pinned aesthetic even when it is not the choice you would make; redirecting a clear brief toward your own taste is failure, not judgment.

### Prohibited typefaces

These names appear in this file only inside the rules that forbid them: IBM Plex Mono, Inter, Fraunces, Instrument Serif.

A check that scans source for these names must match whole words. `Inter` is a prefix of interaction, interface, internal and interval, so a substring scan reports ordinary English as a violation.

### Everything else

- Never use IBM Plex Mono.
- **Never set anything in a monospace typeface unless it is code.** Not numbers, not labels, not reference tags, not captions, not credits, not timestamps. Monospace outside a code block is a costume that says "technical" and reads as machine output. Numerals that need to line up get `font-variant-numeric: tabular-nums` on the normal face instead.
- **Never use the middle dot as a separator.** No U+00B7, and no bullet character standing in for it. Separate with an en dash, a slash, a comma, or plain whitespace with a rule. The middle dot reads as machine-assembled metadata everywhere it appears, which is why it is out on every surface.
- **Never write a line that is only "The" plus a noun.** "The transfer function", "The result", "The problem" — a bare definite noun phrase standing alone is the most common shape in machine-written copy and carries no more information than the noun alone. A title may open with "The"; a label, a bullet or a caption may not be one.
- **Never title anything as a noun followed by a rhythmic tag.** "The argument, rung by rung", "The story, piece by piece", "Design, from the ground up". The tag adds cadence, not meaning, and it is the tell that a title was composed rather than named. Title the thing by what it is.
- **A reference shown to a reader must be identifiable without the source document.** A bare bracket number or a bare superscript means nothing to someone who does not have the bibliography open. Name the author and year, and put the numbering in a source line if the numbering itself matters.
- Default to a sans display face. Use serif only with an articulated reason; `Fraunces` and `Instrument Serif` are banned as defaults specifically because they are the common machine-made choice.
- Hero discipline: the hero fits the first viewport, the headline runs at most two lines, subtext stays under roughly twenty words, and no more than four text elements sit inside it. Trust marks and logo walls go below the hero, never in it.
- A grid has exactly as many cells as there is content for. Reshape the grid rather than pasting in a blank tile.
- Every animation names what it communicates — hierarchy, sequence, feedback, or state change. An animation that names nothing gets cut.
- Reread every visible string before shipping. Never invent a precise-sounding number.
- Use a proportional body face for prose, navigation, labels, dates, names, and human-readable metadata.
- Reserve monospace for code and commands only, and set it in a code block. Identifiers, timestamps and numeric columns take the proportional face.
- Define explicit body and display roles, and a monospace role only where the surface actually renders code. Use tabular numerals on the proportional face for aligned quantities.
- Establish hierarchy through size, weight, spacing, and placement before decoration.
- **Use all-caps titles, labels, and headings very, very sparingly, only when absolutely necessary.** Uppercase letters and `text-transform: uppercase` both count; the default is sentence case. Ruled 2026-09-30.
- Give each screen a clear primary action or reading path. Use spacing and alignment to show relationships.
- Reuse existing tokens and components before adding variants.
- Cover relevant default, hover, focus, active, disabled, loading, empty, error, and success states.
- Use semantic structure and native controls, visible keyboard focus, logical tab order, accessible names, sufficient contrast, and non-color state cues.
- Support narrow, medium, and wide layouts, zoom, text resizing, touch targets, and reduced motion.
- Accessibility is not waived by a tool or a skill that does not address it. The two accessibility bullets above are the floor for every surface.
- A visual world is chosen, not accumulated. Template packs, style presets and named aesthetics contradict each other by construction, so commit to one, take its taste entire, and leave the others unapplied. The rules here apply to whichever is chosen.
- Inspect the existing design system, screenshots, and implementation before proposing a new rule or component.
- Verify browser-visible work with browser or end-to-end tests across responsive, keyboard, loading, empty, and error behavior.

### Mobile and touch

- A responsive site does not get a bottom tab bar.
- Form inputs use a font size of at least 16px. Below that, iOS zooms the page when a field takes focus.
- Touch targets are at least 24 CSS px, the WCAG 2.2 minimum.
- Full-height sections use `svh` or `dvh`, not `vh`, because mobile browser chrome changes the visible height.
- Pages declare `viewport-fit=cover`, and edge-touching layout pads with `env(safe-area-inset-*)`.

## Project record

### Stack selection

The one record of what this app is built out of.

- Template: not recorded. The stack selection was not made in this repository, so no template number is claimed.
- The stack in use, as the repository shows it: static HTML, CSS and vanilla JavaScript in `public/`, with no framework and no build step (`vercel.json` sets `outputDirectory` to `public`). Node scripts serve the site, extract facts and take screenshots. Python 3 standard-library scripts sync the inputs and run the public-content check. Playwright runs the tests.
- The six answers: not recorded.
- Slots each answer decided: not recorded.
- Deviations: none recorded.

### Product-specific typography

- Body: Public Sans, with `Segoe UI`, `system-ui` and `-apple-system` as fallbacks (`--sans` in `public/tokens.css`).
- Display: the same sans face.
- Monospace: none. Code is not shown on either page.
- Type scale (`public/tokens.css`): `--fs-s` 13px (small), `--fs-b` 15px (body), `--fs-h` `clamp(30px,3.2vw,34px)` (heading).

### Tokens and components

The tokens are defined in `public/tokens.css` for light and dark schemes. Use these and nothing else for colour. Values are light, then dark where the dark scheme redefines them. The few properties defined anywhere else are listed under "Where each token is defined" below.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#edf0f3` | `#0d1217` | page background |
| `--surface` | `#fbfcfd` | `#151c23` | cards and panels |
| `--raised` | `#f1f4f7` | `#1b242d` | raised fills within a surface |
| `--paper` | `#fdfdfc` | `#e9edf0` | document and picture backgrounds (inverted in dark) |
| `--ink` | `#141d27` | `#e2e8ee` | primary text |
| `--ink2` | `#4a5665` | `#a9b4c0` | secondary text |
| `--line` | `#d2d9e0` | `#2d3945` | borders and rules |
| `--accent` | `#1c5bb8` | `#7ca6fa` | the one accent: links, labels, active states |
| `--accent-ink` | `#fbfcfd` | `#0d1217` | text on the accent |
| `--accent-soft` | `#dce6f6` | `#1c2b44` | quiet accent fills |
| `--ok` | `#1b7443` | `#5ec48b` | pass status text |
| `--ok-soft` | `#dbeee2` | `#163324` | pass status fill |
| `--warn` | `#855400` | `#e0a849` | caution status text |
| `--warn-soft` | `#f5e8cc` | `#382b13` | caution status fill |
| `--bad` | `#ad2a20` | `#ff8074` | fail status text and limit lines |
| `--bad-soft` | `#f6dcd8` | `#3b1c19` | fail status fill |
| `--c1` | `#1c5bb8` | `#7ca6fa` | chart series 1 |
| `--c2` | `#c9601a` | `#f09a58` | chart series 2 |
| `--c3` | `#17806a` | `#4fcfa5` | chart series 3 |
| `--c4` | `#9c3a8a` | `#e17dd0` | chart series 4 |
| `--c5` | `#6a7482` | `#8793a0` | chart series 5 and neutral marks |
| `--grid` | `#e1e6eb` | `#222c36` | chart grid lines |
| `--band` | `rgb(27 116 67 / .12)` | `rgb(94 196 139 / .14)` | translucent limit or target band on charts |
| `--mesh` | `#e5e9ee` | `#10171d` | background of landing panels and the 3D viewer |
| `--shade` | `rgb(20 32 46 / .08)` | `rgb(0 0 0 / .3)` | soft shadow colour (`--elev`) |
| `--shade2` | `rgb(20 32 46 / .22)` | `rgb(0 0 0 / .6)` | deeper shadow colour (`--elev`) |
| `--veil` | `rgb(20 32 46 / .35)` | `rgb(0 0 0 / .55)` | scrim behind an open panel |

The gray family is the blue-gray set above. A new colour is a new token, not a literal value in a component.

Spacing, radii, motion and touch targets, all from `public/tokens.css`:

- Spacing: `--s1` 4px, `--s2` 8px, `--s3` 12px, `--s4` 16px, `--s5` 24px, `--s6` 32px, `--s7` 48px, `--s8` 64px.
- Radii: `--r1` 6px, `--r2` 12px.
- Motion: `--ease` `cubic-bezier(.2,.7,.2,1)`, `--t` 160ms.
- Touch target: `--tap` 36px, or 44px on a coarse pointer (`@media (pointer:coarse)`).
- Layout and elevation: `--rail` 248px (side rail width), `--stage-h` `clamp(320px,calc(100vh - 300px),720px)` (stage height), `--elev` `0 1px 2px var(--shade),0 14px 32px -18px var(--shade2)` (card shadow).

#### Where each token is defined

`public/tokens.css` and `public/review/index.html` are generated by `scripts/sync.py` from the review app's `:root` blocks and its own styles. Never edit either by hand; a change to a generated value goes through the review app's source and a sync. Every other custom property the pages read has one of the sources below. `tests/tokens.spec.mjs` fails when a `var(--name)` with no fallback has no source.

| Token | Defined in | Value | Use |
|---|---|---|---|
| `--measure` | `public/landing.css`, `:root` | `66ch` | landing text measure (page token) |
| `--wrap` | `public/landing.css`, `:root` | `1200px` | landing content width (page token) |
| `--fs-d` | `public/landing.css`, `:root` | `clamp(40px, 5.2vw, 64px)` | hero title only (page token) |
| `--sheet-h` | set on `.sheet` in `public/review/index.html` | `calc(var(--stage-h) + var(--s7))` | drawing sheet height limit (component-local) |
| `--zw` | set by the review app's script on `.sheet` when zoomed | percentage, e.g. `150%` | zoomed sheet width; falls back to `200%` |
| `--zh` | set by the review app's script on `.sheet` when zoom starts | the sheet's height in px | zoomed sheet height; falls back to `--stage-h` |
| `--sw` | set inline on a placeholder thumbnail (`.th.ph`) by the review app's template | `#rrggbb` part colour | placeholder swatch (script-set) |

The landing page's three page tokens live in its own `:root` and not in `tokens.css`, so they are not part of the shared palette. Moving them into `tokens.css` would need a change to `scripts/sync.py`, which is a separate decision and is not made here.

### Interaction and accessibility

- The landing teaser loops muted for 10 seconds. Under reduced motion it shows its poster only, and nothing plays.
- The full film and the vertical cut download only when the viewer presses play.
- Both pages hold at 375, 768 and 1440 widths with no horizontal page scroll.
- Both pages are checked in light and dark schemes, with no console errors and no mojibake.

### Professor first-visit route

The landing is a reading surface in the established review system: Public Sans, shared blue-gray neutrals, one blue accent, semantic status colours, tonal secondary actions and proportional numerals. A professor may open it on a projected desktop or a phone, so the system follows the viewer's light/dark preference rather than forcing a presentation theme. The shared generated palette and type remain authoritative.

- Wide landing: compact title and honest design status beside the real film. Narrow landing: title, status, film and controls stack. Play is the primary film action; the direct review remains available.
- The mechanism is an unboxed ordered explanation: close the fingers, sense the squeeze, let the cloth move. The tour is a distinct optional disclosure beside ordinary deep-link doors. Evidence follows, with failed requirements given explicit semantic colour and their own evidence links. Credits form a quiet two-column directory on wide screens.
- The tour never opens itself and never blocks navigation. A native button exposes `aria-expanded` and `aria-controls`; each step focuses its heading and marks the corresponding ordinary door with `aria-current="step"`. Previous is disabled at the first step; Finish and Close return focus to the start. Escape closes from within the panel. The live step count is navigation state, not a measured claim.
- Motion has two jobs: a once-only mechanism sequence on entry (480 ms, staggered 80 ms), and tour state continuity (240 ms). Both use the named exponential ease-out token; content is already visible before script or observer. Reduced motion removes both, cancels an active tour animation and retains all controls.
- Additional landing-only tokens in `landing.css`: `--section-space` is `clamp(48px, 7vw, 96px)`; `--motion-enter` is 480 ms; `--motion-step` is 240 ms; `--motion-ease` is `cubic-bezier(.16, 1, .3, 1)`; `--fs-caption` is `clamp(15px, 1.4vw, 24px)` so captions remain readable on a phone. The existing spacing scale supplies component padding and gaps.
- The authored walkthrough assets are `media/review-walkthrough.mp4`, its JPEG poster and its English VTT captions. They are produced by `tests/capture-walkthrough.mjs`, separate from sync-generated films, which are unchanged. The video and caption track receive a source only on explicit play; native controls handle pause and seek. Closing releases both sources. Failure displays a recovery message and retry action while the guide remains usable.
- The four doors are a bounded list of review jobs. Additional evidence belongs inside the review app; expanding from nine to ninety findings does not create ninety landing links.

Interaction prior art: the W3C APG disclosure pattern (https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/) supports the native optional disclosure. The guide uses it rather than a modal or a new tour dependency. The existing authored SVG arrow remains the only icon grammar; no new logo, font, trademark or third-party visual assets are introduced.

The guided fit stop progressively enhances its ordinary view link with a native text fragment targeting the existing “Horn rim to housing wall” label when `document.fragmentDirective` is available. This reveals and highlights the named cell inside the nested table without modifying generated review code. The ordinary fit door remains unchanged; unsupported browsers retain its normal hash route and the guide names the browser Find command and horizontal table scrolling as recovery. Native text fragments are documented at https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Fragment/Text_fragments. The browser test checks the cell against every clipping ancestor and the viewport, rather than treating DOM presence as successful arrival.

### Exceptions

None recorded.

## Standing no-list

The owner's standing rejections, recorded so the project starts above them.

- No kickers.
- No periods on titles.
- No taglines and no AI tells.
- No pointless metrics: show a number only when it changes what the reader does.
- The project brief wins over a palette rule in this file.
