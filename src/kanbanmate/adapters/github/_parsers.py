"""Pure response PARSERS for GitHub replies (ported from the PoC). No I/O.

Each parser takes a decoded JSON dict (as returned by the GraphQL transport) and
returns an adapter value object (:mod:`.types`) or a primitive. They raise
:class:`GraphQLError` on a non-empty ``errors`` array so a failed mutation never
passes silently. Exercised against fixture JSON in tests; the live transport is a
thin injected callable on :class:`~.client.GithubClient`.
"""

from __future__ import annotations

from typing import Any

from kanbanmate.adapters.github.types import CommentRef, IssueContext, RawItem, StatusField


def parse_issue_comments(data: list[dict[str, Any]]) -> list[CommentRef]:
    """Parse a REST ``list issue comments`` array into :class:`CommentRef` records.

    The REST ``GET /repos/{owner}/{repo}/issues/{n}/comments`` endpoint returns a
    JSON *array* (not a wrapped object), so the transport hands this parser a list.
    Each element carries a numeric ``id`` and a ``body``; the sticky-comment logic
    (DESIGN §8.1) needs only those two to relocate its per-step marker.

    Args:
        data: The decoded REST response — a list of comment objects.

    Returns:
        A :class:`CommentRef` per comment, in the order GitHub returns them. A
        comment missing an ``id`` is skipped (it cannot be edited in place).
    """
    refs: list[CommentRef] = []
    for raw in data:
        comment_id = raw.get("id")
        if comment_id is None:
            continue
        refs.append(CommentRef(comment_id=int(comment_id), body=str(raw.get("body") or "")))
    return refs


class GraphQLError(RuntimeError):
    """Raised when a GraphQL response carries a non-empty ``errors`` array."""


class GitHubHTTPError(RuntimeError):
    """Raised when GitHub returns an HTTP status >= 400.

    Carries the HTTP status and the decoded error body so the operator sees the
    real GitHub diagnosis (e.g. ``{"message": "Bad credentials"}``) instead of a
    bare ``HTTP Error 401``.

    Attributes:
        status: The HTTP status code.
        body: The decoded response body.
    """

    def __init__(self, status: int, body: str):
        """Build the error from the HTTP status and decoded body.

        Args:
            status: The HTTP status code (>= 400).
            body: The decoded error response body.
        """
        self.status = status
        self.body = body
        super().__init__(f"GitHub HTTP {status}: {body}")


def raise_for_errors(data: dict[str, Any]) -> dict[str, Any]:
    """Return ``data`` unchanged, or raise on a non-empty ``errors`` array.

    Args:
        data: A decoded GraphQL response.

    Returns:
        The same ``data`` dict when no errors are present.

    Raises:
        GraphQLError: When ``data["errors"]`` is non-empty.
    """
    errors = data.get("errors")
    if errors:
        messages = "; ".join(str(e.get("message", e)) for e in errors)
        raise GraphQLError(messages)
    return data


def parse_cheap_probe(data: dict[str, Any]) -> str:
    """Build an opaque change-detection token from a cheap-probe response.

    The token is the newline-joined, SORTED ``updatedAt`` timestamps of every item
    (the query reads the first page, up to 100). Sorting makes the token independent
    of GitHub's return order, so it is stable when the board is unchanged and flips
    whenever any item's ``updatedAt`` changes (a move/edit) or an item is added/removed.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.cheap_probe` response.

    Returns:
        An opaque token string; ``""`` for an empty board (a stable token).

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    items = ((data.get("data") or {}).get("node") or {}).get("items") or {}
    nodes = items.get("nodes") or []
    stamps = sorted(str((node or {}).get("updatedAt") or "") for node in nodes)
    return "\n".join(stamps)


def _content_fields(content: dict[str, Any] | None) -> tuple[int | None, str, str]:
    """Extract ``(issue_number, title, body)`` from a project item's ``content`` node.

    Draft items and non-Issue content (e.g. a PullRequest) have no issue number;
    a draft still carries a title. Only Issue content carries a body — the
    dependency gate (DESIGN §9) parses ``Depends on #N`` from it, so a draft/PR
    yields an empty body.

    Args:
        content: The decoded ``content`` node of a project item, or ``None``.

    Returns:
        A ``(issue_number, title, body)`` triple; ``issue_number`` and ``body``
        are ``None``/empty unless the content is an Issue.
    """
    content = content or {}
    title = str(content.get("title") or "")
    number = content.get("number")
    is_issue = content.get("__typename") == "Issue"
    issue_number = int(number) if is_issue and number is not None else None
    # The body is only meaningful for an Issue; a draft/PR has none, so default to "".
    body = str(content.get("body") or "") if is_issue else ""
    return issue_number, title, body


def parse_board_items(data: dict[str, Any]) -> tuple[tuple[RawItem, ...], bool, str | None]:
    """Parse one board-items page into raw items plus pagination state.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.board_items` response.

    Returns:
        A triple ``(items, has_next_page, end_cursor)`` where ``items`` is a tuple
        of :class:`~kanbanmate.adapters.github.types.RawItem`.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    items_node = ((data.get("data") or {}).get("node") or {}).get("items") or {}
    page_info = items_node.get("pageInfo") or {}
    raw: list[RawItem] = []
    for node in items_node.get("nodes") or []:
        if not node or not node.get("id"):
            continue
        status_value = node.get("fieldValueByName") or {}
        issue_number, title, body = _content_fields(node.get("content"))
        raw.append(
            RawItem(
                item_id=str(node["id"]),
                issue_number=issue_number,
                title=title,
                status_column=str(status_value.get("name") or ""),
                updated_at=str(node.get("updatedAt") or ""),
                body=body,
            )
        )
    return tuple(raw), bool(page_info.get("hasNextPage")), page_info.get("endCursor")


def parse_status_field(data: dict[str, Any]) -> StatusField:
    """Parse the Status single-select field id + options from a fields response.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.status_option_map`
            response.

    Returns:
        A :class:`~kanbanmate.adapters.github.types.StatusField` with the field id
        and a ``{column_name: option_id}`` mapping.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
        ValueError: When the project has no Status single-select field.
    """
    raise_for_errors(data)
    nodes = (((data.get("data") or {}).get("node") or {}).get("fields") or {}).get("nodes") or []
    for field in nodes:
        if field and field.get("name") == "Status" and "options" in field:
            options = {str(opt["name"]): str(opt["id"]) for opt in field["options"]}
            return StatusField(field_id=str(field["id"]), options=options)
    raise ValueError("no Status single-select field on this project")


def parse_issue_context(data: dict[str, Any]) -> IssueContext:
    """Return an :class:`IssueContext` from an ``issue_context`` GraphQL response.

    Ported from the PoC ``_parsers.py:226-261``. Drills every level defensively
    (``or {}``) so a partially-incomplete response never crashes. The returned
    :class:`IssueContext` is a frozen, hashable value object (consistent with NEW's
    other adapter records).

    Args:
        data: Decoded JSON response from the ``issue_context`` GraphQL query.

    Returns:
        An :class:`IssueContext` with the issue body, up to 50 comment bodies, and
        the first cross-referenced Issue body (or ``None``).

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    issue = ((data.get("data") or {}).get("repository") or {}).get("issue") or {}
    body = str(issue.get("body") or "")
    comments: list[str] = [
        str(node["body"])
        for node in ((issue.get("comments") or {}).get("nodes") or [])
        if node and node.get("body") is not None
    ]
    linked_issue_body: str | None = None
    for node in (issue.get("timelineItems") or {}).get("nodes") or []:
        if not node:
            continue
        source = node.get("source") or {}
        src_body = source.get("body")
        if src_body is not None:
            linked_issue_body = str(src_body)
            break
    return IssueContext(body=body, comments=tuple(comments), linked_issue_body=linked_issue_body)


def parse_issue_closed(data: dict[str, Any]) -> bool:
    """Return ``True`` iff the issue's state is ``CLOSED`` (closed/merged satisfy a dependency).

    Ported from the PoC ``_parsers.py:149-153``. Drills every level defensively
    (``or {}``) so a partially-incomplete response never crashes. A missing or
    empty ``state`` field returns ``False`` — conservative: an undecidable issue
    is NOT treated as done (the #13 dependency gate must not falsely satisfy a
    dependency on a phantom/missing issue).

    Args:
        data: Decoded JSON response from the ``issue_state`` GraphQL query.

    Returns:
        ``True`` when the issue's state equals ``"CLOSED"`` (case-insensitive);
        ``False`` for ``"OPEN"``, a missing ``state``, or a missing issue node.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    issue = ((data.get("data") or {}).get("repository") or {}).get("issue") or {}
    return str(issue.get("state") or "").upper() == "CLOSED"


# ---------------------------------------------------------------------------
# Seeder parsers (consumed by ``kanban init`` / ``kanban seed``, DESIGN §4.3).
# ---------------------------------------------------------------------------


def parse_org_id(data: dict[str, Any]) -> str:
    """Return the organization's global node id from an ``org_id`` response.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.org_id` response.

    Returns:
        The organization's node id.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    org = (data.get("data") or {}).get("organization") or {}
    return str(org["id"])


def parse_find_org_project(data: dict[str, Any], *, title: str) -> str | None:
    """Return the id of the org Project v2 whose title equals ``title``, else ``None``.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.find_org_project`
            response.
        title: The project title to match.

    Returns:
        The matching project's node id, or ``None`` when no title matches.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    nodes = (((data.get("data") or {}).get("organization") or {}).get("projectsV2") or {}).get(
        "nodes"
    ) or []
    for node in nodes:
        if (node or {}).get("title") == title:
            return str(node["id"])
    return None


def parse_created_project(data: dict[str, Any]) -> str:
    """Return the new Project v2 id from a ``create_project`` response.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.create_project`
            response.

    Returns:
        The created project's node id.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    return str(((data.get("data") or {}).get("createProjectV2") or {})["projectV2"]["id"])


def parse_created_status_update(data: dict[str, Any]) -> str:
    """Return the new status-update id from a ``create_status_update`` response.

    Args:
        data: A decoded
            :func:`kanbanmate.adapters.github._queries.create_status_update`
            response.

    Returns:
        The created ``ProjectV2StatusUpdate`` node id (the rolling dashboard's
        id the daemon persists so later refreshes ``update`` rather than
        re-create — phase-24 §24.2).

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    created = (data.get("data") or {}).get("createProjectV2StatusUpdate") or {}
    return str(created["statusUpdate"]["id"])


def parse_project_short_description(data: dict[str, Any]) -> str:
    """Return a project's current ``shortDescription`` from a read response, or ``""``.

    Backs the ``kanban init`` idempotency check (phase-33): the setter writes a
    default description ONLY when this returns an empty string. A null/absent value
    degrades to ``""`` so a never-described project reads as empty.

    Args:
        data: A decoded
            :func:`kanbanmate.adapters.github._queries.project_short_description`
            response.

    Returns:
        The project's current short description, or ``""`` when none is set.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    node = (data.get("data") or {}).get("node") or {}
    return str(node.get("shortDescription") or "")


def parse_status_option_map(data: dict[str, Any]) -> dict[str, str]:
    """Parse the Status field's options into ``{column_name: option_id}`` (board order).

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.status_option_map`
            response.

    Returns:
        The ``{name: option_id}`` map of the Status field, or ``{}`` when no Status
        single-select field is present.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    nodes = (((data.get("data") or {}).get("node") or {}).get("fields") or {}).get("nodes") or []
    for field in nodes:
        if field and field.get("name") == "Status" and "options" in field:
            return {str(opt["name"]): str(opt["id"]) for opt in field["options"]}
    return {}


def parse_status_field_id(data: dict[str, Any]) -> str:
    """Return the Status single-select field node id from a fields response.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.status_option_map`
            response.

    Returns:
        The Status field node id.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
        ValueError: When the project has no Status single-select field.
    """
    raise_for_errors(data)
    nodes = (((data.get("data") or {}).get("node") or {}).get("fields") or {}).get("nodes") or []
    for field in nodes:
        if field and field.get("name") == "Status" and "options" in field:
            return str(field["id"])
    raise ValueError("no Status single-select field on this project")


def parse_item_status_page(data: dict[str, Any]) -> tuple[list[str], bool, str | None]:
    """Return ``(status_names, has_next_page, end_cursor)`` from an items page.

    ``status_names`` carries one column name per item that HAS a Status value; items
    with no status are skipped (a column with zero cards is safe to drop).

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.project_item_statuses`
            response.

    Returns:
        A triple of the per-item Status names, the pagination flag, and the cursor.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    items = ((data.get("data") or {}).get("node") or {}).get("items") or {}
    page = items.get("pageInfo") or {}
    names: list[str] = []
    for node in items.get("nodes") or []:
        value = (node or {}).get("fieldValueByName") or {}
        name = value.get("name")
        if name:
            names.append(str(name))
    return names, bool(page.get("hasNextPage")), page.get("endCursor")


def parse_updated_field_options(data: dict[str, Any]) -> dict[str, str]:
    """Return ``{option_name: option_id}`` from an ``update_status_field_options`` response.

    Args:
        data: A decoded
            :func:`kanbanmate.adapters.github._queries.update_status_field_options` response.

    Returns:
        The refreshed ``{name: option_id}`` map of the field's options.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    field = ((data.get("data") or {}).get("updateProjectV2Field") or {}).get("projectV2Field") or {}
    return {str(opt["name"]): str(opt["id"]) for opt in (field.get("options") or [])}


def parse_repo(data: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Return ``(repository_node_id, {label_name: label_id})`` from a ``repo_id`` response.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.repo_id` response.

    Returns:
        The repository node id and its existing ``{label_name: label_id}`` map.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    repo = (data.get("data") or {}).get("repository") or {}
    labels = {str(n["name"]): str(n["id"]) for n in ((repo.get("labels") or {}).get("nodes") or [])}
    return str(repo["id"]), labels


def parse_created_label(data: dict[str, Any]) -> tuple[str, str]:
    """Return ``(label_node_id, label_name)`` from a ``create_label`` response.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.create_label` response.

    Returns:
        The created label's node id and name.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    label = ((data.get("data") or {}).get("createLabel") or {}).get("label") or {}
    return str(label["id"]), str(label["name"])


def parse_created_issue(data: dict[str, Any]) -> tuple[str, int]:
    """Return ``(issue_node_id, issue_number)`` from a ``create_issue`` response.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.create_issue` response.

    Returns:
        The created issue's node id and number.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    issue = ((data.get("data") or {}).get("createIssue") or {}).get("issue") or {}
    return str(issue["id"]), int(issue["number"])


def parse_added_item(data: dict[str, Any]) -> str:
    """Return the new project item id from an ``add_item_to_project`` response.

    Args:
        data: A decoded :func:`kanbanmate.adapters.github._queries.add_item_to_project`
            response.

    Returns:
        The new ``ProjectV2Item`` node id.

    Raises:
        GraphQLError: When the response carries a non-empty ``errors`` array.
    """
    raise_for_errors(data)
    item = ((data.get("data") or {}).get("addProjectV2ItemById") or {}).get("item") or {}
    return str(item["id"])
