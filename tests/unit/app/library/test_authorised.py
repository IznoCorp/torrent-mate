"""The library services authorise its actor before it touches a store.

An in-process caller is refused what the v1 perimeter refuses an HTTP one: the same
requirement, the same refusal, and nothing opened, locked or reserved before it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import Right
from personalscraper.app.errors import AppForbidden, RefusalCode
from personalscraper.app.library import deleting as library_service
from personalscraper.app.library.listing import LibrarySort
from personalscraper.app.library.reads import LibraryReads
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.library_view import LibraryIndex
from tests.unit.app.library.test_delete_media import Shelf, shelf
from tests.unit.app.library.world import World

__all__ = ["shelf"]

_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)
#: The preprod's ceiling: deletion is forbidden to every account, Admin included.
_PREPROD_CEILING = InstanceCeiling(forbidden=frozenset({Right.LIBRARY_DELETE}), read_only=False)


def _ordinary(*rights: Right) -> Actor:
    """An ordinary actor holding exactly the rights given, under no ceiling.

    Args:
        *rights: The rights its role carries.

    Returns:
        The actor.
    """
    return Actor(
        account_id="account-guest",
        name="Guest",
        role_id="guest",
        role_kind=RoleKind.ORDINARY,
        role_rights=frozenset(rights),
        ceiling=_NO_CEILING,
    )


def test_a_reader_without_library_read_is_refused_before_the_index_opens(world: World, tmp_path: Path) -> None:
    """``right.missing``, not ``library.unavailable``: the refusal comes before the index is opened."""
    unreadable = tmp_path / "unreadable.db"
    unreadable.write_bytes(b"")
    service = LibraryReads(index=LibraryIndex(unreadable), view=world.view, sheets=world.sheets)
    try:
        with pytest.raises(AppForbidden) as refused:
            service.read_items(
                _ordinary(Right.ACQUISITION_REQUEST),
                category=None,
                sort=LibrarySort.RECENT,
                reversed_=False,
                query=None,
                page=0,
            )
    finally:
        world.view.close()

    assert refused.value.code is RefusalCode.RIGHT_MISSING
    assert refused.value.params == {"rights": [Right.LIBRARY_READ.value]}


def test_the_system_under_the_preprod_ceiling_never_deletes(shelf: Shelf, monkeypatch: pytest.MonkeyPatch) -> None:
    """``instance.forbidden_write``: ``pipeline.lock`` is not taken and the folder stays."""
    _, folder = shelf.movie("Movie (2020)", "11")
    locked: list[Path] = []
    real_acquire = library_service.acquire_pipeline_lock

    def recording_acquire(lock_file: Path, *args: object, **kwargs: object) -> bool:
        """Record the lock asked, then take it as the service would."""
        locked.append(lock_file)
        return real_acquire(lock_file, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(library_service, "acquire_pipeline_lock", recording_acquire)
    system = Actor.system(_PREPROD_CEILING, account_id="owner", name="Owner")

    with pytest.raises(AppForbidden) as refused:
        shelf.deletion.delete_media(system, [MediaRef(tmdb_id=11)])

    assert refused.value.code is RefusalCode.INSTANCE_FORBIDDEN_WRITE
    assert refused.value.params == {"right": Right.LIBRARY_DELETE.value}
    assert locked == []
    assert folder.is_dir()
    assert shelf.journal() == []


def test_an_asker_without_library_rescrape_queues_no_request(world: World) -> None:
    """``right.missing``: nothing is queued."""
    movie = world.index.item("Heat", tmdb="949")
    world.index.movie_file(movie, "films/Heat")

    with pytest.raises(AppForbidden) as refused:
        world.rescrape.request_rescrape(_ordinary(Right.LIBRARY_READ), MediaRef(tmdb_id=949))

    assert refused.value.code is RefusalCode.RIGHT_MISSING
    view = world.runs.queue_view()
    assert (view.running, view.queued) == (None, ())
