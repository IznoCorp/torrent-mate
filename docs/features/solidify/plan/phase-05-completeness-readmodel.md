# Phase 5 — Completeness read-model (T4)

## Gate

```bash
make lint && make test && make check

# F5 regression: verify gate and rescraper agree on artwork presence (canonical detection)
command python -m pytest tests -k "artwork_presence and (verify and rescrap)" -q --no-header | grep -E "passed"

# AST/layering guard forbids new local artwork-glob logic outside core
command python -m pytest tests -k "layering and artwork" -q --no-header | grep -E "passed"

python -c "import personalscraper" && echo IMPORT-OK

# ACC hook (DESIGN §10 ACC-04 — one artwork-presence implementation, no local globbing outside core)
test "$(rg -l 'poster\.(jpg|png)' -t py personalscraper/ -g '!core/*' | wc -l)" -le 2 && echo ACC-04-OK
```

## Objective

Make `core/artwork_naming.py` the ENFORCED canonical artwork-presence owner and add a new
`core/completeness.py` (stdlib+core only) with ONE NFO-validity definition and ONE
`media_completeness(dir, media_type)` composing artwork + NFO + renamed-video + trailer
presence (DESIGN §5 T4). Migrate all six artwork-presence sites and the three "NFO valid"
definitions onto the single owners; move the movie-video-renamed check into the verify
check catalog; make the two indexer scan modes write ONE `artwork_json` truth. An
AST/layering test forbids new local artwork-glob logic. This makes DESIGN §9's executable
completeness THE single definition of "acquired". Conformity fix **F5** (verify gate and
rescraper agree on artwork presence via canonical detection).

## Findings addressed

ARTWORK-POSTER-01 (six artwork-presence implementations), ARTWORK-POSTER-02 (verify gate
vs rescraper disagree on "poster present"), ARTWORK-POSTER-03, INDEXER-03 (two scan modes
write divergent artwork_json), VERIFY-MAINTENANCE-02/03/04, SCRAPER-09 (NFO-id parse
convergence, completed here on the read-model side). Conformity fix F5.

## Code anchors (verified)

- `personalscraper/core/artwork_naming.py` (2867 bytes): `artwork_flags(directory) -> dict[str, bool]` :35, `has_poster(directory) -> bool` :60. Self-declared canonical, only 2 adopters today. Target: add `artwork_status(dir, media_type) -> ArtworkStatus` (poster/fanart/landscape presence via canonical detection) and make it the single owner.
- `personalscraper/core/completeness.py`: NEW module (verified absent). Adds `nfo_status(nfo_path) -> NfoStatus` and `media_completeness(dir, media_type) -> Completeness`.
- NFO-validity definitions to converge onto one (strictest live): `personalscraper/nfo_utils.py::is_nfo_complete` :67 (parseable + non-placeholder uniqueid — the canonical one) vs the divergent `personalscraper/indexer/scanner/_modes/enrich.py::_check_nfo_status` :248.
- Six artwork-presence sites (verified present): `personalscraper/verify/checks/artwork.py::PosterPresent` :38 (exact-name check via `ctx.patterns.format("movie_poster", ...)` :59 and `ctx.patterns.tvshow_poster` :63 — the strict gate that must switch to canonical detection; `from_db_row` deriving from `artwork_json` at :75); `personalscraper/maintenance/rescraper.py::_detect_needs` :135 (canonical/loose); `personalscraper/indexer/scanner/_modes/enrich.py` (scan-mode artwork_json writer); a second scan mode (`_modes/full.py` / `_item_stage.py`); `personalscraper/web/staging/read_model.py` (web read-model); and the scraper-side `personalscraper/scraper/existing_validator_drift.py`.
- Verify checker entry: `personalscraper/verify/checker.py::check_movie` :62 (`poster_present, artwork_landscape` inline blocks), `check_tvshow` :87. Verify checks live in `personalscraper/verify/checks/` (`artwork.py`, `base.py`, `catalog.py`, `registry.py`, `nfo.py`, `structure.py`, …).
- Movie-video-renamed check (bolt-on to move into the catalog): currently outside `verify/checks/` (VERIFY-MAINTENANCE-02); lands as a catalog check alongside `artwork.py`/`nfo.py`.
- AST-guard mechanism to mirror: the existing layering test (`tests/.../test_layering.py`) that forbids upward imports — extend the same style to forbid local artwork-glob logic outside `core/artwork_naming.py`.

## Tasks

1. **P5.1 — `core/artwork_naming.artwork_status`.** Add `ArtworkStatus` dataclass + `artwork_status(dir, media_type) -> ArtworkStatus` (canonical poster/fanart/landscape detection covering canonical names, MediaElch names, and `folder.jpg`). Keep `artwork_flags`/`has_poster` as thin wrappers (or migrate their 2 adopters). Unit test canonical + MediaElch + folder.jpg detection. Verify: `pytest tests -k "artwork_status or artwork_naming" -q`.
2. **P5.2 — `core/completeness.py`.** New stdlib+core-only module: `nfo_status(nfo_path) -> NfoStatus` (reusing/aligning the strict `nfo_utils.is_nfo_complete` definition — parseable + uniqueids + title) and `media_completeness(dir, media_type) -> Completeness` composing artwork_status + nfo_status + renamed-video + trailer presence. No imports above `core/`. Verify: `pytest tests -k "completeness" -q`; `python -c "import personalscraper.core.completeness"` OK with no acquire/indexer import.
3. **P5.3 — F5 test-first: verify gate and rescraper agree.** Write a failing test: for a directory whose poster is MediaElch/`folder.jpg`-named, `verify`'s `PosterPresent` and `rescraper._detect_needs` return the SAME presence verdict. Prove it fails (verify strict-exact vs rescraper canonical). Then switch `PosterPresent` (`verify/checks/artwork.py`) and `check_movie`/`check_tvshow` inline blocks to `artwork_status`; align `_detect_needs` to consume `media_completeness`. Verify: F5 test passes; a folder.jpg poster now shows in verify AND is not re-fetched by `rescrape --only artwork`.
4. **P5.4 — Migrate the remaining artwork-presence sites.** Point `web/staging/read_model.py`, `scraper/existing_validator_drift.py`, and both indexer scan modes at `artwork_status`/`media_completeness`; make the two scan modes (`_modes/enrich.py` and the full/item-stage path) write ONE `artwork_json` truth (INDEXER-03). Update tests that patched a local presence helper to the new target. Verify: `pytest tests -k "staging_read_model or scan_enrich or artwork_json" -q`; `artwork_json` identical between the two scan modes for a fixture dir.
5. **P5.5 — NFO-validity convergence.** Replace `enrich.py::_check_nfo_status` with `nfo_status` from `core/completeness.py`; ensure the scraper fast-skip, verify and the indexer all consume the one definition. Verify: `pytest tests -k "nfo_status or nfo_complete or enrich_nfo" -q`.
6. **P5.6 — Movie-video-renamed into the catalog.** Move the movie-video-renamed check into `verify/checks/` as a registered catalog check (consuming `media_completeness`'s renamed-video component). Verify: the check appears in the verify catalog registry test; a not-yet-renamed movie video fails the catalog check exactly as before.
7. **P5.7 — AST guard: no local artwork globbing.** Add a layering/AST test (mirroring `test_layering.py`) that fails if any module outside `core/artwork_naming.py` introduces poster/artwork glob logic, with a pinned allowlist (NamingPatterns formatting + tests). Verify: `pytest tests -k "layering and artwork" -q` green; introduce a temp local `poster.jpg` glob in a scratch module to confirm the guard trips, then revert.
8. **P5.8 — Green + ACC-04.** Full gate; ACC-04 grep ≤ 2. Verify: the gate block above passes end to end.

## Non-goals

- Do not change `ArtworkDownloader.download_image` or `select_best_image` (the canonical
  download/choose paths — audit strength; untouched).
- Do not alter the scraper matching/writeback flow (P4 territory); P5 only unifies the
  *presence/completeness read-model* the scraper's recovery consults.
- Do not move trailer-presence ownership (P6 owns trailer single-truth); `media_completeness`
  merely *reads* filesystem trailer presence as one component.
- Do not touch the scanner walk skeleton (P7) — only the artwork_json truth the enrich
  visitor writes.

## Commit

```
feat(solidify): core/completeness.py — one nfo_status + media_completeness read-model
refactor(solidify): core/artwork_naming.artwork_status becomes the single presence owner
test(solidify): failing regression F5 — verify gate and rescraper agree on artwork presence
test(solidify): AST guard forbids local artwork-glob logic outside core
```

Phase-gate commit:

```
chore(solidify): phase 5 gate — completeness read-model (artwork/NFO/renamed) + F5 + six sites aligned
```
