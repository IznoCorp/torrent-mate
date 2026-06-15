"""Board ports: the GitHub-Projects-v2 read/write boundary.

These Protocols describe what the application needs from the board without
binding it to any transport. The production adapter (:mod:`kanbanmate.adapters.github`)
implements them over a urllib GraphQL/REST client with mandatory connect/read
timeouts; tests inject fakes that return fixture data.

Split rationale (interface segregation): the daemon's read path (probe +
snapshot) and write path (move + comment) have different callers and different
failure modes, so they are two Protocols. An adapter may satisfy both.
"""

from __future__ import annotations

from typing import Protocol

from kanbanmate.adapters.github.types import CommentRef, IssueContext, IssueRef
from kanbanmate.core.domain import BoardSnapshot


class BoardReader(Protocol):
    """Read side of the board: cheap change-detection plus full snapshots.

    The daemon polls :meth:`cheap_probe` frequently and only pays for a full
    :meth:`snapshot` when the probe token changes, keeping API cost bounded.
    """

    def cheap_probe(self) -> str:
        """Return a cheap change-detection token for the board.

        The token is opaque and compared for equality only: when it is
        unchanged between polls the board is assumed unchanged and no snapshot
        is fetched. A natural implementation is the board's latest item
        ``updatedAt`` timestamp.

        Returns:
            An opaque token whose change signals the board may have moved.
        """
        ...

    def snapshot(self) -> BoardSnapshot:
        """Fetch the current full state of the board.

        Returns:
            A :class:`~kanbanmate.core.domain.BoardSnapshot` capturing every
            visible item and the fetch timestamp. The adapter is responsible
            for following GraphQL pagination so the snapshot is complete.
        """
        ...

    def issue_state(self, number: int) -> bool:
        """Return ``True`` iff the issue is CLOSED — the live fallback for an off-board dependency.

        The phase-17 #13 dependency gate calls this to resolve ``Depends on #N``
        references the board snapshot cannot decide (absent from the board).
        A closed/merged issue satisfies its dependent; an open, missing, or
        unresolved issue returns ``False`` (conservative: undecidable is NOT
        treated as done).

        Args:
            number: The issue number whose open/closed state to probe.

        Returns:
            ``True`` when the issue is closed/merged; ``False`` otherwise.
        """
        ...

    def issue_context(self, number: int) -> IssueContext:
        """Gather an issue's body, comment history, and first linked-issue body for prompt context.

        Backs the launch-prompt enrichment (DESIGN §5.2 / PoC ``runner.py:663-704``): the
        Design/launch prompt fills ``{{issue_body}}`` from the first cross-referenced linked
        issue and ``{{comments}}`` from the full comment history. The production
        :class:`~kanbanmate.adapters.github.client.GithubClient` already implements this
        (``client.py:588``) over a single timed GraphQL call — phase 16.1 ported it faithfully
        but left it unwired (zero consumers, off every port); this method closes that M1b gap so
        :meth:`kanbanmate.app.actions.LaunchAction._launch_context` has a real consumer.

        ``IssueContext`` is an adapter value object named here because a ``ports`` Protocol may
        reference adapter records (the :meth:`BoardWriter.list_issue_comments` ↔ ``CommentRef``
        precedent) — only ``core`` may not (the downward-only import guard).

        Args:
            number: The GitHub issue number whose rich context to fetch.

        Returns:
            An :class:`~kanbanmate.adapters.github.types.IssueContext` carrying the issue body,
            comment bodies (≤50, chronological), and the first linked-issue body (or ``None``).
        """
        ...


class BoardWriter(Protocol):
    """Write side of the board: move cards and comment on issues.

    Both operations are issued by the dispatcher (never by a launched agent
    targeting an agent column — that is refused upstream by ``kanban-move``).
    """

    def move_card(self, item_id: str, column_key: str) -> None:
        """Move the card ``item_id`` into the column identified by ``column_key``.

        The adapter resolves ``column_key`` to the project's Status single-select
        option id internally; callers in :mod:`kanbanmate.core`/``app`` only ever
        speak in stable column keys, never in GitHub option ids.

        Args:
            item_id: The opaque ``ProjectV2Item`` node id of the card to move.
            column_key: The stable key of the destination column.
        """
        ...

    def comment(self, issue_number: int, body: str) -> None:
        """Post a comment on the issue numbered ``issue_number``.

        Args:
            issue_number: The GitHub issue number to comment on.
            body: The markdown comment body.
        """
        ...

    def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
        """List the comments on the issue numbered ``issue_number``.

        Backs the rich stage-sticky upsert (DESIGN §8.1): the app-layer producers
        scan the returned bodies for a per-stage HTML marker to decide whether to
        edit an existing sticky or create a fresh one. ``CommentRef`` is an adapter
        value object named here because a ``ports`` Protocol may reference adapter
        records — only ``core`` may not (the downward-only import guard).

        Args:
            issue_number: The GitHub issue number whose comments to list.

        Returns:
            One :class:`~kanbanmate.adapters.github.types.CommentRef` per comment,
            in GitHub's return order.
        """
        ...

    def update_comment(self, comment_id: int, body: str) -> None:
        """Edit an existing issue comment in place (the other half of the upsert).

        Once a marked sticky is located via :meth:`list_issue_comments`, its body is
        rewritten so each ``(ticket, stage)`` keeps a single comment that updates over
        time rather than spamming the timeline (DESIGN §8.1).

        Args:
            comment_id: The integer REST comment id to edit (from a ``CommentRef``).
            body: The new markdown comment body.
        """
        ...


class PullRequests(Protocol):
    """Pull-request close side of the board (Cancel teardown only; DESIGN §8.2).

    A small, dedicated port (interface segregation) so the Cancel teardown
    depends only on the single capability it uses — closing the open PR for a
    branch — and never on the full board write surface. The production
    :class:`~kanbanmate.adapters.github.client.GithubClient` satisfies it
    alongside :class:`BoardReader`/:class:`BoardWriter`, so one client instance
    is wired into all three slots (DESIGN §3.3).
    """

    def close_open_pr_for_branch(self, head_branch: str) -> int | None:
        """Close the open PR for ``head_branch``; KEEP the remote branch.

        Find-then-close: closing a PR does **not** delete its head ref, so the
        remote branch is kept (the operator-decided Cancel semantics, DESIGN
        §8.2). A no-op when no open PR exists or the branch is ``""``/``"HEAD"``.
        This is the single call :class:`~kanbanmate.app.actions.TeardownAction`
        makes through this port.

        Args:
            head_branch: The remote branch name (e.g. ``feat/genesis``).

        Returns:
            The closed PR number, or ``None`` when there was nothing to close.
        """
        ...


class Seeder(Protocol):
    """Per-repo bootstrap side of the board: project / label / issue creation.

    Used **only** by the per-repo installer tier (``kanban init`` / ``kanban
    seed``, DESIGN §4.3) — never by the polling daemon, whose hot path is
    read/move/comment. The methods are split out from :class:`BoardWriter`
    (interface segregation): a different caller, a one-shot lifecycle, and a
    distinct failure mode (a failed ``init`` is operator-fixed, not retried in a
    tick). All operations are idempotent where GitHub allows it so a re-run of
    ``init`` converges rather than duplicating.

    DESIGN §3.3 names this port ``Seeder{create_issue, add_to_project,
    ensure_labels}``; the concrete shape below adds the project + Status-option
    bootstrap that ``init`` needs (the PoC ``Seeder`` capability was deferred
    from sub-phase 1.7 and lands here).
    """

    def ensure_project(self, org: str, title: str) -> str:
        """Idempotently ensure an org Project v2 named ``title`` exists.

        A fresh org Project is created when none of the given title is found
        (DESIGN §4.3: a transferred repo does **not** migrate a personal
        Project, so ``init`` materialises a clean org board).

        Args:
            org: The organization login that owns the project.
            title: The project title to find-or-create.

        Returns:
            The ``ProjectV2`` node id (the ``projects.json`` registry key).
        """
        ...

    def link_to_repo(self, project_id: str, repo: str) -> None:
        """Link Project v2 ``project_id`` to ``repo`` (``owner/name``).

        ``kanban init`` calls this so the org board appears in the repository's Projects tab —
        the canonical repo↔project association. Idempotent on GitHub's side.

        Args:
            project_id: The ``ProjectV2`` node id to link.
            repo: The ``owner/name`` slug of the repository to link to.
        """
        ...

    def update_project_description(self, project_id: str, short_description: str) -> None:
        """Set ``project_id``'s short description when it is empty (phase-33).

        ``kanban init`` gives a fresh board a default one-line description. The
        operation is idempotent: the concrete client reads the current value first
        and SKIPS the write when a description already exists, so an
        operator-authored description is never overwritten and a re-run is a no-op.

        Args:
            project_id: The ``ProjectV2`` node id whose short description to set.
            short_description: The default one-line description to write when the
                project has none.
        """
        ...

    def ensure_columns(self, project_id: str, columns: list[str]) -> dict[str, str]:
        """Ensure the project's auto Status field carries exactly ``columns``.

        Reuses the single Status single-select field GitHub auto-creates on a
        new Project v2 (DESIGN §4.3 — *reuse the auto Status field*) and makes
        its option set equal ``columns`` in board order, preserving existing
        option ids so cards are never orphaned.

        Args:
            project_id: The ``ProjectV2`` node id whose Status field to shape.
            columns: The desired column names, in board order.

        Returns:
            A ``{column_name: option_id}`` map for the requested columns.
        """
        ...

    def ensure_labels(self, repo: str, labels: list[str]) -> dict[str, str]:
        """Idempotently ensure every label in ``labels`` exists on ``repo``.

        Missing labels are created; existing ones are reused (DESIGN §4.3 —
        the ``wave:*`` / ``prio:*`` routing labels).

        Args:
            repo: The ``owner/name`` repository slug.
            labels: The label names to find-or-create.

        Returns:
            A ``{label_name: label_id}`` map for the requested labels.
        """
        ...

    def create_issue(self, repo: str, title: str, body: str, labels: list[str]) -> tuple[str, int]:
        """Create an issue on ``repo`` (creating any missing labels first).

        Args:
            repo: The ``owner/name`` repository slug.
            title: The issue title.
            body: The issue body (markdown).
            labels: Label names to apply (created on demand, never dropped).

        Returns:
            A ``(issue_node_id, issue_number)`` pair for the created issue.
        """
        ...

    def update_issue_body(self, issue_node_id: str, body: str) -> None:
        """Replace an issue's body (``seed`` rewrites ``Depends on #N`` refs).

        Args:
            issue_node_id: The global node id of the issue to patch.
            body: The new markdown body.
        """
        ...

    def close_issue(self, issue_node_id: str) -> None:
        """Close an issue by its global node id (cockpit PR3 ``ticket_close``).

        Args:
            issue_node_id: The global node id of the issue to close.
        """
        ...

    def fetch_issue(self, issue_number: int) -> IssueRef:
        """Read an issue's identity + body by NUMBER (resolves number → node id).

        Backs the cockpit ``ticket_edit`` / ``ticket_close`` executors, which carry an issue NUMBER
        but need its global ``node_id`` for the patch/close mutations.

        Args:
            issue_number: The issue number in the board's repository.

        Returns:
            An :class:`~kanbanmate.adapters.github.types.IssueRef` (``node_id`` / ``number`` /
            ``title`` / ``body``).
        """
        ...

    def add_to_project(self, project_id: str, issue_node_id: str) -> str:
        """Add an issue (by content node id) to a project. Returns the item id.

        Args:
            project_id: The ``ProjectV2`` node id to add the issue to.
            issue_node_id: The issue's global content node id.

        Returns:
            The new ``ProjectV2Item`` node id.
        """
        ...

    def move_card(self, item_id: str, column_key: str) -> None:
        """Set a project item's Status column.

        The seeder uses this to place each freshly-added item into ``Backlog``:
        GitHub Projects v2 adds items with NO Status, so the column must be set
        explicitly (there is no "default column on add"). Same signature as
        :meth:`BoardWriter.move_card`; the concrete client satisfies both.

        Args:
            item_id: The ``ProjectV2Item`` node id to move.
            column_key: The destination column key (a Status option name).
        """
        ...


class ProjectStatusReporter(Protocol):
    """Rolling project status-update side of the board (the live dashboard).

    A small, dedicated port (interface segregation) so the on-change status
    reporter depends only on the two capabilities it uses — creating the rolling
    status update once and refreshing it by id thereafter — and never on the full
    board write surface. The production
    :class:`~kanbanmate.adapters.github.client.GithubClient` satisfies it alongside
    :class:`BoardReader`/:class:`BoardWriter`, so one client instance is wired into
    this slot too (DESIGN §3.3).

    KanbanMate keeps ONE *rolling* status update in the Project's "Status updates"
    section (phase-24): the first post is a :meth:`create_status_update` (whose id
    is persisted), and every subsequent on-change refresh is an
    :meth:`update_status_update` of that id — never a new pill per tick. Both
    operations are fail-soft at the call site (a posting error is observability,
    NEVER a launch blocker), but the adapter still raises on a GraphQL error so the
    caller can decide to swallow it.
    """

    def create_status_update(self, project_id: str, body: str, status: str) -> str:
        """Create the rolling status update on ``project_id``; return its node id.

        The FIRST post: it materialises the status update in the project's "Status
        updates" section. The returned id is persisted by the caller so later
        on-change refreshes call :meth:`update_status_update` (not create) and the
        project shows a single rolling pill (phase-24 §24.2).

        Args:
            project_id: The ``ProjectV2`` node id to post the status update on.
            body: The markdown status-update body (the rendered dashboard).
            status: A ``ProjectV2StatusUpdateStatus`` enum value (``INACTIVE`` /
                ``ON_TRACK`` / ``AT_RISK`` / ``OFF_TRACK`` / ``COMPLETE``).

        Returns:
            The new ``ProjectV2StatusUpdate`` node id.
        """
        ...

    def update_status_update(self, status_update_id: str, body: str, status: str) -> None:
        """Refresh the existing rolling status update ``status_update_id`` in place.

        The on-change refresh: it rewrites the status update identified by the id
        :meth:`create_status_update` returned, so the project keeps a single
        rolling pill the daemon updates only when the body or status enum changes
        (phase-24 §24.2).

        Args:
            status_update_id: The ``ProjectV2StatusUpdate`` node id to refresh.
            body: The new markdown status-update body.
            status: A ``ProjectV2StatusUpdateStatus`` enum value (``INACTIVE`` /
                ``ON_TRACK`` / ``AT_RISK`` / ``OFF_TRACK`` / ``COMPLETE``).
        """
        ...

    def delete_status_update(self, status_update_id: str) -> None:
        """Delete the orphaned rolling status update ``status_update_id`` (phase-36).

        The self-heal re-create path (an :meth:`update_status_update` of a stale id
        failing → a fresh :meth:`create_status_update`) leaves the OLD update
        lingering in the project's "Status updates" section (observed live: 3
        stacked pills). After a successful re-create the reporter best-effort
        deletes the stale id through this method so the project keeps a single
        rolling pill. The call site swallows any error (a delete failure is
        cosmetic, NEVER a launch blocker), but the adapter still raises on a
        GraphQL error so the caller can decide to log + swallow it.

        Args:
            status_update_id: The orphaned ``ProjectV2StatusUpdate`` node id to delete.
        """
        ...
