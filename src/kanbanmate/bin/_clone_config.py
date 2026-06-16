"""Shared per-clone config loaders for the kanban-* agent helpers (DESIGN §8 / §13).

Several leaf entrypoints (``kanban-move``, ``kanban-session-end``) need the SAME three
per-clone config reads: the sole registered project, the clone's column model, and the
clone's transition whitelist (or the built-in :data:`DEFAULT_TRANSITIONS` fallback). These
loaders previously lived in ``bin/kanban_move.py`` and were duplicated by hand into the
session-end auto-advance backstop (the hybrid-flow batch). Lifting them here gives ONE source
of truth so the two leaves import the same helpers (DRY; keeps each leaf small under the
1000-LOC ceiling), and keeps ``bin/kanban_move.py`` importing them for back-compat.

It also hosts :func:`auto_advance_target`, the pure ``"auto:<col>" -> "<col>"`` parser the
session-end launch-stage backstop uses to decide whether a clean-done stage carries an
``advance:auto:<col>`` directive the engine must honour (DESIGN §13 hybrid flow).

This is a leaf helper module (DESIGN §3.2): pure config reads + a pure string parse, no GitHub
network. It imports ``cli.init`` + ``core.*`` only (the same imports the two leaf entrypoints
already carry), so it adds no new layering cycle.
"""

from __future__ import annotations

from pathlib import Path

from kanbanmate.bin._pin import _registry_root
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


def resolve_entry() -> ProjectEntry:
    """Resolve the single registered project from the per-clone registry.

    v1 runs one repo per clone (DESIGN §4.3), so the registry must hold exactly one
    entry; anything else is an operator misconfiguration we surface loudly. The registry is read
    from the runtime root resolved by :func:`~kanbanmate.bin._pin._registry_root` (``$KANBAN_ROOT``
    when set, else the ~/.kanban default — the km-worktree-helper-root fix, #1).

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


def load_clone_columns(entry: ProjectEntry) -> dict[str, Column]:
    """Load the per-clone column model from ``<clone>/.claude/kanban/columns.yml``.

    ``kanban init`` copies the board's ``columns.yml`` into the clone (DESIGN §4.3); the
    anti-loop guard (``kanban-move``) and the auto-advance backstop (``kanban-session-end``) read
    it back here so a directive/CLI ``target`` given as a column ``key`` resolves to its display
    ``name`` — the name :meth:`~kanbanmate.adapters.github.client.GithubClient.move_card` matches
    the Status options against (DESIGN §8.0.5 / §9).

    Args:
        entry: The resolved project registry entry (carries the clone path).

    Returns:
        A mapping of column ``key`` to its :class:`~kanbanmate.core.domain.Column`.

    Raises:
        FileNotFoundError: When the clone has no ``columns.yml`` (clone not initialised).
    """
    columns_path = Path(entry.clone) / CLONE_COLUMNS_RELPATH
    return load_columns(columns_path.read_text(encoding="utf-8"))


def load_clone_transitions(entry: ProjectEntry) -> TransitionConfig:
    """Load the per-clone transition whitelist from ``<clone>/.claude/kanban/transitions.yml``.

    The anti-loop guard (DESIGN §8.0.5) keys on the launch-target columns of this
    whitelist, and the auto-advance backstop reads its ``move_rate_limit_per_hour``, so both must
    read the SAME config the daemon ticks against. Mirrors the daemon's resolution
    (``daemon/loop.py``): the explicit ``transitions.yml`` when the clone ships one, else the
    built-in :data:`~kanbanmate.core.transitions_defaults.DEFAULT_TRANSITIONS` fallback (the
    no-``transitions.yml`` path, DESIGN §8.0.6) — a whitelist is ALWAYS supplied, so the readers
    never silently degrade to "anything allowed" / a missing rate limit.

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


def auto_advance_target(advance: str) -> str | None:
    """Return the ``<col>`` of an ``"auto:<col>"`` advance directive, else ``None`` (DESIGN §13).

    The hybrid-flow launch-stage backstop in ``kanban-session-end`` honours the persisted
    ``advance:auto:<col>`` directive a launch stage carries: a clean-done stage whose ``advance``
    is ``"auto:<col>"`` is auto-advanced to ``<col>`` by the engine; ``"stop"`` (or any non-auto
    value) means the card STOPS (the human-review gates: Plan→Planned, PRCI→Review). This pure
    parser mirrors ``app/script_route._route_success``'s ``advance.startswith("auto:")`` slice so
    the SCRIPT-gate path and the LAUNCH-stage backstop read the directive identically.

    Args:
        advance: The persisted ``advance`` directive (``"auto:<col>"`` | ``"stop"`` | ``""``).

    Returns:
        The stripped ``<col>`` when ``advance`` is ``"auto:<col>"`` with a non-empty target, else
        ``None`` (a ``"stop"``/empty/malformed directive → no engine move).
    """
    if not advance.startswith("auto:"):
        return None
    target = advance[len("auto:") :].strip()
    return target or None


__all__ = [
    "auto_advance_target",
    "load_clone_columns",
    "load_clone_transitions",
    "resolve_entry",
]
