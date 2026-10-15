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
| `<path>` | `<purpose>` | `<yes/no>` | `<yes/no>` |

### Data flow

Describe inputs, transformations, stores, outputs, and trust-boundary crossings.

### Integrations

| System | Direction | Credential name | Failure behavior |
|---|---|---|---|
| `<system>` | `<in/out/both>` | `<name only>` | `<behavior>` |

### Ownership and concurrency

Record component owners, shared mutable resources, worktree constraints, ports, test databases, and deployment targets.

Update this record when a component boundary, data flow, owner, integration, core document, or important path changes.
