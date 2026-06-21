"""Tests for the ``kanban board`` sub-app: import + status (anchor §8).

Drives the real Typer ``board_app`` via ``CliRunner``. ``wiring_for_selection`` is patched so no
test touches the registry/network; the store path resolves to ``tmp_path`` (a real
``FsBoardStateStore``) so the store-path fallback chain and the output formatting are exercised for
real. Help/text assertions force a wide terminal (``COLUMNS=200``) so they are width-independent in
CI's narrow non-TTY (the proven ``test_app_mcp`` pattern).
"""

from __future__ import annotations

import json
import pathlib
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board
from kanbanmate.app.wiring import WiringConfig
from kanbanmate.cli.board import board_app
from kanbanmate.core.domain import BoardSnapshot, Ticket

runner = CliRunner()

_MINIMAL_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
    class: inert
  - key: InProgress
    name: In Progress
    class: reactive
"""


def _wc(tmp_path: pathlib.Path) -> WiringConfig:
    """A WiringConfig whose store path resolves to ``tmp_path`` (flat layout)."""
    return WiringConfig(
        token="t",
        project_id="pid",
        repo="o/r",
        clone_dir="/tmp/clone",
        columns_yaml=_MINIMAL_COLUMNS_YAML,
        kanban_root=str(tmp_path),
        state_root=str(tmp_path),
    )


# ---------------------------------------------------------------------------
# kanban board status
# ---------------------------------------------------------------------------


def test_board_status_no_store_message(tmp_path: pathlib.Path) -> None:
    """With no board.json (version 0) the operator gets a clear 'run import first' hint."""
    with patch(
        "kanbanmate.daemon.registry_wiring.wiring_for_selection", return_value=_wc(tmp_path)
    ):
        result = runner.invoke(
            board_app, ["status", "--root", str(tmp_path)], env={"COLUMNS": "200"}
        )
    assert result.exit_code == 0
    assert "No native board store found" in result.stdout


def test_board_status_json_is_width_independent(tmp_path: pathlib.Path) -> None:
    """``board status --json`` emits the parseable store doc (asserted on parsed JSON, not substrings)."""
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=["Backlog", "InProgress"],
        placement={"item1": "Backlog", "item2": "InProgress"},
        order={"Backlog": ["item1"], "InProgress": ["item2"]},
    )
    with patch(
        "kanbanmate.daemon.registry_wiring.wiring_for_selection", return_value=_wc(tmp_path)
    ):
        result = runner.invoke(
            board_app, ["status", "--root", str(tmp_path), "--json"], env={"COLUMNS": "200"}
        )
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["version"] == 1
    assert doc["placement"] == {"item1": "Backlog", "item2": "InProgress"}


def test_board_status_text_counts(tmp_path: pathlib.Path) -> None:
    """The text summary reports the per-column placement counts."""
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=["Backlog", "InProgress"],
        placement={"a": "Backlog", "b": "Backlog", "c": "InProgress"},
        order={"Backlog": ["a", "b"], "InProgress": ["c"]},
    )
    with patch(
        "kanbanmate.daemon.registry_wiring.wiring_for_selection", return_value=_wc(tmp_path)
    ):
        result = runner.invoke(
            board_app, ["status", "--root", str(tmp_path)], env={"COLUMNS": "200"}
        )
    assert result.exit_code == 0
    assert "version=1" in result.stdout
    assert "Backlog: 2" in result.stdout
    assert "InProgress: 1" in result.stdout


def test_board_status_selection_error_exits_nonzero(tmp_path: pathlib.Path) -> None:
    """A project-selection failure exits non-zero with the error on stderr (fail-loud)."""
    with patch(
        "kanbanmate.daemon.registry_wiring.wiring_for_selection",
        side_effect=RuntimeError("no project registered"),
    ):
        result = runner.invoke(
            board_app, ["status", "--root", str(tmp_path)], env={"COLUMNS": "200"}
        )
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# kanban board import
# ---------------------------------------------------------------------------


def _fake_forge() -> MagicMock:
    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(
            Ticket(item_id="a", issue_number=1, title="A", column_key="Backlog", body=""),
            Ticket(item_id="b", issue_number=2, title="B", column_key="InProgress", body=""),
        ),
        fetched_at=0.0,
    )
    return forge


def test_board_import_writes_store(tmp_path: pathlib.Path) -> None:
    """A real import seeds board.json at the resolved store path and reports the summary."""
    with (
        patch("kanbanmate.daemon.registry_wiring.wiring_for_selection", return_value=_wc(tmp_path)),
        patch("kanbanmate.adapters.github.client.GithubClient", return_value=_fake_forge()),
    ):
        result = runner.invoke(
            board_app, ["import", "--root", str(tmp_path)], env={"COLUMNS": "200"}
        )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "board.json").exists()
    doc = FsBoardStateStore(tmp_path).load()
    assert doc["placement"] == {"a": "Backlog", "b": "InProgress"}
    assert "version=1" in result.stdout


def test_board_import_dry_run_does_not_write(tmp_path: pathlib.Path) -> None:
    """``--dry-run`` prints the [DRY RUN] prefix and writes nothing."""
    with (
        patch("kanbanmate.daemon.registry_wiring.wiring_for_selection", return_value=_wc(tmp_path)),
        patch("kanbanmate.adapters.github.client.GithubClient", return_value=_fake_forge()),
    ):
        result = runner.invoke(
            board_app, ["import", "--root", str(tmp_path), "--dry-run"], env={"COLUMNS": "200"}
        )
    assert result.exit_code == 0, result.stdout
    assert "[DRY RUN]" in result.stdout
    assert not (tmp_path / "board.json").exists()
