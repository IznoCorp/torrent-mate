# Phase a·7 — Layout primitives

A CONVERSION: `.screen.open` FIRST, then `.sheet.dragging`, the section, the empty note, the end mark, the skeleton and the
surface error become variants or `ui/` components, their `legacy.css` rules deleted in the same commit (DESIGN § 2.5,
§ 2.6; § 3, rows 16 and 20).

## Why `.screen.open` converts first

The `screen()` variant is `translateX(100%) invisible` and has no open branch. Only `legacy.css` makes the five route
screens visible: `add-screen.tsx`, `resolution-screen.tsx`, `media-screen.tsx`, `quality-screen.tsx` and
`releases-screen.tsx` all render `${screen()} open`. Every later surface phase reads its oracle through those screens, and a
phase cannot read zero divergence on a screen that is visible only because of the residue it is deleting. So the variant
gains its open branch, the rule goes, and the oracle is read on the five screens BEFORE anything else in this phase moves.

## The proof FIRST

- **The oracle**: zero divergence on every state. Read the five screens' states first, on their own commit-local build.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
  - The ONLY expected movement is R80 (`residue.py`). It loses one hold per residue pair whose rule is deleted: `.sec`,
    `.sechead`, `.empty`, `.surferr`, `.endmark`. Its `PAIRS_FLOOR` is lowered by the same number in the same commit, and
    each lost pair is named in the commit body. This is R80's rule for a conversion phase (DESIGN § 2.6), written down
    instead of slipped in.
  - `.panel`, `.scrim.open` and `.sheet.open` already have their variant (DESIGN § 2.6). Their rules stay until a·18, so R80
    keeps a subject until the phase that deletes it.
- `python3 scripts/check-legacy-css-residue.py --record` after the shrink, then the plain run exit 0.
- `python3 scripts/check-poster-box.py` exit 0: the skeleton tile's box moves into the skeleton's variant.

## The move

- **Variants and components.** New or extended variants go in `ui/variants/`. The components are the section, the section
  head, the empty note, the end mark, the skeleton and the surface error, all in `ui/` with no domain (invariant 10). Every
  file stays under 400 non-blank lines.
- **Engine helpers whose callers switch to those components**: `secHTML`, `secInner`, `emptyInner`, `skelCardsInner` and
  `surfErrInner`.
  - Callers rendering them through `dangerouslySetInnerHTML` render the component instead, and `lib/engine-drawing.ts` loses
    those members.
  - Each helper is deleted from `legacy.js` once its last caller has switched. The phase re-takes the callers first:
    `features/arrivals/page.tsx`, the acquisition tabs, `features/account/page.tsx`, `app/not-found.tsx`,
    `ui/state-surfaces.tsx` and the others the § 2.5 scan prints.
- **`legacy.css` rules deleted** with the markup they styled:
  - `screen` and `.screen.open`;
  - `.sheet.dragging`, which `ui/sheet.tsx` toggles and now draws through a class-qualified utility;
  - `sec`, `sechead`, and the contextual `.sechead .t` and `.sechead .k`;
  - `empty` and `endmark`;
  - `sk`, `skcard` and `.sk.tile`;
  - `surferr`, with `.surferr b` and `.surferr button`.
- **Bare HTML-string writes.** `features/acquisition/discover-feed.ts` writes `empty` and `endmark` as bare strings. The
  phase re-takes those writes: if converting them means redrawing the feed, their rules wait for a·11, and the commit body
  says so.
- **The size ledger.** `legacy.js` only subtracts; `scripts/frontend_size_ledger.py` is re-recorded DOWNWARD in the commit.

## Gate

Per INDEX « Gates ». In addition, the residue ceiling and R80's floor are both lowered and named. Any divergence on a state
other than those this phase's classes draw is STOP B.

## Commit

`refactor(maquette-l13): the open screen, the section, the notes, the skeleton and the surface error are variants`
