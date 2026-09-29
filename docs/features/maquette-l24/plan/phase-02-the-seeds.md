# Phase 2 — The seeds

**No STOP C.**

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.**
  `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/mocks/seeds/settled-decisions.json'));print(len(d),sorted({r['state'] for r in d}))"`
  → **10** rows, **`['resolved', 'superseded']`** — no « Laissée telle quelle » row;
  `pending-decisions.json` → **3** rows; `ls frontend/maquette/design/src/mocks/seeds | wc -l` → **46** files; no
  completeness seed exists.
- **Points ≈ 7.** One dismissed decision (≈ 8 lines new) 1; one medium identified automatically, at « identifié »,
  with no pending decision — S5's subject (≈ 10 lines) 1; completeness for two follows, one complete and one holed
  (≈ 30 lines) 3; `python3 scripts/check-mock-seeds.py` read by OUTPUT 1; the report 1.
- **Readers.** `features/acquisition/resolution-screen.tsx:82` (« Réglées récemment », `.slice(0, 6)`) reads
  `settled` — the new row must not displace one of its six (it is dated oldest).

## Red today

None — seeds have no rule; `check-mock-seeds.py` is the guard.

## Move

1. Add the rows to `settled-decisions.json` and to the staging seed that S5 reads, from the shapes already there.
2. Add `mocks/seeds/follow-completeness.json`, two follows the follow sheet already draws, its rows derived from the
   same seasons `seasons.json` carries — never a second set of figures.

## Mutation

None.

## Register

None.

## Oracle: states that diverge, declared by name

None expected; a state that moves because a list grew by one row is STOP A.

## Commit

`feat(maquette-l24): the seeds of a dismissed decision, a doubted match and completeness`
