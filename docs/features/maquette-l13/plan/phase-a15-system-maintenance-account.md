# Phase a·15 — « Système », « Maintenance », « Compte »

A CONVERSION: the last emitters of `flux` and of the fact rows convert on the three pages, and
`MAINT_ACTIONS`, which is dead data, is deleted (DESIGN § 2.6, § 5.1; § 3, rows 16 and 18).

## The proof FIRST

- **The oracle**: zero divergence on every system, maintenance and account state. Any other
  divergence is STOP B.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
  - `page_host.py:248` and `url_state.py` are RE-AIMED where they read `MAINT_ACTIONS`: they now read
    the served `maintenance-actions.json` answer (`readMaintenanceActions`). Each keeps its count,
    said in its docstring.
  - `machine.py`'s scheduler holds keep their counts. B-327's held-back hold is NOT restored here;
    that is c·6.
- **Fixture checks.** `python3 scripts/check-mock-seeds.py` exit 0 with `MAINT_ACTIONS` marked
  `converted` in `frontend/maquette/fixture-register.json`.
- `python3 scripts/check-legacy-css-residue.py --record` after the shrink, then the plain run exit 0.

## The move

- **The last `flux` emitters convert.** `features/system/page.tsx`, `features/maintenance/page.tsx`
  and `features/account/page.tsx` draw the flux container through the variant a·9 introduced. The
  `.flux` rules are then deleted, together with the contextual `.flux .fx + .fx` rule.
- **Engine helpers leave the three pages.** Any `emptyInner` or `skelCardsInner` call still there
  switches to a·7's components. The phase re-takes the three pages' `lib/engine-drawing.ts` members
  first.
- **Deleted from `legacy.js`**: `MAINT_ACTIONS`. Its type goes from
  `features/maintenance/reference.ts`, because the page already reads the query (DESIGN § 5.1).
- **Out of scope.** The `signout`, `maintact` and `sheet=utilisateur` verbs stay the engine's until
  b·2, so their `data-*` names are emitted unchanged.
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit.

## Gate

Per INDEX « Gates ». In addition, `check-mock-seeds.py` exits 0, and `grep -c "flux"` over
`styles/legacy.css` reads 0.

## Commit

`refactor(maquette-l13): system, maintenance and account draw their facts as components and the dead actions table goes`
