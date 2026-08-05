"""The spine correlates a dispatch by ``info_hash``, never by an exact path string.

Reproduces the EXACT production journey that lost 47 episode rows
(`docs/features/spine-truth/DESIGN.md` §1, established from
``~/.pm2/logs/personalscraper-watch-error.log``, run ``2026-08-05T03:40:50``)::

    ingest  →  097-TEMP/American.Dad.S15.…-FRAIG
    sort    →  002-TVSHOWS/American Dad/American.Dad.S15.…-FRAIG     ← NESTED under the show
    scrape  →  renames the ANCESTOR: 'American Dad' → 'American Dad! (2005)'
               and flattens the release folder into 'Saison 15/'
    dispatch → 002-TVSHOWS/American Dad! (2005)                      ← the show folder

The old ``move_path`` matched ``current_path`` by string EQUALITY, so renaming the ancestor
matched nothing; the release folder then vanished and ``prune_stale`` erased the row. A movie
survived only because sort lands it flat, already canonically named.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

STAGING = "/stage/002-TVSHOWS"
SHOW_BEFORE = f"{STAGING}/American Dad"
SHOW_AFTER = f"{STAGING}/American Dad! (2005)"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _grab_and_sort(store: ConcreteAcquireStore, info_hash: str, release: str, *, show: str = SHOW_BEFORE) -> None:
    """Drive a season grab through ingest + sort, landing NESTED under *show*."""
    store.provenance.upsert_grab(
        info_hash, followed_id=None, media_ref=MediaRef(tvdb_id=73141), kind="season", grabbed_at=1
    )
    store.provenance.set_ingest(info_hash, ingest_path=f"/stage/097-TEMP/{release}", ingested_at=2)
    store.provenance.move_path(f"/stage/097-TEMP/{release}", f"{show}/{release}")


class TestAncestorRenameRepointsTheSubtree:
    """A directory move re-points every tracked path underneath it, not just its own node."""

    def test_show_folder_rename_repoints_its_nested_release_rows(self, store: ConcreteAcquireStore) -> None:
        """The exact prod break: the scrape renames the ancestor, the nested rows follow."""
        _grab_and_sort(store, "h15", "American.Dad.S15.MULTI.VFF.1080p.WEB-FRAIG")
        _grab_and_sort(store, "h17", "American.Dad.S17.MULTI.VFF.1080p.WEB-FRAIG")

        # The scrape renames the SHOW folder and flattens the release folders into Saison NN/.
        store.provenance.move_path(SHOW_BEFORE, SHOW_AFTER)

        for info_hash in ("h15", "h17"):
            row = store.provenance.by_hash(info_hash)
            assert row is not None
            assert row.current_path == SHOW_AFTER, "a nested row must follow its renamed ancestor"

    def test_exact_path_move_still_behaves_as_before(self, store: ConcreteAcquireStore) -> None:
        """The flat (movie) case is untouched: an exact match still moves to the new path."""
        store.provenance.upsert_grab(
            "m1", followed_id=None, media_ref=MediaRef(tmdb_id=426254), kind="movie", grabbed_at=1
        )
        store.provenance.set_ingest("m1", ingest_path="/stage/097-TEMP/Marjorie.Prime", ingested_at=2)
        store.provenance.move_path("/stage/097-TEMP/Marjorie.Prime", "/stage/001-MOVIES/Marjorie Prime (2017)")
        row = store.provenance.by_hash("m1")
        assert row is not None and row.current_path == "/stage/001-MOVIES/Marjorie Prime (2017)"

    def test_a_sibling_folder_sharing_a_name_prefix_is_never_touched(self, store: ConcreteAcquireStore) -> None:
        """Containment is by path COMPONENT: 'American Dad 2' is not inside 'American Dad'."""
        _grab_and_sort(store, "sib", "Release", show=f"{STAGING}/American Dad 2")
        store.provenance.move_path(SHOW_BEFORE, SHOW_AFTER)
        row = store.provenance.by_hash("sib")
        assert row is not None
        assert row.current_path == f"{STAGING}/American Dad 2/Release"

    def test_a_terminal_row_is_not_dragged_by_a_later_staging_rename(self, store: ConcreteAcquireStore) -> None:
        """A dispatched journey is history: a later run recreating the folder must not move it."""
        _grab_and_sort(store, "old", "Old.Release")
        store.provenance.move_path(SHOW_BEFORE, SHOW_AFTER)
        store.provenance.record_dispatch_by_path(SHOW_AFTER, dispatch_path="/disk/series/AD", dispatched_at=9)
        store.provenance.move_path(SHOW_AFTER, f"{STAGING}/Something Else")
        row = store.provenance.by_hash("old")
        assert row is not None and row.current_path == SHOW_AFTER


class TestDispatchCorrelatesByHash:
    """The dispatch resolves the folder to hashes, then writes keyed on the hash."""

    def test_dispatching_a_show_folder_closes_every_row_it_contains(self, store: ConcreteAcquireStore) -> None:
        """Two season packs merged into one show folder are BOTH recorded as dispatched."""
        _grab_and_sort(store, "h15", "American.Dad.S15-FRAIG")
        _grab_and_sort(store, "h17", "American.Dad.S17-FRAIG")
        store.provenance.move_path(SHOW_BEFORE, SHOW_AFTER)

        store.provenance.record_dispatch_by_path(
            SHOW_AFTER, dispatch_path="/Volumes/Disk2/series/American Dad! (2005)", dispatched_at=42
        )

        for info_hash in ("h15", "h17"):
            row = store.provenance.by_hash(info_hash)
            assert row is not None
            assert row.status == "dispatched"
            assert row.dispatch_path == "/Volumes/Disk2/series/American Dad! (2005)"
            assert row.dispatched_at == 42

    def test_a_stale_nested_path_is_still_closed_by_the_dispatch(self, store: ConcreteAcquireStore) -> None:
        """Belt and braces: a stage that forgot to re-point still gets its journey closed.

        This is the failure the old exact-equality UPDATE could not survive. The row here
        never followed the rename — the dispatch of the containing folder closes it anyway.
        """
        _grab_and_sort(store, "stale", "American.Dad.S15-FRAIG", show=SHOW_AFTER)
        store.provenance.record_dispatch_by_path(SHOW_AFTER, dispatch_path="/disk/series/AD", dispatched_at=7)
        row = store.provenance.by_hash("stale")
        assert row is not None and row.status == "dispatched"

    def test_an_untracked_folder_dispatches_without_touching_anything(self, store: ConcreteAcquireStore) -> None:
        """ACC-06: a manual/direct item has no row, and no other row is collaterally closed."""
        _grab_and_sort(store, "h15", "American.Dad.S15-FRAIG")
        store.provenance.move_path(SHOW_BEFORE, SHOW_AFTER)
        store.provenance.record_dispatch_by_path(
            f"{STAGING}/Some Manual Drop", dispatch_path="/disk/x", dispatched_at=5
        )
        row = store.provenance.by_hash("h15")
        assert row is not None and row.status == "ingested"

    def test_a_dispatched_row_is_not_restamped_by_a_later_dispatch(self, store: ConcreteAcquireStore) -> None:
        """The completed journey is an audit record — a later run must not rewrite its dates."""
        _grab_and_sort(store, "h15", "American.Dad.S15-FRAIG")
        store.provenance.move_path(SHOW_BEFORE, SHOW_AFTER)
        store.provenance.record_dispatch_by_path(SHOW_AFTER, dispatch_path="/disk/first", dispatched_at=10)
        store.provenance.record_dispatch_by_path(SHOW_AFTER, dispatch_path="/disk/second", dispatched_at=20)
        row = store.provenance.by_hash("h15")
        assert row is not None
        assert row.dispatch_path == "/disk/first"
        assert row.dispatched_at == 10

    def test_containment_matches_across_unicode_normalisation(self, store: ConcreteAcquireStore) -> None:
        """The FS stores NFD, callers often hold NFC — the containment test sees through it."""
        nfd_show = unicodedata.normalize("NFD", "/stage/002-TVSHOWS/Café Society (2016)")
        nfc_show = unicodedata.normalize("NFC", "/stage/002-TVSHOWS/Café Society (2016)")
        assert nfd_show != nfc_show
        store.provenance.upsert_grab(
            "nfc1", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="episode", grabbed_at=1
        )
        store.provenance.set_ingest("nfc1", ingest_path=f"{nfd_show}/Release", ingested_at=2)
        store.provenance.record_dispatch_by_path(nfc_show, dispatch_path="/disk/x", dispatched_at=3)
        row = store.provenance.by_hash("nfc1")
        assert row is not None and row.status == "dispatched"


class TestScrapeStampRepointsToTheLiveFolder:
    """The scrape stamp is the moment the item's live location becomes the media folder."""

    def test_scrape_stamp_collapses_a_nested_row_onto_the_scraped_folder(self, store: ConcreteAcquireStore) -> None:
        """No rename happened (the show folder was already canonical) — the row still follows.

        Without this, a release nested under an ALREADY-canonical show folder keeps pointing
        at the release directory the scrape just flattened away, and ``prune_stale`` erases
        the journey before the dispatch can close it.
        """
        _grab_and_sort(store, "h15", "American.Dad.S15-FRAIG", show=SHOW_AFTER)
        store.provenance.set_scrape_run(SHOW_AFTER, run_uid="runX", scraped_at=8)
        row = store.provenance.by_hash("h15")
        assert row is not None
        assert row.current_path == SHOW_AFTER, "the scraped folder IS the item's live location"
        assert row.status == "scraped"
        assert row.scraped_at == 8
        assert row.scrape_run_uid == "runX"

    def test_scrape_stamp_leaves_a_terminal_row_alone(self, store: ConcreteAcquireStore) -> None:
        """A dispatched row is not re-opened by a later scrape of the same folder."""
        _grab_and_sort(store, "h15", "American.Dad.S15-FRAIG", show=SHOW_AFTER)
        store.provenance.record_dispatch_by_path(SHOW_AFTER, dispatch_path="/disk/x", dispatched_at=3)
        store.provenance.set_scrape_run(SHOW_AFTER, run_uid="runY", scraped_at=9)
        row = store.provenance.by_hash("h15")
        assert row is not None and row.status == "dispatched"
