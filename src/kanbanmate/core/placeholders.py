"""Fill ``{{key}}`` / ``{{a.b}}`` placeholders in a prompt template.

Pure functional core — imports only :mod:`re` and :mod:`collections.abc.Mapping`,
no I/O (DESIGN §3.2).  Fails loud on unknown keys so a launch prompt referencing a
placeholder absent from the context never launches a half-filled agent.

Ported faithfully from the PoC at
``PersonalScraper/.claude/skills/kanban/kanbanmate/placeholders.py``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

_TOKEN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
"""Token grammar for ``{{key}}`` / ``{{a.b}}`` placeholders.

Whitespace is tolerated inside the braces (e.g. ``{{ x }}``).  The captured
group is a dotted path over ``[\\w.]`` — each segment must be ``\\w+``.
"""


def _resolve(path: str, ctx: Mapping[str, object]) -> object:
    """Walk a dotted *path* through the context mapping.

    At each segment, if the current node is not a :class:`~collections.abc.Mapping`
    or the segment is absent, a :exc:`KeyError` is raised for the **whole** *path*
    (not just the missing segment), mirroring the PoC's fail-loud contract so a
    half-resolved placeholder cannot slip through.

    Args:
        path: Dotted key path, e.g. ``"ticket.title"`` or ``"code"``.
        ctx: The substitution context mapping.

    Returns:
        The resolved value (may be of any type; :func:`fill` coerces it with
        :func:`str`).

    Raises:
        KeyError: If any segment of *path* is absent from the context, or if
            an intermediate node is not a mapping.
    """
    cur: object = ctx
    for part in path.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            raise KeyError(path)
        cur = cur[part]
    return cur


def fill(template: str, ctx: Mapping[str, object]) -> str:
    """Replace every ``{{key}}`` / ``{{a.b}}`` placeholder with its value from *ctx*.

    Uses :data:`_TOKEN` to find tokens and :func:`_resolve` to walk the context.
    Non-string values are coerced via :func:`str`.  A :exc:`KeyError` from a
    missing key propagates — the caller must ensure the context supplies every
    placeholder the template references.

    Args:
        template: A prompt template string containing zero or more
            ``{{placeholder}}`` tokens.
        ctx: The substitution context mapping.

    Returns:
        The template with every token replaced by its resolved value.

    Raises:
        KeyError: If any placeholder references a key absent from *ctx*.
    """
    return _TOKEN.sub(lambda m: str(_resolve(m.group(1), ctx)), template)


# The canonical placeholder set the dispatch context supplies (app/launch_context.py:92-113).
# Single source of truth for bridge's rich prompt editor (GET /api/placeholders). DRIFT GUARD:
# tests/core/test_placeholders.py pins these names to the launch context — change both together.
KNOWN_PLACEHOLDERS: dict[str, str] = {
    "code": "The ticket's issue number (bare int, e.g. 9).",
    "title": "The ticket title.",
    "branch": "The per-ticket WIP / worktree branch name.",
    "ticket_body": "The issue body markdown.",
    "script_output": "The last failing check's output (CI gate / fix-CI stages).",
    "issue_body": "The first cross-referenced linked-issue body.",
    "comments": "The joined ticket comment history.",
    "codename": "The feature codename parsed from the ticket body.",
    "design_path": "Path to the feature DESIGN.md (set after design).",
    "plan_paths": "Path(s) to the implementation plan file(s).",
    "base_clone": "The base clone path (reserved; empty unless set).",
    "dev_repo_path": "The operator's dev-clone path (reserved; empty unless set).",
}


def unknown_placeholders(template: str) -> list[str]:
    """Return the distinct unknown placeholder names referenced by *template*.

    A placeholder is "unknown" when the FIRST dotted segment of its key is not in
    :data:`KNOWN_PLACEHOLDERS`. Names are returned in first-seen order (deduplicated),
    backing the editor's "N unknown placeholders" finding.

    Args:
        template: A prompt template containing zero or more ``{{key}}`` tokens.

    Returns:
        The unknown top-level placeholder names, in first-seen order.
    """
    seen: list[str] = []
    for match in _TOKEN.finditer(template):
        head = match.group(1).split(".", 1)[0]
        if head not in KNOWN_PLACEHOLDERS and head not in seen:
            seen.append(head)
    return seen
