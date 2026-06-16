"""Tests for the ``kanban-progress`` agent helper (:mod:`kanbanmate.bin.kanban_progress`).

Three surfaces (DESIGN §8.1): auto-stage resolution from persisted ``TicketState.stage``
(PoC parity), ``--stage <key>`` explicit override, and a free-form timestamped note as the
genuine no-stage fallback. A fake client records calls so no test touches the network. Usage
errors exit ``2``; wiring failures exit ``1`` (never a crash).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from kanbanmate.adapters.github.types import CommentRef
from kanbanmate.bin import kanban_progress
from kanbanmate.bin.kanban_progress import _timestamped, append_to_stage, main
from kanbanmate.core.stage_comment import marker
from kanbanmate.ports.store import TicketState, TicketStatus


class FakeClient:
    """A GitHub client double recording every comment-path call."""

    def __init__(self, comments: list[CommentRef] | None = None) -> None:
        """Seed the comment list and initialise an empty call log."""
        self._comments = comments or []
        self.calls: list[tuple[Any, ...]] = []

    def list_issue_comments(self, issue: int) -> list[CommentRef]:
        """Record the list call and return the seeded comments."""
        self.calls.append(("list", issue))
        return self._comments

    def update_comment(self, comment_id: int, body: str) -> None:
        """Record an in-place edit (the EDIT path)."""
        self.calls.append(("update", comment_id, body))

    def comment(self, issue: int, body: str) -> None:
        """Record a fresh create (the CREATE / append path)."""
        self.calls.append(("create", issue, body))


class FakeStore:
    """A store double whose ``load`` returns the configured :class:`TicketState` (or ``None``)."""

    def __init__(self, state: TicketState | None) -> None:
        self._state = state

    def load(self, issue: int) -> TicketState | None:
        return self._state


@dataclass(frozen=True)
class _FakeEntry:
    """A minimal stand-in for :class:`~kanbanmate.cli.init.ProjectEntry`."""

    repo: str = "IznoCorp/demo"
    project_id: str = "PVT_PROJECT"
    clone: str = "/tmp/clone"
    status_field_node_id: str = "PVTSSF"
    option_map: dict[str, str] = field(default_factory=dict)


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    client: FakeClient,
    *,
    store_state: TicketState | None = None,
) -> FakeStore:
    """Patch token/registry/client/store + freeze time so ``main`` uses the fakes.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        client: The fake GitHub client.
        store_state: The :class:`TicketState` the fake store's ``load`` returns for
            any issue. ``None`` (default) means no persisted state → free-form fallback.
    """
    store = FakeStore(store_state)
    monkeypatch.setattr(kanban_progress, "_resolve_entry_token", lambda entry: "tok")
    monkeypatch.setattr(kanban_progress, "_resolve_entry", lambda: _FakeEntry())
    monkeypatch.setattr(kanban_progress, "GithubClient", lambda *a, **k: client)
    monkeypatch.setattr(kanban_progress, "FsStateStore", lambda *a, **k: store)
    # String-target form avoids reaching through the module's re-exported ``time``
    # attribute (which mypy treats as not explicitly exported).
    monkeypatch.setattr("kanbanmate.bin.kanban_progress.time.time", lambda: 0.0)
    return store


def test_timestamped_prefixes_a_list_item() -> None:
    """A progress line is rendered as a timestamped markdown list item."""
    assert _timestamped("done thing", 0.0) == "- 1970-01-01 00:00:00Z done thing"


def test_free_form_note_posts_single_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``--stage`` AND no persisted stage → free-form timestamped note (genuine fallback)."""
    client = FakeClient([])
    _wire(monkeypatch, client, store_state=None)

    code = main(["7", "made", "progress"])

    assert code == 0
    assert client.calls == [("create", 7, "- 1970-01-01 00:00:00Z made progress")]


def test_stage_creates_sticky_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--stage`` with no existing sticky creates one carrying the marker + line."""
    client = FakeClient([])
    _wire(monkeypatch, client)

    code = main(["7", "step", "one", "--stage", "Implement"])

    assert code == 0
    # A single list (lookup) then create (the sticky did not exist) — no redundant re-list.
    assert client.calls[0] == ("list", 7)
    method, issue, body = client.calls[1]
    assert method == "create"
    assert issue == 7
    # The created two-zone sticky carries the §8.1 marker, a minimal running header, and
    # the appended line stamped under the **Progress** body zone.
    assert body.startswith(marker("Implement"))
    assert "### 🟡 Implement — in progress" in body
    assert "**Progress**" in body
    assert "step one" in body
    assert not any(call[0] == "update" for call in client.calls)


def test_append_to_stage_appends_under_existing_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """``append_to_stage`` keeps the prior body and adds the new line under it (edit in place)."""
    existing = CommentRef(
        comment_id=42,
        body=(
            f"{marker('Implement')}\n### 🟡 Implement — in progress\n\n"
            "**Progress**\n- 20:49 — earlier line"
        ),
    )
    client = FakeClient([existing])

    append_to_stage(client, issue=7, stage="Implement", line="newer line", now=0.0)  # type: ignore[arg-type]

    # list then update (edit in place — no fresh create).
    assert client.calls[0] == ("list", 7)
    method, comment_id, body = client.calls[1]
    assert method == "update"
    assert comment_id == 42
    # The prior progress line is preserved and the producer header kept; the new stamped
    # line lands under the same **Progress** zone.
    assert "### 🟡 Implement — in progress" in body
    assert "- 20:49 — earlier line" in body
    assert "newer line" in body
    assert not any(call[0] == "create" for call in client.calls)


def test_missing_line_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An issue with no progress line is a usage error (exit 2)."""
    client = FakeClient([])
    _wire(monkeypatch, client)

    assert main(["7"]) == 2
    assert client.calls == []


def test_stage_without_value_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--stage`` with no following key is a usage error (exit 2)."""
    client = FakeClient([])
    _wire(monkeypatch, client)

    assert main(["7", "line", "--stage"]) == 2
    assert client.calls == []


def test_auto_stage_resolves_from_persisted_ticket_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``--stage`` but persisted ``TicketState.stage`` → auto-resolve and append to sticky.

    This is the PoC parity contract: the agent never needed to pass a stage; the engine
    resolves it from the launch column recorded per DESIGN §8.1.d.
    """
    client = FakeClient([])
    persisted = TicketState(
        issue_number=7,
        item_id="PVTI_ITEM",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="Implement",
    )
    _wire(monkeypatch, client, store_state=persisted)

    code = main(["7", "auto", "resolved"])

    assert code == 0
    # Auto-resolved stage → list + create (sticky did not exist).
    assert client.calls[0] == ("list", 7)
    method, issue, body = client.calls[1]
    assert method == "create"
    assert issue == 7
    # The created sticky carries the §8.1 marker for the AUTO-RESOLVED stage.
    assert body.startswith(marker("Implement"))
    assert "auto resolved" in body


def test_explicit_stage_overrides_persisted_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--stage <key>`` takes precedence over the persisted ``TicketState.stage``."""
    client = FakeClient([])
    persisted = TicketState(
        issue_number=7,
        item_id="PVTI_ITEM",
        session_id="ticket-7",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
        stage="Design",  # persisted stage (would be auto-resolved without --stage)
    )
    _wire(monkeypatch, client, store_state=persisted)

    code = main(["7", "explicit", "stage", "--stage", "Implement"])

    assert code == 0
    # The EXPLICIT --stage wins over the persisted stage.
    assert client.calls[0] == ("list", 7)
    _, _, body = client.calls[1]
    assert body.startswith(marker("Implement"))  # NOT "Design"
    assert "explicit stage" in body


def test_wiring_failure_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry/token failure is caught and reported (exit 1), never a traceback."""

    def _boom() -> _FakeEntry:
        raise RuntimeError("no registered project")

    monkeypatch.setattr(kanban_progress, "_resolve_entry_token", lambda entry: "tok")
    monkeypatch.setattr(kanban_progress, "_resolve_entry", _boom)

    assert main(["7", "line"]) == 1
