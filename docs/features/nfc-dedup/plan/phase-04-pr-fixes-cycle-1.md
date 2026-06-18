# Phase 04 — PR fixes cycle 1

## Gate

Phases 1-3 merged-ready; PR #208 CI green; review cycle 1 findings retained (see
IMPLEMENTATION.md "Review cycles → Cycle 1").

## Goal

Harden the `library-dedup-titles` `dispatch_path` safety guard so a missing/empty
`dispatch_path` can never let a verifiable row be cascade-deleted (DESIGN "missing
dispatch_path → skip, never guess"), plus the medium/coverage findings.

---

### Sub-phase 4.1 — Guard hardening + supporting fixes + tests (one commit)

**Commit:** `fix(nfc-dedup): require verifiable dispatch_path before dedup delete + tests`

`personalscraper/commands/library/dedup_titles.py`:

- **F1 (critical)** — the guard must SKIP a group unless **every** member has a
  non-empty `dispatch_path` AND all paths NFC-match. Replace the
  `{p for p in paths.values() if p is not None}` set + `len != 1` test with: skip when
  `any(member path is falsy)` OR the NFC-normalized non-empty paths are not a single
  value. Log `dedup_titles.dispatch_path_unverifiable` with the missing ids.
- **F2 (medium)** — `_get_dispatch_path` coerces empty/whitespace to `None`
  (`return v or None` after strip).
- **F3 (medium)** — guard `db_path.exists()` before `_sqlite3.connect`; on absent →
  `typer.echo(..., err=True); raise typer.Exit(1)`.
- **medium** — fix the `_canonical_key` docstring: the real indexer dedup
  (`get_by_title_kind_year`) is case-SENSITIVE (`WHERE title = ?`, no `lower()`); state
  the `.lower()` here is an intentionally-broader, dispatch_path-guarded grouping, not a
  mirror of a non-existent indexer `lower()`.
- **minor** — only append the survivor title to `to_normalize` when `_is_nfd(...)` (no
  no-op `UPDATE`, no inflated `normalized` count).

`tests/integration/test_dedup_titles.py` (every `run_cli` wrapped in
`patch("personalscraper.conf.loader.load_config", return_value=test_config)` — CI has no
config.json5):

- skip-branch: two live rows, genuinely different real folders → `deleted==0`,
  `skipped>=1`, both rows survive.
- partial-None: one row with a `dispatch_path`, one with `None` → `skipped>=1`,
  `deleted==0`, the path-bearing row is NOT deleted.
- CASCADE: seed a child (`item_attribute`/`season`) on the orphan, `--apply`, assert the
  child row is gone.
- idempotent `normalized==0` on the second `--apply` pass.

## Phase gate

`make test` green; new tests pass with `config/` moved aside (CI repro); `make lint`
clean; re-push → CI green → pr-review cycle 2.
