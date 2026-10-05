"""A ``library.db`` that opens but holds no library: ``library.unavailable``, never a « no such table » 500."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from personalscraper.app.errors import AppUnavailable, RefusalCode
from personalscraper.app.library.deleting import LibraryDeletion
from personalscraper.app.library.listing import LibrarySort
from personalscraper.app.library.reads import LibraryReads
from personalscraper.indexer.library_view import LibraryIndex
from tests.unit.app.library.world import World


def _reads_over(world: World, index_db: Path) -> LibraryReads:
    """Build the reads over another index, sharing the world's catalogue view and sheets.

    Args:
        world: The service's world.
        index_db: The index the service reads.

    Returns:
        The reads; they open nothing until a read asks.
    """
    return LibraryReads(index=LibraryIndex(index_db), view=world.view, sheets=world.sheets)


def _deletion_over(world: World, index_db: Path) -> LibraryDeletion:
    """Build the deletion over another index.

    Args:
        world: The service's world.
        index_db: The index the service reads.

    Returns:
        The deletion; it opens nothing until a deletion asks.
    """
    return LibraryDeletion(index=LibraryIndex(index_db), index_db=index_db, data_dir=world.data_dir)


@pytest.mark.parametrize("case", ["zero_byte", "schema_less"])
def test_an_index_without_the_item_table_is_unavailable(world: World, tmp_path: Path, case: str) -> None:
    """A file SQLite opens but that holds no ``item`` table is refused 503, the same as an absent one."""
    index_db = tmp_path / f"{case}.db"
    if case == "zero_byte":
        index_db.write_bytes(b"")
    else:
        with sqlite3.connect(index_db) as conn:
            conn.execute("CREATE TABLE unrelated (id INTEGER)")
        sqlite3.connect(index_db).close()

    with pytest.raises(AppUnavailable) as refused:
        _reads_over(world, index_db).read_items(
            world.actor, category=None, sort=LibrarySort.RECENT, reversed_=False, query=None, page=0
        )

    assert refused.value.code is RefusalCode.LIBRARY_UNAVAILABLE


def test_an_unreadable_index_counts_as_an_unmounted_disk(world: World, tmp_path: Path) -> None:
    """Plex's bundle clean is told a disk is gone when the index cannot say: the trash is kept."""
    absent = tmp_path / "absent.db"

    assert _deletion_over(world, absent)._disk_unmounted() is True  # noqa: SLF001 - the branch under test is private
