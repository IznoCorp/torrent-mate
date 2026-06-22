"""Tests for core/pm2_allowlist (bosun §5.1)."""

from __future__ import annotations

import pytest
from kanbanmate.core.pm2_allowlist import (
    PM2_ALLOWLIST,
    UI_APP_NAMES,
    validate_daemon_action,
)

NON_UI = sorted(PM2_ALLOWLIST - UI_APP_NAMES)  # ["kanban-km", "kanban-km-serve"]
UI = sorted(UI_APP_NAMES)  # ["kanban-km-config", "kanban-staging-config"]


@pytest.mark.parametrize("app", NON_UI)
@pytest.mark.parametrize("action", ["start", "stop", "restart", "status"])
def test_non_ui_app_all_actions_permitted(app: str, action: str) -> None:
    assert validate_daemon_action(app, action) is None


@pytest.mark.parametrize("app", UI)
def test_ui_app_status_permitted(app: str) -> None:
    assert validate_daemon_action(app, "status") is None


@pytest.mark.parametrize("app", UI)
@pytest.mark.parametrize("action", ["start", "stop", "restart"])
def test_ui_app_standalone_mutation_refused(app: str, action: str) -> None:
    reason = validate_daemon_action(app, action)
    assert reason is not None and "refused" in reason


def test_out_of_allowlist_refused() -> None:
    assert validate_daemon_action("kanban-autodeploy", "restart") is not None
    assert validate_daemon_action("rm-rf", "start") is not None


def test_unknown_action_refused() -> None:
    assert validate_daemon_action("kanban-km", "destroy") is not None
