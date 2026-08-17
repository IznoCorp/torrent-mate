# SP4d wave 4 — Acquisition, and the last two legacy pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The last page wave. `viewAcquisition` (290 lines, three tabs, a deck, a second infinite
scroll) becomes a final component — and with it the two small pages nobody counted, `viewProfil`
(48 lines, « Profil et préférences », off-bar) and `viewIntrouvable` (10 lines, the unknown
address). When this wave lands, **`PAGES_OF()` has no `render` left at all**, which is the
condition SP4-end starts from.

**Tech Stack:** React 19, @tanstack/react-router ^1.170, @tanstack/store ^0.11, Vite 8,
Playwright harness (`command python3` = 3.12.4, chromium `channel="chrome"`).

**Spec:** `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`
(§The waves — "… arr, lib, acq; the **drawer** migrates with its last consumer").

**Recon:** measured 2026-08-18 on `feat/maquette-sp4d3`. Line numbers are anchor HINTS.

## What the recon settled

- **`viewAcquisition` is 290 lines** (`refonte.html` ~11973-12262) — by far the largest renderer
  left. It reads `state.acqTab`, `phase`, `pill`, `filtre`, `followMode`, `sugMode`, `tmdb`, and
  emits `data-acqtab`, `data-pill`, `data-fmode`, `data-sugmode`, `data-tmdb`, `data-sheet`,
  `data-clearq`, `data-swipeact`, `data-go`.
- **Three tabs, and they are three different surfaces**: « En cours » (five derived lists),
  « Suivis » (the follows, with a filter field `#follq` and two display modes), « Découvrir »
  (the suggestion deck AND a list mode, with its own infinite scroll).
- **The second infinite scroll comes with it**: `fillSug` (17), `sugFoot` (17) and `sugObserver`
  are what remains of `mountLoaders` after the library took its half. The deck's own machinery —
  `refreshDeck` (6), `avancerDeck` (48), `sugCardHTML` (16) — moves too.
- **`#follq` is the last field `mountSearch` binds.** When it moves, `mountSearch` has nothing
  left and retires — the same path `.fieldinput` and `#libq` already took.
- **`viewProfil` (~12552, 48 lines)** is the « Profil et préférences » PAGE, off-bar, reached from
  the user sheet. It is NOT `/profil/$titre`, the quality-profile SCREEN that migrated in SP4a.
- **`viewIntrouvable` (~12531, 10 lines)** draws the unknown-address page and is one of the two
  remaining openers of the DRAWER (the other is the topbar burger, static app shell).
- **The DRAWER**: this wave is not automatically its last consumer — the burger is in the static
  app shell, not in a page. Measure before deciding; the spec says the drawer migrates with its
  last consumer, and if the burger still opens it, it stays for SP4-end.
- **Rules that read these pages**: `arrivals.py` (the `data-go` crossref lands here), `deck.py`,
  `mouse.py`, `touch.py`, `follows.py`, `filters.py`, `selection.py`, `audit2.py`, `dest.py`,
  `scen.py`, plus the gate rules `back.py` (R59) and `url_state.py` (R69) at UNCHANGED code.

## Global Constraints

Repeated rather than referenced.

- **Conversion at IDENTICAL markup and behaviour.** No evolution rides along this wave.
- **The FIDELITY ORACLE runs BEFORE any renderer is deleted**, and by RECORDING where the drawing
  is not what the renderer returned (the suggestions' list is filled after the fact, like the
  library's was): `fidelity.py --record` with the legacy owning the page, then `--against`.
- **Gate of EVERY task that changes what is served**: full suite green (50 scripts), R59 / R69 /
  R71 at UNCHANGED rule code.
- **Two worlds never write one container**: when the component owns `#sugitems`, nothing in the
  fragment may write it. `mountLoaders` empties out entirely.
- **Persistent-node discipline**: `#follq` keyed by business identity, its handler moving with the
  field; the deck's cards are NOT rebuilt on every render (`avancerDeck`'s own comment says a
  replaced node cannot animate — that constraint survives the move).
- **Measurement ritual** after every source edit, before any harness run:
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
- `command python3`; static server 127.0.0.1:8899; scratch ports 8913/8917/8918 only; **NEVER
  8710/8711/8712**. One measuring process at a time, FOREGROUND.
- `rg` ALWAYS with a glob filter.
- **The no-French rule is enforced**: names English on the day they are written, rendered French
  in `design/src/i18n/fr.json` under `screens.acquisition.*` / `screens.profile.*` /
  `screens.notFound.*`, copied never retyped; French data or addresses carry a `french-ok:`
  pragma. Comments English and TIMELESS.
- Commits French Conventional, scope `(shell-mobile)`.

---

### Task 1: The référentiel widens for Acquisition

- [ ] Publish what the three tabs draw with and the verbs they call; TDZ check on every `const`
      (two have already bitten: `LIB_PAGE` and `TRIS`).
- [ ] Type them in `data.ts`. Full suite. Commit.

### Task 2: `AcquisitionPage` — the three tabs, at identical emission

- [ ] Strings into `fr.json` by COPY.
- [ ] The component, tab by tab, `#sugitems` and `#sugload` left as the fragment's for this step
      ONLY if that seam is not written while React owns it — otherwise both move together.
- [ ] Record the legacy's drawn page over every `acq-*` state, flip `shellOwned`, compare: 0
      divergences.
- [ ] Full suite. Commit.

### Task 3: The suggestion machinery — WHAT MOVES, AND WHAT DOES NOT

**Measured before deciding** (2026-08-18): `avancerDeck` mutates the deck's own DOM in place —
it inserts a card at the back, decrements every `data-depth`, writes an inline transform on the
outgoing one and removes it 440 ms later, and only rebuilds the pile when it empties. Its own
comment says why: « a replaced node cannot animate ». React owning that markup would restore the
string it last rendered on the next repaint and undo all of it, so converting the deck means
REWRITING the gesture — a behaviour change, in the half four rules measure (R55 `touch.py`, R64
`drag.py`, `deck.py`, `mouse.py`).

So the page's MARKUP migrates and the suggestion machinery does not, and the seam is named rather
than left to be discovered: the component draws `#sugitems`, `#sugload` and `.deckbody` as
containers it never fills, and the fragment keeps filling them exactly as it does today. React
manages zero children there, so neither world removes the other's nodes — the arrangement
`paintSelBar` already has, one level down.

- [ ] **Step 1:** The three containers are drawn by the component and filled by the fragment;
      `mountLoaders` keeps its suggestions half.
- [ ] **Step 2:** A HOLD for the seam: the containers exist, the fragment fills them, and React
      never empties them across a re-render. Mutation: make the component render a child into one
      of them and the hold must fall.
- [ ] **Step 3:** R55, R64, `deck.py` and `mouse.py` green at unchanged rule code. Full suite.
      Commit.

**What this leaves for SP4-end**: the machinery moves to `src/` as an IMPERATIVE module — final
code that mounts and steps aside — rather than as JSX. An imperative gesture engine is final
code; what must die is the fragment as an editing source, not the technique.

### Task 4: `#follq` moves with its field, and `mountSearch` retires

- [ ] The component owns the filter field's handler; `mountSearch` is deleted once it binds
      nothing.
- [ ] Typing really filters, the caret does not jump. Full suite. Commit.

### Task 5: The last two pages, and the drawer's question

- [ ] `ProfilePage` and `NotFoundPage` — 58 lines between them — at identical emission, proven by
      recording.
- [ ] MEASURE the drawer's openers: if `viewIntrouvable` was the last one in a PAGE and the topbar
      burger is the only remaining, the drawer stays for SP4-end. Record the answer either way.
- [ ] `PAGES_OF()` has no `render` left. Full suite. Commit.

### Task 6: The identity rungs

- [ ] R77: `acq`, `profil` and `404` join the shell-owned list; `LEGACY_OWNED` empties, and the
      hold that reads it must say something true when it does.
- [ ] The delegation attributes of these pages gain tap-driven holds.
- [ ] One mutation per amended rule, pasted. Record in `regions.json`. Full suite. Commit.

### Task 7: Wave gate

- [ ] `resync.py`; full suite with the hold total recorded and explained
- [ ] `make check` green; R59/R69/R71 byte-identical against the merge point
- [ ] `IMPLEMENTATION.md` + wave log + README
- [ ] Adversarial review of the whole branch diff — three lenses. Every wave's review has found a
      real defect so far.
- [ ] PR, CI green, squash merge, post-merge live check on the design host
