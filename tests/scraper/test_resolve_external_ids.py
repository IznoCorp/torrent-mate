"""Tests for ``TvServiceMixin._resolve_external_ids`` (phase 5.2).

Series-level cross-reference resolution with the Q5=B re-validation
rule : for every non-canonical family the scraper holds an ID for,
re-validate it via the corresponding façade's ``validate_id`` before
treating it as trusted. Ratings are bundled in the same pass so the
NFO writer gets a single source of truth.

These tests inject mocks for the three façades (``TMDBClient``,
``IMDbClient``, ``RottenTomatoesClient``). They never make HTTP calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from personalscraper.api.metadata._base import Notations
from personalscraper.naming_patterns import PATTERNS, NamingPatterns
from personalscraper.scraper.tv_service import TvServiceMixin


def _imdb_notation() -> Notations:
    return Notations(provider="omdb", source="imdb", score=8.5, votes_count=10)


def _rt_notation() -> Notations:
    return Notations(provider="omdb", source="rotten_tomatoes", score=91.0, votes_count=0)


def _make_mixin(
    *,
    tvdb: Any = None,
    tmdb: Any = None,
    imdb: Any = None,
    rt: Any = None,
    patterns: NamingPatterns | None = None,
) -> TvServiceMixin:
    """Bare mixin instance with all façades wired as mocks."""
    mixin = TvServiceMixin.__new__(TvServiceMixin)
    mixin.dry_run = False

    _tvdb_client = tvdb if tvdb is not None else MagicMock()
    _tmdb_client = tmdb if tmdb is not None else MagicMock()
    _registry = MagicMock()
    _registry.get.side_effect = (
        lambda name,
        _cache={  # type: ignore[misc]
            "tmdb": _tmdb_client,
            "tvdb": _tvdb_client,
        }: _cache.get(name, MagicMock())
    )
    mixin._registry = _registry  # type: ignore[assignment]
    mixin._tvdb = _tvdb_client  # type: ignore[assignment]
    mixin._tmdb = _tmdb_client  # type: ignore[assignment]
    mixin._imdb = imdb if imdb is not None else MagicMock()  # type: ignore[attr-defined]
    mixin._rotten_tomatoes = rt if rt is not None else MagicMock()  # type: ignore[attr-defined]
    mixin._nfo = MagicMock()  # type: ignore[assignment]
    mixin._artwork = MagicMock()  # type: ignore[assignment]
    mixin.config = None  # type: ignore[assignment]
    mixin.patterns = patterns or PATTERNS  # type: ignore[assignment]
    mixin._scraper_language = "fr-FR"
    mixin._scraper_fallback_language = "en-US"
    return mixin


# ---------------------------------------------------------------------------
# Canonical family is trusted — no re-validation
# ---------------------------------------------------------------------------


def test_resolve_external_ids_returns_canonical_id_without_revalidation() -> None:
    """Canonical family (TVDB here) is *not* sent through ``validate_id``.

    The canonical scrape already established the ID's authenticity ;
    re-validating would waste an API call and risk a false negative
    if the upstream payload drifts.
    """
    tmdb = MagicMock()
    tmdb.validate_id.return_value = True
    imdb = MagicMock()
    imdb.validate_id.return_value = True
    imdb.get_rating.return_value = [_imdb_notation()]
    rt = MagicMock()
    rt.get_rating.return_value = [_rt_notation()]
    mixin = _make_mixin(tmdb=tmdb, imdb=imdb, rt=rt)

    external_ids, ratings = mixin._resolve_external_ids(
        canonical_provider="tvdb",
        series_ids={"tvdb": "42", "tmdb": "100", "imdb": "tt0944947"},
        expected_title="The Show",
        expected_year=2020,
    )

    # Canonical kept as-is. The other two are re-validated and kept.
    assert external_ids == {"tvdb": "42", "tmdb": "100", "imdb": "tt0944947"}
    # No call on TVDB façade (canonical).
    # TMDb / IMDb were re-validated once each.
    tmdb.validate_id.assert_called_once_with("100", "The Show", 2020)
    imdb.validate_id.assert_called_once_with("tt0944947", "The Show", 2020)
    # Ratings include the IMDb and RT entries.
    assert _imdb_notation() in ratings
    assert _rt_notation() in ratings


# ---------------------------------------------------------------------------
# Q5=B — non-canonical family validated, rejected on mismatch
# ---------------------------------------------------------------------------


def test_resolve_external_ids_drops_tmdb_when_revalidation_rejects() -> None:
    """``TMDBClient.validate_id`` returning False removes ``tmdb`` from the result.

    Q5=B contract : a non-canonical ID is only trusted if the
    provider's own re-validation says so. Otherwise the scraper
    refuses to leak a potentially stale ID into the NFO.
    """
    tmdb = MagicMock()
    tmdb.validate_id.return_value = False
    imdb = MagicMock()
    imdb.validate_id.return_value = True
    imdb.get_rating.return_value = None
    rt = MagicMock()
    rt.get_rating.return_value = None
    mixin = _make_mixin(tmdb=tmdb, imdb=imdb, rt=rt)

    external_ids, ratings = mixin._resolve_external_ids(
        canonical_provider="tvdb",
        series_ids={"tvdb": "42", "tmdb": "100", "imdb": "tt0944947"},
        expected_title="The Show",
        expected_year=2020,
    )

    assert external_ids == {"tvdb": "42", "imdb": "tt0944947"}
    assert ratings == []


def test_resolve_external_ids_drops_imdb_when_revalidation_rejects() -> None:
    """``IMDbClient.validate_id`` False → ``imdb`` removed AND no IMDb rating fetched."""
    tmdb = MagicMock()
    tmdb.validate_id.return_value = True
    imdb = MagicMock()
    imdb.validate_id.return_value = False
    rt = MagicMock()
    rt.get_rating.return_value = None
    mixin = _make_mixin(tmdb=tmdb, imdb=imdb, rt=rt)

    external_ids, ratings = mixin._resolve_external_ids(
        canonical_provider="tvdb",
        series_ids={"tvdb": "42", "tmdb": "100", "imdb": "tt0944947"},
        expected_title="The Show",
        expected_year=2020,
    )

    assert "imdb" not in external_ids
    imdb.get_rating.assert_not_called()  # Skipped — rejected ID.
    assert ratings == []


# ---------------------------------------------------------------------------
# Tmdb canonical → tvdb is re-validated
# ---------------------------------------------------------------------------


def test_resolve_external_ids_tmdb_canonical_revalidates_tvdb() -> None:
    """When canonical is TMDb, the TVDB ID is the one re-validated."""
    tvdb = MagicMock()
    tvdb.validate_id = MagicMock(return_value=True)
    imdb = MagicMock()
    imdb.validate_id.return_value = True
    imdb.get_rating.return_value = None
    rt = MagicMock()
    rt.get_rating.return_value = None
    mixin = _make_mixin(tvdb=tvdb, imdb=imdb, rt=rt)

    external_ids, _ = mixin._resolve_external_ids(
        canonical_provider="tmdb",
        series_ids={"tvdb": "42", "tmdb": "100"},
        expected_title="X",
        expected_year=None,
    )

    tvdb.validate_id.assert_called_once_with("42", "X", None)
    assert external_ids == {"tvdb": "42", "tmdb": "100"}


# ---------------------------------------------------------------------------
# Ratings aggregation
# ---------------------------------------------------------------------------


def test_resolve_external_ids_collects_ratings_from_imdb_and_rt() -> None:
    """Both IMDb and Rotten Tomatoes contribute to the rating list."""
    imdb = MagicMock()
    imdb.validate_id.return_value = True
    imdb.get_rating.return_value = [_imdb_notation()]
    rt = MagicMock()
    rt.get_rating.return_value = [_rt_notation()]
    mixin = _make_mixin(imdb=imdb, rt=rt)

    _, ratings = mixin._resolve_external_ids(
        canonical_provider="tvdb",
        series_ids={"tvdb": "42", "imdb": "tt0944947"},
        expected_title="X",
        expected_year=2020,
    )

    sources = sorted(r.source for r in ratings)
    assert sources == ["imdb", "rotten_tomatoes"]


def test_resolve_external_ids_no_imdb_no_ratings_call() -> None:
    """Without an IMDb ID, neither the IMDb façade nor RT are queried."""
    imdb = MagicMock()
    rt = MagicMock()
    mixin = _make_mixin(imdb=imdb, rt=rt)

    _, ratings = mixin._resolve_external_ids(
        canonical_provider="tvdb",
        series_ids={"tvdb": "42"},
        expected_title="X",
        expected_year=None,
    )

    imdb.validate_id.assert_not_called()
    imdb.get_rating.assert_not_called()
    rt.get_rating.assert_not_called()
    assert ratings == []
