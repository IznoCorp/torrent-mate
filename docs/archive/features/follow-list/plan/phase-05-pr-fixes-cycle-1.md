# PR Fixes Cycle 1 — feat/follow-list (PR #197)

**Trigger**: `/implement:pr-review` findings on the merged PR.

## Fixes applied

### C1 (MAJOR) — `find_by_ref` cross-key dedup bug

**Problem**: `_FollowSubStore.find_by_ref` used `WHERE media_ref_json = ?` with the
full canonical tuple `{"tvdb_id":..,"tmdb_id":..,"imdb_id":..}`. A series stored
with tvdb+tmdb was NOT found by a tvdb-only lookup, causing:

- `follow remove --tvdb X` → "not found" on a stored tvdb+tmdb row
- `follow add --tvdb X` → duplicate row (no dedup)

**Fix**: `personalscraper/acquire/store.py` — `find_by_ref` now uses SQLite
`json_extract` to match on the **primary available ID** of the lookup ref:

```
if media_ref.tvdb_id is not None → WHERE json_extract(media_ref_json, '$.tvdb_id') = ?
elif media_ref.tmdb_id is not None → WHERE json_extract(media_ref_json, '$.tmdb_id') = ?
elif media_ref.imdb_id is not None → WHERE json_extract(media_ref_json, '$.imdb_id') = ?
```

`ORDER BY id LIMIT 1` returns the first matching row.

**Tests** (tests/acquire/test_store.py):

- `test_follow_find_by_ref_cross_key_tvdb_primary`: add tvdb+tmdb → find_by_ref(tvdb-only) matches
- `test_follow_find_by_ref_cross_key_tmdb_fallback`: add tvdb+tmdb → find_by_ref(tmdb-only) matches
- `test_follow_find_by_ref_no_false_merge`: two series, find_by_ref(one) returns only that one

**CLI test** (tests/commands/test_follow.py):

- `test_follow_add_tvdb_tmdb_remove_tvdb_dedup_reactivate`: add --tvdb+--tmdb →
  remove --tvdb works → re-add dedup (one row)

### C2 (MAJOR) — `follow remove --id <rowid>` untested

**Test** (tests/commands/test_follow.py):

- `test_follow_remove_by_id_soft_unfollows`: add → get rowid → remove --id →
  asserts `active=False` + exactly one `SeriesUnfollowed` emitted.

The `--id` branch in `follow.py` was verified working (no fix needed).

### m1 (MEDIUM) — already-inactive double remove untested

**Test** (tests/commands/test_follow.py):

- `test_follow_remove_already_inactive_no_double_event`: add → remove → remove
  again → exit 0, "already inactive" in output, exactly ONE `SeriesUnfollowed`.

### m2 (MEDIUM) — resolver empty/None-title fall-through untested

**Tests** (tests/acquire/test_title_resolver.py):

- `test_resolve_falls_back_when_title_is_none`: provider returns `title=None` →
  placeholder `"tvdb:81189"` (no raise, not empty)
- `test_resolve_falls_back_when_title_is_empty_string`: provider returns
  `title=""` → placeholder `"tvdb:81189"` (no raise, not empty)

Both are pure tests — the resolver code already handled this correctly via
the `if title:` check.
