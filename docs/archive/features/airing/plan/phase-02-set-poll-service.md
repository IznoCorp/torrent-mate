# Phase 2 — The set-poll service

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `poll_aired` in `personalscraper/acquire/airing.py` and add the golden, set-poll aggregate, fail-soft, empty-chain, and season-selection tests from DESIGN §8.

**Architecture:** `poll_aired` is a stateless fan-out: for each `FollowedSeries` with a `tvdb_id`, call `registry.chain(TvDetailsProvider)` → `get_tv` → iterate non-special seasons (`season_number >= 1`) → `registry.chain(EpisodeFetcher)` → `get_episodes` → filter with `_is_aired` → map to `AiredEpisode`. Chain fallback (TVDB-primary → TMDB on empty/error) mirrors `scraper/tv_service_episodes.py::_fetch_season_with_fallback`. Fail-soft per series and per season.

**Tech Stack:** Python 3.11+, `unittest.mock.MagicMock`, `pytest`

---

## Gate

Phase 1 must have produced:

- `personalscraper/acquire/domain.py` — `AiredEpisode` frozen dataclass present.
- `personalscraper/acquire/airing.py` — `_parse_date` and `_is_aired` helpers present and tested.
- `tests/acquire/test_airing.py` — 8 predicate tests passing (3 `_parse_date` + 5 `_is_aired`).

Verify before starting:

```bash
python -c "from personalscraper.acquire.domain import AiredEpisode; print('AiredEpisode OK')"
python -c "from personalscraper.acquire.airing import _is_aired; print('helpers OK')"
pytest tests/acquire/test_airing.py -v --tb=short 2>&1 | tail -5
```

---

## Sub-phase 2.1 — Implement `poll_aired` in `acquire/airing.py`

**Files:**

- Modify: `personalscraper/acquire/airing.py` (add `poll_aired` after the predicate helpers)

### Task 1: Add `poll_aired` to `airing.py`

- [ ] **Step 1: Open `personalscraper/acquire/airing.py` and append `poll_aired` after the existing helpers**

  Replace the final `__all__` line with the full service function plus an updated `__all__`:

  ```python
  def poll_aired(
      series: Sequence[FollowedSeries],
      registry: "ProviderRegistry",
      *,
      today: date,
  ) -> list[AiredEpisode]:
      """Return the list of episodes that have already aired across a set of followed series.

      For each series whose ``media_ref.tvdb_id`` is set, fetches the season catalog
      via ``registry.chain(TvDetailsProvider)`` then fetches episode details per
      non-special season (``season_number >= 1``) via ``registry.chain(EpisodeFetcher)``.
      Episodes are filtered to those whose ``air_date`` is a known past-or-today date
      (DESIGN §5 predicate).

      Provider chain fall-through: if the primary provider returns an empty list for a
      season, the next provider in the chain is tried (mirrors
      ``scraper.tv_service_episodes.fetch_season_with_fallback``).

      Fail-soft: any ``ApiError``, ``CircuitOpenError``, or unexpected ``Exception``
      per series or per season is logged at warning level and skipped — the remaining
      series/seasons are still polled.

      Args:
          series: The set of followed series to poll.  Typically the result of
              ``store.follow.list_active()`` — RP9 does not read the store itself.
          registry: The live ``ProviderRegistry`` from the composition root.
          today: Reference date (injected for determinism/testability — no hidden
              ``date.today()`` call).

      Returns:
          Flat list of :class:`~personalscraper.acquire.domain.AiredEpisode` objects,
          one per aired episode found across all series.  Empty when no episodes have
          aired or all providers are unavailable.
      """
      result: list[AiredEpisode] = []

      for fs in series:
          media_ref = fs.media_ref
          tvdb_id = media_ref.tvdb_id
          if tvdb_id is None:
              log.debug("acquire.airing.skip_no_tvdb_id", title=fs.title)
              continue

          try:
              tv_providers = list(registry.chain(TvDetailsProvider))  # type: ignore[type-abstract]
              if not tv_providers:
                  log.debug("acquire.airing.no_tv_provider", tvdb_id=tvdb_id)
                  continue

              details = tv_providers[0].get_tv(tvdb_id)
              seasons = [s for s in (details.seasons or []) if s.season_number >= 1]

          except (ApiError, CircuitOpenError) as exc:
              log.warning("acquire.airing.poll_failed", tvdb_id=tvdb_id, title=fs.title, error=str(exc))
              continue
          except Exception as exc:  # noqa: BLE001 — fail-soft: one bad series must not block others
              log.warning("acquire.airing.poll_failed", tvdb_id=tvdb_id, title=fs.title, error=str(exc))
              continue

          for season_info in seasons:
              season_num = season_info.season_number
              try:
                  episodes = _fetch_season_with_fallback(tvdb_id, season_num, registry)
              except Exception as exc:  # noqa: BLE001 — fail-soft per season
                  log.warning(
                      "acquire.airing.poll_failed",
                      tvdb_id=tvdb_id,
                      season=season_num,
                      error=str(exc),
                  )
                  continue

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

      return result


  def _fetch_season_with_fallback(
      tvdb_id: int | str,
      season: int,
      registry: "ProviderRegistry",
  ) -> list:
      """Fetch episode list for one season, falling back through the provider chain.

      Tries each ``EpisodeFetcher`` in the chain in order.  A provider is
      considered successful only when it returns a non-empty list — an empty
      response falls through to the next provider (mirrors
      ``scraper.tv_service_episodes.fetch_season_with_fallback``).

      Args:
          tvdb_id: The TVDB series identifier.
          season: Season number to fetch (>= 1; specials excluded upstream).
          registry: The live ``ProviderRegistry``.

      Returns:
          List of :class:`~personalscraper.api.metadata._base.EpisodeInfo` objects,
          or an empty list when no provider returned data.
      """
      fetchers = list(registry.chain(EpisodeFetcher))  # type: ignore[type-abstract]
      for fetcher in fetchers:
          try:
              episodes = fetcher.get_episodes(str(tvdb_id), season)
              if episodes:
                  return episodes
          except (ApiError, CircuitOpenError) as exc:
              log.debug(
                  "acquire.airing.season_provider_error",
                  tvdb_id=tvdb_id,
                  season=season,
                  error=str(exc),
              )
          except Exception as exc:  # noqa: BLE001
              log.debug(
                  "acquire.airing.season_provider_error",
                  tvdb_id=tvdb_id,
                  season=season,
                  error=str(exc),
              )
      return []


  __all__ = ["AiredEpisode", "_is_aired", "_parse_date", "poll_aired"]
  ```

- [ ] **Step 2: Smoke-test the import**

  ```bash
  python -c "from personalscraper.acquire.airing import poll_aired; print('poll_aired OK')"
  ```

  Expected: `poll_aired OK`

---

## Sub-phase 2.2 — Service tests (golden, set-poll, fail-soft, empty-chain, season-selection)

**Files:**

- Modify: `tests/acquire/test_airing.py` (append new test functions)

### Task 2: Add service tests to `tests/acquire/test_airing.py`

- [ ] **Step 3: Append the service test block to `tests/acquire/test_airing.py`**

  ```python
  # ---------------------------------------------------------------------------
  # Helpers shared by service tests
  # ---------------------------------------------------------------------------

  from unittest.mock import MagicMock, call


  def _make_episode(ep_num: int, season_num: int, air_date: str, title: str = "") -> MagicMock:
      """Build a mock EpisodeInfo with known air_date."""
      ep = MagicMock()
      ep.episode_number = ep_num
      ep.season_number = season_num
      ep.air_date = air_date
      ep.title = title
      return ep


  def _make_season(season_number: int) -> MagicMock:
      """Build a mock SeasonInfo."""
      s = MagicMock()
      s.season_number = season_number
      return s


  def _make_registry(tv_provider: MagicMock, ep_fetcher: MagicMock) -> MagicMock:
      """Build a mock ProviderRegistry returning [tv_provider] and [ep_fetcher]."""
      from personalscraper.api.metadata._contracts import EpisodeFetcher, TvDetailsProvider

      def _chain(cap):
          if cap is TvDetailsProvider:
              return [tv_provider]
          if cap is EpisodeFetcher:
              return [ep_fetcher]
          return []

      registry = MagicMock()
      registry.chain.side_effect = _chain
      return registry


  def _make_series(tvdb_id: int, title: str = "Test Show") -> MagicMock:
      """Build a mock FollowedSeries with a MediaRef."""
      from personalscraper.core.identity import MediaRef

      fs = MagicMock()
      fs.title = title
      fs.media_ref = MediaRef(tvdb_id=tvdb_id)
      return fs


  # ---------------------------------------------------------------------------
  # Golden test — assert WHICH episodes (not len > 0)
  # ---------------------------------------------------------------------------


  def test_poll_aired_golden() -> None:
      """LOAD-BEARING golden: past → surfaced, future → absent, today → surfaced, empty/malformed → absent."""
      from datetime import date

      from personalscraper.acquire.airing import poll_aired
      from personalscraper.core.identity import MediaRef

      TODAY = date(2024, 6, 15)
      TVDB_ID = 81189

      ep_past = _make_episode(1, 1, "2023-01-10", "Past Episode")
      ep_future = _make_episode(2, 1, "2025-12-31", "Future Episode")
      ep_today = _make_episode(3, 1, "2024-06-15", "Today Episode")
      ep_empty = _make_episode(4, 1, "", "TBA Episode")
      ep_malformed = _make_episode(5, 1, "not-a-date", "Malformed Episode")

      ep_fetcher = MagicMock()
      ep_fetcher.get_episodes.return_value = [ep_past, ep_future, ep_today, ep_empty, ep_malformed]

      tv_provider = MagicMock()
      details = MagicMock()
      details.seasons = [_make_season(1)]
      tv_provider.get_tv.return_value = details

      registry = _make_registry(tv_provider, ep_fetcher)
      series = [_make_series(TVDB_ID, "Breaking Bad")]

      aired = poll_aired(series, registry, today=TODAY)

      expected_ref = MediaRef(tvdb_id=TVDB_ID)
      aired_episodes = [(e.season, e.episode, e.air_date) for e in aired]

      assert (1, 1, date(2023, 1, 10)) in aired_episodes, "Past episode must be surfaced"
      assert (1, 3, date(2024, 6, 15)) in aired_episodes, "Today episode must be surfaced (inclusive)"
      assert not any(e.episode == 2 for e in aired), "Future episode must be absent"
      assert not any(e.episode == 4 for e in aired), "Empty air_date must be absent"
      assert not any(e.episode == 5 for e in aired), "Malformed air_date must be absent"
      assert all(e.media_ref == expected_ref for e in aired), "media_ref must match the series ref"


  # ---------------------------------------------------------------------------
  # Set-poll aggregate — 2 series, each AiredEpisode carries its series' media_ref
  # ---------------------------------------------------------------------------


  def test_poll_aired_set_poll_aggregate() -> None:
      """LOAD-BEARING: 2-series poll aggregates all aired episodes, each with correct media_ref."""
      from datetime import date

      from personalscraper.acquire.airing import poll_aired
      from personalscraper.core.identity import MediaRef

      TODAY = date(2024, 6, 15)
      TVDB_A, TVDB_B = 81189, 153021

      ep_a = _make_episode(1, 1, "2023-05-01", "Show A Ep1")
      ep_b = _make_episode(1, 2, "2024-03-10", "Show B Ep1")

      def ep_fetcher_side_effect(series_id, season):
          if str(series_id) == str(TVDB_A):
              return [ep_a]
          return [ep_b]

      ep_fetcher = MagicMock()
      ep_fetcher.get_episodes.side_effect = ep_fetcher_side_effect

      tv_provider = MagicMock()

      def get_tv_side_effect(tvdb_id):
          details = MagicMock()
          details.seasons = [_make_season(1)] if tvdb_id == TVDB_A else [_make_season(2)]
          return details

      tv_provider.get_tv.side_effect = get_tv_side_effect

      registry = _make_registry(tv_provider, ep_fetcher)
      series = [_make_series(TVDB_A, "Show A"), _make_series(TVDB_B, "Show B")]

      aired = poll_aired(series, registry, today=TODAY)

      refs = {e.media_ref for e in aired}
      assert MediaRef(tvdb_id=TVDB_A) in refs, "Show A episodes must carry TVDB_A ref"
      assert MediaRef(tvdb_id=TVDB_B) in refs, "Show B episodes must carry TVDB_B ref"
      assert len(aired) == 2, f"Expected exactly 2 aired episodes, got {len(aired)}"


  # ---------------------------------------------------------------------------
  # Fail-soft — one series raises, others still polled
  # ---------------------------------------------------------------------------


  def test_poll_aired_fail_soft_one_series_raises() -> None:
      """LOAD-BEARING: ApiError on one series must NOT propagate — others still polled."""
      from datetime import date

      from personalscraper.api._contracts import ApiError
      from personalscraper.acquire.airing import poll_aired
      from personalscraper.core.identity import MediaRef

      TODAY = date(2024, 6, 15)
      TVDB_GOOD = 153021

      tv_provider = MagicMock()

      def get_tv_side_effect(tvdb_id):
          if tvdb_id == 99999:
              raise ApiError(provider="tvdb", http_status=500, message="server error")
          details = MagicMock()
          details.seasons = [_make_season(1)]
          return details

      tv_provider.get_tv.side_effect = get_tv_side_effect

      ep_fetcher = MagicMock()
      ep_fetcher.get_episodes.return_value = [_make_episode(1, 1, "2023-01-01", "Good Ep")]

      registry = _make_registry(tv_provider, ep_fetcher)
      series = [_make_series(99999, "Bad Show"), _make_series(TVDB_GOOD, "Good Show")]

      aired = poll_aired(series, registry, today=TODAY)

      assert len(aired) == 1, f"Good show must still be polled, got {len(aired)} episodes"
      assert aired[0].media_ref == MediaRef(tvdb_id=TVDB_GOOD)


  # ---------------------------------------------------------------------------
  # Empty chain — chain() returns [] → empty result, no crash
  # ---------------------------------------------------------------------------


  def test_poll_aired_empty_chain_no_crash() -> None:
      """Empty provider chain returns empty list without raising."""
      from datetime import date

      from personalscraper.acquire.airing import poll_aired

      registry = MagicMock()
      registry.chain.return_value = []

      series = [_make_series(81189, "Test Show")]
      aired = poll_aired(series, registry, today=date(2024, 6, 15))

      assert aired == []


  # ---------------------------------------------------------------------------
  # Season selection — excludes season 0, covers non-special seasons
  # ---------------------------------------------------------------------------


  def test_poll_aired_season_selection_excludes_season_zero() -> None:
      """LOAD-BEARING: get_episodes must be called for seasons 1+ and NEVER for season 0."""
      from datetime import date

      from personalscraper.acquire.airing import poll_aired

      TODAY = date(2024, 6, 15)
      TVDB_ID = 81189

      tv_provider = MagicMock()
      details = MagicMock()
      # Catalog includes season 0 (specials) and seasons 1, 2
      details.seasons = [_make_season(0), _make_season(1), _make_season(2)]
      tv_provider.get_tv.return_value = details

      ep_fetcher = MagicMock()
      ep_fetcher.get_episodes.return_value = []

      registry = _make_registry(tv_provider, ep_fetcher)
      series = [_make_series(TVDB_ID)]

      poll_aired(series, registry, today=TODAY)

      called_seasons = [c.args[1] for c in ep_fetcher.get_episodes.call_args_list]
      assert 0 not in called_seasons, f"Season 0 must be excluded but was called: {called_seasons}"
      assert 1 in called_seasons, "Season 1 must be polled"
      assert 2 in called_seasons, "Season 2 must be polled"
  ```

- [ ] **Step 4: Run all airing tests — all must PASS**

  ```bash
  pytest tests/acquire/test_airing.py -v
  ```

  Expected: `13 passed` (8 predicate + 5 service tests)

- [ ] **Step 5: Run mypy on airing.py**

  ```bash
  python -m mypy personalscraper/acquire/airing.py --strict
  ```

  Expected: `Success: no issues found`

- [ ] **Step 6: Run ruff**

  ```bash
  python -m ruff check personalscraper/acquire/airing.py tests/acquire/test_airing.py
  ```

  Expected: no errors.

- [ ] **Step 7: Commit**

  ```bash
  git add personalscraper/acquire/airing.py tests/acquire/test_airing.py
  git commit -m "feat(airing): poll_aired service + golden/set-poll/fail-soft/season-selection tests"
  ```
