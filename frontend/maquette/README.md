# The maquette — this directory is the visual contract

**Read this before touching anything in `frontend/src` for the `shell-mobile` feature.**

`refonte.html` is the operator-approved interactive prototype of the mobile-first rebuild of
`/acquisition` (third view), `/mediatheque`, `/arrivees` and `/systeme`. It is **not an
illustration**. It is the source the shipped UI is derived from, and the reference every
measurement compares against.

Design spec: `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md` — §7 is
the parity methodology and is the part that matters most.

---

## Why this file exists at all

The previous rebuild (`acq-mobile`, PRs #422 / #423) cost days it should not have. Its own
post-mortem names the two causes:

1. **Translating instead of transplanting.** Maquette fragments were grafted onto existing
   component skeletons. Every detail _resembled_; the whole diverged. The operator's words:
   « j'ai demandé un chat, j'ai eu un chien ».
2. **Eyeball validation.** « Present in the DOM » was treated as « conform ». Several « c'est
   prêt » claims collapsed on contact with the operator.

Underneath both: the parity harness was built **after** the code, as a repair, and it measured a
**deployed** build — so every loop cost minutes and measuring became something to skip.

This directory inverts that. The maquette comes first, the CSS is generated from it, and the
measurement runs locally on every commit.

---

## The four rules

### 1. The maquette is the source. Change it FIRST.

If a region cannot be built as drawn, **amend `refonte.html`**, record why, then follow with the
code. The code never diverges "temporarily" — a temporary divergence is how the previous
rebuild ended up with a monster.

### 2. The CSS is generated, never retyped.

`scripts/extract-maquette-css.py` lifts this file's app CSS block, scopes it under `.tm`, and
writes `frontend/src/styles/ps/app-surface.css`.

- **Editing the generated file by hand is the defect**, not a shortcut.
- `make check` re-runs the extraction and fails on drift — the same guard that protects
  `openapi.json` / `schema.d.ts`.
- To change a pixel, you change the maquette.

The `<style>` element is physically split into two commented blocks:

- **BLOC 1 — HARNAIS DU PROTOTYPE**: the phone frame (`.stage`, `.device`), the demo top and
  bottom bars, the design-note callouts (`.note`), the scenario switch. **Never exported.**
- **BLOC 2 — CSS DE L'APPLICATION**: everything that ships.

Extraction works from an **allowlist** of selectors declared in `regions.json`, never a
blocklist — a new prototype-only helper can therefore never silently reach production.

### 3. The DOM is a contract, checked offline.

Per region, a vitest test renders the component with the shared fixture and asserts that the
emitted **tag chain + class chain** equals the maquette's. jsdom, milliseconds, no browser. This
catches « translating » at the moment it happens.

### 4. Zero divergence is a build condition, not a ticket.

`scripts/parity-probe.py` walks `regions.json` in two headless contexts — the maquette and a
local `vite preview` build — at 390 × 844 / DPR 2 / mobile / touch, and diffs
`getBoundingClientRect` plus a fixed `getComputedStyle` subset. The allowlist is explicit and
**every entry carries an inline justification**. Wired into `make check` and CI.

The probe is **append-only over regions**: each pass re-runs everything already at zero. This
mission has already produced the defect that rule exists for — after a change to one view, only
that view was checked, and another page shipped blank.

---

## Every state has a name, and knows how to reach itself

`window.__go("<id>")` drives the prototype into a state **without clicking**. `window.__states()`
returns the 37 ids. The **≡** button in the harness opens a panel listing them all.

This is what makes the parity probe deterministic. Without it, measuring « the blocked card »
requires knowing how to make one appear — and that knowledge is exactly what evaporates between
two sessions. With it, the probe iterates `regions.json` → for each region, the states it is
visible in → `__go(state)` → measure.

Three orthogonal dials the panel exposes:

| Dial | Values | What it changes |
|---|---|---|
| Data scenario | `reel` · `charge` | real system state of 2026-08-10 vs a dense one |
| Surface phase | `prete` · `chargement` · `erreur` | every surface goes through all three |
| TMDB account | connected · not | Découvrir's full vs degraded mode |

The 37 states cover: the five urgency sections in both scenarios, Suivis in its three modes plus
its two empty cases (filter with no match, « En pause » with none), Découvrir full / degraded /
exhausted / loading, the add screen idle and with real results, the follow sheet on a
22-season complete catalogue and on a holed one, the journey sheet, the « ⋮ » sheet, the library
in grid and list, its empty search, its three lenses, selection mode, single and bulk delete
dialogs, loading and error on every surface, the resolution screen, the media sheet, and Système.

`harness/states.py` drives all 37 and asserts each one renders content, has no horizontal
overflow and raises no JS error. **A state that renders nothing fails the pass.**

## `regions.json` — the extraction contract and the measurement map

One file, three jobs:

- **`exportedSelectors`** (264) — the allowlist `extract-maquette-css.py` exports. Anything not
  listed is not exported.
- **`harnessSelectors`** (26) — the prototype's own chrome, listed so its exclusion is explicit
  rather than implied.
- **`regions`** (36) — what `parity-probe.py` measures, each naming the states it is visible in,
  so the probe never has to guess how to reach a card state.

It also carries the probe's emulation settings, the `computedStyle` subset to diff, and the
(currently empty) allowlist of accepted divergences — **every future entry must carry an inline
justification.**

## What is real in here, and what is not

Real, read from the live system on 2026-08-10:

| Data                                                                                     | Source                                                                       |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| 260 library titles, categories, counts (1 861 items, 8,4 To)                             | `library.db`                                                                 |
| 12 follows with their true states (4 films waiting, 8 series up to date)                 | `acquire.db`                                                                 |
| Incomplete series and their fractions (SAV des émissions 12/71, Les Animaniacs 117/175…) | `library.db`                                                                 |
| Staging contents (Top Chef Le Concours Parallèle, the Mephisto game)                     | `/Volumes/IznoServer SSD/A TRIER`                                            |
| 150 TMDB suggestions                                                                     | the engine, actually executed: 16 seeds → 32 calls → 640 raw → 503 survivors |
| 46 posters                                                                               | TMDB / TVDB, re-encoded WebP 154 px                                          |
| The grab cadence `20 3,15 * * *`                                                         | the live PM2 scheduler                                                       |

Not real: timings and counts in the « charge » scenario, which exist so density can be judged.
They are labelled as such in the design notes.

**Two scenarios**, switched from the harness (the **≡** button):

- **`reel`** (default) — the exact state of the system on 2026-08-10. Calm: nothing to grab,
  nothing in flight, two stuck folders. This is what makes the **rest states** judgeable; a
  prototype that is always busy never shows them.
- **`charge`** — a dense state, for judging density and scrolling.

---

## Known defects deliberately left visible

- **The search cadence is rendered raw**: `Recherche automatique : 20 3,15 * * *`. A cron
  expression on a phone card is raw jargon (**NE-DOIT-PAS-4**). It must become « twice a day, at
  3:20 and 15:20 ». Left uncorrected on purpose so the operator sees the defect rather than the
  fix.

## Two rules the maquette itself re-taught, the hard way

- **R7 — `minmax(0, 1fr)`, never `1fr`.** An `auto` grid track's floor is the item's _intrinsic_
  size, so the horizontally-scrolling pill train sized `.stage`'s track to its max-content and
  blew the 390 px frame out to 910 px.
- **R8 — an author `display` rule beats `[hidden]`.** `.fab` declares `display: grid`, so
  `el.hidden = true` did nothing and the « + » stayed visible on pages that must not have it.
  Any class declaring a `display` must declare its own hidden case.

## And one trap that no synthetic test can catch

Swipe gestures **must claim the horizontal axis** with `touch-action: pan-y` on the row itself
(never on an ancestor — `touch-action` intersects down the whole chain). A passive listener that
claims nothing lets the browser take the gesture and fire `touchcancel`: the swipe then works
**only under synthetic events**, which are never cancelled. This exact divergence happened here —
the code was present, the test was green, and the operator's thumb found nothing.

**Every gesture claim requires `TouchEvent`s dispatched on the real surface.** Never
`PointerEvent`s, never a shortcut around the listener under test.

---

## `harness/` — the probe's working prototype

Throwaway scripts that already do, in headless Chromium, what phase 0 must promote into
`scripts/parity-probe.py`. They are committed because they encode recipes that cost time to get
right, not because they are production tooling:

| Script      | What it proves                                                                                                                         |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `sweep.py`  | renders all 8 views, asserts content, no horizontal overflow, device at 390 px, no JS error. **A view that renders nothing fails.**    |
| `scen.py`   | the same sweep across both data scenarios, with explicit sub-view reset between runs                                                   |
| `inter.py`  | the interaction pass: swipe, infinite scroll, load error + retry, delete dialog                                                        |
| `suivis.py` | Suivis conformity: three modes, chip dot geometry, chip hidden in a homogeneous group and kept in a heterogeneous one, film vocabulary |
| `sel.py`    | the two delete paths from the grid: long-press and selection mode                                                                      |

Run them with the pyenv Python that carries Playwright
(`~/.pyenv/versions/3.11.9/bin/python3`), against a local static server on **127.0.0.1:8899** —
**never** 8710 / 8711, which Caddy routes to prod and staging.

The maquette must be served inside a wrapper supplying `<meta name="viewport">`; without it
Chrome falls back to the legacy 980 px layout viewport and every measurement is wrong. The file
also injects that meta itself if the host page has none — do not remove that guard.
