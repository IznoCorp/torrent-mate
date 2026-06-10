"""Tests for DeleteAuthority.record_dispatch + mark_breach (real torrent API).

These tests mock the REAL ``TorrentItem`` shape (``.hash`` / ``.name`` /
``.size_bytes`` / ``.tags``) and the REAL client surface
(``get_completed()`` + ``is_seeding(item)`` as a CLIENT method taking the
item) — NOT the fictional ``total_size`` / ``info_hash`` / ``item.is_seeding()``
of the original plan draft. The point is that the implementation matches
production: a vacuous mock that codes against fields the real API lacks would
pass ``make check`` while hiding a real bug (repo memory:
"dispatched algo/API code ships vacuous tests").

Covers DESIGN §7.2 (HIT / MISS with miss-reason no-live-torrent | not-seeding |
name+size-ambiguous | tracker-unresolved; write-before-move; lock-free
fail-soft) and §7.3 (mark_breach on unmet at dispatch).
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from personalscraper.acquire.delete_authority import DeleteAuthority, build_delete_authority
from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.api_config import TrackerEconomyConfig

# A representative per-tracker economy: lacale, 72h min seed, ratio floor 1.0.
_LACALE_ECONOMY = TrackerEconomyConfig(target_ratio=2.0, min_ratio=1.0, min_seed_time=259200)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real lazy acquire store on a temp acquire.db, closed afterwards.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        A :class:`ConcreteAcquireStore` (opens on first sub-store access).
    """
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _torrent_item(
    *,
    name: str,
    size_bytes: int,
    tags: list[str] | None = None,
    info_hash: str = "deadbeefcafebabe",
) -> SimpleNamespace:
    """Build a TorrentItem-shaped object using the REAL field names.

    Mirrors ``personalscraper.api.torrent._base.TorrentItem``: the info hash is
    ``.hash`` (NOT ``.info_hash``), the total size is ``.size_bytes`` (NOT
    ``.total_size``), and there is NO ``.is_seeding()`` method on the item — the
    client exposes ``is_seeding(item)`` instead.

    Args:
        name: Torrent display name (the basename to correlate on).
        size_bytes: Total size in bytes.
        tags: Tag labels (source-tracker convention).
        info_hash: The info hash exposed as ``.hash``.

    Returns:
        A SimpleNamespace carrying exactly the fields record_dispatch reads.
    """
    return SimpleNamespace(
        hash=info_hash,
        name=name,
        size_bytes=size_bytes,
        tags=tags if tags is not None else [],
    )


def _client(items: list[SimpleNamespace], *, is_seeding: bool = True) -> MagicMock:
    """Build a torrent-client mock with the REAL method surface.

    ``get_completed()`` returns the items; ``is_seeding(item)`` is a CLIENT
    method (takes the item, returns a bool) — matching
    :class:`TorrentStateInspector`.

    Args:
        items: The completed torrents returned by ``get_completed()``.
        is_seeding: The bool every ``is_seeding(item)`` call returns.

    Returns:
        A configured :class:`MagicMock`.
    """
    client = MagicMock()
    client.get_completed.return_value = items
    client.is_seeding.return_value = is_seeding
    return client


def _read_rows(db_path: Path) -> list[sqlite3.Row]:
    """Read all seed_obligation rows directly via a raw connection.

    The acquire store opens lazily on first sub-store access: in the MISS /
    no-op cases nothing ever touches ``store.seed``, so neither ``acquire.db``
    nor the ``seed_obligation`` table exists yet. A missing DB file or missing
    table is therefore equivalent to "zero rows" — exactly the assertion the
    MISS tests want.

    Args:
        db_path: Path to acquire.db.

    Returns:
        The full row list (possibly empty).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT info_hash, source_tracker, dispatched_path, min_seed_time_s, min_ratio FROM seed_obligation"
        ).fetchall()
    except sqlite3.OperationalError:
        # Table not created yet (store never opened) → no rows.
        return []
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# HIT
# ═══════════════════════════════════════════════════════════════════════════


def test_record_dispatch_hit_writes_obligation(
    store: ConcreteAcquireStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """HIT: basename+size match, seeding, tag matches a configured tracker.

    The obligation row carries info_hash=item.hash, dispatched_path=dest, and
    the economy's min_seed_time / min_ratio. The HIT is logged.
    """
    staging = tmp_path / "staging" / "MyShow.S01E01.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 2048)
    dest = tmp_path / "library" / "MyShow.S01E01.mkv"

    item = _torrent_item(
        name="MyShow.S01E01.mkv",
        size_bytes=2048,
        tags=["lacale"],
        info_hash="abc123def456",
    )
    client = _client([item], is_seeding=True)

    auth = DeleteAuthority(store=store, torrent_client=client, economy={"lacale": _LACALE_ECONOMY})
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    rows = _read_rows(tmp_path / "acquire.db")
    assert len(rows) == 1
    row = rows[0]
    assert row["info_hash"] == "abc123def456"
    assert row["dispatched_path"] == str(dest)
    assert row["source_tracker"] == "lacale"
    assert row["min_seed_time_s"] == 259200
    assert row["min_ratio"] == 1.0
    assert "acquire.record_dispatch.hit" in caplog.text


def test_record_dispatch_hit_calls_is_seeding_with_item(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """The seeding check goes through the CLIENT method ``is_seeding(item)``.

    Proves the implementation uses the real ``TorrentStateInspector`` surface
    (client method taking the item) rather than a non-existent item method.
    """
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    item = _torrent_item(name="Film.mkv", size_bytes=512, tags=["lacale"])
    client = _client([item], is_seeding=True)

    auth = DeleteAuthority(store=store, torrent_client=client, economy={"lacale": _LACALE_ECONOMY})
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    client.is_seeding.assert_called_once_with(item)


# ═══════════════════════════════════════════════════════════════════════════
# MISS family
# ═══════════════════════════════════════════════════════════════════════════


def test_record_dispatch_miss_not_seeding(
    store: ConcreteAcquireStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """MISS: matching torrent but client.is_seeding(item) is False → no row, reason not-seeding."""
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    item = _torrent_item(name="Film.mkv", size_bytes=512, tags=["lacale"])
    client = _client([item], is_seeding=False)

    auth = DeleteAuthority(store=store, torrent_client=client, economy={"lacale": _LACALE_ECONOMY})
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    assert _read_rows(tmp_path / "acquire.db") == []
    assert "acquire.record_dispatch.miss" in caplog.text
    assert "not-seeding" in caplog.text


def test_record_dispatch_miss_no_match(
    store: ConcreteAcquireStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """MISS: no completed torrent matches basename+size → no row, reason no-live-torrent."""
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    # Different name AND different size.
    other = _torrent_item(name="OtherFilm.mkv", size_bytes=999, tags=["lacale"])
    client = _client([other], is_seeding=True)

    auth = DeleteAuthority(store=store, torrent_client=client, economy={"lacale": _LACALE_ECONOMY})
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    assert _read_rows(tmp_path / "acquire.db") == []
    assert "no-live-torrent" in caplog.text


def test_record_dispatch_miss_size_mismatch(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """MISS: same basename but different size_bytes → no row (size disambiguates)."""
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    item = _torrent_item(name="Film.mkv", size_bytes=4096, tags=["lacale"])  # wrong size
    client = _client([item], is_seeding=True)

    auth = DeleteAuthority(store=store, torrent_client=client, economy={"lacale": _LACALE_ECONOMY})
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    assert _read_rows(tmp_path / "acquire.db") == []


def test_record_dispatch_miss_ambiguous(
    store: ConcreteAcquireStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """MISS: two completed torrents share basename+size → no guess, reason name+size-ambiguous."""
    staging = tmp_path / "staging" / "Dup.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 1000)
    dest = tmp_path / "library" / "Dup.mkv"

    a = _torrent_item(name="Dup.mkv", size_bytes=1000, tags=["lacale"], info_hash="aaaa")
    b = _torrent_item(name="Dup.mkv", size_bytes=1000, tags=["lacale"], info_hash="bbbb")
    client = _client([a, b], is_seeding=True)

    auth = DeleteAuthority(store=store, torrent_client=client, economy={"lacale": _LACALE_ECONOMY})
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    assert _read_rows(tmp_path / "acquire.db") == []
    assert "name+size-ambiguous" in caplog.text


def test_record_dispatch_miss_tracker_unresolved(
    store: ConcreteAcquireStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """MISS: a matching seeding torrent but no tag maps to a configured economy.

    This is the honest TODAY case: manually-added torrents carry no source
    tag, so the tracker is unresolved and no obligation is written (no global
    default is invented).
    """
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    # Tags present but none of them is a configured economy tracker.
    item = _torrent_item(name="Film.mkv", size_bytes=512, tags=["manual", "hd"])
    client = _client([item], is_seeding=True)

    auth = DeleteAuthority(store=store, torrent_client=client, economy={"lacale": _LACALE_ECONOMY})
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    assert _read_rows(tmp_path / "acquire.db") == []
    assert "tracker-unresolved" in caplog.text


def test_record_dispatch_miss_no_economy_configured(
    store: ConcreteAcquireStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """MISS: economy map empty/None → every tag is unresolvable, reason tracker-unresolved."""
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    item = _torrent_item(name="Film.mkv", size_bytes=512, tags=["lacale"])
    client = _client([item], is_seeding=True)

    auth = DeleteAuthority(store=store, torrent_client=client, economy=None)
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    assert _read_rows(tmp_path / "acquire.db") == []
    assert "tracker-unresolved" in caplog.text


# ═══════════════════════════════════════════════════════════════════════════
# Fail-soft / no-op
# ═══════════════════════════════════════════════════════════════════════════


def test_record_dispatch_fail_soft_on_client_error(
    store: ConcreteAcquireStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """get_completed() raises → record_dispatch swallows it (no raise, no row)."""
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    client = MagicMock()
    client.get_completed.side_effect = RuntimeError("client unreachable")

    auth = DeleteAuthority(store=store, torrent_client=client, economy={"lacale": _LACALE_ECONOMY})
    # Must NOT raise.
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    assert _read_rows(tmp_path / "acquire.db") == []


def test_record_dispatch_no_client_is_noop(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """No torrent client → record_dispatch is a silent no-op (no row, no get_completed)."""
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    auth = DeleteAuthority(store=store, torrent_client=None, economy={"lacale": _LACALE_ECONOMY})
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    assert _read_rows(tmp_path / "acquire.db") == []


def test_record_dispatch_no_store_is_noop(tmp_path: Path) -> None:
    """No store → record_dispatch is a silent no-op and never touches the client."""
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    client = _client([_torrent_item(name="Film.mkv", size_bytes=512, tags=["lacale"])])
    auth = DeleteAuthority(store=None, torrent_client=client, economy={"lacale": _LACALE_ECONOMY})
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    client.get_completed.assert_not_called()


def test_record_dispatch_stat_error_on_missing_file(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """staging_source missing → no row (size cannot be computed; handled gracefully)."""
    staging = tmp_path / "staging" / "ghost.mkv"  # never created
    dest = tmp_path / "library" / "ghost.mkv"

    item = _torrent_item(name="ghost.mkv", size_bytes=512, tags=["lacale"])
    client = _client([item], is_seeding=True)

    auth = DeleteAuthority(store=store, torrent_client=client, economy={"lacale": _LACALE_ECONOMY})
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    assert _read_rows(tmp_path / "acquire.db") == []


# ═══════════════════════════════════════════════════════════════════════════
# mark_breach (DESIGN §7.3)
# ═══════════════════════════════════════════════════════════════════════════


def test_mark_breach_stamps_descendant_obligation(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """mark_breach(D) stamps breached_at on an active obligation under D/x.mkv."""
    dest_dir = tmp_path / "D"
    child = dest_dir / "x.mkv"
    ob = SeedObligation(
        info_hash="breach1",
        source_tracker="lacale",
        min_seed_time_s=999999,
        min_ratio=1.0,
        added_at=int(time.time()),
        dispatched_path=str(child),
    )
    store.seed.add(ob)

    auth = build_delete_authority(store=store)
    auth.mark_breach(dest_dir)

    found = store.seed.find_by_dispatched_path(child)
    assert found is not None
    assert found.breached_at is not None


def test_mark_breach_no_store_is_noop(tmp_path: Path) -> None:
    """mark_breach on a no-store authority is a silent no-op (never raises)."""
    auth = build_delete_authority(store=None)
    auth.mark_breach(tmp_path / "D")


def test_mark_breach_fail_soft_on_store_error(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """mark_breach swallows store write errors (fail-soft)."""
    auth = build_delete_authority(store=store)
    from unittest.mock import patch

    with patch.object(store.seed, "mark_breached_under", side_effect=RuntimeError("db locked")):
        # Must NOT raise.
        auth.mark_breach(tmp_path / "D")
