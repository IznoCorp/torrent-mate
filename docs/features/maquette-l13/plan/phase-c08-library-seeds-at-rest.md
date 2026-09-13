# Phase c·8 — The library's states at rest

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
