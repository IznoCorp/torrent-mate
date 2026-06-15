"""Shared worktree issue-pin reader for the kanban-* agent helpers (R1 enforcement, §29.1).

A launched agent's worktree carries a pin file (``<worktree>/.claude/kanban-issue``, written by
:func:`kanbanmate.adapters.perms.write_issue_pin` at provision time) naming the single issue the
agent was launched for. Every write-capable helper (``kanban-update-body`` / ``kanban-move`` /
``kanban-comment`` / ``kanban-progress``) consults this pin and REFUSES a mismatched ``<issue>``
argument, so a misattributed agent can never act on another ticket. The pin is the mechanism R1
("only touch your own ticket") needs — prompt wording alone cannot enforce it (phase 29 verdict).

This is a leaf helper (DESIGN §3.2): pure filesystem reads, no GitHub network, no other-layer
imports. When no pin file is found (the operator runs a helper by hand outside any worktree), the
helpers fall back to the UNPINNED behaviour (current contract) — the pin only constrains a
launched agent, never an operator's manual invocation.
"""

from __future__ import annotations

from pathlib import Path

# The pin file's name under a worktree's ``.claude/`` dir. Kept in lock-step with
# :data:`kanbanmate.adapters.perms.ISSUE_PIN_RELPATH` (``.claude/kanban-issue``); duplicated here as
# a bare leaf so the bin layer reads the pin without importing the adapters layer.
_PIN_DIRNAME = ".claude"
_PIN_FILENAME = "kanban-issue"


def parse_issue_arg(raw: str) -> int:
    """Parse a helper's ``<issue>`` argument, stripping a defensive leading ``#`` (defect 3).

    Shipped prompts fill ``{{code}}`` with the bare issue number, but an agent may still type
    ``kanban-move #151 'PR/CI'`` by habit. A leading ``#`` makes the token a bash comment when
    unquoted, and ``int('#151')`` raises — so every kanban-* helper routes its issue argument
    through this single parser, which strips ONE optional leading ``#`` (and surrounding
    whitespace) before the integer conversion. The bare-int fill stays the contract; this is the
    belt-and-suspenders the audit asks for ("do both defensively").

    Args:
        raw: The raw ``<issue>`` token from the command line (e.g. ``"151"`` or ``"#151"``).

    Returns:
        The parsed issue number.

    Raises:
        ValueError: When the token (after stripping a leading ``#``) is not an integer — the
            caller surfaces this as a usage error, never a traceback.
    """
    return int(raw.strip().lstrip("#"))


def find_pinned_issue(start: Path | None = None) -> int | None:
    """Walk up from ``start`` (default cwd) to find the worktree's pinned issue number.

    Searches ``<dir>/.claude/kanban-issue`` at ``start`` and each ancestor up to the filesystem
    root. The agent's shell runs WITH the worktree as its working directory, so the first pin
    found on the way up is the launched ticket's. A malformed or empty pin file is treated as
    ABSENT (returns ``None``) — a corrupt pin must not hard-block a manual invocation, and the
    caller's mismatch check is what enforces the pin when it IS present and valid.

    Args:
        start: The directory to start the upward search from; defaults to the current working
            directory.

    Returns:
        The pinned issue number when a valid pin file is found on the ancestor chain, else
        ``None`` (no pin — unpinned fallback).
    """
    here = (start or Path.cwd()).resolve()
    # Iterate ``here`` itself plus every parent up to the root (``here`` is included in ``parents``
    # only via this explicit chain, so prepend it).
    for directory in (here, *here.parents):
        pin = directory / _PIN_DIRNAME / _PIN_FILENAME
        if not pin.is_file():
            continue
        try:
            text = pin.read_text(encoding="utf-8").strip()
            return int(text)
        except (OSError, ValueError):
            # Unreadable / non-integer pin → treat as absent (a corrupt pin must not hard-block).
            return None
    return None


def check_pin(issue: int, *, start: Path | None = None) -> str | None:
    """Verify ``issue`` matches the worktree pin (when present); return an error message or ``None``.

    When a valid pin file is found and it names a DIFFERENT issue than ``issue``, a clear,
    fail-loud error string is returned so the calling helper can print it to stderr and exit
    non-zero WITHOUT performing any GitHub write. When the pin matches, or no pin file is present
    (operator running the helper outside a worktree — the unpinned fallback), ``None`` is returned
    and the helper proceeds.

    Args:
        issue: The ``<issue>`` argument the agent/operator passed to the helper.
        start: The directory to start the upward pin search from; defaults to the cwd.

    Returns:
        An error message string when the worktree is pinned to a DIFFERENT issue, else ``None``.
    """
    pinned = find_pinned_issue(start)
    if pinned is not None and pinned != issue:
        return (
            f"refusing to act on #{issue}: this worktree is PINNED to #{pinned} "
            f"(R1, §29.1) — an agent may only touch its own ticket"
        )
    return None
