"""Tests for ``MovieServiceMixin._resolve_external_ids`` (phase 5.5).

Mirror of the TV-side tests — same Q5=B contract, applied to movies.
The canonical provider is virtually always TMDb in production but
the method is parametrised so the rare TVDB-canonical case stays
exercised.
"""

from __future__ import annotations

from functools import partial
from typing import Any
from unittest.mock import MagicMock

from personalscraper.api.metadata._base import Notations
from personalscraper.naming_patterns import PATTERNS, NamingPatterns
from personalscraper.scraper._xref import family_to_client, resolve_external_ids
from personalscraper.scraper.movie_service import MovieServiceMixin


def _resolve(
    mixin: MovieServiceMixin,
    *,
    canonical_provider: str,
    movie_ids: dict[str, str],
    expected_title: str,
    expected_year: int | None,
) -> tuple[dict[str, str], list[Notations]]:
    """Drive the shared ``resolve_external_ids`` the way the movie service wires it.

    P4.2 collapsed the per-service ``_resolve_external_ids`` /
    ``_family_to_client`` delegates into the single ``_xref`` free
    functions (ACC-03). This helper reproduces the movie-side wiring so
    the existing behavioural assertions keep exercising the shared body.
    """
    return resolve_external_ids(
        canonical_provider=canonical_provider,
        ids=movie_ids,
        expected_title=expected_title,
        expected_year=expected_year,
        family_to_client=partial(family_to_client, registry=mixin._registry, imdb_client=mixin._imdb),
        imdb_client=mixin._imdb,
        rt_client=mixin._rotten_tomatoes,
    )


def _imdb_notation() -> Notations:
    return Notations(provider="omdb", source="imdb", score=9.0, votes_count=1_000)


def _rt_notation() -> Notations:
    return Notations(provider="omdb", source="rotten_tomatoes", score=94.0, votes_count=0)


def _make_mixin(
    *,
    tvdb: Any = None,
    tmdb: Any = None,
    imdb: Any = None,
    rt: Any = None,
    patterns: NamingPatterns | None = None,
) -> MovieServiceMixin:
    mixin = MovieServiceMixin.__new__(MovieServiceMixin)
    mixin.dry_run = False
    mixin._registry = MagicMock()  # type: ignore[assignment]
    mixin._tvdb = tvdb if tvdb is not None else MagicMock()  # type: ignore[attr-defined]
    mixin._tmdb = tmdb if tmdb is not None else MagicMock()  # type: ignore[assignment]
    mixin._imdb = imdb if imdb is not None else MagicMock()  # type: ignore[attr-defined]
    mixin._rotten_tomatoes = rt if rt is not None else MagicMock()  # type: ignore[attr-defined]
    mixin._artwork = MagicMock()  # type: ignore[assignment]
    mixin._nfo = MagicMock()  # type: ignore[assignment]
    mixin.config = None  # type: ignore[assignment]
    mixin.patterns = patterns or PATTERNS  # type: ignore[assignment]
    return mixin


def test_movie_resolve_external_ids_keeps_canonical_revalidates_others() -> None:
    """Canonical TMDb kept as-is, IMDb re-validated, RT rating fetched."""
    imdb = MagicMock()
    imdb.validate_id.return_value = True
    imdb.get_rating.return_value = [_imdb_notation()]
    rt = MagicMock()
    rt.get_rating.return_value = [_rt_notation()]
    mixin = _make_mixin(imdb=imdb, rt=rt)

    external_ids, ratings = _resolve(
        mixin,
        canonical_provider="tmdb",
        movie_ids={"tmdb": "603", "imdb": "tt0133093"},
        expected_title="The Matrix",
        expected_year=1999,
    )

    assert external_ids == {"tmdb": "603", "imdb": "tt0133093"}
    imdb.validate_id.assert_called_once_with("tt0133093", "The Matrix", 1999)
    sources = sorted(r.source for r in ratings)
    assert sources == ["imdb", "rotten_tomatoes"]


def test_movie_resolve_external_ids_drops_imdb_on_revalidation_reject() -> None:
    """IMDb re-validation False → IMDb dropped, ratings not fetched."""
    imdb = MagicMock()
    imdb.validate_id.return_value = False
    rt = MagicMock()
    rt.get_rating.return_value = [_rt_notation()]
    mixin = _make_mixin(imdb=imdb, rt=rt)

    external_ids, ratings = _resolve(
        mixin,
        canonical_provider="tmdb",
        movie_ids={"tmdb": "603", "imdb": "tt9999999"},
        expected_title="The Matrix",
        expected_year=1999,
    )

    assert external_ids == {"tmdb": "603"}
    imdb.get_rating.assert_not_called()
    rt.get_rating.assert_not_called()  # Skipped — no trusted IMDb anchor.
    assert ratings == []


def test_movie_resolve_external_ids_swallows_validate_exception() -> None:
    """A façade exception during validate_id falls back to "drop the ID"."""
    imdb = MagicMock()
    imdb.validate_id.side_effect = RuntimeError("network down")
    mixin = _make_mixin(imdb=imdb)

    external_ids, _ = _resolve(
        mixin,
        canonical_provider="tmdb",
        movie_ids={"tmdb": "603", "imdb": "tt0133093"},
        expected_title="The Matrix",
        expected_year=1999,
    )

    assert external_ids == {"tmdb": "603"}


def test_movie_resolve_external_ids_no_imdb_no_rating_call() -> None:
    """Without an IMDb ID, RT is not queried either."""
    rt = MagicMock()
    mixin = _make_mixin(rt=rt)

    _, ratings = _resolve(
        mixin,
        canonical_provider="tmdb",
        movie_ids={"tmdb": "603"},
        expected_title="The Matrix",
        expected_year=1999,
    )

    rt.get_rating.assert_not_called()
    assert ratings == []
