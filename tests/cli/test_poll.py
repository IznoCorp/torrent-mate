"""Tests for :mod:`kanbanmate.cli.poll` — the single-tick ``kanban poll --once`` path.

``poll_once`` must run **exactly one** tick and return its result, with no loop, no lock, and no
sleep. Both seams are injected: a stub config loader (so no YAML/columns file is read) and a stub
tick runner (so no real adapters are wired). The tests assert the tick runs once, the config is
loaded from ``<root>/config.yml``, and the returned :class:`~kanbanmate.app.tick.TickResult` is the
runner's result.
"""

from __future__ import annotations

from pathlib import Path

from kanbanmate.app.tick import PersistedState, TickResult
from kanbanmate.app.wiring import WiringConfig
from kanbanmate.cli.poll import poll_once, render_poll
from kanbanmate.daemon.loop import CONFIG_FILENAME


def _config() -> WiringConfig:
    """Build a minimal canned :class:`WiringConfig` (never wired to real adapters in these tests)."""
    return WiringConfig(
        token="tok",
        project_id="PVT_1",
        repo="org/repo",
        clone_dir="/tmp/clone",
        columns_yaml="columns: []",
    )


def _result() -> TickResult:
    """Build a canned :class:`TickResult` for the stub runner to return."""
    return TickResult(
        probe_token="probe-1",
        snapshot_taken=True,
        actions_executed=2,
        reaped=1,
        errors=0,
    )


def test_poll_once_runs_exactly_one_tick(tmp_path: Path) -> None:
    """``poll_once`` invokes the tick runner exactly once and returns its result."""
    calls: list[tuple[WiringConfig, PersistedState | None]] = []

    def fake_run_tick(
        config: WiringConfig, state: PersistedState | None
    ) -> tuple[TickResult, PersistedState]:
        """Record the call and return a canned result + a fresh baseline."""
        calls.append((config, state))
        return _result(), PersistedState()

    result = poll_once(
        root=tmp_path,
        load_config=lambda _path: _config(),
        run_tick=fake_run_tick,
    )

    # Exactly one tick ran (no loop), and its result is returned verbatim.
    assert len(calls) == 1
    assert result.actions_executed == 2
    assert result.reaped == 1
    # The tick starts from a cold baseline (a one-shot poll carries no prior state).
    assert isinstance(calls[0][1], PersistedState)
    assert calls[0][1].columns_by_item == {}


def test_poll_once_loads_config_from_root(tmp_path: Path) -> None:
    """The config is loaded from ``<root>/config.yml`` (the daemon's config path)."""
    loaded_paths: list[Path] = []

    def fake_load(path: Path) -> WiringConfig:
        """Record the config path the loader was asked for."""
        loaded_paths.append(path)
        return _config()

    poll_once(
        root=tmp_path,
        load_config=fake_load,
        run_tick=lambda _c, _s: (_result(), PersistedState()),
    )

    assert loaded_paths == [tmp_path / CONFIG_FILENAME]


def test_render_poll_summarises_result() -> None:
    """``render_poll`` produces a one-line summary of the tick result."""
    rendered = render_poll(_result())

    assert "snapshot=True" in rendered
    assert "actions=2" in rendered
    assert "reaped=1" in rendered
    assert "errors=0" in rendered
