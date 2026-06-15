# Phase 5 — PR fixes cycle 1

> Fixes from `/implement:pr-review` cycle 1 (PR #199, 5-lens review). All findings are coherent with DESIGN.md scope — no design contradictions. 0 critical, 0 major, 8 medium retained; ~6 minor/out-of-scope ignored.

**Goal:** Close 3 mutation-proven test-coverage gaps on DESIGN §4/§6/§8 load-bearing behaviors, fix one latent season-source correctness issue, simplify the parse/type-ignore, and tighten per-season error observability + the module docstring.

---

## Gate

Phase 4 complete: `make check` green (6758 passed), PR #199 open, CI green. All 17 airing tests pass.

---

## Sub-phase 5.1 — Code fixes (`acquire/airing.py`)

**Files:** Modify `personalscraper/acquire/airing.py` only.

### Task 1 — apply four surgical code fixes

- [ ] **F-A + F-B — parse once, construct `AiredEpisode.season` from the authoritative requested season, delete the `# type: ignore`.**
      In `poll_aired`'s inner episode loop, replace:

  ```python
  for ep in episodes:
      if _is_aired(ep.air_date, today):
          result.append(
              AiredEpisode(
                  media_ref=media_ref,
                  season=ep.season_number,
                  episode=ep.episode_number,
                  air_date=_parse_date(ep.air_date),  # type: ignore[arg-type]
                  title=ep.title,
              )
          )
  ```

  with (parse once; narrow on the parsed value; use the loop's `season_num`, which is guaranteed ≥ 1 by the season filter, NOT the provider-reported `ep.season_number` which can default to 0):

  ```python
  for ep in episodes:
      parsed = _parse_date(ep.air_date)
      if parsed is not None and parsed <= today:
          result.append(
              AiredEpisode(
                  media_ref=media_ref,
                  season=season_num,
                  episode=ep.episode_number,
                  air_date=parsed,
                  title=ep.title,
              )
          )
  ```

  This removes the redundant second parse, removes `# type: ignore[arg-type]` (mypy now proves `air_date` is a real `date`), and makes `AiredEpisode.season` always the requested non-special season (Decision C / DESIGN §3). `_is_aired` stays as the unit-tested predicate (do NOT delete it).

- [ ] **F-C — per-season error observability.** In `_fetch_season_with_fallback`, raise the `season_provider_error` log from `debug` to `warning`, and add `exc_info=True` on the bare-`Exception` arm (keep the typed `ApiError`/`CircuitOpenError` arm without `exc_info` since `str(exc)` is structured). Also add `exc_info=True` to the bare-`Exception` arm of `poll_aired`'s per-series catch (keep the event name `acquire.airing.poll_failed` per DESIGN §6 — do NOT rename). The typed per-series arm stays as-is.

- [ ] **F-D — module docstring import-direction fix.** The module docstring's "Import direction" line wrongly lists `core.identity` (never imported) and omits `api._contracts`. Replace with the real set, e.g.: `Import direction: api/metadata + api._contracts (downward) + acquire.domain + stdlib datetime. MediaRef reaches this module only transitively via acquire.domain; never imports core.identity, store, or indexer directly.`

- [ ] **Gate 5.1:** `python -m ruff check personalscraper/acquire/airing.py` clean (no F401/no leftover unused `# type: ignore`); `python -m mypy personalscraper/acquire/airing.py --strict` Success (verify the removed `# type: ignore[arg-type]` is genuinely unneeded — mypy must NOT warn about an unused ignore); `python -m pytest tests/acquire/test_airing.py -q` → 17 passed (existing tests unchanged-behavior: they set `ep.season_number == season_num`, so the season-source change is invisible to them; parse-once is behavior-identical).
- [ ] **Commit:** `fix(airing): authoritative season source + parse-once (drop type-ignore) + per-season error observability + docstring`

---

## Sub-phase 5.2 — Test additions (`tests/acquire/test_airing.py`)

**Files:** Modify `tests/acquire/test_airing.py` only.

### Task 2 — add the four missing load-bearing tests (assert WHICH, mutation-sensitive)

- [ ] **F-E — chain fall-through (DESIGN §4).** Add `test_poll_aired_chain_fallthrough_on_empty`: a registry whose `chain(EpisodeFetcher)` returns `[primary, secondary]`; `primary.get_episodes` → `[]`, `secondary.get_episodes` → one known aired episode. Assert the episode IS surfaced AND `secondary.get_episodes` was called. Add `test_poll_aired_chain_short_circuits_on_nonempty`: `primary` returns a non-empty aired list → assert `secondary.get_episodes` is NOT called (`assert secondary.get_episodes.call_count == 0`). (The shared `_make_registry` helper returns a single fetcher — build a 2-fetcher registry inline or extend the helper.)
- [ ] **F-F — per-season fail-soft (DESIGN §6).** Add `test_poll_aired_fail_soft_one_season_raises`: a 2-season show (`details.seasons = [_make_season(1), _make_season(2)]`); `get_episodes` raises `ApiError` for season 1 but returns a known aired episode for season 2. Assert the season-2 episode is still surfaced (the other season is not poisoned). Distinct from the existing per-_series_ fail-soft test.
- [ ] **F-G — no-tvdb_id skip (DESIGN §4).** Add `test_poll_aired_skips_series_without_tvdb_id`: 2 series, one with `MediaRef(tvdb_id=None)` and one valid. Assert only the valid one is polled (`tv_provider.get_tv.call_count == 1`) and no crash. (Use a real `FollowedSeries`-shaped mock with `media_ref=MediaRef(tvdb_id=None)`.)
- [ ] **F-H — multi-season aggregation + season-from-requested (pins F-A).** Add `test_poll_aired_aggregates_multiple_seasons_with_requested_season`: one series, seasons 1 and 2, each `get_episodes` returning a distinct aired episode whose mock `ep.season_number` is set to `0` (divergent from the requested season). Assert BOTH episodes appear AND each `AiredEpisode.season` equals the REQUESTED season (1 and 2 respectively), proving the VO uses `season_num` not `ep.season_number`. This test MUST FAIL against the pre-5.1 code (which used `ep.season_number`) — confirm it pins the fix.
- [ ] **Gate 5.2:** `python -m pytest tests/acquire/test_airing.py -q` → 22 passed (17 + 5 new); `python -m ruff check tests/acquire/test_airing.py` clean. Each new test asserts WHICH episodes/seasons (never `len > 0` alone).
- [ ] **Commit:** `test(airing): cover chain fall-through, per-season fail-soft, no-tvdb skip, multi-season+season-source`

---

## Final gate (main session, phase 5 milestone)

`make check` green + `python -c "import personalscraper"` smoke (design-gaps not needed — no docs/feature_map change). Then mark phase 5 `[x]`.
