"""GithubClient: the single I/O seam behind the board ports (ported from the PoC).

The client implements :class:`kanbanmate.ports.board.BoardReader` (``cheap_probe``,
``snapshot``) and :class:`kanbanmate.ports.board.BoardWriter` (``move_card``,
``comment``) over GitHub Projects v2. Pure builders (:mod:`._queries`) and parsers
(:mod:`._parsers`) flank a single network seam: an **injected transport**.

Network-timeout safety (CLAUDE.md MANDATORY + DESIGN §3.3): the default transport
(:class:`UrllibTransport`) enforces **both a connect and a read timeout on every
request** so the daemon can never hang on I/O. Tests inject a fake transport that
returns fixture JSON, so no unit test touches the network.

Required token scopes: ``project`` + ``repo`` only (DESIGN §10); validated by
:mod:`.token`.
"""

from __future__ import annotations

import time
from typing import Any

from kanbanmate.adapters.github import _health, _parsers, _queries, _rest
from kanbanmate.adapters.github._parsers import GitHubHTTPError, raise_for_errors
from kanbanmate.adapters.github.client_labels import GithubLabelsMixin
from kanbanmate.adapters.github._transport import (
    GraphQLTransport,
    RestHeadersTransport,
    RestTransport,
    Timeouts,
    UrllibTransport,
)
from kanbanmate.adapters.github.types import (
    CommentRef,
    HealthField,
    IssueContext,
    IssueRef,
    RawItem,
    StatusField,
)
from kanbanmate.core.domain import BoardSnapshot, Ticket
from kanbanmate.core.probes import parse_branch_protection_on

# The HTTP transport concern (the seam type aliases, :class:`Timeouts`,
# :class:`UrllibTransport`, and the transient-retry policy) moved to
# :mod:`._transport` in 19.1 to restore headroom under the 1000-LOC hard ceiling
# (mirrors the ``app/reaper`` / ``app/depgate`` / ``app/drain`` extractions). The
# public names ``Timeouts`` and ``UrllibTransport`` are RE-EXPORTED here via
# ``__all__`` so the long-standing
# ``from kanbanmate.adapters.github.client import GithubClient, Timeouts, UrllibTransport``
# import (e.g. the pagination tests) keeps resolving without touching the caller.
__all__ = ["GithubClient", "Timeouts", "UrllibTransport"]

# Domain-health → GitHub wire-enum map (the status-pill adapter boundary). KanbanMate's core speaks
# its OWN health vocabulary (``core.status_update.StatusValue``: INACTIVE / BLOCKED / WAITING / ACTIVE
# / COMPLETE — mirroring the agent/board states), but GitHub's ``ProjectV2StatusUpdateStatus`` pill is
# a FIXED enum we cannot rename. This adapter is the ONLY place the value crosses to GitHub, so it
# translates here: ACTIVE→ON_TRACK, WAITING→AT_RISK, BLOCKED→OFF_TRACK (INACTIVE / COMPLETE are
# identical on both sides). An UNKNOWN value passes through unchanged so a future health name still
# reaches GitHub (which then validates it) rather than being silently dropped.
_HEALTH_TO_GITHUB_STATUS: dict[str, str] = {
    "INACTIVE": "INACTIVE",
    "BLOCKED": "OFF_TRACK",
    "WAITING": "AT_RISK",
    "ACTIVE": "ON_TRACK",
    "COMPLETE": "COMPLETE",
}


def _to_github_status(health: str) -> str:
    """Map a KanbanMate domain-health name onto GitHub's ``ProjectV2StatusUpdateStatus`` wire enum.

    Args:
        health: A :data:`kanbanmate.core.status_update.StatusValue` domain name (e.g. ``"ACTIVE"``).

    Returns:
        The matching GitHub wire-enum value (e.g. ``"ON_TRACK"``); the input unchanged for an
        unknown name (forward-compatible — GitHub then validates it).
    """
    return _HEALTH_TO_GITHUB_STATUS.get(health, health)


class GithubClient(GithubLabelsMixin):
    """GitHub Projects v2 board adapter — the single client behind every board port.

    One instance satisfies the FULL board surface (DESIGN §3.3 wires it into all slots):
    :class:`~kanbanmate.ports.board.BoardReader` (``cheap_probe`` / ``snapshot`` /
    ``issue_state`` / ``issue_context``), :class:`~kanbanmate.ports.board.BoardWriter`
    (``move_card`` / ``comment`` / ``list_issue_comments`` / ``update_comment``),
    :class:`~kanbanmate.ports.board.PullRequests` (``close_open_pr_for_branch``, the Cancel
    teardown), :class:`~kanbanmate.ports.board.Seeder` (the per-repo ``init`` / ``seed``
    bootstrap: ``ensure_project`` / ``link_to_repo`` / ``ensure_columns`` / ``ensure_labels`` /
    ``create_issue`` / ``update_issue_body`` / ``add_to_project``), plus the ``branch_protection_on``
    advisory probe ``kanban doctor`` reads. Construct with a project node id + the target repo so
    the narrow port methods need no GitHub option ids or slugs; the Status field is cached lazily.
    """

    def __init__(
        self,
        token: str,
        *,
        project_id: str = "",
        repo: str = "",
        graphql_transport: GraphQLTransport | None = None,
        rest_transport: RestTransport | None = None,
        timeouts: Timeouts | None = None,
    ):
        """Create a board client.

        Args:
            token: A GitHub PAT scoped ``project`` + ``repo`` (DESIGN §10).
            project_id: The ``ProjectV2`` node id of the board. Optional for a
                Seeder-only client (``kanban init`` creates the project), required
                for the board read/move/comment paths.
            repo: The ``owner/name`` slug used to resolve issues for ``comment``.
                Optional for a Seeder-only client (the Seeder methods take the repo
                as an argument).
            graphql_transport: Optional GraphQL transport override (tests inject a
                fake returning fixture JSON). Defaults to a real
                :class:`UrllibTransport` with mandatory connect+read timeouts.
            rest_transport: Optional REST transport override (tests inject a fake).
                Defaults to the same :class:`UrllibTransport`.
            timeouts: Connect/read timeouts for the default transport.
        """
        self._project_id = project_id
        self._repo = repo
        default = UrllibTransport(token, timeouts=timeouts)
        # Keep a handle on the default transport so callers/tests can read back the
        # timeouts that prove the safety rule is honoured.
        self._default_transport = default
        self._graphql: GraphQLTransport = graphql_transport or default.graphql
        self._rest: RestTransport = rest_transport or default.rest
        # Headers-bearing REST seam for the Link rel=next pager. When the caller
        # injects a body-only ``rest_transport`` (the existing legacy fakes), there
        # is no header source, so wrap it to yield empty headers — the pager then
        # finds no ``Link`` and terminates after page 1 (graceful single-page
        # fallback). The production default reads real headers off the response.
        self._rest_headers: RestHeadersTransport
        if rest_transport is not None:
            injected = rest_transport
            self._rest_headers = lambda m, p, b: (injected(m, p, b), {})
        else:
            self._rest_headers = default.rest_with_headers
        self._status_field: StatusField | None = None
        # The per-card "Health" single-select field, resolved lazily on first use and
        # cached for the process (health-field). Mirrors ``_status_field``.
        self._health_field: HealthField | None = None

    @property
    def transport_timeouts(self) -> Timeouts:
        """The connect/read timeouts of the default urllib transport.

        Exposed so callers (and the timeout-safety test) can assert both budgets
        are set and non-``None``.
        """
        return self._default_transport.timeouts

    # ---- BoardReader ----
    def cheap_probe(self) -> str:
        """Return an opaque change-detection token for the board (DESIGN §3.1).

        Returns:
            A token built from the 5 newest items' ``updatedAt`` timestamps; equal
            tokens mean the board is assumed unchanged and no snapshot is fetched.
        """
        data = self._graphql(_queries.cheap_probe(self._project_id))
        return _parsers.parse_cheap_probe(data)

    def snapshot(self) -> BoardSnapshot:
        """Fetch the current board state as a :class:`BoardSnapshot`.

        Pages through ALL ``projectItems`` via cursor pagination so boards with
        more than 100 items return a complete snapshot (Hardening H3). The loop
        follows ``endCursor`` until ``hasNextPage`` is ``false``, with a sane
        page cap that guards against a runaway cursor.

        Every page is fetched through the injected :attr:`_graphql` transport so
        the mandatory connect+read timeouts are preserved on every request — no
        bare/untimed urllib call is introduced by the pagination loop.

        Returns:
            A snapshot of every visible item with a wall-clock capture time.
        """

        raw_items: list[RawItem] = []
        after: str | None = None
        max_pages = 10  # 1000 items — well beyond any realistic board

        for _ in range(max_pages):
            data = self._graphql(_queries.board_items(self._project_id, after=after))
            page_items, has_next, end_cursor = _parsers.parse_board_items(data)
            raw_items.extend(page_items)
            if not has_next:
                break
            if not end_cursor:
                # hasNextPage is true but endCursor is absent — malformed response,
                # or empty page. Stop rather than loop forever on the same page.
                break
            if end_cursor == after:
                # The cursor did not advance — broken server or fixture, stop.
                break
            after = end_cursor

        tickets = tuple(self._to_ticket(item) for item in raw_items)
        return BoardSnapshot(tickets=tickets, fetched_at=time.time())

    @staticmethod
    def _to_ticket(raw: RawItem) -> Ticket:
        """Map an adapter :class:`RawItem` to a pure-domain :class:`Ticket`.

        Args:
            raw: A parsed project item.

        Returns:
            A :class:`Ticket`; ``column_key`` is the item's Status column name and
            ``body`` is the linked issue's markdown (empty for draft/PR items),
            carried so the dependency gate can read ``Depends on #N`` (DESIGN §9).
        """
        return Ticket(
            item_id=raw.item_id,
            issue_number=raw.issue_number,
            title=raw.title,
            column_key=raw.status_column,
            body=raw.body,
            is_closed=raw.is_closed,
        )

    # ---- BoardWriter ----
    def move_card(self, item_id: str, column_key: str) -> None:
        """Move card ``item_id`` into the column named ``column_key``.

        Thin BoardWriter wrapper over :meth:`move_card_confirmed` that discards the
        read-your-write Status name — callers of this method only need the move applied.

        Args:
            item_id: The ``ProjectV2Item`` node id to move.
            column_key: The destination column key (a Status option name).

        Raises:
            KeyError: When ``column_key`` is not a known Status option.
            GraphQLError: When the mutation response carries errors.
        """
        self.move_card_confirmed(item_id, column_key)

    def move_card_confirmed(self, item_id: str, column_key: str) -> str | None:
        """Move ``item_id`` to ``column_key`` and return the Status name GitHub recorded.

        Same mutation as :meth:`move_card`, but reads the resulting Status name out of the
        SAME response (read-your-write — no second query, no eventual-consistency lag). A
        returned name equal to ``column_key`` proves GitHub applied the change; ``None``
        means the response carried no Status value, treated by the caller as unconfirmed.

        Args:
            item_id: The ``ProjectV2Item`` node id to move.
            column_key: The destination column key (a Status option name).

        Returns:
            The Status option name GitHub reports after the mutation, or ``None`` when the
            response carries no single-select value.

        Raises:
            KeyError: When ``column_key`` is not a known Status option.
            GraphQLError: When the mutation response carries errors.
        """
        field = self._resolve_status_field()
        try:
            option_id = field.options[column_key]
        except KeyError as exc:
            known = ", ".join(sorted(field.options))
            raise KeyError(f"unknown column '{column_key}'; known columns: {known}") from exc
        data = self._graphql(
            _queries.move_item(self._project_id, item_id, field.field_id, option_id)
        )
        raise_for_errors(data)
        return _parsers.parse_moved_status_name(data)

    def comment(self, issue_number: int, body: str) -> None:
        """Post a comment on issue ``issue_number`` via the REST API.

        REST-by-design (#14): the PoC posted via TWO GraphQL calls (resolve the
        issue node id, then ``addComment``); NEW posts via a single REST POST —
        functionally equivalent, one round-trip, no node-id lookup. The dead GraphQL
        comment builders/parser were DELETED; do NOT reintroduce a GraphQL seam here.

        Args:
            issue_number: The issue number in the client's repository.
            body: The markdown comment body.

        Raises:
            GitHubHTTPError: When the REST POST returns an HTTP error.
        """
        # REST issue-comment create: POST /repos/{owner}/{repo}/issues/{n}/comments.
        # Ported from the PoC `_rest.py` helper, inlined here (in-scope: lives under
        # adapters/github). The narrow port hides the repo from callers.
        path = f"/repos/{self._repo}/issues/{issue_number}/comments"
        self._rest("POST", path, {"body": body})

    def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
        """List ALL comments on issue ``issue_number`` (REST GET, Link-paginated).

        Backs the sticky-comment logic (DESIGN §8.1): the caller scans the returned
        bodies for a per-step HTML marker to decide whether to edit an existing
        comment or create a fresh one. The GET endpoint returns a JSON *array*, so
        each page's decoded value is a list (handled by
        :func:`._parsers.parse_issue_comments`).

        Follows the ``Link rel="next"`` header (ported from the PoC
        ``client.py:233-249``) so a sticky comment beyond page 1 is still found —
        without this, a sticky on page 2+ is invisible and the §8.1 upsert would
        CREATE A DUPLICATE sticky each tick. The first page asks for
        ``per_page=100`` and every subsequent page reuses :attr:`_rest_headers`, so
        the mandatory connect+read timeouts hold on every request (no untimed read
        path).

        Args:
            issue_number: The issue number in the client's repository.

        Returns:
            One :class:`~kanbanmate.adapters.github.types.CommentRef` per comment,
            across every page, in GitHub's return order.

        Raises:
            GitHubHTTPError: When any page's REST GET returns an HTTP error.
        """
        method, path, _ = _rest.list_issue_comments(self._repo, issue_number)
        acc: list[CommentRef] = []
        seen: set[str] = set()
        next_path: str | None = path
        while next_path is not None and next_path not in seen:
            seen.add(next_path)
            raw, headers = self._rest_headers(method, next_path, None)
            # The endpoint returns an array; guard against an unexpected non-list body.
            acc.extend(_parsers.parse_issue_comments(raw if isinstance(raw, list) else []))
            # Advance to the rel=next page (None when exhausted or no Link header —
            # the empty-headers legacy fallback terminates the loop here).
            next_path = _rest.next_link_path(headers.get("Link") or headers.get("link"))
        return acc

    def update_comment(self, comment_id: int, body: str) -> None:
        """Edit an existing issue comment in place (REST PATCH).

        The other half of the sticky-comment upsert (DESIGN §8.1): once the marked
        comment is located via :meth:`list_issue_comments`, its body is rewritten so
        each (ticket, step) keeps a single comment that updates over time rather than
        spamming the timeline.

        Args:
            comment_id: The REST comment id to edit (from a :class:`CommentRef`).
            body: The new markdown comment body.

        Raises:
            GitHubHTTPError: When the REST PATCH returns an HTTP error.
        """
        # REST edit issue comment: PATCH /repos/{owner}/{repo}/issues/comments/{id}.
        path = f"/repos/{self._repo}/issues/comments/{comment_id}"
        self._rest("PATCH", path, {"body": body})

    # ---- Issue context (GraphQL body + comments + linked issue) ----

    def issue_context(self, number: int) -> IssueContext:
        """Gather an issue's body, comments, and first linked-issue body for prompt context.

        Ported from the PoC ``client.py:191-212`` (audit HIGH). Fetches the issue body,
        up to 50 comment bodies (chronological order), and the body of the FIRST
        cross-referenced/linked Issue found in the timeline. The PoC dispatcher consumed
        this to fill ``{{ticket_body}}`` / ``{{issue_body}}`` / ``{{comments}}``
        placeholders (spec §5.2).

        **NEW has NO in-tree consumer yet** — the launch-prompt enrichment pipeline
        is a separate restoration (out of scope here). This method exists for GitHub-
        adapter parity (audit HIGH) so the future launch-prompt enrichment can consume
        it without also needing to port the adapter.

        Args:
            number: The issue number in the client's repository.

        Returns:
            An :class:`~kanbanmate.adapters.github.types.IssueContext` with the issue
            body, comment bodies (tuple, ≤50), and the first linked-issue body (or
            ``None``).
        """
        owner, name = self._repo.split("/", 1)
        data = self._graphql(_queries.issue_context(owner, name, number))
        return _parsers.parse_issue_context(data)

    # ---- Issue state (GraphQL open/closed probe; the #13 dependency-gate fallback) ----

    def issue_state(self, number: int) -> bool:
        """Return ``True`` iff the issue is CLOSED (an off-board dependency gate fallback).

        Ported from the PoC ``client.py:182-189``. Splits ``self._repo`` into
        owner/name, reads ``issue.state`` via :func:`._queries.issue_state`, and
        returns :func:`._parsers.parse_issue_closed`. The phase-17 #13 dependency
        gate consumes this as the LIVE fallback for off-board ``Depends on #N``
        references: the board snapshot is primary; this query resolves only the
        deps the snapshot cannot decide (absent from the board). A closed issue
        satisfies its dependent, avoiding the per-tick N queries of the common
        all-on-board case.

        The request inherits the client's mandatory connect+read timeouts via
        :attr:`_graphql` (no untimed network path is introduced).

        Args:
            number: The issue number in the client's repository.

        Returns:
            ``True`` when the issue's state is ``CLOSED``, ``False`` otherwise
            (``OPEN`` / missing / unresolved — conservative: undecidable is NOT
            treated as done).
        """
        owner, name = self._repo.split("/", 1)
        data = self._graphql(_queries.issue_state(owner, name, number))
        return _parsers.parse_issue_closed(data)

    # ---- Pull-request operations (DESIGN §8.2) ----

    def find_open_pr(self, head_branch: str) -> int | None:
        """Find the open PR whose head ref is ``head_branch``; return its number.

        REST ``GET /repos/{owner}/{repo}/pulls?state=open&head={owner}:{branch}``
        with ``per_page=100`` and Link ``rel="next"`` pagination (ported from the PoC
        ``_rest.list_open_pulls_for_branch``). Qualifies the head with the repo owner
        so a same-named branch in a fork does not match. Returns the first PR number
        or ``None``.

        Follows every ``Link rel="next"`` page via :attr:`_rest_headers` so a PR
        beyond page 1 is still found (reuses the 16.2 pager, not a duplicated loop).
        Each page is resolved via :func:`._rest.parse_open_pull_number`; the loop
        returns on the first hit and advances ``next_path`` via
        :func:`._rest.next_link_path`. A ``seen``-set guard prevents an infinite loop
        from a non-advancing / self-referential ``Link`` header (the same fix applied
        to :meth:`list_issue_comments`).

        Empty string or ``"HEAD"`` branch → return ``None`` without a network
        round-trip (no branch to look up).

        Args:
            head_branch: The remote branch name (e.g. ``feat/genesis``).

        Returns:
            The PR number, or ``None`` when no open PR exists for the branch.
        """
        if not head_branch or head_branch == "HEAD":
            return None
        method, path, _ = _rest.list_open_pulls_for_branch(self._repo, head_branch)
        seen: set[str] = set()
        next_path: str | None = path
        while next_path is not None and next_path not in seen:
            seen.add(next_path)
            raw, headers = self._rest_headers(method, next_path, None)
            number = _rest.parse_open_pull_number(raw if isinstance(raw, list) else None)
            if number is not None:
                return number  # first hit wins — return immediately
            next_path = _rest.next_link_path(headers.get("Link") or headers.get("link"))
        return None

    def close_pr(self, number: int) -> None:
        """Close a pull request WITHOUT merging; the remote branch is KEPT.

        REST ``PATCH /repos/{owner}/{repo}/pulls/{number}`` with body
        ``{"state": "closed"}``.  Closing a PR does **not** delete its head
        branch — there is deliberately no delete-ref call here. The remote
        branch remains intact (the operator-decided Cancel semantics;
        DESIGN §8.2).

        This is **not** a merge (``close`` ≠ ``merge``). The deny-list bans
        merge for agents, but teardown is the dispatcher (mechanical), and
        closing without merging is always safe.

        Args:
            number: The PR number to close.
        """
        path = f"/repos/{self._repo}/pulls/{number}"
        self._rest("PATCH", path, {"state": "closed"})

    def close_open_pr_for_branch(self, head_branch: str) -> int | None:
        """Find and close the open PR for ``head_branch``; return its number.

        Compose :meth:`find_open_pr` → :meth:`close_pr`.  Return the closed
        PR number or ``None`` (no-op when no open PR exists or branch is
        empty / ``"HEAD"``).  The remote branch is kept — close ≠ delete-ref.

        This is the single call :class:`TeardownAction` will make in 8.2.b.

        Args:
            head_branch: The remote branch name (e.g. ``feat/genesis``).

        Returns:
            The closed PR number, or ``None``.
        """
        number = self.find_open_pr(head_branch)
        if number is not None:
            self.close_pr(number)
        return number

    # ---- Branch protection probe (doctor; DESIGN §4.3 / §10) ----
    def branch_protection_on(self, branch: str = "main") -> bool:
        """Return ``True`` iff ``branch`` has branch protection enabled (fail-soft).

        REST ``GET /repos/{owner}/{repo}/branches/{branch}/protection``. The
        endpoint **404s when protection is OFF** (or 403s without admin
        permission), so this method is FAIL-SOFT: on any
        :class:`~kanbanmate.adapters.github._parsers.GitHubHTTPError` it returns
        ``False`` rather than raising — the PoC treated a message-only / 404 body
        as "off" (port of ``cli/runners.py:459-467``). On a 2xx it hands the
        decoded body to the pure
        :func:`~kanbanmate.core.probes.parse_branch_protection_on` and returns its
        verdict.

        The request goes through the same :attr:`_rest` seam every other REST
        call uses, so it inherits the client's mandatory connect+read timeouts
        (CLAUDE.md Network Timeout Safety) — no untimed network path is added.
        This signal is advisory only: ``doctor`` WARNs when protection is off but
        never fails the run (DESIGN §10 — "merge = human only").

        Args:
            branch: The branch to probe (default ``main``, the integration base).

        Returns:
            ``True`` when the branch carries a protection rule; ``False`` when it
            is unprotected (the 404 contract) or the API is unreachable.
        """
        path = f"/repos/{self._repo}/branches/{branch}/protection"
        try:
            body = self._rest("GET", path, None)
        except GitHubHTTPError:
            # 404 = no protection on this branch; 403 = no admin permission to read
            # it. Either way, doctor's advisory check treats it as "off" — never
            # crash the health check on a missing rule or a narrow token.
            return False
        return parse_branch_protection_on(body)

    # ---- Project status updates (the rolling dashboard; phase-24 §24.2) ----
    def create_status_update(self, project_id: str, body: str, status: str) -> str:
        """Create the rolling status update on ``project_id``; return its node id.

        Issues ``createProjectV2StatusUpdate`` against the project's "Status
        updates" section (the FIRST post; thereafter the daemon refreshes the
        same update by id via :meth:`update_status_update`). The returned id is
        persisted by the caller so later on-change refreshes ``update`` rather
        than spawn a new pill (phase-24 §24.2).

        Routes through :attr:`_graphql`, so it inherits the client's mandatory
        connect+read timeouts (CLAUDE.md Network Timeout Safety) — no untimed
        network path is introduced.

        Args:
            project_id: The ``ProjectV2`` node id to post the status update on.
            body: The markdown status-update body (the rendered dashboard).
            status: A KanbanMate DOMAIN health name (``INACTIVE`` / ``BLOCKED`` /
                ``WAITING`` / ``ACTIVE`` / ``COMPLETE``) — mapped to GitHub's
                ``ProjectV2StatusUpdateStatus`` wire enum here via
                :func:`_to_github_status` (ACTIVE→ON_TRACK, WAITING→AT_RISK, BLOCKED→OFF_TRACK).

        Returns:
            The new ``ProjectV2StatusUpdate`` node id.

        Raises:
            GraphQLError: When the mutation response carries errors.
        """
        data = self._graphql(
            _queries.create_status_update(project_id, body, _to_github_status(status))
        )
        return _parsers.parse_created_status_update(data)

    def update_status_update(self, status_update_id: str, body: str, status: str) -> None:
        """Refresh the existing rolling status update ``status_update_id`` in place.

        Issues ``updateProjectV2StatusUpdate`` so the project keeps a SINGLE
        rolling status pill the daemon updates only when the body or status enum
        changes (phase-24 §24.2). The id is the one
        :meth:`create_status_update` returned and the caller persisted.

        Routes through :attr:`_graphql`, so it inherits the client's mandatory
        connect+read timeouts (CLAUDE.md Network Timeout Safety) — no untimed
        network path is introduced.

        Args:
            status_update_id: The ``ProjectV2StatusUpdate`` node id to refresh.
            body: The new markdown status-update body.
            status: A KanbanMate DOMAIN health name (``INACTIVE`` / ``BLOCKED`` /
                ``WAITING`` / ``ACTIVE`` / ``COMPLETE``) — mapped to GitHub's
                ``ProjectV2StatusUpdateStatus`` wire enum here via :func:`_to_github_status`.

        Raises:
            GraphQLError: When the mutation response carries errors.
        """
        data = self._graphql(
            _queries.update_status_update(status_update_id, body, _to_github_status(status))
        )
        raise_for_errors(data)

    def delete_status_update(self, status_update_id: str) -> None:
        """Delete the orphaned rolling status update ``status_update_id`` (phase-36).

        Issues ``deleteProjectV2StatusUpdate`` to remove a stale update the
        self-heal re-create path orphaned, so the project keeps a SINGLE rolling
        pill rather than a stack of dead ones. The caller invokes this only after
        a successful re-create and swallows any error (the lingering update is
        cosmetic, never a launch blocker) — but the adapter still raises on a
        GraphQL error so the caller can decide to log + swallow it.

        Routes through :attr:`_graphql`, so it inherits the client's mandatory
        connect+read timeouts (CLAUDE.md Network Timeout Safety) — no untimed
        network path is introduced.

        Args:
            status_update_id: The orphaned ``ProjectV2StatusUpdate`` node id to delete.

        Raises:
            GraphQLError: When the mutation response carries errors.
        """
        data = self._graphql(_queries.delete_status_update(status_update_id))
        raise_for_errors(data)

    # ---- ProjectHealthReporter (per-card Health single-select chip; health-field) ----
    def ensure_health_field(self, project_id: str) -> HealthField:
        """Find-or-create the "Health" single-select field; reconcile drift, cache it.

        Mirrors :meth:`_resolve_status_field` / :meth:`ensure_columns`: resolves the
        custom per-card "Health" field (so the operator's vocabulary shows as native
        chips, see :mod:`kanbanmate.core.health`) once per process and caches it. The
        find-or-create + reconcile logic lives in
        :func:`kanbanmate.adapters.github._health.ensure_health_field` (extracted to keep
        this already-large client lean); it reuses the ``status_option_map`` read and the
        ``update_status_field_options`` REPLACE, creating the field only when absent.

        Routes through :attr:`_graphql`, so every read/create/replace inherits the
        client's mandatory connect+read timeouts (CLAUDE.md Network Timeout Safety).

        Args:
            project_id: The ``ProjectV2`` node id whose Health field to ensure.

        Returns:
            The resolved/created :class:`~kanbanmate.adapters.github.types.HealthField`.
        """
        if self._health_field is None:
            self._health_field = _health.ensure_health_field(self._graphql, project_id)
        return self._health_field

    def set_item_health(self, item_id: str, value: str) -> None:
        """Set card ``item_id``'s Health single-select value to ``value`` (one HEALTH name).

        REUSES the EXISTING ``move_item`` mutation
        (``updateProjectV2ItemFieldValue { value: { singleSelectOptionId } }``) with the
        Health field id + the option id for ``value`` — there is NO new set mutation; the
        Health write is the SAME single-select item-value write the column move uses,
        only against the Health field. Ensures the field is resolved/cached first.

        Routes through :attr:`_graphql`, inheriting the client's mandatory connect+read
        timeouts (CLAUDE.md Network Timeout Safety) — no untimed network path.

        Args:
            item_id: The ``ProjectV2Item`` node id whose Health value to set.
            value: One of the 5 Health names
                (:data:`~kanbanmate.core.status_update.STATUS_VALUES`).

        Raises:
            KeyError: When ``value`` is not a known Health option.
            GraphQLError: When the mutation response carries errors.
        """
        field = self.ensure_health_field(self._project_id)
        option_id = field.options[value]  # value is one of STATUS_VALUES
        data = self._graphql(
            _queries.move_item(self._project_id, item_id, field.field_id, option_id)
        )
        raise_for_errors(data)

    # ---- Seeder (per-repo init/seed; DESIGN §4.3) ----
    def ensure_project(self, org: str, title: str) -> str:
        """Find-or-create an org Project v2 named ``title`` (DESIGN §4.3).

        A transferred repo does not migrate a personal Project, so ``init``
        materialises a fresh org board — reusing one of the same title if it
        already exists, keeping the whole operation idempotent.

        Args:
            org: The organization login that owns the project.
            title: The project title to find-or-create.

        Returns:
            The ``ProjectV2`` node id (the ``projects.json`` registry key).
        """
        existing = _parsers.parse_find_org_project(
            self._graphql(_queries.find_org_project(org)), title=title
        )
        if existing is not None:
            return existing
        owner_id = _parsers.parse_org_id(self._graphql(_queries.org_id(org)))
        return _parsers.parse_created_project(
            self._graphql(_queries.create_project(owner_id, title))
        )

    def ensure_columns(self, project_id: str, columns: list[str]) -> dict[str, str]:
        """Make the project's Status option set EXACTLY ``columns``, in board order.

        Reuses the Status single-select field GitHub auto-creates on a new
        Project v2 (DESIGN §4.3) and replaces its option list so the desired
        ``columns`` lead, in order. Existing options are preserved **by id** so
        cards already in a column are never orphaned; residual options outside
        ``columns`` that still hold cards are kept (appended) rather than
        dropped. Idempotent: when the option set already equals the target, no
        mutation is issued.

        Args:
            project_id: The ``ProjectV2`` node id whose Status field to shape.
            columns: The desired column names, in board order.

        Returns:
            A ``{column_name: option_id}`` map for the requested ``columns``.
        """
        data = self._graphql(_queries.status_option_map(project_id))
        option_map = _parsers.parse_status_option_map(data)  # {name: id}, board order
        field_id = _parsers.parse_status_field_id(data)

        desired = list(columns)
        # Residual options the template does not define (e.g. GitHub's "Todo").
        residual = [name for name in option_map if name not in desired]
        # Never drop a residual that still holds cards — that would null every
        # such card's Status. Only pay the per-card count when a residual exists.
        kept_residual: list[str] = []
        if residual:
            counts = self._status_option_counts(project_id)
            kept_residual = [name for name in residual if counts.get(name, 0) > 0]

        target = desired + kept_residual
        if list(option_map.keys()) == target:
            # Already in the desired shape + order: idempotent no-op.
            return {col: option_map[col] for col in columns}

        # updateProjectV2Field REPLACES the option set, so send the full target.
        # Pass each EXISTING option's id so GitHub PRESERVES it (and its option
        # id) instead of recreating it — without the id the REPLACE reassigns
        # every option id and orphans every card already in a column. New
        # columns omit `id` so GitHub creates them fresh.
        options_input: list[dict[str, Any]] = []
        for name in target:
            opt: dict[str, Any] = {"name": name, "color": "GRAY", "description": ""}
            if name in option_map:
                opt["id"] = option_map[name]
            options_input.append(opt)
        updated = self._graphql(_queries.update_status_field_options(field_id, options_input))
        option_map = _parsers.parse_updated_field_options(updated) or option_map
        return {col: option_map[col] for col in columns}

    def link_to_repo(self, project_id: str, repo: str) -> None:
        """Link Project v2 ``project_id`` to ``repo`` (``owner/name``).

        Resolves the repository node id, then runs ``linkProjectV2ToRepository`` so the project
        appears in the repo's Projects tab — the canonical repo↔project association ``kanban init``
        establishes. GitHub treats re-linking an already-linked repo as harmless.

        Args:
            project_id: The ``ProjectV2`` node id to link.
            repo: The ``owner/name`` slug of the repository to link to.

        Raises:
            GraphQLError: When the link mutation response carries errors.
        """
        owner, name = repo.split("/", 1)
        repo_node, _existing = _parsers.parse_repo(self._graphql(_queries.repo_id(owner, name)))
        data = self._graphql(_queries.link_project_to_repo(project_id, repo_node))
        raise_for_errors(data)

    def update_project_description(self, project_id: str, short_description: str) -> None:
        """Set ``project_id``'s ``shortDescription`` — but ONLY when it is empty (phase-33).

        ``kanban init`` gives a fresh board a default one-line description. The set
        is IDEMPOTENT and non-destructive: the current description is read first and
        the mutation is SKIPPED when it is already non-empty, so an operator-authored
        description is never overwritten and a re-run of ``init`` does nothing.

        Routes through :attr:`_graphql`, so both the read and the write inherit the
        client's mandatory connect+read timeouts (CLAUDE.md Network Timeout Safety).

        Args:
            project_id: The ``ProjectV2`` node id whose short description to set.
            short_description: The default one-line description to write when the
                project has none.

        Raises:
            GraphQLError: When the read or the mutation response carries errors.
        """
        existing = _parsers.parse_project_short_description(
            self._graphql(_queries.project_short_description(project_id))
        )
        # Idempotent: never clobber an existing description (operator-authored or a
        # prior init's). Only a genuinely empty field is given the default.
        if existing.strip():
            return
        data = self._graphql(_queries.update_project_description(project_id, short_description))
        raise_for_errors(data)

    def create_issue(self, repo: str, title: str, body: str, labels: list[str]) -> tuple[str, int]:
        """Create an issue on ``repo`` (creating any missing labels first).

        Requested labels that do not yet exist are created via
        :meth:`ensure_labels` rather than silently dropped — the ``wave:*`` /
        ``prio:*`` routing depends on them.

        Args:
            repo: The ``owner/name`` repository slug.
            title: The issue title.
            body: The issue body (markdown).
            labels: Label names to apply.

        Returns:
            A ``(issue_node_id, issue_number)`` pair for the created issue.
        """
        owner, name = repo.split("/", 1)
        repo_node, existing = _parsers.parse_repo(self._graphql(_queries.repo_id(owner, name)))
        label_map = dict(existing)
        if any(label not in label_map for label in labels):
            # Some requested label is missing — create them all and re-read the ids.
            label_map = self.ensure_labels(repo, labels)
        label_ids = [label_map[label] for label in labels]
        data = self._graphql(_queries.create_issue(repo_node, title, body, label_ids))
        return _parsers.parse_created_issue(data)

    def fetch_issue(self, issue_number: int) -> IssueRef:
        """Read issue ``issue_number``'s identity + current body via the REST API (§29.1).

        Backs ``kanban-update-body``: it must read the current body to modify it (marker
        preservation / section append) and recover the global ``node_id`` the GraphQL
        :meth:`update_issue_body` mutation patches against, plus the ``title`` for the post-write
        body↔title ``[CODE]`` coherence check. REST ``GET /repos/{owner}/{repo}/issues/{n}``
        returns ``node_id`` / ``title`` / ``body`` in one round-trip; the request inherits the
        client's mandatory connect+read timeouts via the same :attr:`_rest` seam every other REST
        call uses (no untimed network path).

        Args:
            issue_number: The issue number in the client's repository.

        Returns:
            An :class:`~kanbanmate.adapters.github.types.IssueRef` carrying the issue's
            ``node_id`` / ``number`` / ``title`` / current ``body``.

        Raises:
            GitHubHTTPError: When the REST GET returns an HTTP error.
        """
        path = f"/repos/{self._repo}/issues/{issue_number}"
        raw = self._rest("GET", path, None)
        data: dict[str, Any] = raw if isinstance(raw, dict) else {}
        # The REST issue payload carries a ``labels`` array; carry its names so the
        # skiff fast-track override (``set_issue_track_label``) can read the current
        # ``track:*`` labels. ``labels`` may be absent (older/partial payload) → "".
        labels = tuple(str(label["name"]) for label in (data.get("labels") or []))
        return IssueRef(
            node_id=str(data.get("node_id", "")),
            number=int(data.get("number", issue_number)),
            title=str(data.get("title", "")),
            # GitHub returns ``body: null`` for an empty body — normalise to "".
            body=str(data.get("body") or ""),
            labels=labels,
        )

    def update_issue_body(self, issue_node_id: str, body: str) -> None:
        """Patch an issue's body (``seed`` materialises ``Depends on #N``).

        Args:
            issue_node_id: The global node id of the issue to patch.
            body: The new markdown body.
        """
        data = self._graphql(_queries.update_issue_body(issue_node_id, body))
        raise_for_errors(data)

    def close_issue(self, issue_node_id: str) -> None:
        """Close an issue by its global node id (cockpit PR3 ``ticket_close``).

        Routes through :attr:`_graphql`, inheriting the client's mandatory connect+read timeouts.

        Args:
            issue_node_id: The global node id of the issue to close.

        Raises:
            GraphQLError: When the mutation response carries errors.
        """
        data = self._graphql(_queries.close_issue(issue_node_id))
        raise_for_errors(data)

    def add_to_project(self, project_id: str, issue_node_id: str) -> str:
        """Add an issue (by content node id) to a project; return the item id.

        Args:
            project_id: The ``ProjectV2`` node id to add the issue to.
            issue_node_id: The issue's global content node id.

        Returns:
            The new ``ProjectV2Item`` node id.
        """
        data = self._graphql(_queries.add_item_to_project(project_id, issue_node_id))
        return _parsers.parse_added_item(data)

    def _status_option_counts(self, project_id: str) -> dict[str, int]:
        """Count cards per Status column across ALL items (cursor-paginated).

        Protects non-empty columns from being dropped by :meth:`ensure_columns`.
        Items with no Status value contribute nothing (they cannot pin a column
        open).

        Args:
            project_id: The ``ProjectV2`` node id whose items to count.

        Returns:
            A ``{column_name: card_count}`` map over every item with a Status.
        """
        counts: dict[str, int] = {}
        after: str | None = None
        max_pages = 10  # 1000 items — well beyond any realistic board

        for _ in range(max_pages):
            data = self._graphql(_queries.project_item_statuses(project_id, after=after))
            names, has_next, end_cursor = _parsers.parse_item_status_page(data)
            for name in names:
                counts[name] = counts.get(name, 0) + 1
            if not has_next:
                break
            if not end_cursor:
                # hasNextPage is true but endCursor is absent — malformed response,
                # or empty page. Stop rather than loop forever on the same page.
                break
            if end_cursor == after:
                # The cursor did not advance — broken server or fixture, stop.
                break
            after = end_cursor
        return counts

    def status_field_node_id(self, project_id: str) -> str:
        """Return the Status single-select field node id for ``project_id``.

        Used by ``kanban init`` to record the field id in ``projects.json`` so
        the daemon can match Status moves against it. A thin read over the same
        fields query :meth:`ensure_columns` uses.

        Args:
            project_id: The ``ProjectV2`` node id whose Status field to resolve.

        Returns:
            The Status single-select field node id.

        Raises:
            ValueError: When the project has no Status single-select field.
        """
        data = self._graphql(_queries.status_option_map(project_id))
        return _parsers.parse_status_field_id(data)

    def status_options(self, project_id: str) -> dict[str, str]:
        """Return the board's ``{option_name: option_id}`` Status-option map.

        This is the ``kanban seed`` Backlog-landing guard's option probe:
        ``cli/seed.py:_known_status_options`` calls it via
        ``getattr(seeder, "status_options", None)`` so the pre-check can confirm a
        ``Backlog`` Status option exists BEFORE any issue is created — including on
        the explicit ``--project-id`` path where no registry ``option_map`` is
        available (without this method the probe would not resolve on the real
        client and that path would half-seed). It is also the ``BoardReader``-adjacent
        Status introspection over the same fields query :meth:`ensure_columns` and
        :meth:`status_field_node_id` read. The GraphQL request inherits the client's
        mandatory connect + read timeouts via :meth:`_graphql` (no untimed path).

        Args:
            project_id: The ``ProjectV2`` node id whose Status options to read.

        Returns:
            A ``{option_name: option_id}`` map in board order, or an empty map when
            the project has no Status single-select field.
        """
        data = self._graphql(_queries.status_option_map(project_id))
        return _parsers.parse_status_option_map(data)

    # ---- internals ----
    def _resolve_status_field(self) -> StatusField:
        """Resolve and cache the project's Status field (id + option map).

        Returns:
            The cached :class:`StatusField`, fetched once on first move.
        """
        if self._status_field is None:
            data = self._graphql(_queries.status_option_map(self._project_id))
            self._status_field = _parsers.parse_status_field(data)
        return self._status_field
