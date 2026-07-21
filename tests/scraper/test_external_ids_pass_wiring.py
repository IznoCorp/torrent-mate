"""Production-wiring tests for the Q5=B external-ids pass (solidify).

The ``_xref.resolve_external_ids`` Q5=B pass shipped with ``provider-ids`` (#23)
but never had a production caller: it validated non-canonical provider ids and
fetched IMDb / Rotten-Tomatoes ratings in unit tests only, and no scrape ever
invoked it. These tests pin the pass now that it is wired into the confirmed-write
flows shared by the automatic scrape and the operator-forced resolve
(``_write_confirmed_movie`` / ``_write_confirmed_show`` → ``_apply_external_ids``
→ ``run_external_ids_pass``).

They prove, against a real :class:`Scraper` driven by fake providers (never any
network):

* the pass RUNS in ``scrape_movie`` (automatic) and ``scrape_tvshow_forced`` —
  ``validate_id`` and ``get_rating`` are actually called;
* the NFO GAINS the IMDb / Rotten-Tomatoes ``<rating>`` rows merged with the
  canonical TMDb rating;
* an id the façade REJECTS is dropped from the NFO (Q5=B), while an id with no
  wired façade (OMDb absent) is KEPT unvalidated (skip silencieux);
* a quota-exhausted rating provider degrades fail-soft — the scrape still
  succeeds, ids are kept, no external ratings are written.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.metadata._base import Notations
from personalscraper.api.metadata.omdb import OmdbQuotaExhausted
from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.confidence import MatchResult
from personalscraper.scraper.orchestrator import Scraper

# ---------------------------------------------------------------------------
# Fake provider payloads (never real TMDB/TVDB)
# ---------------------------------------------------------------------------

_MOVIE_DATA: dict[str, Any] = {
    "id": 603,
    "title": "The Matrix",
    "original_title": "The Matrix",
    "name": "The Matrix",
    "original_name": "The Matrix",
    "overview": "A hacker learns the truth about his reality.",
    "vote_average": 8.2,
    "vote_count": 20000,
    "genres": [{"name": "Action"}],
    "release_date": "1999-03-31",
    "credits": {"cast": [], "crew": []},
    "images": {"posters": [], "backdrops": [], "logos": []},
    "external_ids": {"imdb_id": "tt0133093"},
    "release_dates": {"results": []},
    "production_countries": [],
    "production_companies": [],
    "origin_country": [],
}
_MOVIE_TMDB_ID = 603

_SHOW_DATA: dict[str, Any] = {
    "id": 66732,  # TMDB xref (secondary)
    "name": "Fallout",
    "original_name": "Fallout",
    "overview": "In a retrofuturistic post-apocalyptic wasteland.",
    "vote_average": 8.4,
    "vote_count": 5000,
    "genres": [{"name": "Sci-Fi"}],
    "first_air_date": "2024-04-10",
    "external_ids": {"imdb_id": "tt12637874", "tvdb_id": 420001},
    "images": {"posters": [], "backdrops": [], "logos": []},
    "seasons": [{"season_number": 1, "episode_count": 1, "poster_path": "/s1.jpg"}],
}
_SHOW_TVDB_ID = 420001
_SHOW_TMDB_XREF = 66732


def _movie_match() -> MatchResult:
    return MatchResult(api_id=_MOVIE_TMDB_ID, api_title="The Matrix", api_year=1999, confidence=0.95, source="tmdb")


def _imdb_notation() -> Notations:
    return Notations(provider="omdb", source="imdb", score=9.0, votes_count=1000)


def _rt_notation() -> Notations:
    return Notations(provider="omdb", source="rotten_tomatoes", score=94.0, votes_count=0)


# ---------------------------------------------------------------------------
# Hermetic helpers
# ---------------------------------------------------------------------------


def _fake_download_image(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"stub")
    return True


def _ratings_from_nfo(nfo_path: Path) -> dict[str, dict[str, str | None]]:
    """Return the NFO ``<ratings>`` rows keyed by ``name`` (name → attrs+value)."""
    root = ET.parse(nfo_path).getroot()
    out: dict[str, dict[str, str | None]] = {}
    ratings = root.find("ratings")
    if ratings is None:
        return out
    for rating in ratings.findall("rating"):
        name = rating.get("name") or ""
        out[name] = {
            "default": rating.get("default"),
            "max": rating.get("max"),
            "value": rating.findtext("value"),
            "votes": rating.findtext("votes"),
        }
    return out


def _uniqueids_from_nfo(nfo_path: Path) -> dict[str, str | None]:
    """Return ``{type: id}`` for every ``<uniqueid>`` row in the NFO."""
    root = ET.parse(nfo_path).getroot()
    return {u.get("type") or "": u.text for u in root.findall("uniqueid")}


def _make_rating_client(*, validate: bool, notation: Notations | None) -> MagicMock:
    """Build a façade mock recording ``validate_id`` and returning one rating."""
    client = MagicMock()
    client.validate_id.return_value = validate
    client.get_rating.return_value = [notation] if notation is not None else []
    return client


@pytest.fixture
def scraper(mock_registry: Any) -> Scraper:
    """A registry-backed Scraper (classification skipped, real EventBus)."""
    settings = MagicMock()
    settings.tmdb_api_key = "fake-key"
    settings.tvdb_api_key = "fake-key"
    with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
        return Scraper(settings, NamingPatterns(), event_bus=EventBus(), registry=mock_registry)


def _run_automatic_movie(scraper: Scraper, movie_dir: Path) -> Any:
    # Fresh payload per run — the NFO write path mutates the movie dict in place
    # (in production it is a fresh coerced dict each call); a deep copy keeps the
    # module-level fixture pristine so tests do not contaminate one another.
    with (
        patch("personalscraper.scraper.confidence.match_movie_detailed", return_value=(_movie_match(), [])),
        patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=copy.deepcopy(_MOVIE_DATA)),
        patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
        patch.object(scraper._artwork, "download_image", side_effect=_fake_download_image),
    ):
        return scraper.scrape_movie(movie_dir)


def _run_forced_movie(scraper: Scraper, movie_dir: Path) -> Any:
    with (
        patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=copy.deepcopy(_MOVIE_DATA)),
        patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
        patch.object(scraper._artwork, "download_image", side_effect=_fake_download_image),
    ):
        return scraper.scrape_movie_forced(movie_dir, _MOVIE_TMDB_ID)


def _staged_movie(tmp_path: Path) -> Path:
    movie_dir = tmp_path / "the.matrix.1999.1080p.BluRay.x264-GROUP"
    movie_dir.mkdir(parents=True)
    (movie_dir / "the.matrix.1999.1080p.BluRay.x264-GROUP.mkv").write_bytes(b"\x00")
    return movie_dir


# ---------------------------------------------------------------------------
# Movie — the pass RUNS and the NFO gains IMDb + RT ratings
# ---------------------------------------------------------------------------


def test_movie_scrape_runs_pass_and_nfo_gains_imdb_rt_ratings(scraper: Scraper, tmp_path: Path) -> None:
    """Automatic ``scrape_movie`` calls ``validate_id`` and writes IMDb+RT ratings."""
    scraper._imdb = _make_rating_client(validate=True, notation=_imdb_notation())
    scraper._rotten_tomatoes = _make_rating_client(validate=True, notation=_rt_notation())

    result = _run_automatic_movie(scraper, _staged_movie(tmp_path))
    assert result.action == "scraped", result.error

    # The pass actually ran against the confirmed identity.
    scraper._imdb.validate_id.assert_called_once_with("tt0133093", "The Matrix", 1999)
    scraper._imdb.get_rating.assert_called_once_with("tt0133093")
    scraper._rotten_tomatoes.get_rating.assert_called_once_with("tt0133093")

    nfo = next(result.media_path.glob("*.nfo"))
    ratings = _ratings_from_nfo(nfo)
    # Canonical TMDb rating merged with the two resolved external ratings.
    assert set(ratings) == {"themoviedb", "imdb", "rottentomatoes"}
    assert ratings["themoviedb"]["default"] == "true"
    assert ratings["themoviedb"]["value"] == "8.2"
    assert ratings["imdb"]["value"] == "9.0"
    assert ratings["imdb"]["max"] == "10"
    assert ratings["rottentomatoes"]["value"] == "94.0"
    assert ratings["rottentomatoes"]["max"] == "100"
    # Confirmed ids are kept (imdb accepted, tmdb canonical).
    assert _uniqueids_from_nfo(nfo) == {"imdb": "tt0133093", "tmdb": "603"}


def test_movie_forced_matches_automatic_enriched_ratings(scraper: Scraper, tmp_path: Path) -> None:
    """The forced resolve emits the SAME enriched ``<ratings>`` block as the automatic scrape."""
    scraper._imdb = _make_rating_client(validate=True, notation=_imdb_notation())
    scraper._rotten_tomatoes = _make_rating_client(validate=True, notation=_rt_notation())

    auto = _run_automatic_movie(scraper, _staged_movie(tmp_path / "auto"))
    forced = _run_forced_movie(scraper, _staged_movie(tmp_path / "forced"))

    assert auto.action == "scraped", auto.error
    assert forced.action == "scraped", forced.error
    auto_nfo = next(auto.media_path.glob("*.nfo"))
    forced_nfo = next(forced.media_path.glob("*.nfo"))
    assert _ratings_from_nfo(forced_nfo) == _ratings_from_nfo(auto_nfo)
    assert _uniqueids_from_nfo(forced_nfo) == _uniqueids_from_nfo(auto_nfo)


def test_movie_scrape_drops_imdb_id_on_revalidation_reject(scraper: Scraper, tmp_path: Path) -> None:
    """Q5=B: a façade-REJECTED IMDb id is removed from the NFO; TMDb becomes default."""
    scraper._imdb = _make_rating_client(validate=False, notation=None)
    scraper._rotten_tomatoes = _make_rating_client(validate=True, notation=_rt_notation())

    result = _run_automatic_movie(scraper, _staged_movie(tmp_path))
    assert result.action == "scraped", result.error

    nfo = next(result.media_path.glob("*.nfo"))
    uniqueids = _uniqueids_from_nfo(nfo)
    assert "imdb" not in uniqueids
    assert uniqueids["tmdb"] == "603"
    # No trusted IMDb anchor → no IMDb/RT rating fetched, legacy TMDb row only.
    scraper._imdb.get_rating.assert_not_called()
    scraper._rotten_tomatoes.get_rating.assert_not_called()
    assert set(_ratings_from_nfo(nfo)) == {"themoviedb"}


def test_movie_scrape_keeps_imdb_id_when_omdb_absent(scraper: Scraper, tmp_path: Path) -> None:
    """OMDb not provisioned (façades ``None``) → IMDb id kept unvalidated, scrape ok."""
    scraper._imdb = None
    scraper._rotten_tomatoes = None

    result = _run_automatic_movie(scraper, _staged_movie(tmp_path))
    assert result.action == "scraped", result.error

    nfo = next(result.media_path.glob("*.nfo"))
    # Skip silencieux: the id survives even though it could not be re-validated.
    assert _uniqueids_from_nfo(nfo) == {"imdb": "tt0133093", "tmdb": "603"}
    assert set(_ratings_from_nfo(nfo)) == {"themoviedb"}


def test_movie_scrape_quota_exhausted_degrades_fail_soft(scraper: Scraper, tmp_path: Path) -> None:
    """A quota-exhausted rating façade never fails the scrape; ids kept, no ext ratings."""
    imdb = MagicMock()
    imdb.validate_id.side_effect = OmdbQuotaExhausted()
    scraper._imdb = imdb
    scraper._rotten_tomatoes = _make_rating_client(validate=True, notation=_rt_notation())

    result = _run_automatic_movie(scraper, _staged_movie(tmp_path))
    # Fail-soft: the scrape completes despite the quota exception.
    assert result.action == "scraped", result.error

    nfo = next(result.media_path.glob("*.nfo"))
    # Ids kept unvalidated; NFO falls back to the legacy single TMDb rating.
    assert _uniqueids_from_nfo(nfo) == {"imdb": "tt0133093", "tmdb": "603"}
    assert set(_ratings_from_nfo(nfo)) == {"themoviedb"}


# ---------------------------------------------------------------------------
# TV — the pass RUNS on the forced-resolve write and the show NFO gains ratings
# ---------------------------------------------------------------------------


def _run_forced_tvshow(scraper: Scraper, show_dir: Path) -> Any:
    episode_map = {(1, 1): {"title": "The End", "still_path": ""}}
    with (
        patch(
            "personalscraper.scraper.tv_service_write.fetch_show_data",
            return_value=(copy.deepcopy(_SHOW_DATA), _SHOW_TMDB_XREF),
        ),
        patch.object(scraper, "_build_episode_map", return_value=episode_map),
        patch.object(scraper, "_xref_enrichment", return_value=None),
        patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
        patch.object(scraper._artwork, "download_image", side_effect=_fake_download_image),
    ):
        return scraper.scrape_tvshow_forced(show_dir, "tvdb", _SHOW_TVDB_ID)


def _staged_show(tmp_path: Path) -> Path:
    show_dir = tmp_path / "Fallout.S01.1080p.WEB.H264-GROUP"
    show_dir.mkdir(parents=True)
    (show_dir / "Fallout.S01E01.1080p.WEB.H264-GROUP.mkv").write_bytes(b"\x00")
    return show_dir


def test_tvshow_forced_runs_pass_and_nfo_gains_imdb_rt_ratings(scraper: Scraper, tmp_path: Path) -> None:
    """``scrape_tvshow_forced`` re-validates the xref ids and enriches ``tvshow.nfo`` ratings."""
    scraper._imdb = _make_rating_client(validate=True, notation=_imdb_notation())
    scraper._rotten_tomatoes = _make_rating_client(validate=True, notation=_rt_notation())

    result = _run_forced_tvshow(scraper, _staged_show(tmp_path))
    assert result.action == "scraped", result.error

    # The pass ran: the non-canonical IMDb id was re-validated against the show identity.
    scraper._imdb.validate_id.assert_called_once_with("tt12637874", "Fallout", 2024)
    scraper._imdb.get_rating.assert_called_once_with("tt12637874")

    nfo = result.media_path / "tvshow.nfo"
    ratings = _ratings_from_nfo(nfo)
    assert set(ratings) == {"themoviedb", "imdb", "rottentomatoes"}
    assert ratings["themoviedb"]["value"] == "8.4"
    assert ratings["imdb"]["value"] == "9.0"
    assert ratings["rottentomatoes"]["value"] == "94.0"
    # TVDB stays canonical/default; the re-validated xref ids are kept.
    uniqueids = _uniqueids_from_nfo(nfo)
    assert uniqueids["tvdb"] == "420001"
    assert uniqueids["tmdb"] == "66732"
    assert uniqueids["imdb"] == "tt12637874"


def test_tvshow_forced_quota_exhausted_degrades_fail_soft(scraper: Scraper, tmp_path: Path) -> None:
    """A rating façade quota exception never fails the TV forced resolve."""
    imdb = MagicMock()
    imdb.validate_id.return_value = True
    imdb.get_rating.side_effect = OmdbQuotaExhausted()
    scraper._imdb = imdb
    scraper._rotten_tomatoes = _make_rating_client(validate=True, notation=_rt_notation())

    result = _run_forced_tvshow(scraper, _staged_show(tmp_path))
    assert result.action == "scraped", result.error

    nfo = result.media_path / "tvshow.nfo"
    # Ids preserved; NFO falls back to the legacy single TMDb rating row.
    uniqueids = _uniqueids_from_nfo(nfo)
    assert uniqueids["tvdb"] == "420001"
    assert uniqueids["imdb"] == "tt12637874"
    assert set(_ratings_from_nfo(nfo)) == {"themoviedb"}
