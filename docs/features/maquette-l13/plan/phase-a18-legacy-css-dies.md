# Phase a·18 — `legacy.css` dies

A CONVERSION by deletion: once no markup wears a class that only `legacy.css` styles, the sheet, its import,
its guard, R80, and every instrument that read it die or re-aim in ONE commit (DESIGN § 3, row 22; § 9.5,
§ 9.9).

## The proof FIRST

- **What the sheet still holds, read first.** `python3 scripts/check-legacy-css-residue.py` reads only the
  classes whose markup is gone, plus the three that already have a variant (`panel`, `scrim`, `linkbtn`) and
  the engine-internal six (`hpanel`, `states`, `ptr`, `armed`, `loading`, `spin`, DESIGN § 2.6).
  - A class with a live emitter and no variant is STOP D, not a deletion.
  - The engine-internal `ptr`, `armed`, `loading` and `spin` style the pull indicator that the engine drives
    until b·8. The phase re-takes them: their drawing moves into the variant that `#ptr` wears, as
    class-qualified utilities, so the pull draws the same.
- **The oracle**: zero divergence on every state.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
  - The only expected movement is R80's disappearance, together with its last three pairs. It is written in
    the commit body.
  - `markup_dressing.py`'s arm (`scripts/check-markup-contracts.py`) keeps its counts.
- **`make check`** exits 0, with zero failures and zero errors.

## The move — all in ONE commit

- **The sheet and its import.** Delete `frontend/maquette/design/src/styles/legacy.css` and its import at
  `app/shell.tsx:26`.
- **The guard and its entries.** Delete `scripts/check-legacy-css-residue.py` and
  `frontend/maquette/legacy-css-residue.json`, together with the guard's entries at `Makefile:89`, in
  `.github/workflows/ci.yml` (the step, and any paths filter that names the guard) and at `run.sh:203`.
- **R80.** Delete `residue.py` and `tests/scripts/test_residue.py`, its `CONTRACTS` entry in `run.sh`, and
  its R80 key in `frontend/maquette/regions.json`. The number R80 is retired, not reused.
- **The comment baseline.** Delete the `design/src/styles/legacy.css` row of
  `frontend/maquette/comment-references-baseline.json`. `scripts/check-maquette-comments.py`'s behaviour on
  an absent file is read before the row goes.
- **The poster-box guard.** `scripts/check-poster-box.py`'s floor is RE-AIMED to the variants: its docstring
  and comment stop naming `styles/legacy.css`, and `BOX_FLOOR` is re-taken by the guard's own method (raise
  it until it falls; the last value that passed is the count).
- **`scripts/markup_dressing.py`.** Its five `legacy` reasons are re-read. Each element is now painted by
  its variant, so each entry is either deleted, when the element is no longer bare, or re-worded with the
  variant that dresses it.
- **The sign-in binding.** `scripts/csstokens_login.py` loses `LEGACY_STYLESHEET`, following the composition
  a·17 left in `serve.py`.
- **Dead constants.** `scripts/check-css-tokens.py`'s `LEGACY_LAYER` goes, because it only ever read the
  sheet when it existed.
- **Comments naming the sheet as a painter** (`app/drawer-gesture.ts`, `ui/variants/frame.ts`,
  `ui/variants/controls.ts`, the feature `variants.ts` headers, `gestures.py`, `exits.py`) are rewritten so
  they name what paints now.
- **The steward amends the D3 and D10 paragraphs of the plan**, which name the sheet. This phase does not.
- **Invariant 10.** No `legacy` bucket is left: `styles/` holds tokens, base and harness.

## Gate

Per INDEX « Gates ». In addition, `make check` exits 0 and
`grep -rn "legacy\.css" scripts frontend/maquette --include=*.py --include=*.ts --include=*.tsx --include=*.json --include=*.sh`
reads only history citations.

## Commit

`chore(maquette-l13): legacy.css, its guard and the rule that compared it to the variants are deleted`
