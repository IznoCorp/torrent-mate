# Phase 5 — The gate, the reference, and the mutation that matters

## Goal

The oracle stops being a script someone can run and becomes something the repository runs.

## Work

1. **Record and commit the reference** at this branch's tree, with `baseCommit` set to the SHA
   measured. The prototype is unchanged by this lot — that is what makes its own reference
   trustworthy.

2. **Wire the third tier.** `run.sh` has two tiers (`--contracts`, full). The oracle is a third
   and duplicates neither: rules say the behaviour holds, the oracle says the rendering did not
   move. Add `run.sh --oracle` and a `make maquette-oracle` target. **Not in `make check`** — it
   is a browser run over 82 states.

3. **Fire the mutation the architecture file names as this lot's definition of done**: a
   deliberate one-pixel padding change must fail the oracle **and name the right region**
   (ACC-03). Anchor on `padding: 11px 12px;`, which exists five times — verified with `grep -c`,
   because an earlier draft anchored on `padding: 12px 14px;`, which is in no version of the file
   and whose assert would have fired while proving nothing.

4. **Full gates**: `make lint`, `make test` (0 failed, 0 errors — an ERROR means collection
   crashed), `make check`, then `frontend/maquette/harness/run.sh` at unchanged hold counts.

5. **Update the state, in one place only.** `frontend-architecture.md` carries the lot's status as
   ONE WORD (`LANDED`); everything richer — the PR, the measurements, the wall-clock — goes in
   `IMPLEMENTATION.md`. Duplicating state is what produced a stale table read as current for three
   days.

6. **Adversarial review** before merge — standing operator instruction, and this lot deserves it
   more than most: an oracle that is wrong is worse than no oracle, because every later lot will
   trust it.

## Done when

Every ACC-01 … ACC-16 of `DESIGN.md` produces its documented output, re-exercised on the final
tree rather than on the tree each was written against.

## Traps

- **The stale copy.** `run.sh` rebuilds and re-copies `/tmp/tm-refonte/wrapped.html` first,
  because a stale copy measures the previous build in silence. Anything invoking the oracle
  outside `run.sh` must do the same, or say loudly that it did not.
- **A green oracle over nothing.** Before declaring done, check the report's count of regions
  actually RESOLVED per state, not the count declared.
- **`make test` ERROR ≠ FAILED.** An ERROR means collection crashed and everything after it was
  skipped.
