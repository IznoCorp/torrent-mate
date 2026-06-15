"""Composition root: build concrete adapters and assemble :class:`Deps` (DESIGN §3.3).

This is the **only** ``app`` module permitted to name concrete adapter classes. Everywhere else
(``tick``, ``actions``) speaks ``ports`` Protocols, so the wiring stays the single seam where the
hexagon's inside meets its outside (DESIGN §3.2). Given a :class:`WiringConfig`, :func:`build_deps`
constructs the GitHub board client, the filesystem state store, the git-worktree workspace, the
tmux sessions adapter, and a real wall-clock, then bundles them into the :class:`Deps` the
actions execute against.

Layering: ``app`` may import ``adapters`` (DESIGN §3.2); this module does, deliberately. It must
not import ``cli`` or ``daemon`` (the entrypoints sit *above* the composition root).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.adapters.workspace.sessions import TmuxSessions
from kanbanmate.adapters.workspace.worktree import GitWorktreeWorkspace
from kanbanmate.app.actions import DEFAULT_BASE, Deps
from kanbanmate.app.tick import PersistedState, TickConfig, TickResult, tick
from kanbanmate.core.columns import load_columns
from kanbanmate.core.transitions import load_transitions
from kanbanmate.core.transitions_defaults import default_transition_config


@dataclass(frozen=True)
class WiringConfig:
    """The runtime configuration needed to build every concrete adapter.

    A thin, typed value object the daemon/CLI fills from ``~/.kanban/`` config + the per-repo
    ``columns.yml``. Keeping it explicit (rather than reading the environment inside the adapters)
    preserves the functional-core / imperative-shell boundary: I/O sources are named here, once.

    Attributes:
        token: A GitHub PAT scoped ``project`` + ``repo`` (DESIGN §10).
        project_id: The ``ProjectV2`` node id of the board to drive.
        repo: The ``owner/name`` slug used to resolve issues for comments.
        clone_dir: The local clone all per-ticket worktrees are siblings of.
        columns_yaml: The raw ``columns.yml`` document; parsed once into the column model.
        kanban_root: The state-store root; defaults to ``~/.kanban/`` when ``None``.
        base: The integration base branch new worktrees check out detached.
        agent_command: The shell command launched inside each agent's tmux session.
        kill_switch: When ``True`` (``~/.kanban/PAUSE`` present) every launch is blocked.
        transitions_yaml: The raw ``transitions.yml`` document from the clone's
            ``.claude/kanban/transitions.yml``; ``None`` when the clone ships none, in which
            case :func:`build_tick_config` falls back to the built-in
            :data:`~kanbanmate.core.transitions_defaults.DEFAULT_TRANSITIONS` so a whitelist is
            ALWAYS supplied (DESIGN §8.0.6) — never a column model.
        config_dir: The project's ``.claude`` directory (skills/commands/agents source) the
            launch COPIES into each worktree so the agent resolves its ``/implement:*`` skills
            (phase 14.6). Threaded onto :attr:`~kanbanmate.app.actions.Deps.config_dir`; an empty
            value disables provisioning. Filled from the registry's ``config_dir`` by the daemon's
            ``_wiring_from_registry``. (The registry's ``dev_repo_path`` does NOT reach here — it
            is consumed only by the post-merge ``kanban-update-main`` path, which reads it off the
            registry directly, so it never needs to thread through the tick.)
    """

    token: str
    project_id: str
    repo: str
    clone_dir: str
    columns_yaml: str
    kanban_root: str | None = None
    base: str = DEFAULT_BASE
    agent_command: str = "claude"
    kill_switch: bool = False
    transitions_yaml: str | None = None
    config_dir: str = ""


class _SystemClock:
    """Wall-clock adapter satisfying :class:`~kanbanmate.ports.clock.Clock`.

    The trivial production clock: :meth:`now` returns :func:`time.time`. Tests inject a frozen or
    scripted clock instead, so this never needs to be configurable.
    """

    def now(self) -> float:
        """Return the current POSIX timestamp.

        Returns:
            Seconds since the Unix epoch (``time.time()``).
        """
        return time.time()


def build_deps(config: WiringConfig) -> Deps:
    """Construct every concrete adapter and assemble the :class:`Deps` bundle.

    The GitHub client satisfies ``BoardReader``, ``BoardWriter`` AND ``PullRequests`` (the Cancel
    teardown's PR-close port, DESIGN §8.2), so a single instance is wired into all three slots.
    The filesystem store, git-worktree workspace, tmux sessions adapter, and system clock fill
    the remaining ports.

    Args:
        config: The runtime configuration naming the token, board, repo, clone, and root.

    Returns:
        A fully wired :class:`Deps` the command actions can execute against.
    """
    board = GithubClient(config.token, project_id=config.project_id, repo=config.repo)
    store = FsStateStore(Path(config.kanban_root) if config.kanban_root else None)
    workspace = GitWorktreeWorkspace(
        config.clone_dir, repo=config.repo, kanban_root=config.kanban_root
    )
    sessions = TmuxSessions()
    clock = _SystemClock()
    return Deps(
        board_writer=board,
        board_reader=board,
        workspace=workspace,
        sessions=sessions,
        store=store,
        clock=clock,
        # One client, three ports: the same instance backs the PR-close port the
        # Cancel teardown uses (DESIGN §8.2), mirroring the board_writer wiring.
        pull_requests=board,
        base=config.base,
        agent_command=config.agent_command,
        repo=config.repo,
        # The session-end shim appended after the launched claude command (DESIGN §8.3). The
        # installed console-script ``kanban-session-end`` resolves on PATH (pyproject
        # [project.scripts]); explicit even though Deps defaults it.
        session_end_bin="kanban-session-end",
        # The project's .claude dir the launch COPIES skills/commands/agents from into each
        # worktree (phase 14.6); empty disables provisioning. Mirrors how ``repo``/``clone_dir``
        # are threaded.
        config_dir=config.config_dir,
        # One client, now four ports: the same instance backs the rolling status-update reporter
        # (the live dashboard, phase-24 §24.3), so it is wired into this slot too. The board id it
        # posts on is threaded alongside (the reporter ``create``s on it).
        status_reporter=board,
        project_id=config.project_id,
    )


def build_tick_config(config: WiringConfig) -> TickConfig:
    """Parse the column model and build the per-tick policy inputs.

    Args:
        config: The runtime configuration carrying the raw ``columns.yml``, the kill-switch,
            and optionally the raw ``transitions.yml``.

    A whitelist is ALWAYS supplied (DESIGN §8.0.6): the explicit ``transitions.yml`` when the clone
    ships one, otherwise the built-in :data:`~kanbanmate.core.transitions_defaults.DEFAULT_TRANSITIONS`
    (the shipped PoC flow). The daemon NEVER ticks without a whitelist — a missing file falls back to
    the default whitelist, never to a column model.

    Returns:
        A :class:`~kanbanmate.app.tick.TickConfig` ready for :func:`~kanbanmate.app.tick.tick`.

    Raises:
        ValueError: When ``config.transitions_yaml`` is set but malformed (fail-closed — the
            daemon refuses to tick with an invalid whitelist rather than launch un-whitelisted).
    """
    if config.transitions_yaml is not None:
        try:
            transitions = load_transitions(config.transitions_yaml)
        except Exception as exc:
            raise ValueError(f"Failed to parse transitions.yml: {exc}") from exc
    else:
        # No transitions.yml on the clone → fall back to the built-in PoC flow so a
        # whitelist is ALWAYS present (DESIGN §8.0.6); never leave it None / a column model.
        transitions = default_transition_config()
    # transitions.yml is the AUTHORITATIVE config surface for the cap + move-rate (#4): an operator
    # editing ``defaults:`` in transitions.yml must take effect. Before #4 the wiring read these
    # ONLY off columns.yml BoardDefaults, so the live rendered transitions.yml defaults block was
    # DEAD CONFIG — an operator's edit there was silently ignored. The parsed TransitionConfig is
    # ALWAYS present (the explicit file, or the default fallback whitelist which itself carries the
    # rendered template defaults), so its cap/rate are always the source of truth. The columns.yml
    # BoardDefaults is now only a documented fallback (its block is demoted to a commented note in
    # the template) — there is ONE authoritative surface.
    return TickConfig(
        columns=load_columns(config.columns_yaml),
        kill_switch=config.kill_switch,
        transitions=transitions,
        concurrency_cap=transitions.concurrency_cap,
        move_rate_limit_per_hour=transitions.move_rate_limit_per_hour,
    )


def run_one_tick(
    config: WiringConfig,
    state: PersistedState | None = None,
) -> tuple[TickResult, PersistedState]:
    """Wire dependencies and run exactly one :func:`~kanbanmate.app.tick.tick` cycle.

    A convenience the daemon loop and ``kanban poll --once`` (Phase 1.12) call: it builds the
    adapter bundle + tick config from ``config`` and drives a single reconciliation pass. The
    returned :class:`~kanbanmate.app.tick.PersistedState` is threaded back into the next call,
    which is what makes the loop idempotent.

    Args:
        config: The runtime configuration to wire from.
        state: The diff baseline carried over from a previous tick; a fresh
            :class:`~kanbanmate.app.tick.PersistedState` when ``None`` (first tick / cold start).

    Returns:
        A ``(TickResult, PersistedState)`` pair: the cycle summary and the next baseline.
    """
    deps = build_deps(config)
    tick_config = build_tick_config(config)
    return tick(deps, tick_config, state or PersistedState())
