# SP4d wave 3 — Médiathèque, and E-001 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The third page wave, and the hardest of the four: `viewLibrary` is 96 lines but it is
the only page whose CONTENT is written by the fragment AFTER the page is drawn — an infinite
scroll that replaces `#libitems` wholesale (`box.outerHTML = …`) as the operator scrolls. Two
worlds writing one container is what tore the React root down in wave 1, so this wave moves the
list AND its loading into the component rather than leaving a seam there.

It also carries **E-001** (`BUGS.md`), the operator's evolution: every sort type must be
reversible. E-001 is **maquette-first** — drawn and measured in the PROTOTYPE, with its own
holds, BEFORE the conversion touches the page. That order is not a preference: a conversion is
judged by « identical markup », and an evolution changes the markup, so doing both at once would
leave neither provable.

**Tech Stack:** React 19, @tanstack/react-router ^1.170, @tanstack/store ^0.11, Vite 8,
Playwright harness (`command python3` = 3.12.4, chromium `channel="chrome"`).

**Spec:** `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`
(§The waves). **Evolution:** `BUGS.md` §E-001, arbitrated by the operator 2026-08-15 into this
wave.

**Recon:** measured 2026-08-17 on `main` = `aeac77cb` (v0.97.19, SP4d wave 2). Every line number
is an anchor HINT — re-grep the SYMBOL before editing.

## What the recon settled

- **`viewLibrary` is 96 lines** (`refonte.html` ~12263-12358): three lenses (`cat`, `rec`,
  `inc`), two modes (`list`, `grid`), a search field, a category pill bar, a count line, a
  selection entry, the sort control, and — for two of the three lenses — an EMPTY `#libitems`
  the fragment fills afterwards.
- **The loading machinery is six functions**: `fillLib` (41), `libFoot` (32), `loadMoreLib` (24),
  `paintLibCount` (13), `libFiltered` (17), `trierLib` (18). `fillLib` writes `box.outerHTML`,
  i.e. it REPLACES the element — which React cannot share. All of `libFiltered`'s five callers
  are inside that machinery, so the whole cluster moves together.
- **`mountLoaders` (~15559) drives both the library and the suggestions**; only the library half
  moves. `libObserver` becomes a React effect; `sugObserver` stays until wave 4.
- **`mountSearch` (~15528) binds `#libq`'s `oninput` and re-focuses it after `render()`** — the
  focus dance exists because the legacy replaced the input on every render. React keeps the node,
  so the handler moves into the component and `mountSearch`'s `#libq` half retires. The precedent
  is written in `mountSearch`'s own comment: `.fieldinput` stopped being bound there when the
  panel took it, « binding it from outside would put two writers on one field ».
- **Eight delegation attributes**: `data-lens`, `data-cat`, `data-lmode`, `data-sort`,
  `data-settri`, `data-selmode`, `data-del`, `data-clearq`. None is asserted by a tap today.
- **Eleven rule scripts read this page** — `audit.py`, `audit2.py`, `back.py`, `bridge.py`,
  `cards.py`, `content.py`, `filters.py`, `gallery.py`, `inter.py`, `scroll.py`, `url_state.py`.
  Two of them are gate rules that must stay at UNCHANGED code: `back.py` (R59) and `url_state.py`
  (R69).
- **NOTHING measures sorting today.** `TRIS` (~14664) holds three one-way sorts; `trierLib`
  applies them; the panel lists them. E-001 therefore ships with the first holds this behaviour
  has ever had.

## E-001 — the ruling, and what it is contested against

**Every sort is offered in BOTH directions, as six explicit actions in the sort panel**, the
current one marked exactly as the current sort is marked today. The button on the count line
reads the chosen direction's own name.

| Sort | One way | The other |
| --- | --- | --- |
| `recent` | Ajout récent | Ajout ancien |
| `az` | A → Z | Z → A |
| `manque` | Les plus incomplets | Les plus complets |

**The alternative, and why it is not taken**: tapping the ALREADY-SELECTED sort to flip it. It is
half the rows, and it is invisible — nothing on a phone tells the operator that a second tap on
the row they already chose does something different. §1 of the constitution asks that the
operator see what the machine will do; a row that reads « A → Z » and does Z → A when tapped
twice is the opposite. **This ruling is open to contest**, and reversing it costs one component
and one rule.

**The state**: `state.tri` keeps naming the sort; a new `state.triSens` carries the direction
(`"desc"` default, `"asc"` reversed). Neither enters the URL — the panel's own note already says
so (« Le tri est une préférence, pas un emplacement… (A7) ») and R69 must stay unchanged.

## Global Constraints

Repeated rather than referenced.

- **Conversion at IDENTICAL markup and behaviour** — E-001 is the ONE exception, drawn first and
  separately, so that everything after it is again judged by identity.
- **The FIDELITY ORACLE runs BEFORE any renderer is deleted**, once per host, against the
  post-E-001 legacy (`fidelity.py viewLibraryLegacy lib-… --host '#view'`).
- **Gate of EVERY task that changes what is served**: full suite green (49 scripts), R59
  (`back.py`) / R69 (`url_state.py`) / R71 (`screens.py`) at UNCHANGED rule code.
- **Two worlds never write one container.** The list, its footer and its observer move together;
  when the component owns `#libitems`, nothing in the fragment may write it. Wave 1 paid for this
  with a torn-down React root, and R77's round-trip hold is what caught it.
- **Persistent-node discipline**: `#libq` is keyed by business identity, the scroll position is
  kept where the legacy kept it, and the caret is not stolen — the legacy's focus dance exists
  only because it rebuilt the node.
- **Measurement ritual** after every source edit, before any harness run:
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
- `command python3`; static server 127.0.0.1:8899; scratch ports 8913/8917/8918 only; **NEVER
  8710/8711/8712**. One measuring process at a time, FOREGROUND.
- `rg` ALWAYS with a glob filter.
- **Store conditions bind**: domain hooks are the only door; the legacy `render()` stays
  explicitly called and never subscribed; a page-state write goes through the store — R77 holds
  that no rule drives a page by mutating the alias.
- **The no-French rule is enforced**: names English on the day they are written, rendered French
  in `design/src/i18n/fr.json` under `screens.library.*`, copied never retyped; French data or
  addresses carry a `french-ok: <reason>` pragma.
- Comments English and TIMELESS. Commits French Conventional, scope `(shell-mobile)`.

---

### Task 1: E-001 in the maquette, with the holds it never had

**Files:** `refonte.html` (`TRIS`, `trierLib`, the sort panel, the count-line button),
`harness/library_sort.py` (NEW rule), `regions.json`, `frontend/maquette/README.md`, `BUGS.md`

- [ ] **Step 1:** `TRIS` becomes six entries (three sorts × two directions) or three sorts plus a
      direction table — whichever emits the six labels above without duplicating a name.
      `state.triSens` joins the store's initial state.
- [ ] **Step 2:** `trierLib` honours the direction for all three sorts, `recent` included (its
      « natural » order is the source's, so reversing it is `.reverse()`, not a comparator).
- [ ] **Step 3:** The panel lists six actions, the current one marked; the count-line button
      reads the current direction's name.
- [ ] **Step 4:** NEW RULE (`harness/library_sort.py`): every sort is reachable in both
      directions from the panel; each one really REVERSES the list (first and last swap, measured
      on the rendered rows, not on the data); the current one is marked; the sort never enters the
      URL. MUTATION: make one direction fall through to the other and the hold must fall, naming
      it.
- [ ] **Step 5:** Full suite. Record the rule in `regions.json` and the README table; close E-001
      in `BUGS.md` with the rule and the mutation named. Commit.

### Task 2: The référentiel widens for the library

**Files:** `refonte.html` (the `window.__referentiel` site), `design/src/data.ts`

- [ ] **Step 1:** Publish what the page draws with — `tileHTML`, `libRowHTML`, `swipeHTML`,
      `CATS`, `INCOMPLETE`, `RECENT`, `SYNOPSIS`, `LIB_PAGE`, `TRIS`, and the world's `lib` —
      plus the verbs the component will need while the loading still lives in the fragment.
      TDZ check on every `const`.
- [ ] **Step 2:** Type them in `data.ts`. Commit.

### Task 3: `LibraryPage` — the page's own markup

**Files:** create `design/src/pages/library.tsx`; `fr.json` (`screens.library.*`);
`refonte.html` (`shellOwned` on the `lib` entry once proven)

- [ ] **Step 1:** Strings into `fr.json` by COPY.
- [ ] **Step 2:** The component: the three lenses, the search field, the pill bar, the view
      switch, the count line with its selection and sort controls, and the three lens bodies — at
      identical emission, `#libitems` and `#libload` included as EMPTY nodes the fragment still
      fills at this step.
- [ ] **Step 3:** Fidelity oracle over every `lib-*` state. Paste the diff (expected: 0).
- [ ] **Step 4:** Full suite. Commit.

### Task 4: The list and its loading move too

**Files:** `design/src/pages/library.tsx`, `refonte.html` (delete `fillLib`, `libFoot`,
`loadMoreLib`, `paintLibCount`, and the library half of `mountLoaders`)

- [ ] **Step 1:** The component owns `#libitems` and `#libload`: the rows, the skeleton, the
      error surface, the empty surface, the end mark, the retry, and the IntersectionObserver as
      an effect. `libCount` / `libLoading` / `libErr` / `libFailedOnce` stay STORE fields.
- [ ] **Step 2:** Prove the seam is closed: nothing in the fragment writes `#libitems` or
      `#libload` any more (source grep, pasted), and the round trip through the page leaves the
      shell alive (R77's hold, which exists for exactly this).
- [ ] **Step 3:** Scroll and count measured against the legacy's own numbers: `scroll.py`,
      `filters.py`, `content.py`, `cards.py`, `gallery.py` green at unchanged rule code.
- [ ] **Step 4:** Full suite. Commit.

### Task 5: The search field's handler moves with the field

**Files:** `design/src/pages/library.tsx`, `refonte.html` (`mountSearch` loses its `#libq` half)

- [ ] **Step 1:** The component owns `#libq`'s `oninput`, keyed by business identity, without the
      focus dance the legacy needed.
- [ ] **Step 2:** Typing really filters, the caret does not jump, and the clear button still
      clears — measured with real typing, not a programmatic write.
- [ ] **Step 3:** Full suite. Commit.

### Task 6: The identity rungs this page never had

**Files:** `harness/page_host.py` (R77), `regions.json`

- [ ] **Step 1:** `lib` moves from `LEGACY_OWNED` to `SHELL_OWNED`; the residue walk keeps
      crossing both worlds on every page it names.
- [ ] **Step 2:** The eight delegation attributes gain tap-driven holds — lens, category, mode,
      sort, direction, selection, deletion, clear — each control looked up before it is tapped,
      each hold comparing the tapped row's own value against what happened.
- [ ] **Step 3:** One mutation per amended rule, pasted. Record in `regions.json`. Full suite.
      Commit.

### Task 7: Wave gate

- [ ] `resync.py`; full suite 49/49 with the hold total recorded and explained
- [ ] `make check` green (includes `check-frontend` and `scripts/check-no-french.py`)
- [ ] R59/R69/R71 byte-identical against the merge point
- [ ] `IMPLEMENTATION.md` + `docs/superpowers/shell-mobile-wave-log.md` wave record; README
      narrative and rule table; `BUGS.md` closes E-001
- [ ] Adversarial review of the whole branch diff — three lenses (conversion fidelity, rule
      soundness, repository coherence). Both previous waves' reviews found real defects; it is
      not a formality.
- [ ] PR, CI green, squash merge, post-merge live check on the design host
