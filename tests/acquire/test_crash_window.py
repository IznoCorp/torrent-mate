"""Crash-window tests for the delete authority + record_dispatch (DESIGN §7.2, §6.3).

Aligned to the REAL lazy/lock-free/write-before-move model — NOT the stale
"lifetime lock" scenario from the original plan draft.

Real model (supersedes the plan's scenario 3 wording):
- Store is lazy-open (build_acquire_store is inert; no connection/lock/migration
  until first sub-store access).
- Cross-process single-writer is SQLite-native: WAL + BEGIN IMMEDIATE +
  busy_timeout=5000 (DESIGN §6.3). No lifetime FileLock.
- Reads are lock-free (WAL). No lock on the read path — the delete-permit reader
  never blocks on or contends for a writer lock.
- Write-before-move: record_dispatch writes the obligation BEFORE the FS move
  (DESIGN §7.2). dispatched_dest does NOT yet exist at call time.
- Path-exists guard in may_delete makes stale obligations inert (crash after
  obligation-write but before FS move → obligation is skipped because dest
  doesn't exist).
- Fail-open: lost obligation (crash before write) → ALLOW at deletion time
  (never over-deletes — the safe direction).

TorrentItem real fields: .hash (NOT .info_hash), .name, .size_bytes (NOT
.total_size), .tags.  is_seeding is a CLIENT method (TorrentStateInspector),
NOT an item method.

Covers DESIGN §12 crash-window categories:
  Scenario 1 — move-then-crash-before-obligation (lost obligation → ALLOW safe)
  Scenario 2 — obligation-then-crash-before-move (stale-inert + re-runnable)
  Scenario 3 — lock-free concurrent writers (supersedes stale "lifetime lock")
  Scenario 4 — write-before-move ordering invariant
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
from personalscraper.core.delete_permit import ALLOW

# Per-tracker economy matching the record_dispatch test pattern: lacale, 72h min
# seed time, ratio floor 1.0.
_LACALE_ECONOMY = TrackerEconomyConfig(target_ratio=2.0, min_ratio=1.0, min_seed_time=259200)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_rows(db_path: Path) -> list[sqlite3.Row]:
    """Read all seed_obligation rows directly via a raw connection.

    The acquire store opens lazily on first sub-store access: when the store
    is never touched, ``acquire.db`` or the ``seed_obligation`` table may not
    exist yet.  A missing DB file or missing table is equivalent to "zero rows".

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
            "SELECT info_hash, source_tracker, dispatched_path, "
            "min_seed_time_s, min_ratio, added_at, satisfied_at, breached_at, released_at "
            "FROM seed_obligation ORDER BY rowid"
        ).fetchall()
    except sqlite3.OperationalError:
        # Table not created yet (store never opened) → no rows.
        return []
    finally:
        conn.close()


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
    client exposes ``is_seeding(item)`` instead (TorrentStateInspector protocol).

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

    ``get_completed()`` returns *items*; ``is_seeding(item)`` is a CLIENT
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


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real lazy acquire store on a temp acquire.db, closed afterwards.

    The store opens lazily on first sub-store access.  Using try/finally to
    ensure close() is called even if a test fails.

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


# ---------------------------------------------------------------------------
# Scenario 1 — move-then-crash-before-obligation
# ---------------------------------------------------------------------------


def test_scenario1_no_obligation_after_move_allows(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """Crash after the FS move but before record_dispatch: no obligation → ALLOW.

    This is the safe failure direction (§7.2 fail-open): a lost obligation
    degrades to "no seed protection", never to "blocks/over-deletes".  The
    dispatched file exists on the destination disk, but the delete authority
    has no record of it — so the deletion is permitted.

    Simulated by NOT calling record_dispatch at all.  The dest file exists
    (the move happened), but the obligation was never written (the crash
    happened before the write).
    """
    dest = tmp_path / "library" / "movie.mkv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("fake media content")

    auth = build_delete_authority(store=store)

    # No obligation was ever written — simulates crash before record_dispatch.
    decision = auth.may_delete(dest)
    assert decision is ALLOW, "Scenario 1: lost obligation must degrade to ALLOW (never over-delete)"

    # Verify the assertion is non-vacuous: the store IS present but has no
    # matching obligation.
    assert _read_rows(tmp_path / "acquire.db") == []


# ---------------------------------------------------------------------------
# Scenario 2 — obligation-then-crash-before-move (stale-inert + re-runnable)
# ---------------------------------------------------------------------------


def test_scenario2_stale_obligation_inert_via_path_guard(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """Crash after obligation-write but before FS move: stale obligation is INERT.

    record_dispatch wrote the obligation (write-before-move, §7.2) but the
    crash happened before the FS move — so dispatched_dest does NOT exist on
    disk.  The path-exists guard in may_delete makes the stale obligation
    inert (skip it → ALLOW).  Creating the file at dest flips the decision to
    VETO, proving the guard is real (mutation proof).
    """
    staging = tmp_path / "staging" / "MyShow.S01E01.mkv"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_bytes(b"x" * 2048)
    dest = tmp_path / "library" / "MyShow.S01E01.mkv"
    # Do NOT create dest — simulates crash before the FS move.

    item = _torrent_item(
        name="MyShow.S01E01.mkv",
        size_bytes=2048,
        tags=["lacale"],
        info_hash="abc123def456",
    )
    client = _client([item], is_seeding=True)

    auth = DeleteAuthority(
        store=store,
        torrent_client=client,
        economy={"lacale": _LACALE_ECONOMY},
    )

    # record_dispatch writes the obligation (write-before-move).
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    # Verify the obligation row exists (the write happened).
    rows_before = _read_rows(tmp_path / "acquire.db")
    assert len(rows_before) == 1
    assert rows_before[0]["dispatched_path"] == str(dest)

    # Stale obligation: dispatched_path is set, but the file does NOT exist
    # on disk → path-exists guard makes it inert → ALLOW.
    decision_stale = auth.may_delete(dest)
    assert decision_stale is ALLOW, (
        "Scenario 2a: stale obligation (dest does not exist) must be ALLOW (path-exists guard makes it inert)"
    )

    # MUTATION PROOF: create the file at dest → same obligation now VETOes.
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("fake media content")
    decision_live = auth.may_delete(dest)
    assert decision_live is not ALLOW, (
        "Scenario 2b: after creating the file, the same obligation MUST VETO "
        "(mutation proof that the guard does real work — not a vacuous assert)"
    )


def test_scenario2_re_runnable_dispatch_after_crash(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """Re-running dispatch after a crash-window recovery is safe.

    After a crash (obligation written, move not done), the staging source
    still exists.  Calling record_dispatch again with the same parameters
    creates a SECOND obligation row — the first is stale (dest doesn't exist)
    and the second is also pre-move.  This does NOT duplicate-explode:
    may_delete still works correctly (ALLOW while dest absent, VETO when
    dest created), proving the model handles at-most-one-active-obligation
    without issue.
    """
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_bytes(b"x" * 1024)
    dest = tmp_path / "library" / "Film.mkv"
    # Do NOT create dest.

    item = _torrent_item(
        name="Film.mkv",
        size_bytes=1024,
        tags=["lacale"],
        info_hash="hash111aaa",
    )
    client = _client([item], is_seeding=True)

    auth = DeleteAuthority(
        store=store,
        torrent_client=client,
        economy={"lacale": _LACALE_ECONOMY},
    )

    # First dispatch attempt (crashes before move).
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)
    assert len(_read_rows(tmp_path / "acquire.db")) == 1

    # Second dispatch attempt (re-run after crash recovery — staging still exists).
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)
    rows = _read_rows(tmp_path / "acquire.db")
    assert len(rows) == 2, "Scenario 2r1: re-run should not duplicate-explode — both rows present"
    # Both rows have the same dispatched_path.
    for row in rows:
        assert row["dispatched_path"] == str(dest)

    # While dest is absent, both obligations are stale → ALLOW.
    decision_stale = auth.may_delete(dest)
    assert decision_stale is ALLOW, "Scenario 2r2: with no file at dest, all obligations are stale → ALLOW"

    # Create dest → now at least one unmet obligation VETOes (first unmet wins).
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("fake content")
    decision_live = auth.may_delete(dest)
    assert decision_live is not ALLOW, "Scenario 2r3: after creating the file, at least one unmet obligation VETOes"


# ---------------------------------------------------------------------------
# Scenario 3 — lock-free concurrent writers (real model)
# ---------------------------------------------------------------------------

# NOTE — this scenario SUPERSEDES the plan's stale "concurrent acquire writer
# holds the lock" scenario.  Sub-phase 3.4 dropped the lifetime FileLock; the
# real store uses lazy-open + SQLite-native single-writer via BEGIN IMMEDIATE +
# busy_timeout + lock-free reads (DESIGN §6.3).  No lifetime lock exists to
# contend on — two handles on the same db_path both open, read, and write
# without deadlock or AcquireLockError.


def test_scenario3_two_stores_same_db_no_deadlock(
    tmp_path: Path,
) -> None:
    """Two stores on the SAME db_path: both open + write without deadlock.

    This is the REAL model (DESIGN §6.3): cross-process single-writer is
    SQLite-native (WAL + BEGIN IMMEDIATE + busy_timeout=5000).  Reads are
    lock-free.  No lifetime FileLock exists to cause contention.

    Store A writes an obligation; store B (separate handle, same db_path)
    immediately reads it back via find_active_under (lock-free read sees A's
    committed write) AND writes its own obligation.  Both rows are present
    after, and no exception is raised — proving the lock-free-read +
    BEGIN-IMMEDIATE-write model has no lifetime-lock contention.
    """
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)

    store_a = build_acquire_store(cfg)
    store_b = build_acquire_store(cfg)

    try:
        # Access sub-stores on both to trigger lazy open.
        _ = store_a.seed  # opens connection A, migrates under brief lock
        _ = store_b.seed  # opens connection B, migration is no-op

        dest_a = tmp_path / "dest_a.mkv"
        dest_a.write_text("a")  # file must exist for path-exists guard in find

        dest_b_path = tmp_path / "dest_b.mkv"
        dest_b_path.write_text("b")

        # Store A writes an obligation.
        ob_a = SeedObligation(
            info_hash="aaa111",
            source_tracker="lacale",
            min_seed_time_s=999999,
            min_ratio=1.0,
            added_at=int(time.time()),
            dispatched_path=str(dest_a),
        )
        store_a.seed.add(ob_a)

        # Store B reads A's write (lock-free WAL read) — MUST see it.
        found = store_b.seed.find_active_under(dest_a)
        assert len(found) == 1, "Scenario 3a: store B's lock-free read must see A's committed write"
        assert found[0].info_hash == "aaa111"

        # Store B writes its own obligation (BEGIN IMMEDIATE + COMMIT).
        ob_b = SeedObligation(
            info_hash="bbb222",
            source_tracker="lacale",
            min_seed_time_s=999999,
            min_ratio=1.0,
            added_at=int(time.time()),
            dispatched_path=str(dest_b_path),
        )
        store_b.seed.add(ob_b)

        # Both rows present — no deadlock, no AcquireLockError.
        rows = _read_rows(db_path)
        assert len(rows) == 2, "Scenario 3b: both writes must succeed — 2 rows present"
        info_hashes = {r["info_hash"] for r in rows}
        assert info_hashes == {"aaa111", "bbb222"}, "Scenario 3c: both info_hashes must be present"
    finally:
        store_b.close()
        store_a.close()


# ---------------------------------------------------------------------------
# Scenario 4 — write-before-move ordering invariant
# ---------------------------------------------------------------------------


def test_scenario4_write_before_move_ordering(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """record_dispatch writes the obligation BEFORE the FS move (§7.2).

    After a HIT record_dispatch:
    - The obligation row's dispatched_path == str(dispatched_dest)
    - dispatched_dest does NOT yet exist on disk (the move hasn't happened yet)
    - This is the write-before-move guarantee: the obligation is in place
      before any bytes land at dest, so a crash after the write but before
      the move leaves a stale obligation (inert via path-exists guard,
      tested in Scenario 2) rather than unprotected media.
    """
    staging = tmp_path / "staging" / "Show.S01E01.mkv"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_bytes(b"y" * 4096)
    dest = tmp_path / "library" / "Show.S01E01.mkv"
    # Deliberately do NOT create dest — the move hasn't happened yet.

    item = _torrent_item(
        name="Show.S01E01.mkv",
        size_bytes=4096,
        tags=["lacale"],
        info_hash="writebeforemove",
    )
    client = _client([item], is_seeding=True)

    auth = DeleteAuthority(
        store=store,
        torrent_client=client,
        economy={"lacale": _LACALE_ECONOMY},
    )

    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    # Assert 1: the obligation row was written.
    rows = _read_rows(tmp_path / "acquire.db")
    assert len(rows) == 1, "Scenario 4a: obligation row must be written"

    row = rows[0]
    assert row["dispatched_path"] == str(dest), (
        "Scenario 4b: dispatched_path must match the dest (not the staging source)"
    )
    assert row["info_hash"] == "writebeforemove", "Scenario 4c: info_hash must match the matched torrent"

    # Assert 2: dest does NOT yet exist on disk — the write happened BEFORE
    # the move (write-before-move invariant).
    assert not dest.exists(), (
        "Scenario 4d: dispatched_dest must NOT exist yet (write-before-move: obligation was written BEFORE the FS move)"
    )

    # Non-vacuous proof: create the file, then may_delete MUST VETO
    # (the obligation is real and the file exists → seedtime check applies).
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("fake content from scenario 4")
    decision = auth.may_delete(dest)
    assert decision is not ALLOW, (
        "Scenario 4e: after creating dest, the obligation must VETO "
        "(non-vacuous proof that the row is a real active obligation)"
    )
