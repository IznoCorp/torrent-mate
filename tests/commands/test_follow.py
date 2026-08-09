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


# ---------------------------------------------------------------------------
# RedisEventPublisher wiring (F3 / F12 / F29 — tm-shell dispatch C)
# ---------------------------------------------------------------------------


_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"


def test_follow_add_wires_publisher_and_closes(tmp_path: Path, monkeypatch, test_config) -> None:
    """``build_redis_publisher`` is called and its result is closed after add."""
    from unittest.mock import patch

    from personalscraper.conf.models.web import WebConfig

    cfg = test_config.model_copy(update={"web": WebConfig(enabled=True)})

    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)
    mock_publisher = MagicMock()

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=cfg.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(
            "personalscraper.commands.follow.build_redis_publisher",
            return_value=mock_publisher,
        ) as mock_build,
    ):
        result = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

    assert result.exit_code == 0, f"Expected exit 0; got:\n{result.output}"
    mock_build.assert_called_once()
    # First arg must be the event_bus; second arg is config.web.
    assert mock_build.call_args[0][0] is app_ctx.event_bus
    assert mock_build.call_args[0][1].enabled is True
    mock_publisher.close.assert_called_once()
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_add_no_close_when_publisher_is_none(tmp_path: Path, monkeypatch, test_config) -> None:
    """When ``build_redis_publisher`` returns None, no .close() is attempted."""
    from unittest.mock import patch

    from personalscraper.conf.models.web import WebConfig

    cfg = test_config.model_copy(update={"web": WebConfig(enabled=False)})

    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=cfg.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(
            "personalscraper.commands.follow.build_redis_publisher",
            return_value=None,
        ) as mock_build,
    ):
        result = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

    assert result.exit_code == 0, f"Expected exit 0; got:\n{result.output}"
    mock_build.assert_called_once()
    # No .close() on a None return — the ``if redis_publisher is not None``
    # guard in the finally block must prevent it.
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_remove_wires_publisher_and_closes(tmp_path: Path, monkeypatch, test_config) -> None:
    """``build_redis_publisher`` is called and its result is closed after remove."""
    from unittest.mock import patch

    from personalscraper.conf.models.web import WebConfig

    cfg = test_config.model_copy(update={"web": WebConfig(enabled=True)})

    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)
    mock_publisher = MagicMock()

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    # Seed: add a series first so remove has something to remove.
    with (
        patch(_PATCH_RESOLVE_PATH, return_value=cfg.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
    ):
        runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=cfg.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(
            "personalscraper.commands.follow.build_redis_publisher",
            return_value=mock_publisher,
        ) as mock_build,
    ):
        result = runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])

    assert result.exit_code == 0, f"Expected exit 0; got:\n{result.output}"
    mock_build.assert_called_once()
    assert mock_build.call_args[0][0] is app_ctx.event_bus
    assert mock_build.call_args[0][1].enabled is True
    mock_publisher.close.assert_called_once()
    acquire.store.close()  # type: ignore[union-attr]


def test_follow_detect_wires_publisher_and_closes(tmp_path: Path, monkeypatch, test_config) -> None:
    """``build_redis_publisher`` is called and its result is closed after detect."""
    from unittest.mock import patch

    from personalscraper.conf.models.web import WebConfig

    cfg = test_config.model_copy(update={"web": WebConfig(enabled=True)})

    db_path = tmp_path / "acquire.db"
    event_bus = EventBus()
    acquire = _acquire_ctx_for(db_path, event_bus)
    app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)
    mock_publisher = MagicMock()

    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
    monkeypatch.setattr(
        "personalscraper.commands.follow.resolve_series_title",
        lambda ref, registry, **kw: "Breaking Bad",
    )

    # Seed: add a series first so detect has something to poll.
    with (
        patch(_PATCH_RESOLVE_PATH, return_value=cfg.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
    ):
        runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=cfg.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(
            "personalscraper.commands.follow.build_redis_publisher",
            return_value=mock_publisher,
        ) as mock_build,
    ):
        result = runner.invoke(app, ["follow", "detect"])

    assert result.exit_code == 0, f"Expected exit 0; got:\n{result.output}"
    mock_build.assert_called_once()
    assert mock_build.call_args[0][0] is app_ctx.event_bus
    assert mock_build.call_args[0][1].enabled is True
    mock_publisher.close.assert_called_once()
    acquire.store.close()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# follow backfill-metadata (acq-states §7.3) — shares the enrichment authority
# ---------------------------------------------------------------------------


def test_media_ref_from_json_never_guesses() -> None:
    """A row with no usable provider id yields ``None`` — never a guessed ref.

    Replaces the former ``_candidate_matching_id`` test: the backfill no longer
    searches by title at all, so "never a wrong poster" is now structural (the
    provider is called BY ID or not at all). What remains to pin is that a
    legacy/ref-less row is recognised as unusable instead of being looked up.
    """
    from personalscraper.commands.follow import _media_ref_from_json

    assert _media_ref_from_json(None) is None
    assert _media_ref_from_json("") is None
    assert _media_ref_from_json("not json") is None
    assert _media_ref_from_json("[1, 2]") is None
    assert _media_ref_from_json('{"tvdb_id": null, "tmdb_id": null, "imdb_id": null}') is None
    ref = _media_ref_from_json('{"tvdb_id": 275274, "tmdb_id": 42}')
    assert ref is not None
    assert (ref.tvdb_id, ref.tmdb_id) == (275274, 42)


class _BackfillArtwork:
    """Minimal ArtworkItem stand-in for the backfill fakes."""

    def __init__(self, type_: str, url: str) -> None:
        self.type = type_
        self.url = url


class _BackfillDetails:
    """Minimal MediaDetails stand-in carrying the three card fields."""

    def __init__(self, year: int, overview: str, poster_url: str, title: str = "Breaking Bad") -> None:
        self.year = year
        self.overview = overview
        # A real provider always names the media — the stub must too, or the
        # backfill cannot repair a nameless row.
        self.title = title
        self.images = [_BackfillArtwork("poster", poster_url)]


class _BackfillTvdbClient:
    """Fake TVDB client: answers ``get_series`` for the seeded id, or explodes."""

    def __init__(self, *, boom: bool = False) -> None:
        self.boom = boom
        self.calls: list[int] = []

    def get_series(self, series_id: int) -> _BackfillDetails:
        """TVDB by-id series endpoint."""
        self.calls.append(series_id)
        if self.boom:
            raise RuntimeError("TVDB is unreachable")
        return _BackfillDetails(_BACKFILL_YEAR, _BACKFILL_OVERVIEW, _BACKFILL_POSTER)


class _FakeRegistry:
    """Provider registry stub returning the fake clients by name."""

    def __init__(self, tvdb: object) -> None:
        self._tvdb = tvdb

    def get(self, name: str) -> object | None:
        """Return the client registered under *name*."""
        return self._tvdb if name == "tvdb" else None


_BACKFILL_TVDB_ID = 468000
_BACKFILL_YEAR = 2024
_BACKFILL_OVERVIEW = "A series about furious things."
_BACKFILL_POSTER = "https://artworks.thetvdb.com/banners/posters/468000-1.jpg"


def _seed_follow_row(
    db_path: Path,
    *,
    poster: str | None,
    overview: str | None,
    year: int | None,
    title: str = "Furious",
) -> int:
    """Insert one follow with the given (possibly partial) card metadata.

    Args:
        db_path: The acquire.db to seed (created + migrated on the fly).
        poster: ``poster_url`` value, or ``None``.
        overview: ``overview`` value, or ``None``.
        year: ``year`` value, or ``None``.
        title: The stored title — pass ``""`` to reproduce a NAMELESS follow.

    Returns:
        The new ``followed_series`` rowid.
    """
    import sqlite3
    import time as _time

    from personalscraper.acquire.domain import FollowedSeries
    from personalscraper.core.identity import MediaRef

    store = build_acquire_store(AcquireConfig(db_path=db_path))
    try:
        follow_id = store.follow.add(
            FollowedSeries(
                media_ref=MediaRef(tvdb_id=_BACKFILL_TVDB_ID),
                title="Furious",
                added_at=int(_time.time()),
                active=True,
                kind="show",
            )
        )
    finally:
        store.close()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE followed_series SET poster_url = ?, overview = ?, year = ?, title = ? WHERE id = ?",
        (poster, overview, year, title, follow_id),
    )
    conn.commit()
    conn.close()
    return follow_id


def _read_card_metadata(db_path: Path, follow_id: int) -> tuple[str | None, str | None, int | None]:
    """Read ``(poster_url, overview, year)`` back from the DB."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT poster_url, overview, year FROM followed_series WHERE id = ?", (follow_id,)).fetchone()
    conn.close()
    return (row[0], row[1], row[2])


def _run_backfill(
    tmp_path: Path,
    monkeypatch,
    test_config,
    tvdb_client: object,
    *,
    dry_run: bool = False,
) -> tuple[Path, int, object]:
    """Seed a partial row and run ``follow backfill-metadata`` against fake providers.

    Returns:
        ``(db_path, follow_id, CliRunner result)``.
    """
    db_path = tmp_path / "acquire.db"
    follow_id = _seed_follow_row(db_path, poster=None, overview="already there", year=None)
    cfg = test_config.model_copy(update={"acquire": AcquireConfig(db_path=db_path)})

    event_bus = EventBus()
    app_ctx = AppContext(
        config=cfg,
        settings=MagicMock(),
        event_bus=event_bus,
        provider_registry=_FakeRegistry(tvdb_client),
        acquire=_acquire_ctx_for(db_path, event_bus),
    )
    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))

    from unittest.mock import patch

    argv = ["follow", "backfill-metadata"] + (["--dry-run"] if dry_run else [])
    with (
        patch(_PATCH_RESOLVE_PATH, return_value=cfg.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
    ):
        result = runner.invoke(app, argv)
    app_ctx.acquire.store.close()  # type: ignore[union-attr]
    return db_path, follow_id, result


def test_backfill_fills_only_missing_fields_and_extends_year(tmp_path: Path, monkeypatch, test_config) -> None:
    """Poster + year are fetched by ID; an overview already stored is preserved."""
    tvdb = _BackfillTvdbClient()
    db_path, follow_id, result = _run_backfill(tmp_path, monkeypatch, test_config, tvdb)

    assert result.exit_code == 0, result.output
    assert tvdb.calls == [_BACKFILL_TVDB_ID], "the provider must be queried BY ID, once"
    poster, overview, year = _read_card_metadata(db_path, follow_id)
    assert poster == _BACKFILL_POSTER
    assert year == _BACKFILL_YEAR, "acq-states §7.3: the backfill now extends to year"
    assert overview == "already there", "an existing value must never be overwritten"
    assert "Backfilled 1" in result.output


def test_backfill_dry_run_writes_nothing(tmp_path: Path, monkeypatch, test_config) -> None:
    """``--dry-run`` reports what it would do and leaves the row untouched."""
    tvdb = _BackfillTvdbClient()
    db_path, follow_id, result = _run_backfill(tmp_path, monkeypatch, test_config, tvdb, dry_run=True)

    assert result.exit_code == 0, result.output
    assert _read_card_metadata(db_path, follow_id) == (None, "already there", None)
    assert "(dry-run)" in result.output


def test_backfill_provider_outage_skips_the_row(tmp_path: Path, monkeypatch, test_config) -> None:
    """A provider failure leaves the row as-is and never fails the command."""
    tvdb = _BackfillTvdbClient(boom=True)
    db_path, follow_id, result = _run_backfill(tmp_path, monkeypatch, test_config, tvdb)

    assert result.exit_code == 0, result.output
    assert _read_card_metadata(db_path, follow_id) == (None, "already there", None)
    assert "skipped 1" in result.output


def test_backfill_repairs_a_nameless_follow(tmp_path: Path, monkeypatch, test_config) -> None:
    """A follow created WITHOUT a title gets its name from the provider.

    Operator, 2026-08-08: « Breaking Bad n'a toujours pas de titre ». The
    create-path fix only covers NEW follows; the rows already stored nameless
    (the add-by-ID form) are repaired here — blank in the list and blank in
    their own sheet until then.
    """
    db_path = tmp_path / "acquire.db"
    follow_id = _seed_follow_row(db_path, poster="https://kept/p.jpg", overview="kept", year=2008, title="")
    cfg = test_config.model_copy(update={"acquire": AcquireConfig(db_path=db_path)})

    tvdb = _BackfillTvdbClient()
    event_bus = EventBus()
    app_ctx = AppContext(
        config=cfg,
        settings=MagicMock(),
        event_bus=event_bus,
        provider_registry=_FakeRegistry(tvdb),
        acquire=_acquire_ctx_for(db_path, event_bus),
    )
    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))

    from unittest.mock import patch

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=cfg.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
    ):
        result = CliRunner().invoke(app, ["follow", "backfill-metadata"])

    assert result.exit_code == 0, result.output
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        title = conn.execute("SELECT title FROM followed_series WHERE id = ?", (follow_id,)).fetchone()[0]
    finally:
        conn.close()
    assert title not in ("", None), "a nameless follow must be repaired, not left blank"


def test_backfill_skips_rows_that_are_already_complete(tmp_path: Path, monkeypatch, test_config) -> None:
    """Idempotence: a complete row costs ZERO provider calls."""
    db_path = tmp_path / "acquire.db"
    follow_id = _seed_follow_row(db_path, poster="https://kept/p.jpg", overview="kept", year=1999)
    cfg = test_config.model_copy(update={"acquire": AcquireConfig(db_path=db_path)})

    tvdb = _BackfillTvdbClient()
    event_bus = EventBus()
    app_ctx = AppContext(
        config=cfg,
        settings=MagicMock(),
        event_bus=event_bus,
        provider_registry=_FakeRegistry(tvdb),
        acquire=_acquire_ctx_for(db_path, event_bus),
    )
    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))

    from unittest.mock import patch

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=cfg.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
    ):
        result = runner.invoke(app, ["follow", "backfill-metadata"])
    app_ctx.acquire.store.close()  # type: ignore[union-attr]

    assert result.exit_code == 0, result.output
    assert tvdb.calls == [], "a complete row must not be looked up"
    assert _read_card_metadata(db_path, follow_id) == ("https://kept/p.jpg", "kept", 1999)


# ---------------------------------------------------------------------------
# PR #320 review cycle 1 — the backfill must not hold a write lock across I/O
# ---------------------------------------------------------------------------


def _seed_partial_follow(db_path: Path, tvdb_id: int, title: str) -> int:
    """Insert one follow with NO card metadata and return its rowid."""
    import sqlite3
    import time as _time

    from personalscraper.acquire.domain import FollowedSeries
    from personalscraper.core.identity import MediaRef

    store = build_acquire_store(AcquireConfig(db_path=db_path))
    try:
        follow_id = store.follow.add(
            FollowedSeries(
                media_ref=MediaRef(tvdb_id=tvdb_id),
                title=title,
                added_at=int(_time.time()),
                active=True,
                kind="show",
            )
        )
    finally:
        store.close()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE followed_series SET poster_url = NULL, overview = NULL, year = NULL WHERE id = ?",
        (follow_id,),
    )
    conn.commit()
    conn.close()
    return follow_id


class _LockProbingTvdbClient:
    """Fake TVDB client that probes, on every call, whether a writer lock is held.

    Stands in for « another process » (the watcher, the web app, a cron): each
    provider call tries to take the acquire-DB write lock from an independent
    connection with a ZERO busy timeout. If the backfill is holding a
    transaction open across its provider I/O, that probe is refused.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self.calls: list[int] = []
        self.lock_refusals: list[int] = []

    def get_series(self, series_id: int) -> _BackfillDetails:
        """TVDB by-id series endpoint + a concurrent-writer probe."""
        import sqlite3

        self.calls.append(series_id)
        probe = sqlite3.connect(str(self._db_path), timeout=0, isolation_level=None)
        try:
            probe.execute("BEGIN IMMEDIATE")
            probe.execute("ROLLBACK")
        except sqlite3.OperationalError:
            self.lock_refusals.append(series_id)
        finally:
            probe.close()
        return _BackfillDetails(_BACKFILL_YEAR, _BACKFILL_OVERVIEW, _BACKFILL_POSTER)


def test_backfill_never_holds_a_write_lock_across_provider_calls(tmp_path: Path, monkeypatch, test_config) -> None:
    """Regression (PR #320 review, m10): no writer lock is held during provider I/O.

    The old form issued raw ``UPDATE``s on the scan connection and committed
    once at the end. Python's sqlite3 opens an implicit transaction on the first
    of those updates, so from row 2 onward the single-writer lock was held
    across every remaining HTTP round-trip — blocking the watcher, the web app
    and the crons for as long as the scan took, and hostage to one slow
    provider. Each row now writes through the store in its own short
    transaction, taken only after its provider call returned.
    """
    db_path = tmp_path / "acquire.db"
    first = _seed_partial_follow(db_path, 468001, "Furious One")
    second = _seed_partial_follow(db_path, 468002, "Furious Two")
    cfg = test_config.model_copy(update={"acquire": AcquireConfig(db_path=db_path)})

    tvdb = _LockProbingTvdbClient(db_path)
    event_bus = EventBus()
    app_ctx = AppContext(
        config=cfg,
        settings=MagicMock(),
        event_bus=event_bus,
        provider_registry=_FakeRegistry(tvdb),
        acquire=_acquire_ctx_for(db_path, event_bus),
    )
    monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))

    from unittest.mock import patch

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=cfg.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
    ):
        result = runner.invoke(app, ["follow", "backfill-metadata"])
    app_ctx.acquire.store.close()  # type: ignore[union-attr]

    assert result.exit_code == 0, result.output
    assert len(tvdb.calls) == 2, f"both rows must be enriched; got {tvdb.calls}"
    assert tvdb.lock_refusals == [], (
        "a concurrent writer was refused DURING a provider call — the backfill is "
        f"holding a transaction across its I/O (refused on {tvdb.lock_refusals})"
    )
    # And the writes still landed.
    for follow_id in (first, second):
        poster, _overview, year = _read_card_metadata(db_path, follow_id)
        assert poster == _BACKFILL_POSTER
        assert year == _BACKFILL_YEAR


def test_backfill_never_writes_through_a_raw_connection(tmp_path: Path) -> None:
    """Structure-level (m10): no ``UPDATE followed_series`` remains under commands/.

    Acquire-DB writes belong to the store seam (ACQUIRE-09). A raw UPDATE on a
    hand-rolled connection is what let the long transaction exist in the first
    place, so the absence is pinned rather than left to review discipline.
    """
    import personalscraper.commands as commands_pkg

    commands_root = Path(commands_pkg.__file__).resolve().parent
    offenders = sorted(
        str(py) for py in commands_root.rglob("*.py") if "UPDATE followed_series" in py.read_text(encoding="utf-8")
    )
    assert offenders == [], f"acquire-DB writes must go through the store; raw UPDATE found in {offenders}"
