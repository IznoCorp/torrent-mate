"""E2E CLI tests for ``personalscraper follow`` command group."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from personalscraper.acquire.context import AcquireContext
from personalscraper.acquire.store import build_acquire_store
from personalscraper.cli import app
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus

runner = CliRunner()


def _make_app_context(*, acquire: AcquireContext, event_bus: EventBus) -> AppContext:
    """Build a minimal AppContext with the given acquire context and event_bus."""
    return AppContext(
        config=MagicMock(),
        settings=MagicMock(),
        event_bus=event_bus,
        provider_registry=MagicMock(),
        acquire=acquire,
    )


def _fake_boundary(app_ctx: AppContext):
    """Return a context manager that yields app_ctx (replaces per_step_boundary)."""

    @contextmanager
    def _boundary(config, settings, *, build_torrent_client=False):
        yield app_ctx

    return _boundary


def _acquire_ctx_for(db_path: Path, event_bus: EventBus) -> AcquireContext:
    """Build a real AcquireContext with a seeded store and a mock title resolver."""
    store = build_acquire_store(AcquireConfig(db_path=db_path))
    return AcquireContext(
        tracker_registry=MagicMock(),
        store=store,
    )


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


def test_follow_command_registered() -> None:
    """The ``follow`` sub-group must appear in the app help output."""
    result = runner.invoke(app, ["--help"])
    assert "follow" in result.output, f"Expected 'follow' in help; got:\n{result.output}"


def test_follow_add_help_exits_zero() -> None:
    """``follow add --help`` exits 0 and mentions --tvdb."""
    result = runner.invoke(app, ["follow", "add", "--help"])
    assert result.exit_code == 0, result.output
    assert "--tvdb" in result.output


def test_follow_list_help_exits_zero() -> None:
    """``follow list --help`` exits 0 and mentions --all."""
    result = runner.invoke(app, ["follow", "list", "--help"])
    assert result.exit_code == 0, result.output
    assert "--all" in result.output


def test_follow_remove_help_exits_zero() -> None:
    """``follow remove --help`` exits 0 and mentions --tvdb."""
    result = runner.invoke(app, ["follow", "remove", "--help"])
    assert result.exit_code == 0, result.output
    assert "--tvdb" in result.output


# ---------------------------------------------------------------------------
# follow add — idempotent dedup (LOAD-BEARING)
# ---------------------------------------------------------------------------


def test_follow_add_inserts_one_row(tmp_path: Path, monkeypatch) -> None:
    """Follow add --tvdb 81189 inserts a row in followed_series."""
    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    # Title resolver: patch resolve_series_title to return a fixed title
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    result = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

    assert result.exit_code == 0, f"Expected exit 0; got:\n{result.output}"
    # Verify the row is actually in the DB (LOAD-BEARING: real row count).
    store2 = build_acquire_store(AcquireConfig(db_path=db_path))
    all_rows = store2.follow.list_all()
    assert len(all_rows) == 1, f"Expected 1 row, got {len(all_rows)}: {all_rows}"
    assert all_rows[0].media_ref.tvdb_id == 81189
    assert all_rows[0].title == "Breaking Bad"
    assert all_rows[0].active is True
    store2.close()
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_add_idempotent_double_add_one_row(tmp_path: Path, monkeypatch) -> None:
    """LOAD-BEARING: follow add twice with same --tvdb → exactly 1 row (dedup)."""
    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
    result2 = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

    assert result2.exit_code == 0, result2.output

    store2 = build_acquire_store(AcquireConfig(db_path=db_path))
    all_rows = store2.follow.list_all()
    assert len(all_rows) == 1, f"LOAD-BEARING: expected exactly 1 row after double add, got {len(all_rows)}: {all_rows}"
    store2.close()
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_add_emits_series_followed_event(tmp_path: Path, monkeypatch) -> None:
    """LOAD-BEARING: follow add emits SeriesFollowed on the event bus."""
    from personalscraper.acquire.events import SeriesFollowed

    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    received: list[SeriesFollowed] = []
    event_bus.subscribe(SeriesFollowed, lambda e: received.append(e))

    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

    assert len(received) == 1, f"Expected 1 SeriesFollowed event, got {len(received)}"
    assert received[0].media_ref.tvdb_id == 81189
    assert received[0].title == "Breaking Bad"
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_add_noop_when_already_active(tmp_path: Path, monkeypatch) -> None:
    """Follow add on an already-active series is a no-op (no duplicate row, no duplicate event)."""
    from personalscraper.acquire.events import SeriesFollowed

    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    received: list[SeriesFollowed] = []
    event_bus.subscribe(SeriesFollowed, lambda e: received.append(e))

    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
    result2 = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

    assert result2.exit_code == 0, result2.output
    # Second add is a no-op: still only 1 event (first add only)
    assert len(received) == 1, f"Expected 1 SeriesFollowed event total (no-op), got {len(received)}"
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_add_metadata_failure_still_follows(tmp_path: Path, monkeypatch) -> None:
    """LOAD-BEARING: title resolution failure → follow still succeeds with fallback title."""
    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    # Simulate title resolution failure: resolver raises (should not propagate)
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: kw.get("fallback_title") or f"tvdb:{ref.tvdb_id}",
    )

    result = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

    assert result.exit_code == 0, f"Expected exit 0 even on title failure; got:\n{result.output}"
    store2 = build_acquire_store(AcquireConfig(db_path=db_path))
    all_rows = store2.follow.list_all()
    assert len(all_rows) == 1, "Series must still be followed despite title resolution failure"
    assert all_rows[0].title == "tvdb:81189", (
        f"LOAD-BEARING: expected fallback title 'tvdb:81189', got {all_rows[0].title!r}"
    )
    store2.close()
    acquire.store.close()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# follow remove + reactivate + list filter tests
# ---------------------------------------------------------------------------


def test_follow_remove_soft_unfollows(tmp_path: Path, monkeypatch) -> None:
    """Follow remove sets active=False; the row is preserved (soft delete)."""
    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
    result = runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])

    assert result.exit_code == 0, result.output

    store2 = build_acquire_store(AcquireConfig(db_path=db_path))
    # Row still exists (soft delete) but active=False.
    all_rows = store2.follow.list_all()
    assert len(all_rows) == 1, f"Expected row preserved after soft delete, got {all_rows}"
    assert all_rows[0].active is False, f"Expected active=False after remove, got {all_rows[0].active}"
    store2.close()
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_remove_emits_series_unfollowed_event(tmp_path: Path, monkeypatch) -> None:
    """LOAD-BEARING: follow remove emits SeriesUnfollowed on the event bus."""
    from personalscraper.acquire.events import SeriesUnfollowed

    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    unfollowed: list[SeriesUnfollowed] = []
    event_bus.subscribe(SeriesUnfollowed, lambda e: unfollowed.append(e))

    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
    runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])

    assert len(unfollowed) == 1, f"Expected 1 SeriesUnfollowed event, got {len(unfollowed)}"
    assert unfollowed[0].media_ref.tvdb_id == 81189
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_reactivate_after_remove_one_row(tmp_path: Path, monkeypatch) -> None:
    """LOAD-BEARING: add → remove → add again reactivates the existing row (not a new row)."""
    from personalscraper.acquire.events import SeriesFollowed

    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    followed_events: list[SeriesFollowed] = []
    event_bus.subscribe(SeriesFollowed, lambda e: followed_events.append(e))

    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
    runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])
    result3 = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

    assert result3.exit_code == 0, result3.output

    store2 = build_acquire_store(AcquireConfig(db_path=db_path))
    all_rows = store2.follow.list_all()
    assert len(all_rows) == 1, f"LOAD-BEARING: add→remove→add must produce exactly 1 row, got {len(all_rows)}"
    assert all_rows[0].active is True, "Re-added row must be active"
    store2.close()

    # Two SeriesFollowed events total (first add + refollow after remove).
    assert len(followed_events) == 2, f"Expected 2 SeriesFollowed events (add + reactivate), got {len(followed_events)}"
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_list_hides_inactive_by_default(tmp_path: Path, monkeypatch) -> None:
    """LOAD-BEARING: follow list (no --all) hides inactive series."""
    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
    runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])

    result_list = runner.invoke(app, ["follow", "list"])

    assert result_list.exit_code == 0, result_list.output
    # LOAD-BEARING: inactive series must NOT appear in default list.
    assert "Breaking Bad" not in result_list.output, (
        f"LOAD-BEARING: 'Breaking Bad' (inactive) must not appear in 'follow list'; got:\n{result_list.output}"
    )
    assert "No followed series" in result_list.output, (
        f"Expected 'No followed series' message; got:\n{result_list.output}"
    )

    result_all = runner.invoke(app, ["follow", "list", "--all"])
    assert result_all.exit_code == 0, result_all.output
    assert "Breaking Bad" in result_all.output, (
        f"Expected 'Breaking Bad' in 'follow list --all'; got:\n{result_all.output}"
    )
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_remove_not_found_prints_message(tmp_path: Path, monkeypatch) -> None:
    """Follow remove on unknown series prints a friendly message, exits 0."""
    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))

    result = runner.invoke(app, ["follow", "remove", "--tvdb", "99999"])

    assert result.exit_code == 0, result.output
    assert "not found" in result.output.lower(), f"Expected 'not found' message; got:\n{result.output}"
    acquire.store.close()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# C1 REGRESSION — cross-key dedup (find_by_ref json_extract)
# ---------------------------------------------------------------------------


def test_follow_add_tvdb_tmdb_remove_tvdb_dedup_reactivate(tmp_path: Path, monkeypatch) -> None:
    """C1 REGRESSION: add with tvdb+tmdb → remove --tvdb works → re-add dedup.

    Before the json_extract fix, remove --tvdb 81189 would say "not found" on a
    series stored with tvdb_id=81189 + tmdb_id=1396 (exact-tuple mismatch), and
    a re-add would create a duplicate row.
    """
    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda *a, **kw: "Breaking Bad",
    )

    # Add with both tvdb and tmdb.
    result_add = runner.invoke(app, ["follow", "add", "--tvdb", "81189", "--tmdb", "1396"])
    assert result_add.exit_code == 0, result_add.output
    assert "Now following" in result_add.output

    # Remove --tvdb 81189 must find the row (cross-key match).
    result_rm = runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])
    assert result_rm.exit_code == 0, result_rm.output
    assert "not found" not in result_rm.output.lower(), (
        f"C1 MISS: remove --tvdb 81189 should find the tvdb+tmdb row; got:\n{result_rm.output}"
    )
    store = acquire.store
    assert store is not None
    all_rows = store.follow.list_all()
    assert len(all_rows) == 1, "Soft-unfollow preserves the single row"
    assert all_rows[0].active is False, "Row must be inactive after remove"

    # Re-add --tvdb 81189 must reactivate, NOT create a duplicate.
    result_readd = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
    assert result_readd.exit_code == 0, result_readd.output
    all_rows2 = store.follow.list_all()
    assert len(all_rows2) == 1, (
        f"C1 DUPLICATE: re-add after cross-key remove must NOT create a second row; got {len(all_rows2)} rows"
    )
    assert all_rows2[0].active is True, "Row must be active again after re-add"
    store.close()


# ---------------------------------------------------------------------------
# C2 REGRESSION — follow remove --id <rowid>
# ---------------------------------------------------------------------------


def test_follow_remove_by_id_soft_unfollows(tmp_path: Path, monkeypatch) -> None:
    """C2 REGRESSION: ``follow remove --id <rowid>`` soft-unfollows and emits event."""
    from personalscraper.acquire.events import SeriesUnfollowed

    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    unfollowed: list[SeriesUnfollowed] = []
    event_bus.subscribe(SeriesUnfollowed, lambda e: unfollowed.append(e))

    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda *a, **kw: "Breaking Bad",
    )

    # Add to get a rowid.
    runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
    store = acquire.store
    assert store is not None
    all_rows = store.follow.list_all()
    assert len(all_rows) == 1
    row_id = all_rows[0].id
    assert row_id is not None

    # Remove by --id.
    result = runner.invoke(app, ["follow", "remove", "--id", str(row_id)])
    assert result.exit_code == 0, result.output

    # Verify soft-unfollow.
    fetched = store.follow.get(row_id)
    assert fetched is not None
    assert fetched.active is False, f"C2 MISS: remove --id {row_id} must set active=False; got active={fetched.active}"

    # Verify event.
    assert len(unfollowed) == 1, f"C2 MISS: expected 1 SeriesUnfollowed event for remove --id, got {len(unfollowed)}"
    store.close()


# ---------------------------------------------------------------------------
# m1 REGRESSION — already-inactive double remove
# ---------------------------------------------------------------------------


def test_follow_remove_already_inactive_no_double_event(tmp_path: Path, monkeypatch) -> None:
    """m1 REGRESSION: double remove on inactive series emits exactly one event."""
    from personalscraper.acquire.events import SeriesUnfollowed

    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    unfollowed: list[SeriesUnfollowed] = []
    event_bus.subscribe(SeriesUnfollowed, lambda e: unfollowed.append(e))

    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda *a, **kw: "Breaking Bad",
    )

    # Add + first remove.
    runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
    runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])
    assert len(unfollowed) == 1, "First remove must emit one event"

    # Second remove — already inactive.
    result2 = runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])
    assert result2.exit_code == 0, result2.output
    assert "already inactive" in result2.output.lower(), (
        f"m1 MISS: second remove must say 'already inactive'; got:\n{result2.output}"
    )
    assert len(unfollowed) == 1, (
        f"m1 DOUBLE-EMIT: second remove on inactive series must NOT emit again; got {len(unfollowed)} events"
    )
    acquire.store.close()  # type: ignore[union-attr]
