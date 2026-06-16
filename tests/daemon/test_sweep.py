"""Tests for the per-project daemon sweep (ingress-multiproject §3.1 / §9).

Covers: each enabled project gets its own tick + per-project ``PersistedState`` baseline +
per-project heartbeat; a failing project's circuit-breaker does NOT trip a healthy sibling; the
daemon-level rollup aggregates correctly; and the per-project heartbeat marker is written.

``run_one_tick`` is patched on the sweep module (the sweep imports it ``from app.wiring``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kanbanmate.app.tick import PersistedState, TickResult
from kanbanmate.app.wiring import WiringConfig
from kanbanmate.daemon import sweep as sweep_mod
from kanbanmate.daemon.sweep import ProjectSweepState, sweep_projects


def _wiring(pid: str, *, repo: str = "o/r", ingress: str = "polling") -> WiringConfig:
    return WiringConfig(
        token="t",
        project_id=pid,
        repo=repo,
        clone_dir="/c",
        columns_yaml="columns: []\n",
        kanban_root="/root",
        ingress=ingress,
        multi_project=True,
    )


def _tick(**over: object) -> TickResult:
    base: dict[str, object] = {
        "probe_token": "x",
        "snapshot_taken": False,
        "actions_executed": 0,
        "reaped": 0,
        "errors": 0,
    }
    base.update(over)
    return TickResult(**base)  # type: ignore[arg-type]


def test_each_project_ticks_with_own_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two projects each get their own run_one_tick call + per-project persisted baseline."""
    seen: list[tuple[str, PersistedState]] = []

    def _mock(wiring: WiringConfig, state: PersistedState) -> tuple[TickResult, PersistedState]:
        seen.append((wiring.project_id, state))
        # Return a NEW baseline carrying this project's id so the next sweep threads it back.
        return _tick(snapshot_taken=True), PersistedState(columns_by_item={wiring.project_id: "X"})

    monkeypatch.setattr(sweep_mod, "run_one_tick", _mock)
    state_by: dict[str, ProjectSweepState] = {}
    wirings = [_wiring("PVT_A"), _wiring("PVT_B")]

    result = sweep_projects(wirings, state_by, kanban_root=tmp_path, now=100.0)

    assert result.projects_swept == 2
    assert result.any_snapshot is True
    assert sorted(pid for pid, _ in seen) == ["PVT_A", "PVT_B"]
    # Each project's baseline advanced independently (no cross-contamination).
    assert state_by["PVT_A"].persisted.columns_by_item == {"PVT_A": "X"}
    assert state_by["PVT_B"].persisted.columns_by_item == {"PVT_B": "X"}


def test_failing_project_does_not_trip_healthy_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One project raising bumps ONLY its own failure run; the healthy one stays at zero."""

    def _mock(wiring: WiringConfig, state: PersistedState) -> tuple[TickResult, PersistedState]:
        if wiring.project_id == "PVT_BAD":
            raise RuntimeError("boom")
        return _tick(), state

    monkeypatch.setattr(sweep_mod, "run_one_tick", _mock)
    state_by: dict[str, ProjectSweepState] = {}
    wirings = [_wiring("PVT_BAD"), _wiring("PVT_OK")]

    result = sweep_projects(wirings, state_by, kanban_root=tmp_path, now=100.0)

    assert state_by["PVT_BAD"].consecutive_failures == 1
    assert state_by["PVT_OK"].consecutive_failures == 0
    # The daemon-level rollup carries the WORST run (1) + the captured error for DEGRADED.
    assert result.max_consecutive_failures == 1
    assert isinstance(result.last_error, RuntimeError)
    # #5: the BACK-OFF signal is the BEST (lowest) run — 0 here, because PVT_OK is healthy. So the
    # daemon does NOT back off: the failing PVT_BAD never throttles the healthy PVT_OK's sweep.
    assert result.min_consecutive_failures == 0


def test_all_projects_failing_backoff_signal_is_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#5: when EVERY project is failing, the back-off signal (min) is > 0 so the daemon backs off."""

    def _mock(wiring: WiringConfig, state: PersistedState) -> tuple[TickResult, PersistedState]:
        raise RuntimeError("boom")

    monkeypatch.setattr(sweep_mod, "run_one_tick", _mock)
    # Both projects already mid-failure-run; both raise again this sweep.
    state_by = {
        "PVT_A": ProjectSweepState(consecutive_failures=2),
        "PVT_B": ProjectSweepState(consecutive_failures=4),
    }

    result = sweep_projects(
        [_wiring("PVT_A"), _wiring("PVT_B")], state_by, kanban_root=tmp_path, now=100.0
    )

    # max = worst (5), min = best (3); both > 0 → the daemon backs off (no healthy project).
    assert result.max_consecutive_failures == 5
    assert result.min_consecutive_failures == 3


def test_probe_failure_counts_without_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A returned-but-probe_failed tick bumps the failure run (the dead-token / outage signal)."""

    def _mock(wiring: WiringConfig, state: PersistedState) -> tuple[TickResult, PersistedState]:
        return _tick(probe_failed=True), state

    monkeypatch.setattr(sweep_mod, "run_one_tick", _mock)
    state_by = {"PVT_A": ProjectSweepState(consecutive_failures=2)}

    sweep_projects([_wiring("PVT_A")], state_by, kanban_root=tmp_path, now=100.0)

    assert state_by["PVT_A"].consecutive_failures == 3


def test_clean_tick_snaps_failure_run_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean tick resets the project's failure run to zero (self-recovery)."""
    monkeypatch.setattr(sweep_mod, "run_one_tick", lambda w, s: (_tick(), s))
    state_by = {"PVT_A": ProjectSweepState(consecutive_failures=5)}

    sweep_projects([_wiring("PVT_A")], state_by, kanban_root=tmp_path, now=100.0)

    assert state_by["PVT_A"].consecutive_failures == 0


def test_per_project_heartbeat_marker_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A per-project heartbeat marker lands under projects/heartbeats/<safe(pid)>.heartbeat."""
    monkeypatch.setattr(sweep_mod, "run_one_tick", lambda w, s: (_tick(), s))

    sweep_projects([_wiring("PVT_A")], {}, kanban_root=tmp_path, now=123.0)

    # The marker is keyed by the collision-resistant slug (#6) — assert via safe_project_id.
    from kanbanmate.core.registry_resolve import safe_project_id

    marker = tmp_path / "projects" / "heartbeats" / f"{safe_project_id('PVT_A')}.heartbeat"
    assert marker.exists()
    assert "123" in marker.read_text()
