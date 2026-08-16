# Phase 3 — Sort/rename + dispatch write points

## Gate

`make lint` + `make test` green. New tests rouge-avant. No regression on sort/dispatch
outcomes. Manual/direct items (no row) untouched.

## Goal

Keep `current_path` live through the sort/rename step, and record `dispatch_path` at
dispatch — both best-effort.

## Sub-phases

### 3.1 — Sort/rename keeps current_path live

- In the sorter/rename path, when a staging folder tracked by provenance is moved/
  renamed, call `store.provenance.set_current_path(H, new_path)`. Match the row by the
  OLD path (`by_path`) before the move; if no row, skip (untracked/direct item).
- The hash isn't on the filesystem; resolve it via `by_path(old_path)` → row → H.
- Best-effort; the sort result is unchanged.

### 3.2 — Dispatch records final path

- In dispatch, after a successful move/merge/replace, call
  `store.provenance.set_dispatch(H, dispatch_path=target_path)` for the tracked item
  (resolve via `by_path` on the pre-dispatch staging path). Set status='dispatched'.
- Best-effort; the dispatch result + `ItemDispatched` event are unchanged.

## Tests (rouge-avant)

- `tests/acquire/test_provenance_writes.py` (extend): after a rename,
  `by_path(new_path)` returns the row (old path no longer matches); after dispatch,
  `dispatch_path` is set + status='dispatched'.
- Negative: an untracked folder rename/dispatch creates no row and does not raise.
- Best-effort: a `set_current_path`/`set_dispatch` raising does not fail the step.
