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
from kanbanmate.ports.board import BoardReader, BoardWriter
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
        base: The integration base branch the per-ticket WIP branch is first created off.
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
        state_root: The PER-PROJECT store sub-root (ingress-multiproject §3.3). When non-empty the
            :class:`~kanbanmate.adapters.store.fs_store.FsStateStore` is rooted HERE
            (``<root>/projects/<safe(project_id)>``) instead of the bare ``kanban_root`` — so N>1
            projects driven by one daemon never collide on issue numbers (two repos can both carry
            ``#5``). Empty (the N=1 default) keeps the LEGACY FLAT layout (``<root>/state/...``), so
            an existing single-project deployed daemon sees no path change and needs no migration
            (the N=1 escape hatch). The runtime-root-level markers (lock, PAUSE, nudge,
            daemon.heartbeat) stay at ``kanban_root``; only the per-ticket store moves here.
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
    state_root: str = ""
    # ingress-multiproject §7: True in a MULTI-PROJECT deployment (N>1 enabled projects on one
    # daemon). Threaded onto :attr:`~kanbanmate.app.actions.Deps.multi_project` so the launch
    # exports ``KANBAN_PROJECT_ID`` + writes the worktree project pin (so the helpers resolve the
    # right per-project sub-root). False (the N=1 default) keeps the launched command byte-identical.
    multi_project: bool = False
    # ingress-multiproject §5: the project's effective ingress mode — ``"polling"`` (tight 10 s
    # cadence) or ``"webhook"`` (slow safety-sweep fallback + sub-second nudge). The daemon reads
    # these across its projects to pick the base poll cadence (the tightest any project needs). The
    # tick itself NEVER reads this — it always reconciles; ingress only sets how often. Default
    # ``"polling"`` keeps the historical 10 s cadence for any caller that does not set it.
    ingress: str = "polling"
    # anchor §4.2: the per-project board backend. "github" (default) keeps every live
    # daemon byte-identical until the operator opts in. "native" routes to NativeBoardBackend
    # one-way (native authority → GitHub mirror; board-view §4.3). "hybrid" adds GitHub→native
    # reconciliation each tick (board-sync) so cards can be moved on EITHER surface.
    board_backend: str = "github"
    # anchor §5: one-way GitHub mirror under native — default on so the GitHub Projects
    # board + status pill + Health field keep reflecting native placement after cutover.
    board_mirror: bool = True


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
    github = GithubClient(config.token, project_id=config.project_id, repo=config.repo)
    # Per-project store sub-root (ingress-multiproject §3.3): the per-ticket state store is rooted at
    # ``state_root`` when set (the N>1 ``<root>/projects/<safe(pid)>`` sub-root), else the bare
    # ``kanban_root`` (the N=1 legacy flat layout — zero path change for the deployed daemon).
    store_root = config.state_root or config.kanban_root
    # The daemon-wake nudge sentinel is DAEMON-LEVEL (one daemon, one sleep): it stays at the runtime
    # root even when the per-ticket store moves to a per-project sub-root (§3.2). When ``state_root``
    # is unset (N=1) the nudge root IS the store root → byte-identical to today.
    nudge_root = config.kanban_root if config.state_root else None
    store = FsStateStore(
        Path(store_root) if store_root else None,
        nudge_root=Path(nudge_root) if nudge_root else None,
    )
    # anchor §4.2: the board_backend switch — the ONLY place concrete adapter classes are named
    # (CLAUDE.md hexagonal rule). Default "github" keeps every live daemon byte-identical.
    board_reader: BoardReader
    board_writer: BoardWriter
    if config.board_backend in ("native", "hybrid"):
        from kanbanmate.adapters.board.native import NativeBoardBackend  # noqa: PLC0415
        from kanbanmate.adapters.store.fs_board import FsBoardStateStore  # noqa: PLC0415
        from kanbanmate.core.columns import load_columns  # noqa: PLC0415

        board_store = FsBoardStateStore(
            Path(store_root) if store_root else Path(config.kanban_root or "~/.kanban").expanduser()
        )
        col_map = load_columns(config.columns_yaml)
        columns = [col.key for col in col_map.values()]
        # Map column key → GitHub Status display name (used by the mirror to call move_card
        # with the option NAME, not the key — see GithubClient.move_card / field.options).
        _col_name_map: dict[str, str] = {col.key: col.name for col in col_map.values()}
        # "hybrid" = bidirectional (native authority + GitHub→native reconcile each tick); "native"
        # = one-way (native → GitHub mirror only). Both keep the mirror on so GitHub stays in sync.
        board_reader = board_writer = NativeBoardBackend(
            forge=github,
            store=board_store,
            columns=columns,
            option_name_for_key=lambda key: _col_name_map.get(key, key),
            mirror=github if config.board_mirror else None,
            hybrid=config.board_backend == "hybrid",
        )
    else:
        board_reader = board_writer = github
    workspace = GitWorktreeWorkspace(
        config.clone_dir, repo=config.repo, kanban_root=config.kanban_root
    )
    sessions = TmuxSessions()
    clock = _SystemClock()
    return Deps(
        board_writer=board_writer,
        board_reader=board_reader,
        workspace=workspace,
        sessions=sessions,
        store=store,
        clock=clock,
        # One client, three ports: the same instance backs the PR-close port the
        # Cancel teardown uses (DESIGN §8.2), mirroring the board_writer wiring.
        pull_requests=github,
        base=config.base,
        agent_command=config.agent_command,
        repo=config.repo,
        # The session-end shim appended after the launched claude command (DESIGN §8.3). The
        # installed console-script ``kanban-session-end`` resolves on PATH (pyproject
        # [project.scripts]); explicit even though Deps defaults it.
        session_end_bin="kanban-session-end",
        # The launching daemon's runtime root, exported as KANBAN_ROOT on the launched command so the
        # trailing ``; kanban-session-end`` AND the agent's kanban-* helpers target the CORRECT root
        # (the km-worktree-helper-root fix, #1). ``config.kanban_root`` is ``str | None`` → coerce
        # None to "" (the default ~/.kanban daemon needs no override; an empty value keeps the
        # launched command byte-identical).
        kanban_root=config.kanban_root or "",
        # The project's .claude dir the launch COPIES skills/commands/agents from into each
        # worktree (phase 14.6); empty disables provisioning. Mirrors how ``repo``/``clone_dir``
        # are threaded.
        config_dir=config.config_dir,
        # One client, now four ports: the same instance backs the rolling status-update reporter
        # (the live dashboard, phase-24 §24.3), so it is wired into this slot too. The board id it
        # posts on is threaded alongside (the reporter ``create``s on it).
        status_reporter=github,
        # One client, now a FIFTH port: the same instance backs the per-card Health reporter
        # (the custom chip carrying the operator's vocabulary — health-field), wired into this
        # slot too so the tick's fail-soft Health step can ensure the field + set per-card values.
        health_reporter=github,
        project_id=config.project_id,
        # The GithubClient also implements Seeder (create_issue / add_to_project) — threaded for the
        # cockpit ticket_create intent executor (PR3).
        seeder=github,
        # Multi-project marker (ingress-multiproject §7): drives the launch's KANBAN_PROJECT_ID
        # export + worktree project pin. False (N=1) keeps the launched command byte-identical.
        multi_project=config.multi_project,
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
    *,
    force_snapshot: bool = False,
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
        force_snapshot: Forwarded to :func:`~kanbanmate.app.tick.tick` (P2): when ``True`` the tick
            snapshots even on an unchanged probe (a nudge / fast-poll re-evaluation). Default
            ``False`` keeps the historical probe-gated behaviour.

    Returns:
        A ``(TickResult, PersistedState)`` pair: the cycle summary and the next baseline.
    """
    deps = build_deps(config)
    tick_config = build_tick_config(config)
    return tick(deps, tick_config, state or PersistedState(), force_snapshot=force_snapshot)
