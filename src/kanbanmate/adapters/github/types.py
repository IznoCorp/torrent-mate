"""Small typed records for decoded GitHub API payloads (ported from the PoC).

These are adapter-internal value objects that sit *between* the raw decoded JSON
and the pure :mod:`kanbanmate.core.domain` model. They keep the parsers honest
(a single shape to construct) without leaking GitHub's wire vocabulary into the
core. The board read path produces :class:`RawItem` records which the client maps
to :class:`kanbanmate.core.domain.Ticket`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawItem:
    """A single ``ProjectV2Item`` as parsed from a board-items GraphQL response.

    This is the adapter-level twin of :class:`kanbanmate.core.domain.Ticket`: it
    carries exactly the fields the parser can read off a project item before the
    client maps it into the pure domain model.

    Attributes:
        item_id: The opaque ``ProjectV2Item`` node id (``PVTI_...``).
        issue_number: The linked issue number, or ``None`` for draft items / items
            whose content is not an Issue (e.g. a PullRequest or DraftIssue).
        title: The item title (issue title or draft note).
        status_column: The item's current Status single-select value name (the
            column name, e.g. ``"In Progress"``); empty when the item has no Status.
        updated_at: The item's ISO-8601 ``updatedAt`` timestamp, used by the cheap
            probe to build a change-detection token.
        body: The linked Issue's markdown body, carried so the dependency gate
            (DESIGN §9) can parse ``Depends on #N`` before a launch. Empty for
            draft items / non-Issue content (a PullRequest or DraftIssue).
    """

    item_id: str
    issue_number: int | None
    title: str
    status_column: str
    updated_at: str
    body: str = ""


@dataclass(frozen=True)
class CommentRef:
    """One issue comment as parsed from the REST ``list comments`` response.

    The sticky-comment logic (DESIGN §8.1) lists an issue's comments and locates
    the one carrying its per-step HTML marker, so it needs only the comment id and
    its body — nothing else off the REST payload.

    Attributes:
        comment_id: The REST comment id (``id`` field; an integer on the wire,
            carried as ``int`` so it round-trips into the update PATCH path).
        body: The full comment body (searched for the per-step HTML marker).
    """

    comment_id: int
    body: str


@dataclass(frozen=True)
class StatusField:
    """The project's Status single-select field, resolved once and reused.

    Attributes:
        field_id: The ``ProjectV2SingleSelectField`` node id (needed by the move
            mutation alongside the option id).
        options: Mapping of column name -> single-select option id, in board order.
    """

    field_id: str
    options: dict[str, str]


@dataclass(frozen=True)
class HealthField:
    """The project's per-card "Health" single-select field, resolved once and reused.

    The twin of :class:`StatusField` for the health-field feature: the custom
    single-select FIELD the daemon maintains so the operator's own vocabulary
    (``INACTIVE / BLOCKED / WAITING / ACTIVE / COMPLETE``) shows as native chips on
    each card (GitHub's fixed status-update pill enum cannot carry the operator's
    words). The client resolves it lazily (find-or-create) and caches it; the tick
    reuses the cached id + option ids to set each card's Health on change.

    Attributes:
        field_id: The ``ProjectV2SingleSelectField`` node id (needed by the
            ``updateProjectV2ItemFieldValue`` mutation alongside the option id).
        options: Mapping of Health value name -> single-select option id.
    """

    field_id: str
    options: dict[str, str]


@dataclass(frozen=True)
class IssueContext:
    """The rich issue context gathered by the ``issue_context`` GraphQL query.

    Ported from the PoC's ``parse_issue_context`` return dict (OLD
    ``_parsers.py:226-261``). Carries the issue body, up to 50 comment bodies
    in chronological order, and the body of the FIRST cross-referenced/linked
    Issue found in the timeline (or ``None``). The launch-prompt enrichment
    pipeline consumes this to fill ``{{ticket_body}}`` / ``{{issue_body}}`` /
    ``{{comments}}`` placeholders — a separate restoration from the GitHub-
    adapter parity work.

    Attributes:
        body: The issue's markdown body (empty string when absent).
        comments: Comment bodies in chronological order (≤50, tuple for
            hashable/immutable — consistent with the other frozen records).
        linked_issue_body: The body of the first cross-referenced Issue in the
            timeline, or ``None`` when there are no cross-references (or the
            cross-referenced source is not an Issue).
    """

    body: str
    comments: tuple[str, ...]
    linked_issue_body: str | None


@dataclass(frozen=True)
class IssueRef:
    """A single issue's identity + body, read off the REST ``GET issues/{n}`` payload.

    The ``kanban-update-body`` helper (§29.1) reads the current body to modify it (marker
    preservation / section append), then patches it back through the GraphQL ``update_issue_body``
    mutation — which is keyed by the issue's global ``node_id``, NOT its number. So this record
    carries both the ``node_id`` (the patch handle) and the ``title`` (for the post-write
    body↔title ``[CODE]`` coherence validation).

    Attributes:
        node_id: The issue's global node id (the ``update_issue_body`` patch handle).
        number: The issue number (echoed back for an integrity check).
        title: The issue title (carries the authoritative ``[CODE]`` bracket).
        body: The issue's current markdown body (empty string when absent).
    """

    node_id: str
    number: int
    title: str
    body: str
