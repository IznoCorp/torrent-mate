# Phase 2 — Dispatch item template + journal parity (T3)

## Gate

```bash
make lint && make test && make check

# Both destruction paths journal through the shared append-only path (F1)
rg -n "record_destruction" -g '*.py' personalscraper/dispatch/       # present in the SHARED template, reached by movie AND tv
rg -n "def dispatch_movie|def dispatch_tvshow" -g '*.py' personalscraper/dispatch/  # thin strategy wrappers only

# One orphan-sweep implementation (single owner)
rg -n "_tmp_dispatch_|_tmp_ingest_" -g '*.py' personalscraper/dispatch/  # markers live in ONE sweep function

python -c "import personalscraper" && echo IMPORT-OK

# ACC hook (DESIGN §10 ACC-06 — TV merge journaled, F1)
command python -m pytest tests -k "journal and (merge or tv)" -q --no-header | grep -E "passed" && echo ACC-06-OK
```

## Objective

Collapse the ~85%-duplicated `dispatch_movie`/`dispatch_tvshow` scaffolds into ONE
`_dispatch_item(dispatcher, src, category_id, spec)` template parameterised by a
`DispatchSpec` per media family (`existing_action` replace/merge, `transfer_fn`,
`identity_guard`, `canonical_name_rule`) (DESIGN §5 T3). Route BOTH destruction paths
(movie replace AND TV merge-overwrite) through the shared append-only destructive journal
(**F1**, test-first). Consolidate the four crash-recovery orphan-cleanup implementations
into ONE sweep, invoked once per run at a defined point, parameterised by the artifact
patterns.

## Findings addressed

PIPELINE-CORE-02 (`dispatch_movie`/`dispatch_tvshow` ~85% duplicated; journal only on the
movie branch) and PIPELINE-CORE-07 (four orphan-cleanup implementations executed
redundantly twice per run with inconsistent dry-run semantics). Conformity fix F1.

## Code anchors (verified)

- `personalscraper/dispatch/dispatcher.py`: `Dispatcher.dispatch_movie` :336, `Dispatcher.dispatch_tvshow` :350, `Dispatcher.process` :200, `Dispatcher._cleanup_orphan_temps` :136.
- `personalscraper/dispatch/_movie.py`: `dispatch_movie` :29; journals via `from personalscraper.indexer.destructive_journal import OP_OVERWRITE, record_destruction` (:18) at :124-127 (guarded by `dispatcher.config.indexer.db_path is not None`).
- `personalscraper/dispatch/_tv.py`: `dispatch_tvshow` :27 — **no** journal import or `record_destruction` call (verified absent). This is the F1 gap: TV merge-overwrites are not journaled.
- `personalscraper/indexer/destructive_journal.py`: `OP_OVERWRITE = "overwrite"` :26, `OP_DELETE = "delete"` :27, `record_destruction(...)` :30, `list_recent(...)` :64. `__all__` at :92.
- `personalscraper/dispatch/_transfer.py`: `_build_rsync_cmd` (single NTFS-flag source) + crash-safe staged-commit patterns (`_move_new`, 3-phase replace with rollback, merge backup/restore) — must survive the dedup untouched (audit "strengths").
- Orphan-sweep implementations (PIPELINE-CORE-07): `personalscraper/dispatch/dispatcher.py::_cleanup_orphan_temps` :136, `personalscraper/dispatch/run.py::_cleanup_staging_orphans` :31, `personalscraper/pipeline.py::_recover_from_previous_run` :202, and the `dispatch/__init__.py` marker set. Markers `_tmp_dispatch_*` / `_tmp_ingest_*` verified in `dispatch/dispatcher.py`, `dispatch/run.py`, `dispatch/__init__.py`, `pipeline.py`.
- Provider-ID identity guard (§7): `personalscraper/dispatch/_identity.py` ("Provider-ID identity guard for destructive dispatch overwrites (§7)") — becomes the `identity_guard` hook on `DispatchSpec`.
- `DispatchSpec`/`_dispatch_item`: NEW symbols (verified no existing `_dispatch_item`/`class DispatchSpec` in `personalscraper/dispatch/`).

## Tasks

1. **P2.1 — F1 test-first: TV merge-overwrite journaled.** Write a failing test that a TV merge-overwrite (an existing episode replaced during merge) appends an `OP_OVERWRITE` row via `record_destruction` — mirroring the movie-replace journal assertion. Prove it fails against current `_tv.py` (no journal). Keep the P0 characterization (which pinned "TV not journaled") — this phase deliberately changes that behaviour, so update the P0 characterization to the new expectation in the same commit and note the intentional change. Verify: new F1 test fails first, then (after P2.3) passes.
2. **P2.2 — `DispatchSpec` + `_dispatch_item` template.** Add `DispatchSpec` (fields: `media_type`, `existing_action: Literal["replaced","merged"]`, `transfer_fn`, `identity_guard`, `canonical_name_rule`, `journal_op`) and `_dispatch_item(dispatcher, src, category_id, spec) -> DispatchResult` in `personalscraper/dispatch/` (e.g. `_item.py`). Extract the shared scaffold (existing-folder detection, identity guard, transfer, journal, result build) into the template; keep replace/merge as the only divergent `transfer_fn` strategies. Verify: `pytest tests -k "dispatch_item or dispatch_spec" -q`; the P0 dispatch characterization still green for the non-journal fields (paths, actions).
3. **P2.3 — Rewire movie + TV through the template.** Make `_movie.py::dispatch_movie` and `_tv.py::dispatch_tvshow` thin wrappers building their `DispatchSpec` and calling `_dispatch_item`; the journal call lives ONCE in the template (reached by both). Verify: F1 test (P2.1) now passes; movie-replace journal behaviour byte-identical; `rg -n "record_destruction" -g '*.py' personalscraper/dispatch/` shows the call in the template, not duplicated per family.
4. **P2.4 — Single orphan sweep.** Create one sweep (e.g. `personalscraper/dispatch/crash_recovery.py::sweep_orphans(roots, *, patterns, dry_run)`) with a declarative artifact table (marker prefix, roots, dry-run policy) covering `_tmp_dispatch_*`, `_tmp_ingest_*` and stale locks. Invoke it ONCE per run at a defined point (pipeline boot / standalone step entry), removing `_cleanup_orphan_temps` (:136), `_cleanup_staging_orphans` (:31) and folding `_recover_from_previous_run` (:202) into the single call. Verify: `pytest tests -k "orphan or crash_recovery or cleanup_temps" -q`; markers appear in exactly one sweep function; no double-execution per run.
5. **P2.5 — Identity guard as a spec hook.** Wire `dispatch/_identity.py` in as the `identity_guard` on the movie `DispatchSpec` (and TV where a provider-ID overwrite guard applies), preserving the §7 provider-ID overwrite protection exactly. Verify: existing identity-guard tests green; a wrong-provider-ID overwrite is still blocked.
6. **P2.6 — Green + module-size.** Full gate; confirm no dispatch module exceeds 800 non-blank LOC after the extraction. Verify: `python3 scripts/check-module-size.py` no new dispatch finding.

## Non-goals

- Do not change the rsync argv construction or the staged-commit/rollback primitives in
  `_transfer.py` (crash-safety; audit strength — keep byte-identical).
- Do not touch the dispatch step-policy/permit resolution (that was P1's F2) beyond calling
  the now-single-owner functions.
- Do not alter move rules (movies replace, TV merge, new→most-free-disk) — only how the
  journal and orphan sweep are shared.
- Do not journal non-destructive operations (append-only trace is for destructions only).

## Commit

```
test(solidify): failing regression F1 — TV merge-overwrite must be journaled
refactor(solidify): _dispatch_item template + DispatchSpec; journal both destruction paths
refactor(solidify): single crash-recovery orphan sweep, one invocation per run
```

Phase-gate commit:

```
chore(solidify): phase 2 gate — dispatch item template + journal parity (F1) + single orphan sweep
```
