# Phase 4 — #30 consumer: deterministic scrape identity resolver

## Gate

`make lint` + `make test` green. New tests rouge-avant. **ACC-02** (determinism) +
**ACC-05** (movies) + **ACC-01/ACC-06** (fall back / untouched) all asserted.

## Goal

Make the scrape resolve identity from provenance FIRST, deterministically, falling
back to the #29 follow-provenance resolver, then free match. This delivers #30.

## Sub-phases

### 4.1 — Provenance resolver

- `_build_provenance_resolver(config) -> Callable[[Path], MediaRef | None]`
  (`personalscraper/scraper/run.py` alongside `_build_follow_tvdb_resolver`): opens the
  acquire store, returns a closure that does `store.provenance.by_path(show_dir)` →
  the grab-time `media_ref` (or None). Fail-soft: any error → None.

### 4.2 — Wire ahead of #29 (series AND movies)

- In `scraper/orchestrator.py` identity resolution: try the provenance resolver first
  → if it yields a `media_ref` with a tvdb/tmdb, force that identity
  (`scrape_tvshow_forced` for series; the movie forced-identity path for films). On
  None, fall through to the existing `_follow_tvdb_resolver` (#29), then free match.
- Movies gain a deterministic identity here (they had none) — strengthens #28.

## Tests (rouge-avant)

- `tests/integration/acquire/test_provenance_scrape.py`:
  - **ACC-02**: a provenance row (tvdb T) for a RENAMED staging folder → the scrape
    forces T, with NO title/episode inference (works even when the folder title would
    NOT match #29);
  - **ACC-05**: a movie provenance row (tmdb M) → forced M;
  - **ACC-01**: with the provenance row absent, resolution falls back to #29 →
    free match (identical to today);
  - **ACC-06**: an untracked (direct-grab) folder → provenance resolver returns None,
    behaviour identical to `main`.
