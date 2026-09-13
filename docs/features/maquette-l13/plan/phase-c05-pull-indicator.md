# Phase c·5 — The pull indicator

A BEHAVIOUR change: « Réglages »' pull-to-refresh indicator is centred, and it is gone when the
refresh is, not after a fixed 1 100 ms (DESIGN § 10, B-331). It relies on the pull block having
moved out of the engine in b·8.

## The proof FIRST

- **Take the reading B-331 leaves open first.** The entry asks whether the spinner is off-centre
  ONLY while `.loading` is on. Sample the pull itself in the harness at 390 px: read the spinner's
  x, y and width at rest, armed, loading, and closing. The report records which moment is
  off-centre, and on the Mac, not the operator's phone.
- **The rule.** Its label is bound to the next free number. It drives a real pull on « Réglages »
  and reads:
  1. while loading, the spinner's centre is within 1 px of the viewport's centre, and it is not cut
     by the scrollport's edge;
  2. the indicator's height returns to 0 WHEN the refresh settles, meaning the query refetch the pull
     triggers, not after a fixed delay;
  3. « Actualisé. » is said after the indicator has closed, never while it is still open.
- **Red today**: reading 2, because of the fixed timer, and reading 1 if the sampling above shows
  the loading state off-centre.
- **Mutations.** With the commit made first, `scripts/mutate.sh`:
  - restores a fixed timeout: reading 2 falls, naming the delay;
  - removes the centring: reading 1 falls, naming the x offset.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new holds named.
- **The oracle may diverge ONLY on the pull states**, each accepted with « B-331 » (D8).

## The move

- **The indicator follows the refresh.** Its open/close block, moved by b·8 to `lib/pull-gesture.ts`
  and the settings surface's binding, closes on the refresh's settlement. The settings surface
  hands over its query's refetch promise, and `lib/` stays domain-free.
- **The centring** is repaired where the sampling locates it: in the variant `#ptr` wears, or in the
  spinner's transform while loading. The phase names which. If the sampling finds no off-centre
  moment on the Mac, the entry's centring half is reported as unreproduced there, and the device
  reading stays the operator's.

## Gate

Per INDEX « Gates ». In addition, B-331 closes, or has its centring half re-owned, with the
sampling and the rule's readings in the report.

## Commit

`fix(maquette-l13): the pull indicator is centred and closes when the refresh settles`

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** `refetch`, `spinner`, `indicator`, `centre`/`center`, `settle` are not vocabulary words — add what the phase declares in the same commit, or name from words already there.
