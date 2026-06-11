"""CLI tests for ``personalscraper grab``."""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.store import build_acquire_store
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.cli import app
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

runner = CliRunner()


# ── 1. Smoke ────────────────────────────────────────────────────────────────────


def test_grab_command_registered() -> None:
    """The ``grab`` command must appear in the app's help output."""
    result = runner.invoke(app, ["--help"])
    assert "grab" in result.output, f"Expected 'grab' in help output; got:\n{result.output}"


def test_grab_help_exits_zero() -> None:
    """``grab --help`` exits 0 and mentions --dry-run / --limit."""
    result = runner.invoke(app, ["grab", "--help"])
    assert result.exit_code == 0, result.output
    assert "--dry-run" in result.output
    assert "--limit" in result.output


# ── 2. Dry-run E2E — side-effect-free ───────────────────────────────────────────


def _make_mock_app_context(*, acquire):
    """Build a minimal AppContext with the given acquire context."""
    from personalscraper.core.app_context import AppContext
    from personalscraper.core.event_bus import EventBus

    return AppContext(
        config=MagicMock(),
        settings=MagicMock(),
        event_bus=EventBus(),
        provider_registry=MagicMock(),
        acquire=acquire,
    )


def test_grab_dry_run_prints_top_candidate(tmp_path: Path, monkeypatch) -> None:
    """E2E: --dry-run prints top candidate without side effects.

    Seeded wanted item stays 'pending' — no state change, no add call.
    """
    # 1. Seed a real acquire.db with one pending item.
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    seed_store = build_acquire_store(cfg)
    seed_store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=12345),
            kind="movie",
            status="pending",
            enqueued_at=int(time.time()),
        )
    )
    seed_store.close()

    # 2. Build a mock tracker registry that returns one candidate.
    mock_result = TrackerResult(
        provider="lacale",
        tracker_id="t1",
        title="Movie 2020 MULTi 1080p BluRay x265-GRP",
        size=ByteSize(5_000_000_000),
        seeders=50,
        leechers=0,
        resolution="1080p",
        info_hash="abc123",
        download_url="https://lacale.test/t/1",
    )
    mock_outcome = SearchOutcome(results=[mock_result], trackers_queried=1, trackers_errored=0)

    mock_registry = MagicMock()
    mock_registry.search_candidates.return_value = mock_outcome

    # Re-open a store pointing at the same seeded DB (lazy open — reads existing data).
    test_store = build_acquire_store(cfg)

    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(
        tracker_registry=mock_registry,
        store=test_store,
        grab=None,  # dry-run: no torrent client needed
    )
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.grab.per_step_boundary", _fake_boundary)

    # 3. Run grab --dry-run.
    result = runner.invoke(app, ["grab", "--dry-run"])

    # 4. Assert the output contains the top candidate info.
    assert result.exit_code == 0, f"Expected exit 0; got {result.exit_code}:\n{result.output}"
    assert "Movie 2020" in result.output, f"Expected 'Movie 2020' in dry-run output; got:\n{result.output}"

    # 5. Side-effect-free: the wanted item must still be 'pending'.
    test_store2 = build_acquire_store(cfg)
    pending = test_store2.wanted.list_pending()
    assert len(pending) == 1, f"Expected 1 pending item; got {len(pending)}"
    assert pending[0].status == "pending", (
        f"Expected status='pending' (side-effect-free dry-run); got status={pending[0].status!r}"
    )
    assert pending[0].grabbed_hash is None, f"Expected grabbed_hash=None (no add); got {pending[0].grabbed_hash!r}"
    test_store2.close()
    test_store.close()


def test_grab_dry_run_no_pending_items(tmp_path: Path, monkeypatch) -> None:
    """--dry-run with no pending items prints a friendly message, exits 0."""
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    empty_store = build_acquire_store(cfg)

    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(
        tracker_registry=MagicMock(),
        store=empty_store,
        grab=None,
    )
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.grab.per_step_boundary", _fake_boundary)

    result = runner.invoke(app, ["grab", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "No pending wanted items" in result.output
    empty_store.close()


# ── 3. No-torrent-client path ───────────────────────────────────────────────────


def test_grab_fails_loud_when_no_torrent_client(monkeypatch) -> None:
    """Without torrent client (grab is None), grab (non-dry-run) exits with error."""
    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(
        tracker_registry=MagicMock(),
        store=None,
        grab=None,
    )
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.grab.per_step_boundary", _fake_boundary)

    result = runner.invoke(app, ["grab"])

    assert result.exit_code != 0 or "No torrent client" in result.output, (
        f"Expected non-zero exit or 'No torrent client' message; got exit={result.exit_code}:\n{result.output}"
    )


# ── 4. --limit flag ─────────────────────────────────────────────────────────────


def test_grab_dry_run_respects_limit(tmp_path: Path, monkeypatch) -> None:
    """--limit 1 over 2 pending items processes only the first."""
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    seed_store = build_acquire_store(cfg)
    now = int(time.time())
    seed_store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=111),
            kind="movie",
            status="pending",
            enqueued_at=now,
        )
    )
    seed_store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=222),
            kind="movie",
            status="pending",
            enqueued_at=now + 1,
        )
    )
    seed_store.close()

    mock_result = TrackerResult(
        provider="lacale",
        tracker_id="t1",
        title="Limited Movie 2024 1080p x265-GRP",
        size=ByteSize(3_000_000_000),
        seeders=10,
        leechers=0,
        resolution="1080p",
        info_hash="def456",
        download_url="https://lacale.test/t/2",
    )
    mock_outcome = SearchOutcome(results=[mock_result], trackers_queried=1, trackers_errored=0)

    mock_registry = MagicMock()
    mock_registry.search_candidates.return_value = mock_outcome

    test_store = build_acquire_store(cfg)

    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(
        tracker_registry=mock_registry,
        store=test_store,
        grab=None,
    )
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.grab.per_step_boundary", _fake_boundary)

    result = runner.invoke(app, ["grab", "--dry-run", "--limit", "1"])

    assert result.exit_code == 0, result.output
    # Should only print one "Item:" line
    item_lines = [line for line in result.output.split("\n") if line.strip().startswith("Item:")]
    assert len(item_lines) == 1, f"Expected 1 item with --limit 1; got {len(item_lines)}:\n{result.output}"
    assert "tvdb_id=111" in result.output or "111" in item_lines[0]
    test_store.close()
