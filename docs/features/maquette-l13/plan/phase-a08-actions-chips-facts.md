# Phase a·8 — Actions, chips, facts, poster

A CONVERSION: the panel and screen actions, the chip and status-dot tones, the fact rows and the
poster box become variants or `ui/` components. Their `legacy.css` rules are deleted, along with
`chipHTML`, `factRowsHTML` and the features' use of `posterBox` (DESIGN § 2.5, § 2.6; § 3, rows 16
and 20).

## The proof FIRST

- **The oracle**: zero divergence on every state.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
  - The only expected movement is R80 (`residue.py`). It loses the `.pip` pair and the six tone
    pairs `.pip.warning`, `.pip.danger`, `.pip.info`, `.pip.waiting`, `.pip.success` and
    `.pip.neutral`. Its `PAIRS_FLOOR` is lowered by the same number in this commit, each pair is
    named, and three pairs remain until a·18 (see a·7).
- `python3 scripts/check-legacy-css-residue.py --record` after the shrink, then the plain run exit 0.
- `python3 scripts/check-poster-box.py` exit 0. The `.poster` box declaration and `.sheetposter`'s
  box move into the poster variant, so the floor is met from the variants.

## The move

- **A rule dies with its LAST emitter** (DESIGN § 2.6). `cardHTML` and `libRowHTML` still emit `cfoot`,
  `solid`, `owned` and `chip` until a·10 and a·11: those rules stay, the variant is what the converted
  components wear, and the commit body names each rule that waits and for which phase.
- **Actions.** The class `sact` and its `.sact.primary` form become the action variant of
  `ui/panel/index.tsx` and of the screens. B-339's `disabled:` half is NOT drawn here: c·3 draws it,
  because it changes the drawing.
- **Buttons.** `btnprimary`, `cfoot` (with its `solid` and `owned` qualifiers), `mediaadd` (with
  `done`) and `primary` become variants.
- **Chips and status dots.** `chip` and the tone classes `info`, `success`, `warning`, `danger`,
  `neutral` and `waiting` become the chip variant's tones and `statusDot()`. Every bare
  `pip ${tone}` write carries the variant instead.
- **Fact rows.** The row classes `fk`, `fn`, `fr`, `fs`, `fw`, `fx`, `fblocked`, `fclick` and
  `fempty` become a facts-row component in `ui/`.
  - Every caller of `factRowsHTML` switches to it: `features/account/page.tsx`,
    `features/arrivals/page.tsx`, `features/arrivals/queries.ts`, `features/maintenance/page.tsx`
    and `features/system/page.tsx`.
  - `factRowsHTML` and `factsListHTML` are then deleted.
  - The `.flux` CONTAINER rules stay: their emitters convert in a·9 and a·15.
- **Chips from the engine.** `chipHTML` callers, `features/settings/page.tsx` among them, switch to
  the chip component, and `chipHTML` is deleted.
- **The poster box.** `pfall`, `poster` and `sheetposter` become the poster variant and a poster
  component in `ui/`.
  - The features stop calling `posterBox`: `ui/panel/index.tsx`,
    `features/arrivals/resolution-cards.tsx` and `features/acquisition/discover-cards.ts`.
  - The engine's own builders (`cardHTML`, `tileHTML`, `libRowHTML`) still call it. So the function
    itself is deleted with the last of them in a·11, and the phase re-takes its callers before
    deleting anything.
- **Members removed.** `lib/engine-drawing.ts` loses `chipHTML`, `factRowsHTML` and `posterBox`.
- **Invariant 10.** `ui/` components take a tone and a label, never a medium or a state name.
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit.

## Gate

Per INDEX « Gates ». In addition, the residue ceiling, R80's floor and the poster-box count are all
in the report.

## Commit

`refactor(maquette-l13): actions, chips, status dots, fact rows and the poster box are variants`
