# Phase 16 — BLOCK 1 dies, `refonte.html` dies, §15 is amended

The lot's own words: BLOCK 1 « is deleted, not converted, and its disappearance is part of this
lot's proof rather than a later tidy-up ».

## What is deleted

| what | where it is today |
| --- | --- |
| the phone frame (`.stage`, `.device`) and its two desktop `@media` re-assertions | BLOCK 1 |
| the harness buttons (`.hbtn`) and the `html.measuring` hides | BLOCK 1 |
| the declared harness deviations (`.device .bottombar`, `.fab`, `.selbar` → `absolute`) | BLOCK 1 |
| the state panel (`.hpanel`, `.states`, 8 rules) | BLOCK 2, 3824–3882 |
| the design-notes overlay (`.note`, `.notes`, 4 rules) | BLOCK 2, 4009–4035 |

**The six app regions of BLOCK 1 are already out** — phase 1 moved them into the base layer, which
is the whole reason phase 1 exists. Nothing that ships is being deleted here.

## What remains, named and counted

`design/src/styles/legacy.css` — the residue of D-L07-5. It carries the sign-in gate (15 rules),
the splash (8 rules) and the markup the engine still draws, with the `login:*` markers `serve.py`
extracts. **Its contract is written at its top**: it names L13 as its death, and
`scripts/check-legacy-css-residue.py` refuses it growing.

The residue is a debt with a number and a date, not a leftover. The lot's « no hand-written
component stylesheet remains » reads as *for every surface this lot converted* — which is every
surface except the ones D5 assigns to L13.

## `refonte.html` dies

With the tokens in `theme.css`, the base in `base.css` and the residue in `legacy.css`, the file
carries a `<title>` and nothing else. `index.html` keeps the title and the file is removed.

**Fourteen files name that path and move in the same commit**: seven under `harness/` (including
`common.py`, which holds `DESIGN_SOURCES` — already widened in phase 1), five under `scripts/`,
plus `serve.py` and `vite.config.mjs`.
<sub>`grep -rln 'refonte\.html' --include='*.py' --include='*.mjs' --include='*.js' frontend scripts | grep -v node_modules | wc -l` → 14 on the day the wave opened, 0 at the close of this phase.</sub>

`vite.config.mjs`'s whole subject was injecting the fragment verbatim. With no fragment, the
plugin's `transformIndexHtml` half goes; its `closeBundle` half — the `dist/assets` symlink that
avoids copying 10 MB per build — stays, and says why in the same comment it says it today.

## §15 of the constitution is amended

§15 names `frontend/maquette/design/refonte.html` as the product. It cannot name a file that no
longer exists, and D3 already says what replaces it: **the tokens plus the component catalogue**.
The amendment adds what replaces it and names what it makes void, rather than quietly editing the
old text — that is § 7.1 of the architecture file, and it is the operator's document, so the
amendment is proposed in the pull request rather than assumed.

`IMPLEMENTATION.md` and `frontend/maquette/README.md` carry the same path in prose and follow.

## Mutation tests

- Add a class to `legacy.css` → `check-legacy-css-residue.py` exits 1 and names it. Restore.
- Re-add `.note` anywhere in the tree → the same check, or the compositor check, refuses the
  scaffolding coming back.

## Gates

The full wave list: ACC-04 through ACC-20. **ACC-14, ACC-15, ACC-17, ACC-18 and ACC-19 are
this phase's own** and are the lot's « Done when » read back as commands.
