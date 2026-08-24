# L06 — The scale

**Lot contract**: `docs/reference/frontend-architecture.md` § « L06 — The scale », Phase 2.
**Branch**: `feat/maquette-l06` · **version**: 0.98.28 → 0.98.29 · squash merge after green CI
and a clean final adversarial review.

## § 1 — What this lot is, measured on the day it opened

One declared scale — space, type, radius, duration, easing — and every declaration folded onto
it. The disorder, re-measured at `5312c57b` (the architecture file's figures had already grown):

| family                               | distinct values today | target          |
| ------------------------------------ | --------------------- | --------------- |
| `padding`                            | **66**                | ~8 steps        |
| `font-size`                          | **21**                | ~7              |
| `border-radius`                      | **18**                | ~5              |
| `gap`                                | **18**                | the space scale |
| durations (`transition`/`animation`) | **11**                | ~3 + 2 easings  |

<sub>`cd frontend/maquette/design && grep -oE "padding:[^;]+;" refonte.html | sort -u | wc -l` — same
shape per property.</sub>

Two inheritances from L03, both binding on this lot (architecture § L06):

- **42 `color-contrast` findings** over 18 of the 83 named states, on 10 distinct elements —
  27 of the 42 are the count badge `.c` inside category and filter chips; the rest are the
  danger button's tone and the bold lead of the two error surfaces.
  <sub>`python3 -c "import json;print(json.load(open('frontend/maquette/a11y-contrast.json'))['counts'])"`</sub>
- **`.search input` is 13 px** (`refonte.html:549`) — under the 16 px threshold at which iOS
  zooms a focused field, live since L03 rightly removed `maximum-scale=1`.

And one decision this lot must take so L13 is not caught by it: the `--tm-*` runtime family.
Measured: it is ONE token, `--tm-bottom-bar-h` — 8 `var()` uses in the stylesheet, every one
carrying its fallback, published at runtime by `legacy.js` (~11770), which measures the real
bottom-bar height. The engine dies at L13; this value needs a home before then.

## § 2 — Decisions (proposed by the wave; the operator's to overturn — none is implemented

before this design is committed on the branch, and every one is named in the PR)

- **D-L06-1 — Where the scale lives, before Tailwind.** The scale is declared as CSS custom
  properties in ONE `:root` block at the top of BLOCK 2 of `refonte.html` — the file § 15 names
  as the visual reference. D3's `tokens.css` file layout belongs to L07's conversion; moving
  files now would be a second conversion for no proof. When L07 lands, the block lifts into
  `@theme` wholesale.
- **D-L06-2 — The steps are derived from the histogram, then arbitrated, never averaged.**
  Phase 1 measures the real value distribution per family and proposes the steps (space also
  serves `gap` and the `margin` values); a derivation must not read back its own output
  (architecture § 6's named trap). The chosen steps are written in the plan with the histogram
  beside them.
- **D-L06-3 — The ratchet, not a flag day.** A new guard arm (extending
  `scripts/check-css-tokens.py`, which already reads BLOCK 2 — never a second script beside it)
  counts declarations outside the scale per family and refuses the count going UP, against a
  baseline recorded in phase 1; the folding phases drive it to zero; the last phase drops the
  baseline and the arm refuses the next off-scale declaration outright. Mutation-tested at each
  state.
- **D-L06-4 — `--tm-bottom-bar-h` stays a runtime value, published by the SHELL.** It is a
  genuinely measured quantity (the drawn bar's height including safe areas), not a design
  constant — folding it into the scale would replace a measurement with a hope. What moves is
  the publisher: the measuring/publishing code leaves the engine for the shell
  (`design/src/app/`), so L13 has nothing to inherit. Every `var()` keeps its fallback;
  `check-css-tokens.py` keeps holding that.
- **D-L06-5 — The contrast repairs are palette decisions, taken here.** The 10 elements move to
  ≥ 4.5:1 (3:1 where axe's large-text rule applies), starting from the badge that carries 27 of
  the 42. Once `a11y.py`'s contrast run reads empty, `color-contrast` joins the enforced
  hard-zero set — an empty debt left unenforced is how it comes back.
- **D-L06-6 — All three field sizes reach 16 px, not only the search.** The lot's contract
  names `.search input` (13 px); `.fieldinput` (14 px) and `.fieldinput.mono` (12 px) are the
  same iOS zoom defect one tap away, and the type scale is being folded anyway — leaving two
  sub-16 field sizes in a 7-size scale would grandfather the defect into the new scale. This
  WIDENS the lot's letter; it is flagged for the operator precisely because of that.

## § 3 — What the oracle will say, and how it is answered

Unlike L04/L05, this lot's whole point is that pixels MOVE. Every folding step and every
contrast repair produces oracle divergences, and the method is the one the architecture § 5
prescribes: each phase's divergences are reviewed one by one, accepted with their reason
written, and the reference is re-recorded per phase ON THE BRANCH (the post-merge re-record
from `main`'s tip still closes the wave). A divergence nobody expected fails the phase — the
scale must explain every moved rectangle.

## § 4 — Phases (the plan owns the detail)

1. **The measurement, the scale, the ratchet** — histograms per family; the `:root` block
   declaring the chosen steps (used by nothing yet); the guard arm with its baseline; zero
   visual change, oracle 0 divergence.
2. **Space folds** — paddings, gaps, margins onto the scale, surface by surface; ratchet down;
   divergences reviewed per step.
3. **Type folds** — 21 sizes onto ~7; the three field sizes reach 16 px (D-L06-6); iOS-zoom
   probe on the served copy.
4. **Radius, duration, easing fold** — and `--tm-bottom-bar-h` moves publisher (D-L06-4).
5. **The palette pays its debt** — the 42 contrast findings to zero; `color-contrast` enters
   the enforced floor (D-L06-5).
6. **The ratchet dies, the gate closes** — baseline dropped, the arm refuses outright; full
   suite, a11y, oracle re-recorded; every accepted divergence listed in the PR.

## § 5 — Out of scope, named

Tailwind/CVA (L07); any markup or behaviour change beyond the publisher move of D-L06-4; the
`page_host.py`/`oracle.py` module-size WARNs; B-036/B-040/B-041/B-042; the live-DB rule class
(open point since #484).
