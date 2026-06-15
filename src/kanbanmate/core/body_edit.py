"""Pure body-editing primitives for the ``kanban-update-body`` helper (§29.1).

Pure functional core — imports only :mod:`re`, no I/O (DESIGN §3.2). The ``kanban-update-body``
bin (a leaf entrypoint) reads an issue body + title over the network, applies one of these
transforms, validates the result, then patches it back. Keeping the transforms pure makes the
marker-preservation, section-append, and ``[CODE]`` coherence rules directly unit-testable without
touching GitHub.

The structured ``**key**: value`` markers (``**roadmap**`` / ``**codename**`` / ``**design**`` /
``**plans**``) are the binding chain between a ticket and its roadmap entry / feature artifacts
(DESIGN §9; :mod:`kanbanmate.core.ticket_fields` parses them back). ``--set-field`` rewrites a
single marker IN PLACE (or appends it when absent); ``--append-section`` appends free text under a
markdown heading WITHOUT touching any marker — the two write paths the hardened prompts route every
body write-back through.
"""

from __future__ import annotations

import re

# The bold-key markers a body write-back must PRESERVE (never silently drop). ``--append-section``
# only adds text below the existing body, so it preserves these by construction; ``--set-field``
# rewrites exactly one of them in place. Kept in lock-step with the keys
# :func:`kanbanmate.core.ticket_fields.parse_ticket_fields` recognises.
PRESERVED_MARKERS: tuple[str, ...] = ("roadmap", "codename", "design", "plans")

# A ``**key**: value`` marker line, anchored at line start (mirrors ``ticket_fields._TICKET_FIELD``
# but parameterised on a single key for the in-place rewrite). ``re.MULTILINE`` so ``^`` matches
# each physical line.
_MARKER_LINE = re.compile(r"^\*\*(\w+)\*\*:[^\n]*$", re.MULTILINE)

# The authoritative ``[CODE]`` bracket at the START of an issue title (``[CODE] Title``).
_TITLE_CODE = re.compile(r"^\s*\[([^\]]+)\]")


def set_field(body: str, key: str, value: str) -> str:
    """Rewrite the ``**key**: value`` marker IN PLACE (or append it when absent).

    When a ``**key**: …`` line already exists, its value is replaced in place (the FIRST
    occurrence — markers are single-valued). When absent, a new ``**key**: value`` marker is
    appended as its own paragraph at the end of the body, so the parser
    (:func:`kanbanmate.core.ticket_fields.parse_ticket_fields`) picks it up. All OTHER markers are
    left byte-identical.

    Args:
        body: The current issue body.
        key: The marker key to set (e.g. ``"roadmap"``, ``"design"``).
        value: The marker's new value (the rest of the line after ``: ``).

    Returns:
        The body with the single ``**key**: value`` marker set.
    """
    new_line = f"**{key}**: {value}"
    replaced = False

    def _sub(match: re.Match[str]) -> str:
        nonlocal replaced
        if replaced or match.group(1) != key:
            return match.group(0)
        replaced = True
        return new_line

    out = _MARKER_LINE.sub(_sub, body)
    if replaced:
        return out
    # Marker absent — append it as its own paragraph (blank-line separated when the body is
    # non-empty) so it parses as a standalone ``**key**: value`` line.
    if not body.strip():
        return new_line
    return body.rstrip("\n") + "\n\n" + new_line


def append_section(body: str, heading: str, text: str) -> str:
    """Append ``text`` under a markdown ``heading`` at the end of the body (markers untouched).

    The brainstorm output path (§29.4): the agent APPENDS its brainstorm under a ``## Brainstorm``
    heading rather than OVERWRITING the seeded feature description. The heading is written verbatim
    (the caller passes the full ``## Heading`` string), then a blank line, then the text. No
    existing marker or prose is removed — the original description + the ``**roadmap**`` line
    survive intact.

    Args:
        body: The current issue body.
        heading: The markdown heading to append under (verbatim, e.g. ``"## Brainstorm"``).
        text: The section body text (typically read from stdin).

    Returns:
        The body with the new heading + text appended.
    """
    section = f"{heading}\n\n{text.rstrip()}"
    if not body.strip():
        return section
    return body.rstrip("\n") + "\n\n" + section


def title_code(title: str) -> str | None:
    """Extract the authoritative ``[CODE]`` bracket from an issue ``title``.

    Args:
        title: The issue title (``[CODE] Title``).

    Returns:
        The bracketed code (stripped), or ``None`` when the title has no leading ``[…]`` bracket.
    """
    match = _TITLE_CODE.match(title)
    return match.group(1).strip() if match else None


def roadmap_marker(body: str) -> str | None:
    """Return the ``**roadmap**`` marker's value from ``body``, or ``None`` when absent.

    Args:
        body: The issue body to scan.

    Returns:
        The roadmap code (stripped), or ``None`` when no ``**roadmap**`` marker is present.
    """
    for match in _MARKER_LINE.finditer(body):
        if match.group(1) == "roadmap":
            # Recover the value after ``**roadmap**:`` (the regex matched the whole line).
            line = match.group(0)
            return line.split(":", 1)[1].strip()
    return None


def declares_dependency_on(linked_body: str, *, issue: int, code: str | None) -> bool:
    """Return whether ``linked_body`` declares a dependency ON this ticket (the #91 poisoning).

    The launch-prompt enrichment takes the FIRST cross-referenced issue's body as
    ``{{issue_body}}`` — but a cross-reference is direction-blind: a DOWNSTREAM dependent (e.g.
    ``[O1] … Depends on #91``) cross-references this ticket (#91) and would inject O1's feature
    text into #91's launch prompt as "linked context". That is the #91 root cause. This predicate
    detects the downstream direction so :meth:`_launch_context` can drop the body
    (``issue_body=""``): the linked body declares a dependency on US when it contains either
    ``Depends on #<this-issue>`` (the seed-rewritten numeric form) or ``Depends on <CODE>`` (the
    raw roadmap-code form, recovered from this ticket's ``[CODE]`` title bracket). A genuine
    UPSTREAM source (one WE depend on) does not mention us, so it is NOT filtered.

    Matching is word-boundary anchored so ``#91`` does not match ``#911`` and ``A1`` does not
    match ``A12``. The ``Depends on`` clause may list several refs (``Depends on #5, #91``), so a
    substring scan of the whole ``Depends on`` surface is sufficient.

    Args:
        linked_body: The cross-referenced issue's body (the candidate ``{{issue_body}}``).
        issue: THIS ticket's issue number (the numeric dependency form ``#<issue>``).
        code: THIS ticket's roadmap code from its ``[CODE]`` title bracket, or ``None`` when the
            title carries no bracket (then only the numeric form is checked).

    Returns:
        ``True`` when ``linked_body`` declares a dependency on this ticket (downstream — drop it),
        else ``False`` (upstream / unrelated — keep it).
    """
    if not linked_body:
        return False
    # ``Depends on #<issue>`` — numeric form (the seed rewrites codes to #N). ``(?!\d)`` stops
    # ``#91`` from matching inside ``#911``.
    if re.search(rf"Depends on\b[^\n]*#{issue}(?!\d)", linked_body):
        return True
    # ``Depends on <CODE>`` — raw roadmap-code form. ``\b`` around the escaped code stops ``A1``
    # from matching inside ``A12``.
    if code and re.search(rf"Depends on\b[^\n]*\b{re.escape(code)}\b", linked_body):
        return True
    return False


def validate_roadmap_matches_title(body: str, title: str) -> str | None:
    """Verify the body ``**roadmap**`` code equals the title ``[CODE]`` bracket; return an error.

    The post-write coherence gate (§29.1): a write must not desync the ticket↔roadmap binding. The
    check is SKIPPED (returns ``None``) when EITHER side is absent — a title with no ``[CODE]``
    bracket or a body with no ``**roadmap**`` marker cannot mismatch (the marker may be added by a
    later write). It returns an error message ONLY when both are present AND differ.

    Args:
        body: The (post-edit) issue body.
        title: The issue title carrying the authoritative ``[CODE]`` bracket.

    Returns:
        An error message string when the codes are both present and DIFFER, else ``None``.
    """
    code = title_code(title)
    marker = roadmap_marker(body)
    if code is None or marker is None:
        return None
    if code != marker:
        return (
            f"body **roadmap** code {marker!r} does not match the title [CODE] bracket {code!r} "
            f"— refusing the write (the ticket↔roadmap binding must stay coherent, §29.1)"
        )
    return None
