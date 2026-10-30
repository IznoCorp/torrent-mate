"""``launch_action``'s refusals before anything is reserved: bad options, a dry run the action lacks."""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.app.errors import AppValidationError
from personalscraper.app.maintenance import service as maintenance_service
from personalscraper.app.maintenance.registry import REGISTRY
from personalscraper.app.maintenance.service import launch_action


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the runner spawn: no process starts, every launch is recorded.

    Args:
        monkeypatch: Pytest's monkeypatch.

    Returns:
        The run uid of every spawn, in order.
    """
    calls: list[str] = []

    def fake_spawn(run_uid: str, action_id: str, options_json: str, dry_run: bool) -> int:
        """Record the launch and answer a fixed pid."""
        calls.append(run_uid)
        return 4242

    monkeypatch.setattr(maintenance_service, "_spawn_runner", fake_spawn)
    return calls


def test_an_option_of_the_wrong_type_is_refused(tmp_path: Path, spawned: list[str]) -> None:
    """A text item id for an integer option: 422, no row reserved, no spawn."""
    (action,) = [a for a in REGISTRY if a.id == "library-rescrape-item"]

    with pytest.raises(AppValidationError):
        launch_action(action, {"item_id": "x"}, db_path=tmp_path / "library.db", data_dir=tmp_path)

    assert spawned == []
    assert not (tmp_path / "library.db").exists()


def test_a_dry_run_of_an_action_without_one_is_refused(tmp_path: Path, spawned: list[str]) -> None:
    """A dry run asked of an action whose ``dry_run`` is ``unsupported``: 422 naming the action."""
    (action,) = [a for a in REGISTRY if a.id == "library-rescrape-item"]
    assert action.dry_run == "unsupported"

    with pytest.raises(AppValidationError, match="library-rescrape-item.*does not support dry-run"):
        launch_action(action, {"item_id": 1}, db_path=tmp_path / "library.db", data_dir=tmp_path, dry_run=True)

    assert spawned == []
