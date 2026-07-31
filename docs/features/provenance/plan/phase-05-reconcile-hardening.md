# Phase 5 — Reconcile + advisory-overlay hardening

## Gate

`make lint` + `make test` green. New tests rouge-avant. **ACC-01, ACC-03, ACC-04,
ACC-06** all proven. This is the phase-gate that certifies the advisory invariants.

## Goal

Prune stale rows (FS=truth) and lock the advisory-overlay invariants with an
end-to-end test so no future change can regress them.

## Sub-phases

### 5.1 — Prune stale

- Wire `store.provenance.prune_stale(Path.exists)` into the post-dispatch reconcile
  (or a maintenance sweep): rows whose `current_path` no longer exists on disk are
  removed (status can go 'reconciled' first for audit, then pruned). The FS is NEVER
  mutated to match the DB.
- Test: a row whose path was deleted is pruned; a present-path row survives.

### 5.2 — Advisory-overlay E2E invariants

- `tests/integration/acquire/test_provenance_advisory.py`:
  - **ACC-01**: run the full follow→grab→ingest→scrape→dispatch E2E with the
    `staging_provenance` table EMPTIED before scrape → behaviour identical to the
    #29 path (no crash, correct fallback).
  - **ACC-03**: inject a raising provenance store at each write point (grab/ingest/
    sort/dispatch) → every step's own result is unchanged (best-effort proven).
  - **ACC-04**: prune removes only stale rows; disk untouched.
  - **ACC-06**: a full direct/manual grab (no wanted) → no row ever created, pipeline
    byte-for-byte identical to `main`.

## Feature-PR

After this gate, `/implement:feature-pr` (local gate + push + PR + CI), then
`/implement:pr-review` (adversarial review — MANDATORY, this is a new subsystem — +
fix loop + manual squash merge per the chosen merge mode).
