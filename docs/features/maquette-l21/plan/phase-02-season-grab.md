# Phase 2 — « Récupérer cette saison » (B-301)

DOIT-3 applied to a season: the seasons panel PRINTS a season as `to_grab` and offers nothing.

## The rule FIRST, and it is red before anything moves

`frontend/maquette/harness/season_grab.py` — new. What it reads, and each fails differently:

1. **A season printed `to_grab` offers the verb.** Read on the panel, by a finger: the row is
   found, hit-tested at its own centre with `elementFromPoint` (what covers it says so), tapped.
2. **The OPERATION IS CALLED.** Read on the NETWORK — the mock records what it answered. *A hold
   reading the screen alone passes a build that toasted and sent nothing*, which is precisely what
   B-309 was.
3. **The season's state MOVES out of `to_grab`** on the panel, read after the act.
4. **Under the busy scenario** (`setOperationOutcome("grabSeasonForFollow", …)` with the pipeline
   running): the ask is QUEUED and said — never a 409, never « occupé ».

**Seen red how**: against `main` the verb does not exist, so holds 1–4 fail with no mutation
needed. That is the strongest form this repository asks for, and it is recorded in the report.

## The move

- **New file** `features/media/season-grab.ts` — the mutation, keyed by title + season number,
  calling `grabSeasonForFollow` through `features/media/queries.ts`. Invariant 7: the media
  feature does NOT import `features/acquisition/`; it calls the OPERATION.
- `features/media/panel-seasons.tsx` (200 non-blank, ceiling 400) gains the button and its
  `data-*` on the season row, and nothing else. **The verb is a new file beside the block, never a
  growth of the producer.**
- Copy in `i18n/fr.json`. **No interface text in the code** — the string is extracted, never
  retyped: a retyped string renders correctly while the reference is broken.
- `data-*` NAMES are code and are English (the operator overturned the old carve-out). The
  contract has three ends — the markup that emits it, the `dataset.X` that reads it, and the rules
  that tap it — and they move in ONE step.

## Gate

`run.sh --contracts`; the rule green with its holds counted; the oracle diverging ONLY on the
states whose seasons panel gained a button, each accepted with « B-301 / DOIT-3 » (D8).

## Commit

`feat(maquette-l21): a season printed to_grab can be taken from where its hole is printed`
