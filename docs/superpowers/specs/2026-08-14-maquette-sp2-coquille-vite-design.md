# Maquette SP2 — the Vite shell

**Status**: approved by the operator (2026-08-14) · **Branch**: `refactor/maquette-sp2`
**Scope**: sub-project 2 of the maquette structuring — the build chassis around the
prototype. **Not one line of the prototype's markup, CSS or logic changes**, and nothing
the prototype renders may differ through the shell — that identity is the deliverable.

## Context

SP1 (merged, PR #429) gave the prototype its served directory: `frontend/maquette/design/`
holds `refonte.html` (1.9 MB, no framework, one inline `<script>` of 1.66 MB) and
`assets/` (925 webp files, hash-named). The harness (42 rules) measures the source through
`/tmp/tm-refonte/wrapped.html`; `serve.py` serves it live on `tm-design` behind a session
gate; `scripts/extract-maquette-css.py` reads its single `<style>`.

The target stack is settled (SP1 spec): React + Vite + TanStack Router + Tailwind + TS.
SP2 builds the **chassis only**: a Vite project around the untouched prototype, with an
executable proof that the shell changes nothing. Module extraction is SP3/SP4; the visual
language is SP5.

## Operator arbitrations (settled — do not re-litigate)

1. **The live host keeps serving the source.** `serve.py` and `tm-design` do not change
   in SP2; what the operator judges on a phone stays exactly what the 42 rules measure.
   The host switches to the Vite output only at the END of SP2's family of work, when the
   identity proof holds — that switch is its own future step, not part of this spec.
2. **The shell is born alongside**, with a DOM-identity proof (rendered DOM and geometry,
   never screenshots — measured twice on this project that screenshot hashes are not an
   oracle).
3. **The end of « zéro dépendance » is assumed**: a `package.json`, a committed lockfile
   and a `node_modules/` (gitignored) enter `frontend/maquette/design/`.

## Design

### The Vite project

`frontend/maquette/design/` becomes the Vite root:

- `package.json` — private, one devDependency: `vite` (same major as the app's,
  `^8.1.3`). Scripts: `dev`, `build`, `preview`.
- `index.html` — the REAL envelope: `<!doctype html>`, `<html lang="fr">`, charset,
  the viewport meta (`width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no`),
  a `<title>`, and a placeholder comment marking where the prototype fragment lands.
  This is knowingly the envelope's THIRD incarnation (serve.py's HEAD/TAIL and the
  harness re-sync recipe are the other two); unifying the three belongs to the
  host-switch step, not to SP2.
- `vite.config.mjs` — one tiny local plugin, `injecte-maquette`: in `transformIndexHtml`
  with `order: "post"`, replace the placeholder with the verbatim content of
  `refonte.html`. `order: "post"` runs after Vite's own HTML processing, so the fragment
  is emitted UNTRANSFORMED — no minification, no script extraction, byte-for-byte the
  source. The same hook serves dev and build.
- `package-lock.json` committed (the build must be deterministic — the frontend's
  already is, measured).

`dist/` and `node_modules/` are already covered by the repo `.gitignore` (`dist/`,
`node_modules/`); the SP1 negation (`!frontend/maquette/design/assets/**`) does not
re-include them. Verify with `git check-ignore` rather than assuming.

### The proof — R72, `harness/coquille.py`

A new rule builds the shell and measures that its output renders the SAME interface as
the source:

1. `npm run build` in `design/` (skip `npm install` when `node_modules/` is present).
2. Serve `dist/` on a scratch port (never 8710/8711/8899/8712) with assets reachable —
   `dist/` carries the fragment whose image URLs are relative `assets/...`; the build
   must make them resolve (copy or Vite `publicDir` pointing at `assets/`).
3. Open the SOURCE (8899 `wrapped.html`) and the BUILD (scratch port) in two contexts of
   the same browser, drive both to the same named states (at least: the default arrival,
   `acq-ajout-resultats`, one library state, one fiche), and compare per state:
   - the rendered DOM: tag/id/class serialization of `#view`, `#screen`, `#sheet`
     subtrees (order included);
   - the geometry of the harness regions: bounding rects of the `harnessSelectors`
     present, within a 1px tolerance;
   - zero failed responses (status ≥ 400) on either side, with `/favicon.ico` excepted
     (both servers generate uninvited requests for it, a harness-environment miss, not
     the prototype's); plus `pageerror` events (JavaScript errors). Known blind spot:
     sub-HTTP failures (`requestfailed`) are not guarded, acceptable for same-origin
     static trees.
4. Mutation-verified in both directions: (a) corrupt the emitted fragment (one class
   renamed in `dist/`'s html) → the DOM comparison falls naming the state and node;
   (b) drop the assets from the scratch server → the response guard catches the failed
   asset 404s on the built side alone.

The rule is allowed to be the suite's slowest; it runs `npm` and a build, so it prints
what it is doing. It must leave no scratch server running on any exit path.

### What SP2 does NOT touch

- `refonte.html` — not one byte.
- `serve.py`, the live host, Caddy — nothing.
- The harness's 42 existing rules and the `wrapped.html` ritual — unchanged (their
  retirement is the host-switch step's business).
- The CSS extraction contract and `make check` — unchanged.
- No React, no TypeScript sources, no Tailwind, no router, no module extraction.

## Delivery

Branch `refactor/maquette-sp2` from `main` (`aa88fc73`). Conventional Commits, scope
`(shell-mobile)`, French messages, no AI attribution. One commit per item:

1. the Vite project (package.json + lockfile, index.html, vite.config.ts, plugin)
2. R72 `harness/coquille.py` + `regions.json` entry + README row (mutation evidence in
   the commit message)
3. docs + version bump (patch → 0.97.2)

## Verification (all executed, none assumed)

- R72 green, both mutations felling exactly their own check, restored green.
- The full 43-script suite green (background, sequential, one measuring process).
- `make check` green (the shell adds no Python and must not disturb the CSS guard);
  `git check-ignore` proves `design/node_modules/` and `design/dist/` are ignored and
  the lockfile is tracked.
- `git status` clean after the R72 run (no scratch residue, no dist/ tracked).
- Push with remote SHA verified; PR; CI 10/10; merge on operator's standing instruction
  for this lane, then `pm2 restart torrentmate-design` is NOT needed (serve.py untouched).

## Out of scope, recorded for the next steps

- The host switch to the Vite output + envelope unification + wrapped.html retirement
  (end of the SP2 family, own spec or explicit step).
- The permanent `/assets/` gate rule (carried from SP1's final review, → this lane).
- SP3 routing, SP4 componentisation, SP5 visual language.
