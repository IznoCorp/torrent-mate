"""Tests for the daemon loop orchestration spine.

Covers ``run_loop`` (lock / reload / shutdown / exception-continue / heartbeat
paths) and ``_load_wiring_config`` (success, missing keys, missing files,
kill-switch).

The existing :func:`test_reload_failure_keeps_last_good_config` (6.4) is kept;
the 6.5 behavioural tests follow, organised by subject.
"""

from __future__ import annotations

import errno
import json
import logging
from pathlib import Path

import pytest
import yaml

from kanbanmate.app.tick import PersistedState, TickResult
from kanbanmate.app.wiring import WiringConfig
from kanbanmate.cli.logs import logs as cli_logs
from kanbanmate.daemon.loop import (
    PAUSE_FILENAME,
    DaemonConfig,
    DaemonLockError,
    _acquire_lock,
    _load_wiring_config,
    _wiring_from_registry,
    run_loop,
)


# ── helpers ────────────────────────────────────────────────────────────────


def _setup_config_files(
    tmp_path: Path,
    *,
    kanban_root: str | None = None,
    include: tuple[str, ...] | None = None,
    exclude: tuple[str, ...] | None = None,
) -> tuple[Path, Path]:
    """Create a valid ``config.yml`` and ``columns.yml`` in *tmp_path*.

    *include* / *exclude* control which top-level keys appear in the config;
    when both are ``None`` every required key is present.

    Returns ``(config_path, columns_path)``.
    """
    root = kanban_root if kanban_root is not None else str(tmp_path)
    columns_yml = tmp_path / "columns.yml"
    columns_yml.write_text("columns: []\n", encoding="utf-8")

    all_data: dict[str, object] = {
        "token": "fake-token",
        "project_id": "fake-project",
        "repo": "owner/name",
        "clone_dir": str(tmp_path / "clone"),
        "columns_path": str(columns_yml),
        "kanban_root": root,
    }
    if include is not None:
        data = {k: v for k, v in all_data.items() if k in include}
    elif exclude is not None:
        data = {k: v for k, v in all_data.items() if k not in exclude}
    else:
        data = dict(all_data)

    config_yml = tmp_path / "config.yml"
    config_yml.write_text(yaml.dump(data), encoding="utf-8")
    return config_yml, columns_yml


def _make_tick_result(**overrides: object) -> TickResult:
    """Build a zero-work :class:`TickResult`, overridable per keyword."""
    defaults: dict[str, object] = {
        "probe_token": "test",
        "snapshot_taken": False,
        "actions_executed": 0,
        "reaped": 0,
        "errors": 0,
    }
    defaults.update(overrides)
    return TickResult(**defaults)  # type: ignore[arg-type]


def _mock_run_one_tick_success(
    _wiring: WiringConfig,
    state: PersistedState | None,
) -> tuple[TickResult, PersistedState]:
    """A :func:`run_one_tick` stand-in that always succeeds."""
    return (_make_tick_result(), state if state is not None else PersistedState())


# ── 6.4 existing test ──────────────────────────────────────────────────────


def test_reload_failure_keeps_last_good_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bad config reload must not crash the daemon; keep the last-good config.

    Drives ``run_loop`` for 3 iterations with a valid initial config, then makes
    the first hot-reload raise ``yaml.YAMLError``.  Asserts the loop completes all
    iterations and every tick uses the same (first-loaded) ``WiringConfig``.
    """
    import yaml as _yaml

    from kanbanmate.app.tick import PersistedState as PS
    from kanbanmate.app.tick import TickResult as TR

    # -- Arrange: valid initial config files in a temp directory.
    columns_yml = tmp_path / "columns.yml"
    columns_yml.write_text("columns: []", encoding="utf-8")
    config_yml = tmp_path / "config.yml"
    config_yml.write_text(
        _yaml.dump(
            {
                "token": "fake-token",
                "project_id": "fake-project",
                "repo": "owner/name",
                "clone_dir": str(tmp_path / "clone"),
                "columns_path": str(columns_yml),
                "kanban_root": str(tmp_path),
            }
        ),
        encoding="utf-8",
    )

    daemon_config = DaemonConfig(
        kanban_root=tmp_path,
        config_path=config_yml,
    )

    # -- Arrange: _config_mtime returns a sequence that triggers one reload.
    # Iter 1: 100.0 (first load, wiring is None).
    # Iter 2: 200.0 (mtime changed → hot-reload attempted → our mock raises).
    # Iter 3: 200.0 (same mtime → no reload, loop continues with old config).
    mtimes = iter([100.0, 200.0, 200.0])
    monkeypatch.setattr(
        "kanbanmate.daemon.loop._config_mtime",
        lambda _path: next(mtimes, 200.0),
    )

    # -- Arrange: _load_wiring_config succeeds on first call then raises.
    call_count = [0]

    def mock_load(path: Path) -> WiringConfig:
        call_count[0] += 1
        if call_count[0] > 1:
            raise _yaml.YAMLError("simulated malformed config.yml mid-run")
        return _load_wiring_config(path)

    monkeypatch.setattr(
        "kanbanmate.daemon.loop._load_wiring_config",
        mock_load,
    )

    # -- Arrange: mock run_one_tick so the test doesn't need real GitHub/tmux/git.
    captured_wirings: list[WiringConfig] = []

    def mock_run_one_tick(wiring: WiringConfig, state: PS | None) -> tuple[TR, PS]:
        captured_wirings.append(wiring)
        return (
            TR(
                probe_token="test",
                snapshot_taken=False,
                actions_executed=0,
                reaped=0,
                errors=0,
            ),
            state or PS(),
        )

    monkeypatch.setattr(
        "kanbanmate.daemon.loop.run_one_tick",
        mock_run_one_tick,
    )

    # -- Act: run 3 iterations. Must not raise.
    run_loop(daemon_config, max_iterations=3, sleep=lambda _s: None)

    # -- Assert: the reload was attempted (initial load + hot-reload that failed).
    assert call_count[0] >= 2, (
        f"expected at least 2 _load_wiring_config calls (initial + failed reload), "
        f"got {call_count[0]}"
    )
    # -- Assert: every tick received the same (first-loaded, last-good) config.
    assert len(captured_wirings) == 3, f"expected 3 ticks, got {len(captured_wirings)}"
    first = captured_wirings[0]
    for i, w in enumerate(captured_wirings):
        assert w is first, (
            f"tick {i} received a different WiringConfig — reload should not "
            f"have replaced the last-good config"
        )


# ════════════════════════════════════════════════════════════════════════════
# 6.5 — _acquire_lock behavioural tests
# ════════════════════════════════════════════════════════════════════════════


def test_acquire_lock_succeeds(tmp_path: Path) -> None:
    """``_acquire_lock`` returns an open file handle holding an exclusive lock."""
    lock_path = tmp_path / "daemon.lock"
    handle = _acquire_lock(lock_path)

    assert handle is not None
    assert not handle.closed
    assert lock_path.exists()

    handle.close()


def test_acquire_lock_refuses_when_flock_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``flock`` raises ``OSError``, ``_acquire_lock`` raises ``DaemonLockError``.

    This is the single-instance guard: a second concurrent daemon process would
    find the lock already held and ``flock(…, LOCK_NB)`` would fail with EAGAIN.
    """
    lock_path = tmp_path / "daemon.lock"

    def _flock_raise(_fd: int, _op: int) -> None:
        raise OSError(errno.EAGAIN, "Resource temporarily unavailable")

    monkeypatch.setattr("kanbanmate.daemon.loop.fcntl.flock", _flock_raise)

    with pytest.raises(DaemonLockError, match="another kanban daemon already holds"):
        _acquire_lock(lock_path)


# ════════════════════════════════════════════════════════════════════════════
# 6.5 — _load_wiring_config behavioural tests
# ════════════════════════════════════════════════════════════════════════════


def test_load_wiring_config_valid_and_defaults(tmp_path: Path) -> None:
    """A valid config yields a :class:`WiringConfig` with correct fields.

    Also verifies that ``base`` and ``agent_command`` default to ``"main"`` and
    ``"claude"`` respectively when omitted.
    """
    config_yml, _columns_yml = _setup_config_files(tmp_path)

    result = _load_wiring_config(config_yml)

    assert result.token == "fake-token"
    assert result.project_id == "fake-project"
    assert result.repo == "owner/name"
    assert result.clone_dir == str(tmp_path / "clone")
    assert "columns:" in result.columns_yaml
    assert result.kanban_root == str(tmp_path)
    # Defaults (not in the config):
    assert result.base == "main"
    assert result.agent_command == "claude"
    # config_dir defaults to "" when omitted (defect 11 default — no worktree skill provisioning).
    assert result.config_dir == ""
    # No PAUSE file → kill_switch is False:
    assert result.kill_switch is False


def test_load_wiring_config_threads_config_dir(tmp_path: Path) -> None:
    """``config_dir`` is threaded off the config.yml override (defect 11).

    Without this the documented config.yml override left config_dir="" →
    provision_worktree_skills was a silent no-op and worktree agents could not resolve
    /implement:* skills, even though the registry path always set it.
    """
    import yaml as _yaml

    config_yml, _columns_yml = _setup_config_files(tmp_path)
    custom = {
        "token": "fake-token",
        "project_id": "fake-project",
        "repo": "owner/name",
        "clone_dir": str(tmp_path / "clone"),
        "columns_path": str(tmp_path / "columns.yml"),
        "kanban_root": str(tmp_path),
        "config_dir": "/home/izno/project/.claude",
    }
    config_yml.write_text(_yaml.dump(custom), encoding="utf-8")

    result = _load_wiring_config(config_yml)

    assert result.config_dir == "/home/izno/project/.claude"


def test_load_wiring_config_custom_base_and_command(tmp_path: Path) -> None:
    """Custom ``base`` and ``agent_command`` are honoured."""
    config_yml, _columns_yml = _setup_config_files(
        tmp_path,
        include=(
            "token",
            "project_id",
            "repo",
            "clone_dir",
            "columns_path",
            "kanban_root",
            "base",
            "agent_command",
        ),
    )
    # Overwrite with custom values.
    import yaml as _yaml

    custom = {
        "token": "ghp_custom",
        "project_id": "PVT_custom",
        "repo": "custom/repo",
        "clone_dir": "/tmp/custom-clone",
        "columns_path": str(tmp_path / "columns.yml"),
        "kanban_root": str(tmp_path),
        "base": "develop",
        "agent_command": "claude-deepseek",
    }
    config_yml.write_text(_yaml.dump(custom), encoding="utf-8")

    result = _load_wiring_config(config_yml)

    assert result.token == "ghp_custom"
    assert result.base == "develop"
    assert result.agent_command == "claude-deepseek"


def test_load_wiring_config_missing_required_key(tmp_path: Path) -> None:
    """A config missing a required key raises ``KeyError``."""
    # Omit "columns_path" — the first required key accessed.
    config_yml, _columns_yml = _setup_config_files(tmp_path, exclude=("columns_path",))
    # Write a minimal config that's valid YAML but missing the key.
    import yaml as _yaml

    config_yml.write_text(
        _yaml.dump({"token": "t", "project_id": "p", "repo": "r", "clone_dir": "c"}),
        encoding="utf-8",
    )

    with pytest.raises(KeyError):
        _load_wiring_config(config_yml)


def test_load_wiring_config_missing_columns_file(tmp_path: Path) -> None:
    """When the referenced ``columns.yml`` does not exist, ``FileNotFoundError`` is raised."""
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    # Point columns_path at a non-existent file.
    import yaml as _yaml

    bad = {
        "token": "t",
        "project_id": "p",
        "repo": "r",
        "clone_dir": "c",
        "columns_path": str(tmp_path / "nonexistent-columns.yml"),
        "kanban_root": str(tmp_path),
    }
    config_yml.write_text(_yaml.dump(bad), encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        _load_wiring_config(config_yml)


def test_load_wiring_config_pause_sentinel_present(tmp_path: Path) -> None:
    """When the ``PAUSE`` sentinel exists beside the config, ``kill_switch`` is ``True``."""
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    # Create the PAUSE sentinel in the kanban_root.
    (tmp_path / PAUSE_FILENAME).write_text("")

    result = _load_wiring_config(config_yml)

    assert result.kill_switch is True


def test_load_wiring_config_pause_sentinel_absent(tmp_path: Path) -> None:
    """When no ``PAUSE`` file exists, ``kill_switch`` is ``False``."""
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    # Explicitly ensure no PAUSE file.
    pause = tmp_path / PAUSE_FILENAME
    if pause.exists():
        pause.unlink()

    result = _load_wiring_config(config_yml)

    assert result.kill_switch is False


# ════════════════════════════════════════════════════════════════════════════
# 6.5 — run_loop behavioural tests
# ════════════════════════════════════════════════════════════════════════════


def test_run_loop_tick_exception_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A tick that raises is caught and the loop continues to the next iteration."""
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    call_count = [0]

    def mock_run_one_tick(
        wiring: WiringConfig,
        state: PersistedState | None,
    ) -> tuple[TickResult, PersistedState]:
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("simulated tick failure")
        return (
            _make_tick_result(),
            state if state is not None else PersistedState(),
        )

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", mock_run_one_tick)

    # Must not raise — the loop catches the exception and continues.
    run_loop(daemon_config, max_iterations=2, sleep=lambda _s: None)

    assert call_count[0] == 2, f"expected 2 ticks (one failed, one succeeded), got {call_count[0]}"


def test_run_loop_lock_released_in_finally(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The flock handle is closed in the ``finally`` block after normal exit."""
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    monkeypatch.setattr(
        "kanbanmate.daemon.loop.run_one_tick",
        _mock_run_one_tick_success,
    )

    # Spy on _acquire_lock to capture the handle.
    lock_handles: list[object] = []
    _orig_acquire = _acquire_lock

    def _spy_acquire(path: Path) -> object:
        h = _orig_acquire(path)
        lock_handles.append(h)
        return h

    monkeypatch.setattr("kanbanmate.daemon.loop._acquire_lock", _spy_acquire)

    run_loop(daemon_config, max_iterations=1, sleep=lambda _s: None)

    assert len(lock_handles) == 1, "expected exactly one lock acquisition"
    # The handle must be closed by the finally block.
    assert lock_handles[0].closed, "lock handle was not closed (finally did not run?)"  # type: ignore[attr-defined]


def test_run_loop_mtime_change_triggers_reload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the config file's ``mtime`` changes, the loop reloads ``WiringConfig``.

    The new config is used by subsequent ticks.
    """
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    # mtime sequence: 100 → 200 (change → reload) → 200 (same → no reload).
    mtimes = iter([100.0, 200.0, 200.0])
    monkeypatch.setattr(
        "kanbanmate.daemon.loop._config_mtime",
        lambda _p: next(mtimes, 200.0),
    )

    load_call_count = [0]

    def _spy_load(path: Path) -> WiringConfig:
        load_call_count[0] += 1
        return _load_wiring_config(path)

    monkeypatch.setattr("kanbanmate.daemon.loop._load_wiring_config", _spy_load)
    monkeypatch.setattr(
        "kanbanmate.daemon.loop.run_one_tick",
        _mock_run_one_tick_success,
    )

    run_loop(daemon_config, max_iterations=3, sleep=lambda _s: None)

    # Initial load on iter 1 (wiring is None) + reload on iter 2 (mtime changed).
    assert load_call_count[0] == 2, (
        f"expected 2 _load_wiring_config calls (initial + reload), got {load_call_count[0]}"
    )


def test_run_loop_mtime_nochange_skips_reload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the config file's ``mtime`` stays the same, no reload occurs."""
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    # Stable mtime: no reload after initial load.
    monkeypatch.setattr(
        "kanbanmate.daemon.loop._config_mtime",
        lambda _p: 100.0,
    )

    load_call_count = [0]

    def _spy_load(path: Path) -> WiringConfig:
        load_call_count[0] += 1
        return _load_wiring_config(path)

    monkeypatch.setattr("kanbanmate.daemon.loop._load_wiring_config", _spy_load)
    monkeypatch.setattr(
        "kanbanmate.daemon.loop.run_one_tick",
        _mock_run_one_tick_success,
    )

    run_loop(daemon_config, max_iterations=3, sleep=lambda _s: None)

    # Only the initial load (wiring is None on first iteration) — no reload.
    assert load_call_count[0] == 1, (
        f"expected 1 _load_wiring_config call (initial only), got {load_call_count[0]}"
    )


def test_run_loop_shutdown_flag_exits_after_tick(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shutdown flag makes the loop finish the current tick then exit.

    Simulates a SIGTERM/SIGINT arriving during the first tick's adaptive sleep:
    the loop must complete the in-flight iteration and then stop (no mid-tick
    kill — DESIGN §5).
    """
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    # Capture the flag so we can toggle it during the sleep.
    flag_ref: list[object] = []

    def _mock_install(flag: object) -> None:
        flag_ref.append(flag)

    monkeypatch.setattr("kanbanmate.daemon.loop._install_signal_handlers", _mock_install)

    tick_count = [0]

    def _mock_tick(
        wiring: WiringConfig,
        state: PersistedState | None,
    ) -> tuple[TickResult, PersistedState]:
        tick_count[0] += 1
        return (
            _make_tick_result(),
            state if state is not None else PersistedState(),
        )

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _mock_tick)

    def _sleep_then_flag(delay: float) -> None:
        # Simulate SIGTERM arriving during sleep: set the shutdown flag.
        if flag_ref:
            flag_ref[0].requested = True  # type: ignore[attr-defined]

    # max_iterations=10 would run 10 ticks without the flag; with the flag set
    # during the first sleep, the loop must exit after exactly 1 tick.
    run_loop(daemon_config, max_iterations=10, sleep=_sleep_then_flag)

    assert tick_count[0] == 1, (
        f"expected exactly 1 tick (flag set during sleep → stop after in-flight "
        f"iteration), got {tick_count[0]}"
    )


def test_run_loop_writes_heartbeat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After a completed tick, ``<kanban_root>/daemon.heartbeat`` exists as a healthy JSON marker (#1)."""
    from kanbanmate.core.heartbeat import parse_heartbeat

    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    monkeypatch.setattr(
        "kanbanmate.daemon.loop.run_one_tick",
        _mock_run_one_tick_success,
    )

    run_loop(daemon_config, max_iterations=1, sleep=lambda _s: None)

    heartbeat_path = tmp_path / "daemon.heartbeat"
    assert heartbeat_path.exists(), f"expected {heartbeat_path} to exist after a completed tick"
    content = heartbeat_path.read_text(encoding="utf-8").strip()
    assert content, "heartbeat file is empty"
    # The structured marker parses to a healthy record (a returning tick).
    heartbeat = parse_heartbeat(content)
    assert heartbeat.last_tick_ok is True
    assert heartbeat.consecutive_failures == 0
    assert heartbeat.ts > 0


def test_run_loop_heartbeat_tracks_consecutive_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run of raising ticks climbs ``consecutive_failures`` in the marker (#1).

    The proven dead-token 401-loop: every tick raises but the daemon stays alive and keeps
    writing a fresh marker — the marker must record the failure run so doctor can FAIL it.
    """
    from kanbanmate.core.heartbeat import parse_heartbeat

    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    def _always_raises(
        _wiring: WiringConfig, _state: PersistedState | None
    ) -> tuple[TickResult, PersistedState]:
        raise RuntimeError("simulated persistent tick failure")

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _always_raises)

    run_loop(daemon_config, max_iterations=3, sleep=lambda _s: None)

    heartbeat = parse_heartbeat((tmp_path / "daemon.heartbeat").read_text(encoding="utf-8"))
    assert heartbeat.last_tick_ok is False
    assert heartbeat.consecutive_failures == 3


def test_run_loop_heartbeat_failures_snap_back_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful tick after failures resets ``consecutive_failures`` to 0 (#1)."""
    from kanbanmate.core.heartbeat import parse_heartbeat

    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    calls = [0]

    def _fail_then_succeed(
        _wiring: WiringConfig, state: PersistedState | None
    ) -> tuple[TickResult, PersistedState]:
        calls[0] += 1
        if calls[0] <= 2:
            raise RuntimeError("transient failure")
        return (_make_tick_result(), state if state is not None else PersistedState())

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _fail_then_succeed)

    run_loop(daemon_config, max_iterations=3, sleep=lambda _s: None)

    heartbeat = parse_heartbeat((tmp_path / "daemon.heartbeat").read_text(encoding="utf-8"))
    assert heartbeat.last_tick_ok is True
    assert heartbeat.consecutive_failures == 0


def test_run_loop_probe_failure_counts_as_failed_poll(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX4-reconcile: a RETURNED tick flagged ``probe_failed`` is a FAILED poll, NOT a clean one.

    The earlier cut swallowed the probe failure and returned a clean result, so the loop reset the
    failure run every tick — a dead token / DNS outage looked healthy forever. The reconciled loop
    must climb ``consecutive_failures`` and write ``last_tick_ok=False`` for a probe-failed tick,
    exactly as it does for a tick that raised outright — so a SUSTAINED outage is visible to doctor
    and monitor D3 (and trips the backoff), even though every post-step still ran inside the tick.
    """
    from kanbanmate.core.heartbeat import parse_heartbeat

    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    def _probe_failed_tick(
        _wiring: WiringConfig, state: PersistedState | None
    ) -> tuple[TickResult, PersistedState]:
        # A returned (not raised) tick that degraded on a probe failure: post-steps ran, but the
        # result flags the failure so the loop must count it as a failed poll.
        result = _make_tick_result(probe_failed=True, probe_error=RuntimeError("probe boom"))
        return (result, state if state is not None else PersistedState())

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _probe_failed_tick)

    run_loop(daemon_config, max_iterations=3, sleep=lambda _s: None)

    heartbeat = parse_heartbeat((tmp_path / "daemon.heartbeat").read_text(encoding="utf-8"))
    assert heartbeat.last_tick_ok is False
    assert heartbeat.consecutive_failures == 3


def test_run_loop_probe_failure_then_recovery_snaps_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX4-reconcile: a TRANSIENT probe failure self-heals — a clean tick resets the failure run."""
    from kanbanmate.core.heartbeat import parse_heartbeat

    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    calls = [0]

    def _probe_fail_then_recover(
        _wiring: WiringConfig, state: PersistedState | None
    ) -> tuple[TickResult, PersistedState]:
        calls[0] += 1
        carried = state if state is not None else PersistedState()
        if calls[0] <= 2:
            return (_make_tick_result(probe_failed=True, probe_error=RuntimeError("blip")), carried)
        return (_make_tick_result(), carried)  # probe recovered → clean tick

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _probe_fail_then_recover)

    run_loop(daemon_config, max_iterations=3, sleep=lambda _s: None)

    heartbeat = parse_heartbeat((tmp_path / "daemon.heartbeat").read_text(encoding="utf-8"))
    assert heartbeat.last_tick_ok is True
    assert heartbeat.consecutive_failures == 0


def test_run_loop_probe_failure_with_401_drops_degraded_sentinel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX4-reconcile: a probe failure carrying a 401 forwards the breadcrumb (dead-token visibility)."""
    from kanbanmate.adapters.github._parsers import GitHubHTTPError
    from kanbanmate.daemon.loop import DEGRADED_FILENAME

    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    def _probe_failed_401(
        _wiring: WiringConfig, state: PersistedState | None
    ) -> tuple[TickResult, PersistedState]:
        err = GitHubHTTPError(401, '{"message": "Bad credentials"}')
        result = _make_tick_result(probe_failed=True, probe_error=err)
        return (result, state if state is not None else PersistedState())

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _probe_failed_401)

    run_loop(daemon_config, max_iterations=1, sleep=lambda _s: None)

    sentinel = tmp_path / DEGRADED_FILENAME
    assert sentinel.exists(), "expected a DEGRADED sentinel after a probe-failed 401 tick"
    assert "401" in sentinel.read_text(encoding="utf-8")


def test_run_loop_writes_degraded_sentinel_on_auth_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 401 raised out of the tick drops a DEGRADED sentinel + actionable log line (#1)."""
    from kanbanmate.adapters.github._parsers import GitHubHTTPError
    from kanbanmate.daemon.loop import DEGRADED_FILENAME

    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    def _auth_fail(
        _wiring: WiringConfig, _state: PersistedState | None
    ) -> tuple[TickResult, PersistedState]:
        raise GitHubHTTPError(401, '{"message": "Bad credentials"}')

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _auth_fail)

    run_loop(daemon_config, max_iterations=1, sleep=lambda _s: None)

    sentinel = tmp_path / DEGRADED_FILENAME
    assert sentinel.exists(), "expected a DEGRADED sentinel after a 401 tick failure"
    assert "401" in sentinel.read_text(encoding="utf-8")


def test_run_loop_clears_degraded_sentinel_on_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful tick clears a previously-dropped DEGRADED sentinel (#1, self-recovery)."""
    from kanbanmate.daemon.loop import DEGRADED_FILENAME

    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)
    # Pre-seed a stale DEGRADED sentinel from a prior auth failure.
    (tmp_path / DEGRADED_FILENAME).write_text("auth HTTP 401\n")

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _mock_run_one_tick_success)

    run_loop(daemon_config, max_iterations=1, sleep=lambda _s: None)

    assert not (tmp_path / DEGRADED_FILENAME).exists(), (
        "a successful tick must clear the DEGRADED sentinel"
    )


def test_run_loop_heartbeat_write_failure_warns_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """#14: a heartbeat-marker write failure is WARNed (not silently swallowed) and the loop survives.

    Before #14 the write was wrapped in a bare ``except: pass`` — a persistent failure (full
    disk, a perms regression on kanban_root) was invisible. The loop must still NOT crash on the
    failure (swallow-don't-crash), but a one-line ``logger.warning`` now makes it diagnosable.
    """
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _mock_run_one_tick_success)

    # Force ONLY the heartbeat-marker write to fail (leave every other Path.write_text intact).
    _orig_write_text = Path.write_text

    def _failing_write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self.name == "daemon.heartbeat":
            raise OSError("simulated heartbeat write failure (disk full)")
        return _orig_write_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", _failing_write_text)

    with caplog.at_level(logging.WARNING):
        # Must NOT raise — the daemon survives a heartbeat write failure.
        run_loop(daemon_config, max_iterations=1, sleep=lambda _s: None)

    # The swallow now leaves a breadcrumb so a persistent failure is diagnosable.
    assert any("daemon heartbeat" in record.getMessage() for record in caplog.records), (
        "expected a warning about the failed heartbeat write"
    )


def test_run_loop_writes_jsonl_log_and_reader_reads_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After one tick the daemon writes parseable JSONL and ``kanban logs`` reads it back.

    This is the round-trip test for the structured daemon log (DESIGN §5).
    The daemon installs a :class:`~kanbanmate.daemon.jsonl_log.JSONLHandler` in
    ``run_loop``; after one iteration ``<root>/log/daemon.jsonl`` must contain at
    least one valid JSON object, and :func:`kanbanmate.cli.logs.logs` must return it
    as non-empty rendered output.
    """
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    monkeypatch.setattr(
        "kanbanmate.daemon.loop.run_one_tick",
        _mock_run_one_tick_success,
    )

    # run_loop cleans up its own JSONL handler in its finally block,
    # so no manual handler removal is needed here.
    run_loop(daemon_config, max_iterations=1, sleep=lambda _s: None)

    # -- The daemon JSONL file must exist and contain at least one parseable line.
    jsonl_path = tmp_path / "log" / "daemon.jsonl"
    assert jsonl_path.exists(), f"expected {jsonl_path} to exist after a completed tick"
    raw = jsonl_path.read_text(encoding="utf-8").strip()
    assert raw, "JSONL log file is empty"
    # Parse the first line to validate it is well-formed JSON.
    first_line = raw.splitlines()[0]
    record = json.loads(first_line)
    assert isinstance(record, dict), "JSONL record must be a JSON object"
    # The record must have the standard daemon-log fields (ts, level, logger, msg).
    assert "ts" in record
    assert "level" in record
    assert "logger" in record
    assert "msg" in record
    # The logger name should be from the daemon package.
    assert record["logger"].startswith("kanbanmate"), (
        f"expected logger name to start with 'kanbanmate', got {record['logger']!r}"
    )

    # -- The reader (kanban logs) must be able to consume what the daemon wrote.
    rendered = cli_logs(tmp_path)
    assert rendered, "kanban logs returned empty output"
    # The rendered output must mention at least one daemon startup marker.
    assert "kanban daemon started" in rendered, (
        f"expected 'kanban daemon started' in rendered log, got: {rendered!r}"
    )


def test_failure_backoff_sleep_normal_regime_is_base() -> None:
    """Below the failure threshold the circuit breaker returns the base cadence unchanged (#2)."""
    from kanbanmate.daemon.loop import _failure_backoff_sleep

    assert _failure_backoff_sleep(0, 10.0) == 10.0
    assert _failure_backoff_sleep(2, 10.0) == 10.0  # still below the 3-failure threshold


def test_failure_backoff_sleep_escalates_geometrically_capped() -> None:
    """At/above the threshold the delay grows geometrically, capped at 300 s (#2)."""
    from kanbanmate.daemon.loop import _failure_backoff_sleep

    assert _failure_backoff_sleep(3, 10.0) == 10.0  # threshold: base * 2**0
    assert _failure_backoff_sleep(4, 10.0) == 20.0  # base * 2**1
    assert _failure_backoff_sleep(5, 10.0) == 40.0  # base * 2**2
    # Far into a sustained outage → clamped at the 300 s ceiling.
    assert _failure_backoff_sleep(100, 10.0) == 300.0


def test_run_loop_backs_off_during_failures_then_snaps_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The loop escalates the sleep during a failure run and snaps back on the first success (#2)."""
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    # Make next_sleep deterministic at the fixed 10 s base so we can assert escalation precisely.
    monkeypatch.setattr("kanbanmate.daemon.loop.next_sleep", lambda *a, **k: 10.0)

    calls = [0]

    def _fail4_then_succeed(
        _wiring: WiringConfig, state: PersistedState | None
    ) -> tuple[TickResult, PersistedState]:
        calls[0] += 1
        if calls[0] <= 4:
            raise RuntimeError("outage")
        return (_make_tick_result(), state if state is not None else PersistedState())

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _fail4_then_succeed)

    sleeps: list[float] = []
    run_loop(daemon_config, max_iterations=5, sleep=lambda s: sleeps.append(s))

    # Failures 1,2 → base (below threshold); failure 3 → base*2**0=10; failure 4 → base*2**1=20;
    # success on tick 5 → snap back to base 10.
    assert sleeps == [10.0, 10.0, 10.0, 20.0, 10.0]


def test_run_loop_max_iterations_zero_exits_immediately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``max_iterations=0`` exits without running any tick."""
    config_yml, _columns_yml = _setup_config_files(tmp_path)
    daemon_config = DaemonConfig(kanban_root=tmp_path, config_path=config_yml)

    tick_called = [False]

    def _mock_tick(
        wiring: WiringConfig,
        state: PersistedState | None,
    ) -> tuple[TickResult, PersistedState]:
        tick_called[0] = True
        return (
            _make_tick_result(),
            state if state is not None else PersistedState(),
        )

    monkeypatch.setattr("kanbanmate.daemon.loop.run_one_tick", _mock_tick)

    run_loop(daemon_config, max_iterations=0, sleep=lambda _s: None)

    assert not tick_called[0], "max_iterations=0 must not run any tick"


# ── registry-derived wiring (no config.yml) ──────────────────────────────────


def test_load_wiring_config_falls_back_to_registry_when_no_config_yml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no ``config.yml``, wiring is derived from ``projects.json`` + token + clone columns."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)  # force the token-file path
    root = tmp_path
    clone = root / "clone"
    cols_dir = clone / ".claude" / "kanban"
    cols_dir.mkdir(parents=True)
    (cols_dir / "columns.yml").write_text("columns: []\n", encoding="utf-8")
    (root / "token").write_text("ghp_registry\n", encoding="utf-8")
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_abc": {
                    "clone": str(clone),
                    "repo": "IznoCorp/demo",
                    "project_id": "PVT_abc",
                    "status_field_node_id": "PVTSSF_x",
                    "option_map": {"Backlog": "opt1"},
                }
            }
        ),
        encoding="utf-8",
    )

    # config.yml deliberately absent → the loader falls back to the registry.
    config = _load_wiring_config(root / "config.yml")

    assert config.project_id == "PVT_abc"
    assert config.repo == "IznoCorp/demo"
    assert config.clone_dir == str(clone)
    assert config.token == "ghp_registry"  # read from the 0600 token file, not config.yml
    assert config.columns_yaml == "columns: []\n"
    assert config.kanban_root == str(root)
    assert config.kill_switch is False


def test_load_wiring_config_no_config_no_registry_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ``config.yml`` and no registered project → ``FileNotFoundError`` pointing at init."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    with pytest.raises(FileNotFoundError, match="kanban init"):
        _load_wiring_config(tmp_path / "config.yml")


def test_load_wiring_config_registry_kill_switch_reflects_pause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The PAUSE sentinel under the root flips the registry-derived kill switch on."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    root = tmp_path
    clone = root / "clone"
    (clone / ".claude" / "kanban").mkdir(parents=True)
    (clone / ".claude" / "kanban" / "columns.yml").write_text("columns: []\n", encoding="utf-8")
    (root / "token").write_text("ghp_registry\n", encoding="utf-8")
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_abc": {
                    "clone": str(clone),
                    "repo": "IznoCorp/demo",
                    "project_id": "PVT_abc",
                    "status_field_node_id": "PVTSSF_x",
                    "option_map": {},
                }
            }
        ),
        encoding="utf-8",
    )
    (root / PAUSE_FILENAME).write_text("", encoding="utf-8")

    config = _load_wiring_config(root / "config.yml")

    assert config.kill_switch is True


# ── transitions.yml loading (phase 12.9) ────────────────────────────────────


def test_registry_wiring_reads_transitions_yaml_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_wiring_from_registry`` reads the clone's ``transitions.yml`` when it exists,
    so a freshly-init'd clone wires the whitelist automatically (phase 12.9)."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    root = tmp_path
    clone = root / "clone"
    kanban_dir = clone / ".claude" / "kanban"
    kanban_dir.mkdir(parents=True)
    (kanban_dir / "columns.yml").write_text("columns: []\n", encoding="utf-8")
    (kanban_dir / "transitions.yml").write_text(
        "project: test\ntransitions: []\n", encoding="utf-8"
    )
    (root / "token").write_text("ghp_registry\n", encoding="utf-8")
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_abc": {
                    "clone": str(clone),
                    "repo": "IznoCorp/demo",
                    "project_id": "PVT_abc",
                    "status_field_node_id": "PVTSSF_x",
                    "option_map": {"Backlog": "opt1"},
                }
            }
        ),
        encoding="utf-8",
    )

    config = _wiring_from_registry(root)

    assert config.transitions_yaml is not None
    assert "test" in config.transitions_yaml
    assert "transitions" in config.transitions_yaml


def test_registry_wiring_transitions_yaml_absent_yields_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the clone has no ``transitions.yml``, ``transitions_yaml`` is ``None``
    — the daemon still ticks via the legacy column-class path."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    root = tmp_path
    clone = root / "clone"
    kanban_dir = clone / ".claude" / "kanban"
    kanban_dir.mkdir(parents=True)
    (kanban_dir / "columns.yml").write_text("columns: []\n", encoding="utf-8")
    # NO transitions.yml written.
    (root / "token").write_text("ghp_registry\n", encoding="utf-8")
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_abc": {
                    "clone": str(clone),
                    "repo": "IznoCorp/demo",
                    "project_id": "PVT_abc",
                    "status_field_node_id": "PVTSSF_x",
                    "option_map": {"Backlog": "opt1"},
                }
            }
        ),
        encoding="utf-8",
    )

    config = _wiring_from_registry(root)

    assert config.transitions_yaml is None


def test_registry_wiring_reads_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_wiring_from_registry`` reads ``entry.config_dir`` off the registered project and
    threads it onto ``WiringConfig.config_dir`` (so the launch can provision skills; 14.6)."""
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)
    root = tmp_path
    clone = root / "clone"
    kanban_dir = clone / ".claude" / "kanban"
    kanban_dir.mkdir(parents=True)
    (kanban_dir / "columns.yml").write_text("columns: []\n", encoding="utf-8")
    (root / "token").write_text("ghp_registry\n", encoding="utf-8")
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_abc": {
                    "clone": str(clone),
                    "repo": "IznoCorp/demo",
                    "project_id": "PVT_abc",
                    "status_field_node_id": "PVTSSF_x",
                    "option_map": {"Backlog": "opt1"},
                    "config_dir": str(clone / ".claude"),
                    "dev_repo_path": "/home/dev/demo",
                }
            }
        ),
        encoding="utf-8",
    )

    config = _wiring_from_registry(root)

    assert config.config_dir == str(clone / ".claude")


def test_load_wiring_config_with_transitions_path(
    tmp_path: Path,
) -> None:
    """When ``config.yml`` carries a ``transitions_path`` pointing at a valid file,
    ``transitions_yaml`` is populated."""
    columns_yml = tmp_path / "columns.yml"
    columns_yml.write_text("columns: []\n", encoding="utf-8")
    transitions_yml = tmp_path / "transitions.yml"
    transitions_yml.write_text("project: test\ntransitions: []\n", encoding="utf-8")
    config_yml = tmp_path / "config.yml"
    config_yml.write_text(
        yaml.dump(
            {
                "token": "fake-token",
                "project_id": "fake-project",
                "repo": "owner/name",
                "clone_dir": str(tmp_path / "clone"),
                "columns_path": str(columns_yml),
                "transitions_path": str(transitions_yml),
                "kanban_root": str(tmp_path),
            }
        ),
        encoding="utf-8",
    )

    result = _load_wiring_config(config_yml)

    assert result.transitions_yaml is not None
    assert "test" in result.transitions_yaml


def test_load_wiring_config_transitions_path_absent_file_yields_none(
    tmp_path: Path,
) -> None:
    """When ``transitions_path`` points at a missing file, ``transitions_yaml`` is ``None``
    (tolerated — an un-migrated clone still ticks via the legacy path)."""
    columns_yml = tmp_path / "columns.yml"
    columns_yml.write_text("columns: []\n", encoding="utf-8")
    config_yml = tmp_path / "config.yml"
    config_yml.write_text(
        yaml.dump(
            {
                "token": "fake-token",
                "project_id": "fake-project",
                "repo": "owner/name",
                "clone_dir": str(tmp_path / "clone"),
                "columns_path": str(columns_yml),
                "transitions_path": str(tmp_path / "nonexistent-transitions.yml"),
                "kanban_root": str(tmp_path),
            }
        ),
        encoding="utf-8",
    )

    result = _load_wiring_config(config_yml)

    assert result.transitions_yaml is None


def test_load_wiring_config_without_transitions_path_yields_none(
    tmp_path: Path,
) -> None:
    """When ``config.yml`` has NO ``transitions_path`` key, ``transitions_yaml`` is ``None``
    (tolerated — an un-migrated clone still ticks)."""
    config_yml, _columns_yml = _setup_config_files(tmp_path)

    result = _load_wiring_config(config_yml)

    assert result.transitions_yaml is None


def test_no_transitions_yaml_ticks_with_default_whitelist(tmp_path: Path) -> None:
    """A config with no ``transitions.yml`` still yields a whitelist: ``build_tick_config`` falls
    back to ``DEFAULT_TRANSITIONS`` so the daemon NEVER ticks without one (DESIGN §8.0.6).

    End-to-end at the daemon's resolution layer: ``_load_wiring_config`` leaves
    ``transitions_yaml=None`` (no file on the clone), and the wiring builder then supplies the
    built-in PoC flow rather than a column model.
    """
    from kanbanmate.app.wiring import build_tick_config

    config_yml, _columns_yml = _setup_config_files(tmp_path)
    wiring = _load_wiring_config(config_yml)
    # No transitions.yml on the clone — the WiringConfig field stays None at this layer.
    assert wiring.transitions_yaml is None

    tick_config = build_tick_config(wiring)

    # The tick still gets a whitelist (the default PoC flow), never None / a column model.
    assert tick_config.transitions is not None
    backlog_to_brainstorming = tick_config.transitions.get("Backlog", "Brainstorming")
    assert backlog_to_brainstorming is not None
    assert backlog_to_brainstorming.prompt is not None
    assert "/implement:brainstorm" in backlog_to_brainstorming.prompt


def test_main_with_root_targets_alternate_runtime_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`kanban run --root X` → main(root=X) → run_loop with a DaemonConfig rooted at X (2nd daemon)."""
    from kanbanmate.daemon import loop as loop_mod

    captured: dict[str, object] = {}

    def _fake_run_loop(daemon_config: object = None, **_kw: object) -> None:
        captured["config"] = daemon_config

    monkeypatch.setattr(loop_mod, "run_loop", _fake_run_loop)
    monkeypatch.setattr("kanbanmate.daemon.loop.logging.basicConfig", lambda **_kw: None)

    loop_mod.main(root=tmp_path)

    cfg = captured["config"]
    assert cfg is not None
    assert cfg.kanban_root == tmp_path  # type: ignore[attr-defined]
    assert cfg.config_path == tmp_path / loop_mod.CONFIG_FILENAME  # type: ignore[attr-defined]


def test_main_without_root_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() with no root runs the default loop (run_loop called with no explicit config)."""
    from kanbanmate.daemon import loop as loop_mod

    captured: dict[str, object] = {}

    def _fake_run_loop(daemon_config: object = None, **_kw: object) -> None:
        captured["config"] = daemon_config
        captured["called"] = True

    monkeypatch.setattr(loop_mod, "run_loop", _fake_run_loop)
    monkeypatch.setattr("kanbanmate.daemon.loop.logging.basicConfig", lambda **_kw: None)

    loop_mod.main()

    assert captured.get("called") is True
    assert captured["config"] is None
