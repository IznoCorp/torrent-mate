# Phase a·12 — Releases and quality

A CONVERSION: whatever `legacy.css` residue is still worn by the releases screen and the quality
screen becomes variants, and its rules are deleted (DESIGN § 2.6; § 3, row 16; INDEX's page order).

## The proof FIRST

- **The oracle**: zero divergence on the releases and quality states. Any other divergence is
  STOP B.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  no movement. The releases readers (`page_host.py`'s profile holds among them) keep their counts.
- `python3 scripts/check-legacy-css-residue.py --record` after the shrink, then the plain run exit 0.

## The move

- **First, re-take what is left.** Most of these two screens' residue already converted: `open` in
  a·7, and `chip`, the tones, `solid` and `primary` in a·8. So the phase re-takes the emit scan of
  DESIGN § 2.6 restricted to `features/releases/releases-screen.tsx` and
  `features/releases/quality-screen.tsx`, and lists every class still styled only by `legacy.css`.
- **Each class on that list** becomes a variant in `ui/variants/` (a primitive) or beside the
  releases feature (a new `variants.ts` there, if none exists). The rule is deleted in the same
  commit, unless another surface still emits the class, in which case it is named and waits for
  that surface's phase.
- **If the scan lists nothing**, the phase has no subject. It makes no commit, and the next commit
  body records the empty reading together with its command.
- **Verbs stay where they are.** `releases` and `profile` stay the engine's until b·2. Their
  `data-*` names are emitted exactly as today.
- **No engine change is expected.** If one happens, `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit.

## Gate

Per INDEX « Gates ». In addition, the scan's list, or its empty reading, goes in the report.

## Commit

`refactor(maquette-l13): the releases and quality screens draw their residue classes as variants`
