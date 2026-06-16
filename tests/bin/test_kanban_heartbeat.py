"""Tests for the ``kanban-heartbeat`` liveness hook (:mod:`kanbanmate.bin.kanban_heartbeat`).

These tests pin the three hard contracts of DESIGN §8.3 (PoC #67):

* **Cold-start guard** — a missing or non-int ``argv`` short-circuits to ``exit 0`` *without*
  touching the store (the engine import is never paid for a malformed call).
* **Always exits 0** — a valid issue refreshes the heartbeat and returns ``0``; an exception
  raised inside the store is swallowed and the hook STILL returns ``0`` (never raises, never
  emits exit 2, which would block the agent's tool use).
* **No-resurrection reuse** — the shim only forwards ``touch_heartbeat``; the no-op-when-absent
  semantic lives in the store adapter (tested there) and is exercised here only indirectly.

The store is patched at its import site inside ``main`` (the import is local to the valid-issue
branch), so the cold-start tests can assert the constructor was never even called.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kanbanmate.bin import kanban_heartbeat


def test_missing_arg_exits_zero_without_store_call() -> None:
    """An arg-less invocation short-circuits to exit 0 and never builds the store."""
    with patch("kanbanmate.adapters.store.fs_store.FsStateStore") as store_cls:
        rc = kanban_heartbeat.main([])

    assert rc == 0
    store_cls.assert_not_called()  # cold-start guard: no engine work for a malformed call


def test_non_int_arg_exits_zero_without_store_call() -> None:
    """A non-integer issue arg short-circuits to exit 0 and never builds the store."""
    with patch("kanbanmate.adapters.store.fs_store.FsStateStore") as store_cls:
        rc = kanban_heartbeat.main(["not-a-number"])

    assert rc == 0
    store_cls.assert_not_called()


def test_good_arg_touches_heartbeat_and_exits_zero() -> None:
    """A valid issue refreshes the heartbeat via the store and returns 0."""
    store = MagicMock()
    with (
        patch("kanbanmate.adapters.store.fs_store.FsStateStore", return_value=store),
        patch("kanbanmate.bin.kanban_heartbeat.time.time", return_value=1234.5),
    ):
        rc = kanban_heartbeat.main(["7"])

    assert rc == 0
    store.touch_heartbeat.assert_called_once_with(7, 1234.5)


def test_store_exception_is_swallowed_and_exits_zero() -> None:
    """An exception raised inside the store is swallowed — the hook STILL exits 0 (never blocks)."""
    store = MagicMock()
    store.touch_heartbeat.side_effect = RuntimeError("filesystem hiccup")
    with patch("kanbanmate.adapters.store.fs_store.FsStateStore", return_value=store):
        rc = kanban_heartbeat.main(["7"])

    # The contract: exit 0 ALWAYS — exit 2 would block the agent's tool use (DESIGN §8.3).
    assert rc == 0
    store.touch_heartbeat.assert_called_once()


def test_store_construction_failure_is_swallowed_and_exits_zero() -> None:
    """A failure building the store (e.g. broken engine) is swallowed — still exit 0."""
    with patch(
        "kanbanmate.adapters.store.fs_store.FsStateStore",
        side_effect=OSError("cannot create ~/.kanban"),
    ):
        rc = kanban_heartbeat.main(["7"])

    assert rc == 0


# ---------------------------------------------------------------------------
# KANBAN_ROOT resolution (#1 — the 4th root-unaware helper, mirroring kanban-done's tests).
# These exercise the REAL store (no FsStateStore patch) so they prove the heartbeat lands under
# the resolved root, the root cause of the km-agent "never_refreshed" symptom.
# ---------------------------------------------------------------------------


def _seed_running_state(root: Path, issue: int) -> None:
    """Persist a RUNNING TicketState for ``issue`` under ``root`` (touch_heartbeat is no-op when absent)."""
    from kanbanmate.adapters.store.fs_store import FsStateStore
    from kanbanmate.ports.store import TicketState, TicketStatus

    FsStateStore(root=root).save(
        TicketState(
            issue_number=issue,
            item_id="PVTI_node",
            session_id="sess-abc",
            status=TicketStatus.RUNNING,
            heartbeat=1000.0,
            stage="Implement",
            profile="docs",
            mode="auto",
            started=900.0,
            worktree="/tmp/wt/ticket-7",
        )
    )


def test_heartbeat_lands_under_kanban_root_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With KANBAN_ROOT set the heartbeat refresh lands under THAT root, not ~/.kanban (#1)."""
    from kanbanmate.adapters.store.fs_store import FsStateStore

    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    _seed_running_state(tmp_path, 7)

    with patch("kanbanmate.bin.kanban_heartbeat.time.time", return_value=2000.0):
        rc = kanban_heartbeat.main(["7"])

    assert rc == 0
    # The refresh advanced the heartbeat on the state UNDER tmp_path (the env root).
    refreshed = FsStateStore(root=tmp_path).load(7)
    assert refreshed is not None
    assert refreshed.heartbeat == 2000.0


def test_heartbeat_falls_back_to_home_kanban_when_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With KANBAN_ROOT UNSET the heartbeat resolves the ``~/.kanban`` default (HOME-patched, #1).

    The state is seeded under ``$HOME/.kanban`` and the env root is left unset; the refresh must
    land there (proving the fallback is real), NOT under tmp_path.
    """
    from kanbanmate.adapters.store.fs_store import FsStateStore

    monkeypatch.delenv("KANBAN_ROOT", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    home_root = fake_home / ".kanban"
    _seed_running_state(home_root, 7)

    with patch("kanbanmate.bin.kanban_heartbeat.time.time", return_value=2000.0):
        rc = kanban_heartbeat.main(["7"])

    assert rc == 0
    refreshed = FsStateStore(root=home_root).load(7)
    assert refreshed is not None
    assert refreshed.heartbeat == 2000.0
    # And nothing was written under tmp_path itself (the env root was unset).
    assert not (tmp_path / "state" / "7.json").exists()
