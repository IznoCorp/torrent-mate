# Phase 4 — Scraper flow unification (T1)

## Gate

```bash
make lint && make test && make check

# Residual-import greps for the extracted seams (zero broken references)
rg -n "movie_service\._resolve_external_ids|tv_service\._resolve_external_ids" -g '*.py' personalscraper/ tests/  # 0
rg -n "patch\(.*movie_service.*_family_to_client|patch\(.*tv_service.*_family_to_client" -g '*.py' tests/         # 0 — mock targets moved

python -c "import personalscraper" && echo IMPORT-OK

# ACC hook (DESIGN §10 ACC-03 — one definition of the shared helpers)
test "$(rg -c 'def _?resolve_external_ids' -t py personalscraper/ | wc -l)" = "1" \
 && test "$(rg -c 'def _?family_to_client' -t py personalscraper/ | wc -l)" = "1" && echo ACC-03-OK
```

## Objective

Collapse the two hand-synchronised copies of the one scrape flow into a shared template +
per-type strategies (DESIGN §5 T1): ONE registry-chain matcher (`scraper/_match.py`) that
kills the dead TV path and makes the live TV match emit the same fallback events as
movies; ONE `resolve_external_ids` + `family_to_client` (`scraper/_ids.py`); ONE folder
rename/merge/case-safe block + ONE artwork-recovery helper that takes the provider from
the item's canonical family (`scraper/_writeback.py`); a shared NFO skeleton with id/title
guards defined once. `movie_service.py`/`tv_service.py` shrink to type-specific strategies
(≤400 LOC target each); the 6-mixin `Scraper` keeps its public surface with internals
re-wired and cross-mixin `Any` contracts replaced by injected collaborators. Conformity
fix **F7** (TVDB-only shows recover artwork). Provider-separation rule (TVDB-primary TV,
TMDB info+fallback, IMDB info) preserved — the template changes WHO calls, never the ORDER.

## Findings addressed

SCRAPER-01 (registry chain-iteration boilerplate ×4 ~450 LOC), SCRAPER-02 (dead TV chain
path; live TV match bypasses the registry, no fallback observability), SCRAPER-03 (parallel
near-clones), SCRAPER-04 (folder rename/merge duplicated, inverted `NamingPatterns` use),
SCRAPER-05 (NFO generation + id/title guards duplicated), SCRAPER-09 (artwork recovery
duplicated + TMDB-hardwired; third NFO-id parser), SCRAPER-10 (movie_service/confidence
near the 1000-LOC ceiling; movie_service embeds a raw-SQL restore subsystem), SCRAPER-11
(Scraper god-object, `Any`-typed cross-mixin contracts), MECHANICAL-DUP-05. Conformity fix
F7.

## Code anchors (verified)

- `personalscraper/scraper/movie_service.py` — 983 non-blank LOC (1097 raw): `_resolve_external_ids` :320, `_family_to_client` :347, injected `_recover_movie_artwork` callable :317 (called :643), the `never unlink a drifted NFO before a confident rewrite` guard (~:656-664, webui-overhaul lesson), and the raw-SQL restore subsystem (SCRAPER-10) to extract.
- `personalscraper/scraper/tv_service.py` — 812 non-blank LOC (913 raw): `_resolve_external_ids` :777, `_family_to_client` :802 (verbatim duplicates of the movie versions — SCRAPER-07). The dead registry-chain TV path (`_lookup_series` area) and the live path that bypasses the chain.
- `personalscraper/scraper/tv_service_write.py` — 389 LOC; consumes `_resolve_external_ids`/`_family_to_client` too.
- `personalscraper/scraper/confidence.py` — 979 non-blank LOC (1156 raw); three self-described sections (movie matching / TV matching / shared scoring) — split along that seam (SCRAPER-10/12).
- `personalscraper/scraper/nfo_generator.py` — 853 non-blank LOC; the shared skeleton builder + per-type sections + id/title guards land here.
- Existing shared seams to build on (audit "strengths" — do not fork back): `personalscraper/scraper/decision_triage.py` (`classify_decision_trigger`/`apply_decision_to_result`, used by movie_service :580 + tv_service :467), `personalscraper/scraper/_xref.py` (xref/external-ids/rating free functions), `personalscraper/scraper/_tvdb_convert.py::fetch_show_data` (single TVDB-primary/TMDB-fallback show fetch), `personalscraper/scraper/rename_service.py` (owns `_merge_dirs`/`_rename_dir_case_safe`/`_cleanup_stale_files`).
- New modules (verified absent today): `scraper/_match.py`, `scraper/_ids.py`, `scraper/_writeback.py` (and `scraper/_db_restore.py` for the extracted restore subsystem).
- Public surface to preserve (used by `scraper/run.py` and `commands/scrape_resolve.py`): `process_movies`, `process_tvshows`, `scrape_movie`, `scrape_tvshow`, `scrape_movie_forced`, and the TV forced-resolve entry.
- F7 anchor: artwork recovery is hardwired to TMDB (SCRAPER-09) — the fix reads ids via `nfo_utils.extract_nfo_metadata` once and dispatches to the provider matching the item's canonical family (`tvdb` for TV when present).

Discrepancy note: DESIGN §5 cites "movie_service.py (983) and tv_service.py (812)"; those
are **non-blank** LOC (matching `check-module-size`), while raw `wc -l` shows 1097/913. No
substantive discrepancy — anchors use the non-blank figure the size gate enforces.

## Tasks

1. **P4.1 — memtrace guard.** Before touching `classify`/`extract_stream_info`-adjacent scraper code, diff `get_impact` for the scraper community against the P0 baseline; note any new callers. Verify: no unexpected bridge-symbol caller appears; record in IMPLEMENTATION.md.
2. **P4.2 — `scraper/_ids.py` (ACC-03).** Extract ONE `resolve_external_ids(...)` + `family_to_client(...)` from the verbatim movie/TV copies; make `movie_service`, `tv_service` and `tv_service_write` thin delegates. Update any test that patched `movie_service._family_to_client` / `tv_service._resolve_external_ids` to the new target. Verify: ACC-03 grep returns exactly `1` for each; `rg -n "patch\(.*_service.*_family_to_client" -g '*.py' tests/` == 0.
3. **P4.3 — `scraper/_match.py` (SCRAPER-01/02).** Extract one `run_chain(registry, capability, item_context, attempt, *, source_filter=None) -> T` owning exception classification, `AttemptOutcome` recording, fallback/exhausted event emission and the `ProviderExhausted` raise. Rewire the 3 live sites (movie match, movie details, TV details) onto it; **rewire** the dead `_lookup_series` TV path onto the chain (preserving the settled TVDB-never-overridden rule via chain order) rather than leaving dead code, and fix the stale docstring. The live TV match now emits the same fallback events as movies. Verify: `pytest tests -k "scraper_match or registry_chain or tv_fallback_event" -q`; a TV match now emits a provider-fallback event (assert on the bus).
4. **P4.4 — `scraper/_writeback.py` (SCRAPER-04/09) + F7 test-first.** Move the folder rename/merge/case-safe block into `rename_service` as `apply_canonical_dir_rename(current, canonical_name, *, dry_run, result)`, deriving `canonical_name` on BOTH sides from `patterns.format(...)` with an explicit no-year branch (fixes the inverted `NamingPatterns` use). Write a **failing** test that a TVDB-only show (no TMDB id) recovers artwork; prove it fails against the TMDB-hardwired path. Then fold movie+TV recovery into one `_recover_artwork(nfo_path, dir, result, *, kind)` reading ids via `nfo_utils.extract_nfo_metadata` once and resolving the canonical family first (tvdb for TV when present). Verify: F7 test passes; the P0 scrape write-back characterization still green for movie/TMDB paths.
5. **P4.5 — Shared NFO skeleton (SCRAPER-05/09).** In `nfo_generator.py`, extract `_strip_title_year(title, date)`, `_clean_id(raw)`, and one `_write_uniqueids(root, ids, canonical_family)` used by all three generators (episode's ordered/default logic is the general form; movies pass canonical `imdb`/`tmdb`, shows `tvdb`/`tmdb`); merge the actor/image/cert helper pairs behind a media-kind parameter; apply the id/title guards once (fixes empty-default uniqueids on movies and `Title ()` TV folder names). Remove the third NFO-id parser (reuse `nfo_utils`). Verify: `pytest tests -k "nfo_generator or uniqueids or nfo_golden" -q`; existing NFO goldens unchanged except the previously-buggy cases.
6. **P4.6 — Strategy split (SCRAPER-03/10/11).** Reduce `movie_service.py`/`tv_service.py` to type-specific strategies (candidate filtering, episode mapping for TV, write orchestration order), calling the shared `_match`/`_ids`/`_writeback`/`nfo_generator`. Extract the raw-SQL restore subsystem out of `movie_service.py` into `scraper/_db_restore.py`, routing its query through an indexer-owned lock-free read helper (single-writer discipline). Replace the 6-mixin `Any`-typed cross-mixin contracts with explicit constructor-injected collaborators behind the slim `Scraper` facade, keeping the public surface (`scrape_movie`/`scrape_tvshow`/`scrape_movie_forced`/…). Verify: `pytest tests -k "scraper or scrape_resolve" -q`; `python -c "from personalscraper.scraper.run import *"` OK; forced-resolve produces the same complete write as automatic scrape (P0 characterization).
7. **P4.7 — Split `confidence.py` (SCRAPER-10/12).** Split along its three sections into ≤800-LOC modules (movie matching / TV matching / shared scoring), collapsing the duplicated TMDB-TV fallback scoring loop and the best-of-loop repeated ×4. Verify: `pytest tests -k "confidence or matching_score" -q`.
8. **P4.8 — Green + module-size relief (SCRAPER-10).** Full gate; confirm `movie_service.py`, `tv_service.py`, `confidence.py` are all ≤800 non-blank LOC. Verify: `python3 scripts/check-module-size.py` shows those three resolved.

## Non-goals

- Do not change the provider ORDER or the settled provider-separation rule (TVDB-primary TV,
  TMDB movies/fallback, IMDB info). Only WHO calls the chain changes.
- Do not touch `decision_triage.py`, `_xref.py`, `_tvdb_convert.fetch_show_data` semantics —
  these are the proven shared kernels; reuse, don't fork.
- Do not move the yt-dlp/trailer stack out of `scraper/` — that is P6.
- Do not change the completeness/artwork-presence *read-model* used by verify/indexer/web —
  that is P5 (this phase only fixes the scraper's recovery provider, F7).
- NFO shape may change freely pre-1.0, but only for the enumerated bug cases; no gratuitous
  reshaping of correct NFOs (behaviour-preserving elsewhere).

## Commit

```
refactor(solidify): scraper/_ids.py — one resolve_external_ids + family_to_client (ACC-03)
refactor(solidify): scraper/_match.py — one registry chain; live TV match emits fallback events
test(solidify): failing regression F7 — TVDB-only show recovers artwork
refactor(solidify): scraper/_writeback.py + shared NFO skeleton; movie/tv reduced to strategies
```

Phase-gate commit:

```
chore(solidify): phase 4 gate — scrape-flow unification (match/ids/writeback/NFO) + F7 + size relief
```
