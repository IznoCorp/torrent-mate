"""Tests for the seed-obligation sweep (``acquire.obligations``).

The sweep is the single writer of ``satisfied_at`` / ``released_at``: it asks
the torrent client once about every open obligation, marks the ones whose floor
is reached as satisfied, and releases the ones whose torrent stayed gone for
the confirmation delay. Fake client, real store over a tmp ``acquire.db``.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from personalscraper.acquire.delete_authority import DeleteAuthority
from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.obligations import SeedRule, is_met, sweep_obligations
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.delete_permit import ALLOW
from personalscraper.core.sqlite import apply_migrations

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "acquire" / "migrations"

_FLOOR_S = 259_200  # 72 h, C411's seed-time floor
_NOW = 1_800_000_000
_CONFIRM_S = 1800
_RULE = SeedRule(count_ratio=True, grace_s=0, ratio_margin=0.1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real lazy acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


class FakeClient:
    """A torrent client answering ``get_by_hashes`` from a fixed list (or raising)."""

    def __init__(self, items: list[SimpleNamespace] | None = None, error: Exception | None = None) -> None:
        """Store the canned torrents and the optional error to raise.

        Args:
            items: Torrents the client holds.
            error: When set, ``get_by_hashes`` raises it.
        """
        self.items = items or []
        self.error = error
        self.calls: list[set[str]] = []

    def get_by_hashes(self, hashes: set[str]) -> list[SimpleNamespace]:
        """Record the call; raise the configured error or return the matching items."""
        self.calls.append(set(hashes))
        if self.error is not None:
            raise self.error
        return [i for i in self.items if i.hash in hashes]


def _item(info_hash: str, *, seeding_time_s: int | None, ratio: float = 0.0) -> SimpleNamespace:
    """Build a TorrentItem-shaped object with the fields the sweep reads."""
    return SimpleNamespace(hash=info_hash, seeding_time_s=seeding_time_s, ratio=ratio)


def _add(store: ConcreteAcquireStore, info_hash: str = "aaaa", *, path: str | None = None, added_at: int = _NOW) -> int:
    """Insert an open C411 obligation and return its id."""
    return store.seed.add(
        SeedObligation(
            info_hash=info_hash,
            source_tracker="c411",
            min_seed_time_s=_FLOOR_S,
            min_ratio=1.0,
            added_at=added_at,
            dispatched_path=path,
        )
    )


def _row(store: ConcreteAcquireStore, obligation_id: int) -> sqlite3.Row:
    """Read one seed_obligation row back."""
    conn = sqlite3.connect(store._db_path)  # noqa: SLF001
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM seed_obligation WHERE id = ?", (obligation_id,)).fetchone()  # type: ignore[no-any-return]
    finally:
        conn.close()


def _sweep(store: ConcreteAcquireStore, client: FakeClient, now: int = _NOW, rule: SeedRule = _RULE):  # noqa: ANN202
    """Run one sweep with the default confirmation delay."""
    return sweep_obligations(store, client, now=now, rule=rule, confirm_absent_after_s=_CONFIRM_S)  # type: ignore[arg-type]


# -- 1, 2, 3: when an obligation is met --------------------------------------------------------


def test_present_torrent_seeded_past_the_floor_is_satisfied(store: ConcreteAcquireStore) -> None:
    """A torrent seeded for at least the floor gets ``satisfied_at == now``."""
    oid = _add(store)
    report = _sweep(store, FakeClient([_item("aaaa", seeding_time_s=_FLOOR_S)]))
    assert _row(store, oid)["satisfied_at"] == _NOW
    assert (report.open, report.satisfied, report.client_error) == (1, 1, False)


def test_under_the_floor_or_unknown_seeding_time_is_untouched(store: ConcreteAcquireStore) -> None:
    """Under the floor, or a ``None`` seeding time, writes nothing."""
    first, second = _add(store, "aaaa"), _add(store, "bbbb")
    client = FakeClient([_item("aaaa", seeding_time_s=_FLOOR_S - 1), _item("bbbb", seeding_time_s=None)])
    report = _sweep(store, client)
    assert _row(store, first)["satisfied_at"] is None
    assert _row(store, second)["satisfied_at"] is None
    assert report.satisfied == 0


@pytest.mark.parametrize(
    ("ratio", "count_ratio", "expected"),
    [(1.1, True, True), (1.05, True, False), (5.0, False, False)],
)
def test_ratio_arm_needs_the_margin_and_the_rule(
    store: ConcreteAcquireStore, ratio: float, count_ratio: bool, expected: bool
) -> None:
    """Ratio over ``min_ratio + margin`` with time under the floor satisfies iff ``count_ratio``."""
    oid = _add(store)
    rule = SeedRule(count_ratio=count_ratio, grace_s=0, ratio_margin=0.1)
    _sweep(store, FakeClient([_item("aaaa", seeding_time_s=10, ratio=ratio)]), rule=rule)
    assert (_row(store, oid)["satisfied_at"] == _NOW) is expected


def test_is_met_is_pure_and_reads_the_snapshot_floors() -> None:
    """``is_met`` compares seeded seconds to the floor, ``None`` is never met."""
    ob = SeedObligation("aaaa", "c411", _FLOOR_S, 1.0, _NOW)
    assert is_met(ob, _item("aaaa", seeding_time_s=_FLOOR_S), _RULE)  # type: ignore[arg-type]
    assert not is_met(ob, _item("aaaa", seeding_time_s=None), _RULE)  # type: ignore[arg-type]
    assert not is_met(ob, _item("aaaa", seeding_time_s=_FLOOR_S - 1), SeedRule(False, 0, 0.1))  # type: ignore[arg-type]


# -- 4: absence is confirmed before a release ------------------------------------------------


def test_absent_torrent_is_released_only_after_the_confirmation_delay(store: ConcreteAcquireStore) -> None:
    """First absence marks ``absent_since``; the release needs 1 800 s more."""
    oid = _add(store)
    empty = FakeClient([])
    first = _sweep(store, empty, now=_NOW)
    assert (_row(store, oid)["absent_since"], _row(store, oid)["released_at"]) == (_NOW, None)
    assert first.marked_absent == 1

    _sweep(store, empty, now=_NOW + 60)
    assert _row(store, oid)["released_at"] is None

    last = _sweep(store, empty, now=_NOW + _CONFIRM_S)
    assert _row(store, oid)["released_at"] == _NOW + _CONFIRM_S
    assert last.released == 1


def test_a_torrent_seen_again_clears_the_absence(store: ConcreteAcquireStore) -> None:
    """A torrent that comes back before the delay resets ``absent_since``."""
    oid = _add(store)
    _sweep(store, FakeClient([]), now=_NOW)
    _sweep(store, FakeClient([_item("aaaa", seeding_time_s=5)]), now=_NOW + 60)
    assert _row(store, oid)["absent_since"] is None
    _sweep(store, FakeClient([]), now=_NOW + _CONFIRM_S + 60)
    assert _row(store, oid)["released_at"] is None  # absence restarts at this pass


def test_hash_case_does_not_make_a_torrent_absent(store: ConcreteAcquireStore) -> None:
    """The client's lowercase hash matches an upper-case stored hash."""
    oid = _add(store, "AAAA")
    client = FakeClient([_item("aaaa", seeding_time_s=_FLOOR_S)])
    _sweep(store, client)
    assert client.calls == [{"aaaa"}]
    assert _row(store, oid)["satisfied_at"] == _NOW


# -- 5, 6: fail-soft and guards --------------------------------------------------------------


def test_client_error_writes_nothing(store: ConcreteAcquireStore) -> None:
    """A client failure ends the pass with no row changed."""
    oid = _add(store)
    report = _sweep(store, FakeClient(error=RuntimeError("down")))
    row = _row(store, oid)
    assert (row["satisfied_at"], row["absent_since"], row["released_at"]) == (None, None, None)
    assert report.client_error is True


def test_nothing_open_makes_no_client_call(store: ConcreteAcquireStore) -> None:
    """With no open obligation the client is not asked."""
    client = FakeClient([])
    report = _sweep(store, client)
    assert client.calls == []
    assert (report.open, report.satisfied, report.marked_absent, report.released) == (0, 0, 0, 0)


def test_satisfied_and_released_rows_are_never_rewritten(store: ConcreteAcquireStore) -> None:
    """The guards make a second write on a closed row a no-op."""
    oid = _add(store)
    assert store.seed.mark_satisfied(oid, 10) == 1
    assert store.seed.mark_satisfied(oid, 20) == 0
    assert store.seed.mark_released(oid, 30) == 1
    assert store.seed.mark_released(oid, 40) == 0
    assert store.seed.mark_satisfied(oid, 50) == 0
    assert store.seed.mark_absent(oid, 60) == 0
    row = _row(store, oid)
    assert (row["satisfied_at"], row["released_at"], row["absent_since"]) == (10, 30, None)
    assert store.seed.list_open() == []


# -- 7: the production consequence -----------------------------------------------------------


def test_a_confirmed_release_lets_the_delete_authority_allow_the_path(
    store: ConcreteAcquireStore, tmp_path: Path
) -> None:
    """The authority VETOes a seeding path, still VETOes after one absence, ALLOWs after the release."""
    media = tmp_path / "library" / "Movie (2020)"
    media.mkdir(parents=True)
    (media / "movie.mkv").write_bytes(b"x")
    # An obligation recorded just now: the live clock of may_delete says « unmet ».
    import time

    _add(store, path=str(media / "movie.mkv"), added_at=int(time.time()))
    authority = DeleteAuthority(store=store)

    assert authority.may_delete(media) is not ALLOW

    _sweep(store, FakeClient([]), now=_NOW)  # first absence: not released yet
    assert authority.may_delete(media) is not ALLOW

    _sweep(store, FakeClient([]), now=_NOW + _CONFIRM_S)  # confirmed
    assert authority.may_delete(media) is ALLOW


# -- 8: the migration ------------------------------------------------------------------------


def test_migration_025_adds_absent_since_and_keeps_rows(tmp_path: Path) -> None:
    """On a database at version 24, migration 025 adds the column and keeps every row."""
    old_dir = tmp_path / "migrations24"
    old_dir.mkdir()
    for script in _MIGRATIONS_DIR.glob("*.sql"):
        if int(script.name.split("_", 1)[0]) <= 24:
            shutil.copy(script, old_dir / script.name)
    conn = sqlite3.connect(tmp_path / "old.db")
    try:
        apply_migrations(conn, old_dir)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 24
        conn.execute(
            "INSERT INTO seed_obligation (info_hash, source_tracker, min_seed_time_s, min_ratio, added_at) "
            "VALUES ('aaaa', 'c411', 259200, 1.0, 5)"
        )
        conn.commit()
        assert "absent_since" not in {r[1] for r in conn.execute("PRAGMA table_info(seed_obligation)")}

        apply_migrations(conn, _MIGRATIONS_DIR)

        assert conn.execute("PRAGMA user_version").fetchone()[0] >= 25
        assert "absent_since" in {r[1] for r in conn.execute("PRAGMA table_info(seed_obligation)")}
        assert conn.execute("SELECT info_hash, absent_since FROM seed_obligation").fetchall() == [("aaaa", None)]
    finally:
        conn.close()
