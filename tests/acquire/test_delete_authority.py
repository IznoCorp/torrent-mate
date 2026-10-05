"""Adversarial fail-open + descendant-boundary mutation tests for DeleteAuthority.

Verifies the DESIGN §7.2 contract:
- Fail-open: store absent / unreadable / no-obligation → ALLOW.
- Mutation-proof: same setup with patched-away guard → VETO (proves guard works).
- Seed-time: unmet → VETO with reason naming tracker + info_hash; met → ALLOW.
- Released obligation → ALLOW (excluded at SQL level by find_active_under).
- Descendant-boundary: LIKE matching with ESCAPE safety (D/child matches, D-other / Dx don't).
- Mixed obligations: first unmet VETO wins.
- Strict permit (operator ruling R1): the same decision, but an unreadable store
  (absent / corrupt / locked) RAISES, no file is created, and the read-only
  connection is closed after each decision; the veto carries ``owed_until``.

Uses :meth:`_SeedSubStore.find_active_under` (returns list) — NOT the exact-match
singleton ``find_by_dispatched_path`` that an earlier plan draft referenced.
The query only filters on ``released_at IS NULL`` (not ``satisfied_at``);
seed-time satisfaction is determined by the clock-based check in
:meth:`DeleteAuthority.may_delete`.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from personalscraper.acquire import delete_authority
from personalscraper.acquire.delete_authority import StrictDeletePermit, build_delete_authority
from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.delete_permit import ALLOW, ObligationsUnreadable


@pytest.fixture
def store(tmp_path: Path) -> Iterator["ConcreteAcquireStore"]:
    """Yield an inert store on a temp acquire.db and close it afterwards.

    The store opens lazily on first sub-store access.  Using try/finally
    to ensure close() is called even if a test fails (matching the pattern
    in tests/acquire/test_store.py).

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


def _obligation(
    dispatched_path: str | None,
    min_seed_time_s: int = 999999,
    *,
    info_hash: str = "abc123def456",
    source_tracker: str = "c411",
    added_at: int | None = None,
    **kwargs: object,
) -> SeedObligation:
    """Build a seed obligation with defaults suitable for VETO-inducing tests.

    Args:
        dispatched_path: Absolute path string (or None for pre-dispatch).
        min_seed_time_s: Minimum seed time (default huge → unmet unless overridden).
        info_hash: Torrent info-hash hex string.
        source_tracker: Tracker name.
        added_at: Unix epoch seconds (defaults to ``int(time.time())``).
        **kwargs: Additional :class:`SeedObligation` fields.

    Returns:
        A frozen :class:`SeedObligation`.
    """
    return SeedObligation(
        info_hash=info_hash,
        source_tracker=source_tracker,
        min_seed_time_s=min_seed_time_s,
        min_ratio=1.0,
        added_at=added_at if added_at is not None else int(time.time()),
        dispatched_path=dispatched_path,
        **kwargs,  # type: ignore[arg-type]
    )


# ═══════════════════════════════════════════════════════════════════════════
# FAIL-OPEN family
# ═══════════════════════════════════════════════════════════════════════════


def test_store_absent_returns_allow(tmp_path: Path) -> None:
    """No store → always ALLOW (fail-open, DESIGN §7.2)."""
    auth = build_delete_authority(store=None)
    decision = auth.may_delete(tmp_path / "movie.mkv")
    assert decision is ALLOW


def test_no_obligation_returns_allow(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """No matching obligation → ALLOW."""
    auth = build_delete_authority(store=store)
    decision = auth.may_delete(tmp_path / "movie.mkv")
    assert decision is ALLOW


def test_has_active_obligation_true_when_present(store: "ConcreteAcquireStore") -> None:
    """§7 HnR — an active obligation for the hash → has_active_obligation True."""
    store.seed.add(_obligation(dispatched_path=None, info_hash="hashOwe"))
    auth = build_delete_authority(store=store)
    assert auth.has_active_obligation("hashOwe") is True


def test_has_active_obligation_false_when_absent(store: "ConcreteAcquireStore") -> None:
    """No obligation for the hash → False (ingest then relies on its seeding probe)."""
    auth = build_delete_authority(store=store)
    assert auth.has_active_obligation("unknownhash") is False


def test_has_active_obligation_false_without_store() -> None:
    """No store → False (fail-safe: no positive obligation asserted)."""
    auth = build_delete_authority(store=None)
    assert auth.has_active_obligation("anything") is False


def test_lookup_exception_fail_open_with_mutation_proof(
    store: "ConcreteAcquireStore", tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Store lookup raises → ALLOW (fail-open), AND mutation-proof.

    Proves the fail-open is doing real work: the SAME obligation that would
    VETO when the store works normally returns ALLOW when the store is
    unreadable.  Also asserts a warning is logged.
    """
    path = tmp_path / "movie.mkv"
    path.write_text("fake content")

    ob = _obligation(dispatched_path=str(path), min_seed_time_s=999999)
    store.seed.add(ob)

    auth = build_delete_authority(store=store)

    # Mutation: patch find_active_under to raise → ALLOW (fail-open guard).
    with patch.object(store.seed, "find_active_under", side_effect=RuntimeError("DB locked")):
        decision = auth.may_delete(path)
    assert decision is ALLOW
    assert "acquire.delete_authority.lookup_failed" in caplog.text
    assert "DB locked" in caplog.text

    # Same obligation without the raise → VETO (proves the guard is non-vacuous).
    decision = auth.may_delete(path)
    assert decision is not ALLOW


def test_path_exists_oserror_fail_open_with_mutation_proof(
    store: "ConcreteAcquireStore",
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1: a dispatched_path raising OSError on .exists() → ALLOW, never raises.

    The fail-open guard must span the WHOLE obligation loop, not just
    find_active_under. ``Path.exists()`` re-raises an OSError whose errno is not
    benign (ENAMETOOLONG / EACCES), so without the widened guard may_delete
    would propagate the error into the deleter and fail CLOSED (DESIGN §9
    requires ALLOW on any error). Mutation-proof: the SAME active unmet
    obligation VETOes once .exists() stops raising.
    """
    path = tmp_path / "movie.mkv"
    path.write_text("fake content")

    ob = _obligation(dispatched_path=str(path), min_seed_time_s=999999)
    store.seed.add(ob)

    auth = build_delete_authority(store=store)

    real_exists = Path.exists

    def _boom(self: Path, *args: object, **kwargs: object) -> bool:
        # Only the obligation's dispatched_path detonates; everything else is
        # delegated to the real implementation.
        if str(self) == str(path):
            raise OSError(36, "File name too long")  # errno 36 == ENAMETOOLONG
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", _boom)

    # OSError in the loop → ALLOW (fail-open), no propagation.
    decision = auth.may_delete(path)
    assert decision is ALLOW
    assert "acquire.delete_authority.lookup_failed" in caplog.text

    # Mutation proof: drop the raise → the same obligation now VETOes.
    monkeypatch.undo()
    decision = auth.may_delete(path)
    assert decision is not ALLOW


def test_stale_obligation_mutation_proof(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """Path-exists guard: missing file → ALLOW; creating it → VETO.

    A stale obligation (dispatched_path set but file absent on disk) is
    inert — the path-exists guard in may_delete skips it.  Creating the
    file flips the decision to VETO, proving the guard does real work.
    """
    path = tmp_path / "gone.mkv"
    # Do NOT create the file — obligation is stale.

    ob = _obligation(dispatched_path=str(path), min_seed_time_s=999999)
    store.seed.add(ob)

    auth = build_delete_authority(store=store)

    # Stale (no file) → ALLOW.
    decision = auth.may_delete(path)
    assert decision is ALLOW

    # Create the file → same obligation now VETOes (mutation proof).
    path.write_text("fake content")
    decision = auth.may_delete(path)
    assert decision is not ALLOW


# ═══════════════════════════════════════════════════════════════════════════
# SEEDTIME family
# ═══════════════════════════════════════════════════════════════════════════


def test_seedtime_not_met_veto(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """Active obligation with seedtime NOT met → VETO; reason names tracker + info_hash."""
    path = tmp_path / "movie.mkv"
    path.write_text("fake content")

    ob = _obligation(
        dispatched_path=str(path),
        min_seed_time_s=999999,
        info_hash="abc123def4567890",
        source_tracker="c411",
    )
    store.seed.add(ob)

    auth = build_delete_authority(store=store)
    decision = auth.may_delete(path)

    assert decision is not ALLOW
    reason_str = str(decision)
    assert "c411" in reason_str
    assert "abc123de" in reason_str  # info_hash[:8]...


def test_seedtime_met_allow(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """Obligation with seedtime already elapsed → ALLOW."""
    path = tmp_path / "movie.mkv"
    path.write_text("fake content")

    # added_at far in the past so elapsed >> min_seed_time_s.
    ob = _obligation(
        dispatched_path=str(path),
        min_seed_time_s=3600,  # 1 hour
        added_at=int(time.time()) - 100_000,  # ~28 hours ago
    )
    store.seed.add(ob)

    auth = build_delete_authority(store=store)
    decision = auth.may_delete(path)
    assert decision is ALLOW


def test_released_obligation_excluded_at_sql_level(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """Released obligation (released_at set) → ALLOW.

    find_active_under filters on ``released_at IS NULL``, so a released
    obligation is excluded at the SQL level even when it is unmet AND the
    dispatched_path exists on disk.  We verify this by asserting that
    find_active_under returns zero results AND that may_delete is ALLOW.
    """
    path = tmp_path / "movie.mkv"
    path.write_text("fake content")

    ob = _obligation(
        dispatched_path=str(path),
        min_seed_time_s=999999,  # Would VETO if found
        released_at=int(time.time()),  # But it's released
    )
    store.seed.add(ob)

    # find_active_under excludes it at SQL level.
    active = store.seed.find_active_under(path)
    assert len(active) == 0, "Released obligation should be excluded by released_at IS NULL"

    auth = build_delete_authority(store=store)
    decision = auth.may_delete(path)
    assert decision is ALLOW


# ═══════════════════════════════════════════════════════════════════════════
# DESCENDANT-BOUNDARY family (DESIGN §7.2 correctness core)
# ═══════════════════════════════════════════════════════════════════════════


def test_descendant_match_vetoes_directory_deletion(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """Obligation on D/movie.mkv (unmet, exists) → may_delete(D) VETOes.

    The LIKE pattern ``D/%`` in find_active_under catches the child, so
    deleting the parent directory D is blocked.
    """
    parent_dir = tmp_path / "D"
    parent_dir.mkdir()
    child_path = parent_dir / "movie.mkv"
    child_path.write_text("fake content")

    ob = _obligation(dispatched_path=str(child_path), min_seed_time_s=999999)
    store.seed.add(ob)

    auth = build_delete_authority(store=store)
    decision = auth.may_delete(parent_dir)
    assert decision is not ALLOW


def test_sibling_prefix_boundary_safe_allow(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """Obligation on D/, may_delete on 'D-other' → ALLOW (boundary-safe LIKE).

    The LIKE pattern uses ESCAPE so that ``D/%`` matches descendants of D
    but NOT paths starting with ``D-`` or ``Dx`` (sibling-prefix).
    """
    d_dir = tmp_path / "D"
    d_dir.mkdir()
    child_path = d_dir / "file.mkv"
    child_path.write_text("fake content")

    ob = _obligation(dispatched_path=str(child_path), min_seed_time_s=999999)
    store.seed.add(ob)

    auth = build_delete_authority(store=store)

    # may_delete a sibling-path that shares a prefix → ALLOW.
    sibling = tmp_path / "D-other"
    sibling.mkdir()
    decision = auth.may_delete(sibling)
    assert decision is ALLOW

    # Also test a same-parent prefix collision: "Dx".
    dx = tmp_path / "Dx"
    dx.mkdir()
    decision = auth.may_delete(dx)
    assert decision is ALLOW


def test_exact_path_match_veto(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """Obligation on D/movie.mkv → may_delete(D/movie.mkv) VETOes (exact match)."""
    parent_dir = tmp_path / "D"
    parent_dir.mkdir()
    child_path = parent_dir / "movie.mkv"
    child_path.write_text("fake content")

    ob = _obligation(dispatched_path=str(child_path), min_seed_time_s=999999)
    store.seed.add(ob)

    auth = build_delete_authority(store=store)
    decision = auth.may_delete(child_path)
    assert decision is not ALLOW


def test_mixed_obligations_one_unmet_vetoes_directory(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """Two obligations under D, one MET one UNMET (both files exist) → may_delete(D) VETOes.

    The iteration in may_delete skips the MET obligation (seedtime elapsed),
    then hits the UNMET one and returns VETO — proving the first unmet wins.
    """
    parent_dir = tmp_path / "D"
    parent_dir.mkdir()

    met_path = parent_dir / "met.mkv"
    met_path.write_text("fake content")
    unmet_path = parent_dir / "unmet.mkv"
    unmet_path.write_text("fake content")

    # MET: seedtime already elapsed.
    met_ob = _obligation(
        dispatched_path=str(met_path),
        min_seed_time_s=3600,
        added_at=int(time.time()) - 100_000,
        info_hash="aaaa1111aaaa",
    )
    store.seed.add(met_ob)

    # UNMET: seedtime NOT elapsed.
    unmet_ob = _obligation(
        dispatched_path=str(unmet_path),
        min_seed_time_s=999999,
        info_hash="bbbb2222bbbb",
        added_at=int(time.time()),
    )
    store.seed.add(unmet_ob)

    auth = build_delete_authority(store=store)
    decision = auth.may_delete(parent_dir)
    assert decision is not ALLOW

    # The VETO reason should reference the UNMET obligation, not the MET one.
    reason_str = str(decision)
    assert "bbbb2222" in reason_str
    assert "aaaa1111" not in reason_str


# ═══════════════════════════════════════════════════════════════════════════
# STRICT PERMIT family (operator ruling R1) and owed_until (R2)
# ═══════════════════════════════════════════════════════════════════════════


class _SpyConnection(sqlite3.Connection):
    """A real connection that records whether it was closed.

    ``sqlite3.Connection.close`` cannot be patched on an instance (a C type), so
    the spy is a subclass handed to the real ``sqlite3.connect`` as its factory.
    """

    opened: "list[_SpyConnection]" = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Open the connection and register it.

        Args:
            *args: Positional arguments of :class:`sqlite3.Connection`.
            **kwargs: Keyword arguments of :class:`sqlite3.Connection`.
        """
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.closed = False
        _SpyConnection.opened.append(self)

    def close(self) -> None:
        """Close the connection and record it."""
        self.closed = True
        super().close()


def _spy_connect(monkeypatch: pytest.MonkeyPatch) -> "list[_SpyConnection]":
    """Route ``sqlite3.connect`` through :class:`_SpyConnection` from now on.

    ``sqlite3`` is one module object, so this reaches every caller: install it
    only once the store is written, so the list holds the permit's connections.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The list every connection opened from now on is appended to.
    """
    real_connect = sqlite3.connect
    opened: list[_SpyConnection] = []
    monkeypatch.setattr(_SpyConnection, "opened", opened)

    def _connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        return real_connect(*args, factory=_SpyConnection, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", _connect)
    return opened


def _owed_store(store: "ConcreteAcquireStore", path: Path) -> int:
    """Record two unmet obligations under *path* and return the later of their due moments.

    Args:
        store: The acquire store to write.
        path: An existing directory the obligations sit under.

    Returns:
        ``max(added_at + min_seed_time_s)`` over the two obligations.
    """
    now = int(time.time())
    early = path / "early.mkv"
    late = path / "late.mkv"
    early.write_text("fake content")
    late.write_text("fake content")
    store.seed.add(_obligation(str(early), min_seed_time_s=1_000, added_at=now, info_hash="eeee1111eeee"))
    store.seed.add(_obligation(str(late), min_seed_time_s=50_000, added_at=now - 10, info_hash="ffff2222ffff"))
    return now - 10 + 50_000


def test_owed_until_is_the_latest_due_moment(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """The fail-open authority's veto carries owed_until = max(added_at + min_seed_time_s)."""
    folder = tmp_path / "Show"
    folder.mkdir()
    expected = _owed_store(store, folder)

    decision = build_delete_authority(store=store).may_delete(folder)

    assert decision is not ALLOW
    assert decision.owed_until == expected  # type: ignore[union-attr]


def test_strict_permit_vetoes_with_owed_until(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """The strict permit makes the same decision and carries the same owed_until."""
    folder = tmp_path / "Show"
    folder.mkdir()
    expected = _owed_store(store, folder)

    decision = StrictDeletePermit(tmp_path / "acquire.db").may_delete(folder)

    assert decision is not ALLOW
    assert decision.owed_until == expected  # type: ignore[union-attr]


def test_strict_permit_allows_without_obligation(store: "ConcreteAcquireStore", tmp_path: Path) -> None:
    """A readable store with nothing owed under the path → ALLOW."""
    store.seed.add(_obligation(str(tmp_path / "elsewhere.mkv")))

    decision = StrictDeletePermit(tmp_path / "acquire.db").may_delete(tmp_path / "movie.mkv")

    assert decision is ALLOW


def test_strict_permit_refuses_absent_store_and_creates_nothing(tmp_path: Path) -> None:
    """acquire.db absent → ObligationsUnreadable, and nothing appears: no file, no journal, no directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    with pytest.raises(ObligationsUnreadable):
        StrictDeletePermit(data_dir / "acquire.db").may_delete(tmp_path / "movie.mkv")
    with pytest.raises(ObligationsUnreadable):
        StrictDeletePermit(tmp_path / "missing" / "acquire.db").may_delete(tmp_path / "movie.mkv")

    assert list(data_dir.iterdir()) == []
    assert not (tmp_path / "missing").exists()


def test_strict_permit_refuses_corrupt_store_and_leaves_it(tmp_path: Path) -> None:
    """acquire.db of garbage bytes → ObligationsUnreadable; the file is left as it was, nothing beside it."""
    db_path = tmp_path / "acquire.db"
    garbage = b"this is not a database at all" * 64
    db_path.write_bytes(garbage)

    with pytest.raises(ObligationsUnreadable):
        StrictDeletePermit(db_path).may_delete(tmp_path / "movie.mkv")

    assert db_path.read_bytes() == garbage
    assert sorted(p.name for p in tmp_path.iterdir()) == ["acquire.db"]


def test_strict_permit_refuses_locked_store(
    store: "ConcreteAcquireStore", tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """acquire.db held under an exclusive lock past the read timeout → ObligationsUnreadable."""
    store.seed.add(_obligation(str(tmp_path / "movie.mkv")))
    store.close()
    monkeypatch.setattr(delete_authority, "_READ_TIMEOUT_S", 0.1)
    holder = sqlite3.connect(tmp_path / "acquire.db")
    try:
        holder.execute("PRAGMA locking_mode = EXCLUSIVE")
        holder.execute("CREATE TABLE lock_probe (x INTEGER)")
        holder.commit()

        with pytest.raises(ObligationsUnreadable):
            StrictDeletePermit(tmp_path / "acquire.db").may_delete(tmp_path / "movie.mkv")
    finally:
        holder.close()


def test_strict_permit_closes_its_connection_after_each_decision(
    store: "ConcreteAcquireStore", tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every decision opens one read-only connection and closes it — allowed, vetoed or refused (N3)."""
    folder = tmp_path / "Show"
    folder.mkdir()
    _owed_store(store, folder)
    spy_connect = _spy_connect(monkeypatch)
    permit = StrictDeletePermit(tmp_path / "acquire.db")

    assert permit.may_delete(tmp_path / "other.mkv") is ALLOW
    assert permit.may_delete(folder) is not ALLOW
    with patch.object(delete_authority, "_decide", side_effect=RuntimeError("lookup failed")):
        with pytest.raises(ObligationsUnreadable):
            permit.may_delete(folder)

    assert len(spy_connect) == 3
    assert all(conn.closed for conn in spy_connect)
