# Phase 6 — Scraper cycle → `fail_under = 60`

**Type**: cycle
**Effort**: L (~1.5 day)
**Entry**: Phase 5 done. `fail_under = 50`. CI green.
**Exit**:

- Coverage of `personalscraper/scraper/` lifts global to ≥ 60.
- Critical gaps closed: `tv_service.py` (15 → ≥ 70 %), `trailer_finder.py` (27 → ≥ 70 %), `confidence.py`, `keywords_cache.py`, `youtube_search.py`, `ytdlp_downloader.py`.
- Design-contract tests for sections of `docs/reference/scraping.md` (codename: `scraper`).
- `fail_under` bumped 50 → 60.

## Detail-at-phase-start

1. `python3 scripts/audit_design_coverage.py | grep "docs/reference/scraping.md"` — orphan section list.
2. `make test-cov` then `coverage report --show-missing | sort -k4 -n | head -30` — identifies the worst modules.
3. The output of (1-2) becomes the work backlog.

## Targeted modules

- `tv_service.py` — TV show scraping path (was 15 % at PR #19 baseline). Already partially addressed by PR #19 typed migration.
- `trailer_finder.py` — TMDB → YouTube trailer resolution.
- `ytdlp_downloader.py` — Cookie management, download error handling.
- `confidence.py` — Already addressed by PR #19 (typed signatures); fill remaining branch gaps.
- `keywords_cache.py` — TTL refresh, corrupt-file recovery.
- `youtube_search.py` — Search ranking and dedup.

## Task template

Same as Phase 5: contract tests against `docs/reference/scraping.md` sections, unit tests filling the worst branches, then bump.

## Task 6.X — Bump `fail_under` to 60

- [ ] `make test-cov` passes at ≥ 60.
- [ ] Edit `pyproject.toml`: `fail_under = 60`.
- [ ] Commit:

```
chore(test-coverage): cycle 2 — scraper, bump fail_under to 60
```

## Task 6.Y — Phase 6 gate

- [ ] `make check` green at `fail_under = 60`.
- [ ] Audit script: scraper orphan count reduced to `skip_audit` entries.
- [ ] Map `--check` clean.
- [ ] Milestone commit:

```
chore(test-coverage): phase 6 gate — scraper cycle done (fail_under=60)
```
