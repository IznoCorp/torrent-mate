# Phase 2 — Title Resolution Helper (`acquire/title_resolver.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fail-soft helper in `acquire/` that calls the metadata `provider_registry` (TVDB primary via `TvDetailsProvider`) to resolve a canonical series title from a `MediaRef`. Network/auth/not-found failures always fall back — they never block a follow.

**Architecture:** `acquire/title_resolver.py` is a thin function module. It takes a `MediaRef` and a `ProviderRegistry` (passed in — no `AppContext`), calls `registry.chain(TvDetailsProvider)[0].get_tv(tvdb_id)` for the title, and falls back to a user-supplied title or `"tvdb:<id>"`. Import direction: `acquire/` may import `api/` (the registry lives there) — this is allowed per `acquire/` layering rules.

**Tech Stack:** `TvDetailsProvider` capability from `personalscraper/api/metadata/_contracts.py`, `ProviderRegistry.chain()` from `personalscraper/api/metadata/registry/__init__.py`, `ApiError` + `CircuitOpenError` from `personalscraper/api/_contracts.py`, `MediaDetails` from `personalscraper/api/metadata/_base.py`.

## Gate (start of phase)

Phase 1 delivered: `FollowedSeries.id`, `find_by_ref`, `list_active`, `list_all`, `set_active`, updated Protocol. Verify:

```bash
python -m pytest tests/acquire/ -v
# Expected: all pass, 0 errors

rg "def find_by_ref" personalscraper/acquire/store.py --type py
# Expected: 1 match
```

---

## Task 5: Implement `resolve_series_title` helper

**Files:**

- Create: `personalscraper/acquire/title_resolver.py`
- Create: `tests/acquire/test_title_resolver.py`

### Sub-phase 2.1 — fail-soft title resolver

- [ ] **Step 2.1.1: Write failing tests**

  Create `tests/acquire/test_title_resolver.py`:

  ```python
  """Tests for acquire/title_resolver.py — fail-soft title resolution."""

  from __future__ import annotations

  from unittest.mock import MagicMock

  import pytest

  from personalscraper.api._contracts import ApiError, CircuitOpenError
  from personalscraper.api.metadata._contracts import TvDetailsProvider
  from personalscraper.core.identity import MediaRef


  def _mock_registry(tv_provider):
      """Build a mock ProviderRegistry whose chain(TvDetailsProvider) returns [tv_provider]."""
      registry = MagicMock()
      registry.chain.return_value = [tv_provider]
      return registry


  def _empty_registry():
      """Build a mock ProviderRegistry with no TvDetailsProvider in chain."""
      registry = MagicMock()
      registry.chain.return_value = []
      return registry


  # ---------------------------------------------------------------------------
  # Success path
  # ---------------------------------------------------------------------------


  def test_resolve_returns_provider_title_on_success() -> None:
      """LOAD-BEARING: successful provider call returns the canonical title."""
      from personalscraper.acquire.title_resolver import resolve_series_title

      mock_details = MagicMock()
      mock_details.title = "Breaking Bad"
      mock_provider = MagicMock(spec=TvDetailsProvider)
      mock_provider.get_tv.return_value = mock_details

      registry = _mock_registry(mock_provider)
      ref = MediaRef(tvdb_id=81189)

      result = resolve_series_title(ref, registry)

      assert result == "Breaking Bad"
      mock_provider.get_tv.assert_called_once_with(81189)


  # ---------------------------------------------------------------------------
  # Failure modes — all must fall back, never raise (LOAD-BEARING)
  # ---------------------------------------------------------------------------


  def test_resolve_falls_back_to_supplied_title_on_api_error() -> None:
      """LOAD-BEARING: ApiError → falls back to user-supplied title."""
      from personalscraper.acquire.title_resolver import resolve_series_title

      mock_provider = MagicMock(spec=TvDetailsProvider)
      mock_provider.get_tv.side_effect = ApiError("network timeout")

      registry = _mock_registry(mock_provider)
      ref = MediaRef(tvdb_id=81189)

      result = resolve_series_title(ref, registry, fallback_title="My Show")

      assert result == "My Show", f"Expected 'My Show', got {result!r}"


  def test_resolve_falls_back_to_placeholder_on_api_error_no_title() -> None:
      """LOAD-BEARING: ApiError with no fallback_title → 'tvdb:<id>' placeholder."""
      from personalscraper.acquire.title_resolver import resolve_series_title

      mock_provider = MagicMock(spec=TvDetailsProvider)
      mock_provider.get_tv.side_effect = ApiError("403 forbidden")

      registry = _mock_registry(mock_provider)
      ref = MediaRef(tvdb_id=81189)

      result = resolve_series_title(ref, registry)

      assert result == "tvdb:81189", f"Expected 'tvdb:81189', got {result!r}"


  def test_resolve_falls_back_on_circuit_open() -> None:
      """LOAD-BEARING: CircuitOpenError → falls back to placeholder."""
      from personalscraper.acquire.title_resolver import resolve_series_title

      mock_provider = MagicMock(spec=TvDetailsProvider)
      mock_provider.get_tv.side_effect = CircuitOpenError("tvdb circuit open")

      registry = _mock_registry(mock_provider)
      ref = MediaRef(tvdb_id=12345)

      result = resolve_series_title(ref, registry)

      assert result == "tvdb:12345"


  def test_resolve_falls_back_on_empty_chain() -> None:
      """LOAD-BEARING: no TvDetailsProvider in chain → falls back without crashing."""
      from personalscraper.acquire.title_resolver import resolve_series_title

      ref = MediaRef(tvdb_id=99999)
      result = resolve_series_title(ref, _empty_registry(), fallback_title="Fallback")

      assert result == "Fallback"


  def test_resolve_falls_back_on_generic_exception() -> None:
      """LOAD-BEARING: unexpected exception → falls back, does not propagate."""
      from personalscraper.acquire.title_resolver import resolve_series_title

      mock_provider = MagicMock(spec=TvDetailsProvider)
      mock_provider.get_tv.side_effect = RuntimeError("unexpected bug")

      registry = _mock_registry(mock_provider)
      ref = MediaRef(tvdb_id=11111)

      # Must not raise — any exception is swallowed and falls back.
      result = resolve_series_title(ref, registry)

      assert result == "tvdb:11111"


  def test_resolve_uses_tmdb_id_placeholder_when_no_tvdb() -> None:
      """Placeholder uses tmdb_id when tvdb_id is absent."""
      from personalscraper.acquire.title_resolver import resolve_series_title

      mock_provider = MagicMock(spec=TvDetailsProvider)
      mock_provider.get_tv.side_effect = ApiError("fail")

      registry = _mock_registry(mock_provider)
      ref = MediaRef(tmdb_id=5678)

      result = resolve_series_title(ref, registry)

      assert result == "tmdb:5678"
  ```

- [ ] **Step 2.1.2: Run tests to confirm they fail**

  ```bash
  python -m pytest tests/acquire/test_title_resolver.py -v
  ```

  Expected: FAIL (ImportError — module does not exist yet).

- [ ] **Step 2.1.3: Implement `acquire/title_resolver.py`**

  Create `personalscraper/acquire/title_resolver.py`:

  ```python
  """Fail-soft series title resolver for the acquire lobe (Follow D1).

  Resolves a canonical human-readable title for a :class:`~personalscraper.core.identity.MediaRef`
  by calling the first available ``TvDetailsProvider`` in the metadata
  ``provider_registry`` chain.  Any failure (network, auth, circuit-open,
  not-found, unexpected exception) falls back gracefully — a metadata hiccup
  must **never** block a follow.

  Fallback precedence:
  1. ``fallback_title`` argument (if provided and non-empty).
  2. ``"tvdb:<tvdb_id>"`` when ``tvdb_id`` is set.
  3. ``"tmdb:<tmdb_id>"`` when only ``tmdb_id`` is set.
  4. ``"imdb:<imdb_id>"`` when only ``imdb_id`` is set.

  Import direction: ``acquire/`` imports ``api/`` (allowed) + ``core/`` + stdlib.
  Never imports triage packages (indexer, scraper, commands).

  Logging: ``personalscraper.logger.get_logger`` (NEVER ``structlog.get_logger``).
  """

  from __future__ import annotations

  from typing import TYPE_CHECKING

  from personalscraper.api._contracts import ApiError, CircuitOpenError
  from personalscraper.api.metadata._contracts import TvDetailsProvider
  from personalscraper.core.identity import MediaRef
  from personalscraper.logger import get_logger

  if TYPE_CHECKING:
      from personalscraper.api.metadata.registry import ProviderRegistry

  log = get_logger("acquire.title_resolver")


  def resolve_series_title(
      media_ref: MediaRef,
      registry: "ProviderRegistry",
      *,
      fallback_title: str | None = None,
  ) -> str:
      """Resolve the canonical title for a TV series via the provider registry.

      Calls the first available ``TvDetailsProvider`` in the chain with the
      ``tvdb_id`` from *media_ref*.  Any error (``ApiError``, ``CircuitOpenError``,
      or any unexpected exception) is caught and logged; the function always
      returns a non-empty string.

      Args:
          media_ref: Provider-ID key; ``tvdb_id`` is used for the lookup (primary).
          registry: The live ``ProviderRegistry`` from the composition root.
          fallback_title: Optional user-supplied title string. Used as the first
              fallback when the provider call fails.

      Returns:
          The canonical series title from the provider, the ``fallback_title`` if
          given, or a ``"<provider>:<id>"`` placeholder (e.g. ``"tvdb:81189"``).
      """
      # Determine the id to pass to the provider and the placeholder to use on failure.
      provider_id: int | str | None = media_ref.tvdb_id
      placeholder = _placeholder(media_ref)

      if provider_id is not None:
          providers = registry.chain(TvDetailsProvider)  # type: ignore[type-abstract]
          if providers:
              try:
                  details = providers[0].get_tv(provider_id)
                  title = getattr(details, "title", None)
                  if title:
                      return str(title)
                  # Provider returned details but title is empty/None — fall through.
                  log.warning(
                      "acquire.title_resolver.empty_title",
                      tvdb_id=provider_id,
                  )
              except (ApiError, CircuitOpenError) as exc:
                  log.warning(
                      "acquire.title_resolver.provider_error",
                      tvdb_id=provider_id,
                      error=str(exc),
                  )
              except Exception as exc:  # noqa: BLE001 — fail-soft: must not block a follow
                  log.warning(
                      "acquire.title_resolver.unexpected_error",
                      tvdb_id=provider_id,
                      error=str(exc),
                  )
          else:
              log.debug("acquire.title_resolver.no_tv_provider_in_chain")

      # Fall back: user-supplied title > placeholder.
      if fallback_title:
          return fallback_title
      return placeholder


  def _placeholder(media_ref: MediaRef) -> str:
      """Build a ``"<provider>:<id>"`` placeholder for a :class:`MediaRef`.

      Args:
          media_ref: Provider-ID key.

      Returns:
          E.g. ``"tvdb:81189"``, ``"tmdb:1234"``, or ``"imdb:tt0903747"``.
      """
      if media_ref.tvdb_id is not None:
          return f"tvdb:{media_ref.tvdb_id}"
      if media_ref.tmdb_id is not None:
          return f"tmdb:{media_ref.tmdb_id}"
      return f"imdb:{media_ref.imdb_id}"


  __all__ = ["resolve_series_title"]
  ```

- [ ] **Step 2.1.4: Run tests to confirm they pass**

  ```bash
  python -m pytest tests/acquire/test_title_resolver.py -v
  ```

  Expected: all 7 tests PASS.

- [ ] **Step 2.1.5: Smoke test import + layering**

  ```bash
  python -c "from personalscraper.acquire.title_resolver import resolve_series_title; print('ok')"
  # Expected: ok

  # Verify no triage imports leak in (acquire/ must not import indexer/scraper/commands).
  rg "from personalscraper\.(indexer|scraper|commands|triage)" personalscraper/acquire/title_resolver.py --type py
  # Expected: no matches
  ```

- [ ] **Step 2.1.6: Run lint**

  ```bash
  python -m ruff check personalscraper/acquire/title_resolver.py
  python -m mypy personalscraper/acquire/title_resolver.py
  ```

  Expected: 0 errors each.

- [ ] **Step 2.1.7: Commit**

  ```bash
  git add personalscraper/acquire/title_resolver.py tests/acquire/test_title_resolver.py
  git commit -m "feat(follow-list): add fail-soft resolve_series_title helper"
  ```

---

## Phase 2 completion check

```bash
python -m pytest tests/acquire/test_title_resolver.py tests/acquire/test_store.py -v
# Expected: all tests pass, 0 errors.

python -c "from personalscraper.acquire.title_resolver import resolve_series_title; print('ok')"
# Expected: ok

make lint
# Expected: 0 errors (ruff + mypy).
```
