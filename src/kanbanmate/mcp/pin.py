"""Pure pin-mismatch guard for the MCP write surface (conduit DESIGN §7).

The worktree-launched server is pinned to the agent's OWN issue number (supplied at launch via
``--issue``). Every write tool first calls :func:`pin_violation`: when the requested write target is
not the pinned issue it returns a friendly refusal message naming both issues, and the tool returns
that refusal performing ZERO I/O.

This mirrors the comparison ``bin/_pin.check_pin`` does (``bin/_pin.py:244-252``) but is a
shell-local one-line ``!=`` — the ``mcp`` layer may NOT import ``bin/_pin`` (forbidden by the
downward-only layering guard, DESIGN §3.1) and does not need to: the pinned value is the launch
``--issue``, so there is no forbidden-layer *value* to import, only the comparison itself.

For defense-in-depth, :func:`read_worktree_pin` re-reads the worktree pin FILE the bins pin on
(``<worktree>/.claude/kanban-issue``, written by :func:`kanbanmate.adapters.perms.write_issue_pin`
at provision time) so ``server.main`` can assert it agrees with the launch ``--issue`` (a mismatch
means the server was misconfigured against the worktree it runs in — it refuses to start). This is a
pure filesystem read, SDK-free + unit-testable; it duplicates the bare file name (``.claude/
kanban-issue``) rather than importing ``bin/_pin.find_pinned_issue`` (the forbidden layer).
"""

from __future__ import annotations

from pathlib import Path

# The pin file's name under a worktree's ``.claude/`` dir. Kept in lock-step with
# :data:`kanbanmate.bin._pin._PIN_DIRNAME` / ``_PIN_FILENAME`` (``.claude/kanban-issue``) and
# :data:`kanbanmate.adapters.perms.ISSUE_PIN_RELPATH`; duplicated here as a bare leaf so the ``mcp``
# layer reads the pin without importing ``bin/_pin`` (forbidden by the layering guard, DESIGN §3.1).
_PIN_DIRNAME = ".claude"
_PIN_FILENAME = "kanban-issue"


def read_worktree_pin(start: Path | None = None) -> int | None:
    """Walk up from ``start`` (default cwd) to read the worktree's pinned issue number, or ``None``.

    Searches ``<dir>/.claude/kanban-issue`` at ``start`` and each ancestor up to the filesystem
    root (mirrors :func:`kanbanmate.bin._pin.find_pinned_issue`, which the ``mcp`` layer may not
    import). The agent's shell runs WITH the worktree as its cwd, so the first pin found on the way
    up is the launched ticket's. A malformed / empty / unreadable pin file is treated as ABSENT
    (returns ``None``) — a corrupt pin must not hard-block; the caller's equality check enforces the
    pin only when it IS present and valid.

    Args:
        start: The directory to start the upward search from; defaults to the current working
            directory.

    Returns:
        The pinned issue number when a valid pin file is found on the ancestor chain, else
        ``None`` (no pin file present — the caller proceeds on ``--issue``).
    """
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        pin = directory / _PIN_DIRNAME / _PIN_FILENAME
        if not pin.is_file():
            continue
        try:
            return int(pin.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            # Unreadable / non-integer pin → treat as absent (a corrupt pin must not hard-block).
            return None
    return None


def pin_violation(requested: int, pinned: int) -> str | None:
    """Return a refusal message when ``requested`` != ``pinned`` write target, else ``None``.

    Args:
        requested: The issue number the write tool was asked to act on.
        pinned: The server's pinned issue number (the agent's own ticket, from ``--issue``).

    Returns:
        A friendly refusal string naming both issues when they differ; ``None`` when they match
        (the write may proceed).
    """
    if requested != pinned:
        return (
            f"refusing to write to #{requested}: this MCP server is pinned to #{pinned} "
            f"(an agent may only act on its own ticket — see conduit DESIGN §7)"
        )
    return None
