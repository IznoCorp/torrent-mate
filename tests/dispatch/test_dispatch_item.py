"""Unit tests for the shared dispatch-item template (plan phase-02 P2.2).

These exercise :func:`personalscraper.dispatch._item._dispatch_item` in
isolation, with *fake* transfer strategies so the template's own scaffold
logic is the unit under test (not rsync). The template is driven through a real
:class:`Dispatcher` over a real :class:`EventBus` (events flow through the bus,
per the required-param rule) with tmp_path-simulated staging + storage disks and
a DB-backed :class:`MediaIndex`.

Coverage:

- **Journal-on-destruction (F1)** — a supersede whose transfer reports
  ``destroyed=True`` appends exactly ONE destructive ``overwrite`` row (op,
  path, actor, detail all driven by the spec); a ``destroyed=False`` add-only
  supersede appends NONE.
- **Identity-guard veto short-circuits** — a spec ``identity_guard`` returning a
  reason skips the item without calling the transfer or journaling anything.
- **``existing_action`` passthrough** — the spec's action label (``replaced`` /
  ``merged``) and ``journal_op`` are reported verbatim.
- **New-media path** — no existing copy routes through ``_move_new`` (never the
  spec ``transfer_fn``) and journals nothing.
- **Failure path** — a failed transfer reports ``error`` and journals nothing.
- **Permit consult** — a VETO marks a breach but the supersede still proceeds;
  a raising permit is fail-open (no breach, transfer proceeds).
- **Acquired-events emit** — events returned by ``record_dispatch`` flow onto
  the bus once the transfer succeeds.
- **Merge-destruction predicate** — the ``_merge_supersedes_existing`` helper
  classifies same-filename overwrite / re-scrape rename / add-only correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.config import Settings
from personalscraper.core.delete_permit import ALLOW, PermitDecision, veto
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.dispatch._item import (
    DispatchSpec,
    TransferOutcome,
    _dispatch_item,
    _merge_supersedes_existing,
    canonical_name_from_destination,
)
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.events import ItemDispatched
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex
from personalscraper.indexer.destructive_journal import OP_OVERWRITE, list_recent

_GB = 1024**3


# ---------------------------------------------------------------------------
# Infrastructure fixtures (mirror the local set in test_dispatch_characterization).
# ---------------------------------------------------------------------------


@pytest.fixture()
def _rsync_available() -> None:
    """Skip when rsync is absent — the Dispatcher requires it at construction."""
    import shutil

    if shutil.which("rsync") is None:
        pytest.skip("rsync not available on this system")


@pytest.fixture()
def char_disks(tmp_path: Path) -> list[Path]:
    """Build four fake disk roots (``Disk1``…``Disk4``) under tmp_path.

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        List of four existing directory paths used as storage disk roots.
    """
    disks: list[Path] = []
    for i in range(1, 5):
        d = tmp_path / f"Disk{i}"
        d.mkdir(parents=True, exist_ok=True)
        disks.append(d)
    return disks


@pytest.fixture()
def char_config(test_config: Config, char_disks: list[Path]) -> Config:
    """Compose a validated Config wired to the fixture disks for dispatch.

    MOVIES is accepted on disk1/disk2/disk3 so new-media disk-choice among
    multiple eligible disks is exercisable; TV_SHOWS stays on disk1.
    ``indexer.db_path`` is pinned under ``paths.data_dir`` so the dispatcher,
    the journal, and the assertions share one SQLite file. Disk thresholds are
    zeroed so tiny fixture items are never gated on free space.

    Args:
        test_config: Synthetic Config fixture (tests/fixtures/config.py).
        char_disks: Four fake disk root paths.

    Returns:
        Validated Config with disks pointing at ``char_disks`` and a pinned
        indexer DB path.
    """
    new_disks = [
        DiskConfig(id="disk1", path=char_disks[0], categories=[CID.MOVIES, CID.TV_SHOWS]),
        DiskConfig(id="disk2", path=char_disks[1], categories=[CID.MOVIES, CID.ANIME, CID.MOVIES_ANIMATION]),
        DiskConfig(
            id="disk3",
            path=char_disks[2],
            categories=[CID.MOVIES, CID.MOVIES_DOCUMENTARY, CID.TV_SHOWS_ANIMATION],
        ),
        DiskConfig(
            id="disk4",
            path=char_disks[3],
            categories=[CID.TV_SHOWS_DOCUMENTARY, CID.AUDIOBOOKS, CID.STANDUP, CID.THEATER, CID.TV_PROGRAMS],
        ),
    ]
    new_indexer = test_config.indexer.model_copy(update={"db_path": test_config.paths.data_dir / "library.db"})
    new_thresholds = test_config.thresholds.model_copy(
        update={"min_free_space_staging_gb": 0, "min_free_space_disk_gb": 0.0}
    )
    config = test_config.model_copy(update={"disks": new_disks, "indexer": new_indexer, "thresholds": new_thresholds})
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture()
def char_db_path(char_config: Config) -> Path:
    """Return the resolved (non-None) indexer DB path pinned by ``char_config``."""
    db_path = char_config.indexer.db_path
    assert db_path is not None, "char_config must pin indexer.db_path"
    return db_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_media_dir(parent: Path, name: str, files: dict[str, bytes]) -> Path:
    """Create ``parent/name`` and populate it with ``files`` (relative → bytes)."""
    media_dir = parent / name
    media_dir.mkdir(parents=True, exist_ok=True)
    for rel, data in files.items():
        target = media_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return media_dir


def _seed_index(db_path: Path, entry: IndexEntry) -> None:
    """Seed the DB-backed MediaIndex with a single existing-media entry."""
    index = MediaIndex(db_path, event_bus=EventBus())
    try:
        index.add(entry)
    finally:
        index.close()


def _patch_disk_usage(monkeypatch: pytest.MonkeyPatch, free_by_path: dict[str, int]) -> None:
    """Force distinct per-disk free-space so the most-free selection is deterministic."""
    import shutil

    real_disk_usage = shutil.disk_usage

    def _fake(path: Any) -> Any:
        path_str = str(path)
        for disk_path, free_bytes in free_by_path.items():
            if path_str == disk_path or path_str.startswith(disk_path + "/"):

                class _Usage:
                    total = 1000 * _GB
                    free = free_bytes
                    used = total - free

                return _Usage()
        return real_disk_usage(path)

    monkeypatch.setattr("personalscraper.dispatch.disk_scanner.shutil.disk_usage", _fake)


class _FakeTransfer:
    """A recording fake transfer strategy with a canned :class:`TransferOutcome`.

    Records every ``(source, dest, capability)`` it is called with so a test can
    assert whether — and with what — the template invoked the transfer.
    """

    def __init__(self, *, success: bool, destroyed: bool) -> None:
        """Store the canned outcome.

        Args:
            success: The ``success`` field of the returned outcome.
            destroyed: The ``destroyed`` field of the returned outcome.
        """
        self._success = success
        self._destroyed = destroyed
        self.calls: list[tuple[Path, Path, object]] = []

    def __call__(self, source: Path, dest: Path, capability: object) -> TransferOutcome:
        """Record the call and return the canned outcome."""
        self.calls.append((source, dest, capability))
        return TransferOutcome(success=self._success, destroyed=self._destroyed)


def _spec(
    *,
    existing_action: Literal["replaced", "merged"] = "replaced",
    media_type: str = "movie",
    transfer_fn: object,
    identity_guard: object = None,
    journal_op: str = OP_OVERWRITE,
    bus_source: str = "dispatch.test",
) -> DispatchSpec:
    """Build a DispatchSpec with test-controlled hooks.

    Args:
        existing_action: The supersede action label reported by the template.
        media_type: ``"movie"`` / ``"tvshow"`` threaded to resolve + index.
        transfer_fn: The (usually fake) transfer strategy.
        identity_guard: Optional §7 guard; ``None`` for no guard.
        journal_op: The op recorded on a destruction.
        bus_source: The ItemDispatched source label.

    Returns:
        A DispatchSpec ready to pass to :func:`_dispatch_item`.
    """
    return DispatchSpec(
        media_type=media_type,
        existing_action=existing_action,
        transfer_fn=transfer_fn,  # type: ignore[arg-type]
        identity_guard=identity_guard,  # type: ignore[arg-type]
        canonical_name_rule=canonical_name_from_destination,
        journal_op=journal_op,
        journal_detail=lambda src: f"TEST destruction — « {src.name} »",
        bus_source=bus_source,
    )


def _overwrite_rows(db_path: Path, dest: Path) -> list[dict[str, object]]:
    """Return destructive ``overwrite`` rows journaled for ``dest``."""
    return [r for r in list_recent(db_path) if r["op"] == "overwrite" and str(r["path"]) == str(dest)]


def _seed_existing_movie(char_config: Config, char_db_path: Path, char_disks: list[Path], name: str) -> Path:
    """Create + index an on-disk movie so the resolver routes to supersede.

    Args:
        char_config: Dispatch-wired Config fixture.
        char_db_path: Shared indexer DB path.
        char_disks: Fake disk roots.
        name: Movie folder basename.

    Returns:
        The existing on-disk folder path (destination of the supersede).
    """
    movies_folder = char_config.category(CID.MOVIES).folder_name
    existing = _make_media_dir(char_disks[0] / movies_folder, name, {"old.mkv": b"x" * 16})
    _seed_index(
        char_db_path,
        IndexEntry(name=name, disk="disk1", category=CID.MOVIES, path=str(existing), media_type="movie"),
    )
    return existing


# ---------------------------------------------------------------------------
# Journal-on-destruction (F1)
# ---------------------------------------------------------------------------


def test_supersede_destroyed_journals_exactly_one_row(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """A supersede reporting ``destroyed=True`` journals exactly one overwrite row.

    The fake transfer succeeds and reports destruction; the template must call
    the transfer once with ``(src, dest, cap)``, report the spec's
    ``existing_action``, journal ONE ``overwrite`` row (op/actor/detail from the
    spec), and emit an ItemDispatched with the spec's ``bus_source``.
    """
    name = "Dune (2021)"
    existing = _seed_existing_movie(char_config, char_db_path, char_disks, name)
    source = _make_media_dir(tmp_path / "staging_src", name, {"new.mkv": b"y" * 4096})

    transfer = _FakeTransfer(success=True, destroyed=True)
    spec = _spec(existing_action="replaced", transfer_fn=transfer, bus_source="dispatch.movie")

    events: list[Event] = []
    bus = EventBus()
    bus.subscribe(Event, events.append)
    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=bus)
    try:
        result = _dispatch_item(dispatcher, source, CID.MOVIES, spec)
    finally:
        index.close()

    assert result.action == "replaced"
    assert result.disk == "disk1"
    assert result.destination == existing
    # Transfer invoked exactly once with the staging src and the on-disk dest.
    assert len(transfer.calls) == 1
    assert transfer.calls[0][0] == source
    assert transfer.calls[0][1] == existing

    rows = _overwrite_rows(char_db_path, existing)
    assert len(rows) == 1, f"exactly one overwrite row expected; got {list_recent(char_db_path)}"
    assert rows[0]["actor"] == "dispatch"
    assert rows[0]["op"] == OP_OVERWRITE
    assert name in str(rows[0]["detail"])  # spec.journal_detail(src) was used

    dispatched = [e for e in events if isinstance(e, ItemDispatched)]
    assert len(dispatched) == 1
    assert dispatched[0].source == "dispatch.movie"
    assert dispatched[0].action == "replaced"


def test_supersede_add_only_never_journals(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """A supersede reporting ``destroyed=False`` (add-only) journals nothing.

    Same wiring as the destruction case, but the fake transfer reports no
    destruction — the template must run the transfer and report the action yet
    append ZERO journal rows (the trace is for destructions only, §7 / F1).
    """
    name = "Fallout (2024)"
    existing = _seed_existing_movie(char_config, char_db_path, char_disks, name)
    source = _make_media_dir(tmp_path / "staging_src", name, {"new.mkv": b"y" * 4096})

    transfer = _FakeTransfer(success=True, destroyed=False)
    spec = _spec(existing_action="replaced", transfer_fn=transfer)

    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=EventBus())
    try:
        result = _dispatch_item(dispatcher, source, CID.MOVIES, spec)
    finally:
        index.close()

    assert result.action == "replaced"
    assert len(transfer.calls) == 1  # the transfer still ran
    assert _overwrite_rows(char_db_path, existing) == []


# ---------------------------------------------------------------------------
# Identity-guard veto short-circuits
# ---------------------------------------------------------------------------


def test_identity_guard_veto_short_circuits(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """A §7 identity-guard veto skips the item: no transfer, no journal, no emit."""
    name = "Ferrari (2023)"
    existing = _seed_existing_movie(char_config, char_db_path, char_disks, name)
    source = _make_media_dir(tmp_path / "staging_src", name, {"new.mkv": b"y" * 4096})

    transfer = _FakeTransfer(success=True, destroyed=True)
    block_reason = "Remplacement bloqué : autre média (§7)."
    spec = _spec(existing_action="replaced", transfer_fn=transfer, identity_guard=lambda s, t: block_reason)

    events: list[Event] = []
    bus = EventBus()
    bus.subscribe(Event, events.append)
    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=bus)
    try:
        result = _dispatch_item(dispatcher, source, CID.MOVIES, spec)
    finally:
        index.close()

    assert result.action == "skipped"
    assert result.reason == block_reason
    assert transfer.calls == []  # transfer never invoked
    assert _overwrite_rows(char_db_path, existing) == []
    assert [e for e in events if isinstance(e, ItemDispatched)] == []
    # Source is untouched (nothing consumed the staging folder).
    assert source.exists()


# ---------------------------------------------------------------------------
# existing_action + journal_op passthrough (TV "merged")
# ---------------------------------------------------------------------------


def test_existing_action_and_journal_op_passthrough_for_merge(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """A ``merged`` spec reports ``merged`` and journals with the spec's op.

    Uses a TV-show spec (``existing_action="merged"``, ``media_type="tvshow"``)
    with a fake destroying transfer to prove the template threads the family
    label and journal op through verbatim (no movie-specific hardcoding).
    """
    name = "Fallout (2024)"
    tv_folder = char_config.category(CID.TV_SHOWS).folder_name
    existing = _make_media_dir(char_disks[0] / tv_folder, name, {"Saison 01/episode1.mkv": b"x" * 16})
    _seed_index(
        char_db_path,
        IndexEntry(name=name, disk="disk1", category=CID.TV_SHOWS, path=str(existing), media_type="tvshow"),
    )
    source = _make_media_dir(tmp_path / "staging_src", name, {"Saison 01/episode1.mkv": b"y" * 4096})

    transfer = _FakeTransfer(success=True, destroyed=True)
    spec = _spec(
        existing_action="merged",
        media_type="tvshow",
        transfer_fn=transfer,
        bus_source="dispatch.tv",
    )

    events: list[Event] = []
    bus = EventBus()
    bus.subscribe(Event, events.append)
    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=bus)
    try:
        result = _dispatch_item(dispatcher, source, CID.TV_SHOWS, spec)
    finally:
        index.close()

    assert result.action == "merged"
    rows = _overwrite_rows(char_db_path, existing)
    assert len(rows) == 1
    assert rows[0]["op"] == OP_OVERWRITE
    dispatched = [e for e in events if isinstance(e, ItemDispatched)]
    assert len(dispatched) == 1
    assert dispatched[0].action == "merged"
    assert dispatched[0].source == "dispatch.tv"


# ---------------------------------------------------------------------------
# New-media path (never uses spec.transfer_fn; never journals)
# ---------------------------------------------------------------------------


def test_new_media_moves_via_move_new_and_never_journals(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _rsync_available: None,
) -> None:
    """New media routes through ``_move_new`` (not ``transfer_fn``) and journals nothing.

    ``_move_new`` is faked (returns True without touching files) so the test is
    hermetic; the spec's ``transfer_fn`` must NOT be called on the new-media
    branch, no destructive row is journaled, and an ItemDispatched ``moved``
    event lands with the spec's ``bus_source``. Disk free space is forced so the
    most-free disk (disk2) is deterministic.
    """
    _patch_disk_usage(
        monkeypatch,
        {
            str(char_disks[0]): 100 * _GB,
            str(char_disks[1]): 500 * _GB,
            str(char_disks[2]): 200 * _GB,
            str(char_disks[3]): 50 * _GB,
        },
    )
    name = "Oppenheimer (2023)"
    source = _make_media_dir(tmp_path / "staging_src", name, {"movie.mkv": b"\x00" * 4096})

    move_calls: list[tuple[Path, Path]] = []

    transfer = _FakeTransfer(success=True, destroyed=True)
    spec = _spec(existing_action="replaced", transfer_fn=transfer, bus_source="dispatch.movie")

    events: list[Event] = []
    bus = EventBus()
    bus.subscribe(Event, events.append)
    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=bus)

    def _fake_move_new(src: Path, dst: Path, capability: object = None) -> bool:
        move_calls.append((src, dst))
        return True

    monkeypatch.setattr(dispatcher, "_move_new", _fake_move_new)

    try:
        result = _dispatch_item(dispatcher, source, CID.MOVIES, spec)
    finally:
        index.close()

    assert result.action == "moved"
    assert result.disk == "disk2"
    assert len(move_calls) == 1
    assert transfer.calls == []  # new-media path never uses the supersede transfer
    # No destruction journaled on a new placement (any op, any path).
    assert [r for r in list_recent(char_db_path) if r["op"] == "overwrite"] == []
    dispatched = [e for e in events if isinstance(e, ItemDispatched)]
    assert len(dispatched) == 1
    assert dispatched[0].action == "moved"
    assert dispatched[0].source == "dispatch.movie"


# ---------------------------------------------------------------------------
# Failure path
# ---------------------------------------------------------------------------


def test_failed_transfer_reports_error_and_never_journals(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """A failed transfer reports ``error``, journals nothing, and emits nothing."""
    name = "Dune (2021)"
    existing = _seed_existing_movie(char_config, char_db_path, char_disks, name)
    source = _make_media_dir(tmp_path / "staging_src", name, {"new.mkv": b"y" * 4096})

    transfer = _FakeTransfer(success=False, destroyed=False)
    spec = _spec(existing_action="replaced", transfer_fn=transfer)

    events: list[Event] = []
    bus = EventBus()
    bus.subscribe(Event, events.append)
    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=bus)
    try:
        result = _dispatch_item(dispatcher, source, CID.MOVIES, spec)
    finally:
        index.close()

    assert result.action == "error"
    assert len(transfer.calls) == 1
    assert _overwrite_rows(char_db_path, existing) == []
    assert [e for e in events if isinstance(e, ItemDispatched)] == []


# ---------------------------------------------------------------------------
# Permit consult (shared scaffold)
# ---------------------------------------------------------------------------


class _RecordingPermit:
    """A permit returning a canned decision and recording breach marks."""

    def __init__(self, decision: PermitDecision) -> None:
        self._decision = decision
        self.breaches: list[Path] = []

    def may_delete(self, path: Path) -> PermitDecision:
        """Return the canned decision."""
        return self._decision

    def record_dispatch(self, *, staging_source: Path, dispatched_dest: Path) -> list[Event]:
        """No-op recorder — announces nothing."""
        return []

    def mark_breach(self, path: Path) -> None:
        """Record the breached path."""
        self.breaches.append(path)


class _RaisingPermit(_RecordingPermit):
    """A permit whose ``may_delete`` raises — exercises the fail-open branch."""

    def may_delete(self, path: Path) -> PermitDecision:
        """Raise to simulate an unreadable permit store."""
        raise RuntimeError("permit store unreadable")


def test_permit_veto_marks_breach_but_supersede_proceeds(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """A VETO records a breach yet the supersede still runs (real media wins, O3)."""
    name = "Dune (2021)"
    existing = _seed_existing_movie(char_config, char_db_path, char_disks, name)
    source = _make_media_dir(tmp_path / "staging_src", name, {"new.mkv": b"y" * 4096})

    permit = _RecordingPermit(veto("live seed obligation unmet"))
    transfer = _FakeTransfer(success=True, destroyed=True)
    spec = _spec(existing_action="replaced", transfer_fn=transfer)

    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=EventBus(), permit=permit, recorder=permit)
    try:
        result = _dispatch_item(dispatcher, source, CID.MOVIES, spec)
    finally:
        index.close()

    assert result.action == "replaced"
    assert permit.breaches == [existing]  # breach recorded on the destroyed target
    assert len(transfer.calls) == 1  # supersede proceeded anyway
    assert len(_overwrite_rows(char_db_path, existing)) == 1


def test_permit_error_is_fail_open_no_breach(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """A raising permit is treated as ALLOW: supersede proceeds, no breach marked."""
    name = "Dune (2021)"
    _seed_existing_movie(char_config, char_db_path, char_disks, name)
    source = _make_media_dir(tmp_path / "staging_src", name, {"new.mkv": b"y" * 4096})

    permit = _RaisingPermit(ALLOW)
    transfer = _FakeTransfer(success=True, destroyed=True)
    spec = _spec(existing_action="replaced", transfer_fn=transfer)

    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=EventBus(), permit=permit, recorder=permit)
    try:
        result = _dispatch_item(dispatcher, source, CID.MOVIES, spec)
    finally:
        index.close()

    assert result.action == "replaced"
    assert permit.breaches == []  # fail-open consult never marks a breach
    assert len(transfer.calls) == 1


# ---------------------------------------------------------------------------
# Acquired-events emit
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class _AcquiredMarker(Event):
    """A sentinel event a fake recorder returns for the template to emit."""

    tag: str = "acquired"


class _AnnouncingRecorder:
    """A no-veto recorder that returns one sentinel event from record_dispatch."""

    def may_delete(self, path: Path) -> PermitDecision:
        """Always permit."""
        return ALLOW

    def record_dispatch(self, *, staging_source: Path, dispatched_dest: Path) -> list[Event]:
        """Return a single sentinel event to be emitted once the move succeeds."""
        return [_AcquiredMarker()]

    def mark_breach(self, path: Path) -> None:
        """No-op breach marker."""


def test_acquired_events_from_recorder_flow_onto_the_bus(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """Events returned by ``record_dispatch`` are emitted once the supersede succeeds."""
    name = "Dune (2021)"
    _seed_existing_movie(char_config, char_db_path, char_disks, name)
    source = _make_media_dir(tmp_path / "staging_src", name, {"new.mkv": b"y" * 4096})

    recorder = _AnnouncingRecorder()
    transfer = _FakeTransfer(success=True, destroyed=True)
    spec = _spec(existing_action="replaced", transfer_fn=transfer)

    events: list[Event] = []
    bus = EventBus()
    bus.subscribe(Event, events.append)
    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=bus, recorder=recorder)
    try:
        _dispatch_item(dispatcher, source, CID.MOVIES, spec)
    finally:
        index.close()

    assert any(isinstance(e, _AcquiredMarker) for e in events), "record_dispatch events must be emitted on success"


# ---------------------------------------------------------------------------
# Merge-destruction predicate (_merge_supersedes_existing)
# ---------------------------------------------------------------------------


def test_merge_predicate_same_filename_overwrite_is_destruction(tmp_path: Path) -> None:
    """Same relative path present on disk → the merge overwrites it (destruction)."""
    source = _make_media_dir(tmp_path / "src", "Show", {"Saison 01/episode1.mkv": b"y" * 8})
    dest = _make_media_dir(tmp_path / "dst", "Show", {"Saison 01/episode1.mkv": b"x" * 8})
    assert _merge_supersedes_existing(source, dest) is True


def test_merge_predicate_rescrape_rename_is_destruction(tmp_path: Path) -> None:
    """Same (season, episode) key under a different filename → purge destroys it."""
    source = _make_media_dir(tmp_path / "src", "Show", {"Saison 01/S04E06 - NEW.mkv": b"y" * 8})
    dest = _make_media_dir(tmp_path / "dst", "Show", {"Saison 01/S04E06 - OLD.mkv": b"x" * 8})
    assert _merge_supersedes_existing(source, dest) is True


def test_merge_predicate_add_only_is_not_destruction(tmp_path: Path) -> None:
    """Distinct episodes, no shared path or key → add-only, no destruction."""
    source = _make_media_dir(tmp_path / "src", "Show", {"Saison 01/S04E07 - NEW.mkv": b"y" * 8})
    dest = _make_media_dir(tmp_path / "dst", "Show", {"Saison 01/S04E06 - OLD.mkv": b"x" * 8})
    assert _merge_supersedes_existing(source, dest) is False


def test_merge_predicate_missing_dest_is_not_destruction(tmp_path: Path) -> None:
    """A destination that does not exist yet cannot be superseded."""
    source = _make_media_dir(tmp_path / "src", "Show", {"Saison 01/episode1.mkv": b"y" * 8})
    dest = tmp_path / "dst" / "Show"  # never created
    assert _merge_supersedes_existing(source, dest) is False
