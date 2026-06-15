# Implementation Progress — ownership

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP6 — "do I already own this?" ownership predicate (port + indexer predicate + wiring) (minor)
**Version bump**: 0.29.0 → 0.30.0
**Branch**: feat/ownership
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/198
**Design**: docs/features/ownership/DESIGN.md
**Master plan**: docs/features/ownership/plan/INDEX.md

## Phases

| #   | Phase                                                        | File                   | Status |
| --- | ------------------------------------------------------------ | ---------------------- | ------ |
| 1   | Core port (OwnershipChecker Protocol + NullOwnershipChecker) | phase-01-port.md       | [x]    |
| 2   | Indexer predicate (is_owned SELECT-only + golden)            | phase-02-predicate.md  | [x]    |
| 3   | Adapter + composition-root wiring + integration test         | phase-03-wiring.md     | [x]    |
| 4   | Docs + ACCEPTANCE + gate                                     | phase-04-gate.md       | [x]    |
| 5   | PR review fixes — cycle 1                                     | phase-05-pr-fixes-cycle-1.md | [x]    |

## Review cycles

### Cycle 1

- Toolkit: code-reviewer + pr-test-analyzer on PR #198 (CI green). pr-test-analyzer: **STRONG, mutation-proven** (8 SQL/adapter mutations each kill tests — soft-delete liveness, provider-id no-cross-contamination, imdb raw-vs-CAST, episode mis-join, kind filter, read-only, fail-soft, broken-db). code-reviewer: SQL/fail-soft/lock-free/boundary all correct, no critical/major. Retained findings (design-conformant):
  - **M1 (medium)** no test for a same-`tvdb_id` movie+show COLLISION: the kind filter is mutation-proven present, but no test pins that `is_owned(kind='movie', tvdb=X)` doesn't return True off a same-id show's episode file (realistic: TVDB series-ids / TMDB movie-ids can numerically collide). A false-owned would skip a wanted movie.
  - m1 (minor, code) `_ensure_open`: if `PRAGMA query_only=ON` raises after `sqlite3.connect`, the opened conn is never assigned nor closed (dangling handle until GC). m2 (minor, test) `close()` doesn't assert the underlying conn is actually released (a no-op close survives all tests).
- Decision: **Case B**. Fix phase 5 executed (1 commit `a44a9cc8`): **M1** same-tvdb movie+show collision test pins the kind-disambiguation (predicate already correct — kind filter in both branches; verified `is_owned(kind='movie', tvdb=X)`=False off a same-id owned show, `kind='episode'`=True); **m1** `_ensure_open` wraps the PRAGMA + closes the conn before re-raising (no leaked handle); **m2** close-releases-conn test (`conn.execute` post-close raises ProgrammingError). make check 6740 green. Merge = manual.

## Next action

All phases complete — run `/implement:feature-pr`.
