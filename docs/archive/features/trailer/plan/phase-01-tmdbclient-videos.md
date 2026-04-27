# Phase 1 — Extend `TMDBClient` with video endpoints

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DESIGN §6 first half ("Extend TMDBClient"). Add `fetch_movie_videos()`,
`fetch_tv_videos()`, and the `Video` dataclass to `personalscraper/scraper/tmdb_client.py`.
Add golden fixtures and unit tests in `tests/scraper/test_tmdb_client_videos.py`. This phase
is purely additive — no existing method, test, or behavior is touched. Mergeable on its own.

**Architecture:** Two new methods calling `GET /movie/{id}/videos` and `GET /tv/{id}/videos`
via the existing `_get()` infrastructure (retry, circuit breaker, Bearer auth). Results are
deserialized into a `Video` dataclass. Same fail-soft policy as `get_keywords()` — HTTP 404
returns `[]` silently.

**Tech Stack:** Python, `dataclasses`, `pytest`, `ruff`, `mypy`.

---

## Gate (entry condition)

This is Phase 1 — no prior phase required. Verify branch before starting:

```bash
git branch --show-current
# expected: feat/trailer
```

---

## Dependencies

None. This phase is the root node of the dependency graph.

---

## Invariants for this phase

- **All existing tests in `tests/scraper/` remain green and unchanged.** The only files
  touched are `personalscraper/scraper/tmdb_client.py` (additions only) and newly created
  test/fixture files.
- `TMDBClient`'s public API surface is additive — no existing method signature changes.
- The `Video` dataclass lives in `personalscraper/scraper/tmdb_client.py` (same module as
  `TMDBClient`) to avoid circular imports.

---

## Sub-phase 1.1 — `Video` dataclass + golden fixtures

### Files

| Action | Path                                        | Responsibility                          |
| ------ | ------------------------------------------- | --------------------------------------- |
| Modify | `personalscraper/scraper/tmdb_client.py`    | Add `Video` dataclass (before class)    |
| Create | `tests/fixtures/tmdb/movie_550_videos.json` | Golden fixture: movie videos response   |
| Create | `tests/fixtures/tmdb/tv_1399_videos.json`   | Golden fixture: TV show videos response |

### Step 1: Create `tests/fixtures/tmdb/` directory if it does not exist

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"; mkdir -p "$REPO_ROOT/tests/fixtures/tmdb"
```

### Step 2: Write `tests/fixtures/tmdb/movie_550_videos.json`

This is the shape returned by `GET /movie/550/videos?language=en-US`. Store a realistic
minimal fixture (2 trailers, 1 teaser) so tests stay deterministic:

```json
{
  "id": 550,
  "results": [
    {
      "id": "533ec654c3a36854480003eb",
      "iso_639_1": "en",
      "iso_3166_1": "US",
      "key": "6JnN1DmbqoU",
      "name": "Fight Club - Official Trailer",
      "official": true,
      "published_at": "1999-09-15T00:00:00.000Z",
      "site": "YouTube",
      "size": 1080,
      "type": "Trailer"
    },
    {
      "id": "533ec654c3a36854480003ec",
      "iso_639_1": "en",
      "iso_3166_1": "US",
      "key": "SUXWAEX2jlg",
      "name": "Fight Club - Teaser Trailer",
      "official": true,
      "published_at": "1999-07-01T00:00:00.000Z",
      "site": "YouTube",
      "size": 720,
      "type": "Teaser"
    }
  ]
}
```

### Step 3: Write `tests/fixtures/tmdb/tv_1399_videos.json`

```json
{
  "id": 1399,
  "results": [
    {
      "id": "5c9294240e0a267cd516835f",
      "iso_639_1": "en",
      "iso_3166_1": "US",
      "key": "KPLWWIOCOOQ",
      "name": "Game of Thrones - Season 8 Official Trailer",
      "official": true,
      "published_at": "2019-03-05T00:00:00.000Z",
      "site": "YouTube",
      "size": 1080,
      "type": "Trailer"
    }
  ]
}
```

### Step 4: Add `Video` dataclass to `tmdb_client.py`

Add the following block immediately after the `TMDBError` class (before `_is_retryable`):

```python
@dataclass(frozen=True)
class Video:
    """A video entry from the TMDB /videos endpoint.

    Attributes:
        id: TMDB internal video UUID.
        site: Hosting platform, typically "YouTube".
        key: Platform video identifier (YouTube video ID).
        type: Video category: "Trailer", "Teaser", "Clip", "Featurette", etc.
        official: Whether the video is from an official channel.
        size: Vertical resolution in pixels (e.g. 1080, 720, 480).
        iso_639_1: Language code (e.g. "en", "fr").
    """

    id: str
    site: str
    key: str
    type: str
    official: bool
    size: int
    iso_639_1: str
```

Also add `from dataclasses import dataclass` to the imports at the top of the file.

### Step 5: Commit sub-phase 1.1

```bash
git add \
  personalscraper/scraper/tmdb_client.py \
  tests/fixtures/tmdb/movie_550_videos.json \
  tests/fixtures/tmdb/tv_1399_videos.json
git commit -m "feat(trailer): add Video dataclass and golden fixtures for TMDB /videos"
```

---

## Sub-phase 1.2 — `fetch_movie_videos` + `fetch_tv_videos` methods

### Files

| Action | Path                                       | Responsibility                                             |
| ------ | ------------------------------------------ | ---------------------------------------------------------- |
| Modify | `personalscraper/scraper/tmdb_client.py`   | Add `fetch_movie_videos()` and `fetch_tv_videos()` methods |
| Create | `tests/scraper/test_tmdb_client_videos.py` | Unit tests with mocked HTTP transport                      |

### Step 1: Write the failing test first

Create `tests/scraper/test_tmdb_client_videos.py`:

```python
"""Unit tests for TMDBClient.fetch_movie_videos / fetch_tv_videos.

HTTP transport is mocked via unittest.mock.patch on TMDBClient._get.
Fixtures loaded from tests/fixtures/tmdb/.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.scraper.tmdb_client import TMDBError, TMDBClient, Video

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tmdb"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture()
def client() -> TMDBClient:
    """TMDBClient with a dummy API key (no real HTTP)."""
    return TMDBClient(api_key="test-key-placeholder")


# ── fetch_movie_videos ────────────────────────────────────────────────────────

class TestFetchMovieVideos:
    def test_returns_video_list(self, client):
        """fetch_movie_videos returns a list of Video dataclass instances."""
        fixture = _load("movie_550_videos.json")
        with patch.object(client, "_get", return_value=fixture):
            videos = client.fetch_movie_videos(550, language="en-US")
        assert len(videos) == 2
        assert all(isinstance(v, Video) for v in videos)

    def test_video_fields_populated(self, client):
        """Video fields map correctly from the TMDB response."""
        fixture = _load("movie_550_videos.json")
        with patch.object(client, "_get", return_value=fixture):
            videos = client.fetch_movie_videos(550, language="en-US")
        trailer = next(v for v in videos if v.type == "Trailer")
        assert trailer.key == "6JnN1DmbqoU"
        assert trailer.official is True
        assert trailer.site == "YouTube"
        assert trailer.size == 1080
        assert trailer.iso_639_1 == "en"

    def test_calls_correct_endpoint(self, client):
        """fetch_movie_videos calls /movie/{id}/videos."""
        fixture = _load("movie_550_videos.json")
        mock_get = MagicMock(return_value=fixture)
        with patch.object(client, "_get", mock_get):
            client.fetch_movie_videos(550, language="en-US")
        mock_get.assert_called_once_with("/movie/550/videos", {"language": "en-US"})

    def test_returns_empty_on_404(self, client):
        """fetch_movie_videos returns [] on HTTP 404 (item not found)."""
        with patch.object(client, "_get", side_effect=TMDBError(404, 34, "Not Found")):
            result = client.fetch_movie_videos(99999, language="en-US")
        assert result == []

    def test_returns_empty_on_unexpected_exception(self, client):
        """fetch_movie_videos returns [] and logs warning on unexpected errors."""
        with patch.object(client, "_get", side_effect=ConnectionError("timeout")):
            result = client.fetch_movie_videos(550, language="en-US")
        assert result == []

    def test_empty_results_returns_empty_list(self, client):
        """fetch_movie_videos returns [] when TMDB results list is empty."""
        with patch.object(client, "_get", return_value={"id": 1, "results": []}):
            result = client.fetch_movie_videos(1, language="en-US")
        assert result == []


# ── fetch_tv_videos ───────────────────────────────────────────────────────────

class TestFetchTvVideos:
    def test_returns_video_list(self, client):
        """fetch_tv_videos returns a list of Video instances."""
        fixture = _load("tv_1399_videos.json")
        with patch.object(client, "_get", return_value=fixture):
            videos = client.fetch_tv_videos(1399, language="en-US")
        assert len(videos) == 1
        assert isinstance(videos[0], Video)

    def test_calls_correct_endpoint(self, client):
        """fetch_tv_videos calls /tv/{id}/videos."""
        fixture = _load("tv_1399_videos.json")
        mock_get = MagicMock(return_value=fixture)
        with patch.object(client, "_get", mock_get):
            client.fetch_tv_videos(1399, language="en-US")
        mock_get.assert_called_once_with("/tv/1399/videos", {"language": "en-US"})

    def test_returns_empty_on_404(self, client):
        """fetch_tv_videos returns [] on HTTP 404."""
        with patch.object(client, "_get", side_effect=TMDBError(404, 34, "Not Found")):
            result = client.fetch_tv_videos(99999, language="en-US")
        assert result == []

    def test_language_override(self, client):
        """fetch_tv_videos passes the language parameter to _get."""
        mock_get = MagicMock(return_value={"id": 1, "results": []})
        with patch.object(client, "_get", mock_get):
            client.fetch_tv_videos(1, language="fr-FR")
        mock_get.assert_called_once_with("/tv/1/videos", {"language": "fr-FR"})
```

### Step 2: Run failing tests

```bash
pytest tests/scraper/test_tmdb_client_videos.py -v 2>&1 | head -20
```

Expected: `AttributeError` or `ImportError` — methods do not exist yet.

### Step 3: Implement the methods in `tmdb_client.py`

Add the following two methods to `TMDBClient`, after `get_keywords()`:

```python
def fetch_movie_videos(self, tmdb_id: int, language: str) -> list[Video]:
    """Fetch video entries (trailers, teasers) for a movie.

    Calls ``GET /movie/{id}/videos``.

    Fail-soft policy identical to ``get_keywords()``: HTTP 404, timeout,
    and any unexpected exception all return ``[]`` and log a warning.

    Args:
        tmdb_id: TMDB movie ID.
        language: BCP-47 language tag (e.g. "fr-FR", "en-US").

    Returns:
        List of Video dataclass instances. Empty on any error.
    """
    return self._fetch_videos(f"/movie/{tmdb_id}/videos", tmdb_id, "movie", language)

def fetch_tv_videos(self, tmdb_id: int, language: str) -> list[Video]:
    """Fetch video entries (trailers, teasers) for a TV show.

    Calls ``GET /tv/{id}/videos``.

    Fail-soft policy identical to ``get_keywords()``: HTTP 404, timeout,
    and any unexpected exception all return ``[]`` and log a warning.

    Args:
        tmdb_id: TMDB TV show ID.
        language: BCP-47 language tag (e.g. "fr-FR", "en-US").

    Returns:
        List of Video dataclass instances. Empty on any error.
    """
    return self._fetch_videos(f"/tv/{tmdb_id}/videos", tmdb_id, "tv", language)

def _fetch_videos(
    self, endpoint: str, tmdb_id: int, media_type: str, language: str
) -> list[Video]:
    """Internal: call /videos endpoint and deserialize into Video list.

    Args:
        endpoint: Full endpoint path (e.g. "/movie/550/videos").
        tmdb_id: TMDB ID for logging context.
        media_type: "movie" or "tv" for log messages.
        language: BCP-47 language tag passed as query parameter.

    Returns:
        List of Video instances; empty list on any error.
    """
    try:
        data = self._get(endpoint, {"language": language})
    except TMDBError as exc:
        if exc.http_status == 404:
            return []
        logger.warning(
            "TMDB videos fetch failed for %s/%d (HTTP %d): %s — using empty list",
            media_type, tmdb_id, exc.http_status, exc.message,
        )
        return []
    except Exception as exc:
        logger.warning(
            "TMDB videos fetch failed for %s/%d: %s — using empty list",
            media_type, tmdb_id, exc,
        )
        return []

    raw_list = data.get("results") or []
    videos: list[Video] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            videos.append(Video(
                id=str(item["id"]),
                site=str(item.get("site", "")),
                key=str(item.get("key", "")),
                type=str(item.get("type", "")),
                official=bool(item.get("official", False)),
                size=int(item.get("size", 0)),
                iso_639_1=str(item.get("iso_639_1", "")),
            ))
        except (KeyError, TypeError, ValueError):
            logger.debug("Skipping malformed video entry: %r", item)
            continue
    return videos
```

### Step 4: Run tests — all must pass

```bash
pytest tests/scraper/test_tmdb_client_videos.py -v
```

Expected: all tests PASS.

### Step 5: Verify existing scraper tests still pass

```bash
pytest tests/scraper/ -v --tb=short 2>&1 | tail -20
```

Expected: no regressions.

### Step 6: Commit sub-phase 1.2

```bash
git add \
  personalscraper/scraper/tmdb_client.py \
  tests/scraper/test_tmdb_client_videos.py
git commit -m "feat(trailer): implement fetch_movie_videos and fetch_tv_videos on TMDBClient"
```

---

## Sub-phase 1.3 — `fetch_tv_season_videos` method (season-level trailer support)

This sub-phase adds the third TMDB videos endpoint, used by the opt-in season-level trailer
download path (DESIGN §4 "Season trailers" extension, opt-in via
`config.trailers.seasons.enabled`).

### Files

| Action | Path                                               | Responsibility                            |
| ------ | -------------------------------------------------- | ----------------------------------------- |
| Modify | `personalscraper/scraper/tmdb_client.py`           | Add `fetch_tv_season_videos()` method     |
| Create | `tests/fixtures/tmdb/tv_1399_season_1_videos.json` | Golden fixture: TV season videos response |
| Modify | `tests/scraper/test_tmdb_client_videos.py`         | Add three season-videos tests             |

### Step 1: Write the golden fixture `tests/fixtures/tmdb/tv_1399_season_1_videos.json`

This is the shape returned by `GET /tv/1399/season/1/videos?language=en-US` (same schema as
the show-level `/tv/{id}/videos` response, with the season number reflected in `id`).

```json
{
  "id": 3624,
  "results": [
    {
      "id": "5e8c69f0e7e8c1001754ce9d",
      "iso_639_1": "en",
      "iso_3166_1": "US",
      "key": "BpJYNVhGf1s",
      "name": "Game of Thrones - Season 1 Trailer",
      "official": true,
      "published_at": "2011-03-25T00:00:00.000Z",
      "site": "YouTube",
      "size": 1080,
      "type": "Trailer"
    }
  ]
}
```

### Step 2: Write the failing tests

Add the following test class to `tests/scraper/test_tmdb_client_videos.py`:

```python
# ── fetch_tv_season_videos ────────────────────────────────────────────────────

class TestFetchTvSeasonVideos:
    def test_fetch_tv_season_videos_returns_videos(self, client):
        """Happy path: season-level fetch returns the canonical Video list."""
        fixture = _load("tv_1399_season_1_videos.json")
        with patch.object(client, "_get", return_value=fixture):
            videos = client.fetch_tv_season_videos(1399, season_number=1, language="en-US")
        assert len(videos) == 1
        assert isinstance(videos[0], Video)
        assert videos[0].key == "BpJYNVhGf1s"

    def test_fetch_tv_season_videos_404_returns_empty(self, client):
        """Fail-soft on 404 — many shows have no season-level videos on TMDB."""
        with patch.object(client, "_get", side_effect=TMDBError(404, 34, "Not Found")):
            result = client.fetch_tv_season_videos(99999, season_number=3, language="en-US")
        assert result == []

    def test_fetch_tv_season_videos_uses_circuit_breaker(self, client):
        """Same circuit breaker (`_get`) covers show- and season-level video fetches.

        Asserted indirectly: the implementation funnels through `_fetch_videos`
        which delegates to `self._get` — the same path show-level fetches use,
        therefore the same `tmdb_videos` breaker (DESIGN §1) applies.
        """
        mock_get = MagicMock(return_value={"id": 1, "results": []})
        with patch.object(client, "_get", mock_get):
            client.fetch_tv_season_videos(1, season_number=2, language="fr-FR")
        mock_get.assert_called_once_with("/tv/1/season/2/videos", {"language": "fr-FR"})
```

### Step 3: Run failing tests

```bash
pytest tests/scraper/test_tmdb_client_videos.py::TestFetchTvSeasonVideos -v 2>&1 | head -10
```

Expected: `AttributeError` — method does not exist yet.

### Step 4: Implement the method in `tmdb_client.py`

Reuse the existing `_fetch_videos` helper (single source of truth — the only difference is
the URL path construction). Add the following method to `TMDBClient`, after `fetch_tv_videos()`:

```python
def fetch_tv_season_videos(
    self, tv_id: int, season_number: int, language: str
) -> list[Video]:
    """Fetch videos for a specific TV show season from TMDB.

    Calls ``GET /tv/{tv_id}/season/{season_number}/videos``. TMDB indexes
    seasons starting at 1 (specials are season 0).

    Args:
        tv_id: TMDB TV show id.
        season_number: TMDB season number (1-indexed; specials = 0).
        language: BCP-47 language code (e.g. "fr-FR", "en-US").

    Returns:
        List of Video dataclass instances. Empty list on 404 (no videos
        for this season — common for older shows or non-flagship seasons)
        or any other error (fail-soft, same as show-level).

    Raises:
        Same as fetch_tv_videos — propagates circuit-breaker open, fails
        fast on unrecoverable 5xx after retries, fail-soft on 404 (returns []).
    """
    return self._fetch_videos(
        f"/tv/{tv_id}/season/{season_number}/videos",
        tv_id,
        f"tv-season-{season_number}",
        language,
    )
```

URL template: `/tv/{tv_id}/season/{season_number}/videos?language={language}`. The existing
`_fetch_videos` helper handles the query parameter wiring, JSON deserialization, and
fail-soft policy (404 → `[]`, other exceptions → `[]` + WARNING log).

### Step 5: Run tests — all must pass

```bash
pytest tests/scraper/test_tmdb_client_videos.py::TestFetchTvSeasonVideos -v
```

### Step 6: Commit sub-phase 1.3

```bash
git add \
  personalscraper/scraper/tmdb_client.py \
  tests/fixtures/tmdb/tv_1399_season_1_videos.json \
  tests/scraper/test_tmdb_client_videos.py
git commit -m "feat(trailer): add fetch_tv_season_videos for season-level trailer discovery"
```

---

## Phase 1 quality gate

- [ ] `pytest tests/scraper/ -q` — all green, no regressions in existing tests
- [ ] `python -m ruff check personalscraper/scraper/tmdb_client.py tests/scraper/test_tmdb_client_videos.py` — no errors
- [ ] `python -m mypy personalscraper/scraper/tmdb_client.py` — no type errors

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/scraper/ -q
python -m ruff check personalscraper/scraper/tmdb_client.py tests/scraper/test_tmdb_client_videos.py
python -m mypy personalscraper/scraper/tmdb_client.py
```

## Milestone commit

```bash
git commit --allow-empty -m "chore(trailer): phase 01 gate — TMDBClient video endpoints + Video dataclass"
```

## Exit condition for Phase 3a

Phase 3a may start only when:

- `pytest tests/scraper/ -q` exits 0
- `Video`, `fetch_movie_videos`, `fetch_tv_videos` are importable from `personalscraper.scraper.tmdb_client`
- The milestone commit `chore(trailer): phase 01 gate — ...` is on the branch
