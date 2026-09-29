# Phase 2 — The seeds

**No STOP C.**

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.**
  `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/mocks/seeds/settled-decisions.json'));print(len(d),sorted({r['state'] for r in d}),list(d[0]))"`
  → **10** rows, **`['resolved', 'superseded']`**, keys `folder, kind, title, reason, state, when, year` — no
  « Laissée telle quelle » row, no id, no count, no author; `pending-decisions.json` → **3** rows;
  `ls frontend/maquette/design/src/mocks/seeds | wc -l` → **46** files; no completeness seed exists.
- **Points ≈ 13.** `id`, `candidatesCount`, `settledBy` on the ten settled rows (≈ 30 lines edited) 6; one dismissed
  decision (≈ 8 lines new) 1; one medium the engine identified alone, at « identifié », its settled row
  `settledBy: engine` — the subject of « Corriger » (≈ 10 lines) 1; completeness for two follows, one complete and one
  holed (≈ 30 lines) 3; `python3 scripts/check-mock-seeds.py` read by OUTPUT 1; the report 1.
- **Readers.** `features/acquisition/resolution-screen.tsx:183` (« Réglées récemment », `.slice(0, 6)`) reads
  `settled` — the new rows must not displace one of its six (they are dated oldest).

## Red today

None — seeds have no rule; `check-mock-seeds.py` is the guard.

## Move

1. Edit `settled-decisions.json` and add the rows, from the shapes already there; each settled row's folder and
   choice match a medium the journey or the Médiathèque seeds already carry — one operator-settled, one
   engine-settled, one dismissed, one shelved (phase 6's subject).
2. Add `mocks/seeds/follow-completeness.json`, two follows the follow sheet already draws, its rows derived from the
   same seasons `seasons.json` carries — never a second set of figures.

## Mutation

None.

## Register

None.

## Oracle: states that diverge, declared by name

None expected; a state that moves because a list grew by one row is STOP A.

## Commit

`feat(maquette-l24): the seeds of who settled a decision, a dismissed one, and completeness`
