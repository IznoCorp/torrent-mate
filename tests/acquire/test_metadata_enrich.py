"""Unit tests for the shared follow-metadata enricher (acq-states phase 7.2).

Pins the contract both callers depend on — the create-follow route and the
``follow backfill-metadata`` CLI:

- client/DB values win over the provider (and suppress the call entirely),
- provider lookups go by ID with the strict TVDB/TMDB separation,
- a provider failure yields ``None`` + a WARNING, never an exception.
"""

from __future__ import annotations

import logging

import pytest

from personalscraper.acquire.metadata_enrich import FollowMetadata, enrich_follow_metadata
from personalscraper.api._contracts import ApiError
from personalscraper.core.identity import MediaRef

_TVDB_ID = 468000
_TMDB_ID = 12345


class _Artwork:
    """Minimal ArtworkItem stand-in."""

    def __init__(self, type_: str, url: str) -> None:
        self.type = type_
        self.url = url


class _Details:
    """Minimal MediaDetails stand-in."""

    def __init__(
        self,
        *,
        year: int | None = None,
        overview: str = "",
        poster: str = "",
        title: str = "Titre du fournisseur",
    ) -> None:
        self.year = year
        self.overview = overview
        # A real provider ALWAYS returns a title — the stub must too, or the
        # enrichment reads « still incomplete » and polls the fallback.
        self.title = title
        self.images = [_Artwork("landscape", "https://x/land.jpg"), _Artwork("poster", poster)] if poster else []


class _RecordingClient:
    """Provider client recording every by-id call it receives."""

    def __init__(self, details: _Details | None = None, *, boom: Exception | None = None) -> None:
        self._details = details if details is not None else _Details()
        self._boom = boom
        self.calls: list[tuple[str, int]] = []

    def get_series(self, series_id: int) -> _Details:
        """TVDB by-id series endpoint."""
        self.calls.append(("get_series", series_id))
        if self._boom is not None:
            raise self._boom
        return self._details

    def get_tv(self, provider_id: int) -> _Details:
        """TMDB by-id TV endpoint."""
        self.calls.append(("get_tv", provider_id))
        if self._boom is not None:
            raise self._boom
        return self._details

    def get_movie(self, movie_id: int) -> _Details:
        """By-id movie endpoint (both providers expose it)."""
        self.calls.append(("get_movie", movie_id))
        if self._boom is not None:
            raise self._boom
        return self._details


def test_existing_values_win_and_skip_every_provider_call() -> None:
    """A complete ``existing`` short-circuits: no provider is ever touched."""
    tvdb = _RecordingClient(_Details(year=2024, overview="provider", poster="https://p/prov.jpg"))
    # A COMPLETE snapshot now includes the title: a follow whose name is
    # unknown still has something to fetch (a nameless row is unusable).
    existing = FollowMetadata(poster_url="https://c/client.jpg", overview="client", year=2023, title="Client")

    result = enrich_follow_metadata(
        MediaRef(tvdb_id=_TVDB_ID), "show", tmdb_client=None, tvdb_client=tvdb, existing=existing
    )

    assert result == existing
    assert tvdb.calls == []


def test_only_missing_fields_are_filled() -> None:
    """A partial ``existing`` keeps its values and gains only the missing ones."""
    tvdb = _RecordingClient(_Details(year=2024, overview="provider", poster="https://p/prov.jpg"))

    result = enrich_follow_metadata(
        MediaRef(tvdb_id=_TVDB_ID),
        "show",
        tmdb_client=None,
        tvdb_client=tvdb,
        existing=FollowMetadata(overview="client"),
    )

    assert result.overview == "client", "an existing value must never be overwritten"
    assert result.poster_url == "https://p/prov.jpg"
    assert result.year == 2024


def test_show_queries_tvdb_first_and_stops_when_complete() -> None:
    """TVDB is primary for shows; a complete answer means TMDB is not called."""
    tvdb = _RecordingClient(_Details(year=2024, overview="provider", poster="https://p/prov.jpg"))
    tmdb = _RecordingClient(_Details(year=1999, overview="tmdb", poster="https://p/tmdb.jpg"))

    result = enrich_follow_metadata(
        MediaRef(tvdb_id=_TVDB_ID, tmdb_id=_TMDB_ID), "show", tmdb_client=tmdb, tvdb_client=tvdb
    )

    assert tvdb.calls == [("get_series", _TVDB_ID)]
    assert tmdb.calls == [], "TVDB answered everything — TMDB must not be polled"
    assert result.year == 2024


def test_show_completes_from_tmdb_with_its_own_id() -> None:
    """TMDB completes what TVDB left out — and is handed the TMDB id, never the TVDB one."""
    tvdb = _RecordingClient(_Details(year=2024))  # no poster, no overview
    tmdb = _RecordingClient(_Details(overview="tmdb overview", poster="https://p/tmdb.jpg"))

    result = enrich_follow_metadata(
        MediaRef(tvdb_id=_TVDB_ID, tmdb_id=_TMDB_ID), "show", tmdb_client=tmdb, tvdb_client=tvdb
    )

    assert tmdb.calls == [("get_tv", _TMDB_ID)], "no cross-contamination: TMDB gets the TMDB id"
    assert result.year == 2024
    assert result.overview == "tmdb overview"
    assert result.poster_url == "https://p/tmdb.jpg"


def test_movie_queries_tmdb_first() -> None:
    """TMDB is primary for movies (the strict separation runs the other way)."""
    tvdb = _RecordingClient(_Details(year=1999))
    tmdb = _RecordingClient(_Details(year=2024, overview="film", poster="https://p/film.jpg"))

    result = enrich_follow_metadata(
        MediaRef(tvdb_id=_TVDB_ID, tmdb_id=_TMDB_ID), "movie", tmdb_client=tmdb, tvdb_client=tvdb
    )

    assert tmdb.calls == [("get_movie", _TMDB_ID)]
    assert tvdb.calls == []
    assert result.year == 2024


def test_provider_failure_is_swallowed_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    """A provider outage yields empty metadata + a WARNING — never an exception."""
    caplog.set_level(logging.WARNING)
    tvdb = _RecordingClient(boom=ApiError(provider="tvdb", http_status=500, message="boom"))

    result = enrich_follow_metadata(MediaRef(tvdb_id=_TVDB_ID), "show", tmdb_client=None, tvdb_client=tvdb)

    assert result.is_empty
    assert [r for r in caplog.records if r.levelno >= logging.WARNING], "the failure must be loud"


def test_missing_client_or_id_yields_empty_without_error() -> None:
    """No client (or no matching id) simply drops the source."""
    assert enrich_follow_metadata(MediaRef(tvdb_id=_TVDB_ID), "show", tmdb_client=None, tvdb_client=None).is_empty
    tmdb = _RecordingClient(_Details(year=2024))
    # A show known only by its TVDB id must not be looked up in TMDB.
    assert enrich_follow_metadata(MediaRef(tvdb_id=_TVDB_ID), "show", tmdb_client=tmdb, tvdb_client=None).is_empty
    assert tmdb.calls == []


def test_empty_overview_is_normalised_to_none() -> None:
    """``MediaDetails.overview`` defaults to ``""`` — storing it would fake an enriched row."""
    tvdb = _RecordingClient(_Details(year=2024, overview="   ", poster="https://p/prov.jpg"))

    result = enrich_follow_metadata(MediaRef(tvdb_id=_TVDB_ID), "show", tmdb_client=None, tvdb_client=tvdb)

    assert result.overview is None
    assert result.poster_url == "https://p/prov.jpg"
