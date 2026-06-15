# Phase 1 — AiredEpisode VO + aired predicate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add the `AiredEpisode` frozen dataclass to `acquire/domain.py` and the `_parse_date` / `_is_aired` helper functions to `acquire/airing.py`, with full unit tests.

**Architecture:** Two small surgical additions — one new frozen VO in the existing domain module, one new module stub with predicate helpers only (no service yet). Tests cover all five air-date boundary cases from DESIGN §8 (past / future / today / empty / malformed).

**Tech Stack:** Python 3.11+, `dataclasses`, `datetime`, `pytest`, `make test`

---

## Gate

_This is Phase 1 — no previous phase gate required._

---

## Sub-phase 1.1 — Add `AiredEpisode` to `acquire/domain.py`

**Files:**

- Modify: `personalscraper/acquire/domain.py` (add after the `FollowedSeries` class)

### Task 1: Add the `AiredEpisode` dataclass

- [ ] **Step 1: Open and read the bottom of `personalscraper/acquire/domain.py` to locate insert point**

  The file does **not** currently import `date` (Step 2 adds it) and has an `__all__` list near the bottom that Step 3 also updates. Add the `AiredEpisode` class after `FollowedSeries` (before `WantedItem`).

- [ ] **Step 2: Add `date` to the existing stdlib imports at the top of `domain.py`**

  The existing import block is:

  ```python
  from __future__ import annotations

  from dataclasses import dataclass
  from typing import Literal

  from personalscraper.core.identity import MediaRef
  ```

  Change to:

  ```python
  from __future__ import annotations

  from dataclasses import dataclass
  from datetime import date
  from typing import Literal

  from personalscraper.core.identity import MediaRef
  ```

- [ ] **Step 3: Add `AiredEpisode` after `FollowedSeries`, before `WantedItem`**

  ```python
  @dataclass(frozen=True)
  class AiredEpisode:
      """A TV episode that has already aired (air-date <= today).

      Emitted by :func:`~personalscraper.acquire.airing.poll_aired`.
      Only episodes whose ``air_date`` has passed (inclusive of today) are
      represented here — unscheduled / future / TBA episodes are never emitted.

      Attributes:
          media_ref: Provider-ID key of the parent followed series (tvdb_id primary).
          season: Season number (1-based; specials / season 0 are excluded by the poller).
          episode: Episode number within the season.
          air_date: The parsed, confirmed air-date (always a real :class:`datetime.date`).
          title: Episode title for display/logging; empty string when the provider
              did not supply one.
      """

      media_ref: MediaRef
      season: int
      episode: int
      air_date: date
      title: str = ""
  ```

  Then add `AiredEpisode` to the module's `__all__` so it is a documented public export
  alongside the other VOs (current value:
  `__all__ = ["FollowedSeries", "RatioState", "SeedObligation", "WantedItem", "WantedKind", "WantedStatus"]`):

  ```python
  __all__ = ["AiredEpisode", "FollowedSeries", "RatioState", "SeedObligation", "WantedItem", "WantedKind", "WantedStatus"]
  ```

- [ ] **Step 4: Verify no import cycle — run the smoke test**

  ```bash
  python -c "from personalscraper.acquire.domain import AiredEpisode; print('OK')"
  ```

  Expected output: `OK`

- [ ] **Step 5: Commit**

  ```bash
  git add personalscraper/acquire/domain.py
  git commit -m "feat(airing): add AiredEpisode frozen VO to acquire/domain"
  ```

---

## Sub-phase 1.2 — Create `acquire/airing.py` stub with predicate helpers (CREATE)

**Files:**

- Create: `personalscraper/acquire/airing.py`
- Create: `tests/acquire/test_airing.py`

### Task 2: Write the failing predicate tests first (TDD)

- [ ] **Step 1: Create `tests/acquire/test_airing.py` with predicate unit tests**

  ```python
  """Tests for acquire/airing.py — aired predicate helpers (Phase 1)."""

  from __future__ import annotations

  from datetime import date


  # ---------------------------------------------------------------------------
  # _parse_date
  # ---------------------------------------------------------------------------


  def test_parse_date_valid_past() -> None:
      """_parse_date returns a date for a valid ISO-8601 string."""
      from personalscraper.acquire.airing import _parse_date

      result = _parse_date("2023-01-15")
      assert result == date(2023, 1, 15)


  def test_parse_date_empty_string_returns_none() -> None:
      """_parse_date returns None for an empty string (TBA / unknown)."""
      from personalscraper.acquire.airing import _parse_date

      assert _parse_date("") is None


  def test_parse_date_malformed_returns_none() -> None:
      """_parse_date returns None for a non-ISO string — never raises."""
      from personalscraper.acquire.airing import _parse_date

      assert _parse_date("January 15, 2023") is None
      assert _parse_date("2023/01/15") is None
      assert _parse_date("not-a-date") is None


  # ---------------------------------------------------------------------------
  # _is_aired
  # ---------------------------------------------------------------------------


  def test_is_aired_past_date_true() -> None:
      """LOAD-BEARING: an episode with a past air-date is aired."""
      from personalscraper.acquire.airing import _is_aired

      today = date(2024, 6, 1)
      assert _is_aired("2023-01-15", today) is True


  def test_is_aired_future_date_false() -> None:
      """LOAD-BEARING: an episode with a future air-date is NOT aired."""
      from personalscraper.acquire.airing import _is_aired

      today = date(2024, 6, 1)
      assert _is_aired("2025-12-31", today) is False


  def test_is_aired_today_boundary_true() -> None:
      """LOAD-BEARING: air_date == today counts as aired (<= today inclusive)."""
      from personalscraper.acquire.airing import _is_aired

      today = date(2024, 6, 15)
      assert _is_aired("2024-06-15", today) is True


  def test_is_aired_empty_string_false() -> None:
      """LOAD-BEARING: empty air_date (TBA) is never aired, never raises."""
      from personalscraper.acquire.airing import _is_aired

      assert _is_aired("", date(2024, 6, 1)) is False


  def test_is_aired_malformed_false() -> None:
      """LOAD-BEARING: malformed air_date is never aired, never raises."""
      from personalscraper.acquire.airing import _is_aired

      assert _is_aired("not-a-date", date(2024, 6, 1)) is False
  ```

- [ ] **Step 2: Run tests to confirm they FAIL (module doesn't exist yet)**

  ```bash
  pytest tests/acquire/test_airing.py -v 2>&1 | head -20
  ```

  Expected: `ImportError` or `ModuleNotFoundError` — `personalscraper.acquire.airing` does not exist.

### Task 3: Create `personalscraper/acquire/airing.py` with predicate helpers only

- [ ] **Step 3: Create `personalscraper/acquire/airing.py`**

  ```python
  """Air-date set-poll service for the acquire lobe (RP9).

  Exposes :func:`poll_aired` — a stateless function that, given a set of
  followed TV series and a metadata ``ProviderRegistry``, returns the list of
  episodes that have already aired (air-date <= today).

  Mirrors :mod:`personalscraper.acquire.title_resolver` in structure:
  no ``AcquireContext`` handle, no store/indexer import.

  Import direction: ``api/metadata`` (downward) + ``acquire.domain`` +
  ``core.identity`` + stdlib ``datetime``.  Never imports store, indexer,
  or any triage package.

  Logging: ``personalscraper.logger.get_logger`` (NEVER ``structlog.get_logger``).
  """

  from __future__ import annotations

  from datetime import date, datetime
  from typing import TYPE_CHECKING, Sequence

  from personalscraper.acquire.domain import AiredEpisode, FollowedSeries
  from personalscraper.api._contracts import ApiError, CircuitOpenError
  from personalscraper.api.metadata._contracts import EpisodeFetcher, TvDetailsProvider
  from personalscraper.logger import get_logger

  if TYPE_CHECKING:
      from personalscraper.api.metadata.registry import ProviderRegistry

  log = get_logger("acquire.airing")


  # ---------------------------------------------------------------------------
  # Predicate helpers (phase 1)
  # ---------------------------------------------------------------------------


  def _parse_date(air_date: str) -> date | None:
      """Parse an ISO-8601 date string from a provider response.

      Args:
          air_date: Raw ``EpisodeInfo.air_date`` string (``"YYYY-MM-DD"`` or ``""``).

      Returns:
          A :class:`datetime.date` on success, ``None`` on empty string or any
          parse failure.  Never raises.
      """
      if not air_date:
          return None
      try:
          return datetime.strptime(air_date, "%Y-%m-%d").date()
      except (ValueError, TypeError):
          return None


  def _is_aired(air_date: str, today: date) -> bool:
      """Return True iff *air_date* is a known past-or-today date.

      Implements the DESIGN §5 predicate:
      ``aired ⇔ air_date != "" AND parse_date(air_date) is not None AND parsed <= today``

      The ``<= today`` comparison is **inclusive**: an episode whose air-date is
      exactly today counts as aired (day-boundary ambiguity is acceptable for
      the calendar-trigger; documented in DESIGN §5).

      Args:
          air_date: Raw ``EpisodeInfo.air_date`` string.
          today: The reference date injected by the caller (no hidden ``date.today()``).

      Returns:
          ``True`` when the episode has aired; ``False`` for TBA / future / malformed.
      """
      parsed = _parse_date(air_date)
      return parsed is not None and parsed <= today


  # poll_aired will be added in phase 2.
  __all__ = ["_is_aired", "_parse_date"]
  ```

- [ ] **Step 4: Run the predicate tests — all must PASS**

  ```bash
  pytest tests/acquire/test_airing.py -v
  ```

  Expected: `8 passed` (3 `_parse_date` + 5 `_is_aired` tests)

- [ ] **Step 5: Run mypy on both new files**

  ```bash
  python -m mypy personalscraper/acquire/airing.py personalscraper/acquire/domain.py --strict
  ```

  Expected: `Success: no issues found`

- [ ] **Step 6: Run ruff on new files**

  ```bash
  python -m ruff check personalscraper/acquire/airing.py tests/acquire/test_airing.py
  ```

  Expected: no errors. If line-length warnings appear, verify `ruff.toml` / `pyproject.toml` sets `line-length = 120`.

- [ ] **Step 7: Commit**

  ```bash
  git add personalscraper/acquire/airing.py tests/acquire/test_airing.py
  git commit -m "test(airing): predicate unit tests + _parse_date / _is_aired helpers"
  ```
