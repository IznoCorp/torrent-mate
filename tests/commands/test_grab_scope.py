"""The pre-run passes of ``grab`` keep to the instance's scope in a shared client.

Both passes take hashes from the acquire store and look them up in the client:
under a scope, a hash whose torrent sits in another category belongs to another
instance and is neither read as ours nor deleted.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from personalscraper.acquire import reconcile as reconcile_module
from personalscraper.acquire.context import AcquireContext
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.commands.grab import _reconcile_before_run, _reswitch_before_run
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.api_config import TorrentScope
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef

_SCOPE = TorrentScope(category="tm-dev", download_root=Path("/srv/tm-dev"))
_OWN_HASH = "a" * 40
_FOREIGN_HASH = "b" * 40


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _grab_row(store: ConcreteAcquireStore, info_hash: str, tvdb_id: int) -> None:
    """Insert a wanted row grabbed with *info_hash*."""
    rowid = store.wanted.add(
        WantedItem(media_ref=MediaRef(tvdb_id=tvdb_id), kind="episode", status="pending", enqueued_at=1_900_000_000)
    )
    assert store.wanted.claim_for_search(rowid, 1_900_000_100) is True
    store.wanted.mark_grabbed(rowid, info_hash)


def _dead(info_hash: str, category: str) -> TorrentItem:
    """A dead-swarm torrent of *category*, as the shared client reports it."""
    return TorrentItem(
        hash=info_hash,
        name="Show.S01E01.mkv",
        size_bytes=1,
        progress=0.0,
        state="stalledDL",
        category=category,
        swarm_seeds=0,
    )


def _client(*items: TorrentItem) -> MagicMock:
    """A client answering ``get_by_hashes`` over *items*, recording ``delete``."""
    client = MagicMock()
    client.get_by_hashes.side_effect = lambda hashes: [i for i in items if i.hash in hashes]
    return client


def _acquire(store: ConcreteAcquireStore, client: MagicMock) -> AcquireContext:
    """An acquire context holding *store* and *client*."""
    return SimpleNamespace(  # type: ignore[return-value]
        store=store, torrent_client=client, delete_authority=None, ownership=MagicMock()
    )


def test_scoped_reswitch_pass_never_deletes_another_instances_torrent(store: ConcreteAcquireStore) -> None:
    """The stalled hash sits in category ``prod``: the pass deletes nothing."""
    _grab_row(store, _FOREIGN_HASH, 1)
    client = _client(_dead(_FOREIGN_HASH, "prod"))

    _reswitch_before_run(_acquire(store, client), EventBus(), Console(quiet=True), scope=_SCOPE)

    client.delete.assert_not_called()


def test_scoped_reswitch_pass_still_deletes_its_own_dead_torrent(store: ConcreteAcquireStore) -> None:
    """The stalled hash sits in the scope's category: it is switched as before."""
    _grab_row(store, _OWN_HASH, 2)
    client = _client(_dead(_OWN_HASH, "tm-dev"))

    _reswitch_before_run(_acquire(store, client), EventBus(), Console(quiet=True), scope=_SCOPE)

    client.delete.assert_called_once_with(_OWN_HASH, delete_files=True)


def test_unscoped_reswitch_pass_is_unchanged(store: ConcreteAcquireStore) -> None:
    """Without a scope the category plays no part."""
    _grab_row(store, _FOREIGN_HASH, 3)
    client = _client(_dead(_FOREIGN_HASH, "prod"))

    _reswitch_before_run(_acquire(store, client), EventBus(), Console(quiet=True), scope=None)

    client.delete.assert_called_once_with(_FOREIGN_HASH, delete_files=True)


def _reconciled_items(
    monkeypatch: pytest.MonkeyPatch, store: ConcreteAcquireStore, client: MagicMock, scope: TorrentScope | None
) -> dict[str, TorrentItem] | None:
    """Run the reconcile pass and return the client view it handed the sweep."""
    seen: list[dict[str, TorrentItem] | None] = []

    def _capture(_store: object, _ownership: object, client_items: dict[str, TorrentItem] | None, **_kw: object):
        seen.append(client_items)
        return reconcile_module.ReconcileSummary()

    monkeypatch.setattr(reconcile_module, "reconcile_wanted", _capture)
    _reconcile_before_run(_acquire(store, client), EventBus(), Console(quiet=True), scope=scope)
    return seen[0]


def test_scoped_reconcile_view_leaves_out_another_instances_torrent(
    monkeypatch: pytest.MonkeyPatch, store: ConcreteAcquireStore
) -> None:
    """The sweep is handed only the scope's torrents."""
    _grab_row(store, _OWN_HASH, 4)
    _grab_row(store, _FOREIGN_HASH, 5)
    client = _client(_dead(_OWN_HASH, "tm-dev"), _dead(_FOREIGN_HASH, "prod"))

    assert set(_reconciled_items(monkeypatch, store, client, _SCOPE) or {}) == {_OWN_HASH}


def test_unscoped_reconcile_view_keeps_every_torrent(
    monkeypatch: pytest.MonkeyPatch, store: ConcreteAcquireStore
) -> None:
    """Without a scope the sweep sees both torrents."""
    _grab_row(store, _OWN_HASH, 6)
    _grab_row(store, _FOREIGN_HASH, 7)
    client = _client(_dead(_OWN_HASH, "tm-dev"), _dead(_FOREIGN_HASH, "prod"))

    assert set(_reconciled_items(monkeypatch, store, client, None) or {}) == {_OWN_HASH, _FOREIGN_HASH}


def test_scoped_reconcile_hands_the_sweep_the_foreign_hashes(
    monkeypatch: pytest.MonkeyPatch, store: ConcreteAcquireStore
) -> None:
    """A stored hash held in another category reaches the sweep as ``foreign``."""
    _grab_row(store, _OWN_HASH, 8)
    _grab_row(store, _FOREIGN_HASH, 9)
    client = _client(_dead(_OWN_HASH, "tm-dev"), _dead(_FOREIGN_HASH, "prod"))
    seen: dict[str, object] = {}

    def _capture(_store: object, _ownership: object, _items: object, **kw: object):
        seen.update(kw)
        return reconcile_module.ReconcileSummary()

    monkeypatch.setattr(reconcile_module, "reconcile_wanted", _capture)
    _reconcile_before_run(_acquire(store, client), EventBus(), Console(quiet=True), scope=_SCOPE)

    assert seen["foreign"] == {_FOREIGN_HASH}
