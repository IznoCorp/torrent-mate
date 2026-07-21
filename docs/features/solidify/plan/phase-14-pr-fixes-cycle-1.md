# Phase 14 — PR #316 review fixes, cycle 1

Two findings from the `/implement:pr-review` multi-agent review of PR #316 (13
subsystem chunks × correctness/silent-failure/over-deletion/design-conformity,
each finding adversarially verified). Both confirmed against live code by the
guarantor. Neither contradicts DESIGN.md — both are retained, in-scope fixes.

Operator decisions (2026-07-21):

- Fix both **now**, test-first, inside #316 (single-PR refactor).
- Finding A orphan semantics: **FileSystem + index**. A trailer is orphan only
  when its media is truly absent on disk; a media dir present on disk but not in
  the index is an **index bug to repair**, not an orphan — purge self-heals it.
- Scope: Part 1 (data-loss fix) **and** Part 2 (index self-heal) both land here.

## Finding A — MAJOR — `trailers purge` deletes legitimate trailers

`personalscraper/trailers/cli.py` (`_discover_fs_orphan_trailers`) +
`personalscraper/trailers/scanner.py:302` (`_build_library_items`).

The P6.4 FS-truth rewrite walks media dirs **from disk** (so they exist), then
deletes the trailers of any dir absent from `live_dirs`. But `live_dirs` is only
the **dispatched** item set (`_build_library_items` skips rows without a
`dispatch_path` attribute). So a media dir present on disk but not dispatched
(MediaElch-managed, library-scanned-not-yet-dispatched, or predating dispatch
tracking) has its real `*-trailer.*` deleted. Origin/main's purge was
ledger-based and never walked the FS — the over-deleting walk is new in this PR.

### Fix

- **`_media_dir_has_content(media_dir)`** (new): True iff a real media video
  exists under the dir — a `VIDEO_EXTENSIONS` file that is not a trailer
  (`is_trailer_filename`), not a sample (`is_sample_path`), not inside a
  `Trailers/` subfolder. Bounded to 2 levels (movie flat + TV `Saison NN/`).
- **Combined orphan rule**: a trailer is orphan iff its media dir is **not in the
  index (`live_dirs`) AND has no media content**. Present media → kept, always,
  regardless of dispatch state. This eliminates the entire false-positive class.
- **Self-heal (Part 2)**: a present-content dir absent from `live_dirs` is an
  index gap → `scan_and_stage_dir(conn, media_dir, disk_cfg, category_id, kind)`
  reindexes it. Disk walk reuses the scanner's own iteration
  (`disk_cfg.categories` → `config.category(id).folder_name` → `TV_CATEGORY_IDS`)
  so `(disk_cfg, category_id, kind)` is correct by construction — no reverse map.
- **Index unavailable** (`live_dirs is None`) still short-circuits the whole walk
  (no delete, no heal) — the existing safety net is preserved. FS-truth deletion
  and healing only run with the index available.
- **§8 rien-en-silence**: dry-run reports both "would delete N orphan trailers"
  and "would re-index M present dirs missing from the index"; real run reports
  deleted + healed counts. Purge now writing to `library.db` is surfaced.
- Staging root: FS-truth deletion only (no heal — not a library disk).

## Finding B — minor — `.env` secrets world-readable window

`personalscraper/conf/envfile.py:89` + `personalscraper/io_utils.py:35`.

`write_env_keys` routes through `atomic_write_text`, whose temp is created at
`0o644` and `os.replace`d onto `.env` (inheriting `0o644`) before the post-hoc
`chmod 0o600` — a window where the temp and `.env` are group/other-readable.
Pre-refactor used `mkstemp` (always `0o600`). Regression introduced by this PR.

### Fix

- `io_utils.atomic_write_text` / `_atomic_write_bytes` gain an optional
  `mode: int = 0o644` (default unchanged for all other callers). The temp fd is
  `os.fchmod`-ed to `mode` immediately after open — closing the window even if a
  stale temp pre-existed — so bytes are only written once perms are correct.
- `envfile.py` passes `mode=0o600` and drops the now-redundant post-`chmod`.

## Sub-phases

- **14.1** — RED tests for A: (a) present media *with video* not in index →
  trailer kept + `scan_and_stage_dir` called (heal); (b) true orphan (no video)
  still deleted; (c) index-unavailable still short-circuits. Update the mock
  shape of `test_purge_finds_fs_orphan_never_ledger_recorded` (add
  `disk.categories` + `config.category`).
- **14.2** — GREEN A: `_media_dir_has_content`, `_HealTarget`, rewritten
  `_discover_fs_orphan_trailers` (scanner-parity walk + combined rule),
  `_heal_index_gaps`, updated `purge` body.
- **14.3** — RED+GREEN B: temp-mode test; `mode` param in io_utils + `fchmod`;
  envfile passes `0o600`, drops chmod.
- **14.4** — `make check` (backend + frontend lane), hand back to operator.

## Acceptance

- A-regression test red before 14.2, green after; existing purge tests green.
- B test red before 14.3, green after.
- `make check` exit 0. No push — operator squash-merges #316 manually.
