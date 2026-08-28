# Phase 13 — The close

Nothing new is built here. This phase is where the lot's claims are turned into readings.

## The two arms reach their final counts

- **Invariant 4** — the server-state key count started at **11**. It ends at **0**, and the arm's
  ceiling is lowered to 0 in this commit so nothing can put one back.
- **Invariant 5** — 0 violations, and the corpus floor is raised to whatever the corpus now is.
  A floor that stayed at 3 while the corpus grew to thirty would be an arm reading a tenth of its
  subject.

## The fixtures are gone

`grep -rn "__referentiel" frontend/maquette/design/src/features | wc -l` → **0**. Whatever of the
41 `served` families survives is named, with the reason, and the register is updated so no family
sits unclassified — `check-mock-seeds.py --arm inventory` refuses that by construction.

## The demands are recomputed

`python3 scripts/compare-contracts.py --check`. The register is COMPUTED, never written, so this
is a re-derivation and not an edit.

## The register is written, and it was written DURING the wave

L08 merged with twenty findings that lived only in a commit message and it took another wave to
recover them, as classes rather than names. Every finding of this wave is already in `BUGS.md`
by the time this phase runs; this phase only checks that none is missing.

**Two findings are already filed and are not this lot's to fix**, recorded at the wave's opening:

- `BUGS.md` carries **seven duplicated rows** — B-079 to B-085 appear once `fixed #505` and once
  `open`. 108 rows, 101 distinct identifiers.
- `frontend-architecture.md` § 3 has **two invariants numbered 10**.

## The fifth post-merge gesture: recount B-085

« Guards green over what they do not read » stands at **26** across three waves. This wave adds
its own figure to `BUGS.md` § Guards green over what they do not read, **with the pull request
that establishes it**. **Zero is a real answer and is written down** with the same authority as a
six.

## The full gate

```
frontend/maquette/harness/run.sh          # every rule, the a11y tier, the oracle
make check                                # 0 failed, 0 error
```

An ERROR in `make test` means collection crashed and everything after it was skipped.

## And the four post-merge gestures that cannot be done from this branch

Written here so the next reader finds them, per § 5 of the architecture file:

1. `make maquette-oracle` then `python3 frontend/maquette/oracle.py --record` — the reference
   names the commit it measured, and the squash replaces that commit.
   **This cannot be done from a remote container**: the reference carries
   `"platform": "Darwin/arm64"` and the oracle refuses to compare across platforms.
2. Move this wave's row from « In flight » to « Last landed » in `IMPLEMENTATION.md`, and name
   L10 as next.
3. Archive `docs/features/maquette-l09/` under `docs/archive/features/`.
4. Recount B-085 (above), if it was not already written before the merge.
