# Maquette SP3 — the router, by strangler

**Status**: approved by the operator (2026-08-14, « c'est parti pour SP3 », strangler confirmed) · **Branch**: `feat/maquette-sp3`
**Scope**: sub-project 3 — React and TanStack Router enter the maquette as the OUTER
shell; the legacy engine runs unchanged inside a catch-all route; the router becomes the
single owner of the URL and the history. The harness switches to measuring the BUILD
first, while build ≡ source still holds, so every later step lands under watching rules.

## Context

The host serves the Vite build (bascule, PR #431), rebuilt on stale sources, held by R73.
R72 still proves build ≡ source to the byte — a guarantee SP3 will deliberately break the
day the router enters the build. The prototype is one 1.66 MB inline script: hand-rolled
navigation (R59 back-path with guard entry, R69 URL-carries-state, R71 screen stack),
74 named states behind the `__go` seam, 44 rules measuring `wrapped.html` on 8899.

TanStack Router ships React (and Solid) adapters only — choosing it brings React in now.
The operator confirmed the strangler after an explicit confidence check: the app stays
whole and measurable at every step, each migrated surface is final code, and the URL
bridge is the one delicate piece — watched by exactly R59/R69/R71.

## Operator arbitrations (settled)

1. **Strangler**: React 19 + TanStack Router as the outer shell from SP3; the legacy
   engine (the inline script, verbatim) runs inside a single catch-all route; SP4 empties
   it surface by surface.
2. **The build becomes the measured truth** before the router enters. What the operator
   judges, what the rules measure and what the pipeline builds are ONE artifact again.
   The `wrapped.html` ritual's CONTENT changes (a copy of the build instead of a
   hand-wrapped source); its isolation role survives.

## Phase A — the measurement switch (build ≡ source still true)

Small by design, and done FIRST because it is risk-free while R72 holds:

- The re-sync ritual becomes: `npm run build` in `design/`, then
  `cp design/dist/index.html /tmp/tm-refonte/wrapped.html`. The 8899 URL, `commun.py`,
  and every rule's probes are UNCHANGED — the served document is byte-identical to the
  old wrapper except the envelope (title, lang, PWA head), which no rule's subtree probes
  read. Mutation rituals keep working: the fragment sits verbatim inside the copy, and
  mutations keep applying to the COPY, never the source.
- Documented in the README and IMPLEMENTATION.md recipes; the harness scripts that READ
  the raw source (`panneau.py`, `export.py`, `demarrage.py`, `palette.py`,
  `renommer.mjs`, `extract-maquette-css.py`) keep reading `refonte.html` — they assert
  SOURCE properties and are not affected by what is served.
- Exit gate: the full 44-script suite green measuring the build copy.

## Phase B — React + TanStack Router, the strangler shell

### The shell

- `design/` gains dependencies: `react`, `react-dom`, `@tanstack/react-router` (versions
  aligned with `frontend/`'s: React ^19, router latest v1). The envelope (`index.html`)
  gains ONE `<script type="module" src="/src/coquille.tsx">` (name final at plan time) —
  the first and only module entry; Vite bundles it under `dist/vite/` (reserved at SP2).
- The shell mounts the router on a dedicated root element ADDED to the envelope body,
  BEFORE the legacy fragment. The legacy fragment stays injected verbatim by the SP2
  plugin — its markup, its inline script, untouched.
- **Route table v1** (the addressable locations R69 already defined — states are NOT
  routes):
  - `/` with the existing query params (`page`, `tab`, `lens`, `mode`, `cat`, `rub`) as
    validated search params — the catch-all that hosts the legacy engine;
  - no other route in SP3. Screens (fiche, ajout, profil, releases, resolution) and
    layers (sheet, drawer) remain the legacy engine's business until SP4 migrates them.
    SP3 delivers the OWNERSHIP change, not new addressing.

### The URL bridge — single writer, and it is the router

The delicate piece, named and contained:

- The legacy nav cluster (`noterLeChemin`, the `popstate` handler, `deroulerCouche`, the
  layer/screen-stack pushes, the boot-time guard entry) stops calling
  `history.pushState`/`history.back` directly. A bridge object (`window.__pont`, a seam
  like `__go`) exposes the same verbs (`noter(etat, url)`, `entrer(couche)`,
  `derouler(couche)`, `retour()`), implemented ON the router's history instance. One
  writer; the legacy code keeps its LOGIC (what to push, when to unwind) and loses only
  its primitive calls.
- The router's search params drive `applyState` on real navigations (back/forward, direct
  URL entry), through the same `pilotage` discipline `__go` already uses — a navigation
  is not a journey replayed.
- **R59's guard-entry semantics** (exit-armed double-back, the Android close behavior)
  must survive the bridge byte-for-byte in behavior. R59, R69, R71 are the acceptance
  gates of the bridge — no bridge lands while any of the three is red.
- `__go` keeps driving states WITHOUT navigation, as today.

### R72's renegotiation, explicit

The day the module entry lands, byte-exact `dist == envelope + fragment` is false by
design. R72's contract shrinks to what stays true and worth holding:

- the FRAGMENT is still emitted verbatim inside `dist/index.html` (the plugin path is
  unchanged) — the byte-exact assertion is rescoped to the fragment substring;
- the DOM/geometry comparison (source-standalone vs build) RETIRES: the build now
  contains the router by design. Its purpose — keeping the shell honest while the host
  switched — is complete. The retirement is recorded in `regions.json` (a rule retires
  when its mechanism disappears, never silently), and the rendered-truth duty passes to
  the 43 rules now measuring the build directly.
- A NEW hold replaces it in `coquille.py`: the module entry is present exactly once in
  the emitted document, and the bundle it names exists under `dist/vite/`.

### New rule — R74, the bridge

One rule for the new mechanism: with the shell mounted, (a) `history` has a single
writer — a legacy-style direct `pushState` is absent from the source (source-read
assertion on the nav cluster), (b) a real back after `results → fiche` still redraws the
covered screen (R71's journey, re-run through the bridge), (c) a direct URL with query
params lands on the state R69 promises, (d) `__go` still drives without touching the
history depth. Mutation-verified: severing the bridge (one verb rerouted to a no-op)
must fell (b) or (c) naming the mechanism.

## What does NOT change in SP3

- `refonte.html`'s rendering logic and surfaces — zero behavioral change; only the nav
  cluster's history PRIMITIVES are re-plugged onto the bridge (same file, smallest diff
  that makes the router the single writer).
- `serve.py` — nothing; it serves whatever the build emits. (`dist/vite/*` assets resolve
  as relative module imports inside the document — verify at plan time whether serve.py
  needs a route for them; if it does, that is Phase B scope and must be session-gated
  like `/assets/`.)
- The CSS extraction contract, the session gate, R73, the source-reading rules.

## Delivery

Branch `feat/maquette-sp3` from `main` (`a7e7396b`). Two phases, each with its own gate;
Conventional Commits, scope `(shell-mobile)`, French messages. Version bump: 0.97.4 at
delivery (patch — the maquette is pre-v1 tooling; the operator's per-PR bump rule).

Phase A: ritual switch + README/IMPLEMENTATION recipes + suite 44/44 green on the build
copy. Phase B: shell + bridge + R72 rescope + R74, suite green (now 45 rules), live host
smoke (the built document with the router mounts and the legacy app answers), PR, CI,
merge on standing instruction, pm2 restart not required (serve.py untouched) but the
post-merge live check re-run.

## Verification (all executed, none assumed)

- Phase A gate: 44/44 green measuring the build copy, before any Phase B commit.
- R74 green with its four holds; the bridge-severing mutation felling its hold by name.
- R59, R69, R71 green THROUGH the bridge (unchanged rule code — that is the point).
- R72 rescoped: fragment-verbatim assertion + module-entry hold green; retirement of the
  DOM comparison recorded in regions.json.
- R73 green (serving contract untouched). Full suite green. `make check` green.
- Push verified, PR, CI 10/10, merge, post-merge live check.

## Out of scope (SP4+)

- Migrating any surface into React components; emptying the catch-all.
- New routes for screens (fiche etc.) — SP4, one surface at a time.
- Konsta UI / Motion / TanStack DB-Store evaluations (SP4/SP5 as settled in SP1).
- The dev-server path (`vite dev`, `::1`) as a measured target — the harness measures
  builds; dev stays a human convenience.
- Retiring `refonte.html` as the editing source — that is the END of SP4, not SP3.
