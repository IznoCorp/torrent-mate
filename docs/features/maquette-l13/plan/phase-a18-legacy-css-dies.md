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

## Amendment — 2026-09-13, ruling 59 (the steward, on the implementer's STOP D)

**VOID in this file**: « Delete `residue.py` and `tests/scripts/test_residue.py` » read as the whole module and
the whole test; and « their drawing moves into the variant that `#ptr` wears, as class-qualified utilities ».
Measured at the opening of a·18 on `f4b0732ae`:

- `harness/resolution_card.py:71` imports `read_factories` from `residue.py`. The reader half of `residue.py`
  (`VARIANT_SOURCES`, `FACTORY`, `CVA_CALL`, `LITERAL`, `balanced`, `split_top_level`, `without_comments`,
  `read_factories`) moves as is into `harness/factories.py`, and `resolution_card.py` imports it from there. The
  reader's tests move to `tests/scripts/test_factories.py`; R80's own tests die with it. The five « `residue.py`
  reads a branch through its literals » comments name `factories.py`.
- `window.__reposPTR` (`engine/legacy.js`) writes `ptr.className = "ptr"`, and the driver's reset
  (`harness/drive.ts`), `press.py` and `touch.py` call it: a utility on `#ptr` does not survive it. The rotation
  and the armed colour move onto the child `.spin` as parent-qualified utilities, `[.ptr.loading_&]:…` and
  `[.ptr.armed_&]:text-primary`.
- **FILED, NOT REPAIRED — b·8's**: the same reset erases the utilities `index.html` gives `#ptr` itself (its grid,
  its clipping, its zero height, its transition, its colour) in every state the driver builds.
- Measured without a hole: `setOpen` has no caller, so `.scrim.open` and `.sheet.open` have no engine emitter;
  `.panel` is `factsPanel()` and `.linkbtn` is `countLineAction()`, term for term; `csstokens_login.py`'s
  `LEGACY_STYLESHEET` left at a·17; `markup_dressing.py`'s two `.surferr button` reasons are rewritten with
  `surfaceError()`.
- **A blind spot, for the reader round** (L13a writes no rule): with `[.ptr.loading_&]:[animation:…]` removed from
  `.spin`, neither `press.py` nor `touch.py` falls — no rule reads that the pull's spinner turns while it loads.
