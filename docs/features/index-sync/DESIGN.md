# DESIGN — index-sync (post-dispatch index maintenance hook)

**Codename**: index-sync
**Commit type**: feat
**SemVer bump**: minor (0.37.0 → 0.38.0)
**Status**: design (uncommitted)

## Problem

`personalscraper dispatch` moves freshly-processed media onto the storage disks and
seeds `canonical_provider` + `external_ids_json` into `library.db`, but it does **not**
relink the new `media_file`/`media_release` rows nor reconcile season counts. The index
therefore lags reality until an operator runs, by hand:

```
library-index --mode full --disk <touched> --no-budget   # per touched disk
library-relink --apply
library-fix-season-counts --apply
```

Observed run 2026-06-29: after dispatching 8 items, `library-reconcile` reported
`items_without_files=6` (the freshly dispatched shows/movies had releases but **0 linked
files**). The manual sequence above fixed it (`relink linked=229`, `items_without_files 6→1`,
`fix-season-counts fixed=128`). This manual step is easy to forget and leaves the library
index silently incoherent between dispatch and the next manual maintenance.

## Goal

Automatically run the index-maintenance sequence at the end of `personalscraper dispatch`
(hence also `personalscraper run`), scoped to the disks actually touched by that dispatch,
so newly dispatched items are indexed and linked with no manual step.

## Non-goals

- No change to the dispatch move logic itself (replace/merge/move rules unchanged).
- Not a full library re-scan: only disks touched by the current dispatch are scanned.
- Does not address the standing enrichment backlog (`enrich_stale`) — out of scope.
- Does not change `library-relink` / `library-fix-season-counts` internals; the hook
  composes the existing commands/services.

## Decisions (operator, 2026-06-30)

1. **Scan granularity**: `--mode incremental` restricted to the touched disks. The
   validation phase MUST prove incremental indexes the freshly dispatched items; if an
   item is missed, fall back to `--mode full --disk <disk>` for that disk.
2. **Failure mode**: fail-soft. Dispatch/run stays a success (files already moved). On any
   maintenance error, log a warning and print the manual fallback command. Never fail a
   successful dispatch because of best-effort indexing.
3. **Trigger**: every `dispatch` invocation (so `run` too), only when ≥1 item was actually
   dispatched (moved/merged/replaced). Opt-out via `--no-post-maintenance` CLI flag and a
   config key (default enabled).

## Approach

### Touched-disks collection

`dispatch` already records the target disk per item in `DispatchResult.disk`
(`personalscraper/dispatch/_types.py`). Collect the distinct, non-None `disk` ids of all
items whose action was `moved | merged | replaced`. That set drives the per-disk scan.
If the set is empty (0 dispatched), the hook is a no-op.

### Hook sequence (per dispatch, after the move loop completes)

For each touched disk id `D` (sequential — NEVER parallel; parallel scan dies on the
SQLite writer lock):

1. `library-index --mode incremental --disk D --no-budget`
   - incremental (NOT quick): quick's merkle short-circuit would not re-stage new items and
     a post-maintenance quick scan trips the bulk-restore freeze guard.
   - fallback: if a post-scan check shows a dispatched item on `D` still has no linked
     files, re-run `--mode full --disk D --no-budget` once for that disk.
     Then once, globally (these are fast, DB-only):
2. `library-relink --apply`
3. `library-fix-season-counts --apply`

### Wiring

- Hook lives at the `dispatch` CLI command in `personalscraper/commands/pipeline.py`
  (the `dispatch()` function, ~line 274), invoked after the dispatch run returns its
  results and before the command exits. Because `run` calls the same dispatch path, the
  hook covers both.
- Extract the maintenance sequence into a single reusable function (e.g.
  `personalscraper/dispatch/post_maintenance.py::run_post_dispatch_maintenance(config, touched_disks, *, enabled)`)
  so it is unit-testable in isolation and can be reused by `run`.
- The function composes the existing indexer entry points (the same code paths behind
  `library-index`, `library-relink`, `library-fix-season-counts`) rather than shelling out.

### Config + flag

- New config key under the dispatch/indexer config (final location TBD in plan; e.g.
  `indexer.post_dispatch_maintenance.enabled: bool = true`). Follow the config-overlay
  layout (`docs/reference/config-overlay-layout.md`) — add to the example template and the
  owning overlay file.
- CLI `--no-post-maintenance` flag on `dispatch` (and `run`) overrides config to disable
  for that invocation.
- Resolution order: flag (if passed) > config key > default(true).

### Observability

Emit structured events around the hook: start (with touched-disks list), per-step result
(scan/relink/fix counts), completion, and a fail-soft warning on error. Use
`personalscraper.logger.get_logger` (NOT structlog directly — enforced by check_logging).

### Idempotence / safety

- Re-running dispatch with nothing new → 0 touched disks → hook no-op.
- incremental scan + relink + fix-season-counts are all idempotent (re-run links nothing
  new, fixes nothing).
- Sequential per-disk scan avoids the DB writer-lock crash of parallel mode.
- macFUSE/NTFS ghost-inode noise on Disk1 is ignored (existing behavior).

## ACCEPTANCE (executable; each is a shell command with expected output)

ACC-01 — Flag exists and disables the hook:

```
personalscraper dispatch --help | grep -c -- '--no-post-maintenance'
# expected: 1
```

ACC-02 — Config key present in the example template:

```
grep -rEc "post_dispatch_maintenance|post_maintenance" config.example/ | awk -F: '{s+=$2} END{print (s>0)?"OK":"MISSING"}'
# expected: OK
```

ACC-03 — Hook function is importable and callable with an empty touched-disks set (no-op):

```
python3 -c "from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance; print('import-ok')"
# expected: import-ok
```

ACC-04 — Unit/integration tests for the hook pass:

```
python3 -m pytest tests/ -k "post_dispatch_maintenance or index_sync" -q 2>&1 | tail -1
# expected: a line ending with "passed" and 0 failed
```

ACC-05 — Full quality gate green:

```
make check 2>&1 | tail -3
# expected: lint clean, NNNN passed with 0 failed/errors, module-size + typed-api OK
```

ACC-06 — End-to-end behavioral proof (manual, documented): after a real dispatch of ≥1
item with the hook enabled, `library-reconcile --read-only` reports
`items_without_files` not increased by the dispatched items (the newly dispatched items
have linked files). Recorded in the phase report with before/after `items_without_files`.

## Testing strategy

- Unit: `run_post_dispatch_maintenance` with mocked indexer entry points — asserts (a)
  empty disk set → no scan call, (b) per-disk sequential scan calls for each touched disk,
  (c) incremental mode used, (d) relink + fix-season-counts called once after scans,
  (e) fail-soft: an exception in any step is caught, logged, and does NOT propagate.
- Integration: a temp `library.db` + fake disk tree — dispatch a synthetic item, run the
  hook, assert the item gains linked `media_file` rows (the regression for the 2026-06-29
  `items_without_files=6` symptom).
- Flag/config resolution test: flag overrides config; config default is enabled.
- Regression test reproducing the 2026-06-29 symptom (per the project rule: one test per
  observed bug) — items_without_files before/after the hook.

## Risks

- Incremental scan might not re-stage brand-new dispatched dirs the way full does → the
  validation phase MUST verify and wire the full `--disk` fallback. This is the main
  technical unknown.
- Scan duration on a large touched disk (disk_1 ~12 min for full). incremental should be
  far faster; if not acceptable, the opt-out flag is the escape hatch.
- Writer-lock contention if another indexer process runs concurrently → the hook should
  use the existing `--wait-for-lock` mechanism rather than failing hard.
