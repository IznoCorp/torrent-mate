# ACCEPTANCE — follow-list (Follow D1, v0.29.0)

Every criterion below is an executable shell command. Run from the repo root
with `personalscraper` installed (`pip install -e ".[dev]"`) and a valid
`config/` present. All pytest selectors use `-x` (stop on first failure).

---

## ACC-01 — follow add inserts a row and resolves title

```bash
python -m pytest tests/commands/test_follow.py::test_follow_add_inserts_one_row -x -v
```

Expected output: `1 passed`.

## ACC-02 — idempotent double-add produces exactly 1 row

```bash
python -m pytest tests/commands/test_follow.py::test_follow_add_idempotent_double_add_one_row -x -v
```

Expected output: `1 passed`.

## ACC-03 — metadata resolution failure still follows (fallback title)

```bash
python -m pytest tests/commands/test_follow.py::test_follow_add_metadata_failure_still_follows -x -v
```

Expected output: `1 passed`.

## ACC-04 — follow remove soft-unfollows (row preserved, active=False)

```bash
python -m pytest tests/commands/test_follow.py::test_follow_remove_soft_unfollows -x -v
```

Expected output: `1 passed`.

## ACC-05 — add → remove → add reactivates existing row (no duplicate)

```bash
python -m pytest tests/commands/test_follow.py::test_follow_reactivate_after_remove_one_row -x -v
```

Expected output: `1 passed`.

## ACC-06 — follow list (no --all) hides inactive; --all shows it

```bash
python -m pytest tests/commands/test_follow.py::test_follow_list_hides_inactive_by_default -x -v
```

Expected output: `1 passed`.

## ACC-07 — SeriesFollowed emitted on add

```bash
python -m pytest tests/commands/test_follow.py::test_follow_add_emits_series_followed_event -x -v
```

Expected output: `1 passed`.

## ACC-08 — SeriesUnfollowed emitted on remove

```bash
python -m pytest tests/commands/test_follow.py::test_follow_remove_emits_series_unfollowed_event -x -v
```

Expected output: `1 passed`.

## ACC-09 — store unit: find_by_ref id round-trip + dedup (LOAD-BEARING)

```bash
python -m pytest tests/acquire/test_store.py::test_follow_find_by_ref_round_trips_id -x -v
```

Expected output: `1 passed`.

## ACC-10 — store unit: list_active excludes inactive (LOAD-BEARING)

```bash
python -m pytest tests/acquire/test_store.py::test_follow_list_active_excludes_inactive -x -v
```

Expected output: `1 passed`.

## ACC-11 — store unit: set_active flips flag + reactivates (LOAD-BEARING)

```bash
python -m pytest tests/acquire/test_store.py::test_follow_set_active_flips_flag -x -v
```

Expected output: `1 passed`.

## ACC-12 — title resolver: all failure modes fall back, never raise (LOAD-BEARING)

```bash
python -m pytest tests/acquire/test_title_resolver.py -x -v
```

Expected output: `7 passed`.

## ACC-13 — FollowSubStore Protocol conformance

```bash
python -m pytest tests/acquire/test_store.py::test_follow_substore_satisfies_protocol -x -v
```

Expected output: `1 passed`.

## ACC-14 — make check green

```bash
make check
```

Expected: exits 0, `0 errors` from ruff + mypy, all tests pass, module-size under 1000 LOC.
