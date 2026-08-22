# Phase 3 — Accessible names

## Gate

Produced by Phase 2:

- `<main>` exists, the skip link reaches it, landmarks are named and unique.
- The heading outline holds: one `<h1>` per screen, no level skipped.
- `oracle.py --check` at 0 divergence, harness contracts green.

The tree is fixed before anything is named off it: naming a region that does not exist yet, or
that is about to change tag, is work done twice.

## What this phase does

Every interactive element carries a name an assistive technology can announce.

**The static count is 3 of 115 buttons, and it is not the number.** The engine builds buttons
from helper functions and template strings, so a static scan walks past most of them. The
measurement is `a11y.py --rules button-name,link-name,image-alt,label` over the 83 rendered
states, and the number it reports at the start of this phase is the one the phase burns down.

## Where a label lives, and it is not negotiable

| Where the element is drawn | Where its label lives |
| --- | --- |
| `design/src/**/*.tsx` — components | `design/src/i18n/fr.json`, read through `useTranslation()` |
| `design/src/engine/legacy.js` — the dying engine | a French literal in that file |

**Extract, never retype.** A retyped string renders correctly while the reference is broken,
which is the worst shape a defect can take: it looks right.

**Why the engine is allowed its French, stated with the arm that allows it** rather than assumed:
`check_strings` builds its scope from `.ts`/`.tsx` under the shell, so `legacy.js` string
literals are read by no arm, and `check_unread_javascript` names the file as one of the two
allowed JavaScript files with its reason. That is a named exemption, not an omission — the
distinction this repository exists to make. Separately, `check_french_debt` bounds the 25
declared debt *words* (names, not strings) to that same file.

## Sub-phases

### 3.1 — The shell and the layers

`index.html` and the engine-drawn layers: the tab bar, the drawer, the dialogs, the toast, the
install banner, the selection bar. These are the controls a keyboard user meets first and the
ones Phase 4 will move focus into, so they are named first.

Commit: `feat(maquette-l03): the shell's controls announce what they do`

### 3.2 — The pages

The eight page components under `design/src/pages/`. Labels through `useTranslation()`, keys
added to `fr.json`.

Commit: `feat(maquette-l03): every control on a page has a name`

### 3.3 — The screens and the panel

The five screen components under `design/src/screens/`, plus `components/panel.tsx` and
`components/sheet.tsx`. The sheet's drag handle (`#sheetgrab`) is a control with no name and no
keyboard path at all — it gets a name here and its keyboard path in Phase 4.

Commit: `feat(maquette-l03): the screens and the panel announce their controls`

### 3.4 — Images and icons

Decorative SVGs already carry `aria-hidden="true"` in most places (13 occurrences). Complete it,
and give every `<img>` either real alternative text or an empty `alt` when it is decorative — the
avatar's `<img alt="">` is correct and is the model.

Commit: `feat(maquette-l03): an icon is either named or explicitly decorative`

## Verification

| ID | Command | Expected |
| --- | --- | --- |
| ACC-08 | `python3 frontend/maquette/a11y.py --check --rules button-name,link-name,image-alt,label` | 0 violations over 83 states |
| ACC-09 | `python3 scripts/check-no-french.py` | exit 0 |
| — | `python3 frontend/maquette/oracle.py --check` | 0 divergence — a name is invisible to it, so a divergence here means something else moved |
| — | `grep -c '"' frontend/maquette/design/src/i18n/fr.json` | grows; no French label added to a `.tsx` |

## Out of scope for this phase

Focus order, trapping and restoration (Phase 4). A control that has a name but cannot be reached
by keyboard is a Phase 4 defect, not a Phase 3 one — and the split is deliberate: the two fail
for different reasons and are proved by different rules.
