# SP4d wave 2 — Arrivées — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The second of SP4d's four page waves. `viewArrivals` leaves the fragment and becomes a
final React component, on the PAGE machinery wave 1 paid for. Arrivées is the pipeline's health
— what is stuck, what is moving, what arrived, and the run itself — and it is the first migrated
page that carries a CONTROL that mutates the world: the pilot's bar, whose three states include
the queue DOIT-4 exists for.

**Tech Stack:** React 19, @tanstack/react-router ^1.170, @tanstack/store ^0.11, Vite 8,
Playwright harness (`command python3` = 3.12.4, chromium `channel="chrome"`).

**Spec:** `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`
(§The waves — "SP4d… — the pages: … sys/maint/config, **arr**, lib, acq").

**Recon:** measured 2026-08-17 on `main` = `21c54a98` (v0.97.18, SP4d wave 1). Every line number
is an anchor HINT — re-grep the SYMBOL before editing.

## What the recon settled

- **`viewArrivals` is 43 lines** (`refonte.html` ~12496-12538). It reads `state.phase`,
  `state.scen`, and calls `derived.stuck()` / `.moving()` / `.settled()`.
- **Two of its emitters have exactly ONE caller — itself**: `barrePipelineHTML` (~12356, 29
  lines) and `dernierPassageHTML` (~12469, 26 lines). They are NOT shared, so they become real
  JSX in the component rather than published emitters. This is the difference from wave 1, where
  every emitter had other callers.
- **`secHTML` (~11669, 8 lines) has EIGHT call sites**, three of them `viewArrivals`' own and
  five inside `viewAcquisition`, which is still legacy. (The recon first said nine: `rg -c`
  counts the DEFINITION line too, and `viewLibrary` — named here at first — never called it. The
  miscount is left recorded rather than quietly fixed, because it is the same one a reader would
  make.) It stays in the fragment and gains an INNER split (`secInner`), the
  same shape as `emptyInner` / `skelCardsInner` / `surfErrInner`: the component draws the
  `<section class="sec">` itself and fills it. Its short-circuit (`count === "0" || inner === ""`
  → no section at all) is the component's to reproduce.
- **`cardHTML` (~11555, 50 lines) is reused VERBATIM**, as `add.tsx` already does: the delegated
  click handlers depend on that markup being byte-exact.
- **`state.pipe` has three values** (`repos`, `encours`, `file`) and two writers — the
  `data-pipe` delegation (`dataset.pipe`, 2 sites). The bar's controls stay the DELEGATION's:
  the component emits `data-pipe="lancer"` / `"arreter"` and writes nothing itself.
- **`PIPELINE` (~10713) is the data**: `etapes`, `dernier` (with `faits`), `declencheurs`. Nine
  references, all read-only. It joins `window.__referentiel` unchanged.
- **Six named states draw the PAGE**: `arr-repos`, `arr-encours`, `arr-file`, `arr-charge`,
  `arr-chargement`, `arr-erreur`. Two more (`arr-resolution`, `arr-decision`) open a SCREEN above
  it and are already React's.
- **R66 (`arrivals.py`, 24 holds)** is the rule that judges this page. R77's `SHELL_OWNED` /
  `LEGACY_OWNED` lists and its residue walk move `arr` from one side to the other.

## Global Constraints

Repeated rather than referenced: a plan that points at another plan for its constraints is a plan
whose constraints nobody reads.

- **Conversion at IDENTICAL markup and behaviour**: same tags, classes, attributes, texts.
  Restore the whitespace text node at every legacy line-break point inside an inline container
  (`{" "}`) — SP4b paid it three times, SP4d wave 1 a fourth, in the save bar.
- **The FIDELITY ORACLE runs BEFORE any renderer is deleted**, once per host:
  `python3 frontend/maquette/fidelity.py viewArrivalsLegacy arr-repos arr-encours …` with the
  renderer temporarily published as `window.__referentiel.viewArrivalsLegacy`, removed with it.
  A page with a second host needs one run per host (wave 1's save bar shipped unproven because
  the oracle only ever read `#view`).
- **Gate of EVERY task that changes what is served**: full suite green (49 scripts), R59
  (`back.py`) / R69 (`url_state.py`) / R71 (`screens.py`) at UNCHANGED rule code.
- **The rule ladder gains this page's identity the SAME wave it moves**: Arrivées' controls are
  delegation-driven (`data-pipe`, `data-go`, and `cardHTML`'s own `data-*`), and R66 drives the
  page through `__go` — never through a tap. The wave that MOVES the emitter owes those
  attributes a hold, driven by a real tap.
- **Measurement ritual** after every source edit, before any harness run:
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
  (`/tmp/tm-refonte/` must also carry the `assets` symlink).
- `command python3`; static server 127.0.0.1:8899; scratch ports 8913/8917/8918 only; **NEVER
  8710/8711/8712**. One measuring process at a time, FOREGROUND.
- `rg` ALWAYS with a glob filter.
- **Persistent-node discipline**: any input or scrollable inside a component is keyed by business
  identity.
- **Publication discipline**: `function` declarations hoist; a `const` declared after the
  `window.__referentiel` site is published as a getter (TDZ).
- **Store conditions bind**: domain hooks are the only door; the legacy `render()` stays
  explicitly called and never subscribed; world mutations notify through `magasin?.toucher()`.
- **The no-French rule is enforced**: every name English on the day it is written, every rendered
  French string EXTRACTED into `design/src/i18n/fr.json` under `screens.arrivals.*` — never
  retyped. A data value or an address that stays French carries a `french-ok: <reason>` pragma.
- Comments English and TIMELESS — a comment naming a wave says nothing to a reader two years
  from now. Commits French Conventional, scope `(shell-mobile)`.

---

### Task 1: The référentiel widens for Arrivées, and `secHTML` gains its inner

**Files:** `refonte.html` (the `window.__referentiel` site), `design/src/data.ts`

- [ ] **Step 1:** `secInner(pip, title, count, inner, note)` extracted from `secHTML`, which keeps
      emitting exactly what it emitted; publish `secInner`, `secHTML`, `cardHTML`, `PIPELINE`,
      `derived` (or the three verbs), `listeFaitsHTML`/`factRowsHTML` (already published).
      TDZ check on every `const`.
- [ ] **Step 2:** Type them in `data.ts` beside the existing contracts.
- [ ] **Step 3:** Full suite. Commit.

### Task 2: `ArrivalsPage`, at identical emission

**Files:** create `design/src/pages/arrivals.tsx`; `fr.json` (`screens.arrivals.*`);
`refonte.html` (`shellOwned` on the `arr` entry, `viewArrivals` deleted once proven)

- [ ] **Step 1:** Strings into `fr.json` by COPY, never retyping.
- [ ] **Step 2:** The component: the note, the pilot's bar (three states, `data-pipe` verbatim),
      the last run's nine steps, the conditional real-data note, the live line, the empty state,
      and the three `sec` sections with `cardHTML` inside — at identical emission.
- [ ] **Step 3:** Fidelity oracle over the six `arr-*` states, byte for byte, BEFORE deleting
      `viewArrivals` / `barrePipelineHTML` / `dernierPassageHTML`. Paste the diff (expected: 0).
- [ ] **Step 4:** R66's 24 holds green at UNCHANGED rule code. Full suite. Commit.

### Task 3: The identity rungs this page never had

**Files:** `harness/page_host.py` (R77), `harness/arrivals.py` (R66), `regions.json`

- [ ] **Step 1:** R77: `arr` moves from `LEGACY_OWNED` to `SHELL_OWNED`; the residue walk keeps
      crossing both worlds on every page it names.
- [ ] **Step 2:** The delegation holds, driven by REAL taps: `data-pipe="lancer"` starts a run
      (and, during one, QUEUES it rather than refusing), `data-pipe="arreter"` stops it, the
      `data-go="acq"` crossref lands on Acquisition, and a stuck card's foot opens the resolution
      screen. Each control looked up before it is tapped.
- [ ] **Step 3:** One mutation per amended rule, pasted. Record the amendments in `regions.json`.
- [ ] **Step 4:** Full suite. Commit.

### Task 4: Wave gate

- [ ] `resync.py`; full suite 49/49 with the hold total recorded and explained if it moved
- [ ] `make check` green (includes `check-frontend` and `scripts/check-no-french.py`)
- [ ] R59/R69/R71 byte-identical against the merge point
- [ ] `IMPLEMENTATION.md` + `docs/superpowers/shell-mobile-wave-log.md` wave record; the
      README's narrative paragraph names the pages the shell owns
- [ ] Adversarial review of the whole branch diff — three lenses, as wave 1: conversion fidelity,
      rule soundness, repository coherence. Wave 1's review found a shipped defect no rule
      covered; it is not a formality.
- [ ] PR, CI green, squash merge, post-merge live check on the design host
