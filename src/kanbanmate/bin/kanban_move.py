"""Agent helper: move a ticket's card to a non-triggering column (DESIGN §8).

``kanban-move <issue> <column>`` advances a ticket's Status to ``column`` via
:meth:`~kanbanmate.adapters.github.client.GithubClient.move_card`. ``column`` may be given
as either the stable column ``key`` or its human-readable ``name`` — both resolve to the same
:class:`~kanbanmate.core.domain.Column`.

**Anti-loop guard (DESIGN §8.0.5, MANDATORY).** An agent must never move a card into a
**launch-transition target** — a column that is the destination of a prompt-bearing whitelisted
transition. Moving a card into such a column would re-fire that transition's launch (the agent's
own stage, or another), creating an orchestration loop. The refusal is keyed on the **transition
whitelist** (``transitions.yml``), NOT on a static column class: this helper loads the per-clone
whitelist (or the built-in ``DEFAULT_TRANSITIONS`` fallback when the clone ships none — the same
fallback the daemon uses), computes its launch-target column set, and **refuses** with a clear
non-zero error when the resolved target is in that set — *before* any GitHub call.

**Merge stays human (DESIGN §8.0.5).** Because the refusal keys on prompt-bearing transitions, the
``Review → Merge`` row — a human-authorised SCRIPT gate with **no prompt** — does NOT make ``Merge``
a launch target. So an agent may freely move a card into ``Merge``; the merge boundary rests on
Merge being unreachable as a launch target + branch protection + the ``gh pr merge`` ban
(CLAUDE.md), never on an autonomous self-advance into Merge.

This is a leaf entrypoint (DESIGN §3.2): it wires the GitHub adapter from the loaded token and
the per-clone registry, reads the ticket's ``item_id`` from the persisted store, then delegates
the move to the board adapter (which applies the mandatory connect+read timeouts on every
request). On bad/missing arguments or a launch-target destination it fails cleanly (non-zero exit,
clear stderr) and never lets an unexpected error crash the calling agent shell.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.github.token import load_token
from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.bin._pin import _registry_root, check_pin, parse_issue_arg, resolve_kanban_root
from kanbanmate.cli.init import (
    CLONE_COLUMNS_RELPATH,
    CLONE_TRANSITIONS_RELPATH,
    ProjectEntry,
    _load_registry,
    _projects_path,
)
from kanbanmate.core.columns import load_columns
from kanbanmate.core.domain import Column
from kanbanmate.core.transitions import TransitionConfig, load_transitions
from kanbanmate.core.transitions_defaults import default_transition_config

_PROG = "kanban-move"


def _resolve_entry() -> ProjectEntry:
    """Resolve the single registered project from the per-clone registry.

    v1 runs one repo per clone (DESIGN §4.3), so the registry must hold exactly one
    entry; anything else is an operator misconfiguration we surface loudly. The registry is read
    from the runtime root resolved by :func:`_registry_root` (``$KANBAN_ROOT`` when set, else the
    ~/.kanban default — the km-worktree-helper-root fix, #1).

    Returns:
        The sole :class:`~kanbanmate.cli.init.ProjectEntry`.

    Raises:
        RuntimeError: When the registry does not hold exactly one project.
    """
    projects_path = _projects_path(_registry_root())
    registry = _load_registry(projects_path)
    if len(registry) != 1:
        raise RuntimeError(
            f"expected exactly one registered project in {projects_path}, found {len(registry)}"
        )
    return next(iter(registry.values()))


def _load_clone_columns(entry: ProjectEntry) -> dict[str, Column]:
    """Load the per-clone column model from ``<clone>/.claude/kanban/columns.yml``.

    ``kanban init`` copies the board's ``columns.yml`` into the clone (DESIGN §4.3); the
    anti-loop guard reads it back here so a CLI ``target`` given as a human-readable column
    ``name`` resolves to its stable column ``key`` — the key the transition whitelist's
    launch targets are expressed in (DESIGN §8.0.5).

    Args:
        entry: The resolved project registry entry (carries the clone path).

    Returns:
        A mapping of column ``key`` to its :class:`~kanbanmate.core.domain.Column`.

    Raises:
        FileNotFoundError: When the clone has no ``columns.yml`` (clone not initialised).
    """
    columns_path = Path(entry.clone) / CLONE_COLUMNS_RELPATH
    return load_columns(columns_path.read_text(encoding="utf-8"))


def _load_clone_transitions(entry: ProjectEntry) -> TransitionConfig:
    """Load the per-clone transition whitelist from ``<clone>/.claude/kanban/transitions.yml``.

    The anti-loop guard (DESIGN §8.0.5) keys on the launch-target columns of this
    whitelist, so it must read the SAME config the daemon ticks against. Mirrors the
    daemon's resolution (``daemon/loop.py``): the explicit ``transitions.yml`` when
    the clone ships one, else the built-in :data:`DEFAULT_TRANSITIONS` fallback (the
    no-``transitions.yml`` path, DESIGN §8.0.6) — a whitelist is ALWAYS supplied, so
    the guard never silently degrades to "anything allowed".

    Args:
        entry: The resolved project registry entry (carries the clone path).

    Returns:
        The parsed :class:`~kanbanmate.core.transitions.TransitionConfig` — from the
        clone's ``transitions.yml`` when present, otherwise the default flow.
    """
    transitions_path = Path(entry.clone) / CLONE_TRANSITIONS_RELPATH
    if transitions_path.exists():
        return load_transitions(transitions_path.read_text(encoding="utf-8"))
    # No transitions.yml on the clone → the same DEFAULT_TRANSITIONS fallback the
    # daemon uses (DESIGN §8.0.6); never fall back to "no whitelist / anything goes".
    return default_transition_config()


def resolve_target_column(columns: dict[str, Column], target: str) -> Column:
    """Resolve a CLI ``target`` (a column ``key`` *or* ``name``) to its :class:`Column`.

    The operator/agent may name the destination by either its stable ``key`` (e.g.
    ``"Backlog"``) or its human-readable ``name`` (e.g. ``"In Progress"``). Both map to
    the same column.

    Args:
        columns: The loaded column model (keyed by column ``key``).
        target: The destination column, given as a ``key`` or a ``name``.

    Returns:
        The matching :class:`Column`.

    Raises:
        KeyError: When ``target`` matches no column key or name.
    """
    if target in columns:
        return columns[target]
    for column in columns.values():
        if column.name == target:
            return column
    known = ", ".join(sorted(columns)) or "(none)"
    raise KeyError(f"unknown column {target!r}; known columns: {known}")


def main(argv: list[str] | None = None) -> int:
    """Entry point: move a ticket's card to a non-launch-target column.

    Resolves the single registered project, loads the clone's column model (for name→key
    resolution) and its transition whitelist, and **refuses** (anti-loop, DESIGN §8.0.5) when the
    resolved target column is a **launch-transition target** (the destination of a prompt-bearing
    whitelisted transition). For any other target it reads the ticket's ``item_id`` from the
    persisted store and calls
    :meth:`~kanbanmate.adapters.github.client.GithubClient.move_card`, which applies the
    mandatory connect+read timeouts on every request.

    Failure handling: a usage error exits ``2``; a launch-target destination or any wiring/board
    failure is reported to stderr and exits ``1`` — never a traceback that would crash the calling
    agent.

    Args:
        argv: Optional argument vector (excluding the program name); defaults to
            :data:`sys.argv` ``[1:]``. Expects exactly ``<issue> <column>``.

    Returns:
        ``0`` on a successful move, ``2`` on a usage error, ``1`` on a launch-target destination
        or any other failure.
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    if len(raw_argv) != 2:
        print(f"usage: {_PROG} <issue> <column>", file=sys.stderr)
        return 2
    try:
        issue = parse_issue_arg(raw_argv[0])
    except ValueError:
        print(f"{_PROG}: issue must be an integer, got {raw_argv[0]!r}", file=sys.stderr)
        return 2
    target = raw_argv[1]

    # Pin enforcement (R1, §29.1): refuse a mismatched issue when the worktree is pinned (absent
    # pin → unpinned operator use). Checked BEFORE any GitHub call so no move is ever issued.
    pin_error = check_pin(issue)
    if pin_error is not None:
        print(f"{_PROG}: {pin_error}", file=sys.stderr)
        return 1

    try:
        entry = _resolve_entry()
        columns = _load_clone_columns(entry)
        # Resolve the CLI target (a key OR a human name) to its Column so we test
        # membership by the stable column KEY — the same key the transition whitelist
        # uses for its launch targets.
        column = resolve_target_column(columns, target)
        launch_targets = _load_clone_transitions(entry).launch_target_columns()
        # Anti-loop guard (DESIGN §8.0.5): an agent may NEVER move a card into a launch-transition
        # target — re-entering such a column would re-fire its prompt-bearing transition (the
        # agent's own stage or another) and form an orchestration loop. The refusal is keyed on the
        # whitelist (a launch target), NOT a static column class. Refuse BEFORE any GitHub call so
        # no move_card is ever issued for a launch target.
        if column.key in launch_targets:
            print(
                f"{_PROG}: refusing to move #{issue} into "
                f"{column.name!r} (anti-loop, DESIGN §8.0.5) — a launch-transition target; "
                f"agents may only move cards into non-launch columns",
                file=sys.stderr,
            )
            return 1

        # The dispatcher records the ticket's ProjectV2Item id at launch; the move targets it.
        # Resolve the store root from $KANBAN_ROOT (#1 km-root fix); None → ~/.kanban (DESIGN §4.1).
        store = FsStateStore(resolve_kanban_root())
        state = store.load(issue)
        if state is None or not state.item_id:
            print(
                f"{_PROG}: no persisted item id for #{issue}; is the ticket in flight?",
                file=sys.stderr,
            )
            return 1

        client = GithubClient(load_token(), project_id=entry.project_id, repo=entry.repo)
        # move_card resolves the column NAME to the Status option id and runs the mutation; the
        # injected urllib transport applies the mandatory connect+read timeouts on every request.
        client.move_card(state.item_id, column.name)
        # Advance breadcrumb (DESIGN §8.1.d/.e): the agent advanced its OWN card, so drop a
        # breadcrumb keyed by the ISSUE number, SYNCHRONOUSLY before ``claude`` exits. This is
        # the proof the daemon's ✅-on-advance finalize (8.1.e) and session-end's ✅/⚠️ split
        # (8.1.f) rely on; the writer and readers MUST share the issue key (8.1.d invariant).
        #
        # Written in its OWN try/except (warn-not-abort): the move already landed on GitHub, so a
        # breadcrumb-write failure must NEVER abort the move — it only logs a warning to stderr.
        #
        # NO dedup / anti-loop marker is recorded for the agent's own forward move (port of OLD's
        # bug #2 note): the move MUST still produce the next poll diff so the daemon reacts to it.
        try:
            store.record_agent_advance(issue, now=time.time())
        except Exception as exc:  # noqa: BLE001 — warn-not-abort: the move already landed.
            print(
                f"{_PROG}: warning: could not record advance breadcrumb for #{issue}: {exc}",
                file=sys.stderr,
            )
    except Exception as exc:  # noqa: BLE001 — never crash the caller; report + exit non-zero.
        print(f"{_PROG}: {exc}", file=sys.stderr)
        return 1

    print(f"moved #{issue} -> {column.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
