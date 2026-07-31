"""End-to-end grab→scrape identity handoff: the follow's TVDB id reaches the scrape.

The STSNW #29 bug: a followed series acquired via the queue landed in « à
résoudre » because the scrape free-matched a DIFFERENT tvdb than the follow. The
fix reuses the follow's TVDB id at scrape time via a resolver built from the
acquire store's GRABBED rows (`_build_follow_tvdb_resolver`).

The unit tests cover the pure resolver (`resolve_followed_tvdb`, in-memory lists)
and the wiring against a MagicMock store. What was NOT proven end-to-end: the
REAL resolver, built from a REAL acquire.db seeded with real grabbed episodes,
resolving a real staging folder to the follow's tvdb. This test closes that seam
— the exact store→grabbed→resolver→tvdb chain #29 depends on.

Integration tier (real store + real filesystem, no network): default suite.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from personalscraper.scraper.run import _build_follow_tvdb_resolver


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
    """A config whose ``acquire`` sub-config locates the store (all the builder reads)."""
    return SimpleNamespace(acquire=AcquireConfig(db_path=db))


def _seed_grabbed_episodes(
    store: ConcreteAcquireStore,
    *,
    tvdb: int,
    followed_id: int,
    eps: list[tuple[int, int]],
) -> None:
    """Persist grabbed episode wanted rows for a follow (status='grabbed')."""
    for season, episode in eps:
        store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=tvdb),
                kind="episode",
                status="grabbed",
                enqueued_at=1,
                followed_id=followed_id,
                season=season,
                episode=episode,
                grabbed_hash=f"h{season:02d}{episode:02d}",
            )
        )


def _show_dir(tmp_path: Path, folder: str, eps: list[tuple[int, int]]) -> Path:
    """Create a staging show folder with one .mkv per (season, episode)."""
    d = tmp_path / folder
    d.mkdir()
    for season, episode in eps:
        (d / f"{folder}.S{season:02d}E{episode:02d}.MULTi.1080p.WEB.x265-GRP.mkv").write_bytes(b"")
    return d


class TestScrapeFollowProvenanceE2E:
    """The real resolver, built from a real store, resolves the follow's tvdb."""

    def test_grabbed_episodes_resolve_follow_tvdb(
        self, store_and_db: tuple[ConcreteAcquireStore, Path], tmp_path: Path
    ) -> None:
        """#29 END-TO-END: « Star Trek » folder ⊆ « Star Trek: Strange New Worlds » follow.

        The grabbed S03E09/E10 uniquely identify the follow's tvdb 382389, so the
        resolver forces it instead of letting the scrape free-match a duplicate.
        """
        store, db = store_and_db
        fid = store.follow.add(
            FollowedSeries(
                media_ref=MediaRef(tvdb_id=382389),
                title="Star Trek: Strange New Worlds",
                added_at=1,
            )
        )
        eps = [(3, 9), (3, 10)]
        _seed_grabbed_episodes(store, tvdb=382389, followed_id=fid, eps=eps)
        show = _show_dir(tmp_path, "Star Trek", eps)

        resolver = _build_follow_tvdb_resolver(_config(db))
        assert resolver is not None, "a grabbed queue must yield a resolver"
        assert resolver(show) == 382389

    def test_resolver_abstains_when_nothing_grabbed(
        self, store_and_db: tuple[ConcreteAcquireStore, Path], tmp_path: Path
    ) -> None:
        """No grabbed rows → no resolver (free match), never a spurious force."""
        store, db = store_and_db
        store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=382389), title="Star Trek", added_at=1))
        # Follow exists but NOTHING is grabbed.
        assert _build_follow_tvdb_resolver(_config(db)) is None

    def test_resolver_abstains_on_unrelated_folder(
        self, store_and_db: tuple[ConcreteAcquireStore, Path], tmp_path: Path
    ) -> None:
        """A grabbed follow does not force its tvdb onto an unrelated show folder."""
        store, db = store_and_db
        fid = store.follow.add(
            FollowedSeries(
                media_ref=MediaRef(tvdb_id=382389),
                title="Star Trek: Strange New Worlds",
                added_at=1,
            )
        )
        _seed_grabbed_episodes(store, tvdb=382389, followed_id=fid, eps=[(3, 9)])
        # A wholly unrelated folder whose episode is NOT covered by the grabbed set.
        other = _show_dir(tmp_path, "Breaking Bad", [(1, 1)])
        resolver = _build_follow_tvdb_resolver(_config(db))
        assert resolver is not None
        assert resolver(other) is None

    def test_title_matches_but_episodes_not_covered_abstains(
        self, store_and_db: tuple[ConcreteAcquireStore, Path], tmp_path: Path
    ) -> None:
        """Coverage-all in isolation: a TITLE-matching folder abstains when uncovered.

        The folder « Star Trek » passes the subset title guard against the follow,
        so the ONLY thing left to decide is coverage-all — its S05E01 file is NOT
        in the grabbed set (S03E09). A regression that weakened coverage-all
        (e.g. « any shared episode » instead of « covers ALL ») would wrongly
        force the tvdb; this abstains, proving the coverage check alone.
        """
        store, db = store_and_db
        fid = store.follow.add(
            FollowedSeries(
                media_ref=MediaRef(tvdb_id=382389),
                title="Star Trek: Strange New Worlds",
                added_at=1,
            )
        )
        _seed_grabbed_episodes(store, tvdb=382389, followed_id=fid, eps=[(3, 9)])
        # Title matches (« Star Trek » ⊆ follow), but the episode is NOT grabbed.
        show = _show_dir(tmp_path, "Star Trek", [(5, 1)])
        resolver = _build_follow_tvdb_resolver(_config(db))
        assert resolver is not None
        assert resolver(show) is None
