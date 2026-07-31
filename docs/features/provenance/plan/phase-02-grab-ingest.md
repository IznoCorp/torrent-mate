# Phase 2 — Grab + ingest write points

## Gate

`make lint` + `make test` green. New tests rouge-avant. **ACC-06 asserted**: a grab
with no wanted identity creates NO provenance row. No regression on the grab/ingest
result itself.

## Goal

Capture the identity seed at grab and the hash↔folder link at ingest — both
best-effort (a provenance write failure NEVER changes the grab/ingest outcome).

## Sub-phases

### 2.1 — Grab seed

- At the point a grab succeeds with a wanted-derived identity (the acquire
  service/orchestrator grab path, where `info_hash` + `item.media_ref` + `followed_id`
  are known), call `store.provenance.upsert_grab(...)`. Guard: only when the grab
  came from a `wanted` item (follow-driven). A direct/manual add has no such call
  site → no row (ACC-06).
- The write is wrapped best-effort; the grab's `GrabOutcome` / status is unchanged.

### 2.2 — Ingest link

- In the watcher/ingest, when a completed torrent (hash H, known `content_path`) is
  copied into staging, call `store.provenance.set_ingest(H, ingest_path=<staging folder>)`
  ONLY if a provenance row for H exists (`by_hash`); else skip (direct grab). Also set
  `current_path = ingest_path`.
- Best-effort; the ingest result is unchanged whether or not the write succeeds.

## Tests (rouge-avant)

- `tests/acquire/test_provenance_writes.py`:
  - a follow-driven grab creates a row with the wanted identity + followed_id;
  - **ACC-06**: a grab/ingest for a hash with no wanted row creates NO row and the
    step result is identical;
  - a provenance write raising is swallowed (the grab/ingest still succeeds — patch
    the store method to raise, assert the step's own return is unchanged).
- Integration (extend `tests/integration/acquire/`): after a follow-driven grab+ingest,
  `by_path(staging_folder)` returns the row with `current_path == staging_folder`.
