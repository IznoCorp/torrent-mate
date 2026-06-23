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
PRESERVED_MARKERS: tuple[str, ...] = ("roadmap", "codename", "design", "plans", "track")

# A ``**key**: value`` marker line, anchored at line start (mirrors ``ticket_fields._TICKET_FIELD``
# but parameterised on a single key for the in-place rewrite). ``re.MULTILINE`` so ``^`` matches
# each physical line.
_MARKER_LINE = re.compile(r"^\*\*(\w+)\*\*:[^\n]*$", re.MULTILINE)

# The authoritative ``[CODE]`` bracket at the START of an issue title (``[CODE] Title``).
_TITLE_CODE = re.compile(r"^\s*\[([^\]]+)\]")

# FIX 5 — body-top status header (clean-termination DESIGN §FIX-5). The daemon keeps an
# always-visible current-status block at the TOP of the issue body (GitHub cannot pin a timeline
# comment). HTML-comment delimiters are invisible in the rendered issue, never collide with the
# ``**key**:`` markers or ``##`` headings, and survive a GitHub round-trip.
STATUS_BEGIN = "<!-- kanban:status:begin -->"
STATUS_END = "<!-- kanban:status:end -->"

# Locate-and-replace an EXISTING status block exactly once. ``re.escape`` on the literal HTML
# comments means this can only ever match the exact delimited region — never an agent's prose —
# and ``re.DOTALL`` lets ``.*?`` span the multi-line block content.
_STATUS_BLOCK = re.compile(re.escape(STATUS_BEGIN) + r".*?" + re.escape(STATUS_END), re.DOTALL)


def _strip_delimiters(value: str) -> str:
    """Remove any literal STATUS_BEGIN/STATUS_END delimiter from an injected status field (nit 5).

    The status block is bounded by the :data:`STATUS_BEGIN` / :data:`STATUS_END` HTML comments and
    located by the non-greedy :data:`_STATUS_BLOCK` regex. If a field rendered INTO the block ever
    contained one of those delimiter literals, a later replace could match up to the EMBEDDED
    delimiter and split the block — leaving a malformed second region. Dropping the literals from the
    field content keeps the delimiters at the block boundaries ONLY, so the block stays well-formed.

    Args:
        value: A status field value (``stage`` / ``state`` / ``summary``) about to be rendered.

    Returns:
        ``value`` with every literal ``STATUS_BEGIN`` / ``STATUS_END`` occurrence removed.
    """
    return value.replace(STATUS_BEGIN, "").replace(STATUS_END, "")


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


def set_status_header(
    body: str,
    *,
    stage: str,
    state: str,
    summary: str,
    timestamp: str,
) -> str:
    """Insert/replace the body-top current-status block (FIX 5; pure, deterministic).

    The daemon keeps an always-visible header at the TOP of the issue body because GitHub
    cannot pin a timeline comment (clean-termination DESIGN §FIX-5). The block is delimited by
    :data:`STATUS_BEGIN` / :data:`STATUS_END` HTML comments so it is a single, region-disjoint
    zone: it can NEVER overlap a ``**key**:`` marker (:data:`PRESERVED_MARKERS`) or a ``##``
    heading, so :func:`set_field` / :func:`append_section` and this transform operate on
    non-overlapping bytes — markers + the ``## Brainstorm`` section are byte-preserved.

    Behaviour:

    * When a status block already exists (``_STATUS_BLOCK`` matches), it is REPLACED in place
      (``count=1`` guards against a malformed double block), leaving every other byte identical.
      An identical block produces an identical body — idempotent, so the app-layer body-diff gate
      can skip the write.
    * When absent, the block is PREPENDED at the TOP (header above all existing content; the
      markers + the ``## Brainstorm`` section are untouched, just shifted down) — the operator
      wants the status always visible at the top of the body.

    Args:
        body: The current issue body (may be empty).
        stage: The current stage / column name (e.g. ``"Design"``).
        state: The lifecycle state word (``running`` / ``done`` / ``blocked`` / ``waiting`` /
            ``interrupted`` / ``cancelled``).
        summary: A short free-text summary (empty string omits the ``— …`` clause).
        timestamp: A pre-formatted ``YYYY-MM-DD HH:MM`` stamp (typically
            :func:`kanbanmate.core.stage_comment.fmt_timestamp`).

    Returns:
        The body with the status block set at the top (replaced in place when one existed).
    """
    # Defensive de-fanging (nit 5): a ``stage``/``state``/``summary`` carrying the LITERAL
    # ``STATUS_BEGIN`` / ``STATUS_END`` delimiter would let the non-greedy ``_STATUS_BLOCK`` regex
    # self-corrupt — a stray ``STATUS_END`` inside the content would terminate the block early on the
    # NEXT replace, leaving an orphaned tail (a second, malformed region). Stripping any delimiter
    # occurrence from the injected fields BEFORE rendering guarantees the delimiters only ever appear
    # at the block boundaries, so the block stays a single well-formed region for any field content.
    stage = _strip_delimiters(stage)
    state = _strip_delimiters(state)
    summary = _strip_delimiters(summary)
    line = f"**KanbanMate status** — {stage} · {state}"
    if summary:
        line += f" — {summary}"
    rendered = f"{STATUS_BEGIN}\n{line}\n_updated {timestamp}_\n{STATUS_END}"
    if _STATUS_BLOCK.search(body):
        # REPLACE the existing block in place (region-disjoint from every marker/section, so they
        # stay byte-identical). ``count=1`` collapses a (malformed) double block to one.
        return _STATUS_BLOCK.sub(lambda _m: rendered, body, count=1)
    if not body:
        return rendered
    # ABSENT: prepend at the TOP above all existing content (markers + ## Brainstorm untouched).
    return f"{rendered}\n\n{body}"


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
