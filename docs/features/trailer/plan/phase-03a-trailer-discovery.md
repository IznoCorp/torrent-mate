# Phase 3a — Trailer discovery (`trailer_finder`, `youtube_search`, `trailers_cache`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DESIGN §3 (Architecture — scraper layer) and DESIGN §4 (Key Decision §4
— language fallback and two-tier discovery strategy). Create three new modules:
`scraper/trailer_finder.py` (TMDB-first, YouTube fallback), `scraper/youtube_search.py`
(direct YouTube search), and `scraper/trailers_cache.py` (TTL cache for video responses and
search results via `JsonTTLCache`). No download happens here — this phase returns a
YouTube URL string or `None`. All network layers are mocked in tests.

**Architecture:** `TrailerFinder.find(tmdb_id, media_type, title, year, languages) -> str | None`.
Calls `TMDBClient.fetch_movie_videos` / `fetch_tv_videos` per language; falls back to
`YoutubeSearch.search(title, year, query_format)` if TMDB returns no suitable video.
Results cached via `TrailersCache` (backed by `JsonTTLCache`).

**Tech Stack:** Python, `dataclasses`, `pytest`, `ruff`, `mypy`, `requests`.

---

## Gate (entry condition)

Phase 1 and Phase 2 must be complete:

```bash
# Phase 1 gate
python -c "from personalscraper.scraper.tmdb_client import Video, TMDBClient; print('OK')"

# Phase 2 gate
python -c "from personalscraper.scraper.json_ttl_cache import JsonTTLCache; print('OK')"
```

---

## Dependencies

- Phase 1 (provides `Video`, `fetch_movie_videos`, `fetch_tv_videos`)
- Phase 2 (provides `JsonTTLCache`)

---

## Invariants for this phase

- No yt-dlp import anywhere in this phase. Discovery only — no downloading.
- `TrailerFinder` is stateless with respect to disk. It only returns a URL string.
- Existing `tests/scraper/` tests remain green without modification.

---

## Sub-phase 3a.1 — `YoutubeSearch` + fixtures

### Files

| Action | Path                                            | Responsibility                               |
| ------ | ----------------------------------------------- | -------------------------------------------- |
| Create | `personalscraper/scraper/youtube_search.py`     | HTTP-based YouTube search layer              |
| Create | `tests/fixtures/youtube/search_fight_club.json` | Golden fixture for YouTube search response   |
| Create | `tests/scraper/test_youtube_search.py`          | Unit tests (mocked HTTP)                     |

### Step 1: Create `tests/fixtures/youtube/` and golden fixture

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"; mkdir -p "$REPO_ROOT/tests/fixtures/youtube"
```

Write `tests/fixtures/youtube/search_fight_club.json` — a minimal YouTube Data API v3
`search.list` response (only fields used by `YoutubeSearch`):

```json
{
  "items": [
    {
      "id": {"videoId": "6JnN1DmbqoU"},
      "snippet": {"title": "Fight Club - Official Trailer (1999)"}
    },
    {
      "id": {"videoId": "BdJKm16Co6M"},
      "snippet": {"title": "Fight Club - Full Movie Explained"}
    }
  ]
}
```

### Step 2: Write failing tests

Create `tests/scraper/test_youtube_search.py`:

```python
"""Unit tests for YoutubeSearch — direct YouTube search fallback layer.

HTTP transport is fully mocked via unittest.mock.patch on requests.get.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.scraper.youtube_search import YoutubeSearch

FIXTURES = Path(__file__).parent.parent / "fixtures" / "youtube"


def _fixture_response(name: str) -> MagicMock:
    """Build a mock requests.Response from a fixture file."""
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = data
    return mock_resp


class TestYoutubeSearch:
    @pytest.fixture()
    def searcher(self) -> YoutubeSearch:
        return YoutubeSearch(query_format="{title} {year} bande annonce")

    def test_returns_first_video_url(self, searcher):
        """search() returns a YouTube URL for the first result."""
        with patch("requests.get", return_value=_fixture_response("search_fight_club.json")):
            url = searcher.search("Fight Club", 1999)
        assert url == "https://www.youtube.com/watch?v=6JnN1DmbqoU"

    def test_returns_none_on_empty_results(self, searcher):
        """search() returns None when YouTube returns no items."""
        empty = MagicMock()
        empty.ok = True
        empty.json.return_value = {"items": []}
        with patch("requests.get", return_value=empty):
            url = searcher.search("Unknown Movie", 2099)
        assert url is None

    def test_returns_none_on_http_error(self, searcher):
        """search() returns None and logs warning on HTTP failure."""
        error_resp = MagicMock()
        error_resp.ok = False
        error_resp.status_code = 403
        with patch("requests.get", return_value=error_resp):
            url = searcher.search("Fight Club", 1999)
        assert url is None

    def test_query_format_substitution(self, searcher):
        """search() sends a query with title and year substituted."""
        with patch("requests.get", return_value=_fixture_response("search_fight_club.json")) as mock_get:
            searcher.search("Fight Club", 1999)
        call_url = mock_get.call_args[0][0]
        assert "Fight Club" in call_url or "Fight+Club" in call_url
        assert "1999" in call_url

    def test_returns_none_on_connection_error(self, searcher):
        """search() returns None on connection failure."""
        with patch("requests.get", side_effect=ConnectionError("no network")):
            url = searcher.search("Fight Club", 1999)
        assert url is None

    def test_custom_query_format(self):
        """YoutubeSearch respects a custom query format string."""
        s = YoutubeSearch(query_format="{title} {year} trailer")
        with patch("requests.get", return_value=_fixture_response("search_fight_club.json")) as mock_get:
            s.search("Fight Club", 1999)
        call_url = mock_get.call_args[0][0]
        assert "trailer" in call_url
```

### Step 3: Run failing tests

```bash
pytest tests/scraper/test_youtube_search.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError`.

### Step 4: Implement `personalscraper/scraper/youtube_search.py`

**Two-tier strategy (DESIGN §1 + §9):**

1. **Primary** — YouTube Data API v3 `/search.list` with `key={YOUTUBE_API_KEY}`. Without
   the `key=` parameter, googleapis returns HTTP 403 for every request — a bare endpoint
   call *does not work*. The key lives in `.env` and is read by the settings layer.
2. **Fallback** — yt-dlp's built-in `ytsearch1` pseudo-URL
   (`yt_dlp.YoutubeDL({'default_search': 'ytsearch1', 'noplaylist': True})
   .extract_info(query, download=False)`). Triggered when:
   - `YOUTUBE_API_KEY` is unset / empty in the environment, OR
   - primary returns HTTP 403 (quota exhausted), OR
   - primary fails a retriable error (5xx / network) after `http_retry` has exhausted its
     budget.

Quota accounting: each `search.list` costs 100 units against the default 10 000 units/day
allowance; after 100 search calls in a day the API returns 403. We track the number of
quota units consumed in a small sidecar JSON (`.data/youtube_quota.json`, written atomically
via `JsonTTLCache.set` with key `quota:<YYYY-MM-DD>` and TTL 2 days) so the CLI can surface
"you have N units left today" in `trailers verify`. When the tracker projects the next
call would exceed the daily budget, we short-circuit directly to the fallback without
burning a 403.

```python
"""Two-tier YouTube search for trailer discovery.

Primary: YouTube Data API v3 ``search.list`` (requires ``YOUTUBE_API_KEY``).
Fallback: yt-dlp ``ytsearch1`` (no key, no quota, slower).

Returns the first video URL or ``None`` on failure. The fallback is invoked
transparently when the primary is unavailable (no key, quota exceeded, or
HTTP error) — callers do not need to know which tier produced the result.
"""

from __future__ import annotations

import os
import urllib.parse
from datetime import date
from typing import Any

import requests

from personalscraper.logger import get_logger
from personalscraper.scraper.circuit_breaker import CircuitBreaker
from personalscraper.scraper.json_ttl_cache import JsonTTLCache

logger = get_logger(__name__)

_YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"

# Timeout for the primary HTTP call (seconds)
_SEARCH_TIMEOUT_SEC = 10

# Default quota accounting (overridable from config in Phase 7).
_DEFAULT_DAILY_QUOTA_UNITS = 10_000
_DEFAULT_SEARCH_LIST_COST = 100


class YoutubeSearch:
    """Two-tier YouTube searcher — v3 API primary + yt-dlp ytsearch fallback.

    Attributes:
        _query_format: Python str.format template with {title} and {year}.
        _api_key: YouTube Data API v3 key (may be ``""`` to force fallback).
        _quota: JsonTTLCache-backed quota counter (daily reset).
        _breaker: CircuitBreaker dedicated to the YouTube domain.
    """

    def __init__(
        self,
        query_format: str,
        *,
        api_key: str,
        quota_cache: JsonTTLCache,
        breaker: CircuitBreaker,
        daily_quota_units: int = _DEFAULT_DAILY_QUOTA_UNITS,
        search_list_cost_units: int = _DEFAULT_SEARCH_LIST_COST,
    ) -> None:
        """Initialize with a query format string and auth material.

        Args:
            query_format: Template with ``{title}`` and ``{year}`` placeholders.
            api_key: YouTube Data API v3 key. Empty string forces fallback.
            quota_cache: Sidecar cache for today's quota units consumed.
            breaker: Circuit breaker dedicated to YouTube (NOT the TMDB one).
            daily_quota_units: Total units per day (default ``10_000``).
            search_list_cost_units: Units per ``search.list`` call (default ``100``).
        """
        self._query_format = query_format
        self._api_key = api_key
        self._quota = quota_cache
        self._breaker = breaker
        self._daily_quota_units = daily_quota_units
        self._search_list_cost_units = search_list_cost_units

    def search(self, title: str, year: int | None) -> str | None:
        """Search YouTube for a trailer and return the first video URL.

        Args:
            title: Media title to search for.
            year: Release year (substituted into the query format, may be None).

        Returns:
            YouTube watch URL string, or ``None`` on failure / no results.
        """
        year_str = str(year) if year else ""
        query = self._query_format.format(title=title, year=year_str).strip()

        if self._api_key and not self._breaker.is_open() and self._has_quota_left():
            url = self._primary_search(query)
            if url is not None:
                return url
            # Primary reported 403 / exhausted — fall through to fallback.

        return self._fallback_search(query)

    # ------------------------------------------------------------------
    # Primary: YouTube Data API v3
    # ------------------------------------------------------------------

    def _primary_search(self, query: str) -> str | None:
        """Call YouTube Data API v3 ``search.list``. Returns URL or None."""
        encoded_query = urllib.parse.quote_plus(query)
        url = (
            f"{_YOUTUBE_SEARCH_URL}"
            f"?part=snippet&type=video&maxResults=5"
            f"&q={encoded_query}"
            f"&key={self._api_key}"
        )
        try:
            resp = requests.get(url, timeout=_SEARCH_TIMEOUT_SEC)
        except requests.RequestException as exc:
            logger.warning(
                "YouTube primary search transport error — falling back",
                query=query,
                error=str(exc),
            )
            self._breaker.record_failure()
            return None

        # Charge quota once the call reaches the server, even on error paths
        # (Google bills quota even for 403/404 responses on some endpoints).
        self._consume_quota(self._search_list_cost_units)

        if resp.status_code == 403:
            logger.info(
                "YouTube primary search HTTP 403 (quota or key issue) — falling back",
                query=query,
            )
            # Freeze quota for the day to short-circuit future calls.
            self._mark_quota_exhausted()
            return None
        if not resp.ok:
            logger.warning(
                "YouTube primary search HTTP %d — falling back",
                resp.status_code,
                query=query,
            )
            self._breaker.record_failure()
            return None

        try:
            data = resp.json()
        except ValueError:
            logger.warning("YouTube primary returned non-JSON — falling back", query=query)
            return None

        items = data.get("items") or []
        if not items:
            return None
        try:
            video_id = items[0]["id"]["videoId"]
        except (KeyError, TypeError):
            logger.warning(
                "YouTube primary response missing videoId — falling back",
                query=query,
            )
            return None

        self._breaker.record_success()
        return _WATCH_URL.format(video_id=video_id)

    # ------------------------------------------------------------------
    # Fallback: yt-dlp ytsearch1
    # ------------------------------------------------------------------

    def _fallback_search(self, query: str) -> str | None:
        """Use yt-dlp's ``ytsearch1`` pseudo-URL. No quota, no API key."""
        # Import lazily so test environments without yt-dlp still import the module.
        try:
            import yt_dlp
        except ImportError:
            logger.error(
                "YouTube fallback requires yt-dlp; install with `pip install yt-dlp`",
                query=query,
            )
            return None

        opts = {
            "default_search": "ytsearch1",
            "noplaylist": True,
            "quiet": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info: dict[str, Any] | None = ydl.extract_info(query, download=False)
        except yt_dlp.utils.DownloadError as exc:
            logger.warning(
                "YouTube fallback (ytsearch1) failed",
                query=query,
                error=str(exc),
            )
            self._breaker.record_failure()
            return None

        entries = (info or {}).get("entries") or []
        if not entries:
            return None
        first = entries[0]
        video_id = first.get("id")
        if not video_id:
            return None

        self._breaker.record_success()
        return _WATCH_URL.format(video_id=video_id)

    # ------------------------------------------------------------------
    # Quota accounting
    # ------------------------------------------------------------------

    def _quota_key(self) -> str:
        """Return today's quota cache key (UTC date)."""
        return f"quota:{date.today().isoformat()}"

    def _has_quota_left(self) -> bool:
        """Return True when today's consumed units leave room for one more call."""
        consumed = int(self._quota.get(self._quota_key()) or 0)
        return (consumed + self._search_list_cost_units) <= self._daily_quota_units

    def _consume_quota(self, units: int) -> None:
        """Record ``units`` consumed against today's budget."""
        key = self._quota_key()
        consumed = int(self._quota.get(key) or 0)
        # TTL = 36 hours so yesterday's entry can be inspected if needed.
        self._quota.set(key, consumed + units, ttl_seconds=36 * 3600)

    def _mark_quota_exhausted(self) -> None:
        """Pin today's counter to the daily limit to force fallback immediately."""
        self._quota.set(
            self._quota_key(),
            self._daily_quota_units,
            ttl_seconds=36 * 3600,
        )


def youtube_api_key_from_env() -> str:
    """Read ``YOUTUBE_API_KEY`` from the environment.

    Returns an empty string when the key is unset — the caller treats that as
    "skip primary and go straight to fallback".
    """
    return os.environ.get("YOUTUBE_API_KEY", "").strip()
```

The corresponding tests must now cover:

- **API-key path** — primary returns URL on 200 with `{items: [{id: {videoId: "ABC"}}]}`.
- **Quota exhaustion** — after consuming `daily_quota_units`, `_has_quota_left()` is False
  and `search()` jumps to fallback without issuing HTTP.
- **HTTP 403 from primary** triggers `_mark_quota_exhausted()` + fallback.
- **Missing API key** (empty `api_key`) skips primary entirely.
- **Fallback hit** — yt-dlp `extract_info` returns `{entries: [{id: "XYZ"}]}`, URL built.
- **Fallback miss** — yt-dlp returns no entries → `None`.
- **Circuit breaker open** — `breaker.is_open() is True` skips primary (falls back).

The fixture for the "yt-dlp fallback" test case patches
`personalscraper.scraper.youtube_search.yt_dlp.YoutubeDL` with a MagicMock whose
`__enter__().extract_info` returns the canned dict.

### Step 5: Run tests — all must pass

```bash
pytest tests/scraper/test_youtube_search.py -v
```

### Step 6: Commit sub-phase 3a.1

```bash
git add \
  personalscraper/scraper/youtube_search.py \
  tests/scraper/test_youtube_search.py \
  tests/fixtures/youtube/search_fight_club.json
git commit -m "feat(trailer): add YoutubeSearch fallback layer with mocked tests"
```

---

## Sub-phase 3a.2 — `TrailersCache` + tests

### Files

| Action | Path                                         | Responsibility                                        |
| ------ | -------------------------------------------- | ----------------------------------------------------- |
| Create | `personalscraper/scraper/trailers_cache.py`  | TMDB video + YouTube search result caching            |
| Create | `tests/scraper/test_trailers_cache.py`       | Unit tests (tmpdir-based, no HTTP)                    |

### Step 1: Write failing tests

Create `tests/scraper/test_trailers_cache.py`:

```python
"""Unit tests for TrailersCache — TMDB video and YouTube search result caching."""

from pathlib import Path

import pytest

from personalscraper.scraper.tmdb_client import Video
from personalscraper.scraper.trailers_cache import TrailersCache


@pytest.fixture()
def cache(tmp_path: Path) -> TrailersCache:
    return TrailersCache(tmp_path / "trailers_cache.json")


_VIDEO = Video(id="abc", site="YouTube", key="XYZ123", type="Trailer",
               official=True, size=1080, iso_639_1="en")


class TestTmdbVideosCache:
    def test_miss_returns_none(self, cache):
        assert cache.get_tmdb_videos(550, "movie", "en-US") is None

    def test_set_then_get_returns_list(self, cache):
        cache.set_tmdb_videos(550, "movie", "en-US", [_VIDEO])
        result = cache.get_tmdb_videos(550, "movie", "en-US")
        assert result is not None
        assert len(result) == 1
        assert result[0].key == "XYZ123"

    def test_different_languages_are_independent(self, cache):
        cache.set_tmdb_videos(550, "movie", "en-US", [_VIDEO])
        assert cache.get_tmdb_videos(550, "movie", "fr-FR") is None

    def test_different_media_types_are_independent(self, cache):
        cache.set_tmdb_videos(550, "movie", "en-US", [_VIDEO])
        assert cache.get_tmdb_videos(550, "tv", "en-US") is None


class TestYoutubeSearchCache:
    def test_miss_returns_none(self, cache):
        assert cache.get_youtube_search("Fight Club", 1999) is None

    def test_set_then_get_returns_url(self, cache):
        url = "https://www.youtube.com/watch?v=test123"
        cache.set_youtube_search("Fight Club", 1999, url)
        assert cache.get_youtube_search("Fight Club", 1999) == url

    def test_none_url_is_stored(self, cache):
        """A None result (no trailer found) should also be cacheable."""
        cache.set_youtube_search("Obscure Movie", 2020, None)
        # A stored None means "we searched and found nothing" — must not return miss
        result = cache.get_youtube_search("Obscure Movie", 2020)
        # Either the sentinel is stored (result is a sentinel) or None indicates
        # "cached as not found" — the implementation must distinguish miss from stored-None.
        # This test verifies get() does not return None for a stored None (hit vs miss).
        # Implementation uses a sentinel dict {"no_result": True} for this case.
        assert result is not None or cache._has_key(_make_yt_key("Obscure Movie", 2020))
```

> Note: `_make_yt_key` and `cache._has_key` are implementation-internal helpers tested here
> only to verify the stored-None sentinel behavior. The test above documents the intent;
> the implementation can expose `_has_key` as a private method for testability.

### Step 2: Implement `personalscraper/scraper/trailers_cache.py`

```python
"""Cache for TMDB video responses and YouTube search results.

Uses ``JsonTTLCache`` for storage. TMDB video lists are cached for 7 days
(trailers don't change often). YouTube search results are cached for 30 days
(avoids re-querying for items already known to have no trailer).

Key scheme:
    TMDB videos:    ``tmdb_videos:{media_type}:{tmdb_id}:{language}``
    YouTube search: ``yt_search:{title_hash}:{year}``
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from personalscraper.scraper.json_ttl_cache import JsonTTLCache
from personalscraper.scraper.tmdb_client import Video

logger = logging.getLogger(__name__)

_TMDB_TTL_SECONDS = 7 * 24 * 3600       # 7 days
_YOUTUBE_TTL_SECONDS = 30 * 24 * 3600   # 30 days

# Sentinel stored when a YouTube search returned no results, to distinguish
# a "searched and found nothing" hit from a cache miss.
_NO_RESULT_SENTINEL = {"__no_result__": True}


def _tmdb_key(tmdb_id: int, media_type: str, language: str) -> str:
    return f"tmdb_videos:{media_type}:{tmdb_id}:{language}"


def _yt_key(title: str, year: int | None) -> str:
    digest = hashlib.sha1(title.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"yt_search:{digest}:{year or 0}"


class TrailersCache:
    """File-backed cache for TMDB video lists and YouTube search results.

    Thin typed wrapper over ``JsonTTLCache``.

    Attributes:
        _cache: Underlying ``JsonTTLCache`` instance.
    """

    def __init__(self, path: Path) -> None:
        """Initialize the cache backed by ``path``.

        Args:
            path: Absolute path to the backing JSON file.
        """
        self._cache = JsonTTLCache(path)

    # ------------------------------------------------------------------
    # TMDB video lists
    # ------------------------------------------------------------------

    def get_tmdb_videos(
        self, tmdb_id: int, media_type: str, language: str
    ) -> list[Video] | None:
        """Return cached TMDB video list or None on miss.

        Args:
            tmdb_id: TMDB numeric ID.
            media_type: "movie" or "tv".
            language: BCP-47 language tag.

        Returns:
            List of Video instances, or None on cache miss / expiry.
        """
        key = _tmdb_key(tmdb_id, media_type, language)
        raw = self._cache.get(key)
        if raw is None:
            return None
        try:
            return [Video(**v) for v in raw]
        except (TypeError, KeyError) as exc:
            logger.warning("Cannot deserialize cached videos for key %r: %s", key, exc)
            return None

    def set_tmdb_videos(
        self, tmdb_id: int, media_type: str, language: str, videos: list[Video]
    ) -> None:
        """Cache a TMDB video list for 7 days.

        Args:
            tmdb_id: TMDB numeric ID.
            media_type: "movie" or "tv".
            language: BCP-47 language tag.
            videos: List of Video instances to cache.
        """
        key = _tmdb_key(tmdb_id, media_type, language)
        serialized = [
            {
                "id": v.id, "site": v.site, "key": v.key, "type": v.type,
                "official": v.official, "size": v.size, "iso_639_1": v.iso_639_1,
            }
            for v in videos
        ]
        self._cache.set(key, serialized, ttl_seconds=_TMDB_TTL_SECONDS)

    # ------------------------------------------------------------------
    # YouTube search results
    # ------------------------------------------------------------------

    def get_youtube_search(self, title: str, year: int | None) -> str | None:
        """Return cached YouTube URL, or None on cache miss.

        Note: a stored ``None`` (no result found) is returned as the sentinel
        string ``"__no_result__"`` — callers should treat any non-None return
        as a cache hit and check ``is_no_result(url)`` to distinguish.

        Use ``get_youtube_search_hit()`` for the full hit/miss/no-result API.

        Args:
            title: Media title.
            year: Release year, or None.

        Returns:
            YouTube URL string, ``"__no_result__"`` sentinel, or None on miss.
        """
        key = _yt_key(title, year)
        raw = self._cache.get(key)
        if raw is None:
            return None
        if isinstance(raw, dict) and raw.get("__no_result__"):
            return "__no_result__"
        return str(raw)

    def set_youtube_search(self, title: str, year: int | None, url: str | None) -> None:
        """Cache a YouTube search result (URL or no-result) for 30 days.

        Args:
            title: Media title.
            year: Release year, or None.
            url: YouTube URL string, or None if no trailer was found.
        """
        key = _yt_key(title, year)
        value: Any = url if url is not None else _NO_RESULT_SENTINEL
        self._cache.set(key, value, ttl_seconds=_YOUTUBE_TTL_SECONDS)

    def _has_key(self, key: str) -> bool:
        """Return True if the backing cache has the given key (any TTL state).

        Internal helper for tests.

        Args:
            key: Cache key string.

        Returns:
            True if the key is present in the backing file.
        """
        data = self._cache._load()
        return key in data
```

### Step 3: Run tests — all must pass

```bash
pytest tests/scraper/test_trailers_cache.py -v
```

### Step 4: Commit sub-phase 3a.2

```bash
git add \
  personalscraper/scraper/trailers_cache.py \
  tests/scraper/test_trailers_cache.py
git commit -m "feat(trailer): add TrailersCache for TMDB video + YouTube search results"
```

---

## Sub-phase 3a.3 — `TrailerFinder` + tests

### Files

| Action | Path                                         | Responsibility                                       |
| ------ | -------------------------------------------- | ---------------------------------------------------- |
| Create | `personalscraper/scraper/trailer_finder.py`  | TMDB-first / YouTube-fallback discovery orchestrator |
| Create | `tests/scraper/test_trailer_finder.py`       | Unit tests (all dependencies mocked)                 |

### Step 1: Write failing tests

Create `tests/scraper/test_trailer_finder.py`:

```python
"""Unit tests for TrailerFinder — TMDB-first / YouTube-fallback discovery.

All external dependencies (TMDBClient, YoutubeSearch, TrailersCache) are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.scraper.tmdb_client import Video
from personalscraper.scraper.trailer_finder import TrailerFinder

_TRAILER_VIDEO = Video(
    id="abc", site="YouTube", key="TRAILER_KEY", type="Trailer",
    official=True, size=1080, iso_639_1="en"
)
_TEASER_VIDEO = Video(
    id="def", site="YouTube", key="TEASER_KEY", type="Teaser",
    official=True, size=720, iso_639_1="en"
)
_YT_URL = "https://www.youtube.com/watch?v=TRAILER_KEY"


@pytest.fixture()
def finder(tmp_path):
    client = MagicMock()
    searcher = MagicMock()
    from personalscraper.scraper.trailers_cache import TrailersCache
    cache = TrailersCache(tmp_path / "tc.json")
    return TrailerFinder(
        tmdb_client=client,
        youtube_search=searcher,
        cache=cache,
        languages=["fr-FR", "en-US"],
    )


class TestTrailerFinder:
    def test_returns_tmdb_trailer_url(self, finder):
        """find() returns YouTube URL for first Trailer type from TMDB."""
        finder._tmdb_client.fetch_movie_videos.return_value = [_TRAILER_VIDEO]
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL

    def test_tmdb_teaser_used_when_no_trailer(self, finder):
        """find() falls back to Teaser if no Trailer type exists in TMDB results."""
        finder._tmdb_client.fetch_movie_videos.return_value = [_TEASER_VIDEO]
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == "https://www.youtube.com/watch?v=TEASER_KEY"

    def test_youtube_fallback_on_empty_tmdb(self, finder):
        """find() falls back to YouTube search when TMDB returns no videos."""
        finder._tmdb_client.fetch_movie_videos.return_value = []
        finder._youtube_search.search.return_value = _YT_URL
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL

    def test_returns_none_when_both_fail(self, finder):
        """find() returns None when TMDB and YouTube both return nothing."""
        finder._tmdb_client.fetch_movie_videos.return_value = []
        finder._youtube_search.search.return_value = None
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url is None

    def test_language_priority_fr_before_en(self, finder):
        """find() queries fr-FR before en-US and returns on first hit."""
        def fetch_side_effect(tmdb_id, language):
            if language == "fr-FR":
                return [_TRAILER_VIDEO]
            return []
        finder._tmdb_client.fetch_movie_videos.side_effect = fetch_side_effect
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL
        # Only one call (fr-FR) because it already found a result
        assert finder._tmdb_client.fetch_movie_videos.call_count == 1

    def test_tv_show_uses_fetch_tv_videos(self, finder):
        """find() calls fetch_tv_videos for media_type='tv'."""
        finder._tmdb_client.fetch_tv_videos.return_value = [_TRAILER_VIDEO]
        url = finder.find(1399, "tv", title="Game of Thrones", year=2011)
        assert url == _YT_URL
        finder._tmdb_client.fetch_tv_videos.assert_called()

    def test_cache_hit_skips_network(self, finder, tmp_path):
        """find() returns cached URL without calling TMDBClient or YoutubeSearch."""
        # Prime the cache directly
        finder._cache.set_tmdb_videos(550, "movie", "fr-FR", [_TRAILER_VIDEO])
        url = finder.find(550, "movie", title="Fight Club", year=1999)
        assert url == _YT_URL
        finder._tmdb_client.fetch_movie_videos.assert_not_called()
```

### Step 2: Implement `personalscraper/scraper/trailer_finder.py`

The implementation orchestrates: (1) cache check, (2) TMDB per-language, (3) YouTube fallback.

**Public interface:**

```python
class TrailerFinder:
    def __init__(
        self,
        tmdb_client: TMDBClient,
        youtube_search: YoutubeSearch,
        cache: TrailersCache,
        languages: list[str],
    ) -> None: ...

    def find(
        self,
        tmdb_id: int,
        media_type: str,   # "movie" or "tv"
        title: str,
        year: int | None,
    ) -> str | None:
        """Return a YouTube URL for the best available trailer, or None."""
```

**Algorithm (per DESIGN §4):**

1. For each language in `self._languages`:
   a. Check `TrailersCache.get_tmdb_videos(tmdb_id, media_type, language)`.
   b. If cache miss, call `TMDBClient.fetch_movie_videos` or `fetch_tv_videos`; store in cache.
   c. **Filter by `site == "YouTube"` — mandatory**. TMDB `/videos` routinely includes
      Vimeo and DailyMotion entries; we can only build a `youtube.com/watch?v={key}` URL
      for YouTube entries, so any non-YouTube video must be dropped before preference
      selection. This closes the reviewer-flagged hole where `{v.key}` could land on a
      non-existent YouTube URL.
   d. Within the YouTube subset, prefer `official == True`, then `type == "Trailer"`, then
      `type == "Teaser"`. Fall through to any remaining YouTube video.
   e. If a suitable video found: return `https://www.youtube.com/watch?v={key}`.
2. If no TMDB video found across all languages:
   a. Check `TrailersCache.get_youtube_search(title, year)`.
   b. If cache miss, call `YoutubeSearch.search(title, year)`; store result (even None —
      the `__no_result__` sentinel is a module-private singleton, not a magic string, to
      avoid collision with a legitimate URL).
   c. Return URL (or None if no result).

The implementation is approximately 100 lines. Key helpers:

- `_best_video(videos: list[Video]) -> Video | None`:
    1. `youtube_only = [v for v in videos if v.site == "YouTube"]` — drop non-YouTube.
    2. For pass in (`Trailer+official`, `Trailer`, `Teaser+official`, `Teaser`, `any`): return the first match.
- `_video_to_url(v: Video) -> str` — `f"https://www.youtube.com/watch?v={v.key}"`.

### Test contract — public API only

The `TrailerFinder.__init__` signature is public (positional args `tmdb_client`,
`youtube_search`, `cache`, `languages`). Tests may inspect these attributes through the
public `cache` / `tmdb_client` properties exposed on the finder, and may use the public
`TrailersCache` methods (`get_tmdb_videos`, `set_tmdb_videos`, `has_cached_search`) rather
than touching `_has_key` / `_make_yt_key` / other leading-underscore names. If an existing
test uses `_private` access, migrate it to the public surface before merging Phase 3a.

### Step 3: Run tests — all must pass

```bash
pytest tests/scraper/test_trailer_finder.py -v
```

### Step 4: Commit sub-phase 3a.3

```bash
git add \
  personalscraper/scraper/trailer_finder.py \
  tests/scraper/test_trailer_finder.py
git commit -m "feat(trailer): add TrailerFinder with TMDB-first YouTube-fallback discovery"
```

---

## Phase 3a quality gate

- [ ] `pytest tests/scraper/ -q` — all green, no regressions
- [ ] `python -m ruff check personalscraper/scraper/youtube_search.py personalscraper/scraper/trailers_cache.py personalscraper/scraper/trailer_finder.py` — no errors
- [ ] `python -m mypy personalscraper/scraper/trailer_finder.py personalscraper/scraper/trailers_cache.py` — no errors

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/scraper/ -q
python -m ruff check personalscraper/scraper/youtube_search.py \
  personalscraper/scraper/trailers_cache.py \
  personalscraper/scraper/trailer_finder.py
python -m mypy personalscraper/scraper/trailer_finder.py personalscraper/scraper/trailers_cache.py
```

## Milestone commit

```bash
git commit --allow-empty -m "chore(trailer): phase 03a gate — trailer discovery stack (finder + youtube + cache)"
```

## Exit condition for Phase 3b and Phase 3c

Phases 3b and 3c may start only when:

- `TrailerFinder`, `YoutubeSearch`, `TrailersCache` are importable from their respective modules
- `pytest tests/scraper/ -q` exits 0
- The milestone commit is on the branch
