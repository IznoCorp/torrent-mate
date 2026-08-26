# Phase 10 — The wave closes

## Scope

- `IMPLEMENTATION.md` § « Where the frontend work stands » — the landed row, written when the
  pull request OPENS, not after the merge.
- `docs/reference/frontend-architecture.md` — L08's status `NOT STARTED` → `LANDED`, and the
  refresh of any measured rationale this wave falsified (§ 7.1: that is the wave's DUTY, not an
  amendment).
- `frontend/maquette/README.md` — what the mock layer is and how to drive it.
- `BUGS.md` — whatever the adversarial review confirms.
- `personalscraper/__init__.py` — 0.98.41 → 0.98.42. **`main` moved mid-wave** (a Plex guard merged), so the branch was rebased and the bump re-taken: after a rebase the version the branch carries may be the version `main` now has, and the check compares against `main`.

## What must be refreshed rather than left standing

The measured inventory in `IMPLEMENTATION.md` § THE OBJECTIVE says the maquette has **0 API
modules and 1 network call**. This wave makes the second false by construction. Refreshing the
figure, in the wave that moved it, is § 7.1's duty — leaving it is the stale-directive disease the
architecture file exists to fight.

The same paragraph's item 3 says « while the maquette is a maquette it is NOT connected to the
backend ». That stays TRUE and must be seen to stay true: a mock layer is not a connection. The
sentence is left as it is; what changes is the count beside it.

## The adversarial review

Before the merge, and it is the operator's standing instruction. Reviewers who did not write the
lot, reading against the design's § 3 first: for each instrument, what does it not read, and is
that answer still the one the design claims?

## What is NOT done at this phase, and cannot be

**Re-recording the oracle references.** They must not move — this lot displays nothing — and if
they did the wave would stop rather than re-record. Should the operator arbitrate a movement,
`--record` runs on their machine and nowhere else: `oracle-reference.json` carries
`"platform": "Darwin/arm64"` and a recording taken on Linux would leave the instrument unusable.

**Moving the row from « In flight » to « Last landed ».** That is a post-merge step, and the only
one of the three that cannot be done from this branch.

## Done when

- Every ACCEPTANCE criterion has been run and its output recorded.
- The state row is written and the lot's status is `LANDED` in the architecture file.
- The version is bumped.
