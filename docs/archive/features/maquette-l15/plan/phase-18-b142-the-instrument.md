# Phase 18 — B-142: the clause map's instrument

**Kind** instrument. It converts nothing and the oracle has nothing to say about it.

## Why it exists

Three instruments compare this interface to what already exists — `IMPLEMENTATION.md` § THE
OBJECTIVE, the demands register, `audit_design_coverage.py`. **None reads `product-intent.md`**,
the only document saying what the product must BE. A capability the constitution requires that
neither the maquette nor the backend has is invisible to every gate here, which is how three
dictated sections went a month unnoticed.

The mapping exists — `docs/reference/product-intent-map.md`, 23 clauses, ratified by the operator
on 2026-08-30 (Q7). **What does not exist is the arm that refuses a clause naming no surface.**

## What lands — `scripts/check-intent-map.py`

Its shape is `MODEL.md` § 4's and is not re-decided:

- It reads the constitution's numbered clauses **inside the two sections « Ce que l'interface DOIT
  faire » and « Ce que l'interface NE DOIT PAS faire » only**. `^\d+\. \*\*(DOIT|NE-DOIT-PAS)-\d+`
  over the whole file matches **24 lines for 23 clauses**, because §19's fourth point begins
  « 4. **NE-DOIT-PAS-8 est la limite dure.** ». The section bound is what makes 24 into 23.
- It refuses: a clause with **no row**; a `served` / `served, unproved` / `partly` row naming a
  surface absent from the tree — a route path with no file under `routes/`, a feature directory
  with no folder under `features/` (`to draw` and `outside the interface` rows name none and are
  exempt); a `to draw` row, or the « to draw » half of a `partly` row, **naming no lot** or a lot
  absent from the plan; a `served` row **naming no proof**; and any verdict outside the five-word
  vocabulary the map declares.
- **It prints one line per clause and never a count alone.** A number that is printed and not
  compared is a number nobody reads — a control drifted by seven inside the pull request that
  introduced it.
- **A refusal carries its reason**, or it gets worked around.

## What it cannot do, said so nobody expects it

It cannot tell whether a named proof READS the clause. Two rows of the first map named a print
statement and a rule about PM2 processes as proof, and only a reader found them. That check is a
review's, at every amendment of the map — and the arm's own output says so on every run.

## The two traps, both already paid for

- **Seeding the mapping from what exists today certifies the status quo.** The vocabulary file did
  exactly that and let twenty-four French words in with the rest. The map was written clause by
  clause against the tree and five of its rows say « to draw »; the arm reads it as written and
  never regenerates it.
- **A floor, not only a ceiling.** The arm holds the clause count at 23 and the row count at 23. An
  arm that read zero clauses would refuse nothing and print « no violation ».

## Where it runs, and the hole that had to be closed first

It goes in the contracts tier (`frontend/maquette/harness/run.sh`'s `REPOSITORY_GUARDS`). **And
that tier's job is gated on the `maquette` path filter, not on `docs`** — so the three documents it
reads are added to the `maquette` filter beside `BUGS.md` and `CLAUDE.md`.

**B-244 is closed in this phase.** `check-implementation-state.py` already had this defect:
it reads `IMPLEMENTATION.md`, which only the `docs` filter names, so a pull request touching that
file alone — a post-merge gesture, exactly — ran it in no job.
`tests/scripts/test_ci_filter_covers_the_guards.py` passed over it because it asks « is this path
named by ANY filter? » and never « by the filter that gates the job that runs the guard? ». The
hold is strengthened to ask the second question, and it must be **seen to fail** against the
workflow as it stands before the filter is fixed.

## The mutations

Three, each seen red and restored: delete a row from the map (a clause with no row); change a row's
`Owner` to a lot the plan does not carry; point a `served` row's surface at a route that does not
exist.
