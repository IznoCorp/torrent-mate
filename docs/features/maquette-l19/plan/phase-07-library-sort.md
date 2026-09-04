# Phase 07 — Library: the sort sheet

## Objective

The sort sheet is built inline in the delegation (`legacy.js:10007`, under `data-sort`) rather
than in a named function — the only one of the ten in that shape. It moves to
`features/library/panel-sort.ts`, kind `sort`, no address.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular

- **The panel has no address on purpose and keeps none**: its own meta line says the sort « is a
  preference, not a location: it stays on this device and does not enter the URL ». That
  sentence is the interface's, moves to `fr.json`, and the rule below reads it where it is drawn.
- `TRIS` is `interface`-class: the table of six sort names stays the interface's. It moves with
  the producer into the feature rather than to a seed — routing a label through a mock would
  have the interface asking a server for its own words.
- `TRIS` is published on the reference today « because the rule that holds E-001 reads the NAMES
  from the prototype rather than restating them ». **That reader is a RULE, not a component**: it
  keeps reading the names, from wherever they now live, and this phase repoints it rather than
  letting it read a table nobody fills.
- `data-setsort` (the branch that APPLIES a sort) is a verb and does **not** move: this lot
  moves two verbs and this is not one of them.

## The rule that bites

`harness/library_sort.py` already exists. It gains: the sheet opens through the seam, the six
names come from the interface's own table, and the CURRENT sort is the one marked primary. The
mutation inverts the « is this the current sort » test and the hold must fall naming the sort it
marked instead.

## Verdict

**Landed.** `features/library/panel-sort.ts`, kind `sort`, no address.

**`TRIS` left the engine.** `features/library/sorting.ts` owns the ways and publishes
`window.__sortWays` — `settings-labels.ts`'s arrangement — so the count line, the panel, the
engine's `sortLabel` and `library_sort.py` read ONE derivation. The KEYS are code, the six NAMES
are `fr.json`'s.

### The mutation

`sortReversed === (direction === "inverse")` → `true`, so every direction claims to be the one in
force. `library_sort.py` fell twice: « exactly one of them is marked as the one in force » and
« with a reversed direction in force, exactly that one is marked ». R120 did not — correctly: it
holds the SEAM, and which entry is primary is the sort rule's subject.

### The phase's finding — a reading taken against the previous build

**`library_sort.py` reported 19 holds GREEN while reading `window.__referentiel.TRIS`, which this
phase had already removed.** Running a rule directly after editing `design/src` measures the
PREVIOUS build: `run.sh` and `scripts/mutate.sh` rebuild and republish, a bare
`python3 harness/<rule>.py` does not. It is B-303's shape one file over — the served copy is a
manual artefact, and a stale one measures code nobody is testing.

Rebuilt and re-read, the rule crashed on `None`, which is the honest answer, and it is repointed
at the seam. **Phase 06's own « 53 green » was re-taken on a fresh build and holds** — it had the
same exposure and did not have the defect.

**The discipline this establishes for the rest of the wave**: a rule read outside `run.sh` or
`mutate.sh` is preceded by `npm run build` and `served_copy.py --publish`, or it is not a reading.

### Readings

| Gate | Reading |
| --- | --- |
| **oracle** | 2 958 measurements, **NO DIVERGENCE** |
| `run.sh --contracts` | 14 rules, 26 guards, no violation |
| `library_sort.py` | 19 holds, green |
| `engine/legacy.js` | 32 286 → **32 256**, re-recorded |

### Deviation

**Two shapes in the descriptor were tightened**, and both are typing rather than drawing: the
target is two literals rather than one carrying `reversed: undefined` — an attribute the
delegation would read as PRESENT — and the absent tone is `undefined` rather than `null`, which is
what `Action.ton` declares. The engine wrote `null` because JavaScript let it. The oracle says the
drawing is identical.
