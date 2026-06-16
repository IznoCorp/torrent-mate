"""Pure composition of the launched agent's shell env-export prefix (DESIGN §8.3 / multiproject §7).

The launched ``claude`` command is a shell line of the form::

    export KANBAN_ROOT=...; export KANBAN_PROJECT_ID=...; export PATH=...; claude … ; kanban-session-end

The PREFIX (the ``export …; `` chain) is built here as a PURE function of the launch context — no
I/O, no clock — so it stays unit-testable and ``core`` stays leaf. The imperative ``app`` layer
(``LaunchAction._agent_command``) supplies the already-quoted PATH segment + the resolved
``kanban_root`` / ``project_id`` and appends the bare ``claude`` command. Keeping the composition in
``core`` (not ``app``) also relieves the at-ceiling ``app/actions.py`` (DESIGN §9 — new code in NEW
modules; the at-ceiling files must not grow).

Quoting note: each VALUE is quoted by the caller (it holds the worktree path / root / node id) so a
path with spaces stays one shell token; ``"$PATH"`` inside the PATH segment is deliberately left
expandable by the caller. This function only concatenates the already-prepared segments in the
canonical order.
"""

from __future__ import annotations

import shlex


def build_env_prefix(
    *,
    kanban_root: str,
    project_id: str,
    multi_project: bool,
    path_segment: str,
) -> str:
    """Return the ``export …; `` shell prefix for the launched agent command (pure).

    Composes the canonical export chain in order: ``KANBAN_ROOT`` (only when non-empty — the default
    ~/.kanban daemon keeps a byte-identical command), then ``KANBAN_PROJECT_ID`` (ONLY in a
    multi-project deployment with a project id — so the helpers resolve the right per-project store
    sub-root; N=1 omits it for a byte-identical command), then the caller-supplied PATH segment.

    Args:
        kanban_root: The launching daemon's runtime root; ``""`` omits the ``KANBAN_ROOT`` export
            (the default ~/.kanban daemon — byte-identical command line).
        project_id: The project node id; exported as ``KANBAN_PROJECT_ID`` only when ``multi_project``
            is set and this is non-empty (the multi-project signal; the km-root invariant extended).
        multi_project: Whether this is a multi-project deployment (N>1 enabled projects on one
            daemon). False (N=1) omits the project export for a byte-identical single-project command.
        path_segment: The already-composed, already-quoted ``export PATH=…; `` segment the caller
            built (it needs the absolute worktree bin dir). Appended verbatim.

    Returns:
        The concatenated ``export …; `` prefix (empty exports omitted), ready to prepend to the bare
        ``claude`` command.
    """
    root_prefix = f"export KANBAN_ROOT={shlex.quote(kanban_root)}; " if kanban_root else ""
    project_prefix = (
        f"export KANBAN_PROJECT_ID={shlex.quote(project_id)}; "
        if multi_project and project_id
        else ""
    )
    return f"{root_prefix}{project_prefix}{path_segment}"
