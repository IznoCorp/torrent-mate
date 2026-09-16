# Phase c·8 — The library's states at rest

**Opening measure (2026-09-15, on `6839dd913`):**

- **Commands.** `ls harness/seeds_at_rest.py` → exists (R128), 15 `journal.check(` calls today,
  ALL on the acquisition surface (its own docstring: "the acquisition seeds offer at rest a takeable
  arrival for a followed medium, a blocked one, a paused follow and a season with a hole" — L21's
  four states; the library half is untouched territory in the same file). `python3 -c
  "…json.load(open('design/src/mocks/seeds/library-items.json'))…"` → 345 rows, fields `title`,
  `secondaryLine`, `category`, `ids`, `poster`; a separate `design/src/mocks/seeds/
  incomplete-shows.json` exists for the incomplete lens. No tsc probe: seed/rule work, no type
  change. `grep -n B-345 BUGS.md` → `open`, 1× (the library half; acquisition and settings already
  closed per the phase's own text).
- **Points ≈ 8.** The seed files touched (`library-items.json`, `library-categories.json`,
  `incomplete-shows.json`, projected through `build-mock-seeds.py`, never hand-edited) ≈ 1; extending
  R128 with one hold per library state (lenses, categories, the incomplete lens, selection+delete,
  sort, a row with a hole — six clusters named in the phase) and its per-state mutations ≈ 3 at the
  low end of "new rule", raised toward the high end for the six-way enumeration ≈ 4; the phase's own
  "measure before filling" enumeration is real, phase-opening work this commit does not substitute
  for, carried at ≈ 3 for the uncertainty. Figure is a ceiling estimate pending that enumeration.
- **Found (2026-09-15).** R128 already exists and already reads BOTH ends (layer + screen) with no
  `window.__go` call, on the acquisition surface only — the library half genuinely adds to the same
  file rather than starting one, matching the phase's own framing exactly (no contradiction found
  here).
- **Landed (2026-09-16).** The enumeration is in R128's docstring and the eight holds are green from
  the start: the seeds hold every state the library draws, so the « fill the holes » half is empty.
  Two mutations fell holds by name. The instrument's own trap is written down: a paged listing judged
  by one page, and `total` (1 861) where `loaded` (345) is what the layer holds. B-345 `to confirm`.

A BEHAVIOUR change: the seeds the design host serves at rest hold at least one subject in every state
the library surfaces can draw, so a hand can try each case without a named state. This is the library
half of B-345 and the fixture clause L13 inherits (DESIGN § 10; B-345).

## The proof FIRST

- **Measure before filling.** List every state the library surfaces can draw: the lenses, the
  categories, the incomplete lens, selection and delete, sort, and a row with a hole. List them
  against what the seeds hold at rest, from the drawing's branches and not from memory. The list
  goes in the new holds' docstring. That measurement is what the ruling asks for (« the fixture
  families' owner measures the states each surface can draw against the states the seeds hold, and
  fills the holes »).
- **The rule is R128 (`seeds_at_rest.py`).** It gains one hold per library state, and like the rest
  of the file it calls `window.__go` NOWHERE: the walk is a boot plus taps a thumb makes.
  - **Red first**: each state the seeds do not hold today fails, naming it.
  - **Mutation.** With the commit made first, `scripts/mutate.sh` removes one filled subject from the
    seed. Its hold falls, naming the state.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  R128's added holds named.
- **The oracle may diverge ONLY on library states whose seed content changed**, each accepted with
  « B-345 » (D8). The phase lists them.

## The move

- **Fill the holes.** The library seeds under `design/src/mocks/seeds/` gain the missing subjects,
  projected through `scripts/build-mock-seeds.py` where the seed is generated. They are never
  hand-edited in a generated file. `python3 scripts/check-mock-seeds.py` exits 0.
- **The rest of the register's « the library and the rest ».** The design assigns only the library
  half. Every other surface's share that is not already done (L21 did acquisition, #588 did
  settings) is measured by the same method and REPORTED to the steward, not filled here.

## Gate

Per INDEX « Gates ». In addition, B-345's library half closes with R128's red readings and the
mutation. The re-owned remainder is named in the report.

## Commit

`fix(maquette-l13): the library seeds hold every drawable state at rest`
