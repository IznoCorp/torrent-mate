# DESIGN — Acquisition provenance registry (`provenance`)

**Type**: feat · **Bump**: minor (0.66.2 → 0.67.0) · **Ticket**: kanban #356 · **Subsumes**: #30

## 1. Problem

Between **grab** (a torrent hash is added to the client for a known follow/identity)
and **scrape** (the staging folder needs its TVDB/TMDB identity), the pipeline is
**stateless**: each step re-reads the filesystem and the folder is _renamed_
(sort/clean) along the way. So the link "this staging folder came from this grab"
is **lost** and must be re-inferred at scrape from folder title + episode coverage
(#29). That inference is robust but soft, produced the STSNW #29 and Wicker #28
incidents, and gives movies no deterministic identity at all.

The knowledge exists at **ingest** (the torrent client knows hash → content_path)
but is discarded. This feature persists it as an **advisory provenance registry**
so the scrape can resolve identity **deterministically**.

## 2. Non-negotiable architectural rule — ADVISORY OVERLAY

The registry is a **hint reconciled against the filesystem**, NEVER a second source
of truth. The filesystem stays authoritative; steps stay idempotent by re-reading it.

- Every consumer is **fail-soft**: a missing / stale / path-drifted row yields
  `None` and the caller falls back to today's behaviour (the #29 inference, then
  free match). The registry can only **strengthen** a resolution, never block one.
- The registry is **pruned to match the disk** (a row whose `current_path` no
  longer exists is stale and removed), never the reverse.
- No step's _correctness_ may depend on the registry being present or consistent.
  A wiped `staging_provenance` table degrades the pipeline to exactly its current
  behaviour — this is an ACCEPTANCE invariant, not a hope.
- **MANUAL / DIRECT grabs are NEVER affected (operator constraint).** A torrent
  added OUTSIDE the acquisition flow (a manual/direct add — no `wanted` row, no
  follow identity) has **no provenance seed**, so **no row is created** for it, and
  every step (ingest / scrape / dispatch) behaves EXACTLY as today (free match /
  #29). The spine only ever creates a row when a grab carries a wanted-derived
  identity; it NEVER intercepts or alters the generic grab/ingest/scrape/dispatch
  path. A provenance row is strictly additive metadata on the follow-driven subset.

This preserves the current design's key strength (no DB/FS divergence class of
bugs) while adding determinism when the registry IS consistent — and it guarantees
zero regression on the manual/direct torrent path.

## 3. Data model

Provenance is **per-torrent-hash**, not per-wanted: a season-pack (one hash) maps
to many `wanted` rows but exactly **one** staging folder. New table in `acquire.db`
(migration 010), keyed on the info-hash:

```sql
CREATE TABLE staging_provenance (
    info_hash        TEXT PRIMARY KEY,     -- grabbed torrent hash (lowercase hex)
    followed_id      INTEGER REFERENCES followed_series(id) ON DELETE SET NULL,
    media_ref_json   TEXT,                 -- identity KNOWN at grab (tvdb/tmdb) — the seed
    kind             TEXT CHECK (kind IN ('movie','episode')),
    ingest_path      TEXT,                 -- staging folder the watcher created
    current_path     TEXT,                 -- updated by sort/rename (the live folder)
    scraped_ref_json TEXT,                 -- identity actually scraped (audit / drift)
    dispatch_path    TEXT,                 -- final destination after dispatch
    grabbed_at       INTEGER,
    ingested_at      INTEGER,
    scraped_at       INTEGER,
    dispatched_at    INTEGER,
    status           TEXT CHECK (status IN
                       ('grabbed','ingested','scraped','dispatched','reconciled'))
);
CREATE INDEX idx_provenance_current_path ON staging_provenance(current_path);
```

`ProvenanceStore` (new sub-store on the acquire store): `upsert_grab`, `set_ingest`,
`set_current_path`, `set_scraped`, `set_dispatch`, `by_path(path)`, `prune_stale(exists_fn)`.
All writes are fail-soft (a provenance write NEVER fails a pipeline step — wrapped,
logged, swallowed): the registry is advisory.

## 4. Write points (each fail-soft, best-effort)

| Step                                      | Write                                                                                                                                                                              |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **grab** (orchestrator, on `add` success) | `upsert_grab(hash, followed_id, media_ref, kind, grabbed_at)` — the identity seed is captured when we KNOW it                                                                      |
| **ingest** (watcher, after copy)          | `set_ingest(hash, ingest_path=staging_folder)` — the client's content_path → the staging folder basename links hash↔folder (the knowledge that exists here today and is discarded) |
| **sort/rename**                           | `set_current_path(hash, new_path)` when the folder moves — keeps the live path in sync (the "maj de ligne" that dodges the rename problem)                                         |
| **scrape**                                | READ `by_path(show_dir)` → seed identity; then `set_scraped(hash, scraped_ref)`                                                                                                    |
| **dispatch**                              | `set_dispatch(hash, dispatch_path)`                                                                                                                                                |

Reconcile (opportunistic, post-dispatch or on a maintenance sweep): `prune_stale`
drops rows whose `current_path` no longer exists — the FS is truth.

## 5. Consumers

### 5.1 #30 — deterministic scrape identity (primary)

`_build_provenance_resolver(config) -> Callable[[Path], MediaRef | None]`: given a
staging folder, `by_path(folder)` → the grab-time `media_ref` → force that
tvdb/tmdb. Wired **ahead of** the #29 follow-provenance resolver in
`orchestrator.py` identity resolution; on `None` (row absent / path drift) it falls
through to #29, then free match. **Movies included** — this gives films a
deterministic identity at scrape, strengthening #28 beyond the year filter.

### 5.2 Provenance surface (UI) — later phase / optional

A read endpoint exposing the journey (grabbed → ingested → scraped → dispatched)
per acquisition, feeding a "provenance" view — makes the pipeline legible
(product-intent §pipeline lisible). Read-only, no new write mechanism.

### 5.3 Crash recovery / audit — enabled, not built here

The registry is the substrate for future "resume a stuck item", "re-scrape this
grab", "where did this media come from" features. Out of scope for the MVP; the
schema is designed to support them.

## 6. Phases (outline — the plan expands these)

1. **Schema + store** — migration 010 `staging_provenance` + `ProvenanceStore`
   CRUD (upsert-by-hash, `by_path`, `prune_stale`), advisory-write wrapper. Tests.
2. **Grab + ingest write points** — record the identity seed at grab; link
   hash↔folder at ingest. Fail-soft. Tests proving a write failure never fails
   the step.
3. **Sort/rename + dispatch write points** — keep `current_path` live; record
   `dispatch_path`. Tests.
4. **#30 consumer** — `_build_provenance_resolver`, wired ahead of #29 (fail-soft
   fallback), movies + series. Integration test: provenance row → deterministic
   tvdb; missing row → #29 fallback → free match.
5. **Reconcile + advisory-overlay hardening** — `prune_stale`; the ACCEPTANCE
   invariant "wiped registry ⇒ current behaviour" proven; FS-divergence never
   blocks a step.
6. **Provenance read surface** (optional) — API + minimal UI journey view.

## 7. ACCEPTANCE (executable — filled per phase)

- **ACC-01** (advisory invariant): with `staging_provenance` emptied, the full
  acquisition→scrape→dispatch E2E behaves identically to `main` (fall back to #29).
  `pytest tests/integration/acquire/test_provenance_advisory.py -q` → all pass.
- **ACC-02** (#30 determinism): a grab whose provenance row records tvdb T makes
  the scrape force T for the renamed staging folder — no title/episode inference.
- **ACC-03** (fail-soft write): a provenance-store write raising never fails the
  grab/ingest/sort/scrape/dispatch step (the step's own result is unchanged).
- **ACC-04** (prune): a row whose `current_path` was deleted on disk is pruned;
  the FS is never mutated to match the DB.
- **ACC-05** (movies): a followed movie grabbed with tmdb M scrapes deterministically
  as M via provenance (independent of the #28 year filter).
- **ACC-06** (manual/direct grab untouched — operator constraint): a torrent added to
  the client OUTSIDE the acquisition flow (no wanted row) creates NO provenance row,
  and flows through ingest→scrape→dispatch byte-for-byte identically to `main` (free
  match / #29). No provenance code path executes for it.

## 8. Out of scope

Crash-resume actions, re-scrape-by-grab, full provenance UI beyond a read view.
The schema supports them; they are separate features.
