# Phase 1 — Schema + ProvenanceStore

## Gate

`make lint` + `make test` green. New tests rouge-avant. No existing test changes
except additive. `python -c "import personalscraper"` smoke.

## Goal

Add the `staging_provenance` table and a `ProvenanceStore` sub-store on the acquire
store, with fail-soft writes. NO write points wired yet (phase 2+) — this phase is
the substrate + its unit tests only.

## Sub-phases

### 1.1 — Migration

- `personalscraper/acquire/migrations/010_staging_provenance.sql`: `CREATE TABLE
staging_provenance` per DESIGN §3 + `idx_provenance_current_path`. Bump the
  acquire schema version guard.
- Test: a fresh `build_acquire_store` applies migration 010; the table + index exist
  (`tests/acquire/test_migrations.py` additive).

### 1.2 — ProvenanceStore

- `personalscraper/acquire/store.py` (or a new `_provenance_store.py` if the module
  nears the LOC budget): `ProvenanceStore` with:
  - `upsert_grab(info_hash, followed_id, media_ref, kind, grabbed_at)`
  - `set_ingest(info_hash, ingest_path)` · `set_current_path(info_hash, path)`
  - `set_scraped(info_hash, scraped_ref)` · `set_dispatch(info_hash, dispatch_path)`
  - `by_path(path) -> ProvenanceRow | None` · `by_hash(info_hash)` · `prune_stale(exists_fn)`
- All writes wrapped so an exception is logged + swallowed (advisory — never raises to
  a pipeline step). Reads never raise.
- Expose it on the acquire store (e.g. `store.provenance`).
- Domain VO `ProvenanceRow` (frozen) + `MediaRef` json round-trip (reuse
  `_media_ref_to_json` / decode).

## Tests (rouge-avant)

- `tests/acquire/test_provenance_store.py`: upsert-by-hash idempotence; `by_path`
  hit/miss; `set_current_path` updates the live path; `prune_stale` drops rows whose
  `exists_fn` is False and KEEPS present ones; a write whose underlying execute raises
  is swallowed (monkeypatch the conn to raise → method returns without raising).
- MediaRef round-trips (tvdb / tmdb) through the row.
