# Phase 6 — Trailers ownership + single truth (T5)

## Gate

```bash
make lint && make test && make check

# Residual-import greps for the moved modules (zero matches — ACC-14 representative)
test "$(rg -c 'from personalscraper.scraper.(youtube_search|trailer_finder|ytdlp_downloader)' -t py personalscraper/ tests/ | wc -l)" = "0" && echo ACC-14-OK
rg -n "from personalscraper.scraper.(trailers_cache|json_ttl_cache|keywords_cache)" -g '*.py' personalscraper/ tests/  # 0
rg -n "patch\(.*scraper\.(youtube_search|trailer_finder|ytdlp_downloader)" -g '*.py' tests/  # 0 — mock targets moved

python -c "import personalscraper" && echo IMPORT-OK

# trailers/placement.py os.replace routed through io_utils (ACC-09 progress)
rg -n "os\.replace" -t py personalscraper/trailers/placement.py   # 0

# ACC hook (DESIGN §10 ACC-06-style; F6 — trailers audit can audit existing trailers)
command python -m pytest tests -k "trailers_audit and (existing or fs_probe)" -q --no-header | grep -E "passed"
```

## Objective

Give `trailers/` ownership of its discovery stack and establish a single truth for trailer
existence (DESIGN §5 T5): move `youtube_search.py`, `trailer_finder.py`,
`ytdlp_downloader.py`, `trailers_cache.py` from `scraper/` into `trailers/discovery/`; move
the shared `json_ttl_cache.py` to `core/` and make `keywords_cache` reuse it (kills the
verbatim copy). Filesystem becomes truth for trailer existence (constitution P26); the
indexer `trailer_found` attribute is the derived index (refreshed by scan enrich via T4
`media_completeness`); the state JSON shrinks to a download-attempt ledger. Rebuild
`trailers audit` on a filesystem probe so it can see existing trailers (**F6**,
test-first). Decompose the 455-line `TrailersOrchestrator.run()` into
select→resolve→download→place→record stages (≤80 LOC each) with one `TrailerOutcome`
factory. Placement rules stay in `placement.py`.

## Findings addressed

TRAILERS-01..06 (three unreconciled truths; audit built on the without-trailer query;
455-line run() repeating TrailerState construction; yt-dlp stack misplaced in scraper/),
DOCS-ARCH-DRIFT-07 (stack ownership drift), MECHANICAL-DUP-03 (`keywords_cache` verbatim
copy of the TTL cache), plus `trailers/placement.py` atomic-write (CROSS-CUTTING-02, moved
site). Conformity fix F6.

## Code anchors (verified)

- Stack files in `scraper/` to move (all verified present): `personalscraper/scraper/youtube_search.py`, `trailer_finder.py`, `ytdlp_downloader.py`, `trailers_cache.py`, `json_ttl_cache.py`, `keywords_cache.py`.
- `personalscraper/trailers/` (verified): `orchestrator.py` (`class TrailersOrchestrator` :114, `run(self, items=None) -> dict[str, int]` :200, the 6-outcome ladder incl. `trailers_no_trailer_found` :464), `scanner.py` (queries `item_attribute(key='trailer_found')` :189 — the derived index), `state.py`, `placement.py` (movies flat / TV `Trailers/` — already single-home; `os.replace` present here → route through io_utils), `cli.py` (`audit` :677, `_audit_impl` :538 — built on the items-WITHOUT-trailer query at :582), `step.py`, `events.py`.
- New locations: `personalscraper/trailers/discovery/` (NEW dir) for youtube/finder/ytdlp/trailers_cache; `personalscraper/core/json_ttl_cache.py` (moved from scraper/) consumed by both scraper (keywords) and trailers.
- T4 seam consumed here: `personalscraper/core/completeness.py::media_completeness` (P5) supplies the filesystem trailer-presence component that refreshes `trailer_found` during scan enrich.
- Placement rule invariant (Move Rules / trailers.md): movies flat, TV shows in `Trailers/` subfolder — stays in `placement.py`.

## Tasks

1. **P6.1 — Move the discovery stack.** `git mv` `youtube_search.py`, `trailer_finder.py`, `ytdlp_downloader.py`, `trailers_cache.py` from `scraper/` to `trailers/discovery/`; update all imports (scraper keeps only its TMDB-video capability call). Update mock-patch targets in tests to the new paths. Verify: `rg -c 'from personalscraper.scraper.(youtube_search|trailer_finder|ytdlp_downloader)' -t py personalscraper/ tests/` == 0; `python -c "import personalscraper.trailers.discovery.trailer_finder"` OK.
2. **P6.2 — Move the shared TTL cache to core/.** `git mv scraper/json_ttl_cache.py core/json_ttl_cache.py`; rewrite `keywords_cache` to reuse it (delete the verbatim copy, MECHANICAL-DUP-03); update trailers/scraper imports. Verify: `rg -n "from personalscraper.scraper.json_ttl_cache" -g '*.py' personalscraper/ tests/` == 0; `pytest tests -k "ttl_cache or keywords_cache" -q` green.
3. **P6.3 — F6 test-first: audit sees existing trailers.** Write a failing test that `trailers audit` reports an EXISTING trailer on disk (not just items missing one). Prove it fails against the current without-trailer-query implementation (`cli.py:582`). Then rebuild `_audit_impl`/`audit` on a filesystem probe (via `media_completeness`'s trailer component / `placement`-aware FS walk). Verify: F6 test passes; audit lists existing + missing trailers.
4. **P6.4 — Single truth reconciliation.** Make the filesystem the truth for existence; refresh the indexer `trailer_found` attribute (`scanner.py:189`) from the FS during scan enrich (T4); shrink `state.py`'s JSON to a download-attempt ledger (cooldowns, failures) — never a presence claim. Verify: `pytest tests -k "trailer_found or trailer_state or trailer_truth" -q`; a trailer deleted on disk flips the derived `trailer_found` on next enrich, and the state JSON no longer asserts presence.
5. **P6.5 — Orchestrator decomposition.** Split `TrailersOrchestrator.run()` into `_select`/`_resolve`/`_download`/`_place`/`_record` stages (≤80 LOC each) and collapse the 6-outcome ladder into one `TrailerOutcome` factory; keep placement rules in `placement.py`. Verify: `pytest tests -k "trailers_orchestrator" -q`; the P0 trailer-outcome characterization still green (the six outcomes unchanged in observable behaviour).
6. **P6.6 — Atomic-write for placement (CROSS-CUTTING-02, moved site).** Route `trailers/placement.py`'s `os.replace` through `io_utils.atomic_write_*` / the durable rename helper. Verify: `rg -n "os\.replace" -t py personalscraper/trailers/placement.py` == 0; placement tests green.
7. **P6.7 — Green + module-size.** Full gate; confirm the decomposed orchestrator and moved modules are all ≤800 non-blank LOC. Verify: `python3 scripts/check-module-size.py` no new trailers finding.

## Non-goals

- Do not change placement rules (movies flat / TV `Trailers/`) — only where the code lives.
- Do not touch the scraper TMDB-video capability call that stays in `scraper/`.
- Do not re-model `media_completeness` (P5 owns it); P6 only consumes the trailer component.
- Do not convert the `core/json_ttl_cache.py` `os.replace` to a non-core writer — once in
  `core/`, ACC-09 allows it (excluded by `core/**`).

## Commit

```
refactor(solidify): move yt-dlp/YouTube stack scraper/ -> trailers/discovery/; TTL cache -> core/
test(solidify): failing regression F6 — trailers audit reports existing trailers (FS probe)
refactor(solidify): filesystem is trailer-existence truth; state JSON becomes attempt ledger
refactor(solidify): decompose TrailersOrchestrator.run into select/resolve/download/place/record
```

Phase-gate commit:

```
chore(solidify): phase 6 gate — trailers ownership move + single truth + orchestrator decomposition (F6)
```
