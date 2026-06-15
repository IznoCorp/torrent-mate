"""Tests for the ``kanban-update-body`` agent helper (:mod:`kanbanmate.bin.kanban_update_body`).

Covers the §29.1 contract: PINNED to the launched issue (refuses a mismatch), marker-preserving
``--set-field``, the ``--append-section`` stdin path, and the post-write body↔title ``[CODE]``
coherence gate (a mismatch writes NOTHING). A fake client records the body patch so no test touches
the network; the registry/token/pin are patched so nothing is read off a real clone.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pytest

from kanbanmate.adapters.github.types import IssueRef
from kanbanmate.bin import kanban_update_body
from kanbanmate.bin.kanban_update_body import main


class FakeClient:
    """A board-client double: returns a canned :class:`IssueRef` and records the body patch."""

    def __init__(self, issue: IssueRef) -> None:
        """Store the canned issue and an empty patch log."""
        self._issue = issue
        self.patches: list[tuple[str, str]] = []

    def fetch_issue(self, issue_number: int) -> IssueRef:
        """Return the canned issue (independent of ``issue_number``)."""
        return self._issue

    def update_issue_body(self, issue_node_id: str, body: str) -> None:
        """Record the body patch so a test can assert the final body."""
        self.patches.append((issue_node_id, body))


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
    pinned: int | None = None,
    stdin: str = "",
) -> None:
    """Patch token/registry/client/pin/stdin so ``main`` runs offline.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        client: The fake client every ``GithubClient(...)`` call yields.
        pinned: When set, ``check_pin`` behaves as if the worktree is pinned to this issue; when
            ``None``, the worktree is unpinned (operator use).
        stdin: The text ``--append-section`` reads from stdin.
    """
    monkeypatch.setattr(kanban_update_body, "load_token", lambda: "tok")
    monkeypatch.setattr(kanban_update_body, "_resolve_entry", lambda: _FakeEntry())
    monkeypatch.setattr(kanban_update_body, "GithubClient", lambda *a, **k: client)

    def _check_pin(issue: int) -> str | None:
        if pinned is not None and pinned != issue:
            return f"refusing to act on #{issue}: this worktree is PINNED to #{pinned}"
        return None

    monkeypatch.setattr(kanban_update_body, "check_pin", _check_pin)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))


def _issue(body: str = "Desc\n\n**roadmap**: A1", title: str = "[A1] Feature") -> IssueRef:
    """Return a canned :class:`IssueRef` carrying ``body`` + ``title``."""
    return IssueRef(node_id="NODE_7", number=7, title=title, body=body)


# ---------------------------------------------------------------------------
# Pinning (R1, §29.1)
# ---------------------------------------------------------------------------


def test_pin_match_proceeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pinned issue matching the argument proceeds and patches the body."""
    client = FakeClient(_issue())
    _wire(monkeypatch, client, pinned=7)
    assert main(["7", "--set-field", "design", "docs/d.md"]) == 0
    assert len(client.patches) == 1


def test_pin_mismatch_refuses_no_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pinned worktree refuses a DIFFERENT issue and writes nothing (exit 1)."""
    client = FakeClient(_issue())
    _wire(monkeypatch, client, pinned=7)
    assert main(["9", "--set-field", "design", "docs/d.md"]) == 1
    assert client.patches == []


def test_unpinned_proceeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """No pin file (operator use) → any issue proceeds."""
    client = FakeClient(_issue())
    _wire(monkeypatch, client, pinned=None)
    assert main(["123", "--set-field", "codename", "x"]) == 0


# ---------------------------------------------------------------------------
# --set-field: marker preservation
# ---------------------------------------------------------------------------


def test_set_field_preserves_other_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--set-field design`` rewrites design but preserves the ``**roadmap**`` marker."""
    client = FakeClient(_issue(body="Desc\n\n**roadmap**: A1\n\n**design**: old.md"))
    _wire(monkeypatch, client, pinned=7)
    assert main(["7", "--set-field", "design", "new.md"]) == 0
    _node, body = client.patches[0]
    assert "**design**: new.md" in body
    assert "**roadmap**: A1" in body
    assert "old.md" not in body


# ---------------------------------------------------------------------------
# --append-section: the brainstorm APPEND path (stdin)
# ---------------------------------------------------------------------------


def test_append_section_reads_stdin_and_preserves_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--append-section`` appends stdin text under a heading, preserving the seeded body."""
    client = FakeClient(_issue(body="Original description\n\n**roadmap**: A1"))
    _wire(monkeypatch, client, pinned=7, stdin="Requirements:\n- one")
    assert main(["7", "--append-section", "## Brainstorm"]) == 0
    _node, body = client.patches[0]
    assert "Original description" in body  # never overwritten
    assert "## Brainstorm" in body
    assert "Requirements:" in body
    assert "**roadmap**: A1" in body


# ---------------------------------------------------------------------------
# Post-write coherence gate
# ---------------------------------------------------------------------------


def test_coherence_mismatch_refuses_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting a ``**roadmap**`` that disagrees with the title ``[CODE]`` writes nothing (exit 1)."""
    client = FakeClient(_issue(body="Desc", title="[A1] Feature"))
    _wire(monkeypatch, client, pinned=7)
    # Try to set roadmap to B2 while the title is [A1] → incoherent → refused.
    assert main(["7", "--set-field", "roadmap", "B2"]) == 1
    assert client.patches == []


def test_coherence_match_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting ``**roadmap**`` to the title's own ``[CODE]`` is coherent → writes."""
    client = FakeClient(_issue(body="Desc", title="[A1] Feature"))
    _wire(monkeypatch, client, pinned=7)
    assert main(["7", "--set-field", "roadmap", "A1"]) == 0
    _node, body = client.patches[0]
    assert "**roadmap**: A1" in body


# ---------------------------------------------------------------------------
# Argument + wiring failure handling
# ---------------------------------------------------------------------------


def test_no_mode_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither --set-field nor --append-section is a usage error (argparse, exit 2)."""
    client = FakeClient(_issue())
    _wire(monkeypatch, client, pinned=7)
    assert main(["7"]) == 2


def test_wiring_failure_exits_one_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry/token failure is caught and reported (exit 1), never a traceback."""
    client = FakeClient(_issue())
    _wire(monkeypatch, client, pinned=7)

    def _boom() -> _FakeEntry:
        raise RuntimeError("no registered project")

    monkeypatch.setattr(kanban_update_body, "_resolve_entry", _boom)
    assert main(["7", "--set-field", "codename", "x"]) == 1


def test_empty_node_id_refuses_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """A resolved issue with an empty node id refuses the write (exit 1)."""
    client = FakeClient(IssueRef(node_id="", number=7, title="[A1] F", body="Desc"))
    _wire(monkeypatch, client, pinned=7)
    assert main(["7", "--set-field", "codename", "x"]) == 1
    assert client.patches == []
