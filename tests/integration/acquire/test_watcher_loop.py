"""Integration tests for the watch daemon loop and watch-now sentinel command.

Tests use fake AppContext, patched subprocess, and controlled time to
exercise the watch loop without real qBittorrent, subprocesses, or sleeps.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from personalscraper.api.torrent._base import TorrentItem
from personalscraper.conf.models.watch_seed import WatchConfig

# ---------------------------------------------------------------------------
# autouse — reset the module-global _shutdown_requested before/after each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_shutdown_flag() -> Any:
    """Reset ``_shutdown_requested`` before and after each test.

    The watch loop exits when this flag is True.  Leaving it set from a
    previous test would cause the next test's loop to exit immediately.
    """
    import personalscraper.commands.watch as _wm

    _wm._shutdown_requested = False
    yield
    _wm._shutdown_requested = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_watch_config(
    tmp_path: Path,
    *,
    enabled: bool = True,
    poll_interval_s: int = 10,
    debounce_s: int = 60,
    safety_net_hours: int = 24,
) -> SimpleNamespace:
    """Build a minimal config stub with only the attributes ``watch()`` reads.

    Args:
        tmp_path: Pytest temp dir used as ``paths.data_dir``.
        enabled: ``WatchConfig.enabled``.
        poll_interval_s: ``WatchConfig.poll_interval_s``.
        debounce_s: ``WatchConfig.debounce_s``.
        safety_net_hours: ``WatchConfig.safety_net_hours``.

    Returns:
        A ``SimpleNamespace`` with ``watch`` (real ``WatchConfig``) and
        ``paths`` (``SimpleNamespace`` with ``data_dir=tmp_path``).
    """
    watch_cfg = WatchConfig(
        enabled=enabled,
        poll_interval_s=poll_interval_s,
        debounce_s=debounce_s,
        safety_net_hours=safety_net_hours,
    )
    return SimpleNamespace(
        watch=watch_cfg,
        paths=SimpleNamespace(data_dir=tmp_path),
    )


def _make_fake_app_context(
    *,
    completed: list[TorrentItem] | None = None,
    store_watch: MagicMock | None = None,
) -> SimpleNamespace:
    """Build a fake ``AppContext`` stub for the watch loop.

    Args:
        completed: Torrents returned by ``torrent_client.get_completed()``.
        store_watch: Pre-configured mock for ``acquire.store.watch``.

    Returns:
        A ``SimpleNamespace`` with ``torrent_client``, ``acquire``, and
        ``provider_registry`` — the three attributes ``watch()`` accesses.
    """
    if completed is None:
        completed = []
    if store_watch is None:
        store_watch = MagicMock()
        store_watch.get_last_successful_run_at.return_value = None

    torrent_client = MagicMock()
    torrent_client.get_completed.return_value = completed

    acquire = SimpleNamespace(
        store=SimpleNamespace(watch=store_watch),
        close=MagicMock(),
    )
    provider_registry = MagicMock()

    return SimpleNamespace(
        torrent_client=torrent_client,
        acquire=acquire,
        provider_registry=provider_registry,
    )


def _make_ctx(tmp_path: Path, *, enabled: bool = True, **kw: Any) -> SimpleNamespace:
    """Build a stub ``typer.Context`` carrying our minimal config.

    Args:
        tmp_path: Pytest temp dir.
        enabled: Passed through to :func:`_make_watch_config`.
        **kw: Passed through to :func:`_make_watch_config`.

    Returns:
        ``SimpleNamespace(obj=SimpleNamespace(config=...))``.
    """
    config = _make_watch_config(tmp_path, enabled=enabled, **kw)
    return SimpleNamespace(obj=SimpleNamespace(config=config))


def _completed_item(
    hash: str = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    name: str = "test-torrent",
    tags: list[str] | None = None,
) -> TorrentItem:
    """Build a minimal ``TorrentItem`` with only the fields the loop reads.

    Args:
        hash: Info hash string (default: 40-char hex).
        name: Display name.
        tags: Tag list (default ``[]``).

    Returns:
        A ``TorrentItem`` with ``hash``, ``name``, ``tags``, and neutral
        defaults for required fields the loop does not read.
    """
    if tags is None:
        tags = []
    return TorrentItem(
        hash=hash,
        name=name,
        size_bytes=0,
        progress=1.0,
        state="uploading",
        tags=tags,
    )


# ---------------------------------------------------------------------------
# Standard patch-set context manager (used by most loop tests)
# ---------------------------------------------------------------------------


class _WatchPatches:
    """Bundle of patches needed to invoke ``watch()`` in a test.

    Attributes:
        mock_time: Patched ``personalscraper.commands.watch.time`` mock.
        mock_subprocess: Patched ``personalscraper.commands.watch.subprocess`` mock.
        mock_build: Patched ``_build_app_context`` mock.
        mock_tracker_cls: Patched ``IngestTracker`` mock.
        mock_is_lock_held: Patched ``is_lock_held`` mock.
        mock_get_settings: Patched ``cli_compat.get_settings`` mock.
        mock_signal: Patched ``signal.signal`` mock.
        fake_app: The fake AppContext returned by ``_build_app_context``.
    """

    def __init__(
        self,
        fake_app: SimpleNamespace,
        *,
        is_lock_held: bool = False,
        ingested: dict[str, Any] | None = None,
    ) -> None:
        """Create the patch bundle (does NOT activate patches).

        Args:
            fake_app: Returned by ``_build_app_context``.
            is_lock_held: Return value for the patched ``is_lock_held``.
            ingested: Dict returned by ``IngestTracker.load()``.
        """
        if ingested is None:
            ingested = {}
        self.fake_app = fake_app
        self._is_lock_held = is_lock_held
        self._ingested = ingested

        self.mock_time = MagicMock()
        self.mock_subprocess = MagicMock()
        self.mock_build = MagicMock(return_value=fake_app)
        self.mock_is_lock_held = MagicMock(return_value=is_lock_held)
        self.mock_get_settings = MagicMock()
        self.mock_signal = MagicMock()

        # IngestTracker mock — the class is instantiated inside the loop.
        self._mock_tracker = MagicMock()
        self._mock_tracker.load.return_value = ingested
        self.mock_tracker_cls = MagicMock(return_value=self._mock_tracker)

        self._patches: list[Any] = []

    def _enter(self) -> "_WatchPatches":
        """Activate all patches.  Returns self for use as a context manager."""
        self._patches = [
            patch("personalscraper.commands.watch.time", self.mock_time),
            patch("personalscraper.commands.watch.subprocess", self.mock_subprocess),
            patch("personalscraper.commands.watch._build_app_context", self.mock_build),
            patch("personalscraper.commands.watch.IngestTracker", self.mock_tracker_cls),
            patch("personalscraper.commands.watch.is_lock_held", self.mock_is_lock_held),
            patch("personalscraper.commands.watch.cli_compat.get_settings", self.mock_get_settings),
            patch("personalscraper.commands.watch.signal.signal", self.mock_signal),
        ]
        for p in self._patches:
            p.start()
        return self

    def _exit(self, *exc_info: Any) -> None:
        """Deactivate all patches."""
        for p in self._patches:
            p.stop()

    def __enter__(self) -> "_WatchPatches":
        return self._enter()

    def __exit__(self, *exc_info: Any) -> None:
        self._exit(*exc_info)

    def set_time_sequence(
        self,
        times: list[float],
        *,
        shutdown_after_sleeps: int = 1,
    ) -> None:
        """Configure the time mock for N cycles then shutdown.

        Args:
            times: Values returned by successive ``time.time()`` calls.
            shutdown_after_sleeps: Set ``_shutdown_requested`` after this many
                ``time.sleep()`` calls (default 1 → one cycle).
        """
        self.mock_time.time.side_effect = times + [times[-1] + 1.0]  # safety pad

        sleep_count = [0]

        def _fake_sleep(_seconds: float) -> None:
            sleep_count[0] += 1
            if sleep_count[0] >= shutdown_after_sleeps:
                import personalscraper.commands.watch as _wm

                _wm._shutdown_requested = True

        self.mock_time.sleep.side_effect = _fake_sleep

    def set_single_cycle(self) -> None:
        """Shortcut: one cycle at t=0 then shutdown."""
        self.set_time_sequence([0.0], shutdown_after_sleeps=1)


# ---------------------------------------------------------------------------
# 1.  test_sentinel_written_by_watch_now  (ACC-9)
# ---------------------------------------------------------------------------


def test_sentinel_written_by_watch_now(tmp_path: Path) -> None:
    """ACC-9: ``watch-now`` writes the ``watch.trigger`` sentinel file."""
    from personalscraper.commands.watch import watch_now

    config = _make_watch_config(tmp_path, enabled=True)
    ctx = SimpleNamespace(obj=SimpleNamespace(config=config))

    watch_now(ctx)

    sentinel = tmp_path / "watch.trigger"
    assert sentinel.exists(), f"Expected sentinel at {sentinel}"
    assert sentinel.read_text() == ""


# ---------------------------------------------------------------------------
# 2.  test_sentinel_consumed_after_manual_fire
# ---------------------------------------------------------------------------


def test_sentinel_consumed_after_manual_fire(tmp_path: Path) -> None:
    """Sentinel pre-created → 1 cycle → Popen called with ``--trigger-reason manual`` → sentinel gone."""
    from personalscraper.commands.watch import watch

    # Pre-create the sentinel.
    (tmp_path / "watch.trigger").write_text("")

    fake_app = _make_fake_app_context()

    ctx = _make_ctx(tmp_path, enabled=True)

    with _WatchPatches(fake_app, is_lock_held=False) as p:
        p.set_single_cycle()

        watch(ctx)

    # Popen must have been called with the manual trigger reason.
    p.mock_subprocess.Popen.assert_called_once()
    popen_args = p.mock_subprocess.Popen.call_args[0][0]
    assert "--trigger-reason" in popen_args
    reason_idx = popen_args.index("--trigger-reason")
    assert popen_args[reason_idx + 1] == "manual"

    # Sentinel must be consumed.
    assert not (tmp_path / "watch.trigger").exists(), "Sentinel should have been unlinked"


# ---------------------------------------------------------------------------
# 3.  test_sentinel_kept_on_requeue
# ---------------------------------------------------------------------------


def test_sentinel_kept_on_requeue(tmp_path: Path) -> None:
    """Sentinel present + pipeline lock held → REQUEUE → NO Popen → sentinel persists."""
    from personalscraper.commands.watch import watch

    (tmp_path / "watch.trigger").write_text("")

    fake_app = _make_fake_app_context()

    ctx = _make_ctx(tmp_path, enabled=True)

    with _WatchPatches(fake_app, is_lock_held=True) as p:
        p.set_single_cycle()

        watch(ctx)

    # No Popen because the lock was held (REQUEUE decision).
    p.mock_subprocess.Popen.assert_not_called()

    # Sentinel must still exist.
    assert (tmp_path / "watch.trigger").exists(), "Sentinel should NOT have been unlinked on requeue"


# ---------------------------------------------------------------------------
# 4.  test_new_completion_spawns_cross_seed
# ---------------------------------------------------------------------------


def test_new_completion_spawns_cross_seed(tmp_path: Path) -> None:
    """Fresh completion → cycle 1 spawns ``cross-seed --hash H`` → dedup on cycle 2."""
    from personalscraper.commands.watch import watch

    h = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
    completed = [_completed_item(hash=h, name="fresh.torrent")]
    fake_app = _make_fake_app_context(completed=completed)

    ctx = _make_ctx(tmp_path, enabled=True)

    with _WatchPatches(fake_app, is_lock_held=False, ingested={}) as p:
        # 2 cycles: first for cross-seed, second for idle (dedup).
        # _interruptible_sleep slices poll_interval_s=10 into 1 s chunks →
        #   11 slices = 10 (cycle 1 full sleep) + 1 (cycle 2 early exit).
        p.set_time_sequence([0.0, 0.0], shutdown_after_sleeps=11)

        watch(ctx)

    # Cycle 1: cross-seed via subprocess.run (synchronous).
    p.mock_subprocess.run.assert_called_once()
    run_args = p.mock_subprocess.run.call_args[0][0]
    assert "--hash" in run_args
    hash_idx = run_args.index("--hash")
    assert run_args[hash_idx + 1] == h

    # Cycle 2: should NOT call run again (hash already in cross_seed_dispatched).
    assert p.mock_subprocess.run.call_count == 1, "cross-seed should only fire once per hash"


# ---------------------------------------------------------------------------
# 5.  test_debounce_fires_run
# ---------------------------------------------------------------------------


def test_debounce_fires_run(tmp_path: Path) -> None:
    """After cross-seed + debounce expiry → ``subprocess.Popen`` with ``run --no-console``."""
    from personalscraper.commands.watch import watch

    h = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
    completed = [_completed_item(hash=h, name="fresh.torrent")]
    fake_app = _make_fake_app_context(completed=completed)

    # debounce_s=60 (WatchConfig minimum), poll_interval_s=10.
    # Time jump from t=10 (START_DEBOUNCE) to t=70 to satisfy now >= debounce_until.
    ctx = _make_ctx(tmp_path, enabled=True, poll_interval_s=10, debounce_s=60)

    with _WatchPatches(fake_app, is_lock_held=False, ingested={}) as p:
        # Cycle 1 (t=0):  FIRE_CROSS_SEED
        # Cycle 2 (t=10): START_DEBOUNCE  (debounce_until = 10 + 60 = 70)
        # Cycle 3 (t=70): FIRE_RUN         (70 >= 70)
        # _interruptible_sleep slices poll_interval_s=10 into 1 s chunks →
        #   21 slices = 10+10 (cycles 1-2 full) + 1 (cycle 3 early exit).
        p.set_time_sequence([0.0, 10.0, 70.0], shutdown_after_sleeps=21)

        watch(ctx)

    # Popen must have been called for the run.
    assert p.mock_subprocess.Popen.call_count >= 1, "Expected at least one Popen call for the debounced run"
    popen_args = p.mock_subprocess.Popen.call_args[0][0]
    assert "--no-console" in popen_args
    assert "--trigger-reason" in popen_args
    reason_idx = popen_args.index("--trigger-reason")
    assert popen_args[reason_idx + 1] == "completion"


# ---------------------------------------------------------------------------
# 6.  test_run_success_recorded
# ---------------------------------------------------------------------------


def test_run_success_recorded(tmp_path: Path) -> None:
    """Tracked Popen returns 0 on poll → ``store.watch.set_last_successful_run_at`` called."""
    from personalscraper.commands.watch import watch

    # Sentinel present → manual run (simplest path to FIRE_RUN).
    (tmp_path / "watch.trigger").write_text("")

    fake_popen = MagicMock()
    fake_popen.poll.return_value = 0  # success

    store_watch_mock = MagicMock()
    store_watch_mock.get_last_successful_run_at.return_value = None
    fake_app = _make_fake_app_context(store_watch=store_watch_mock)

    ctx = _make_ctx(tmp_path, enabled=True)

    with _WatchPatches(fake_app, is_lock_held=False) as p:
        p.mock_subprocess.Popen.return_value = fake_popen
        p.set_single_cycle()

        watch(ctx)

    # The successful run must be persisted.
    store_watch_mock.set_last_successful_run_at.assert_called_once()


# ---------------------------------------------------------------------------
# 7.  test_run_failure_does_not_persist_or_reset_state  (ACC 10.4e)
# ---------------------------------------------------------------------------


def test_run_failure_does_not_persist_or_reset_state(tmp_path: Path) -> None:
    """Tracked Popen returns non-zero → ``set_last_successful_run_at`` NOT called, state untouched.

    The machine owns debounce/backoff resets (W7 anti-storm).  A failed run
    must neither persist the timestamp nor touch debounce/backoff fields.
    """
    from personalscraper.commands.watch import watch

    (tmp_path / "watch.trigger").write_text("")

    fake_popen = MagicMock()
    fake_popen.poll.return_value = 1  # failure

    store_watch_mock = MagicMock()
    store_watch_mock.get_last_successful_run_at.return_value = None
    fake_app = _make_fake_app_context(store_watch=store_watch_mock)

    ctx = _make_ctx(tmp_path, enabled=True)

    with _WatchPatches(fake_app, is_lock_held=False) as p:
        p.mock_subprocess.Popen.return_value = fake_popen
        p.set_single_cycle()

        watch(ctx)

    # Failure must NOT persist the timestamp.
    store_watch_mock.set_last_successful_run_at.assert_not_called()


# ---------------------------------------------------------------------------
# 8.  test_poll_error_skips_cycle
# ---------------------------------------------------------------------------


def test_poll_error_skips_cycle(tmp_path: Path) -> None:
    """``get_completed()`` raises a TORRENT_LISTING_ERRORS member → cycle skipped, loop continues."""
    from personalscraper.commands.watch import watch

    fake_app = _make_fake_app_context(completed=[])

    # Make get_completed raise on first call, return [] on subsequent.
    fake_app.torrent_client.get_completed.side_effect = [
        ConnectionError("fake connection error"),
        [],
    ]

    ctx = _make_ctx(tmp_path, enabled=True)

    with _WatchPatches(fake_app, is_lock_held=False) as p:
        # 2 cycles: first hits the error, second succeeds normally.
        # _interruptible_sleep slices poll_interval_s=10 into 1 s chunks →
        #   11 slices = 10 (cycle 1 sleep) + 1 (cycle 2 early exit).
        p.set_time_sequence([0.0, 0.0], shutdown_after_sleeps=11)

        # Must not crash.
        watch(ctx)

    # 10 slices for cycle 1 (error path sleep) + 1 slice for cycle 2
    # (shutdown flag set during first chunk).
    assert p.mock_time.sleep.call_count == 11, (
        f"Expected 11 sleep calls (10 + 1 interrupt), got {p.mock_time.sleep.call_count}"
    )


# ---------------------------------------------------------------------------
# 9.  test_disabled_exits_immediately
# ---------------------------------------------------------------------------


def test_disabled_exits_immediately(tmp_path: Path) -> None:
    """``WatchConfig(enabled=False)`` → returns before ``_build_app_context``."""
    from personalscraper.commands.watch import watch

    fake_app = _make_fake_app_context()

    ctx = _make_ctx(tmp_path, enabled=False)

    with _WatchPatches(fake_app) as p:
        watch(ctx)

    # _build_app_context must NOT have been called — the guard is at the top.
    p.mock_build.assert_not_called()


# ---------------------------------------------------------------------------
# 10.  test_sigterm_flag_stops_loop
# ---------------------------------------------------------------------------


def test_sigterm_flag_stops_loop(tmp_path: Path) -> None:
    """Set ``_shutdown_requested`` via sleep side-effect after 1 cycle → graceful shutdown."""
    from personalscraper.commands.watch import watch

    fake_app = _make_fake_app_context()
    ctx = _make_ctx(tmp_path, enabled=True)

    with _WatchPatches(fake_app, is_lock_held=False) as p:
        p.set_single_cycle()

        watch(ctx)

    # After shutdown, acquire.close() and provider_registry.close() must have been called.
    fake_app.acquire.close.assert_called_once()
    fake_app.provider_registry.close.assert_called_once()


# ---------------------------------------------------------------------------
# 11.  _interruptible_sleep
# ---------------------------------------------------------------------------


def test_interruptible_sleep_returns_early_when_shutdown_requested() -> None:
    """``_interruptible_sleep`` returns early when ``_shutdown_requested`` is set mid-sleep.

    The shutdown flag (set by SIGTERM handler) is polled between 1 s slices.
    Patching ``time.sleep`` to count calls and set the flag after 2 slices
    must result in fewer calls than the duration (5) — i.e. the function
    exits early instead of sleeping the full 5 s.
    """
    import personalscraper.commands.watch as _wm

    call_count = [0]

    def _counting_sleep(secs: float) -> None:
        call_count[0] += 1
        if call_count[0] >= 2:
            _wm._shutdown_requested = True

    with patch.object(_wm.time, "sleep", side_effect=_counting_sleep):
        _wm._interruptible_sleep(5.0)

    # Flag set after 2 calls — must return in well under the 5 full slices.
    assert call_count[0] < 5, f"Expected _interruptible_sleep to return early (<5 calls), got {call_count[0]}"


# ---------------------------------------------------------------------------
# 12.  ACC-8 — help tests via CliRunner
# ---------------------------------------------------------------------------


def test_watch_help(tmp_path: Path) -> None:
    """ACC-8: ``personalscraper watch --help`` exits 0."""
    from personalscraper.cli_app import app

    config = _make_watch_config(tmp_path, enabled=True)

    with (
        patch("personalscraper.conf.loader.load_config", return_value=config),
        patch("personalscraper.conf.loader.resolve_config_path", return_value=Path("/fake/config.json5")),
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["watch", "--help"])

    assert result.exit_code == 0, f"watch --help failed:\n{result.output}"


def test_watch_now_help(tmp_path: Path) -> None:
    """ACC-8: ``personalscraper watch-now --help`` exits 0."""
    from personalscraper.cli_app import app

    config = _make_watch_config(tmp_path, enabled=True)

    with (
        patch("personalscraper.conf.loader.load_config", return_value=config),
        patch("personalscraper.conf.loader.resolve_config_path", return_value=Path("/fake/config.json5")),
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["watch-now", "--help"])

    assert result.exit_code == 0, f"watch-now --help failed:\n{result.output}"
