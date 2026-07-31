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


class TestScrapeRenameTracking:
    """Review A/B: the orchestrator keeps provenance current_path live across the rename."""

    def test_track_scrape_rename_stamps_scrape_run_uid_on_real_store(self, tmp_path: Path) -> None:
        """F3: _track_scrape_rename moves current_path AND stamps scrape_run_uid (real store)."""
        from personalscraper.scraper._shared import ScrapeResult
        from personalscraper.scraper.orchestrator import Scraper

        store = build_acquire_store(AcquireConfig(db_path=tmp_path / "a.db"))
        try:
            store.provenance.upsert_grab(
                "h", followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=1
            )
            store.provenance.set_ingest("h", ingest_path="/001-MOVIES/Some.Movie.2020.WEB", ingested_at=2)
            result = ScrapeResult(media_path=Path("/001-MOVIES/Some Movie (2020)"), media_type="movie")
            Scraper._track_scrape_rename(
                SimpleNamespace(_provenance=store.provenance, _run_uid="scrapeRUN"),  # type: ignore[arg-type]
                Path("/001-MOVIES/Some.Movie.2020.WEB"),
                result,
            )
            row = store.provenance.by_hash("h")
            assert row is not None
            assert row.current_path == "/001-MOVIES/Some Movie (2020)"  # rename tracked
            assert row.scrape_run_uid == "scrapeRUN"  # scraping run stamped
        finally:
            store.close()

    def test_track_scrape_rename_moves_path_on_rename(self) -> None:
        """A renamed scrape result triggers provenance.move_path(input → final)."""
        from types import SimpleNamespace

        from personalscraper.scraper._shared import ScrapeResult
        from personalscraper.scraper.orchestrator import Scraper

        calls: list[tuple[str, str]] = []

        class _Spy:
            def move_path(self, old_path: str, new_path: str) -> None:
                calls.append((old_path, new_path))

            def set_scrape_run(self, staging_path: str, *, run_uid: str | None) -> None:
                pass  # F3 stamp — not under test here

        result = ScrapeResult(media_path=Path("/001-MOVIES/Some Movie (2020)"), media_type="movie")
        Scraper._track_scrape_rename(  # call the method with a minimal fake self
            SimpleNamespace(_provenance=_Spy(), _run_uid=None),  # type: ignore[arg-type]
            Path("/001-MOVIES/Some.Movie.2020.1080p.WEB"),
            result,
        )
        assert calls == [("/001-MOVIES/Some.Movie.2020.1080p.WEB", "/001-MOVIES/Some Movie (2020)")]

    def test_track_scrape_rename_noop_when_not_renamed(self) -> None:
        """When media_path == input (no rename), no move_path call is made."""
        from types import SimpleNamespace

        from personalscraper.scraper._shared import ScrapeResult
        from personalscraper.scraper.orchestrator import Scraper

        calls: list[tuple[str, str]] = []

        class _Spy:
            def move_path(self, old_path: str, new_path: str) -> None:  # pragma: no cover - must not fire
                calls.append((old_path, new_path))

            def set_scrape_run(self, staging_path: str, *, run_uid: str | None) -> None:
                pass  # F3 stamp — not under test here

        same = Path("/001-MOVIES/Already Canonical (2020)")
        Scraper._track_scrape_rename(
            SimpleNamespace(_provenance=_Spy(), _run_uid=None), same, ScrapeResult(media_path=same, media_type="movie")
        )  # type: ignore[arg-type]
        assert calls == []
