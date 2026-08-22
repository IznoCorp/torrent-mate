# Phase 2 — Landmarks and structure

## Gate

Produced by Phase 1:

- `frontend/maquette/a11y.py` exists with `--record`, `--check` and `--rules`.
- `frontend/maquette/harness/run.sh --a11y` runs, and the CI job carries its step.
- `a11y-debt.json` and `a11y-contrast.json` are committed — the starting line.
- `hold-counts-baseline.json` names a commit that is an ancestor of `HEAD`, and `--compare`
  refuses one that is not.

## What this phase does

Gives the document an outline an assistive technology can navigate, **by substituting the tag of
an element that already exists — never by adding a box** (DESIGN § D-L03-3). That rule is what
makes « the rendering did not move » achievable rather than aspirational: `<main>` and `<div>`
are both `display: block`, so the oracle sees nothing; a new wrapper is a new box and a layout
risk.

Measured starting point: **0 `<main>`, 2 `<nav>`, 13 `role=` lines, 1 `<h1>` for 26 `<h2>`.**

## Sub-phases

### 2.1 — The main landmark and the skip link

`<div id="port">` becomes `<main id="port">` in `design/index.html`. `#port` is the scrolling
viewport that holds `#view`; it is the element a « skip to content » link must land on, and it
already exists, so no box is added.

Add the skip link as the first focusable element of the frame. It is visually hidden until
focused — a pattern the stylesheet must carry, and one the oracle does not see because an
element that is not focused is not styled by `:focus-visible`.

Commit: `feat(maquette-l03): the viewport is the main landmark, and a skip link reaches it`

### 2.2 — Region roles and accessible names on what already exists

`header.topbar`, `nav.bottombar`, `aside.drawer` are already the right elements. What they lack
is disambiguation: two elements currently carry `aria-label="Navigation principale"` — the tab
bar and the drawer — which makes the two landmarks indistinguishable to a screen reader's
landmark list. Give each the name of what it actually is.

Name the remaining regions that carry none, using the labels the interface itself uses so the
spoken name and the visible name agree.

Commit: `feat(maquette-l03): every landmark says which one it is`

### 2.3 — The heading outline

One `<h1>` per screen, `<h2>` beneath it, no level skipped. Today there is a single `<h1>` in the
whole prototype — the login screen's « Connexion » — and 26 `<h2>` that hang under nothing.

Substitution again: a page title already rendered as `<h2>` or as a styled `<div>` becomes the
screen's `<h1>`, and the stylesheet is amended so the two render identically. This is the
sub-phase most likely to move a rectangle, and the oracle arbitrates each one.

Commit: `feat(maquette-l03): every screen has one heading at the top of its outline`

### 2.4 — `aria-current` and the document title

The active tab in `nav.bottombar` carries `aria-current="page"`. The document title follows the
route, so a screen reader announces where a navigation landed instead of repeating
« TorrentMate Design ».

The tab bar is drawn by the engine (`legacy.js`, `nav.innerHTML = PAGES_OF()…`), so the attribute
is placed there. That is the attribute half of D-L03-1 — the mechanism does not go into the
engine, the attribute does.

Commit: `feat(maquette-l03): the active tab and the document title say where you are`

## Verification

| ID | Command | Expected |
| --- | --- | --- |
| ACC-06 | `grep -rEc '<main([ >/]\|$)' frontend/maquette/design/index.html` | `1` |
| ACC-07 | `python3 frontend/maquette/oracle.py --check` | 0 divergence |
| — | `python3 frontend/maquette/a11y.py --check --rules landmark-one-main,page-has-heading-one,heading-order,landmark-unique` | 0 violations over 83 states |
| — | `frontend/maquette/harness/run.sh --contracts` | 5 rules, no violation |

**On an oracle divergence**: neutralise it in the stylesheet until the oracle is green, or drop
that substitution. **Never `--accept`.** That mode ratifies a REVIEWED change, and this phase has
no reviewed change to ratify — its whole promise is that nothing moved.

## Out of scope for this phase

No accessible names on controls (Phase 3), no focus management (Phase 4), no live regions
(Phase 5). Landmarks that need a name get one here because a landmark without a name is not a
landmark; a *button* without a name waits for Phase 3.
