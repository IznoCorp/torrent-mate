"""Tests for the bridge board-provision shell (dry-run diff + apply).

The shell takes an already-resolved ``project_id`` + a fallback option list (the
HTTP layer resolves the registry — ``app`` may not import ``cli``); it reads the
board's current options via the seeder's optional ``status_options`` probe and
diffs them against the desired columns.
"""

from typing import cast

from kanbanmate.app.board_provision import ProvisionResult, provision_board
from kanbanmate.ports.board import Seeder


class _FakeSeeder:
    """A Seeder exposing status_options + ensure_columns, recording calls."""

    def __init__(self, options: dict[str, str]) -> None:
        self._options = dict(options)
        self.ensure_calls: list[list[str]] = []

    def status_options(self, project_id: str) -> dict[str, str]:
        return dict(self._options)

    def ensure_columns(self, project_id: str, columns: list[str]) -> dict[str, str]:
        self.ensure_calls.append(list(columns))
        # Simulate GitHub returning the requested columns mapped to ids.
        return {c: self._options.get(c, f"OPT_{c}") for c in columns}


class _BareSeeder:
    """A Seeder WITHOUT a status_options probe (forces the fallback path)."""

    def __init__(self) -> None:
        self.ensure_calls: list[list[str]] = []

    def ensure_columns(self, project_id: str, columns: list[str]) -> dict[str, str]:
        self.ensure_calls.append(list(columns))
        return {c: f"OPT_{c}" for c in columns}


def test_dry_run_computes_diff_without_mutating() -> None:
    seeder = _FakeSeeder({"Backlog": "o1", "Done": "o2"})
    result = provision_board(
        project_id="PVT_x",
        desired_columns=["Backlog", "Spec", "Done"],
        dry_run=True,
        seeder=cast(Seeder, seeder),
    )
    assert isinstance(result, ProvisionResult)
    assert result.applied is False
    assert any(c.kind == "add" and c.column == "Spec" for c in result.diff.changes)
    assert seeder.ensure_calls == []  # NO mutation on dry-run
    assert result.option_map == {}


def test_apply_calls_ensure_columns_in_desired_order() -> None:
    seeder = _FakeSeeder({"Backlog": "o1", "Done": "o2"})
    result = provision_board(
        project_id="PVT_x",
        desired_columns=["Backlog", "Spec", "Done"],
        dry_run=False,
        seeder=cast(Seeder, seeder),
    )
    assert result.applied is True
    assert seeder.ensure_calls == [["Backlog", "Spec", "Done"]]
    assert result.option_map == {"Backlog": "o1", "Spec": "OPT_Spec", "Done": "o2"}


def test_fallback_options_used_when_no_probe() -> None:
    # A seeder lacking status_options falls back to the caller-supplied option list.
    seeder = _BareSeeder()
    result = provision_board(
        project_id="PVT_x",
        desired_columns=["Backlog", "Spec"],
        fallback_options=["Backlog"],
        dry_run=True,
        seeder=cast(Seeder, seeder),
    )
    assert any(c.kind == "add" and c.column == "Spec" for c in result.diff.changes)
    assert seeder.ensure_calls == []
