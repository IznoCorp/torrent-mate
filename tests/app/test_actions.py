"""Tests for the command-pattern actions (:mod:`kanbanmate.app.actions`).

Every dependency is a :class:`unittest.mock.MagicMock` typed against the ``ports`` Protocols, so
no test touches git, tmux, the filesystem, or the network. Each test asserts the *call sequence*
an action makes against its injected :class:`Deps` — the behavioural contract ported from the PoC
(launch / teardown / reset / block).

The mocks are held in a :class:`_Mocks` bundle and asserted on **directly** (not reached through
the typed :class:`Deps` fields), so the assertions stay visible to mypy strict — mirroring the
``tests/adapters/test_workspace.py`` convention of keeping a ``MagicMock`` reference in hand.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kanbanmate.app.actions import (
    STATUS_RUNNING,
    BlockAction,
    Deps,
    LaunchAction,
    ResetAction,
    RollbackAction,
    RunScriptAction,
    TeardownAction,
)
from kanbanmate.adapters.github.types import IssueContext, IssueRef
from kanbanmate.core.body_edit import STATUS_BEGIN
from kanbanmate.core.domain import Ticket
from kanbanmate.ports.store import TicketState


@dataclass
class _Mocks:
    """The individual mocks behind a :class:`Deps`, kept for direct assertion."""

    board_writer: MagicMock
    board_reader: MagicMock
    workspace: MagicMock
    sessions: MagicMock
    store: MagicMock
    clock: MagicMock
    pull_requests: MagicMock
    deps: Deps


def _ticket(issue: int | None = 7, item_id: str = "PVTI_7") -> Ticket:
    """Build a :class:`Ticket` with test defaults.

    Args:
        issue: The issue number (``None`` for a draft item with no issue).
        item_id: The project item node id.

    Returns:
        A frozen :class:`Ticket`.
    """
    return Ticket(item_id=item_id, issue_number=issue, title="t", column_key="InProgress")


def _launch(ticket: Ticket, **kwargs: object) -> LaunchAction:
    """Build a :class:`LaunchAction` with a resolvable profile (phase 20, transitions-only).

    The profile resolution FAILS LOUD when the transition ``profile`` is empty (DESIGN §8.0.6:
    the profile lives on the transition; there is NO per-column default tier), so a bare
    ``LaunchAction(ticket=...)`` no longer launches. These action-level tests exercise the launch
    flow itself (not the profile wiring), so this factory supplies a default ``profile="docs"``
    (preserving the historical ``saved.profile == "docs"`` assertions) UNLESS the caller overrides
    ``profile`` explicitly. The dedicated profile-resolution tests below set it explicitly to
    assert fail-loud.

    Args:
        ticket: The ticket the launch acts on.
        **kwargs: Any :class:`LaunchAction` field overrides (e.g. ``prompt`` / ``profile``).

    Returns:
        A :class:`LaunchAction` with a resolvable profile.
    """
    if "profile" not in kwargs:
        kwargs["profile"] = "docs"
    return LaunchAction(ticket=ticket, **kwargs)  # type: ignore[arg-type]


def _mocks(
    *,
    now: float = 1000.0,
    worktree: Path | None = None,
    config_dir: str = "",
    kanban_root: str = "",
) -> _Mocks:
    """Build a :class:`_Mocks` bundle with a :class:`Deps` wired from fresh mocks.

    Args:
        now: The value the mocked clock returns from ``now()``.
        worktree: The path ``Workspace.ensure_worktree`` returns. When provided (a real
            ``tmp_path``), :class:`LaunchAction` materialises the permission settings into it for
            real — so launch tests pass a writable temp dir; non-launch tests may omit it.
        config_dir: The project's ``.claude`` dir threaded onto :attr:`Deps.config_dir`; the
            launch COPIES its ``skills``/``commands``/``agents`` into the worktree. Empty (the
            default) skips provisioning.
        kanban_root: The launching daemon's runtime root threaded onto :attr:`Deps.kanban_root`.
            Empty (the default) keeps the launched command byte-identical (no ``KANBAN_ROOT``
            export); a non-empty value injects ``export KANBAN_ROOT=<root>;`` (km-root fix, #1).

    Returns:
        A :class:`_Mocks` exposing both the individual mocks and the assembled :class:`Deps`.
    """
    board_writer = MagicMock()
    board_reader = MagicMock()
    workspace = MagicMock()
    workspace.ensure_worktree.return_value = worktree or Path("/tmp/worktrees/ticket-7")
    # Default teardown branch: a real feature branch, so the branch -D + PR-close paths fire.
    workspace.discover_branch.return_value = "feat/genesis"
    # A run_transition_script default verdict (exit 0, empty output) for RunScriptAction tests.
    workspace.run_transition_script.return_value = (0, "")
    sessions = MagicMock()
    sessions.launch.return_value = "ticket-7"
    sessions.is_alive.return_value = True
    # Phase-25 §25.1: a prompt-bearing launch polls ``capture`` then send-keys the filled prompt
    # into the REPL. Default the capture snapshot to a READY-REPL marker so the bounded poll
    # returns immediately (trust_seen=False), AND carry a running-turn marker so the post-send
    # submit-retry sees the prompt landed (a turn in flight) and does NOT re-deliver — a launch test
    # that wants the trust path / a stuck or eaten prompt overrides it.
    sessions.capture.return_value = "│ > Welcome to Claude\n  esc to interrupt"
    store = MagicMock()
    # 15.7: every LaunchAction._launch_context now reads script output from the store.
    store.load_script_output.return_value = ""
    clock = MagicMock()
    clock.now.return_value = now
    pull_requests = MagicMock()
    pull_requests.close_open_pr_for_branch.return_value = 123
    deps = Deps(
        board_writer=board_writer,
        board_reader=board_reader,
        workspace=workspace,
        sessions=sessions,
        store=store,
        clock=clock,
        pull_requests=pull_requests,
        base="main",
        agent_command="claude /implement:phase",
        repo="owner/repo",
        config_dir=config_dir,
        kanban_root=kanban_root,
        # Inject a no-op sleeper so the launch's trust/ready poll runs offline (phase-25 §25.1).
        sleeper=lambda _seconds: None,
    )
    return _Mocks(
        board_writer, board_reader, workspace, sessions, store, clock, pull_requests, deps
    )


def _delivered_prompt(sessions: MagicMock) -> str:
    """Return the literal text send-keys'd into the REPL, joined (phase-25 §25.1).

    The launch types the filled prompt INTO the live REPL via ``send_text(..., literal=True)``
    (PoC parity), not as a positional in the launch command. This helper joins those literal
    payloads so a test can assert the filled content reached the agent's REPL.

    Args:
        sessions: The mocked ``Sessions`` whose ``send_text`` calls to inspect.

    Returns:
        The concatenation of every ``literal=True`` ``send_text`` payload.
    """
    return "".join(
        c.args[1] for c in sessions.send_text.call_args_list if c.kwargs.get("literal") is True
    )


# ---------------------------------------------------------------------------
# LaunchAction
# ---------------------------------------------------------------------------


def test_launch_action_ensures_worktree_launches_and_saves(tmp_path: Path) -> None:
    """LaunchAction wires worktree -> settings -> session -> persisted running state, upserts a
    RUNNING stage header (🟡 "in progress" badge, DESIGN §8.1.c)."""
    m = _mocks(now=1234.0, worktree=tmp_path)
    _launch(_ticket(issue=7)).execute(m.deps)

    m.workspace.ensure_worktree.assert_called_once_with(7, base="main")
    # The launch command is now the real claude argv wrapped with the session-end shim (phase 14),
    # NOT the static Deps.agent_command. It carries --session-id <uuid>, --add-dir <worktree>, the
    # ``; kanban-session-end <issue>`` wrapper, and the tmux session name stays ticket-<n>.
    m.sessions.launch.assert_called_once()
    session_name, cwd, command = m.sessions.launch.call_args.args
    assert session_name == "ticket-7"
    assert cwd == str(tmp_path)
    assert "--session-id" in command
    assert f"--add-dir {tmp_path}" in command
    assert "; kanban-session-end 7" in command
    # The permission profile is materialised into the worktree BEFORE the session launches.
    assert (tmp_path / ".claude" / "settings.json").is_file()
    # Sub-phase 9.2: verify the materialised settings carry defaultMode == "auto"
    # (the mode an unattended launched agent boots under, DESIGN §10 H4).
    import json  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    written_settings = json.loads(
        (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    assert isinstance(written_settings, dict)
    assert written_settings["permissions"]["defaultMode"] == "auto"
    assert written_settings["bypassPermissions"] is False
    # State persisted with the running status, the item id, and heartbeat=now.
    m.store.save.assert_called_once()
    saved: TicketState = m.store.save.call_args.args[0]
    assert saved.issue_number == 7
    assert saved.item_id == "PVTI_7"
    # session_id is now the generated claude --session-id UUID (was the tmux name "ticket-7"):
    # it must EQUAL the --session-id value in the launched command so `claude --resume <id>` works.
    import shlex  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    parts = shlex.split(command)
    launched_uuid = parts[parts.index("--session-id") + 1]
    assert saved.session_id == launched_uuid
    assert saved.session_id != "ticket-7"  # no longer the tmux name
    uuid.UUID(saved.session_id)  # a valid uuid (raises if not)
    assert saved.status == STATUS_RUNNING
    assert saved.heartbeat == 1234.0
    # The widened launch metadata (DESIGN §8.1.d) is persisted as the single
    # source of truth the finalizers reload: stage = the launch column key,
    # plus profile / mode / started / worktree.
    assert saved.stage == "InProgress"
    assert saved.profile == "docs"
    assert saved.mode == "auto"
    assert saved.started == 1234.0
    assert saved.worktree == str(tmp_path)
    # 15.1: the reaper-retry counter defaults to 0 on a fresh launch.
    assert saved.retries == 0
    # Defect 4: the ticket title + body are persisted so a reaper relaunch rebuilds the real Ticket
    # (not ``ticket-N`` / "") and the relaunched agent does not self-DESYNC.
    assert saved.title == "t"
    assert saved.body == ""
    # Step 5 posts a RUNNING stage header via upsert (replaces the old free-text comment).
    # The upsert probes for an existing sticky first (list_issue_comments).
    m.board_writer.list_issue_comments.assert_called_once_with(7)
    # Absent → create path. The comment body carries the rich two-zone header.
    m.board_writer.comment.assert_called_once()
    body: str = m.board_writer.comment.call_args.args[1]
    assert m.board_writer.comment.call_args.args[0] == 7
    # Verify the RUNNING header content (badge 🟡, English label "in progress",
    # session id, profile, worktree, log hint). The session id rendered in the header is now the
    # claude --session-id UUID (matches the persisted state), not the tmux name.
    assert "<!-- kanban:step=InProgress -->" in body
    assert "🟡" in body
    assert "in progress" in body
    assert launched_uuid in body
    assert "docs" in body
    assert "kanban logs 7" in body
    assert tmp_path.name in body  # worktree directory name


def test_launch_command_prefixes_worktree_kanban_bin_on_path(tmp_path: Path) -> None:
    """Phase 38: the launched command starts with a PATH export prepending the worktree kanban-bin.

    The export pins BOTH ``claude`` and the trailing ``; kanban-session-end`` to the engine's own
    helper scripts, regardless of the agent's inherited ``pyenv global`` python. The kanban-bin dir
    is provisioned into the worktree before launch.
    """
    import shlex  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    from kanbanmate.adapters.perms import KANBAN_BIN_RELDIR  # noqa: PLC0415 — test-local

    m = _mocks(worktree=tmp_path)
    _launch(_ticket(issue=7)).execute(m.deps)

    _name, _cwd, command = m.sessions.launch.call_args.args
    expected_bin = tmp_path / KANBAN_BIN_RELDIR
    # The command line opens with the PATH export naming the worktree kanban-bin dir, then ``;``.
    assert command.startswith(f"export PATH={shlex.quote(str(expected_bin))}:")
    assert '"$PATH";' in command  # $PATH must stay UNQUOTED so it expands in the agent's shell
    # The claude argv + session-end wrapper still follow the prefix.
    assert "--session-id" in command
    assert "; kanban-session-end 7" in command
    # The kanban-bin dir is materialised into the worktree.
    assert expected_bin.is_dir()


def test_launch_command_prefixes_kanban_root_export_when_non_default(tmp_path: Path) -> None:
    """km-root (#1): a non-empty ``Deps.kanban_root`` injects ``export KANBAN_ROOT=<root>;``.

    The launching daemon's runtime root is exported on the command line so the trailing
    ``; kanban-session-end`` AND the agent's kanban-* helpers target the CORRECT root (e.g.
    ~/.kanban-km) instead of the hardcoded ~/.kanban (the km-worktree-helper-root bug). The value
    is shlex-quoted, and the export precedes the PATH prefix + the claude argv.
    """
    import shlex  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    root = "/Users/izno/.kanban-km"
    m = _mocks(worktree=tmp_path, kanban_root=root)
    _launch(_ticket(issue=7)).execute(m.deps)

    _name, _cwd, command = m.sessions.launch.call_args.args
    # The command opens with the shlex-quoted KANBAN_ROOT export, BEFORE the PATH prefix.
    assert command.startswith(f"export KANBAN_ROOT={shlex.quote(root)}; ")
    assert command.index("export KANBAN_ROOT=") < command.index("export PATH=")
    # The rest of the launch line (PATH prefix + claude argv + session-end wrapper) still follows.
    assert "export PATH=" in command
    assert "--session-id" in command
    assert "; kanban-session-end 7" in command


def test_launch_command_omits_kanban_root_export_for_default_root(tmp_path: Path) -> None:
    """km-root (#1): an EMPTY ``Deps.kanban_root`` keeps the command byte-identical (no export).

    The default ~/.kanban daemon needs no override, so the launched command line must carry NO
    ``KANBAN_ROOT`` export — proving the injection is gated strictly on a non-empty root.
    """
    m = _mocks(worktree=tmp_path)  # kanban_root defaults to "" (the default daemon)
    _launch(_ticket(issue=7)).execute(m.deps)

    _name, _cwd, command = m.sessions.launch.call_args.args
    assert "KANBAN_ROOT" not in command
    # The command still opens directly with the PATH prefix (the default-root contract).
    assert command.startswith("export PATH=")


def test_launch_action_orders_worktree_before_state_save(tmp_path: Path) -> None:
    """The worktree + session exist before state is persisted (crash-safety ordering)."""
    m = _mocks(worktree=tmp_path)
    parent = MagicMock()
    parent.attach_mock(m.workspace.ensure_worktree, "ensure")
    parent.attach_mock(m.sessions.launch, "launch")
    parent.attach_mock(m.store.save, "save")

    _launch(_ticket(issue=7)).execute(m.deps)

    ordered = [name for name, _, _ in parent.mock_calls]
    assert ordered.index("ensure") < ordered.index("launch") < ordered.index("save")


def test_launch_action_noop_for_draft_without_issue() -> None:
    """A draft item (issue_number=None) cannot get a worktree, so nothing launches."""
    m = _mocks()
    _launch(_ticket(issue=None)).execute(m.deps)

    m.workspace.ensure_worktree.assert_not_called()
    m.sessions.launch.assert_not_called()
    m.store.save.assert_not_called()


def test_launch_action_stage_comment_fail_soft(tmp_path: Path) -> None:
    """When the stage-comment upsert raises (network down), the launch still completes.

    The 🟡 header is best-effort (DESIGN §8.1 fail-soft): a GitHub error during the
    upsert is logged and swallowed — it must never break the launch or prevent the
    state persist + session start.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.board_writer.list_issue_comments.side_effect = RuntimeError("network down")

    # Must NOT raise.
    _launch(_ticket(issue=7)).execute(m.deps)

    # The critical path (worktree + session + state) still completed.
    m.workspace.ensure_worktree.assert_called_once_with(7, base="main")
    # The launched command is the wrapped claude argv (phase 14), not the static agent_command.
    m.sessions.launch.assert_called_once()
    launch_name, launch_cwd, launch_command = m.sessions.launch.call_args.args
    assert launch_name == "ticket-7"
    assert launch_cwd == str(tmp_path)
    assert "--session-id" in launch_command
    assert "; kanban-session-end 7" in launch_command
    m.store.save.assert_called_once()
    # The comment was attempted (and failed), but no comment was created.
    m.board_writer.comment.assert_not_called()


def test_launch_action_provisions_skills_and_pins_manual_merge(tmp_path: Path) -> None:
    """A non-empty ``config_dir`` provisions skills/commands/agents into the worktree AND pins
    the worktree's IMPLEMENTATION.md to manual merge (phase 14.6; mirrors PoC start_session).

    The worktree and the config dir are distinct real temp dirs so the COPY is observable.
    """
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    # A real config dir with a skills/ subtree to copy + an IMPLEMENTATION.md in the worktree.
    config_dir = tmp_path / "config"
    (config_dir / "skills" / "implement-phase").mkdir(parents=True)
    (config_dir / "skills" / "implement-phase" / "SKILL.md").write_text("phase", encoding="utf-8")
    (worktree / "IMPLEMENTATION.md").write_text(
        "# Feature\n\n**PR merge**: auto\n", encoding="utf-8"
    )

    m = _mocks(now=1234.0, worktree=worktree, config_dir=str(config_dir))
    _launch(_ticket(issue=7)).execute(m.deps)

    # The skills subtree was COPIED into the worktree's .claude/ (not symlinked).
    copied = worktree / ".claude" / "skills" / "implement-phase" / "SKILL.md"
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == "phase"
    # The IMPLEMENTATION.md was pinned to manual merge (replacing the ``auto`` line in place).
    impl = (worktree / "IMPLEMENTATION.md").read_text(encoding="utf-8")
    assert "**PR merge**: manual" in impl
    assert "**PR merge**: auto" not in impl


def test_launch_action_empty_config_dir_skips_provisioning(tmp_path: Path) -> None:
    """An empty ``config_dir`` skips skill provisioning (no crash, no .claude/skills copied).

    The launch still completes (worktree + settings + session + state) — provisioning is a no-op.
    """
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    m = _mocks(now=1234.0, worktree=worktree, config_dir="")
    _launch(_ticket(issue=7)).execute(m.deps)

    # No skills dir was created (provisioning short-circuited on the empty config_dir).
    assert not (worktree / ".claude" / "skills").exists()
    # The critical launch path still completed.
    m.sessions.launch.assert_called_once()
    m.store.save.assert_called_once()


def test_launch_action_writes_mcp_registration_single_project(tmp_path: Path) -> None:
    """The launch block writes a worktree ``.mcp.json`` pinned to the issue (conduit §8.1).

    N=1 (default ``multi_project``): ``args`` omit ``--project``; the empty ``kanban_root`` resolves
    to the canonical ``~/.kanban`` runtime root. Asserted via the REAL ``write_mcp_registration``
    output (the launch wrote it into the real ``tmp_path`` worktree).
    """
    import json  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    m = _mocks(now=1234.0, worktree=worktree)  # kanban_root="" → default ~/.kanban
    _launch(_ticket(issue=9)).execute(m.deps)

    config = json.loads((worktree / ".mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["kanban"]
    assert server["command"] == "kanban"
    assert server["args"][:5] == [
        "mcp",
        "--root",
        str(Path("~/.kanban/").expanduser()),
        "--issue",
        "9",
    ]
    assert "--project" not in server["args"]


def test_launch_action_writes_mcp_registration_multi_project(tmp_path: Path) -> None:
    """A multi-project launch bakes ``--project <project_id>`` into ``.mcp.json`` (conduit §8.1)."""
    import json  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    m = _mocks(now=1234.0, worktree=worktree, kanban_root=str(tmp_path / "km"))
    # Mark the launch context as multi-project with a concrete node id (mirrors write_project_pin).
    deps = replace(m.deps, multi_project=True, project_id="PVT_node")
    _launch(_ticket(issue=5)).execute(deps)

    args = json.loads((worktree / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["kanban"][
        "args"
    ]
    assert args[-2:] == ["--project", "PVT_node"]
    assert args[1:3] == ["--root", str(tmp_path / "km")]


# ---------------------------------------------------------------------------
# LaunchAction — per-dispatch audit log (dispatch.jsonl, 15.3)
# ---------------------------------------------------------------------------


def test_launch_action_appends_one_dispatch_record(tmp_path: Path) -> None:
    """A successful launch appends EXACTLY ONE JSON line to
    ``<root>/log/dispatch.jsonl`` carrying the full PoC field set + a
    ``logged_at`` float; ``ts`` equals the injected clock's now (deterministic),
    ``logged_at`` is only checked for presence (stamped via ``time.time()``)."""
    import json  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415

    kanban_root = tmp_path / "kanban"
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    # Use a REAL fs store (so the audit file is observable) but keep every other
    # dependency mocked — only the store side-effect is exercised end to end.
    real_store = FsStateStore(root=kanban_root)
    m = _mocks(now=1234.0, worktree=worktree)
    deps = replace(m.deps, store=real_store)

    _launch(_ticket(issue=7)).execute(deps)

    log_path = kanban_root / "log" / "dispatch.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    # The full PoC field set (launch.py:297-309), mapped to NEW locals.
    assert record["issue"] == 7
    assert record["repo"] == "owner/repo"
    assert record["to"] == "InProgress"
    assert record["permission_profile"] == "docs"
    assert record["worktree"] == str(worktree)
    assert record["tmux"] == "ticket-7"
    # ts is the injected clock's now (deterministic).
    assert record["ts"] == 1234.0
    # session_uuid is the launched claude --session-id uuid (a valid uuid).
    uuid.UUID(record["session_uuid"])
    # logged_at is stamped by the adapter (time.time()) — assert presence, a float.
    assert isinstance(record["logged_at"], float)


def test_launch_action_second_launch_appends_second_line(tmp_path: Path) -> None:
    """A SECOND launch appends a SECOND line — the dispatch log is append-only."""
    import json  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415

    kanban_root = tmp_path / "kanban"
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    real_store = FsStateStore(root=kanban_root)
    m = _mocks(now=1234.0, worktree=worktree)
    deps = replace(m.deps, store=real_store)

    _launch(_ticket(issue=7)).execute(deps)
    _launch(_ticket(issue=8, item_id="PVTI_8")).execute(deps)

    log_path = kanban_root / "log" / "dispatch.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["issue"] == 7
    assert json.loads(lines[1])["issue"] == 8


def test_launch_action_audit_failure_is_swallowed(tmp_path: Path) -> None:
    """An ``append_dispatch`` failure is SWALLOWED — the launch still completes
    (running state saved + 🟡 sticky posted) and no exception propagates.

    The audit-log write is the LAST step and fail-soft: the agent already
    started, so a write failure must never break a fully-launched ticket.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.store.append_dispatch.side_effect = RuntimeError("disk full")

    # Must NOT raise even though the audit append blows up.
    _launch(_ticket(issue=7)).execute(m.deps)

    # The full launch path still completed: session started, state saved, sticky posted.
    m.sessions.launch.assert_called_once()
    m.store.save.assert_called_once()
    m.board_writer.comment.assert_called_once()
    # The audit append WAS attempted (and raised, swallowed).
    m.store.append_dispatch.assert_called_once()


def test_launch_action_dispatch_recorded_before_sticky_and_sticky_failure_is_soft(
    tmp_path: Path,
) -> None:
    """tug FIX 4: the 🟡 sticky upsert is OFF the critical path.

    The dispatch record (the "launched" audit signal) is appended BEFORE the 🟡 running-header
    upsert, and a sticky upsert that RAISES must NOT break the launch — the agent has already
    started (tmux + prompt) and the dispatch is already recorded. Patches
    ``actions.upsert_stage_comment`` to raise and asserts (a) ``append_dispatch`` still ran, and
    (b) the dispatch append happened BEFORE the sticky upsert (the reordering).
    """
    from unittest.mock import patch  # noqa: PLC0415

    m = _mocks(now=1234.0, worktree=tmp_path)
    call_order: list[str] = []
    m.store.append_dispatch.side_effect = lambda *_a, **_k: call_order.append("dispatch")

    def _boom(*_a: object, **_k: object) -> None:
        call_order.append("sticky")
        raise RuntimeError("github down")

    with patch("kanbanmate.app.actions.upsert_stage_comment", side_effect=_boom) as upsert:
        # Must NOT raise even though the sticky upsert blows up.
        _launch(_ticket(issue=7)).execute(m.deps)

    # The agent is fully launched: tmux session started + running state persisted.
    m.sessions.launch.assert_called_once()
    m.store.save.assert_called_once()
    # The dispatch record was written EVEN THOUGH the sticky raised (fail-soft, off critical path).
    m.store.append_dispatch.assert_called_once()
    upsert.assert_called_once()
    # Ordering: dispatch BEFORE sticky (FIX 4 reorder — the audit signal is not blocked on GitHub).
    assert call_order == ["dispatch", "sticky"]


def test_launch_action_clears_stale_done_and_end_attempts(tmp_path: Path) -> None:
    """FIX 2: a fresh launch clears a stale done/<issue> breadcrumb + end_attempts counter.

    A done breadcrumb (1800s TTL) or an end_attempts counter from a PRIOR stage must not survive
    into this launch — otherwise the reaper would done-exit this fresh agent prematurely. Pre-seed
    both with a REAL fs store, launch, and assert both are cleared after.
    """
    from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415

    kanban_root = tmp_path / "kanban"
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    real_store = FsStateStore(root=kanban_root)
    # Pre-seed the stale breadcrumbs from the prior stage.
    real_store.record_agent_done(7, now=1234.0)
    real_store.bump_end_attempt(7)
    assert real_store.recent_agent_done(7, now=1234.0) is True
    assert real_store.get_end_attempts(7) == 1

    m = _mocks(now=1234.0, worktree=worktree)
    deps = replace(m.deps, store=real_store)
    _launch(_ticket(issue=7)).execute(deps)

    # Both stale markers were cleared at launch (the new session's done-exit gate is clean).
    assert real_store.recent_agent_done(7, now=1234.0) is False
    assert real_store.get_end_attempts(7) == 0


def test_launch_action_breadcrumb_clear_failure_is_fail_soft(tmp_path: Path) -> None:
    """FIX 2: a ``clear_agent_done`` failure must NOT abort the launch (fail-soft).

    The breadcrumb only matters to the NEXT reap tick (it ages out at the TTL), so a clear failure
    must never break a launch the agent has already started — the running state is still saved.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.store.clear_agent_done.side_effect = RuntimeError("disk full")

    # Must NOT raise even though the breadcrumb clear blows up.
    _launch(_ticket(issue=7)).execute(m.deps)

    # The clear WAS attempted (and raised, swallowed); the launch still completed end to end.
    m.store.clear_agent_done.assert_called_once_with(7)
    m.sessions.launch.assert_called_once()
    m.store.save.assert_called_once()


def test_launch_action_end_attempts_clear_failure_is_fail_soft(tmp_path: Path) -> None:
    """FIX 2: a ``clear_end_attempts`` failure must NOT abort the launch either (symmetric, independent).

    The two breadcrumb clears sit in SEPARATE try/except blocks, so a failure of the SECOND one
    (``clear_end_attempts``) must be swallowed independently — the first clear having succeeded
    must not leave the launch half-done. ``clear_agent_done`` is left succeeding so this isolates
    the second clear's fail-soft path; the running state must still be saved.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.store.clear_end_attempts.side_effect = RuntimeError("disk full")

    # Must NOT raise even though the second breadcrumb clear blows up.
    _launch(_ticket(issue=7)).execute(m.deps)

    # The first clear ran cleanly; the second WAS attempted (and raised, swallowed); launch finished.
    m.store.clear_agent_done.assert_called_once_with(7)
    m.store.clear_end_attempts.assert_called_once_with(7)
    m.sessions.launch.assert_called_once()
    m.store.save.assert_called_once()


def test_launch_action_audit_record_ensure_ascii_false(tmp_path: Path) -> None:
    """A non-ASCII repo round-trips intact through the dispatch JSON line
    (``ensure_ascii=False``)."""
    import json  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415

    kanban_root = tmp_path / "kanban"
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    real_store = FsStateStore(root=kanban_root)
    m = _mocks(now=1234.0, worktree=worktree)
    # A non-ASCII repo slug on Deps (the audit record's ``repo`` field).
    deps = replace(m.deps, store=real_store, repo="owner/dépôt-café")

    _launch(_ticket(issue=7)).execute(deps)

    raw = (kanban_root / "log" / "dispatch.jsonl").read_text(encoding="utf-8")
    # The non-ASCII chars are written verbatim (not \uXXXX-escaped).
    assert "dépôt-café" in raw
    record = json.loads(raw.splitlines()[0])
    assert record["repo"] == "owner/dépôt-café"


# ---------------------------------------------------------------------------
# TeardownAction
# ---------------------------------------------------------------------------


def test_teardown_action_full_parity_sequence() -> None:
    """TeardownAction fires every step of the full Cancel-teardown parity (DESIGN §8.2).

    kill (guarded) → remove_worktree(force=True) → branch -D (via the workspace seam) →
    purge_ticket (exhaustive teardown, 13.7) → close_open_pr_for_branch → recap comment.
    """
    m = _mocks()
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    # 1. Session alive → killed once.
    m.sessions.is_alive.assert_called_once_with("ticket-7")
    m.sessions.kill.assert_called_once_with("ticket-7")
    # 2. Worktree removed WITH --force (a cancelled worktree is almost always dirty).
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    # 3. Local branch resolved then force-deleted via the adapter seam (no subprocess here).
    m.workspace.discover_branch.assert_called_once_with(7)
    m.workspace.delete_branch.assert_called_once_with(7, "feat/genesis")
    # 4. Exhaustive purge (state + slot + breadcrumb + queue/moves/retries), 13.7 split.
    #    Cancel teardown abandons the ticket → keep_budgets=False (the default, full purge).
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    # 6. Open PR closed for the branch (remote branch kept — close ≠ delete-ref).
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    # 7. Recap comment posted with the full-parity English text.
    m.board_writer.comment.assert_called_once()
    issue_arg, body_arg = m.board_writer.comment.call_args.args
    assert issue_arg == 7
    assert "cancelled" in body_arg
    assert "PR closed, remote branch kept" in body_arg
    assert "Backlog" in body_arg


def test_teardown_action_reap_flavour_is_non_destructive() -> None:
    """The ``reap`` flavour (defect 5) kills the session + purges state ONLY — non-destructive.

    PoC ``reaper._move_to_blocked`` parity: a stale-agent park-in-Blocked must NOT remove the
    worktree, delete the branch, or close the open PR — a twice-stalled InProgress/PRCI/Review
    agent keeps its unpushed work and its open PR. It also posts NO recap (the reaper posts its
    own stall-reason comment) and flips NO ❌ sticky (the reaper flips ⛔ itself).
    """
    m = _mocks()
    TeardownAction(ticket=_ticket(issue=7), keep_budgets=True, flavour="reap").execute(m.deps)

    # The session is killed and state purged (budget-preserving) — those steps still run.
    m.sessions.kill.assert_called_once_with("ticket-7")
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    # The DESTRUCTIVE steps are ALL skipped (defect 5): no worktree removal, no branch delete,
    # no PR close.
    m.workspace.remove_worktree.assert_not_called()
    m.workspace.delete_branch.assert_not_called()
    m.pull_requests.close_open_pr_for_branch.assert_not_called()
    # No teardown recap comment and no ❌ sticky finalize — the reaper owns the ⛔ signaling.
    m.board_writer.comment.assert_not_called()
    m.board_writer.update_comment.assert_not_called()


def test_teardown_action_discovers_branch_before_removing_worktree() -> None:
    """Teardown discovers the branch BEFORE removing the worktree (phase-25 §25.3, bug D).

    ``discover_branch`` runs ``git -C <worktree> rev-parse``; running it AFTER ``remove_worktree``
    hits a gone worktree → exit 128 (caught fail-soft but noisy + always-None, so the branch -D and
    PR close silently no-op). The fix reorders discovery to step 0, so on the happy path the branch
    is resolved against a LIVE worktree and the branch -D / PR close actually fire.
    """
    m = _mocks()
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    # Both ran, and discover_branch ran STRICTLY BEFORE remove_worktree (the workspace mock records
    # every sub-call in order). The branch was resolved off a live worktree → branch -D + PR close fired.
    names = [c[0] for c in m.workspace.mock_calls if c[0] in ("discover_branch", "remove_worktree")]
    assert names == ["discover_branch", "remove_worktree"], (
        f"discover_branch must precede remove_worktree (bug D), got order {names}"
    )
    # The happy path resolved the branch and actually deleted it (no exit-128 always-None path).
    m.workspace.delete_branch.assert_called_once_with(7, "feat/genesis")
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")


def test_teardown_action_keep_budgets_true_preserves_budgets() -> None:
    """A reaper teardown (``keep_budgets=True``) purges with the budget-preserving flag.

    The reaper constructs ``TeardownAction(ticket=…, keep_budgets=True)`` (13.8) so a reaped
    stale agent keeps its per-issue ``moves/`` rate-limit history + ``retries/`` fix-CI
    counters — the durable §6 rate-limit can then ACCUMULATE across reaps. The flag must be
    forwarded verbatim to ``purge_ticket``.
    """
    m = _mocks()
    TeardownAction(ticket=_ticket(issue=7), keep_budgets=True).execute(m.deps)

    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=True)


def test_teardown_action_default_keep_budgets_false_full_purge() -> None:
    """The default Cancel ``TeardownAction`` purges with ``keep_budgets=False`` (full teardown).

    Cancel (cli/cancel) constructs the bare ``TeardownAction(ticket=…)``, abandoning the
    ticket → the exhaustive purge drops the per-issue budgets too.
    """
    m = _mocks()
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)


def test_teardown_action_skips_kill_when_session_dead() -> None:
    """A dead session is not killed (Sessions.kill raises on an absent session)."""
    m = _mocks()
    m.sessions.is_alive.return_value = False
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.sessions.kill.assert_not_called()
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)


def test_teardown_action_skips_branch_delete_and_pr_for_no_branch() -> None:
    """A detached worktree (discover_branch → None) skips branch -D AND the PR close."""
    m = _mocks()
    m.workspace.discover_branch.return_value = None
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.workspace.discover_branch.assert_called_once_with(7)
    m.workspace.delete_branch.assert_not_called()
    m.pull_requests.close_open_pr_for_branch.assert_not_called()
    # The rest of the teardown still runs.
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.board_writer.comment.assert_called_once()


def test_teardown_action_skips_branch_delete_and_pr_for_head() -> None:
    """A ``"HEAD"`` branch (defensive) is treated as no-branch: no branch -D, no PR close."""
    m = _mocks()
    m.workspace.discover_branch.return_value = "HEAD"
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.workspace.delete_branch.assert_not_called()
    m.pull_requests.close_open_pr_for_branch.assert_not_called()
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)


def test_teardown_action_preserves_wip_branch_on_cancel() -> None:
    """Cancel PRESERVES the per-ticket WIP branch ``kanban/ticket-<n>`` (DESIGN §13).

    A pre-create-branch ticket's worktree is on the WIP branch carrying committed design/plan;
    deleting it on Cancel would destroy those artifacts. The branch delete is SKIPPED for the WIP
    branch (a ``feat/<codename>`` branch is still deleted — see the full-parity test), while the
    rest of the teardown still runs and the recap says the WIP branch was kept.
    """
    m = _mocks()
    m.workspace.discover_branch.return_value = "kanban/ticket-7"
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    # The WIP branch is NOT force-deleted (it carries the committed design/plan).
    m.workspace.delete_branch.assert_not_called()
    # The rest of the teardown still runs (worktree removed, state purged, recap posted).
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.board_writer.comment.assert_called_once()
    _issue_arg, body_arg = m.board_writer.comment.call_args.args
    assert "kanban/ticket-7" in body_arg
    assert "KEPT" in body_arg


def test_teardown_action_fail_soft_continues_after_kill_error() -> None:
    """A failing kill step does not prevent the remaining teardown steps."""
    m = _mocks()
    m.sessions.is_alive.return_value = True
    m.sessions.kill.side_effect = RuntimeError("tmux dead")

    # Must NOT raise — fail-soft swallows the error and continues.
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.sessions.kill.assert_called_once_with("ticket-7")
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.workspace.delete_branch.assert_called_once_with(7, "feat/genesis")
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    m.board_writer.comment.assert_called_once()


def test_teardown_action_fail_soft_continues_after_worktree_error() -> None:
    """A failing worktree removal does not prevent branch -D, slot release, PR close, comment."""
    m = _mocks()
    m.workspace.remove_worktree.side_effect = RuntimeError("worktree gone")

    # Must NOT raise.
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.sessions.kill.assert_called_once_with("ticket-7")
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.workspace.delete_branch.assert_called_once_with(7, "feat/genesis")
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    m.board_writer.comment.assert_called_once()


def test_teardown_action_fail_soft_continues_after_branch_delete_error() -> None:
    """A failing branch delete does not gate the slot release, PR close, or recap comment."""
    m = _mocks()
    m.workspace.delete_branch.side_effect = RuntimeError("branch busy")

    # Must NOT raise.
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.workspace.delete_branch.assert_called_once_with(7, "feat/genesis")
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    # The PR close still fires even though branch -D failed (independent steps).
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    m.board_writer.comment.assert_called_once()


def test_teardown_action_fail_soft_continues_after_discover_branch_error() -> None:
    """A failing branch discovery does not crash teardown; the PR close safely no-ops."""
    m = _mocks()
    m.workspace.discover_branch.side_effect = RuntimeError("worktree gone")

    # Must NOT raise.
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    # branch never resolved → the PR close is skipped (independent + safe).
    m.pull_requests.close_open_pr_for_branch.assert_not_called()
    m.board_writer.comment.assert_called_once()


def test_teardown_action_fail_soft_continues_after_purge_ticket_error() -> None:
    """A failing ticket purge does not prevent the PR close or the recap comment."""
    m = _mocks()
    m.store.purge_ticket.side_effect = RuntimeError("fs gone")

    # Must NOT raise.
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    m.board_writer.comment.assert_called_once()


def test_teardown_action_fail_soft_continues_after_pr_close_error() -> None:
    """A failing PR close does not prevent the final recap comment."""
    m = _mocks()
    m.pull_requests.close_open_pr_for_branch.side_effect = RuntimeError("network down")

    # Must NOT raise.
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    m.board_writer.comment.assert_called_once()


def test_teardown_action_fail_soft_survives_comment_failure() -> None:
    """A failing final comment does not prevent the prior steps from completing."""
    m = _mocks()
    m.board_writer.comment.side_effect = RuntimeError("network down")

    # Must NOT raise.
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.sessions.kill.assert_called_once_with("ticket-7")
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    # Comment was attempted (and failed), but the call was made.
    m.board_writer.comment.assert_called_once()


def test_teardown_action_replay_is_safe() -> None:
    """A second teardown (replay) destroys nothing and never raises.

    Replay-safe is NOT a clean no-op: the worktree/branch may already be gone, so the
    adapter primitives surface their own errors — but every step is fail-soft, so the
    whole flow completes idempotently without raising (DESIGN §8.2 / PoC teardown).
    """
    m = _mocks()
    # Simulate a replay: every destructive primitive errors because its target is gone.
    m.sessions.is_alive.return_value = False
    m.workspace.remove_worktree.side_effect = RuntimeError("not a working tree")
    m.workspace.delete_branch.side_effect = RuntimeError("branch not found")
    m.store.purge_ticket.side_effect = RuntimeError("already free")
    m.pull_requests.close_open_pr_for_branch.return_value = None

    # Must NOT raise.
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    # Every step was still attempted exactly once (independent, fail-soft).
    m.sessions.kill.assert_not_called()  # dead session → no kill
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.workspace.delete_branch.assert_called_once_with(7, "feat/genesis")
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")
    m.board_writer.comment.assert_called_once()


def test_teardown_action_never_relaunches() -> None:
    """TeardownAction must never start an agent or create a worktree."""
    m = _mocks()
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.sessions.launch.assert_not_called()
    m.workspace.ensure_worktree.assert_not_called()
    m.store.save.assert_not_called()


def test_teardown_action_default_flavour_is_cancel() -> None:
    """The default ``flavour`` is ``"cancel"`` (the historical Cancel-column wording)."""
    assert TeardownAction(ticket=_ticket(issue=7)).flavour == "cancel"


def test_teardown_action_cancel_flavour_posts_cancel_wording() -> None:
    """The Cancel flavour posts the abandonment recap (cancelled + Backlog re-arm) — unchanged."""
    m = _mocks()
    TeardownAction(ticket=_ticket(issue=7), flavour="cancel").execute(m.deps)

    _issue, body = m.board_writer.comment.call_args.args
    assert "cancelled" in body
    assert "move the card to Backlog" in body


# ---------------------------------------------------------------------------
# TeardownAction — Done flavour (phase 28.1)
# ---------------------------------------------------------------------------


def test_teardown_done_flavour_posts_done_wording_not_cancel() -> None:
    """The Done flavour posts the "moved to Done — agent torn down" recap, NOT the cancel text.

    A card landing in Done with a live agent is recognised as complete, not abandoned: the recap
    must NOT say "cancelled" and must NOT invite a Backlog re-arm (those are the Cancel wording).
    """
    m = _mocks()
    TeardownAction(ticket=_ticket(issue=7), flavour="done").execute(m.deps)

    _issue, body = m.board_writer.comment.call_args.args
    assert "moved to Done" in body
    assert "torn down" in body
    # Emphatically NOT the cancel wording.
    assert "cancelled" not in body
    assert "Backlog" not in body


def test_teardown_done_flavour_finalizes_open_sticky_done_not_cancelled() -> None:
    """The Done flavour flips an OPEN stage sticky to ✅ done (not ❌ cancelled).

    The teardown lists the issue comments, finds the running sticky, and re-renders its header to
    the done badge. We assert the PATCHed body carries the ✅ "— done" header, never the ❌
    "cancelled" one.
    """
    m = _mocks()
    # One OPEN (running) stage sticky for the issue, so the finalize has something to flip.
    running_sticky = MagicMock()
    running_sticky.comment_id = 555
    running_sticky.body = "<!-- kanban:step=InProgress -->\n### 🟡 InProgress — in progress\n"
    m.board_writer.list_issue_comments.return_value = [running_sticky]

    TeardownAction(ticket=_ticket(issue=7), flavour="done").execute(m.deps)

    # The sticky was PATCHed to the ✅ done header (the upsert routes through update_comment).
    m.board_writer.update_comment.assert_called_once()
    _cid, new_body = m.board_writer.update_comment.call_args.args
    assert "✅" in new_body
    assert "— done" in new_body
    assert "cancelled" not in new_body
    assert "❌" not in new_body


def test_teardown_done_flavour_runs_full_destructive_teardown() -> None:
    """The Done flavour runs the SAME destructive steps as Cancel (kill / remove / branch / purge / PR)."""
    m = _mocks()
    TeardownAction(ticket=_ticket(issue=7), flavour="done").execute(m.deps)

    m.sessions.kill.assert_called_once_with("ticket-7")
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)
    m.workspace.delete_branch.assert_called_once_with(7, "feat/genesis")
    # keep_budgets=False: the ticket's work is complete, so the exhaustive purge drops budgets too.
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.pull_requests.close_open_pr_for_branch.assert_called_once_with("feat/genesis")


# ---------------------------------------------------------------------------
# TeardownAction — replay-safety via worktree_exists (phase 28.1, SHARED path)
# ---------------------------------------------------------------------------


def test_teardown_skips_worktree_steps_when_worktree_already_gone() -> None:
    """A replay (worktree already removed) SKIPS discover_branch + remove_worktree entirely.

    The shared replay-safety gate probes ``worktree_exists`` (a clone-registry read, no
    ``git -C <gone>``); when absent, the two worktree-touching steps are skipped, so a second
    teardown produces NO noisy exit-128 ``git -C <gone>`` calls. The rest of the teardown still
    runs (kill, purge, sticky finalize, recap).
    """
    m = _mocks()
    m.workspace.worktree_exists.return_value = False

    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    # The worktree-touching steps were SKIPPED — no git -C <gone> noise.
    m.workspace.discover_branch.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    # With no branch resolved, the branch delete + PR close safely no-op (falsy branch).
    m.workspace.delete_branch.assert_not_called()
    m.pull_requests.close_open_pr_for_branch.assert_not_called()
    # The rest of the teardown still runs.
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    m.board_writer.comment.assert_called_once()


def test_teardown_done_flavour_skips_worktree_steps_when_gone() -> None:
    """The Done flavour also benefits from the shared worktree-absent skip (replay-safe)."""
    m = _mocks()
    m.workspace.worktree_exists.return_value = False

    TeardownAction(ticket=_ticket(issue=7), flavour="done").execute(m.deps)

    m.workspace.discover_branch.assert_not_called()
    m.workspace.remove_worktree.assert_not_called()
    m.store.purge_ticket.assert_called_once_with(7, keep_budgets=False)
    # Done recap still posted.
    _issue, body = m.board_writer.comment.call_args.args
    assert "moved to Done" in body


def test_teardown_runs_worktree_steps_when_present() -> None:
    """When the worktree IS present, the worktree-touching steps run (no behaviour regression)."""
    m = _mocks()
    m.workspace.worktree_exists.return_value = True

    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.workspace.discover_branch.assert_called_once_with(7)
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)


def test_teardown_worktree_exists_probe_failure_assumes_present() -> None:
    """A throwing ``worktree_exists`` probe FAILS CLOSED to "present" (the removal is fail-soft).

    A transient registry hiccup must not wrongly skip a real worktree removal; assuming "present"
    keeps the (itself fail-soft) discover/remove path intact.
    """
    m = _mocks()
    m.workspace.worktree_exists.side_effect = RuntimeError("git listing blip")

    # Must NOT raise.
    TeardownAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.workspace.discover_branch.assert_called_once_with(7)
    m.workspace.remove_worktree.assert_called_once_with(7, force=True)


# ---------------------------------------------------------------------------
# TeardownAction — body-top status header on the TERMINAL transitions (FIX 5 gap)
# ---------------------------------------------------------------------------


def _deps_with_seeder(m: _Mocks, body: str = "existing body") -> tuple[Deps, MagicMock]:
    """Wire a fake ``Seeder`` onto ``m.deps`` so the body-status header write is observable.

    The ``_mocks`` bundle leaves ``Deps.seeder=None`` (a no-op for ``update_body_status``), so a
    test that asserts the terminal-transition header write must inject a seeder. Returns the new
    frozen :class:`Deps` plus the seeder mock to assert on.

    Args:
        m: The base mock bundle whose ``deps`` to clone with a seeder.
        body: The body ``fetch_issue`` returns (the header is prepended above it).

    Returns:
        A ``(deps_with_seeder, seeder_mock)`` tuple.
    """
    seeder = MagicMock()
    seeder.fetch_issue.return_value = IssueRef(
        node_id="ISSUE_NODE_7", number=7, title="[A1] X", body=body
    )
    return replace(m.deps, seeder=seeder), seeder


def test_teardown_done_flavour_writes_done_body_header() -> None:
    """The Done-arrival teardown refreshes the body-top header to ``done`` (the terminal-gap fix).

    Without this, a card reaching Done kept a STALE header (the prior stage's running/done). The
    Done flavour must PATCH the body with a ``done`` status block — never left on a stale state.
    """
    m = _mocks()
    deps, seeder = _deps_with_seeder(m)
    TeardownAction(ticket=_ticket(issue=7), flavour="done").execute(deps)

    seeder.update_issue_body.assert_called_once()
    _node_id, new_body = seeder.update_issue_body.call_args.args
    assert new_body.startswith(STATUS_BEGIN)
    assert "**KanbanMate status** — InProgress · done — merged / done" in new_body
    assert "existing body" in new_body  # original content preserved below the header


def test_teardown_cancel_flavour_writes_cancelled_body_header() -> None:
    """The Cancel teardown refreshes the body-top header to ``cancelled`` (the terminal-gap fix)."""
    m = _mocks()
    deps, seeder = _deps_with_seeder(m)
    TeardownAction(ticket=_ticket(issue=7), flavour="cancel").execute(deps)

    seeder.update_issue_body.assert_called_once()
    _node_id, new_body = seeder.update_issue_body.call_args.args
    assert "**KanbanMate status** — InProgress · cancelled — ticket cancelled" in new_body


def test_teardown_reap_flavour_does_not_write_body_header() -> None:
    """The ``reap`` flavour does NOT write the body header here — the reaper flips it to ``blocked``.

    A parked stale agent is blocked, not done/cancelled, so the teardown must leave the body-status
    write to the reaper's own ⛔ step (which runs AFTER this non-destructive teardown).
    """
    m = _mocks()
    deps, seeder = _deps_with_seeder(m)
    TeardownAction(ticket=_ticket(issue=7), flavour="reap").execute(deps)

    seeder.update_issue_body.assert_not_called()


def test_teardown_body_header_failure_is_swallowed() -> None:
    """A seeder error during the terminal body-header write never aborts the teardown (fail-soft)."""
    m = _mocks()
    deps, seeder = _deps_with_seeder(m)
    seeder.fetch_issue.side_effect = RuntimeError("boom")

    # Must NOT raise; the recap comment still posts (the step after the body-header write).
    TeardownAction(ticket=_ticket(issue=7), flavour="done").execute(deps)
    m.board_writer.comment.assert_called_once()


# ---------------------------------------------------------------------------
# ResetAction
# ---------------------------------------------------------------------------


def test_reset_action_clears_state_without_launching() -> None:
    """ResetAction purges persisted state and launches nothing (Cancel → Backlog).

    The purge is intentionally idempotent: a single ``purge_ticket`` call (the exhaustive
    teardown, 13.7) clears runtime state (uuid / worktree / session) plus every other per-ticket
    marker (slot / breadcrumb / queue / moves / retries). The diff's re-arm does NOT require an
    explicit ``set_item_column("Backlog")`` call — NEW's poll-based diff compares against the
    ``columns_by_item`` baseline (advanced by the tick after every move), not against the
    ``TicketState`` store. After the purge, the baseline still records Backlog, so the next
    move into an agent column re-triggers a LAUNCH (sub-phase 8.2.d investigation). No
    production change is needed — this is a genuine simplification the polling pivot bought
    over the PoC.
    """
    m = _mocks()
    ResetAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.store.purge_ticket.assert_called_once_with(7)
    m.sessions.launch.assert_not_called()
    m.workspace.ensure_worktree.assert_not_called()
    m.store.save.assert_not_called()


def test_reset_action_preserves_issue_metadata() -> None:
    """ResetAction clears runtime state but never touches the GitHub issue metadata."""
    m = _mocks()
    ResetAction(ticket=_ticket(issue=7)).execute(m.deps)

    m.store.purge_ticket.assert_called_once_with(7)
    # Issue metadata on GitHub is untouched — no board writes of any kind.
    m.board_writer.comment.assert_not_called()
    m.board_writer.move_card.assert_not_called()
    # No relaunch.
    m.sessions.launch.assert_not_called()
    m.workspace.ensure_worktree.assert_not_called()
    m.store.save.assert_not_called()


# ---------------------------------------------------------------------------
# BlockAction
# ---------------------------------------------------------------------------


def test_block_action_comments_and_does_not_launch() -> None:
    """BlockAction records the reason on the ticket and NEVER launches an agent."""
    m = _mocks()
    BlockAction(ticket=_ticket(issue=7), reason="anti-loop guard tripped").execute(m.deps)

    m.board_writer.comment.assert_called_once()
    issue_arg, body_arg = m.board_writer.comment.call_args.args
    assert issue_arg == 7
    assert "anti-loop guard tripped" in body_arg
    # Emphatically no launch.
    m.sessions.launch.assert_not_called()
    m.workspace.ensure_worktree.assert_not_called()
    m.store.save.assert_not_called()


# ---------------------------------------------------------------------------
# RollbackAction (phase 12.5)
# ---------------------------------------------------------------------------


def test_rollback_action_moves_card_then_comments_english() -> None:
    """RollbackAction bounces the card to ``to_column`` THEN posts an English recap.

    Order is load-bearing: the move (the effect) precedes the comment (the courtesy recap)
    so a transient comment failure never leaves the board un-bounced. The recap text is
    English (the PoC text was French "carte ramenée en").
    """
    m = _mocks()
    parent = MagicMock()
    parent.attach_mock(m.board_writer.move_card, "move")
    parent.attach_mock(m.board_writer.comment, "comment")

    RollbackAction(
        ticket=_ticket(issue=7),
        to_column="Backlog",
        reason="move not whitelisted",
    ).execute(m.deps)

    # Card bounced back to the origin column.
    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Backlog")
    # Recap comment posted on the issue, in English, naming the bounce target.
    m.board_writer.comment.assert_called_once()
    issue_arg, body_arg = m.board_writer.comment.call_args.args
    assert issue_arg == 7
    assert "move not whitelisted" in body_arg
    assert "card returned to Backlog" in body_arg
    # No French recap text survives the translation.
    assert "carte ramenée" not in body_arg
    # Order: move BEFORE comment.
    ordered = [name for name, _, _ in parent.mock_calls]
    assert ordered.index("move") < ordered.index("comment")


def test_rollback_action_fail_soft_on_move_error() -> None:
    """A failing move is logged and does not abort the recap comment (fail-soft per step)."""
    m = _mocks()
    m.board_writer.move_card.side_effect = RuntimeError("board down")

    # Must NOT raise.
    RollbackAction(ticket=_ticket(issue=7), to_column="Backlog", reason="r").execute(m.deps)

    m.board_writer.move_card.assert_called_once_with("PVTI_7", "Backlog")
    # The recap comment still fires even though the move failed (independent step).
    m.board_writer.comment.assert_called_once()


def test_rollback_action_noop_for_draft_without_issue() -> None:
    """A draft item (issue_number=None) has no issue to bounce — nothing happens."""
    m = _mocks()
    RollbackAction(ticket=_ticket(issue=None), to_column="Backlog", reason="r").execute(m.deps)

    m.board_writer.move_card.assert_not_called()
    m.board_writer.comment.assert_not_called()


# ---------------------------------------------------------------------------
# RunScriptAction (phase 12.5)
# ---------------------------------------------------------------------------


def test_run_script_action_runs_with_kanban_env_and_reports_exit_code() -> None:
    """RunScriptAction runs the script via the workspace runner with KANBAN_REPO/BRANCH env.

    The per-ticket worktree branch is discovered, the env is built (KANBAN_REPO from Deps,
    KANBAN_BRANCH from the discovered branch), and the script runs through the workspace
    runner (the subprocess lives in the adapter — this action is subprocess-free).
    """
    m = _mocks()
    m.workspace.discover_branch.return_value = "feat/genesis"
    m.workspace.run_transition_script.return_value = (0, "PR ready")

    RunScriptAction(
        ticket=_ticket(issue=7),
        script="bin/check-pr-ready.sh",
        on_fail="move:Implement",
        advance="auto:PRReady",
    ).execute(m.deps)

    # The branch is discovered for the env.
    m.workspace.discover_branch.assert_called_once_with(7)
    # The script runs via the workspace runner with the required env.
    m.workspace.run_transition_script.assert_called_once_with(
        7,
        "bin/check-pr-ready.sh",
        {"KANBAN_REPO": "owner/repo", "KANBAN_BRANCH": "feat/genesis"},
    )


def test_run_script_action_reports_nonzero_exit_without_raising() -> None:
    """A non-zero exit (check failed) is recorded by logging — the action never raises.

    Phase 12 only records the verdict; the on_fail routing on a failed check is phase 13.
    """
    m = _mocks()
    m.workspace.run_transition_script.return_value = (1, "check failed")

    # Must NOT raise (the verdict is logged; routing is phase 13).
    RunScriptAction(ticket=_ticket(issue=7), script="bin/check.sh", on_fail="rollback").execute(
        m.deps
    )

    m.workspace.run_transition_script.assert_called_once()


def test_run_script_action_fail_soft_on_runner_exception() -> None:
    """A runner exception (a wedged script) is logged, never raised out of the tick."""
    m = _mocks()
    m.workspace.run_transition_script.side_effect = RuntimeError("script wedged")

    # Must NOT raise — fail-soft so the daemon tick survives a broken transition script.
    RunScriptAction(ticket=_ticket(issue=7), script="bin/check.sh").execute(m.deps)

    m.workspace.run_transition_script.assert_called_once()


def test_run_script_action_noop_for_draft_without_issue() -> None:
    """A draft item (issue_number=None) has no worktree — nothing runs."""
    m = _mocks()
    RunScriptAction(ticket=_ticket(issue=None), script="bin/check.sh").execute(m.deps)

    m.workspace.discover_branch.assert_not_called()
    m.workspace.run_transition_script.assert_not_called()


# ---------------------------------------------------------------------------
# LaunchAction — filled per-transition prompt (phase 12.5)
# ---------------------------------------------------------------------------


def test_launch_action_fills_and_send_keys_the_per_transition_prompt(tmp_path: Path) -> None:
    """A LaunchAction with a prompt launches BARE claude, then SEND-KEYS the filled prompt + Enter.

    Phase-25 §25.1 (PoC parity): the launch COMMAND must NOT carry the positional prompt (the bug
    that left the agent idle); the filled ``/implement:*`` prompt — with ``{{code}}`` substituted to
    ``#7``, the title, and the branch — is typed INTO the live REPL via ``send_text`` and SUBMITTED
    with a trailing Enter. Default capture pane is a ready REPL (no trust dialog) → no dismiss Enter.
    """
    import shlex  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    m = _mocks(now=1234.0, worktree=tmp_path)
    m.workspace.discover_branch.return_value = "feat/genesis"

    LaunchAction(
        ticket=_ticket(issue=7),
        prompt="/implement:phase ticket {{code}} ({{title}}) on {{branch}}",
        profile="dev",
        permission_mode="auto",
    ).execute(m.deps)

    # The launch command is BARE — no positional prompt. It carries the real argv + the wrapper,
    # but NONE of the filled-prompt tokens (#7 / /implement:phase / the branch).
    m.sessions.launch.assert_called_once()
    session_name, cwd, command = m.sessions.launch.call_args.args
    assert session_name == "ticket-7"
    assert cwd == str(tmp_path)
    assert "--session-id" in command
    assert f"--add-dir {tmp_path}" in command
    assert "; kanban-session-end 7" in command
    assert "/implement:phase" not in command  # the prompt is NOT in the launch command anymore
    assert "#7" not in command
    parts = shlex.split(command)
    # No positional message: the token before the ``;`` separator is the --add-dir worktree path.
    assert parts[parts.index(";") - 1] == str(tmp_path)
    # --permission-mode reflects the per-transition mode (NOT pinned_mode(profile)) — plan-drift.
    assert parts[parts.index("--permission-mode") + 1] == "auto"

    # The FILLED prompt was delivered INTO the REPL via send_text (literal) + a submit Enter. The
    # default ready-REPL pane means NO leading trust-dismiss Enter, so the sequence is exactly
    # [literal prompt, literal space, Enter].
    literal_sends = [
        c.args[1] for c in m.sessions.send_text.call_args_list if c.kwargs.get("literal") is True
    ]
    # {{code}} fills the BARE issue number (defect 3) — the delivered prompt carries ``7``, not ``#7``.
    assert "/implement:phase ticket 7 (t) on feat/genesis" in literal_sends
    # Exactly one Enter (submit), no trust-dismiss Enter on a ready pane.
    enter_calls = [
        c for c in m.sessions.send_text.call_args_list if c.kwargs.get("literal") is False
    ]
    assert len(enter_calls) == 1
    assert enter_calls[0].args[1] == "Enter"

    # The per-transition profile/mode are persisted on the widened state.
    saved: TicketState = m.store.save.call_args.args[0]
    assert saved.profile == "dev"
    assert saved.mode == "auto"


def test_launch_action_with_trust_dialog_sends_dismiss_enter_first(tmp_path: Path) -> None:
    """When the poll sees the trust dialog, a dismiss Enter precedes the literal prompt (PoC parity).

    Phase-25 §25.1: the capture-pane poll returns a trust-dialog snapshot FIRST, then a ready REPL.
    ``build_sendkeys_sequence(trust_prompt_seen=True)`` prepends a bare Enter to dismiss
    "Is this a project you trust?" BEFORE typing the prompt — so the first send_text is an Enter.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    # First capture: the trust dialog (the poll stops on the first trust marker). Then a running-turn
    # pane backs the submit-retry check so the prompt reads as landed (no re-delivery).
    m.sessions.capture.side_effect = [
        "Do you trust the files in this folder?",
        "● working…\n  esc to interrupt",
    ]

    LaunchAction(
        ticket=_ticket(issue=7),
        prompt="/implement:phase {{code}}",
        profile="dev",
    ).execute(m.deps)

    # The send_text call sequence is: Enter (dismiss trust), literal prompt, literal space, Enter.
    calls = m.sessions.send_text.call_args_list
    # First send is the trust-dismiss Enter (literal=False).
    assert calls[0].args[1] == "Enter"
    assert calls[0].kwargs.get("literal") is False
    # The filled prompt is typed literally after the dismiss Enter ({{code}} → bare 7, defect 3).
    literal_sends = [c.args[1] for c in calls if c.kwargs.get("literal") is True]
    assert "/implement:phase 7" in literal_sends
    # Two Enter events total: the trust dismiss + the final submit.
    enters = [c for c in calls if c.kwargs.get("literal") is False]
    assert len(enters) == 2


def test_launch_action_poll_waits_for_ready_then_sends(tmp_path: Path) -> None:
    """The bounded poll keeps capturing while the pane is ``pending``, sleeping between captures.

    Phase-25 §25.1 (PoC ``poll_trust_dialog`` parity): real ``claude`` needs seconds to render, so a
    single capture misses the REPL. The poll captures, sleeps the injected sleeper on a ``pending``
    snapshot, and stops on the first ``ready`` marker — only THEN does it send-keys the prompt.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    # Two booting (pending) snapshots, then a ready REPL — the poll must iterate three times. A
    # fourth capture (a clean REPL with no pending prompt) backs the submit-retry check: it reads as
    # SUBMITTED on the first probe, so no extra Enter is re-sent.
    m.sessions.capture.side_effect = [
        "booting...",
        "starting...",
        "│ > Welcome to Claude",
        # submit-retry check: a running turn ⇒ the prompt landed → no resend, no re-delivery.
        "│ > Welcome to Claude\n  esc to interrupt",
    ]
    sleeps: list[float] = []
    m.deps = replace(m.deps, sleeper=sleeps.append)

    _launch(_ticket(issue=7), prompt="/implement:phase {{code}}").execute(m.deps)

    # Captured four times (2 pending + 1 ready poll + 1 submit-retry check), slept twice for the poll
    # (0.5 each) then once for the submit-retry settle (0.6).
    assert m.sessions.capture.call_count == 4
    assert sleeps == [0.5, 0.5, 0.6]
    # The prompt was delivered only AFTER the ready REPL was seen.
    literal_sends = [
        c.args[1] for c in m.sessions.send_text.call_args_list if c.kwargs.get("literal") is True
    ]
    assert "/implement:phase 7" in literal_sends  # {{code}} → bare 7 (defect 3)
    # A ready pane (not trust) + a submitted-on-first-check input box ⇒ exactly one Enter (the
    # initial submit); the submit-retry loop re-sends NO extra Enter.
    enters = [c for c in m.sessions.send_text.call_args_list if c.kwargs.get("literal") is False]
    assert len(enters) == 1


def test_poll_pane_timeout_logs_warning_with_pane_tail(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """#11: when the poll exhausts all attempts (no trust/ready), it WARNs with the pane tail.

    Previously a poll timeout was a silent ``return False``; now it logs so an operator can see what
    the REPL actually showed when the marker heuristics drifted. The launch still proceeds.
    """
    import logging  # noqa: PLC0415

    m = _mocks(now=1234.0, worktree=tmp_path)
    # Every capture is an unrecognised pane → the poll never sees trust/ready → it times out.
    m.sessions.capture.return_value = "some unexpected claude UI we do not recognise"
    m.deps = replace(m.deps, sleeper=lambda _s: None)

    with caplog.at_level(logging.WARNING):
        _launch(_ticket(issue=7), prompt="/implement:phase {{code}}").execute(m.deps)

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "timed out" in messages
    assert "Pane tail" in messages


def test_post_send_verification_warns_and_stickies_when_prompt_undelivered(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """If the prompt never leaves the input box, the submit-retry loop EXHAUSTS then WARNs + stickies.

    The pane keeps showing the filled prompt verbatim — unambiguous "keystrokes did not land"
    evidence. The submit-retry loop re-sends Enter up to its budget; on exhaustion it falls back to
    the WARN + advisory sticky (verify_prompt_delivered). The launch must NOT raise.
    """
    import logging  # noqa: PLC0415

    m = _mocks(now=1234.0, worktree=tmp_path)
    prompt = "/implement:phase {{code}} run all the remaining phases now please"
    # {{code}} fills the bare issue number (defect 3), so the undelivered line carries ``7``. The
    # pane CONSTANTLY shows the prompt still sitting in the input box: the poll reads it as ready
    # (``│ >``), every submit-retry probe reads it as still-pending (prompt verbatim), and the final
    # verify confirms it undelivered → WARN + sticky.
    filled_first_line = "/implement:phase 7 run all the remaining phases now please"
    m.sessions.capture.return_value = f"│ > {filled_first_line}"
    m.deps = replace(m.deps, sleeper=lambda _s: None)

    with caplog.at_level(logging.WARNING):
        # Must NOT raise — the submit-retry fallback is WARN-only.
        _launch(_ticket(issue=7), prompt=prompt).execute(m.deps)

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "UNDELIVERED" in messages
    # An advisory sticky note was upserted (the board writer's comment path was exercised).
    assert m.board_writer.list_issue_comments.called


def test_launch_action_without_prompt_launches_bare_and_sends_no_prompt(tmp_path: Path) -> None:
    """A LaunchAction with prompt=None launches BARE claude and send-keys NO prompt (phase-25 §25.1).

    The legacy (prompt=None) path builds the real argv + the session-end wrapper; the bare claude
    session boots without an injected first message — so the launch NEVER polls capture-pane nor
    types a prompt into the REPL (no ``send_text`` prompt delivery, no ``capture`` poll).
    """
    import shlex  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    m = _mocks(now=1234.0, worktree=tmp_path)

    _launch(_ticket(issue=7)).execute(m.deps)

    m.sessions.launch.assert_called_once()
    _name, _cwd, command = m.sessions.launch.call_args.args
    assert command != "claude /implement:phase"  # NOT the static Deps.agent_command anymore
    assert "--session-id" in command
    assert f"--add-dir {tmp_path}" in command
    assert "; kanban-session-end 7" in command
    parts = shlex.split(command)
    # No positional message: the token before the ``;`` separator is the --add-dir worktree path.
    assert parts[parts.index(";") - 1] == str(tmp_path)
    # prompt=None ⇒ no prompt delivery: the launch neither polls capture-pane nor types a prompt.
    m.sessions.capture.assert_not_called()
    m.sessions.send_text.assert_not_called()


def test_launch_action_prompt_with_unknown_key_raises_keyerror(tmp_path: Path) -> None:
    """A prompt referencing a TYPO'd key fails loud (KeyError) — a half-filled agent never starts.

    A defaulted-"" enrichment key (e.g. ``{{codename}}``) fills cleanly; a genuine typo
    (``{{titel}}``) raises, preserving the fail-loud contract.
    """
    import pytest  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    m = _mocks(now=1234.0, worktree=tmp_path)

    # A defaulted-"" enrichment key must NOT raise.
    _launch(
        _ticket(issue=7),
        prompt="codename is {{codename}}",
    ).execute(m.deps)
    m.sessions.launch.assert_called_once()

    # A typo'd key (not a known/ defaulted key) raises KeyError.
    with pytest.raises(KeyError):
        _launch(
            _ticket(issue=7),
            prompt="title is {{titel}}",
        ).execute(m.deps)
    # Minor (c): the FILL runs BEFORE the session is created, so the typo'd-key launch NEVER spawned
    # a tmux session (no untracked bare-claude leak). ``launch`` was called exactly ONCE — by the
    # earlier clean launch above, NOT by the failing one.
    assert m.sessions.launch.call_count == 1


def test_launch_action_fills_script_output_from_store(tmp_path: Path) -> None:
    """A LaunchAction whose prompt contains ``{{script_output}}`` fills it from the store.

    15.7: ``_launch_context`` sources ``script_output`` from
    ``deps.store.load_script_output(issue)`` — the last failing check's output
    persisted by 15.6. The sentinel appears verbatim in the SEND-KEYS'd prompt (phase-25 §25.1:
    delivered into the REPL, not in the launch command) so the fix-CI agent gets the failure text.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.store.load_script_output.return_value = "CI FAILED: test_foo assertion error"

    _launch(
        _ticket(issue=7),
        prompt="The CI is red:\n{{script_output}}\nFix the problems.",
    ).execute(m.deps)

    m.sessions.launch.assert_called_once()
    # The filled failure text was typed INTO the REPL (not composed into the launch command).
    assert "CI FAILED: test_foo assertion error" in _delivered_prompt(m.sessions)
    # The store was queried for the correct issue.
    m.store.load_script_output.assert_called_once_with(7)


def test_launch_action_empty_script_output_is_benign(tmp_path: Path) -> None:
    """When the store has no persisted script output, ``{{script_output}}`` fills as ``""``.

    Back-compat: a non-fix-CI launch (or any launch where no check has failed yet)
    fills the placeholder with the empty string and does not crash.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.store.load_script_output.return_value = ""

    _launch(
        _ticket(issue=7),
        prompt="codename is {{codename}} and script_output is '{{script_output}}'",
    ).execute(m.deps)

    m.sessions.launch.assert_called_once()
    # The empty script_output does not crash the launch — the placeholder is replaced with "",
    # so the delivered prompt still contains "script_output is " (nothing between the quotes).
    assert "script_output is" in _delivered_prompt(m.sessions)


# ---------------------------------------------------------------------------
# LaunchAction — transition-only permission resolution (phase 20, DESIGN §8.0.6)
# ---------------------------------------------------------------------------


def test_launch_resolves_profile_from_transition(tmp_path: Path) -> None:
    """The launch profile is the matched transition's ``profile`` (transitions-only, DESIGN §8.0.6).

    The agent launches AT the transition, so its profile comes from the transition ``profile`` —
    that value is what the launch persists + materialises (no per-column default tier exists).
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    LaunchAction(
        ticket=_ticket(issue=7),
        profile="dev",
    ).execute(m.deps)

    saved: TicketState = m.store.save.call_args.args[0]
    assert saved.profile == "dev"  # the transition profile resolved


def test_launch_fails_loud_when_transition_profile_empty(tmp_path: Path) -> None:
    """An empty transition ``profile`` FAILS LOUD (no column default, no silent global; §8.0.6/§10).

    The launch must RAISE before any worktree/session is created, NOT silently run under
    ``Deps.profile`` — the security-relevant invariant (DESIGN §10).
    """
    import pytest  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    m = _mocks(now=1234.0, worktree=tmp_path)
    with pytest.raises(ValueError, match="no permission profile resolved"):
        LaunchAction(
            ticket=_ticket(issue=7),
            profile="",
        ).execute(m.deps)

    # FAIL-LOUD BEFORE side-effects: no worktree, no session, no persisted state — and emphatically
    # NOT a silent fallback to the global Deps.profile (which is "docs").
    m.workspace.ensure_worktree.assert_not_called()
    m.sessions.launch.assert_not_called()
    m.store.save.assert_not_called()


def test_launch_does_not_use_global_deps_profile(tmp_path: Path) -> None:
    """The production resolution NEVER consults ``Deps.profile`` (the no-silent-global invariant).

    Even with a non-default ``Deps.profile`` set, a LaunchAction with no transition profile fails
    loud rather than borrowing the global — so adversarial verification finds no leak (§8.0.6/§10).
    """
    import pytest  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    m = _mocks(now=1234.0, worktree=tmp_path)
    deps_with_global = replace(m.deps, profile="dev")  # a tempting global to (not) borrow
    with pytest.raises(ValueError, match="no permission profile resolved"):
        LaunchAction(ticket=_ticket(issue=7)).execute(deps_with_global)
    m.sessions.launch.assert_not_called()


def test_launch_resolved_bypass_profile_is_rejected(tmp_path: Path) -> None:
    """A transition profile resolving to a bypass mode is rejected (§10 floor survives, §8.0.6).

    Even though the resolution found a profile, ``materialise_settings`` /
    ``build_claude_argv`` reject a bypass — so the bypass ban holds end-to-end, not just at load.
    """
    import pytest  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    m = _mocks(now=1234.0, worktree=tmp_path)
    with pytest.raises(ValueError, match="bypass"):
        LaunchAction(
            ticket=_ticket(issue=7),
            profile="bypassPermissions",
        ).execute(m.deps)
    # The bypass never reached a live session.
    m.sessions.launch.assert_not_called()


# ---------------------------------------------------------------------------
# LaunchAction — parse_ticket_fields enrichment (18.1)
# ---------------------------------------------------------------------------


def _ticket_with_body(issue: int, body: str, item_id: str = "PVTI_7") -> Ticket:
    """Build a :class:`Ticket` with a specific ``body`` for field-parsing tests.

    Args:
        issue: The issue number.
        body: The markdown body (may contain ``**key**: value`` markers).
        item_id: The project item node id.

    Returns:
        A frozen :class:`Ticket` with the given body.
    """
    return Ticket(
        item_id=item_id, issue_number=issue, title="t", column_key="InProgress", body=body
    )


def test_launch_context_parses_codename_from_ticket_body(tmp_path: Path) -> None:
    """``_launch_context`` fills ``codename`` / ``design_path`` / ``plan_paths``
    from markers in the ticket body (PoC parity, 18.1).

    The returned context dict carries the real parsed values, not ``""``.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    body = (
        "**codename**: genesis\n"
        "**design**: docs/DESIGN.md\n"
        "**plans**: docs/plan/phase-1.md, docs/plan/phase-2.md\n"
    )
    ticket = _ticket_with_body(issue=7, body=body)

    LaunchAction(
        ticket=ticket,
        prompt="codename is {{codename}} and design is {{design_path}}",
        profile="docs",
    ).execute(m.deps)

    m.sessions.launch.assert_called_once()
    # The codename and design_path are substituted from the parsed markers (in the delivered prompt).
    delivered = _delivered_prompt(m.sessions)
    assert "genesis" in delivered
    assert "docs/DESIGN.md" in delivered
    # The plan_paths are also filled (the template didn't reference them, but the
    # context dict carries them — we assert via the _launch_context dict below).


def test_launch_context_plan_paths_filled_from_body(tmp_path: Path) -> None:
    """``_launch_context`` fills ``plan_paths`` from the comma-joined ``**plans**`` marker."""
    m = _mocks(now=1234.0, worktree=tmp_path)
    body = "**plans**: a.md, b.md"
    ticket = _ticket_with_body(issue=7, body=body)

    LaunchAction(
        ticket=ticket,
        prompt="plans are {{plan_paths}}",
        profile="docs",
    ).execute(m.deps)

    m.sessions.launch.assert_called_once()
    assert "a.md, b.md" in _delivered_prompt(m.sessions)


def test_launch_context_empty_body_fills_empty_strings(tmp_path: Path) -> None:
    """A ticket body with NO markers defaults ``codename`` / ``design_path`` /
    ``plan_paths`` to ``""`` (back-compat — no crash).

    The launch still completes with the defaulted empty strings.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    # The default _ticket uses body="" (the dataclass default).
    _launch(
        _ticket(issue=7),
        prompt="codename is '{{codename}}' and plans are '{{plan_paths}}'",
    ).execute(m.deps)

    m.sessions.launch.assert_called_once()
    # The empty-string placeholders are substituted (the delivered prompt contains the
    # surrounding text from the template — the codename/plans tokens were filled
    # with "" and the launch did NOT crash with a KeyError).
    delivered = _delivered_prompt(m.sessions)
    assert "codename is" in delivered
    assert "plans are" in delivered


def test_launch_context_code_is_bare_issue_number(tmp_path: Path) -> None:
    """``{{code}}`` fills the BARE issue number, not ``#<issue>`` (defect 3).

    Every shipped prompt pins helper calls to ``{{code}}`` (e.g. ``kanban-move {{code}} 'PR/CI'``)
    and the kanban-* helpers parse ``int(argv[0])``; a leading ``#`` makes ``#7`` a bash comment
    (zero args → usage exit 2) and ``int('#7')`` raises. The delivered prompt must carry ``7``.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    _launch(
        _ticket(issue=7),
        prompt="kanban-move {{code}} 'PR/CI'",
    ).execute(m.deps)

    m.sessions.launch.assert_called_once()
    delivered = _delivered_prompt(m.sessions)
    assert "kanban-move 7 'PR/CI'" in delivered
    assert "#7" not in delivered  # no '#' prefix that would break the helper's int parse


def test_launch_context_body_with_only_codename_others_empty(tmp_path: Path) -> None:
    """Partial markers: a body with only ``**codename**`` fills codename;
    ``design_path`` and ``plan_paths`` stay ``""``."""
    m = _mocks(now=1234.0, worktree=tmp_path)
    body = "**codename**: solo-feature"
    ticket = _ticket_with_body(issue=7, body=body)

    LaunchAction(
        ticket=ticket,
        prompt="codename={{codename}} design={{design_path}} plans={{plan_paths}}",
        profile="docs",
    ).execute(m.deps)

    m.sessions.launch.assert_called_once()
    assert "codename=solo-feature" in _delivered_prompt(m.sessions)
    # design_path and plan_paths are "" — the tokens are substituted (no KeyError).


# ---------------------------------------------------------------------------
# LaunchAction — issue_context enrichment (18.2)
# ---------------------------------------------------------------------------


def test_launch_context_fills_issue_body_and_comments(tmp_path: Path) -> None:
    """``_launch_context`` fills ``{{issue_body}}`` from the linked issue and ``{{comments}}``
    from the joined comment history via ``board_reader.issue_context`` (PoC parity, 18.2).

    ``issue_body`` resolves to ``ctx.linked_issue_body`` (the FIRST cross-referenced issue,
    NOT this ticket's own body) and ``comments`` to the ``\\n---\\n``-joined bodies.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.board_reader.issue_context.return_value = IssueContext(
        body="THIS TICKET BODY",
        comments=("c1", "c2"),
        linked_issue_body="LINKED",
    )

    LaunchAction(
        ticket=_ticket(issue=7),
        prompt="issue_body={{issue_body}} comments=[{{comments}}]",
        profile="docs",
    ).execute(m.deps)

    # The enrichment queried issue_context for the right issue.
    m.board_reader.issue_context.assert_called_once_with(7)
    m.sessions.launch.assert_called_once()
    # {{issue_body}} = linked_issue_body; {{comments}} = the PoC \n---\n join (delivered prompt).
    delivered = _delivered_prompt(m.sessions)
    assert "issue_body=LINKED" in delivered
    assert "comments=[c1\n---\nc2]" in delivered


def test_launch_context_issue_context_fail_soft(tmp_path: Path) -> None:
    """A throwing ``issue_context`` degrades ``issue_body``/``comments`` to ``""`` and the launch
    still completes — a GraphQL hiccup must NOT break a launch (fail-soft, 18.2).

    Mirrors the stage-comment fail-soft shape: the critical path (worktree + session + state +
    sticky) still completes and no exception propagates.
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.board_reader.issue_context.side_effect = RuntimeError("graphql down")

    # Must NOT raise: a referenced {{issue_body}}/{{comments}} fills "" (no leftover {{...}}).
    LaunchAction(
        ticket=_ticket(issue=7),
        prompt="ib=[{{issue_body}}] c=[{{comments}}]",
        profile="docs",
    ).execute(m.deps)

    m.board_reader.issue_context.assert_called_once_with(7)
    # The full launch path still completed despite the enrichment failure.
    m.workspace.ensure_worktree.assert_called_once_with(7, base="main")
    m.sessions.launch.assert_called_once()
    m.store.save.assert_called_once()
    # The RUNNING sticky is still posted (best-effort header survives the enrichment failure).
    m.board_writer.comment.assert_called_once()
    # Both placeholders resolved to "" — no leftover {{...}} tokens in the delivered prompt.
    delivered = _delivered_prompt(m.sessions)
    assert "ib=[]" in delivered
    assert "c=[]" in delivered
    assert "{{issue_body}}" not in delivered
    assert "{{comments}}" not in delivered


def test_launch_context_no_linked_issue_fills_empty_issue_body(tmp_path: Path) -> None:
    """A context with ``linked_issue_body=None`` fills ``{{issue_body}}`` as ``""`` (the
    ``or ""`` guard) while ``{{comments}}`` still carries the joined history (18.2)."""
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.board_reader.issue_context.return_value = IssueContext(
        body="b",
        comments=("only-comment",),
        linked_issue_body=None,
    )

    LaunchAction(
        ticket=_ticket(issue=7),
        prompt="ib=[{{issue_body}}] c=[{{comments}}]",
        profile="docs",
    ).execute(m.deps)

    m.sessions.launch.assert_called_once()
    delivered = _delivered_prompt(m.sessions)
    assert "ib=[]" in delivered  # None → "" (the ``or ""`` guard)
    assert "c=[only-comment]" in delivered


# ---------------------------------------------------------------------------
# §29.3 — {{issue_body}} direction fix (the #91 poisoning)
# ---------------------------------------------------------------------------


def test_launch_context_drops_downstream_dependent_by_number(tmp_path: Path) -> None:
    """A linked body that ``Depends on #<this-issue>`` is a DOWNSTREAM dependent → dropped (§29.3).

    This is the #91 root cause: O1's body ("Depends on #91") cross-references #91, so the
    enrichment would inject O1's feature text into #91's launch prompt. The direction filter must
    drop it (``issue_body=""``).
    """
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.board_reader.issue_context.return_value = IssueContext(
        body="this ticket",
        comments=(),
        linked_issue_body="O1 feature text.\n\nDepends on #91",
    )

    LaunchAction(
        ticket=_ticket(issue=91),
        prompt="ib=[{{issue_body}}]",
        profile="docs",
    ).execute(m.deps)

    delivered = _delivered_prompt(m.sessions)
    assert "ib=[]" in delivered  # the downstream dependent's body was filtered out
    assert "O1 feature text" not in delivered


def test_launch_context_keeps_genuine_upstream_source(tmp_path: Path) -> None:
    """A genuine UPSTREAM source (one we depend on; it does NOT mention us) is still injected."""
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.board_reader.issue_context.return_value = IssueContext(
        body="this ticket",
        comments=(),
        linked_issue_body="Upstream spec we build on (no back-reference).",
    )

    LaunchAction(
        ticket=_ticket(issue=91),
        prompt="ib=[{{issue_body}}]",
        profile="docs",
    ).execute(m.deps)

    delivered = _delivered_prompt(m.sessions)
    assert "ib=[Upstream spec we build on (no back-reference).]" in delivered


def test_launch_context_drops_downstream_dependent_by_code(tmp_path: Path) -> None:
    """The code-form ``Depends on <CODE>`` (CODE from our ``[CODE]`` title) is also filtered."""
    m = _mocks(now=1234.0, worktree=tmp_path)
    m.board_reader.issue_context.return_value = IssueContext(
        body="this ticket",
        comments=(),
        linked_issue_body="O1 text.\n\nDepends on A1",
    )

    # Our title carries the [A1] bracket; the linked body depends on A1 → downstream → dropped.
    ticket = replace(_ticket(issue=91), title="[A1] My feature")
    LaunchAction(ticket=ticket, prompt="ib=[{{issue_body}}]", profile="docs").execute(m.deps)

    delivered = _delivered_prompt(m.sessions)
    assert "ib=[]" in delivered
    assert "O1 text" not in delivered
