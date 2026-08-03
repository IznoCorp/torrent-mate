"""CLI tests for ``personalscraper search``.

The eager ``load_config`` in the Typer callback is patched for every test here by
the autouse ``_mock_cli_config_load`` fixture in ``tests/commands/conftest.py`` —
without it these invocations would exit ``SystemExit(2)`` in CI, which has no
``config.json5``.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.store import build_acquire_store
from personalscraper.cli import app
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

runner = CliRunner()


# ── 1. Smoke ────────────────────────────────────────────────────────────────────


def test_search_command_registered() -> None:
    """The ``search`` command must appear in the app's help output."""
    result = runner.invoke(app, ["--help"])
    assert "search" in result.output, f"Expected 'search' in help output; got:\n{result.output}"


def test_search_help_exits_zero() -> None:
    """``search --help`` exits 0 and mentions --dry-run / --limit / --followed-id."""
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0, result.output
    assert "--dry-run" in result.output
    assert "--limit" in result.output
    assert "--followed-id" in result.output


# ── 2. Helpers ──────────────────────────────────────────────────────────────────


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


def _patch_capturing_boundary(monkeypatch, app_ctx) -> list[dict]:
    """Patch ``per_step_boundary`` and capture the kwargs each call receives.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        app_ctx: The AppContext the fake boundary yields.

    Returns:
        A list appended with one kwargs dict per boundary entry.
    """
    calls: list[dict] = []

    @contextmanager
    def _fake_boundary(config, settings, **kwargs):
        calls.append(kwargs)
        yield app_ctx

    monkeypatch.setattr("personalscraper.commands.search.per_step_boundary", _fake_boundary)
    return calls


def _empty_acquire(cfg):
    """Build an AcquireContext over a freshly-opened store for ``cfg``."""
    from personalscraper.acquire.context import AcquireContext

    return AcquireContext(tracker_registry=MagicMock(), store=build_acquire_store(cfg))


# ── 3. Dry-run — side-effect-free ───────────────────────────────────────────────


def test_search_dry_run_no_pending_items(tmp_path: Path, monkeypatch) -> None:
    """--dry-run with no pending items prints a friendly message, exits 0."""
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    empty_store = build_acquire_store(cfg)

    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(
        tracker_registry=MagicMock(),
        store=empty_store,
    )
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False, stream_events=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.search.per_step_boundary", _fake_boundary)

    result = runner.invoke(app, ["search", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "No pending wanted items" in result.output
    empty_store.close()


def test_search_dry_run_shows_queue(tmp_path: Path, monkeypatch) -> None:
    """--dry-run shows the queue with cadence gating, no tracker calls."""
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
            kind="episode",
            status="pending",
            enqueued_at=now - 86400 * 40,  # 40 days ago — past default cutoff
            season=1,
            episode=3,
        )
    )
    seed_store.close()

    test_store = build_acquire_store(cfg)

    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(
        tracker_registry=MagicMock(),
        store=test_store,
    )
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False, stream_events=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.search.per_step_boundary", _fake_boundary)

    result = runner.invoke(app, ["search", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "2 items in queue" in result.output
    # The movie (enqueued now) should be eligible for search
    assert "Would search:" in result.output
    # The old episode (40 days) should be past cutoff → would abandon
    assert "Would abandon (cutoff):" in result.output
    # Dry-run must not contact trackers
    mock_registry = mock_acquire.tracker_registry
    mock_registry.search_candidates.assert_not_called()

    test_store.close()


def test_search_dry_run_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    """--dry-run does not mutate the DB — before and after state identical."""
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    seed_store = build_acquire_store(cfg)
    now = int(time.time())
    seed_store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=333),
            kind="movie",
            status="pending",
            enqueued_at=now,
        )
    )
    seed_store.close()

    def _snapshot():
        s = build_acquire_store(cfg)
        items = s.wanted.list_pending()
        s.close()
        return [(it.media_ref.tvdb_id, it.status) for it in items]

    before = _snapshot()

    test_store = build_acquire_store(cfg)

    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(
        tracker_registry=MagicMock(),
        store=test_store,
    )
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False, stream_events=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.search.per_step_boundary", _fake_boundary)

    result = runner.invoke(app, ["search", "--dry-run"])

    assert result.exit_code == 0, result.output
    after = _snapshot()
    assert before == after, f"DB mutated by dry-run:\nbefore={before}\nafter={after}"
    test_store.close()


def test_search_dry_run_no_tracker_calls(tmp_path: Path, monkeypatch) -> None:
    """--dry-run never hits the tracker registry (zero search_candidates calls)."""
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    seed_store = build_acquire_store(cfg)
    now = int(time.time())
    seed_store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=444),
            kind="movie",
            status="pending",
            enqueued_at=now,
        )
    )
    seed_store.close()

    test_store = build_acquire_store(cfg)
    mock_registry = MagicMock()

    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(
        tracker_registry=mock_registry,
        store=test_store,
    )
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False, stream_events=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.search.per_step_boundary", _fake_boundary)

    result = runner.invoke(app, ["search", "--dry-run"])

    assert result.exit_code == 0, result.output
    mock_registry.search_candidates.assert_not_called()
    test_store.close()


def test_search_dry_run_respects_limit(tmp_path: Path, monkeypatch) -> None:
    """--dry-run --limit 1 over 2 pending items processes only the first."""
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    seed_store = build_acquire_store(cfg)
    now = int(time.time())
    seed_store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=555),
            kind="movie",
            status="pending",
            enqueued_at=now,
        )
    )
    seed_store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=666),
            kind="movie",
            status="pending",
            enqueued_at=now + 1,
        )
    )
    seed_store.close()

    test_store = build_acquire_store(cfg)

    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(
        tracker_registry=MagicMock(),
        store=test_store,
    )
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False, stream_events=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.search.per_step_boundary", _fake_boundary)

    result = runner.invoke(app, ["search", "--dry-run", "--limit", "1"])

    assert result.exit_code == 0, result.output
    assert "1 items in queue" in result.output, f"Expected 1 item with --limit 1; got:\n{result.output}"
    assert "tvdb_id=555" in result.output
    test_store.close()


def test_search_dry_run_respects_followed_id(tmp_path: Path, monkeypatch) -> None:
    """--followed-id keeps only that series' pending items in the preview."""
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    seed_store = build_acquire_store(cfg)
    now = int(time.time())
    kept_id = seed_store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=777), title="Kept Show", added_at=now))
    other_id = seed_store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=888), title="Other Show", added_at=now))
    seed_store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=777),
            kind="episode",
            status="pending",
            enqueued_at=now,
            followed_id=kept_id,
            season=1,
            episode=1,
        )
    )
    seed_store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=888),
            kind="episode",
            status="pending",
            enqueued_at=now,
            followed_id=other_id,
            season=1,
            episode=1,
        )
    )
    seed_store.close()

    test_store = build_acquire_store(cfg)

    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(tracker_registry=MagicMock(), store=test_store)
    _patch_capturing_boundary(monkeypatch, _make_mock_app_context(acquire=mock_acquire))

    result = runner.invoke(app, ["search", "--dry-run", "--followed-id", str(kept_id)])

    assert result.exit_code == 0, result.output
    assert "1 items in queue" in result.output, f"Expected only the targeted series' item; got:\n{result.output}"
    assert "tvdb_id=777" in result.output
    assert "tvdb_id=888" not in result.output
    test_store.close()


# ── 4. The torrent client is never built (NE-DOIT-PAS-8 / ACC-09) ───────────────


def test_search_dry_run_never_builds_torrent_client(tmp_path: Path, monkeypatch) -> None:
    """--dry-run opens its boundary with build_torrent_client=False."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    acquire = _empty_acquire(cfg)
    calls = _patch_capturing_boundary(monkeypatch, _make_mock_app_context(acquire=acquire))

    result = runner.invoke(app, ["search", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert len(calls) == 1, f"Expected exactly one boundary entry; got {calls}"
    assert calls[0]["build_torrent_client"] is False, (
        f"search --dry-run must never connect to the torrent daemon; got {calls[0]}"
    )
    assert acquire.store is not None
    acquire.store.close()


def test_search_real_run_never_builds_torrent_client(tmp_path: Path, monkeypatch) -> None:
    """A REAL search run also opens its boundary with build_torrent_client=False.

    The availability pass states what is takeable; it downloads nothing, so it has
    no business waking qBittorrent (NE-DOIT-PAS-8).
    """
    from personalscraper.acquire.reconcile import ReconcileSummary
    from personalscraper.acquire.service import SearchRunSummary

    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    acquire = _empty_acquire(cfg)
    calls = _patch_capturing_boundary(monkeypatch, _make_mock_app_context(acquire=acquire))

    fake_service = MagicMock()
    fake_service.run_search.return_value = SearchRunSummary()
    monkeypatch.setattr(
        "personalscraper.commands.search._build_search_service",
        lambda acquire, config, event_bus: fake_service,
    )
    monkeypatch.setattr(
        "personalscraper.commands.search._reconcile_before_search",
        lambda acquire, event_bus, console: ReconcileSummary(),
    )

    result = runner.invoke(app, ["search"])

    assert result.exit_code == 0, result.output
    assert len(calls) == 1, f"Expected exactly one boundary entry; got {calls}"
    assert calls[0]["build_torrent_client"] is False, f"search must never connect to the torrent daemon; got {calls[0]}"
    assert acquire.store is not None
    acquire.store.close()


def test_build_search_service_wires_no_torrent_client(tmp_path: Path, test_config) -> None:
    """``_build_search_service`` constructs the orchestrator with torrent_client=None."""
    from personalscraper.commands.search import _build_search_service

    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    acquire = _empty_acquire(cfg)

    with patch("personalscraper.acquire.orchestrator.GrabOrchestrator") as mock_orchestrator:
        _build_search_service(acquire, test_config, MagicMock())

    mock_orchestrator.assert_called_once()
    client = mock_orchestrator.call_args.kwargs["torrent_client"]
    assert client is None, f"Search orchestrator must hold no torrent client; got {client!r}"
    assert acquire.store is not None
    acquire.store.close()


# ── 5. Real run with fake service ───────────────────────────────────────────────


def test_search_reports_summary_counts(tmp_path: Path, monkeypatch) -> None:
    """Real run prints summary line with counts from the service's SearchRunSummary."""
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    seed_store = build_acquire_store(cfg)
    seed_store.close()

    test_store = build_acquire_store(cfg)

    from personalscraper.acquire.context import AcquireContext
    from personalscraper.acquire.service import SearchRunSummary

    mock_acquire = AcquireContext(
        tracker_registry=MagicMock(),
        store=test_store,
    )
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False, stream_events=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.search.per_step_boundary", _fake_boundary)

    # Patch _build_search_service to return a mock service whose run_search
    # returns known counts.
    fake_service = MagicMock()
    fake_summary = SearchRunSummary(available=3, waiting=5, unverified=1, abandoned=0, skipped=2)
    fake_service.run_search.return_value = fake_summary

    monkeypatch.setattr(
        "personalscraper.commands.search._build_search_service",
        lambda acquire, config, event_bus: fake_service,
    )

    # Also patch _reconcile_before_search to avoid DB writes during the reconcile sweep.
    from personalscraper.acquire.reconcile import ReconcileSummary

    monkeypatch.setattr(
        "personalscraper.commands.search._reconcile_before_search",
        lambda acquire, event_bus, console: ReconcileSummary(),
    )

    result = runner.invoke(app, ["search"])

    assert result.exit_code == 0, f"Expected exit 0; got {result.exit_code}:\n{result.output}"
    assert "Search complete:" in result.output
    assert "3 available" in result.output
    assert "5 waiting" in result.output
    assert "1 unverified" in result.output
    assert "0 abandoned" in result.output
    assert "2 skipped" in result.output
    test_store.close()


def test_search_forwards_limit_and_followed_id_to_service(tmp_path: Path, monkeypatch) -> None:
    """A real run forwards --limit / --followed-id verbatim to ``run_search``."""
    from personalscraper.acquire.reconcile import ReconcileSummary
    from personalscraper.acquire.service import SearchRunSummary

    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    acquire = _empty_acquire(cfg)
    _patch_capturing_boundary(monkeypatch, _make_mock_app_context(acquire=acquire))

    fake_service = MagicMock()
    fake_service.run_search.return_value = SearchRunSummary()
    monkeypatch.setattr(
        "personalscraper.commands.search._build_search_service",
        lambda acquire, config, event_bus: fake_service,
    )
    monkeypatch.setattr(
        "personalscraper.commands.search._reconcile_before_search",
        lambda acquire, event_bus, console: ReconcileSummary(),
    )

    result = runner.invoke(app, ["search", "--limit", "3", "--followed-id", "9"])

    assert result.exit_code == 0, result.output
    fake_service.run_search.assert_called_once_with(limit=3, followed_id=9)
    assert acquire.store is not None
    acquire.store.close()


# ── 5. RedisEventPublisher wiring ──────────────────────────────────────────────


def test_search_dry_run_wires_publisher_and_closes(tmp_path: Path, monkeypatch) -> None:
    """``build_redis_publisher`` is called and its result is closed after search --dry-run."""
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.core.app_context import AppContext
    from personalscraper.core.event_bus import EventBus

    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    test_store = build_acquire_store(cfg)

    event_bus = EventBus()
    mock_acquire = AcquireContext(
        tracker_registry=MagicMock(),
        store=test_store,
    )
    app_ctx = AppContext(
        config=MagicMock(),
        settings=MagicMock(),
        event_bus=event_bus,
        provider_registry=MagicMock(),
        acquire=mock_acquire,
    )
    mock_publisher = MagicMock()

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False, stream_events=False):
        yield app_ctx

    monkeypatch.setattr("personalscraper.commands.search.per_step_boundary", _fake_boundary)

    with patch(
        "personalscraper.commands.search.build_redis_publisher",
        return_value=mock_publisher,
    ) as mock_build:
        result = runner.invoke(app, ["search", "--dry-run"])

    assert result.exit_code == 0, f"Expected exit 0; got:\n{result.output}"
    mock_build.assert_called_once()
    assert mock_build.call_args[0][0] is app_ctx.event_bus
    mock_publisher.close.assert_called_once()
    test_store.close()


def test_search_no_close_when_publisher_is_none(tmp_path: Path, monkeypatch) -> None:
    """When ``build_redis_publisher`` returns None, no ``.close()`` is attempted."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    acquire = _empty_acquire(cfg)
    _patch_capturing_boundary(monkeypatch, _make_mock_app_context(acquire=acquire))

    with patch(
        "personalscraper.commands.search.build_redis_publisher",
        return_value=None,
    ) as mock_build:
        result = runner.invoke(app, ["search", "--dry-run"])

    assert result.exit_code == 0, f"Expected exit 0; got:\n{result.output}"
    mock_build.assert_called_once()
    assert acquire.store is not None
    acquire.store.close()
