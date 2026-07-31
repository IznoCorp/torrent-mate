"""Phase 4 — the #30 scrape consumer: provenance drives deterministic identity.

The scrape resolvers built in ``scraper/run.py`` read the provenance registry
(``current_path → media_ref`` recorded at grab, kept live through sort) so the
scrape forces the recorded identity instead of re-inferring it:

  * TV (``_build_follow_tvdb_resolver``): provenance tvdb FIRST, then the #29
    episode/title inference, then free match.
  * MOVIES (``_build_provenance_movie_resolver``): provenance tmdb (movies have no
    #29 fallback — that is TV-only).

Both fail-soft: no provenance ⇒ today's behaviour.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from personalscraper.scraper.run import _build_follow_tvdb_resolver, _build_provenance_movie_resolver


@pytest.fixture
def store_and_db(tmp_path: Path) -> Iterator[tuple[ConcreteAcquireStore, Path]]:
    """Yield a real acquire store + its db path, closed afterwards."""
    db = tmp_path / "acquire.db"
    s = build_acquire_store(AcquireConfig(db_path=db))
    try:
        yield s, db
    finally:
        s.close()


def _config(db: Path) -> SimpleNamespace:
    """A config whose ``acquire`` sub-config locates the store."""
    return SimpleNamespace(acquire=AcquireConfig(db_path=db))


def _track(store: ConcreteAcquireStore, info_hash: str, ref: MediaRef, kind: str, current_path: str) -> None:
    """Record a follow-driven grab + ingest so the row sits at *current_path*."""
    store.provenance.upsert_grab(info_hash, followed_id=None, media_ref=ref, kind=kind, grabbed_at=1)
    store.provenance.set_ingest(info_hash, ingest_path=current_path, ingested_at=2)


class TestTvProvenanceResolver:
    """The TV resolver forces the provenance tvdb deterministically (#30)."""

    def test_provenance_tvdb_forced_for_its_path(self, store_and_db: tuple[ConcreteAcquireStore, Path]) -> None:
        """A provenance row at the show folder forces its tvdb — no title inference."""
        store, db = store_and_db
        # A generic « Star Trek » folder that #29's title guard would score LOW,
        # yet provenance carries the exact tvdb → deterministic force.
        _track(store, "h1", MediaRef(tvdb_id=382389), "episode", "/002-TVSHOWS/Star Trek")
        resolver = _build_follow_tvdb_resolver(_config(db))
        assert resolver is not None
        assert resolver(Path("/002-TVSHOWS/Star Trek")) == 382389

    def test_no_provenance_falls_back(self, store_and_db: tuple[ConcreteAcquireStore, Path]) -> None:
        """A folder with no provenance row resolves via #29 (here: nothing → None)."""
        store, db = store_and_db
        _track(store, "h1", MediaRef(tvdb_id=382389), "episode", "/002-TVSHOWS/Star Trek")
        resolver = _build_follow_tvdb_resolver(_config(db))
        assert resolver is not None
        # A DIFFERENT folder → no provenance hit, no grabbed-episode coverage → None.
        assert resolver(Path("/002-TVSHOWS/Unrelated Show")) is None


class TestMovieProvenanceResolver:
    """The MOVIE resolver forces the provenance tmdb (#30 / ACC-05)."""

    def test_provenance_tmdb_forced_for_its_path(self, store_and_db: tuple[ConcreteAcquireStore, Path]) -> None:
        """A movie provenance row forces its tmdb at its folder path."""
        store, db = store_and_db
        _track(store, "m1", MediaRef(tmdb_id=27205), "movie", "/001-MOVIES/Inception")
        resolver = _build_provenance_movie_resolver(_config(db))
        assert resolver is not None
        assert resolver(Path("/001-MOVIES/Inception")) == 27205

    def test_miss_returns_none(self, store_and_db: tuple[ConcreteAcquireStore, Path]) -> None:
        """An untracked movie folder → None (free match, unchanged)."""
        store, db = store_and_db
        _track(store, "m1", MediaRef(tmdb_id=27205), "movie", "/001-MOVIES/Inception")
        resolver = _build_provenance_movie_resolver(_config(db))
        assert resolver is not None
        assert resolver(Path("/001-MOVIES/Other")) is None

    def test_no_provenance_yields_no_resolver(self, store_and_db: tuple[ConcreteAcquireStore, Path]) -> None:
        """No tracked rows ⇒ the builder returns None (free match)."""
        _, db = store_and_db
        assert _build_provenance_movie_resolver(_config(db)) is None
