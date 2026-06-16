"""Build the placeholder substitution context for a launch prompt (extracted from actions.py).

The launch FILLS the matched transition's ``/implement:*`` prompt against a context dict
(``{{code}}`` / ``{{title}}`` / ``{{branch}}`` / ``{{script_output}}`` / enrichment keys). Assembling
that dict is a cohesive, self-contained step that reads the ticket + the workspace branch + the
board's issue context + the persisted script output. It lived as ``LaunchAction._launch_context``;
it is lifted here verbatim (as a free function taking the ticket explicitly) to keep the at-ceiling
``app/actions.py`` under the 1000-LOC hard ceiling (DESIGN §9 — new code in NEW modules; the
at-ceiling files must not grow). Behaviour is unchanged — the same sources, the same fail-soft
enrichment, the same fill-loud contract on a genuine typo.

Layering: ``app`` may import ``adapters``/``core`` and other ``app`` modules; it must not import the
entrypoints.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from kanbanmate.core.body_edit import declares_dependency_on, title_code
from kanbanmate.core.ticket_fields import parse_ticket_fields

if TYPE_CHECKING:  # pragma: no cover - type-only imports (no runtime cycle)
    from kanbanmate.app.actions import Deps
    from kanbanmate.core.domain import Ticket

logger = logging.getLogger(__name__)


def build_launch_context(
    ticket: Ticket,
    deps: Deps,
    issue: int,
    worktree: Path,
) -> dict[str, object]:
    """Build the placeholder context the shipped ``/implement:*`` prompts reference.

    Sources what NEW HAS TODAY: ``code`` / ``title`` / ``ticket_body`` from the :class:`Ticket`, and
    ``branch`` from the per-ticket worktree (discovered via the workspace port). ``script_output``
    (15.7) is sourced from :meth:`kanbanmate.ports.store.StateStore.load_script_output` — the last
    failing check's combined stdout+stderr, or ``""`` when absent. Staged enrichment: ``codename`` /
    ``design_path`` / ``plan_paths`` are parsed from the ticket body via
    :func:`~kanbanmate.core.ticket_fields.parse_ticket_fields` (PoC parity). ``issue_body`` (the FIRST
    cross-referenced linked-issue body) and ``comments`` (the full comment history, joined by
    ``\\n---\\n``) are enriched from :meth:`kanbanmate.ports.board.BoardReader.issue_context` —
    **fail-soft**: a GraphQL error degrades both to ``""`` and logs, never breaking the launch. The
    remaining keys NEW cannot supply (``dev_repo_path`` / ``base_clone``) default to ``""`` so
    :func:`fill` does not fail on a referenced-but-unsuppliable key. The fail-loud contract still
    holds for a genuine typo: a template token that is NOT a known key raises ``KeyError`` at fill.

    Args:
        ticket: The ticket being launched (the ``{{code}}`` / ``{{title}}`` / ``{{ticket_body}}`` +
            dependency-direction source).
        deps: The adapter bundle (the workspace port discovers the branch; the board reader enriches).
        issue: The ticket issue number (the ``{{code}}`` placeholder, bare ``<n>``).
        worktree: The per-ticket worktree path (unused beyond branch discovery here).

    Returns:
        The substitution context mapping for :func:`kanbanmate.core.placeholders.fill`.
    """
    # Discover the worktree's branch (idempotent read): the per-ticket WIP branch
    # ``kanban/ticket-<n>`` (pre create-branch) or ``feat/<codename>`` (post); a still-detached /
    # gone worktree reports ``None`` (mapped to ``""`` for the placeholder).
    branch = deps.workspace.discover_branch(issue) or ""
    fields = parse_ticket_fields(ticket.body or "")
    # 18.2: enrich the prompt with the FIRST cross-referenced issue body (``issue_body``, NOT
    # ``ticket_body``) + the ``\n---\n``-joined comment history (timeouts inherited).
    try:
        ctx = deps.board_reader.issue_context(issue)
        issue_body = ctx.linked_issue_body or ""
        # §29.3 direction fix (the #91 poisoning): a body declaring a dependency ON us
        # (``Depends on #<issue>``/``<CODE>``) is a DOWNSTREAM dependent — drop it (not our spec).
        if declares_dependency_on(issue_body, issue=issue, code=title_code(ticket.title)):
            issue_body = ""
        comments = "\n---\n".join(ctx.comments)  # PoC join (runner.py:663-704)
    except Exception:
        # A GraphQL hiccup must NOT break a launch — degrade to empty context (fail-soft).
        logger.exception(
            "issue_context enrichment failed for #%s; launching with empty issue_body/comments",
            issue,
        )
        issue_body = ""
        comments = ""
    return {
        # Fill ``{{code}}`` as the BARE issue number (defect 3): every shipped prompt pins helper
        # calls like ``kanban-move {{code}} 'PR/CI'`` to this placeholder, and the kanban-* helpers
        # parse ``int(argv[0])`` — a leading ``#`` makes ``#151`` a bash comment (zero args → usage
        # exit 2) and ``int('#151')`` raises. The helpers ALSO strip a leading ``#`` defensively,
        # but the contract value is the bare int.
        "code": str(issue),
        "title": ticket.title,
        "branch": branch,
        "ticket_body": ticket.body or "",
        # 15.7: fill from the LAST failing check's output (persisted by 15.6). Not cleared on
        # consume — a reaper relaunch re-reads the SAME failure context; 15.6 refreshes it.
        "script_output": deps.store.load_script_output(issue),
        # issue_body / comments: enriched from deps.board_reader.issue_context(issue) above (PoC
        # parity, 18.2) — the first cross-referenced linked-issue body and the joined comment
        # history; fail-soft to "" on a GraphQL error.
        "issue_body": issue_body,
        "comments": comments,
        # codename / design_path / plan_paths: parsed from the ticket body via parse_ticket_fields
        # (PoC parity, 18.1). The remaining enrichment keys (dev_repo_path / base_clone) are still
        # defaulted to "" — no shipped prompt references them, so the empty default is justified.
        "codename": fields["codename"],
        "design_path": fields["design_path"],
        "plan_paths": fields["plan_paths"],
        "base_clone": "",
        "dev_repo_path": "",
    }
