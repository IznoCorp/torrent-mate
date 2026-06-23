"""Parse structured fields the Design/Plan agents write into the ticket body.

Pure functional core — imports only :mod:`re`, no I/O (DESIGN §3.2).  A
Design agent writes ``**codename**: <value>`` / ``**design**: <path>``, then a
Plan agent writes ``**plans**: <path1>, <path2>, ...``.  Later agents read
those markers back so the ``{{codename}}`` / ``{{design_path}}`` /
``{{plan_paths}}`` placeholders fill correctly in launch prompts.

Ported faithfully from the PoC at
``PersonalScraper/.claude/skills/kanban/kanbanmate/runner.py``
(:func:`parse_ticket_fields`).
"""

from __future__ import annotations

import re

_TICKET_FIELD = re.compile(r"^\*\*(\w+)\*\*:\s*(.+)$", re.MULTILINE)
"""Regex for ``**key**: value`` Markdown-bold field markers.

Each line has the exact form ``**key**: value`` (bold-key syntax).  Keys
are case-sensitive and must be ``\\w+`` (word characters only).  The regex is
anchored at line start and compiled with :data:`re.MULTILINE`.
"""


def parse_ticket_fields(body: str | None) -> dict[str, str]:
    """Extract structured fields the Design/Plan agents write into the ticket body.

    The Design step writes::

        **codename**: my-feature
        **design**: docs/features/my-feature/DESIGN.md

    The Plan step writes::

        **plans**: docs/plan-1.md, docs/plan-2.md

    The Triage step writes::

        **track**: express

    Each line has the exact form ``**key**: value`` (bold-key Markdown syntax).
    Keys are case-sensitive; unknown keys are silently ignored.  The key mapping
    is:

    * ``**codename**`` → ``"codename"`` (verbatim string)
    * ``**design**`` → ``"design_path"`` (note the body key is *design* but
      the result key is *design_path* — the ``{{design_path}}`` placeholder
      convention)
    * ``**plans**`` → ``"plan_paths"`` (body key *plans* → result *plan_paths*;
      each comma-separated path is stripped and re-joined with ``", "`` so the
      result is a single string ready for the ``{{plan_paths}}`` placeholder)
    * ``**track**`` → ``"track"`` (verbatim string; lane name from triage)

    Missing markers default to the empty string ``""`` — a first-contact ticket
    with no markers fills every key with ``""`` and the launch prompt still
    builds (back-compat: the Design agent does not reference these fields).

    Args:
        body: The GitHub issue body (Markdown text).  ``None`` is treated as
            the empty string (no crash).

    Returns:
        A dict with exactly four keys:

        * ``codename`` (:class:`str`) — the codename, or ``""``
        * ``design_path`` (:class:`str`) — the design document path, or ``""``
        * ``plan_paths`` (:class:`str`) — comma-joined plan paths, or ``""``
        * ``track`` (:class:`str`) — the lane name (express/lite/full), or ``""``
    """
    result: dict[str, str] = {"codename": "", "design_path": "", "plan_paths": "", "track": ""}
    for m in _TICKET_FIELD.finditer(body or ""):
        key = m.group(1).strip()
        val = m.group(2).strip()
        if key == "codename":
            result["codename"] = val
        elif key == "design":
            result["design_path"] = val
        elif key == "plans":
            # Normalise: "path1, path2" → strip each part, re-join ", ".
            parts = [p.strip() for p in val.split(",") if p.strip()]
            result["plan_paths"] = ", ".join(parts)
        elif key == "track":
            result["track"] = val
    return result
