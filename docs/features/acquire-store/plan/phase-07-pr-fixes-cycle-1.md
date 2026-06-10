# Phase 07 — PR-review fixes (cycle 1)

> **For agentic workers:** This phase records the reviewer findings fixed in PR
> review cycle 1. Each fix is design-conformant (it makes the code match DESIGN
> intent) and ships a paired regression test per the project rule
> "regression test per bug".

**Goal:** Fix 4 reviewer findings on the acquire deletion-authority + domain so
the code matches the DESIGN §7.2 (record_dispatch best-effort / HIT-MISS
observability) and §9 (fail-open) intent.

**Architecture:** No layering change — `acquire/` still imports only
`core/`/`conf/`/stdlib. The C1 directory-size sum uses stdlib `rglob` only (NO
import of `dispatch/_transfer`). All fixes preserve the existing fail-open /
fail-soft contracts and add no new failure modes.

**Tech stack:** `personalscraper/acquire/delete_authority.py`,
`personalscraper/acquire/domain.py`,
`personalscraper/acquire/migrations/001_init.sql`, `tests/acquire/*`.

---

## Sub-phase 7.1 — deletion-authority + domain fixes

### C1 (MAJOR) — record_dispatch never matched a directory source

`dispatch_movie` / `dispatch_tvshow` pass a DIRECTORY as `staging_source`.
`staging_source.stat().st_size` returned the directory inode size (~KB), never
the torrent's multi-GB `size_bytes`, so every real directory dispatch MISSed and
no obligation was ever written.

**Fix:** new `DeleteAuthority._staging_size` — when the source is a directory,
sum `f.stat().st_size for f in source.rglob("*") if f.is_file()` (recursive
content size); otherwise keep `stat().st_size`. Honest fail-open MISS still
applies when processed/renamed media diverges from the torrent's reported size
(full torrent↔media linkage arrives with RP5b). The existing OSError-on-stat
fail-soft now also covers rglob/stat errors during the walk (MISS
`reason="stat-error"`).

**Files:** Modify `personalscraper/acquire/delete_authority.py`.
**Test:** `tests/acquire/test_record_dispatch.py::test_record_dispatch_hit_directory_recursive_size`
(directory whose recursive total == `item.size_bytes` → one obligation row) and
`::test_record_dispatch_directory_size_mismatch_miss` (total != size → MISS, no row).

### F3 (folded into C1) — record_dispatch correlation window unguarded

The span between the guarded `get_completed()` / size compute and the store write
— the match comprehension, `is_seeding(item)` (a client call that can raise on a
flaky connection), `_resolve_tracker`, and the `SeedObligation(...)` construction
— was unguarded, contradicting the "never raises" docstring promise. An
`is_seeding` raise would propagate into the dispatch FS path (write-before-move →
aborts the move).

**Fix:** the whole correlation body is extracted into
`DeleteAuthority._correlate_and_record` and wrapped in a fail-soft guard in
`record_dispatch`: any unexpected exception logs
`acquire.record_dispatch.miss reason="unexpected-error"` and returns, never
raises. The specific MISS reasons (no-live-torrent, not-seeding,
name+size-ambiguous, tracker-unresolved) and the write_failed fail-soft are
preserved.

**Files:** Modify `personalscraper/acquire/delete_authority.py`.
**Test:** `tests/acquire/test_record_dispatch.py::test_record_dispatch_fail_soft_on_is_seeding_error`
(client `is_seeding` raises → no raise, no row, miss logged).

### F1 (MAJOR) — may_delete fails CLOSED on a path-exists OSError

In `may_delete`, the fail-open `try/except` only wrapped `find_active_under`. The
per-obligation loop after it — specifically `Path(dp).exists()` — ran unguarded.
`Path.exists()` re-raises an OSError whose errno is not benign (ENAMETOOLONG on a

> 255-byte path, EACCES on an unreadable parent), so a pathological
> `dispatched_path` made `may_delete` RAISE into the deleter → fail CLOSED. DESIGN
> §9 requires ALLOW on any error.

**Fix:** the obligation evaluation (find_active_under + seed-time + path-exists)
is extracted into `DeleteAuthority._evaluate_obligations`, and the fail-open
guard in `may_delete` now wraps the whole call: any exception → log
`acquire.delete_authority.lookup_failed` + return ALLOW. The VETO/ALLOW logic is
unchanged.

**Files:** Modify `personalscraper/acquire/delete_authority.py`.
**Test:** `tests/acquire/test_delete_authority.py::test_path_exists_oserror_fail_open_with_mutation_proof`
(an active unmet obligation whose `dispatched_path` raises OSError on `.exists()`
→ ALLOW, never raises; mutation-proof: without the raise it VETOes).

### T1 (MEDIUM) — SeedObligation numeric invariant unenforced (defeats HnR guard)

`SeedObligation.min_seed_time_s` / `min_ratio` had no `>= 0` guard. A negative
`min_seed_time_s` makes `seed_time_elapsed >= obligation.min_seed_time_s`
trivially true → a live seed silently passes the HnR guard.

**Fix:** `SeedObligation.__post_init__` raises ValueError if `min_seed_time_s < 0`
or `min_ratio < 0` (mirrors `WantedItem.__post_init__`). Defense-in-depth at the
DB boundary: `CHECK (min_seed_time_s >= 0 AND min_ratio >= 0)` added to the
`seed_obligation` table in `migrations/001_init.sql` (no deployed DB — record_dispatch
never matched, so editing 001 directly is safe; `user_version` stays 1).

**Files:** Modify `personalscraper/acquire/domain.py`,
`personalscraper/acquire/migrations/001_init.sql`.
**Test:** `tests/acquire/test_domain.py` (negative min_seed_time_s / min_ratio
raise ValueError; zero accepted) and `tests/acquire/test_migrations.py` (the SQL
CHECK rejects a negative insert via a raw connection → IntegrityError; zero
accepted).

---

## Gate

- `python -m pytest tests/acquire/ tests/core/ tests/architecture/ -q` → 0 failures.
- `python -m mypy personalscraper/acquire/` → 0 errors.
- `ruff check` + `ruff format --check` on changed paths → clean.
- `python scripts/check-pragma-discipline.py` → exit 0.
- `make check` → GREEN.
