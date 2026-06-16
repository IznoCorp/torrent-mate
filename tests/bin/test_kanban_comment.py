"""Unit tests for the ``kanban-comment`` agent helper (DESIGN §8.1).

The sticky path was rewired onto the rich two-zone subsystem
(:mod:`kanbanmate.core.stage_comment` + :mod:`kanbanmate.app.stage_signal`); this leaf
now only parses argv, wires the GitHub adapter, and delegates. A fake GitHub client
records ``list_issue_comments`` / ``update_comment`` / ``comment`` calls so no test
touches the network. The tests assert:

- ``--sticky <STEP>`` CREATES a running-header sticky carrying the body when absent;
- ``--sticky <STEP>`` EDITS the located sticky in place (header preserved) when present;
- ``--append`` skips the marker lookup entirely (lists nothing, never edits);
- ``main`` fails cleanly (non-zero, no traceback) on a missing mode or a wiring error.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from kanbanmate.adapters.github.types import CommentRef
from kanbanmate.bin import kanban_comment
from kanbanmate.bin.kanban_comment import main
from kanbanmate.core.stage_comment import marker


class FakeClient:
    """A GitHub client double recording every comment-path call.

    Replays a configured comment list for ``list_issue_comments`` and records the
    ``(method, *args)`` of every create/edit so a test can assert exactly which
    REST path the sticky logic exercised.
    """

    def __init__(self, comments: list[CommentRef] | None = None) -> None:
        """Seed the comment list and initialise an empty call log.

        Args:
            comments: The comments ``list_issue_comments`` should return.
        """
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


# ---------------------------------------------------------------------------
# main(): argv parsing + mode dispatch (fakes injected via monkeypatch)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeEntry:
    """A minimal stand-in for :class:`~kanbanmate.cli.init.ProjectEntry`."""

    repo: str = "IznoCorp/demo"
    project_id: str = "PVT_PROJECT"
    clone: str = "/tmp/clone"
    status_field_node_id: str = "PVTSSF"
    option_map: dict[str, str] = field(default_factory=dict)


def _wire(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> None:
    """Patch token/registry/client construction so ``main`` uses ``client``.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        client: The fake client every ``GithubClient(...)`` call should yield.
    """
    # #4: the helper now resolves the PER-ENTRY token via ``_resolve_entry_token`` (not load_token).
    monkeypatch.setattr(kanban_comment, "_resolve_entry_token", lambda entry: "tok")
    monkeypatch.setattr(kanban_comment, "_resolve_entry", lambda: _FakeEntry())
    monkeypatch.setattr(kanban_comment, "GithubClient", lambda *a, **k: client)


def test_main_sticky_creates_running_header_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--sticky`` lists comments and CREATES a running-header sticky when absent."""
    client = FakeClient([])
    _wire(monkeypatch, client)

    code = main(["7", "kicking", "off", "--sticky", "Design"])

    assert code == 0
    # A single list (lookup) then a create (the sticky did not exist).
    assert [c[0] for c in client.calls] == ["list", "create"]
    assert client.calls[0] == ("list", 7)
    _, issue, body = client.calls[1]
    assert issue == 7
    # The created sticky carries the §8.1 marker, a running 🟡 header, and the body line.
    assert body.startswith(marker("Design"))
    assert "### 🟡 Design — in progress" in body
    assert "kicking off" in body


def test_main_sticky_edits_existing_preserving_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--sticky`` edits the existing marked sticky in place, preserving its header."""
    existing = CommentRef(
        comment_id=99,
        body=f"{marker('Design')}\n### 🟡 Design — in progress\n- session : `abc`",
    )
    client = FakeClient([existing])
    _wire(monkeypatch, client)

    code = main(["--sticky", "Design", "7", "updated"])

    assert code == 0
    assert [c[0] for c in client.calls] == ["list", "update"]
    method, comment_id, body = client.calls[1]
    assert method == "update"
    assert comment_id == 99
    # The producer-owned header is preserved; the new body line is appended.
    assert "### 🟡 Design — in progress" in body
    assert "updated" in body


def test_main_append_skips_marker_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--append`` never lists comments and never edits — it only creates."""
    client = FakeClient([CommentRef(comment_id=5, body=f"{marker('Design')}\nx")])
    _wire(monkeypatch, client)

    code = main(["7", "free", "form", "note", "--append"])

    assert code == 0
    # The free-form body is posted verbatim, with NO marker prefix.
    assert client.calls == [("create", 7, "free form note")]
    assert not any(call[0] == "list" for call in client.calls)
    assert not any(call[0] == "update" for call in client.calls)


def test_main_bare_positional_defaults_to_free_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``kanban-comment <issue> <msg>`` (no flag) posts a free-form comment (PoC parity).

    The bare-positional form is the implicit ``--append`` default: it calls
    ``client.comment`` with no marker lookup and no edit — matching the PoC
    ``kanban-comment`` contract where bare positional was the only form.
    """
    client = FakeClient([])
    _wire(monkeypatch, client)

    code = main(["7", "free", "form", "default"])

    assert code == 0
    # Bare positional → free-form comment, no list/no update (no marker lookup).
    assert client.calls == [("create", 7, "free form default")]
    assert not any(call[0] == "list" for call in client.calls)
    assert not any(call[0] == "update" for call in client.calls)


def test_main_bad_issue_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-integer issue is rejected by argparse (exit 2), not a crash."""
    client = FakeClient([])
    _wire(monkeypatch, client)

    code = main(["notanint", "body", "--append"])

    assert code == 2
    assert client.calls == []


def test_main_wiring_failure_exits_one_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry/token failure is caught and reported (exit 1), never a traceback."""

    def _boom() -> _FakeEntry:
        raise RuntimeError("no registered project")

    monkeypatch.setattr(kanban_comment, "_resolve_entry_token", lambda entry: "tok")
    monkeypatch.setattr(kanban_comment, "_resolve_entry", _boom)

    code = main(["7", "body", "--append"])

    assert code == 1


# ---------------------------------------------------------------------------
# FIX 1 — multi-root registry resolution ($KANBAN_ROOT, km-worktree-helper-root fix)
# ---------------------------------------------------------------------------


def _write_one_project_registry(root: Path) -> None:
    """Write a single-project ``projects.json`` under *root* (the km-root registry)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_PROJECT": {
                    "repo": "IznoCorp/demo",
                    "clone": "/tmp/clone",
                    "project_id": "PVT_PROJECT",
                    "status_field_node_id": "PVTSSF",
                }
            }
        ),
        encoding="utf-8",
    )


def test_resolve_entry_reads_from_kanban_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_resolve_entry`` resolves the registry from ``$KANBAN_ROOT``, not the ~/.kanban default.

    Proves the FIX-1 km-root fix: a one-project registry placed under a tmp ``$KANBAN_ROOT`` is
    found, so a kanban-km daemon's helper acts on its OWN repo, never the hardcoded ~/.kanban.
    """
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    _write_one_project_registry(tmp_path)

    entry = kanban_comment._resolve_entry()

    assert entry.repo == "IznoCorp/demo"
    assert entry.project_id == "PVT_PROJECT"


def test_resolve_entry_empty_kanban_root_raises_naming_that_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An EMPTY ``$KANBAN_ROOT`` registry raises a RuntimeError naming the tmp path.

    The error message naming ``tmp_path`` (not ~/.kanban) proves the helper read the env root —
    the live km-worktree-helper-root bug was that it always read ~/.kanban regardless of the root.
    """
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))  # no projects.json under it → 0 projects

    with pytest.raises(RuntimeError, match=str(tmp_path)):
        kanban_comment._resolve_entry()


def test_resolve_entry_kanban_root_unset_falls_back_to_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ``$KANBAN_ROOT`` unset, the helper falls back to the ``DEFAULT_KANBAN_ROOT`` default.

    ``DEFAULT_KANBAN_ROOT`` (the import-time-frozen ``~/.kanban``) is patched to a tmp dir so the
    fallback resolves under tmp (never the operator's real home); a one-project registry there
    resolves, proving the unset-env fallback is live (the contract `kanban_move`/`done` preserve).
    """
    monkeypatch.delenv("KANBAN_ROOT", raising=False)
    default_root = tmp_path / "default-kanban"
    monkeypatch.setattr("kanbanmate.cli.init.DEFAULT_KANBAN_ROOT", default_root)
    _write_one_project_registry(default_root)

    entry = kanban_comment._resolve_entry()

    assert entry.repo == "IznoCorp/demo"
